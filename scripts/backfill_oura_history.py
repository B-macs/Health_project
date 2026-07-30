"""
scripts/backfill_oura_history.py — historical Oura pull for arbitrary date ranges.

sync_oura_all() only ever covers a rolling window ending today, so anything
older than the integration's own start date is invisible to the app. This
script pulls one or more explicit historical ranges and does two things with
each: appends the rows into the normal Oura Sheet tabs (Daily / Sleep Periods /
Workouts / Sessions / Rest Mode) and writes local CSV + raw-JSON copies under
Input_files/oura_export/ (gitignored, same as every other personal data file).

Sheet writes only ever ADD dates/ids the tab doesn't already have — a real
synced day is never overwritten, and re-running the same range is idempotent
(see Repository.backfill_oura_history). Sparse endpoints leave their columns
blank rather than dropping the date, matching sync_oura_all's behaviour.

The default ranges are the two the ring has data for outside the live sync
window; override with --range as needed.

Usage:
    python scripts/backfill_oura_history.py                    # dry run (default)
    python scripts/backfill_oura_history.py --apply            # Sheets + local export
    python scripts/backfill_oura_history.py --export-only      # local files, no Sheet writes
    python scripts/backfill_oura_history.py --apply --range 2025-06-01:2025-06-30

Reads credentials from .streamlit/secrets.toml (the same file the Streamlit
app uses) or environment variables, via services.config.load_config — nothing
here reads st.secrets or imports streamlit.
"""

from __future__ import annotations

import csv
import json
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.config import load_config
from services.repository import (
    _OURA_DAILY_HEADER,
    _OURA_REST_MODE_HEADER,
    _OURA_SESSION_HEADER,
    _OURA_SLEEP_PERIOD_HEADER,
    _OURA_WORKOUT_HEADER,
    Repository,
)

ROOT = Path(__file__).resolve().parent.parent
EXPORT_DIR = ROOT / "Input_files" / "oura_export"

DEFAULT_RANGES = [("2023-07-04", "2024-07-16"), ("2025-01-08", "2025-03-14")]

# tab_key -> (csv filename, header) — the header doubles as the CSV column
# order, so a CSV column always means the same thing as its Sheet column.
TAB_HEADERS = {
    "daily": ("oura_daily.csv", _OURA_DAILY_HEADER),
    "sleep_periods": ("oura_sleep_periods.csv", _OURA_SLEEP_PERIOD_HEADER),
    "workouts": ("oura_workouts.csv", _OURA_WORKOUT_HEADER),
    "sessions": ("oura_sessions.csv", _OURA_SESSION_HEADER),
    "rest_mode_periods": ("oura_rest_mode.csv", _OURA_REST_MODE_HEADER),
}


def _load_repo() -> Repository:
    secrets_path = ROOT / ".streamlit" / "secrets.toml"
    overrides = {}
    if secrets_path.exists():
        with open(secrets_path, "rb") as f:
            overrides = tomllib.load(f)
    return Repository(load_config(overrides))


def _parse_ranges(argv: list[str]) -> list[tuple[str, str]]:
    ranges = []
    for i, arg in enumerate(argv):
        if arg == "--range" and i + 1 < len(argv):
            start, _, end = argv[i + 1].partition(":")
            if not start or not end:
                raise SystemExit(f"--range needs START:END (got {argv[i + 1]!r})")
            ranges.append((start.strip(), end.strip()))
    return ranges or DEFAULT_RANGES


def _write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in header})


def main() -> None:
    argv = sys.argv[1:]
    export_only = "--export-only" in argv
    apply = "--apply" in argv or export_only
    ranges = _parse_ranges(argv)
    repo = _load_repo()

    if not repo.oura_configured():
        raise SystemExit("Oura is not configured -- add OURA_TOKEN to .streamlit/secrets.toml.")

    # Merge every range into one row set per tab. Ranges are pulled separately
    # (one API call set each) but deduped on the way in, so overlapping ranges
    # passed on the command line can't produce doubled rows.
    merged: dict[str, dict[str, dict]] = {key: {} for key in TAB_HEADERS}
    raw_by_range: dict[str, dict[str, list[dict]]] = {}

    for start, end in ranges:
        print(f"Fetching Oura {start} to {end} ...")
        fetched = repo.fetch_oura_history(start, end)
        raw_by_range[f"{start}_{end}"] = fetched["raw"]
        for key, rows in fetched["rows"].items():
            key_field = TAB_HEADERS[key][1][0]
            for row in rows:
                merged[key][str(row.get(key_field))] = row
        print("  " + "  ".join(
            f"{key}={len(rows)}" for key, rows in fetched["rows"].items()
        ))

    print("\nTotal unique rows across all ranges:")
    for key in TAB_HEADERS:
        print(f"  {key:20s} {len(merged[key]):5d}")

    if not apply:
        print("\nDry run only -- nothing written. Re-run with --apply (Sheets + local "
              "export) or --export-only (local files only).")
        return

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = EXPORT_DIR / "raw"
    raw_dir.mkdir(exist_ok=True)

    for key, (filename, header) in TAB_HEADERS.items():
        rows = sorted(
            merged[key].values(),
            key=lambda r: str(r.get("date") or r.get("day") or r.get("start_day") or ""),
        )
        _write_csv(EXPORT_DIR / filename, header, rows)
        print(f"Wrote {len(rows):5d} rows -> {(EXPORT_DIR / filename).relative_to(ROOT)}")

    for range_label, raw in raw_by_range.items():
        for endpoint, entries in raw.items():
            path = raw_dir / f"{endpoint}_{range_label}.json"
            path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    print(f"Wrote raw JSON payloads -> {raw_dir.relative_to(ROOT)}/")

    if export_only:
        print("\n--export-only: Google Sheets left untouched.")
        return

    print("\nAppending to Google Sheets (existing dates/ids are skipped) ...")
    result = repo.backfill_oura_history({k: list(v.values()) for k, v in merged.items()})
    for key, counts in result.items():
        print(f"  {key:20s} written={counts['written']:5d}  skipped={counts['skipped']:5d}")


if __name__ == "__main__":
    main()
