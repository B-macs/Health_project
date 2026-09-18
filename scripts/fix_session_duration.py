# -*- coding: utf-8 -*-
"""Correct the recorded DURATION of one logged session, and everything derived
from it.

2026-09-16 was logged as 189 minutes: the session was left open after the
25-minute walk and finished hours later, so the clock kept running. Session AU
is RPE x minutes, so the day carried 378 AU instead of ~90 — four times the
real load, which feeds Strain and the ACWR windows for the next four weeks.

What it does, for one date:
  1. queries the LIVE Notion training database for every page on that date,
  2. refuses if the pages carry more than one session id (that is the
     duplicate-save case: use archive_duplicate_sessions.py first),
  3. writes the new "Session Duration" and a recomputed "Session AU" onto
     EVERY page of the session — Notion stores a session flat, so the
     session-level fields live on each exercise row,
  4. patches the mirror's training_sessions row,
  5. re-derives the Metrics History row for that date, which is where the
     stored strain comes from.

The hosted app reads from its local cache and picks this up on its next sync
of that window, or on the next redeploy. Run WITHOUT HEALTH_DATASTORE_PATH —
the reads must be live, since a datastore row carries a synthesized page id
that Notion will refuse to update.

    python scripts/fix_session_duration.py --date 2026-09-16 --minutes 45
    python scripts/fix_session_duration.py --date 2026-09-16 --minutes 45 --apply
"""
from __future__ import annotations

import argparse
import os
import sys
import tomllib
from collections import defaultdict
from datetime import date as _date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from services import engine  # noqa: E402
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
    ap.add_argument("--date", required=True, help="ISO date of the session")
    ap.add_argument("--minutes", required=True, type=float, help="the real duration")
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
    if not pages:
        print(f"no training pages on {args.date}")
        return 1
    by_session: dict[str, list[dict]] = defaultdict(list)
    for p in pages:
        by_session[notion.get_property(p, "Session ID", "rich_text") or ""].append(p)
    if len(by_session) > 1:
        print(f"REFUSED: {len(by_session)} session ids on {args.date} — "
              f"archive the duplicates first.")
        return 1
    session_id, session_pages = next(iter(by_session.items()))
    for p in session_pages:
        if notion_reader.is_synthesized_page_id(p["id"]):
            print("REFUSED: a synthesized page id — the read was not live.")
            return 1

    first = session_pages[0]
    old_minutes = notion.get_property(first, "Session Duration", "number")
    rpe = notion.get_property(first, "Session RPE", "number")
    old_au = notion.get_property(first, "Session AU", "number")
    new_au = engine.compute_session_au(rpe or 0, args.minutes)
    print(f"{args.date}  session {session_id}  {len(session_pages)} exercises")
    print(f"  duration  {old_minutes} -> {args.minutes:g} min")
    print(f"  RPE       {rpe} (unchanged)")
    print(f"  AU        {old_au} -> {new_au:g}")
    if not args.apply:
        print("dry run — nothing written")
        return 0

    props = {"Session Duration": notion.number(args.minutes),
             "Session AU": notion.number(new_au)}
    for p in session_pages:
        notion.update_page(repo._nc, p["id"], props)
    print(f"updated {len(session_pages)} Notion pages")

    store = repo._sb
    if store is not None:
        store.patch("training_sessions", "session_id", session_id,
                    {"session_duration_minutes": args.minutes, "session_au": new_au})
        print("patched the mirror's training_sessions row")

    changed = repo.sync_metrics_history(days=30, today=_date.today(),
                                        only_dates={args.date})
    print(f"re-derived Metrics History for {args.date} ({changed} row(s) written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
