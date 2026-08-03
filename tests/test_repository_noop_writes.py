"""
Tests for the "only write when something actually changed" behaviour —
_cell_eq, _row_unchanged and Repository._row_is_current, plus the two upsert
paths that use them.

Every Home open re-persists a rolling 7-day window to both Biometric Blend
and Metrics History. Six of those seven days are settled history that cannot
have changed, so six of every seven writes were rewriting a row with exactly
what it already held — two Sheets operations each (upsert_row_by_key does a
find then an update) against the 60-per-minute quota that is the actual cause
of the sync failures the rest of this codebase keeps working around.

The subtle part is the comparison. gspread numericises on read, so a value
written as the float 71.0 comes back as the int 71, and a blank comes back as
"" rather than None. A naive != reports "changed" for every row on every
sync, which would make the whole optimisation a no-op.
"""

from __future__ import annotations

import datetime

from services.clients import sheets
from services.config import Config
from services.readiness import MODEL_VERSION
from services.repository import Repository, _cell_eq, _row_unchanged


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


# ─── _cell_eq — spreadsheet equality, not Python equality ────────────────────

def test_int_and_float_forms_of_the_same_number_are_equal():
    assert _cell_eq(71.0, 71) is True
    assert _cell_eq(71, 71.0) is True


def test_numeric_string_and_number_are_equal():
    assert _cell_eq("71", 71) is True
    assert _cell_eq(9.4, "9.4") is True


def test_blank_forms_are_all_equal():
    assert _cell_eq("", None) is True
    assert _cell_eq(None, "") is True
    assert _cell_eq("", "") is True
    assert _cell_eq("  ", "") is True


def test_a_blank_is_not_equal_to_a_zero():
    """The distinction the whole engine rests on: 0 is a real score, absent
    is not a score at all."""
    assert _cell_eq("", 0) is False
    assert _cell_eq(0, "") is False


def test_genuinely_different_numbers_are_not_equal():
    assert _cell_eq(71, 72) is False
    assert _cell_eq(9.4, 9.5) is False


def test_text_compares_as_text():
    assert _cell_eq("fused", "fused") is True
    assert _cell_eq("fused", "oura_only") is False
    assert _cell_eq(" fused ", "fused") is True


# ─── _row_unchanged ──────────────────────────────────────────────────────────

HEADER = ["date", "readiness_score", "sleep_score", "strain"]


def test_row_unchanged_when_every_cell_matches():
    existing = {"date": "2026-08-01", "readiness_score": 71, "sleep_score": 83, "strain": 9.4}
    assert _row_unchanged(["2026-08-01", 71.0, 83.0, 9.4], existing, HEADER) is True


def test_row_changed_when_one_cell_differs():
    existing = {"date": "2026-08-01", "readiness_score": 71, "sleep_score": 83, "strain": 9.4}
    assert _row_unchanged(["2026-08-01", 71.0, 83.0, 11.2], existing, HEADER) is False


def test_row_changed_when_a_value_arrives_where_there_was_a_blank():
    """The case that must always write: last night's data landing."""
    existing = {"date": "2026-08-01", "readiness_score": "", "sleep_score": "", "strain": ""}
    assert _row_unchanged(["2026-08-01", 71.0, 83.0, 9.4], existing, HEADER) is False


def test_row_changed_when_there_is_no_existing_row():
    assert _row_unchanged(["2026-08-01", 71.0, 83.0, 9.4], None, HEADER) is False
    assert _row_unchanged(["2026-08-01", 71.0, 83.0, 9.4], {}, HEADER) is False


# ─── The upsert paths ────────────────────────────────────────────────────────

class _FakeWorksheet:
    def __init__(self, title, rows):
        self.title = title
        self._rows = rows
        self.writes = []

    def get_all_records(self, numericise_ignore=None, expected_headers=None):
        return list(self._rows)

    def find(self, value, in_column=None):
        return None

    def append_row(self, values):
        self.writes.append(values)

    def update(self, values, rng=None):
        self.writes.append(values)


class _FakeSpreadsheet:
    def __init__(self, tabs):
        self._tabs = tabs

    def worksheet(self, title):
        return self._tabs[title]


class _FakeClient:
    def __init__(self, tabs):
        self._ss = _FakeSpreadsheet(tabs)

    def open_by_key(self, sheet_id):
        return self._ss


def _repo_with(title, rows):
    ws = _FakeWorksheet(title, rows)
    repo = Repository(_config())
    repo._sheets_client = _FakeClient({title: ws})
    return repo, ws


METRICS = sheets.METRICS_HISTORY_WORKSHEET


def test_metrics_history_row_identical_to_stored_is_not_written():
    stored = [{"date": "2026-08-01", "readiness_score": 71, "sleep_pct": 95,
               "sleep_score": 83, "strain": 9.4,
               "readiness_model_version": MODEL_VERSION}]
    repo, ws = _repo_with(METRICS, stored)
    repo.upsert_metrics_history_row({
        "date": "2026-08-01", "readiness_score": 71.0, "sleep_pct": 95.0,
        "sleep_score": 83.0, "strain": 9.4,
    })
    assert ws.writes == []


def test_metrics_history_row_with_a_changed_value_is_written():
    stored = [{"date": "2026-08-01", "readiness_score": 71, "sleep_pct": 95,
               "sleep_score": 83, "strain": 9.4}]
    repo, ws = _repo_with(METRICS, stored)
    repo.upsert_metrics_history_row({
        "date": "2026-08-01", "readiness_score": 71.0, "sleep_pct": 95.0,
        "sleep_score": 83.0, "strain": 12.7,      # a session was logged
    })
    assert len(ws.writes) == 1


def test_metrics_history_row_for_a_new_date_is_written():
    repo, ws = _repo_with(METRICS, [])
    repo.upsert_metrics_history_row({
        "date": "2026-08-01", "readiness_score": 71.0, "sleep_pct": 95.0,
        "sleep_score": 83.0, "strain": 9.4,
    })
    assert len(ws.writes) == 1


def test_metrics_history_writes_when_data_arrives_over_a_blank():
    """First open of the day: the row exists but is empty. Must write."""
    stored = [{"date": "2026-08-01", "readiness_score": "", "sleep_pct": "",
               "sleep_score": "", "strain": ""}]
    repo, ws = _repo_with(METRICS, stored)
    repo.upsert_metrics_history_row({
        "date": "2026-08-01", "readiness_score": 71.0, "sleep_pct": 95.0,
        "sleep_score": 83.0, "strain": None,
    })
    assert len(ws.writes) == 1


def test_a_read_failure_falls_back_to_writing():
    """The optimisation must never be able to SUPPRESS a write — if it can't
    tell whether the row changed, it writes."""
    class _Exploding(_FakeWorksheet):
        def get_all_records(self, numericise_ignore=None, expected_headers=None):
            raise RuntimeError("transient Sheets error")

    ws = _Exploding(METRICS, [])
    repo = Repository(_config())
    repo._sheets_client = _FakeClient({METRICS: ws})
    repo.upsert_metrics_history_row({
        "date": "2026-08-01", "readiness_score": 71.0, "sleep_pct": 95.0,
        "sleep_score": 83.0, "strain": 9.4,
    })
    assert len(ws.writes) == 1


BLEND = sheets.BIOMETRIC_BLEND_WORKSHEET


def test_biometric_blend_row_identical_to_stored_is_not_written():
    from services import models
    stored = [{"date": "2026-08-01", "hrv_ms": 45, "resting_heart_rate": 52,
               "sleep_duration_hours": 7.5, "steps": 8000, "sources_missing": ""}]
    repo, ws = _repo_with(BLEND, stored)
    repo.upsert_biometric_blend_row(models.BiometricRecord(
        date="2026-08-01", hrv_ms=45.0, resting_heart_rate=52.0,
        sleep_duration_hours=7.5, steps=8000,
    ))
    assert ws.writes == []


def test_biometric_blend_row_with_a_changed_value_is_written():
    from services import models
    stored = [{"date": "2026-08-01", "hrv_ms": 45, "resting_heart_rate": 52,
               "sleep_duration_hours": 7.5, "steps": 8000, "sources_missing": ""}]
    repo, ws = _repo_with(BLEND, stored)
    repo.upsert_biometric_blend_row(models.BiometricRecord(
        date="2026-08-01", hrv_ms=45.0, resting_heart_rate=52.0,
        sleep_duration_hours=7.5, steps=11500,   # later step count
    ))
    assert len(ws.writes) == 1


def test_a_settled_week_costs_no_writes_at_all():
    """The point of the whole thing: re-persisting a window of unchanged
    history is free."""
    stored = [
        {"date": f"2026-07-{d:02d}", "readiness_score": 70 + d, "sleep_pct": 90,
         "sleep_score": 80, "strain": 9.0,
         "readiness_model_version": MODEL_VERSION}
        for d in range(25, 32)
    ]
    repo, ws = _repo_with(METRICS, stored)
    for row in stored:
        repo.upsert_metrics_history_row({
            "date": row["date"], "readiness_score": float(row["readiness_score"]),
            "sleep_pct": 90.0, "sleep_score": 80.0, "strain": 9.0,
        })
    assert ws.writes == []


def test_a_row_written_under_an_older_readiness_model_is_rewritten():
    """readiness_model_version is part of the row, so a stored figure from
    MODEL_VERSION 1 (blank) is correctly seen as stale once the rescoring
    model landed — the no-op skip must not freeze old maths in place."""
    stored = [{"date": "2026-08-01", "readiness_score": 71, "sleep_pct": 95,
               "sleep_score": 83, "strain": 9.4, "readiness_model_version": ""}]
    repo, ws = _repo_with(METRICS, stored)
    repo.upsert_metrics_history_row({
        "date": "2026-08-01", "readiness_score": 71.0, "sleep_pct": 95.0,
        "sleep_score": 83.0, "strain": 9.4,
    })
    assert len(ws.writes) == 1


# ─── The tab is read ONCE per sync, not once per row ────────────────────────
# _read_records is keyed on sheets.write_generation(), so the first real write
# in a loop invalidates it. Without an up-front snapshot, every later row's
# check re-downloads the whole tab — turning a 7-row sync where everything
# changed into 7 extra full-tab reads, which is worse than not checking at all.

class _CountingWorksheet(_FakeWorksheet):
    def __init__(self, title, rows):
        super().__init__(title, rows)
        self.reads = 0

    def get_all_records(self, numericise_ignore=None, expected_headers=None):
        self.reads += 1
        return list(self._rows)


def test_metrics_sync_reads_the_tab_once_even_when_every_row_changes():
    ws = _CountingWorksheet(METRICS, [])
    repo = Repository(_config())
    repo._sheets_client = _FakeClient({METRICS: ws})

    existing = repo._rows_by_key(ws, "date")
    assert ws.reads == 1
    for day in range(1, 8):
        d = f"2026-08-{day:02d}"
        repo.upsert_metrics_history_row(
            {"date": d, "readiness_score": 70.0 + day, "sleep_pct": 90.0,
             "sleep_score": 80.0, "strain": 9.0},
            existing=existing.get(d),
        )
    assert len(ws.writes) == 7      # all new, all written
    assert ws.reads == 1            # and still only the one read


def test_rows_by_key_indexes_by_the_key_column():
    stored = [{"date": "2026-08-01", "readiness_score": 71},
              {"date": "2026-08-02", "readiness_score": 68}]
    ws = _CountingWorksheet(METRICS, stored)
    repo = Repository(_config())
    repo._sheets_client = _FakeClient({METRICS: ws})
    got = repo._rows_by_key(ws, "date")
    assert set(got) == {"2026-08-01", "2026-08-02"}
    assert got["2026-08-02"]["readiness_score"] == 68


def test_rows_by_key_returns_empty_on_a_read_failure():
    """Empty makes every row look new, so everything is written — the safe
    direction when we cannot tell what changed."""
    class _Exploding(_FakeWorksheet):
        def get_all_records(self, numericise_ignore=None, expected_headers=None):
            raise RuntimeError("transient Sheets error")

    ws = _Exploding(METRICS, [])
    repo = Repository(_config())
    repo._sheets_client = _FakeClient({METRICS: ws})
    assert repo._rows_by_key(ws, "date") == {}


def test_explicit_none_existing_means_write_without_a_lookup():
    """Inside a sync loop None means 'this date has no row', which must be a
    write, not a re-read."""
    ws = _CountingWorksheet(METRICS, [])
    repo = Repository(_config())
    repo._sheets_client = _FakeClient({METRICS: ws})
    repo.upsert_metrics_history_row(
        {"date": "2026-08-01", "readiness_score": 71.0, "sleep_pct": 95.0,
         "sleep_score": 83.0, "strain": 9.4},
        existing=None,
    )
    assert len(ws.writes) == 1
    assert ws.reads == 0
