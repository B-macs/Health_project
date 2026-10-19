# -*- coding: utf-8 -*-
"""Copy the body-composition readings into Supabase (rebuild Phase 2, fault F15).

    python scripts/import_body_composition.py            # dry run: counts only
    python scripts/import_body_composition.py --apply    # write them

The Metabolism screen read the Foryond scale's export from a local, git-ignored
file (Input_files/Fitdays.csv) and the gym's InBody scans from
body_composition_baselines.SCANS, so on a server it showed no weight at all.
The readings now live in two Supabase tables (scale_readings, inbody_scans;
scripts/migrate_2026-10-19_metabolism_tables.sql creates them), and the screen
reads them like every other table.

Safe to run again after a new export: rows are keyed by their time, so a
reading already stored is overwritten with the same values and nothing is
deleted. Nothing about the readings is printed beyond counts and the date
range, because a console log is easy to paste somewhere public.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import body_composition_baselines as bcb  # noqa: E402
from services import body_composition as bc  # noqa: E402
from services.config import load_config  # noqa: E402
from services.repository import Repository  # noqa: E402

FITDAYS = _ROOT / "Input_files" / "Fitdays.csv"


def _config():
    secrets = _ROOT / ".streamlit" / "secrets.toml"
    overrides = tomllib.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
    # A copy of the store rebuilt for this run only, never the checkout's datastore.db.
    copy = Path(tempfile.mkdtemp(prefix="import_bc_")) / "record.db"
    return load_config({**overrides, "HEALTH_SYSTEM_OF_RECORD": "supabase",
                        "HEALTH_DATASTORE_MODE": "cache",
                        "HEALTH_DATASTORE_PATH": str(copy)})


def _span(items) -> str:
    if not items:
        return "none"
    return f"{len(items)}, {items[0].day.isoformat()} to {items[-1].day.isoformat()}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the readings to Supabase")
    ap.add_argument("--fitdays", type=Path, default=FITDAYS,
                    help="the Foryond (Fitdays) export to read")
    args = ap.parse_args()

    readings = (bc.parse_fitdays_csv(args.fitdays.read_text(encoding="utf-8-sig"))
                if args.fitdays.exists() else [])
    scans = list(bcb.SCANS)
    print(f"scale readings in the export: {_span(readings)}")
    print(f"gym scans in body_composition_baselines.py: {_span(scans)}")
    if not args.fitdays.exists():
        print(f"(no export at {args.fitdays}; only the gym scans would be written)")

    repo = Repository(_config())
    print(f"already stored: scale {len(repo.get_scale_readings())}, "
          f"gym {len(repo.get_inbody_scans())}")
    if not args.apply:
        print("Dry run: nothing written. Run with --apply to write.")
        return 0
    sent_scale = repo.save_scale_readings(readings)
    sent_scans = repo.save_inbody_scans(scans)
    print(f"written: scale {sent_scale}, gym {sent_scans}")
    check = Repository(_config())
    print(f"read back from Supabase: scale {len(check.get_scale_readings())}, "
          f"gym {len(check.get_inbody_scans())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
