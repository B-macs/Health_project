"""A low-readiness day shortens the working sets, never the warm-up or a test.

The athlete, August 2026: "The warm up and the release doesn't need to be
increased in time and reps when I have a better readiness like my active
workouts, if anything it should be increased when my readiness is lower - if
there is science behind that. Otherwise keep it as the min when readiness is
low." And 2026-10: "Some timers shouldn't go down when I'm under performing like
hip lifts."

The first half was already true from 2026-09-16 (Key Rule 23: readiness never
raises load). The second was not: the readiness volume factor ran over EVERY
exercise in views/training.py, so a 0.75 morning took the psoas march from 20
lifts a side to 15, the planks from 20 s to 15 and the day-28 timed tests from
40 s to 30 — and the engine's 5-second floor made a 2-second glute-bridge hold
LONGER. No study sets a warm-up's length from a readiness score, so the warm-up
holds at its prescription. sessions.readiness_scales is the rule and
sessions.readiness_dose applies it; the view calls nothing else.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

import training_plan as tp
from services import engine
from services import sessions as sess

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOW_FACTORS = (0.9, 0.82, 0.75, 0.6, 0.5)

BLOCK_B = tp.PLAN_BLOCK_B
ALL_BLOCK_B = [(d, ex) for d in sorted(BLOCK_B) for ex in BLOCK_B[d]["exercises"]]


def _dose(ex: dict) -> tuple:
    return tuple(ex.get(k) for k in ("sets", "reps", "reps_in_set", "hold_seconds",
                                     "duration_minutes"))


@pytest.mark.parametrize("factor", LOW_FACTORS)
def test_every_warm_up_item_keeps_its_prescription(factor):
    """The march, the planks, the 90/90 hip lift, the hip airplane, the glute
    bridge, the raise: every preparation item of the live block."""
    for d, ex in ALL_BLOCK_B:
        if ex["name"] in sess.PREPARATION_NAMES:
            assert sess.readiness_dose(ex, factor, BLOCK_B[d]["day_type"]) is ex, (d, ex["name"])


@pytest.mark.parametrize("factor", LOW_FACTORS)
def test_nothing_on_the_test_day_is_shortened(factor):
    """Day 28 re-times the Bunkie lines. A hold shortened on a low morning
    would read as a weaker trunk — it would measure the morning."""
    for ex in BLOCK_B[28]["exercises"]:
        assert sess.readiness_dose(ex, factor, BLOCK_B[28]["day_type"]) is ex, ex["name"]
    assert any("(Timed)" in ex["name"] for ex in BLOCK_B[28]["exercises"]), (
        "the test day still carries timed lines, so this check has something to hold")


def test_ramp_sets_and_finding_tests_keep_their_prescription():
    ramps = [ex for _d, ex in ALL_BLOCK_B if ex.get("warmup")]
    assert ramps, "Block B still ramps its compounds"
    for ex in ramps:
        assert not sess.readiness_scales(ex)
    tests = [ex for _d, ex in ALL_BLOCK_B if sess.is_measurement(ex["name"])]
    assert tests, "Block B still grades the grip on Wednesday"
    for ex in tests:
        assert not sess.readiness_scales(ex)


def test_the_working_sets_still_shorten():
    """The rule narrows what the factor reaches; it does not switch it off."""
    squat = next(ex for ex in BLOCK_B[1]["exercises"] if ex["name"] == "Goblet Squat")
    assert sess.readiness_scales(squat, "main")
    assert sess.readiness_dose(squat, 0.5, "main")["reps"] < squat["reps"]
    curl_up = next(ex for ex in BLOCK_B[3]["exercises"]
                   if ex["name"] == "McGill Curl-Up (Progressed)")
    assert sess.readiness_dose(curl_up, 0.5, "rest")["reps_in_set"] < curl_up["reps_in_set"]


@pytest.mark.parametrize("factor", LOW_FACTORS)
def test_no_floor_ever_lengthens_an_item(factor):
    """The 5-second and 5-minute floors used to lift shorter items up to them:
    the glute bridge's 2-second hold ran 5 s and the 3-minute incline walk ran
    5. Readiness may hold or cut; it never adds (Key Rule 23)."""
    every = [ex for plan in (tp.PLAN, tp.PLAN_STAGE2, tp.PLAN_STAGE2B, BLOCK_B)
             for day in plan.values() for ex in day["exercises"]]
    for ex in every:
        scaled = engine.apply_exercise_volume_modifier(ex, factor)
        for key in ("reps", "reps_in_set", "hold_seconds", "duration_minutes"):
            if ex.get(key) is not None:
                assert scaled[key] <= ex[key], (ex["name"], key, ex[key], scaled[key])


def test_the_two_short_items_the_floor_used_to_stretch():
    bridge = engine.apply_exercise_volume_modifier({"hold_seconds": 2, "reps_in_set": 8}, 0.6)
    assert bridge["hold_seconds"] == 2
    walk = engine.apply_exercise_volume_modifier({"duration_minutes": 3}, 0.5)
    assert walk["duration_minutes"] == 3
    # Above the floor the floor still holds a long item up at it.
    assert engine.apply_exercise_volume_modifier({"hold_seconds": 6}, 0.1)["hold_seconds"] == 5


def test_the_badge_says_the_warm_up_stays():
    policy = sess.load_policy({"signal_color": "green"}, {"volume_factor": 0.75,
                                                         "description": "Poor readiness"})
    assert policy["volume_factor"] == 0.75
    assert "warm-up and the tests stay at full dose" in policy["volume_note"]
    plain = sess.load_policy({"signal_color": "green"}, {"volume_factor": 1.0})
    assert "warm-up" not in plain["volume_note"]


def test_the_view_applies_the_factor_through_the_rule_only():
    """One call site, and it is the rule. A direct engine call in the view
    would put the warm-up back under the factor without failing anything
    else."""
    src = (ROOT / "views" / "training.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute)]
    names = {n.func.attr for n in calls}
    assert "apply_exercise_volume_modifier" not in names
    assert "readiness_dose" in names
