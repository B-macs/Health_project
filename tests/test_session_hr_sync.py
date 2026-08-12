"""
Repository.sync_session_hr_for_date — the HR half of strain.

THE BUG THIS EXISTS FOR. Until 2026-08-10 this method read `ex.sets` off
models.ExerciseEntry, which has no `sets` field — it carries the aggregates
(actual_sets, total_volume_kg) and no per-set detail. So it raised
AttributeError on EVERY call, and the failure was invisible from every
direction:

  * save_session_hr is the next statement after the broken expression, so it
    was never reached;
  * that caller only runs inside run_sync_if_due, which catches and returns
    (False, message) — a tuple that reads exactly like "no Garmin activity
    today", an ordinary outcome;
  * views/training.py calls compute_session_hr directly for the on-screen
    figure and never calls save_session_hr, so the screen looked fine;
  * the one existing test that touches the method monkeypatches the method
    itself.

Consequence: get_session_hr_history() always returned [], blend_strain always
returned SOURCE_RPE, and the Edwards'-TRIMP half of strain — the 70% HR
weighting, the "Garmin HR + RPE" source label, the whole hr_load blend — had
reached the displayed number on ZERO days ever.

The per-set timestamps it needs live in the "Sets" rich_text JSON, which is
what get_session_sets_by_exercise reads.

WHY KEYED BY MOVEMENT NAME. compute_session_hr has two callers that count
exercises differently: views/training.py passes live plan-day indices with
gaps preserved where an exercise was skipped, while anything rebuilt from
Notion sees only the exercises actually logged, renumbered from zero. The same
integer therefore means different movements depending on the path, and
per-exercise HR would land on the wrong exercise. Both sides now key by name.
Nothing consumed per_exercise_json before this (the tab was always empty), so
choosing the better key cost no migration.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from services import models
from services.config import Config
from services.repository import Repository


def _config() -> Config:
    return Config(
        notion_api_key="ntn_test",
        notion_db_readiness="db-readiness",
        notion_db_training="db-training",
        notion_db_config="db-config",
        google_sheets_id="sheet-id",
        google_service_account={"type": "service_account"},
    )


def _page(movement: str, sets: list[dict]) -> dict:
    """A Notion training row, shaped the way notion.get_property reads it."""
    return {
        "properties": {
            "Movement": {"type": "title",
                         "title": [{"plain_text": movement}]},
            "Sets": {"type": "rich_text",
                     "rich_text": [{"plain_text": json.dumps(sets)}]},
        }
    }


SETS_A = [{"set_num": 1, "reps": 10, "weight": 20.0, "ts": "2026-08-10T10:00:00+02:00"},
          {"set_num": 2, "reps": 10, "weight": 20.0, "ts": "2026-08-10T10:04:00+02:00"}]
SETS_B = [{"set_num": 1, "reps": 8, "weight": 40.0, "ts": "2026-08-10T10:10:00+02:00"}]


# ─── get_session_sets_by_exercise ────────────────────────────────────────────

def test_sets_are_read_from_the_sets_json_and_keyed_by_movement_name(monkeypatch):
    repo = Repository(_config())
    monkeypatch.setattr(
        repo, "_query",
        lambda db, filter_=None, sorts=None: [_page("Goblet Squat", SETS_A),
                                              _page("Hip Thrust", SETS_B)],
    )
    out = repo.get_session_sets_by_exercise(date(2026, 8, 10))
    assert set(out) == {"Goblet Squat", "Hip Thrust"}
    assert out["Goblet Squat"] == SETS_A
    assert [s["ts"] for s in out["Goblet Squat"]] == [r["ts"] for r in SETS_A], (
        "the per-set timestamps are the whole point — without them "
        "compute_session_hr cannot match a Garmin activity at all"
    )


def test_the_query_is_filtered_to_the_one_date(monkeypatch):
    """Unwindowed would mean every training row ever, on a method that runs on
    page open."""
    seen = {}

    repo = Repository(_config())

    def fake_query(db, filter_=None, sorts=None):
        seen["filter"] = filter_
        return []

    monkeypatch.setattr(repo, "_query", fake_query)
    repo.get_session_sets_by_exercise(date(2026, 8, 10))
    assert seen["filter"] == {"property": "Session Date",
                              "date": {"equals": "2026-08-10"}}


def test_rows_without_sets_or_a_name_are_dropped_not_crashed(monkeypatch):
    repo = Repository(_config())
    monkeypatch.setattr(
        repo, "_query",
        lambda db, filter_=None, sorts=None: [
            _page("Goblet Squat", SETS_A),
            _page("No Sets Logged", []),
            _page("", SETS_B),
        ],
    )
    assert list(repo.get_session_sets_by_exercise(date(2026, 8, 10))) == ["Goblet Squat"]


def test_unparseable_sets_json_yields_no_entry_rather_than_raising(monkeypatch):
    repo = Repository(_config())
    bad = {"properties": {
        "Movement": {"type": "title", "title": [{"plain_text": "Broken"}]},
        "Sets": {"type": "rich_text", "rich_text": [{"plain_text": "{not json"}]},
    }}
    monkeypatch.setattr(repo, "_query", lambda db, filter_=None, sorts=None: [bad])
    assert repo.get_session_sets_by_exercise(date(2026, 8, 10)) == {}


# ─── the sync itself ─────────────────────────────────────────────────────────

def _session(d: date) -> models.SessionRecord:
    return models.SessionRecord(
        session_date=str(d),
        session_duration_minutes=52.0,
        session_rpe=6.0,
        session_au=312.0,
        exercises=[models.ExerciseEntry(name="Goblet Squat", movement_type="Squat")],
    )


def test_the_sync_no_longer_raises_and_reaches_compute(monkeypatch):
    """THE regression test. Before the fix this raised AttributeError on
    `ex.sets` before compute_session_hr was ever called."""
    repo = Repository(_config())
    d = date(2026, 8, 10)
    monkeypatch.setattr(repo, "get_recent_sessions", lambda days=7: [_session(d)])
    monkeypatch.setattr(repo, "get_session_sets_by_exercise",
                        lambda _d: {"Goblet Squat": SETS_A})
    seen = {}

    def fake_compute(session_date, by_exercise, **kw):
        seen["by_exercise"] = by_exercise
        seen["duration"] = kw.get("duration_minutes")
        return {"session_au": 300.0}

    monkeypatch.setattr(repo, "compute_session_hr", fake_compute)
    monkeypatch.setattr(repo, "save_session_hr", lambda summary: seen.setdefault("saved", summary))

    assert repo.sync_session_hr_for_date(d) is True
    assert seen["by_exercise"] == {"Goblet Squat": SETS_A}, (
        "the sets must come from the Sets JSON, not from ExerciseEntry"
    )
    assert seen["duration"] == 52.0
    assert seen["saved"] == {"session_au": 300.0}, "the result must be PERSISTED"


def test_the_sync_never_reads_a_sets_attribute_off_exercise_entry():
    """ExerciseEntry has no `sets` field, and this is the assertion that would
    have caught the original bug at the point it was written."""
    assert not hasattr(models.ExerciseEntry(name="x", movement_type="y"), "sets")


def test_a_session_with_no_captured_sets_returns_false_without_calling_compute(monkeypatch):
    """Sessions logged before per-set capture existed have no timestamps, so
    there is nothing to match — an ordinary fall-back-to-RPE outcome, and it
    must not spend Garmin calls finding that out."""
    repo = Repository(_config())
    d = date(2026, 8, 10)
    monkeypatch.setattr(repo, "get_recent_sessions", lambda days=7: [_session(d)])
    monkeypatch.setattr(repo, "get_session_sets_by_exercise", lambda _d: {})
    monkeypatch.setattr(repo, "compute_session_hr",
                        lambda *a, **k: pytest.fail("compute must not be called"))
    assert repo.sync_session_hr_for_date(d) is False


def test_no_session_on_the_day_returns_false(monkeypatch):
    repo = Repository(_config())
    monkeypatch.setattr(repo, "get_recent_sessions", lambda days=7: [])
    monkeypatch.setattr(repo, "compute_session_hr",
                        lambda *a, **k: pytest.fail("compute must not be called"))
    assert repo.sync_session_hr_for_date(date(2026, 8, 10)) is False


def test_a_null_compute_result_is_not_persisted(monkeypatch):
    """None means no matching activity. Writing it would put an empty row in
    the Session HR tab and make blend_strain think HR data exists."""
    repo = Repository(_config())
    d = date(2026, 8, 10)
    monkeypatch.setattr(repo, "get_recent_sessions", lambda days=7: [_session(d)])
    monkeypatch.setattr(repo, "get_session_sets_by_exercise",
                        lambda _d: {"Goblet Squat": SETS_A})
    monkeypatch.setattr(repo, "compute_session_hr", lambda *a, **k: None)
    monkeypatch.setattr(repo, "save_session_hr",
                        lambda s: pytest.fail("must not persist a null result"))
    assert repo.sync_session_hr_for_date(d) is False


# ─── the two writers agree on the key ────────────────────────────────────────

def test_both_writers_key_compute_session_hr_by_movement_name():
    """views/training.py's live path and the Notion-rebuilt path must produce
    the same key for the same movement, or per-exercise HR lands on the wrong
    exercise. Source-level, since views/ has no runtime coverage."""
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "views" / "training.py").read_text(
        encoding="utf-8")
    assert "_sets_by_movement(exercises)" in src
    assert "{i: rows for i, rows in st.session_state.tp_set_log.items()" not in src, (
        "the live path is passing plan-day INDICES again — they do not mean "
        "the same thing as the indices a Notion rebuild produces"
    )
