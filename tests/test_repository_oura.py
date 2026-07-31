"""
Tests for services/repository.py's Oura row mappers and "not configured"
behavior. Fixture dicts below are copied from real, live-verified Oura API
v2 responses (daily_readiness, daily_sleep, daily_activity, daily_stress,
daily_spo2, daily_cardiovascular_age, workout, sleep) — not guessed field
names. session/daily_resilience/rest_mode_period/vo2_max had no data on the
verified account, so those row mappers are tested with synthetic input
matching Oura's documented schema instead (noted per-test).

No network: sync_oura_all() itself isn't unit tested here (it's I/O
orchestration — mirrors the same choice made for Garmin's sync_garmin_daily/
sync_garmin_activities), only the pure row-mapping functions it calls.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from services.clients import local_cache
from services.config import Config
from services.repository import Repository


def _config(**overrides) -> Config:
    base = dict(
        notion_api_key="ntn_test",
        notion_db_readiness="db-readiness",
        notion_db_training="db-training",
        notion_db_biometrics="db-biometrics",
        notion_db_config="db-config",
        google_sheets_id="sheet-id",
        google_service_account={"type": "service_account"},
    )
    base.update(overrides)
    return Config(**base)


# ─── oura_configured ─────────────────────────────────────────────────────────

def test_oura_not_configured_by_default():
    repo = Repository(_config())
    assert repo.oura_configured() is False
    assert repo._oc is None


def test_oura_configured_when_token_present():
    repo = Repository(_config(oura_token="Y76AC25JVDVDSUX42QRWIUKUYNPHUNNJ"))
    assert repo.oura_configured() is True
    assert repo._oc == "Y76AC25JVDVDSUX42QRWIUKUYNPHUNNJ"


# ─── _oura_daily_row ─────────────────────────────────────────────────────────
# Fixtures below are real API responses for 2026-07-05 (daily_resilience was
# empty for this account/day, so that group key is simply absent).

_REAL_DAILY_READINESS = {
    "id": "3d86573f-f970-4554-a8e1-1c49fb574cda",
    "contributors": {
        "activity_balance": 100, "body_temperature": 85, "hrv_balance": 8,
        "previous_day_activity": 99, "previous_night": 45, "recovery_index": 2,
        "resting_heart_rate": 14, "sleep_balance": 50, "sleep_regularity": 86,
    },
    "day": "2026-07-05", "score": 46,
}
_REAL_DAILY_SLEEP = {
    "id": "e39a935e-e27b-45cc-8da6-c5e22e29bb95",
    "contributors": {
        "deep_sleep": 90, "efficiency": 58, "latency": 81, "rem_sleep": 32,
        "restfulness": 64, "timing": 78, "total_sleep": 59,
    },
    "day": "2026-07-05", "score": 64,
}
_REAL_DAILY_ACTIVITY = {
    "id": "6efbc4de-8f53-4095-9f90-1c1f1a203099",
    "active_calories": 483, "average_met_minutes": 1.4375,
    "contributors": {
        "meet_daily_targets": 100, "move_every_hour": 95, "recovery_time": 100,
        "stay_active": 76, "training_frequency": 100, "training_volume": 99,
    },
    "day": "2026-07-05", "high_activity_time": 0, "medium_activity_time": 3780,
    "low_activity_time": 10260, "sedentary_time": 33420, "resting_time": 36840,
    "score": 96, "steps": 9358, "target_calories": 250, "total_calories": 2684,
}
_REAL_DAILY_STRESS = {
    "id": "cf190a1e-785a-45b7-91e1-b5527c34eef3",
    "day": "2026-07-05", "day_summary": None, "recovery_high": 0, "stress_high": 0,
}
_REAL_DAILY_SPO2 = {
    "id": "78feff17-dcaf-4a57-8461-0d41416cf316",
    "breathing_disturbance_index": 2, "day": "2026-07-05",
    "spo2_percentage": {"average": 97.628},
}
_REAL_DAILY_CARDIO = {
    "id": "7edc7483-247d-4a68-92da-a5d77377eb32",
    "day": "2026-07-05", "pulse_wave_velocity": 6.5778117179870605, "vascular_age": 32,
}
_REAL_SLEEP_TIME = {
    "id": "8c214111-3b56-4429-934b-272f6d7eebaa",
    "day": "2026-07-05", "optimal_bedtime": None, "recommendation": None,
    "status": "not_enough_nights",
}


def test_oura_daily_row_maps_real_fields():
    repo = Repository(_config())
    group = {
        "daily_readiness": _REAL_DAILY_READINESS,
        "daily_sleep": _REAL_DAILY_SLEEP,
        "daily_activity": _REAL_DAILY_ACTIVITY,
        "daily_stress": _REAL_DAILY_STRESS,
        "daily_spo2": _REAL_DAILY_SPO2,
        "daily_cardiovascular_age": _REAL_DAILY_CARDIO,
        "sleep_time": _REAL_SLEEP_TIME,
    }
    row = repo._oura_daily_row("2026-07-05", group)

    assert row["date"] == "2026-07-05"
    assert row["sleep_score"] == 64
    assert row["sleep_total_sleep"] == 59
    assert row["sleep_rem_sleep"] == 32
    assert row["readiness_score"] == 46
    assert row["readiness_hrv_balance"] == 8
    assert row["readiness_resting_heart_rate"] == 14
    assert row["activity_score"] == 96
    assert row["steps"] == 9358
    assert row["activity_met_minutes"] == 1.4375
    assert row["total_calories"] == 2684
    assert row["active_calories"] == 483
    assert row["resting_time"] == 36840
    assert row["stress_high_duration"] == 0
    assert row["stress_recovery_duration"] == 0
    assert row["spo2_average"] == 97.628
    assert row["spo2_breathing_disturbance_index"] == 2
    assert row["vascular_age"] == 32
    assert row["sleep_time_status"] == "not_enough_nights"
    # daily_resilience and vo2_max absent from group entirely (no data that day)
    assert row["resilience_level"] is None
    assert row["vo2_max"] is None


def test_oura_daily_row_captures_temperature_in_degrees_not_just_the_score():
    """readiness_body_temperature is a 0-100 contributor score; the actual
    deviation in degrees is a separate top-level field. Both are kept — the
    degrees one is Oura's only published temperature signal."""
    repo = Repository(_config())
    readiness = dict(_REAL_DAILY_READINESS,
                     temperature_deviation=-0.11, temperature_trend_deviation=23.29)
    row = repo._oura_daily_row("2026-07-05", {"daily_readiness": readiness})
    assert row["readiness_temperature_deviation"] == -0.11
    assert row["readiness_temperature_trend_deviation"] == 23.29
    assert row["readiness_body_temperature"] == 85  # the contributor score, unchanged


def test_oura_daily_row_captures_remaining_readiness_contributors():
    repo = Repository(_config())
    row = repo._oura_daily_row("2026-07-05", {"daily_readiness": _REAL_DAILY_READINESS})
    assert row["readiness_previous_night"] == 45
    assert row["readiness_sleep_regularity"] == 86


def test_oura_daily_row_captures_activity_met_minute_breakdown_and_contributors():
    repo = Repository(_config())
    activity = dict(
        _REAL_DAILY_ACTIVITY,
        high_activity_met_minutes=0, medium_activity_met_minutes=574,
        low_activity_met_minutes=232, sedentary_met_minutes=8,
        non_wear_time=3060, inactivity_alerts=0,
        equivalent_walking_distance=19109, meters_to_target=-7900, target_meters=12000,
    )
    row = repo._oura_daily_row("2026-07-05", {"daily_activity": activity})
    assert row["activity_medium_met_minutes"] == 574
    assert row["activity_sedentary_met_minutes"] == 8
    assert row["activity_non_wear_time"] == 3060
    assert row["activity_equivalent_walking_distance"] == 19109
    assert row["activity_meters_to_target"] == -7900
    # contributors sub-scores, previously dropped entirely
    assert row["activity_meet_daily_targets"] == 100
    assert row["activity_move_every_hour"] == 95
    assert row["activity_training_volume"] == 99
    assert row["activity_stay_active"] == 76


def test_oura_daily_header_and_row_stay_in_lockstep():
    """A column added to one and not the other silently writes blanks, or
    drops data into a cell nobody reads."""
    from services.repository import _OURA_DAILY_HEADER
    repo = Repository(_config())
    row = repo._oura_daily_row("2026-07-05", {})
    assert set(row) == set(_OURA_DAILY_HEADER)
    assert len(_OURA_DAILY_HEADER) == len(set(_OURA_DAILY_HEADER))  # no dupes


def test_oura_sleep_period_header_and_row_stay_in_lockstep():
    from services.repository import _OURA_SLEEP_PERIOD_HEADER
    repo = Repository(_config())
    row = repo._oura_sleep_period_row({})
    assert set(row) == set(_OURA_SLEEP_PERIOD_HEADER)
    assert len(_OURA_SLEEP_PERIOD_HEADER) == len(set(_OURA_SLEEP_PERIOD_HEADER))


def test_oura_daily_row_handles_completely_empty_group():
    repo = Repository(_config())
    row = repo._oura_daily_row("2026-07-01", {})
    assert row["date"] == "2026-07-01"
    assert all(v is None for k, v in row.items() if k != "date")


# ─── _oura_workout_row ───────────────────────────────────────────────────────

def test_oura_workout_row_maps_real_fields():
    repo = Repository(_config())
    workout = {
        "id": "23ba5ad9-6f40-4037-b270-3999b713caf8",
        "activity": "walking", "calories": 75.32189178466797, "day": "2026-07-05",
        "distance": 1248.8091165254777, "intensity": "moderate", "label": None,
        "source": "confirmed", "start_datetime": "2026-07-05T11:30:00.000+02:00",
        "end_datetime": "2026-07-05T11:53:00.000+02:00",
    }
    row = repo._oura_workout_row(workout)
    assert row["workout_id"] == "23ba5ad9-6f40-4037-b270-3999b713caf8"
    assert row["activity"] == "walking"
    assert row["distance_km"] == 1.25
    assert row["start_datetime"] == "2026-07-05T11:30:00.000+02:00"


def test_oura_workout_row_blanks_distance_when_absent():
    repo = Repository(_config())
    row = repo._oura_workout_row({"id": "x", "activity": "stopwatch", "distance": None})
    assert row["distance_km"] == ""


# ─── _oura_sleep_period_row ──────────────────────────────────────────────────

def test_oura_sleep_period_row_maps_real_scalar_fields():
    repo = Repository(_config())
    sleep = {
        "id": "87d8bf41-4988-435f-a189-e10e719ec5c2",
        "average_breath": 14.25, "average_heart_rate": 54.875, "average_hrv": 24,
        "awake_time": 4735, "bedtime_end": "2026-07-07T07:42:58.000+02:00",
        "bedtime_start": "2026-07-06T23:16:03.000+02:00", "day": "2026-07-07",
        "deep_sleep_duration": 2610, "efficiency": 84,
        "heart_rate": {"interval": 300.0, "items": [None, 60.0, 58.0]},  # excluded from the row
    }
    row = repo._oura_sleep_period_row(sleep)
    assert row["sleep_id"] == "87d8bf41-4988-435f-a189-e10e719ec5c2"
    assert row["average_heart_rate"] == 54.875
    assert row["average_hrv"] == 24
    assert row["deep_sleep_duration"] == 2610
    assert row["efficiency"] == 84
    assert "heart_rate" not in row  # embedded time-series excluded, by design


def test_oura_sleep_period_row_captures_per_period_readiness_and_deltas():
    """A nap's readiness genuinely differs from the day-level daily_readiness
    row, so this is extra signal rather than a duplicate of it."""
    repo = Repository(_config())
    sleep = {
        "id": "87d8bf41", "day": "2026-07-07", "type": "long_sleep", "period": 0,
        "sleep_score_delta": 0, "readiness_score_delta": -2,
        "sleep_algorithm_version": "v2", "sleep_analysis_reason": "bedtime_edit",
        "low_battery_alert": False,
        "readiness": {"score": 84, "temperature_deviation": -0.13,
                      "contributors": {"body_temperature": 99}},
    }
    row = repo._oura_sleep_period_row(sleep)
    assert row["period"] == 0
    assert row["readiness_score"] == 84
    assert row["readiness_temperature_deviation"] == -0.13
    assert row["readiness_score_delta"] == -2
    assert row["sleep_algorithm_version"] == "v2"
    assert row["low_battery_alert"] is False
    assert "readiness" not in row  # flattened, not stored as a dict


def test_oura_sleep_period_row_blanks_missing_readiness_block():
    repo = Repository(_config())
    row = repo._oura_sleep_period_row({"id": "x"})
    assert row["readiness_score"] is None
    assert row["readiness_temperature_deviation"] is None


# ─── _oura_session_row / _oura_rest_mode_row ────────────────────────────────
# rest_mode_period still has no real data on this account (synthetic input
# below). session DOES now, from the 2026-07-30 historical backfill — and it
# disproved the documented-schema guess: motion_count is a TimeSeries, not a
# scalar. See test_oura_session_row_sums_real_motion_count_timeseries.

def test_oura_session_row_maps_documented_fields():
    repo = Repository(_config())
    session = {
        "id": "s-1", "day": "2026-07-05", "type": "meditation",
        "start_datetime": "2026-07-05T08:00:00+02:00",
        "end_datetime": "2026-07-05T08:10:00+02:00",
        "mood": "good", "motion_count": 3,
        "heart_rate": {"interval": 5.0, "items": [60, 61]},  # excluded from the row
    }
    row = repo._oura_session_row(session)
    assert row["session_id"] == "s-1"
    assert row["type"] == "meditation"
    assert row["mood"] == "good"
    assert row["motion_count"] == 3
    assert "heart_rate" not in row


def test_oura_session_row_sums_real_motion_count_timeseries():
    """Real payload (session 7bf0c282, 2023-07-17). motion_count arrives as
    Oura's TimeSeries struct; writing it unreduced is a Sheets 400, so the row
    must carry a single number."""
    repo = Repository(_config())
    session = {
        "id": "7bf0c282-c84d-413f-98fe-d2496cca0f4e",
        "day": "2023-07-17", "type": "meditation", "mood": None,
        "start_datetime": "2023-07-17T22:02:44.000+02:00",
        "end_datetime": "2023-07-17T22:03:24.000+02:00",
        "motion_count": {
            "interval": 5.0, "items": [0, 19, 2, 20, 34, 0, 26, 15],
            "timestamp": "2023-07-17T22:02:44.000+02:00",
        },
        "heart_rate": {"interval": 5.0, "items": [60, 61]},
        "heart_rate_variability": {"interval": 5.0, "items": [20, 21]},
    }
    row = repo._oura_session_row(session)
    assert row["motion_count"] == 116
    assert isinstance(row["motion_count"], (int, float))
    assert "heart_rate" not in row
    assert "heart_rate_variability" not in row


def test_oura_session_row_blanks_motion_count_when_null():
    """The shape the live 7-day sync has been seeing — which is why the
    TimeSeries bug stayed hidden until a historical range was pulled."""
    repo = Repository(_config())
    assert repo._oura_session_row({"id": "s-1", "motion_count": None})["motion_count"] is None


def test_oura_session_row_survives_an_empty_timeseries():
    repo = Repository(_config())
    row = repo._oura_session_row({"id": "s-1", "motion_count": {"interval": 5.0, "items": []}})
    assert row["motion_count"] is None


def test_oura_session_row_skips_null_padding_inside_the_timeseries():
    repo = Repository(_config())
    row = repo._oura_session_row({"id": "s-1", "motion_count": {"items": [3, None, 4]}})
    assert row["motion_count"] == 7


def test_oura_rest_mode_row_maps_documented_fields():
    repo = Repository(_config())
    period = {"id": "r-1", "start_day": "2026-06-01", "end_day": "2026-06-10", "end_time": "2026-06-10T09:00:00+02:00"}
    row = repo._oura_rest_mode_row(period)
    assert row == {
        "rest_mode_id": "r-1", "start_day": "2026-06-01",
        "end_day": "2026-06-10", "end_time": "2026-06-10T09:00:00+02:00",
    }


# ─── oura_last_synced / oura_sync_due / mark_oura_synced ────────────────────
# Local-file throttle (services/clients/local_cache.py), not st.cache_data —
# it has to survive both a Streamlit process restart and any unrelated
# st.cache_data.clear() call elsewhere in the app (views/checkin.py clears it
# on every check-in save), neither of which an in-memory-only cache survives.

def test_oura_sync_due_when_never_synced(tmp_path, monkeypatch):
    monkeypatch.setattr(local_cache, "_DEFAULT_PATH", tmp_path / "sync_state.json")
    repo = Repository(_config())
    assert repo.oura_last_synced() is None
    assert repo.oura_sync_due(hours=2) is True


def test_oura_sync_not_due_right_after_marking(tmp_path, monkeypatch):
    monkeypatch.setattr(local_cache, "_DEFAULT_PATH", tmp_path / "sync_state.json")
    repo = Repository(_config())
    now = datetime(2026, 7, 14, 10, 0, 0)
    repo.mark_oura_synced(when=now)
    assert repo.oura_last_synced() == now
    assert repo.oura_sync_due(hours=2, now=now + timedelta(minutes=30)) is False


def test_oura_sync_due_again_after_window_elapses(tmp_path, monkeypatch):
    monkeypatch.setattr(local_cache, "_DEFAULT_PATH", tmp_path / "sync_state.json")
    repo = Repository(_config())
    now = datetime(2026, 7, 14, 10, 0, 0)
    repo.mark_oura_synced(when=now)
    assert repo.oura_sync_due(hours=2, now=now + timedelta(hours=2, minutes=1)) is True


def test_oura_sync_throttle_survives_across_repository_instances(tmp_path, monkeypatch):
    """Simulates a Streamlit process restart (or an unrelated
    st.cache_data.clear() elsewhere): a brand-new Repository instance still
    sees the marker a previous one wrote, because it lives on disk rather
    than on the Repository instance or in Streamlit's in-memory cache."""
    monkeypatch.setattr(local_cache, "_DEFAULT_PATH", tmp_path / "sync_state.json")
    repo_a = Repository(_config())
    repo_a.mark_oura_synced(when=datetime(2026, 7, 14, 9, 0, 0))

    repo_b = Repository(_config())
    assert repo_b.oura_last_synced() == datetime(2026, 7, 14, 9, 0, 0)
    assert repo_b.oura_sync_due(hours=2, now=datetime(2026, 7, 14, 9, 30, 0)) is False


def test_oura_last_synced_ignores_corrupted_marker(tmp_path, monkeypatch):
    path = tmp_path / "sync_state.json"
    monkeypatch.setattr(local_cache, "_DEFAULT_PATH", path)
    path.write_text('{"oura_last_synced": "not-a-real-timestamp"}')
    repo = Repository(_config())
    assert repo.oura_last_synced() is None
    assert repo.oura_sync_due(hours=2) is True
