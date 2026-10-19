"""GET and PUT /api/checkin: the morning check-in (rebuild Phase 2,
milestone 5).

What it pins:
- the form for a day opens with that day's entry when it has one, and at the
  defaults otherwise, with every control's options and limits from
  services/checkin_form.py (the phone holds no range of its own);
- the days a check-in can be saved for are the caller's today and the three
  before it, by the caller's date (rule 3);
- a save names every problem at once and stores nothing then; a save of the
  opened entry replaces it, so pain can return to 0 (fault F3); one row per
  date, so a repeated request stores one entry;
- "practice done" is inferred from the minutes.

A fake Repository; no network.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from healthapi.deps import get_repository  # noqa: E402
from healthapi.main import create_app  # noqa: E402
from services import checkin_form as cf  # noqa: E402
from services.models import CheckInRecord  # noqa: E402

KEY = "test-engine-key"
TODAY = date(2026, 10, 19)


class CheckInStore:
    """One row per date; `replace` is the flag each save carried."""

    def __init__(self, rows=None, read_fails=False):
        self.rows: dict[str, CheckInRecord] = dict(rows or {})
        self.read_fails = read_fails
        self.saves: list[tuple[str, bool]] = []

    def get_check_in(self, iso_date):
        if self.read_fails:
            raise RuntimeError("the store did not answer")
        return self.rows.get(iso_date)

    def save_check_in(self, record, replace=False):
        self.saves.append((record.date, replace))
        self.rows[record.date] = record


def _values(**over) -> dict:
    return {**cf.FORM_DEFAULTS, **over}


def _client(monkeypatch, store):
    monkeypatch.setenv("HEALTH_ENGINE_KEY", KEY)
    monkeypatch.delenv("HEALTH_PROBES", raising=False)
    app = create_app(startup=False)
    app.dependency_overrides[get_repository] = lambda: store
    return TestClient(app)


def _headers(local: date = TODAY) -> dict:
    return {"X-Engine-Key": KEY, "X-Local-Date": local.isoformat()}


def _get(monkeypatch, store, query="", local=TODAY):
    with _client(monkeypatch, store) as c:
        return c.get(f"/api/checkin{query}", headers=_headers(local))


def _put(monkeypatch, store, day: date, values: dict, opened_entry=False):
    with _client(monkeypatch, store) as c:
        return c.put("/api/checkin", headers=_headers(),
                     json={"date": day.isoformat(), "opened_entry": opened_entry,
                           "values": values})


def test_a_day_without_an_entry_opens_at_the_defaults_with_every_limit(monkeypatch):
    body = _get(monkeypatch, CheckInStore()).json()
    assert body["date"] == TODAY.isoformat() and body["is_today"]
    assert body["options"] == [(TODAY - timedelta(days=i)).isoformat()
                               for i in range(cf.BACKFILL_DAYS + 1)]
    assert not body["existing"] and not body["read_failed"]
    assert body["values"] == cf.FORM_DEFAULTS
    assert {r["field"]: (r["min"], r["max"]) for r in body["whole"]} == cf.WHOLE_RANGES
    assert {r["field"]: r["step"] for r in body["decimal"]} == cf.DECIMAL_STEPS
    locations, tags = cf.options_lists()
    assert body["locations"] == locations and body["tags"] == tags
    assert body["conditions"] == list(cf.CONDITIONS)
    assert body["switches"] == list(cf.SWITCHES)


def test_a_day_with_an_entry_opens_with_it(monkeypatch):
    day = TODAY - timedelta(days=1)
    stored = CheckInRecord(date=day.isoformat(), current_condition="Good",
                           tightness_score=3, pain_score=4)
    body = _get(monkeypatch, CheckInStore({day.isoformat(): stored}), f"?date={day}").json()
    assert body["existing"] and not body["is_today"]
    assert body["values"]["pain_score"] == 4 and body["values"]["current_condition"] == "Good"


def test_a_failed_read_opens_at_the_defaults_and_says_so(monkeypatch):
    body = _get(monkeypatch, CheckInStore(read_fails=True)).json()
    assert body["read_failed"] and not body["existing"]
    assert body["values"] == cf.FORM_DEFAULTS


def test_no_form_outside_the_backfill_window(monkeypatch):
    for day in (TODAY + timedelta(days=1), TODAY - timedelta(days=cf.BACKFILL_DAYS + 1)):
        r = _get(monkeypatch, CheckInStore(), f"?date={day}")
        assert r.status_code == 422 and r.json()["error"].startswith("invalid_check_in")


def test_the_window_follows_the_callers_day(monkeypatch):
    # 00:30 in Berlin is 22:30 UTC the day before; the phone's day decides.
    berlin_day = date.today() + timedelta(days=1)
    body = _get(monkeypatch, CheckInStore(), local=berlin_day).json()
    assert body["options"][0] == berlin_day.isoformat() and body["date"] == berlin_day.isoformat()


def test_a_save_stores_one_row_and_answers_the_stored_form(monkeypatch):
    store = CheckInStore()
    values = _values(tightness_score=2, meditation_minutes=10.0)
    first = _put(monkeypatch, store, TODAY, values)
    again = _put(monkeypatch, store, TODAY, values)
    assert first.status_code == 200 and again.json() == first.json()
    assert list(store.rows) == [TODAY.isoformat()]
    assert first.json()["existing"] and first.json()["values"]["tightness_score"] == 2
    assert store.rows[TODAY.isoformat()].meditation_done, "inferred from the minutes"


def test_the_opened_entry_is_replaced_so_pain_can_return_to_zero(monkeypatch):
    # Fault F3: a pain of 4 could not be corrected back to 0 the same day.
    store = CheckInStore({TODAY.isoformat(): CheckInRecord(
        date=TODAY.isoformat(), current_condition="Good", tightness_score=3, pain_score=4)})
    r = _put(monkeypatch, store, TODAY, _values(pain_score=0), opened_entry=True)
    assert r.status_code == 200 and r.json()["values"]["pain_score"] == 0
    assert store.saves == [(TODAY.isoformat(), True)]
    assert store.rows[TODAY.isoformat()].pain_score == 0


def test_every_problem_is_named_and_nothing_is_stored(monkeypatch):
    store = CheckInStore()
    values = _values(pain_score=11, anatomical_locations=["Elbow"])
    del values["bristol_type"]
    r = _put(monkeypatch, store, TODAY, values)
    assert r.status_code == 422
    error = r.json()["error"]
    for part in ("pain_score must be a whole number from 0 to 10", "bristol_type is not set",
                 "anatomical_locations has a choice that is not an option: Elbow"):
        assert part in error
    assert store.rows == {} and store.saves == []


def test_no_save_outside_the_backfill_window(monkeypatch):
    store = CheckInStore()
    r = _put(monkeypatch, store, TODAY - timedelta(days=cf.BACKFILL_DAYS + 1), _values())
    assert r.status_code == 422 and "is not today or one of the" in r.json()["error"]
    assert store.rows == {}


def test_a_text_field_must_be_text_and_a_switch_true_or_false(monkeypatch):
    r = _put(monkeypatch, CheckInStore(), TODAY,
             _values(subjective_tightness=5, travel_flag="yes"))
    assert r.status_code == 422
    assert "subjective_tightness must be text" in r.json()["error"]
    assert "travel_flag must be true or false" in r.json()["error"]


def test_the_values_model_names_every_form_field():
    from healthapi.schemas import CheckInValues
    assert set(CheckInValues.model_fields) == set(cf.FORM_DEFAULTS)
    assert set(asdict(CheckInRecord(date="x", current_condition=None, tightness_score=None,
                                    pain_score=None))) - {"date", "meditation_done"} \
        == set(cf.FORM_DEFAULTS)
