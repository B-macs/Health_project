"""
Tests for the Repository.get_all_*_rows methods added for
services.datastore (the project's consolidated database) -- Garmin
Daily/Activities, Session HR, the 5 Oura tabs, and the Notion Config DB.
Each is a thin unwindowed passthrough over an existing worksheet/DB
accessor, so what's actually being verified here is that they read the
right source and return every row unmapped (contrasting with the
narrower/windowed existing methods, e.g. get_session_hr_history, which
drops columns get_all_session_hr_rows must keep).

Fake Sheets client mirrors _FakeMultiSheetsClient in
tests/test_repository_biometric_blend.py (supports multiple named tabs).
"""

from __future__ import annotations

from services.clients import sheets
from services.config import Config
from services.repository import Repository
from tests.test_repository import _FakeNotionClient, _date_prop, _rich_text_prop, _title_prop


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
        self.numericise_ignore_calls: list = []

    def get_all_records(self, numericise_ignore=None):
        self.numericise_ignore_calls.append(numericise_ignore)
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


def _repo_with_tabs(**tabs) -> Repository:
    repo = Repository(_config())
    repo._sheets_client = _FakeMultiSheetsClient(tabs)
    return repo


# ─── Garmin ───────────────────────────────────────────────────────────────

def test_get_all_garmin_daily_rows_returns_every_row_unmapped():
    rows = [{"date": "2026-07-30", "steps": 8000}, {"date": "2026-07-31", "steps": 9000}]
    repo = _repo_with_tabs(**{sheets.GARMIN_DAILY_WORKSHEET: rows})
    assert repo.get_all_garmin_daily_rows() == rows


def test_get_all_garmin_activities_rows_returns_every_row_unmapped():
    rows = [{"activity_id": "a1", "date": "2026-07-31", "type": "running"}]
    repo = _repo_with_tabs(**{sheets.GARMIN_ACTIVITIES_WORKSHEET: rows})
    assert repo.get_all_garmin_activities_rows() == rows


# ─── Session HR ───────────────────────────────────────────────────────────

def test_get_all_session_hr_rows_includes_columns_get_session_hr_history_drops():
    rows = [{
        "date": "2026-07-31", "activity_id": "a1", "activity_name": "Run",
        "activity_type": "running", "start_time_local": "2026-07-31 07:00:00",
        "duration_minutes": 30, "overlap_minutes": 28, "avg_hr": 140, "max_hr": 165,
        "hr_max_used": 190, "edwards_load": 120.5, "hr_strain": 8.2, "banister_trimp": 95.0,
        "total_minutes": 30, "zone_source": "garmin", "zone_minutes_json": "{}",
        "per_exercise_json": "{}",
    }]
    repo = _repo_with_tabs(**{sheets.SESSION_HR_WORKSHEET: rows})
    result = repo.get_all_session_hr_rows()
    assert result == rows
    # The exact gap this method closes vs. get_session_hr_history.
    for col in ("activity_id", "start_time_local", "duration_minutes", "total_minutes"):
        assert col in result[0]


def test_get_all_session_hr_rows_returns_empty_list_on_error():
    repo = Repository(_config())  # no sheets client configured -> raises internally
    assert repo.get_all_session_hr_rows() == []


# ─── Oura ─────────────────────────────────────────────────────────────────

def test_get_all_oura_daily_rows_returns_all_rows():
    rows = [{"date": "2026-07-31", "sleep_score": 82}]
    repo = _repo_with_tabs(**{sheets.OURA_DAILY_WORKSHEET: rows})
    assert repo.get_all_oura_daily_rows() == rows


def test_get_all_oura_workouts_rows_returns_all_rows():
    rows = [{"workout_id": "w1", "day": "2026-07-31", "activity": "walking"}]
    repo = _repo_with_tabs(**{sheets.OURA_WORKOUTS_WORKSHEET: rows})
    assert repo.get_all_oura_workouts_rows() == rows


def test_get_all_oura_sleep_periods_rows_exempts_hypnogram_columns_from_numericising():
    rows = [{"sleep_id": "s1", "day": "2026-07-31", "sleep_phase_5_min": "4422211"}]
    repo = _repo_with_tabs(**{sheets.OURA_SLEEP_PERIODS_WORKSHEET: rows})
    result = repo.get_all_oura_sleep_periods_rows()
    assert result == rows
    ws = repo._sheets_client.open_by_key("sheet-id").worksheet(sheets.OURA_SLEEP_PERIODS_WORKSHEET)
    assert ws.numericise_ignore_calls[0] is not None  # the hypnogram-column indices were passed


def test_get_all_oura_sessions_rows_returns_all_rows():
    rows = [{"session_id": "se1", "day": "2026-07-31", "type": "meditation"}]
    repo = _repo_with_tabs(**{sheets.OURA_SESSIONS_WORKSHEET: rows})
    assert repo.get_all_oura_sessions_rows() == rows


def test_get_all_oura_rest_mode_rows_returns_all_rows():
    rows = [{"rest_mode_id": "r1", "start_day": "2026-07-20", "end_day": "2026-07-25"}]
    repo = _repo_with_tabs(**{sheets.OURA_REST_MODE_WORKSHEET: rows})
    assert repo.get_all_oura_rest_mode_rows() == rows


# ─── Config DB (Notion) ───────────────────────────────────────────────────

def test_get_all_config_rows_returns_every_key_as_a_faithful_copy():
    pages = [
        {"properties": {
            "Key": _title_prop("current_stage"), "Value": _rich_text_prop("2"),
            "Updated": _date_prop("2026-07-01"),
        }},
        {"properties": {
            "Key": _title_prop("phases"), "Value": _rich_text_prop('[{"phase_number": 1}]'),
            "Updated": _date_prop("2026-07-01"),
        }},
    ]
    repo = Repository(_config())
    repo._notion_client = _FakeNotionClient({"db-config": pages})
    rows = repo.get_all_config_rows()
    assert rows == [
        {"key": "current_stage", "value": "2", "updated": "2026-07-01"},
        {"key": "phases", "value": '[{"phase_number": 1}]', "updated": "2026-07-01"},
    ]


def test_get_all_config_rows_empty_when_nothing_configured():
    repo = Repository(_config())
    repo._notion_client = _FakeNotionClient({"db-config": []})
    assert repo.get_all_config_rows() == []


# ─── Readiness checkins raw (Notion, includes AI-parsed fields) ──────────

def test_get_all_readiness_checkins_raw_includes_ai_parsed_fields():
    page = {"properties": {
        "Date": _date_prop("2026-07-31"), "Tightness": {"number": 3}, "Pain": {"number": 0},
        "Parsed": {"checkbox": True}, "Parsed Severity": {"number": 4.5},
        "Parsed Areas": _rich_text_prop('["lower_back"]'),
        "Parsed Sensations": _rich_text_prop('["tight"]'),
        "Warning": {"select": {"name": "monitor"}},
    }}
    repo = Repository(_config())
    repo._notion_client = _FakeNotionClient({"db-readiness": [page]})
    row = repo.get_all_readiness_checkins_raw()[0]
    assert row["parsed"] == 1
    assert row["parsed_severity"] == 4.5
    assert row["parsed_areas"] == '["lower_back"]'
    assert row["parsed_sensations"] == '["tight"]'
    assert row["warning_level"] == "monitor"


def test_get_all_readiness_checkins_raw_is_unwindowed():
    repo = Repository(_config())
    repo._notion_client = _FakeNotionClient({"db-readiness": []})
    repo.get_all_readiness_checkins_raw()
    query = repo._notion_client.databases.queries[-1]
    assert "filter" not in query
