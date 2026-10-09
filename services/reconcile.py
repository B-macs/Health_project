"""
services/reconcile.py — make Supabase hold exactly what Notion and Google
Sheets hold, before Supabase becomes the only store (2026-10-09).

Two SQLite snapshots with the datastore's own schema are compared table by
table on their primary keys:

  source  services/datastore.rebuild() over a Repository reading the LEGACY
          stores live (Notion and Sheets), i.e. what the record says;
  target  supabase_store.pull(), i.e. what Supabase holds.

Every row is one of: MISSING (in the source, not in Supabase), EXTRA (in
Supabase, not in the source), DIFFERENT (both, with a value that differs), or
equal. apply() makes Supabase match the source: missing and different rows are
written whole, extra rows are deleted, children before parents.

COMPARING VALUES, not representations. The two snapshots come through
different doors — gspread and Notion payloads on one side, PostgREST JSON on
the other — so 371 and 371.0 are the same number, "" and NULL are the same
blank (the mirror writes NULL for a blank, a push keeps "" in a text column),
'TRUE' in a numeric column is 1, and two JSON texts that parse to the same
list are the same value. Anything else that differs is reported.

training_sets has no natural key (its id is a surrogate each store mints), so
its rows are compared PER EXERCISE as ordered lists, and a difference replaces
that exercise's whole set list — the same delete-then-insert the mirror uses.

ONLY BEFORE THE SWITCH. Once the hosted app has run with Supabase as the
record (record_cache.RECORD_SINCE_KEY is set), Notion and Sheets are a frozen
archive and Supabase holds rows they never will; apply() would delete them.
The script refuses then, and so do the older Notion-to-Supabase tools.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

from services import supabase_store

#: Compared and written. datastore_meta describes a snapshot, not data.
SKIP_TABLES = frozenset({"datastore_meta"})

_SET_FIELDS = ("set_num", "reps", "weight", "rest", "tut", "velocity", "band_tier",
               "ts", "is_warmup", "rest_taken_seconds", "reps_left", "weight_left")

_BOOLS = {"TRUE": 1.0, "FALSE": 0.0, "True": 1.0, "False": 0.0,
          "true": 1.0, "false": 0.0}


@dataclass
class TableDiff:
    table: str
    source_rows: int = 0
    target_rows: int = 0
    missing: list = field(default_factory=list)     # keys only in the source
    extra: list = field(default_factory=list)       # keys only in Supabase
    different: list = field(default_factory=list)   # keys whose values differ
    examples: list = field(default_factory=list)    # (key, column, source, target)

    @property
    def clean(self) -> bool:
        return not (self.missing or self.extra or self.different)


def _as_number(v):
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if s in _BOOLS:
            return _BOOLS[s]
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _as_json(v):
    if isinstance(v, str) and v[:1] in "[{":
        try:
            return json.loads(v)
        except ValueError:
            return None
    return None


def same_value(a, b) -> bool:
    """Equal as values, whatever door each one came through."""
    a = None if a == "" else a
    b = None if b == "" else b
    if a is None or b is None:
        return a is None and b is None
    if a == b:
        return True
    na, nb = _as_number(a), _as_number(b)
    if na is not None and nb is not None:
        return abs(na - nb) <= 1e-9 * max(1.0, abs(na), abs(nb))
    ja, jb = _as_json(a), _as_json(b)
    if ja is not None and jb is not None:
        return ja == jb
    return False


def _rows(conn: sqlite3.Connection, table: str) -> list[dict]:
    if not supabase_store.table_exists(conn, table):
        return []
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(f'SELECT * FROM "{table}"')]


def _sets_by_exercise(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    if not supabase_store.table_exists(conn, "training_sets"):
        return out
    conn.row_factory = sqlite3.Row
    for r in conn.execute("SELECT * FROM training_sets ORDER BY id"):
        out.setdefault(r["exercise_id"], []).append(dict(r))
    return out


def _same_sets(a: list[dict], b: list[dict]) -> bool:
    if len(a) != len(b):
        return False
    return all(same_value(x.get(f), y.get(f)) for x, y in zip(a, b) for f in _SET_FIELDS)


def diff_table(source: sqlite3.Connection, target: sqlite3.Connection,
               table: str, max_examples: int = 5) -> TableDiff:
    if table == "training_sets":
        src, tgt = _sets_by_exercise(source), _sets_by_exercise(target)
        d = TableDiff(table, sum(map(len, src.values())), sum(map(len, tgt.values())))
        d.missing = sorted(k for k in src if k not in tgt)
        d.extra = sorted(k for k in tgt if k not in src)
        d.different = sorted(k for k in src if k in tgt and not _same_sets(src[k], tgt[k]))
        return d
    pk = supabase_store.primary_key(table)
    src = {str(r[pk]): r for r in _rows(source, table) if r.get(pk) not in (None, "")}
    tgt = {str(r[pk]): r for r in _rows(target, table) if r.get(pk) not in (None, "")}
    d = TableDiff(table, len(src), len(tgt))
    d.missing = sorted(k for k in src if k not in tgt)
    d.extra = sorted(k for k in tgt if k not in src)
    for key in sorted(k for k in src if k in tgt):
        s, t = src[key], tgt[key]
        bad = [c for c in s if c in t and not same_value(s[c], t[c])]
        if bad:
            d.different.append(key)
            if len(d.examples) < max_examples:
                d.examples.append((key, bad[0], s[bad[0]], t[bad[0]]))
    return d


def tables_to_compare(source: sqlite3.Connection) -> list[str]:
    from services import datastore_postgres
    names = datastore_postgres.table_names(datastore_postgres.to_postgres())
    return [t for t in names if t not in SKIP_TABLES]


def diff_all(source: sqlite3.Connection, target: sqlite3.Connection) -> list[TableDiff]:
    return [diff_table(source, target, t) for t in tables_to_compare(source)]


def missing_only(diffs: list[TableDiff]) -> list[TableDiff]:
    """The same comparison with only the MISSING rows kept — what is safe to
    copy AFTER the switch: nothing is deleted, nothing is overwritten. Once
    Supabase is the record it may hold newer values and rows Notion never
    will, so only a row Supabase lacks entirely can be taken from the
    archive."""
    return [TableDiff(d.table, d.source_rows, d.target_rows, missing=list(d.missing))
            for d in diffs if d.missing]


def blank_fills(source: sqlite3.Connection, target: sqlite3.Connection,
                diffs: list[TableDiff]) -> dict[str, dict[str, dict]]:
    """For rows on both sides that differ: only the columns Supabase holds
    BLANK and the archive does not — {table: {key: {pk: key, column: value}}}.

    The other half of an add-only copy. A value is never overwritten, only a
    blank filled: three session notes were in Notion and NULL in Supabase on
    2026-10-09, because a queued note update had been lost."""
    from services import supabase_store as ss
    out: dict[str, dict[str, dict]] = {}
    for d in diffs:
        if d.table == "training_sets" or not d.different:
            continue
        pk = ss.primary_key(d.table)
        src = {str(r[pk]): r for r in _rows(source, d.table)}
        tgt = {str(r[pk]): r for r in _rows(target, d.table)}
        for key in d.different:
            s, t = src.get(key), tgt.get(key)
            if not s or not t:
                continue
            cols = {c: s[c] for c in s if c in t and c != pk
                    and t[c] in (None, "") and s[c] not in (None, "")}
            if cols:
                out.setdefault(d.table, {})[key] = {pk: s[pk], **cols}
    return out


def fill_blanks(repo, fills: dict[str, dict[str, dict]]) -> dict[str, int]:
    """Write blank_fills() through a Supabase-record Repository. An upsert of
    a subset of columns changes only those columns."""
    from services import supabase_store as ss
    for table, rows in fills.items():
        repo._write_record(table, rows, ss.UPSERT)
    return {table: len(rows) for table, rows in fills.items()}


def apply_additions(store, source: sqlite3.Connection, diffs: list[TableDiff],
                    fills: dict[str, dict[str, dict]]) -> dict[str, int]:
    """The add-only reconcile straight against the store: missing rows
    written, blanks filled; nothing deleted, nothing overwritten."""
    from services import supabase_store as ss
    done = apply(store, source, missing_only(diffs))
    for table, rows in fills.items():
        numeric = ss.numeric_columns(table)
        payload = [ss.coerce_row(r, numeric) for r in rows.values()]
        for batch in ss.group_by_columns(payload):
            store.upsert(table, batch)
        done[f"{table} (blanks filled)"] = len(rows)
    return done


def copy_missing(repo, source: sqlite3.Connection, diffs: list[TableDiff]) -> dict[str, int]:
    """Write the MISSING rows of `diffs` through a Supabase-record Repository —
    Supabase first, then the local copy (Repository._write_record) — parents
    before children. Returns {table: rows copied}."""
    from services import supabase_store as ss
    by_table = {d.table: d for d in diffs if d.missing}
    order = list(ss.LOAD_ORDER) + [t for t in by_table if t not in ss.LOAD_ORDER]
    src_sets = _sets_by_exercise(source)
    done: dict[str, int] = {}
    for table in order:
        d = by_table.get(table)
        if not d:
            continue
        if table == "training_sets":
            batch = {eid: [{k: v for k, v in s.items() if k != "id"}
                           for s in src_sets.get(eid, [])] for eid in d.missing}
            repo._write_record(table, batch, ss.REPLACE)
            done[table] = sum(len(v) for v in batch.values())
            continue
        pk = ss.primary_key(table)
        wanted = set(d.missing)
        batch = {str(r[pk]): r for r in _rows(source, table) if str(r.get(pk)) in wanted}
        if batch:
            repo._write_record(table, batch, ss.UPSERT)
        done[table] = len(batch)
    return done


def apply(store, source: sqlite3.Connection, diffs: list[TableDiff]) -> dict[str, int]:
    """Make Supabase match the source for every row named in `diffs`.

    Parents are written before children and deleted after them, because the
    foreign keys are enforced in Postgres. Returns {table: rows written or
    deleted}."""
    by_table = {d.table: d for d in diffs}
    done: dict[str, int] = {}
    order = list(supabase_store.LOAD_ORDER) + [
        d.table for d in diffs if d.table not in supabase_store.LOAD_ORDER]

    # 1. Deletions, children first: sets of extra/rewritten exercises, then
    #    extra exercises, then extra sessions, then every other table's extras.
    for table in reversed(order):
        d = by_table.get(table)
        if not d or not d.extra:
            continue
        column = "exercise_id" if table == "training_sets" else supabase_store.primary_key(table)
        for key in d.extra:
            store.delete_where(table, column, key)
        done[table] = done.get(table, 0) + len(d.extra)

    # 2. Writes, parents first.
    src_sets = _sets_by_exercise(source)
    for table in order:
        d = by_table.get(table)
        if not d:
            continue
        keys = d.missing + d.different
        if not keys:
            continue
        numeric = supabase_store.numeric_columns(table)
        if table == "training_sets":
            for exercise_id in keys:
                store.delete_where("training_sets", "exercise_id", exercise_id)
                payload = [supabase_store.coerce_row(
                    {k: v for k, v in s.items() if k != "id"}, numeric)
                    for s in src_sets.get(exercise_id, [])]
                if payload:
                    store.insert("training_sets", payload)
            done[table] = done.get(table, 0) + len(keys)
            continue
        pk = supabase_store.primary_key(table)
        wanted = set(keys)
        rows = [supabase_store.coerce_row(r, numeric) for r in _rows(source, table)
                if str(r.get(pk)) in wanted]
        for batch in supabase_store.group_by_columns(rows):
            store.upsert(table, batch)
        done[table] = done.get(table, 0) + len(rows)
    return done
