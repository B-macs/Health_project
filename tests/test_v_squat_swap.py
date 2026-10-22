"""The V squat in the hack squat's place when its machine is in use (WP-28).

The owner's note of 2026-10-22: "There should be an option to change the type
of the exercise if the machine isn't available - hack squat change to V squat",
and his answers 9 and 10: the V squat now, other alternatives when he names
them; his gym has no pendulum squat; a session with a swap counts as done, is
not a flare-up, and gate 1's +10% reads only the main lift's own sets.
"""

from __future__ import annotations

import inspect

import goal_block as gb
import goal_week as gw
import training_constants as tc
from services import gate1, rules, session_order
from services import sessions as s


def test_the_hack_squat_swaps_for_the_v_squat_and_its_ramp():
    alt = session_order.alternatives_for("Hack Squat")
    assert [e["name"] for e in alt] == ["V Squat (Ramp Set)", "V Squat"]
    assert s.ramp_lift_index(alt, 0) == 1, "the ramp follows its own lift"
    hack = next(e for e in gb.SESSIONS["B"] if e["name"] == "Hack Squat")
    v = alt[1]
    for key in ("equipment_type", "increment_size", "increment_unit", "sets", "rep_min", "rep_max"):
        assert v[key] == hack[key], key
    assert session_order.alternatives_for("Romanian Deadlift (DB)") == []


def test_the_v_squat_went_through_the_workflow():
    """Key Rule 25: goal, area, reason, source and the better check, and his
    pendulum-squat answer is the check."""
    pick = gw.pick_for("V Squat")
    assert pick is not None and pick.area == "quads" and pick.better
    assert "2026-10-22" in pick.source and "pendulum" in pick.better
    assert gw.pick_for("V Squat (Ramp Set)") is gw.PICKS["Ramp set"]


def test_the_v_squat_has_a_safety_rule_and_its_three_map_entries():
    for name in ("V Squat", "V Squat (Ramp Set)"):
        assert rules.check_movement(name, 2)["severity"] == "caution", name
        assert tc.EXERCISE_BODY_REGION[name] == "lower_body"
        assert tc.EXERCISE_MOVEMENT_WEIGHT[name] == tc.EXERCISE_MOVEMENT_WEIGHT["Hack Squat"]
        assert tc.EXERCISE_REGION_SHARES[name] == tc.EXERCISE_REGION_SHARES["Hack Squat"]


def test_the_v_squat_text_is_instructions_only():
    """Key Rule 20: what the screen shows says what to do; no date, no file."""
    text = gb.V_SQUAT["mechanics"]
    assert "2026" not in text and "tier_lists" not in text and "RIGHT" in text


def test_gate_one_reads_only_the_hack_squats_own_sets():
    """A swap changes no gate-1 lift: the main lifts are read by their own
    names, and nothing in a save records a flare-up."""
    assert "Hack Squat" in gate1.MAIN_LIFTS and "V Squat" not in gate1.MAIN_LIFTS
    from services import training_session
    assert "record_flare" not in inspect.getsource(training_session)
