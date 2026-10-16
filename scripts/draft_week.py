"""draft_week.py — place the goal system's week and print it.

    python scripts/draft_week.py

The cards are in goal_week.py, the rules in services/placement.py; the time
model is services/sessions.session_seconds. Prints each session in order with
its modelled minutes, the weekly hard sets per area, and every broken rule
(none means the week passes). Reads and writes nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import goal_week as gw  # noqa: E402
from services import placement as pl  # noqa: E402


def dose(card: pl.Card) -> str:
    if card.type == "hold":
        return f"{card.sets} x {card.hold_seconds} s"
    if card.type == "hold_reps":
        return f"{card.sets} x {card.reps_in_set} x {card.hold_seconds} s"
    return f"{card.sets} x {card.reps}"


def main() -> int:
    week = pl.place(gw.CARDS, gw.SPEC)
    for day in gw.DAYS:
        items = pl.order(week[day])
        print(f"\n{day} - session {gw.LETTERS[day]}: {pl.minutes(week[day]):.0f} modelled minutes")
        for card in items:
            side = " each side" if card.laterality == "unilateral" else ""
            print(f"   {card.name}: {dose(card)}{side}")
    for name, v in gw.OFF_GYM.items():
        print(f"\n{' and '.join(v['days'])} (no gym): {name}: {v['sets']} sets")
    total = pl.weekly_sets(week, gw.EXTRA_SETS)
    print("\nWeekly hard sets:", ", ".join(f"{a} {n:g}" for a, n in sorted(total.items())))
    over = pl.over_target(week)
    print(f"Over the {pl.SESSION_MINUTES_TARGET}-minute target:",
          ", ".join(f"{d} {m:.0f}" for d, m in over) if over else "none")
    broken = pl.violations(week, gw.SPEC, gw.EXTRA_SETS, gw.EXTRA_DAYS)
    print("Broken rules:", "none" if not broken else "")
    for line in broken:
        print("  ", line)
    return 0 if not broken else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
