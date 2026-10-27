"""scripts/measure_oura_sleep_curves.py: how Oura's curves for Total Sleep and
Efficiency are measured from his nights (Sleep Score MODEL_VERSION 4,
2026-10-27). The live measurement reads the store; these pin the rule."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "measure_oura_sleep_curves",
    Path(__file__).resolve().parent.parent / "scripts" / "measure_oura_sleep_curves.py")
curves = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(curves)


def test_a_step_counts_only_with_enough_nights_and_sits_at_its_middle():
    pairs = [(5.6, 50.0)] * 5 + [(6.1, 60.0)] * 4
    assert curves.curve(pairs, 5.5, 6.5, 0.5) == ((5.75, 50.0),)


def test_the_curve_never_falls_as_the_reading_rises():
    pairs = [(5.6, 60.0)] * 5 + [(6.1, 55.0)] * 5
    assert curves.curve(pairs, 5.5, 6.5, 0.5) == ((5.75, 60.0), (6.25, 60.0))


def test_the_fit_says_how_far_oura_s_part_sits_from_the_curve():
    knots = ((5.75, 50.0), (6.25, 60.0))
    f = curves.fit([(5.75, 50.0), (6.0, 59.0), (6.25, 56.0)], knots)
    assert f["nights"] == 3
    assert f["mean"] == (0 + 4 + 4) / 3
    assert f["within_3"] == 1 / 3


def test_the_pairs_are_hours_and_efficiency_against_oura_s_own_parts():
    rows = [{"oura_sleep_total_seconds": 21600.0, "oura_sleep_total_sleep_score": 63.0,
             "oura_sleep_efficiency": 80.0, "oura_sleep_efficiency_score": 72.0},
            {"oura_sleep_total_seconds": None, "oura_sleep_total_sleep_score": 50.0,
             "oura_sleep_efficiency": None, "oura_sleep_efficiency_score": None}]
    total, eff = curves.pairs_from(rows)
    assert total == [(6.0, 63.0)]
    assert eff == [(80.0, 72.0)]
