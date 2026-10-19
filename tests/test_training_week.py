"""The training page's week, moved to services/training_week.py and
metrics_logic (move TRN-10, 2026-10-19), and two faults found in the move,
both from the 12-week block's empty rest days (Wednesday and Saturday):

- F24: the strip drew a planned rest day as a planned session, and as
  missed once it had passed;
- F25: the week count took the rest days as scheduled sessions, so a perfect
  week could not happen (5 of 7 is under 80%).
"""

from __future__ import annotations

from datetime import date, timedelta

from services import metrics_logic as ml
from services import sessions as sess
from services import training_week as tw

START = date(2026, 10, 19)                 # the 12-week block's first Monday
BLOCK = sess.build_phase(5, START)
NEXT_MON = START + timedelta(days=7)


def _d(i: int) -> str:
    return (START + timedelta(days=i)).isoformat()


def _first_week(logged: set[str]):
    history = ml.compute_week_history(NEXT_MON + timedelta(days=1), [BLOCK],
                                      [{"date": d} for d in logged])
    return next(w for w in history if w.week_start == START.isoformat())


def test_the_rest_days_are_not_scheduled_sessions():
    assert _first_week(set()).scheduled == 5
    assert _first_week({_d(i) for i in (0, 1, 3, 4, 6)}).status == "ultimate"
    assert _first_week({_d(i) for i in (0, 1, 3, 4)}).status == "perfect", "4 of 5 is 80%"


def test_a_session_on_a_rest_day_passes_the_week_but_never_makes_it_perfect():
    week = _first_week({_d(i) for i in (0, 1, 2)})          # A, B and yoga on Wednesday
    assert (week.completed, week.logged_days) == (2, 3)
    assert week.status == "normal", "three logged days pass the week (Key Rule 22)"
    assert _first_week({_d(0), _d(1)}).status == "failed"
    week = _first_week({_d(i) for i in (0, 1, 2, 3, 5)})    # three planned, two on rest days
    assert week.completed == 3 and week.status == "normal"


def test_an_earlier_block_still_counts_all_seven_days():
    block_b = sess.build_phase(4, date(2026, 9, 21))
    history = ml.compute_week_history(date(2026, 9, 29), [block_b], [])
    assert history[0].scheduled == 7


def test_the_live_line_reads_the_verdicts_own_thresholds():
    assert ml.week_progress(0, 0) == ("no_plan", 0)
    assert ml.week_progress(5, 5) == ("ultimate", 0)
    assert ml.week_progress(5, 4) == ("perfect", 1)
    assert ml.week_progress(5, 1, logged_days=1) == ("failing", 2)
    assert ml.week_progress(5, 2, logged_days=3) == ("normal", 2)
    assert ml.week_progress(7, 3) == ("normal", 3)
    for scheduled in range(0, 8):
        for completed in range(0, scheduled + 1):
            kind, _ = ml.week_progress(scheduled, completed)
            status = ml.week_status(scheduled, completed)
            assert kind == {"failed": "failing"}.get(status, status), (scheduled, completed)


def test_the_banner_counts_this_weeks_planned_sessions():
    wednesday = START + timedelta(days=2)
    banner = tw.banner(tw.week_history([BLOCK], wednesday, {_d(0), _d(1)}), wednesday)
    assert (banner["scheduled"], banner["completed"]) == (5, 2)
    assert (banner["progress"], banner["to_go"]) == ("failing", 1)
    assert banner["streak_weeks"] == 0 and banner["last_week"] is None


def test_a_failed_last_week_shows_on_monday_only():
    logged = {_d(0)}
    assert tw.banner(tw.week_history([BLOCK], NEXT_MON, logged), NEXT_MON)["last_week"] == "failed"
    tuesday = NEXT_MON + timedelta(days=1)
    assert tw.banner(tw.week_history([BLOCK], tuesday, logged), tuesday)["last_week"] is None


def test_a_planned_rest_day_is_rest_on_the_strip():
    thursday = START + timedelta(days=3)
    cells = tw.week_strip(START, BLOCK, {_d(0)}, thursday)
    assert [c.state for c in cells] == [
        "completed", "missed", "rest", "planned", "planned", "rest", "planned"]
    assert [tw.strip_marker(c, thursday) for c in cells] == [
        "done", "missed", "rest", "today", "planned", "rest", "planned"]
    assert tw.week_strip(START, BLOCK, {_d(2)}, thursday)[2].state == "completed"
    assert [c.state for c in tw.week_strip(START, None, set(), thursday)] == ["rest"] * 7


def test_a_week_paged_to_shows_its_stored_verdict():
    today = NEXT_MON + timedelta(days=2)
    history = tw.week_history([BLOCK], today, {_d(i) for i in (0, 1, 3, 4, 6)})
    assert tw.viewed_week_status(history, START, today) == "ultimate"
    assert tw.viewed_week_status(history, NEXT_MON, today) is None, "the banner's week"
    assert tw.viewed_week_status(history, None, today) is None
    assert tw.viewed_week_status(history, START - timedelta(days=7), today) is None
