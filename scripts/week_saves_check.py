# -*- coding: utf-8 -*-
"""The check after the owner's training week in the new app (rebuild Phase 7).

    python scripts/week_saves_check.py --from 2026-10-21 --to 2026-10-27          # a short report
    python scripts/week_saves_check.py --from 2026-10-21 --to 2026-10-27 --json   # the same as JSON;
                                                                                  # the gate reads it

For each day of the week it counts what is stored and what is stored twice:
- PLAN: the plan sessions of the day (any session with an exercise that is not a yoga,
  outdoor or accessory item); more than one is a duplicate.
- YOGA: a flow stored twice the same day (two sessions with the same poses) is a
  duplicate; two different flows are not.
- OUTDOOR: a Garmin activity stored twice (its id is in the note, "activity <id>").
- ACCESSORY: the accessory session; two with the same exercises the same day are a
  duplicate.
- MOVES: the schedule notes stored for the week's days (the phases' shift_reasons), each
  with whether the session moved. Every one of them should be an answer the owner gave:
  the check lists the dates, never the reason (a reason can name last night's sleep).

It prints DATES AND COUNTS ONLY, never a name, a note or a reading, so the output may be
pasted into a chat; and it only reads: the tables are pulled into memory.
The --json answer goes to reports/rebuild/p7/week_saves.json (gitignored).
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import tomllib
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "reports" / "rebuild" / "p7" / "week_saves.json"
TABLES = ("training_sessions", "training_exercises", "config")
YOGA, OUTDOOR, ACCESSORY = "Yoga", "Outdoor", "Accessory"
SUPPLEMENTARY = frozenset({YOGA, OUTDOOR, ACCESSORY})
_ACTIVITY = re.compile(r"\bactivity (\d+)\b")


def _rows(conn: sqlite3.Connection, sql: str, *args) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql, args)]


def days(start: str, end: str) -> list[str]:
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def _kind(types: set[str]) -> str:
    """A session's kind from its exercises' types: a plan session has any other type."""
    if not types or not types <= SUPPLEMENTARY:
        return "plan"
    return next(iter(types)) if len(types) == 1 else "mixed"


def day_counts(conn: sqlite3.Connection, day: str) -> dict:
    """What one day holds, and how much of it is stored twice."""
    sessions = [r["session_id"] for r in _rows(conn, "SELECT session_id FROM training_sessions WHERE session_date = ?", day)]
    exercises = _rows(conn, "SELECT session_id, movement_name, movement_type, notes FROM training_exercises "
                            "WHERE session_date = ?", day)
    by_session: dict[str, list[dict]] = {}
    for e in exercises:
        by_session.setdefault(e["session_id"], []).append(e)
    kinds: dict[str, list[str]] = {}
    for sid in sorted(set(sessions) | set(by_session)):
        rows = by_session.get(sid, [])
        if not rows:
            continue    # a session row with no exercise stores nothing a screen counts
        kinds.setdefault(_kind({r["movement_type"] or "" for r in rows}), []).append(sid)

    def same_content(ids: list[str]) -> int:
        seen: dict[tuple, int] = {}
        for sid in ids:
            key = tuple(sorted(r["movement_name"] or "" for r in by_session[sid]))
            seen[key] = seen.get(key, 0) + 1
        return sum(n - 1 for n in seen.values())

    activities: dict[str, int] = {}
    for sid in kinds.get(OUTDOOR, []):
        for r in by_session[sid]:
            for found in _ACTIVITY.findall(r["notes"] or ""):
                activities[found] = activities.get(found, 0) + 1
    plan = len(kinds.get("plan", []))
    return {
        "plan": plan, "yoga": len(kinds.get(YOGA, [])), "outdoor": len(kinds.get(OUTDOOR, [])),
        "accessory": len(kinds.get(ACCESSORY, [])),
        "duplicates": {"plan": max(plan - 1, 0), "yoga": same_content(kinds.get(YOGA, [])),
                       "outdoor": sum(n - 1 for n in activities.values()),
                       "accessory": same_content(kinds.get(ACCESSORY, []))},
    }


def moves(conn: sqlite3.Connection, week: list[str]) -> list[dict]:
    """The schedule notes stored for the week's days: the date, and whether it moved."""
    from services import scheduling
    raw = _rows(conn, "SELECT value FROM config WHERE key = 'phases'")
    phases = json.loads(raw[0]["value"]) if raw and raw[0]["value"] else []
    out = []
    for phase in phases if isinstance(phases, list) else []:
        for day, reason in sorted((phase.get("shift_reasons") or {}).items()):
            if day in week:
                out.append({"date": day, "moved": bool(scheduling.shift_note_moved(str(reason)))})
    return out


def check(conn: sqlite3.Connection, start: str, end: str) -> dict:
    week = days(start, end)
    per_day = {d: day_counts(conn, d) for d in week}
    duplicates = sum(sum(c["duplicates"].values()) for c in per_day.values())
    return {"from": start, "to": end, "days": per_day, "duplicates": duplicates, "moves": moves(conn, week)}


def main() -> int:
    ap = argparse.ArgumentParser(description="The saves of a training week in the new app, each stored once.")
    ap.add_argument("--from", dest="start", required=True, help="the week's first day, YYYY-MM-DD")
    ap.add_argument("--to", dest="end", required=True, help="the week's last day, YYYY-MM-DD")
    ap.add_argument("--json", action="store_true", help="print JSON and write reports/rebuild/p7/week_saves.json")
    args = ap.parse_args()
    from services import supabase_store
    from services.config import load_config
    secrets = ROOT / ".streamlit" / "secrets.toml"
    overrides = tomllib.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
    cfg = load_config({**overrides, "HEALTH_SYSTEM_OF_RECORD": "supabase"})
    store = supabase_store.SupabaseStore(cfg.supabase_url, cfg.supabase_secret_key)
    conn = sqlite3.connect(":memory:")
    supabase_store.pull(store, conn, list(TABLES))
    result = check(conn, args.start, args.end)
    if args.json:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0
    for day, c in result["days"].items():
        dup = {k: v for k, v in c["duplicates"].items() if v}
        print(f"{day}: plan {c['plan']}, yoga {c['yoga']}, outdoor {c['outdoor']}, accessory {c['accessory']}"
              + (f"; STORED TWICE: {', '.join(f'{k} {v}' for k, v in dup.items())}" if dup else ""))
    notes = [f"{m['date']} ({'moved' if m['moved'] else 'kept'})" for m in result["moves"]]
    print(f"schedule notes: {', '.join(notes) or 'none'}")
    print(f"duplicates: {result['duplicates']}")
    return 0 if not result["duplicates"] else 1


if __name__ == "__main__":
    sys.exit(main())
