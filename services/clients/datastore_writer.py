"""
services/clients/datastore_writer.py — applying a written row to the LOCAL
datastore, so the read cache is correct the instant a write happens.

THE PROBLEM THIS SOLVES. Reads from the local SQLite datastore cost 32 ms
against 8,884 ms live, so a hosted deployment wants to serve them from there.
But clients/datastore_reader.py's own docstring calls reading a snapshot while
writing live "worse still" than either alternative, and it is right: a stale
cache plus live writes means a session is logged, the next page reads a cache
that has never heard of it, and strain, ACWR and tomorrow's prescription are
computed from data that is already wrong. No error, and the numbers look
plausible.

So the cache is WRITTEN THROUGH rather than merely refreshed. Every write the
app makes lands here synchronously, in the same breath as the backend write,
and the next read sees it.

WHY THIS IS CHEAP: the rows already exist. Repository fans every write into
supabase_store.OUTBOX in datastore-row shape — the Sheets seam, the Notion
seam and the bulk-rewrite seam all produce them — so this applies the SAME
rows to a second sink. No new mapping, and nothing that can disagree with what
the mirror sends.

THE THREE MODES MIRROR POSTGREST'S EXACTLY, deliberately, because the two
sinks must not diverge:

  UPSERT   INSERT ... ON CONFLICT(pk) DO UPDATE SET <only the given columns>.
           Partial rows are the normal case (a Notion update writes four
           columns), and a plain INSERT OR REPLACE would NULL every column not
           supplied — the local-cache twin of the orphan-row hazard that made
           partial writes use PATCH against Postgres.
  PATCH    UPDATE ... WHERE pk = ?. Changes nothing when the row is absent,
           which is the point: it must never invent a row from four columns.
  REPLACE  DELETE by parent key, then INSERT. For training_sets, whose key is
           a surrogate. An EMPTY list still deletes — it means the exercise
           now has no sets.

WAL, and one connection per Repository. The background sync thread writes
while the Streamlit script thread reads (key rule 12), and WAL is what lets a
reader proceed during a write instead of seeing "database is locked". A
busy_timeout covers writer-vs-writer, which is rare here because writes are
short and the sync chain is serialised by BackgroundSyncRunner's lock.
"""

from __future__ import annotations

import sqlite3

#: How long a blocked writer waits before raising. Writes here are single-row
#: and sub-millisecond; anything approaching this is a real problem, not
#: contention.
BUSY_TIMEOUT_MS = 5000


class DatastoreWriteError(RuntimeError):
    """Raised when a row cannot be applied to the local cache.

    Never swallowed by the caller the way a Supabase flush failure is. A
    failed mirror leaves a replica behind; a failed cache write leaves the
    thing the app READS FROM disagreeing with the system of record, and the
    next page renders a number that is quietly wrong.
    """


def connect_rw(path: str) -> sqlite3.Connection:
    """Open the datastore read-WRITE.

    check_same_thread=False for the same reason datastore_reader.connect uses
    it: Streamlit serves reruns from a worker thread while the Repository is
    cached across them, and the background sync runs on its own thread.
    """
    conn = sqlite3.connect(path, check_same_thread=False,
                           timeout=BUSY_TIMEOUT_MS / 1000)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def upsert(conn: sqlite3.Connection, table: str, pk: str, row: dict) -> None:
    """Insert, or update ONLY the supplied columns.

    `INSERT OR REPLACE` would be wrong and quietly so: it replaces the whole
    row, so a four-column Notion update would blank the other twenty.
    """
    if not row:
        return
    cols = list(row)
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != pk)
    sql = (f'INSERT INTO "{table}" ({", ".join(cols)}) VALUES ({placeholders}) '
           f'ON CONFLICT({pk}) DO UPDATE SET {updates}' if updates else
           f'INSERT INTO "{table}" ({", ".join(cols)}) VALUES ({placeholders}) '
           f'ON CONFLICT({pk}) DO NOTHING')
    conn.execute(sql, [row[c] for c in cols])


def patch(conn: sqlite3.Connection, table: str, pk: str, key, row: dict) -> int:
    """Update an existing row only. Returns rows changed (0 or 1)."""
    cols = [c for c in row if c != pk]
    if not cols:
        return 0
    sets = ", ".join(f"{c}=?" for c in cols)
    cur = conn.execute(f'UPDATE "{table}" SET {sets} WHERE {pk}=?',
                       [row[c] for c in cols] + [key])
    return cur.rowcount


def replace_children(conn: sqlite3.Connection, table: str, parent_column: str,
                     parent_key, rows: list[dict]) -> None:
    """Delete this parent's rows, then insert the new set.

    The delete runs even when `rows` is empty — that means the parent now has
    no children, and skipping it would leave the previous write's rows
    attached forever.
    """
    conn.execute(f'DELETE FROM "{table}" WHERE {parent_column}=?', (parent_key,))
    if not rows:
        return
    cols = list(rows[0])
    placeholders = ", ".join("?" for _ in cols)
    conn.executemany(
        f'INSERT INTO "{table}" ({", ".join(cols)}) VALUES ({placeholders})',
        [[r.get(c) for c in cols] for r in rows],
    )
