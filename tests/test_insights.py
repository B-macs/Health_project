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


# directive_copy was removed on 2026-10-13: no view called it. The Engine
# Data panel speaks in Home's words (tests/test_home_and_training_last_gaps.py).


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


# ── the tightness timeline's scale (rebuild Phase 8) ─────────────────────────

def test_the_timeline_scale_is_the_check_in_scale_with_its_end_dates():
    from services import insights
    axis = insights.score_timeline_axis(["2026-10-01", "2026-10-09", "2026-10-20"])
    assert (axis["lo"], axis["hi"]) == (0.0, 10.0)
    assert axis["y_labels"] == ["10", "5", "0"]
    assert axis["x_labels"] == ["1 Oct", "20 Oct"]
    assert (axis["start"], axis["end"]) == ("2026-10-01", "2026-10-20")


def test_one_entry_has_one_date_and_none_has_no_scale():
    from services import insights
    assert insights.score_timeline_axis(["2026-10-20"])["x_labels"] == ["20 Oct"]
    assert insights.score_timeline_axis([]) is None


# ── the body areas he selected (rebuild Phase 8, the owner, 2026-10-20) ───────

def test_the_selected_areas_are_counted_once_per_check_in():
    import json
    from services import insights
    rows = [{"anatomical_locations": json.dumps(["Central Lower Back", "Glute Medius — Right"])},
            {"anatomical_locations": json.dumps(["Central Lower Back", "Central Lower Back"])},
            {"anatomical_locations": json.dumps([])},
            {"anatomical_locations": None}]
    assert insights.selected_area_frequency(rows) == {"Central Lower Back": 2, "Glute Medius — Right": 1}


def test_a_malformed_selection_is_skipped_never_guessed():
    from services import insights
    assert insights.selected_area_frequency([{"anatomical_locations": "not json"}]) == {}
