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


# ─── All seven of Oura's sleep parts (Sleep Score MODEL_VERSION 3, 2026-10-27) ─

_PARTS = {"sleep_total_sleep": "oura_sleep_total_sleep_score",
          "sleep_efficiency": "oura_sleep_efficiency_score",
          "sleep_rem_sleep": "oura_sleep_rem_score",
          "sleep_deep_sleep": "oura_sleep_deep_score",
          "sleep_latency": "oura_sleep_latency_score",
          "sleep_timing": "oura_sleep_timing_score"}


def test_oura_s_other_six_sleep_parts_reach_the_biometric_rows():
    """The score can only use Oura's parts if the rows carry them; the raw
    efficiency percent keeps its own field beside its part."""
    row = {"date": "2026-07-13", "steps": 2000, "sleep_restfulness": 58,
           **{col: 50 + i for i, col in enumerate(_PARTS)}}
    rec = _record(row)
    for i, (col, field) in enumerate(_PARTS.items()):
        assert getattr(rec, field) == 50.0 + i, field
    assert rec.oura_sleep_efficiency != rec.oura_sleep_efficiency_score


def test_a_zero_part_is_a_reading_and_a_blank_part_is_none():
    rec = _record({"date": "2026-07-13", "steps": 2000, "sleep_total_sleep": 0,
                   "sleep_timing": ""})
    assert rec.oura_sleep_total_sleep_score == 0.0
    assert rec.oura_sleep_timing_score is None
