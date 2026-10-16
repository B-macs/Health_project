"""The 12-week block's order rule — services/scheduling.in_order_reschedules.

The athlete, approved 2026-10-16: "The sessions run in order, A, B, C, then D.
A missed day moves the rest along; three sessions in a week meet the dose."
The week is Monday A, Tuesday B, Thursday C, Friday D. A missed Monday makes
Tuesday A, Thursday B and Friday C, and D does not run that week. Nothing is
moved without his press (ask-first), nothing leaves the week (Key Rule 18b),
and a "keep as planned" answer is not asked again.
"""
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

import training_plan as tp
from services import plan as ph
from services import scheduling as sch
from services import sessions as sess

START = date(2026, 10, 19)          # a Monday
MON, TUE, WED, THU, FRI, SAT, SUN = (date(2026, 10, 19 + i) for i in range(7))
PHASE = sess.build_phase(5, START)
PLAN = sess.calendar_plan(PHASE)
NUM = {"A": 1, "B": 2, "C": 4, "D": 5}


def _letters(phase, days=(MON, TUE, WED, THU, FRI, SAT, SUN)):
    out = {}
    for d in days:
        out[d] = (PLAN.get(ph.day_number_in_phase(phase, d)) or {}).get("session_letter")
    return out


def _apply(phase, overrides, reasons):
    return replace(phase, date_overrides={**phase.date_overrides, **overrides},
                   shift_reasons={**phase.shift_reasons, **reasons})


def test_the_block_runs_in_order_and_block_b_does_not():
    assert sch.runs_in_order(PLAN)
    assert not sch.runs_in_order(tp.PLAN_BLOCK_B)
    assert _letters(PHASE) == {MON: "A", TUE: "B", WED: None, THU: "C", FRI: "D",
                               SAT: None, SUN: None}


def test_nothing_missed_proposes_nothing():
    assert sch.in_order_reschedules(PHASE, PLAN, set(), MON) == ({}, {})
    assert sch.in_order_reschedules(PHASE, PLAN, {MON.isoformat()}, TUE) == ({}, {})


def test_a_missed_monday_moves_the_rest_along_and_d_does_not_run():
    ovr, rsn = sch.in_order_reschedules(PHASE, PLAN, set(), TUE)
    assert ovr == {MON.isoformat(): NUM["D"], TUE.isoformat(): NUM["A"],
                   THU.isoformat(): NUM["B"], FRI.isoformat(): NUM["C"]}
    assert rsn[MON.isoformat()].startswith(sch.DROPPED_REASON_PREFIX)
    moved = _apply(PHASE, ovr, rsn)
    assert _letters(moved) == {MON: "D", TUE: "A", WED: None, THU: "B", FRI: "C",
                               SAT: None, SUN: None}
    assert sch.in_order_summary(PHASE, PLAN, ovr, TUE) == [
        "Session D does not run this week", "Today: session A",
        "Thursday 22 Oct: session B", "Friday 23 Oct: session C"]


def test_after_it_runs_nothing_more_is_proposed():
    """The answer is final: the same render loop that wrote it must find
    nothing to write next time."""
    ovr, rsn = sch.in_order_reschedules(PHASE, PLAN, set(), TUE)
    moved = _apply(PHASE, ovr, rsn)
    assert sch.in_order_reschedules(moved, PLAN, set(), TUE) == ({}, {})
    assert sch.in_order_reschedules(moved, PLAN, {TUE.isoformat()}, THU) == ({}, {})


def test_a_second_missed_day_moves_them_again():
    ovr, rsn = sch.in_order_reschedules(PHASE, PLAN, set(), TUE)
    moved = _apply(PHASE, ovr, rsn)
    ovr2, rsn2 = sch.in_order_reschedules(moved, PLAN, set(), THU)
    after = _apply(moved, ovr2, rsn2)
    assert {_letters(after)[THU], _letters(after)[FRI]} == {"A", "B"}
    assert (_letters(after)[THU], _letters(after)[FRI]) == ("A", "B")
    assert {_letters(after)[MON], _letters(after)[TUE]} == {"C", "D"}


def test_a_done_session_is_not_run_again():
    """Monday logged, Tuesday missed: Thursday B, Friday C, and D does not run."""
    ovr, rsn = sch.in_order_reschedules(PHASE, PLAN, {MON.isoformat()}, THU)
    after = _apply(PHASE, ovr, rsn)
    assert (_letters(after)[THU], _letters(after)[FRI], _letters(after)[TUE]) == ("B", "C", "D")
    assert _letters(after)[MON] == "A"


def test_on_a_rest_day_the_next_strength_days_take_the_order():
    """Monday missed, Tuesday done, seen on Wednesday: Thursday A, Friday C."""
    ovr, rsn = sch.in_order_reschedules(PHASE, PLAN, {TUE.isoformat()}, WED)
    after = _apply(PHASE, ovr, rsn)
    assert (_letters(after)[THU], _letters(after)[FRI], _letters(after)[MON]) == ("A", "C", "D")


def test_keep_as_planned_is_not_asked_again():
    ovr, _ = sch.in_order_reschedules(PHASE, PLAN, set(), TUE)
    missed = [date.fromisoformat(iso) for iso in ovr if date.fromisoformat(iso) < TUE]
    declined = _apply(PHASE, *sch.declined_entries(PHASE, missed, sch.LEFT_AS_MISSED))
    assert sch.in_order_reschedules(declined, PLAN, set(), TUE) == ({}, {})
    assert sch.in_order_reschedules(declined, PLAN, {TUE.isoformat()}, THU) == ({}, {})


def test_a_missed_friday_seen_on_saturday_has_nowhere_to_go():
    logged = {d.isoformat() for d in (MON, TUE, THU)}
    assert sch.in_order_reschedules(PHASE, PLAN, logged, SAT) == ({}, {})


def test_every_proposal_stays_inside_its_week():
    """Key Rule 18b: plan.reject_violating_overrides refuses nothing."""
    for today in (TUE, WED, THU, FRI):
        for logged in (set(), {MON.isoformat()}, {TUE.isoformat()}):
            ovr, _ = sch.in_order_reschedules(PHASE, PLAN, logged, today)
            kept, rejected = ph.reject_violating_overrides(PHASE, ovr)
            assert not rejected and kept == ovr, (today, logged)


@pytest.mark.parametrize("week", [2, 7, 12])
def test_the_rule_reads_any_week(week):
    monday = date.fromordinal(START.toordinal() + (week - 1) * 7)
    tuesday = date.fromordinal(monday.toordinal() + 1)
    ovr, _ = sch.in_order_reschedules(PHASE, PLAN, set(), tuesday)
    base = (week - 1) * 7
    assert ovr[tuesday.isoformat()] == base + NUM["A"]
    assert ovr[monday.isoformat()] == base + NUM["D"]


def test_the_training_page_reads_plan_sessions_for_the_order():
    """A yoga session is not session A: the in-order path reads the PLAN-day
    logged set, never the yoga-inclusive one."""
    src = (Path(__file__).resolve().parent.parent / "views" / "training.py").read_text(
        encoding="utf-8")
    block = src[src.index("_mr_in_order = scheduling.runs_in_order"):]
    block = block[:block.index("def _mr_write")]
    assert "_plan_logged_dates(_mr_monday.isoformat()" in block
    assert "include_supplementary=not _mr_in_order" in block
