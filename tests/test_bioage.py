"""
Tests for services/bioage.py — the muscle-imbalance count.

The seventeen tests that covered the Stage-Adjusted Recovery Score were
removed with the score itself on 2026-08-04 (see that module's docstring for
why it could only ever read 100). They were correct tests of code that no
longer runs; git history holds them if the reasoning is ever needed.

What is left is the count that still renders, and the property that matters
about it: it reads the clinical profile directly, so it does not depend on
training history, a date, or the network.
"""

from __future__ import annotations

import patient_profile
from services import bioage


def test_muscle_imbalance_count_sums_both_lists():
    imbalances = {"overactive_tight": ["a", "b", "c"], "underactive_weak": ["d"]}
    assert bioage.muscle_imbalance_count(imbalances) == 4


def test_muscle_imbalance_count_handles_missing_keys():
    assert bioage.muscle_imbalance_count({}) == 0


def test_muscle_imbalance_count_against_real_patient_profile():
    # Regression check: if patient_profile.PROFILE's imbalances change
    # (CLAUDE.md rule 8 — updated before each new training block), this
    # documents that the count changed intentionally rather than silently.
    assert bioage.muscle_imbalance_count(patient_profile.PROFILE["imbalances"]) == 8


def test_the_retired_scoring_functions_are_gone():
    """A guard, not a formality. The defect was subtle enough to survive review
    once — a ratio whose denominator maximises over a set containing its own
    numerator — so reintroducing any of these names should fail loudly rather
    than quietly restore a metric that reads 100 forever."""
    for name in ("region_effort", "has_weighted_training", "current_window_effort",
                 "region_baseline_ceiling", "region_recovery_score", "hero_score"):
        assert not hasattr(bioage, name), (
            f"{name} is back — see services/bioage.py's docstring before wiring it up"
        )
