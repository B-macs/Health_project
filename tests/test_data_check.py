"""The daily data check (services/data_check.py, rebuild Phase 4).

It answers one question: has the store lost rows? It compares the newest
backup with the store pulled now, and reports the backup's rows whose key
the store no longer holds. What it pins:

- a row the store lost is reported, with its key; a row added since the
  backup is not a problem;
- a training set is missing only when its exercise has no set at all now (a
  re-logged exercise gets new set ids, and that is not a loss);
- the newest backup is chosen by the day in its name, a foreign file is
  ignored, and a backup older than two days is called stale;
- with no backup there is nothing to compare, and the answer says so;
- a failed read becomes one DataCheckFailed, and the check never writes.

Made-up rows only; no network (FakeStore stands in for Supabase).
"""
from __future__ import annotations

import gzip
import os
import sqlite3
import tempfile
from datetime import date, datetime, timedelta, timezone

import pytest

from services import backup, data_check, supabase_store
from tests._record_store import SCHEMA, FakeStore

NOW = datetime(2026, 10, 20, 6, 0, tzinfo=timezone.utc)


def _db(rows: dict[str, list[dict]]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    for table, items in rows.items():
        for item in items:
            cols = ", ".join(item)
            marks = ", ".join("?" for _ in item)
            conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(item.values()))
    conn.commit()
    return conn


def _gz(rows: dict[str, list[dict]]) -> bytes:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA)
        for table, items in rows.items():
            for item in items:
                cols = ", ".join(item)
                marks = ", ".join("?" for _ in item)
                conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(item.values()))
        conn.commit()
        conn.close()
        with open(path, "rb") as fh:
            return gzip.compress(fh.read())
    finally:
        os.remove(path)


def _ex(exercise_id: str, day: str = "2026-10-19") -> dict:
    return {"exercise_id": exercise_id, "session_id": f"{day}-s", "session_date": day,
            "movement_name": "Made-up lift"}


def _set(exercise_id: str, n: int) -> dict:
    return {"exercise_id": exercise_id, "set_num": n, "reps": 10, "weight": 20}


class FakeStorage:
    def __init__(self, objects: list[dict], files: dict[str, bytes], fail: bool = False):
        self._objects = objects
        self._files = files
        self.fail = fail
        self.downloaded: list[str] = []

    def objects(self) -> list[dict]:
        if self.fail:
            raise backup.StorageError("list health-backups: HTTP 500")
        return self._objects

    def download(self, name: str) -> bytes:
        self.downloaded.append(name)
        return self._files[name]


# ── comparing two copies ─────────────────────────────────────────────────────

def test_a_row_the_store_lost_is_reported_with_its_key():
    old = _db({"config": [{"key": "phases", "value": "[]"}, {"key": "current_stage", "value": "2"}]})
    now = _db({"config": [{"key": "phases", "value": "[]"}]})
    [row] = [t for t in data_check.compare(old, now, ["config"])]
    assert row == {"table": "config", "backup_rows": 2, "store_rows": 1, "missing": 1,
                   "examples": ["current_stage"]}


def test_a_row_added_since_the_backup_is_not_a_problem():
    old = _db({"config": [{"key": "phases", "value": "[]"}]})
    now = _db({"config": [{"key": "phases", "value": "[1]"}, {"key": "new", "value": "x"}]})
    [row] = data_check.compare(old, now, ["config"])
    assert row["missing"] == 0 and row["store_rows"] == 2


def test_sets_are_missing_only_when_their_exercise_has_none_left():
    old = _db({"training_exercises": [_ex("a"), _ex("b")],
               "training_sets": [_set("a", 1), _set("a", 2), _set("b", 1)]})
    # "a" was re-logged with one set (new set ids): not a loss. "b" lost every set.
    now = _db({"training_exercises": [_ex("a"), _ex("b")], "training_sets": [_set("a", 1)]})
    rows = {r["table"]: r for r in data_check.compare(old, now, ["training_exercises", "training_sets"])}
    assert rows["training_exercises"]["missing"] == 0
    assert rows["training_sets"]["missing"] == 1
    assert rows["training_sets"]["examples"] == ["b"]


def test_at_most_five_keys_are_named():
    old = _db({"config": [{"key": f"k{i}", "value": ""} for i in range(8)]})
    now = _db({})
    [row] = data_check.compare(old, now, ["config"])
    assert row["missing"] == 8 and len(row["examples"]) == data_check.EXAMPLES


def test_a_table_only_one_copy_has_is_skipped():
    old = _db({})
    now = _db({})
    old.execute("CREATE TABLE gone_table (k TEXT PRIMARY KEY)")
    assert data_check.compare(old, now, ["gone_table"]) == []


# ── choosing the backup ──────────────────────────────────────────────────────

def test_the_newest_backup_is_chosen_by_its_day_and_a_foreign_file_is_ignored():
    objects = [{"name": "health-2026-10-18.db.gz", "updated_at": "2026-10-18T07:00:00Z"},
               {"name": "health-2026-10-19.db.gz", "updated_at": "2026-10-19T07:00:00Z"},
               {"name": "notes.txt"}, {"name": "health-not-a-day.db.gz"}]
    name, day, when = data_check.newest_backup(objects)
    assert (name, day) == ("health-2026-10-19.db.gz", date(2026, 10, 19))
    assert when == datetime(2026, 10, 19, 7, 0, tzinfo=timezone.utc)
    assert data_check.newest_backup([{"name": "notes.txt"}]) is None


def test_a_backup_older_than_two_days_is_stale():
    day = date(2026, 10, 17)
    assert data_check.is_stale(day, NOW - timedelta(hours=49), NOW)
    assert not data_check.is_stale(day, NOW - timedelta(hours=47), NOW)
    # No upload time: judged from the end of its day, never too early.
    assert not data_check.is_stale(date(2026, 10, 18), None, NOW)
    assert data_check.is_stale(date(2026, 10, 16), None, NOW)


# ── the whole check ──────────────────────────────────────────────────────────

def test_the_check_compares_the_newest_backup_with_the_store_pulled_now():
    backup_rows = {"config": [{"key": "phases", "value": "[]"}, {"key": "lost", "value": "x"}],
                   "training_exercises": [_ex("a")], "training_sets": [_set("a", 1)]}
    storage = FakeStorage([{"name": "health-2026-10-19.db.gz", "updated_at": "2026-10-19T07:00:00Z"}],
                          {"health-2026-10-19.db.gz": _gz(backup_rows)})
    store = FakeStore({"config": [{"key": "phases", "value": "[]"}],
                       "training_exercises": [_ex("a")], "training_sets": [_set("a", 1)]})
    out = data_check.run(store, NOW, storage=storage)
    assert storage.downloaded == ["health-2026-10-19.db.gz"]
    assert out["backup_name"] == "health-2026-10-19.db.gz"
    assert out["backup_day"] == "2026-10-19"
    assert out["backup_stale"] is False
    assert out["missing_rows"] == 1
    assert [t["table"] for t in out["tables"] if t["missing"]] == ["config"]
    assert out["checked_at"] == "2026-10-20T06:00:00+00:00"
    # It only reads: the store saw no write of any kind.
    assert store.log == []


def test_with_no_backup_there_is_nothing_to_compare():
    out = data_check.run(FakeStore(), NOW, storage=FakeStorage([], {}))
    assert out["backup_name"] is None and out["tables"] == [] and out["missing_rows"] == 0


def test_a_failed_read_is_one_error_and_nothing_else():
    with pytest.raises(data_check.DataCheckFailed):
        data_check.run(FakeStore(), NOW, storage=FakeStorage([], {}, fail=True))
    storage = FakeStorage([{"name": "health-2026-10-19.db.gz"}], {"health-2026-10-19.db.gz": b"not gzip"})
    with pytest.raises(data_check.DataCheckFailed):
        data_check.run(FakeStore(), NOW, storage=storage)


def test_a_failed_pull_is_one_error():
    storage = FakeStorage([{"name": "health-2026-10-19.db.gz"}], {"health-2026-10-19.db.gz": _gz({})})

    def broken_pull(store, conn):
        raise supabase_store.SupabaseError("select config: HTTP 500")

    with pytest.raises(data_check.DataCheckFailed):
        data_check.run(FakeStore(), NOW, storage=storage, pull=broken_pull)


def test_the_time_must_carry_its_zone():
    with pytest.raises(ValueError):
        data_check.run(FakeStore(), datetime(2026, 10, 20, 6, 0), storage=FakeStorage([], {}))


def test_the_check_module_writes_nothing():
    """No call that writes: the check reads the backup and the store, and the
    temporary copies it makes are its own files."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(data_check))
    writes = {"upsert", "insert", "patch", "delete_where", "upload", "delete", "ensure_bucket"}
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert called & writes == set()
