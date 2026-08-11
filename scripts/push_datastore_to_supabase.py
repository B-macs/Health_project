"""Push the local SQLite datastore into Supabase, then verify the copy.

    python scripts/push_datastore_to_supabase.py --dry-run   # counts only
    python scripts/push_datastore_to_supabase.py             # push + verify
    python scripts/push_datastore_to_supabase.py --verify    # verify only

Source is datastore.db, not the live Notion/Sheets, so this costs no API
quota — and it makes the check a true round trip: the same rows, through
PostgreSQL, back out again.

DESTRUCTIVE: replaces the Supabase contents wholesale, the same contract
services/datastore.py already has for the SQLite copy, where the data is a
regenerable projection rather than the system of record.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
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


def _verify(conn, store, tables) -> int:
    """Compare row counts, then the actual values of a sample row per table."""
    print(f"\n{'table':<28}{'sqlite':>8}{'supabase':>10}   status")
    print("-" * 60)
    bad = 0
    for t in tables:
        local = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        remote = store.count(t)
        ok = local == remote
        bad += 0 if ok else 1
        print(f"{t:<28}{local:>8}{remote:>10}   {'ok' if ok else 'MISMATCH'}")
    return bad


def _verify_values(conn, store) -> int:
    """Spot-check real values survived — floats especially.

    Row counts alone would pass a load that turned every DOUBLE PRECISION into
    NULL, which is precisely the failure the "" -> NULL coercion could cause if
    it were applied to the wrong columns.
    """
    problems = 0
    conn.row_factory = sqlite3.Row
    checks = [
        ("oura_daily", "date", "readiness_hrv_balance"),
        ("oura_sleep_periods", "sleep_id", "average_hrv"),
        ("training_sets", "exercise_id", "weight"),
        ("sleep_fusion", "date", "cohen_kappa"),
        ("metrics_history", "date", "strain"),
    ]
    print(f"\n{'value check':<28}{'sqlite':>14}{'supabase':>14}")
    print("-" * 60)
    for table, key, col in checks:
        row = conn.execute(
            f"SELECT {key}, {col} FROM {table} WHERE {col} IS NOT NULL "
            f"AND {col} != '' ORDER BY {key} LIMIT 1"
        ).fetchone()
        if row is None:
            print(f"{table+'.'+col:<28}{'(no data)':>14}")
            continue
        got = store.select_value(table, f"{key}=eq.{row[key]}", col)
        same = got is not None and abs(float(got) - float(row[col])) < 1e-9
        problems += 0 if same else 1
        print(f"{table+'.'+col:<28}{row[col]:>14}{str(got):>14}"
              f"{'' if same else '   MISMATCH'}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "datastore.db"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true", help="verify only, no push")
    args = ap.parse_args()

    cfg = load_config(_secrets())
    if not cfg.supabase_url or not cfg.supabase_secret_key:
        print("SUPABASE_URL / SUPABASE_SECRET_KEY not configured.")
        return 2

    conn = sqlite3.connect(args.db)
    store = supabase_store.SupabaseStore(cfg.supabase_url, cfg.supabase_secret_key)
    tables = datastore_postgres.table_names(datastore_postgres.to_postgres())

    if args.dry_run:
        total = sum(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in tables)
        print(f"{len(tables)} tables, {total} rows in {args.db} — nothing sent")
        return 0

    if not args.verify:
        print(f"pushing {len(tables)} tables from {Path(args.db).name} …")
        for r in supabase_store.push(conn, store, tables):
            flag = "" if r.ok else "   ⚠ SHORT"
            print(f"  {r.table:<28}{r.loaded_rows:>7} rows{flag}")

    bad = _verify(conn, store, tables)
    bad += _verify_values(conn, store)
    print()
    print("VERDICT:", "faithful copy" if bad == 0 else f"{bad} problem(s)")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
