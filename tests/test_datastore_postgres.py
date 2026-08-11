"""
The PostgreSQL translation of datastore_schema.sql.

There is ONE schema — services/datastore_schema.sql — and
services/datastore_postgres.py derives the Postgres dialect from it. A
hand-written second file would mean two descriptions of the same 21 tables,
drifting the first time a column is added to one and not the other. These
tests are what make the derived file trustworthy: every table and every column
must survive translation, and the type mapping must be the CORRECT one rather
than the one that merely looks right.

The mapping worth the most attention is REAL. SQLite's REAL is an 8-byte IEEE
float; PostgreSQL's REAL is 4-byte. Translating the name onto itself would
pass every "does it apply cleanly" check and silently halve the precision of
all 165 float columns — every HRV reading, every kilogram, every strain value.
"""

from __future__ import annotations

import re

import pytest

from services import datastore_postgres as dp

SQLITE = dp.SCHEMA_PATH.read_text(encoding="utf-8")
POSTGRES = dp.to_postgres()


# ─── nothing is lost in translation ──────────────────────────────────────────

def test_every_table_survives_in_the_same_order():
    assert dp.table_names(POSTGRES) == dp.table_names(SQLITE)


def test_every_column_of_every_table_survives():
    """Column-for-column, not just a count — a rename would pass a count."""
    for table in dp.table_names(SQLITE):
        assert dp.column_names(POSTGRES, table) == dp.column_names(SQLITE, table), (
            f"{table} lost or renamed a column in translation"
        )


def test_the_translation_is_not_empty_or_truncated():
    assert len(dp.table_names(POSTGRES)) >= 21
    assert POSTGRES.rstrip().endswith(";")


# ─── the type mapping ────────────────────────────────────────────────────────

def test_sqlite_real_becomes_double_precision_not_real():
    """THE mapping to get wrong quietly. Postgres REAL is 4-byte; SQLite REAL
    is 8. Same word, half the precision, on every float column in the app."""
    assert " REAL" not in POSTGRES, "REAL survived — floats would lose precision"
    assert "DOUBLE PRECISION" in POSTGRES
    assert POSTGRES.count("DOUBLE PRECISION") == len(
        re.findall(r"^\s+\w+\s+REAL\b", SQLITE, re.M)
    )


def test_sqlite_integer_becomes_bigint():
    """Several columns hold epoch-millisecond timestamps and Garmin activity
    ids, which overflow a 4-byte int."""
    assert not re.search(r"^\s+\w+\s+INTEGER\b", POSTGRES, re.M)
    assert "BIGINT" in POSTGRES


def test_the_autoincrement_key_becomes_a_generated_identity():
    """GENERATED ALWAYS, not BIGSERIAL: services/datastore.py never supplies
    training_sets.id, and GENERATED ALWAYS turns a future INSERT that tries
    into an error rather than a silent sequence desync."""
    assert "AUTOINCREMENT" not in POSTGRES
    assert "BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY" in POSTGRES
    assert POSTGRES.count("GENERATED ALWAYS AS IDENTITY") == 1


# ─── the things Postgres is strict about and SQLite is not ───────────────────

def test_every_drop_cascades():
    """Postgres refuses to drop a table a foreign key still references, so
    without CASCADE the SECOND run of the schema fails — which is exactly when
    nobody is watching."""
    drops = re.findall(r"DROP TABLE IF EXISTS (\w+)( CASCADE)?;", POSTGRES)
    assert drops, "no DROP statements survived"
    missing = [t for t, casc in drops if not casc]
    assert not missing, f"DROP without CASCADE: {missing}"


def test_foreign_keys_are_declared_after_every_table_exists():
    """The SQLite file declares training_sets BEFORE training_exercises, the
    table it points at — legal only because enforcement is off there. In
    Postgres an inline REFERENCES to a table that does not exist yet is an
    error, so they are lifted out and applied at the end."""
    # Code only: the schema's own header COMMENT discusses its REFERENCES
    # clauses in prose, and that prose is deliberately preserved.
    before_fks = POSTGRES.split("-- ── Foreign keys")[0]
    code_only = "\n".join(
        dp._split_code_and_comment(l)[0] for l in before_fks.splitlines()
    )
    assert "REFERENCES" not in code_only.upper(), (
        "an inline REFERENCES survived inside a CREATE TABLE"
    )
    alters = re.findall(r"ALTER TABLE (\w+) ADD CONSTRAINT", POSTGRES)
    assert sorted(alters) == ["training_exercises", "training_sets"]
    # ...and after the last CREATE, not interleaved.
    assert POSTGRES.index("ALTER TABLE") > POSTGRES.rindex("CREATE TABLE")


def test_foreign_keys_point_at_primary_keys():
    """Postgres requires the referenced column to be unique; SQLite does not.
    Both targets are declared PRIMARY KEY, which is what makes enforcing them
    possible at all."""
    for ref_table, ref_col in re.findall(r"REFERENCES (\w+)\((\w+)\)", POSTGRES):
        cols = dp.column_names(SQLITE, ref_table)
        assert ref_col in cols
        assert re.search(rf"^\s+{ref_col}\s+TEXT PRIMARY KEY", SQLITE, re.M), (
            f"{ref_table}.{ref_col} is not a PRIMARY KEY — Postgres will "
            f"reject the foreign key"
        )


# ─── the file stays derived ──────────────────────────────────────────────────

def test_comments_are_preserved():
    """They carry the provenance notes — which Notion property a column came
    from, why a value may be blank — which is the real documentation."""
    assert "-- NULL when the exercise has no band tier" in POSTGRES


def test_the_generated_file_says_it_is_generated():
    assert POSTGRES.lstrip().startswith("-- GENERATED FILE")
    assert "datastore_postgres.py" in POSTGRES


def test_translation_is_deterministic():
    assert dp.to_postgres() == POSTGRES


def test_the_checked_in_copy_matches_the_translator(tmp_path):
    """If services/datastore_schema_postgres.sql is committed, it must be what
    the translator currently produces — otherwise someone edited the generated
    file and the two dialects have already diverged."""
    from pathlib import Path

    out = Path(dp.__file__).resolve().parent / "datastore_schema_postgres.sql"
    if not out.exists():
        pytest.skip("no generated copy committed yet")
    assert out.read_text(encoding="utf-8") == POSTGRES, (
        "services/datastore_schema_postgres.sql is stale or hand-edited — "
        "re-run scripts/build_supabase_schema.py"
    )
