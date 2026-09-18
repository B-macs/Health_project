# -*- coding: utf-8 -*-
"""Rebuild a block that is SEEDED BUT HAS NOT STARTED, in place.

seed_next_block.py places the NEXT block; it cannot replace one that is
already stored. That is the case this script exists for: on 2026-09-18 the
athlete cancelled the 10 km race, so Block B lost its fixed last date — and
the stored phase had been built against that date, three weeks long with its
week 1 dropped (sessions.build_phase drops weeks in the authored order when a
block with `ends_on` starts late). Nothing about it was wrong when it was
written; the block it was built for no longer exists.

What it does, for one phase number:
  1. reads the LIVE stored phases,
  2. refuses unless that phase is still in the future — a block that has
     started carries logged sessions against its day numbers, and rebuilding
     it under them would silently re-point every one,
  3. refuses if it carries reschedules or week verdicts, for the same reason,
  4. rebuilds it with sessions.build_phase at its own start date, which reads
     today's authored content and today's PHASE_META,
  5. writes the list back through Repository.set_phases, which keeps its own
     refusals (overlap, week alignment).

⚠ THE HOSTED APP READS ITS OWN LOCAL COPY. This reaches Notion and Supabase,
not that copy; redeploy the app afterwards.

    python scripts/reseed_block.py --phase 4
    python scripts/reseed_block.py --phase 4 --apply
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import tomllib
from dataclasses import replace
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from services import plan as ph, sessions as sess  # noqa: E402
from services.config import load_config  # noqa: E402
from services.repository import Repository  # noqa: E402


def _repo() -> Repository:
    overrides = {}
    secrets = _ROOT / ".streamlit" / "secrets.toml"
    if secrets.exists():
        with open(secrets, "rb") as fh:
            overrides = tomllib.load(fh)
    return Repository(load_config(overrides))


def _line(p) -> str:
    weeks = ph.plan_weeks(p)
    return (f"phase {p.phase_number}  {p.start_date} .. {ph.phase_end_date(p)}  "
            f"{p.length_days:>3}d  {p.status:<9} {p.name}  weeks {weeks}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True, type=int)
    ap.add_argument("--apply", action="store_true", help="without this, nothing is written")
    args = ap.parse_args()

    repo = _repo()
    phases = repo.get_phases()
    today = dt.date.today()
    current = next((p for p in phases if p.phase_number == args.phase), None)
    if current is None:
        print(f"REFUSED: no stored phase {args.phase}.")
        return 1
    start = dt.date.fromisoformat(current.start_date)
    if start <= today:
        print(f"REFUSED: phase {args.phase} started on {start}. A block that has run "
              f"carries logged sessions against its day numbers.")
        return 1
    if current.date_overrides or current.shift_reasons or current.week_results:
        print(f"REFUSED: phase {args.phase} already carries reschedules or week verdicts.")
        return 1

    rebuilt = sess.build_phase(args.phase, start, status=current.status)
    print("stored:  " + _line(current))
    print("rebuilt: " + _line(rebuilt))
    if rebuilt == current:
        print("no change — the stored block already matches today's authored content.")
        return 0
    if not args.apply:
        print("dry run — nothing written")
        return 0

    repo.set_phases([rebuilt if p.phase_number == args.phase else p for p in phases])
    print("written to Notion, flushed to Supabase")
    for p in sorted(repo.get_phases(), key=lambda x: x.start_date):
        print("  " + _line(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
