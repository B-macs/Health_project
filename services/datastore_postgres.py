"""
services/datastore_postgres.py -- translates datastore_schema.sql (SQLite)
into the equivalent PostgreSQL DDL for the Supabase project.

A TRANSLATOR, NOT A SECOND SCHEMA FILE. Keeping a hand-written Postgres copy
beside the SQLite one would mean two schemas describing the same 21 tables,
drifting apart the first time a column is added to one and not the other --
the same failure the EXERCISE_BODY_REGION / EXERCISE_MOVEMENT_WEIGHT pair is
bound by a test to avoid. There is ONE schema; this derives the other dialect
from it, and tests/test_datastore_postgres.py fails if any table or column
goes missing in translation.

WHAT ACTUALLY DIFFERS, and why each mapping is what it is:

  REAL -> DOUBLE PRECISION, not REAL. SQLite's REAL is an 8-byte IEEE float;
      PostgreSQL's REAL is 4-byte. Mapping the name onto itself would look
      right and silently halve the precision of all 165 float columns --
      every HRV reading, every kilogram, every strain value.

  INTEGER -> BIGINT. SQLite integers are up to 8 bytes and several of these
      columns hold epoch-millisecond timestamps and Garmin activity ids,
      which overflow a 4-byte int.

  INTEGER PRIMARY KEY AUTOINCREMENT -> BIGINT GENERATED ALWAYS AS IDENTITY.
      training_sets' surrogate key. `GENERATED ALWAYS` is deliberate over
      BIGSERIAL: services/datastore.py never supplies this column, and
      GENERATED ALWAYS makes a future INSERT that tries to an error rather
      than a silent sequence desync.

  DROP TABLE ... -> ... CASCADE. Postgres refuses to drop a table another
      table's foreign key still references; SQLite, with enforcement off,
      does not care. Without CASCADE a rebuild fails on the second run.

  FOREIGN KEYS MOVE TO THE END. The SQLite file creates training_sets (which
      references training_exercises) BEFORE the table it points at, which is
      only legal because PRAGMA foreign_keys is off there. Rather than
      reorder the file -- and lose its readable grouping -- the REFERENCES
      clauses are lifted out of the CREATEs and re-emitted as ALTER TABLE
      statements once every table exists.

      They are ENFORCED here, unlike in SQLite. The SQLite header explains
      that enforcement was skipped because a wholesale regenerate has "no
      write path for a constraint to protect"; that stops being true the
      moment this database is the write path. It is safe today because
      services/datastore.py already inserts parents first -- sessions, then
      exercises, then sets.

WHAT IS NOT TRANSLATED. Comments are preserved verbatim, because they carry
the provenance notes (which column came from which Notion property, why a
value may be blank) that are the actual documentation of this data.
"""
from __future__ import annotations

import re
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "datastore_schema.sql"

#: SQLite type -> PostgreSQL type. See the module docstring for why REAL does
#: NOT map to REAL.
TYPE_MAP = {
    "REAL": "DOUBLE PRECISION",
    "INTEGER": "BIGINT",
    "TEXT": "TEXT",
    "BLOB": "BYTEA",
    "NUMERIC": "NUMERIC",
}

_IDENTITY = "BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY"

_DROP_RE = re.compile(r"^\s*DROP TABLE IF EXISTS\s+(\w+)\s*;", re.I | re.M)
_AUTOINC_RE = re.compile(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", re.I)
_REFERENCES_RE = re.compile(r"\s+REFERENCES\s+(\w+)\s*\(\s*(\w+)\s*\)", re.I)
_CREATE_RE = re.compile(r"CREATE TABLE\s+(\w+)", re.I)


def _split_code_and_comment(line: str) -> tuple[str, str]:
    """(code, trailing comment). Splits on the first `--` that is not inside a
    string literal — the schema has none, but a naive split would still be
    wrong the day one appears, and these comments carry the provenance notes."""
    in_str = False
    for i, ch in enumerate(line):
        if ch == "'":
            in_str = not in_str
        elif ch == "-" and not in_str and line[i:i + 2] == "--":
            return line[:i], line[i:]
    return line, ""


def to_postgres(sqlite_ddl: str | None = None) -> str:
    """The PostgreSQL equivalent of the SQLite schema.

    Reads services/datastore_schema.sql when given nothing, so callers cannot
    accidentally translate a stale copy.
    """
    if sqlite_ddl is None:
        sqlite_ddl = SCHEMA_PATH.read_text(encoding="utf-8")

    foreign_keys: list[tuple[str, str, str, str]] = []
    current_table = ""
    out: list[str] = []

    for line in sqlite_ddl.splitlines():
        code, comment = _split_code_and_comment(line)

        m = _CREATE_RE.search(code)
        if m:
            current_table = m.group(1)

        # Lift FKs out; they are re-emitted as ALTER TABLE once all tables exist.
        ref = _REFERENCES_RE.search(code)
        if ref and current_table:
            column = code.strip().split()[0]
            foreign_keys.append((current_table, column, ref.group(1), ref.group(2)))
            code = _REFERENCES_RE.sub("", code)

        code = _AUTOINC_RE.sub(_IDENTITY, code)
        for sqlite_type, pg_type in TYPE_MAP.items():
            if sqlite_type == "INTEGER":
                # Never rewrite the INTEGER already consumed by _IDENTITY.
                code = re.sub(rf"\b{sqlite_type}\b(?!\s+GENERATED)", pg_type, code)
            else:
                code = re.sub(rf"\b{sqlite_type}\b", pg_type, code)

        code = _DROP_RE.sub(r"DROP TABLE IF EXISTS \1 CASCADE;", code)
        out.append((code + comment).rstrip() if (code.strip() or comment) else "")

    body = "\n".join(out).rstrip()

    if foreign_keys:
        body += "\n\n-- ── Foreign keys ─────────────────────────────────────────────────────\n"
        body += ("-- Lifted out of the CREATEs above: the SQLite file declares\n"
                 "-- training_sets before the table it references, which is only legal\n"
                 "-- with enforcement off. Applied here once every table exists, and\n"
                 "-- ENFORCED — services/datastore.py already loads parents first\n"
                 "-- (sessions, then exercises, then sets).\n")
        for table, column, ref_table, ref_column in foreign_keys:
            body += (
                f"ALTER TABLE {table} ADD CONSTRAINT {table}_{column}_fkey\n"
                f"    FOREIGN KEY ({column}) REFERENCES {ref_table}({ref_column});\n"
            )

    header = (
        "-- GENERATED FILE — do not edit.\n"
        "-- Produced by services/datastore_postgres.py::to_postgres() from\n"
        "-- services/datastore_schema.sql, which is the ONE schema. Change that\n"
        "-- file and regenerate; editing this one puts the two dialects out of\n"
        "-- step, which is the whole thing the translator exists to prevent.\n"
        "--\n"
        "-- Apply with: python scripts/build_supabase_schema.py\n\n"
    )
    return header + body + "\n"


def table_names(ddl: str) -> list[str]:
    """Every table a DDL string creates, in order."""
    return _CREATE_RE.findall(ddl)


def column_names(ddl: str, table: str) -> list[str]:
    """Column names declared for `table`, ignoring comments and constraints."""
    m = re.search(rf"CREATE TABLE\s+{table}\s*\((.*?)\n\);", ddl, re.S | re.I)
    if not m:
        return []
    cols = []
    for raw in m.group(1).splitlines():
        code, _ = _split_code_and_comment(raw)
        code = code.strip().rstrip(",").strip()
        if not code or code.upper().startswith(("PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK")):
            continue
        cols.append(code.split()[0])
    return cols
