"""Tests for services/volume.py — weekly volume load (tonnage)."""

from datetime import date

from services.models import ExerciseEntry, SessionRecord
from services import volume


def _session(session_date: str, volumes: list[float]) -> SessionRecord:
    exercises = [
        ExerciseEntry(name=f"Ex{i}", movement_type="reps", total_volume_kg=v)
        for i, v in enumerate(volumes)
    ]
    return SessionRecord(
        session_date=session_date,
        session_duration_minutes=30.0,
        session_rpe=6.0,
        session_au=180.0,
        exercises=exercises,
    )


def test_weekly_volume_load_sums_across_multiple_sessions_and_sets():
    sessions = [
        _session("2026-07-06", [240.0, 120.0]),  # Monday
        _session("2026-07-08", [300.0]),          # Wednesday, same week
    ]
    total = volume.weekly_volume_load(sessions, date(2026, 7, 6))
    assert total == 660.0


def test_weekly_volume_load_filters_by_week_boundary():
    sessions = [
        _session("2026-07-05", [500.0]),  # Sunday -- previous week, excluded
        _session("2026-07-06", [100.0]),  # Monday -- start of window, included
        _session("2026-07-12", [50.0]),   # Sunday -- end of window, included
        _session("2026-07-13", [999.0]),  # Monday -- next week, excluded
    ]
    total = volume.weekly_volume_load(sessions, date(2026, 7, 6))
    assert total == 150.0


def test_weekly_volume_load_empty_sessions_returns_zero():
    assert volume.weekly_volume_load([], date(2026, 7, 6)) == 0.0


def test_weekly_volume_load_no_sessions_in_range_returns_zero():
    sessions = [_session("2026-06-01", [500.0])]
    assert volume.weekly_volume_load(sessions, date(2026, 7, 6)) == 0.0


def test_weekly_volume_load_ignores_exercises_with_no_volume():
    # Bodyweight/hold exercises have total_volume_kg == 0.0 -- must not error.
    sessions = [_session("2026-07-06", [0.0, 0.0, 150.0])]
    total = volume.weekly_volume_load(sessions, date(2026, 7, 6))
    assert total == 150.0
