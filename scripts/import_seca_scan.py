# -*- coding: utf-8 -*-
"""Store a SECA scan's export in Supabase (WP-37), from the owner's PC.

    python scripts/import_seca_scan.py                 # dry run: the newest export in Input_files
    python scripts/import_seca_scan.py --apply         # store it
    python scripts/import_seca_scan.py --file PATH --apply

The gym's SECA exports a German table view (Input_files/*_TableView_*.csv, never
in git). The phone app imports the same file on Insights › Metabolism; this
script is for a scan already on the PC. The same export stored twice is one
scan. It prints the scan's date and counts only, never a figure, because a
console log is easy to paste somewhere public.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from services import body_composition as bc  # noqa: E402

INPUT = _ROOT / "Input_files"


def newest_export(folder: Path = INPUT) -> Path | None:
    """The newest SECA table export in `folder`, by name (the date is in it)."""
    found = sorted(folder.glob("*_TableView_*.csv"))
    return found[-1] if found else None


def _config():
    from services.config import load_config
    secrets = _ROOT / ".streamlit" / "secrets.toml"
    overrides = tomllib.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
    # A copy of the store rebuilt for this run only, never the checkout's datastore.db.
    copy = Path(tempfile.mkdtemp(prefix="import_seca_")) / "record.db"
    return load_config({**overrides, "HEALTH_SYSTEM_OF_RECORD": "supabase",
                        "HEALTH_DATASTORE_MODE": "cache",
                        "HEALTH_DATASTORE_PATH": str(copy)})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, default=None, help="the SECA export (default: the newest)")
    ap.add_argument("--apply", action="store_true", help="store it in Supabase")
    args = ap.parse_args()
    path = args.file or newest_export()
    if path is None or not path.exists():
        print("No SECA export found (Input_files/*_TableView_*.csv).")
        return 1
    scan = bc.parse_seca_csv(path.read_text(encoding="utf-8-sig"))
    blank = [f for f in ("visceral_fat", "waist_cm") if getattr(scan, f) is None]
    print(f"SECA scan of {scan.day.isoformat()} from {path.name}: "
          f"{len(scan.segments)} body segments; not measured: {', '.join(blank) or 'none'}.")
    from services.repository import Repository
    repo = Repository(_config())
    print(f"already stored: {len(repo.get_seca_scans())} SECA scan(s)")
    if not args.apply:
        print("Dry run: nothing written. Run with --apply to store it.")
        return 0
    stored = repo.save_seca_scan(scan)
    print(f"stored: {len(stored)} SECA scan(s)")
    check = Repository(_config())
    print(f"read back from Supabase: {len(check.get_seca_scans())} SECA scan(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
