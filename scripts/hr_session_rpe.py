"""
scripts/hr_session_rpe.py — attribute Garmin heart rate to individual
exercises and derive a per-exercise HR-based RPE.

WHY THIS EXISTS
───────────────
The training log records per-set completion timestamps and Garmin records a
3-second heart-rate series. Nothing joined them. This does, and prints the
work/rest sawtooth so a session can be read the way it was actually
performed rather than as a single session-level RPE.

WHAT THE RPE MEANS — read before trusting the number
────────────────────────────────────────────────────
It is a CARDIOVASCULAR RPE: how hard an exercise was metabolically. It is
NOT the athlete's set RPE, which measures proximity to failure. The two
genuinely differ and both are real. Heart rate answers to relative effort,
rest density and accumulated fatigue — not to absolute load.

The worked example is 2026-08-06, where Lat Pulldown (159) and Single-Arm DB
Row (163) peaked above a heavier Hip Thrust (149). The athlete's account:
he works closer to true max on the pulls he trusts, the single-arm row is
right-then-left inside ONE logged set with a single minute of rest after
both sides, and the pulls come later under accumulated fatigue. That is the
behaviour this script measures, and it is why the number is offered beside
his own RPE rather than instead of it.

THE TIMESTAMP CAVEAT
────────────────────
Sets logged before 2026-08-07 were stamped with the host's naive clock. On a
UTC host that put every set two hours behind the athlete's wall clock (see
services.sessions.set_timestamp). Rows written after the fix carry an explicit
UTC offset and need no correction. Use --offset-hours for historical rows;
--auto-offset picks the shift that best lands the sets inside the activity.

USAGE
─────
    python scripts/hr_session_rpe.py --date 2026-08-06 --auto-offset
    python scripts/hr_session_rpe.py --date 2026-08-06 --offset-hours 2
    python scripts/hr_session_rpe.py --date 2026-08-06 --hr-max 180

HRmax defaults to the highest plausible reading in the activity, which
UNDER-estimates unless a genuinely maximal effort was recorded — every
intensity derived from it is then overstated. The script says so in its
output rather than hiding it. Pass --hr-max once a real maximum is known.
"""

from __future__ import annotations

import argparse
import bisect
import json
import os
import sys
from datetime import datetime, timedelta
from statistics import median

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import hr_load  # noqa: E402
from services.clients import garmin, notion  # noqa: E402
from services.config import load_config  # noqa: E402
from services.repository import Repository  # noqa: E402

# Heart rate lags effort: the peak of a set routinely lands after the set has
# ended. Without this, a set's true peak gets credited to the rest that
# follows it and every exercise reads easier than it was.
CARDIAC_LAG_SECONDS = 25

# A gap longer than this between one set's end and the next set's completion
# is a transition between exercises, not a working window.
MAX_WORK_WINDOW_SECONDS = 100

# Fallback working-window length for the first set of a session, which has no
# preceding set to measure from.
DEFAULT_FIRST_SET_SECONDS = 55


def _repo() -> Repository:
    """Same bootstrap as the other scripts: secrets.toml, not st.secrets —
    services/ never reads Streamlit (CLAUDE.md key rule 9)."""
    import tomllib
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, ".streamlit", "secrets.toml"), "rb") as fh:
        return Repository(load_config(tomllib.load(fh)))


def fetch_sets(repo: Repository, day: str) -> list[dict]:
    """Every logged exercise for `day` that carries per-set records, in the
    order it was performed."""
    pages = repo._query(
        repo.config.notion_db_training,
        filter_={"property": "Session Date", "date": {"equals": day}},
    )
    out = []
    for p in pages:
        sets = json.loads(notion.get_property(p, "Sets", "rich_text") or "[]")
        sets = [s for s in sets if s.get("ts")]
        if sets:
            out.append({"name": str(notion.get_property(p, "Movement", "title")),
                        "sets": sets})
    out.sort(key=lambda x: x["sets"][0]["ts"])
    return out


def find_activity(repo: Repository, day: str, limit: int = 25) -> dict | None:
    """The Garmin activity covering `day`, longest first — a strength session
    captured as 'indoor_cardio' is still the right activity."""
    acts = [a for a in garmin.get_recent_activities(repo._gc, limit=limit)
            if (a.get("startTimeLocal") or "").startswith(day)]
    return max(acts, key=lambda a: a.get("duration") or 0) if acts else None


class HRSeries:
    """(epoch, bpm) samples with range lookups."""

    def __init__(self, samples: list[tuple[float, float]]):
        self.ts = [t for t, _ in samples]
        self.bpm = [b for _, b in samples]

    def __len__(self) -> int:
        return len(self.ts)

    def between(self, a: float, b: float) -> list[float]:
        return self.bpm[bisect.bisect_left(self.ts, a):bisect.bisect_right(self.ts, b)]

    def at(self, t: float) -> float | None:
        i = bisect.bisect_left(self.ts, t)
        cands = [c for c in (i - 1, i) if 0 <= c < len(self.ts)]
        if not cands:
            return None
        return self.bpm[min(cands, key=lambda k: abs(self.ts[k] - t))]

    def span(self) -> tuple[float, float]:
        return (self.ts[0], self.ts[-1]) if self.ts else (0.0, 0.0)


def build_windows(exercises: list[dict], offset_hours: float) -> list[dict]:
    """One work window per SET, in performed order.

    The stored `ts` is the moment the completion button was tapped, i.e. the
    END of the set — the start is not recorded and has to be reconstructed
    from the previous set's end plus its prescribed rest. That reconstruction
    is the least certain part of this script and is why the output labels the
    window rather than presenting it as measured.
    """
    flat = []
    for ex in exercises:
        for s in ex["sets"]:
            ts = datetime.fromisoformat(s["ts"]) + timedelta(hours=offset_hours)
            flat.append({"exercise": ex["name"], "set_num": s.get("set_num"),
                         "end": ts.timestamp(), "rest": float(s.get("rest") or 60)})
    flat.sort(key=lambda r: r["end"])
    prev_free = None
    for w in flat:
        gap = (w["end"] - prev_free) if prev_free is not None else None
        w["start"] = (prev_free if gap is not None and 0 < gap <= MAX_WORK_WINDOW_SECONDS
                      else w["end"] - DEFAULT_FIRST_SET_SECONDS)
        prev_free = w["end"] + w["rest"]
    return flat


def best_offset(windows_fn, series: HRSeries, candidates=(0, 1, 2, 3, -1)) -> tuple[float, int]:
    """Offset placing the most sets inside the activity. Coverage rather than
    HR contrast: a wrong offset usually puts the sets outside the recording
    entirely, which is unambiguous, whereas contrast differences between
    near-miss offsets are small and easy to over-read."""
    lo, hi = series.span()
    scored = []
    for off in candidates:
        inside = sum(1 for w in windows_fn(off) if lo <= w["end"] <= hi)
        scored.append((inside, -abs(off), off))
    scored.sort(reverse=True)
    return float(scored[0][2]), scored[0][0]


def analyse(windows: list[dict], series: HRSeries, hr_rest: float,
            hr_max: float) -> list[dict]:
    """Per-set HR, then per-exercise aggregation into an HR-derived RPE."""
    for w in windows:
        work = series.between(w["start"], w["end"] + CARDIAC_LAG_SECONDS)
        rest = series.between(w["end"] + CARDIAC_LAG_SECONDS, w["end"] + w["rest"] + 10)
        w["hr_start"] = series.at(w["start"])
        w["hr_peak"] = max(work) if work else None
        w["hr_low"] = min(rest) if rest else None
        w["samples"] = work

    by_ex: dict[str, list[dict]] = {}
    for w in windows:
        by_ex.setdefault(w["exercise"], []).append(w)

    out = []
    for name, ws in by_ex.items():
        samples = [h for w in ws for h in w["samples"]]
        peaks = [w["hr_peak"] for w in ws if w["hr_peak"] is not None]
        rpe = hr_load.exercise_hr_rpe(
            samples, hr_rest=hr_rest, hr_max=hr_max,
            peak_hr=max(peaks) if peaks else None,
        )
        out.append({"exercise": name, "sets": ws, "rpe": rpe,
                    "start": min(w["start"] for w in ws)})
    out.sort(key=lambda r: r["start"])
    return out


def resting_hr(repo: Repository, day: str, window_days: int = 45) -> tuple[float, str]:
    """The athlete's real resting HR, from the Oura/Garmin blend.

    Matters more than it looks. Heart-rate RESERVE divides by (max - rest),
    so an inflated resting value compresses the denominator and overstates
    every intensity. The obvious fallback -- the minimum reading inside the
    activity -- is exactly that trap: on 2026-08-06 it read 73 because the
    athlete never stopped moving, against a true resting HR near 54. That
    single substitution moved Romanian Deadlift from RPE 4.8 to 3.6.

    Prefers the session date's own reading, then the median of the
    surrounding window (one night's RHR is noisy), and only then the
    activity minimum -- which is labelled so it is never mistaken for a
    resting measurement.
    """
    try:
        rows = repo.get_biometric_rolling(days=window_days) or []
    except Exception:
        rows = []
    vals = [(r.date, float(r.resting_heart_rate))
            for r in rows if getattr(r, "resting_heart_rate", None)]
    exact = [v for d, v in vals if d == day]
    if exact:
        return exact[0], f"measured RHR {day}"
    if vals:
        return median([v for _, v in vals]), f"median RHR, last {window_days}d"
    return 0.0, "unavailable"


def _f(v, w=5, dp=0):
    return f"{v:>{w}.{dp}f}" if v is not None else " " * (w - 1) + "-"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", required=True, help="session date, YYYY-MM-DD")
    ap.add_argument("--activity-id", type=int, default=None)
    ap.add_argument("--hr-max", type=float, default=None)
    ap.add_argument("--hr-rest", type=float, default=None)
    ap.add_argument("--offset-hours", type=float, default=0.0,
                    help="correct pre-2026-08-07 naive timestamps")
    ap.add_argument("--auto-offset", action="store_true",
                    help="pick the offset that best lands sets inside the activity")
    ap.add_argument("--sets", action="store_true", help="print every set, not just exercises")
    args = ap.parse_args()

    repo = _repo()

    exercises = fetch_sets(repo, args.date)
    if not exercises:
        print(f"No logged sets with timestamps on {args.date}.")
        return 1

    act_id = args.activity_id
    if act_id is None:
        act = find_activity(repo, args.date)
        if not act:
            print(f"No Garmin activity found on {args.date}.")
            return 1
        act_id = act["activityId"]
        print(f"Activity {act_id}  {act.get('startTimeLocal')}  "
              f"{(act.get('duration') or 0)/60:.1f} min  "
              f"type={act.get('activityType',{}).get('typeKey')}")

    series = HRSeries(repo.garmin_activity_hr_samples(act_id))
    if not len(series):
        print("Activity has no per-sample heart-rate series.")
        return 1
    lo, hi = series.span()
    print(f"HR samples: {len(series)}  "
          f"{datetime.fromtimestamp(lo):%H:%M:%S}-{datetime.fromtimestamp(hi):%H:%M:%S}")

    offset = args.offset_hours
    if args.auto_offset:
        offset, inside = best_offset(lambda o: build_windows(exercises, o), series)
        total = sum(len(e["sets"]) for e in exercises)
        print(f"Auto-offset: {offset:+g}h  ({inside}/{total} sets inside the activity)")

    windows = build_windows(exercises, offset)

    hr_max = args.hr_max or hr_load.estimate_hr_max(series.bpm)
    hr_rest, rest_src = args.hr_rest, "supplied"
    if hr_rest is None:
        hr_rest, rest_src = resting_hr(repo, args.date)
        if not hr_rest:
            hr_rest, rest_src = min(series.bpm), "activity minimum — NOT a resting HR"
    print(f"HRmax used: {hr_max:.0f}{' (observed — see caveat below)' if not args.hr_max else ''}"
          f"   HRrest used: {hr_rest:.0f} ({rest_src})")

    results = analyse(windows, series, hr_rest=hr_rest, hr_max=hr_max)

    print()
    print(f"{'EXERCISE':<34}{'sets':>5}{'meanHR':>8}{'peakHR':>8}{'%HRR':>7}{'HR-RPE':>8}  conf")
    print("-" * 78)
    for r in results:
        m = r["rpe"]
        print(f"{r['exercise'][:34]:<34}{len(r['sets']):>5}"
              f"{_f(m['mean_hr'], 8)}{_f(m['peak_hr'], 8)}"
              f"{_f((m['peak_hrr'] or 0) * 100, 7)}{_f(m['rpe'], 8, 1)}"
              f"  {'yes' if m['confident'] else 'NO'}")
        if args.sets:
            for w in r["sets"]:
                print(f"    set {w['set_num']}  "
                      f"{datetime.fromtimestamp(w['start']):%H:%M:%S}-"
                      f"{datetime.fromtimestamp(w['end']):%H:%M:%S}"
                      f"  start{_f(w['hr_start'])} peak{_f(w['hr_peak'])}"
                      f" rest-low{_f(w['hr_low'])}")

    if not args.hr_max:
        print("\nHRmax was taken from this recording. estimate_hr_max UNDER-estimates "
              "until a\ngenuinely maximal effort is recorded, so every %HRR and RPE above "
              "is an UPPER\nbound. Rows marked conf=NO reached the assumed ceiling. "
              "Pass --hr-max when known.")
    print("This is a CARDIOVASCULAR RPE (metabolic demand), not proximity to failure.\n"
          "Compare it against your own set RPE; do not replace one with the other.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
