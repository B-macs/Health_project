"""
Tests for offline mode — Repository serving Google Sheets READS from a
locally-built datastore (services/clients/datastore_reader.py) instead of
the Sheets API, switched on by Config.datastore_path.

The property that matters is INDISTINGUISHABILITY: a read taken offline
must return what the same read returns live, or every measurement taken
during offline iteration is measuring the wrong thing. Most of what follows
pins that down — blank cells, digit-coded strings, gspread's 'TRUE'/'FALSE'
— rather than merely checking that some rows come back.

The second property is that offline mode is loudly read-only. A write that
silently no-ops would leave the caller believing a sync had persisted, which
is worse than a crash; a write that reached live Sheets while reads came
from a snapshot would be worse still.

These build a real on-disk SQLite datastore through services.datastore's own
rebuild(), not a hand-written schema, so a column added to the schema
without a matching table here fails these tests rather than silently
round-tripping as NULL.
"""

from __future__ import annotations

import sqlite3

import pytest

from services import datastore
from services.clients import sheets
from services.clients.datastore_reader import DatastoreReadOnlyError, OfflineWorksheet
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


class _StubRepo:
    """Just enough of Repository for datastore.rebuild(). Every getter it
    calls must exist here, so adding a table to rebuild() without adding it
    here fails loudly instead of building a short datastore."""

    def __init__(self, **tables):
        self._t = tables

    def _rows(self, name):
        return self._t.get(name, [])

    def get_all_readiness_checkins_raw(self): return self._rows("readiness")
    def get_all_training_exercises_raw(self): return self._rows("training")
    def get_all_garmin_daily_rows(self): return self._rows("garmin_daily")
    def get_all_garmin_activities_rows(self): return self._rows("garmin_activities")
    def get_all_garmin_sleep_stages_rows(self): return self._rows("garmin_sleep_stages")
    def get_all_sleep_fusion_rows(self): return self._rows("sleep_fusion")
    def get_all_session_hr_rows(self): return self._rows("session_hr")
    def get_all_oura_daily_rows(self): return self._rows("oura_daily")
    def get_all_oura_workouts_rows(self): return self._rows("oura_workouts")
    def get_all_oura_sleep_periods_rows(self): return self._rows("oura_sleep_periods")
    def get_all_oura_sessions_rows(self): return self._rows("oura_sessions")
    def get_all_oura_rest_mode_rows(self): return self._rows("oura_rest_mode")
    def get_all_config_rows(self): return self._rows("config")
    def get_biometric_blend_history(self): return []
    def get_metrics_history(self): return self._rows("metrics_history")
    def get_wake_time_adjustments(self): return {}
    def get_weekly_rollup_history(self): return []
    def get_all_sheet1_biometric_records(self): return []


def _build_datastore(tmp_path, **tables) -> str:
    path = tmp_path / "datastore.db"
    conn = sqlite3.connect(path)
    datastore.rebuild(_StubRepo(**tables), conn)
    conn.close()
    return str(path)


def _offline_repo(tmp_path, **tables) -> Repository:
    return Repository(_config(datastore_path=_build_datastore(tmp_path, **tables)))


# ─── The switch itself ────────────────────────────────────────────────────

def test_repository_is_not_offline_by_default():
    """Blank datastore_path is what the deployed app runs with. Offline must
    never be something you get by accident."""
    assert Repository(_config()).offline is False


def test_offline_repository_never_builds_a_sheets_client(tmp_path):
    """The whole point: no Google API call, including the service-account
    auth handshake. _sheets_client staying None is the observable proof —
    this Config's service account is fake and would fail if used."""
    repo = _offline_repo(tmp_path, garmin_daily=[{"date": "2026-07-31", "steps": 8000}])
    rows = repo.get_all_garmin_daily_rows()
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-07-31" and rows[0]["steps"] == 8000
    assert repo._sheets_client is None


def test_a_row_carries_every_column_even_those_the_source_omitted(tmp_path):
    """gspread returns one key per HEADER cell, not per populated cell, so a
    live row always carries the full column set with "" for the empty ones.
    Offline matches that: a caller doing row["hrv_ms"] must not start
    KeyError-ing just because it is reading a snapshot."""
    repo = _offline_repo(tmp_path, garmin_daily=[{"date": "2026-07-31", "steps": 8000}])
    row = repo.get_all_garmin_daily_rows()[0]
    assert row["hrv_ms"] == ""
    assert row["resting_hr"] == ""


# ─── The two tables this work existed to add ──────────────────────────────

def test_sleep_fusion_reads_offline(tmp_path):
    """Sleep Fusion and Garmin Sleep Stages were absent from the first
    datastore build, which is exactly why iterating on the Sleep drill-down
    kept spending live Sheets quota."""
    row = {
        "date": "2026-07-28", "source": "fused", "rules_version": 2,
        "master_hypnogram": "4421", "reason_codes": "zzmG",
        "phantom_wake_minutes": 73.15, "movement_cutpoints": "1.45,2.43,5.63",
    }
    repo = _offline_repo(tmp_path, sleep_fusion=[row])
    got = repo.get_sleep_fusion_history()
    assert len(got) == 1
    assert got[0]["date"] == "2026-07-28"
    assert got[0]["source"] == "fused"
    assert got[0]["phantom_wake_minutes"] == 73.15


def test_garmin_sleep_stages_read_offline_without_decoding(tmp_path):
    row = {
        "date": "2026-07-28", "totals_match": "TRUE", "utc_offset_minutes": 120,
        "sleep_levels_json": '[{"activityLevel": 2.0}]',
        "movement_levels": "1.13,0.75,4.20", "movement_contiguous": "TRUE",
    }
    repo = _offline_repo(tmp_path, garmin_sleep_stages=[row])
    assert repo.get_garmin_sleep_stages_dates() == {"2026-07-28"}
    stages = repo.get_garmin_sleep_stages()
    assert stages["2026-07-28"]["segments"] == [{"activityLevel": 2.0}]


# ─── Indistinguishability from a live read ────────────────────────────────

def test_digit_coded_strings_survive_the_round_trip_as_strings(tmp_path):
    """A hypnogram read back as an int is this project's known
    unrecoverable-corruption failure — it is why _OURA_NUMERICISE_IGNORE
    exists. The datastore must not reintroduce it by another route."""
    hypnogram = "4442211133344422111"
    repo = _offline_repo(tmp_path, oura_sleep_periods=[
        {"sleep_id": "s1", "day": "2026-07-28", "sleep_phase_30_sec": hypnogram},
    ])
    got = repo.get_all_oura_sleep_periods_rows()[0]
    assert got["sleep_phase_30_sec"] == hypnogram
    assert isinstance(got["sleep_phase_30_sec"], str)


def test_a_blank_cell_reads_back_as_empty_string_not_none(tmp_path):
    """services/datastore.py normalizes "" to NULL on the way in. If the
    read did not reverse it, every `row.get(x) == ""` in the codebase would
    take a different branch offline than it does live — a difference that
    would show up as wrong numbers, not as an error."""
    repo = _offline_repo(tmp_path, garmin_daily=[{"date": "2026-07-31", "steps": ""}])
    got = repo.get_all_garmin_daily_rows()[0]
    assert got["steps"] == ""
    assert got["steps"] is not None


def test_gspread_boolean_strings_are_preserved_verbatim(tmp_path):
    """gspread hands back 'TRUE'/'FALSE' strings, and repository.py tests
    them as strings (`str(...).lower() not in ("true", "1")`). SQLite's type
    affinity leaves them as text even in a declared-INTEGER column; this
    pins that, because a silent coercion to 0/1 would flip those checks."""
    repo = _offline_repo(tmp_path, garmin_sleep_stages=[
        {"date": "2026-07-28", "totals_match": "TRUE", "movement_contiguous": "FALSE"},
    ])
    got = repo.get_all_garmin_sleep_stages_rows()[0]
    assert got["totals_match"] == "TRUE"
    assert got["movement_contiguous"] == "FALSE"


def test_numeric_columns_keep_their_type(tmp_path):
    repo = _offline_repo(tmp_path, garmin_daily=[
        {"date": "2026-07-31", "steps": 8412, "resting_hr": 54, "sleep_hours": 7.58},
    ])
    got = repo.get_all_garmin_daily_rows()[0]
    assert got["steps"] == 8412 and isinstance(got["steps"], int)
    assert got["sleep_hours"] == 7.58 and isinstance(got["sleep_hours"], float)


# ─── Read-only enforcement ────────────────────────────────────────────────

def test_every_write_primitive_raises_rather_than_no_opping(tmp_path):
    """A no-op write is the dangerous failure: the caller believes a sync
    persisted. Checks the gspread methods repository.py actually reaches for
    (via sheets.upsert_row_by_key / rewrite_worksheet / append_rows)."""
    ws = OfflineWorksheet(sqlite3.connect(":memory:"), "Sleep Fusion", "sleep_fusion")
    for method in ("find", "update", "append_row", "append_rows", "resize", "clear"):
        with pytest.raises(DatastoreReadOnlyError) as exc:
            getattr(ws, method)
        assert method in str(exc.value)


def test_saving_a_fusion_row_offline_raises(tmp_path):
    """End-to-end through Repository, not just the stub: the write must fail
    at the call the app actually makes."""
    repo = _offline_repo(tmp_path)
    with pytest.raises(DatastoreReadOnlyError):
        repo.save_sleep_fusion({"date": "2026-07-28", "source": "fused"})


def test_the_datastore_file_is_opened_read_only(tmp_path):
    """Belt and braces beneath OfflineWorksheet: even a code path that got
    hold of the raw connection cannot write through it."""
    repo = _offline_repo(tmp_path)
    with pytest.raises(sqlite3.OperationalError):
        repo._ds.execute("DELETE FROM sleep_fusion")


def test_raw_sheet1_passthrough_refuses_rather_than_returning_mapped_columns(tmp_path):
    """The datastore holds Sheet1 mapped, not under its raw Apple Health
    export headers. Returning the mapped columns from a method named "raw"
    would be a quiet lie about the shape."""
    repo = _offline_repo(tmp_path)
    with pytest.raises(DatastoreReadOnlyError):
        repo.get_raw_sheet_rows()


# ─── Wiring completeness ──────────────────────────────────────────────────

def test_every_sheets_tab_maps_to_a_real_datastore_table(tmp_path):
    """The tab->table map and the schema are edited in different files, so
    they can drift. A tab pointing at a table that does not exist would read
    as an empty tab forever — silently, and only in offline mode."""
    from services.repository import _DATASTORE_TABLE_BY_TAB

    conn = sqlite3.connect(_build_datastore(tmp_path))
    actual = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    missing = {tab: table for tab, table in _DATASTORE_TABLE_BY_TAB.items()
               if table not in actual}
    assert not missing, f"tabs mapped to non-existent datastore tables: {missing}"


def test_every_worksheet_getter_goes_through_the_offline_seam(tmp_path):
    """Repository._ws is what makes offline mode one seam rather than
    fourteen. A getter that opens a tab directly would bypass it and reach
    live Sheets from an offline Repository — the one failure this design has
    to make impossible. Verified by calling each getter on an offline
    Repository whose Sheets client would raise if touched."""
    repo = _offline_repo(tmp_path)
    repo._sheets_client = object()  # any attribute use raises AttributeError

    getters = [name for name in dir(Repository)
               if name.startswith("_") and name.endswith("_ws") and name != "_ws"
               and callable(getattr(Repository, name))]
    assert len(getters) == 14, f"expected 14 worksheet getters, found {getters}"
    for name in getters:
        ws = getattr(repo, name)()
        assert isinstance(ws, OfflineWorksheet), f"{name} bypassed the offline seam"
