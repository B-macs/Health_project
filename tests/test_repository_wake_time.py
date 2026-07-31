"""
Tests for the Wake Time Adjustments persistence layer — Repository.
get_wake_time_adjustment / set_wake_time_adjustment / get_wake_time_adjustments.

CLAUDE.md rule 4's narrow, documented exception to "no manual biometric
entry": a per-night correction for Oura's known wake-time-overestimation
pattern (services.sleep_score.compute_sleep_score's wake_time_adjustments
param). The raw Oura reading (models.BiometricRecord.oura_sleep_awake_seconds)
lives in an entirely separate tab/field and is never touched here.

Same tiny-tab pattern as Metrics History (test_repository_metrics_history.py)
— fake worksheet mirrors _FakeMetricsHistoryWorksheet there (find/update/
append_row/get_all_records) since upsert_row_by_key needs all four.
"""

from __future__ import annotations

import datetime

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


class _FakeCell:
    def __init__(self, row):
        self.row = row


class _FakeWakeTimeWorksheet:
    def __init__(self, rows=None):
        self.header = ["date", "adjustment_minutes"]
        self.rows = rows or []
        self.appended = []
        self.updates = []

    def get_all_records(self, numericise_ignore=None):
        return [dict(zip(self.header, r)) for r in self.rows]

    def find(self, query, in_column=None):
        idx = in_column - 1
        for i, row in enumerate(self.rows):
            if idx < len(row) and row[idx] == query:
                return _FakeCell(row=i + 2)
        return None

    def update(self, values, range_name):
        self.updates.append((range_name, values))
        cell_row = int("".join(ch for ch in range_name.split(":")[0] if ch.isdigit()))
        self.rows[cell_row - 2] = list(values[0])

    def append_row(self, values):
        self.appended.append(values)
        self.rows.append(list(values))


class _FakeSpreadsheet:
    def __init__(self, ws: _FakeWakeTimeWorksheet):
        self._ws = ws

    def worksheet(self, name):
        return self._ws


class _FakeSheetsClient:
    def __init__(self, ws: _FakeWakeTimeWorksheet):
        self._ws = ws

    def open_by_key(self, sheet_id):
        return _FakeSpreadsheet(self._ws)


def _repo_with_ws(ws: _FakeWakeTimeWorksheet) -> Repository:
    repo = Repository(_config())
    repo._sheets_client = _FakeSheetsClient(ws)
    return repo


# ─── get_wake_time_adjustment ────────────────────────────────────────────────

def test_get_wake_time_adjustment_returns_zero_when_nothing_stored():
    repo = _repo_with_ws(_FakeWakeTimeWorksheet())
    assert repo.get_wake_time_adjustment(datetime.date(2026, 7, 20)) == 0.0


def test_get_wake_time_adjustment_returns_stored_value():
    ws = _FakeWakeTimeWorksheet(rows=[["2026-07-20", 15]])
    repo = _repo_with_ws(ws)
    assert repo.get_wake_time_adjustment(datetime.date(2026, 7, 20)) == 15.0


def test_get_wake_time_adjustment_ignores_other_dates():
    ws = _FakeWakeTimeWorksheet(rows=[["2026-07-19", 30]])
    repo = _repo_with_ws(ws)
    assert repo.get_wake_time_adjustment(datetime.date(2026, 7, 20)) == 0.0


# ─── set_wake_time_adjustment ────────────────────────────────────────────────

def test_set_wake_time_adjustment_appends_new_date():
    ws = _FakeWakeTimeWorksheet()
    repo = _repo_with_ws(ws)
    repo.set_wake_time_adjustment(datetime.date(2026, 7, 20), 20.0)
    assert ws.appended == [["2026-07-20", 20.0]]


def test_set_wake_time_adjustment_updates_existing_date_in_place():
    ws = _FakeWakeTimeWorksheet(rows=[["2026-07-20", 10]])
    repo = _repo_with_ws(ws)
    repo.set_wake_time_adjustment(datetime.date(2026, 7, 20), 25.0)
    assert len(ws.rows) == 1  # updated in place, not appended
    assert ws.rows[0] == ["2026-07-20", 25.0]


def test_set_wake_time_adjustment_never_touches_a_different_date():
    ws = _FakeWakeTimeWorksheet(rows=[["2026-07-19", 30]])
    repo = _repo_with_ws(ws)
    repo.set_wake_time_adjustment(datetime.date(2026, 7, 20), 5.0)
    assert len(ws.rows) == 2
    assert ["2026-07-19", 30] in ws.rows
    assert ["2026-07-20", 5.0] in ws.rows


# ─── get_wake_time_adjustments (bulk/ranged read) ────────────────────────────

def test_get_wake_time_adjustments_keys_by_date():
    ws = _FakeWakeTimeWorksheet(rows=[
        ["2026-07-19", 10],
        ["2026-07-20", 15],
    ])
    repo = _repo_with_ws(ws)
    out = repo.get_wake_time_adjustments()
    assert out == {"2026-07-19": 10.0, "2026-07-20": 15.0}


def test_get_wake_time_adjustments_filters_by_start_and_end():
    ws = _FakeWakeTimeWorksheet(rows=[
        ["2026-06-01", 10],
        ["2026-07-01", 20],
        ["2026-08-01", 30],
    ])
    repo = _repo_with_ws(ws)
    out = repo.get_wake_time_adjustments(start="2026-06-15", end="2026-07-15")
    assert out == {"2026-07-01": 20.0}


def test_get_wake_time_adjustments_empty_tab_returns_empty_dict():
    repo = _repo_with_ws(_FakeWakeTimeWorksheet())
    assert repo.get_wake_time_adjustments() == {}


def test_get_wake_time_adjustments_skips_blank_cells():
    ws = _FakeWakeTimeWorksheet(rows=[["2026-07-20", ""]])
    repo = _repo_with_ws(ws)
    assert repo.get_wake_time_adjustments() == {}
