"""services/supplementary_save.py against a fake Supabase in record mode.

Moved out of views/training.py on 2026-10-19 (moves TRN-17, TRN-18) so the
phone's API saves yoga and outdoor sessions the same way. What it pins: a save
sent again rewrites the same rows (caller-minted ids); a second save with OTHER
ids (a second browser or phone) continues the first one's session and writes
nothing twice, which is the 2026-10-05 failure (one press, 51 sessions); the
session note is added once; an outdoor activity is logged once, and its AU
preview is the AU stored.
"""

from __future__ import annotations

from datetime import date

import pytest

from services import record_cache, session_save, supabase_store
from services import supplementary_save as sup
from services import yoga as yg
from tests._record_store import FakeStore, new_local_copy, record_repo

DAY = date(2026, 10, 19)
FLOW = yg.YOGA_LIBRARY[0]


@pytest.fixture(autouse=True)
def _empty_outbox():
    supabase_store.OUTBOX.drain()
    yield
    supabase_store.OUTBOX.drain()


@pytest.fixture
def local_copy(tmp_path):
    path = new_local_copy(tmp_path)
    yield path
    record_cache.forget(path)


def _ids(n):
    return session_save.new_exercise_ids(n)


def _sessions(store, kind):
    return {r["session_id"] for r in store.tables.get("training_exercises", [])
            if r.get("movement_type") == kind}


def test_a_yoga_flow_sent_again_with_the_same_ids_stores_it_once(local_copy):
    store = FakeStore()
    repo = record_repo(local_copy, store)
    sid, ids = "2026-10-19-yoga0001", _ids(len(FLOW.poses))
    assert sup.save_yoga(repo, FLOW, DAY, 2, sid, ids, note="Hips opened up")
    assert not sup.save_yoga(repo, FLOW, DAY, 2, sid, ids, note="Hips opened up")
    assert _sessions(store, sup.YOGA_TYPE) == {sid}
    assert len(store.tables["training_exercises"]) == len(FLOW.poses)


def test_a_second_device_continues_the_first_session_and_writes_nothing_twice(local_copy):
    """The 2026-10-05 failure: every run minted its own id."""
    store = FakeStore()
    repo = record_repo(local_copy, store)
    first = "2026-10-19-yoga0001"
    half = len(FLOW.poses) // 2
    # The first device stopped after half the poses: simulate by saving a
    # shorter flow under its id.
    partial = yg.YogaSession(**{**FLOW.__dict__, "poses": FLOW.poses[:half]})
    assert sup.save_yoga(repo, partial, DAY, 2, first, _ids(half))
    assert sup.save_yoga(repo, FLOW, DAY, 2, "2026-10-19-yoga0002", _ids(len(FLOW.poses)))
    assert _sessions(store, sup.YOGA_TYPE) == {first}
    names = [r["movement_name"] for r in store.tables["training_exercises"]]
    assert sorted(names) == sorted(p.name for p in FLOW.poses)


def test_the_yoga_note_is_added_once_to_the_last_pose(local_copy):
    store = FakeStore()
    repo = record_repo(local_copy, store)
    sid, ids = "2026-10-19-yoga0001", _ids(len(FLOW.poses))
    sup.save_yoga(repo, FLOW, DAY, 2, sid, ids, note="Hips opened up")
    last = next(r for r in store.tables["training_exercises"] if r["exercise_id"] == ids[-1])
    assert (last.get("notes") or "").endswith("Hips opened up")
    assert (last.get("notes") or "").count("Hips opened up") == 1


def test_a_yoga_flow_needs_one_id_per_pose(local_copy):
    with pytest.raises(ValueError):
        sup.save_yoga(record_repo(local_copy, FakeStore()), FLOW, DAY, 2, "s", _ids(1))


ACT = {"activity_id": 98765, "type": "hiking", "name": "Mittenwald", "duration_minutes": 47.6,
       "start_time_local": "2026-10-19 09:12:00", "avg_hr": 118, "max_hr": "151",
       "distance_km": "6.2", "calories": ""}


def test_an_outdoor_activity_is_logged_once_and_its_preview_is_what_is_stored(local_copy):
    store = FakeStore()
    repo = record_repo(local_copy, store)
    assert sup.outdoor_minutes(ACT) == 48 and sup.outdoor_au(ACT, 3) == 144.0
    assert sup.save_outdoor(repo, DAY, ACT, 3, "2026-10-19-out00001", "ex-1")
    assert not sup.save_outdoor(repo, DAY, ACT, 3, "2026-10-19-out00002", "ex-2")
    [row] = store.tables["training_exercises"]
    assert row["movement_name"] == "Outdoor Hike" and "activity 98765" in row["notes"]
    assert row["garmin_max_hr"] == 151.0 and row.get("garmin_calories") is None
    [session] = store.tables["training_sessions"]
    assert session["session_au"] == 144.0 and session["session_duration_minutes"] == 48


def test_the_outdoor_family_is_offered_first_and_everything_stays_pickable():
    rows = [{"type": "cycling"}, {"type": "hiking"}, {"type": "strength_training"},
            {"type": "walking"}]
    assert [r["type"] for r in sup.order_activities(rows)] == [
        "hiking", "walking", "cycling", "strength_training"]
