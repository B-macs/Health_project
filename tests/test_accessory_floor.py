# -*- coding: utf-8 -*-
"""The accessory session must be worth opening: at least ten minutes, all of it
training.

Athlete, 2026-08-18, looking at the live screen: "the extra training set is
too short it should be at least 10 mins and decompression breathing is not
training."

Both were true and the screen was flattering itself. It read "3 items · about
10 min" over a session that was Dead Hang, one release, and two minutes of
lying face down breathing. The 10 came from an estimate that counted a per-side
item ONCE and charged 30 s a changeover, so the real time was nearer six
minutes, a third of it breathing.

THE FIX, 2026-08-18: breathing left the recipe (the exercise stays in
training_plan; Stage 1 uses it), and the shrunk tier filled until it cleared a
floor of 600 s of WORK, both sides counted — a floor cannot sit on an estimate
known to read low.

THE FLOOR MOVED TO MODELLED TIME, 2026-10-13, when the release left the
session (athlete: "Drop the release"). Since 2026-09-11 the time model counts
both sides and the measured changeovers, so the floor sits on what the session
TAKES — what "10 mins" meant — at twelve minutes, never past the twenty of the
athlete's 10-20 ask. The work floor had been met by long release holds with few
changeovers; filled from shorter warm-up items it pushed a rest day to 22.
"""
from __future__ import annotations

import datetime as dt

import pytest

import training_plan as tp
from services import accessory as acc

TODAY = dt.date(2026, 10, 13)


def _choose(plan, day, **kw):
    return acc.choose(plan_day=plan[day], region_rows=[], region_acwr={},
                      volume_rec={}, legs_must_stay_clean=False,
                      tomorrow_plan_day=plan.get(day + 1), today=TODAY, **kw)


#: Every day of the live block and the one before it, so the floor is tested
#: against real collisions rather than an empty session.
ALL_DAYS = ([("block_b", tp.PLAN_BLOCK_B, d) for d in sorted(tp.PLAN_BLOCK_B)]
            + [("stage_2b", tp.PLAN_STAGE2B, d) for d in sorted(tp.PLAN_STAGE2B)])
IDS = [f"{name}-{day}" for name, _plan, day in ALL_DAYS]


@pytest.mark.parametrize("name, plan, day", ALL_DAYS, ids=IDS)
def test_no_accessory_session_prescribes_breathing(name, plan, day):
    """"Decompression breathing is not training." It may be worth doing; it is
    not what a session offered as extra training should spend a fifth of
    itself on."""
    choice = _choose(plan, day)
    names = [e["name"] for e in choice.exercises]
    assert "Prone Decompression Breathing" not in names, (day, names)


@pytest.mark.parametrize("name, plan, day", ALL_DAYS, ids=IDS)
def test_every_session_lands_inside_the_ten_to_twenty_minute_ask(name, plan, day):
    """At least ten modelled minutes — the floor of twelve is a target with a
    margin, and a Wednesday that cannot reach it without leg work stops short
    of it and says so — and never past twenty."""
    choice = _choose(plan, day)
    minutes = acc.modelled_minutes(choice.exercises)
    # Whole minutes, the way the screen states them: the Wednesday session is
    # 9.98 modelled minutes and reads "10 min".
    assert 10 <= round(minutes) <= acc.SESSION_MAX_MINUTES, (
        f"{name} day {day}: {minutes:.1f} min — {[e['name'] for e in choice.exercises]}")
    if choice.tier == acc.TIER_SHRUNK and minutes < acc.SHRUNK_MIN_MINUTES:
        assert any("under the" in r for r in choice.reasons), (
            "a session short of its floor says so")


@pytest.mark.parametrize("name, plan, day", ALL_DAYS, ids=IDS)
def test_the_shrunk_tier_never_reaches_into_adaptation_seeking_work(name, plan, day):
    """THE CONTRACT THE FLOOR MUST NOT BREAK. A shrunk session fires on rest
    days, assessment days and gym days at RPE 6+ precisely because the right
    answer there is no training stimulus. Filling it with warm-up-class work
    is fine; filling it with something only an activation list offers would
    quietly turn a rest day into a session."""
    choice = _choose(plan, day)
    if choice.tier != acc.TIER_SHRUNK:
        return
    activation = {e["name"] for pool in acc._ACTIVATE.values() for e in pool}
    warm_up = {e["name"] for e in acc._SHRUNK_FILL} | {
        e["name"] for e in tp.ACCESSORY_HANG_LADDER}
    for e in choice.exercises:
        if e["name"] in activation:
            assert e["name"] in warm_up, (
                f"day {day}: shrunk session took {e['name']!r}, which only an "
                f"activation list offers"
            )


@pytest.mark.parametrize("name, plan, day", ALL_DAYS, ids=IDS)
def test_no_exercise_is_prescribed_twice_in_one_day(name, plan, day):
    """The recipe substitutes past a collision with the block's own session.
    The fill loop must not undo that by taking something twice."""
    choice = _choose(plan, day)
    names = [e["name"] for e in choice.exercises]
    assert len(names) == len(set(names)), (day, names)
    planned = {e["name"] for e in plan[day]["exercises"]}
    assert not (set(names) & planned), (
        f"day {day} repeats work the session itself already does: "
        f"{sorted(set(names) & planned)}"
    )


def test_a_gym_day_is_the_hard_case_and_still_clears():
    """The squat day is the live example: a loaded session at RPE 7, so the
    tier shrinks, and its warm-up has already taken the march, the planks, the
    hip lift, the hip airplane and the glute bridge."""
    choice = _choose(tp.PLAN_BLOCK_B, 1)
    assert choice.tier == acc.TIER_SHRUNK
    assert acc.modelled_minutes(choice.exercises) >= acc.SHRUNK_MIN_MINUTES
    assert len(choice.exercises) >= 4
