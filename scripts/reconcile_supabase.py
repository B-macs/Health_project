# -*- coding: utf-8 -*-
"""Make Supabase hold exactly what Notion and Google Sheets hold — the last
step before Supabase becomes the only store (2026-10-09).

  1. reads EVERY table from the legacy stores, live (services/datastore.rebuild
     over a Repository with HEALTH_SYSTEM_OF_RECORD=notion) into a temp file,
  2. reads every table from Supabase (supabase_store.pull) into another,
  3. compares them row by row on the primary key (services/reconcile.py) and
     prints, per table, the rows Supabase is missing, holds extra, or holds
     with a different value,
  4. with --apply, makes Supabase match: missing and different rows written
     whole, extra rows deleted, children before parents — then compares again.

A backup of Supabase as it was is written to Input_files/mirror_backups/
(gitignored: it holds personal readings) before anything is changed.

REFUSES once the hosted app has run with Supabase as the record
(record_cache.RECORD_SINCE_KEY): from then on Notion and Sheets are a frozen
archive, and "make Supabase match them" would delete everything logged since.

Run WITHOUT HEALTH_DATASTORE_PATH set — the legacy reads must be live.

    python scripts/reconcile_supabase.py
    python scripts/reconcile_supabase.py --add-only   # add missing rows, fill blanks
    python scripts/reconcile_supabase.py --apply      # also delete and overwrite

--add-only writes only rows Supabase lacks and values it holds blank: nothing
is deleted and no value is overwritten. The hosted app does the same once, by
itself, at its first start with Supabase as the record (services/switchover.py).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import tomllib
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from services import datastore, reconcile, record_cache, supabase_store  # noqa: E402
from services.config import load_config  # noqa: E402
from services.repository import Repository  # noqa: E402

_BACKUP_DIR = _ROOT / "Input_files" / "mirror_backups"


def _secrets() -> dict:
    p = _ROOT / ".streamlit" / "secrets.toml"
    return tomllib.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _report(diffs) -> int:
    print(f"\n{'table':<26}{'source':>8}{'supabase':>10}{'missing':>9}{'extra':>7}{'differ':>8}")
    print("-" * 68)
    open_rows = 0
    for d in diffs:
        n = len(d.missing) + len(d.extra) + len(d.different)
        open_rows += n
        print(f"{d.table:<26}{d.source_rows:>8}{d.target_rows:>10}"
              f"{len(d.missing):>9}{len(d.extra):>7}{len(d.different):>8}"
              f"{'' if d.clean else '   <-'}")
    print("-" * 68)
    for d in diffs:
        for key, column, src, tgt in d.examples[:3]:
            # Column names and keys only: values can be personal readings.
            print(f"  {d.table}: {key} differs in {column} "
                  f"({type(src).__name__} vs {type(tgt).__name__})")
        if d.missing[:3]:
            print(f"  {d.table}: missing e.g. {', '.join(map(str, d.missing[:3]))}")
        if d.extra[:3]:
            print(f"  {d.table}: extra e.g. {', '.join(map(str, d.extra[:3]))}")
    return open_rows


def _snapshot_supabase(store, path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        supabase_store.pull(store, conn)
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="without this, nothing is written")
    ap.add_argument("--add-only", action="store_true",
                    help="write missing rows and fill blanks; delete and overwrite nothing")
    args = ap.parse_args()

    if os.environ.get("HEALTH_DATASTORE_PATH"):
        print("REFUSED: HEALTH_DATASTORE_PATH is set; the legacy reads must be live.")
        return 1
    secrets = _secrets()
    legacy = load_config({**secrets, "HEALTH_SYSTEM_OF_RECORD": "notion"})
    if not (legacy.supabase_url and legacy.supabase_secret_key):
        print("REFUSED: Supabase is not configured.")
        return 1
    store = supabase_store.SupabaseStore(legacy.supabase_url, legacy.supabase_secret_key)
    since = record_cache.record_since(store)
    if since:
        print(f"REFUSED: Supabase has been the system of record since {since}. "
              f"Notion and Sheets are a frozen archive; matching Supabase to "
              f"them would delete everything logged since.")
        return 1

    work = Path(tempfile.mkdtemp(prefix="reconcile_"))
    src_path, tgt_path = str(work / "legacy.db"), str(work / "supabase.db")
    print("reading Notion and Google Sheets (live) ...")
    src = sqlite3.connect(src_path)
    counts = datastore.rebuild(Repository(legacy), src)
    print(f"  {sum(counts.values())} rows in {len(counts)} tables")
    print("reading Supabase ...")
    _snapshot_supabase(store, tgt_path)
    tgt = sqlite3.connect(tgt_path)

    diffs = reconcile.diff_all(src, tgt)
    open_rows = _report(diffs)
    if not open_rows:
        print("\nSupabase matches Notion and Google Sheets.")
        return 0
    if not (args.apply or args.add_only):
        print(f"\n{open_rows} rows differ. dry run — nothing written")
        return 0

    fills = reconcile.blank_fills(src, tgt, diffs) if args.add_only else {}
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = _BACKUP_DIR / f"supabase_before_reconcile_{datetime.now():%Y%m%d-%H%M%S}.db"
    tgt.close()
    Path(tgt_path).replace(backup)
    print(f"\nbackup of Supabase as it was: {backup}")

    if args.add_only:
        done = reconcile.apply_additions(store, src, diffs, fills)
    else:
        done = reconcile.apply(store, src, diffs)
    print("written / deleted:", json.dumps(done))

    _snapshot_supabase(store, tgt_path)
    after = reconcile.diff_all(src, sqlite3.connect(tgt_path))
    left = _report(after)
    print("\nSupabase matches Notion and Google Sheets." if not left
          else f"\n{left} rows still differ.")
    if args.add_only:
        return 0
    return 0 if not left else 1


if __name__ == "__main__":
    sys.exit(main())
