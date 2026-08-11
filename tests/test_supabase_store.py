"""
Pushing the SQLite datastore into Supabase (PostgreSQL).

WHAT ACTUALLY BREAKS is types, not transport. SQLite is loosely typed and
stores whatever it is handed; PostgreSQL is strict and rejects it. Both
failures below were found by loading 2,844 real rows, and neither is visible
from reading the schema:

  ""       in a numeric column. gspread returns "" for a blank cell and the
           offline datastore preserves it verbatim (that fidelity is pinned by
           tests/test_repository_offline_datastore.py). Postgres will not put
           "" in a DOUBLE PRECISION column.

  "FALSE"  in a numeric column. gspread returns booleans as the STRINGS
           'TRUE'/'FALSE', again preserved verbatim. 415 rows of
           oura_sleep_periods.low_battery_alert and both of
           garmin_sleep_stages' boolean columns carry them, sitting in
           BIGINT columns that SQLite was happy to accept.

The mapping is faithful rather than convenient: those columns are declared
BIGINT with comments calling them booleans, and readiness_checkins already
stores its booleans as 0/1.

These tests are pure — no network. The round trip against the live project is
scripts/push_datastore_to_supabase.py --verify, which compares every row count
and spot-checks real float values.
"""

from __future__ import annotations

import sqlite3

import pytest

from services import datastore_postgres as dp
from services import supabase_store as ss


# ─── which columns Postgres will treat as numbers ────────────────────────────

def test_numeric_columns_finds_doubles_and_bigints():
    cols = ss.numeric_columns("metrics_history")
    assert {"readiness_score", "sleep_pct", "sleep_score", "strain"} <= cols
    assert "date" not in cols, "a TEXT primary key is not numeric"


def test_text_columns_holding_digits_are_not_numeric():
    """The hypnograms are digit-coded STRINGS. Treating them as numeric would
    put them through the ""->NULL rule and, worse, invite storing them as
    numbers — which clients/datastore_reader.py exists to prevent because it
    is unrecoverable."""
    cols = ss.numeric_columns("sleep_fusion")
    for text_col in ("master_hypnogram", "oura_hypnogram", "garmin_hypnogram",
                     "reason_codes", "movement_cutpoints"):
        assert text_col not in cols


# ─── the coercion ────────────────────────────────────────────────────────────

def test_empty_string_in_a_numeric_column_becomes_null():
    out = ss.coerce_row({"strain": "", "date": "2026-08-10"}, {"strain"})
    assert out["strain"] is None


def test_empty_string_in_a_text_column_is_left_alone():
    """Blank and absent are different for text here — a stored empty
    hypnogram is not the same as never having recorded one."""
    out = ss.coerce_row({"master_hypnogram": "", "strain": ""}, {"strain"})
    assert out["master_hypnogram"] == ""
    assert out["strain"] is None


@pytest.mark.parametrize("raw,expected", [
    ("TRUE", 1), ("FALSE", 0), ("True", 1), ("False", 0),
    ("true", 1), ("false", 0),
])
def test_boolean_strings_in_numeric_columns_become_one_and_zero(raw, expected):
    assert ss.coerce_row({"totals_match": raw}, {"totals_match"})["totals_match"] == expected


def test_a_boolean_string_in_a_TEXT_column_stays_a_string():
    """There it is a value, not a boolean — e.g. a status word that happens to
    read TRUE. Only numeric columns get the mapping."""
    out = ss.coerce_row({"stress_day_summary": "FALSE"}, set())
    assert out["stress_day_summary"] == "FALSE"


def test_real_numbers_and_nulls_pass_through_untouched():
    row = {"strain": 7.4, "steps": 9182, "sleep_score": None, "date": "2026-08-10"}
    assert ss.coerce_row(row, {"strain", "steps", "sleep_score"}) == row


def test_float_precision_is_not_rounded_by_coercion():
    """cohen_kappa and the HRV values carry three decimals that matter."""
    out = ss.coerce_row({"cohen_kappa": 0.226}, {"cohen_kappa"})
    assert out["cohen_kappa"] == 0.226


def test_every_boolean_string_in_the_real_datastore_is_covered():
    """Scans the actual datastore.db, if present, for any non-numeric string
    sitting in a numeric column that the coercion would NOT handle — the check
    that found the original bug. Skips on a checkout without the snapshot."""
    from pathlib import Path

    db = Path(__file__).resolve().parent.parent / "datastore.db"
    if not db.exists():
        pytest.skip("no datastore.db in this checkout")
    ddl = dp.to_postgres()
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    unhandled = {}
    for table in dp.table_names(ddl):
        numeric = ss.numeric_columns(table, ddl)
        if not numeric:
            continue
        for row in conn.execute(f"SELECT * FROM {table}"):
            for col in numeric:
                v = row[col]
                if not isinstance(v, str) or v.strip() == "":
                    continue
                coerced = ss.coerce_row({col: v}, {col})[col]
                if isinstance(coerced, str):
                    try:
                        float(coerced)
                    except ValueError:
                        unhandled[f"{table}.{col}"] = v[:20]
    assert not unhandled, (
        f"values Postgres will reject and the coercion does not handle: "
        f"{unhandled}"
    )


# ─── load ordering ───────────────────────────────────────────────────────────

def test_parents_load_before_children():
    """The foreign keys are ENFORCED in Postgres, so a child inserted first is
    a hard error rather than an orphan row."""
    assert ss.LOAD_ORDER.index("training_sessions") < ss.LOAD_ORDER.index("training_exercises")
    assert ss.LOAD_ORDER.index("training_exercises") < ss.LOAD_ORDER.index("training_sets")


def test_every_table_has_a_delete_filter():
    """PostgREST refuses an unfiltered DELETE. A table missing from the map
    would raise rather than silently leave its old rows behind — which would
    look like a successful push over a stale table."""
    for table in dp.table_names(dp.to_postgres()):
        assert table in ss._ANY_ROW_FILTER, f"{table} has no delete filter"


def test_truncate_refuses_an_unknown_table():
    store = ss.SupabaseStore("https://example.supabase.co", "key")
    with pytest.raises(ss.SupabaseError, match="no delete filter"):
        store.truncate("not_a_table")


# ─── configuration ───────────────────────────────────────────────────────────

def test_an_unconfigured_store_refuses_to_be_built():
    """Better than a confusing 401 later."""
    with pytest.raises(ss.SupabaseError, match="not configured"):
        ss.SupabaseStore("", "")
    with pytest.raises(ss.SupabaseError, match="not configured"):
        ss.SupabaseStore("https://example.supabase.co", "")


def test_supabase_settings_are_optional_in_config():
    """A checkout without Supabase keys must behave exactly as before —
    nothing in the live app reads from Postgres yet."""
    from services.config import Config
    cfg = Config(
        notion_api_key="k", notion_db_readiness="a", notion_db_training="b",
        notion_db_biometrics="c", notion_db_config="d", google_sheets_id="e",
        google_service_account={},
    )
    assert cfg.supabase_url == ""
    assert cfg.supabase_secret_key == ""


def test_the_publishable_key_is_not_carried_in_config():
    """Only the SERVER key is here. The publishable key has no server-side
    use, and holding both invites reaching for the wrong one."""
    from services.config import Config
    assert not any("publishable" in f.lower() for f in Config.__dataclass_fields__)
