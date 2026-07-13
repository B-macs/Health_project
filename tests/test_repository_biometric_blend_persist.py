"""
Tests for the Biometric Blend persistence layer — Repository.
upsert_biometric_blend_row / sync_biometric_blend / get_biometric_blend_history.

Unlike get_biometric_rolling() (a live recompute, tested in
test_repository_biometric_blend.py), this is what makes "look back at last
month" show a fixed historical value: each day's blended result is written
once to its own sheet tab rather than only ever being re-derived live.

Fake worksheet mirrors _FakeWeeklyRollupWorksheet in test_repository.py
(find/update/append_row/get_all_records) since upsert_row_by_key needs all four.
"""

from __future__ import annotations

import datetime
import json

from services import models
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


class _FakeBlendWorksheet:
    def __init__(self, rows=None):
        self.header = [
            "date", "hrv_ms", "resting_heart_rate", "sleep_duration_hours", "steps", "sources_missing",
        ]
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
        # naive but sufficient for these tests: values is [[row...]]
        cell_row = int("".join(ch for ch in range_name.split(":")[0] if ch.isdigit()))
        self.rows[cell_row - 2] = list(values[0])

    def append_row(self, values):
        self.appended.append(values)
        self.rows.append(list(values))


class _FakeSpreadsheet:
    def __init__(self, ws: _FakeBlendWorksheet):
        self._ws = ws

    def worksheet(self, name):
        return self._ws


class _FakeSheetsClient:
    def __init__(self, ws: _FakeBlendWorksheet):
        self._ws = ws

    def open_by_key(self, sheet_id):
        return _FakeSpreadsheet(self._ws)


def _repo_with_blend_ws(ws: _FakeBlendWorksheet) -> Repository:
    repo = Repository(_config())
    repo._sheets_client = _FakeSheetsClient(ws)
    return repo


# ─── _biometric_blend_row ────────────────────────────────────────────────────

def test_biometric_blend_row_maps_populated_record():
    repo = _repo_with_blend_ws(_FakeBlendWorksheet())
    record = models.BiometricRecord(
        date="2026-07-13", hrv_ms=38.5, resting_heart_rate=54.0,
        sleep_duration_hours=7.2, steps=8000,
        sources_missing=("hrv_ms:garmin",),
    )
    row = repo._biometric_blend_row(record)
    assert row == {
        "date": "2026-07-13", "hrv_ms": 38.5, "resting_heart_rate": 54.0,
        "sleep_duration_hours": 7.2, "steps": 8000,
        "sources_missing": json.dumps(["hrv_ms:garmin"]),
    }


def test_biometric_blend_row_blanks_missing_values():
    repo = _repo_with_blend_ws(_FakeBlendWorksheet())
    record = models.BiometricRecord(date="2026-07-13")
    row = repo._biometric_blend_row(record)
    assert row["hrv_ms"] == ""
    assert row["resting_heart_rate"] == ""
    assert row["sleep_duration_hours"] == ""
    assert row["steps"] == ""
    assert row["sources_missing"] == ""


# ─── upsert_biometric_blend_row ──────────────────────────────────────────────

def test_upsert_biometric_blend_row_appends_new_date():
    ws = _FakeBlendWorksheet()
    repo = _repo_with_blend_ws(ws)
    record = models.BiometricRecord(date="2026-07-13", hrv_ms=38.5, steps=8000)
    repo.upsert_biometric_blend_row(record)
    assert ws.appended == [["2026-07-13", 38.5, "", "", 8000, ""]]


def test_upsert_biometric_blend_row_updates_existing_date_in_place():
    ws = _FakeBlendWorksheet(rows=[["2026-07-13", 30.0, "", "", 5000, ""]])
    repo = _repo_with_blend_ws(ws)
    record = models.BiometricRecord(date="2026-07-13", hrv_ms=38.5, steps=8000)
    repo.upsert_biometric_blend_row(record)
    assert len(ws.rows) == 1  # updated in place, not appended
    assert ws.rows[0][1] == 38.5
    assert ws.rows[0][4] == 8000


# ─── get_biometric_blend_history ─────────────────────────────────────────────

def test_get_biometric_blend_history_round_trips_sources_missing():
    ws = _FakeBlendWorksheet(rows=[
        ["2026-07-12", 40, 50, 7.5, 8000, json.dumps(["steps:oura"])],
        ["2026-07-13", 38, 52, 7.0, 9000, ""],
    ])
    repo = _repo_with_blend_ws(ws)
    records = repo.get_biometric_blend_history()
    assert [r.date for r in records] == ["2026-07-12", "2026-07-13"]  # sorted ascending
    assert records[0].sources_missing == ("steps:oura",)
    assert records[1].sources_missing == ()
    assert records[1].hrv_ms == 38


def test_get_biometric_blend_history_filters_by_start_and_end():
    ws = _FakeBlendWorksheet(rows=[
        ["2026-06-01", 40, 50, 7.5, 8000, ""],
        ["2026-07-01", 40, 50, 7.5, 8000, ""],
        ["2026-08-01", 40, 50, 7.5, 8000, ""],
    ])
    repo = _repo_with_blend_ws(ws)
    records = repo.get_biometric_blend_history(start="2026-06-15", end="2026-07-15")
    assert [r.date for r in records] == ["2026-07-01"]


def test_get_biometric_blend_history_empty_tab_returns_empty_list():
    repo = _repo_with_blend_ws(_FakeBlendWorksheet())
    assert repo.get_biometric_blend_history() == []


def test_get_biometric_blend_history_treats_blank_cells_as_none():
    ws = _FakeBlendWorksheet(rows=[["2026-07-13", "", "", "", "", ""]])
    repo = _repo_with_blend_ws(ws)
    records = repo.get_biometric_blend_history()
    r = records[0]
    assert (r.hrv_ms, r.resting_heart_rate, r.sleep_duration_hours, r.steps) == (None, None, None, None)


# ─── sync_biometric_blend ────────────────────────────────────────────────────

def test_sync_biometric_blend_persists_every_computed_day(monkeypatch):
    ws = _FakeBlendWorksheet()
    repo = _repo_with_blend_ws(ws)
    fake_records = [
        models.BiometricRecord(date="2026-07-12", hrv_ms=40, steps=8000),
        models.BiometricRecord(date="2026-07-13", hrv_ms=38, steps=9000),
    ]
    monkeypatch.setattr(repo, "get_biometric_rolling", lambda days=7, today=None: fake_records)
    n = repo.sync_biometric_blend(days=7, today=datetime.date(2026, 7, 13))
    assert n == 2
    assert len(ws.appended) == 2
    assert [row[0] for row in ws.appended] == ["2026-07-12", "2026-07-13"]


def test_sync_biometric_blend_returns_zero_for_no_data(monkeypatch):
    repo = _repo_with_blend_ws(_FakeBlendWorksheet())
    monkeypatch.setattr(repo, "get_biometric_rolling", lambda days=7, today=None: [])
    assert repo.sync_biometric_blend(today=datetime.date(2026, 7, 13)) == 0
