"""WP-46, Settings › Weight steps (the athlete, 2026-11-03: "I should have
settings to change the weight increments"; his answer "A": a list of
equipment, each with its step, each exercise linked to one item)."""
from __future__ import annotations

import pytest

import goal_block as gb
from services import equipment as eq
from services import sessions

PLAN = [e for day in gb.SESSIONS.values() for e in day] + [
    e for alts in gb.ALTERNATIVES.values() for e in alts]
NAMES = {e["name"] for e in eq.lifts(PLAN)}


def _body(**steps):
    items = [{"id": i.id, "name": i.name, "step": steps.get(i.id, i.step), "unit": i.unit,
              "kind": i.kind} for i in eq.DEFAULT_ITEMS]
    return {"items": items, "links": {}}


def _ex(name):
    return next(e for e in PLAN if e["name"] == name)


def test_with_nothing_stored_every_lift_steps_as_the_block_wrote_it():
    for ex in PLAN:
        if ex.get("equipment_type") in (None, "band"):
            continue
        got = eq.apply(ex, eq.defaults())
        assert (got["increment_size"], got["increment_unit"]) == (
            ex["increment_size"], ex["increment_unit"]), ex["name"]


def test_a_lift_with_a_dumbbell_in_each_hand_steps_twice_the_dumbbell_step():
    settings = eq.from_stored(eq.validated(_body(dumbbells=2.0), NAMES))
    assert eq.apply(_ex("Romanian Deadlift (DB)"), settings)["increment_size"] == 4.0
    assert eq.apply(_ex("Single-Arm DB Row"), settings)["increment_size"] == 2.0
    assert eq.apply(_ex("Romanian Deadlift (Ramp Set)"), settings)["increment_size"] == 4.0


def test_a_link_moves_a_lift_and_its_ramp_to_another_item():
    body = _body()
    body["items"].append({"id": "custom-1", "name": "Old gym machine", "step": 5.0,
                          "unit": "kg", "kind": "machine"})
    body["links"] = {"Hack Squat": "custom-1"}
    settings = eq.from_stored(eq.validated(body, NAMES))
    assert eq.apply(_ex("Hack Squat"), settings)["increment_size"] == 5.0
    assert eq.apply(_ex("Hack Squat (Ramp Set)"), settings)["increment_size"] == 5.0
    assert eq.apply(_ex("Machine Chest Press"), settings)["increment_size"] == 2.5
    row = next(r for r in eq.answer(settings, PLAN)["exercises"] if r["name"] == "Hack Squat")
    assert row["item_id"] == "custom-1" and row["default_item_id"] == "machines"


def test_a_cable_lift_moved_to_a_kilogram_item_counts_in_kilograms():
    body = _body()
    body["links"] = {"High-to-Low Cable Woodchop": "new_cable_machine"}
    settings = eq.from_stored(eq.validated(body, NAMES))
    traits = eq.with_units(sessions.exercise_traits(), PLAN, settings)
    assert traits["High-to-Low Cable Woodchop"]["unit"] == "kg"
    assert traits["Lat-Pulldown Cable Crunch (Facing Away)"]["unit"] == "unit"


@pytest.mark.parametrize("change, why", [
    (lambda b: b["items"].pop(0), "default items cannot be removed"),
    (lambda b: b["items"][0].update(step=0), "a step is more than 0"),
    (lambda b: b["items"][0].update(step=30), "a step is more than 0"),
    (lambda b: b["items"][0].update(unit="lb"), "a unit is one of"),
    (lambda b: b["items"][0].update(kind="band"), "a kind is one of"),
    (lambda b: b["items"][0].update(name=""), "name is 1 to"),
    (lambda b: b["items"].append(dict(b["items"][0])), "same id"),
    (lambda b: b["links"].update({"Not A Lift": "machines"}), "no exercise is called"),
    (lambda b: b["links"].update({"Hack Squat": "nowhere"}), "no item has the id"),
])
def test_a_list_the_engine_refuses_says_why(change, why):
    body = _body()
    change(body)
    with pytest.raises(eq.InvalidSettings, match=why):
        eq.validated(body, NAMES)


def test_a_damaged_stored_list_reads_as_the_defaults_where_it_is_damaged():
    settings = eq.from_stored({"items": [{"id": "machines", "step": "x"}],
                               "links": {"Hack Squat": "gone"}})
    assert settings.item("machines").step == 2.5
    assert settings.links == {}


def test_the_settings_list_names_each_lift_once_and_no_ramp_set():
    names = [r["name"] for r in eq.answer(eq.defaults(), PLAN)["exercises"]]
    assert len(names) == len(set(names))
    assert not any(sessions.RAMP_SUFFIX in n for n in names)
    assert {"Hack Squat", "V Squat", "Single-Arm Cable Y Raise"} <= set(names)
