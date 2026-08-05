"""The Sleep Cycle (iOS) export measured against Oura and Garmin.

READ-ONLY. Runs no sync and writes nothing. Run it offline so it costs zero
API calls, including the service-account auth handshake:

    HEALTH_DATASTORE_PATH=datastore.db .\\venv\\Scripts\\python.exe \\
        scripts\\compare_sleepcycle_to_devices.py

Sleep Cycle infers sleep from the iPhone microphone and accelerometer and
relays a few fields from Apple HealthKit. The question this answers is
whether it is worth continuing to record — not whether it is "accurate",
which is unanswerable: Oura is itself a consumer PPG/actigraphy device, so
every disagreement below is two instruments' distance from an absent truth.
The vocabulary is therefore bias / limits of agreement / disagreement, never
accuracy or error. Same stance as biometrics.hrv_agreement and
sleep_fusion.agreement: measured, shown, never mistaken for truth.

THE BAR, pre-registered (see THRESHOLDS below): a channel survives only if
it could STAND IN FOR the device measurement on a night no device recorded.
That needs a bias small enough to matter and stable enough that a constant
offset fixes it — so limits of agreement decide, not r. Every threshold's
justification is derived from an engine decision granularity or an existing
project constant, never from an observed value in this data.

No p-value is a decision criterion anywhere here. There are ~30 comparisons
across 12 channels and multiplicity would eat any alpha, so decisions are
made on effect size against a pre-registered threshold with a bootstrap 95%
CI. Nothing in services/ uses a p-value either. The p-values that ARE
printed (the partner battery) are descriptive companions to an effect size.

--------------------------------------------------------------------------
MEASURED 2026-08-05 — 299 nights 2024-10-31 -> 2026-07-23, n=43 paired vs
Oura, n=168 vs Garmin. MEASUREMENT VERDICT: keep recording, do not ingest.
ATHLETE'S DECISION 2026-08-05: STOP RECORDING — CONSIDERED AND NOT
IMPLEMENTED. Nothing here beats wearing the ring and the watch, and the
coverage archive that was the whole remaining case shrank from 245 unique
nights to 119 once Garmin's own history was backfilled. This script is
retained because it is re-runnable at zero cost and because these numbers
exist nowhere else — Input_files/ is gitignored. It is a closed question,
not a dormant one.

The structural findings decided most channels before any statistic ran, and
they are facts about the file that no sample size or regime change affects:

  S1  `Time in bed` == End - Start to a median of 0.00s. It is the RECORDING
      WINDOW — opened by hand, usually closed by the alarm (Normal on
      233/308) — not a measurement of anything.
  S2  Awake+Light+Deep+Dream == `Time in bed` to 0.1s, and Light+Deep+Dream
      == `Time asleep` exactly. So AWAKE IS A RESIDUAL of S1's window and
      every duration, efficiency, latency and stage number inherits every
      error in a window the user defines.
  S4  `Snore time` > 0 and `Breathing disruptions` > 0 are the IDENTICAL 180
      nights — crosstab 180/128, zero off-diagonal. One detector, two
      readouts. They are not two channels and can never corroborate.
  S6  INSTRUMENT REGIME BREAK. Mean ambient noise steps ~23.5 dB (2024-11 ->
      2025-09) to ~19.5 dB (2025-11 -> 2026-07) across a recording hole. The
      record is at least two phones. 40 of the 43 Oura-paired nights are in
      the OLD regime; essentially every orphan night is in the NEW one — so
      no coefficient fitted here may be applied there. Same prohibition as
      sleep_movement.py's "do NOT pool 645 and 265 nights".
  S7  No time series anywhere: all 29 columns are night-level scalars. A
      nightly scalar cannot enter sleep_movement.py's 30-second grid or
      sleep_fusion's +/-3-minute rules AT ANY AGREEMENT LEVEL.
  S8  `Steps` is a daily HealthKit total repeated across same-day rows, and
      `Heart rate` is non-zero on 14/308 nights matching neither Oura
      average nor lowest HR. Relays, not measurements.
  S10 `Body temperature deviation` 0/308, `Mood` 297/308 "Not set",
      `Regularity` uninformative. Dead columns.

WHAT THE PARTNER BATTERY FOUND — the athlete's own hypothesis, confirmed.
Across 26 solo nights (Cork/Dublin/Kinsale/Thun) vs 148 partner-present
nights (Munich), P(snore>0) is 0.115 vs 0.642: risk difference +0.527, 95%
bootstrap CI (+0.371, +0.662), clearing the pre-registered +0.30. It holds
in BOTH instrument regimes separately (old p=4.1e-05, new p=0.046) and
AMBIENT NOISE IS IDENTICAL between the groups within each regime (23.10 vs
23.10 dB, 19.40 vs 19.05 dB) — so the away rooms were not merely quieter.
Alcohol, which reliably increases snoring in the DRINKER, produces no rise
on the athlete's own tagged nights. The acoustic breathing channel is real
and it is measuring the partner. Per S4 that verdict covers `Breathing
disruptions` too, since it is the same 180 nights.

The one the athlete expected to survive did not, but not for the expected
reason: `Movements per hour` is NOT partner-contaminated (solo vs partner
p=0.43) — it is simply uncorrelated with Oura restless periods (rho=0.111,
CI spanning zero) at ~3x the rate. Two counting rules on two detectors.

WHY NOTHING IS INGESTED, even though 119 nights are covered by no device.
(That figure was 247 until the Garmin duration backfill of 2026-08-05 showed
most "device-free" nights were simply nights whose Garmin history had never
been pulled. Over the 631-night era: Garmin 357, Oura 65, either 368 (58%);
Sleep Cycle adds 119, taking coverage to 77%; 144 nights have nothing.)
CLAUDE.md rule 2b and sleep_fusion.py's shadow report settle it: partial
coverage of a rolling-baseline metric is not directional, it is noise with a
plausible-looking sign — 26 fused nights moved the traffic light green ->
YELLOW and RAISED 7-day sleep debt 8.04h -> 8.47h. Here it would be worse on
four axes: the mixture is 119 uncalibrated against 43 calibrated nights (the
anchored part would be the minority); the calibration is one night-level
bias, not a per-minute mapping; +0.47h across 119 nights would raise the
56-night sleep baseline exactly over the stretch the ring was not worn,
making every later ring night score worse by comparison; and fusion's escape
hatch — recompute the entire history in one pass — is unavailable because
Sleep Cycle starts 2024-10-31 and oura_sleep_periods starts 2023-07-05. No
single pass covers both. Per S1/S2 the imported quantity would also swing on
whether the athlete remembered to press start: phone-button behaviour rather
than physiology, which is rule 2b's objection one notch more literal.

THE BIAS HAS NO FIXED VALUE, BECAUSE THERE IS NO FIXED REFERENCE. Added
2026-08-05 after measuring against Garmin as well, and it corrects the
framing above rather than the numbers. Sleep Cycle reads +0.47h vs Oura
(n=43) but **-0.73h vs Garmin (n=168 after the duration backfill, sd 0.70,
r=0.740)** — opposite sign. Note which way that cuts: the systematic offset
is SMALLER against Garmin, but the night-to-night scatter is 50% WIDER than
the devices' own (sd 0.70 vs 0.46), and scatter is what decides
substitutability. The reason the sign flips is that the two wearables do not
agree with each other: **Garmin reads +1.01h MORE sleep than Oura (sd 0.46,
r=0.923, n=58 backfilled nights), replicating +1.11h over the 26 fused
nights** — two independent windows, so a stable instrument offset. And
their minute-by-minute stage agreement is 52.3% at Cohen's kappa 0.178 —
"slight" on the conventional scale. So Sleep Cycle sits BETWEEN the devices,
not outside them. Do not describe its +0.47h as an overestimate or as the
classic actigraphy wake-specificity failure; that was the first reading here
and it does not survive a second comparator. The correct statement is that a
channel whose offset depends on which device you call the reference is
precisely the channel that cannot be substituted into a rolling baseline —
which makes the verdict firmer, not softer.

GARMIN HAS THE HISTORY, BUT ONLY THE SUMMARY. Probed 2026-08-05 over
2024-10-31..2026-05-18 (10 sampled dates, `backfill_garmin_sleep_stages.py
--probe`): sleepLevels present on 0/10, but `sleepTimeSeconds` present on
6/10, reaching back to 2024-10-31. The watch WAS worn across the Sleep Cycle
era — the local record looked thin only because stage capture began
2026-05-19 and `garmin_daily.sleep_hours` on 2026-06-28. Consequences:
a DURATION backfill was run 2026-08-05 (scripts/backfill_garmin_daily_sleep.py
— 618 nights archived, 361 confirmed, 108 unconfirmed, 149 empty), taking the
comparison from n=11 to n=168, while a STAGE comparison against history is
permanently impossible — Garmin keeps the
daily total and discards the hypnogram, so the 53 captured nights are all
there will ever be. Before relying on the historical totals, check
`sleepWindowConfirmationType`: an unconfirmed window is Garmin guessing.

WHAT WOULD CHANGE THE ANSWER. Staging reads UNTESTABLE, not failed (n=19,
one app version, one season) and accrues one night per night now the ring is
worn again — re-run this after ~30 same-regime paired nights. Respiratory
rate needs both 30 same-regime pairs AND the bias collapsing on solo nights;
a Garmin 265 returning averageRespirationValue would let it be triangulated
instead of compared to a single comparator. Movement needs a per-minute
export, which is a format change, not a statistic. The snore attribution
needs no more of the same observational contrast — it needs a phone-position
crossover (alternate sides of the bed for 14 nights) or 15+ solo nights.
Do not re-attempt an ingest without re-running this and getting different
numbers; the CSV is gitignored, so these figures cannot be reproduced from a
clone and this docstring is their only durable record.
--------------------------------------------------------------------------
"""

import csv
import math
import random
import statistics as st
import sys
import tomllib
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.config import load_config              # noqa: E402
from services.repository import Repository           # noqa: E402
from services import biometrics as B                 # noqa: E402
from services import sleep_fusion as F               # noqa: E402


# ---------------------------------------------------------------- thresholds
# Every derivation sentence must be auditable for never mentioning a value
# observed in this data. That is what makes "pre-registered" mean something
# when the numbers are already known.
THRESHOLDS = {
    # 20 min is Sleep Debt's practical step and the Total Sleep contributor's;
    # 45 min is DEEP_RUN_PLAUSIBLE_MINUTES, this codebase's own "long enough
    # to matter" unit.
    "duration_bias_hours": 20 / 60,
    "duration_loa_half_hours": 45 / 60,
    # 15 min is the coarsest offset that stays inside one sleep-onset cycle and
    # cannot move a night to the wrong date (WAKE_CONFIRM_RADIUS_MINUTES is 3).
    "bedtime_offset_minutes": 15.0,
    # Oura's efficiency contributor moves ~1 point per percentage point.
    "efficiency_bias_pct": 3.0,
    # sleep_score.py divides REM/deep seconds by total; 3pp is ~one point.
    "stage_bias_pp": 3.0,
    # ~Oura's own night-to-night sd for this athlete: a channel must agree to
    # within the comparator's noise before it can substitute for it.
    "resp_bias_brpm": 0.5,
    "resp_loa_half_brpm": 1.5,
    # IR = sd(diff)/sd(reference). At IR >= 1 the channel is worse than
    # predicting the reference's own mean every night. 0.75 <=> |r| >= 0.66.
    "information_ratio": 0.75,
    # Roughly the gap between "mostly the partner" and "mostly shared".
    "partner_risk_difference": 0.30,
    # sleep_movement.MIN_CALIBRATION_NIGHTS / biometrics.MIN_HRV_PAIRED_NIGHTS.
    "n_for_bias": 14,
    "n_for_correlation": 30,
    "n_for_correction": 50,
}

SOLO_CITIES = {"Cork", "Dublin 9", "Kinsale", "Thun"}   # supplied by the athlete
PARTNER_CITY = "Munich"
REGIME_SPLIT = "2025-10"     # the recording hole the instrument stepped across

BOOTSTRAP = 10000
random.seed(20260805)


# ------------------------------------------------------------------ plumbing
def arg(flag: str, default: str) -> str:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def num(value) -> float | None:
    try:
        return float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return None


def rule(width: int = 78) -> None:
    print("-" * width)


def boot_ci(sample: list[float], stat, lo: float = 2.5, hi: float = 97.5):
    """Percentile bootstrap CI. Returns (low, high) or (None, None)."""
    if len(sample) < 3:
        return None, None
    draws = []
    for _ in range(BOOTSTRAP):
        resample = [random.choice(sample) for _ in sample]
        try:
            draws.append(stat(resample))
        except (ValueError, ZeroDivisionError, st.StatisticsError):
            pass
    if not draws:
        return None, None
    draws.sort()
    return draws[int(lo / 100 * len(draws))], draws[int(hi / 100 * len(draws)) - 1]


def fisher_ci(r: float, n: int):
    """95% CI on a correlation. Reported alongside every r, never a point
    estimate on its own — at n=19 the interval is the whole story."""
    if n < 4 or abs(r) >= 1:
        return None, None
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1 / math.sqrt(n - 3)
    return math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)


def pearson(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3 or len(set(a)) < 2 or len(set(b)) < 2:
        return None
    return st.correlation(a, b)


def spearman(a: list[float], b: list[float]) -> float | None:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out
    return pearson(ranks(a), ranks(b))


def mannwhitney_p(a: list[float], b: list[float]) -> float | None:
    """Normal approximation with tie correction. Descriptive only — no
    decision in this script reads a p-value."""
    n1, n2 = len(a), len(b)
    if n1 < 3 or n2 < 3:
        return None
    pooled = sorted(a + b)
    def rank_of(v):
        lo = pooled.index(v)
        hi = len(pooled) - 1 - pooled[::-1].index(v)
        return (lo + hi) / 2 + 1
    r1 = sum(rank_of(x) for x in a)
    u1 = r1 - n1 * (n1 + 1) / 2
    mu = n1 * n2 / 2
    ties = 0
    i = 0
    while i < len(pooled):
        j = i
        while j + 1 < len(pooled) and pooled[j + 1] == pooled[i]:
            j += 1
        t = j - i + 1
        ties += t ** 3 - t
        i = j + 1
    n = n1 + n2
    var = n1 * n2 / 12 * ((n + 1) - ties / (n * (n - 1))) if n > 1 else 0
    if var <= 0:
        return None
    z = (u1 - mu) / math.sqrt(var)
    return 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))


def agreement(sc: list[float], ref: list[float], label: str, unit: str,
              bias_max: float | None, loa_max: float | None,
              n_floor: int = THRESHOLDS["n_for_bias"]) -> dict:
    """Bland-Altman first, r second. At small n the bias is far better
    estimated than the correlation, so the report leads with it."""
    diffs = [s - r for s, r in zip(sc, ref)]
    n = len(diffs)
    out = {"label": label, "n": n, "unit": unit}
    if n < 3:
        out["verdict"] = "UNTESTABLE"
        return out
    bias = st.mean(diffs)
    sd = st.stdev(diffs) if n > 1 else 0.0
    out.update(bias=bias, sd=sd, loa=(bias - 1.96 * sd, bias + 1.96 * sd))
    out["bias_ci"] = boot_ci(diffs, st.mean)
    sd_ref = st.stdev(ref) if len(set(ref)) > 1 else 0.0
    out["ir"] = sd / sd_ref if sd_ref else None
    r = pearson(sc, ref)
    out["r"] = r
    out["r_ci"] = fisher_ci(r, n) if r is not None else (None, None)

    if n < n_floor:
        out["verdict"] = "UNTESTABLE"
    elif bias_max is None:
        out["verdict"] = "DISPLAY-ONLY"
    else:
        ok_bias = abs(bias) <= bias_max
        ok_loa = loa_max is None or 1.96 * sd <= loa_max
        ok_ir = out["ir"] is None or out["ir"] <= THRESHOLDS["information_ratio"]
        out["verdict"] = "IMPORTABLE" if (ok_bias and ok_loa and ok_ir) else "FAIL"
        out["why"] = ("" if ok_bias else "bias ")+("" if ok_loa else "LoA ")+("" if ok_ir else "IR")
    return out


def show(res: dict) -> None:
    if res["n"] < 3:
        print(f"  {res['label']:<26} n={res['n']:<3}  {'UNTESTABLE':>12}")
        return
    lo, hi = res["loa"]
    r = res.get("r")
    rl, rh = res.get("r_ci", (None, None))
    r_s = "—" if r is None else (f"{r:+.3f}" + (f" ({rl:+.2f},{rh:+.2f})" if rl is not None else ""))
    ir = res.get("ir")
    print(f"  {res['label']:<26} n={res['n']:<3} bias={res['bias']:+7.2f} "
          f"LoA=({lo:+6.2f},{hi:+6.2f}) {res['unit']:<5} "
          f"IR={'—' if ir is None else f'{ir:.2f}':>5}  r={r_s:<22} "
          f"{res['verdict']}{(' ('+res['why'].strip()+')') if res.get('why') else ''}")


# ------------------------------------------------------------------ §0 load
CSV_PATH = Path(arg("--csv", str(ROOT / "Input_files" / "sleepdata.csv")))
MIN_ASLEEP_MIN = float(arg("--min-asleep-minutes", "60"))
SHOW_NIGHTS = "--nights" in sys.argv

if not CSV_PATH.exists():
    print(f"No Sleep Cycle export at {CSV_PATH}")
    print("Export it from Sleep Cycle -> Settings -> Export data, then drop the")
    print("CSV in Input_files/ (gitignored) or pass --csv PATH.")
    raise SystemExit(1)

with open(CSV_PATH, encoding="utf-8-sig", newline="") as fh:
    raw_rows = list(csv.DictReader(fh, delimiter=";"))

print("=" * 78)
print("SLEEP CYCLE vs OURA + GARMIN — agreement, not accuracy")
print("=" * 78)
print(f"§0 PROVENANCE")
print(f"  csv                {CSV_PATH}")
print(f"  rows read          {len(raw_rows)}")

# Keying. Wake date collides less than start date AND is what Oura's `day`
# already means, so it is the key; collisions resolve to the longest sleep.
start_keys = len({r["Start"][:10] for r in raw_rows})
end_keys = len({r["End"][:10] for r in raw_rows})
print(f"  keying             wake-date {len(raw_rows) - end_keys} collisions vs "
      f"start-date {len(raw_rows) - start_keys} -> keyed on WAKE DATE "
      f"(== Oura `day`), longest `Time asleep` wins")

kept: dict[str, dict] = {}
dropped_short = 0
for row in raw_rows:
    asleep = num(row["Time asleep (seconds)"]) or 0.0
    if asleep < MIN_ASLEEP_MIN * 60:
        dropped_short += 1
        continue
    key = row["End"][:10]
    if key not in kept or asleep > (num(kept[key]["Time asleep (seconds)"]) or 0):
        kept[key] = row
print(f"  dropped < {MIN_ASLEEP_MIN:.0f}min    {dropped_short}")
print(f"  nights kept        {len(kept)}   span {min(kept)} -> {max(kept)}")

# Dead / relay columns, flagged rather than silently carried.
for col, note in [("Body temperature deviation (degrees Celsius)", "S10 dead column"),
                  ("Heart rate (bpm)", "S8 HealthKit relay"),
                  ("Mood", "S10 dead column"),
                  ("Steps", "S8 daily HealthKit total, not overnight")]:
    live = sum(1 for r in raw_rows if (num(r.get(col)) or 0) > 0)
    print(f"  RETIRED  {col[:44]:<46} {live:>3}/{len(raw_rows)} live  ({note})")

repository = Repository(load_config(
    tomllib.load(open(ROOT / ".streamlit" / "secrets.toml", "rb"))
    if (ROOT / ".streamlit" / "secrets.toml").exists() else {}))
offline = bool(getattr(repository.config, "datastore_path", None))
print(f"  comparator source  {'OFFLINE datastore (zero API calls)' if offline else 'LIVE Sheets'}")

oura_rows = repository.get_all_oura_sleep_periods_rows()
oura_by_day: dict[str, dict] = {}
grouped: dict[str, list[dict]] = {}
for row in oura_rows:
    grouped.setdefault(str(row.get("day") or ""), []).append(row)
for day, entries in grouped.items():
    main, _naps = B.split_sleep_periods(B.dedupe_sleep_periods(entries))
    if main:
        oura_by_day[day] = main
garmin = {d: r for d, r in repository.get_garmin_sleep_stages().items()
          if (num(r.get("segment_count")) or 0) > 0}
print(f"  oura nights        {len(oura_by_day)}     garmin nights {len(garmin)}")


def parse_local(value: str):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


# Pair by WINDOW OVERLAP, not by date equality — sleep_fusion's own guard.
# Date equality silently mis-pairs evening sessions and any night Oura
# assigns to the previous day.
paired: list[tuple[str, dict, dict]] = []
rejected_overlap = 0
for day, sc in kept.items():
    ref = oura_by_day.get(day)
    if not ref:
        continue
    a0, a1 = parse_local(sc["Start"]), parse_local(sc["End"])
    b0, b1 = parse_local(ref.get("bedtime_start")), parse_local(ref.get("bedtime_end"))
    if not all([a0, a1, b0, b1]):
        continue
    if b0.tzinfo is not None:
        a0 = a0.replace(tzinfo=b0.tzinfo)
        a1 = a1.replace(tzinfo=b0.tzinfo)
    if F.window_overlap_fraction(a0, a1, b0, b1) < F.MIN_WINDOW_OVERLAP_FRACTION:
        rejected_overlap += 1
        continue
    paired.append((day, sc, ref))
paired.sort()
print(f"  paired vs Oura     {len(paired)}   rejected on window overlap < "
      f"{F.MIN_WINDOW_OVERLAP_FRACTION}: {rejected_overlap}")

# ------------------------------------------------------------- §1 coverage
print()
print("§1 COVERAGE — the one unambiguously true finding, printed first")
sc_days = set(kept)
both = {d for d in sc_days if d in oura_by_day or d in garmin}
orphans = sorted(sc_days - both)
print(f"  Sleep Cycle nights                     {len(sc_days)}")
print(f"  ... also covered by Oura               {len(sc_days & set(oura_by_day))}")
print(f"  ... also covered by Garmin             {len(sc_days & set(garmin))}")
print(f"  ... covered by NEITHER device          {len(orphans)}")
runs, run = [], 1
for i in range(1, len(orphans)):
    d0 = datetime.fromisoformat(orphans[i - 1]).date()
    d1 = datetime.fromisoformat(orphans[i]).date()
    if (d1 - d0) <= timedelta(days=2):
        run += 1
    else:
        runs.append(run)
        run = 1
runs.append(run)
print(f"  longest unbroken device-free run       {max(runs)} nights   "
      f"(a rolling baseline cares about runs, not totals)")

# ------------------------------------------------------------ §2 agreement
print()
print("§2 AGREEMENT vs OURA — Bland-Altman first, r second (see docstring)")
rule()


def col(rows_, name, scale=1.0):
    return [(num(r[name]) or 0.0) * scale for r in rows_]


sc_rows = [p[1] for p in paired]
ou_rows = [p[2] for p in paired]

results = [
    agreement(col(sc_rows, "Time asleep (seconds)", 1 / 3600),
              [(num(r.get("total_sleep_duration")) or 0) / 3600 for r in ou_rows],
              "time asleep", "h",
              THRESHOLDS["duration_bias_hours"], THRESHOLDS["duration_loa_half_hours"]),
    agreement(col(sc_rows, "Time in bed (seconds)", 1 / 3600),
              [(num(r.get("time_in_bed")) or 0) / 3600 for r in ou_rows],
              "time in bed (S1: window)", "h",
              THRESHOLDS["duration_bias_hours"], THRESHOLDS["duration_loa_half_hours"]),
    agreement([100 * (num(r["Time asleep (seconds)"]) or 0) / (num(r["Time in bed (seconds)"]) or 1)
               for r in sc_rows],
              [num(r.get("efficiency")) or 0.0 for r in ou_rows],
              "efficiency (derived)", "%", THRESHOLDS["efficiency_bias_pct"], 8.0),
    agreement(col(sc_rows, "Respiratory rate (breaths per minute)"),
              [num(r.get("average_breath")) or 0.0 for r in ou_rows],
              "respiratory rate", "brpm",
              THRESHOLDS["resp_bias_brpm"], THRESHOLDS["resp_loa_half_brpm"]),
    agreement(col(sc_rows, "Time before sleep (seconds)", 1 / 60),
              [(num(r.get("latency")) or 0) / 60 for r in ou_rows],
              "latency", "min", 10.0, None),
]

staged = [(s, o) for s, o in zip(sc_rows, ou_rows)
          if (num(s["Deep (seconds)"]) or 0) > 0 or (num(s["Dream (seconds)"]) or 0) > 0]
if staged:
    ss, oo = [x[0] for x in staged], [x[1] for x in staged]
    for sc_col, ou_col, label in [("Deep (seconds)", "deep_sleep_duration", "deep % of asleep"),
                                  ("Dream (seconds)", "rem_sleep_duration", "REM % of asleep")]:
        results.append(agreement(
            [100 * (num(s[sc_col]) or 0) / (num(s["Time asleep (seconds)"]) or 1) for s in ss],
            [100 * (num(o.get(ou_col)) or 0) / (num(o.get("total_sleep_duration")) or 1) for o in oo],
            label, "pp", THRESHOLDS["stage_bias_pp"], None,
            n_floor=THRESHOLDS["n_for_correlation"]))

for res in results:
    show(res)

# Movement is a units mismatch, not a bias — Pearson and bias are meaningless
# here, so it gets Spearman only (sleep_movement.py's argument).
sc_mv = col(sc_rows, "Movements per hour")
ou_mv = [(num(r.get("restless_periods")) or 0) / max((num(r.get("time_in_bed")) or 1) / 3600, 0.1)
         for r in ou_rows]
rho = spearman(sc_mv, ou_mv)
rlo, rhi = fisher_ci(rho, len(sc_mv)) if rho is not None else (None, None)
print(f"  {'movements/hour':<26} n={len(sc_mv):<3} rho={rho:+.3f} "
      f"({rlo:+.2f},{rhi:+.2f})  SC {st.median(sc_mv):.0f}/h vs Oura restless "
      f"{st.median(ou_mv):.0f}/h — different counting rules; IMPORT unavailable (S7: no series)")

print()
print(f"  §2b GARMIN — {len(sc_days & set(garmin))} paired nights. Below every n floor "
      f"({THRESHOLDS['n_for_bias']}); reported as a count, not a comparison. NO STATISTIC.")

if SHOW_NIGHTS:
    print()
    print(f"  {'date':<12}{'SC asleep':>10}{'Oura':>8}{'diff':>8}{'SC RR':>8}{'Oura RR':>9}")
    for day, s, o in paired:
        print(f"  {day:<12}{(num(s['Time asleep (seconds)']) or 0)/3600:>10.2f}"
              f"{(num(o.get('total_sleep_duration')) or 0)/3600:>8.2f}"
              f"{(num(s['Time asleep (seconds)']) or 0)/3600 - (num(o.get('total_sleep_duration')) or 0)/3600:>+8.2f}"
              f"{num(s['Respiratory rate (breaths per minute)']) or 0:>8.1f}"
              f"{num(o.get('average_breath')) or 0:>9.1f}")

# ------------------------------------- §3 acoustic channel and attribution
print()
print("§3 ACOUSTIC — no comparator exists, so no r. Attribution instead.")
rule()
all_rows = list(kept.values())


def regime(row: dict) -> str:
    return "old" if row["End"][:7] < REGIME_SPLIT else "new"


snore_pos = sum(1 for r in raw_rows if (num(r["Snore time (seconds)"]) or 0) > 0)
bd_pos = sum(1 for r in raw_rows if (num(r["Breathing disruptions (per hour)"]) or 0) > 0)
both_pos = sum(1 for r in raw_rows
               if (num(r["Snore time (seconds)"]) or 0) > 0
               and (num(r["Breathing disruptions (per hour)"]) or 0) > 0)
print(f"  S4  snore>0 on {snore_pos} nights, breathing-disruptions>0 on {bd_pos}, "
      f"both on {both_pos}, off-diagonal {snore_pos + bd_pos - 2 * both_pos}")
print(f"      -> ONE DETECTOR, TWO READOUTS. Breathing disruptions inherits "
      f"snore's verdict and cannot corroborate it.")
blank = sum(1 for r in raw_rows if not r["Snore time (seconds)"].strip())
print(f"  S5  snore blanks: {blank}/{len(raw_rows)} — every zero is a MEASURED "
      f"zero, which is what makes the contrast below legitimate")
print()

solo = [r for r in all_rows if (r.get("City") or "").strip() in SOLO_CITIES]
partner = [r for r in all_rows if (r.get("City") or "").strip() == PARTNER_CITY]
print(f"  Solo nights (athlete-supplied: {', '.join(sorted(SOLO_CITIES))}): {len(solo)}")
print(f"  Partner-present nights ({PARTNER_CITY}, partner there essentially always): {len(partner)}")
print()
print(f"  {'channel':<24}{'solo median':>13}{'partner median':>16}{'solo %zero':>12}"
      f"{'partner %zero':>15}{'MWU p':>10}")
for label, colname in [("snore (s)", "Snore time (seconds)"),
                       ("breathing disrupt/h", "Breathing disruptions (per hour)"),
                       ("ambient noise (dB)", "Ambient Noise (dB)"),
                       ("movements/hour", "Movements per hour"),
                       ("respiratory rate", "Respiratory rate (breaths per minute)"),
                       ("coughs/hour", "Coughs (per hour)")]:
    a = [num(r[colname]) for r in solo if num(r[colname]) is not None]
    b = [num(r[colname]) for r in partner if num(r[colname]) is not None]
    if len(a) < 3 or len(b) < 3:
        continue
    p = mannwhitney_p(a, b)
    print(f"  {label:<24}{st.median(a):>13.2f}{st.median(b):>16.2f}"
          f"{100*sum(1 for x in a if x == 0)/len(a):>11.1f}%"
          f"{100*sum(1 for x in b if x == 0)/len(b):>14.1f}%"
          f"{'—' if p is None else f'{p:.2e}':>10}")

sa = [1.0 if (num(r["Snore time (seconds)"]) or 0) > 0 else 0.0 for r in solo]
pa = [1.0 if (num(r["Snore time (seconds)"]) or 0) > 0 else 0.0 for r in partner]
rd = st.mean(pa) - st.mean(sa)
lo_s, hi_s = boot_ci(sa, st.mean)
lo_p, hi_p = boot_ci(pa, st.mean)
rd_lo, rd_hi = (lo_p - hi_s), (hi_p - lo_s)
print()
print(f"  P(snore>0):  solo {st.mean(sa):.3f}   partner {st.mean(pa):.3f}")
print(f"  RISK DIFFERENCE {rd:+.3f}  ~95% CI ({rd_lo:+.3f}, {rd_hi:+.3f})   "
      f"threshold >= {THRESHOLDS['partner_risk_difference']:.2f} with CI excluding 0")
attributed = rd >= THRESHOLDS["partner_risk_difference"] and rd_lo > 0
print(f"  -> H_partner {'CONFIRMED' if attributed else 'not confirmed'}")

print()
print("  Stratified by instrument regime (S6) — the confound that could have "
      "manufactured this:")
for reg in ("old", "new"):
    a = [num(r["Snore time (seconds)"]) for r in solo if regime(r) == reg]
    b = [num(r["Snore time (seconds)"]) for r in partner if regime(r) == reg]
    na = [num(r["Ambient Noise (dB)"]) for r in solo
          if regime(r) == reg and num(r["Ambient Noise (dB)"])]
    nb = [num(r["Ambient Noise (dB)"]) for r in partner
          if regime(r) == reg and num(r["Ambient Noise (dB)"])]
    if len(a) < 3 or len(b) < 3:
        continue
    p = mannwhitney_p(a, b)
    print(f"    {reg:<4} solo n={len(a):<3} {100*sum(1 for x in a if x == 0)/len(a):5.1f}% zero | "
          f"partner n={len(b):<3} {100*sum(1 for x in b if x == 0)/len(b):5.1f}% zero | "
          f"p={p:.2e} | ambient {st.median(na):.2f} vs {st.median(nb):.2f} dB "
          f"(p={mannwhitney_p(na, nb):.2f})")
print("    Ambient noise equal within each regime => the away rooms were not "
      "merely quieter.")

alc = [num(r["Snore time (seconds)"]) for r in partner if "Alcohol" in (r.get("Notes") or "")]
ctl = [num(r["Snore time (seconds)"]) for r in partner
       if (r.get("Notes") or "").strip() and "Alcohol" not in (r.get("Notes") or "")]
if len(alc) >= 3 and len(ctl) >= 3:
    print()
    print(f"  Alcohol test (home nights, control = tagged-but-not-alcohol, so "
          f"tagging discipline was active):")
    print(f"    alcohol n={len(alc)} median {st.median(alc):.1f}s   "
          f"control n={len(ctl)} median {st.median(ctl):.1f}s   "
          f"p={mannwhitney_p(alc, ctl):.3f}")
    print(f"    Alcohol reliably increases snoring IN THE DRINKER. No rise here.")
    print(f"    Power note: this detects a doubling, not a 20% rise — a null "
          f"reads 'no effect of the size alcohol is known to produce'.")

# ------------------------------------------------------------ §4 self-report
print()
print("§4 SELF-REPORT (`Notes`) — not sensor data, and the one channel with a "
      "live path into the safety layer")
rule()
tags: dict[str, int] = {}
for r in raw_rows:
    for tag in (r.get("Notes") or "").split(":"):
        if tag.strip():
            tags[tag.strip()] = tags.get(tag.strip(), 0) + 1
tagged = sum(1 for r in raw_rows if (r.get("Notes") or "").strip())
print(f"  tagged nights {tagged}/{len(raw_rows)} over "
      f"{min(kept)} -> {max(kept)}")
print("  " + "  ".join(f"{k}:{v}" for k, v in sorted(tags.items(), key=lambda kv: -kv[1])[:10]))
try:
    checkins = repository.get_all_readiness_checkin_rows()
    print(f"  app's own readiness_checkins: {len(checkins)} rows")
except Exception:
    print("  app's own readiness_checkins: unavailable offline")
print("  WARNING  `alcohol_units` is read by services/scheduling.py::"
      "should_shift_session, which writes date_overrides to Notion and MOVES A")
print("           TRAINING DAY. This channel is not display-only by "
      "construction. Do NOT backfill Notes into readiness_checkins.")

# ------------------------------------------------------------- §5 verdict
print()
print("§5 VERDICT")
rule()
survivors = [r["label"] for r in results if r["verdict"] == "IMPORTABLE"]
untestable = [r["label"] for r in results if r["verdict"] == "UNTESTABLE"]
failed = [r["label"] for r in results if r["verdict"] == "FAIL"]
print(f"  SURVIVING (importable)  {', '.join(survivors) if survivors else 'NONE'}")
print(f"  FAILED                  {', '.join(failed) if failed else 'none'}")
print(f"  UNTESTABLE (n floor)    {', '.join(untestable) if untestable else 'none'}")
print(f"  RETIRED (structural)    heart rate, steps, body temp, mood, regularity "
      f"(S8/S10); movement (S7: no time series)")
print(f"  ATTRIBUTED TO PARTNER   snore, breathing disruptions "
      f"(S4: one detector) — RD {rd:+.3f}")
print(f"  COVERAGE VALUE          {len(orphans)} nights no device recorded, "
      f"longest run {max(runs)}")
print()
print(f"  RECOMMENDATION: "
      f"{'KEEP RECORDING, INGEST ' + ', '.join(survivors) if survivors else 'KEEP RECORDING, DO NOT INGEST'}")
print()
print("  Engine wiring is closed for every channel regardless of the above —")
print("  CLAUDE.md rule 2b and sleep_fusion.py's shadow report. See docstring.")
