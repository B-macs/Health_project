"""
scripts/backfill_garmin_from_sheet1.py -- One-time historical backfill.

The engine's biometric source moved from Sheet1 (Apple Health auto-export)
to a blended Oura+Garmin read (services/biometrics.py, services/repository.py
::get_biometric_rolling). readiness.py's rolling baselines need 14-56 days
of history; Oura/Garmin history only goes back as far as those integrations
have been running. This script maps legacy Sheet1 rows into the Garmin Daily
sheet tab's shape (per the user's choice: backfill into Garmin's tab, not
Oura's) for any date Garmin doesn't already have -- never overwrites a real
Garmin-synced day.

Fields Sheet1 never captured (sleep_score, avg_stress, calories_total,
min_hr, max_hr) are left blank, same as any other missing Garmin field.

Usage:
    python scripts/backfill_garmin_from_sheet1.py          # dry run (default)
    python scripts/backfill_garmin_from_sheet1.py --apply  # actually writes

Reads credentials from .streamlit/secrets.toml (same file the Streamlit app
uses) or environment variables, via services.config.load_config -- nothing
here reads st.secrets/imports streamlit.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import biometrics
from services.config import load_config
from services.repository import Repository


def _load_repo() -> Repository:
    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    overrides = {}
    if secrets_path.exists():
        with open(secrets_path, "rb") as f:
            overrides = tomllib.load(f)
    return Repository(load_config(overrides))


def main() -> None:
    apply = "--apply" in sys.argv
    repo = _load_repo()

    records = repo.get_all_sheet1_biometric_records()
    if not records:
        print("Sheet1 is empty -- nothing to backfill.")
        return

    existing_garmin_dates = repo.get_garmin_daily_dates()
    to_write = [r for r in records if r.date not in existing_garmin_dates]

    print(f"Sheet1 history: {len(records)} rows ({records[0].date} to {records[-1].date}).")
    print(f"Garmin Daily tab already has {len(existing_garmin_dates)} dates.")
    print(f"{len(to_write)} date(s) would be backfilled into Garmin Daily:")
    for r in to_write[:10]:
        print(f"  {r.date}  hrv={r.hrv_ms}  rhr={r.resting_heart_rate}  "
              f"sleep_h={r.sleep_duration_hours}  steps={r.steps}")
    if len(to_write) > 10:
        print(f"  ... and {len(to_write) - 10} more")

    if not to_write:
        print("\nNothing to do.")
        return

    if not apply:
        print("\nDry run only -- no changes written. Re-run with --apply to write these rows.")
        return

    for r in to_write:
        repo.upsert_garmin_daily_row(biometrics.sheet1_row_to_garmin_daily_row(r))
    print(f"\nWrote {len(to_write)} row(s) to the Garmin Daily tab.")


if __name__ == "__main__":
    main()
