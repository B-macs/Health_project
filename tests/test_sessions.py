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


def test_estimate_duration_floor_is_10_minutes():
    assert sessions.estimate_duration([]) >= 10


# ─── checkpoint payload / restore ──────────────────────────────────────────

_STATE = {
    "tp_ex_idx": 2, "tp_set": 1, "tp_rep_in_set": 1, "tp_phase": "resting",
    "tp_started": True, "tp_done_today": False, "tp_session_logged": False,
    "tp_side": "right", "tp_session_start_ts": 12345.0,
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
