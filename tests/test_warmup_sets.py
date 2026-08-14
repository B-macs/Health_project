"""Tests for the three per-set fields added 2026-08-14 with Stage 2B.

`is_warmup`, `rest_taken_seconds` and `reps_left`/`weight_left` are one
migration over one set of rows, which is why they share a test file.

The property that matters most is the DEFAULT. Every set logged before these
fields existed carries none of them, and every one of those was a working set at
an unmeasured rest with both sides equal. An absent key therefore has to read as
"working", "not measured" and "symmetric" — getting `is_warmup` backwards would
silently empty the whole pre-2026-08 tonnage and strength history, which is a
failure that looks exactly like a quiet week.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date

import pytest

import training_plan as tp
from services import sessions, strength, tonnage
from services.clients import notion_reader
from services.repository import _working_volume_kg


def _reps_ex(**kw):
    return tp._ex(name="Goblet Squat", ex_type="reps", mechanics="m",
                  biomechanical_focus="b", progression="p", regression="r",
                  sets=3, reps=10, rest_seconds=90, weight_kg=20.0,
                  equipment_type="dumbbell", **kw)


# ── the default is "working" ────────────────────────────────────────────────

def test_a_set_with_no_flag_is_a_working_set():
    """The whole pre-2026-08 history is this case."""
    assert sessions.is_working_set({"reps": 10, "weight": 20.0}) is True


def test_a_flagged_set_is_not_a_working_set():
    assert sessions.is_working_set({"reps": 6, "weight": 12.5, "is_warmup": True}) is False


def test_the_three_modules_agree_on_what_a_working_set_is():
    """tonnage.py and strength.py import nothing from services/ by design, so
    each repeats the expression inline. This is what stops the three drifting."""
    rows = [{"reps": 10, "weight": 20.0},
            {"reps": 6, "weight": 12.5, "is_warmup": True},
            {"reps": 10, "weight": 20.0, "is_warmup": False}]
    via_sessions = [s for s in rows if sessions.is_working_set(s)]
    via_inline = [s for s in rows if not s.get("is_warmup")]
    assert via_sessions == via_inline
    assert len(via_sessions) == 2


# ── build_set_record: every new key is omit-when-absent ─────────────────────

def test_a_normal_set_record_is_unchanged_by_the_migration():
    """The common case has to stay byte-identical, or every existing reader
    and every stored row starts carrying keys that mean nothing."""
    rec = sessions.build_set_record(_reps_ex(), 1, None, "2026-08-17T09:00:00+01:00")
    assert set(rec) == {"set_num", "reps", "weight", "rest", "tut", "velocity", "ts"}


def test_a_ramp_exercise_flags_every_set_it_logs():
    rec = sessions.build_set_record(_reps_ex(warmup=True), 1, None, "ts")
    assert rec["is_warmup"] is True


def test_rest_taken_is_written_only_when_it_was_measured():
    no_rest = sessions.build_set_record(_reps_ex(), 1, None, "ts")
    assert "rest_taken_seconds" not in no_rest
    measured = sessions.build_set_record(_reps_ex(), 1, None, "ts", rest_taken_seconds=104)
    assert measured["rest_taken_seconds"] == 104
    # The prescribed number stays beside it, untouched — they are two different
    # facts about the same interval, and the point is being able to compare them.
    assert measured["rest"] == 90


def test_equal_sides_write_no_side_keys():
    actual = {"reps": 10, "weight_kg": 22.5, "reps_left": 10, "weight_kg_left": 22.5}
    rec = sessions.build_set_record(_reps_ex(), 1, actual, "ts")
    assert "reps_left" not in rec and "weight_left" not in rec


def test_a_weaker_left_side_is_recorded_rather_than_overwriting_the_right():
    """The bug this closes: editing the left side used to rewrite the whole row,
    so a lighter left arm read as the prescribed weight being declined."""
    actual = {"reps": 10, "weight_kg": 22.5, "reps_left": 8, "weight_kg_left": 20.0}
    rec = sessions.build_set_record(_reps_ex(), 1, actual, "ts")
    assert (rec["reps"], rec["weight"]) == (10, 22.5)
    assert (rec["reps_left"], rec["weight_left"]) == (8, 20.0)


def test_make_sets_data_carries_the_warmup_flag_too():
    """A session saved from the day-overview screen must not launder its ramp
    sets into working ones."""
    rows = sessions.make_sets_data(_reps_ex(warmup=True))
    assert rows and all(r["is_warmup"] is True for r in rows)
    assert all("is_warmup" not in r for r in sessions.make_sets_data(_reps_ex()))


# ── the readers ─────────────────────────────────────────────────────────────

REGION_MAP = {"Goblet Squat": "lower_body"}
TODAY = date(2026, 9, 1)


def test_a_ramp_set_adds_no_tonnage():
    working = [{"reps": 10, "weight": 20.0}] * 3
    ramp = [{"reps": 6, "weight": 12.5, "is_warmup": True}]
    rows = [{"movement_name": "Goblet Squat", "session_date": "2026-08-31",
             "sets": ramp + working}]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=2)
    week = next(w for w in series if w.week_start == date(2026, 8, 31))
    assert week.value("lower_body").kg == pytest.approx(600.0)   # not 675.0
    assert week.value("lower_body").sets == 3


def test_a_ramp_set_never_reaches_a_1rm_estimate():
    rows = [{"movement_name": "Goblet Squat", "session_date": "2026-08-31",
             "exercise_rpe": 7,
             "sets": [{"reps": 6, "weight": 12.5, "is_warmup": True},
                      {"reps": 10, "weight": 20.0}]}]
    out = list(strength.qualifying_rows(rows, TODAY))
    assert len(out) == 1
    _name, _day, loaded, _rpe = out[0]
    assert loaded == [{"reps": 10, "weight": 20.0}]


def test_total_volume_excludes_the_ramp_but_the_set_still_happened():
    """Volume is a claim about work; actual_sets is a count of sets performed.
    The asymmetry is deliberate — see repository._working_volume_kg."""
    sets = [{"reps": 6, "weight": 12.5, "is_warmup": True},
            {"reps": 10, "weight": 20.0}]
    assert _working_volume_kg(sets) == pytest.approx(200.0)
    assert len(sets) == 2


def test_reconstructed_duration_still_counts_the_ramp_and_the_prescribed_rest():
    """A ramp takes real time, so the session really was that long — and the
    rest term stays on the PRESCRIBED number while REST_TAKEN_FEEDS_DURATION is
    False, so Strain and ACWR cannot step on the field's mere existence."""
    assert sessions.REST_TAKEN_FEEDS_DURATION is False
    sets = [{"velocity": "controlled", "reps": 6, "rest": 90, "is_warmup": True,
             "rest_taken_seconds": 300},
            {"velocity": "controlled", "reps": 10, "rest": 90}]
    # 20 + 20 active, plus the FIRST row's prescribed 90 (never its measured 300)
    assert sessions.exercise_seconds_from_sets(sets) == 130


# ── the projections, which drop unknown keys in silence ─────────────────────

_NEW_KEYS = ("is_warmup", "rest_taken_seconds", "reps_left", "weight_left")


def test_every_projection_of_a_set_row_carries_the_new_keys():
    """Three separate hand-written column lists stand between a logged set and
    storage — the Supabase mirror, the datastore populate, and the offline
    restore. A key missing from any one of them is dropped without raising."""
    import inspect
    from services import datastore, repository

    mirror = inspect.getsource(repository.Repository._mirror_training_write)
    populate = inspect.getsource(datastore._populate_training)
    restore = inspect.getsource(notion_reader._restore_set)
    for key in _NEW_KEYS:
        assert f'"{key}"' in mirror, f"{key} missing from the Supabase mirror projection"
        assert f'"{key}"' in populate, f"{key} missing from the datastore projection"
        assert f'"{key}"' in restore, f"{key} missing from the offline restore"


def test_a_set_round_trips_through_sqlite_with_its_new_fields():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE training_sets (set_num INTEGER, reps REAL, weight REAL, "
        "rest REAL, tut REAL, velocity TEXT, band_tier TEXT, ts TEXT, "
        "is_warmup INTEGER DEFAULT 0, rest_taken_seconds REAL, "
        "reps_left REAL, weight_left REAL)"
    )
    conn.execute(
        "INSERT INTO training_sets VALUES (1, 10.0, 22.5, 90.0, 0.0, 'controlled', "
        "NULL, '2026-08-17T09:00:00+01:00', 1, 104.0, 8.0, 20.0)"
    )
    row = conn.execute("SELECT * FROM training_sets").fetchone()
    out = notion_reader._restore_set(row)
    assert out["is_warmup"] is True
    # Integral fields come back as ints, not "104.0" — a seeded stepper reading
    # "8.0 reps" is the bug _INTEGRAL_SET_FIELDS exists to stop.
    assert out["rest_taken_seconds"] == 104 and isinstance(out["rest_taken_seconds"], int)
    assert out["reps_left"] == 8 and isinstance(out["reps_left"], int)
    assert out["weight_left"] == 20.0


def test_restoring_a_row_from_a_snapshot_built_before_the_columns_existed():
    """datastore.db is a cache the athlete may not have rebuilt. A missing
    column has to read as "not recorded", not raise IndexError on every read."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE training_sets (set_num INTEGER, reps REAL, weight REAL, "
        "rest REAL, tut REAL, velocity TEXT, band_tier TEXT, ts TEXT)"
    )
    conn.execute("INSERT INTO training_sets VALUES (1, 10.0, 20.0, 90.0, 0.0, 'controlled', NULL, NULL)")
    row = conn.execute("SELECT * FROM training_sets").fetchone()
    out = notion_reader._restore_set(row)
    assert out["reps"] == 10
    assert "is_warmup" not in out and "rest_taken_seconds" not in out


def test_the_json_a_ramp_set_stores_is_the_json_that_comes_back():
    rec = sessions.build_set_record(_reps_ex(warmup=True), 1, None, "ts",
                                    rest_taken_seconds=95)
    assert json.loads(json.dumps(rec)) == rec
