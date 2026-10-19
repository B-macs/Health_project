"""The reps of a bodyweight exercise can be changed, and the change is logged.

Athlete, 2026-10-13: "I should be able to adjust the reps on the body weight
exercises." Until then only a loaded exercise had a stepper: an unloaded one
showed a fixed number and every set logged the prescription, so a session where
he did 20 lifts a side on a written 10 recorded 10 (it is how the psoas march
came to be written at the wrong dose). Holds and hold_reps stay fixed — the
per-rep timer counts them.
"""
from __future__ import annotations

import pathlib

import training_plan as tp
from services import sessions as sess

ROOT = pathlib.Path(__file__).resolve().parent.parent
B = tp.PLAN_BLOCK_B


def _ex(day: int, name: str) -> dict:
    return next(e for e in B[day]["exercises"] if e["name"] == name)


def test_every_unloaded_reps_exercise_of_the_live_block_gets_a_stepper():
    unloaded = {e["name"] for d in B for e in B[d]["exercises"]
                if e["type"] == "reps" and not e.get("equipment_type")}
    assert {"Standing Psoas March", "90/90 Hip Lift", "Hip Airplane", "Dead Bug",
            "Adductor Lift (Side-Lying)"} <= unloaded
    for d in B:
        for e in B[d]["exercises"]:
            if e["name"] in unloaded:
                assert sess.reps_are_editable(e), (d, e["name"])


def test_holds_and_timed_reps_stay_fixed_and_loaded_lifts_are_unchanged():
    assert not sess.reps_are_editable(_ex(1, "Forearm Plank"))
    assert not sess.reps_are_editable(_ex(1, "Single-Leg Glute Bridge"))   # hold_reps
    assert not sess.reps_are_editable(_ex(3, "Bird-Dog"))                  # hold_reps
    assert sess.reps_are_editable(_ex(1, "Goblet Squat"))


def test_the_entry_starts_at_the_prescription_with_no_weight():
    march = _ex(1, "Standing Psoas March")
    entry = sess.bodyweight_entry(march)
    assert entry["reps"] == march["reps"] == 20
    assert entry["weight_kg"] is None and entry["band_tier"] is None
    assert entry["source"] == sess.BODYWEIGHT_SOURCE
    assert "Change them if you do a different number" in sess.actual_caption(entry)


def test_a_changed_count_is_what_the_set_logs_and_what_the_screen_says():
    lift = _ex(1, "90/90 Hip Lift")
    entry = sess.bodyweight_entry(lift)
    entry["reps"] = sess.step_reps(entry["reps"], +1)
    assert entry["reps"] == lift["reps"] + 1
    record = sess.build_set_record(lift, 1, entry, "2026-10-13T09:00:00+02:00")
    assert record["reps"] == lift["reps"] + 1
    assert sess.displayed_prescription(lift, entry)["reps"] == lift["reps"] + 1
    untouched = sess.build_set_record(lift, 1, None, "2026-10-13T09:00:00+02:00")
    assert untouched["reps"] == lift["reps"], "no entry still logs the prescription"


def test_the_screen_seeds_steppers_and_saves_them_for_unloaded_exercises():
    src = (ROOT / "views" / "training.py").read_text(encoding="utf-8")
    # The seeding moved to services/prescription.py on 2026-10-19.
    seed_src = (ROOT / "services" / "prescription.py").read_text(encoding="utf-8")
    assert "prescription.seed_exercise(" in src
    assert "sess.bodyweight_entry(ex)" in seed_src
    assert "if not loaded and not sess.reps_are_editable(ex):" in seed_src
    # The save moved to services/session_save.py on 2026-10-19 (the save the
    # phone's API uses too); tests/test_session_save.py stores a march's reps.
    save_src = (ROOT / "services" / "session_save.py").read_text(encoding="utf-8")
    assert 'if actual and (ex.get("equipment_type") or sess.reps_are_editable(ex)):' in save_src
    assert "if st.session_state.tp_actuals.get(_eidx) is None:" in src, (
        "the fixed number shows only where no stepper does")
