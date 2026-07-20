"""
Tests for services/bioage.py — the Strength BioAge Stage-Adjusted Recovery
Score engine (views/insights.py, ?bioage=strength).

Core behavior under test: every region score stays None ("—" on screen)
until that region has real logged *weighted* volume, regardless of how much
bodyweight rehab work has been logged — see services/bioage.py's module
docstring for why that's deliberate, not a gap to fill in later.
"""

from __future__ import annotations

from datetime import date

import patient_profile
from services import bioage
from services.models import ExerciseEntry, SessionRecord

_MAP = {
    "Bench Press": "upper_body",
    "Squat": "lower_body",
    "Plank": "core",
}


def _session(session_date: str, exercises: list[ExerciseEntry]) -> SessionRecord:
    return SessionRecord(
        session_date=session_date,
        session_duration_minutes=45.0,
        session_rpe=6.0,
        session_au=270.0,
        exercises=exercises,
    )


def _exercise(name: str, volume_kg: float | None) -> ExerciseEntry:
    return ExerciseEntry(name=name, movement_type="Weight", actual_sets=3, total_volume_kg=volume_kg)


# ─── region_effort ───────────────────────────────────────────────────────────

def test_region_effort_sums_volume_for_tagged_exercises_only():
    sessions = [
        _session("2026-07-01", [_exercise("Bench Press", 100.0), _exercise("Squat", 200.0)]),
        _session("2026-07-02", [_exercise("Bench Press", 50.0)]),
    ]
    assert bioage.region_effort(sessions, "upper_body", _MAP) == 150.0
    assert bioage.region_effort(sessions, "lower_body", _MAP) == 200.0


def test_region_effort_ignores_unmapped_exercise_names():
    sessions = [_session("2026-07-01", [_exercise("Unknown Movement", 999.0)])]
    assert bioage.region_effort(sessions, "upper_body", _MAP) == 0.0
    assert bioage.region_effort(sessions, "core", _MAP) == 0.0


def test_region_effort_treats_none_volume_as_zero():
    sessions = [_session("2026-07-01", [_exercise("Plank", None)])]
    assert bioage.region_effort(sessions, "core", _MAP) == 0.0


# ─── has_weighted_training — the core behavior this module exists for ──────

def test_has_weighted_training_false_for_bodyweight_only_history():
    sessions = [
        _session("2026-07-01", [_exercise("Squat", 0.0)]),
        _session("2026-07-02", [_exercise("Squat", None)]),
    ]
    assert bioage.has_weighted_training(sessions, "lower_body", _MAP) is False


def test_has_weighted_training_true_once_any_weighted_set_logged():
    sessions = [
        _session("2026-07-01", [_exercise("Squat", 0.0)]),
        _session("2026-07-02", [_exercise("Squat", 40.0)]),
    ]
    assert bioage.has_weighted_training(sessions, "lower_body", _MAP) is True


def test_has_weighted_training_does_not_leak_across_regions():
    sessions = [_session("2026-07-01", [_exercise("Bench Press", 60.0)])]
    assert bioage.has_weighted_training(sessions, "lower_body", _MAP) is False
    assert bioage.has_weighted_training(sessions, "upper_body", _MAP) is True


# ─── current_window_effort / region_baseline_ceiling ───────────────────────

def test_current_window_effort_excludes_sessions_outside_the_28d_window():
    sessions = [
        _session("2026-06-01", [_exercise("Squat", 500.0)]),  # outside a 28d window ending 2026-07-01
        _session("2026-06-25", [_exercise("Squat", 100.0)]),
    ]
    effort = bioage.current_window_effort(sessions, "lower_body", _MAP, today=date(2026, 7, 1))
    assert effort == 100.0


def test_region_baseline_ceiling_is_the_best_trailing_window_to_date():
    sessions = [
        _session("2026-06-01", [_exercise("Squat", 300.0)]),  # a strong early week
        _session("2026-06-29", [_exercise("Squat", 50.0)]),   # a light recent week
    ]
    ceiling = bioage.region_baseline_ceiling(sessions, "lower_body", _MAP, today=date(2026, 7, 1))
    assert ceiling >= 300.0


def test_region_baseline_ceiling_zero_with_no_session_history():
    assert bioage.region_baseline_ceiling([], "lower_body", _MAP, today=date(2026, 7, 1)) == 0.0


# ─── region_recovery_score ──────────────────────────────────────────────────

def test_region_recovery_score_none_when_no_baseline_yet():
    assert bioage.region_recovery_score(current_effort=50.0, baseline_ceiling_effort=0.0, stage=1) is None


def test_region_recovery_score_same_effort_scores_higher_at_an_earlier_stage():
    # Same current effort (45) against the same personal-best baseline
    # (100), at each stage's own volume_cap_pct (services.rules.
    # STAGE_CONSTRAINTS: stage1=0.70, stage2=0.90, stage3=1.0) — the whole
    # point of "stage-adjusted": being capped early in rehab isn't
    # penalized, it's the denominator that shrinks.
    assert bioage.region_recovery_score(45.0, 100.0, stage=1) == 64.3
    assert bioage.region_recovery_score(45.0, 100.0, stage=2) == 50.0
    assert bioage.region_recovery_score(45.0, 100.0, stage=3) == 45.0


def test_region_recovery_score_caps_at_100():
    assert bioage.region_recovery_score(current_effort=500.0, baseline_ceiling_effort=100.0, stage=3) == 100.0


def test_region_recovery_score_unknown_stage_falls_back_to_full_cap():
    # STAGE_CONSTRAINTS.get(stage, {}).get("volume_cap_pct", 1.0) — an
    # out-of-range stage number shouldn't crash, just use no cap.
    assert bioage.region_recovery_score(50.0, 100.0, stage=99) == 50.0


# ─── hero_score ──────────────────────────────────────────────────────────────

def test_hero_score_averages_real_scores_and_ignores_none():
    assert bioage.hero_score([80.0, None, 60.0]) == 70.0


def test_hero_score_none_when_every_region_is_none():
    assert bioage.hero_score([None, None, None]) is None


# ─── muscle_imbalance_count ─────────────────────────────────────────────────

def test_muscle_imbalance_count_sums_both_lists():
    imbalances = {"overactive_tight": ["a", "b", "c"], "underactive_weak": ["d"]}
    assert bioage.muscle_imbalance_count(imbalances) == 4


def test_muscle_imbalance_count_handles_missing_keys():
    assert bioage.muscle_imbalance_count({}) == 0


def test_muscle_imbalance_count_against_real_patient_profile():
    # Regression check: if patient_profile.PROFILE's imbalances change
    # (CLAUDE.md rule 8 — updated before each new training block), this
    # documents that the count changed intentionally rather than silently.
    assert bioage.muscle_imbalance_count(patient_profile.PROFILE["imbalances"]) == 8


# ─── Stage 2A activation — real EXERCISE_BODY_REGION, not the test's own _MAP ──
# Demonstrates the previously-dormant pipeline (CLAUDE.md's "Strength BioAge
# scores dormant" Known Open Issue) now activates end-to-end once a real
# Stage 2 exercise logs non-zero weighted volume.

def test_stage2_exercise_activates_lower_body_region_via_real_map():
    import training_constants as tc
    sessions = [_session("2026-07-20", [_exercise("Goblet Squat", 240.0)])]
    assert bioage.has_weighted_training(sessions, "lower_body", tc.EXERCISE_BODY_REGION) is True
    assert bioage.region_effort(sessions, "lower_body", tc.EXERCISE_BODY_REGION) == 240.0


def test_stage1_bodyweight_exercise_still_does_not_activate_via_real_map():
    import training_constants as tc
    # Glute Bridge is a real, mapped Stage 1 name, but Stage 1 never logs
    # weighted volume — total_volume_kg stays 0/None regardless of mapping.
    sessions = [_session("2026-07-01", [_exercise("Glute Bridge", 0.0)])]
    assert bioage.has_weighted_training(sessions, "lower_body", tc.EXERCISE_BODY_REGION) is False
