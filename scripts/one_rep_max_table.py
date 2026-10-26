# -*- coding: utf-8 -*-
"""Each lift's estimated one-rep max in 2025 and this year, side by side.

    python scripts/one_rep_max_table.py                       # this year from 1 January
    python scripts/one_rep_max_table.py --since 2026-10-19    # the 12-week block only

The owner asked on 2026-10-26: take the 2025 lifts, estimate each one-rep max, and
compare it with this year's, estimated the same way. The Strength page's 81% could
not answer that. It counts only the lifts that have a 2025 entry, and it reads the
session's effort rating as reps left on every set.

- 2025: the "Absolute PR List" of Input_files/2025-training-year.md, which is on the
  owner's PC only and never in git. A line that is not a weight times reps is left
  out: a hold, an assisted pull-up (its number is help, not load). A weight range
  ("21-24 kg") counts at its lower end.
- This year: every working set in the store. A ramp set does not count. A lift in
  machine units (a cable stack) is listed apart, because a unit is not a kilogram.
  On a one-side lift the stronger side counts.
- Both years use the Strength page's own estimate (services/strength.py, WP-38):
  Epley with the one rep left the 2025 best is given, weight x (1 + (reps + 1) / 30),
  for every set of both years. Past about 10 reps the estimate gets rough, and the
  table marks those with *.

The pairs below say which 2025 lift each current lift is set against and how close
the match is. A machine's stack weight does not convert to dumbbells or a barbell,
so a "rough" pair is shown for its direction only.

It only reads: the store is pulled into a copy made for this run, and nothing is
written anywhere. It prints lift names and numbers, nothing else.
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
import tomllib
from datetime import date, timedelta
from pathlib import Path
from typing import NamedTuple

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

LOG_2025 = _ROOT / "Input_files" / "2025-training-year.md"
#: Epley gets rough past about this many reps.
EPLEY_RELIABLE_REPS = 10
#: "Now" is the best set in this many days.
RECENT_DAYS = 28

#: (2025 lift in the PR list, lift logged this year, how close the two are).
PAIRS: tuple[tuple[str, str, str], ...] = (
    ("DB Row", "Single-Arm DB Row", "same lift"),
    ("Lat Pulldown", "Lat Pulldown", "same lift"),
    ("Incline DB Press", "Incline DB Press", "same lift"),
    ("Hip Thrust", "Hip Thrust (Loaded)", "same lift"),
    ("Split Squat", "Bulgarian Split Squat", "same lift"),
    ("RDL", "Romanian Deadlift (DB)", "close: a barbell then, dumbbells now"),
    ("Seated DB Press", "Machine Shoulder Press", "rough: dumbbells then, a machine now"),
    ("Flat DB Press", "Machine Chest Press", "rough: dumbbells then, a machine now"),
    ("Back Squat", "Hack Squat", "rough: a barbell then, a machine now"),
    ("Back Squat", "V Squat", "rough: a barbell then, a machine now"),
    ("Back Squat", "Goblet Squat", "rough: a goblet squat is limited by holding the weight"),
)


class Best(NamedTuple):
    lift: str
    weight: float
    reps: int
    day: str | None
    one_rm: float


#: The reps left every set is given, both years (strength_baselines.PR_RIR).
REPS_LEFT = 1.0


def epley(weight: float, reps: int) -> float:
    """The estimated one-rep max as the Strength page works it out (services/strength.py,
    estimated_1rm with the 2025 best's reps left): weight x (1 + (reps + 1) / 30)."""
    from services import strength
    return strength.estimated_1rm(float(weight), float(reps), 10.0 - REPS_LEFT)[0]


_PR_LINE = re.compile(r"^\s*-\s*\*\*(?P<name>[^*]+?):?\*\*:?\s*(?P<rest>.+)$")


def parse_pr_list(text: str) -> list[Best]:
    """The lifts of the log's "Absolute PR List" section that are a weight times reps.
    The multiplication sign may arrive as ×, x or a mangled byte sequence, so the reps
    are the first whole number after "kg"."""
    out: list[Best] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = "PR List" in line
            continue
        if not inside:
            continue
        m = _PR_LINE.match(line)
        if not m:
            continue
        name, rest = m["name"].strip(), m["rest"]
        at = rest.find("kg")
        if at < 0 or "assist" in rest.lower():
            continue
        weight = re.match(r"\s*(\d+(?:\.\d+)?)", rest)
        reps = re.search(r"(\d+)", rest[at + 2:])
        if not weight or not reps:
            continue
        w, r = float(weight[1]), int(reps[1])
        out.append(Best(name, w, r, None, epley(w, r)))
    return out


def _sides(s: dict) -> list[tuple[float, int]]:
    """The set's right side, and its left side where the record keeps one."""
    right = (float(s.get("weight") or 0), int(s.get("reps") or 0))
    if s.get("weight_left") is None and s.get("reps_left") is None:
        return [right]
    left = (float(s.get("weight_left") if s.get("weight_left") is not None else right[0]),
            int(s.get("reps_left") if s.get("reps_left") is not None else right[1]))
    return [right, left]


def best_by_lift(rows: list[dict], since: date, until: date,
                 unit_lifts: frozenset[str] = frozenset()) -> tuple[dict[str, Best], set[str]]:
    """The heaviest estimate of each lift over [since, until], and the lifts left out
    because they are logged in machine units."""
    best: dict[str, Best] = {}
    in_units: set[str] = set()
    for row in rows:
        name, raw = row.get("movement_name"), row.get("session_date")
        if not name or not raw:
            continue
        try:
            day = date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        if not since <= day <= until:
            continue
        if name in unit_lifts:
            in_units.add(name)
            continue
        for s in row.get("sets") or []:
            if s.get("is_warmup"):
                continue
            for w, r in _sides(s):
                if w <= 0 or r <= 0:
                    continue
                est = epley(w, r)
                if name not in best or est > best[name].one_rm:
                    best[name] = Best(name, w, r, day.isoformat(), est)
    return best, in_units


def _set_text(b: Best) -> str:
    return f"{b.weight:g} kg x {b.reps}{'*' if b.reps > EPLEY_RELIABLE_REPS else ''}"


def report(prs: list[Best], year: dict[str, Best], recent: dict[str, Best],
           in_units: set[str], since: date) -> str:
    lines = ["2025 (your log's PR list)", f"{'Lift':28s} {'Best set':16s} {'Est. 1RM':>9s}"]
    for b in prs:
        lines.append(f"{b.lift:28s} {_set_text(b):16s} {b.one_rm:8.1f}")
    lines += ["", f"This year (from {since.isoformat()})",
              f"{'Lift':40s} {'Best set':16s} {'Date':11s} {'Est. 1RM':>9s} {'Last 28 days':>13s}"]
    for name in sorted(year, key=lambda n: -year[n].one_rm):
        b, r = year[name], recent.get(name)
        lines.append(f"{name:40s} {_set_text(b):16s} {b.day:11s} {b.one_rm:8.1f} "
                     f"{(f'{r.one_rm:.1f}' if r else '-'):>13s}")
    if in_units:
        lines.append("In machine units, not kilograms (not compared): " + ", ".join(sorted(in_units)))
    by_2025 = {b.lift: b for b in prs}
    lines += ["", "Side by side",
              f"{'2025 lift':18s} {'2025':>6s} {'This year':28s} {'Best':>6s} {'%':>5s} "
              f"{'Now':>6s} {'%':>5s}  How close"]
    for old, new, close in PAIRS:
        then, b, r = by_2025.get(old), year.get(new), recent.get(new)
        if not then or not b:
            continue
        now = f"{r.one_rm:6.1f} {r.one_rm / then.one_rm * 100:4.0f}%" if r else f"{'-':>6s} {'':>5s}"
        lines.append(f"{old:18s} {then.one_rm:6.1f} {new:28s} {b.one_rm:6.1f} "
                     f"{b.one_rm / then.one_rm * 100:4.0f}% {now}  {close}")
    lines += ["", "* more than 10 reps: the estimate is rough.",
              "Est. 1RM: weight x (1 + (reps + 1) / 30), the same way for both years,",
              "as the Strength page works it out."]
    return "\n".join(lines)


def _config():
    from services.config import load_config
    secrets = _ROOT / ".streamlit" / "secrets.toml"
    overrides = tomllib.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
    # A copy of the store rebuilt for this run only, never the checkout's datastore.db.
    copy = Path(tempfile.mkdtemp(prefix="one_rm_")) / "record.db"
    return load_config({**overrides, "HEALTH_SYSTEM_OF_RECORD": "supabase",
                        "HEALTH_DATASTORE_MODE": "cache",
                        "HEALTH_DATASTORE_PATH": str(copy)})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path, default=LOG_2025, help="the 2025 training-year file")
    ap.add_argument("--since", type=date.fromisoformat, default=None,
                    help="the first day of this year's sets (default: 1 January)")
    args = ap.parse_args()
    if not args.log.exists():
        print(f"No 2025 log at {args.log}.")
        return 1
    from services import sessions
    from services.repository import Repository

    today = date.today()
    since = args.since or date(today.year, 1, 1)
    prs = parse_pr_list(args.log.read_text(encoding="utf-8-sig", errors="replace"))
    units = frozenset(n for n, t in sessions.exercise_traits().items() if t.get("unit") == "unit")
    rows = Repository(_config()).get_all_training_exercises_raw()
    year, in_units = best_by_lift(rows, since, today, units)
    recent, _ = best_by_lift(rows, max(since, today - timedelta(days=RECENT_DAYS - 1)), today, units)
    print(report(prs, year, recent, in_units, since))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
