"""
services/record_cache.py — the local copy a Supabase-record process reads from.

When Supabase is the system of record (Config.system_of_record ==
"supabase"), reads still come from a local SQLite file: a PostgREST round trip
costs ~136 ms whatever the payload (measured 2026-08-11 — 4,284 ms for every
table against 32 ms from SQLite), so the app cannot read Postgres page by page.
That file is a COPY, and this module keeps it honest.

REBUILT ONCE PER PROCESS, at the first Repository built in it, and not only
when the file is missing. Before 2026-10-09 the hosted cache was filled only
when a redeploy had wiped it, and an existing file was kept. With Supabase the
only store, a file left by an earlier process can lack rows that another
process wrote since — a script, a second machine — and nothing can tell a
stale copy from a current one by looking at it. Within a process the copy stays
current because every write goes to Supabase first and then through to it
(Repository._write_record).

Into a temp file, then os.replace, so a failed rebuild never leaves a
half-filled copy that reads as real data. Leftover -wal/-shm files are removed
first: SQLite would replay an old write-ahead log into the new file.

No Streamlit and no Repository import: Repository.__init__ calls this, and
repo.get_repository() reaches it through services.datastore.ensure_local_cache.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

_LOCK = threading.Lock()
_HYDRATED: set[str] = set()
#: When each copy was last pulled from Supabase in this process (time.time()).
_PULLED_AT: dict[str, float] = {}

#: THE COPY'S ONE WRITER AT A TIME, process-wide: a pull (refresh) holds it
#: from its first read of Supabase to the moment the new rows are in the
#: file, and every write-through (Repository._write_through) holds it while
#: it writes. A row written while a pull runs therefore lands AFTER the pull,
#: in the new copy, and is never lost: its Supabase write came first, so the
#: pull either read it or the write-through applies it again (rebuild Phase
#: 2's freshness rule, 2026-10-19). Re-entrant, so a write-through inside a
#: refresh's own thread cannot deadlock.
WRITE_LOCK = threading.RLock()

#: The config row the HOSTED app writes the first time it starts with
#: Supabase as the record (repo.get_repository -> Repository.
#: mark_record_since). From then on Notion and Google Sheets are a frozen
#: archive and Supabase holds rows they never will, so every tool that copies
#: the legacy stores INTO Supabase (scripts/reconcile_supabase.py,
#: backfill_mirror_sessions.py, prune_mirror_sessions.py) refuses to write
#: once it is set: its "make Supabase match Notion" would delete everything
#: logged since. Only the hosted app writes it, so a local script run before
#: the switch cannot set it early.
RECORD_SINCE_KEY = "supabase_record_since"


def record_since(store) -> str | None:
    """When Supabase became the system of record, or None if it has not yet.
    Raises when Supabase cannot be read: "unknown" must not read as "not
    yet" to a tool that is about to delete rows."""
    return store.select_value("config", f"key=eq.{RECORD_SINCE_KEY}", "value")


def is_supabase_record(config) -> bool:
    """Supabase is the only store and the local copy is a cache of it."""
    return (getattr(config, "system_of_record", "notion") == "supabase"
            and config.datastore_mode == "cache"
            and bool(config.datastore_path))


def _key(path: str) -> str:
    return str(Path(path).resolve())


def hydrate_once(config, store_factory=None) -> str | None:
    """Rebuild config.datastore_path from Supabase, once per process.

    Returns the path when this call rebuilt it, None when this process already
    had. Raises when Supabase cannot be read: serving reads from an empty or
    stale copy would render as though nothing had been logged.
    """
    key = _key(config.datastore_path)
    with _LOCK:
        if key in _HYDRATED:
            return None
        _rebuild(config, key, store_factory)
        _HYDRATED.add(key)
        _PULLED_AT[key] = time.time()
        return config.datastore_path


def pulled_at(path: str) -> float | None:
    """When the copy at `path` was last pulled in this process, or None."""
    return _PULLED_AT.get(_key(path))


def is_stale(path: str, max_age_seconds: float, now: float | None = None) -> bool:
    """The copy was pulled longer ago than `max_age_seconds`, or never in
    this process. Not the file's own age: every write-through touches the
    file, and a copy this process wrote to can still lack another process's
    rows."""
    at = pulled_at(path)
    return at is None or (now if now is not None else time.time()) - at >= max_age_seconds


def refresh(config, store_factory=None) -> str:
    """Pull the copy again from Supabase, in this process, while it runs.

    Two processes (the Streamlit app and the engine) each keep a copy, and
    each copy holds only its own process's writes since its last pull. This
    brings in the other's. Into a temp file first, so a failed pull leaves
    the copy as it was; then copied INTO the live file with SQLite's backup,
    not os.replace, because Repositories hold the live file open: through
    the backup their connections see the new rows at their next read, where
    a replaced file would leave them on the old one (and Windows will not
    replace an open file at all). The whole pull holds WRITE_LOCK, so no row
    this process writes meanwhile is lost."""
    from services import supabase_store

    key = _key(config.datastore_path)
    store = (store_factory or supabase_store.SupabaseStore)(
        config.supabase_url, config.supabase_secret_key)
    with WRITE_LOCK:
        fd, tmp = tempfile.mkstemp(dir=str(Path(key).parent), suffix=".refreshing")
        os.close(fd)
        try:
            src = sqlite3.connect(tmp)
            try:
                supabase_store.pull(store, src)
                dst = sqlite3.connect(key, timeout=30)
                try:
                    src.backup(dst)
                finally:
                    dst.close()
            finally:
                src.close()
        finally:
            Path(tmp).unlink(missing_ok=True)
        with _LOCK:
            _HYDRATED.add(key)
            _PULLED_AT[key] = time.time()
    return config.datastore_path


#: The local copy's tables, the same file services/datastore.py builds from.
SCHEMA_PATH = Path(__file__).with_name("datastore_schema.sql")


def empty_copy(path: str) -> str:
    """An empty local copy at `path` with every table, marked as rebuilt so a
    Repository over it never pulls from Supabase: for a store that is not
    Supabase (the tests' and the sync rehearsal's in-memory one). Pair with
    forget(path)."""
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()
    mark_hydrated(path)
    return path


def mark_hydrated(path: str) -> None:
    """Treat `path` as already rebuilt in this process. For tests that build
    a Supabase-record Repository over a fake store and a prepared file."""
    with _LOCK:
        _HYDRATED.add(_key(path))


def forget(path: str) -> None:
    """Undo mark_hydrated / hydrate_once for `path` (tests)."""
    with _LOCK:
        _HYDRATED.discard(_key(path))
        _PULLED_AT.pop(_key(path), None)


def _rebuild(config, path: str, store_factory=None) -> None:
    from services import supabase_store

    if not (config.supabase_url and config.supabase_secret_key):
        raise RuntimeError(
            "Supabase is the system of record, so SUPABASE_URL and "
            "SUPABASE_SECRET_KEY are required to build the local copy.")
    parent = Path(path).parent
    if not os.access(parent, os.W_OK):
        raise RuntimeError(
            f"the local copy of Supabase is rebuilt in {parent}/, which is not "
            f"writable. Point HEALTH_DATASTORE_PATH at a writable directory.")

    store = (store_factory or supabase_store.SupabaseStore)(
        config.supabase_url, config.supabase_secret_key)
    fd, tmp = tempfile.mkstemp(dir=str(parent), suffix=".hydrating")
    os.close(fd)
    conn = sqlite3.connect(tmp)
    try:
        supabase_store.pull(store, conn)
    except BaseException:
        conn.close()          # Windows will not unlink an open file
        Path(tmp).unlink(missing_ok=True)
        raise
    conn.close()
    for suffix in ("-wal", "-shm"):
        Path(path + suffix).unlink(missing_ok=True)
    os.replace(tmp, path)
