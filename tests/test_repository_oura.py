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


# ─── _oura_session_row / _oura_rest_mode_row ────────────────────────────────
# No real data available on the verified account for these two — synthetic
# input matching Oura's documented schema.

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


def test_oura_rest_mode_row_maps_documented_fields():
    repo = Repository(_config())
    period = {"id": "r-1", "start_day": "2026-06-01", "end_day": "2026-06-10", "end_time": "2026-06-10T09:00:00+02:00"}
    row = repo._oura_rest_mode_row(period)
    assert row == {
        "rest_mode_id": "r-1", "start_day": "2026-06-01",
        "end_day": "2026-06-10", "end_time": "2026-06-10T09:00:00+02:00",
    }
