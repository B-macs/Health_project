"""
services/supabase_store.py -- pushes the local SQLite datastore into the
Supabase (PostgreSQL) project, and reads it back to prove the copy is faithful.

STEP 2 OF THE CUTOVER. Step 1 created the 21 tables
(services/datastore_postgres.py). Nothing in the live app reads from Postgres
yet -- this exists to get real data in and to check the schema is actually
right, which a load of 2,900 real rows answers and no amount of reading the
DDL does.

NO NEW DEPENDENCY. Supabase's Data API is PostgREST, which is plain HTTP over
JSON, so this uses urllib -- the same choice voice_training/voxplot/storage/
supabase.py already made in this repo. Adding psycopg would buy a nicer API in
exchange for a build-tooling dependency and a second credential (the database
password), neither of which this needs.

THE ACTUAL RISK IS TYPES, not transport. SQLite stores what it is given:
gspread hands back "" for a blank cell, and the offline datastore preserves
that verbatim because reading a hypnogram back as a number is unrecoverable
(see clients/datastore_reader.py). PostgreSQL will not accept "" in a DOUBLE
PRECISION column -- it is an error, not a coercion. So every value crosses
through `_coerce`, and the rule is deliberate: an empty string becomes NULL in
a numeric column, because "no reading" is what a blank cell has always meant
here, while in a TEXT column it stays "" -- there, blank and absent are
genuinely different and flattening them would rewrite history.

The source is the SQLite file, not Repository. datastore.db is already a full
copy, so pushing from it costs zero Notion/Sheets quota and makes the
comparison a true round trip: the same rows, through Postgres, back out.
"""
from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from services import datastore_postgres

#: Parents before children. training_sets references training_exercises, which
#: references training_sessions, and those foreign keys are ENFORCED in
#: Postgres (unlike SQLite, where they are documentation) -- so a child
#: inserted first is a hard error rather than an orphan row.
LOAD_ORDER = ("training_sessions", "training_exercises", "training_sets")

#: PostgREST accepts an array of objects as a bulk insert. 500 keeps a request
#: comfortably under the payload limit even for oura_sleep_periods, whose rows
#: carry whole hypnograms as strings.
BATCH = 500

_TIMEOUT = 60


class SupabaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadResult:
    table: str
    source_rows: int
    loaded_rows: int
    #: The table is in the schema but not in this SQLite snapshot — a
    #: datastore built before the table was added. It is SKIPPED ENTIRELY,
    #: truncate included; see push().
    source_missing: bool = False

    @property
    def ok(self) -> bool:
        return not self.source_missing and self.source_rows == self.loaded_rows


class SupabaseStore:
    """Thin PostgREST wrapper. Holds the secret key; never logs it."""

    def __init__(self, url: str, secret_key: str):
        if not url or not secret_key:
            raise SupabaseError(
                "Supabase is not configured — set SUPABASE_URL and "
                "SUPABASE_SECRET_KEY (see services/config.py)."
            )
        self.url = url.rstrip("/")
        self._key = secret_key

    def _headers(self, extra: dict | None = None) -> dict:
        h = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        h.update(extra or {})
        return h

    def _request(self, method: str, path: str, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            f"{self.url}/rest/v1/{path}", data=data, method=method,
            headers=self._headers(headers),
        )
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
                raw = r.read()
                return r.headers, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:400]
            # The key never appears in the message — only the path and Postgres'
            # own complaint, which is what actually says what went wrong.
            raise SupabaseError(f"{method} {path} → HTTP {exc.code}: {detail}") from None

    # ─── reads ───────────────────────────────────────────────────────────

    def count(self, table: str) -> int:
        headers, _ = self._request(
            "GET", f"{table}?select=*&limit=1",
            headers={"Prefer": "count=exact", "Range": "0-0"},
        )
        content_range = headers.get("Content-Range", "")
        return int(content_range.split("/")[-1]) if "/" in content_range else 0

    def select(self, table: str, order: str = "", limit: int = 1000) -> list[dict]:
        q = f"{table}?select=*&limit={limit}"
        if order:
            q += f"&order={urllib.parse.quote(order)}"
        _headers, rows = self._request("GET", q)
        return rows or []

    def select_all(self, table: str, order: str = "") -> list[dict]:
        """EVERY row, following Range pages.

        select() takes a limit and is honest about it; this one must not,
        because it backs the pull into the local datastore and a silently
        truncated table there is a read cache that is quietly missing history.
        Supabase caps a single response (max-rows, 1000 by default), so a
        table over that ceiling comes back short with no error at all — the
        same shape of failure as a throttled Sheets read.
        """
        # Paging by offset REQUIRES a total order. Without one Postgres may
        # return rows in any order per request, so page 2 can repeat or skip
        # what page 1 held — and the result still looks like a full table.
        order = order or primary_key(table)
        rows: list[dict] = []
        while True:
            q = (f"{table}?select=*&limit={BATCH}&offset={len(rows)}"
                 f"&order={urllib.parse.quote(order)}")
            _headers, page = self._request("GET", q)
            if not page:
                return rows
            rows.extend(page)
            if len(page) < BATCH:
                return rows

    def select_value(self, table: str, where: str, column: str):
        """One column of the first row matching a PostgREST filter, or None.

        Separate from select() because select() builds its own `?select=`;
        handing it a string that already carried a filter produced a URL with
        two `?` and a parse error from PostgREST.
        """
        _headers, rows = self._request(
            "GET", f"{table}?{where}&select={column}&limit=1")
        return rows[0][column] if rows else None

    # ─── writes ──────────────────────────────────────────────────────────

    def truncate(self, table: str) -> None:
        """Delete every row.

        PostgREST REFUSES an unfiltered DELETE — a safety feature, and one
        worth not defeating with a wildcard. Each table gets an always-true
        filter on its own primary key, so an unknown table raises here rather
        than silently deleting nothing and leaving a half-replaced copy that
        looks loaded.
        """
        try:
            where = _ANY_ROW_FILTER[table]
        except KeyError:
            raise SupabaseError(
                f"no delete filter for {table!r} — add one to _ANY_ROW_FILTER, "
                f"or a push would silently leave its old rows in place"
            ) from None
        self._request("DELETE", f"{table}?{where}")

    def upsert(self, table: str, rows: list[dict]) -> int:
        """Insert-or-update on the primary key, in batches.

        `resolution=merge-duplicates` is PostgREST's ON CONFLICT DO UPDATE.
        This is what lets the live mirror run repeatedly without truncating
        anything — truncate-then-insert leaves a window in which the table is
        EMPTY, which is tolerable for a one-shot migration and not for
        something that runs on a background cadence beside a user's session.

        A partial column set is deliberate and safe: an existing row has only
        the supplied columns updated, and a new row takes NULL for the rest,
        which is exactly what the sheet row it mirrors holds. Every row in one
        request must carry the SAME keys, which is true because they all come
        from one tab's header.
        """
        sent = 0
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i + BATCH]
            self._request("POST", table, body=chunk, headers={
                "Prefer": "resolution=merge-duplicates,return=minimal"})
            sent += len(chunk)
        return sent

    def insert(self, table: str, rows: list[dict]) -> int:
        """Bulk insert in batches. Returns the number of rows sent."""
        sent = 0
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i + BATCH]
            self._request("POST", table, body=chunk,
                          headers={"Prefer": "return=minimal"})
            sent += len(chunk)
        return sent


#: PostgREST requires a WHERE clause on DELETE. Each table gets a filter on a
#: column that is NOT NULL for every row — its primary key.
_ANY_ROW_FILTER = {
    "training_sets": "id=gte.0",
    "training_exercises": "exercise_id=neq.__none__",
    "training_sessions": "session_id=neq.__none__",
    "readiness_checkins": "date=neq.__none__",
    "garmin_daily": "date=neq.__none__",
    "garmin_activities": "activity_id=neq.__none__",
    "session_hr": "date=neq.__none__",
    "oura_daily": "date=neq.__none__",
    "oura_workouts": "workout_id=neq.__none__",
    "oura_sleep_periods": "sleep_id=neq.__none__",
    "garmin_sleep_stages": "date=neq.__none__",
    "sleep_fusion": "date=neq.__none__",
    "oura_sessions": "session_id=neq.__none__",
    "oura_rest_mode": "rest_mode_id=neq.__none__",
    "biometric_blend": "date=neq.__none__",
    "metrics_history": "date=neq.__none__",
    "wake_time_adjustments": "date=neq.__none__",
    "weekly_rollup": "week_start=neq.__none__",
    "sheet1_legacy_biometrics": "date=neq.__none__",
    "notion_biometrics": "date=neq.__none__",
    "config": "key=neq.__none__",
    "datastore_meta": "key=neq.__none__",
}


# ─── SQLite → Postgres value coercion ────────────────────────────────────

def primary_key(table: str, ddl: str | None = None) -> str:
    """The table's primary-key column, read off the schema.

    Used to give select_all a total order. Derived rather than listed beside
    _ANY_ROW_FILTER because a second hand-maintained table-to-column map is
    the duplication this whole schema-derivation exists to avoid.
    """
    import re
    ddl = ddl if ddl is not None else datastore_postgres.to_postgres()
    m = re.search(rf"CREATE TABLE {table} \((.*?)\n\);", ddl, re.S)
    if not m:
        raise SupabaseError(f"no CREATE TABLE for {table!r}")
    for line in m.group(1).splitlines():
        code, _ = datastore_postgres._split_code_and_comment(line)
        if "PRIMARY KEY" in code.upper():
            return code.split()[0]
    raise SupabaseError(f"{table} has no PRIMARY KEY to page by")


def numeric_columns(table: str, ddl: str | None = None) -> set[str]:
    """Columns Postgres will treat as numbers, so "" has to become NULL."""
    ddl = ddl if ddl is not None else datastore_postgres.to_postgres()
    import re
    m = re.search(rf"CREATE TABLE {table} \((.*?)\n\);", ddl, re.S)
    if not m:
        return set()
    out = set()
    for line in m.group(1).splitlines():
        code, _ = datastore_postgres._split_code_and_comment(line)
        code = code.strip().rstrip(",")
        if not code:
            continue
        parts = code.split()
        if len(parts) >= 2 and parts[1].upper() in ("DOUBLE", "BIGINT", "NUMERIC"):
            out.add(parts[0])
    return out


#: gspread hands booleans back as the STRINGS 'TRUE'/'FALSE', and the offline
#: datastore preserves them verbatim (clients/datastore_reader.py pins that as
#: fidelity). SQLite stores them happily in an INTEGER column because it is
#: loosely typed; PostgreSQL rejects them outright.
#:
#: Found by loading real data, not by reading the schema: 415 rows of
#: oura_sleep_periods.low_battery_alert plus both of garmin_sleep_stages'
#: boolean columns. 1/0 is the faithful mapping rather than a convenience —
#: these columns are declared BIGINT with comments that call them booleans,
#: and readiness_checkins already stores its booleans as 0/1.
_BOOL_STRINGS = {"TRUE": 1, "FALSE": 0, "True": 1, "False": 0,
                 "true": 1, "false": 0}


def coerce_row(row: dict, numeric: set[str]) -> dict:
    """One SQLite row as PostgreSQL will accept it.

    Two transformations, both confined to NUMERIC columns:

      ""            -> NULL. A blank cell has always meant "no reading" here
                      (gspread returns "" for one, and the offline datastore
                      keeps it verbatim), so NULL is the faithful reading.
      TRUE / FALSE  -> 1 / 0. See _BOOL_STRINGS.

    In a TEXT column both are LEFT ALONE. There, blank and absent are
    genuinely different — a stored empty hypnogram is not the same as never
    having recorded one — and collapsing them would rewrite history. A literal
    "TRUE" in a text column is a value, not a boolean.
    """
    out = {}
    for k, v in row.items():
        if k in numeric and isinstance(v, str):
            s = v.strip()
            if s == "":
                out[k] = None
                continue
            if s in _BOOL_STRINGS:
                out[k] = _BOOL_STRINGS[s]
                continue
        out[k] = v
    return out


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def pull(store: SupabaseStore, conn: sqlite3.Connection,
         tables: list[str] | None = None, progress=None) -> dict[str, int]:
    """Rebuild the local SQLite datastore FROM Supabase — the reverse of
    push(), and the piece that makes the read cache independent of Notion and
    Google Sheets.

    This is the direction that matters once Supabase is the system of record.
    Reads must stay local: measured 2026-08-11, a single PostgREST round trip
    costs ~136 ms whatever the table's size (a 2-row table times the same as a
    600-row one, so it is latency, not payload), which puts a full 22-table
    read at 4,284 ms against 32 ms from SQLite. Serving the app straight from
    Postgres would be 113x slower than the local path. So Postgres holds the
    truth and SQLite serves the reads, refreshed by this function.

    Wholesale replace, like rebuild(): DROP+CREATE from the same schema file,
    so the two paths cannot produce differently-shaped databases.
    """
    ddl = datastore_postgres.to_postgres()
    all_tables = tables or datastore_postgres.table_names(ddl)

    conn.executescript(
        (datastore_postgres.SCHEMA_PATH).read_text(encoding="utf-8"))
    conn.execute("BEGIN")
    try:
        counts: dict[str, int] = {}
        for table in all_tables:
            rows = store.select_all(table)
            if rows:
                cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
                # training_sets.id is assigned by each store's own identity
                # column and carries no meaning; let SQLite mint its own, the
                # same way rebuild() does.
                if table == "training_sets":
                    cols = [c for c in cols if c != "id"]
                placeholders = ", ".join(f":{c}" for c in cols)
                conn.executemany(
                    f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
                    [{c: r.get(c) for c in cols} for r in rows],
                )
            counts[table] = len(rows)
            if progress:
                progress(table, len(rows))
        conn.commit()
        return counts
    except Exception:
        conn.rollback()
        raise


def rows_from_sqlite(conn: sqlite3.Connection, table: str) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]


def push(conn: sqlite3.Connection, store: SupabaseStore,
         tables: list[str] | None = None, progress=None) -> list[LoadResult]:
    """Replace the Supabase contents with the SQLite datastore's.

    Wholesale replace, matching services/datastore.py's own contract for the
    SQLite copy: this data is a regenerable projection of Notion and Sheets,
    not a system of record, so there is nothing to merge. That stops being
    true the day Postgres becomes the write path, at which point this becomes
    a migration rather than a push.

    Children are deleted before parents and inserted after them — the foreign
    keys are enforced here, unlike in SQLite.

    A table in the schema but ABSENT from this snapshot is skipped whole —
    not truncated, not inserted — and reported as source_missing. Truncating
    it would delete live Supabase rows because the LOCAL copy is out of date,
    which is a stale snapshot destroying good data. Rebuild with
    scripts/build_datastore.py and push again.
    """
    ddl = datastore_postgres.to_postgres()
    all_tables = tables or datastore_postgres.table_names(ddl)
    ordered = ([t for t in LOAD_ORDER if t in all_tables]
               + [t for t in all_tables if t not in LOAD_ORDER])
    present = [t for t in ordered if table_exists(conn, t)]
    missing = [t for t in ordered if t not in present]

    # PREFLIGHT, before a single DELETE. A table the schema declares but the
    # project has not been given yet 404s on truncate — and discovering that
    # halfway through has already emptied whatever came earlier in the order,
    # which leaves Supabase worse than not running at all. Measured: a first
    # attempt wiped config and datastore_meta before failing on the new
    # table. Reading is free; deleting is not.
    absent_remotely = []
    for table in present:
        try:
            store.count(table)
        except SupabaseError as exc:
            if "PGRST205" in str(exc) or "404" in str(exc):
                absent_remotely.append(table)
            else:
                raise
    if absent_remotely:
        raise SupabaseError(
            f"these tables do not exist in the Supabase project yet: "
            f"{', '.join(absent_remotely)}. Nothing was deleted. Apply "
            f"services/datastore_schema_postgres.sql (or just the missing "
            f"CREATE TABLE statements) in the SQL editor, then push again."
        )

    for table in reversed(present):        # children first
        store.truncate(table)

    results = [LoadResult(t, 0, 0, source_missing=True) for t in missing]
    for table in present:
        rows = rows_from_sqlite(conn, table)
        numeric = numeric_columns(table, ddl)
        payload = [coerce_row(r, numeric) for r in rows]
        # training_sets.id is GENERATED ALWAYS — Postgres rejects a supplied
        # value, and the surrogate key carries no meaning worth preserving.
        if table == "training_sets":
            payload = [{k: v for k, v in r.items() if k != "id"} for r in payload]
        sent = store.insert(table, payload) if payload else 0
        results.append(LoadResult(table, len(rows), sent))
        if progress:
            progress(results[-1])
    return results
