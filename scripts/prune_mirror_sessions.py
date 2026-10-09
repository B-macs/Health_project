# -*- coding: utf-8 -*-
"""Remove training rows that Supabase holds and Notion does not.

Found 2026-10-09. Supabase held 50 sessions on 2026-10-05 where Notion holds
two (the gym session and one yoga flow). The yoga press that wrote 51 copies
that morning was repaired in Notion (385 pages archived), and the archive
script deleted the copies' Supabase rows, but 361 exercise rows came back. The
most likely route: the hosted app still held those rows in its send queue and
sent them after the delete (a queue drains at the end of a Home-page sync or
when the process exits). The hosted app rebuilds its read cache from Supabase
on a restart, so the copies came back with every restart: strain 21 for that
Monday.

What it does, for a date range:
  1. reads every training page in the range from the LIVE Notion database,
  2. reads the same range from Supabase (sessions and exercises),
  3. names every exercise and every session Supabase holds and Notion does not,
  4. with --apply, saves those rows and their sets to a JSON file under
     Input_files/mirror_backups/ (gitignored: the rows are personal readings),
     deletes them child-first (sets, exercises, sessions), and reads Supabase
     back.

It refuses when Notion returns no exercises for the range: an empty or failed
read would otherwise name every Supabase row in the range for deletion. Run it
WITHOUT HEALTH_DATASTORE_PATH set, so the Notion side is the live one. The
hosted app sees the change after its next restart. The opposite direction
(Notion holds a row, Supabase does not) is scripts/backfill_mirror_sessions.py.

    python scripts/prune_mirror_sessions.py --from 2026-10-05 --to 2026-10-05
    python scripts/prune_mirror_sessions.py --from 2026-10-05 --to 2026-10-05 --apply
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from collections import Counter
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

_BACKUP_DIR = _ROOT / "Input_files" / "mirror_backups"

#: Ids go into a PostgREST `in.(...)` filter unquoted, so only characters that
#: cannot change the filter are allowed: Notion page ids are UUIDs and session
#: ids are "<date>-<8 hex>". Anything else is refused rather than escaped.
_SAFE_ID = re.compile(r"^[0-9A-Za-z-]+$")

#: Ids per DELETE or GET request. Small enough that a GET of the sets of one
#: chunk stays far under Supabase's 1,000-row response cap.
_CHUNK = 20


class PruneRefused(RuntimeError):
    pass


def prune_plan(notion_rows: list[dict], sb_exercises: list[dict],
               sb_sessions: list[dict]) -> tuple[list[str], list[str]]:
    """(exercise ids, session ids) that Supabase holds and Notion does not.

    `notion_rows` are get_all_training_exercises_raw() rows already cut to the
    range; `sb_exercises` and `sb_sessions` are Supabase rows for the same
    range. A session is pruned only when no Notion exercise names it and no
    Supabase exercise that stays points to it (the foreign key would refuse
    the delete halfway through).
    """
    if not notion_rows:
        raise PruneRefused(
            "Notion returned no exercises for this range. An empty or failed "
            "read would name every Supabase row for deletion, so nothing is done.")
    notion_ex = {r["exercise_id"] for r in notion_rows}
    notion_sessions = {r["session_id"] for r in notion_rows if r.get("session_id")}
    ex_ids = sorted({r["exercise_id"] for r in sb_exercises} - notion_ex)
    kept_sessions = {r["session_id"] for r in sb_exercises
                     if r["exercise_id"] in notion_ex}
    session_ids = sorted({r["session_id"] for r in sb_sessions}
                         - notion_sessions - kept_sessions)
    for value in ex_ids + session_ids:
        if not _SAFE_ID.match(str(value)):
            raise PruneRefused(f"unexpected id {value!r}; nothing is done")
    return ex_ids, session_ids


def _chunks(values: list[str]):
    for i in range(0, len(values), _CHUNK):
        yield values[i:i + _CHUNK]


def _in(column: str, values: list[str]) -> str:
    return f"{column}=in.({','.join(values)})"


def _get(store, path: str) -> list[dict]:
    _h, rows = store._request("GET", path)
    rows = rows or []
    if len(rows) >= 1000:
        raise PruneRefused(f"a read hit the 1,000-row cap ({path[:60]}...); nothing is done")
    return rows


def _supabase_range(store, start: str, end: str) -> tuple[list[dict], list[dict]]:
    span = f"session_date=gte.{start}&session_date=lte.{end}"
    exercises = _get(store, f"training_exercises?select=*&{span}")
    sessions = _get(store, f"training_sessions?select=*&{span}")
    return exercises, sessions


def _repo():
    from services.config import load_config
    from services.repository import Repository
    overrides = {}
    secrets = _ROOT / ".streamlit" / "secrets.toml"
    if secrets.exists():
        with open(secrets, "rb") as fh:
            overrides = tomllib.load(fh)
    # Notion is the side being read, so it is named explicitly: the default
    # is Supabase whenever Supabase is configured.
    return Repository(load_config({**overrides, "HEALTH_SYSTEM_OF_RECORD": "notion"}))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", required=True, help="first ISO date")
    ap.add_argument("--to", dest="end", required=True, help="last ISO date")
    ap.add_argument("--apply", action="store_true", help="without this, nothing is deleted")
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
    sb_exercises, sb_sessions = _supabase_range(store, args.start, args.end)
    try:
        ex_ids, session_ids = prune_plan(notion_rows, sb_exercises, sb_sessions)
    except PruneRefused as exc:
        print(f"REFUSED: {exc}")
        return 1

    doomed = set(ex_ids)
    per_session = Counter(r["session_id"] for r in sb_exercises if r["exercise_id"] in doomed)
    print(f"Notion: {len(notion_rows)} exercises in {args.start}..{args.end}; "
          f"Supabase: {len(sb_exercises)} exercises, {len(sb_sessions)} sessions.")
    print(f"Supabase-only: {len(ex_ids)} exercises, {len(session_ids)} sessions.")
    for sid, n in sorted(per_session.items()):
        print(f"  {sid}  {n} exercises")
    if not ex_ids and not session_ids:
        print("nothing to remove")
        return 0
    if args.apply:
        from services import record_cache
        since = record_cache.record_since(store)
        if since:
            print(f"REFUSED: Supabase has been the system of record since {since}; "
                  f"Notion is a frozen archive and must not be copied over it.")
            return 1
    if not args.apply:
        print("dry run — nothing deleted")
        return 0

    sets = [s for chunk in _chunks(ex_ids)
            for s in _get(store, f"training_sets?select=*&{_in('exercise_id', chunk)}")]
    backup = {
        "range": [args.start, args.end],
        "taken_at": datetime.now().isoformat(timespec="seconds"),
        "training_sessions": [r for r in sb_sessions if r["session_id"] in set(session_ids)],
        "training_exercises": [r for r in sb_exercises if r["exercise_id"] in doomed],
        "training_sets": sets,
    }
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    path = _BACKUP_DIR / (f"prune_{args.start}_{args.end}_"
                          f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
    path.write_text(json.dumps(backup, indent=1, default=str), encoding="utf-8")
    print(f"backup: {path} ({len(backup['training_exercises'])} exercises, "
          f"{len(sets)} sets, {len(backup['training_sessions'])} sessions)")

    # Child-first: the foreign keys are enforced in Postgres.
    for chunk in _chunks(ex_ids):
        store._request("DELETE", f"training_sets?{_in('exercise_id', chunk)}")
    for chunk in _chunks(ex_ids):
        store._request("DELETE", f"training_exercises?{_in('exercise_id', chunk)}")
    for chunk in _chunks(session_ids):
        store._request("DELETE", f"training_sessions?{_in('session_id', chunk)}")

    after_ex, after_sessions = _supabase_range(store, args.start, args.end)
    left = ({r["exercise_id"] for r in after_ex} & doomed,
            {r["session_id"] for r in after_sessions} & set(session_ids))
    print(f"read back: Supabase now {len(after_ex)} exercises, {len(after_sessions)} "
          f"sessions; still present: {len(left[0])} exercises, {len(left[1])} sessions")
    return 0 if not any(left) else 1


if __name__ == "__main__":
    sys.exit(main())
