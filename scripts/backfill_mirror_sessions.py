# -*- coding: utf-8 -*-
"""Copy logged training sessions that Notion holds and Supabase does not.

Found 2026-09-22. Notion held four logged days in the week of 2026-09-14 (the
15th, 16th, 17th and 18th); Supabase held two. A mirror flush drops its rows
when it fails rather than retrying (Repository.flush_supabase_mirror), so the
sessions of the 17th and 18th never reached Postgres. That was invisible until
the hosted app restarted: its read cache is rebuilt FROM Supabase
(datastore.ensure_local_cache), so the rebuilt cache saw two days, the
failed-week rule judged the week failed, and a repeat week was written into
the stored schedule.

What it does, for a date range:
  1. reads every training page in the range from the LIVE Notion database,
  2. reads the same range from Supabase,
  3. names every exercise Notion holds and Supabase does not,
  4. with --apply, queues those sessions, exercises and sets through the same
     mirror queue a live save uses, flushes it, and reads Supabase back.

Rows Supabase already holds are left alone, so it is safe to re-run. Run it
WITHOUT HEALTH_DATASTORE_PATH set: the Notion side must be the live one.
The hosted app sees the rows after its next restart, when it rebuilds its
cache from Supabase.

    python scripts/backfill_mirror_sessions.py --from 2026-09-14 --to 2026-09-20
    python scripts/backfill_mirror_sessions.py --from 2026-09-14 --to 2026-09-20 --apply
"""
from __future__ import annotations

import argparse
import os
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from services import supabase_store  # noqa: E402
from services.config import load_config  # noqa: E402
from services.repository import Repository  # noqa: E402

_EXERCISE_COLUMNS = (
    "exercise_id", "session_id", "session_date", "movement_name", "movement_type",
    "planned_sets", "planned_reps", "exercise_rpe", "actual_sets", "total_volume_kg",
    "notes", "note_summary", "sentiment_score", "flagged_body_parts", "warning_level",
    "garmin_avg_hr", "garmin_max_hr", "garmin_distance_km", "garmin_calories",
)
_SESSION_COLUMNS = ("session_id", "session_date", "session_duration_minutes",
                    "session_rpe", "session_au")


def _repo() -> Repository:
    overrides = {}
    secrets = _ROOT / ".streamlit" / "secrets.toml"
    if secrets.exists():
        with open(secrets, "rb") as fh:
            overrides = tomllib.load(fh)
    return Repository(load_config(overrides))


def _supabase_exercise_ids(store, start: str, end: str) -> set[str]:
    _h, rows = store._request(
        "GET", f"training_exercises?select=exercise_id,session_date"
               f"&session_date=gte.{start}&session_date=lte.{end}")
    return {r["exercise_id"] for r in rows or []}


def _set_row(exercise_id: str, s: dict) -> dict:
    """The projection services/datastore.py::_populate_training and
    Repository._mirror_training_write both use."""
    return {"exercise_id": exercise_id, "set_num": s.get("set_num"),
            "reps": s.get("reps"), "weight": s.get("weight"), "rest": s.get("rest"),
            "tut": s.get("tut"), "velocity": s.get("velocity"),
            "band_tier": s.get("band_tier"), "ts": s.get("ts"),
            "is_warmup": 1 if s.get("is_warmup") else 0,
            "rest_taken_seconds": s.get("rest_taken_seconds"),
            "reps_left": s.get("reps_left"), "weight_left": s.get("weight_left")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", required=True, help="first ISO date")
    ap.add_argument("--to", dest="end", required=True, help="last ISO date")
    ap.add_argument("--apply", action="store_true", help="without this, nothing is written")
    args = ap.parse_args()

    if os.environ.get("HEALTH_DATASTORE_PATH"):
        print("REFUSED: HEALTH_DATASTORE_PATH is set, so Notion reads would come from the "
              "local snapshot. Unset it; the Notion side must be live.")
        return 1

    repo = _repo()
    store = repo._sb
    if store is None:
        print("REFUSED: Supabase is not configured.")
        return 1

    notion_rows = [ex for ex in repo.get_all_training_exercises_raw()
                   if ex["session_date"] and args.start <= ex["session_date"] <= args.end]
    held = _supabase_exercise_ids(store, args.start, args.end)
    missing = [ex for ex in notion_rows if ex["exercise_id"] not in held]

    by_session = defaultdict(list)
    for ex in missing:
        by_session[(ex["session_date"], ex["session_id"])].append(ex["movement_name"])
    print(f"Notion: {len(notion_rows)} exercises in {args.start}..{args.end}; "
          f"Supabase holds {len(held)}; missing {len(missing)}.")
    for (day, sid), names in sorted(by_session.items()):
        print(f"  {day}  {sid}  {len(names)} exercises")
    if not missing:
        print("nothing to copy")
        return 0
    if not args.apply:
        print("dry run — nothing written")
        return 0

    for ex in missing:
        sid = ex["session_id"] or f"{ex['session_date']}:no-session-id"
        repo.queue_mirror("training_sessions", sid,
                          {c: (sid if c == "session_id" else ex[c]) for c in _SESSION_COLUMNS})
        repo.queue_mirror("training_exercises", ex["exercise_id"],
                          {c: (sid if c == "session_id" else ex[c]) for c in _EXERCISE_COLUMNS})
        repo.queue_mirror("training_sets", ex["exercise_id"],
                          [_set_row(ex["exercise_id"], s) for s in ex["sets"]],
                          mode=supabase_store.REPLACE)
    sent = repo.flush_supabase_mirror()
    print(f"flushed: {sent}")
    if repo.mirror_last_error:
        print(f"FLUSH ERROR: {repo.mirror_last_error}")
        return 1

    still = [ex for ex in missing
             if ex["exercise_id"] not in _supabase_exercise_ids(store, args.start, args.end)]
    print(f"read back: {len(missing) - len(still)} of {len(missing)} now in Supabase")
    return 0 if not still else 1


if __name__ == "__main__":
    sys.exit(main())
