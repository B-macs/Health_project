"""Tests for services/sessions.py — pure training-session logic extracted
from views/training.py."""

import ast
from datetime import date

from services import sessions
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


# ─── actual_caption ─────────────────────────────────────────────────────────

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
}


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
