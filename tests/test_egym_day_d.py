"""The EGYM session is session D of the 12-week block from week 4.

The athlete, 2026-11-11: "Can we make this training Training day D", and to the
four questions asked (D every Friday from 13 November to the end of the block;
the rear delts at 3 sets a week; 2 sets a machine; the "+" menu keeps the
session): "Yes, build it". goal_block.EGYM_D_FROM_WEEK.
"""
from __future__ import annotations

from datetime import date, timedelta

import egym_circuit as ec
import goal_block as gb
from services import egym_session as egs
from services import gate1
from services import sessions as sess
from services import training_session as ts

PLAN = gb.PLAN_GOAL_BLOCK


def _day_num(week: int, weekday: int) -> int:
    return (week - 1) * 7 + weekday + 1


def test_session_d_is_the_egym_session_from_friday_13_november():
    first = _day_num(gb.EGYM_D_FROM_WEEK, 4)
    assert gb.START + timedelta(days=first - 1) == date(2026, 11, 13)
    for week in range(gb.EGYM_D_FROM_WEEK, gb.WEEKS + 1):
        day = PLAN[_day_num(week, 4)]
        assert [e["name"] for e in day["exercises"]] == list(ec.names()), week
        assert day["objective"] == f"Session D — EGYM (week {week})"
        assert day["session_letter"] == "D" and day["day_type"] == "main"
        assert ts.egym_day(day["exercises"])


def test_weeks_1_to_3_keep_the_d_he_ran():
    for week in range(1, gb.EGYM_D_FROM_WEEK):
        names = [e["name"] for e in PLAN[_day_num(week, 4)]["exercises"]]
        assert names == [e["name"] for e in gb.SESSIONS["D"]], week


def test_a_b_and_c_are_unchanged_and_gate_1_counts_them_only():
    for week in range(1, gb.WEEKS + 1):
        for weekday, letter in ((0, "A"), (1, "B"), (3, "C")):
            names = [e["name"] for e in PLAN[_day_num(week, weekday)]["exercises"]]
            if letter == "A" and week in gb.TEST_WEEKS:
                continue                       # the plank test replaces the crunch
            assert names == [e["name"] for e in gb.SESSIONS[letter]], (week, letter)
    assert gb.CORE_LETTERS == ("A", "B", "C") and gate1.CORE_REQUIRED == 3
    assert "Hack Squat" in [e["name"] for e in gb.SESSIONS["B"]], "the gate-1 lift keeps B"


def test_the_rear_delts_get_three_sets_a_week_from_week_4():
    """His answer 2: Monday's crossover only, 3 of the 4 weekly sets."""
    for week in (gb.EGYM_D_FROM_WEEK, gb.WEEKS):
        sets = sum(e["sets"] for d in range(_day_num(week, 0), _day_num(week, 6) + 1)
                   for e in PLAN[d]["exercises"] if e["name"] == "Reverse Cable Crossover")
        assert sets == 3, week


def test_the_egym_d_day_fits_the_session_shape():
    """Under the 70-minute limit with EGYM's own set length, and no shape rule broken."""
    day = PLAN[_day_num(gb.EGYM_D_FROM_WEEK, 4)]
    assert sess.session_shape_violations(day) == []
    assert egs.modelled_minutes(day["exercises"]) <= 70


def test_the_day_view_names_two_sets_not_reps():
    day = PLAN[_day_num(gb.EGYM_D_FROM_WEEK, 4)]
    from services import training_screen
    line = training_screen.exercise_line(day["exercises"][0])
    assert line["prescription"] == "2 sets, one after the other"


def test_the_plus_menus_session_is_the_same_machines():
    """His answer 4: the "+" menu keeps the EGYM session as an extra."""
    assert [e["name"] for e in egs.build_day()["exercises"]] == list(ec.names())
