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

from services import plan as ph, sessions as sess
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
        print(f"  {p.phase_number}  {p.start_date} .. {ph.phase_end_date(p)}  "
              f"{p.length_days:>3}d  {p.status:<9} {p.name}{mark}")
    if active is None:
        print("  (no phase covers today — nothing is scheduled)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", help="ISO date, must be a Monday")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    repo = _repo()
    phases = repo.get_phases()

    if args.show or not args.start:
        _show(phases)
        nxt = sess.next_phase_offer(phases)
        print("next block to seed:", nxt if nxt else "none authored")
        return 0

    start = dt.date.fromisoformat(args.start)
    number = sess.next_phase_offer(phases)
    if number is None:
        print("REFUSED: no next block is authored, or its predecessor is missing.")
        _show(phases)
        return 1

    meta = sess.PHASE_META[number]
    plan_days = len(sess.plan_dict_for_phase(number))
    new_phase = ph.default_phase(start, length_days=plan_days,
                                 phase_number=number, name=meta["name"])
    # Seeded ahead: it is not today's block yet, and it must not shadow the
    # one that is. active_phase promotes it on the date, not on this status.
    if start > dt.date.today():
        new_phase = type(new_phase)(**{**new_phase.__dict__, "status": "upcoming"})

    updated = sess.begin_new_phase(phases, new_phase)
    print(f"would store: phase {number} — {meta['name']}")
    print(f"  {start} .. {ph.phase_end_date(new_phase)}  ({plan_days} days, "
          f"stage {meta['stage']}, status {new_phase.status})")

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
