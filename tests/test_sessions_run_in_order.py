"""The 12-week block's order rule — services/scheduling.in_order_reschedules.

The athlete, 2026-11-11: "When I miss a monday training, it should move all
the training by 1 day. not replace anything, Missed monday training becomes
tuesday. Tuesday becomes wednesday, Wednesday day off becomes thursday and so
on." His answer the same day: the move stops at the end of the week (Key Rule
18b), so the last day of the week falls off. It replaces the rule of
2026-10-16, which moved only the strength days onto the other strength days
and left D out of the week. Nothing is moved without his press (ask-first),
and a "keep as planned" answer is not asked again.

The week is Monday A, Tuesday B, Wednesday rest, Thursday C, Friday D,
Saturday rest, Sunday the flexibility session (weeks 1-3; from week 4 Sunday
is a rest day).
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
WEEK = (MON, TUE, WED, THU, FRI, SAT, SUN)
PHASE = sess.build_phase(5, START)
PLAN = sess.calendar_plan(PHASE)
#: The same week with a rest day on Sunday, as every week from week 4 runs.
REST_SUNDAY = {**PLAN, 7: PLAN[6]}


def _days(phase):
    """The plan day each date of the week runs, Monday to Sunday."""
    return tuple(ph.day_number_in_phase(phase, d) for d in WEEK)


def _letters(phase, plan_dict=PLAN):
    return tuple((plan_dict.get(n) or {}).get("session_letter") for n in _days(phase))


def _apply(phase, overrides, reasons):
    return replace(phase, date_overrides={**phase.date_overrides, **overrides},
                   shift_reasons={**phase.shift_reasons, **reasons})


def _move(phase, logged, today, plan_dict=PLAN):
    ovr, rsn = sch.in_order_reschedules(phase, plan_dict, logged, today)
    return _apply(phase, ovr, rsn), ovr, rsn


def test_the_block_runs_in_order_and_block_b_does_not():
    assert sch.runs_in_order(PLAN)
    assert not sch.runs_in_order(tp.PLAN_BLOCK_B)
    assert _letters(PHASE) == ("A", "B", None, "C", "D", None, None)


def test_nothing_missed_proposes_nothing():
    assert sch.in_order_reschedules(PHASE, PLAN, set(), MON) == ({}, {})
    assert sch.in_order_reschedules(PHASE, PLAN, {MON.isoformat()}, TUE) == ({}, {})


def test_a_missed_monday_moves_every_day_one_day_later():
    """His example: Monday's A on Tuesday, Tuesday's B on Wednesday,
    Wednesday's rest on Thursday, and so on to Sunday."""
    moved, ovr, rsn = _move(PHASE, set(), TUE)
    assert _days(moved) == (1, 1, 2, 3, 4, 5, 6)
    assert _letters(moved) == ("A", "A", "B", None, "C", "D", None)
    assert rsn[MON.isoformat()] == sch.MISSED_MOVED_PREFIX + "session A runs on Tuesday 20 Oct"
    assert rsn[TUE.isoformat()].startswith("Session A here")
    assert sch.in_order_summary(PHASE, PLAN, ovr, TUE) == [
        "Today: session A", "Wednesday 21 Oct: session B", "Thursday 22 Oct: rest day",
        "Friday 23 Oct: session C", "Saturday 24 Oct: session D", "Sunday 25 Oct: rest day",
        "The flexibility session does not run this week"]


def test_with_a_rest_day_on_sunday_one_missed_day_loses_nothing():
    _moved, ovr, _ = _move(PHASE, set(), TUE, REST_SUNDAY)
    assert not any("does not run" in line
                   for line in sch.in_order_summary(PHASE, REST_SUNDAY, ovr, TUE))


def test_a_missed_tuesday_seen_on_wednesday():
    """Monday done, Tuesday missed: B on Wednesday, the rest day on Thursday,
    C on Friday, D on Saturday (the week of 2026-11-09)."""
    moved, _, rsn = _move(PHASE, {MON.isoformat()}, WED, REST_SUNDAY)
    assert _days(moved) == (1, 2, 2, 3, 4, 5, 6)
    assert _letters(moved) == ("A", "B", "B", None, "C", "D", None)
    assert rsn[TUE.isoformat()] == sch.MISSED_MOVED_PREFIX + "session B runs on Wednesday 21 Oct"


def test_after_it_runs_nothing_more_is_proposed():
    """The answer is final: the same render loop that wrote it must find
    nothing to write next time."""
    moved, _, _ = _move(PHASE, set(), TUE)
    assert sch.in_order_reschedules(moved, PLAN, set(), TUE) == ({}, {})
    assert sch.in_order_reschedules(moved, PLAN, {TUE.isoformat(), WED.isoformat()},
                                    THU) == ({}, {})


def test_a_second_missed_day_moves_the_week_again_and_loses_nothing():
    moved, _, _ = _move(PHASE, set(), TUE, REST_SUNDAY)
    after, ovr, _ = _move(moved, set(), WED, REST_SUNDAY)
    assert _days(after) == (1, 1, 1, 2, 3, 4, 5)
    assert _letters(after, REST_SUNDAY) == ("A", "A", "A", "B", None, "C", "D")
    assert not any("does not run" in line
                   for line in sch.in_order_summary(moved, REST_SUNDAY, ovr, WED))


def test_a_third_missed_day_leaves_the_last_session_out_of_the_week():
    moved, _, _ = _move(PHASE, set(), TUE, REST_SUNDAY)
    moved, _, _ = _move(moved, set(), WED, REST_SUNDAY)
    after, ovr, _ = _move(moved, set(), THU, REST_SUNDAY)
    assert _days(after) == (1, 1, 1, 1, 2, 3, 4)
    assert sch.in_order_summary(moved, REST_SUNDAY, ovr, THU)[-1] == (
        "Session D does not run this week")


def test_two_missed_days_seen_late_move_the_week_two_days():
    """Monday and Tuesday missed, the app opened on Wednesday."""
    moved, _, rsn = _move(PHASE, set(), WED, REST_SUNDAY)
    assert _days(moved) == (1, 2, 1, 2, 3, 4, 5)
    assert {rsn[MON.isoformat()], rsn[TUE.isoformat()]} == {
        sch.MISSED_MOVED_PREFIX + "session A runs on Wednesday 21 Oct",
        sch.MISSED_MOVED_PREFIX + "session B runs on Thursday 22 Oct"}


def test_a_done_session_is_not_run_again():
    """Monday missed, Tuesday's B done, seen Wednesday: A on Wednesday, then
    the rest day, C and D."""
    moved, _, _ = _move(PHASE, {TUE.isoformat()}, WED)
    assert _days(moved) == (1, 2, 1, 3, 4, 5, 6)


def test_a_missed_friday_runs_on_saturday():
    logged = {d.isoformat() for d in (MON, TUE, THU)}
    moved, _, _ = _move(PHASE, logged, SAT)
    assert _days(moved) == (1, 2, 3, 4, 5, 5, 6)


def test_keep_as_planned_is_not_asked_again():
    ovr, _ = sch.in_order_reschedules(PHASE, PLAN, set(), TUE)
    missed = [date.fromisoformat(iso) for iso in ovr if date.fromisoformat(iso) < TUE]
    assert missed == [MON]
    declined = _apply(PHASE, *sch.declined_entries(PHASE, missed, sch.LEFT_AS_MISSED))
    assert sch.in_order_reschedules(declined, PLAN, set(), TUE) == ({}, {})
    assert sch.in_order_reschedules(declined, PLAN, {TUE.isoformat()}, THU) == ({}, {})


def test_a_day_the_first_rule_answered_is_not_asked_again():
    """A missed day the rule of 2026-10-16 marked "does not run this week"
    keeps its answer."""
    answered = replace(PHASE, shift_reasons={
        MON.isoformat(): sch.DROPPED_REASON_PREFIX + "session D does not run this week"})
    assert sch.in_order_reschedules(answered, PLAN, set(), TUE) == ({}, {})


def test_the_missed_note_says_moved_and_is_not_shown_on_a_logged_day():
    moved, _, rsn = _move(PHASE, set(), TUE)
    note = sch.shift_note(moved.shift_reasons, MON.isoformat(), logged=False)
    assert note == rsn[MON.isoformat()] and sch.shift_note_moved(note)
    assert sch.shift_note(moved.shift_reasons, MON.isoformat(), logged=True) is None


def test_every_proposal_stays_inside_its_week():
    """Key Rule 18b: plan.reject_violating_overrides refuses nothing."""
    for today in (TUE, WED, THU, FRI, SAT, SUN):
        for logged in (set(), {MON.isoformat()}, {TUE.isoformat()}):
            ovr, _ = sch.in_order_reschedules(PHASE, PLAN, logged, today)
            kept, rejected = ph.reject_violating_overrides(PHASE, ovr)
            assert not rejected and kept == ovr, (today, logged)


@pytest.mark.parametrize("week", [2, 7, 12])
def test_the_rule_reads_any_week(week):
    monday = date.fromordinal(START.toordinal() + (week - 1) * 7)
    tuesday = date.fromordinal(monday.toordinal() + 1)
    sunday = date.fromordinal(monday.toordinal() + 6)
    ovr, _ = sch.in_order_reschedules(PHASE, PLAN, set(), tuesday)
    base = (week - 1) * 7
    assert ovr[monday.isoformat()] == ovr[tuesday.isoformat()] == base + 1
    assert ovr[sunday.isoformat()] == base + 6


def test_the_training_page_reads_plan_sessions_for_the_order():
    """A yoga session is not session A: the in-order path reads the PLAN-day
    logged set, never the yoga-inclusive one."""
    src = (Path(__file__).resolve().parent.parent / "views" / "training.py").read_text(
        encoding="utf-8")
    block = src[src.index("_mr_in_order = scheduling.runs_in_order"):]
    block = block[:block.index("def _mr_write")]
    assert "_plan_logged_dates(_mr_monday.isoformat()" in block
    assert "include_supplementary=not _mr_in_order" in block
