"""Tests for services/sessions.py — pure training-session logic extracted
from views/training.py."""

import ast
from datetime import date, datetime, timezone


# ─── set_timestamp — the 2026-08-06 two-hour skew ──────────────────────────

def test_set_timestamp_renders_in_the_athletes_zone_not_the_hosts():
    """The bug this replaces: a bare datetime.now() on a UTC host recorded a
    13:08 local set as 11:08, and an offset-free ISO string gives no hint it
    is wrong. Verified with the real instant from 2026-08-06."""
    utc_instant = datetime(2026, 8, 6, 11, 8, 27, tzinfo=timezone.utc)
    assert sessions.set_timestamp(utc_instant, "Europe/Berlin") == "2026-08-06T13:08:27+02:00"


def test_set_timestamp_is_always_offset_aware():
    """An instant carrying its offset can be converted by any reader; a naive
    one cannot be recovered without knowing which host wrote it."""
    for tz in ("Europe/Berlin", "UTC", ""):
        out = sessions.set_timestamp(datetime(2026, 8, 6, 11, 8, 27, tzinfo=timezone.utc), tz)
        assert datetime.fromisoformat(out).utcoffset() is not None
        # Same instant regardless of how it is rendered.
        assert datetime.fromisoformat(out) == datetime(2026, 8, 6, 11, 8, 27, tzinfo=timezone.utc)


def test_set_timestamp_handles_dst_rather_than_a_fixed_offset():
    """Berlin is +02:00 in August and +01:00 in January. A configured fixed
    offset would be an hour wrong for half the year."""
    summer = sessions.set_timestamp(datetime(2026, 8, 6, 11, 0, tzinfo=timezone.utc), "Europe/Berlin")
    winter = sessions.set_timestamp(datetime(2026, 1, 6, 11, 0, tzinfo=timezone.utc), "Europe/Berlin")
    assert summer.endswith("+02:00") and winter.endswith("+01:00")


def test_set_timestamp_falls_back_rather_than_raising_on_a_bad_zone():
    """A typo in config must not cost a logged set mid-session."""
    out = sessions.set_timestamp(datetime(2026, 8, 6, 11, 8, 27, tzinfo=timezone.utc), "Not/AZone")
    assert datetime.fromisoformat(out) == datetime(2026, 8, 6, 11, 8, 27, tzinfo=timezone.utc)

import pytest

from services import engine, sessions
from services.models import Phase

_PHASE = Phase(phase_number=1, name="Stage 1 Rehab", start_date="2026-06-29",
                length_days=14, status="active")


# ─── coach_message ──────────────────────────────────────────────────────────

def test_coach_message_prefers_the_engine_directive():
    headline, subtitle = sessions.coach_message(
        {"action": "Reduced load today."}, {"objective": "Fallback", "phase": "Week 2"})
    assert headline == "Reduced load today."
    assert subtitle == "Week 2"


def test_coach_message_falls_back_to_clinical_objective():
    headline, _ = sessions.coach_message({"action": ""}, {"objective": "Tissue Tolerance", "phase": "Week 1"})
    assert headline == "Tissue Tolerance"


# ─── is_run_or_walk ──────────────────────────────────────────────────────────

def test_is_run_or_walk_matches_walking_exercises():
    assert sessions.is_run_or_walk({"name": "Controlled Walking"}) is True
    assert sessions.is_run_or_walk({"name": "Walking — Gait Focus"}) is True
    assert sessions.is_run_or_walk({"name": "5-Minute Walk + Stair Assessment"}) is True


def test_is_run_or_walk_does_not_false_positive_on_trunk():
    # Plain substring matching would wrongly match "run" inside "Trunk".
    assert sessions.is_run_or_walk({"name": "Trunk Rotation"}) is False


def test_is_run_or_walk_false_for_unrelated_exercise():
    assert sessions.is_run_or_walk({"name": "Glute Bridge"}) is False


# ─── summarize_garmin_activities ─────────────────────────────────────────────

def test_summarize_garmin_activities_single_match():
    matched = [{"duration": 900.0, "averageHR": 106.0, "maxHR": 144.0,
                "distance": 1894.75, "calories": 312.0}]
    summary = sessions.summarize_garmin_activities(matched)
    assert summary == {"avg_hr": 106, "max_hr": 144.0, "distance_km": 1.89, "calories": 312}


def test_summarize_garmin_activities_sums_and_weights_multiple_matches():
    matched = [
        {"duration": 600.0, "averageHR": 100.0, "maxHR": 120.0, "distance": 800.0, "calories": 100.0},
        {"duration": 300.0, "averageHR": 130.0, "maxHR": 150.0, "distance": 400.0, "calories": 50.0},
    ]
    summary = sessions.summarize_garmin_activities(matched)
    # duration-weighted avg_hr: (100*600 + 130*300) / 900 = 110
    assert summary["avg_hr"] == 110
    assert summary["max_hr"] == 150.0
    assert summary["distance_km"] == 1.2
    assert summary["calories"] == 150


def test_summarize_garmin_activities_blanks_missing_fields_instead_of_zero():
    # A Stopwatch-type activity with no HR/distance data at all.
    matched = [{"duration": 600.0}]
    summary = sessions.summarize_garmin_activities(matched)
    assert summary == {"avg_hr": None, "max_hr": None, "distance_km": None, "calories": None}


def test_summarize_garmin_activities_empty_list():
    assert sessions.summarize_garmin_activities([]) == {
        "avg_hr": None, "max_hr": None, "distance_km": None, "calories": None,
    }


# ─── movement_category ──────────────────────────────────────────────────────

def test_movement_category_hip_hinge():
    assert sessions.movement_category({"name": "Glute Bridge"}) == "Hip Hinge"


def test_movement_category_core_stability():
    assert sessions.movement_category({"name": "Bird-Dog"}) == "Core Stability"


def test_movement_category_defaults_to_mobility():
    assert sessions.movement_category({"name": "Cat-Cow"}) == "Mobility"


# ─── movement_category — 2026-08-01 mislabelling fix ────────────────────────
#
# The cascade's final `return "Mobility"` used to swallow every upper-body
# lift in the Stage 2 plan. All five names below were logged and displayed
# as "Mobility"; three of them were logged that way on 2026-07-30 alongside
# 4,350 kg of tonnage.

def test_loaded_upper_body_lifts_are_not_labelled_mobility():
    for name, expected in [
        ("Lat Pulldown",      "Upper Body Pull"),
        ("Single-Arm DB Row", "Upper Body Pull"),
        ("Face Pull (Cable)", "Upper Body Pull"),
        ("Incline DB Press",  "Upper Body Push"),
        ("Hip Thrust (Loaded)", "Hip Hinge"),
    ]:
        assert sessions.movement_category({"name": name}) == expected


def test_pallof_press_stays_core_stability_despite_the_press_keyword():
    """Order dependency worth pinning: the core check must run before the
    push check, or anti-rotation core work becomes Upper Body Push."""
    assert sessions.movement_category({"name": "Pallof Press (Cable)"}) == "Core Stability"
    assert sessions.movement_category(
        {"name": "Pallof Press Hold (Doorframe)"}) == "Core Stability"


def test_side_lying_hip_abduction_is_isolation_not_core():
    """Distinct from the Side Bridge family, which the 'side bridge'/'side
    lying' keywords are actually for."""
    assert sessions.movement_category({"name": "Side-Lying Hip Abduction"}) == "Isolation"
    assert sessions.movement_category(
        {"name": "Side Bridge (Modified — Bent Knee)"}) == "Core Stability"


def test_band_and_step_walks_are_not_conditioning():
    """A Lateral Band Walk is a banded glute activation drill done on the
    spot; only actual locomotion is conditioning."""
    assert sessions.movement_category({"name": "Lateral Band Walk"}) == "Mobility"
    assert sessions.movement_category({"name": "Controlled Walking"}) == "Conditioning"


def test_bodyweight_squat_patterns_are_labelled_by_pattern():
    for name in ("Chair Sit-to-Stand", "Forward Step-Up (Stair)",
                 "Reverse Lunge", "Wall Sit (Extended Duration)"):
        assert sessions.movement_category({"name": name}) == "Squat Pattern"


def test_unknown_name_falls_back_to_the_movement_weight_table_category():
    """A name absent from every keyword branch is only called Mobility when
    the weight table agrees it is mobility work."""
    assert sessions.movement_category({"name": "Clamshell"}) == "Isolation"
    assert sessions.movement_category({"name": "Sciatic Nerve Floss"}) == "Mobility"
    assert sessions.movement_category({"name": "Entirely Invented Move"}) == "Mobility"


def test_no_planned_exercise_is_silently_labelled_mobility_while_carrying_load():
    """The invariant behind the fix: nothing weighted above the isolation
    tier may be displayed as Mobility."""
    import training_constants as tc
    mobility_weight = dict(tc.EXERCISE_MOVEMENT_WEIGHT.values())["mobility_core"]
    isolation_weight = dict(tc.EXERCISE_MOVEMENT_WEIGHT.values())["isolation"]
    for name, (_category, weight) in tc.EXERCISE_MOVEMENT_WEIGHT.items():
        if weight > isolation_weight:
            assert sessions.movement_category({"name": name}) != "Mobility", (
                f"{name!r} is weighted {weight} but displays as Mobility"
            )
        assert mobility_weight <= weight


def test_focus_areas_deduplicates_preserving_order():
    exercises = [{"name": "Bird-Dog"}, {"name": "Glute Bridge"}, {"name": "Dead Bug"}]
    assert sessions.focus_areas(exercises) == ["Core Stability", "Hip Hinge"]


# ─── split_release_and_main ────────────────────────────────────────────────

def test_split_release_and_main():
    exercises = [
        {"name": "Upper Glute / TFL Self-Release"},
        {"name": "Bird-Dog"},
        {"name": "Right Posterior Hip Capsule Stretch"},
    ]
    release, main = sessions.split_release_and_main(exercises)
    assert [e["name"] for e in release] == [
        "Upper Glute / TFL Self-Release", "Right Posterior Hip Capsule Stretch"]
    assert [e["name"] for e in main] == ["Bird-Dog"]


# ─── prescription_label / make_sets_data / estimate_duration ──────────────

def test_prescription_label_hold():
    ex = {"type": "hold", "laterality": "bilateral", "sets": 2, "hold_seconds": 90, "rest_seconds": 30}
    assert sessions.prescription_label(ex) == "2 sets × 90s hold  |  30s rest"


def test_prescription_label_reps_with_tempo():
    ex = {"type": "reps", "laterality": "bilateral", "sets": 2, "reps": 10,
          "tempo": "4-0-4", "rest_seconds": 45}
    assert sessions.prescription_label(ex) == "2 sets × 10 reps  Tempo 4-0-4  |  45s rest"


def test_make_sets_data_reps_produces_one_row_per_set():
    ex = {"type": "reps", "sets": 3, "reps": 10, "rest_seconds": 60}
    rows = sessions.make_sets_data(ex)
    assert len(rows) == 3
    assert rows[0] == {"set_num": 1, "reps": 10, "weight": 0.0, "rest": 60, "tut": 0, "velocity": "controlled"}


def test_make_sets_data_duration_produces_one_row():
    ex = {"type": "duration", "duration_minutes": 3}
    rows = sessions.make_sets_data(ex)
    assert len(rows) == 1
    assert rows[0]["tut"] == 180


def test_make_sets_data_uses_weight_kg_when_present():
    ex = {"type": "reps", "sets": 3, "reps": 10, "rest_seconds": 60, "weight_kg": 20.0}
    rows = sessions.make_sets_data(ex)
    assert all(r["weight"] == 20.0 for r in rows)


def test_make_sets_data_defaults_to_zero_weight_when_absent():
    # Regression guard — existing Stage 1 bodyweight exercises have no
    # weight_kg key at all; must still produce 0.0, not a KeyError.
    ex = {"type": "hold", "sets": 2, "hold_seconds": 30, "rest_seconds": 15}
    rows = sessions.make_sets_data(ex)
    assert all(r["weight"] == 0.0 for r in rows)


def test_make_sets_data_includes_band_tier_when_present():
    ex = {"type": "reps", "sets": 2, "reps": 10, "rest_seconds": 45, "band_tier": "Green"}
    rows = sessions.make_sets_data(ex)
    assert all(r["band_tier"] == "Green" for r in rows)


def test_make_sets_data_omits_band_tier_key_when_absent():
    ex = {"type": "reps", "sets": 1, "reps": 10, "rest_seconds": 45}
    rows = sessions.make_sets_data(ex)
    assert "band_tier" not in rows[0]


# ─── build_set_record (real per-set capture) ───────────────────────────────

_TS = "2026-07-30T18:04:03"


def test_build_set_record_captures_actual_reps_and_weight_over_prescription():
    # The whole point of per-set capture: what the user actually did wins
    # over what the plan prescribed.
    ex = {"type": "reps", "sets": 3, "reps": 10, "rest_seconds": 60, "weight_kg": 10.0}
    rec = sessions.build_set_record(ex, 2, {"reps": 8, "weight_kg": 12.5}, _TS)
    assert rec["set_num"] == 2
    assert rec["reps"] == 8
    assert rec["weight"] == 12.5
    assert rec["ts"] == _TS


def test_build_set_record_consecutive_sets_can_differ():
    # The exact case the old synthesized rows could not represent: a 10/9/8
    # session read back identically to a clean 10/10/10 one.
    ex = {"type": "reps", "sets": 3, "reps": 10, "rest_seconds": 60, "weight_kg": 12.5}
    recs = [
        sessions.build_set_record(ex, 1, {"reps": 10, "weight_kg": 12.5}, _TS),
        sessions.build_set_record(ex, 2, {"reps": 9, "weight_kg": 12.5}, _TS),
        sessions.build_set_record(ex, 3, {"reps": 8, "weight_kg": 12.5}, _TS),
    ]
    assert [r["reps"] for r in recs] == [10, 9, 8]
    assert [r["set_num"] for r in recs] == [1, 2, 3]


def test_build_set_record_falls_back_to_prescription_without_steppers():
    # Bodyweight/release exercises never get a tp_actuals entry seeded.
    ex = {"type": "reps", "sets": 3, "reps": 10, "rest_seconds": 60}
    rec = sessions.build_set_record(ex, 1, None, _TS)
    assert rec["reps"] == 10
    assert rec["weight"] == 0.0


def test_build_set_record_hold_reps_uses_reps_in_set():
    ex = {"type": "hold_reps", "sets": 2, "reps_in_set": 8, "hold_seconds": 3, "rest_seconds": 45}
    rec = sessions.build_set_record(ex, 1, None, _TS)
    assert rec["reps"] == 8
    assert rec["tut"] == 3
    assert rec["velocity"] == "isometric"


def test_build_set_record_hold_is_always_one_rep():
    ex = {"type": "hold", "sets": 2, "hold_seconds": 30, "rest_seconds": 15}
    rec = sessions.build_set_record(ex, 1, {"reps": 99}, _TS)
    assert rec["reps"] == 1
    assert rec["tut"] == 30


def test_build_set_record_duration_carries_seconds_and_no_rest():
    ex = {"type": "duration", "duration_minutes": 3}
    rec = sessions.build_set_record(ex, 1, None, _TS)
    assert rec["tut"] == 180
    assert rec["rest"] == 0
    assert rec["velocity"] == "continuous"


def test_build_set_record_band_tier_from_actual_wins():
    ex = {"type": "reps", "sets": 2, "reps": 10, "rest_seconds": 45, "band_tier": "Green"}
    rec = sessions.build_set_record(ex, 1, {"band_tier": "Blue"}, _TS)
    assert rec["band_tier"] == "Blue"


def test_build_set_record_omits_band_tier_when_neither_has_one():
    ex = {"type": "reps", "sets": 1, "reps": 10, "rest_seconds": 45}
    assert "band_tier" not in sessions.build_set_record(ex, 1, None, _TS)


def test_build_set_record_zero_weight_actual_is_not_treated_as_missing():
    # 0.0 is falsy — a deliberate bodyweight logging must not fall back to
    # the plan's prescribed weight.
    ex = {"type": "reps", "sets": 2, "reps": 10, "rest_seconds": 45, "weight_kg": 20.0}
    rec = sessions.build_set_record(ex, 1, {"reps": 10, "weight_kg": 0.0}, _TS)
    assert rec["weight"] == 0.0


def test_build_set_record_shape_matches_make_sets_data():
    # Downstream readers (Repository.get_recent_sessions' volume math,
    # get_last_session_all_sets, services.volume, engine.double_progression)
    # consume both shapes interchangeably — "ts" is the only addition.
    ex = {"type": "reps", "sets": 3, "reps": 10, "rest_seconds": 60, "weight_kg": 10.0}
    synthesized = sessions.make_sets_data(ex)[0]
    captured = sessions.build_set_record(ex, 1, None, _TS)
    assert set(captured) - set(synthesized) == {"ts"}
    assert set(synthesized) - set(captured) == set()


# ─── upsert_set_record ("← Back" then redo must not duplicate) ─────────────

def test_upsert_set_record_appends_new_set_numbers():
    rows = []
    for n in (1, 2, 3):
        sessions.upsert_set_record(rows, {"set_num": n, "reps": 10, "weight": 12.5})
    assert [r["set_num"] for r in rows] == [1, 2, 3]


def test_upsert_set_record_replaces_same_set_number_in_place():
    # The "← Back", fix it, re-complete flow: set 2 is redone at 8 reps.
    rows = [
        {"set_num": 1, "reps": 10, "weight": 12.5},
        {"set_num": 2, "reps": 10, "weight": 12.5},
        {"set_num": 3, "reps": 10, "weight": 12.5},
    ]
    sessions.upsert_set_record(rows, {"set_num": 2, "reps": 8, "weight": 12.5})
    assert len(rows) == 3                       # no duplicate record
    assert [r["set_num"] for r in rows] == [1, 2, 3]   # order preserved
    assert rows[1]["reps"] == 8                 # overwritten, not appended


def test_upsert_set_record_repeated_redo_still_yields_one_record():
    rows = [{"set_num": 1, "reps": 10, "weight": 12.5}]
    for reps in (9, 8, 7):
        sessions.upsert_set_record(rows, {"set_num": 1, "reps": reps, "weight": 12.5})
    assert len(rows) == 1
    assert rows[0]["reps"] == 7


def test_upsert_set_record_overwrite_changes_derived_tonnage():
    # The propagation guarantee: tonnage is recomputed from these rows, never
    # stored alongside them, so a corrected set is reflected automatically.
    tonnage = lambda rs: sum(r["reps"] * r["weight"] for r in rs)
    rows = [{"set_num": n, "reps": 10, "weight": 12.5} for n in (1, 2, 3)]
    assert tonnage(rows) == 375.0
    sessions.upsert_set_record(rows, {"set_num": 3, "reps": 6, "weight": 12.5})
    assert tonnage(rows) == 325.0


# ─── reps/weight/band-tier steppers ────────────────────────────────────────

def test_step_reps_increments_and_decrements():
    assert sessions.step_reps(8, +1) == 9
    assert sessions.step_reps(8, -1) == 7


def test_step_reps_floors_at_one():
    assert sessions.step_reps(1, -1) == 1


def test_step_weight_kg_increments_by_2_5():
    assert sessions.step_weight_kg(10.0, +1) == 12.5
    assert sessions.step_weight_kg(10.0, -1) == 7.5


def test_step_weight_kg_floors_at_zero():
    assert sessions.step_weight_kg(2.5, -1) == 0.0
    assert sessions.step_weight_kg(0.0, -1) == 0.0


def test_step_weight_kg_respects_custom_increment():
    # Face Pull / Pallof Press: a machine calibrated in its own 1-unit scale,
    # not the default 2.5kg plate/dumbbell jump.
    assert sessions.step_weight_kg(5.0, +1, increment=1) == 6.0
    assert sessions.step_weight_kg(5.0, -1, increment=1) == 4.0


def test_step_band_tier_moves_one_position():
    assert sessions.step_band_tier("Green", +1) == "Blue"
    assert sessions.step_band_tier("Blue", -1) == "Green"


def test_step_band_tier_clamped_at_both_ends():
    assert sessions.step_band_tier("Black", +1) == "Black"
    assert sessions.step_band_tier("Green", -1) == "Green"


# ─── seed_actual_entry ──────────────────────────────────────────────────────

def test_seed_actual_entry_bodyweight_exercise_returns_all_none():
    entry = sessions.seed_actual_entry({"type": "reps", "equipment_type": None}, None, "high", True)
    assert entry == {"reps": None, "weight_kg": None, "band_tier": None,
                      "source": "plan_default", "last_seen_date": None}


def test_seed_actual_entry_no_last_performance_uses_plan_defaults():
    ex = {"type": "reps", "reps": 8, "weight_kg": 10.0, "equipment_type": "dumbbell"}
    entry = sessions.seed_actual_entry(ex, None, "normal", True)
    assert entry["reps"] == 8 and entry["weight_kg"] == 10.0 and entry["source"] == "plan_default"


def test_seed_actual_entry_prefers_last_performance_over_plan():
    ex = {"type": "reps", "reps": 8, "weight_kg": 10.0, "equipment_type": "dumbbell"}
    last = {"reps": 6, "weight_kg": 12.5, "session_date": "2026-07-14"}
    entry = sessions.seed_actual_entry(ex, last, "normal", True)
    assert entry["reps"] == 6 and entry["weight_kg"] == 12.5 and entry["source"] == "last_time"
    assert entry["last_seen_date"] == "2026-07-14"


def test_seed_actual_entry_applies_readiness_nudge_on_top_of_last_performance():
    ex = {"type": "reps", "reps": 8, "weight_kg": 10.0, "equipment_type": "dumbbell"}
    last = {"reps": 6, "weight_kg": 10.0, "session_date": "2026-07-14"}
    entry = sessions.seed_actual_entry(ex, last, "high", True)
    assert entry["weight_kg"] == 12.5


def test_seed_actual_entry_readiness_nudge_respects_custom_weight_increment():
    # Same readiness-nudge path as above, but a unit-based machine (Face
    # Pull / Pallof Press) must nudge by its own 1-unit increment, not the
    # default 2.5kg.
    ex = {"type": "reps", "reps": 10, "weight_kg": 5.0, "equipment_type": "cable"}
    last = {"reps": 8, "weight_kg": 5.0, "session_date": "2026-07-14"}
    entry = sessions.seed_actual_entry(ex, last, "high", True, weight_increment=1)
    assert entry["weight_kg"] == 6.0


def test_seed_actual_entry_suppresses_increase_from_zero_baseline():
    # Bulgarian Split Squat weeks 1-2: bodyweight, plan/history both None/0
    # — a good readiness day must not silently introduce load.
    ex = {"type": "reps", "reps": 8, "weight_kg": None, "equipment_type": "dumbbell"}
    entry = sessions.seed_actual_entry(ex, None, "high", True)
    assert entry["weight_kg"] == 0.0


def test_seed_actual_entry_off_grid_weight_unchanged_on_normal_readiness():
    # Prone Y-Raise uses 1kg accessory dumbbells, not a 2.5kg multiple.
    ex = {"type": "hold_reps", "reps_in_set": 8, "weight_kg": 1.0, "equipment_type": "dumbbell"}
    entry = sessions.seed_actual_entry(ex, None, "normal", True)
    assert entry["weight_kg"] == 1.0
    assert entry["reps"] is None  # hold_reps never gets a reps stepper


def test_seed_actual_entry_band_exercise_gets_tier_not_weight():
    ex = {"type": "reps", "reps": 10, "equipment_type": "band", "band_tier": "Green"}
    entry = sessions.seed_actual_entry(ex, None, "normal", True)
    assert entry["weight_kg"] is None
    assert entry["band_tier"] == "Green"


def test_seed_actual_entry_band_prefers_last_performance_tier():
    ex = {"type": "reps", "reps": 10, "equipment_type": "band", "band_tier": "Green"}
    last = {"reps": 12, "band_tier": "Blue", "weight_kg": 999.0, "session_date": "2026-07-14"}
    entry = sessions.seed_actual_entry(ex, last, "normal", True)
    assert entry["band_tier"] == "Blue"
    assert entry["weight_kg"] is None  # never populated for a band exercise
    assert entry["reps"] == 12


def test_seed_actual_entry_band_applies_readiness_nudge():
    ex = {"type": "reps", "reps": 10, "equipment_type": "band", "band_tier": "Green"}
    entry = sessions.seed_actual_entry(ex, None, "high", True)
    assert entry["band_tier"] == "Blue"


# ─── seed_actual_entry: double progression ─────────────────────────────────

def test_seed_actual_entry_double_progression_fires_and_takes_priority():
    # Goblet Squat shape: rep_min=8, rep_max=10, all last-session sets hit 10.
    ex = {"type": "reps", "reps": 8, "rep_min": 8, "rep_max": 10,
          "weight_kg": 10.0, "equipment_type": "dumbbell"}
    last_session_sets = [{"reps": 10, "weight": 10.0}, {"reps": 10, "weight": 10.0},
                          {"reps": 10, "weight": 10.0}]
    # last_performance would otherwise seed reps=10/weight=10.0 -- double
    # progression must win instead of being overridden by it.
    last_performance = {"reps": 10, "weight_kg": 10.0, "session_date": "2026-07-14"}
    entry = sessions.seed_actual_entry(
        ex, last_performance, "normal", True, last_session_sets=last_session_sets,
    )
    assert entry["weight_kg"] == 12.5
    assert entry["reps"] == 8
    assert entry["source"] == "double_progression"


def test_seed_actual_entry_double_progression_does_not_fire_falls_through():
    # One set falls short of rep_max -- double progression doesn't fire,
    # existing last_performance/readiness-nudge behavior applies unchanged.
    ex = {"type": "reps", "reps": 8, "rep_min": 8, "rep_max": 10,
          "weight_kg": 10.0, "equipment_type": "dumbbell"}
    last_session_sets = [{"reps": 10, "weight": 10.0}, {"reps": 9, "weight": 10.0},
                          {"reps": 10, "weight": 10.0}]
    last_performance = {"reps": 9, "weight_kg": 10.0, "session_date": "2026-07-14"}
    entry = sessions.seed_actual_entry(
        ex, last_performance, "normal", True, last_session_sets=last_session_sets,
    )
    assert entry["source"] == "last_time"
    assert entry["reps"] == 9
    assert entry["weight_kg"] == 10.0


def test_seed_actual_entry_no_last_session_sets_falls_through_unchanged():
    # last_session_sets omitted (defaults to None) -- exact existing
    # behavior, even though rep_min/rep_max are set on the exercise.
    ex = {"type": "reps", "reps": 8, "rep_min": 8, "rep_max": 10,
          "weight_kg": 10.0, "equipment_type": "dumbbell"}
    last_performance = {"reps": 10, "weight_kg": 10.0, "session_date": "2026-07-14"}
    entry = sessions.seed_actual_entry(ex, last_performance, "normal", True)
    assert entry["source"] == "last_time"
    assert entry["reps"] == 10
    assert entry["weight_kg"] == 10.0


def test_seed_actual_entry_double_progression_does_not_fire_on_a_short_session():
    # Integration-level regression guard: ex["sets"] (prescribed count) must
    # thread through to double_progression's prescribed_sets check. Only 1
    # of 3 prescribed sets was logged (session cut short); that one set
    # hits rep_max, but progression must not fire from a partial session.
    ex = {"type": "reps", "reps": 8, "rep_min": 8, "rep_max": 10, "sets": 3,
          "weight_kg": 10.0, "equipment_type": "dumbbell"}
    last_session_sets = [{"reps": 10, "weight": 10.0}]  # only 1 of 3 sets logged
    last_performance = {"reps": 10, "weight_kg": 10.0, "session_date": "2026-07-14"}
    entry = sessions.seed_actual_entry(
        ex, last_performance, "normal", True, last_session_sets=last_session_sets,
    )
    assert entry["source"] != "double_progression"
    assert entry["weight_kg"] == 10.0


def test_seed_actual_entry_double_progression_uses_actual_lifted_weight_not_stale_plan_weight():
    # Integration-level regression guard for the stale-weight bug: ex's
    # plan-authored weight_kg (10.0) is behind what was actually lifted
    # last session (12.5, e.g. from an earlier progression) -- the seeded
    # weight must progress from the real 12.5, not the stale plan value.
    ex = {"type": "reps", "reps": 8, "rep_min": 8, "rep_max": 10, "sets": 3,
          "weight_kg": 10.0, "equipment_type": "dumbbell"}
    last_session_sets = [{"reps": 10, "weight": 12.5}] * 3
    last_performance = {"reps": 10, "weight_kg": 12.5, "session_date": "2026-07-14"}
    entry = sessions.seed_actual_entry(
        ex, last_performance, "normal", True, last_session_sets=last_session_sets,
    )
    assert entry["source"] == "double_progression"
    assert entry["weight_kg"] == 15.0  # 12.5 (actually lifted) + 2.5, not 10.0 (stale) + 2.5


# ─── LOAD RESOLUTION: progression proposes, autoregulation clamps ──────────
#
# Regression suite for the 2026-08-06 contradiction: the session header read
# "Reduced load today — don't push to failure" while Lat Pulldown was
# prescribed 47.5kg x 11, up from 45kg x 10 on both axes. Cause was two
# independently computed signals — engine.traffic_light drove the banner,
# engine.readiness_training_modifier drove the numbers — with the directive
# reaching the prescription through one wire that only tested for "red".
#
# These tests pin the three properties that make it impossible: a green day
# still progresses, a reduced-load day never exceeds the prior session on
# EITHER axis, and the header text is a function of the same object that
# clamps the numbers.

_GREEN = {"signal_color": "green", "multiplier": 1.05, "label": "PROGRESSIVE OVERLOAD"}
_ORANGE = {"signal_color": "orange", "multiplier": 0.75, "label": "REDUCED VOLUME  (−25%)"}
_YELLOW_INJURY = {"signal_color": "yellow", "multiplier": 0.85,
                   "label": "CONSERVATIVE LOAD  (injury weight 80%)"}
_RED = {"signal_color": "red", "multiplier": 0.0, "label": "REST / DELOAD"}
_HIGH_STREAK = {"volume_factor": 1.12, "streak_label": "high", "streak_days": 3,
                 "description": "Strong 3-day readiness -- +12% volume"}
_NEUTRAL = {"volume_factor": 1.0, "streak_label": "normal", "streak_days": 0,
             "description": ""}

# The exact exercise and history from the bug report.
_PULLDOWN = {"name": "Lat Pulldown", "type": "reps", "reps": 10, "sets": 3,
              "weight_kg": 45.0, "equipment_type": "cable",
              "laterality": "bilateral", "rest_seconds": 60}
_PULLDOWN_LAST_SETS = [{"reps": 10, "weight": 45.0}] * 3
_PULLDOWN_LAST_PERF = {"reps": 10, "weight_kg": 45.0, "session_date": "2026-07-30"}


# ── load_policy ────────────────────────────────────────────────────────────

def test_load_policy_green_day_is_not_reduced_and_shows_no_banner():
    p = sessions.load_policy(_GREEN, _HIGH_STREAK)
    assert p["reduced"] is False
    assert p["banner_kind"] == ""
    assert p["banner_text"] == ""
    assert p["volume_factor"] == 1.12  # readiness proposal survives untouched


def test_load_policy_orange_signal_is_reduced_even_though_it_is_not_red():
    # The whole defect in one assertion: the old wire was
    # `allow_increase = signal_color != "red"`, and orange is not red.
    p = sessions.load_policy(_ORANGE, _HIGH_STREAK)
    assert p["reduced"] is True
    assert p["banner_kind"] == "warning"


def test_load_policy_yellow_injury_signal_is_reduced_too():
    p = sessions.load_policy(_YELLOW_INJURY, _HIGH_STREAK)
    assert p["reduced"] is True
    assert p["banner_kind"] == "warning"


def test_load_policy_caps_an_inflating_volume_factor_on_a_reduced_day():
    # readiness wanted +12% reps; the directive says hold. 1.12 -> 1.0, which
    # is what stops round(10 x 1.12) = 11 from ever being built.
    p = sessions.load_policy(_ORANGE, _HIGH_STREAK)
    assert p["volume_factor"] == 1.0
    assert "held at 100%" in p["volume_note"]


def test_load_policy_never_raises_a_reducing_volume_factor():
    low = {"volume_factor": 0.75, "streak_label": "low", "description": "Low readiness"}
    p = sessions.load_policy(_GREEN, low)
    assert p["reduced"] is True          # readiness alone is enough
    assert p["volume_factor"] == 0.75    # clamping is downward-only


def test_load_policy_red_signal_gets_the_rest_banner():
    p = sessions.load_policy(_RED, _HIGH_STREAK)
    assert p["reduced"] is True
    assert p["banner_kind"] == "error"
    assert "Rest day" in p["banner_text"]


def test_load_policy_degrades_to_no_opinion_on_missing_inputs():
    # A failed engine lookup must not read as a green light.
    p = sessions.load_policy(None, None)
    assert p["reduced"] is False
    assert p["volume_factor"] == 1.0
    assert p["banner_text"] == ""


def test_load_policy_records_every_reason_not_just_the_first():
    low = {"volume_factor": 0.75, "streak_label": "low", "description": "Low readiness"}
    p = sessions.load_policy(_ORANGE, low)
    assert len(p["reasons"]) == 3  # signal, multiplier < 1, factor < 1


# ── last_completed_ceiling ─────────────────────────────────────────────────

def test_ceiling_is_the_top_set_not_the_last_set():
    sets = [{"reps": 10, "weight": 45.0}, {"reps": 8, "weight": 47.5},
            {"reps": 8, "weight": 45.0}]
    c = sessions.last_completed_ceiling(None, sets)
    assert c["weight_kg"] == 47.5
    # 8, not 10 -- 47.5 x 10 was never completed and must not be prescribable.
    assert c["reps"] == 8


def test_ceiling_falls_back_to_last_performance_when_sets_are_unavailable():
    c = sessions.last_completed_ceiling(_PULLDOWN_LAST_PERF, None)
    assert c == {"weight_kg": 45.0, "reps": 10, "band_tier": None,
                 "session_date": "2026-07-30"}


def test_ceiling_with_no_history_is_all_none_so_nothing_is_clamped():
    c = sessions.last_completed_ceiling(None, None)
    assert c["weight_kg"] is None and c["reps"] is None and c["band_tier"] is None


def test_ceiling_takes_the_heaviest_band_tier_completed():
    sets = [{"reps": 12, "band_tier": "Green"}, {"reps": 12, "band_tier": "Yellow"}]
    assert sessions.last_completed_ceiling(None, sets)["band_tier"] == "Yellow"


def test_ceiling_falls_back_to_overall_reps_when_top_weight_sets_have_none():
    sets = [{"reps": 12, "weight": None}, {"reps": None, "weight": 20.0}]
    c = sessions.last_completed_ceiling(None, sets)
    assert c["weight_kg"] == 20.0
    assert c["reps"] == 12


# ── clamp_to_ceiling ───────────────────────────────────────────────────────

def test_clamp_lowers_both_axes_and_records_what_it_moved():
    entry = {"reps": 11, "weight_kg": 47.5, "band_tier": None, "source": "last_time"}
    out = sessions.clamp_to_ceiling(entry, {"weight_kg": 45.0, "reps": 10})
    assert out["weight_kg"] == 45.0 and out["reps"] == 10
    assert out["clamped"]["weight_kg"] == {"from": 47.5, "to": 45.0}
    assert out["clamped"]["reps"] == {"from": 11, "to": 10}


def test_clamp_never_raises_a_number_that_is_already_below_the_ceiling():
    entry = {"reps": 8, "weight_kg": 40.0, "band_tier": None}
    out = sessions.clamp_to_ceiling(entry, {"weight_kg": 45.0, "reps": 10})
    assert out["weight_kg"] == 40.0 and out["reps"] == 8
    assert out["clamped"] == {}


def test_clamp_leaves_an_axis_alone_when_the_ceiling_has_no_record_of_it():
    entry = {"reps": 11, "weight_kg": 47.5, "band_tier": None}
    out = sessions.clamp_to_ceiling(entry, {"weight_kg": None, "reps": None})
    assert out["weight_kg"] == 47.5 and out["reps"] == 11


def test_clamp_lowers_a_band_tier():
    entry = {"reps": 12, "weight_kg": None, "band_tier": "Red"}
    out = sessions.clamp_to_ceiling(entry, {"band_tier": "Blue"})
    assert out["band_tier"] == "Blue"


def test_clamp_does_not_mutate_the_entry_it_was_given():
    entry = {"reps": 11, "weight_kg": 47.5, "band_tier": None}
    sessions.clamp_to_ceiling(entry, {"weight_kg": 45.0, "reps": 10})
    assert entry["weight_kg"] == 47.5 and entry["reps"] == 11


# ── assert_within_ceiling ──────────────────────────────────────────────────

def test_assertion_is_a_noop_on_a_normal_day():
    sessions.assert_within_ceiling(
        {"reps": 11, "weight_kg": 47.5}, {"weight_kg": 45.0, "reps": 10},
        {"reduced": False}, "Lat Pulldown",
    )  # must not raise


def test_assertion_raises_on_an_over_ceiling_weight():
    with pytest.raises(sessions.PrescriptionContradiction) as exc:
        sessions.assert_within_ceiling(
            {"reps": 10, "weight_kg": 47.5}, {"weight_kg": 45.0, "reps": 10},
            {"reduced": True, "reasons": ["engine directive: REDUCED VOLUME"]},
            "Lat Pulldown",
        )
    assert "Lat Pulldown" in str(exc.value) and "47.5" in str(exc.value)


def test_assertion_raises_on_over_ceiling_reps_even_when_weight_is_fine():
    with pytest.raises(sessions.PrescriptionContradiction):
        sessions.assert_within_ceiling(
            {"reps": 11, "weight_kg": 45.0}, {"weight_kg": 45.0, "reps": 10},
            {"reduced": True, "reasons": []}, "Lat Pulldown",
        )


def test_assertion_raises_on_an_over_ceiling_band_tier():
    with pytest.raises(sessions.PrescriptionContradiction):
        sessions.assert_within_ceiling(
            {"reps": 12, "weight_kg": None, "band_tier": "Red"},
            {"band_tier": "Blue"}, {"reduced": True, "reasons": []}, "Pallof Press",
        )


# ── resolve_prescription: the end-to-end regressions ───────────────────────

def test_green_day_still_progresses():
    # The fix must not turn every day into a hold.
    p = sessions.load_policy(_GREEN, _HIGH_STREAK)
    entry = sessions.resolve_prescription(
        _PULLDOWN, _PULLDOWN_LAST_PERF, "high", p,
        last_session_sets=_PULLDOWN_LAST_SETS,
    )
    assert entry["weight_kg"] == 47.5   # 45 + 2.5, the readiness nudge
    assert entry["clamped"] == {}


def test_the_2026_08_06_bug_reduced_load_day_never_exceeds_the_prior_session():
    # THE regression. Header said reduced load; Lat Pulldown was seeded
    # 47.5kg x 11, up from 45kg x 10. Both axes must now hold.
    p = sessions.load_policy(_ORANGE, _HIGH_STREAK)
    ex = engine.apply_exercise_volume_modifier(_PULLDOWN, p["volume_factor"])
    entry = sessions.resolve_prescription(
        ex, _PULLDOWN_LAST_PERF, "high", p,
        last_session_sets=_PULLDOWN_LAST_SETS,
    )
    assert entry["weight_kg"] <= 45.0
    assert entry["reps"] <= 10
    assert entry["weight_kg"] == 45.0 and entry["reps"] == 10


def test_the_raw_readiness_factor_is_what_would_have_inflated_the_reps():
    # Pins the actual mechanism, so a future refactor that drops the cap fails
    # here with an explanation rather than just somewhere.
    assert engine.apply_exercise_volume_modifier(_PULLDOWN, 1.12)["reps"] == 11
    assert engine.apply_exercise_volume_modifier(_PULLDOWN, 1.0)["reps"] == 10


def test_reduced_load_day_holds_every_signal_colour_that_shows_a_banner():
    for directive in (_ORANGE, _YELLOW_INJURY, _RED):
        p = sessions.load_policy(directive, _HIGH_STREAK)
        ex = engine.apply_exercise_volume_modifier(_PULLDOWN, p["volume_factor"])
        entry = sessions.resolve_prescription(
            ex, _PULLDOWN_LAST_PERF, "high", p,
            last_session_sets=_PULLDOWN_LAST_SETS,
        )
        assert entry["weight_kg"] <= 45.0, directive["signal_color"]
        assert entry["reps"] <= 10, directive["signal_color"]


def test_reduced_load_day_blocks_double_progression_too():
    # The other upward path: every set hit rep_max, so double progression
    # wants +2.5kg. It proposes; the clamp still holds it.
    ex = {"name": "RDL", "type": "reps", "reps": 10, "rep_min": 10, "rep_max": 12,
          "sets": 3, "weight_kg": 12.5, "equipment_type": "dumbbell"}
    last_sets = [{"reps": 12, "weight": 12.5}] * 3
    last_perf = {"reps": 12, "weight_kg": 12.5, "session_date": "2026-07-30"}
    p = sessions.load_policy(_ORANGE, _NEUTRAL)
    entry = sessions.resolve_prescription(ex, last_perf, "normal", p,
                                           last_session_sets=last_sets)
    assert entry["weight_kg"] == 12.5
    assert entry["clamped"]["weight_kg"] == {"from": 15.0, "to": 12.5}


def test_reduced_load_day_holds_a_band_tier_increase():
    ex = {"name": "Pallof Press", "type": "reps", "reps": 12, "sets": 3,
          "band_tier": "Blue", "equipment_type": "band"}
    last_perf = {"reps": 12, "band_tier": "Blue", "session_date": "2026-07-30"}
    p = sessions.load_policy(_ORANGE, _HIGH_STREAK)
    entry = sessions.resolve_prescription(ex, last_perf, "high", p)
    assert entry["band_tier"] == "Blue"


def test_reduced_load_day_still_allows_a_decrease():
    # Clamping downward must not become "hold at last session no matter what"
    # -- a low-readiness streak still reduces below the ceiling.
    low = {"volume_factor": 0.75, "streak_label": "low", "description": "Low readiness"}
    p = sessions.load_policy(_ORANGE, low)
    entry = sessions.resolve_prescription(
        _PULLDOWN, _PULLDOWN_LAST_PERF, "low", p,
        last_session_sets=_PULLDOWN_LAST_SETS,
    )
    assert entry["weight_kg"] == 42.5  # 45 - 2.5, below the ceiling, untouched
    assert entry["clamped"] == {}


def test_reduced_load_day_with_no_history_does_not_invent_a_ceiling():
    # First-ever exposure on a reduced day: nothing to clamp against, and the
    # volume cap upstream already kept the plan's authored reps honest.
    p = sessions.load_policy(_ORANGE, _HIGH_STREAK)
    ex = engine.apply_exercise_volume_modifier(_PULLDOWN, p["volume_factor"])
    entry = sessions.resolve_prescription(ex, None, "high", p)
    assert entry["reps"] == 10                     # not 11
    assert entry["weight_kg"] == 47.5              # unclamped: no record exists
    assert entry["clamped"] == {}


def test_resolution_output_always_carries_the_clamped_ledger():
    # Downstream captions read entry["clamped"]; it must exist on every path.
    for policy in (sessions.load_policy(_GREEN, _NEUTRAL),
                   sessions.load_policy(_ORANGE, _NEUTRAL)):
        entry = sessions.resolve_prescription(
            _PULLDOWN, _PULLDOWN_LAST_PERF, "normal", policy,
            last_session_sets=_PULLDOWN_LAST_SETS,
        )
        assert "clamped" in entry


# ── header text and the numbers cannot disagree ────────────────────────────

def test_header_and_numbers_are_derived_from_the_same_object():
    # The structural property, stated as a test: whenever the policy renders a
    # hold-back banner, the resolution it also drives must not exceed the
    # prior session -- for every combination of the two signals that can occur.
    directives = [_GREEN, _ORANGE, _YELLOW_INJURY, _RED,
                  {"signal_color": "grey", "multiplier": 1.0, "label": "OBSERVATION MODE"}]
    modifiers = [_HIGH_STREAK, _NEUTRAL,
                 {"volume_factor": 0.75, "streak_label": "low", "description": "Low"},
                 {"volume_factor": 1.04, "streak_label": "high", "description": "+4%"}]
    for d in directives:
        for m in modifiers:
            p = sessions.load_policy(d, m)
            ex = engine.apply_exercise_volume_modifier(_PULLDOWN, p["volume_factor"])
            entry = sessions.resolve_prescription(
                ex, _PULLDOWN_LAST_PERF, m["streak_label"], p,
                last_session_sets=_PULLDOWN_LAST_SETS,
            )
            banner_says_hold = p["banner_kind"] in ("warning", "error")
            if banner_says_hold:
                assert entry["weight_kg"] <= 45.0, (d, m)
                assert entry["reps"] <= 10, (d, m)
            else:
                # No banner means no hold-back claim was made, so an increase
                # is honest. Assert the pairing, not the direction.
                assert p["reduced"] is False, (d, m)


def test_a_banner_is_shown_for_exactly_the_days_that_are_reduced():
    for d in (_GREEN, _ORANGE, _YELLOW_INJURY, _RED,
              {"signal_color": "grey", "multiplier": 1.0}):
        for m in (_HIGH_STREAK, _NEUTRAL,
                  {"volume_factor": 0.5, "streak_label": "low", "description": "x"}):
            p = sessions.load_policy(d, m)
            assert bool(p["banner_text"]) == p["reduced"], (d, m)
            assert bool(p["banner_kind"]) == p["reduced"], (d, m)


def test_the_old_signal_color_test_would_have_missed_two_of_three_banner_days():
    # Documents the defect itself so it cannot be reintroduced as a
    # "simplification": the retired wire was `signal_color != "red"`.
    missed = [d for d in (_ORANGE, _YELLOW_INJURY, _RED)
              if d["signal_color"] != "red"
              and sessions.load_policy(d, _HIGH_STREAK)["reduced"]]
    assert len(missed) == 2


# ── the printed prescription matches the stepper underneath it ─────────────

def test_printed_prescription_reads_the_resolved_entry_not_the_plan():
    # The third disagreement in the 2026-08-06 report: the exercise header
    # printed prescription_label(ex) — the plan's reps after the readiness
    # volume modifier, 11 — while the stepper below it held the resolved 10.
    inflated = engine.apply_exercise_volume_modifier(_PULLDOWN, 1.12)
    assert inflated["reps"] == 11
    resolved = {"reps": 10, "weight_kg": 45.0, "band_tier": None}
    shown = sessions.displayed_prescription(inflated, resolved)
    assert shown["reps"] == 10
    assert "10" in sessions.prescription_label(shown)
    assert "11" not in sessions.prescription_label(shown)


def test_printed_prescription_shows_the_resolved_weight_too():
    shown = sessions.displayed_prescription(
        _PULLDOWN, {"reps": 10, "weight_kg": 45.0, "band_tier": None})
    assert shown["weight_kg"] == 45.0


def test_printed_prescription_falls_back_to_the_plan_with_no_stepper():
    # Unloaded exercises have no resolved entry; the plan value IS the
    # prescription and must survive untouched.
    assert sessions.displayed_prescription(_PULLDOWN, None) is _PULLDOWN


def test_printed_prescription_never_overlays_a_hold_reps_counter():
    # reps_in_set is driven by the live hold-timer, not the stepper.
    ex = {"name": "Prone Y-Raise", "type": "hold_reps", "reps_in_set": 8,
          "sets": 3, "weight_kg": 1.0, "equipment_type": "dumbbell"}
    shown = sessions.displayed_prescription(ex, {"reps": 99, "weight_kg": 1.0})
    assert shown["reps_in_set"] == 8


def test_printed_prescription_does_not_mutate_the_plan_exercise():
    ex = dict(_PULLDOWN)
    sessions.displayed_prescription(ex, {"reps": 3, "weight_kg": 5.0})
    assert ex["reps"] == 10 and ex["weight_kg"] == 45.0


def test_header_text_and_printed_numbers_agree_on_the_bug_day():
    # End to end: banner, printed prescription and stepper value, all three
    # from one resolution, on the exact 2026-08-06 inputs.
    p = sessions.load_policy(_ORANGE, _HIGH_STREAK)
    ex = engine.apply_exercise_volume_modifier(_PULLDOWN, p["volume_factor"])
    entry = sessions.resolve_prescription(
        ex, _PULLDOWN_LAST_PERF, "high", p, last_session_sets=_PULLDOWN_LAST_SETS)
    label = sessions.prescription_label(sessions.displayed_prescription(ex, entry))
    assert "don't push to failure" in p["banner_text"]
    # prescription_label carries reps, not weight — pin each where it renders.
    assert "10 reps" in label and "11 reps" not in label
    assert entry["weight_kg"] == 45.0 and entry["reps"] == 10
    assert sessions.displayed_prescription(ex, entry)["weight_kg"] == 45.0


# ─── actual_caption ─────────────────────────────────────────────────────────

def test_actual_caption_reports_a_held_prescription():
    entry = {"source": "last_time", "reps": 10, "weight_kg": 45.0, "band_tier": None,
             "last_seen_date": "2026-07-30",
             "clamped": {"weight_kg": {"from": 47.5, "to": 45.0},
                         "reps": {"from": 11, "to": 10}}}
    caption = sessions.actual_caption(entry)
    assert "Held down" in caption and "47.5 → 45 kg" in caption and "11 → 10 reps" in caption


def test_actual_caption_says_nothing_extra_when_nothing_was_held():
    entry = {"source": "last_time", "reps": 8, "weight_kg": 12.5, "band_tier": None,
             "last_seen_date": "2026-07-14", "clamped": {}}
    assert sessions.actual_caption(entry) == "Last time: 8 reps @ 12.5 kg (2026-07-14)"


def test_actual_caption_last_time_weight():
    entry = {"source": "last_time", "reps": 8, "weight_kg": 12.5, "band_tier": None,
             "last_seen_date": "2026-07-14"}
    assert sessions.actual_caption(entry) == "Last time: 8 reps @ 12.5 kg (2026-07-14)"


def test_actual_caption_last_time_band_tier():
    entry = {"source": "last_time", "reps": 10, "weight_kg": None, "band_tier": "Blue",
             "last_seen_date": "2026-07-14"}
    assert sessions.actual_caption(entry) == "Last time: 10 reps @ Blue (Medium) (2026-07-14)"


def test_actual_caption_plan_default():
    assert sessions.actual_caption({"source": "plan_default"}) == "No prior record — using plan default."


def test_estimate_duration_floor_is_10_minutes():
    assert sessions.estimate_duration([]) >= 10


# ─── exercise_duration_seconds ─────────────────────────────────────────────

def test_exercise_duration_seconds_duration_type():
    ex = {"type": "duration", "duration_minutes": 5}
    assert sessions.exercise_duration_seconds(ex) == 300


def test_exercise_duration_seconds_hold():
    ex = {"type": "hold", "sets": 3, "hold_seconds": 30, "rest_seconds": 15}
    # 3*30 + 2*15 = 120
    assert sessions.exercise_duration_seconds(ex) == 120


def test_exercise_duration_seconds_hold_reps():
    ex = {"type": "hold_reps", "sets": 2, "hold_seconds": 5, "reps_in_set": 4, "rest_seconds": 20}
    # 2*5*4 + 1*20 = 60
    assert sessions.exercise_duration_seconds(ex) == 60


def test_exercise_duration_seconds_reps():
    ex = {"type": "reps", "sets": 3, "reps": 10, "rest_seconds": 45}
    # 3*20 + 2*45 = 150
    assert sessions.exercise_duration_seconds(ex) == 150


def test_exercise_duration_seconds_unknown_type_returns_zero():
    assert sessions.exercise_duration_seconds({"type": "unknown"}) == 0


def test_exercise_duration_seconds_sums_to_estimate_duration():
    # estimate_duration is now built from this function — lock the
    # relationship in so a future edit to one doesn't silently drift from
    # the other: 120s base + (per-exercise time + 30s transition) each.
    exercises = [
        {"type": "duration", "duration_minutes": 5},
        {"type": "hold", "sets": 3, "hold_seconds": 30, "rest_seconds": 15},
        {"type": "reps", "sets": 3, "reps": 10, "rest_seconds": 45},
    ]
    raw_total = 120 + sum(sessions.exercise_duration_seconds(ex) + 30 for ex in exercises)
    assert sessions.estimate_duration(exercises) == max(10, round(raw_total / 60))


# ─── exercise_seconds_from_sets ─────────────────────────────────────────────

def test_exercise_seconds_from_sets_empty_list_returns_zero():
    assert sessions.exercise_seconds_from_sets([]) == 0


def test_exercise_seconds_from_sets_duration_type():
    ex = {"type": "duration", "duration_minutes": 5}
    assert sessions.exercise_seconds_from_sets(sessions.make_sets_data(ex)) == 300


def test_exercise_seconds_from_sets_hold():
    ex = {"type": "hold", "sets": 3, "hold_seconds": 30, "rest_seconds": 15}
    assert sessions.exercise_seconds_from_sets(sessions.make_sets_data(ex)) == 120


def test_exercise_seconds_from_sets_hold_reps_multiplies_tut_by_reps():
    # Regression guard for the specific hold_reps nuance: make_sets_data's
    # per-row "tut" is the PER-REP hold duration, not pre-multiplied.
    ex = {"type": "hold_reps", "sets": 2, "hold_seconds": 5, "reps_in_set": 4, "rest_seconds": 20}
    rows = sessions.make_sets_data(ex)
    assert rows[0]["tut"] == 5 and rows[0]["reps"] == 4          # stored un-multiplied
    assert sessions.exercise_seconds_from_sets(rows) == 60        # 2*5*4 + 1*20


def test_exercise_seconds_from_sets_reps_uses_flat_estimate():
    ex = {"type": "reps", "sets": 3, "reps": 10, "rest_seconds": 45}
    assert sessions.exercise_seconds_from_sets(sessions.make_sets_data(ex)) == 150


def test_exercise_seconds_from_sets_matches_plan_time_estimate_across_all_types_and_weeks():
    # Locks in the identity exercise_seconds_from_sets(make_sets_data(ex))
    # == exercise_duration_seconds(ex) across the entire real Stage 2A plan
    # -- what makes the confirmed Session A/B/C content multipliers valid
    # regression numbers computed from logged-shaped data, not just the
    # plan dict directly.
    import training_plan as tp
    for fn in (tp._s2_session_a, tp._s2_session_b, tp._s2_session_c):
        for week in (1, 2, 3, 4):
            for ex in fn(week)["exercises"]:
                assert sessions.exercise_seconds_from_sets(sessions.make_sets_data(ex)) == \
                    sessions.exercise_duration_seconds(ex), f"week {week} {ex['name']!r}"


# ─── checkpoint payload / restore ──────────────────────────────────────────

_STATE = {
    "tp_ex_idx": 2, "tp_set": 1, "tp_rep_in_set": 1, "tp_phase": "resting",
    "tp_started": True, "tp_done_today": False, "tp_session_logged": False,
    "tp_side": "right", "tp_session_start_ts": 12345.0, "tp_actuals": {},
    "tp_set_log": {}, "tp_garmin_declared": False,
    "tp_rest_started_at": 12400.0,
    # None on a plan session; the accessory session's whole day dict while one
    # is running. Present-but-None rather than absent is the point — see
    # CHECKPOINT_FIELDS' own note on why a missing key kills the checkpoint.
    "tp_accessory_plan": None,
}


def test_checkpoint_state_fixture_covers_every_checkpoint_field():
    """Guards the fixture above against drifting out of sync with
    CHECKPOINT_FIELDS — checkpoint_payload does a direct state[k] lookup, so
    a field added to CHECKPOINT_FIELDS but not to a caller's state dict is a
    KeyError at runtime, not a silently-missing key."""
    assert set(_STATE) == set(sessions.CHECKPOINT_FIELDS)


def test_checkpoint_payload_includes_day_num_and_all_fields():
    payload = sessions.checkpoint_payload(9, _STATE)
    assert payload["day_num"] == 9
    assert payload["tp_ex_idx"] == 2
    assert payload["tp_phase"] == "resting"


def test_restore_from_checkpoint_matching_day():
    payload = sessions.checkpoint_payload(9, _STATE)
    restored = sessions.restore_from_checkpoint(payload, 9)
    assert restored["tp_ex_idx"] == 2
    assert restored["tp_side"] == "right"
    assert "day_num" not in restored  # only the checkpoint fields, not the routing key


def test_restore_from_checkpoint_mismatched_day_returns_none():
    payload = sessions.checkpoint_payload(9, _STATE)
    assert sessions.restore_from_checkpoint(payload, 10) is None


def test_restore_from_checkpoint_none_input():
    assert sessions.restore_from_checkpoint(None, 9) is None


# ─── seed_default_phase ─────────────────────────────────────────────────────

def test_seed_default_phase_creates_phase_1_when_none_exist():
    seeded = sessions.seed_default_phase([], date(2026, 6, 29))
    assert len(seeded) == 1
    assert seeded[0].phase_number == 1
    assert seeded[0].start_date == "2026-06-29"


def test_seed_default_phase_leaves_existing_phases_untouched():
    existing = [_PHASE]
    assert sessions.seed_default_phase(existing, date(2026, 6, 29)) is existing


def test_seed_default_phase_no_plan_start_returns_empty():
    assert sessions.seed_default_phase([], None) == []


# ─── plan_dict_for_phase ────────────────────────────────────────────────────

def test_plan_dict_for_phase_1_is_stage1_plan():
    import training_plan as tp
    assert sessions.plan_dict_for_phase(1) is tp.PLAN


def test_plan_dict_for_phase_2_is_stage2_plan():
    import training_plan as tp
    assert sessions.plan_dict_for_phase(2) is tp.PLAN_STAGE2


def test_plan_dict_for_phase_unknown_returns_none():
    assert sessions.plan_dict_for_phase(99) is None


# ─── begin_new_phase ────────────────────────────────────────────────────────

def test_begin_new_phase_appends_the_new_phase():
    new_phase = Phase(phase_number=2, name="Stage 2", start_date="2026-07-20",
                       length_days=28, status="active")
    updated = sessions.begin_new_phase([_PHASE], new_phase)
    assert updated[-1] is new_phase
    assert len(updated) == 2


def test_begin_new_phase_marks_a_date_lapsed_prior_phase_completed():
    # _PHASE runs 2026-06-29 for 14 days -> ends 2026-07-12, well before the
    # module's real date.today() call in begin_new_phase, so it's lapsed.
    new_phase = Phase(phase_number=2, name="Stage 2", start_date="2026-07-20",
                       length_days=28, status="active")
    updated = sessions.begin_new_phase([_PHASE], new_phase)
    assert updated[0].status == "completed"
    assert updated[0].phase_number == _PHASE.phase_number  # unchanged otherwise


def test_begin_new_phase_leaves_non_lapsed_phases_untouched():
    from datetime import timedelta
    future_phase = Phase(phase_number=1, name="Stage 1", start_date=date.today().isoformat(),
                          length_days=14, status="active")
    new_phase = Phase(phase_number=2, name="Stage 2",
                       start_date=(date.today() + timedelta(days=14)).isoformat(),
                       length_days=28, status="active")
    updated = sessions.begin_new_phase([future_phase], new_phase)
    assert updated[0].status == "active"


def test_begin_new_phase_preserves_date_overrides_and_shift_reasons_on_completion():
    # Regression guard: begin_new_phase used to reconstruct each prior
    # Phase field-by-field, which silently dropped date_overrides/
    # shift_reasons back to {} (both default to {} when omitted) the
    # moment a phase transitioned to "completed" -- erasing every manual
    # reschedule and readiness auto-shift ever recorded on that phase.
    lapsed_with_history = Phase(
        phase_number=1, name="Stage 1 Rehab", start_date="2026-06-29", length_days=14,
        status="active",
        date_overrides={"2026-07-05": 8},
        shift_reasons={"2026-07-05": "Sleep debt of 10.2h over the last 7 nights"},
    )
    new_phase = Phase(phase_number=2, name="Stage 2", start_date="2026-07-20",
                       length_days=28, status="active")
    updated = sessions.begin_new_phase([lapsed_with_history], new_phase)
    assert updated[0].status == "completed"
    assert updated[0].date_overrides == {"2026-07-05": 8}
    assert updated[0].shift_reasons == {"2026-07-05": "Sleep debt of 10.2h over the last 7 nights"}


# ─── day_view_state routing ─────────────────────────────────────────────────

def test_day_view_state_no_active_phase():
    assert sessions.day_view_state(date(2026, 7, 7), date(2026, 7, 7), None, False) == "no_phase"


def test_day_view_state_today_with_active_phase():
    assert sessions.day_view_state(date(2026, 7, 7), date(2026, 7, 7), _PHASE, False) == "today"


def test_day_view_state_past_completed():
    assert sessions.day_view_state(date(2026, 7, 5), date(2026, 7, 7), _PHASE, True) == "past_completed"


def test_day_view_state_past_missed():
    assert sessions.day_view_state(date(2026, 7, 5), date(2026, 7, 7), _PHASE, False) == "past_missed"


def test_day_view_state_future():
    assert sessions.day_view_state(date(2026, 7, 10), date(2026, 7, 7), _PHASE, False) == "future"


def test_day_view_state_outside_phase_range_is_rest():
    assert sessions.day_view_state(date(2026, 6, 1), date(2026, 7, 7), _PHASE, False) == "rest"


def test_day_view_state_future_day_logged_status_ignored():
    # is_logged is irrelevant for future dates -- can't have completed a day
    # that hasn't happened yet; routing must still resolve to "future".
    assert sessions.day_view_state(date(2026, 7, 10), date(2026, 7, 7), _PHASE, True) == "future"


# ─── No Streamlit import ────────────────────────────────────────────────────

def test_no_streamlit_import():
    tree = ast.parse(open(sessions.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"


# ─── outdoor_exercise_name (the Garmin hike importer's naming) ──────────────

def test_outdoor_exercise_name_maps_the_family_and_falls_back():
    # Fixed canonical names, never Garmin's free text — the name is the key
    # into the movement-weight and body-region tables. Measured 2026-08-10:
    # a real Alpine hike arrives typed "walking" ("Mittenwald Walking"),
    # which is why walking maps to the same tier as hiking.
    assert sessions.outdoor_exercise_name("walking") == "Outdoor Walk"
    assert sessions.outdoor_exercise_name("casual_walking") == "Outdoor Walk"
    assert sessions.outdoor_exercise_name("hiking") == "Outdoor Hike"
    assert sessions.outdoor_exercise_name("trail_running") == "Outdoor Trail Run"
    assert sessions.outdoor_exercise_name("running") == "Outdoor Run"
    assert sessions.outdoor_exercise_name("TRAIL_RUNNING") == "Outdoor Trail Run"
    # Anything else the athlete picks anyway logs under the fallback name —
    # the type filter is advice, the pick is the decision.
    assert sessions.outdoor_exercise_name("cycling") == "Outdoor Activity"
    assert sessions.outdoor_exercise_name(None) == "Outdoor Activity"


# ─── next_phase_offer ──────────────────────────────────────────────────────

def _ph(number, start="2026-07-20", length=28, status="completed"):
    return Phase(phase_number=number, name=f"P{number}", start_date=start,
                 length_days=length, status=status)


def test_next_phase_offer_returns_the_next_authored_block():
    assert sessions.next_phase_offer([_ph(1), _ph(2)]) == 3


def test_next_phase_offer_never_re_offers_an_existing_block():
    assert sessions.next_phase_offer([_ph(1), _ph(2), _ph(3)]) is None


def test_next_phase_offer_will_not_skip_a_block():
    """A Phase 3 with no Phase 2 would leave a hole in the day numbering and in
    the stage history."""
    assert sessions.next_phase_offer([_ph(1)]) == 2


def test_next_phase_offer_is_silent_when_no_phase_exists_yet():
    """Seeding the very first phase belongs to the plan-start screen, which
    collects a start date this function has no way to ask for."""
    assert sessions.next_phase_offer([]) is None


def test_every_offerable_phase_has_content_and_a_clinical_stage():
    for number, meta in sessions.PHASE_META.items():
        assert meta["stage"] in (1, 2, 3), number
        assert meta["name"] and meta["button"], number


def test_stage_2b_is_a_new_block_at_the_same_clinical_stage():
    """Phase and Stage are separate systems. Reading "2B" as stage 3 would hand
    over Performance-and-Growth ceilings (ACWR 1.5, RPE 10) on a block name."""
    assert sessions.PHASE_META[3]["stage"] == 2
    assert sessions.plan_dict_for_phase(3) is not None
