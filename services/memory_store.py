"""
services/memory_store.py — an in-memory Supabase: PostgREST reduced to what
the Repository calls, over plain lists. No network.

Two users. The tests (tests/_record_store.py), which read back exactly what
was stored. And the sync rehearsal (api/healthapi/rehearsal.py, rebuild
Phase 9), which runs the engine's real sync chain on its own Cloud Run
service over made-up data and must never reach the real store: there
`latency_s` makes every call wait as long as a real one would, so the chain
is timed with the store's round trips in it (about 0.14 s a call, measured
against the real project on 2026-08-11), and `round_trips` counts them (not
`calls`: the tests' failing stores keep their own counter by that name).

Thread-safe, because supabase_store.pull reads several tables at once (the
daily backup's copy) and the engine serves requests on a thread pool.
"""
from __future__ import annotations

import threading
import time

from services import supabase_store


class MemoryStore:
    """PostgREST, reduced to what the repository calls, over plain lists.

    `fail_on` makes one operation or one table raise SupabaseError: an
    (op, table) pair, or a table for every operation on it."""

    def __init__(self, tables: dict | None = None, fail_on=None, latency_s: float = 0.0):
        self.tables = {t: [dict(r) for r in rows] for t, rows in (tables or {}).items()}
        self.log: list[tuple] = []
        self.fail_on = fail_on
        self.latency_s = latency_s
        self.round_trips = 0
        self._lock = threading.RLock()

    def round_trip(self) -> None:
        """One call's wait, and its count (the rehearsal's stand-in for the
        backup bucket waits through it too)."""
        with self._lock:
            self.round_trips += 1
        if self.latency_s > 0:
            time.sleep(self.latency_s)

    def _check(self, op, table):
        if self.fail_on in ((op, table), table):
            raise supabase_store.SupabaseError(f"boom on {op} {table}")

    def upsert(self, table, rows):
        self.round_trip()
        with self._lock:
            self._check("upsert", table)
            self.log.append(("upsert", table, len(rows)))
            pk = supabase_store.primary_key(table)
            current = {str(r[pk]): r for r in self.tables.get(table, [])}
            for r in rows:
                current[str(r[pk])] = {**current.get(str(r[pk]), {}), **r}
            self.tables[table] = list(current.values())
            return len(rows)

    def patch(self, table, pk, key, row):
        self.round_trip()
        with self._lock:
            self._check("patch", table)
            self.log.append(("patch", table, str(key)))
            n = 0
            for r in self.tables.get(table, []):
                if str(r.get(pk)) == str(key):
                    r.update(row)
                    n += 1
            return n

    def delete_where(self, table, column, value):
        self.round_trip()
        with self._lock:
            self._check("delete", table)
            self.log.append(("delete", table, str(value)))
            self.tables[table] = [r for r in self.tables.get(table, [])
                                  if str(r.get(column)) != str(value)]

    def insert(self, table, rows):
        self.round_trip()
        with self._lock:
            self._check("insert", table)
            self.log.append(("insert", table, len(rows)))
            self.tables.setdefault(table, []).extend(dict(r) for r in rows)
            return len(rows)

    def select_all(self, table, order=""):
        self.round_trip()
        with self._lock:
            return [dict(r) for r in self.tables.get(table, [])]

    def select_value(self, table, where, column):
        self.round_trip()
        col, _, value = where.partition("=eq.")
        with self._lock:
            for r in self.tables.get(table, []):
                if str(r.get(col)) == value:
                    return r.get(column)
        return None
