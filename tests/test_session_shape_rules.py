"""Key Rule 21 — the session shape — applied to every block from Block B on.

The athlete's direction after the 81-minute session of 2026-09-10: limit the
number of exercises against what a normal hour holds, limit the one-set items,
nest ramp sets under their own lift, and price an exercise change at what it
measures. services.sessions.session_shape_violations is the check and this
file runs it over EVERY plan registered from SESSION_SHAPE_RULES_FROM_PHASE on,
so a future block cannot drift past the numbers without either fixing itself
or changing the constant deliberately — which is what "so future blocks don't
cross the same thing" means in code.

Stage 2B (phase 3) is the block that produced the rules and is exempt: it ends
2026-09-13 and its content is history. The one assertion about it here is that
it WOULD fail, so the rules cannot quietly become vacuous.
"""

from __future__ import annotations

import pytest

import training_plan as tp
from services import sessions as s

GOVERNED = sorted(n for n in s.PHASE_META if n >= s.SESSION_SHAPE_RULES_FROM_PHASE)


def test_at_least_one_block_is_governed():
    """A guard that checks nothing is worse than none."""
    assert GOVERNED, "no registered plan is subject to the session-shape rules"


@pytest.mark.parametrize("phase_number", GOVERNED)
def test_every_day_of_every_governed_block_fits_the_shape(phase_number):
    plan = s.plan_dict_for_phase(phase_number)
    bad = {d: s.session_shape_violations(plan[d]) for d in sorted(plan)}
    bad = {d: v for d, v in bad.items() if v}
    assert not bad, "\n".join(f"phase {phase_number} day {d}: {'; '.join(v)}"
                              for d, v in bad.items())


def test_the_rules_are_not_vacuous_stage_2b_day_22_would_fail_them():
    """The session that produced the rules: 20 entries, 81 minutes, ramps
    and top sets interleaved across two stations, eight working exercises."""
    reasons = s.session_shape_violations(tp.PLAN_STAGE2B[22])
    text = " ".join(reasons)
    assert "working exercises" in text
    assert "not immediately followed by its own lift" in text
    assert "min with measured changeovers" in text


def test_the_ceilings_are_what_the_athlete_set():
    """Three main lifts, one core item, one hip item — six leaves room for the
    press day's clinical face-pull pairing. No one-set training entries. Over
    an hour is fine; 84 is not."""
    assert s.SESSION_SHAPE["max_working_families"] == 6
    assert s.SESSION_SHAPE["max_single_set_training_entries"] == 0
    assert 60 <= s.SESSION_SHAPE["max_gym_minutes"] <= 70
    assert s.SESSION_SHAPE["max_preparation_entries"] == 7


def test_a_ramp_anywhere_but_before_its_lift_is_a_violation():
    lift = next(e for e in tp._s2b_gym_a(4)["exercises"] if e["name"] == "Goblet Squat")
    ok = {"day_type": "main", "exercises": [tp.GOBLET_RAMP, lift]}
    assert not [r for r in s.session_shape_violations(ok) if "followed" in r]
    stray = {"day_type": "main", "exercises": [tp.GOBLET_RAMP, tp.END_RANGE_PSOAS_ISOMETRIC, lift]}
    assert any("followed" in r for r in s.session_shape_violations(stray))


def test_an_unflagged_ramp_is_a_violation():
    lift = next(e for e in tp._s2b_gym_a(4)["exercises"] if e["name"] == "Goblet Squat")
    unflagged = dict(tp.GOBLET_RAMP, warmup=False)
    day = {"day_type": "main", "exercises": [unflagged, lift]}
    assert any("warmup=True" in r for r in s.session_shape_violations(day))


def test_a_one_set_training_entry_is_a_violation_but_activation_and_release_are_not():
    prep = [tp.UPPER_GLUTE_RELEASE_5MIN, tp.PREP_RAISE, tp.PREP_GLUTE_ACTIVATION]
    day = {"day_type": "main", "exercises": prep + [tp.END_RANGE_PSOAS_ISOMETRIC]}
    assert not [r for r in s.session_shape_violations(day) if "one-set" in r]
    day["exercises"] = prep + [dict(tp.END_RANGE_PSOAS_ISOMETRIC, sets=1)]
    assert any("one-set" in r for r in s.session_shape_violations(day))


def test_run_and_rest_days_are_only_held_to_the_nesting_rule():
    """A run day's content is the run; the counts and the clock are a gym
    session's rules and a flexibility day's."""
    day = {"day_type": "stretch", "exercises": tp.PLAN_STAGE2B[23]["exercises"]}
    assert s.session_shape_violations(day) == []


def test_a_flexibility_day_has_its_own_entry_and_minute_ceilings():
    """Block B's cluster day was 13 entries / 61 min before 2026-09-11; Stage
    2B's is pinned as failing so the rule cannot go vacuous."""
    assert s.SESSION_SHAPE["max_flexibility_entries"] == 10
    assert 40 <= s.SESSION_SHAPE["max_flexibility_minutes"] <= 55
    old = {"day_type": "stretch", "session_kind": "flexibility",
           "exercises": tp.PLAN_STAGE2B[25]["exercises"]}
    text = " ".join(s.session_shape_violations(old))
    assert "entries on a flexibility day" in text and "min on a flexibility day" in text
    assert s.session_shape_violations(tp.PLAN_BLOCK_B[4]) == []


def test_working_families_treat_ramp_top_and_lift_as_one():
    a4 = tp._s2b_gym_a(4)["exercises"]
    fams = s.working_families(a4)
    assert fams.count("Goblet Squat") == 1
    assert "Goblet Squat (Ramp Set)" not in fams and "Goblet Squat (Heavy Top Set)" not in fams
    assert "Walking Raise (Incline)" not in fams and "Dead Bug" not in fams
