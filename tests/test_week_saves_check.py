"""scripts/week_saves_check.py: the check after the owner's training week in the new app
(rebuild Phase 7). It counts each day's plan, yoga, outdoor and accessory sessions, and
what is stored twice (a second plan session, the same yoga flow or accessory session
twice, the same Garmin activity twice), and lists the week's schedule notes by date with
whether the session moved, never a name, a note or a reading."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("week_saves_check", ROOT / "scripts" / "week_saves_check.py")
wc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wc)

MON, TUE, WED = "2026-10-19", "2026-10-20", "2026-10-21"


def _db(sessions, exercises, phases=None) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript((ROOT / "services" / "datastore_schema.sql").read_text(encoding="utf-8"))
    for sid, day in sessions:
        conn.execute("INSERT INTO training_sessions (session_id, session_date) VALUES (?, ?)", (sid, day))
    for i, (sid, day, name, kind, notes) in enumerate(exercises):
        conn.execute("INSERT INTO training_exercises (exercise_id, session_id, session_date, movement_name, "
                     "movement_type, notes) VALUES (?, ?, ?, ?, ?, ?)", (f"e{i}", sid, day, name, kind, notes))
    if phases is not None:
        conn.execute("INSERT INTO config (key, value) VALUES ('phases', ?)", (json.dumps(phases),))
    return conn


def test_a_clean_week_stores_each_save_once():
    conn = _db([("p1", MON), ("y1", MON), ("o1", TUE), ("a1", TUE), ("p2", WED)],
               [("p1", MON, "Hack Squat", "Strength", ""), ("y1", MON, "Pose A", "Yoga", ""),
                ("y1", MON, "Pose B", "Yoga", ""), ("o1", TUE, "Outdoor Walk", "Outdoor", "activity 501"),
                ("a1", TUE, "Dead Bug", "Accessory", ""), ("p2", WED, "Row", "Strength", "")])
    out = wc.check(conn, MON, WED)
    assert out["duplicates"] == 0
    assert out["days"][MON] == {"plan": 1, "yoga": 1, "outdoor": 0, "accessory": 0,
                                "duplicates": {"plan": 0, "yoga": 0, "outdoor": 0, "accessory": 0}}
    assert out["days"][TUE]["outdoor"] == 1 and out["days"][TUE]["accessory"] == 1


def test_each_kind_stored_twice_is_counted():
    conn = _db([("p1", MON), ("p2", MON), ("y1", TUE), ("y2", TUE), ("o1", WED), ("o2", WED),
                ("a1", WED), ("a2", WED)],
               [("p1", MON, "Hack Squat", "Strength", ""), ("p2", MON, "Hack Squat", "Strength", ""),
                ("y1", TUE, "Pose A", "Yoga", ""), ("y2", TUE, "Pose A", "Yoga", ""),
                ("o1", WED, "Outdoor Walk", "Outdoor", "activity 501"),
                ("o2", WED, "Outdoor Walk", "Outdoor", "Garmin: walking, activity 501"),
                ("a1", WED, "Dead Bug", "Accessory", ""), ("a2", WED, "Dead Bug", "Accessory", "")])
    out = wc.check(conn, MON, WED)
    assert out["days"][MON]["duplicates"]["plan"] == 1
    assert out["days"][TUE]["duplicates"]["yoga"] == 1
    assert out["days"][WED]["duplicates"] == {"plan": 0, "yoga": 0, "outdoor": 1, "accessory": 1}
    assert out["duplicates"] == 4


def test_two_different_yoga_flows_or_activities_are_not_duplicates():
    conn = _db([("y1", MON), ("y2", MON), ("o1", MON), ("o2", MON)],
               [("y1", MON, "Pose A", "Yoga", ""), ("y2", MON, "Pose C", "Yoga", ""),
                ("o1", MON, "Outdoor Walk", "Outdoor", "activity 501"),
                ("o2", MON, "Outdoor Hike", "Outdoor", "activity 5012")])
    out = wc.check(conn, MON, MON)
    assert out["duplicates"] == 0 and out["days"][MON]["yoga"] == 2 and out["days"][MON]["outdoor"] == 2


def test_the_schedule_notes_show_dates_and_whether_they_moved_never_the_reason():
    phases = [{"phase_number": 5, "shift_reasons": {
        TUE: "Missed session carried forward from 2026-10-19",
        WED: "Declined: left as missed by choice",
        "2026-10-30": "outside the week"}}]
    conn = _db([], [], phases)
    out = wc.check(conn, MON, WED)
    assert [m["date"] for m in out["moves"]] == [TUE, WED]
    assert all(set(m) == {"date", "moved"} for m in out["moves"])
    assert "reason" not in json.dumps(out) and "Declined" not in json.dumps(out)


def test_the_output_names_no_exercise_and_no_note():
    conn = _db([("o1", MON)], [("o1", MON, "Outdoor Walk", "Outdoor", "activity 501 heart rate 118")])
    text = json.dumps(wc.check(conn, MON, MON))
    assert "Outdoor Walk" not in text and "118" not in text and "501" not in text
