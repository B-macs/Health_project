"""
datastore.db -> Supabase -> datastore.db must be lossless.

The push has existed since 2026-08-10 and the pull since 2026-08-11, which
finally made the fidelity question answerable by EXPERIMENT rather than by
reading the schema. Running it (scripts/pull_datastore_from_supabase.py
--round-trip) found 19 of 21 tables byte-identical and two that were not, in
exactly three columns:

    oura_sleep_periods.low_battery_alert    428 cells   'FALSE' -> 0
    garmin_sleep_stages.totals_match         68 cells   'TRUE'  -> 1
    garmin_sleep_stages.movement_contiguous  68 cells   'TRUE'  -> 1

All three mirror a Google Sheets cell, and gspread returns a boolean cell as
the STRING 'TRUE'/'FALSE' — which clients/datastore_reader.py pins as a
fidelity rule, because an offline read has to return what a live read would.
They were declared INTEGER, which SQLite's loose typing accepted silently;
PostgreSQL enforces the declaration, so the value had to be coerced to 1/0
and came back 1/0.

THE ONE THAT ACTUALLY BITES is movement_contiguous, and it is why this file
exists rather than a note in the schema. Repository read it as
`str(v).upper() != "FALSE"`, so a coerced 0 stringifies to "0", misses the
comparison, and INVERTS to contiguous — a night whose movement series needed
gap-filling would be reported as clean. No error, no warning; the diagnostic
would simply stop diagnosing.

Fixed at the declaration (TEXT, so no coercion happens at all and the round
trip is lossless by construction) AND at the reader (falsey spellings named
explicitly instead of testing for one of them). Either alone would have
worked; both, because the reader's fragility outlives this particular
column and the next mis-declaration will not announce itself either.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from services import datastore_postgres as dp
from services import supabase_store as ss

ROOT = Path(__file__).resolve().parent.parent

#: (table, column) for every column that mirrors a gspread boolean cell.
GSPREAD_BOOLEAN_COLUMNS = [
    ("oura_sleep_periods", "low_battery_alert"),
    ("garmin_sleep_stages", "totals_match"),
    ("garmin_sleep_stages", "movement_contiguous"),
]


@pytest.mark.parametrize("table,column", GSPREAD_BOOLEAN_COLUMNS)
def test_gspread_boolean_columns_are_text_in_both_dialects(table, column):
    """Declared TEXT so no coercion is needed and the Postgres round trip is
    lossless BY CONSTRUCTION rather than by a reverse mapping that would have
    to be maintained alongside the forward one."""
    sqlite_ddl = dp.SCHEMA_PATH.read_text(encoding="utf-8")
    assert f"{column}" in sqlite_ddl
    for ddl, dialect in ((sqlite_ddl, "sqlite"), (dp.to_postgres(), "postgres")):
        body = ddl.split(f"CREATE TABLE {table} (")[1].split("\n);")[0]
        line = [l for l in body.splitlines()
                if l.strip().split()[:1] == [column]][0]
        assert " TEXT" in line, (
            f"{dialect}: {table}.{column} is not TEXT — a gspread 'TRUE' would "
            f"be coerced and the round trip would be lossy"
        )


@pytest.mark.parametrize("table,column", GSPREAD_BOOLEAN_COLUMNS)
def test_gspread_boolean_columns_are_not_coerced_on_push(table, column):
    """The push only touches numeric columns. These must not be among them,
    or 'TRUE' becomes 1 on the way out and stays 1 on the way back."""
    assert column not in ss.numeric_columns(table)
    row = ss.coerce_row({column: "FALSE"}, ss.numeric_columns(table))
    assert row[column] == "FALSE", "the string was coerced away"


def test_a_stored_zero_does_not_read_as_contiguous():
    """The inversion, pinned directly.

    `str(v).upper() != "FALSE"` treats EVERY unrecognised value as contiguous,
    so the failure is silent and points the wrong way — the safe direction for
    an unknown value is "not contiguous", i.e. do not claim a clean night.
    """
    from services.repository import Repository

    def contiguous(value):
        # The expression as repository.py evaluates it.
        return str(value).strip().lower() not in ("false", "0")

    for falsey in ("FALSE", "false", "False", 0, "0"):
        assert contiguous(falsey) is False, f"{falsey!r} read as contiguous"
    for truthy in ("TRUE", "true", 1, "1"):
        assert contiguous(truthy) is True, f"{truthy!r} read as not contiguous"

    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    assert 'str(r.get("movement_contiguous", "")).upper() != "FALSE"' not in src, (
        "the fragile form is back: it treats an unrecognised value as "
        "contiguous, which is the direction that hides a problem"
    )
    assert Repository  # the module imports


# ─── paging ──────────────────────────────────────────────────────────────

def test_every_table_has_a_primary_key_to_page_by():
    """select_all pages by offset, which is only correct under a TOTAL order
    — without one Postgres may return rows in any order per request, so page 2
    can repeat or skip what page 1 held and the result still looks like a full
    table."""
    for table in dp.table_names(dp.to_postgres()):
        assert ss.primary_key(table)


def test_the_primary_key_matches_the_delete_filters_column():
    """_ANY_ROW_FILTER filters on a column that is NOT NULL for every row —
    its primary key. Two derivations of the same fact must agree."""
    for table, where in ss._ANY_ROW_FILTER.items():
        assert where.split("=")[0] == ss.primary_key(table), table


def test_select_all_keeps_paging_until_a_short_page():
    """A table over the response ceiling (Supabase's max-rows, 1000 by
    default) comes back SHORT with no error — the same shape of failure as a
    throttled Sheets read, and the reason select_all exists beside select."""
    pages, seen = [], []

    class _Store(ss.SupabaseStore):
        def __init__(self): self.url, self._key = "https://x", "k"
        def _request(self, method, path, body=None, headers=None):
            seen.append(path)
            return {}, pages.pop(0)

    pages[:] = [[{"date": i} for i in range(ss.BATCH)],
                [{"date": i} for i in range(ss.BATCH, ss.BATCH + 7)]]
    rows = _Store().select_all("metrics_history")
    assert len(rows) == ss.BATCH + 7
    assert len(seen) == 2, "stopped after one page"
    assert f"offset={ss.BATCH}" in seen[1]
    assert "order=" in seen[0], "paged without a total order"


def test_select_all_stops_on_an_empty_first_page():
    class _Store(ss.SupabaseStore):
        def __init__(self): self.url, self._key = "https://x", "k"
        def _request(self, method, path, body=None, headers=None):
            return {}, []
    assert _Store().select_all("config") == []


# ─── pull ────────────────────────────────────────────────────────────────

def test_pull_rebuilds_from_the_same_schema_file_as_rebuild():
    """One schema, two fill paths. If pull built its own tables the two
    datastores would drift the first time a column was added."""
    class _Store:
        def select_all(self, table):
            return [{"key": "current_stage", "value": "2", "updated": "2026-07-20"}] \
                if table == "config" else []

    conn = sqlite3.connect(":memory:")
    counts = ss.pull(_Store(), conn, ["config", "metrics_history"])
    assert counts == {"config": 1, "metrics_history": 0}
    got = conn.execute("SELECT key, value FROM config").fetchall()
    assert got == [("current_stage", "2")]
    # ...and every other table exists, empty, because the whole schema ran.
    assert conn.execute("SELECT COUNT(*) FROM readiness_checkins").fetchone()[0] == 0


def test_a_failing_pull_leaves_no_half_filled_datastore():
    """rebuild()'s all-or-nothing contract, matched. A partly-filled cache is
    worse than an empty one: it reads as real data."""
    class _Store:
        def select_all(self, table):
            if table == "metrics_history":
                raise ss.SupabaseError("boom")
            return [{"key": "k", "value": "v", "updated": "2026-01-01"}]

    conn = sqlite3.connect(":memory:")
    with pytest.raises(ss.SupabaseError):
        ss.pull(_Store(), conn, ["config", "metrics_history"])
    assert conn.execute("SELECT COUNT(*) FROM config").fetchone()[0] == 0


def test_pull_lets_sqlite_mint_its_own_training_set_ids():
    """id is a surrogate assigned independently by each store; supplying
    Postgres' value would be meaningless and, in the other direction, is
    rejected outright by GENERATED ALWAYS."""
    class _Store:
        def select_all(self, table):
            if table == "training_sets":
                return [{"id": 90001, "exercise_id": "ex-1", "set_num": 1,
                         "reps": 10, "weight": 20.0, "rest": 90, "tut": 0,
                         "velocity": "controlled", "band_tier": None, "ts": None}]
            return []

    conn = sqlite3.connect(":memory:")
    ss.pull(_Store(), conn, ["training_sets"])
    row = conn.execute("SELECT id, exercise_id FROM training_sets").fetchone()
    assert row[1] == "ex-1"
    assert row[0] == 1, "Postgres' surrogate id was carried across"
