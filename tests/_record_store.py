"""A record-mode Repository over a fake Supabase, for tests.

Supabase as the system of record (2026-10-09): every write goes to Supabase
first and is waited for, then to the local SQLite copy. FakeStore is
services/memory_store.MemoryStore: PostgREST reduced to what the Repository
calls, over plain lists, so a test can read back exactly what was stored. No
network.

Shared by tests/test_supabase_record_mode.py and tests/test_session_save.py.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from services import record_cache
from services.memory_store import MemoryStore
from services.config import Config
from services.repository import Repository

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = (ROOT / "services" / "datastore_schema.sql").read_text(encoding="utf-8")


#: The in-memory store moved to services/memory_store.py on 2026-10-20, so the
#: sync rehearsal (api/healthapi/rehearsal.py) can run on it in the engine's image.
FakeStore = MemoryStore


def new_local_copy(tmp_path) -> str:
    """An empty local copy with the datastore schema, marked as rebuilt so
    the Repository does not rebuild it from Supabase. Pair with
    record_cache.forget(path) at teardown."""
    return record_cache.empty_copy(str(tmp_path / "record_cache.db"))


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
