"""The watch's walks that count, and the body areas' load (2026-10-20).

A walk counts on the day walked unless a logged session holds it (the date's
heart-rate match, or an outdoor import's "activity <id>" note); a gym session
on the watch is never a walk. The body-area panel reads the WEIGHTED load, so
an area can never read above the day. Made-up rows, no store.
"""

from __future__ import annotations

from datetime import date

import pytest

from services import hr_matching
from services import repository as repo_mod


def _bare():
    return repo_mod.Repository.__new__(repo_mod.Repository)


def test_only_the_walks_no_session_holds_count(monkeypatch):
    repo = _bare()
    acts = [
        {"activity_id": 1, "date": "2026-10-17", "type": "walking", "name": "Walk",
         "duration_minutes": 124, "avg_hr": 100},
        {"activity_id": 2, "date": "2026-10-17", "type": "walking", "name": "To the gym",
         "duration_minutes": 20, "avg_hr": 100},
        {"activity_id": 3, "date": "2026-10-18", "type": "hiking", "duration_minutes": 90, "avg_hr": 110},
        {"activity_id": 4, "date": "2026-10-19", "type": "indoor_cardio", "duration_minutes": 65, "avg_hr": 119},
        {"activity_id": 5, "date": "2026-09-01", "type": "walking", "duration_minutes": 30, "avg_hr": 100},
    ]
    repo._garmin_activities_ws = lambda: None
    repo._read_records = lambda _ws: acts
    repo.get_session_hr_history = lambda start=None: [
        {"date": "2026-10-17", "activity_type": "walking", "activity_name": "To the gym", "avg_hr": 100.0}]
    repo.get_all_training_exercises_raw = lambda: [
        {"session_date": "2026-10-18", "notes": "Garmin import: Hike [hiking], activity 3"}]
    repo.get_observed_hr_max = lambda days=365, today=None: 178.0
    out = repo.get_watch_cardio(start="2026-10-01", end="2026-10-20")
    assert list(out) == ["2026-10-17"]
    [walk] = out["2026-10-17"]
    assert walk["activity_id"] == "1" and walk["load"] == 124.0


def test_the_body_areas_read_the_weighted_load(monkeypatch):
    repo = _bare()
    session = {"session_id": "s", "date": "2026-10-20", "au": 455.0, "multiplier": 0.75,
               "weighted_au": 341.25, "elapsed_seconds": 3900,
               "exercise_seconds": [{"name": "Single-Arm DB Row", "seconds": 600}]}
    repo._weighted_sessions = lambda days=28, today=None: [session]
    rows = repo.get_daily_region_au(days=7, today=date(2026, 10, 20))["rows"]
    assert rows[0]["total_au"] == pytest.approx(341.25, abs=0.06), "the weighted load, never the raw 455"


def test_a_match_row_holds_the_activity_with_its_type_and_name():
    """A stored match row names no id: date, type and name decide, and the
    closest average heart rate breaks a tie. Each activity is held once."""
    acts = [
        {"activity_id": 7, "date": "2026-10-07", "type": "walking", "name": "Walk", "avg_hr": 95},
        {"activity_id": 8, "date": "2026-10-07", "type": "walking", "name": "Walk", "avg_hr": 106},
        {"activity_id": 9, "date": "2026-10-08", "type": "walking", "name": "Walk", "avg_hr": 106},
        {"activity_id": 10, "date": "2026-10-07", "type": "hiking", "name": "Walk", "avg_hr": 106},
    ]
    one = [{"date": "2026-10-07", "activity_type": "walking", "activity_name": "Walk", "avg_hr": 106.0}]
    assert hr_matching.held_activity_ids(one, acts) == {"8"}
    two = one + [{"date": "2026-10-07", "activity_type": "walking", "activity_name": "Walk", "avg_hr": 106.0}]
    assert hr_matching.held_activity_ids(two, acts) == {"7", "8"}, "never the same walk twice"
    assert hr_matching.held_activity_ids([{"activity_id": 9}], acts) == {"9"}
    assert hr_matching.held_activity_ids(
        [{"date": "2026-10-07", "activity_type": "running", "activity_name": "Walk"}], acts) == set()
