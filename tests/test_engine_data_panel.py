"""Insights › Engine Data, moved into services on 2026-10-19 (move INS-4).

The tab reads decision.engine_state for its panels and shows THE verdict Home
shows for its banner. What this pins:

  * fault F4: the tab used to build its own policy as load_policy(rec, {}),
    without the readiness signal Home passes, so on a day only readiness asked
    for less the two screens disagreed;
  * the card, drift and ACWR texts come out of services/insights.py, so the
    phone's API can return them;
  * the weekly volume series covers the right Mondays.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from services import insights, verdict, volume
from services import sessions as sess
from services.models import ExerciseEntry, SessionRecord

ROOT = Path(__file__).resolve().parent.parent
GREEN = {"signal_color": "green", "label": "GREEN — standard progressive overload",
         "action": "", "multiplier": 1.0}
LOW_READINESS = {"volume_factor": 0.85, "streak_label": "low",
                 "description": "Readiness has been low for 3 days"}


def test_a_day_only_readiness_reduces_reads_the_same_on_both_screens():
    """F4. The old panel's own policy said no change; Home's verdict, which
    the panel now shows, says reduced load."""
    assert sess.load_policy(GREEN, {})["banner_kind"] == ""                # the old panel
    shown = verdict.today_verdict(GREEN, LOW_READINESS)
    assert shown.reduced and shown.badge == verdict.BADGE_WORDS[shown.banner_kind]
    assert shown.badge == "REDUCED LOAD"


def test_the_panel_shows_the_verdict_home_shows():
    src = (ROOT / "views" / "insights.py").read_text(encoding="utf-8")
    assert "_verdict = today_mod.today_verdict()" in src
    assert "rec = today_mod.today_directive()" in src
    assert "load_policy(" not in src
    assert "decision.engine_state(" in src


def test_a_metric_card_says_value_comparison_and_change():
    card = insights.metric_card({"value": 41.0, "unit": "ms", "baseline_28d": 45.2,
                                 "delta_pct": -9.3, "signal": "yellow"})
    assert card == {"value": "41.0 ms", "comparison": "28d avg: 45.2 ms",
                    "change": "▼ 9.3%", "signal": "yellow"}
    assert insights.metric_card({})["value"] == "—"
    assert insights.metric_card({})["comparison"] == "No baseline"


def test_temperature_names_its_cut_points_instead_of_a_baseline():
    card = insights.metric_card({"value": 0.42, "unit": "°C", "signal": "yellow",
                                 "absolute_thresholds": {"red": 0.6, "yellow": 0.3}})
    assert card["value"] == "+0.42 °C"
    assert card["comparison"] == "vs personal norm · red ≥ +0.60"
    assert card["change"] == "Elevated — re-check tomorrow"


def test_the_missing_device_is_named_for_its_own_metric_only():
    missing = ("hrv_ms:garmin", "sleep_duration_hours:oura")
    assert insights.missing_source(missing, "hrv_ms") == "garmin"
    assert insights.missing_source(missing, "resting_heart_rate") is None
    assert insights.missing_source(None, "hrv_ms") is None


def test_drift_lines_name_each_metric_and_flag_an_adverse_move():
    drift = {"prior_days": 21, "metrics": {
        "hrv_ms": {"recent": 40.1, "prior": 46.0, "delta_pct": -12.8, "adverse": True}}}
    [line] = insights.drift_lines(drift, {"hrv_ms": {"label": "HRV"}})
    assert line.startswith("**HRV** — last ")
    assert "40.1 vs prior 21 46.0 (-12.8%)" in line and line.endswith("⚠ adverse")


def test_the_acwr_panel_says_one_thing_in_order():
    assert insights.acwr_status({"hard_locked": True, "exceeds_ceiling": True})[0] == "error"
    kind, text = insights.acwr_status({"hard_locked": False, "baseline_established": False,
                                       "in_stage_days": 6})
    assert kind == "info" and "6/" in text
    assert insights.acwr_status({"hard_locked": False, "exceeds_ceiling": True})[0] == "warning"
    assert insights.acwr_status({"hard_locked": False}) is None
    assert insights.acwr_chronic_label({"chronic_basis": "stage"})[0] == "Chronic avg"
    assert insights.acwr_chronic_label({})[0] == "Chronic 28d avg"


def test_the_weekly_volume_covers_eight_mondays_ending_this_week():
    session = SessionRecord(session_date="2026-10-20", session_duration_minutes=50,
                            session_rpe=6, session_au=300.0,
                            exercises=[ExerciseEntry(name="Goblet Squat", movement_type="Squat",
                                                     total_volume_kg=675.0)])
    series = volume.weekly_volume_series([session], date(2026, 10, 22))
    assert [week for week, _kg in series][0] == date(2026, 8, 31)
    assert series[-1] == (date(2026, 10, 19), 675.0)
    assert len(series) == 8 and all(kg == 0.0 for _week, kg in series[:-1])
