"""WP-43 (the athlete, 2026-11-03): a weight step needs BOTH arms at the top
of the range, and the three shoulder lifts of the new machine step only when
every session in 14 days earned it.

His words: "Yes both arms must reach the top of the range before weight
increase, this should already be a rule." Until this change the rule read the
right arm's reps only. "Double the time means a": the window is 14 days, not
7, on the Single-Arm Cable Y Raise, the Cable Lateral Raise and the Reverse
Cable Crossover; "Single arm db row can stay the same rule."
"""
from __future__ import annotations

import goal_block as gb
from services import engine, sessions


def _sets(right, left=None, weight=6.0, left_weight=None):
    out = []
    for i, r in enumerate(right):
        s = {"reps": r, "weight": weight}
        if left is not None and left[i] != r:
            s["reps_left"] = left[i]
        if left_weight is not None:
            s["weight_left"] = left_weight
        out.append(s)
    return out


def _step(history, window_days=engine.PROGRESSION_WINDOW_DAYS):
    return engine.range_progression(10, 15, history, 6.0, 12, increment=2.0,
                                    prescribed_sets=3, window_days=window_days)


def test_the_left_arm_short_of_the_top_holds_the_weight():
    plan = _step([("2026-11-03", _sets([15, 15, 15], left=[15, 14, 13]))])
    assert plan["action"] == "hold" and plan["weight"] == 6.0


def test_both_arms_at_the_top_step_the_weight():
    plan = _step([("2026-11-03", _sets([15, 15, 15], left=[15, 15, 15]))])
    assert plan["action"] == "step_up" and plan["weight"] == 8.0


def test_a_left_arm_stored_only_where_it_differs_reads_as_the_right():
    """The phone stores the left arm only where it differs, so no left value
    means the left arm did what the right did."""
    plan = _step([("2026-11-03", _sets([15, 15, 15]))])
    assert plan["action"] == "step_up"


def test_one_set_past_the_top_steps_only_when_each_arm_earned_it():
    right_only = _step([("2026-11-03", _sets([16, 12, 11], left=[13, 12, 11]))])
    assert right_only["action"] == "hold"
    both = _step([("2026-11-03", _sets([16, 12, 11], left=[13, 16, 11]))])
    assert both["action"] == "step_up"


def test_a_left_arm_at_a_lighter_weight_does_not_earn_the_step():
    plan = _step([("2026-11-03", _sets([15, 15, 15], weight=6.0, left_weight=4.0))])
    assert plan["action"] == "hold"


def test_fourteen_days_reach_back_to_a_session_seven_days_do_not():
    history = [("2026-11-03", _sets([15, 15, 15])),
               ("2026-10-24", _sets([13, 12, 12]))]
    assert _step(history)["action"] == "step_up"
    assert _step(history, window_days=14)["action"] == "hold"


def test_the_three_shoulder_lifts_carry_the_fourteen_day_window_and_the_row_does_not():
    y = next(e for e in gb.SESSIONS["A"] if e["name"] == "Single-Arm Cable Y Raise")
    row = next(e for e in gb.SESSIONS["B"] if e["name"] == "Single-Arm DB Row")
    assert sessions.step_window_days(y) == 14
    assert sessions.step_window_days(row) == 7


def test_the_y_raise_steps_two_kg_and_says_both_arms_and_fourteen_days():
    y = next(e for e in gb.SESSIONS["A"] if e["name"] == "Single-Arm Cable Y Raise")
    lp = {"session_date": "2026-11-03", "reps": 15, "weight_kg": 6.0}
    up = sessions.resolve_prescription(
        y, lp, "normal", {"reduced": False},
        weight_increment=y["increment_size"],
        history=[("2026-11-03", _sets([15, 15, 15]))])
    assert up["action"] == "step_up" and up["weight_kg"] == 8.0
    short = sessions.resolve_prescription(
        y, lp, "normal", {"reduced": False},
        weight_increment=y["increment_size"],
        history=[("2026-11-03", _sets([14, 13, 12]))])
    assert short["next_step"] == (
        "The weight goes up when, on both arms, every set reaches 15 reps or one set "
        "goes past 15, in each session of this lift in 14 days.")
