"""services/prescription.seed_exercise: today's numbers for one exercise.

Moved out of the Training page's `_seed_actuals_if_needed` on 2026-10-19 so
the phone's API gets the same numbers. What it pins:

  * a loaded lift resolves exactly as sessions.resolve_prescription does with
    the same reads, and the pain gate reads the CALLER's day;
  * an unreadable check-in blocks a weight step, like a missing one;
  * a ramp, an unloaded exercise and an exercise without a stepper each get
    what the page gave them;
  * a failed lookup reads as no data and never blocks;
  * the previous session is the raw reading, never the proposal;
  * a contradiction falls back to the last completed session and says so.
"""

from __future__ import annotations

from datetime import date

import pytest

from services import prescription
from services import sessions as sess

TODAY = date(2026, 10, 20)
POLICY = sess.load_policy(None, None)
LIFT = {"name": "Goblet Squat", "type": "reps", "sets": 3, "reps": 10, "rep_min": 8,
        "rep_max": 12, "weight_kg": 22.5, "equipment_type": "dumbbell", "increment_size": 2.25}
LAST = {"session_date": "2026-10-16", "reps": 12, "weight_kg": 22.5, "band_tier": None}
LAST_SETS = [{"set_num": n, "reps": 12, "weight": 22.5} for n in (1, 2, 3)]
HISTORY = [("2026-10-16", LAST_SETS), ("2026-10-13", LAST_SETS)]


class FakeRepo:
    """The four reads the seed makes; `fail` names the ones that raise."""

    def __init__(self, check_ins=(), fail=()):
        self.check_ins, self.fail = list(check_ins), set(fail)
        self.readiness_args = None

    def _maybe_fail(self, name):
        if name in self.fail:
            raise RuntimeError(f"{name} failed")

    def get_last_performance(self, name):
        self._maybe_fail("last")
        return dict(LAST)

    def get_last_session_all_sets(self, name):
        self._maybe_fail("last_sets")
        return [dict(s) for s in LAST_SETS]

    def get_recent_session_sets(self, name):
        self._maybe_fail("history")
        return list(HISTORY)

    def get_recent_readiness(self, days=60, today=None):
        self.readiness_args = (days, today)
        self._maybe_fail("readiness")
        return list(self.check_ins)


def _expected(step_block, last=LAST, last_sets=LAST_SETS, history=HISTORY):
    return sess.resolve_prescription(LIFT, last, "normal", POLICY, weight_increment=2.25,
                                     last_session_sets=last_sets, history=history,
                                     step_block=step_block)


def _seed(repo, ex=LIFT, **kw):
    return prescription.seed_exercise(repo, ex, streak_label="normal", policy=POLICY,
                                      today=TODAY, **kw)


@pytest.mark.parametrize("check_ins, block", [
    ([{"date": "2026-10-20", "pain_score": 2}], None),
    ([{"date": "2026-10-20", "pain_score": 7}], "today's pain score is 7/10"),
    ([{"date": "2026-10-19", "pain_score": 1}], "there is no check-in for today"),
])
def test_a_loaded_lift_resolves_as_sessions_does_with_the_pain_gate(check_ins, block):
    repo = FakeRepo(check_ins)
    seed = _seed(repo)
    assert seed.entry == _expected(block)
    assert repo.readiness_args == (1, TODAY)              # the caller's day
    assert seed.contradiction is None


def test_an_unreadable_check_in_blocks_the_step_like_a_missing_one():
    seed = _seed(FakeRepo(fail={"readiness"}))
    assert seed.entry == _expected(prescription.CHECK_IN_UNREAD)


def test_a_failed_lookup_reads_as_no_data_and_never_blocks():
    seed = _seed(FakeRepo(fail={"last", "last_sets", "history"}))
    assert seed.previous == sess.previous_performance(None, None)
    assert seed.entry == _expected(None, last=None, last_sets=None, history=[])


def test_the_previous_session_is_the_raw_reading_never_the_proposal():
    seed = _seed(FakeRepo([{"date": "2026-10-20", "pain_score": 0}]))
    assert seed.previous == sess.previous_performance(LAST, LAST_SETS)


def test_only_the_previous_reading_when_the_entry_is_already_there():
    seed = _seed(FakeRepo(), with_entry=False)
    assert seed.entry is None and seed.previous == sess.previous_performance(LAST, LAST_SETS)


def test_a_ramp_proposes_from_its_lift_and_an_unloaded_exercise_from_the_plan():
    ramp = {"name": "Goblet Squat (ramp)", "type": "reps", "sets": 1, "reps": 6,
            "equipment_type": "dumbbell", "warmup": True}
    lift_entry = {"reps": 10, "weight_kg": 27.0, "band_tier": None}
    assert _seed(FakeRepo(), ramp, lift_entry=lift_entry).entry == sess.ramp_entry(ramp, lift_entry)
    march = {"name": "Standing Psoas March", "type": "reps", "sets": 2, "reps": 20}
    assert _seed(FakeRepo(), march).entry == sess.bodyweight_entry(march)


def test_an_exercise_without_a_stepper_has_no_seed():
    plank = {"name": "Forearm Plank", "type": "hold", "sets": 2, "hold_seconds": 30}
    assert _seed(FakeRepo(), plank) is None


def test_a_contradiction_falls_back_to_the_last_completed_session(monkeypatch):
    def contradict(*a, **k):
        raise sess.PrescriptionContradiction("reduced day proposed 25 kg over 22.5 kg")
    monkeypatch.setattr(sess, "resolve_prescription", contradict)
    seed = _seed(FakeRepo([{"date": "2026-10-20", "pain_score": 0}]))
    ceiling = sess.last_completed_ceiling(LAST, LAST_SETS)
    assert seed.contradiction == "reduced day proposed 25 kg over 22.5 kg"
    assert (seed.entry["weight_kg"], seed.entry["reps"], seed.entry["source"]) == (
        ceiling.get("weight_kg"), ceiling.get("reps"), "last_time")
