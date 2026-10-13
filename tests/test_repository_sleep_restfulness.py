"""Oura's own Restfulness contributor reaches the biometric rows.

Sleep Score MODEL_VERSION 2 (2026-10-13, the athlete's choice) scores
Restfulness from Oura's 0-100 reading in the Oura Daily row instead of a band
over restless periods per hour, which scored 0 on 426 of 427 real nights. The
score can only use the reading if Repository.get_biometric_rolling carries it,
so these pin the trip — including a genuine 0, which `or None` would lose.
"""

from __future__ import annotations

import datetime

from tests.test_repository_biometric_blend import _repo_with_tabs


def _record(oura_daily_row):
    return _repo_with_tabs(
        oura_daily=[oura_daily_row],
        oura_sleep=[{"sleep_id": "s1", "day": "2026-07-13", "type": "long_sleep",
                     "total_sleep_duration": 28800, "average_hrv": 40,
                     "lowest_heart_rate": 50, "restless_periods": 360}],
    ).get_biometric_rolling(days=7, today=datetime.date(2026, 7, 13))[0]


def test_oura_s_restfulness_is_carried_beside_the_raw_count():
    rec = _record({"date": "2026-07-13", "steps": 2000, "sleep_restfulness": 64})
    assert rec.oura_sleep_restfulness == 64.0
    assert rec.oura_sleep_restless_periods == 360


def test_a_zero_restfulness_is_a_reading_not_a_missing_value():
    rec = _record({"date": "2026-07-13", "steps": 2000, "sleep_restfulness": 0})
    assert rec.oura_sleep_restfulness == 0.0


def test_a_blank_or_absent_restfulness_reads_as_none():
    assert _record({"date": "2026-07-13", "steps": 2000,
                    "sleep_restfulness": ""}).oura_sleep_restfulness is None
    assert _record({"date": "2026-07-13", "steps": 2000}).oura_sleep_restfulness is None
