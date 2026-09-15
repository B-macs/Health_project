# -*- coding: utf-8 -*-
"""Seed the next training block BEFORE its Monday, so it starts by itself.

This replaced the begin-block button on 2026-08-18. The button was the only
route into a new phase and it could create the wrong one: driven by whatever
the stored phase list said, a stale list made it offer a block that was
already running, a week late, over the top of the real one.

Blocks always start on a Monday and are authored ahead of time, so the phase
is seeded in advance with status "upcoming" and plan.active_phase picks it up
on the date. Nothing to press, nothing to get wrong on the morning itself.

Refusals, all deliberate and all from the layers that own them:
  * a non-Monday start, or a length that is not a whole number of weeks —
    plan.default_phase and Repository.set_phases both refuse (key rule 18b);
  * a block that skips its predecessor — sessions.next_phase_offer;
  * a range overlapping a live phase — Repository.set_phases;
  * a block whose content is not authored — next_phase_offer again.

The write goes to Notion and flushes to Supabase inline (the config keys in
Repository._FLUSH_IMMEDIATELY), so a redeploy cannot lose it — which is the
failure that made this script necessary in the first place.

THE FAILED-WEEK RULE RUNS FIRST (services/week_repeat.py, 2026-09-15). A block
whose last week failed is one week longer than its calendar said, so the next
block cannot be placed until that week is judged — and begin_new_phase would
otherwise mark the lapsed block 'completed', which the rule never repeats. A
block with a fixed last date (Block B, race day) is built by
sessions.build_phase, which drops weeks in its authored order when it starts
late.

⚠ THE HOSTED APP READS ITS OWN LOCAL COPY. A write from here reaches Notion and
Supabase, not that copy; redeploy the app afterwards so it rebuilds the copy
from Supabase.

Usage:
    python scripts/seed_next_block.py --start 2026-09-14            # seed
    python scripts/seed_next_block.py --start 2026-09-14 --dry-run  # check only
    python scripts/seed_next_block.py --show                        # list phases
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from services import plan as ph, sessions as sess, week_repeat
from services.config import load_config
from services.repository import Repository


def _repo() -> Repository:
    overrides = {}
    secrets = _ROOT / ".streamlit" / "secrets.toml"
    if secrets.exists():
        with open(secrets, "rb") as fh:
            overrides = tomllib.load(fh)
    return Repository(load_config(overrides))


def _show(phases) -> None:
    today = dt.date.today()
    active = ph.active_phase(phases, today)
    print("stored phases:")
    for p in sorted(phases, key=lambda x: x.start_date):
        mark = "  <-- ACTIVE TODAY" if active is not None and p is active else ""
        weeks = f"  weeks {p.week_plan}" if p.week_plan is not None else ""
        print(f"  {p.phase_number}  {p.start_date} .. {ph.phase_end_date(p)}  "
              f"{p.length_days:>3}d  {p.status:<9} {p.name}{weeks}{mark}")
        for monday, outcome in sorted(p.week_results.items()):
            print(f"       week of {monday}: {outcome}")
    if active is None:
        print("  (no phase covers today — nothing is scheduled)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", help="ISO date, must be a Monday")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    repo = _repo()
    stored = repo.get_phases()
    today = dt.date.today()
    first = min((dt.date.fromisoformat(p.start_date) for p in stored), default=today)
    phases, judged = week_repeat.apply_failed_week_rule(
        stored, repo.get_logged_session_dates(first, today), today)
    for monday, outcome in judged:
        print(f"failed-week rule — week of {monday}: {outcome}")

    if args.show or not args.start:
        _show(phases)
        nxt = sess.next_phase_offer(phases)
        print("next block to seed:", nxt if nxt else "none authored")
        if judged:
            print("(the rule's verdicts above are NOT stored by --show)")
        return 0

    start = dt.date.fromisoformat(args.start)
    number = sess.next_phase_offer(phases)
    if number is None:
        print("REFUSED: no next block is authored, or its predecessor is missing.")
        _show(phases)
        return 1

    meta = sess.PHASE_META[number]
    # Seeded ahead: it is not today's block yet, and it must not shadow the
    # one that is. active_phase promotes it on the date, not on this status.
    try:
        new_phase = sess.build_phase(number, start,
                                     status="upcoming" if start > today else "active")
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        return 1

    updated = sess.begin_new_phase(phases, new_phase)
    weeks = ph.plan_weeks(new_phase)
    print(f"would store: phase {number} — {meta['name']}")
    print(f"  {start} .. {ph.phase_end_date(new_phase)}  ({new_phase.length_days} days, "
          f"authored weeks {weeks}, stage {meta['stage']}, status {new_phase.status})")

    if args.dry_run:
        print("dry run — nothing written")
        return 0

    repo.set_phases(updated)          # refuses overlap / misalignment
    repo.set_config("current_stage", str(meta["stage"]))
    print("written to Notion, flushed to Supabase")

    _show(repo.get_phases())
    return 0


if __name__ == "__main__":
    sys.exit(main())
