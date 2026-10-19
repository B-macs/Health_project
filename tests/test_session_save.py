"""services/session_save.py: one save of a complete training session.

The Training page and the phone's API both store a session through it. What
this pins:

  * the same save sent three times stores ONE session. The phone resends a
    save it never heard back about, and 2026-09-10 was stored three times
    when every press of Save minted fresh ids;
  * a send that stops partway is completed by the next send of the same save,
    with no exercise stored twice;
  * the session note is added once, however often the save is sent;
  * the flow's live values (steppers, Garmin minutes, per-set records)
    replace the prescription, as the Training page always stored them;
  * a save that cannot be stored whole is refused before anything is written.

Against a fake Supabase (tests/_record_store.py). No network.
"""

from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from services import record_cache, session_save, sessions as sess, supabase_store
from tests._record_store import FakeStore, local_rows, new_local_copy, record_repo

GOBLET = {"name": "Goblet Squat", "type": "reps", "sets": 3, "reps": 10, "weight_kg": 22.5,
          "equipment_type": "dumbbell", "rest_seconds": 90}
PLANK = {"name": "Forearm Plank", "type": "hold", "sets": 2, "hold_seconds": 30,
         "rest_seconds": 30}
WALK = {"name": "Incline Walk", "type": "duration", "duration_minutes": 15}
BAND_ROW = {"name": "Band Row", "type": "reps", "sets": 2, "reps": 12, "equipment_type": "band",
            "band_tier": "Green", "rest_seconds": 60}
MARCH = {"name": "Standing Psoas March", "type": "reps", "sets": 2, "reps": 20,
         "rest_seconds": 30}
PALLOF_HOLD = {"name": "Pallof Hold", "type": "hold_reps", "sets": 2, "reps_in_set": 4,
               "hold_seconds": 5, "rest_seconds": 45, "equipment_type": "cable"}

PENDING = {"session_id": "2026-10-19-0a1b2c3d", "session_date": "2026-10-19",
           "duration_minutes": 52, "session_rpe": 6, "exercise_ids": ["ex-goblet", "ex-plank"]}
GOBLET_SETS = [{"set_num": n, "reps": 10, "weight": 22.5, "rest": 90, "tut": 0,
                "velocity": "controlled", "ts": f"2026-10-19T08:1{n}:00"} for n in (1, 2, 3)]


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


def _session(notes: str = "", user_notes: dict | None = None) -> session_save.SessionSave:
    return session_save.build_session(PENDING, [GOBLET, PLANK], set_log={0: GOBLET_SETS},
                                      notes_by_idx=user_notes or {}, session_notes=notes)


def _rows(store: FakeStore, table: str) -> list[dict]:
    return store.tables.get(table, [])


class DropsOneSetsWrite(FakeStore):
    """Fails the `nth` write of a set list, once: a connection that drops in
    the middle of a save."""

    def __init__(self, nth: int):
        super().__init__()
        self.nth, self.calls = nth, 0

    def insert(self, table, rows):
        if table == "training_sets":
            self.calls += 1
            if self.calls == self.nth:
                raise supabase_store.SupabaseError("connection dropped")
        return super().insert(table, rows)


# ─── the same save, sent again ───────────────────────────────────────────────

def test_a_session_sent_three_times_is_stored_once(local_copy):
    store = FakeStore()
    repo = record_repo(local_copy, store)
    session = _session()
    for _ in range(3):
        assert session_save.save_session(repo, session) == ["ex-goblet", "ex-plank"]
    assert [r["session_id"] for r in _rows(store, "training_sessions")] == ["2026-10-19-0a1b2c3d"]
    assert sorted(r["exercise_id"] for r in _rows(store, "training_exercises")) == [
        "ex-goblet", "ex-plank"]
    assert len(_rows(store, "training_sets")) == 3 + 2
    assert local_rows(local_copy, "SELECT COUNT(*) FROM training_sets") == [(5,)]
    assert local_rows(local_copy, "SELECT session_au FROM training_sessions") == [(312.0,)]
    assert repo.get_logged_session_dates(date(2026, 10, 19), date(2026, 10, 19)) == {"2026-10-19"}


def test_a_send_that_stops_partway_is_completed_by_the_next_without_a_duplicate(local_copy):
    store = DropsOneSetsWrite(nth=2)          # the plank's sets, on the first send
    repo = record_repo(local_copy, store)
    session = _session()
    with pytest.raises(session_save.SessionSaveError) as stopped:
        session_save.save_session(repo, session)
    assert (stopped.value.written, stopped.value.total) == (1, 2)
    # The failed exercise is absent, never stored without its sets.
    assert [r["exercise_id"] for r in _rows(store, "training_exercises")] == ["ex-goblet"]

    assert session_save.save_session(repo, session) == ["ex-goblet", "ex-plank"]
    assert len(_rows(store, "training_sessions")) == 1
    assert sorted(r["exercise_id"] for r in _rows(store, "training_exercises")) == [
        "ex-goblet", "ex-plank"]
    assert local_rows(local_copy, "SELECT COUNT(*) FROM training_sets") == [(5,)]


def test_the_session_note_is_added_once_to_the_last_exercise(local_copy):
    store = FakeStore()
    repo = record_repo(local_copy, store)
    session = _session(notes="Hips felt loose", user_notes={1: "Left side shook at 25 s "})
    for _ in range(2):
        session_save.save_session(repo, session)
    notes = {r["exercise_id"]: r.get("notes") for r in _rows(store, "training_exercises")}
    assert notes["ex-plank"] == "Left side shook at 25 s\n\nHips felt loose"
    assert not notes["ex-goblet"]


def test_each_exercise_waits_for_its_own_heart_rate_rpe(local_copy):
    """The session's one rating is never copied onto every exercise:
    Repository.reassign_exercise_rpe_from_hr fills each one in later."""
    store = FakeStore()
    session_save.save_session(record_repo(local_copy, store), _session())
    assert all(r.get("exercise_rpe") is None for r in _rows(store, "training_exercises"))


# ─── refused before anything is written ──────────────────────────────────────

@pytest.mark.parametrize("change", [
    {"session_id": " "},
    {"session_date": "19/10/2026"},
    {"exercises": ()},
    {"exercises": (dataclasses.replace(_session().exercises[0], exercise_id=""),)},
    {"exercises": (_session().exercises[0], _session().exercises[0])},
])
def test_a_save_that_cannot_be_stored_whole_is_refused_before_anything_is_written(
        local_copy, change):
    store = FakeStore()
    with pytest.raises(ValueError):
        session_save.save_session(record_repo(local_copy, store),
                                  dataclasses.replace(_session(), **change))
    assert store.log == []


# ─── the ids: minted once, by the caller ─────────────────────────────────────

def test_ids_are_minted_once_and_every_retry_sends_the_first_press():
    first = session_save.pending_save(date(2026, 10, 19), 52, 6, 3)
    assert first["session_id"].startswith("2026-10-19-")
    assert len(set(first["exercise_ids"])) == 3
    # A later press, after more time and with another rating, resends the first.
    assert session_save.pending_save(date(2026, 10, 19), 60, 7, 3, earlier=first) == first


def test_a_save_begun_before_the_caller_minted_ids_keeps_its_session():
    old = {"session_id": "2026-10-19-abcd1234", "session_date": "2026-10-19",
           "duration_minutes": 52, "session_rpe": 6, "session_au": 312.0}
    new = session_save.pending_save(date(2026, 10, 19), 60, 7, 2, earlier=old)
    assert (new["session_id"], new["duration_minutes"], new["session_rpe"]) == (
        "2026-10-19-abcd1234", 52, 6)
    assert len(set(new["exercise_ids"])) == 2


def test_the_store_keeps_the_callers_exercise_id(local_copy):
    store = FakeStore()
    repo = record_repo(local_copy, store)
    assert repo.save_training_exercise(
        session_id="2026-10-19-0a1b2c3d", movement_name="Goblet Squat",
        movement_type="Squat Pattern", planned_sets=3, planned_reps=10, rpe=None,
        sets=GOBLET_SETS, session_date="2026-10-19", session_duration_minutes=52,
        session_rpe=6, session_au=312.0, exercise_id="ex-goblet") == "ex-goblet"
    assert [r["exercise_id"] for r in _rows(store, "training_exercises")] == ["ex-goblet"]


# ─── what is stored for each exercise ────────────────────────────────────────

def test_the_per_set_records_are_the_sets():
    ex = session_save.exercise_from_flow(GOBLET, "e", logged_sets=GOBLET_SETS,
                                         actual={"reps": 8, "weight_kg": 30.0})
    assert list(ex.sets) == GOBLET_SETS


def test_without_set_records_the_stepped_values_replace_the_prescription():
    ex = session_save.exercise_from_flow(GOBLET, "e", actual={"reps": 9, "weight_kg": 25.0})
    assert [(s["reps"], s["weight"]) for s in ex.sets] == [(9, 25.0)] * 3
    assert (ex.planned_sets, ex.planned_reps) == (3, 10)          # the plan, as written
    assert GOBLET["reps"] == 10 and GOBLET["weight_kg"] == 22.5   # the plan is not changed


@pytest.mark.parametrize("ex, actual, expected", [
    (BAND_ROW, {"reps": 14, "band_tier": "Blue"}, [(14, "Blue")] * 2),
    (MARCH, {"reps": 18}, [(18, None)] * 2),                       # unloaded reps step too
    (PALLOF_HOLD, {"reps": 5, "weight_kg": 7.0}, [(5, None)] * 2),   # hold reps per set
])
def test_each_kind_of_stepper_is_stored(ex, actual, expected):
    sets = session_save.exercise_from_flow(ex, "e", actual=actual).sets
    assert [(s["reps"], s.get("band_tier")) for s in sets] == expected


def test_a_held_exercise_keeps_its_prescription_whatever_a_stepper_says():
    sets = session_save.exercise_from_flow(PLANK, "e", actual={"reps": 3}).sets
    assert [(s["reps"], s["tut"]) for s in sets] == [(1, 30)] * 2


def test_garmin_minutes_replace_the_planned_minutes_and_say_so():
    ex = session_save.exercise_from_flow(
        WALK, "e", garmin_minutes=17.6, user_note="  Calves tight ",
        garmin_detail={"avg_hr": 121.0, "max_hr": 139.0, "distance_km": 1.4, "calories": 98.0})
    assert ex.sets[0]["tut"] == pytest.approx(17.6 * 60)
    assert ex.note == "Garmin-verified duration: 18 min (planned 15 min).\nCalves tight"
    assert (ex.garmin_avg_hr, ex.garmin_max_hr, ex.garmin_distance_km, ex.garmin_calories) == (
        121.0, 139.0, 1.4, 98.0)


def test_the_movement_type_is_the_exercises_unless_one_type_is_given():
    plain = session_save.build_session(PENDING, [GOBLET, PLANK])
    assert [e.movement_type for e in plain.exercises] == [
        sess.movement_category(GOBLET), sess.movement_category(PLANK)]
    accessory = session_save.build_session(PENDING, [GOBLET, PLANK],
                                           movement_type_override="Accessory")
    assert {e.movement_type for e in accessory.exercises} == {"Accessory"}


def test_one_id_per_exercise_or_nothing_is_built():
    with pytest.raises(ValueError):
        session_save.build_session({**PENDING, "exercise_ids": ["only-one"]}, [GOBLET, PLANK])


@pytest.mark.parametrize("note, session_note, expected", [
    ("", "", ""),
    ("Felt strong", "", "Felt strong"),
    ("", " Hips loose ", "Hips loose"),
    ("Felt strong ", "Hips loose", "Felt strong\n\nHips loose"),
])
def test_the_session_note_joins_the_way_the_notes_were_appended(note, session_note, expected):
    assert session_save.with_session_note(note, session_note) == expected


def test_a_joined_note_is_cut_to_the_column_limit():
    joined = session_save.with_session_note("a" * 1990, "b" * 50)
    assert len(joined) == session_save.NOTE_LIMIT
