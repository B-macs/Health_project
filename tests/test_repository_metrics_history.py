"""
Tests for the Metrics History persistence layer — Repository.
upsert_metrics_history_row / sync_metrics_history / get_metrics_history.

Same rationale as test_repository_biometric_blend_persist.py: Readiness/
Sleep %/Strain are otherwise pure live recomputes (services.dashboard.
compute_daily_metrics_snapshot) — this is what makes "look back at last
month" show a fixed historical value instead of a re-derived one that could
drift (e.g. if the rehab stage changes later, since strain's CLF depends on
the *current* stage).

Fake worksheet mirrors _FakeBlendWorksheet in
test_repository_biometric_blend_persist.py (find/update/append_row/
get_all_records) since upsert_row_by_key needs all four.
"""

from __future__ import annotations

import datetime

import pytest

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


class _FakeMetricsHistoryWorksheet:
    def __init__(self, rows=None):
        self.header = ["date", "readiness_score", "sleep_pct", "strain"]
        self.rows = rows or []
        self.appended = []
        self.updates = []

    def get_all_records(self):
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
    def __init__(self, ws: _FakeMetricsHistoryWorksheet):
        self._ws = ws

    def worksheet(self, name):
        return self._ws


class _FakeSheetsClient:
    def __init__(self, ws: _FakeMetricsHistoryWorksheet):
        self._ws = ws

    def open_by_key(self, sheet_id):
        return _FakeSpreadsheet(self._ws)


def _repo_with_ws(ws: _FakeMetricsHistoryWorksheet) -> Repository:
    repo = Repository(_config())
    repo._sheets_client = _FakeSheetsClient(ws)
    return repo


# ─── _metrics_history_row ───────────────────────────────────────────────────

def test_metrics_history_row_maps_populated_snapshot():
    repo = _repo_with_ws(_FakeMetricsHistoryWorksheet())
    row = repo._metrics_history_row({
        "date": "2026-07-20", "readiness_score": 72.5, "sleep_pct": 88, "strain": 9.4,
    })
    assert row == {"date": "2026-07-20", "readiness_score": 72.5, "sleep_pct": 88, "strain": 9.4}


def test_metrics_history_row_blanks_none_values():
    repo = _repo_with_ws(_FakeMetricsHistoryWorksheet())
    row = repo._metrics_history_row({
        "date": "2026-07-20", "readiness_score": None, "sleep_pct": None, "strain": None,
    })
    assert row["readiness_score"] == ""
    assert row["sleep_pct"] == ""
    assert row["strain"] == ""


# ─── upsert_metrics_history_row ─────────────────────────────────────────────

def test_upsert_metrics_history_row_appends_new_date():
    ws = _FakeMetricsHistoryWorksheet()
    repo = _repo_with_ws(ws)
    repo.upsert_metrics_history_row({
        "date": "2026-07-20", "readiness_score": 72.5, "sleep_pct": 88, "strain": 9.4,
    })
    assert ws.appended == [["2026-07-20", 72.5, 88, 9.4]]


def test_upsert_metrics_history_row_updates_existing_date_in_place():
    ws = _FakeMetricsHistoryWorksheet(rows=[["2026-07-20", 60.0, 70, 5.0]])
    repo = _repo_with_ws(ws)
    repo.upsert_metrics_history_row({
        "date": "2026-07-20", "readiness_score": 72.5, "sleep_pct": 88, "strain": 9.4,
    })
    assert len(ws.rows) == 1  # updated in place, not appended
    assert ws.rows[0] == ["2026-07-20", 72.5, 88, 9.4]


# ─── get_metrics_history ─────────────────────────────────────────────────────

def test_get_metrics_history_sorted_ascending():
    ws = _FakeMetricsHistoryWorksheet(rows=[
        ["2026-07-20", 72.5, 88, 9.4],
        ["2026-07-19", 65.0, 80, 7.0],
    ])
    repo = _repo_with_ws(ws)
    history = repo.get_metrics_history()
    assert [r["date"] for r in history] == ["2026-07-19", "2026-07-20"]
    assert history[1]["readiness_score"] == 72.5


def test_get_metrics_history_filters_by_start_and_end():
    ws = _FakeMetricsHistoryWorksheet(rows=[
        ["2026-06-01", 70, 80, 8.0],
        ["2026-07-01", 70, 80, 8.0],
        ["2026-08-01", 70, 80, 8.0],
    ])
    repo = _repo_with_ws(ws)
    history = repo.get_metrics_history(start="2026-06-15", end="2026-07-15")
    assert [r["date"] for r in history] == ["2026-07-01"]


def test_get_metrics_history_empty_tab_returns_empty_list():
    repo = _repo_with_ws(_FakeMetricsHistoryWorksheet())
    assert repo.get_metrics_history() == []


def test_get_metrics_history_treats_blank_cells_as_none():
    ws = _FakeMetricsHistoryWorksheet(rows=[["2026-07-20", "", "", ""]])
    repo = _repo_with_ws(ws)
    r = repo.get_metrics_history()[0]
    assert (r["readiness_score"], r["sleep_pct"], r["strain"]) == (None, None, None)


# ─── sync_metrics_history ────────────────────────────────────────────────────

def test_sync_metrics_history_writes_one_row_per_day(monkeypatch):
    ws = _FakeMetricsHistoryWorksheet()
    repo = _repo_with_ws(ws)
    monkeypatch.setattr(repo, "get_biometric_rolling", lambda days=None, today=None: [])
    monkeypatch.setattr(repo, "get_daily_session_au", lambda days=None, today=None: [])
    monkeypatch.setattr(repo, "get_current_stage", lambda: 1)

    n = repo.sync_metrics_history(days=3, today=datetime.date(2026, 7, 20))
    assert n == 3
    assert len(ws.appended) == 3
    assert {row[0] for row in ws.appended} == {"2026-07-18", "2026-07-19", "2026-07-20"}


def test_sync_metrics_history_persists_real_snapshot_values(monkeypatch):
    ws = _FakeMetricsHistoryWorksheet()
    repo = _repo_with_ws(ws)
    au_rows = [{"date": "2026-07-20", "total_au": 300.0}]
    monkeypatch.setattr(repo, "get_biometric_rolling", lambda days=None, today=None: [])
    monkeypatch.setattr(repo, "get_daily_session_au", lambda days=None, today=None: au_rows)
    monkeypatch.setattr(repo, "get_current_stage", lambda: 2)

    repo.sync_metrics_history(days=1, today=datetime.date(2026, 7, 20))
    row = next(r for r in ws.appended if r[0] == "2026-07-20")
    assert row[3] is not None and row[3] > 0  # strain computed from the AU logged that day


def test_sync_metrics_history_uses_today_when_not_given(monkeypatch):
    ws = _FakeMetricsHistoryWorksheet()
    repo = _repo_with_ws(ws)
    monkeypatch.setattr(repo, "get_biometric_rolling", lambda days=None, today=None: [])
    monkeypatch.setattr(repo, "get_daily_session_au", lambda days=None, today=None: [])
    monkeypatch.setattr(repo, "get_current_stage", lambda: 1)

    n = repo.sync_metrics_history(days=1)
    assert n == 1
    assert ws.appended[0][0] == datetime.date.today().isoformat()
