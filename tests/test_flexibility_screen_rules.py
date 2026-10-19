"""Insights › Flexibility's rules, moved to services/flexibility_screen.py on
2026-10-19 (move INS-3), and two faults fixed with them:

- F10: the screen printed "of 4 slots run" and counted the slots not
  measured from a typed 4; the battery has three slots.
- F13: an unfinished assessment lived only in the local .sync_state.json, so
  a hosted restart lost it. It is now kept in the store as well.
"""

from __future__ import annotations

import datetime as dt
import json

import cluster_a_battery as cba
from services import battery as btry
from services import flexibility as fx
from services import flexibility_screen as fxs
from services.clients import local_cache
from services.repository import Repository

TODAY = dt.date(2026, 10, 19)
_DRAFT_KEY = "flexibility_draft"


def _reading(key, value, side="", setup=None):
    return btry.Reading(test_key=key, value=value, unit=cba.TESTS[key].unit, side=side,
                        setup_value=setup)


def test_the_slot_count_is_the_battery_s_own():
    report = fx.assess(fxs.begin(TODAY, cold=True), TODAY)
    assert fxs.slots_total(report) == len(cba.SLOT_EVALUATORS) == 3, "F10"
    assert fxs.slots_not_run(report) == 3 - len(report.result.slots)


def test_the_capture_order_and_its_ticks():
    draft = fxs.begin(TODAY, cold=True)
    order = fxs.capture_order(draft)
    assert order == list(cba.applicable_tests(draft))
    assert fxs.clamp_step(99, order) == len(order) - 1 and fxs.clamp_step(-3, order) == 0
    done = fx.merge_reading(draft, _reading(order[0], 40.0))
    ticks = fxs.step_ticks(order, 1, done)
    assert ticks[0] == "done" and ticks[1] == "now" and set(ticks[2:]) <= {""}
    assert fxs.step_ticks(order, 0, None)[0] == "now"


def test_a_step_merges_each_typed_side_with_its_setup_and_load():
    draft = fxs.begin(TODAY, cold=False)
    key = fxs.capture_order(draft)[0]
    updated = fxs.apply_entries(draft, key, {"left": 41.0, "right": None},
                                load=2.5, setup_value=30.0, void=True)
    assert len(updated.readings) == 1, "a blank side is not a reading"
    reading = updated.readings[0]
    assert (reading.side, reading.value, reading.load_kg, reading.setup_value, reading.voided) == (
        "left", 41.0, 2.5, 30.0, True)
    assert not updated.cold


def test_the_setup_number_is_offered_back():
    key = fxs.capture_order(fxs.begin(TODAY, cold=True))[0]
    earlier = (btry.Assessment(cluster="a", taken_on=dt.date(2026, 9, 1), cold=True,
                               readings=(_reading(key, 40.0, setup=31.0),)),)
    assert fxs.prior_setup(fxs.begin(TODAY, cold=True), earlier, key) == (31.0, True)
    own = fx.merge_reading(fxs.begin(TODAY, cold=True), _reading(key, 42.0, setup=29.0))
    assert fxs.prior_setup(own, earlier, key) == (29.0, False)
    assert fxs.prior_setup(fxs.begin(TODAY, cold=True), (), key) == (None, False)


def test_a_missing_setup_number_joins_its_reading():
    key = fxs.capture_order(fxs.begin(TODAY, cold=True))[0]
    stored = fx.merge_reading(fxs.begin(TODAY, cold=True), _reading(key, 40.0))
    item = cba.MissingInput(test_key=key, setup=True)
    filled = fxs.fill_missing(stored, {item: 30.5})
    assert filled.reading(key).setup_value == 30.5 and filled.reading(key).value == 40.0
    assert fxs.fill_missing(stored, {item: None}) == stored


def test_the_leg_day_check_reads_yesterday_and_a_failed_read_is_quiet():
    class _Repo:
        def __init__(self, answer):
            self.answer = answer

        def get_recent_sessions(self, days=3, today=None):
            if isinstance(self.answer, Exception):
                raise self.answer
            return self.answer

    assert not fxs.legs_loaded_yesterday(_Repo([]), TODAY)
    assert not fxs.legs_loaded_yesterday(_Repo(RuntimeError("store unreachable")), TODAY)


def test_finishing_stores_the_assessment_then_drops_the_draft():
    calls = []

    class _Repo:
        def save_flexibility_assessment(self, a):
            calls.append("save")

        def clear_flexibility_draft(self):
            calls.append("clear")

    fxs.finish(_Repo(), fxs.begin(TODAY, cold=True))
    assert calls == ["save", "clear"]


# ─── F13: the draft survives a restart ────────────────────────────────────────

class _FakeRepo:
    """The real draft methods over a fake config row."""

    def __init__(self):
        self.config = {}

    def get_config_value(self, key):
        return self.config.get(key)

    def set_config(self, key, value, today=None):
        self.config[key] = value

    get_flexibility_draft = Repository.get_flexibility_draft
    save_flexibility_draft = Repository.save_flexibility_draft
    clear_flexibility_draft = Repository.clear_flexibility_draft


def test_an_unfinished_assessment_comes_back_after_a_restart():
    repo = _FakeRepo()
    draft = fx.merge_reading(fxs.begin(TODAY, cold=True),
                             _reading(fxs.capture_order(fxs.begin(TODAY, cold=True))[0], 40.0))
    repo.save_flexibility_draft(draft)
    assert json.loads(repo.config[_DRAFT_KEY])["taken_on"] == TODAY.isoformat()
    local_cache.update({_DRAFT_KEY: None})          # the restart: the local file is gone
    back = repo.get_flexibility_draft()
    assert back is not None and back.readings == draft.readings, "F13"
    assert local_cache.read().get(_DRAFT_KEY), "the local mirror is healed"


def test_a_cleared_draft_never_comes_back():
    repo = _FakeRepo()
    repo.save_flexibility_draft(fxs.begin(TODAY, cold=True))
    repo.clear_flexibility_draft()
    assert repo.config[_DRAFT_KEY] == ""
    assert repo.get_flexibility_draft() is None
