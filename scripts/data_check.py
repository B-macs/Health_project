# -*- coding: utf-8 -*-
"""The daily data check, from this computer: rows the store has lost.

    python scripts/data_check.py          # a short summary
    python scripts/data_check.py --json   # the whole answer (the gate reads this)

The same check the Worker runs once a day through the engine
(services/data_check.py): every table of the newest backup in Supabase Storage
against the store pulled now. A row the backup holds and the store does not is
MISSING. It only reads: nothing is written, repaired or deleted. The keys it
names are ids and dates, never a reading.

To repair a missing row, after the owner says yes: download the backup
(dashboard -> Storage -> health-backups), gunzip it, then
    python scripts/push_datastore_to_supabase.py --db <file> --overwrite-record
"""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from services import data_check, supabase_store  # noqa: E402
from services.config import load_config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="print the whole answer as JSON")
    args = ap.parse_args()
    secrets = _ROOT / ".streamlit" / "secrets.toml"
    overrides = tomllib.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
    cfg = load_config({**overrides, "HEALTH_SYSTEM_OF_RECORD": "supabase"})
    store = supabase_store.SupabaseStore(cfg.supabase_url, cfg.supabase_secret_key)
    try:
        result = data_check.run(store, datetime.now(timezone.utc))
    except data_check.DataCheckFailed as exc:
        print(json.dumps({"error": "store_unavailable", "detail": str(exc)}) if args.json
              else f"The check did not run: {exc}")
        return 2
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    print(f"newest backup: {result['backup_name'] or 'none'}"
          + (" (older than two days)" if result["backup_stale"] else ""))
    print(f"rows missing from the store: {result['missing_rows']}")
    for table in result["tables"]:
        if table["missing"]:
            print(f"  {table['table']}: {table['missing']} (e.g. {', '.join(table['examples'])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
