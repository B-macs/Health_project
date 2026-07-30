"""
Tests for services/repository.py's historical Oura backfill —
fetch_oura_history (read-only pull over an arbitrary range) and
backfill_oura_history (batch-append, skipping keys the tab already holds).

Both are I/O orchestration, so the Oura API and the Sheets client are faked
at the module boundary (services.clients.oura.get_collection /
services.clients.sheets.*). The row mappers underneath are already covered by
tests/test_repository_oura.py — what's tested here is the range plumbing, the
raw-payload passthrough, and specifically the never-overwrite-a-synced-day
guarantee that makes re-running a backfill safe.
"""

from __future__ import annotations

import pytest

from services import repository as repo_mod
from services.config import Config
from services.repository import Repository, _sheet_key


def _config(**overrides) -> Config:
    base = dict(
        notion_api_key="ntn_test",
        notion_db_readiness="db-readiness",
        notion_db_training="db-training",
        notion_db_biometrics="db-biometrics",
        notion_db_config="db-config",
        google_sheets_id="sheet-id",
        google_service_account={"type": "service_account"},
        oura_token="token-abc",
    )
    base.update(overrides)
    return Config(**base)


# ─── _sheet_key ──────────────────────────────────────────────────────────────

def test_sheet_key_strips_time_component_added_by_sheets_formatting():
    assert _sheet_key("2023-07-04 00:00:00") == "2023-07-04"


def test_sheet_key_leaves_uuids_and_blanks_alone():
    assert _sheet_key("87d8bf41-4988-435f-a189-e10e719ec5c2") == "87d8bf41-4988-435f-a189-e10e719ec5c2"
    assert _sheet_key(None) == ""


# ─── fetch_oura_history ─────────────────────────────────────────────────────

def test_fetch_oura_history_requires_configuration():
    repo = Repository(_config(oura_token=""))
    with pytest.raises(RuntimeError, match="not configured"):
        repo.fetch_oura_history("2023-07-04", "2023-07-05")


def _fake_collection(payloads: dict[str, list[dict]], calls: list | None = None):
    def get_collection(token, endpoint, start_date, end_date):
        if calls is not None:
            calls.append((endpoint, start_date, end_date))
        return payloads.get(endpoint, [])
    return get_collection


def test_fetch_oura_history_maps_rows_and_passes_the_range_through(monkeypatch):
    calls: list = []
    payloads = {
        "daily_sleep": [
            {"day": "2023-07-05", "score": 71, "contributors": {"total_sleep": 60}},
            {"day": "2023-07-04", "score": 64, "contributors": {"total_sleep": 55}},
        ],
        "daily_activity": [{"day": "2023-07-04", "score": 88, "steps": 9001}],
        "workout": [{"id": "w-1", "day": "2023-07-04", "activity": "walking", "distance": 2000}],
    }
    monkeypatch.setattr(repo_mod.oura, "get_collection", _fake_collection(payloads, calls))

    out = Repository(_config()).fetch_oura_history("2023-07-04", "2023-07-06")

    # Daily rows are merged per date and returned in date order.
    daily = out["rows"]["daily"]
    assert [r["date"] for r in daily] == ["2023-07-04", "2023-07-05"]
    assert daily[0]["sleep_score"] == 64
    assert daily[0]["steps"] == 9001          # merged from a different endpoint
    assert daily[1]["steps"] is None          # no daily_activity that day
    assert out["rows"]["workouts"] == [{
        "workout_id": "w-1", "day": "2023-07-04", "activity": "walking",
        "intensity": "", "calories": None, "distance_km": 2.0,
        "start_datetime": "", "end_datetime": "", "source": "",
    }]
    # Every endpoint got the caller's range verbatim — no today-relative window.
    assert {(s, e) for _ep, s, e in calls} == {("2023-07-04", "2023-07-06")}


def test_fetch_oura_history_returns_raw_payloads_for_archiving(monkeypatch):
    """The Sheet schema deliberately drops embedded time-series; `raw` keeps
    them so a local export doesn't need a second round of API calls."""
    payloads = {"sleep": [{"id": "s-1", "day": "2023-07-05", "heart_rate": {"items": [55, 56]}}]}
    monkeypatch.setattr(repo_mod.oura, "get_collection", _fake_collection(payloads))

    out = Repository(_config()).fetch_oura_history("2023-07-04", "2023-07-06")

    assert out["raw"]["sleep"][0]["heart_rate"] == {"items": [55, 56]}
    assert "heart_rate" not in out["rows"]["sleep_periods"][0]


def test_fetch_oura_history_writes_nothing(monkeypatch):
    monkeypatch.setattr(repo_mod.oura, "get_collection", _fake_collection(
        {"daily_sleep": [{"day": "2023-07-04", "score": 64}]}))

    def explode(*args, **kwargs):
        raise AssertionError("fetch_oura_history must not touch Sheets")

    for name in ("get_or_create_worksheet", "upsert_row_by_key", "append_rows"):
        monkeypatch.setattr(repo_mod.sheets, name, explode)

    Repository(_config()).fetch_oura_history("2023-07-04", "2023-07-06")


def test_fetch_oura_history_covers_every_endpoint_exactly_once(monkeypatch):
    calls: list = []
    monkeypatch.setattr(repo_mod.oura, "get_collection", _fake_collection({}, calls))
    Repository(_config()).fetch_oura_history("2025-01-08", "2025-03-14")

    endpoints = [ep for ep, _s, _e in calls]
    assert len(endpoints) == len(set(endpoints))  # no endpoint fetched twice
    assert set(endpoints) == set(repo_mod._OURA_DAILY_ENDPOINTS) | {
        "workout", "sleep", "session", "rest_mode_period",
    }


# ─── backfill_oura_history ──────────────────────────────────────────────────


class _FakeTab:
    def __init__(self, records=None):
        self.records = records or []
        self.appended: list[list] = []


def _patch_sheets(monkeypatch, tabs: dict[str, _FakeTab]):
    """Routes each tab getter to a named _FakeTab, keyed by worksheet title."""
    monkeypatch.setattr(
        repo_mod.sheets, "get_or_create_worksheet",
        lambda client, sheet_id, title, header: tabs.setdefault(title, _FakeTab()),
    )
    monkeypatch.setattr(repo_mod.sheets, "get_worksheet_records", lambda ws: ws.records)

    def append_rows(ws, rows, chunk_size=500):
        ws.appended.extend(rows)
        return len(rows)

    monkeypatch.setattr(repo_mod.sheets, "append_rows", append_rows)
    monkeypatch.setattr(Repository, "_sc", property(lambda self: object()))


def test_backfill_appends_new_dates_in_header_order(monkeypatch):
    tabs: dict[str, _FakeTab] = {}
    _patch_sheets(monkeypatch, tabs)
    repo = Repository(_config())

    result = repo.backfill_oura_history({
        "daily": [{"date": "2023-07-04", "sleep_score": 64, "steps": 9001}],
    })

    daily = tabs[repo_mod.sheets.OURA_DAILY_WORKSHEET]
    assert len(daily.appended) == 1
    row = daily.appended[0]
    assert len(row) == len(repo_mod._OURA_DAILY_HEADER)
    assert row[repo_mod._OURA_DAILY_HEADER.index("date")] == "2023-07-04"
    assert row[repo_mod._OURA_DAILY_HEADER.index("sleep_score")] == 64
    assert row[repo_mod._OURA_DAILY_HEADER.index("steps")] == 9001
    assert result["daily"] == {"written": 1, "skipped": 0}


def test_backfill_blanks_missing_fields_rather_than_dropping_the_row(monkeypatch):
    """Sparse endpoints (vo2_max, daily_resilience) must not cost a whole date."""
    tabs: dict[str, _FakeTab] = {}
    _patch_sheets(monkeypatch, tabs)
    repo = Repository(_config())

    repo.backfill_oura_history({"daily": [{"date": "2023-07-04", "vo2_max": None}]})

    row = tabs[repo_mod.sheets.OURA_DAILY_WORKSHEET].appended[0]
    assert row[repo_mod._OURA_DAILY_HEADER.index("date")] == "2023-07-04"
    assert row[repo_mod._OURA_DAILY_HEADER.index("vo2_max")] == ""


def test_backfill_never_overwrites_a_date_the_tab_already_has(monkeypatch):
    """The core safety property: a live-synced day survives a backfill that
    covers it, and a re-run of the same range appends nothing."""
    tabs = {repo_mod.sheets.OURA_DAILY_WORKSHEET: _FakeTab(
        records=[{"date": "2026-07-05", "sleep_score": 64}],
    )}
    _patch_sheets(monkeypatch, tabs)
    repo = Repository(_config())

    result = repo.backfill_oura_history({"daily": [
        {"date": "2026-07-05", "sleep_score": 99},   # already synced — skip
        {"date": "2023-07-04", "sleep_score": 71},   # genuinely new — append
    ]})

    daily = tabs[repo_mod.sheets.OURA_DAILY_WORKSHEET]
    assert result["daily"] == {"written": 1, "skipped": 1}
    assert [r[0] for r in daily.appended] == ["2023-07-04"]
    assert daily.records == [{"date": "2026-07-05", "sleep_score": 64}]  # untouched


def test_backfill_dedupes_existing_dates_despite_sheet_time_formatting(monkeypatch):
    tabs = {repo_mod.sheets.OURA_DAILY_WORKSHEET: _FakeTab(
        records=[{"date": "2023-07-04 00:00:00"}],
    )}
    _patch_sheets(monkeypatch, tabs)

    result = Repository(_config()).backfill_oura_history({"daily": [{"date": "2023-07-04"}]})
    assert result["daily"] == {"written": 0, "skipped": 1}


def test_backfill_skips_event_rows_by_their_own_id(monkeypatch):
    tabs = {repo_mod.sheets.OURA_WORKOUTS_WORKSHEET: _FakeTab(
        records=[{"workout_id": "w-1", "day": "2023-07-04"}],
    )}
    _patch_sheets(monkeypatch, tabs)

    result = Repository(_config()).backfill_oura_history({"workouts": [
        {"workout_id": "w-1", "day": "2023-07-04", "activity": "walking"},
        {"workout_id": "w-2", "day": "2023-07-05", "activity": "running"},
    ]})

    assert result["workouts"] == {"written": 1, "skipped": 1}
    assert tabs[repo_mod.sheets.OURA_WORKOUTS_WORKSHEET].appended[0][0] == "w-2"


def test_backfill_reports_zero_for_tabs_with_no_data_without_opening_them(monkeypatch):
    """An empty endpoint (rest_mode_period, sessions in some ranges) shouldn't
    cost a worksheet read at all."""
    tabs: dict[str, _FakeTab] = {}
    _patch_sheets(monkeypatch, tabs)

    result = Repository(_config()).backfill_oura_history({"daily": []})

    assert result == {
        "daily": {"written": 0, "skipped": 0},
        "workouts": {"written": 0, "skipped": 0},
        "sleep_periods": {"written": 0, "skipped": 0},
        "sessions": {"written": 0, "skipped": 0},
        "rest_mode_periods": {"written": 0, "skipped": 0},
    }
    assert tabs == {}  # no tab was opened


# ─── shared endpoint→tab wiring (used by both sync_oura_all and the backfill) ─

def test_oura_tab_specs_cover_every_result_key_sync_oura_all_returns():
    repo = Repository(_config())
    assert [key for key, _ws, _header in repo._oura_tab_specs()] == [
        "daily", "workouts", "sleep_periods", "sessions", "rest_mode_periods",
    ]


def test_oura_event_specs_key_column_is_always_header_zero():
    repo = Repository(_config())
    for _key, _endpoint, _ws_getter, header, _mapper in repo._oura_event_specs():
        assert header[0].endswith("_id")
