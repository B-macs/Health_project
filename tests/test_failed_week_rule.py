"""
THE FAILED-WEEK RULE (athlete, 2026-09-15): "if I fail a week it gets repeated
and pushes out the block by one week."

  * A week with 0-2 logged days is a FAILED week (metrics_logic).
  * A failed week runs again the week after, by itself; a 3-day week does not,
    but can be redone by choice (services/week_repeat.py).
  * The block gets a week longer and every later block starts a week later —
    except a block that must end on a fixed date (Block B, race day), which
    loses a droppable week instead, and refuses when none is left.
  * The repeat changes which CONTENT a calendar day shows and nothing else
    (sessions.calendar_plan); day numbers stay calendar positions.
  * A week that runs again because it FAILED holds the load (athlete,
    2026-09-16): weight, band and reps start at the last session and nothing
    progresses; the + button still adds. A week redone by choice progresses.

The first real use is pinned here too: Stage 2B week 4 (2026-09-07) logged
one day and runs again 2026-09-14..20 with the shorter sessions the athlete
chose, and Block B starts 2026-09-21 with weeks 2-4 so the race stays on its
last day.
"""

from __future__ import annotations

import ast
import json
import sqlite3
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

import training_plan as tp
from services import metrics_logic as ml
from services import plan as ph
from services import sessions as sess
from services import supabase_store
from services import week_repeat as wr
from services.config import Config
from services.models import Phase
from services.repository import Repository

ROOT = Path(__file__).resolve().parent.parent

# ─── the live shape, as stored on 2026-09-15 ─────────────────────────────────

STAGE1 = Phase(1, "Stage 1 Rehab", "2026-06-29", 14, "completed")
STAGE2A = Phase(2, "Stage 2 — Transition (Work Capacity)", "2026-07-20", 28, "completed")
BLOCK_A = Phase(3, "Stage 2B — Strength + Running Build", "2026-08-17", 28, "active",
                date_overrides={"2026-09-07": 24, "2026-09-08": 27, "2026-09-09": 25,
                                "2026-09-10": 22, "2026-09-12": 23},
                shift_reasons={"2026-09-07": "Missed → moved to 2026-09-09"})
#: A log with ONE day in the week of 2026-09-07 and one each in two earlier
#: weeks — the counts that matter, not the athlete's real dates (whether new
#: personal readings belong in this public repo is his open question).
LOGGED = {"2026-08-25", "2026-09-01", "2026-09-10"}
TUE_0915 = date(2026, 9, 15)


def _live():
    return [STAGE1, STAGE2A, BLOCK_A]


def _after_first_failure():
    """The list the seed script stores on 2026-09-15. Appended by hand rather
    than through sessions.begin_new_phase, which reads the wall clock and
    would mark Block A completed once these tests run after 2026-09-20."""
    phases, _ = wr.apply_failed_week_rule(_live(), LOGGED, TUE_0915)
    return phases + [sess.build_phase(4, date(2026, 9, 21), status="upcoming")]


def _by_number(phases, n):
    return next(p for p in phases if p.phase_number == n)


# ═════════════════════════════════════════════════════════════════════════════
#  The line: 0-2 days fails, 3 does not
# ═════════════════════════════════════════════════════════════════════════════

_ENDED = (date(2026, 9, 7), date(2026, 9, 15))


@pytest.mark.parametrize("days", [0, 1, 2])
def test_zero_to_two_logged_days_is_a_failed_week(days):
    assert ml.score_week(*_ENDED, scheduled=7, completed=days).status == "failed"


def test_three_logged_days_is_not_a_failed_week():
    assert ml.score_week(*_ENDED, scheduled=7, completed=3).status == "normal"


def test_the_line_is_a_count_of_days_not_a_share():
    """The old line was 20%: one day in five read as a normal week. The
    athlete's is a count, so two days fail however short the week."""
    assert ml.FAILED_WEEK_MAX_DAYS == 2
    assert ml.score_week(*_ENDED, scheduled=5, completed=2).status == "failed"


def test_a_short_week_done_in_full_is_still_ultimate():
    assert ml.score_week(*_ENDED, scheduled=2, completed=2).status == "ultimate"


def test_the_label_and_the_rule_agree_on_last_week():
    """The screen said "Failed week" for 2026-09-07; the rule must repeat it."""
    history = ml.compute_week_history(TUE_0915, _live(), [{"date": d} for d in LOGGED])
    last = next(w for w in history if w.week_start == "2026-09-07")
    assert last.status == "failed"
    _, events = wr.apply_failed_week_rule(_live(), LOGGED, TUE_0915)
    assert events and events[0][0] == "2026-09-07"
    assert events[0][1].startswith(wr.FAILED_PREFIX)


# ═════════════════════════════════════════════════════════════════════════════
#  The first real use: Stage 2B week 4 runs again, Block B keeps race day
# ═════════════════════════════════════════════════════════════════════════════

def test_last_weeks_failure_repeats_it_this_week():
    phases, events = wr.apply_failed_week_rule(_live(), LOGGED, TUE_0915)
    block_a = _by_number(phases, 3)
    assert block_a.week_plan == [1, 2, 3, 4, 4]
    assert block_a.length_days == 35
    assert ph.phase_end_date(block_a) == date(2026, 9, 20)
    assert block_a.week_results == {
        "2026-09-07": "Failed — 1 of 7 days logged, repeated the week after"}
    assert events == [("2026-09-07", block_a.week_results["2026-09-07"])]
    assert ph.active_phase(phases, TUE_0915) == block_a


def test_last_weeks_reschedules_stay_where_they_were():
    phases, _ = wr.apply_failed_week_rule(_live(), LOGGED, TUE_0915)
    block_a = _by_number(phases, 3)
    assert block_a.date_overrides == BLOCK_A.date_overrides
    assert block_a.shift_reasons == BLOCK_A.shift_reasons


def test_the_repeat_runs_the_shorter_sessions_the_athlete_chose():
    """Mon-Sat run Block B week 1's sessions in last week's slots; Sunday keeps
    Stage 2B's own reassessment. The exercise lists are Block B's objects, so
    every rule that checks Block B checks these."""
    block_a = _by_number(_after_first_failure(), 3)
    calendar = sess.calendar_plan(block_a)
    for position, block_b_day in zip(range(29, 35), (1, 2, 3, 4, 5, 7)):
        assert calendar[position]["exercises"] is tp.PLAN_BLOCK_B[block_b_day]["exercises"]
    assert calendar[35] is tp.PLAN_STAGE2B[28]


def test_the_repeat_keeps_last_weeks_shape():
    block_a = _by_number(_after_first_failure(), 3)
    calendar = sess.calendar_plan(block_a)
    authored = [tp.PLAN_STAGE2B[d]["day_type"] for d in range(22, 29)]
    repeated = [calendar[p]["day_type"] for p in range(29, 36)]
    assert repeated == authored == ["main", "stretch", "rest", "stretch", "main", "rest", "test"]


def test_the_repeat_week_run_is_the_restart_run_not_the_35_minute_run():
    """Stage 2B day 23 as authored is 35 minutes continuous; the only run logged
    since July was a 20-minute run/walk. The repeat must never show day 23."""
    calendar = sess.calendar_plan(_by_number(_after_first_failure(), 3))
    runs = [ex for p in range(29, 36) for ex in calendar[p]["exercises"]
            if "Running" in ex["name"]]
    assert [(ex["name"], ex["duration_minutes"]) for ex in runs] == \
        [("Running Intervals (Run/Walk)", 20)]


def test_the_repeat_week_does_not_announce_a_block_that_has_not_started():
    calendar = sess.calendar_plan(_by_number(_after_first_failure(), 3))
    for position in range(29, 36):
        assert "Block B" not in calendar[position]["objective"]
        assert calendar[position]["phase"] == tp.PLAN_STAGE2B[22]["phase"]


def test_the_first_run_of_week_4_still_shows_what_it_authored():
    calendar = sess.calendar_plan(_by_number(_after_first_failure(), 3))
    for position in range(1, 29):
        assert calendar[position] is tp.PLAN_STAGE2B[position]


def test_block_b_starts_next_monday_with_all_four_weeks():
    """It ran weeks 2-4 while the race fixed its last date: the repeat above
    pushed it, and a block that cannot end later loses a week instead. The race
    was cancelled 2026-09-18, so nothing is given up — it starts late and runs
    its full four weeks."""
    block_b = _by_number(_after_first_failure(), 4)
    assert (block_b.start_date, block_b.length_days, block_b.status) ==         ("2026-09-21", 28, "upcoming")
    # None means "as authored" — no week was dropped and none is repeated.
    assert block_b.week_plan is None
    assert ph.plan_weeks(block_b) == [1, 2, 3, 4]
    calendar = sess.calendar_plan(block_b)
    assert calendar[1] is tp.PLAN_BLOCK_B[1]
    assert calendar[28] is tp.PLAN_BLOCK_B[28]
    assert ph.phase_end_date(block_b) == date(2026, 10, 18)


def test_the_stored_list_passes_the_stores_own_refusals():
    phases = _after_first_failure()
    assert wr._alignment_problem(phases) is None
    assert ph.active_phase(phases, date(2026, 9, 20)).phase_number == 3
    assert ph.active_phase(phases, date(2026, 9, 21)).phase_number == 4


def test_the_notice_says_why_and_when_block_b_starts():
    assert wr.repeat_notice(_after_first_failure(), TUE_0915) == (
        "Last week had 1 of 7 days logged, so it failed. This week runs it again. "
        "Every weight, band and rep starts at your last session, and nothing goes "
        "up by itself this week. "
        "Block B — Strength + Running Build starts Monday 21 September.")


def test_no_notice_in_an_ordinary_week():
    assert wr.repeat_notice(_live(), date(2026, 9, 1)) is None


# ═════════════════════════════════════════════════════════════════════════════
#  "unless I fail this week again"
# ═════════════════════════════════════════════════════════════════════════════

def test_failing_this_week_too_repeats_it_and_block_b_simply_starts_later():
    phases, events = wr.apply_failed_week_rule(
        _after_first_failure(), LOGGED | {"2026-09-15", "2026-09-16"}, date(2026, 9, 21))
    block_a, block_b = _by_number(phases, 3), _by_number(phases, 4)
    assert [e[0] for e in events] == ["2026-09-14"]
    assert block_a.week_plan == [1, 2, 3, 4, 4, 4]
    # It used to lose week 2 here, to keep race day. Nothing is lost now.
    assert (block_b.start_date, block_b.week_plan) == ("2026-09-28", None)
    assert ph.plan_weeks(block_b) == [1, 2, 3, 4]
    assert ph.phase_end_date(block_b) == date(2026, 10, 25)
    assert sess.calendar_plan(block_b)[28] is tp.PLAN_BLOCK_B[28]


def test_passing_this_week_leaves_block_b_on_the_21st():
    before = _after_first_failure()
    phases, events = wr.apply_failed_week_rule(
        before, LOGGED | {"2026-09-15", "2026-09-17", "2026-09-20"}, date(2026, 9, 21))
    assert events == [("2026-09-14", "Passed — 3 of 7 days logged")]
    assert _by_number(phases, 4) == _by_number(before, 4)
    assert _by_number(phases, 3).week_plan == [1, 2, 3, 4, 4]


def test_a_third_failure_is_no_longer_refused():
    """With race day fixed, a third failure would have needed Block B to give up
    the decision run or the race week, so the repeat was refused. No block has a
    fixed last date now, so a repeat always fits — it moves things later."""
    twice, _ = wr.apply_failed_week_rule(
        _after_first_failure(), LOGGED, date(2026, 9, 21))
    thrice, events = wr.apply_failed_week_rule(twice, LOGGED, date(2026, 9, 28))
    assert [e[0] for e in events] == ["2026-09-21"]
    assert "not repeated" not in events[0][1]
    assert _by_number(thrice, 3).week_plan == [1, 2, 3, 4, 4, 4, 4]
    assert _by_number(thrice, 4).start_date == "2026-10-05"
    assert ph.plan_weeks(_by_number(thrice, 4)) == [1, 2, 3, 4]


def test_a_failed_week_inside_block_b_lengthens_block_b():
    """Week 1 of Block B itself fails. It used to be refused — the block could
    not grow without ending after the race. Now the block runs its week 1 twice
    and ends a week later."""
    phases = _after_first_failure()
    phases, events = wr.apply_failed_week_rule(
        phases, LOGGED | {"2026-09-15", "2026-09-16", "2026-09-17"}, date(2026, 9, 28))
    assert [e[0] for e in events] == ["2026-09-14", "2026-09-21"]
    assert "not repeated" not in events[1][1]
    block_b = _by_number(phases, 4)
    assert block_b.week_plan == [1, 1, 2, 3, 4]
    assert (block_b.start_date, block_b.length_days) == ("2026-09-21", 35)
    assert ph.phase_end_date(block_b) == date(2026, 10, 25)


# ═════════════════════════════════════════════════════════════════════════════
#  Judged once, from the rule's first week, only when the week has ended
# ═════════════════════════════════════════════════════════════════════════════

def test_the_rule_is_idempotent():
    once, _ = wr.apply_failed_week_rule(_live(), LOGGED, TUE_0915)
    twice, events = wr.apply_failed_week_rule(once, LOGGED, TUE_0915)
    assert twice is once and events == []


def test_nothing_due_returns_the_same_list_object():
    phases = _live()
    same, events = wr.apply_failed_week_rule(phases, LOGGED, date(2026, 9, 9))
    assert same is phases and events == []


def test_weeks_before_the_rule_started_are_never_judged():
    """2026-08-24 and 2026-08-31 would both fail; the athlete asked for last
    week only."""
    phases, _ = wr.apply_failed_week_rule(_live(), LOGGED, TUE_0915)
    assert set(_by_number(phases, 3).week_results) == {"2026-09-07"}


def test_the_week_in_progress_is_never_judged():
    _, events = wr.apply_failed_week_rule(_live(), set(), date(2026, 9, 13))
    assert events == []


def test_a_deleted_session_cannot_repeat_a_week_that_already_passed():
    passed, _ = wr.apply_failed_week_rule(
        _live(), LOGGED | {"2026-09-08", "2026-09-09"}, TUE_0915)
    assert _by_number(passed, 3).week_results["2026-09-07"].startswith(wr.PASSED_PREFIX)
    again, events = wr.apply_failed_week_rule(passed, LOGGED, TUE_0915)
    assert again is passed and events == []


def test_completed_blocks_are_never_judged():
    phases = [STAGE1, STAGE2A, replace(BLOCK_A, status="completed")]
    same, events = wr.apply_failed_week_rule(phases, set(), TUE_0915)
    assert same is phases and events == []


def test_weeks_that_piled_up_are_judged_oldest_first():
    """App not opened for a fortnight: week 4 failed, and so did its repeat."""
    phases, events = wr.apply_failed_week_rule(_live(), LOGGED, date(2026, 9, 22))
    assert [e[0] for e in events] == ["2026-09-07", "2026-09-14"]
    assert _by_number(phases, 3).week_plan == [1, 2, 3, 4, 4, 4]


# ═════════════════════════════════════════════════════════════════════════════
#  Generic behaviour: mid-block repeats, and a block with no fixed end
# ═════════════════════════════════════════════════════════════════════════════

_NO_FIXED_END = {1: {}, 2: {}, 3: {}, 4: {}}


def _mid_block():
    block = Phase(3, "Block", "2026-09-07", 28, "active",
                  date_overrides={"2026-09-22": 17, "2026-09-24": 15, "2026-09-09": 0},
                  shift_reasons={"2026-09-22": "swapped", "2026-09-09": "forced rest"})
    later = Phase(4, "Next", "2026-10-05", 28, "upcoming")
    return [block, later]


def test_a_mid_block_repeat_moves_later_reschedules_with_their_sessions():
    phases, _ = wr.apply_failed_week_rule(_mid_block(), set(), date(2026, 9, 15),
                                          meta=_NO_FIXED_END)
    block = phases[0]
    assert block.week_plan == [1, 1, 2, 3, 4]
    # Week 1's forced rest stays; week 3's swap moves a week later, still in its own week.
    assert block.date_overrides == {"2026-09-09": 0, "2026-09-29": 24, "2026-10-01": 22}
    assert block.shift_reasons == {"2026-09-09": "forced rest", "2026-09-29": "swapped"}
    assert ph.override_violations(block) == []


def test_a_repeat_pushes_an_ordinary_next_block_a_whole_week():
    phases, _ = wr.apply_failed_week_rule(_mid_block(), set(), date(2026, 9, 15),
                                          meta=_NO_FIXED_END)
    nxt = phases[1]
    assert (nxt.start_date, nxt.length_days, nxt.week_plan) == ("2026-10-12", 28, None)


# ═════════════════════════════════════════════════════════════════════════════
#  Redo by choice
# ═════════════════════════════════════════════════════════════════════════════

def test_redo_by_choice_runs_this_week_again_next_week():
    before = _after_first_failure()
    three_days = LOGGED | {"2026-09-15", "2026-09-16", "2026-09-17"}
    after, why = wr.redo_this_week(before, three_days, date(2026, 9, 18))
    assert why is None
    assert _by_number(after, 3).week_plan == [1, 2, 3, 4, 4, 4]
    assert _by_number(after, 3).week_results["2026-09-14"] == \
        "Redone by choice — 3 of 7 days logged when chosen"
    # The third line was "Block B still ends on 11 October, so it has 2 weeks
    # instead of 3" — the cost of a fixed race date. There is no such cost now.
    assert wr.consequences(before, after) == [
        "Stage 2B — Strength + Running Build runs to 27 September instead of 20 September.",
        "Block B — Strength + Running Build starts 28 September instead of 21 September.",
    ]


def test_a_redone_week_is_not_repeated_a_second_time_when_it_ends():
    after, _ = wr.redo_this_week(_after_first_failure(), LOGGED, date(2026, 9, 16))
    judged, events = wr.apply_failed_week_rule(after, LOGGED, date(2026, 9, 21))
    assert judged is after and events == []


def test_the_same_week_cannot_be_redone_twice():
    after, _ = wr.redo_this_week(_after_first_failure(), LOGGED, date(2026, 9, 16))
    again, why = wr.redo_this_week(after, LOGGED, date(2026, 9, 17))
    assert again is None and "already" in why


def test_the_repeat_notice_for_a_redone_week():
    after, _ = wr.redo_this_week(_after_first_failure(), LOGGED, date(2026, 9, 16))
    assert wr.repeat_notice(after, date(2026, 9, 22)).startswith(
        "This week runs last week again, as you chose.")


# ═════════════════════════════════════════════════════════════════════════════
#  The calendar helpers
# ═════════════════════════════════════════════════════════════════════════════

def test_a_phase_that_never_used_the_rule_reads_its_authored_plan_unchanged():
    for phase in _live():
        assert sess.calendar_plan(phase) is sess.plan_dict_for_phase(phase.phase_number)


def test_plan_day_for_position():
    repeated = replace(BLOCK_A, length_days=35, week_plan=[1, 2, 3, 4, 4])
    assert ph.plan_day_for_position(BLOCK_A, 23) == 23
    assert ph.plan_day_for_position(repeated, 30) == 23
    assert ph.plan_day_for_position(repeated, 36) is None
    shortened = Phase(4, "B", "2026-09-21", 21, "upcoming", week_plan=[2, 3, 4])
    assert ph.plan_day_for_position(shortened, 1) == 8
    assert ph.plan_day_for_position(shortened, 21) == 28


def test_drop_week_follows_the_authored_order_and_spares_the_repeat():
    assert ph.drop_week([1, 2, 3, 4], (1, 2)) == [2, 3, 4]
    assert ph.drop_week([2, 3, 4], (1, 2)) == [3, 4]
    assert ph.drop_week([3, 4], (1, 2)) is None
    assert ph.drop_week([2, 2, 3, 4], (1, 2), after=1) is None


@pytest.mark.parametrize("start", [
    date(2026, 9, 21), date(2026, 9, 28), date(2026, 10, 5), date(2026, 11, 30),
])
def test_block_b_is_four_whole_weeks_whenever_it_starts(start):
    """No fixed last date since 2026-09-18, so no start date costs it a week and
    none is refused. It used to end on 2026-10-11 whatever happened."""
    block_b = sess.build_phase(4, start)
    assert block_b.length_days == 28
    assert ph.plan_weeks(block_b) == [1, 2, 3, 4]
    assert ph.phase_end_date(block_b) == start + timedelta(days=27)


def test_no_block_carries_a_fixed_last_date():
    for number, meta in sess.PHASE_META.items():
        assert "ends_on" not in meta, number
        assert "drop_weeks" not in meta, number


# ═════════════════════════════════════════════════════════════════════════════
#  A failed week holds the load
# ═════════════════════════════════════════════════════════════════════════════
#
# Athlete, 2026-09-16, the morning after the repeated week's squat day went up
# on every lift and his back tired by the next afternoon: "if there is a failed
# week then no increases in the weights during that week." Settled the same
# day: failed weeks only, not a redo by choice; weight, band AND reps; and a
# starting point rather than a limit on the + button.

_GOBLET = next(e for e in tp.PLAN_BLOCK_B[1]["exercises"] if e["name"] == "Goblet Squat")
_BAND_PALLOF = {"name": "Band Pallof Press", "type": "reps", "reps": 10, "sets": 3,
                "equipment_type": "band", "band_tier": "Blue"}
_GREEN = sess.load_policy({"signal_color": "green"}, {"volume_factor": 1.0})
_HELD = sess.hold_for_failed_week(_GREEN)


def _last(reps, weight):
    sets = [{"reps": r, "weight": weight} for r in reps]
    return {"reps": reps[-1], "weight_kg": weight, "session_date": "2026-09-10"}, sets


def test_the_repeat_of_a_failed_week_holds_the_load():
    assert wr.failed_week_holds_load(_after_first_failure(), TUE_0915)


def test_an_ordinary_week_does_not_hold():
    assert not wr.failed_week_holds_load(_live(), date(2026, 9, 1))


def test_the_week_after_a_passed_repeat_progresses_again():
    passed = LOGGED | {"2026-09-14", "2026-09-15", "2026-09-16"}
    phases, _ = wr.apply_failed_week_rule(_after_first_failure(), passed, date(2026, 9, 21))
    assert not wr.failed_week_holds_load(phases, date(2026, 9, 21))


def test_failing_the_repeat_holds_its_repeat_too():
    phases, _ = wr.apply_failed_week_rule(
        _after_first_failure(), LOGGED | {"2026-09-15", "2026-09-16"}, date(2026, 9, 21))
    assert wr.failed_week_holds_load(phases, date(2026, 9, 21))


def test_a_week_redone_by_choice_keeps_normal_progression():
    after, _ = wr.redo_this_week(_after_first_failure(), LOGGED, date(2026, 9, 16))
    assert not wr.failed_week_holds_load(after, date(2026, 9, 22))
    assert wr.HOLD_SENTENCE not in wr.repeat_notice(after, date(2026, 9, 22))


def test_the_squat_day_that_went_up_now_starts_at_last_session():
    # 2026-09-15: 22.5 kg x 8, 8, 8 on 2026-09-10 and a high readiness streak,
    # so the app started the goblet squat at 25 kg. Since 2026-09-16 readiness
    # never raises a weight, so it starts at 22.5 in any week.
    last, sets = _last([8, 8, 8], 22.5)
    for policy in (_GREEN, _HELD):
        entry = sess.resolve_prescription(_GOBLET, last, "high", policy,
                                          last_session_sets=sets, previous_session_sets=sets)
        assert (entry["weight_kg"], entry["reps"]) == (22.5, 8)


def test_a_hold_stops_an_earned_step_and_says_so():
    # Two sessions at 13 reps earn 22.5 -> 25 kg at 9 reps; the held week
    # repeats 22.5 x 13 instead, and the caption names the failed week.
    last, sets = _last([13, 13, 13], 22.5)
    free = sess.resolve_prescription(_GOBLET, last, "normal", _GREEN,
                                     last_session_sets=sets, previous_session_sets=sets)
    assert (free["weight_kg"], free["reps"]) == (25.0, 9)
    held = sess.resolve_prescription(_GOBLET, last, "normal", _HELD,
                                     last_session_sets=sets, previous_session_sets=sets)
    assert (held["weight_kg"], held["reps"]) == (22.5, 13)
    assert held["clamped"] == {"weight_kg": {"from": 25.0, "to": 22.5}}
    caption = sess.actual_caption(held)
    assert "25 → 22.5 kg" in caption and "last week failed" in caption
    assert "reduced-load" not in caption
    assert "next_step" not in held   # nothing goes up this week, so no "goes up after" line


def test_a_hold_repeats_the_reps_rather_than_lowering_them():
    # A step lowers the reps by what it costs. Putting only the weight back
    # would prescribe 22.5 x 9 in a week meant to repeat 22.5 x 13.
    last, sets = _last([13, 13, 13], 22.5)
    held = sess.resolve_prescription(_GOBLET, last, "normal", _HELD,
                                     last_session_sets=sets, previous_session_sets=sets)
    assert held["reps"] == 13


def test_a_hold_keeps_the_band_and_still_lowers_it_on_a_low_streak():
    last = {"reps": 10, "band_tier": "Blue", "session_date": "2026-09-10"}
    sets = [{"reps": 10, "band_tier": "Blue"}] * 3
    high = sess.resolve_prescription(_BAND_PALLOF, last, "high", _HELD, last_session_sets=sets)
    low = sess.resolve_prescription(_BAND_PALLOF, last, "low", _HELD, last_session_sets=sets)
    assert (high["band_tier"], low["band_tier"]) == ("Blue", "Green")


def test_a_good_readiness_streak_cannot_add_reps_in_a_held_week():
    # The engine no longer emits a factor over 1.0 (2026-09-16); the cap stays
    # so a held week holds whatever the factor's source becomes.
    policy = sess.hold_for_failed_week(
        sess.load_policy({"signal_color": "green"}, {"volume_factor": 1.12}))
    assert policy["volume_factor"] == 1.0
    assert policy["volume_note"] == \
        "Readiness suggested +12% volume; held at 100% — last week failed"


def test_a_low_streak_still_lowers_the_weight_in_a_held_week():
    last, sets = _last([8, 8, 8], 22.5)
    held = sess.resolve_prescription(_GOBLET, last, "low", _HELD, last_session_sets=sets)
    assert held["weight_kg"] == 20.0


def test_the_hold_is_not_a_reduced_load_day():
    # A green morning in a repeated week is still green: no fatigue banner.
    assert _HELD["reduced"] is False
    assert (_HELD["banner_kind"], _HELD["banner_text"]) == (_GREEN["banner_kind"],
                                                           _GREEN["banner_text"])


def test_a_reduced_day_inside_a_held_week_stays_at_or_under_the_last_session():
    reduced = sess.load_policy({"signal_color": "orange", "label": "REDUCED VOLUME"},
                               {"volume_factor": 1.0})
    last, sets = _last([13, 13, 13], 22.5)
    held = sess.resolve_prescription(_GOBLET, last, "high",
                                     sess.hold_for_failed_week(reduced),
                                     last_session_sets=sets, previous_session_sets=sets)
    assert held["weight_kg"] <= 22.5 and held["reps"] <= 13
    assert "reduced-load day" in sess.actual_caption(held)


def test_the_invariant_check_covers_a_held_week():
    with pytest.raises(sess.PrescriptionContradiction, match="failed-week repeat"):
        sess.assert_within_ceiling({"reps": 8, "weight_kg": 25.0},
                                   {"weight_kg": 22.5, "reps": 8}, _HELD, "Goblet Squat")


# ═════════════════════════════════════════════════════════════════════════════
#  Storage
# ═════════════════════════════════════════════════════════════════════════════

def _config(path=None, mode="readonly"):
    return Config(
        notion_api_key="k", notion_db_readiness="db-readiness",
        notion_db_training="db-training", notion_db_config="db-config",
        google_sheets_id="e", google_service_account={},
        datastore_path=path, datastore_mode=mode)


class _FakeNotion:
    def __init__(self, pages=None):
        self._pages = list(pages or [])
        self.writes = []
        outer = self

        class _Pages:
            def update(self, page_id, properties=None, **kw):
                outer.writes.append(("update", page_id, properties))
                return {"id": page_id}

            def create(self, parent, properties=None, **kw):
                outer.writes.append(("create", parent["database_id"], properties))
                return {"id": "page-new"}

        class _Databases:
            def query(self, **kw):
                return {"results": outer._pages, "has_more": False}

        self.pages = _Pages()
        self.databases = _Databases()


def _phases_page(phases_json: str) -> dict:
    return {"id": "3bec1e81-c8fe-8106-b48a-d7e98fa5d5eb", "properties": {
        "Key": {"title": [{"plain_text": "phases"}]},
        "Value": {"rich_text": [{"plain_text": phases_json}]}}}


@pytest.fixture(autouse=True)
def _empty_outbox():
    supabase_store.OUTBOX.drain()
    yield
    supabase_store.OUTBOX.drain()


def test_the_new_fields_are_stored_only_by_a_block_that_uses_them():
    repo = Repository(_config())
    repo._notion_client = _FakeNotion()
    repo.set_phases(_after_first_failure(), today=TUE_0915)
    (_, _, props), = repo._notion_client.writes
    stored = json.loads("".join(c["text"]["content"] for c in props["Value"]["rich_text"]))
    assert "week_plan" not in stored[0] and "week_results" not in stored[0]
    assert stored[2]["week_plan"] == [1, 2, 3, 4, 4]
    assert stored[2]["week_results"] == {
        "2026-09-07": "Failed — 1 of 7 days logged, repeated the week after"}
    assert "week_plan" not in stored[3] and "week_results" not in stored[3]

    reread = Repository(_config())
    reread._notion_client = _FakeNotion([_phases_page(json.dumps(stored))])
    assert reread.get_phases() == _after_first_failure()


def test_a_week_plan_that_does_not_fit_its_length_is_refused():
    from services.plan import WeekAlignmentError

    repo = Repository(_config())
    repo._notion_client = _FakeNotion()
    with pytest.raises(WeekAlignmentError, match="week_plan"):
        repo.set_phases([replace(BLOCK_A, week_plan=[1, 2, 3, 4, 4])])
    assert repo._notion_client.writes == []


def test_the_live_read_goes_past_a_stale_local_copy(tmp_path):
    """The hosted app reads phases from its own copy, which a seed-script write
    never reaches. The automatic writer must read Notion itself, or it writes
    the older list over the newer one."""
    path = tmp_path / "cache.db"
    conn = sqlite3.connect(path)
    conn.executescript((ROOT / "services" / "datastore_schema.sql").read_text(encoding="utf-8"))
    conn.execute("INSERT INTO config (key, value, updated) VALUES (?,?,?)",
                 ("phases", json.dumps([{"phase_number": 3, "name": "old",
                                         "start_date": "2026-08-17", "length_days": 28,
                                         "status": "active"}]), "2026-09-11"))
    conn.commit()
    conn.close()
    newer = [{"phase_number": 3, "name": "new", "start_date": "2026-08-17",
              "length_days": 35, "status": "active", "week_plan": [1, 2, 3, 4, 4]}]
    repo = Repository(_config(str(path), mode="cache"))
    repo._notion_client = _FakeNotion([_phases_page(json.dumps(newer))])
    assert repo.get_phases()[0].name == "old"
    assert repo.get_phases_live()[0].week_plan == [1, 2, 3, 4, 4]


# ═════════════════════════════════════════════════════════════════════════════
#  The training screen
# ═════════════════════════════════════════════════════════════════════════════

_VIEW = (ROOT / "views" / "training.py").read_text(encoding="utf-8")


def test_the_training_screen_never_looks_content_up_by_authored_day():
    """In a repeated week the calendar position and the authored day differ,
    and a lookup by authored day shows last month's session with no error."""
    calls = [node for node in ast.walk(ast.parse(_VIEW))
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == "plan_dict_for_phase"]
    assert calls == [], "use sess.calendar_plan(phase) for a phase's day content"


def _function_source(name: str) -> str:
    tree = ast.parse(_VIEW)
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(_VIEW, node)


def test_the_automatic_repeat_rereads_notion_before_it_writes():
    render = _function_source("render")
    rule_at = render.index("week_repeat.apply_failed_week_rule(")
    write_at = render.index("set_phases(_fw_new)")
    assert rule_at < render.index("get_phases_live()", rule_at) < write_at


def test_the_redo_rereads_notion_before_it_writes():
    redo = _function_source("_render_week_repeat")
    assert redo.index("get_phases_live()") < redo.index("set_phases(_fresh)")


def test_the_rule_runs_before_the_scheduling_writers_that_depend_on_it():
    render = _function_source("render")
    assert render.index("apply_failed_week_rule(") < render.index("missed_reschedules(")


def test_the_screen_holds_the_load_before_anything_reads_the_policy():
    render = _function_source("render")
    hold_at = render.index("sess.hold_for_failed_week(_policy)")
    assert "week_repeat.failed_week_holds_load(phases" in render
    assert render.index("_policy = _verdict.policy") < hold_at
    assert hold_at < render.index('_volume_factor = _policy["volume_factor"]')
    assert hold_at < render.index("_render_accessory_session(")


def test_the_screen_seeds_with_both_sessions_and_the_pain_gate():
    """The engine's two-session rule and the pain gate only exist if the screen
    hands them their inputs; a missing argument would silently mean 'never
    step' (no previous session) or 'always allowed' (no block)."""
    seed = _function_source("_seed_actuals_if_needed")
    call_at = seed.index("sess.resolve_prescription(")
    assert "get_previous_session_all_sets(" in seed[:call_at]
    assert "get_recent_readiness(" in seed[:call_at]
    assert "previous_session_sets=previous_session_sets" in seed[call_at:]
    assert "step_block=step_block" in seed[call_at:]
    # A failed read blocks rather than allowing the step.
    assert 'step_block = "today\'s check-in could not be read"' in seed


# ═════════════════════════════════════════════════════════════════════════════
#  When the redo is OFFERED (athlete, 2026-09-18)
# ═════════════════════════════════════════════════════════════════════════════
#
# "It only shows if the previous week was a failed week and only shows on the
# Monday, if accepted it doesn't show until the next Monday if that repeated
# week also fails." The button had stood at the top of the training page every
# day of a week he had already repeated.

MON_0921 = date(2026, 9, 21)


def test_the_redo_is_offered_on_a_monday_after_a_failed_week():
    # The week of 09-14 logged two days.
    logged = LOGGED | {"2026-09-15", "2026-09-16"}
    assert wr.redo_is_offered(_after_first_failure(), logged, MON_0921)


def test_the_redo_is_not_offered_on_any_other_day():
    logged = LOGGED | {"2026-09-15", "2026-09-16"}
    for offset in range(1, 7):
        day = MON_0921 + timedelta(days=offset)
        assert not wr.redo_is_offered(_after_first_failure(), logged, day), day


def test_the_redo_is_not_offered_when_last_week_was_not_failed():
    three_days = LOGGED | {"2026-09-15", "2026-09-16", "2026-09-17"}
    assert not wr.redo_is_offered(_after_first_failure(), three_days, MON_0921)


def test_the_redo_is_not_offered_in_the_week_he_already_repeated():
    """The report that produced the rule: mid-week, inside the repeat."""
    for day in (TUE_0915, date(2026, 9, 18)):
        assert not wr.redo_is_offered(_after_first_failure(), LOGGED, day)


def test_a_redone_week_that_also_fails_is_offered_again():
    """The count decides, not the stored verdict: a week redone BY CHOICE is
    recorded as redone when chosen and never judged, so reading the verdict
    would hide the offer after exactly the redo he asked for."""
    after, _ = wr.redo_this_week(_after_first_failure(), LOGGED, date(2026, 9, 16))
    assert _by_number(after, 3).week_results["2026-09-14"].startswith(wr.REDONE_PREFIX)
    assert wr.redo_is_offered(after, LOGGED | {"2026-09-15"}, MON_0921)


def test_the_redo_is_not_offered_outside_a_block():
    assert not wr.redo_is_offered([], LOGGED, MON_0921)


def test_the_screen_asks_the_rule_before_it_draws_the_button():
    redo = _function_source("_render_week_repeat")
    assert redo.index("redo_is_offered(") < redo.index('st.button("Redo this week"')
