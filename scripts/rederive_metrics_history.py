# -*- coding: utf-8 -*-
"""Re-compute every stored Metrics History row under the current code.

    python scripts/rederive_metrics_history.py           # dry run: what would change
    python scripts/rederive_metrics_history.py --apply   # backup, write, read back

Why it exists: a change to how a stored figure is computed does not reach the
rows already stored, and the app's routine sync re-computes only the last 7
days. The first use (2026-10-13, the athlete's request): Sleep Score
MODEL_VERSION 2 (Restfulness from Oura's own reading), no Sleep Score or
readiness on a night the ring did not record (WP-11), and strain stored with
the heart-rate blend the Home card showed (WP-18).

Supabase is the system of record, so this reads and writes Supabase. It
refuses to run until the switch has finished (both config markers exist):
before that, the one-time catch-up could still add rows computed the old way
after this run. --apply first writes an off-site copy of every table to
Input_files/backups/ (gitignored), then calls
Repository.rederive_metrics_history, which writes only the rows whose values
move, then reads the table back from Supabase and compares.
"""
from __future__ import annotations

import argparse
import math
import sys
import tempfile
import tomllib
from datetime import date, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from services import backup, record_cache, supabase_store, switchover  # noqa: E402
from services.config import load_config  # noqa: E402
from services.repository import Repository  # noqa: E402

_COLUMNS = ("readiness_score", "sleep_score", "strain")


def _num(value):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _same(a, b) -> bool:
    a, b = _num(a), _num(b)
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) < 0.05


def _config():
    secrets = _ROOT / ".streamlit" / "secrets.toml"
    overrides = tomllib.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
    # A copy of the store rebuilt for this run only, never the checkout's
    # datastore.db.
    copy = Path(tempfile.mkdtemp(prefix="rederive_")) / "record.db"
    return load_config({**overrides, "HEALTH_SYSTEM_OF_RECORD": "supabase",
                        "HEALTH_DATASTORE_MODE": "cache",
                        "HEALTH_DATASTORE_PATH": str(copy)})


def _planned(repo: Repository, today: date) -> dict[str, dict]:
    """{date: computed row} for every stored date, with nothing written:
    rederive_metrics_history's own computation, its one write call captured."""
    captured: dict[str, dict] = {}

    def capture(snapshot, existing=None):
        captured[snapshot["date"]] = repo._metrics_history_row(snapshot)

    original = repo.upsert_metrics_history_row
    repo.upsert_metrics_history_row = capture
    try:
        repo.rederive_metrics_history(today=today)
    finally:
        repo.upsert_metrics_history_row = original
    return captured


def _report(stored: dict[str, dict], planned: dict[str, dict]) -> int:
    moved = 0
    for col in _COLUMNS:
        changes = [(d, stored[d].get(col), planned[d].get(col)) for d in sorted(planned)
                   if d in stored and not _same(stored[d].get(col), planned[d].get(col))]
        blanked = sum(1 for _d, _old, new in changes if _num(new) is None)
        deltas = [_num(new) - _num(old) for _d, old, new in changes
                  if _num(new) is not None and _num(old) is not None]
        mean = f", mean change {sum(deltas) / len(deltas):+.1f}" if deltas else ""
        print(f"  {col}: {len(changes)} rows change ({blanked} become blank{mean})")
        moved += len(changes)
    return moved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="back up, then write the changed rows")
    args = ap.parse_args()
    today = date.today()

    cfg = _config()
    store = supabase_store.SupabaseStore(cfg.supabase_url, cfg.supabase_secret_key)
    since = record_cache.record_since(store)
    caught_up = store.select_value("config", f"key=eq.{switchover.CATCH_UP_KEY}", "value")
    if not since or not caught_up:
        print("Refused: the Supabase switch has not finished "
              f"(record_since={'set' if since else 'missing'}, "
              f"catch-up={'done' if caught_up else 'missing'}). "
              "Open the hosted app once and wait a minute, then run this again.")
        return 2
    print(f"Switch recorded; catch-up done. Today is {today}.")

    repo = Repository(cfg)
    stored = {str(r["date"]): r for r in repo.get_metrics_history() if r.get("date")}
    planned = _planned(repo, today)
    print(f"{len(stored)} stored rows, {len(planned)} re-computed.")
    moved = _report(stored, planned)
    if not args.apply:
        print("Dry run: nothing written. Run with --apply to write.")
        return 0
    if not moved:
        print("Nothing moves; nothing to write.")
        return 0

    out = _ROOT / "Input_files" / "backups"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"health-{today.isoformat()}-before-rederive-{datetime.now():%H%M%S}.db.gz"
    path.write_bytes(backup.snapshot(store))
    print(f"Backup: {path} ({path.stat().st_size / 1e6:.1f} MB)")

    written = repo.rederive_metrics_history(today=today)
    print(f"Re-derived {written} rows.")

    fresh = {str(r["date"]): r for r in store.select_all("metrics_history")}
    wrong = [d for d, row in planned.items()
             if d in fresh and not all(_same(fresh[d].get(c), row.get(c)) for c in _COLUMNS)]
    print(f"Read back from Supabase: {len(fresh)} rows; {len(wrong)} differ from the plan"
          + (f" ({wrong[:5]})" if wrong else "") + ".")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
