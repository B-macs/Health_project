"""WP-43 (the athlete, 2026-11-03): a weight step needs BOTH arms at the top
of the range, and the three shoulder lifts of the new machine stepped only when
every session in 14 days earned it, until 2026-11-20: from then they run the
repeat-aim rule (tests/test_repeat_aim_rule.py). The window itself stays a
lift's own setting ("progression_window_days").

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


def test_the_shoulder_lifts_left_the_fourteen_day_window_and_the_row_keeps_seven():
    """2026-11-20: the repeat-aim rule replaced the 14 days on the shoulder lifts."""
    y = next(e for e in gb.SESSIONS["A"] if e["name"] == "Single-Arm Cable Y Raise")
    row = next(e for e in gb.SESSIONS["B"] if e["name"] == "Single-Arm DB Row")
    assert sessions.repeats_aim(y) and "progression_window_days" not in y
    assert not sessions.repeats_aim(row) and sessions.step_window_days(row) == 7


def test_the_row_says_both_arms_and_seven_days():
    row = next(e for e in gb.SESSIONS["B"] if e["name"] == "Single-Arm DB Row")
    lp = {"session_date": "2026-11-03", "reps": 10, "weight_kg": 20.0}
    short = sessions.resolve_prescription(
        row, lp, "normal", {"reduced": False},
        weight_increment=row["increment_size"],
        history=[("2026-11-03", _sets([10, 9, 9], weight=20.0))])
    assert short["next_step"].startswith("The weight goes up when, on both arms, every set")
    assert short["next_step"].endswith("in each session of this lift in 7 days.")
