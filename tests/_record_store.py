"""A record-mode Repository over a fake Supabase, for tests.

Supabase as the system of record (2026-10-09): every write goes to Supabase
first and is waited for, then to the local SQLite copy. FakeStore is
PostgREST reduced to what the Repository calls, over plain lists, so a test
can read back exactly what was stored. No network.

Shared by tests/test_supabase_record_mode.py and tests/test_session_save.py.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from services import record_cache, supabase_store
from services.config import Config
from services.repository import Repository

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = (ROOT / "services" / "datastore_schema.sql").read_text(encoding="utf-8")


class FakeStore:
    """PostgREST, reduced to what the repository calls, over plain lists."""

    def __init__(self, tables: dict | None = None, fail_on=None):
        self.tables = {t: [dict(r) for r in rows] for t, rows in (tables or {}).items()}
        self.log: list[tuple] = []
        self.fail_on = fail_on

    def _check(self, op, table):
        if self.fail_on in ((op, table), table):
            raise supabase_store.SupabaseError(f"boom on {op} {table}")

    def upsert(self, table, rows):
        self._check("upsert", table)
        self.log.append(("upsert", table, len(rows)))
        pk = supabase_store.primary_key(table)
        current = {str(r[pk]): r for r in self.tables.get(table, [])}
        for r in rows:
            current[str(r[pk])] = {**current.get(str(r[pk]), {}), **r}
        self.tables[table] = list(current.values())
        return len(rows)

    def patch(self, table, pk, key, row):
        self._check("patch", table)
        self.log.append(("patch", table, str(key)))
        n = 0
        for r in self.tables.get(table, []):
            if str(r.get(pk)) == str(key):
                r.update(row)
                n += 1
        return n

    def delete_where(self, table, column, value):
        self._check("delete", table)
        self.log.append(("delete", table, str(value)))
        self.tables[table] = [r for r in self.tables.get(table, [])
                              if str(r.get(column)) != str(value)]

    def insert(self, table, rows):
        self._check("insert", table)
        self.log.append(("insert", table, len(rows)))
        self.tables.setdefault(table, []).extend(dict(r) for r in rows)
        return len(rows)

    def select_all(self, table, order=""):
        return [dict(r) for r in self.tables.get(table, [])]

    def select_value(self, table, where, column):
        col, _, value = where.partition("=eq.")
        for r in self.tables.get(table, []):
            if str(r.get(col)) == value:
                return r.get(column)
        return None


def new_local_copy(tmp_path) -> str:
    """An empty local copy with the datastore schema, marked as rebuilt so
    the Repository does not rebuild it from Supabase. Pair with
    record_cache.forget(path) at teardown."""
    path = tmp_path / "record_cache.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    record_cache.mark_hydrated(str(path))
    return str(path)


def record_config(path: str) -> Config:
    return Config(
        notion_api_key="", notion_db_readiness="record:readiness",
        notion_db_training="record:training", notion_db_config="record:config",
        google_sheets_id="", google_service_account={},
        datastore_path=path, datastore_mode="cache",
        supabase_url="https://x.supabase.co", supabase_secret_key="k",
        system_of_record="supabase")


def record_repo(path: str, store: FakeStore) -> Repository:
    repo = Repository(record_config(path))
    repo._supabase_store_obj = store
    return repo


def local_rows(path: str, sql: str, *args) -> list[tuple]:
    conn = sqlite3.connect(path)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()
