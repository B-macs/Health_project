"""
Tests for services/stats.py, ported verbatim from the old flat tests.py runner.
"""

import ast
import random

from services import stats
from tests._legacy_check import check


def test_stats_symptom_detection():
    check("'shooting' -> neural",              stats.detect_neural_symptoms("shooting pain down my leg"), True)
    check("'tingling' -> neural",             stats.detect_neural_symptoms("tingling in my left foot"), True)
    check("'numb' -> neural",                 stats.detect_neural_symptoms("my foot went numb"), True)
    check("'tight lower back' -> not neural", stats.detect_neural_symptoms("tight lower back"), False)
    check("empty string -> not neural",       stats.detect_neural_symptoms(""), False)

    check("'bowel' -> urgent",                stats.detect_urgent_symptoms("bowel issues today"), True)
    check("'cauda equina' -> urgent",         stats.detect_urgent_symptoms("cauda equina symptoms"), True)
    check("'shooting' -> not urgent",         stats.detect_urgent_symptoms("shooting pain"), False)

    check("neural text -> auto_warning_level flag",   stats.auto_warning_level("shooting down my leg"), "flag")
    check("urgent text -> auto_warning_level flag",   stats.auto_warning_level("bladder control issues"), "flag")
    check("normal text -> auto_warning_level None",   stats.auto_warning_level("slightly tight today"), None)
    check("empty -> auto_warning_level None",         stats.auto_warning_level(""), None)


def test_stats_trend_slope():
    # Perfectly flat series -> slope ≈ 0
    check("flat series -> slope ~0", stats.trend_slope([5.0, 5.0, 5.0, 5.0, 5.0]), 0.0, tol=1e-4)

    # Perfectly linear increasing -> slope = 1.0
    check("linear +1/day -> slope ~1.0", stats.trend_slope([0, 1, 2, 3, 4, 5, 6]), 1.0, tol=1e-3)

    # Decreasing
    check("linear -1/day -> slope ~-1.0", stats.trend_slope([6, 5, 4, 3, 2, 1, 0]), -1.0, tol=1e-3)

    # Too few values
    check("< 3 values -> None", stats.trend_slope([5.0, 6.0]), None)
    check("empty -> None",      stats.trend_slope([]), None)

    # None values are filtered
    check("Nones filtered -> still computes", stats.trend_slope([None, 1, 2, 3, None, 5]),
          stats.trend_slope([1, 2, 3, 5]), tol=0.5)


def test_stats_recovery_direction():
    # Improving: pain and tightness both decreasing (negative slopes)
    improving = stats.recovery_direction([5, 4, 3, 2, 1, 0], [5, 4, 3, 2, 1, 0])
    check("decreasing pain+tightness -> improving", improving, "improving")

    # Degrading: both increasing
    degrading = stats.recovery_direction([0, 1, 2, 3, 4, 5], [0, 1, 2, 3, 4, 5])
    check("increasing pain+tightness -> degrading", degrading, "degrading")

    # Stable: flat
    stable = stats.recovery_direction([3, 3, 3, 3, 3, 3], [2, 2, 2, 2, 2, 2])
    check("flat -> stable", stable, "stable")

    # Insufficient
    insuff = stats.recovery_direction([3], [])
    check("< 3 values -> insufficient_data", insuff, "insufficient_data")


def test_stats_session_tonnage():
    check("3×10@20kg = 200 (one set)", stats.session_tonnage([{"reps_completed": 10, "weight_kg": 20.0}]), 200.0)
    check("multiple sets sum",
          stats.session_tonnage([
              {"reps_completed": 10, "weight_kg": 20.0},
              {"reps_completed": 8,  "weight_kg": 25.0},
              {"reps_completed": 6,  "weight_kg": 30.0},
          ]),
          10 * 20 + 8 * 25 + 6 * 30)  # 200 + 200 + 180 = 580
    check("empty -> 0.0", stats.session_tonnage([]), 0.0)
    check("None weight treated as 0", stats.session_tonnage([{"reps_completed": 10, "weight_kg": None}]), 0.0)
    check("None reps treated as 0",   stats.session_tonnage([{"reps_completed": None, "weight_kg": 20.0}]), 0.0)


def test_stats_lag_correlation():
    # Perfect negative correlation at lag 1: when au spikes, hrv drops next day
    random.seed(42)
    base = [60.0] * 20
    hrv_series = list(base)
    au_series = [0.0] * 20
    for i in [5, 10, 15]:
        au_series[i] = 300.0
        hrv_series[i + 1] = 40.0

    corr = stats.lag_correlation(hrv_series, au_series, [1])
    check("lag-1 correlation exists (not None)", corr[1] is not None, True)
    check("spike AU -> drop HRV next day -> negative correlation", corr[1] < 0, True)

    # Perfect positive correlation at lag 0
    same = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    corr_same = stats.lag_correlation(same, same, [0])
    check("lag-0 self-correlation = 1.0", corr_same[0], 1.0, tol=1e-6)

    # Too few values -> None
    corr_short = stats.lag_correlation([1, 2], [1, 2], [1])
    check("< 5 paired values -> None", corr_short[1], None)


def test_no_streamlit_import():
    tree = ast.parse(open(stats.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"
