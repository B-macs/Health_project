# -*- coding: utf-8 -*-
"""Archive the duplicate copies of a session that was saved more than once.

2026-09-10 was saved three times: a Save that stopped partway (8 exercises
written, then 2) was pressed again, and every press minted a fresh session id
and rewrote everything. Three session rows, 1,306 AU for one session, strain
17.1 for the day against 15.5 for a heavier single-row day. The save path now
resumes under one id (views/training.py, 2026-09-11); this repairs the data
that the old path left behind.

What it does, for one date:
  1. queries the LIVE Notion training database for every page on that date,
  2. groups the pages by Session ID,
  3. keeps the one session id you name (the complete copy) and ARCHIVES every
     page under any other id — Notion's archive is a soft delete, restorable
     from Notion's own trash,
  4. deletes the same rows from Supabase, in child-first order: training_sets
     by exercise_id, training_exercises by exercise_id, training_sessions by
     session_id.

The hosted app reads from its local cache, which is rebuilt from Supabase on
the next redeploy; until then it still shows the duplicates. Run this WITHOUT
HEALTH_DATASTORE_PATH set — the reads must be live, since a datastore row
carries a synthesized page id that Notion will refuse to archive.

    python scripts/archive_duplicate_sessions.py --date 2026-09-10 --keep 2026-09-10-156321a3
    python scripts/archive_duplicate_sessions.py --date 2026-09-10 --keep 2026-09-10-156321a3 --apply
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
from services.clients import notion, notion_reader  # noqa: E402
from services.config import load_config  # noqa: E402
from services.repository import Repository  # noqa: E402


def _repo() -> Repository:
    overrides = {}
    secrets = _ROOT / ".streamlit" / "secrets.toml"
    if secrets.exists():
        with open(secrets, "rb") as fh:
            overrides = tomllib.load(fh)
    return Repository(load_config(overrides))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="ISO date of the duplicated session")
    ap.add_argument("--keep", required=True, help="the session id to KEEP (the complete copy)")
    ap.add_argument("--apply", action="store_true", help="without this, nothing is written")
    args = ap.parse_args()

    if os.environ.get("HEALTH_DATASTORE_PATH"):
        print("REFUSED: unset HEALTH_DATASTORE_PATH — this needs live Notion page ids.")
        return 1

    repo = _repo()
    pages = repo._query(
        repo.config.notion_db_training,
        filter_={"property": "Session Date", "date": {"equals": args.date}},
    )
    by_session: dict[str, list[dict]] = defaultdict(list)
    for p in pages:
        sid = notion.get_property(p, "Session ID", "rich_text") or ""
        by_session[sid].append(p)

    print(f"{len(pages)} training pages on {args.date} under {len(by_session)} session ids:")
    for sid, ps in sorted(by_session.items()):
        mark = "KEEP" if sid == args.keep else "archive"
        print(f"  {sid}  {len(ps):2d} exercises  -> {mark}")
    if args.keep not in by_session:
        print(f"REFUSED: {args.keep!r} is not one of the session ids on that date.")
        return 1
    doomed = [(sid, p) for sid, ps in by_session.items() if sid != args.keep for p in ps]
    if not doomed:
        print("nothing to archive")
        return 0
    for _sid, p in doomed:
        if notion_reader.is_synthesized_page_id(p["id"]):
            print("REFUSED: a synthesized page id — the read was not live.")
            return 1
    if not args.apply:
        print(f"dry run — would archive {len(doomed)} pages and delete their mirror rows")
        return 0

    for _sid, p in doomed:
        notion.archive_page(repo._nc, p["id"])
    print(f"archived {len(doomed)} Notion pages")

    store = repo._sb
    if store is None:
        print("no Supabase store configured — mirror rows NOT deleted")
        return 0
    for _sid, p in doomed:
        store.delete_where("training_sets", "exercise_id", p["id"])
        store.delete_where("training_exercises", "exercise_id", p["id"])
    for sid in {sid for sid, _p in doomed}:
        store.delete_where("training_sessions", "session_id", sid)
    print(f"deleted the mirror rows for {len(doomed)} exercises and "
          f"{len({sid for sid, _p in doomed})} sessions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
