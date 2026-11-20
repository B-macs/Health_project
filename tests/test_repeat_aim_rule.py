"""The repeat-aim rule of the four lifts on the new cable machine, and the back
extension's 1 kg steps (Update 5, WP-50, WP-53 and WP-54).

The athlete, 2026-11-19: "the 14 day rule is only when I do 12 reps x 3 then
the next week I do 12 x3 again rather than 13x3. Not if I go over the amount
myself then it resets to that rep target. If I do 16 x 3 then it should go up
the weight and down to the bottom of the reps. if I do 15 x 3 when asked for 11
reps. it should ask to do 15 x 3 the next week, if I complete that then it goes
up a weight and reduce reps." His answers of 2026-11-20: "Yes that is right",
"Yes bottom of the range", "A - Correct is asks 12 again, B - It should ask 14
not 13, C - It should go up in weight and drop in reps". For the hip flexion
(WP-54): "This logic should follow the same logic in number 3".

The back extension (WP-53): "back extension can go up in 1kg from 5kg to 10kg
after that it returns to 2.5kg as per now"; "Agree" to 8, 9, 10, then 12.5.
"""
from __future__ import annotations

import goal_block as gb
from services import engine, sessions

LIFTS = ("Single-Arm Cable Y Raise", "Cable Lateral Raise", "Reverse Cable Crossover",
         "Standing Cable Hip Flexion")


def _sets(*reps, weight=6.0, left=None):
    out = []
    for i, r in enumerate(reps):
        s = {"reps": r, "weight": weight}
        if left is not None and left[i] != r:
            s["reps_left"] = left[i]
        out.append(s)
    return out


def _history(*sessions_oldest_first):
    """(date, sets), given OLDEST first, returned newest first as the rule reads it."""
    return [(f"2026-11-{i + 1:02d}", sets) for i, sets in enumerate(sessions_oldest_first)][::-1]


def _rule(*sessions_oldest_first, plan_reps=12):
    return engine.repeat_aim_progression(10, 15, _history(*sessions_oldest_first), 6.0, plan_reps,
                                         increment=2.0, prescribed_sets=3)


# ─── His rule, point by point ───────────────────────────────────────────────

def test_every_set_at_the_aim_asks_it_again_then_one_more():
    # From the start: 12 x 3 is the first time; 12 x 3 again is the second.
    first = _rule(_sets(12, 12, 12))
    assert (first["weight"], first["aim"], first["times"]) == (6.0, 12, 1)
    second = _rule(_sets(12, 12, 12), _sets(12, 12, 12))
    assert (second["aim"], second["times"]) == (13, 0)


def test_more_than_the_aim_asks_what_he_did_and_counts_as_the_first_time():
    # Asked 11 (11 x 3 once), did 15 x 3: the next asks 15.
    asked_11 = _rule(_sets(11, 11, 11))
    assert asked_11["aim"] == 11
    did_15 = _rule(_sets(11, 11, 11), _sets(15, 15, 15))
    assert (did_15["weight"], did_15["aim"], did_15["times"], did_15["action"]) == (6.0, 15, 1, "hold")
    # Asked 15 and did 15 x 3: the weight goes up, the aim to the bottom.
    up = _rule(_sets(11, 11, 11), _sets(15, 15, 15), _sets(15, 15, 15))
    assert (up["weight"], up["aim"], up["action"]) == (8.0, 10, "step_up")


def test_what_he_did_is_the_average_of_the_sets():
    """3b: "It should ask 14 not 13" for 15, 14, 13 asked at 11."""
    plan = _rule(_sets(11, 11, 11), _sets(15, 14, 13))
    assert (plan["aim"], plan["times"]) == (14, 1)


def test_a_set_under_the_aim_asks_it_again_and_does_not_count():
    """3a: asked 12, did 12, 12, 10: 12 again. The miss does not count as a time."""
    miss = _rule(_sets(12, 12, 12), _sets(12, 12, 10))
    assert (miss["aim"], miss["times"]) == (12, 1)
    after = _rule(_sets(12, 12, 12), _sets(12, 12, 10), _sets(12, 12, 12))
    assert (after["aim"], after["times"]) == (13, 0)


def test_one_set_past_the_top_steps_the_weight_at_once():
    """3c and "If I do 16 x 3 then it should go up the weight and down to the
    bottom of the reps"."""
    for last in (_sets(16, 16, 16), _sets(15, 15, 16), _sets(11, 12, 18)):
        plan = _rule(_sets(11, 11, 11), last)
        assert (plan["weight"], plan["aim"], plan["action"]) == (8.0, 10, "step_up"), last


def test_every_set_at_the_top_steps_only_when_the_aim_was_the_top():
    held = _rule(_sets(13, 13, 13), _sets(15, 15, 15))
    assert (held["weight"], held["aim"], held["action"]) == (6.0, 15, "hold")


def test_a_weight_he_chose_counts_from_that_session():
    """"me increasing the weight and you updating the logic": the app takes his
    weight; older sessions at another weight hold nothing back."""
    plan = _rule(_sets(12, 12, 12), _sets(12, 12, 12, weight=8.0))
    assert (plan["weight"], plan["aim"], plan["times"]) == (8.0, 12, 1)
    # Under the bottom at his new weight: the bottom, not counted.
    heavy = _rule(_sets(12, 12, 12), _sets(8, 8, 8, weight=10.0))
    assert (heavy["weight"], heavy["aim"], heavy["times"]) == (10.0, 10, 0)


def test_a_session_with_too_few_sets_counts_toward_nothing():
    plan = _rule(_sets(12, 12, 12), _sets(12, 12))
    assert (plan["aim"], plan["times"]) == (12, 1)
    past = _rule(_sets(12, 12, 12), _sets(16, 16))
    assert past["action"] == "hold" and past["weight"] == 6.0


def test_a_one_arm_lift_reads_the_weaker_arm_and_steps_on_both():
    weaker = _rule(_sets(11, 11, 11), _sets(15, 15, 15, left=[13, 13, 13]))
    assert weaker["aim"] == 13
    one_arm_past = _rule(_sets(11, 11, 11), _sets(16, 16, 16, left=[14, 14, 14]))
    assert one_arm_past["action"] == "hold" and one_arm_past["weight"] == 6.0


def test_the_last_set_under_the_range_twice_takes_the_weight_back():
    plan = _rule(_sets(12, 12, 12), _sets(10, 9, 8), _sets(10, 9, 8))
    assert (plan["weight"], plan["action"]) == (4.0, "step_back")


def test_the_failed_week_hold_and_a_blocked_step():
    hold = engine.repeat_aim_progression(10, 15, _history(_sets(12, 12, 11)), 6.0, 12,
                                         increment=2.0, prescribed_sets=3, hold=True)
    assert (hold["weight"], hold["aim"], hold["action"]) == (6.0, 11, "held")
    blocked = engine.repeat_aim_progression(10, 15, _history(_sets(16, 16, 16)), 6.0, 12,
                                            increment=2.0, prescribed_sets=3, allow_step=False)
    assert (blocked["weight"], blocked["action"]) == (6.0, "hold")


def test_no_history_is_the_plan():
    plan = engine.repeat_aim_progression(10, 15, [], 2.0, 12, increment=2.0, prescribed_sets=3)
    assert (plan["weight"], plan["aim"], plan["action"]) == (2.0, 12, "start")


# ─── His own sessions ───────────────────────────────────────────────────────

def _real(rows):
    return [(d, [{"reps": r, "weight": w} for r, w in sets]) for d, sets in rows]


def test_his_hip_flexion_reads_15_after_11_nov_and_8_kg_after_19_nov():
    """WP-54: "On standing hip flexion I did 6kg x 15 x 3 but this week I started
    on 11 reps ?? Why it should be at 15??"."""
    rows = [("2026-11-11", [(15, 6)] * 3), ("2026-11-04", [(13, 6), (13, 6), (14, 6)]),
            ("2026-10-27", [(12, 6)] * 3), ("2026-10-20", [(12, 2)] * 3)]
    before = engine.repeat_aim_progression(10, 15, _real(rows), 2.0, 12, increment=2.0,
                                           prescribed_sets=3)
    assert (before["weight"], before["aim"]) == (6.0, 15)
    after = engine.repeat_aim_progression(
        10, 15, _real([("2026-11-19", [(11, 6), (12, 6), (18, 6)])] + rows), 2.0, 12,
        increment=2.0, prescribed_sets=3)
    assert (after["weight"], after["aim"], after["action"]) == (8.0, 10, "step_up")


def test_his_crossover_reads_8_kg_by_12():
    rows = [("2026-11-17", [(12, 8)] * 3), ("2026-11-09", [(16, 6), (16, 6), (10, 8)]),
            ("2026-11-03", [(16, 6)] * 3), ("2026-10-29", [(15, 6), (15, 6), (16, 6)]),
            ("2026-10-26", [(15, 4), (15, 6), (18, 6)]), ("2026-10-23", [(15, 3), (15, 4), (15, 5)])]
    plan = engine.repeat_aim_progression(10, 15, _real(rows), 3.0, 15, increment=2.0,
                                         prescribed_sets=3)
    assert (plan["weight"], plan["aim"], plan["times"]) == (8.0, 12, 1)


# ─── The four lifts in the block ────────────────────────────────────────────

def _lift(name):
    return next(e for d in gb.SESSIONS.values() for e in d if e["name"] == name)


def test_the_four_lifts_run_the_rule_through_the_seed():
    hf = _lift("Standing Cable Hip Flexion")
    lp = {"session_date": "2026-11-11", "reps": 15, "weight_kg": 6.0}
    entry = sessions.resolve_prescription(
        hf, lp, "normal", {"reduced": False}, weight_increment=hf["increment_size"],
        history=_real([("2026-11-11", [(15, 6)] * 3), ("2026-11-04", [(13, 6), (13, 6), (14, 6)])]))
    assert (entry["weight_kg"], entry["reps"], entry["times_at_aim"]) == (6.0, 15, 1)
    assert "do it once more" in sessions.actual_caption(entry)
    assert entry["next_step"] == (
        "The aim goes up one rep after two sessions with every set at the aim. The weight goes "
        "up when, on both arms, every set reaches 15 with an aim of 15, or one set goes past 15.")
    for name in LIFTS:
        assert sessions.repeats_aim(_lift(name)), name


def test_a_step_on_the_rule_says_the_aim_is_the_bottom():
    y = _lift("Single-Arm Cable Y Raise")
    lp = {"session_date": "2026-11-11", "reps": 16, "weight_kg": 6.0}
    entry = sessions.resolve_prescription(
        y, lp, "normal", {"reduced": False}, weight_increment=y["increment_size"],
        history=[("2026-11-11", _sets(16, 16, 16))])
    assert (entry["weight_kg"], entry["reps"], entry["action"]) == (8.0, 10, "step_up")
    assert sessions.actual_caption(entry).endswith("and the aim is the bottom of the range.")


# ─── The back extension's steps (WP-53) ─────────────────────────────────────

FINE = gb.BACK_EXTENSION_FINE_STEP


def test_the_back_extension_steps_1_kg_from_5_to_10_kg():
    up = [0.0]
    while up[-1] < 15:
        up.append(engine.step_weight(up[-1], 1, 2.5, FINE))
    assert up == [0.0, 2.5, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.5, 15.0]
    assert engine.step_weight(7.5, 1, 2.5, FINE) == 8.0
    assert engine.step_weight(7.5, -1, 2.5, FINE) == 7.0
    assert engine.step_weight(12.5, -1, 2.5, FINE) == 10.0
    assert engine.step_weight(5.0, -1, 2.5, FINE) == 2.5
    assert engine.step_weight(3.0, 1, 2.5, FINE) == 5.0
    assert engine.step_weight(7.5, 1, 2.5) == 10.0  # without the band: a plate


def test_the_back_extension_steps_from_7_5_to_8_kg():
    be = _lift("45° Back Extension")
    assert be["fine_step"] == {"from_kg": 5.0, "to_kg": 10.0, "step": 1.0}
    plan = engine.range_progression(8, 12, [("2026-11-19", _sets(12, 12, 12, weight=7.5))],
                                    0.0, 12, increment=2.5, prescribed_sets=3,
                                    fine_step=be["fine_step"])
    assert (plan["weight"], plan["action"]) == (8.0, "step_up")
    lp = {"session_date": "2026-11-19", "reps": 12, "weight_kg": 7.5}
    entry = sessions.resolve_prescription(
        be, lp, "normal", {"reduced": False}, weight_increment=be["increment_size"],
        history=[("2026-11-19", _sets(*[be["rep_max"]] * 3, weight=7.5))])
    assert (entry["weight_kg"], entry["action"]) == (8.0, "step_up")
    top = sessions.resolve_prescription(
        be, lp, "normal", {"reduced": False}, weight_increment=be["increment_size"],
        history=[("2026-11-19", _sets(*[be["rep_max"]] * 3, weight=10.0))])
    assert top["weight_kg"] == 12.5


def test_a_low_streak_lowers_the_back_extension_one_fine_step():
    be = _lift("45° Back Extension")
    lp = {"session_date": "2026-11-19", "reps": 10, "weight_kg": 8.0}
    entry = sessions.resolve_prescription(
        be, lp, "low", {"reduced": False}, weight_increment=be["increment_size"],
        history=[("2026-11-19", _sets(10, 10, 10, weight=8.0))])
    assert entry["weight_kg"] == 7.0
