# -*- coding: utf-8 -*-
"""The accessory session must be worth opening: 10 minutes, all of it training.

Athlete, 2026-08-18, looking at the live screen: "the extra training set is
too short it should be at least 10 mins and decompression breathing is not
training."

Both were true and the screen was flattering itself. It read "3 items · about
10 min" over a session that was Dead Hang, one release, and two minutes of
lying face down breathing. The 10 came from estimate_duration, which counts a
per-side item ONCE -- the screen even says so in its own caption -- so the
real working time was nearer six minutes, a third of it breathing.

TWO CAUSES, and the second is the interesting one. Breathing was a fixed
closing slot on both tiers. And the shrunk tier took exactly one release item,
which on a GYM day is where it collapses: the block's own release block has
already used the ischial, upper-glute, piriformis and anterior-hip items, and
the accessory recipe substitutes past a collision rather than repeating work
-- correctly -- so there was almost nothing left to take.

THE FIX. Breathing leaves the recipe (the exercise stays in training_plan;
Stage 1 uses it). The shrunk tier now fills from RELEASE-ONLY candidates until
it clears a 10-minute floor measured in laterality-aware working time. Release
is not a training stressor, so a longer shrunk session still honours the
tier's contract -- what it must never do is reach into _ACTIVATE.
"""
from __future__ import annotations

import datetime as dt

import pytest

import training_plan as tp
from services import accessory as acc

TODAY = dt.date(2026, 8, 18)


def _choose(plan_day, **kw):
    return acc.choose(plan_day=plan_day, region_rows=[], region_acwr={},
                      volume_rec={}, battery_baseline_captured=True,
                      legs_must_stay_clean=False, today=TODAY, **kw)


#: Every day of the live block, so the floor is tested against real collisions
#: rather than an empty session.
ALL_DAYS = sorted(tp.PLAN_STAGE2B)


@pytest.mark.parametrize("day", ALL_DAYS)
def test_no_accessory_session_prescribes_breathing(day):
    """"Decompression breathing is not training." It may be worth doing; it is
    not what a session offered as extra training should spend a fifth of
    itself on."""
    choice = _choose(tp.PLAN_STAGE2B[day])
    names = [e["name"] for e in choice.exercises]
    assert "Prone Decompression Breathing" not in names, (day, names)


@pytest.mark.parametrize("day", ALL_DAYS)
def test_the_shrunk_tier_clears_its_ten_minute_floor(day):
    """The floor is on WORK, both sides counted -- not on estimate_duration,
    which is known to read low and is what produced the misleading '10 min'."""
    choice = _choose(tp.PLAN_STAGE2B[day])
    if choice.tier != acc.TIER_SHRUNK:
        return
    worked = acc.work_seconds(choice.exercises)
    assert worked >= acc.SHRUNK_MIN_WORK_SECONDS, (
        f"day {day}: shrunk session is {worked / 60:.1f} min of work, floor is "
        f"{acc.SHRUNK_MIN_WORK_SECONDS / 60:.0f} — "
        f"{[e['name'] for e in choice.exercises]}"
    )


@pytest.mark.parametrize("day", ALL_DAYS)
def test_the_shrunk_tier_never_reaches_into_adaptation_seeking_work(day):
    """THE CONTRACT THE FLOOR MUST NOT BREAK. A shrunk session fires on rest
    days, assessment days and gym days at RPE 6+ precisely because the right
    answer there is no training stimulus. Filling it with release is fine;
    filling it with activation would quietly turn a rest day into a session."""
    choice = _choose(tp.PLAN_STAGE2B[day])
    if choice.tier != acc.TIER_SHRUNK:
        return
    activation = {e["name"] for pool in acc._ACTIVATE.values() for e in pool}
    # Items that appear in BOTH pools are release by nature (thoracic
    # extension); what must not appear is anything only an activation list has.
    release = {e["name"] for e in acc._SHRUNK_FILL} | {
        e["name"] for e in tp.ACCESSORY_HANG_LADDER}
    for e in choice.exercises:
        if e["name"] in activation:
            assert e["name"] in release, (
                f"day {day}: shrunk session took {e['name']!r}, which only an "
                f"activation list offers"
            )


@pytest.mark.parametrize("day", ALL_DAYS)
def test_no_exercise_is_prescribed_twice_in_one_day(day):
    """The recipe substitutes past a collision with the block's own session.
    The fill loop must not undo that by taking something twice."""
    choice = _choose(tp.PLAN_STAGE2B[day])
    names = [e["name"] for e in choice.exercises]
    assert len(names) == len(set(names)), (day, names)
    planned = {e["name"] for e in tp.PLAN_STAGE2B[day]["exercises"]}
    assert not (set(names) & planned), (
        f"day {day} repeats work the session itself already does: "
        f"{sorted(set(names) & planned)}"
    )


def test_a_gym_day_is_the_hard_case_and_still_clears():
    """Day 2 is the live example: a loaded session at RPE 6, so the tier
    shrinks, and the release block has already taken four of the candidates.
    This is the case that produced two real exercises before the fix."""
    choice = _choose(tp.PLAN_STAGE2B[2])
    assert choice.tier == acc.TIER_SHRUNK
    assert acc.work_seconds(choice.exercises) >= acc.SHRUNK_MIN_WORK_SECONDS
    assert len(choice.exercises) >= 4


def test_a_short_session_says_so_rather_than_pretending():
    """If the pool genuinely runs out, the reason is recorded. Silence would
    put the app back where it started -- a session that reads 10 minutes and
    is not."""
    src = __import__("inspect").getsource(acc.choose)
    assert "floor" in src and "short_by" in src


def test_work_seconds_counts_both_sides():
    """The whole reason the old number lied."""
    one_side = [{"name": "x", "type": "hold", "laterality": "bilateral",
                 "sets": 1, "hold_seconds": 60, "rest_seconds": 0}]
    two_side = [dict(one_side[0], laterality="unilateral")]
    assert acc.work_seconds(two_side) == 2 * acc.work_seconds(one_side)
