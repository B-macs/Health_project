"""
Tests for Repository.get_biometric_rolling()'s new Oura+Garmin blended
implementation -- the engine's live biometric source as of this change
(replacing Sheet1/Apple Health; see get_sheet1_biometric_rolling for the
retired pipeline, still covered in tests/test_repository.py).

Fake Sheets client mirrors _FakeSheetsClient/_FakeWorksheet in
tests/test_repository.py but supports multiple named tabs (Oura Daily,
Oura Sleep Periods, Garmin Daily), since the blend reads all three.
"""

from __future__ import annotations

import datetime

from services import biometrics
from services.clients import sheets
from services.config import Config
from services.repository import Repository
from tests.test_repository import _FakeNotionClient, _date_prop, _number_prop


def _config(**overrides) -> Config:
    base = dict(
        notion_api_key="ntn_test",
        notion_db_readiness="db-readiness",
        notion_db_training="db-training",
        notion_db_config="db-config",
        google_sheets_id="sheet-id",
        google_service_account={"type": "service_account"},
    )
    base.update(overrides)
    return Config(**base)


class _FakeWorksheet:
    def __init__(self, rows):
        self._rows = rows

    def get_all_records(self, numericise_ignore=None):
        return self._rows


class _FakeSpreadsheet:
    def __init__(self, tabs: dict):
        self._tabs = {name: _FakeWorksheet(rows) for name, rows in tabs.items()}

    def worksheet(self, title):
        return self._tabs[title]


class _FakeMultiSheetsClient:
    def __init__(self, tabs: dict):
        self._spreadsheet = _FakeSpreadsheet(tabs)

    def open_by_key(self, sheet_id):
        return self._spreadsheet


def _repo_with_tabs(oura_daily=None, oura_sleep=None, garmin_daily=None, readiness_pages=None) -> Repository:
    repo = Repository(_config())
    repo._sheets_client = _FakeMultiSheetsClient({
        sheets.OURA_DAILY_WORKSHEET: oura_daily or [],
        sheets.OURA_SLEEP_PERIODS_WORKSHEET: oura_sleep or [],
        sheets.GARMIN_DAILY_WORKSHEET: garmin_daily or [],
    })
    # get_biometric_rolling() also pulls alcohol units from the Notion
    # Readiness DB (self-reported, not a wearable source) — empty by
    # default so these blend-only tests are unaffected.
    repo._notion_client = _FakeNotionClient({"db-readiness": readiness_pages or []})
    return repo


def test_blend_both_sources_present():
    repo = _repo_with_tabs(
        oura_daily=[{"date": "2026-07-13", "steps": 2000}],
        oura_sleep=[{
            "sleep_id": "s1", "day": "2026-07-13", "type": "long_sleep",
            "total_sleep_duration": 28800,  # 8h
            "average_hrv": 40, "lowest_heart_rate": 50,
        }],
        garmin_daily=[{
            "date": "2026-07-13", "steps": 9000, "resting_hr": 60,
            "sleep_hours": 7.0, "hrv_ms": 30,
        }],
    )
    rows = repo.get_biometric_rolling(days=7, today=datetime.date(2026, 7, 13))
    assert len(rows) == 1
    r = rows[0]
    assert r.date == "2026-07-13"
    # HRV holds at Oura-only end to end, not just in the pure blender —
    # biometrics.HRV_GARMIN_HOLD. The 70/30 it takes once lifted is asserted
    # in test_lifting_the_hold_blends_hrv_through_the_repository below.
    assert r.hrv_ms == 40
    assert r.resting_heart_rate == 50 * 0.7 + 60 * 0.3
    assert r.sleep_duration_hours == 8.0 * 0.7 + 7.0 * 0.3
    assert r.steps == round(2000 * 0.2 + 9000 * 0.8)
    assert r.sources_missing == (biometrics.HRV_HELD_FLAG,)


def test_blend_garmin_missing_falls_back_to_oura_and_flags_it():
    repo = _repo_with_tabs(
        oura_daily=[{"date": "2026-07-13", "steps": 2000}],
        oura_sleep=[{
            "sleep_id": "s1", "day": "2026-07-13", "type": "long_sleep",
            "total_sleep_duration": 28800, "average_hrv": 40, "lowest_heart_rate": 50,
        }],
        garmin_daily=[],  # not synced yet today
    )
    rows = repo.get_biometric_rolling(days=7, today=datetime.date(2026, 7, 13))
    assert len(rows) == 1
    r = rows[0]
    assert r.hrv_ms == 40
    assert r.resting_heart_rate == 50
    assert r.sleep_duration_hours == 8.0
    assert r.steps == 2000
    assert set(r.sources_missing) == {
        "hrv_ms:garmin", "resting_heart_rate:garmin",
        "sleep_duration_hours:garmin", "steps:garmin",
    }


def test_blend_oura_missing_falls_back_to_garmin_and_flags_it():
    repo = _repo_with_tabs(
        oura_daily=[],
        oura_sleep=[],
        garmin_daily=[{
            "date": "2026-07-13", "steps": 9000, "resting_hr": 60,
            "sleep_hours": 7.0, "hrv_ms": 30,
        }],
    )
    rows = repo.get_biometric_rolling(days=7, today=datetime.date(2026, 7, 13))
    assert len(rows) == 1
    r = rows[0]
    # Everything falls back to Garmin EXCEPT hrv_ms, which is held.
    assert r.hrv_ms is None
    assert r.resting_heart_rate == 60
    assert r.sleep_duration_hours == 7.0
    assert r.steps == 9000
    assert set(r.sources_missing) == {
        biometrics.HRV_HELD_FLAG, "resting_heart_rate:oura",
        "sleep_duration_hours:oura", "steps:oura",
    }


def test_blend_takes_vitals_from_long_sleep_but_duration_from_the_whole_day():
    """The split nap support turns on: the main night alone supplies HRV and
    resting HR (a nap's are measured over minutes of an awake, upright body),
    while the day's total sleep counts the nap too — it is sleep that
    happened. Before 2026-08-03 the 30-minute nap here was discarded
    entirely and this day read 7.0 h. See services/biometrics.py."""
    repo = _repo_with_tabs(
        oura_sleep=[
            {"sleep_id": "nap", "day": "2026-07-13", "type": "nap",
             "total_sleep_duration": 1800, "average_hrv": 20, "lowest_heart_rate": 70},
            {"sleep_id": "main", "day": "2026-07-13", "type": "long_sleep",
             "total_sleep_duration": 25200, "average_hrv": 42, "lowest_heart_rate": 48},
        ],
    )
    rows = repo.get_biometric_rolling(days=7, today=datetime.date(2026, 7, 13))
    r = rows[0]
    assert r.hrv_ms == 42
    assert r.resting_heart_rate == 48
    assert r.sleep_duration_hours == 7.5


def test_blend_empty_range_returns_empty_list():
    repo = _repo_with_tabs()
    assert repo.get_biometric_rolling(days=7, today=datetime.date(2026, 7, 13)) == []


def test_blend_sorted_ascending_across_dates():
    repo = _repo_with_tabs(
        oura_daily=[
            {"date": "2026-07-13", "steps": 1000},
            {"date": "2026-07-10", "steps": 2000},
        ],
    )
    rows = repo.get_biometric_rolling(days=7, today=datetime.date(2026, 7, 13))
    assert [r.date for r in rows] == ["2026-07-10", "2026-07-13"]


def test_blend_excludes_dates_outside_window():
    repo = _repo_with_tabs(
        oura_daily=[
            {"date": "2026-07-13", "steps": 1000},
            {"date": "2026-05-01", "steps": 2000},  # outside a 7-day window
        ],
    )
    rows = repo.get_biometric_rolling(days=7, today=datetime.date(2026, 7, 13))
    assert [r.date for r in rows] == ["2026-07-13"]


def test_blend_attaches_alcohol_units_from_notion_checkin():
    readiness_page = {"properties": {
        "Date": _date_prop("2026-07-13"),
        "Alcohol Units": _number_prop(1.5),
    }}
    repo = _repo_with_tabs(
        oura_daily=[{"date": "2026-07-13", "steps": 2000}],
        readiness_pages=[readiness_page],
    )
    rows = repo.get_biometric_rolling(days=7, today=datetime.date(2026, 7, 13))
    assert len(rows) == 1
    assert rows[0].alcohol_units == 1.5


def test_blend_alcohol_units_none_when_no_checkin_logged():
    repo = _repo_with_tabs(oura_daily=[{"date": "2026-07-13", "steps": 2000}])
    rows = repo.get_biometric_rolling(days=7, today=datetime.date(2026, 7, 13))
    assert rows[0].alcohol_units is None


def test_blend_passes_through_raw_oura_sleep_awake_seconds():
    # Feeds the wake-time-adjustment feature (CLAUDE.md rule 4's narrow
    # manual-entry exception, services.sleep_score.compute_sleep_score) --
    # a straight passthrough of Oura's raw awake_time reading, same as its
    # oura_sleep_efficiency/oura_sleep_total_seconds siblings.
    repo = _repo_with_tabs(
        oura_sleep=[{
            "sleep_id": "s1", "day": "2026-07-13", "type": "long_sleep",
            "total_sleep_duration": 28800, "average_hrv": 40, "lowest_heart_rate": 50,
            "awake_time": 1800,
        }],
    )
    rows = repo.get_biometric_rolling(days=7, today=datetime.date(2026, 7, 13))
    assert rows[0].oura_sleep_awake_seconds == 1800


# ─── HRV hold, end to end, plus the measurement that lifts it ─────────────

def _paired_repo(n_paired: int, garmin_hrv=30, oura_hrv=40):
    """n_paired consecutive days where BOTH devices report HRV."""
    days = [datetime.date(2026, 7, 1) + datetime.timedelta(days=i) for i in range(n_paired)]
    return _repo_with_tabs(
        oura_daily=[{"date": d.isoformat(), "steps": 2000} for d in days],
        oura_sleep=[{
            "sleep_id": f"s{i}", "day": d.isoformat(), "type": "long_sleep",
            "total_sleep_duration": 28800, "average_hrv": oura_hrv, "lowest_heart_rate": 50,
        } for i, d in enumerate(days)],
        garmin_daily=[{
            "date": d.isoformat(), "steps": 9000, "resting_hr": 60,
            "sleep_hours": 7.0, "hrv_ms": garmin_hrv,
        } for d in days],
    )


def test_lifting_the_hold_blends_hrv_through_the_repository(monkeypatch):
    """Carries the intent of the original assertion the hold changed."""
    monkeypatch.setattr(biometrics, "HRV_GARMIN_HOLD", False)
    repo = _repo_with_tabs(
        oura_daily=[{"date": "2026-07-13", "steps": 2000}],
        oura_sleep=[{
            "sleep_id": "s1", "day": "2026-07-13", "type": "long_sleep",
            "total_sleep_duration": 28800, "average_hrv": 40, "lowest_heart_rate": 50,
        }],
        garmin_daily=[{
            "date": "2026-07-13", "steps": 9000, "resting_hr": 60,
            "sleep_hours": 7.0, "hrv_ms": 30,
        }],
    )
    r = repo.get_biometric_rolling(days=7, today=datetime.date(2026, 7, 13))[0]
    assert r.hrv_ms == 40 * 0.7 + 30 * 0.3
    assert r.sources_missing == ()


def test_hrv_blend_status_reports_no_evidence_when_garmin_has_no_hrv():
    """The Forerunner 645 era, and every night of history: Garmin's HRV
    endpoint returns nothing, so there is nothing to compare."""
    repo = _repo_with_tabs(
        oura_daily=[{"date": "2026-07-13", "steps": 2000}],
        oura_sleep=[{
            "sleep_id": "s1", "day": "2026-07-13", "type": "long_sleep",
            "total_sleep_duration": 28800, "average_hrv": 40, "lowest_heart_rate": 50,
        }],
        garmin_daily=[{"date": "2026-07-13", "steps": 9000, "resting_hr": 60, "hrv_ms": ""}],
    )
    status = repo.hrv_blend_status(days=30, today=datetime.date(2026, 7, 13))
    assert status["held"] is True
    assert status["garmin_nights"] == 0
    assert status["n"] == 0
    assert status["ready"] is False
    assert status["mean_bias"] is None


def test_hrv_blend_status_measures_the_bias_once_both_devices_report():
    repo = _paired_repo(20, garmin_hrv=30, oura_hrv=40)
    status = repo.hrv_blend_status(days=60, today=datetime.date(2026, 7, 21))
    assert status["n"] == 20
    assert status["ready"] is True
    assert status["mean_bias"] == -10.0     # Garmin reads 10 ms below Oura
    assert status["sd_bias"] == 0.0
    assert status["held"] is True, "measuring the bias must not lift the hold by itself"


def test_hrv_blend_status_stays_not_ready_under_the_night_floor():
    repo = _paired_repo(biometrics.MIN_HRV_PAIRED_NIGHTS - 1)
    status = repo.hrv_blend_status(days=60, today=datetime.date(2026, 7, 21))
    assert status["n"] == biometrics.MIN_HRV_PAIRED_NIGHTS - 1
    assert status["ready"] is False


def test_readiness_hrv_is_unchanged_by_garmin_arriving_while_held():
    """The whole purpose. The same Oura nights must produce the same hrv_ms
    whether or not a Garmin watch started reporting HRV partway through."""
    without = _repo_with_tabs(
        oura_daily=[{"date": "2026-07-13", "steps": 2000}],
        oura_sleep=[{"sleep_id": "s1", "day": "2026-07-13", "type": "long_sleep",
                     "total_sleep_duration": 28800, "average_hrv": 40, "lowest_heart_rate": 50}],
        garmin_daily=[{"date": "2026-07-13", "steps": 9000, "resting_hr": 60, "sleep_hours": 7.0}],
    ).get_biometric_rolling(days=7, today=datetime.date(2026, 7, 13))[0]
    with_garmin_hrv = _repo_with_tabs(
        oura_daily=[{"date": "2026-07-13", "steps": 2000}],
        oura_sleep=[{"sleep_id": "s1", "day": "2026-07-13", "type": "long_sleep",
                     "total_sleep_duration": 28800, "average_hrv": 40, "lowest_heart_rate": 50}],
        garmin_daily=[{"date": "2026-07-13", "steps": 9000, "resting_hr": 60,
                       "sleep_hours": 7.0, "hrv_ms": 22}],
    ).get_biometric_rolling(days=7, today=datetime.date(2026, 7, 13))[0]
    assert without.hrv_ms == with_garmin_hrv.hrv_ms == 40
