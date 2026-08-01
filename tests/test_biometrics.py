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
    # HRV is held at Oura-only (biometrics.HRV_GARMIN_HOLD); the 70/30 it
    # would otherwise take is asserted in
    # test_lifting_the_hold_restores_the_70_30_hrv_blend below.
    assert record.hrv_ms == 40.0
    assert record.resting_heart_rate == 50.0 * 0.7 + 60.0 * 0.3
    assert record.sleep_duration_hours == 8.0 * 0.7 + 7.0 * 0.3
    assert record.steps == round(2000 * 0.2 + 9000 * 0.8)
    assert record.sources_missing == (biometrics.HRV_HELD_FLAG,)


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

    # HRV alone does NOT fall back to Garmin while the hold is on — see
    # blend_hrv's docstring. The other three still do.
    assert record.hrv_ms is None
    assert record.resting_heart_rate == 60.0
    assert set(record.sources_missing) == {
        biometrics.HRV_HELD_FLAG,
        "resting_heart_rate:oura", "sleep_duration_hours:oura", "steps:oura",
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


# ─── HRV hold — Oura-only until the two devices are measured against each
#     other. See biometrics.HRV_GARMIN_HOLD for the argument. ────────────────

def test_hrv_hold_is_on_by_default():
    """If this ever flips silently, the changeover it guards against has
    already happened."""
    assert biometrics.HRV_GARMIN_HOLD is True


def test_hrv_hold_ignores_garmin_and_keeps_ouras_value():
    value, flag = biometrics.blend_hrv(oura_val=45.0, garmin_val=30.0)
    assert value == 45.0, "held HRV must be Oura's number, not a 70/30 blend"
    assert flag == biometrics.HRV_HELD_FLAG


def test_hrv_hold_yields_none_rather_than_substituting_garmin():
    """The harder half of the rule: a wrist reading dropped into a series
    baselined on finger readings is worse than a gap, because a gap is
    visible and a silently-rescaled value is not."""
    value, flag = biometrics.blend_hrv(oura_val=None, garmin_val=30.0)
    assert value is None
    assert flag == biometrics.HRV_HELD_FLAG


def test_hrv_hold_is_a_no_op_when_garmin_has_nothing():
    """Today's situation, and every night of this app's history: the hold
    must not change current behaviour at all."""
    assert biometrics.blend_hrv(45.0, None) == biometrics.blend_metric(
        45.0, None,
        biometrics.OURA_WEIGHT_RECOVERY_SLEEP,
        biometrics.GARMIN_WEIGHT_RECOVERY_SLEEP)
    assert biometrics.blend_hrv(None, None) == (None, None)


def test_held_flag_is_distinct_from_garmin_simply_having_no_data():
    """"We chose not to use it" and "there was nothing to use" are different
    facts; only the first is a decision worth revisiting."""
    _, held = biometrics.blend_hrv(45.0, 30.0)
    _, absent = biometrics.blend_hrv(45.0, None)
    assert held == biometrics.HRV_HELD_FLAG
    assert absent == "garmin"
    assert held != absent


def test_blend_biometric_day_holds_hrv_but_still_blends_the_other_fields():
    """The hold is HRV-only — RHR and sleep keep their 70/30."""
    record = biometrics.blend_biometric_day(
        "2026-08-01",
        {"hrv_ms": 40.0, "resting_heart_rate": 50.0, "sleep_duration_hours": 7.0, "steps": 100},
        {"hrv_ms": 20.0, "resting_heart_rate": 60.0, "sleep_duration_hours": 8.0, "steps": 200},
    )
    assert record.hrv_ms == 40.0
    assert record.resting_heart_rate == 53.0        # 50*.7 + 60*.3
    assert abs(record.sleep_duration_hours - 7.3) < 1e-9
    assert biometrics.HRV_HELD_FLAG in record.sources_missing


# ─── hrv_agreement — the measurement that lifts the hold ──────────────────

def test_hrv_agreement_reports_signed_bias_garmin_minus_oura():
    """Negative means Garmin reads lower — the direction wrist PPG usually
    errs, and the direction that would quietly depress readiness."""
    stats = biometrics.hrv_agreement([(50.0, 44.0), (60.0, 54.0), (40.0, 34.0)])
    assert stats["n"] == 3
    assert stats["mean_bias"] == -6.0
    assert stats["median_bias"] == -6.0
    assert stats["sd_bias"] == 0.0


def test_hrv_agreement_is_not_ready_below_the_night_floor():
    below = biometrics.hrv_agreement([(50.0, 45.0)] * (biometrics.MIN_HRV_PAIRED_NIGHTS - 1))
    at = biometrics.hrv_agreement([(50.0, 45.0)] * biometrics.MIN_HRV_PAIRED_NIGHTS)
    assert below["ready"] is False
    assert at["ready"] is True


def test_hrv_agreement_sd_exposes_an_unstable_offset():
    """A large sd means the offset is not a constant, so no single weighting
    fixes it — the case where lifting the hold would be wrong even at n>=14."""
    steady = biometrics.hrv_agreement([(50.0, 45.0)] * 20)
    jumpy = biometrics.hrv_agreement([(50.0, 45.0 + (10 if i % 2 else -10)) for i in range(20)])
    assert steady["sd_bias"] == 0.0
    assert jumpy["sd_bias"] > 9.0
    assert steady["mean_bias"] == jumpy["mean_bias"]  # identical mean, different story


def test_hrv_agreement_with_no_paired_nights_is_empty_not_zero():
    """Today's state. n=0 must not read as "bias is 0.0", which would look
    like perfect agreement."""
    stats = biometrics.hrv_agreement([])
    assert stats["n"] == 0
    assert stats["ready"] is False
    assert stats["mean_bias"] is None


# ─── Lifting the hold restores exactly the documented 70/30 behaviour.
#     These carry the intent of the two blend_biometric_day assertions the
#     hold changed, so that behaviour stays pinned rather than discarded. ────

def test_lifting_the_hold_restores_the_70_30_hrv_blend(monkeypatch):
    monkeypatch.setattr(biometrics, "HRV_GARMIN_HOLD", False)
    record = biometrics.blend_biometric_day(
        "2026-07-13",
        {"hrv_ms": 40.0, "resting_heart_rate": 50.0, "sleep_duration_hours": 8.0, "steps": 2000},
        {"hrv_ms": 30.0, "resting_heart_rate": 60.0, "sleep_duration_hours": 7.0, "steps": 9000},
    )
    assert record.hrv_ms == 40.0 * 0.7 + 30.0 * 0.3
    assert record.sources_missing == ()


def test_lifting_the_hold_restores_the_garmin_hrv_fallback(monkeypatch):
    monkeypatch.setattr(biometrics, "HRV_GARMIN_HOLD", False)
    record = biometrics.blend_biometric_day(
        "2026-07-13", {},
        {"hrv_ms": 30.0, "resting_heart_rate": 60.0, "sleep_duration_hours": 7.0, "steps": 9000},
    )
    assert record.hrv_ms == 30.0
    assert "hrv_ms:oura" in record.sources_missing


def test_the_hold_only_ever_touches_hrv(monkeypatch):
    """Whatever the hold does, RHR/sleep/steps must be bit-identical with it
    on and off — a hold that quietly moved another metric would be a far
    worse bug than the one it prevents."""
    oura = {"hrv_ms": 40.0, "resting_heart_rate": 50.0, "sleep_duration_hours": 8.0, "steps": 2000}
    garmin = {"hrv_ms": 30.0, "resting_heart_rate": 60.0, "sleep_duration_hours": 7.0, "steps": 9000}
    held = biometrics.blend_biometric_day("2026-07-13", oura, garmin)
    monkeypatch.setattr(biometrics, "HRV_GARMIN_HOLD", False)
    lifted = biometrics.blend_biometric_day("2026-07-13", oura, garmin)
    for field in ("resting_heart_rate", "sleep_duration_hours", "steps"):
        assert getattr(held, field) == getattr(lifted, field)
