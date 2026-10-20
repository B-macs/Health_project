"""scripts/session_field_check.py: the field check after the owner's real session in the
new app (rebuild Phase 6). It finds the day's plan session (a yoga, outdoor or accessory
session is not one), counts duplicates, picks the Streamlit session to compare with, and
names the fields the new save leaves empty, never a value."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("session_field_check", ROOT / "scripts" / "session_field_check.py")
fc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fc)

DAY, BEFORE, LONG_AGO = "2026-10-21", "2026-10-19", "2026-10-12"


def _db(sessions, exercises, sets) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript((ROOT / "services" / "datastore_schema.sql").read_text(encoding="utf-8"))
    for table, rows in (("training_sessions", sessions), ("training_exercises", exercises),
                        ("training_sets", sets)):
        for r in rows:
            cols = ", ".join(r)
            conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({', '.join('?' * len(r))})", list(r.values()))
    return conn


def _session(sid, day, rpe=6):
    return {"session_id": sid, "session_date": day, "session_duration_minutes": 50, "session_rpe": rpe,
            "session_au": rpe * 50}


def _exercise(eid, sid, day, name, kind="Strength", notes="", hr_rpe=None):
    return {"exercise_id": eid, "session_id": sid, "session_date": day, "movement_name": name,
            "movement_type": kind, "planned_sets": 2, "planned_reps": 10, "actual_sets": 2,
            "total_volume_kg": 400, "notes": notes, "exercise_rpe": hr_rpe}


def _set(eid, n, weight=20.0, ts="2026-10-19T08:00:00+02:00", rest=60, left=None):
    return {"exercise_id": eid, "set_num": n, "reps": 10, "weight": weight, "ts": ts,
            "is_warmup": 0, "rest_taken_seconds": rest, "reps_left": left}


def _store(new_sets=None, extra_sessions=(), extra_exercises=()):
    sessions = [_session("old", BEFORE), _session("older", LONG_AGO), _session("yoga", DAY),
                _session("new", DAY), *extra_sessions]
    exercises = [
        _exercise("o1", "old", BEFORE, "Squat", notes="felt fine", hr_rpe=6.5),
        _exercise("o2", "old", BEFORE, "Row"),
        _exercise("x1", "older", LONG_AGO, "Squat"),
        _exercise("y1", "yoga", DAY, "Flow", kind="Yoga"),
        _exercise("n1", "new", DAY, "Squat"),
        _exercise("n2", "new", DAY, "Row"),
        *extra_exercises,
    ]
    sets = [_set("o1", 1, left=9), _set("o1", 2, rest=None), _set("o2", 1), _set("x1", 1),
            *(new_sets if new_sets is not None else
              [_set("n1", 1, ts="2026-10-21T08:00:00+02:00"), _set("n1", 2, ts="2026-10-21T08:03:00+02:00", rest=None),
               _set("n2", 1, ts="2026-10-21T08:10:00+02:00")])]
    return _db(sessions, exercises, sets)


def test_a_full_save_misses_nothing_and_names_what_is_empty_by_design():
    result = fc.check(_store(), DAY)
    assert (result["plan_sessions"], result["duplicates"], result["base_date"]) == (1, 0, BEFORE)
    assert result["missing"] == []
    # The left side was equal, the note was not written, the heart-rate sync has not run.
    assert "training_sets.reps_left" in result["conditional"]
    assert "training_exercises.notes" in result["conditional"]
    assert result["later"] == ["training_exercises.exercise_rpe"]
    assert result["set_times_with_offset"] == "3/3"


def test_a_field_the_new_save_never_fills_is_missing():
    sets = [_set("n1", 1, weight=None, ts=None), _set("n1", 2, weight=None, ts=None), _set("n2", 1, weight=None, ts=None)]
    result = fc.check(_store(new_sets=sets), DAY)
    assert set(result["missing"]) == {"training_sets.weight", "training_sets.ts"}
    assert result["tables"]["training_sets"]["weight"] == {"old": "3/3", "new": "0/3"}


def test_a_second_plan_session_on_the_day_is_a_duplicate_and_yoga_is_not():
    result = fc.check(_store(extra_sessions=[_session("again", DAY)],
                             extra_exercises=[_exercise("a1", "again", DAY, "Squat")]), DAY)
    assert (result["plan_sessions"], result["duplicates"]) == (2, 1)
    alone = fc.check(_store(), DAY)
    assert alone["plan_sessions"] == 1, "the yoga session on the same day is not a plan session"


def test_the_base_shares_the_most_exercises_with_the_new_session():
    assert fc.check(_store(), DAY)["base_date"] == BEFORE
    sessions = [{"session_id": s, "session_date": d} for s, d in (("a", "2026-10-10"), ("b", "2026-10-11"), ("n", DAY))]
    exercises = [{"session_id": "a", "movement_name": "Squat", "movement_type": "S"},
                 {"session_id": "a", "movement_name": "Row", "movement_type": "S"},
                 {"session_id": "b", "movement_name": "Squat", "movement_type": "S"},
                 {"session_id": "n", "movement_name": "Squat", "movement_type": "S"},
                 {"session_id": "n", "movement_name": "Row", "movement_type": "S"}]
    assert fc.pick_base(sessions, exercises, "n", DAY) == "a", "two shared beats one, though older"


def test_no_session_that_day_says_so():
    result = fc.check(_store(), "2026-10-30")
    assert result["plan_sessions"] == 0 and "error" in result


def test_the_answer_holds_names_and_counts_never_a_value():
    text = json.dumps(fc.check(_store(), DAY))
    for value in ("felt fine", "20.0", "2026-10-21T08", "400", "6.5"):
        assert value not in text, value
