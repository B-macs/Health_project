"""Every save through the engine API is idempotent (rebuild rule 4), and a
failed write is reported, never dropped (rule 5). The gate's
idempotency_fail counter runs this file.

The phone mints every id once, before the first send, and resends a save it
never heard back about. So, through the real Repository over a fake
Supabase (tests/_record_store.py; Supabase is the record, every write goes
there first and is waited for):

- a training session sent three times stores ONE session;
- a send that stops partway answers 503 with what is stored, and the same
  body sent again completes it, no exercise stored twice;
- a write Supabase refuses answers an error and leaves nothing in the local
  copy for it;
- a yoga flow and an outdoor activity sent twice each store one session;
- a check-in and a wake-time correction sent twice store one row.

No network.
"""

from __future__ import annotations

from datetime import date

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from healthapi.deps import get_repository, get_sync_runner  # noqa: E402
from healthapi.main import create_app  # noqa: E402
from services import checkin_form as cf  # noqa: E402
from services import record_cache, supabase_store  # noqa: E402
from services import yoga as yg  # noqa: E402
from services.background_sync import BackgroundSyncRunner  # noqa: E402
from tests._record_store import (FakeStore, local_rows, new_local_copy,  # noqa: E402
                                 record_config, record_repo)

KEY = "test-engine-key"
TODAY = date(2026, 10, 19)

GOBLET = {"name": "Goblet Squat", "type": "reps", "sets": 3, "reps": 10, "weight_kg": 22.5,
          "equipment_type": "dumbbell", "rest_seconds": 90}
PLANK = {"name": "Forearm Plank", "type": "hold", "sets": 2, "hold_seconds": 30,
         "rest_seconds": 30}


def _sets(n: int, reps: int = 10, weight: float = 22.5) -> list[dict]:
    return [{"set_num": i, "reps": reps, "weight": weight, "rest": 90, "tut": 0,
             "velocity": "controlled", "ts": f"2026-10-19T08:1{i}:00"} for i in range(1, n + 1)]


BODY = {
    "session_id": "2026-10-19-0a1b2c3d", "date": TODAY.isoformat(), "kind": "plan",
    "duration_minutes": 52, "session_rpe": 6, "notes": "Hips felt loose.",
    "exercises": [
        {"exercise_id": "ex-goblet", "exercise": GOBLET, "actual": {"reps": 10, "weight_kg": 22.5},
         "sets": _sets(3), "note": "Last set slow."},
        {"exercise_id": "ex-plank", "exercise": PLANK, "sets": [
            {"set_num": 1, "reps": 1, "weight": 0, "rest": 30, "tut": 30,
             "ts": "2026-10-19T08:20:00"}]},
    ],
}


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


def _client(monkeypatch, repo, path):
    monkeypatch.setenv("HEALTH_ENGINE_KEY", KEY)
    monkeypatch.delenv("HEALTH_PROBES", raising=False)
    app = create_app(startup=False)
    app.dependency_overrides[get_repository] = lambda: repo
    runner = BackgroundSyncRunner(record_config(path))
    app.dependency_overrides[get_sync_runner] = lambda: runner
    return TestClient(app)


def _send(client, method, path, body):
    return getattr(client, method)(path, json=body,
                                   headers={"X-Engine-Key": KEY, "X-Local-Date": TODAY.isoformat()})


def _rows(store: FakeStore, table: str) -> list[dict]:
    return store.tables.get(table, [])


# ── the training session ─────────────────────────────────────────────────────

def test_a_session_sent_three_times_stores_one_session(monkeypatch, local_copy):
    store = FakeStore()
    repo = record_repo(local_copy, store)
    with _client(monkeypatch, repo, local_copy) as c:
        answers = [_send(c, "post", "/api/training/sessions", BODY) for _ in range(3)]
    assert [a.status_code for a in answers] == [200, 200, 200]
    assert answers[0].json() == answers[2].json()
    assert answers[0].json()["au"] == 52 * 6
    exercises = _rows(store, "training_exercises")
    assert sorted(e["exercise_id"] for e in exercises) == ["ex-goblet", "ex-plank"]
    assert {e["session_id"] for e in exercises} == {"2026-10-19-0a1b2c3d"}
    assert len(_rows(store, "training_sessions")) == 1
    goblet_sets = [s for s in _rows(store, "training_sets") if s["exercise_id"] == "ex-goblet"]
    assert len(goblet_sets) == 3, "the sets are replaced, never appended"
    notes = [e.get("notes") or "" for e in exercises]
    assert sum(n.count("Hips felt loose.") for n in notes) == 1, "the session note once"
    local = local_rows(local_copy, "SELECT COUNT(*) FROM training_exercises")[0][0]
    assert local == 2, "the local copy holds the same two exercises"


class DropsOnce(FakeStore):
    """Refuses the `nth` write of a set list once: a connection that drops
    in the middle of a save."""

    def __init__(self, nth: int):
        super().__init__()
        self.nth, self.calls = nth, 0

    def insert(self, table, rows):
        if table == "training_sets":
            self.calls += 1
            if self.calls == self.nth:
                raise supabase_store.SupabaseError("the connection dropped")
        return super().insert(table, rows)


def test_a_save_that_stops_partway_is_completed_by_the_same_body(monkeypatch, local_copy):
    store = DropsOnce(nth=2)
    repo = record_repo(local_copy, store)
    with _client(monkeypatch, repo, local_copy) as c:
        first = _send(c, "post", "/api/training/sessions", BODY)
        again = _send(c, "post", "/api/training/sessions", BODY)
    assert first.status_code == 503
    assert first.json()["error"].startswith("save_incomplete: 1 of 2 exercises stored")
    assert again.status_code == 200
    exercises = _rows(store, "training_exercises")
    assert sorted(e["exercise_id"] for e in exercises) == ["ex-goblet", "ex-plank"]
    assert len([s for s in _rows(store, "training_sets") if s["exercise_id"] == "ex-goblet"]) == 3


def test_a_refused_write_answers_an_error_and_keeps_nothing_locally(monkeypatch, local_copy):
    store = FakeStore(fail_on=("upsert", "training_exercises"))
    repo = record_repo(local_copy, store)
    with _client(monkeypatch, repo, local_copy) as c:
        r = _send(c, "post", "/api/training/sessions", BODY)
    assert r.status_code == 503 and r.json()["error"].startswith("save_incomplete: 0 of 2")
    assert _rows(store, "training_exercises") == []
    assert local_rows(local_copy, "SELECT COUNT(*) FROM training_exercises")[0][0] == 0


def test_a_session_for_a_later_day_is_refused(monkeypatch, local_copy):
    repo = record_repo(local_copy, FakeStore())
    with _client(monkeypatch, repo, local_copy) as c:
        r = _send(c, "post", "/api/training/sessions", {**BODY, "date": "2026-10-20"})
    assert r.status_code == 422 and r.json() == {"error": "future_day"}


def test_two_exercises_with_one_id_are_refused_before_anything_is_written(monkeypatch, local_copy):
    store = FakeStore()
    repo = record_repo(local_copy, store)
    body = {**BODY, "exercises": [dict(BODY["exercises"][0]),
                                  {**BODY["exercises"][1], "exercise_id": "ex-goblet"}]}
    with _client(monkeypatch, repo, local_copy) as c:
        r = _send(c, "post", "/api/training/sessions", body)
    assert r.status_code == 422 and r.json()["error"].startswith("invalid_session")
    assert _rows(store, "training_exercises") == []


def test_a_second_plan_session_on_a_logged_day_is_refused(monkeypatch, local_copy):
    """WP-32 (2026-10-26): after a save the Training tab showed the morning's plan
    with Start, and a second session under new ids would have counted the day
    twice. The engine refuses it; the accessory session still saves that day."""
    store = FakeStore()
    repo = record_repo(local_copy, store)
    second = {**BODY, "session_id": "2026-10-19-ffffffff",
              "exercises": [{**e, "exercise_id": e["exercise_id"] + "-2"} for e in BODY["exercises"]]}
    accessory = {**second, "session_id": "2026-10-19-acc00001", "kind": "accessory",
                 "exercises": [{**e, "exercise_id": e["exercise_id"] + "-acc"} for e in BODY["exercises"]]}
    with _client(monkeypatch, repo, local_copy) as c:
        assert _send(c, "post", "/api/training/sessions", BODY).status_code == 200
        r = _send(c, "post", "/api/training/sessions", second)
        assert _send(c, "post", "/api/training/sessions", BODY).status_code == 200
        assert _send(c, "post", "/api/training/sessions", accessory).status_code == 200
    assert r.status_code == 409 and r.json() == {"error": "already_logged"}
    ids = {row["exercise_id"] for row in _rows(store, "training_exercises")}
    assert "ex-goblet-2" not in ids and {"ex-goblet", "ex-goblet-acc"} <= ids


def test_the_retest_readings_are_stored_once_as_the_morning_s_assessment(monkeypatch, local_copy):
    """WP-33: each test of the retest is its own entry; its reading rides in the
    save and lands in the flexibility record Insights reads, once however often
    the save is sent."""
    store = FakeStore()
    repo = record_repo(local_copy, store)
    test = {"name": "Flexibility Test: Knees fully bent (Test)", "type": "duration", "sets": 1,
            "duration_minutes": 3}
    body = {**BODY, "exercises": BODY["exercises"] + [{
        "exercise_id": "ex-bent", "exercise": test, "sets": [],
        "reading": {"test_key": "leverage_bent", "values": {"left": 20.0, "right": 22.5},
                    "setup_value": 31.0}}]}
    with _client(monkeypatch, repo, local_copy) as c:
        assert _send(c, "post", "/api/training/sessions", body).status_code == 200
        assert _send(c, "post", "/api/training/sessions", body).status_code == 200
        bad = {**body, "session_id": BODY["session_id"], "exercises": body["exercises"][:2] + [{
            **body["exercises"][2], "reading": {"test_key": "made_up", "values": {"": 1.0}}}]}
        refused = _send(c, "post", "/api/training/sessions", bad)
    stored = repo.get_flexibility_assessments()
    assert len(stored) == 1 and stored[0].taken_on == TODAY and stored[0].cold
    assert sorted((r.side, r.value) for r in stored[0].readings) == [("left", 20.0), ("right", 22.5)]
    assert refused.status_code == 422 and refused.json()["error"].startswith("invalid_session")


def test_the_retest_check_answers_from_the_readings_and_writes_nothing(monkeypatch, local_copy):
    store = FakeStore()
    repo = record_repo(local_copy, store)
    with _client(monkeypatch, repo, local_copy) as c:
        ok = _send(c, "post", "/api/training/flexibility-check", {"readings": [
            {"test_key": "leverage_bent", "values": {"left": 20.0, "right": 22.5}}]})
        bad = _send(c, "post", "/api/training/flexibility-check", {"readings": [
            {"test_key": "made_up", "values": {"": 1.0}}]})
    assert ok.status_code == 200 and set(ok.json()) == {"pattern", "label", "reason"}
    assert bad.status_code == 422
    assert repo.get_flexibility_assessments() == ()


# ── yoga and outdoor ─────────────────────────────────────────────────────────

def test_a_yoga_flow_sent_twice_stores_one_session(monkeypatch, local_copy):
    store = FakeStore()
    repo = record_repo(local_copy, store)
    flow = yg.YOGA_LIBRARY[0]
    body = {"slug": flow.slug, "session_id": "2026-10-19-yoga0001",
            "pose_ids": [f"pose-{i}" for i in range(len(flow.poses))], "note": ""}
    other = {**body, "session_id": "2026-10-19-yoga0002",
             "pose_ids": [f"other-{i}" for i in range(len(flow.poses))]}
    with _client(monkeypatch, repo, local_copy) as c:
        first = _send(c, "post", "/api/training/yoga", body)
        again = _send(c, "post", "/api/training/yoga", body)
        second_press = _send(c, "post", "/api/training/yoga", other)
    # The same save sent again answers as it did (the outbox resends after a lost answer);
    # another save of the flow the same day is the one told it was already logged.
    assert first.json() == {"logged": True} and again.json() == {"logged": True}
    assert second_press.json() == {"logged": False}
    exercises = _rows(store, "training_exercises")
    assert len(exercises) == len(flow.poses)
    assert {e["session_id"] for e in exercises} == {"2026-10-19-yoga0001"}


def test_an_outdoor_activity_sent_twice_stores_one_session(monkeypatch, local_copy):
    store = FakeStore()
    repo = record_repo(local_copy, store)
    hike = {"activity_id": "12345", "date": TODAY.isoformat(), "name": "Mittenwald Walking",
            "type": "walking", "duration_minutes": 95.4, "distance_km": 7.2, "avg_hr": 118}
    monkeypatch.setattr(repo, "get_garmin_activities_for_date", lambda d: [hike])
    body = {"date": TODAY.isoformat(), "activity_id": "12345", "rpe": 4,
            "session_id": "2026-10-19-hike0001", "exercise_id": "ex-hike"}
    other = {**body, "session_id": "2026-10-19-hike0002", "exercise_id": "ex-hike-2"}
    with _client(monkeypatch, repo, local_copy) as c:
        first = _send(c, "post", "/api/training/outdoor", body)
        again = _send(c, "post", "/api/training/outdoor", body)
        second_press = _send(c, "post", "/api/training/outdoor", other)
    assert first.status_code == 200 and first.json()["logged"] is True
    assert again.json()["logged"] is True, "the same save sent again answers as it did"
    assert second_press.json()["logged"] is False
    assert len(_rows(store, "training_exercises")) == 1


# ── the check-in and the wake-time correction ────────────────────────────────

def test_a_check_in_sent_twice_stores_one_row(monkeypatch, local_copy):
    store = FakeStore()
    repo = record_repo(local_copy, store)
    body = {"date": TODAY.isoformat(), "opened_entry": False,
            "values": {**cf.FORM_DEFAULTS, "tightness_score": 3}}
    with _client(monkeypatch, repo, local_copy) as c:
        first = _send(c, "put", "/api/checkin", body)
        again = _send(c, "put", "/api/checkin", {**body, "opened_entry": True})
    assert first.status_code == 200 and again.status_code == 200
    rows = _rows(store, "readiness_checkins")
    assert len(rows) == 1 and rows[0]["date"] == TODAY.isoformat()


def test_an_accessory_session_never_marks_the_plan_day_done(monkeypatch, local_copy):
    """T108: the accessory session is stored under its own Type, which keeps
    it out of the plan day's "logged" (Repository.SUPPLEMENTARY_SESSION_TYPES)."""
    from services import accessory as acc
    store = FakeStore()
    repo = record_repo(local_copy, store)
    body = {**BODY, "session_id": "2026-10-19-acce0001", "kind": "accessory",
            "exercises": [{**BODY["exercises"][1], "exercise_id": "ex-acc"}]}
    with _client(monkeypatch, repo, local_copy) as c:
        for _ in range(2):
            assert _send(c, "post", "/api/training/sessions", body).status_code == 200
    rows = _rows(store, "training_exercises")
    assert [r["exercise_id"] for r in rows] == ["ex-acc"]
    assert {r.get("movement_type") for r in rows} == {acc.ACCESSORY_TYPE}
    assert not repo.has_logged_session(TODAY)


def test_a_daily_session_sent_twice_stores_one_session_under_its_own_type(monkeypatch, local_copy):
    """WP-40: the daily tendon session is idempotent like every save, is
    stored under its own Type, and never marks the plan day done."""
    from services import daily_session as dly
    store = FakeStore()
    repo = record_repo(local_copy, store)
    body = {**BODY, "session_id": "2026-10-19-dai10001", "kind": "daily",
            "exercises": [{**BODY["exercises"][1], "exercise_id": "ex-daily"}]}
    with _client(monkeypatch, repo, local_copy) as c:
        for _ in range(2):
            assert _send(c, "post", "/api/training/sessions", body).status_code == 200
    rows = _rows(store, "training_exercises")
    assert [r["exercise_id"] for r in rows] == ["ex-daily"]
    assert {r.get("movement_type") for r in rows} == {dly.DAILY_TYPE}
    assert len(_rows(store, "training_sessions")) == 1
    assert not repo.has_logged_session(TODAY)


# ── the phone's raw sets (rebuild Phase 6) ───────────────────────────────────

SPLIT = {"name": "Split Squat", "type": "reps", "laterality": "unilateral", "sets": 2, "reps": 8,
         "weight_kg": 9.0, "equipment_type": "dumbbell", "rest_seconds": 60}
TEST_HOLD = {"name": "Side Plank (Timed)", "type": "hold", "laterality": "unilateral", "sets": 1,
             "hold_seconds": 30, "rest_seconds": 0}
RAMP = {"name": "Goblet Squat Ramp", "type": "reps", "sets": 1, "reps": 5, "weight_kg": 13.5,
        "equipment_type": "dumbbell", "rest_seconds": 30, "warmup": True}

RAW_BODY = {
    "session_id": "2026-10-19-1a2b3c4d", "date": TODAY.isoformat(), "kind": "plan",
    "duration_minutes": 40, "session_rpe": 7, "notes": "",
    "exercises": [
        {"exercise_id": "ex-ramp", "exercise": RAMP, "raw_sets": [
            {"set_num": 1, "completed_at": "2026-10-19T08:01:00+02:00",
             "right": {"reps": 5, "weight_kg": 13.5}, "rest_started_at": 1000.0, "rest_ended_at": 1030.0}]},
        {"exercise_id": "ex-split", "exercise": SPLIT, "raw_sets": [
            {"set_num": 1, "completed_at": "2026-10-19T08:05:00+02:00",
             "right": {"reps": 8, "weight_kg": 9.0}, "left": {"reps": 7, "weight_kg": 9.0},
             "rest_started_at": 2000.0, "rest_ended_at": 2061.0},
            # The flow's Back redid set 2: the later version is kept.
            {"set_num": 2, "completed_at": "2026-10-19T08:07:00+02:00",
             "right": {"reps": 6, "weight_kg": 9.0}, "left": {"reps": 6, "weight_kg": 9.0}},
            {"set_num": 2, "completed_at": "2026-10-19T08:08:00+02:00",
             "right": {"reps": 8, "weight_kg": 9.0}, "left": {"reps": 8, "weight_kg": 9.0}}]},
        {"exercise_id": "ex-test", "exercise": TEST_HOLD, "raw_sets": [
            {"set_num": 1, "completed_at": "2026-10-19T08:12:00+02:00",
             "right": {"seconds": 41}, "left": {"seconds": 37},
             # A rest of 25 minutes was an interruption, not a rest.
             "rest_started_at": 3000.0, "rest_ended_at": 4500.0}]},
    ],
}


def test_a_skipped_exercise_is_stored_with_no_set_done(monkeypatch, local_copy):
    """WP-22 (2026-10-22): an exercise the phone sends with no raw set was
    skipped. It is stored with its planned sets and none done, and no set row;
    the save used to store its prescription as if it was done."""
    body = {**RAW_BODY, "session_id": "2026-10-19-5c1pped0",
            "exercises": [RAW_BODY["exercises"][1],
                          {"exercise_id": "ex-skipped", "exercise": GOBLET, "raw_sets": []}]}
    store = FakeStore()
    repo = record_repo(local_copy, store)
    with _client(monkeypatch, repo, local_copy) as c:
        assert _send(c, "post", "/api/training/sessions", body).status_code == 200
    skipped = next(r for r in _rows(store, "training_exercises") if r["exercise_id"] == "ex-skipped")
    assert skipped["planned_sets"] == 3 and skipped["actual_sets"] == 0
    assert not [s for s in _rows(store, "training_sets") if s["exercise_id"] == "ex-skipped"]
    assert [s for s in _rows(store, "training_sets") if s["exercise_id"] == "ex-split"]


def test_raw_sets_become_the_engines_own_set_records(monkeypatch, local_copy):
    from services import guided_flow, session_save
    from services import sessions as sess
    store = FakeStore()
    repo = record_repo(local_copy, store)
    with _client(monkeypatch, repo, local_copy) as c:
        answers = [_send(c, "post", "/api/training/sessions", RAW_BODY) for _ in range(3)]
    assert [a.status_code for a in answers] == [200, 200, 200]
    assert len(_rows(store, "training_sessions")) == 1, "three sends, one session"
    sets = {}
    for s in _rows(store, "training_sets"):
        sets.setdefault(s["exercise_id"], []).append(s)
    ramp, split, test = sets["ex-ramp"], sets["ex-split"], sets["ex-test"]
    assert len(ramp) == 1 and ramp[0]["is_warmup"] in (1, True), "a ramp stays a ramp"
    assert ramp[0]["rest_taken_seconds"] == 30
    assert sorted(s["set_num"] for s in split) == [1, 2], "a set sent twice is stored once"
    one = next(s for s in split if s["set_num"] == 1)
    two = next(s for s in split if s["set_num"] == 2)
    assert (one["reps"], one["reps_left"], one["rest_taken_seconds"]) == (8, 7, 61)
    assert two["reps"] == 8 and two.get("reps_left") is None, "the later version, equal sides"
    assert (test[0]["tut"], test[0]["tut_left"]) == (41, 37)
    assert test[0].get("rest_taken_seconds") is None, "an interruption is not a rest"
    # Each record is build_set_record's, the same rule the Streamlit save uses.
    expected = sess.build_set_record(
        SPLIT, 1, {"reps": 8, "weight_kg": 9.0, "reps_left": 7, "weight_kg_left": 9.0},
        "2026-10-19T08:05:00+02:00", guided_flow.rest_taken(2000.0, 2061.0))
    assert session_save.records_from_raw(SPLIT, RAW_BODY["exercises"][1]["raw_sets"][:1]) == [expected]
