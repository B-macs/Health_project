"""services/sleep_screen.py and the Readiness drill-down helpers in
services/home.py: what the drill-downs show, moved out of app.py on
2026-10-19 (moves HOME-7 to HOME-17) so the phone's API returns the same.

tests/test_sleep_screen_is_all_or_nothing.py renders app.py's own sleep
functions over the same rules; this pins the rules themselves, and fault F5:
on a fused night the wake-time stepper offered − and + that changed nothing.
"""

from __future__ import annotations

from datetime import date, timedelta

from services import dashboard as dash
from services import home, sleep_screen as ss

NIGHT = date(2026, 10, 18)
WATCH_ONLY_ROW = {"source": "garmin_only", "master_hypnogram": "2223",
                  "master_deep_minutes": 60, "master_light_minutes": 240,
                  "master_rem_minutes": 100, "master_awake_minutes": 20, "minutes": 420}


# ─── which panels a night shows (HOME-8) ─────────────────────────────────────

def test_the_score_decides_for_the_whole_screen():
    detail = {"bedtime_start": "x"}
    assert ss.screen_mode(True, {}, detail, True) == ss.SCORED
    assert ss.screen_mode(False, {}, detail, True) == ss.BLANK      # a detail, no score
    assert ss.screen_mode(False, {}, None, True) == ss.BLANK


def test_a_night_only_the_watch_recorded_is_the_one_unscored_night_drawn():
    assert ss.screen_mode(False, WATCH_ONLY_ROW, None, True) == ss.WATCH_ONLY
    assert ss.screen_mode(False, {**WATCH_ONLY_ROW, "master_hypnogram": ""}, None,
                          True) == ss.BLANK


def test_a_scored_night_whose_detail_failed_says_so():
    assert ss.screen_mode(True, {}, None, False) == ss.DETAIL_FAILED
    assert ss.screen_mode(True, {}, None, True) == ss.NO_DETAIL


def test_the_watch_only_split_is_of_time_asleep():
    rows = {r["stage"]: r for r in ss.watch_only_stages(WATCH_ONLY_ROW)}
    assert [r["stage"] for r in ss.watch_only_stages(WATCH_ONLY_ROW)] == [
        "awake", "rem", "light", "deep"]
    assert rows["awake"]["pct"] is None and rows["awake"]["minutes"] == 20
    assert (rows["deep"]["pct"], rows["light"]["pct"], rows["rem"]["pct"]) == (15, 60, 25)


# ─── where the strip and the captions come from (HOME-10 to HOME-13) ────────

def test_the_strip_names_what_produced_it():
    fused = {"source": "fused", "master_hypnogram": "1122", "phantom_wake_minutes": 12}
    src = ss.strip_source(fused, {"hypnogram_30sec": "4444"}, True)
    assert (src["codes"], src["title"], src["note"]) == ("1122", "Fused (Oura + Garmin)", "phantom")
    assert ss.strip_source(WATCH_ONLY_ROW, None, True)["note"] == "watch"
    oura = ss.strip_source({}, {"hypnogram_30sec": "4444"}, True)
    assert (oura["codes"], oura["title"], oura["note"]) == ("4444", "Oura", "plain")
    assert ss.strip_source({}, {"hypnogram_30sec": "4444"}, False)["title"] == (
        "Oura (fusion unavailable)")


def test_the_strip_window_falls_back_to_the_watch():
    detail = {"bedtime_start": "2026-10-17T23:00:00+02:00",
              "bedtime_end": "2026-10-18T07:00:00+02:00"}
    assert ss.strip_window(detail, {}, dash.minutes_between) == (
        "2026-10-17T23:00:00+02:00", 480.0)
    start, minutes = ss.strip_window(None, {**WATCH_ONLY_ROW, "window_start_utc": "w"},
                                     dash.minutes_between)
    assert (start, minutes) == ("w", 420.0)


def test_the_movement_caption_names_its_source_and_the_shifts():
    assert ss.movement_caption({}) is None
    cap = ss.movement_caption({"master_movement": "1112", "movement_source": "fused",
                               "movement_position_shifts": 1})
    assert cap["title"] == "Fused (Oura + Garmin)"
    assert cap["details"] == ["ring resolves small motion, watch confirms whole-body",
                              "1 position shift"]
    assert ss.movement_caption({"master_movement": "1", "movement_position_shifts": 3})[
        "details"] == ["3 position shifts"]


def test_the_overnight_axis_falls_back_to_the_bedtime_window():
    assert ss.overnight_axis([(0.0, "23:10")], {}, dash.format_clock) == [(0.0, "23:10")]
    axis = ss.overnight_axis([], {"bedtime_start": "2026-10-17T23:00:00+02:00",
                                  "bedtime_end": "2026-10-18T07:00:00+02:00"},
                             dash.format_clock)
    assert [x for x, _label in axis] == [0.0, 1.0] and all(label for _x, label in axis)
    assert ss.overnight_axis([], {}, dash.format_clock) == []
    assert [p[1] for p in ss.OVERNIGHT_PANELS] == ["hr_series", "hrv_series"]


# ─── the wake-time correction (HOME-16, HOME-17, F5) ────────────────────────

def test_a_fused_night_offers_no_stepper_because_a_manual_value_would_change_nothing():
    """F5. The fusion figure wins on a fused night
    (sleep_fusion.effective_wake_adjustments)."""
    control = ss.wake_control(NIGHT, {NIGHT.isoformat(): 14.0}, {NIGHT.isoformat(): ss.FUSION})
    assert not control["editable"] and control["source"] == ss.FUSION
    assert "would change nothing" in control["caption"] and "Oura wake" in control["caption"]


def test_a_manual_correction_stays_editable_and_credits_the_oura_pattern():
    control = ss.wake_control(NIGHT, {NIGHT.isoformat(): 10.0}, {NIGHT.isoformat(): ss.MANUAL})
    assert control["editable"] and control["source"] == ss.MANUAL
    assert control["caption"].startswith("Wake time corrected −10 min")
    none = ss.wake_control(NIGHT, {}, {})
    assert none == {"minutes": 0.0, "source": "", "editable": True, "caption": ""}


def test_the_drill_down_marks_adjusted_nights():
    window = [NIGHT - timedelta(days=n) for n in range(30)]
    adjustments = {NIGHT.isoformat(): 10.0, (NIGHT - timedelta(days=3)).isoformat(): 5.0,
                   (NIGHT - timedelta(days=40)).isoformat(): 8.0}
    view = ss.wake_display(NIGHT, adjustments, window)
    assert view == {"adjusted": True, "nights_adjusted": 2}


def test_the_sleep_contributors_caption_names_the_correction():
    assert ss.contributors_caption("6 of 7 measured.", {}) == "6 of 7 measured."
    assert ss.contributors_caption("", {"wake_adjustment_minutes": 12}) == (
        "Total sleep and Efficiency include a 12 min wake-time correction, "
        "and so do the figures below.")


# ─── the Readiness drill-down (HOME-14, HOME-15) ────────────────────────────

def test_the_readiness_key_metrics_sign_the_temperature_and_dash_the_missing():
    cells = home.readiness_key_metrics(
        {"resting_heart_rate": 53.6, "hrv_ms": 41.2, "oura_temperature_deviation": -0.4},
        {"average_breath": 14.27})
    assert [c["value"] for c in cells] == ["54 bpm", "41 ms", "-0.40 °C", "14.3 /min"]
    assert [c["value"] for c in home.readiness_key_metrics({}, None)] == ["—"] * 4
    assert home.readiness_key_metrics({"oura_temperature_deviation": 0.4}, {})[2][
        "value"] == "+0.40 °C"


def test_the_readiness_caption_joins_only_what_has_something_to_say():
    breakdown = {"score": 58.0, "missing": [], "available_weight": 1.0, "alcohol_units": None,
                 "components": []}
    caption = home.readiness_contributors_caption(66.0, breakdown)
    assert caption and "  " not in caption
    assert home.readiness_contributors_caption(None, {"missing": [], "available_weight": 1.0,
                                                      "alcohol_units": None,
                                                      "components": []}) == ""


def test_the_drawing_and_the_api_name_the_stages_from_one_table():
    """The stage and movement names live in services/sleep_screen.py: the
    Streamlit strips draw under them and the API's tap details use them, so
    the two can never name a stage differently. styles.py is read as text
    (it imports Streamlit)."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "styles.py").read_text(encoding="utf-8")
    assert "_sleep_screen.STAGE_NAMES[code]" in src
    assert "MOVEMENT_LABELS: dict[str, str] = dict(_sleep_screen.MOVEMENT_NAMES)" in src
    assert ss.STAGE_NAMES == {"1": "Deep", "2": "Light", "3": "REM", "4": "Awake", "0": "No data"}
    assert ss.MOVEMENT_NAMES == {"1": "No motion", "2": "Restless", "3": "Tossing", "4": "Active"}
