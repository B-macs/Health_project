"""
Tests for services/datastore.py — the consolidated-database rebuild
orchestration. Uses a minimal duck-typed stub Repository (same convention
as tests/test_metrics.py's _FakeRepository) exposing exactly the methods
rebuild() calls, so these tests exercise datastore.py's own reshape/insert
logic without touching real Notion/Sheets or the Repository field-mapping
code (that's covered separately in tests/test_repository*.py for each new
get_all_* getter).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import pytest

from services import datastore
from services.models import BiometricRecord, WeekScore


class _StubRepository:
    def __init__(
        self, readiness=None, training_exercises=None, garmin_daily=None,
        garmin_activities=None, session_hr=None, oura_daily=None,
        oura_workouts=None, oura_sleep_periods=None, oura_sessions=None,
        oura_rest_mode=None, biometric_blend=None, metrics_history=None,
        wake_time_adjustments=None, weekly_rollup=None, sheet1=None,
        config_rows=None, garmin_sleep_stages=None, sleep_fusion=None,
        fail_on=None,
    ):
        self._garmin_sleep_stages = garmin_sleep_stages or []
        self._sleep_fusion = sleep_fusion or []
        self._readiness = readiness or []
        self._training_exercises = training_exercises or []
        self._garmin_daily = garmin_daily or []
        self._garmin_activities = garmin_activities or []
        self._session_hr = session_hr or []
        self._oura_daily = oura_daily or []
        self._oura_workouts = oura_workouts or []
        self._oura_sleep_periods = oura_sleep_periods or []
        self._oura_sessions = oura_sessions or []
        self._oura_rest_mode = oura_rest_mode or []
        self._biometric_blend = biometric_blend or []
        self._metrics_history = metrics_history or []
        self._wake_time_adjustments = wake_time_adjustments or {}
        self._weekly_rollup = weekly_rollup or []
        self._sheet1 = sheet1 or []
        self._config_rows = config_rows or []
        self._fail_on = fail_on
        self.readiness_call_count = 0

    def _maybe_fail(self, name):
        if self._fail_on == name:
            raise RuntimeError(f"simulated failure in {name}")

    def get_all_readiness_checkins_raw(self):
        self.readiness_call_count += 1
        self._maybe_fail("get_all_readiness_checkins_raw")
        return self._readiness

    def get_all_training_exercises_raw(self):
        self._maybe_fail("get_all_training_exercises_raw")
        return self._training_exercises

    def get_all_garmin_daily_rows(self):
        self._maybe_fail("get_all_garmin_daily_rows")
        return self._garmin_daily

    def get_all_garmin_activities_rows(self):
        self._maybe_fail("get_all_garmin_activities_rows")
        return self._garmin_activities

    def get_all_garmin_sleep_stages_rows(self):
        self._maybe_fail("get_all_garmin_sleep_stages_rows")
        return self._garmin_sleep_stages

    def get_all_sleep_fusion_rows(self):
        self._maybe_fail("get_all_sleep_fusion_rows")
        return self._sleep_fusion

    def get_all_session_hr_rows(self):
        self._maybe_fail("get_all_session_hr_rows")
        return self._session_hr

    def get_all_oura_daily_rows(self):
        self._maybe_fail("get_all_oura_daily_rows")
        return self._oura_daily

    def get_all_oura_workouts_rows(self):
        self._maybe_fail("get_all_oura_workouts_rows")
        return self._oura_workouts

    def get_all_oura_sleep_periods_rows(self):
        self._maybe_fail("get_all_oura_sleep_periods_rows")
        return self._oura_sleep_periods

    def get_all_oura_sessions_rows(self):
        self._maybe_fail("get_all_oura_sessions_rows")
        return self._oura_sessions

    def get_all_oura_rest_mode_rows(self):
        self._maybe_fail("get_all_oura_rest_mode_rows")
        return self._oura_rest_mode

    def get_biometric_blend_history(self):
        self._maybe_fail("get_biometric_blend_history")
        return self._biometric_blend

    def get_metrics_history(self):
        self._maybe_fail("get_metrics_history")
        return self._metrics_history

    def get_wake_time_adjustments(self):
        self._maybe_fail("get_wake_time_adjustments")
        return self._wake_time_adjustments

    def get_weekly_rollup_history(self):
        self._maybe_fail("get_weekly_rollup_history")
        return self._weekly_rollup

    def get_all_sheet1_biometric_records(self):
        self._maybe_fail("get_all_sheet1_biometric_records")
        return self._sheet1

    def get_all_config_rows(self):
        self._maybe_fail("get_all_config_rows")
        return self._config_rows


_ALL_TABLES = [
    "readiness_checkins", "training_sessions", "training_exercises", "training_sets",
    "garmin_daily", "garmin_activities", "garmin_sleep_stages", "sleep_fusion",
    "session_hr", "oura_daily", "oura_workouts",
    "oura_sleep_periods", "oura_sessions", "oura_rest_mode", "biometric_blend",
    "metrics_history", "wake_time_adjustments", "weekly_rollup",
    "sheet1_legacy_biometrics", "config", "datastore_meta",
]


def _table_names(conn) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    # sqlite_sequence is SQLite's own bookkeeping table, auto-created by the
    # one AUTOINCREMENT column (training_sets.id) -- not one of ours.
    return {r[0] for r in rows} - {"sqlite_sequence"}


def _count(conn, table) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ─── Schema / basic rebuild ──────────────────────────────────────────────

def test_rebuild_creates_every_table_on_a_fresh_connection():
    conn = sqlite3.connect(":memory:")
    datastore.rebuild(_StubRepository(), conn)
    assert _table_names(conn) == set(_ALL_TABLES)


def test_rebuild_returns_row_counts_matching_input_data():
    stub = _StubRepository(
        readiness=[{"date": "2026-07-30"}, {"date": "2026-07-31"}],
        garmin_daily=[{"date": "2026-07-31", "steps": 8000}],
    )
    conn = sqlite3.connect(":memory:")
    counts = datastore.rebuild(stub, conn)
    assert counts["readiness_checkins"] == 2
    assert counts["garmin_daily"] == 1
    assert counts["oura_daily"] == 0


def test_rebuild_reads_readiness_unwindowed_no_args():
    stub = _StubRepository()
    conn = sqlite3.connect(":memory:")
    datastore.rebuild(stub, conn)
    assert stub.readiness_call_count == 1


def test_rebuild_writes_datastore_meta_built_at_and_row_counts():
    conn = sqlite3.connect(":memory:")
    now = datetime(2026, 7, 31, 9, 0, 0)
    counts = datastore.rebuild(_StubRepository(garmin_daily=[{"date": "2026-07-31"}]), conn, now=now)
    meta = dict(conn.execute("SELECT key, value FROM datastore_meta").fetchall())
    assert meta["built_at"] == now.isoformat()
    assert json.loads(meta["row_counts_json"]) == counts


# ─── Config (Notion Config DB) ────────────────────────────────────────────

def test_rebuild_populates_config_table_as_a_faithful_key_value_copy():
    rows = [
        {"key": "current_stage", "value": "1", "updated": "2026-07-01"},
        {"key": "phases", "value": '[{"phase_number": 1}]', "updated": "2026-07-01"},
    ]
    conn = sqlite3.connect(":memory:")
    counts = datastore.rebuild(_StubRepository(config_rows=rows), conn)
    assert counts["config"] == 2
    result = dict(conn.execute("SELECT key, value FROM config").fetchall())
    assert result["current_stage"] == "1"
    assert result["phases"] == '[{"phase_number": 1}]'


# ─── Training normalization ──────────────────────────────────────────────

def _exercise(**overrides) -> dict:
    base = {
        "exercise_id": "ex-1", "session_id": "2026-07-31-abcd1234", "session_date": "2026-07-31",
        "movement_name": "Glute Bridge", "movement_type": "reps", "planned_sets": 3,
        "planned_reps": 12, "exercise_rpe": 6, "actual_sets": 3, "total_volume_kg": 0.0,
        "session_duration_minutes": 40, "session_rpe": 6, "session_au": 240.0,
        "notes": "", "note_summary": "", "sentiment_score": None, "flagged_body_parts": "[]",
        "warning_level": None, "garmin_avg_hr": None, "garmin_max_hr": None,
        "garmin_distance_km": None, "garmin_calories": None, "sets": [],
    }
    base.update(overrides)
    return base


def test_rebuild_groups_training_exercises_by_session_id_not_by_date():
    same_day_different_sessions = [
        _exercise(exercise_id="ex-1", session_id="2026-07-31-aaaa1111"),
        _exercise(exercise_id="ex-2", session_id="2026-07-31-bbbb2222"),
    ]
    conn = sqlite3.connect(":memory:")
    counts = datastore.rebuild(_StubRepository(training_exercises=same_day_different_sessions), conn)
    assert counts["training_sessions"] == 2
    assert counts["training_exercises"] == 2


def test_rebuild_handles_blank_session_id_with_synthesized_key():
    exercises = [_exercise(exercise_id="ex-1", session_id="")]
    conn = sqlite3.connect(":memory:")
    datastore.rebuild(_StubRepository(training_exercises=exercises), conn)
    rows = conn.execute("SELECT session_id FROM training_sessions").fetchall()
    assert rows == [("2026-07-31:no-session-id",)]


def test_rebuild_training_sets_round_trips_ts_present_and_absent():
    real_set = {"set_num": 1, "reps": 10, "weight": 20.0, "rest": 60, "tut": 0,
                "velocity": "controlled", "ts": "2026-07-31T08:00:00"}
    synthesized_set = {"set_num": 1, "reps": 1, "weight": 0.0, "rest": 0,
                        "tut": 60, "velocity": "isometric"}
    exercises = [
        _exercise(exercise_id="ex-real", sets=[real_set]),
        _exercise(exercise_id="ex-synth", session_id="2026-07-31-zzzz9999", sets=[synthesized_set]),
    ]
    conn = sqlite3.connect(":memory:")
    datastore.rebuild(_StubRepository(training_exercises=exercises), conn)
    rows = {r[0]: r[1] for r in conn.execute("SELECT exercise_id, ts FROM training_sets").fetchall()}
    assert rows["ex-real"] == "2026-07-31T08:00:00"
    assert rows["ex-synth"] is None


def test_rebuild_training_sets_band_tier_optional():
    with_band = _exercise(exercise_id="ex-band", sets=[{"set_num": 1, "reps": 10, "weight": 0.0,
                                                          "rest": 60, "tut": 0, "velocity": "controlled",
                                                          "band_tier": "medium"}])
    without_band = _exercise(exercise_id="ex-noband", session_id="2026-07-31-yyyy8888",
                              sets=[{"set_num": 1, "reps": 10, "weight": 20.0, "rest": 60,
                                     "tut": 0, "velocity": "controlled"}])
    conn = sqlite3.connect(":memory:")
    datastore.rebuild(_StubRepository(training_exercises=[with_band, without_band]), conn)
    rows = {r[0]: r[1] for r in conn.execute("SELECT exercise_id, band_tier FROM training_sets").fetchall()}
    assert rows["ex-band"] == "medium"
    assert rows["ex-noband"] is None


# ─── Readiness duplicate / blank-cell / AI fields handling ───────────────

def test_rebuild_readiness_duplicate_dates_last_one_wins():
    rows = [
        {"date": "2026-07-31", "tightness_score": 3},
        {"date": "2026-07-31", "tightness_score": 6},
    ]
    conn = sqlite3.connect(":memory:")
    datastore.rebuild(_StubRepository(readiness=rows), conn)
    result = conn.execute("SELECT date, tightness_score FROM readiness_checkins").fetchall()
    assert result == [("2026-07-31", 6.0)]


def test_rebuild_readiness_carries_ai_parsed_fields():
    rows = [{
        "date": "2026-07-31", "parsed": 1, "parsed_severity": 4.5,
        "parsed_areas": '["lower_back"]', "parsed_sensations": '["tight"]',
        "warning_level": "monitor",
    }]
    conn = sqlite3.connect(":memory:")
    datastore.rebuild(_StubRepository(readiness=rows), conn)
    row = conn.execute(
        "SELECT parsed, parsed_severity, parsed_areas, warning_level FROM readiness_checkins"
    ).fetchone()
    assert row == (1, 4.5, '["lower_back"]', "monitor")


def test_insert_rows_normalizes_blank_sheet_cells_to_none():
    conn = sqlite3.connect(":memory:")
    datastore.rebuild(_StubRepository(garmin_daily=[{"date": "2026-07-31", "steps": ""}]), conn)
    row = conn.execute("SELECT steps FROM garmin_daily").fetchone()
    assert row[0] is None


# ─── Biometric blend / weekly rollup / Sheet1 dataclass conversion ───────

def test_rebuild_converts_biometric_record_and_json_encodes_sources_missing():
    record = BiometricRecord(
        date="2026-07-31", hrv_ms=45.0, resting_heart_rate=52.0,
        sleep_duration_hours=7.5, steps=8000, sources_missing=("hrv_ms:garmin",),
    )
    conn = sqlite3.connect(":memory:")
    datastore.rebuild(_StubRepository(biometric_blend=[record]), conn)
    row = conn.execute("SELECT date, hrv_ms, sources_missing FROM biometric_blend").fetchone()
    assert row[0] == "2026-07-31"
    assert row[1] == 45.0
    assert json.loads(row[2]) == ["hrv_ms:garmin"]


def test_rebuild_converts_weekscore_phase_number_to_phase_column():
    score = WeekScore(week_start="2026-07-06", week_end="2026-07-12", phase_number=1,
                       scheduled=4, completed=3, status="ended", computed_at="2026-07-13T00:00:00")
    conn = sqlite3.connect(":memory:")
    datastore.rebuild(_StubRepository(weekly_rollup=[score]), conn)
    row = conn.execute("SELECT week_start, phase, scheduled, completed FROM weekly_rollup").fetchone()
    assert row == ("2026-07-06", 1, 4, 3)


def test_rebuild_sheet1_legacy_drops_sources_missing_field():
    record = BiometricRecord(date="2023-01-01", hrv_ms=40.0, resting_heart_rate=55.0,
                              sleep_duration_hours=7.0, steps=5000)
    conn = sqlite3.connect(":memory:")
    datastore.rebuild(_StubRepository(sheet1=[record]), conn)
    row = conn.execute("SELECT date, hrv_ms, steps FROM sheet1_legacy_biometrics").fetchone()
    assert row == ("2023-01-01", 40.0, 5000)


# ─── Idempotency / atomicity ─────────────────────────────────────────────

def test_rebuild_is_idempotent_running_twice_does_not_duplicate_rows():
    stub = _StubRepository(
        readiness=[{"date": "2026-07-31"}],
        garmin_daily=[{"date": "2026-07-31", "steps": 8000}],
        training_exercises=[_exercise()],
    )
    conn = sqlite3.connect(":memory:")
    datastore.rebuild(stub, conn)
    first_counts = {t: _count(conn, t) for t in _ALL_TABLES if t != "datastore_meta"}
    datastore.rebuild(stub, conn)
    second_counts = {t: _count(conn, t) for t in _ALL_TABLES if t != "datastore_meta"}
    assert first_counts == second_counts
    assert first_counts["readiness_checkins"] == 1
    assert first_counts["training_sessions"] == 1


def test_rebuild_rolls_back_every_table_on_failure_partway_through():
    # garmin_daily populates before the failing call (get_metrics_history);
    # after rollback, tables populated earlier in the same attempt must be
    # empty too, not left holding this failed attempt's rows.
    stub = _StubRepository(
        garmin_daily=[{"date": "2026-07-31", "steps": 8000}],
        fail_on="get_metrics_history",
    )
    conn = sqlite3.connect(":memory:")
    with pytest.raises(RuntimeError, match="simulated failure"):
        datastore.rebuild(stub, conn)
    assert _count(conn, "garmin_daily") == 0
    assert conn.execute("SELECT COUNT(*) FROM datastore_meta").fetchone()[0] == 0


def test_rebuild_failure_does_not_prevent_a_later_successful_rebuild():
    stub = _StubRepository(garmin_daily=[{"date": "2026-07-31", "steps": 8000}],
                            fail_on="get_metrics_history")
    conn = sqlite3.connect(":memory:")
    with pytest.raises(RuntimeError):
        datastore.rebuild(stub, conn)
    stub._fail_on = None
    counts = datastore.rebuild(stub, conn)
    assert counts["garmin_daily"] == 1
