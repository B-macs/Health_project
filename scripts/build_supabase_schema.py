"""Emit (and optionally apply) the PostgreSQL schema for the Supabase project.

    python scripts/build_supabase_schema.py            # write the .sql
    python scripts/build_supabase_schema.py --apply    # ...and run it

WHY --apply USUALLY CANNOT RUN. Supabase's Data API is PostgREST, which does
CRUD on tables that already exist; it has no route that executes DDL. Creating
tables therefore needs a real PostgreSQL connection, which needs the database
PASSWORD -- a different credential from SUPABASE_SECRET_KEY, and one this repo
does not store. So --apply needs BOTH:

    pip install "psycopg[binary]"
    SUPABASE_DB_URL=postgresql://postgres.<ref>:<password>@<host>:5432/postgres

Without them the script still writes the file, and pasting that into the
Supabase SQL editor does the same job with no extra credential on disk. That
is the recommended path for a one-off: this schema is applied when it changes,
not on a schedule.

Safe to re-run. Every CREATE is preceded by DROP TABLE IF EXISTS ... CASCADE,
so applying it twice is idempotent -- and DESTRUCTIVE: it drops the tables and
everything in them. That is the same wholesale-rebuild contract
services/datastore.py already has for the SQLite copy, where the data is a
regenerable projection of Notion and Sheets rather than the system of record.
Once this database BECOMES the system of record, this script stops being safe
to run and the change becomes a migration -- see the guard below.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import datastore_postgres  # noqa: E402

OUT_PATH = Path(__file__).resolve().parent.parent / "services" / "datastore_schema_postgres.sql"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="execute against SUPABASE_DB_URL (DROPS EVERY TABLE FIRST)")
    ap.add_argument("--yes", action="store_true",
                    help="skip the confirmation prompt for --apply")
    args = ap.parse_args()

    ddl = datastore_postgres.to_postgres()
    OUT_PATH.write_text(ddl, encoding="utf-8")
    tables = datastore_postgres.table_names(ddl)
    print(f"wrote {OUT_PATH.relative_to(Path.cwd())}  ({len(tables)} tables, {len(ddl.splitlines())} lines)")

    if not args.apply:
        print("\nTo apply, either:")
        print("  1. paste that file into the Supabase SQL editor (no extra credential), or")
        print("  2. pip install \"psycopg[binary]\" and set SUPABASE_DB_URL, then re-run with --apply")
        return 0

    db_url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not db_url:
        print("\nSUPABASE_DB_URL is not set — that is the database password "
              "connection string, not SUPABASE_SECRET_KEY. See this file's docstring.")
        return 2
    try:
        import psycopg
    except ImportError:
        print("\npsycopg is not installed:  pip install \"psycopg[binary]\"")
        return 2

    if not args.yes:
        print("\n⚠ This DROPS all 21 tables and everything in them.")
        if input("Type 'drop' to continue: ").strip().lower() != "drop":
            print("aborted")
            return 1

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
    print(f"applied {len(tables)} tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
