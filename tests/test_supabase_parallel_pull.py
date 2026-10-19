"""supabase_store.pull fetches the tables in parallel and writes them in order.

The hosted engine copies every table at each cold start, and Cloud Run refuses
a request whose instance takes too long to start (2026-10-19). Fetching four
tables at a time took the copy from 5.9 s to 1.5 s against the real project.
These pin that the fetches really overlap, that the rows land as fetched, and
that one failed fetch still leaves no half-filled copy. No network.
"""

from __future__ import annotations

import sqlite3
import threading

import pytest

from services import supabase_store as ss


def test_the_tables_are_fetched_at_the_same_time():
    # Two fetches must be in flight together, or the barrier times out.
    barrier = threading.Barrier(2, timeout=5)

    class _Store:
        def select_all(self, table):
            barrier.wait()
            return [{"key": "k", "value": table, "updated": "2026-10-19"}] if table == "config" else []

    conn = sqlite3.connect(":memory:")
    counts = ss.pull(_Store(), conn, ["config", "metrics_history"])
    assert counts == {"config": 1, "metrics_history": 0}
    assert conn.execute("SELECT key, value FROM config").fetchall() == [("k", "config")]


def test_a_slow_first_table_still_lands_with_its_own_rows():
    first_done = threading.Event()

    class _Store:
        def select_all(self, table):
            if table == "config":
                first_done.wait(timeout=5)          # finishes after the second table
                return [{"key": "k", "value": "v", "updated": "2026-10-19"}]
            first_done.set()
            return [{"date": "2026-10-19", "readiness_score": 70.0}]

    conn = sqlite3.connect(":memory:")
    assert ss.pull(_Store(), conn, ["config", "metrics_history"]) == {
        "config": 1, "metrics_history": 1}
    assert conn.execute("SELECT date FROM metrics_history").fetchall() == [("2026-10-19",)]


def test_one_failed_fetch_leaves_every_table_empty():
    class _Store:
        def select_all(self, table):
            if table == "metrics_history":
                raise ss.SupabaseError("boom")
            return [{"key": "k", "value": "v", "updated": "2026-10-19"}]

    conn = sqlite3.connect(":memory:")
    with pytest.raises(ss.SupabaseError):
        ss.pull(_Store(), conn, ["config", "metrics_history"])
    assert conn.execute("SELECT COUNT(*) FROM config").fetchone()[0] == 0
