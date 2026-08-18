# -*- coding: utf-8 -*-
"""The Cluster A session must be exercises, not a label.

Athlete, 2026-08-18: "I see you have put in just Cluster A Flexibility
session, 25 Mins — you need to break down every exercise and put it in as a
workout, you cant leave it as a block that defeats the whole purpose of it."

He was right, and it was the same failure the release protocols had: the five
items were fully authored in cluster_a_prescription.STACKS["D"], with
position/movement/feel/stop/progress text in the mechanics library, and none
of it had ever reached training_plan.py. The plan carried ONE entry —
"Cluster A Flexibility Session", 25 minutes, duration — so the guided flow
showed a label and a timer. Nothing was logged per exercise, so nothing
reached Strain, the regional split, the per-exercise notes, or the day-28
review. Three layers of careful work rendered as a countdown.

WHAT THIS PINS. The plan's cluster day must BE the prescribed stack: same
exercises, same order, same doses. Authoring it into the plan creates a second
copy of a decision that already lives in the prescription, so the copy is
bound to its source here rather than trusted to stay in step.
"""
from __future__ import annotations

import pytest

import cluster_a_mechanics as cm
import cluster_a_prescription as cp
import training_constants as tc
import training_plan as tp
from services import rules

PLAN = tp.PLAN_STAGE2B
#: The days the cluster session runs. Derived, not hardcoded, so the test
#: follows the block if the session moves.
CLUSTER_DAYS = [d for d in sorted(PLAN)
                if "Cluster A" in (PLAN[d].get("objective") or "")]

#: The pattern the battery actually returned, cold, on 2026-08-12. If a later
#: assessment changes it, the plan's stack changes with it and this constant is
#: the one line that has to move.
PATTERN = "D"
STACK = cp.STACKS[PATTERN]
STACK_NAMES = [cm.exercise(i.exercise).name for i in STACK.items]


def _cluster_exercises(day: int) -> list[dict]:
    """The day's exercises that belong to the stack — i.e. everything after the
    release block and the raise."""
    return [e for e in PLAN[day]["exercises"] if e["name"] in STACK_NAMES]


def test_the_cluster_session_actually_runs_somewhere():
    assert CLUSTER_DAYS, "no cluster day in the block"


def test_the_label_block_is_gone():
    """The single 25-minute duration entry that replaced five exercises."""
    for d in sorted(PLAN):
        names = [e["name"] for e in PLAN[d]["exercises"]]
        assert "Cluster A Flexibility Session" not in names, (
            f"day {d} still carries the opaque session block — a label and a "
            f"timer instead of the prescribed work"
        )


@pytest.mark.parametrize("day", CLUSTER_DAYS)
def test_every_prescribed_exercise_is_in_the_day(day):
    assert [e["name"] for e in _cluster_exercises(day)] == STACK_NAMES, (
        f"day {day}'s cluster work does not match pattern {PATTERN}'s stack"
    )


@pytest.mark.parametrize("day", CLUSTER_DAYS)
def test_the_stack_runs_after_the_release_block(day):
    """The prescription's own rule: every stack is prefixed with the release
    block. Stretching into an ungripped hip is the point of the ordering."""
    names = [e["name"] for e in PLAN[day]["exercises"]]
    first_stack = min(names.index(n) for n in STACK_NAMES)
    release = [n for n in names[:first_stack]
               if n in __import__("services.sessions", fromlist=["x"]).RELEASE_EXERCISE_NAMES]
    assert release, f"day {day} starts the stack with no release block before it"


@pytest.mark.parametrize("day", CLUSTER_DAYS)
def test_the_doses_match_the_prescription(day):
    """The plan holds a COPY of a decision the prescription owns. Bound here so
    the two cannot drift — the same anti-drift idiom as the argmax test that
    binds the two region maps."""
    by_name = {e["name"]: e for e in _cluster_exercises(day)}
    for item in STACK.items:
        name = cm.exercise(item.exercise).name
        ex = by_name[name]
        dose = item.dose.lower()
        # The dose string is prose ("4 × 90 s", "3 × 10", "3 × 8 per side").
        # What must agree is the SET COUNT, which is the number the athlete
        # performs and the one a drifting copy would get wrong first.
        head = dose.split("×")[0].split("x")[0].strip()
        if head.isdigit():
            assert ex["sets"] == int(head), (
                f"day {day} {name!r}: plan has {ex['sets']} sets, prescription "
                f"says {item.dose!r}"
            )


@pytest.mark.parametrize("name", STACK_NAMES)
def test_every_stack_name_is_mapped(name):
    """An unmapped name scores at the 1.0 barbell tier and vanishes from the
    regional split — the 2026-08-01 Stage 1 over-count, by another door."""
    assert tc.EXERCISE_MOVEMENT_WEIGHT.get(name), name
    assert tc.EXERCISE_BODY_REGION.get(name), name


@pytest.mark.parametrize("name", STACK_NAMES)
def test_every_stack_name_reaches_the_safety_rules(name):
    """These are wide-stance, end-range hip positions on a body with a
    retrolisthesis. `unknown` reads exactly like `cleared`, so each name must
    actually land on a rule."""
    assert rules.check_movement(name, 2)["severity"] in ("caution", "cleared"), name


@pytest.mark.parametrize("name", STACK_NAMES)
def test_every_stack_exercise_tells_the_athlete_how(name):
    """The mechanics text is why breaking the block up is worth doing: the
    guided flow can show position, movement, feel and stop for each item. A
    25-minute timer could show none of it."""
    ex = next(e for d in CLUSTER_DAYS for e in PLAN[d]["exercises"]
              if e["name"] == name)
    mech = ex["mechanics"]
    assert len(mech) > 120, f"{name} has no real how-to text"
    assert "FEEL:" in mech and "STOP:" in mech, (
        f"{name} must carry its feel and stop cues — the stop is the safety "
        f"instruction for an end-range hip position"
    )


def test_the_right_hip_keeps_its_rotation_cue():
    """Key rule 7: right hip flexion past 60 degrees is cued neutral or
    slightly internal, because external rotation is what snaps. The 90/90 is
    the one item in this stack that takes the right hip there."""
    ex = next(e for d in CLUSTER_DAYS for e in PLAN[d]["exercises"]
              if e["name"].startswith("90/90"))
    text = (ex["mechanics"] + ex.get("regression", "")).lower()
    assert "internal" in text and "right" in text, (
        "the 90/90 must carry the neutral/internal rotation cue on the right"
    )
