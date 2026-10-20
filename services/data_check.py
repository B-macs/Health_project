"""
services/data_check.py — the daily data check: rows the store has lost.

WHY. The Phase 4 prompt (2026-10-07) asked for a daily check that compares
Notion with Supabase over the last 30 days, because the Supabase mirror had
lost logged sessions (2026-09-17/18, 09-23, 10-06..08). Since 2026-10-09
Supabase is the only store and Notion a frozen archive: comparing the two
would report everything logged since the switch. The question the check
exists for is unchanged — has the store lost rows? — and the daily backup
(services/backup.py) is now the copy to ask it against.

WHAT. Every table of the newest backup is compared with the store as it is
now, pulled fresh (the record itself, not a local copy that can lag): a row
whose key the backup holds and the store does not is MISSING. A table's key
is its primary key, except training_sets, whose `id` each store mints anew on
every write (a re-logged exercise replaces its sets): a set row is missing
when the store holds no set at all for its exercise. A row added since the
backup is not a problem and is not reported; a changed value is not
compared. A table the backup has and the schema no longer has is skipped.

It only reads. It changes nothing, repairs nothing, and needs no caller day:
the backup's age is in hours. A backup older than STALE_HOURS is reported,
because the check then misses everything written since that backup.
Repairing a missing row is the owner's decision (restore it from the backup
with scripts/push_datastore_to_supabase.py, after he says yes).
"""
from __future__ import annotations

import gzip
import os
import sqlite3
import tempfile
import zlib
from datetime import date, datetime, timedelta, timezone

from services import backup, datastore_postgres, supabase_store

#: Older than this, the newest backup is reported as stale (two days).
STALE_HOURS = 48
#: The keys of the missing rows named per table, at most.
EXAMPLES = 5
#: The tables whose primary key is not the row's identity, and the column that is.
GROUP_KEY = {"training_sets": "exercise_id"}


class DataCheckFailed(RuntimeError):
    """The check could not read the backup or the store; nothing was checked."""


def table_key(table: str) -> str:
    return GROUP_KEY.get(table) or supabase_store.primary_key(table)


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def compare(backup_conn: sqlite3.Connection, store_conn: sqlite3.Connection,
            tables: list[str]) -> list[dict]:
    """One entry per table both copies have: its row counts, how many of the
    backup's rows the store no longer holds, and up to EXAMPLES of their keys."""
    in_backup, in_store = _tables(backup_conn), _tables(store_conn)
    out = []
    for table in tables:
        if table not in in_backup or table not in in_store:
            continue
        key = table_key(table)
        present = {str(k) for (k,) in store_conn.execute(f"SELECT DISTINCT {key} FROM {table}")}
        gone = [str(k) for (k,) in backup_conn.execute(f"SELECT {key} FROM {table}")
                if str(k) not in present]
        out.append({
            "table": table,
            "backup_rows": backup_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
            "store_rows": store_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
            "missing": len(gone),
            "examples": sorted(set(gone))[:EXAMPLES],
        })
    return out


def newest_backup(objects: list[dict]) -> tuple[str, date, datetime | None] | None:
    """The newest of our backups by the day in its name, with its upload time
    when Storage gives one. A name that is not one of ours is ignored."""
    best = None
    for obj in objects:
        name = str(obj.get("name") or "")
        if not (name.startswith(backup.PREFIX) and name.endswith(backup.SUFFIX)):
            continue
        try:
            day = date.fromisoformat(name[len(backup.PREFIX):-len(backup.SUFFIX)])
        except ValueError:
            continue
        stamp = obj.get("updated_at") or obj.get("created_at")
        try:
            when = datetime.fromisoformat(str(stamp).replace("Z", "+00:00")) if stamp else None
        except ValueError:
            when = None
        if best is None or day > best[1]:
            best = (name, day, when)
    return best


def is_stale(day: date, uploaded: datetime | None, now: datetime) -> bool:
    """Older than STALE_HOURS by its upload time; by its day when Storage gave
    no time (the day's end, so a backup is never called stale too early)."""
    if uploaded is not None:
        if uploaded.tzinfo is None:
            uploaded = uploaded.replace(tzinfo=timezone.utc)
        return now - uploaded > timedelta(hours=STALE_HOURS)
    end_of_day = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    return now - end_of_day > timedelta(hours=STALE_HOURS)


def _open_copy(data: bytes) -> tuple[sqlite3.Connection, str]:
    fd, path = tempfile.mkstemp(suffix=".db")
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    return sqlite3.connect(path), path


def run(store: supabase_store.SupabaseStore, now: datetime,
        storage: backup.Storage | None = None, pull=supabase_store.pull) -> dict:
    """The check, read-only: the newest backup against the store pulled now."""
    if now.tzinfo is None:
        raise ValueError("now must carry its time zone")
    try:
        return _run(store, now, storage or backup.Storage(store), pull)
    except (backup.StorageError, supabase_store.SupabaseError, OSError, EOFError,
            zlib.error, sqlite3.Error) as exc:
        raise DataCheckFailed(str(exc)[:200]) from exc


def _run(store, now: datetime, storage: backup.Storage, pull) -> dict:
    result = {"checked_at": now.astimezone(timezone.utc).isoformat(), "backup_name": None,
              "backup_day": None, "backup_stale": False, "missing_rows": 0, "tables": []}
    newest = newest_backup(storage.objects())
    if newest is None:
        return result
    name, day, uploaded = newest
    result.update(backup_name=name, backup_day=day.isoformat(),
                  backup_stale=is_stale(day, uploaded, now))
    tables = datastore_postgres.table_names(datastore_postgres.to_postgres())
    paths: list[str] = []
    conns: list[sqlite3.Connection] = []
    try:
        backup_conn, path = _open_copy(gzip.decompress(storage.download(name)))
        conns.append(backup_conn)
        paths.append(path)
        store_conn, path = _open_copy(b"")
        conns.append(store_conn)
        paths.append(path)
        pull(store, store_conn)
        result["tables"] = compare(backup_conn, store_conn, tables)
    finally:
        for conn in conns:
            conn.close()
        for path in paths:
            os.remove(path)
    result["missing_rows"] = sum(t["missing"] for t in result["tables"])
    return result
