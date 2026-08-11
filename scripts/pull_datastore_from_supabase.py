"""Rebuild the local datastore FROM Supabase -- no Notion, no Google Sheets.

    python scripts/pull_datastore_from_supabase.py                 # -> datastore.db
    python scripts/pull_datastore_from_supabase.py --out copy.db
    python scripts/pull_datastore_from_supabase.py --round-trip    # fidelity check

This is the direction that makes the app independent of Notion and Google.
scripts/build_datastore.py fills the same file by reading them; this fills it
from Supabase instead, so once Supabase is the system of record the other two
are only needed for the original migration.

READS STAY LOCAL, deliberately. Measured 2026-08-11: one PostgREST round trip
costs ~136 ms regardless of table size, so a full 22-table read is 4,284 ms
against 32 ms from SQLite -- 113x. Postgres holds the truth; SQLite serves the
reads.

--round-trip is the honest check: push the current datastore, pull it back
into a scratch file, and diff every table cell by cell. Anything that comes
back different is a lossy column, reported rather than assumed absent.

Writes into a temp file and os.replace()s it only on success, the same
contract build_datastore.py has, so a failed pull never destroys the last
known-good snapshot.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services import datastore_postgres, supabase_store  # noqa: E402
from services.config import load_config  # noqa: E402


def _secrets() -> dict:
    p = ROOT / ".streamlit" / "secrets.toml"
    if not p.exists():
        return {}
    import tomllib
    return tomllib.loads(p.read_text(encoding="utf-8"))


def _store():
    cfg = load_config(_secrets())
    if not cfg.supabase_url or not cfg.supabase_secret_key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SECRET_KEY not configured.")
    return supabase_store.SupabaseStore(cfg.supabase_url, cfg.supabase_secret_key)


def _pull_into(path: Path, store, tables=None) -> dict[str, int]:
    """Pull into a temp file beside `path`, then atomically replace it."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".pulling")
    os.close(fd)
    try:
        conn = sqlite3.connect(tmp)
        counts = supabase_store.pull(
            store, conn, tables,
            progress=lambda t, n: print(f"  {t:<28}{n:>7} rows"))
        conn.close()
        os.replace(tmp, path)
        return counts
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _diff(a: Path, b: Path, tables) -> int:
    """Cell-by-cell comparison of two datastores. training_sets.id is skipped:
    it is a surrogate assigned independently by each store and carries no
    meaning -- the ORDER it induces is what matters, and that is checked by
    comparing the rows in id order."""
    ca, cb = sqlite3.connect(a), sqlite3.connect(b)
    ca.row_factory = cb.row_factory = sqlite3.Row
    problems = 0
    print(f"\n{'table':<28}{'rows':>12}   status")
    print("-" * 62)
    for t in tables:
        pk = supabase_store.primary_key(t)
        try:
            ra = [dict(r) for r in ca.execute(f'SELECT * FROM "{t}" ORDER BY {pk}')]
            rb = [dict(r) for r in cb.execute(f'SELECT * FROM "{t}" ORDER BY {pk}')]
        except sqlite3.OperationalError as exc:
            print(f"{t:<28}{'--':>12}   {exc}")
            problems += 1
            continue
        if len(ra) != len(rb):
            print(f"{t:<28}{f'{len(ra)} vs {len(rb)}':>12}   ROW COUNT DIFFERS")
            problems += 1
            continue
        bad = []
        for x, y in zip(ra, rb):
            for col in x:
                if t == "training_sets" and col == "id":
                    continue
                if x[col] != y[col]:
                    bad.append((col, x[col], y[col]))
        if bad:
            problems += 1
            cols = sorted({c for c, _, _ in bad})
            print(f"{t:<28}{len(ra):>12}   {len(bad)} CELLS DIFFER in {cols}")
            for c, u, v in bad[:3]:
                print(f"{'':<28}{'':>12}     {c}: {u!r} -> {v!r}")
        else:
            print(f"{t:<28}{len(ra):>12}   identical")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "datastore.db"))
    ap.add_argument("--round-trip", action="store_true",
                    help="push the current datastore, pull it back, diff both")
    args = ap.parse_args()
    store = _store()
    tables = datastore_postgres.table_names(datastore_postgres.to_postgres())

    if args.round_trip:
        src = ROOT / "datastore.db"
        conn = sqlite3.connect(src)
        live = [t for t in tables if supabase_store.table_exists(conn, t)]
        # Round-trip whatever the project actually has. A table the schema
        # declares but Supabase has not been given yet is NAMED and skipped,
        # never silently dropped from the comparison -- a fidelity check that
        # quietly tested 21 of 22 tables would read as a clean bill of health.
        absent = []
        for t in list(live):
            try:
                store.count(t)
            except supabase_store.SupabaseError:
                absent.append(t)
                live.remove(t)
        if absent:
            print(f"!! not in the Supabase project, EXCLUDED from this check: "
                  f"{', '.join(absent)}\n  (apply their CREATE TABLE from "
                  f"services/datastore_schema_postgres.sql)\n")
        print(f"pushing {len(live)} tables from {src.name} ...")
        for r in supabase_store.push(conn, store, live):
            print(f"  {r.table:<28}{r.loaded_rows:>7} rows"
                  f"{'' if r.ok else '   SHORT'}")
        scratch = src.parent / "datastore_roundtrip.db"
        print(f"\npulling back into {scratch.name} ...")
        _pull_into(scratch, store, live)
        bad = _diff(src, scratch, live)
        print()
        print("VERDICT:", "round trip is lossless" if bad == 0
              else f"{bad} table(s) changed -- see above")
        return 0 if bad == 0 else 1

    out = Path(args.out)
    print(f"pulling {len(tables)} tables from Supabase into {out.name} ...")
    counts = _pull_into(out, store, tables)
    print(f"\n{sum(counts.values())} rows across {len(counts)} tables -- "
          f"no Notion, no Google Sheets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
