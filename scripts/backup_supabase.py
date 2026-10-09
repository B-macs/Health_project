# -*- coding: utf-8 -*-
"""Take a copy of every Supabase table — the system of record since 2026-10-09.

    python scripts/backup_supabase.py              # a copy on THIS computer
    python scripts/backup_supabase.py --storage    # today's copy in Supabase Storage

The default writes Input_files/backups/health-YYYY-MM-DD.db.gz (gitignored: it
holds personal readings) — the off-site copy, which is the one that survives
losing the Supabase project itself. --storage takes the copy the hosted app
takes by itself once a day (services/backup.py): a private bucket, 30 days
kept.

Reads Supabase only. To restore a copy: gunzip it, then
    python scripts/push_datastore_to_supabase.py --db <file> --overwrite-record
"""
from __future__ import annotations

import argparse
import sys
import tomllib
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from services import backup, supabase_store  # noqa: E402
from services.config import load_config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--storage", action="store_true",
                    help="upload today's copy to the Supabase Storage bucket instead")
    args = ap.parse_args()
    secrets = _ROOT / ".streamlit" / "secrets.toml"
    overrides = tomllib.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
    cfg = load_config({**overrides, "HEALTH_SYSTEM_OF_RECORD": "supabase"})
    store = supabase_store.SupabaseStore(cfg.supabase_url, cfg.supabase_secret_key)
    if args.storage:
        name = backup.run(store, date.today())
        print(f"uploaded {name} to the {backup.BUCKET} bucket")
        return 0
    out = _ROOT / "Input_files" / "backups"
    out.mkdir(parents=True, exist_ok=True)
    path = out / backup.object_name(date.today())
    path.write_bytes(backup.snapshot(store))
    print(f"wrote {path} ({path.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
