"""WP-46, a replacement made in a session (the athlete, 2026-11-03: "if the
machine with the current settings isnt available I should be able to do
another machine or free weight by creating it easy in the app., this doesnt
change the muscles worked on the exercise replacement"; "a it is now offered
every time")."""
from __future__ import annotations

from datetime import date

import pytest

import goal_block as gb
import training_constants as tc
from services import equipment as eq
from services import replacements as rp
from services import sessions

TODAY = date(2026, 11, 3)
PLAN = [e for d in gb.SESSIONS.values() for e in d] + [
    e for alts in gb.ALTERNATIVES.values() for e in alts]
LIFTS = {e["name"] for e in eq.lifts(PLAN)}
KNOWN = set(sessions.exercise_traits()) | {e["name"] for e in PLAN}
TABLES = (tc.EXERCISE_BODY_REGION, tc.EXERCISE_REGION_SHARES, tc.EXERCISE_MOVEMENT_WEIGHT)


def _add(stored, lift="Hack Squat", name="Smith Machine Squat", item="machines"):
    return rp.validated(stored, lift, name, item, lift_names=LIFTS, known_names=KNOWN,
                        settings=eq.defaults(), today=TODAY)


def test_a_replacement_is_stored_under_its_lift_and_the_same_name_twice_stores_one():
    stored, entry = _add({})
    assert stored == {"Hack Squat": [{"name": "Smith Machine Squat", "item_id": "machines",
                                      "created": "2026-11-03"}]}
    again, same = _add(stored, name="  smith machine   squat ")
    assert again is stored and same == entry


@pytest.mark.parametrize("kwargs, why", [
    ({"lift": "Standing Psoas March"}, "is not a lift with a weight"),
    ({"name": "  "}, "the name is 1 to"),
    ({"name": "x" * 41}, "the name is 1 to"),
    ({"name": "Machine Chest Press"}, "already called"),
    ({"name": "V Squat"}, "already called"),
    ({"item": "nowhere"}, "not on the list"),
])
def test_a_replacement_the_engine_refuses_says_why(kwargs, why):
    with pytest.raises(rp.ReplacementRefused, match=why):
        _add({}, **kwargs)


def test_a_name_another_lifts_replacement_has_is_taken():
    stored, _ = _add({})
    with pytest.raises(rp.ReplacementRefused, match="already called"):
        _add(stored, lift="Machine Chest Press", name="Smith Machine Squat")


def test_it_keeps_the_lifts_sets_range_rest_and_side_and_takes_its_items_step():
    hack = next(e for e in gb.SESSIONS["B"] if e["name"] == "Hack Squat")
    ramp = next(e for e in gb.SESSIONS["B"] if e["name"] == "Hack Squat (Ramp Set)")
    _, entry = _add({})
    group = rp.exercises_for(hack, entry, eq.defaults(), ramp)
    assert [e["name"] for e in group] == ["Smith Machine Squat (Ramp Set)", "Smith Machine Squat"]
    repl = group[-1]
    for key in ("sets", "reps", "rep_min", "rep_max", "rest_seconds", "laterality", "type"):
        assert repl[key] == hack[key], key
    assert (repl["equipment_type"], repl["increment_size"], repl["weight_kg"]) == ("machine", 2.5, 0.0)
    assert repl["replacement_for"] == "Hack Squat" and repl["warning"] is None
    assert group[0]["warmup"] is True
    assert sessions.base_name(group[0]["name"]) == sessions.base_name(repl["name"])


def test_a_pair_lift_on_free_weights_steps_both_hands_and_on_a_machine_one_step():
    rdl = next(e for e in gb.SESSIONS["B"] if e["name"] == "Romanian Deadlift (DB)")
    on_dumbbells = rp.exercises_for(rdl, {"name": "Kettlebell RDL", "item_id": "dumbbells"},
                                    eq.defaults(), None)[-1]
    on_machine = rp.exercises_for(rdl, {"name": "Machine RDL", "item_id": "machines"},
                                  eq.defaults(), None)[-1]
    assert on_dumbbells["increment_size"] == 5.0 and on_machine["increment_size"] == 2.5


def test_it_counts_in_the_lifts_body_areas_and_never_overwrites_a_name():
    stored, _ = _add({}, name="Pendulum Squat Test Name")
    try:
        rp.register(stored)
        for table in TABLES:
            assert table["Pendulum Squat Test Name"] == table["Hack Squat"]
            assert table["Pendulum Squat Test Name (Ramp Set)"] == table["Hack Squat (Ramp Set)"]
        before = tc.EXERCISE_BODY_REGION["Machine Chest Press"]
        rp.register({"Hack Squat": [{"name": "Machine Chest Press", "item_id": "machines"}]})
        assert tc.EXERCISE_BODY_REGION["Machine Chest Press"] == before
    finally:
        for table in TABLES:
            table.pop("Pendulum Squat Test Name", None)
            table.pop("Pendulum Squat Test Name (Ramp Set)", None)


def test_its_traits_are_the_lifts_in_its_items_unit():
    stored = {"Single-Arm DB Row": [{"name": "Cable Row One Arm", "item_id": "cables"}]}
    traits = rp.traits(stored, sessions.exercise_traits(), eq.defaults())
    assert traits["Cable Row One Arm"]["one_arm"] is True
    assert traits["Cable Row One Arm"]["sides"] == 2 and traits["Cable Row One Arm"]["unit"] == "unit"
