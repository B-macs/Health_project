# -*- coding: utf-8 -*-
"""The field check after the owner's real session in the new app (rebuild Phase 6).

    python scripts/session_field_check.py --date 2026-10-21           # a short report
    python scripts/session_field_check.py --date 2026-10-21 --json    # the same as JSON;
                                                                      # the gate reads it

It compares the plan session stored on --date (the one the new app saved) with the
last plan session the Streamlit app saved before it that shares the most exercises
with it, field by field, over the three tables a save writes: training_sessions,
training_exercises and training_sets (exercises matched by name, sets by number).

- MISSING: a field the Streamlit session fills and the new one fills nowhere. This is
  what the gate's fields_missing counts.
- CONDITIONAL: a field that is empty by design when nothing called for it (the left
  side's own numbers when the sides were equal, a rest after the last set, a band on a
  lift without one). Listed with its counts, never counted as missing.
- LATER: a field a later job fills (the heart-rate sync's per-exercise effort, the note
  parse, a Garmin import). Listed, never counted.
- DUPLICATES: plan sessions stored on --date beyond the first. A yoga, outdoor or
  accessory session is not a plan session (Repository.SUPPLEMENTARY_SESSION_TYPES).

It prints TABLE AND FIELD NAMES AND COUNTS ONLY, never a value, so the output may be
pasted into a chat; and it only reads: the three tables are pulled into memory.
The --json answer goes to reports/rebuild/p6/field_check.json (gitignored).
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "reports" / "rebuild" / "p6" / "field_check.json"
TABLES = ("training_sessions", "training_exercises", "training_sets")
SUPPLEMENTARY = frozenset({"Yoga", "Outdoor", "Accessory"})
#: Ids and keys: compared by matching, not as fields.
KEYS = {"training_sessions": {"session_id", "session_date"},
        "training_exercises": {"exercise_id", "session_id", "session_date", "movement_name"},
        "training_sets": {"id", "exercise_id", "set_num"}}
#: Empty by design when nothing called for them: a side's own numbers when the sides
#: were equal, a rest that was not measured, a note not written. (A weight, a band or a
#: hold time is not here: the same exercise needs it both times.)
CONDITIONAL = {"training_sets": {"reps_left", "weight_left", "tut_left", "rest_taken_seconds", "velocity"},
               "training_exercises": {"notes"}}
#: Filled after the save by another job.
LATER = {"training_exercises": {"exercise_rpe", "note_summary", "sentiment_score",
                                "flagged_body_parts", "warning_level", "garmin_avg_hr",
                                "garmin_max_hr", "garmin_distance_km", "garmin_calories"}}
_OFFSET = re.compile(r"[+-]\d\d:?\d\d$|Z$")


def filled(value) -> bool:
    return value is not None and value != "" and value != "[]"


def plan_sessions(sessions: list[dict], exercises: list[dict], day: str) -> list[str]:
    """The plan sessions stored on `day`: a session whose exercises are all of a
    supplementary type is left out; so is one with no exercise at all."""
    kinds: dict[str, set[str]] = {}
    for e in exercises:
        kinds.setdefault(e.get("session_id"), set()).add(e.get("movement_type") or "")
    return sorted(s["session_id"] for s in sessions
                  if s.get("session_date") == day and kinds.get(s["session_id"])
                  and not kinds[s["session_id"]] <= SUPPLEMENTARY)


def pick_base(sessions: list[dict], exercises: list[dict], new_id: str, day: str) -> str | None:
    """The earlier plan session that shares the most exercise names with the new one;
    the latest of those on a tie."""
    names: dict[str, set[str]] = {}
    for e in exercises:
        names.setdefault(e.get("session_id"), set()).add(e.get("movement_name") or "")
    mine = names.get(new_id, set())
    dates = {s["session_id"]: s.get("session_date") or "" for s in sessions}
    earlier = sorted({sid for s in sessions for sid in [s["session_id"]]
                      if (dates[sid] < day) and sid in names
                      and not {e.get("movement_type") or "" for e in exercises if e.get("session_id") == sid} <= SUPPLEMENTARY})
    if not earlier:
        return None
    return max(earlier, key=lambda sid: (len(names[sid] & mine), dates[sid], sid))


def _fill_counts(rows: list[dict], skip: set[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        for col, value in r.items():
            if col in skip:
                continue
            counts.setdefault(col, 0)
            if filled(value):
                counts[col] += 1
    return counts


def compare(old: dict[str, list[dict]], new: dict[str, list[dict]]) -> dict:
    """The field-by-field comparison of two sessions' rows, table by table: for each
    field, how many rows fill it in the old session and in the new one (counts only).
    The old session's exercises are kept only where the new one has the same name, and
    its sets only where the new one has the same exercise name and set number."""
    names_new = {e["movement_name"] for e in new["training_exercises"]}
    old_ex = [e for e in old["training_exercises"] if e["movement_name"] in names_new]
    name_of = {e["exercise_id"]: e["movement_name"] for e in [*old["training_exercises"], *new["training_exercises"]]}
    new_sets = {(name_of.get(s["exercise_id"]), s.get("set_num")) for s in new["training_sets"]}
    old_sets = [s for s in old["training_sets"]
                if s["exercise_id"] in {e["exercise_id"] for e in old_ex}
                and (name_of.get(s["exercise_id"]), s.get("set_num")) in new_sets]
    paired = {"training_sessions": (old["training_sessions"], new["training_sessions"]),
              "training_exercises": (old_ex, new["training_exercises"]),
              "training_sets": (old_sets, new["training_sets"])}
    out = {"tables": {}, "missing": [], "conditional": [], "later": []}
    for table, (o_rows, n_rows) in paired.items():
        skip = KEYS[table]
        o_counts, n_counts = _fill_counts(o_rows, skip), _fill_counts(n_rows, skip)
        fields = {}
        for col in sorted(set(o_counts) | set(n_counts)):
            o_n, n_n = o_counts.get(col, 0), n_counts.get(col, 0)
            fields[col] = {"old": f"{o_n}/{len(o_rows)}", "new": f"{n_n}/{len(n_rows)}"}
            if o_n and not n_n:
                name = f"{table}.{col}"
                if col in LATER.get(table, set()):
                    out["later"].append(name)
                elif col in CONDITIONAL.get(table, set()):
                    out["conditional"].append(name)
                else:
                    out["missing"].append(name)
        out["tables"][table] = fields
    stamps = [s.get("ts") for s in new["training_sets"] if filled(s.get("ts"))]
    out["set_times_with_offset"] = f"{sum(bool(_OFFSET.search(str(t))) for t in stamps)}/{len(new['training_sets'])}"
    return out


def session_rows(conn: sqlite3.Connection, session_id: str) -> dict[str, list[dict]]:
    conn.row_factory = sqlite3.Row
    sessions = [dict(r) for r in conn.execute("SELECT * FROM training_sessions WHERE session_id = ?", (session_id,))]
    exercises = [dict(r) for r in conn.execute("SELECT * FROM training_exercises WHERE session_id = ?", (session_id,))]
    ids = [e["exercise_id"] for e in exercises]
    sets = [dict(r) for r in conn.execute(
        f"SELECT * FROM training_sets WHERE exercise_id IN ({','.join('?' * len(ids))})", ids)] if ids else []
    return {"training_sessions": sessions, "training_exercises": exercises, "training_sets": sets}


def check(conn: sqlite3.Connection, day: str) -> dict:
    """The whole check over a database holding the three tables."""
    conn.row_factory = sqlite3.Row
    sessions = [dict(r) for r in conn.execute("SELECT session_id, session_date FROM training_sessions")]
    exercises = [dict(r) for r in conn.execute(
        "SELECT exercise_id, session_id, movement_name, movement_type FROM training_exercises")]
    plan = plan_sessions(sessions, exercises, day)
    result = {"date": day, "plan_sessions": len(plan), "duplicates": max(0, len(plan) - 1)}
    if not plan:
        return {**result, "error": "no plan session is stored on this date"}
    new_id = plan[-1]
    base = pick_base(sessions, exercises, new_id, day)
    if base is None:
        return {**result, "error": "no earlier plan session to compare with"}
    base_date = next(s["session_date"] for s in sessions if s["session_id"] == base)
    return {**result, "base_date": base_date, **compare(session_rows(conn, base), session_rows(conn, new_id))}


def main() -> int:
    ap = argparse.ArgumentParser(description="The field check after a session saved by the new app.")
    ap.add_argument("--date", required=True, help="the day of the new app's session, YYYY-MM-DD")
    ap.add_argument("--json", action="store_true", help="print JSON and write reports/rebuild/p6/field_check.json")
    args = ap.parse_args()
    from services import supabase_store
    from services.config import load_config
    secrets = ROOT / ".streamlit" / "secrets.toml"
    overrides = tomllib.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
    cfg = load_config({**overrides, "HEALTH_SYSTEM_OF_RECORD": "supabase"})
    store = supabase_store.SupabaseStore(cfg.supabase_url, cfg.supabase_secret_key)
    conn = sqlite3.connect(":memory:")
    supabase_store.pull(store, conn, list(TABLES))
    result = check(conn, args.date)
    if args.json:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0
    if "error" in result:
        print(f"{args.date}: {result['error']} ({result['plan_sessions']} plan sessions)")
        return 1
    print(f"{args.date}: {result['plan_sessions']} plan session(s), {result['duplicates']} duplicate(s); "
          f"compared with {result['base_date']}")
    print(f"missing: {', '.join(result['missing']) or 'none'}")
    print(f"empty by design here: {', '.join(result['conditional']) or 'none'}")
    print(f"filled later by another job: {', '.join(result['later']) or 'none'}")
    print(f"set times with a UTC offset: {result['set_times_with_offset']}")
    return 0 if not result["missing"] and not result["duplicates"] else 1


if __name__ == "__main__":
    sys.exit(main())
