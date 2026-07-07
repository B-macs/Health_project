"""Tests for services/insights.py — pure logic extracted from views/insights.py."""

import ast
from datetime import date

from services import insights


def test_no_streamlit_import():
    tree = ast.parse(open(insights.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"


# ─── directive_copy ─────────────────────────────────────────────────────────

def test_directive_copy_green_uses_the_real_action_text():
    label, detail = insights.directive_copy(
        {"signal_color": "green", "action": "Train hard today.", "label": "GO"})
    assert label == "Train normally today."
    assert detail == "Train hard today."


def test_directive_copy_red_uses_fixed_clinical_copy():
    label, detail = insights.directive_copy(
        {"signal_color": "red", "action": "anything", "label": "REST"})
    assert "Rest day" in label
    assert "systemic fatigue" in detail


def test_directive_copy_yellow_and_orange_share_the_same_detail():
    _, yellow_detail = insights.directive_copy({"signal_color": "yellow", "action": "x", "label": "y"})
    _, orange_detail = insights.directive_copy({"signal_color": "orange", "action": "x", "label": "y"})
    assert yellow_detail == orange_detail


def test_directive_copy_unknown_signal_falls_back_to_rec_fields():
    label, detail = insights.directive_copy(
        {"signal_color": "purple", "action": "fallback action", "label": "fallback label"})
    assert label == "fallback label"
    assert detail == "fallback action"


# ─── metric_delta_str ───────────────────────────────────────────────────────

def test_metric_delta_str_positive():
    assert insights.metric_delta_str(5.2) == "▲ 5.2%"


def test_metric_delta_str_negative():
    assert insights.metric_delta_str(-3.1) == "▼ 3.1%"


def test_metric_delta_str_none():
    assert insights.metric_delta_str(None) == ""


def test_metric_delta_str_zero():
    assert insights.metric_delta_str(0) == ""


# ─── acwr_chart_data ────────────────────────────────────────────────────────

def test_acwr_chart_data_returns_28_dates_ending_today():
    data = insights.acwr_chart_data([0.0] * 28, today=date(2026, 7, 7))
    assert len(data["dates"]) == 28
    assert data["dates"][-1] == "2026-07-07"
    assert data["dates"][0] == "2026-06-10"


def test_acwr_chart_data_window_split_is_21_chronic_7_acute():
    data = insights.acwr_chart_data([0.0] * 28, today=date(2026, 7, 7))
    assert data["windows"].count("Chronic (28d)") == 21
    assert data["windows"].count("Acute (7d)") == 7
    assert data["windows"][-7:] == ["Acute (7d)"] * 7


# ─── body_region_frequency ──────────────────────────────────────────────────

def test_body_region_frequency_counts_across_rows():
    rows = [
        {"ai_body_parts": '["Glute — Right", "Hip Flexor"]'},
        {"ai_body_parts": '["Glute — Right"]'},
    ]
    freq = insights.body_region_frequency(rows)
    assert freq == {"Glute — Right": 2, "Hip Flexor": 1}


def test_body_region_frequency_skips_malformed_json():
    rows = [{"ai_body_parts": "not json"}, {"ai_body_parts": '["Hip Flexor"]'}]
    freq = insights.body_region_frequency(rows)
    assert freq == {"Hip Flexor": 1}


def test_body_region_frequency_empty_rows():
    assert insights.body_region_frequency([]) == {}


# ─── slope_direction_rows ───────────────────────────────────────────────────

def test_slope_direction_pain_negative_slope_is_improving():
    rows = insights.slope_direction_rows({"pain_slope": -0.1})
    assert rows[0]["Direction"] == "improving"


def test_slope_direction_pain_positive_slope_is_worsening():
    rows = insights.slope_direction_rows({"pain_slope": 0.1})
    assert rows[0]["Direction"] == "worsening"


def test_slope_direction_hrv_positive_slope_is_improving():
    rows = insights.slope_direction_rows({"hrv_slope": 0.2})
    assert rows[0]["Direction"] == "improving"


def test_slope_direction_hrv_negative_slope_is_dash_not_worsening():
    # Only pain/tightness ever show "worsening" -- everything else is
    # "improving" or "--", matching the original view's exact branching.
    rows = insights.slope_direction_rows({"hrv_slope": -0.2})
    assert rows[0]["Direction"] == "--"


def test_slope_direction_none_value_is_dash():
    rows = insights.slope_direction_rows({"pain_slope": None})
    assert rows[0]["Direction"] == "--"
    assert rows[0]["Slope / day"] == "--"


def test_slope_direction_variable_name_formatting():
    rows = insights.slope_direction_rows({"tightness_slope": -0.05})
    assert rows[0]["Variable"] == "Tightness"
