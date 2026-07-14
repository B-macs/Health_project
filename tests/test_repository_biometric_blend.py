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

from services.clients import sheets
from services.config import Config
from services.repository import Repository
from tests.test_repository import _FakeNotionClient, _date_prop, _number_prop


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


class _FakeWorksheet:
    def __init__(self, rows):
        self._rows = rows

    def get_all_records(self):
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
    assert r.hrv_ms == 40 * 0.7 + 30 * 0.3
    assert r.resting_heart_rate == 50 * 0.7 + 60 * 0.3
    assert r.sleep_duration_hours == 8.0 * 0.7 + 7.0 * 0.3
    assert r.steps == round(2000 * 0.2 + 9000 * 0.8)
    assert r.sources_missing == ()


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
    assert r.hrv_ms == 30
    assert r.resting_heart_rate == 60
    assert r.sleep_duration_hours == 7.0
    assert r.steps == 9000
    assert set(r.sources_missing) == {
        "hrv_ms:oura", "resting_heart_rate:oura",
        "sleep_duration_hours:oura", "steps:oura",
    }


def test_blend_picks_long_sleep_over_naps_for_the_same_day():
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
    assert r.sleep_duration_hours == 7.0


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
