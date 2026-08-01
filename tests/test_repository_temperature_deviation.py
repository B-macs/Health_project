"""Raw °C temperature-deviation passthrough through Repository.get_biometric_rolling().

engine.traffic_light scores body temperature against ABSOLUTE cut points, so
it needs the raw reading — not just Oura's 0-100 body_temperature
contributor, which is Oura's already-scored version of the same signal. Both
are carried on BiometricRecord; these pin that the raw one survives the trip
from the Oura Daily tab intact, including the two values a careless
`or None` would destroy: 0.0 and negatives.

Fixture helpers are shared with tests/test_repository_biometric_blend.py.
"""

from __future__ import annotations

import datetime

from tests.test_repository_biometric_blend import _repo_with_tabs


#
#
# engine.traffic_light scores body temperature against ABSOLUTE °C cut points,
# so it needs the raw reading, not just Oura's 0-100 body_temperature
# contributor. Both are carried; these pin that the raw one survives the trip.

def _temp_repo(oura_daily_row):
    return _repo_with_tabs(
        oura_daily=[oura_daily_row],
        oura_sleep=[{"sleep_id": "s1", "day": "2026-07-13", "type": "long_sleep",
                     "total_sleep_duration": 28800, "average_hrv": 40,
                     "lowest_heart_rate": 50}],
    ).get_biometric_rolling(days=7, today=datetime.date(2026, 7, 13))[0]


def test_raw_temperature_deviation_is_carried_alongside_the_scored_contributor():
    rec = _temp_repo({
        "date": "2026-07-13", "steps": 2000,
        "readiness_body_temperature": 51,
        "readiness_temperature_deviation": 0.65,
    })
    assert rec.oura_temperature_deviation == 0.65
    assert rec.oura_body_temperature == 51


def test_a_zero_temperature_deviation_is_a_reading_not_a_missing_value():
    """`or None` would collapse a genuine 0.0 °C deviation — a perfectly
    normal night — into "no data", greying the metric."""
    rec = _temp_repo({
        "date": "2026-07-13", "steps": 2000,
        "readiness_body_temperature": 100,
        "readiness_temperature_deviation": 0.0,
    })
    assert rec.oura_temperature_deviation == 0.0


def test_a_negative_temperature_deviation_survives_intact():
    rec = _temp_repo({
        "date": "2026-07-13", "steps": 2000,
        "readiness_temperature_deviation": -0.07,
    })
    assert rec.oura_temperature_deviation == -0.07


def test_a_blank_temperature_cell_reads_back_as_none():
    rec = _temp_repo({
        "date": "2026-07-13", "steps": 2000,
        "readiness_temperature_deviation": "",
    })
    assert rec.oura_temperature_deviation is None


def test_temperature_deviation_is_none_when_the_column_is_absent_entirely():
    rec = _temp_repo({"date": "2026-07-13", "steps": 2000})
    assert rec.oura_temperature_deviation is None
