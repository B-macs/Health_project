"""
services/backup.py — a daily copy of Supabase, kept in Supabase Storage.

WHY. Since 2026-10-09 Supabase is the only store, and the Free plan takes no
backups ("We automatically back up all Pro, Team, and Enterprise Plan
projects", supabase.com/docs/guides/platform/backups — checked that day; free
projects are told to export their own). Notion and Google Sheets hold
everything up to the switch as a frozen archive, and nothing after it.

WHAT. Once a day the hosted app's sync chain (Repository.
backup_supabase_if_due) pulls every table from Supabase into a fresh SQLite
file — the record itself, not the app's local copy, which can miss rows
another process wrote — compresses it (7.4 MB -> 1.1 MB on 2026-10-09), and
uploads it to a PRIVATE Storage bucket as health-YYYY-MM-DD.db.gz. Copies
older than KEEP_DAYS are deleted. 30 copies are ~33 MB of the free 1 GB.

WHAT IT GUARDS AGAINST. A bad write, a wrong delete, a repair gone wrong —
every data problem this project has actually had. It is in the same project,
so it does NOT guard against losing the project itself; for that, keep an
off-site copy now and then with scripts/backup_supabase.py.

RESTORE. Download a copy (dashboard -> Storage -> health-backups), gunzip it,
then: python scripts/push_datastore_to_supabase.py --db <file> --overwrite-record
"""
from __future__ import annotations

import gzip
import json
import os
import sqlite3
import tempfile
import urllib.error
import urllib.request
from datetime import date, timedelta

from services import supabase_store

BUCKET = "health-backups"
KEEP_DAYS = 30
PREFIX = "health-"
SUFFIX = ".db.gz"


def object_name(day: date) -> str:
    return f"{PREFIX}{day.isoformat()}{SUFFIX}"


def _http(method: str, url: str, headers: dict, data: bytes | None = None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


class StorageError(RuntimeError):
    pass


class Storage:
    """The three Storage calls a backup needs, over the same server key."""

    def __init__(self, store: supabase_store.SupabaseStore, http=_http):
        self._store = store
        self._http = http

    def _headers(self, content_type: str = "application/json", **extra) -> dict:
        return self._store._headers({"Content-Type": content_type, **extra})

    def ensure_bucket(self) -> None:
        status, body = self._http(
            "POST", f"{self._store.url}/storage/v1/bucket", self._headers(),
            json.dumps({"id": BUCKET, "name": BUCKET, "public": False}).encode())
        # 200 created; 400/409 with "already exists" means it is there.
        if status >= 300 and b"exist" not in body.lower():
            raise StorageError(f"create bucket {BUCKET}: HTTP {status} {body[:200]!r}")

    def upload(self, name: str, data: bytes) -> None:
        status, body = self._http(
            "POST", f"{self._store.url}/storage/v1/object/{BUCKET}/{name}",
            self._headers("application/gzip", **{"x-upsert": "true"}), data)
        if status >= 300:
            raise StorageError(f"upload {name}: HTTP {status} {body[:200]!r}")

    def objects(self) -> list[dict]:
        """Every object in the bucket, as Storage lists it (name, updated_at, ...)."""
        status, body = self._http(
            "POST", f"{self._store.url}/storage/v1/object/list/{BUCKET}", self._headers(),
            json.dumps({"prefix": "", "limit": 1000}).encode())
        if status >= 300:
            raise StorageError(f"list {BUCKET}: HTTP {status} {body[:200]!r}")
        return [o for o in json.loads(body or b"[]") if o.get("name")]

    def names(self) -> list[str]:
        return [o["name"] for o in self.objects()]

    def download(self, name: str) -> bytes:
        """One copy's bytes (the daily data check reads the newest; it changes nothing)."""
        status, body = self._http(
            "GET", f"{self._store.url}/storage/v1/object/{BUCKET}/{name}",
            self._store._headers({"Accept": "*/*"}))
        if status >= 300:
            raise StorageError(f"download {name}: HTTP {status} {body[:200]!r}")
        return body

    def delete(self, names: list[str]) -> None:
        if not names:
            return
        status, body = self._http(
            "DELETE", f"{self._store.url}/storage/v1/object/{BUCKET}", self._headers(),
            json.dumps({"prefixes": names}).encode())
        if status >= 300:
            raise StorageError(f"delete old copies: HTTP {status} {body[:200]!r}")


def snapshot(store: supabase_store.SupabaseStore) -> bytes:
    """Every table, pulled from Supabase into a fresh SQLite file, gzipped."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        conn = sqlite3.connect(path)
        try:
            supabase_store.pull(store, conn)
        finally:
            conn.close()
        with open(path, "rb") as fh:
            return gzip.compress(fh.read(), 6)
    finally:
        os.remove(path)


def expired(names: list[str], today: date, keep_days: int = KEEP_DAYS) -> list[str]:
    """Copies older than keep_days. A name that is not one of ours is never
    touched."""
    cutoff = today - timedelta(days=keep_days)
    out = []
    for name in names:
        if not (name.startswith(PREFIX) and name.endswith(SUFFIX)):
            continue
        try:
            day = date.fromisoformat(name[len(PREFIX):-len(SUFFIX)])
        except ValueError:
            continue
        if day < cutoff:
            out.append(name)
    return out


def missing_days(names: list[str], today: date, days: int = 7) -> list[date]:
    """The days among the `days` before `today` with no copy of ours (the check
    before the switch-over, rebuild Phase 9: a backup on each of the last 7 days).
    Today is left out: its copy is made by the day's first sync."""
    have = set(names)
    return [today - timedelta(days=back) for back in range(days, 0, -1)
            if object_name(today - timedelta(days=back)) not in have]


def run(store: supabase_store.SupabaseStore, today: date,
        storage: Storage | None = None, take=snapshot) -> str:
    """Take today's copy, upload it, delete expired ones; returns its name."""
    storage = storage or Storage(store)
    data = take(store)
    storage.ensure_bucket()
    name = object_name(today)
    storage.upload(name, data)
    storage.delete(expired(storage.names(), today))
    return name
