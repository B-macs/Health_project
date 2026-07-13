"""
Tests for services/biometrics.py -- the pure Oura+Garmin blending math that
replaced Sheet1/Apple Health as the engine's biometric source. No I/O, no
Sheets/network -- plain dicts in, BiometricRecord out.
"""

from __future__ import annotations

from services import biometrics
from services.models import BiometricRecord


# ─── blend_metric ────────────────────────────────────────────────────────────

def test_blend_metric_both_present_weighted_average():
    value, missing = biometrics.blend_metric(100.0, 50.0, oura_weight=0.7, garmin_weight=0.3)
    assert value == 85.0  # 100*0.7 + 50*0.3
    assert missing is None


def test_blend_metric_oura_missing_uses_garmin_and_flags_oura():
    value, missing = biometrics.blend_metric(None, 50.0, oura_weight=0.7, garmin_weight=0.3)
    assert value == 50.0
    assert missing == "oura"


def test_blend_metric_garmin_missing_uses_oura_and_flags_garmin():
    value, missing = biometrics.blend_metric(100.0, None, oura_weight=0.7, garmin_weight=0.3)
    assert value == 100.0
    assert missing == "garmin"


def test_blend_metric_both_missing_returns_none_with_no_flag():
    value, missing = biometrics.blend_metric(None, None, oura_weight=0.7, garmin_weight=0.3)
    assert (value, missing) == (None, None)


def test_blend_metric_steps_weighting_favors_garmin():
    value, missing = biometrics.blend_metric(
        1000.0, 9000.0, oura_weight=biometrics.OURA_WEIGHT_STEPS, garmin_weight=biometrics.GARMIN_WEIGHT_STEPS,
    )
    assert value == 1000.0 * 0.20 + 9000.0 * 0.80
    assert missing is None


# ─── pick_main_sleep_period ──────────────────────────────────────────────────

def test_pick_main_sleep_period_empty_returns_none():
    assert biometrics.pick_main_sleep_period([]) is None


def test_pick_main_sleep_period_prefers_long_sleep_type():
    entries = [
        {"type": "nap", "total_sleep_duration": 5000},
        {"type": "long_sleep", "total_sleep_duration": 25000},
    ]
    assert biometrics.pick_main_sleep_period(entries)["type"] == "long_sleep"


def test_pick_main_sleep_period_falls_back_to_longest_duration():
    entries = [
        {"type": "nap", "total_sleep_duration": 1200},
        {"type": "nap", "total_sleep_duration": 3600},
    ]
    picked = biometrics.pick_main_sleep_period(entries)
    assert picked["total_sleep_duration"] == 3600


def test_pick_main_sleep_period_handles_missing_duration():
    entries = [{"type": "nap"}, {"type": "nap", "total_sleep_duration": 900}]
    picked = biometrics.pick_main_sleep_period(entries)
    assert picked["total_sleep_duration"] == 900


# ─── blend_biometric_day ─────────────────────────────────────────────────────

def test_blend_biometric_day_both_sources_present():
    oura = {"hrv_ms": 40.0, "resting_heart_rate": 50.0, "sleep_duration_hours": 8.0, "steps": 2000}
    garmin = {"hrv_ms": 30.0, "resting_heart_rate": 60.0, "sleep_duration_hours": 7.0, "steps": 9000}
    record = biometrics.blend_biometric_day("2026-07-13", oura, garmin)

    assert isinstance(record, BiometricRecord)
    assert record.date == "2026-07-13"
    assert record.hrv_ms == 40.0 * 0.7 + 30.0 * 0.3
    assert record.resting_heart_rate == 50.0 * 0.7 + 60.0 * 0.3
    assert record.sleep_duration_hours == 8.0 * 0.7 + 7.0 * 0.3
    assert record.steps == round(2000 * 0.2 + 9000 * 0.8)
    assert record.sources_missing == ()


def test_blend_biometric_day_flags_missing_garmin_metrics():
    oura = {"hrv_ms": 40.0, "resting_heart_rate": 50.0, "sleep_duration_hours": 8.0, "steps": 2000}
    garmin = {}
    record = biometrics.blend_biometric_day("2026-07-13", oura, garmin)

    assert record.hrv_ms == 40.0
    assert record.resting_heart_rate == 50.0
    assert record.sleep_duration_hours == 8.0
    assert record.steps == 2000
    assert set(record.sources_missing) == {
        "hrv_ms:garmin", "resting_heart_rate:garmin",
        "sleep_duration_hours:garmin", "steps:garmin",
    }


def test_blend_biometric_day_flags_missing_oura_metrics():
    oura = {}
    garmin = {"hrv_ms": 30.0, "resting_heart_rate": 60.0, "sleep_duration_hours": 7.0, "steps": 9000}
    record = biometrics.blend_biometric_day("2026-07-13", oura, garmin)

    assert record.hrv_ms == 30.0
    assert set(record.sources_missing) == {
        "hrv_ms:oura", "resting_heart_rate:oura", "sleep_duration_hours:oura", "steps:oura",
    }


def test_blend_biometric_day_both_empty_yields_all_none():
    record = biometrics.blend_biometric_day("2026-07-13", {}, {})
    assert record.hrv_ms is None
    assert record.resting_heart_rate is None
    assert record.sleep_duration_hours is None
    assert record.steps is None
    assert record.sources_missing == ()


# ─── sheet1_row_to_garmin_daily_row ──────────────────────────────────────────

def test_sheet1_row_to_garmin_daily_row_maps_known_fields():
    record = BiometricRecord(
        date="2026-01-15", hrv_ms=45.2, resting_heart_rate=58.0,
        sleep_duration_hours=7.5, steps=8500,
    )
    row = biometrics.sheet1_row_to_garmin_daily_row(record)
    assert row["date"] == "2026-01-15"
    assert row["hrv_ms"] == 45.2
    assert row["resting_hr"] == 58.0
    assert row["sleep_hours"] == 7.5
    assert row["steps"] == 8500
    assert row["sleep_score"] == ""
    assert row["avg_stress"] == ""
    assert row["calories_total"] == ""
    assert row["min_hr"] == ""
    assert row["max_hr"] == ""


def test_sheet1_row_to_garmin_daily_row_blanks_missing_values():
    record = BiometricRecord(date="2026-01-15")
    row = biometrics.sheet1_row_to_garmin_daily_row(record)
    assert row["steps"] == ""
    assert row["hrv_ms"] == ""
    assert row["resting_hr"] == ""
    assert row["sleep_hours"] == ""
