# -*- coding: utf-8 -*-
"""Every contraindication must carry its exit.

Written 2026-08-17, on the athlete's challenge, minutes after the same
standard was applied to the clinical findings. His two questions:

    "At what stage do any of these items get opened?"  — the answer was NEVER:
    no stage, date or measurement re-opens a contraindicated rule, verified by
    running one through check_movement at stages 1-4.

    "There is no physio appointment, so these will just stay unanswered — we
    need a better way."  — and the recorded standing instruction agrees:
    physio access is months apart; settle clinical questions here, and let
    tested findings overwrite guesswork.

So every contraindicated rule now carries an entry in
rules.CONTRAINDICATION_EXITS: what it rests on, what it costs against the
athlete's actual goals, and the EXIT — evidence obtainable by the athlete
alone that would downgrade it. The template is the running rule, which was
contraindicated-at-every-stage until its graded introduction was designed and
its severity corrected with the athlete's sign-off.

WHAT THIS DOES NOT DO: change a verdict. check_movement never reads the table.
A downgrade is an explicit severity edit citing the exit evidence — the
running correction's exact shape — never a side effect. "Never weaken a
guardrail" stays true; what ends is "held forever by default".
"""
from __future__ import annotations

import pytest

from services import rules

CONTRA = {r.movement: r for r in rules.MOVEMENT_RULES
          if r.severity == "contraindicated"}
EXITS = rules.CONTRAINDICATION_EXITS

REQUIRED_KEYS = ("rests_on", "cost_today", "exit", "single_person")


def test_every_contraindicated_rule_has_an_exit_entry():
    missing = sorted(set(CONTRA) - set(EXITS))
    assert not missing, (
        f"contraindicated rules with no exit entry: {missing}. A restriction "
        f"with no path to an answer is unfalsifiable — the state the whole "
        f"list was in until 2026-08-17."
    )


def test_every_exit_entry_names_a_real_contraindicated_rule():
    """The other direction: an entry for a rule that is no longer
    contraindicated is stale and must be retired with the downgrade."""
    stale = sorted(set(EXITS) - set(CONTRA))
    assert not stale, f"exit entries for non-contraindicated rules: {stale}"


@pytest.mark.parametrize("movement", sorted(EXITS))
def test_every_exit_is_fully_specified(movement):
    e = EXITS[movement]
    missing = [k for k in REQUIRED_KEYS if k not in e]
    assert not missing, f"{movement!r} exit is missing {missing}"
    for k in ("rests_on", "cost_today", "exit"):
        assert isinstance(e[k], str) and e[k].strip(), f"{movement!r}: empty {k}"


@pytest.mark.parametrize("movement", sorted(EXITS))
def test_every_exit_is_runnable_alone(movement):
    """The athlete's constraint, twice stated: a path that waits on a physio
    appointment is a path that stays unanswered."""
    assert EXITS[movement]["single_person"] is True, movement


@pytest.mark.parametrize("movement", sorted(EXITS))
def test_every_exit_names_what_the_rule_rests_on(movement):
    """The evidential basis must be on the entry, because the challenge that
    produced this table started with 'where does it say annular tears?' —
    a fair question the list could not answer about itself."""
    rests = EXITS[movement]["rests_on"].lower()
    assert any(w in rests for w in ("mri", "annulus", "retrolisthesis",
                                    "osteochondrosis", "source-document")), (
        f"{movement!r} does not name its evidence: {EXITS[movement]['rests_on']!r}"
    )


def test_a_deliberate_zero_cost_hold_is_a_stated_choice_not_an_absence():
    """Some rules cost nothing against any recorded goal, and holding them
    forever is correct — but only as a decision that says so."""
    for movement, e in EXITS.items():
        if "NO EXIT PROTOCOL" in e["exit"]:
            assert "zero" in e["cost_today"].lower(), (
                f"{movement!r} has no exit protocol but does not claim zero "
                f"cost — a real-cost rule needs a real exit"
            )


def test_the_table_changes_no_verdict():
    """check_movement must not consult the exits — a downgrade is an explicit
    severity edit with the evidence cited, never a side effect."""
    import inspect
    src = inspect.getsource(rules.check_movement)
    assert "CONTRAINDICATION_EXITS" not in src
