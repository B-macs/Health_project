"""
services/clients/datastore_reader.py — a read-only SQLite stand-in for a
Google Sheets worksheet.

When Config.datastore_path is set, services/repository.py hands back an
OfflineWorksheet instead of opening the real tab, so every read is served
from the local datastore (services/datastore.py) and the process makes NO
Google API call at all — not a smaller number of them, none, including the
service-account auth handshake. That is the point: the Sheets quota is 60
reads+writes per minute per user, and an afternoon of iterating on the Sleep
drill-down exhausts it long before the logic is right.

Deliberately duck-typed against gspread's Worksheet rather than wired in
behind a new abstraction. `.title` and `.get_all_records()` are the entire
surface repository.py reads through, so matching those two makes every
existing call site — `_read_records`, `sheets.get_worksheet_records`, and
the two places that call `.get_all_records()` straight off the worksheet —
work unmodified. No read path had to learn that offline mode exists.

Two fidelity rules, both load-bearing:

  * NULL is returned as "" — services/datastore.py's _insert_rows normalizes
    a blank Sheets cell to NULL on the way in, and this reverses it on the
    way out. Without it an offline row would carry None where a live row
    carries "", and every `if row.get(x) == ""` in the codebase would take
    the other branch offline than it does live.
  * `numericise_ignore` is accepted and ignored, which is correct rather
    than lazy. gspread's numericising happens when the CELL is read, so the
    datastore already holds the post-numericise value: a digit-coded
    hypnogram was exempted at build time and stored as TEXT, a real number
    was coerced at build time and stored as a number. SQLite's type affinity
    round-trips both exactly (a declared-INTEGER column holding gspread's
    'TRUE' keeps it as text). Re-applying the rule here would be the one
    thing that could corrupt them.

WRITES RAISE. Anything that is not a read — find/update/append_row/resize —
hits __getattr__ and raises DatastoreReadOnlyError naming the method. A
silent no-op would be far worse than a crash: the caller would believe a
sync had persisted, and the datastore is a snapshot, not a write target.
Reading local while writing live would be worse still.
"""

from __future__ import annotations

import sqlite3


class DatastoreReadOnlyError(RuntimeError):
    """Raised when offline mode is asked to do anything but read. Never
    caught internally — an attempted write against a read-only snapshot is
    a bug in the caller, not a condition to degrade around."""


def connect(path: str) -> sqlite3.Connection:
    """Opens the datastore read-only, so a bug that reaches a write path
    fails at SQLite as well as at OfflineWorksheet. check_same_thread=False
    because Streamlit serves reruns from a worker thread while the
    Repository is cached across them (@st.cache_resource); reads are the
    only operation and SQLite serializes them internally."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


class OfflineWorksheet:
    """One datastore table, wearing enough of gspread's Worksheet interface
    to be read through unchanged."""

    def __init__(self, conn: sqlite3.Connection, title: str, table: str):
        self.title = title
        self._conn = conn
        self._table = table

    def get_all_records(self, numericise_ignore: list | None = None,
                        expected_headers: list | None = None) -> list[dict]:
        """Every row in the backing table, as dicts keyed by column name —
        the same shape gspread returns for the live tab. Both keyword
        arguments are accepted for signature compatibility and ignored; see
        the module docstring for why that is the correct behavior for
        numericise_ignore rather than an omission.

        A table missing from the datastore returns [] — the same thing a
        live tab that exists but holds no data rows returns. This is the one
        place a missing table is tolerated rather than raised: a datastore
        built before a tab existed should read as "no rows yet", exactly as
        the empty tab itself would, instead of crashing a page that handles
        emptiness fine. The build script's own row-count output is where a
        genuinely missing table is meant to be noticed."""
        if not table_exists(self._conn, self._table):
            return []
        rows = self._conn.execute(f'SELECT * FROM "{self._table}"').fetchall()
        return [{k: ("" if r[k] is None else r[k]) for k in r.keys()} for r in rows]

    def __repr__(self) -> str:
        return f"<OfflineWorksheet {self.title!r} -> {self._table}>"

    def __getattr__(self, name: str):
        """Every non-read worksheet operation lands here, because none of
        them are defined above. Dunders are re-raised as AttributeError so
        copy/pickle/inspect probing behaves normally instead of blowing up
        with a write error."""
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        raise DatastoreReadOnlyError(
            f"Worksheet.{name}() was called on the offline datastore "
            f"(tab {self.title!r}). Offline mode is read-only: unset "
            f"datastore_path / HEALTH_DATASTORE_PATH to run against live "
            f"Google Sheets, or rebuild the snapshot with "
            f"`python scripts/build_datastore.py`."
        )
