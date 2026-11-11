"""The evening mobility session (2026-11-11): services/mobility_session.py.

The athlete, from the flexibility blueprint's second-best slot (same day,
evening, after morning training): "strength training in the morning and
mobilty in the evening, lets schedule it on the days I have no strength
training the next day ... The mobility training will replace the tendon
training on those days." His answers the same day: "Two evenings, no Sunday"
and "Follow the rule".

What it pins:
- the evening is due on a day whose scheduled plan day is a strength session
  and whose next day's is not, read through date_overrides, so it moves when
  the sessions move;
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


def test_the_evening_follows_the_sessions_when_they_move():
    """"Follow the rule": the week of 2026-11-09 as it is stored, session D
    moved onto Tuesday and the rest along: B on Wednesday, rest on Thursday, C
    on Friday. The evenings are Wednesday and Friday, as he said."""
    phases = _phases(**{"2026-11-10": 26, "2026-11-11": 23, "2026-11-12": 24,
                        "2026-11-13": 25})
    due = [d for d in _week(4) if mob.is_due(phases, d)]
    assert due == [date(2026, 11, 11), date(2026, 11, 13)]


# ─── A move never adds an evening (the athlete, 2026-11-11) ─────────────────

#: Week 4 with Friday's C moved to Thursday: Wednesday B, Thursday C, Friday
#: rest, Saturday D, Sunday rest.
_C_ON_THURSDAY = {"2026-11-10": 23, "2026-11-11": 23, "2026-11-12": 25, "2026-11-13": 24,
                  "2026-11-14": 26, "2026-11-15": 27}
WED, THU, SAT = date(2026, 11, 11), date(2026, 11, 12), date(2026, 11, 14)


def test_a_moved_evening_not_yet_done_goes_to_the_new_day():
    """"when I move the Friday training to Thursday the evening mobility if
    not performed goes to Thursday": Wednesday's evening not done, Thursday
    and Saturday both have one."""
    phases = _phases(**_C_ON_THURSDAY)
    assert [d for d in _week(4) if mob.is_due(phases, d)] == [THU, SAT]
    assert not mob.is_due(phases, WED), "Wednesday is no longer before a day off"


def test_a_moved_evening_already_done_is_not_owed_again():
    """Wednesday's evening done, then C moved to Thursday: the week still owes
    one evening, Saturday's; Thursday has none."""
    phases = _phases(**_C_ON_THURSDAY)
    assert not mob.is_due(phases, THU, done_on=[WED])
    assert mob.is_due(phases, SAT, done_on=[WED])
    assert not mob.is_due(phases, SAT, done_on=[WED, THU]), "both evenings done"


def test_a_done_evening_in_a_normal_week_leaves_the_second_one():
    phases = _phases()
    tuesday, friday = _week(5)[1], _week(5)[4]
    assert mob.is_due(phases, friday, done_on=[tuesday])
    assert mob.is_due(phases, friday, done_on=[]), "a missed Tuesday is not made up, nor taken away"
    # A session done in another week does not count in this one.
    assert mob.is_due(phases, friday, done_on=[_week(4)[4]])


def test_a_forced_rest_has_no_evening_and_gives_one_to_the_day_before():
    phases = _phases(**{"2026-11-16": 0})              # Monday of week 5 forced rest
    assert not mob.is_due(phases, date(2026, 11, 16))
    phases = _phases(**{"2026-11-17": 0})              # Tuesday forced rest
    assert mob.is_due(phases, date(2026, 11, 16)), "Monday is now before a day off"


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
