"""scripts/one_rep_max_table.py: each lift's estimated one-rep max in 2025 and this year
(the owner's question of 2026-10-26). The numbers here are made up; the script reads
the real ones on the owner's PC."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("one_rep_max_table", ROOT / "scripts" / "one_rep_max_table.py")
orm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orm)

_LOG = """# A training year

## Absolute PR List (Highest Numbers of the Year)

### Push
- **Bench:** 50 kg × 5
- **Mangled Press:** 20 kg Ã— 10
- **Range Pull:** 30–35 kg x 15
- **Assisted Pull-Up:** 20 kg assist × 8
- **Plank:** 30 s × 3

---

## 1. Push Strength
- **Not A PR:** 99 kg × 1
"""


def _row(name, day, sets):
    return {"movement_name": name, "session_date": day, "sets": sets}


def test_the_estimate_is_the_strength_page_s_own():
    """Both years with the 2025 best's one rep left (WP-38)."""
    from services import strength
    assert orm.epley(60, 12) == strength.estimated_1rm(60, 12, 9.0)[0] == 60 * (1 + 13 / 30)
    assert orm.epley(80, 5) == 80 * (1 + 6 / 30)


def test_the_pr_list_reads_weight_times_reps_only():
    prs = {b.lift: b for b in orm.parse_pr_list(_LOG)}
    assert set(prs) == {"Bench", "Mangled Press", "Range Pull"}   # no assist, no hold, no later section
    assert (prs["Bench"].weight, prs["Bench"].reps) == (50, 5)
    assert (prs["Mangled Press"].weight, prs["Mangled Press"].reps) == (20, 10)
    assert prs["Range Pull"].weight == 30                          # a range at its lower end


def test_ramp_sets_and_unit_lifts_do_not_count():
    rows = [
        _row("Lift", "2026-10-20", [{"reps": 6, "weight": 80, "is_warmup": True},
                                    {"reps": 10, "weight": 50}]),
        _row("Cable", "2026-10-20", [{"reps": 12, "weight": 3}]),
    ]
    best, in_units = orm.best_by_lift(rows, date(2026, 1, 1), date(2026, 10, 26), frozenset({"Cable"}))
    assert set(best) == {"Lift"} and best["Lift"].weight == 50
    assert in_units == {"Cable"}


def test_the_stronger_side_counts():
    rows = [_row("Row", "2026-10-20", [{"reps": 8, "weight": 20, "reps_left": 10}])]
    best, _ = orm.best_by_lift(rows, date(2026, 1, 1), date(2026, 10, 26))
    assert (best["Row"].weight, best["Row"].reps) == (20, 10)


def test_the_window_bounds_the_days():
    rows = [_row("Lift", "2025-12-31", [{"reps": 5, "weight": 100}]),
            _row("Lift", "2026-03-01", [{"reps": 5, "weight": 60}]),
            _row("Lift", "2026-10-25", [{"reps": 5, "weight": 50}])]
    year, _ = orm.best_by_lift(rows, date(2026, 1, 1), date(2026, 10, 26))
    recent, _ = orm.best_by_lift(rows, date(2026, 9, 29), date(2026, 10, 26))
    assert year["Lift"].weight == 60 and recent["Lift"].weight == 50


def test_the_side_by_side_divides_by_the_2025_estimate():
    prs = orm.parse_pr_list("## Absolute PR List\n- **RDL:** 60 kg x 12\n")
    rows = [_row("Romanian Deadlift (DB)", "2026-10-20", [{"reps": 12, "weight": 42}])]
    year, _ = orm.best_by_lift(rows, date(2026, 1, 1), date(2026, 10, 26))
    text = orm.report(prs, year, year, set(), date(2026, 1, 1))
    side_by_side = text.split("Side by side")[1]
    line = next(l for l in side_by_side.splitlines() if l.startswith("RDL "))
    assert "70%" in line and "close" in line          # same reps both years: 42 / 60


def test_every_pair_names_a_lift_a_plan_defines():
    import goal_block
    from services import sessions
    swaps = {ex["name"] for options in goal_block.ALTERNATIVES.values() for ex in options}
    known = set(sessions.exercise_traits()) | swaps
    assert {new for _old, new, _close in orm.PAIRS} <= known
