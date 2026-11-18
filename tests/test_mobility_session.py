"""The evening mobility session (2026-11-11): services/mobility_session.py.

The athlete, from the flexibility blueprint's second-best slot (same day,
evening, after morning training): "strength training in the morning and
mobilty in the evening, lets schedule it on the days I have no strength
training the next day ... The mobility training will replace the tendon
training on those days." His answers the same day: "Two evenings, no Sunday"
and "Follow the rule".

What it pins:
- the evening is due on the second of two training days in a row with a rest
  day after it (2026-11-18: "mobility only when there is a rest day the next
  day after the two days of training"): yesterday trained (a logged plan
  session), today a strength day, tomorrow rest, read through date_overrides,
  so it moves when the sessions move; a strength day alone has none;
- in a normal week that is Tuesday and Friday, never more than two a week (the
  blueprint's limit), and from week 4 no Sunday session;
- the session is the Sunday stack, defined in goal_block.py, never here;
- its Type is its own, never "Mobility" (a plan exercise's movement type), an
  extra that never marks a plan day done and never makes a logged day.
"""

from __future__ import annotations

import ast
import dataclasses
from datetime import date, timedelta
from pathlib import Path

import goal_block as gb
from services import mobility_session as mob
from services import sessions as sess
from services.repository import Repository

ROOT = Path(__file__).resolve().parents[1]
PLAN = gb.PLAN_GOAL_BLOCK


def _phases(**overrides):
    return [dataclasses.replace(sess.build_phase(5, gb.START), date_overrides=dict(overrides))]


def _week(n: int) -> list[date]:
    monday = gb.START + timedelta(days=(n - 1) * 7)
    return [monday + timedelta(days=i) for i in range(7)]


def test_a_normal_week_has_its_evenings_on_tuesday_and_friday():
    """Strength Monday, Tuesday, Thursday, Friday: Tuesday is before the
    Wednesday rest, Friday before the Saturday rest."""
    phases = _phases()
    for n in range(gb.EVENING_MOBILITY_FROM_WEEK, gb.WEEKS + 1):
        due = [d.strftime("%a") for d in _week(n) if mob.is_due(phases, d)]
        assert due == ["Tue", "Fri"], n


def test_never_more_than_two_evenings_a_week_and_no_sunday_session():
    """"Two evenings, no Sunday": the blueprint allows one or two flexibility
    sessions a week, so from week 4 the Sunday is a rest day."""
    phases = _phases()
    for n in range(gb.EVENING_MOBILITY_FROM_WEEK, gb.WEEKS + 1):
        sunday = PLAN[n * 7]
        assert sunday["day_type"] == "rest" and sunday["exercises"] == [], n
        flexibility_days = [d for d in range(n * 7 - 6, n * 7 + 1)
                            if PLAN[d].get("session_kind") == "flexibility"]
        evenings = [d for d in _week(n) if mob.is_due(phases, d)]
        assert flexibility_days == [] and 1 <= len(evenings) <= 2, n


def test_the_evening_follows_the_sessions_when_they_move_and_a_lone_day_has_none():
    """"Follow the rule": session D moved onto Tuesday and the rest along: B
    on Wednesday, rest on Thursday, C on Friday, rest on Saturday. Wednesday is
    the second of two training days before a rest day; Friday's C stands alone
    between two rest days and has no evening (2026-11-18)."""
    phases = _phases(**{"2026-11-10": 26, "2026-11-11": 23, "2026-11-12": 24,
                        "2026-11-13": 25})
    due = [d for d in _week(4) if mob.is_due(phases, d)]
    assert due == [date(2026, 11, 11)]


# ─── A move never adds an evening (the athlete, 2026-11-11) ─────────────────

#: Week 4 with Friday's C moved to Thursday: Wednesday B, Thursday C, Friday
#: rest, Saturday D, Sunday rest.
_C_ON_THURSDAY = {"2026-11-10": 23, "2026-11-11": 23, "2026-11-12": 25, "2026-11-13": 24,
                  "2026-11-14": 26, "2026-11-15": 27}
WED, THU, SAT = date(2026, 11, 11), date(2026, 11, 12), date(2026, 11, 14)


MON4 = date(2026, 11, 9)


def test_a_moved_session_takes_the_evening_to_the_new_second_day():
    """"when I move the Friday training to Thursday the evening mobility if
    not performed goes to Thursday": Monday's A trained, Tuesday missed, B on
    Wednesday, C moved to Thursday, rest on Friday. Wednesday's B follows a
    missed day and has none; Thursday is the second of two training days
    before a rest day; Saturday's D stands alone after Friday's rest."""
    phases = _phases(**_C_ON_THURSDAY)
    assert not mob.is_due(phases, WED, trained_on={MON4}), "Tuesday was not trained"
    assert mob.is_due(phases, THU, trained_on={MON4, WED})
    assert not mob.is_due(phases, SAT, trained_on={MON4, WED, THU}), "D alone after a rest day"


#: Week 5 with Thursday's C moved to Wednesday: Monday A, Tuesday B, Wednesday C,
#: Thursday rest, Friday D, Saturday and Sunday rest.
_C_ON_WEDNESDAY = {"2026-11-18": 32, "2026-11-19": 31}
MON5, TUE5, WED5 = date(2026, 11, 16), date(2026, 11, 17), date(2026, 11, 18)


def test_a_moved_evening_already_done_is_not_owed_again():
    """A move never adds an evening: Tuesday's evening done, then Thursday's C
    moved to Wednesday. Wednesday is now the second of two training days before
    a rest day, the week's only evening, and it is already done; not done, it
    has one."""
    phases = _phases(**_C_ON_WEDNESDAY)
    assert not mob.is_due(phases, WED5, done_on=[TUE5], trained_on={MON5, TUE5})
    assert mob.is_due(phases, WED5, done_on=[], trained_on={MON5, TUE5})


def test_a_missed_day_never_puts_the_evening_on_the_day_after_it():
    """The week of 16 Nov, as he saw it: Monday's A missed. Before the week
    moved, Tuesday held B with rest on Wednesday, and the tile read mobility on
    Tuesday at 12:05; after the move (A Tuesday, B Wednesday, rest Thursday, C
    Friday, D Saturday) it read mobility on Wednesday too. Now Tuesday has none
    either way, and the evenings are Wednesday and Saturday."""
    before = _phases()
    assert not mob.is_due(before, TUE5, trained_on=set()), "Monday was not trained"
    moved = _phases(**{"2026-11-17": 29, "2026-11-18": 30, "2026-11-19": 31,
                       "2026-11-20": 32, "2026-11-21": 33, "2026-11-22": 34})
    assert not mob.is_due(moved, TUE5, trained_on=set())
    assert mob.is_due(moved, WED5, trained_on={TUE5})
    assert not mob.is_due(moved, date(2026, 11, 20), trained_on={TUE5, WED5})
    assert mob.is_due(moved, date(2026, 11, 21), trained_on={TUE5, WED5, date(2026, 11, 20)})


def test_in_a_normal_week_the_evening_needs_yesterday_trained():
    """Tuesday's evening needs Monday's session done, Friday's Thursday's.
    Today counts by its plan: a strength day not yet trained still has its
    evening."""
    phases = _phases()
    mon, tue, thu, fri = _week(5)[0], _week(5)[1], _week(5)[3], _week(5)[4]
    assert mob.is_due(phases, tue, trained_on={mon})
    assert not mob.is_due(phases, tue, trained_on=set())
    assert mob.is_due(phases, fri, trained_on={mon, tue, thu})
    assert not mob.is_due(phases, fri, trained_on={mon, tue})
    assert mob.is_training_day(phases, tue, tue, set()), "today counts by its plan"
    assert not mob.is_training_day(phases, mon, tue, set()), "a past day counts by the log"


def test_a_done_evening_in_a_normal_week_leaves_the_second_one():
    phases = _phases()
    tuesday, friday = _week(5)[1], _week(5)[4]
    assert mob.is_due(phases, friday, done_on=[tuesday])
    assert mob.is_due(phases, friday, done_on=[]), "a missed Tuesday is not made up, nor taken away"
    # A session done in another week does not count in this one.
    assert mob.is_due(phases, friday, done_on=[_week(4)[4]])


def test_a_forced_rest_has_no_evening_and_a_strength_day_it_leaves_alone_has_none():
    phases = _phases(**{"2026-11-16": 0})              # Monday of week 5 forced rest
    assert not mob.is_due(phases, date(2026, 11, 16))
    assert not mob.is_due(phases, date(2026, 11, 17)), "Tuesday's B follows a day off"
    phases = _phases(**{"2026-11-17": 0})              # Tuesday forced rest
    assert not mob.is_due(phases, date(2026, 11, 16)), "Monday's A stands alone (2026-11-18)"


def test_no_block_no_evening_and_the_blocks_last_strength_day_has_one():
    assert not mob.is_due(_phases(), gb.START - timedelta(days=1))
    assert not mob.is_due([], date(2026, 11, 11))
    last_friday = gb.START + timedelta(days=gb.WEEKS * 7 - 3)
    assert last_friday.weekday() == 4 and mob.is_due(_phases(), last_friday)


def test_the_session_is_the_sunday_stack_and_this_module_defines_no_exercise():
    day = mob.build_day()
    assert [e["name"] for e in day["exercises"]] == [e["name"] for e in gb.FLEX_STACK]
    assert day["is_gym_session"] is False and day["session_kind"] == "flexibility"
    assert not sess.session_shape_violations(day)
    tree = ast.parse((ROOT / "services" / "mobility_session.py").read_text(encoding="utf-8"))
    calls = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
             for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "_ex" not in calls


def test_its_type_is_its_own_an_extra_and_never_a_logged_day():
    """Never "Mobility": plan exercises are stored under that movement type,
    and it would make their rows read as an extra. Not a logged day: it sits
    on a strength day, and counted, an evening session alone would mark a
    skipped strength day done."""
    assert mob.MOBILITY_TYPE == "Evening Mobility"
    assert "Mobility" not in Repository.SUPPLEMENTARY_SESSION_TYPES
    assert mob.MOBILITY_TYPE in Repository.SUPPLEMENTARY_SESSION_TYPES
    assert mob.MOBILITY_TYPE in Repository.NOT_A_TRAINING_DAY_TYPES


def test_done_today_reads_its_own_type():
    assert mob.done_today([{"session_id": "s", "type": mob.MOBILITY_TYPE, "last_set_ts": None}])
    assert not mob.done_today([{"session_id": "s", "type": "Daily", "last_set_ts": None}])
    assert not mob.done_today([])
