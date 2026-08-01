"""Tests for services/dashboard.py — pure Home-page computation extracted
from app.py's previously undocumented, unparameterized dashboard-math cluster."""

import ast
from datetime import date, timedelta

from services import dashboard
from services import hr_load


def test_no_streamlit_import():
    tree = ast.parse(open(dashboard.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"


# ─── au_to_strain_or_none ───────────────────────────────────────────────────

def test_au_to_strain_or_none_zero_au_is_none():
    assert dashboard.au_to_strain_or_none(0, stage=1) is None


def test_au_to_strain_or_none_negative_au_is_none():
    assert dashboard.au_to_strain_or_none(-5, stage=1) is None


def test_au_to_strain_or_none_none_input_is_none():
    assert dashboard.au_to_strain_or_none(None, stage=1) is None


def test_au_to_strain_or_none_positive_au_returns_a_value():
    assert dashboard.au_to_strain_or_none(200, stage=1) is not None


# ─── fill_7day ───────────────────────────────────────────────────────────────

def test_fill_7day_returns_7_values_in_date_order():
    rows = [{"date": "2026-07-01", "hrv_ms": 40}, {"date": "2026-07-07", "hrv_ms": 45}]
    out = dashboard.fill_7day(rows, "hrv_ms", date(2026, 7, 7))
    assert len(out) == 7
    assert out[0] == 40  # 6 days before selected_date
    assert out[-1] == 45  # selected_date itself


def test_fill_7day_missing_dates_are_none():
    out = dashboard.fill_7day([], "hrv_ms", date(2026, 7, 7))
    assert out == [None] * 7


# ─── rolling_prior_strain ────────────────────────────────────────────────────

def test_rolling_prior_strain_excludes_today():
    # Only "today" has AU logged -- the prior-7-days window (today-1..today-7)
    # should see nothing, so no rolling strain.
    au_rows = [{"date": "2026-07-07", "total_au": 500.0}]
    assert dashboard.rolling_prior_strain(au_rows, stage=1, today=date(2026, 7, 7)) is None


def test_rolling_prior_strain_averages_across_7_prior_days_including_rest_days():
    au_rows = [{"date": "2026-07-06", "total_au": 700.0}]  # 1 day with load, 6 rest days
    result = dashboard.rolling_prior_strain(au_rows, stage=1, today=date(2026, 7, 7))
    assert result is not None


# ─── display_strain ──────────────────────────────────────────────────────────

def test_display_strain_prefers_todays_actual_strain():
    value, is_rolling = dashboard.display_strain(today_strain=8.0, rolling_strain=3.0)
    assert value == 8.0
    assert is_rolling is False


def test_display_strain_falls_back_to_rolling_when_no_session_today():
    value, is_rolling = dashboard.display_strain(today_strain=None, rolling_strain=3.0)
    assert value == 3.0
    assert is_rolling is True


def test_display_strain_both_none():
    value, is_rolling = dashboard.display_strain(None, None)
    assert value is None
    assert is_rolling is False


# ─── apply_step_modifier ─────────────────────────────────────────────────────

def test_apply_step_modifier_none_strain_stays_none():
    assert dashboard.apply_step_modifier(None, [], today=date(2026, 7, 7)) is None


def test_apply_step_modifier_no_step_data_returns_unmodified_strain():
    assert dashboard.apply_step_modifier(10.0, [], today=date(2026, 7, 7)) == 10.0


def test_apply_step_modifier_clamps_to_0_21_range():
    # Extreme high yesterday steps vs. a low baseline should push toward the
    # ceiling, never past 21.
    bio_rows = [{"date": "2026-07-06", "steps": 40000}] + [
        {"date": (date(2026, 7, 5) - __import__("datetime").timedelta(days=d)).isoformat(), "steps": 1000}
        for d in range(7)
    ]
    result = dashboard.apply_step_modifier(20.5, bio_rows, today=date(2026, 7, 7))
    assert 0.0 <= result <= 21.0


# ─── sleep_percent ───────────────────────────────────────────────────────────

def test_sleep_percent_computes_rounded_percentage():
    assert dashboard.sleep_percent(7.5, 8.0) == 94


def test_sleep_percent_none_hours_is_none():
    assert dashboard.sleep_percent(None, 8.0) is None


def test_sleep_percent_zero_hours_is_none():
    assert dashboard.sleep_percent(0, 8.0) is None


# ─── step_wake_time_adjustment ───────────────────────────────────────────────
# The Sleep card drill-down's +/- control (CLAUDE.md rule 4's narrow
# manual-entry exception) — mirrors services.sessions' step_reps/
# step_weight_kg steppers.

def test_step_wake_time_adjustment_increments_by_default_step():
    assert dashboard.step_wake_time_adjustment(0.0, +1) == 5.0


def test_step_wake_time_adjustment_decrements_by_default_step():
    assert dashboard.step_wake_time_adjustment(10.0, -1) == 5.0


def test_step_wake_time_adjustment_floored_at_zero():
    assert dashboard.step_wake_time_adjustment(0.0, -1) == 0.0


def test_step_wake_time_adjustment_capped_at_ceiling():
    assert dashboard.step_wake_time_adjustment(120.0, +1) == 120.0


# ─── readiness_meta / strain_meta / sleep_meta ──────────────────────────────

def test_readiness_meta_optimal_tier():
    color, val, lbl, hdr, desc, extra = dashboard.readiness_meta(90)
    assert lbl == "Optimal"
    assert val == "90"


def test_readiness_meta_rest_tier():
    _, _, lbl, _, _, _ = dashboard.readiness_meta(30)
    assert lbl == "Rest"


def test_readiness_meta_not_computed_sentinel():
    _, val, lbl, _, _, _ = dashboard.readiness_meta("NOT_COMPUTED")
    assert lbl == "No Readings"
    assert val == "--"


def test_readiness_meta_boundary_85_is_optimal_not_good():
    _, _, lbl, _, _, _ = dashboard.readiness_meta(85)
    assert lbl == "Optimal"


def test_strain_meta_none_score():
    _, val, lbl, _, _ = dashboard.strain_meta(None)
    assert lbl == "No Readings"
    assert val == "--"


def test_strain_meta_light_tier():
    _, _, lbl, _, _ = dashboard.strain_meta(3.0)
    assert lbl == "Light"


def test_strain_meta_rolling_vs_non_rolling_have_different_copy():
    _, _, lbl_r, hdr_r, desc_r = dashboard.strain_meta(3.0, is_rolling=True)
    _, _, lbl_nr, hdr_nr, desc_nr = dashboard.strain_meta(3.0, is_rolling=False)
    assert lbl_r == lbl_nr == "Light"
    assert hdr_r != hdr_nr


def test_sleep_meta_none_score():
    _, val, lbl, _, _ = dashboard.sleep_meta(None, 8.0, None)
    assert lbl == "No Readings"
    assert val == "--"


def test_sleep_meta_optimal_tier_with_baseline_window():
    _, val, lbl, _, desc = dashboard.sleep_meta(90, 7.8, 28)
    assert lbl == "Optimal"
    assert val == "90"
    assert "28d avg" in desc


def test_sleep_meta_no_baseline_window_uses_target_copy():
    _, _, _, _, desc = dashboard.sleep_meta(90, 8.0, None)
    assert "target" in desc


# ─── compute_daily_metrics_snapshot ─────────────────────────────────────────

def test_snapshot_returns_all_keys_with_minimal_data():
    snap = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows=[], au_rows=[], stage=1,
    )
    assert set(snap) == {
        "readiness_score", "sleep_pct", "sleep_score", "strain", "strain_is_rolling",
        # Added with heart-rate-derived strain — strain_source makes an RPE
        # fallback visible instead of silent (services.hr_load.SOURCE_*).
        "strain_source", "strain_source_label", "strain_rpe_only",
        "strain_hr_only", "hr_detail",
    }


def test_snapshot_strain_falls_back_to_rpe_without_hr_rows():
    """The backup path: no Garmin activity for the day means the strain value
    must be exactly what it was before HR load existed, and must SAY so."""
    au = [{"date": "2026-07-20", "total_au": 360.0}]
    baseline = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows=[], au_rows=au, stage=2, hr_rows=None,
    )
    assert baseline["strain"] == dashboard.au_to_strain_or_none(360.0, 2)
    assert baseline["strain_source"] == hr_load.SOURCE_RPE
    assert "RPE only" in baseline["strain_source_label"]


def test_snapshot_strain_uses_hr_when_the_day_matched_an_activity():
    au = [{"date": "2026-07-20", "total_au": 360.0}]
    hr = [{"date": "2026-07-20", "hr_strain": 19.0}]
    snap = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows=[], au_rows=au, stage=2, hr_rows=hr,
    )
    rpe_only = dashboard.au_to_strain_or_none(360.0, 2)
    assert snap["strain_source"] == hr_load.SOURCE_BLENDED
    assert snap["strain_hr_only"] == 19.0
    assert snap["strain_rpe_only"] == rpe_only
    # Weighted toward HR, so it sits above the RPE-only figure.
    assert rpe_only < snap["strain"] <= 19.0


def test_snapshot_hr_row_for_a_different_date_is_ignored():
    au = [{"date": "2026-07-20", "total_au": 360.0}]
    hr = [{"date": "2026-07-19", "hr_strain": 19.0}]
    snap = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows=[], au_rows=au, stage=2, hr_rows=hr,
    )
    assert snap["strain_source"] == hr_load.SOURCE_RPE
    assert snap["strain_hr_only"] is None


def test_snapshot_rolling_strain_day_reports_no_source():
    """A day with no session shows the trailing-average stand-in, which isn't
    attributable to either method."""
    au = [{"date": "2026-07-18", "total_au": 300.0}]
    snap = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows=[], au_rows=au, stage=2,
        rolling_reference_date=date(2026, 7, 20),
    )
    assert snap["strain_is_rolling"] is True
    assert snap["strain_source"] == hr_load.SOURCE_NONE


def test_snapshot_no_data_everything_none():
    snap = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows=[], au_rows=[], stage=1,
    )
    assert snap["readiness_score"] is None
    assert snap["sleep_pct"] is None
    assert snap["sleep_score"] is None
    assert snap["strain"] is None


def test_snapshot_sleep_pct_uses_sleep_hours_for_the_given_date():
    bio_rows = [{"date": "2026-07-20", "sleep_duration_hours": 6.0}]
    snap = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows, au_rows=[], stage=1,
    )
    # no computable baseline from a single row -> falls back to the 8h default
    assert snap["sleep_pct"] == 75


def test_snapshot_precomputed_sleep_base_hours_is_used_directly():
    bio_rows = [{"date": "2026-07-20", "sleep_duration_hours": 6.0}]
    snap = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows, au_rows=[], stage=1, sleep_base_hours=6.0,
    )
    assert snap["sleep_pct"] == 100


def test_snapshot_strain_uses_todays_au_when_logged_that_day():
    au_rows = [{"date": "2026-07-20", "total_au": 300.0}]
    snap = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows=[], au_rows=au_rows, stage=2,
    )
    assert snap["strain"] is not None
    assert snap["strain_is_rolling"] is False


def test_snapshot_strain_falls_back_to_rolling_when_no_session_that_day():
    au_rows = [{"date": "2026-07-13", "total_au": 700.0}]  # 7 days before, none on the target day
    snap = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows=[], au_rows=au_rows, stage=1,
    )
    assert snap["strain_is_rolling"] is True


def test_snapshot_rolling_reference_date_defaults_to_the_scored_date():
    # Rolling strain looks at the 7 days BEFORE the reference date. With no
    # default override, that's `d` itself -- so AU logged the day before `d`
    # counts toward the rolling fallback.
    au_rows = [{"date": "2026-07-19", "total_au": 700.0}]
    snap = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows=[], au_rows=au_rows, stage=1,
    )
    assert snap["strain_is_rolling"] is True
    assert snap["strain"] is not None


def test_snapshot_rolling_reference_date_override_shifts_the_rolling_window():
    # Same AU data, but the rolling window is now anchored to a date where
    # the prior-7-days window no longer includes 07-19 -> no rolling fallback.
    au_rows = [{"date": "2026-07-19", "total_au": 700.0}]
    snap = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows=[], au_rows=au_rows, stage=1,
        rolling_reference_date=date(2026, 8, 1),
    )
    assert snap["strain"] is None


def test_snapshot_wake_time_adjustments_defaults_to_none_and_is_a_passthrough():
    # None is the default -- must reproduce the exact prior sleep_score
    # behavior when the caller doesn't pass this at all.
    bio_rows = [{"date": f"2026-06-{i+1:02d}", "sleep_duration_hours": 8.0} for i in range(10)] + [
        {"date": "2026-07-20", "sleep_duration_hours": 6.0,
         "oura_sleep_total_seconds": 21600.0, "oura_sleep_awake_seconds": 1800.0},
    ]
    snap_default = dashboard.compute_daily_metrics_snapshot(date(2026, 7, 20), bio_rows, au_rows=[], stage=1)
    snap_explicit_none = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows, au_rows=[], stage=1, wake_time_adjustments=None,
    )
    assert snap_default["sleep_score"] == snap_explicit_none["sleep_score"] == 77.8


def test_snapshot_wake_time_adjustments_raises_the_sleep_score():
    bio_rows = [{"date": f"2026-06-{i+1:02d}", "sleep_duration_hours": 8.0} for i in range(10)] + [
        {"date": "2026-07-20", "sleep_duration_hours": 6.0,
         "oura_sleep_total_seconds": 21600.0, "oura_sleep_awake_seconds": 1800.0},
    ]
    snap = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows, au_rows=[], stage=1,
        wake_time_adjustments={"2026-07-20": 30},
    )
    assert snap["sleep_score"] == 84.3


# ─── sleep_fusion_shadow_report (2026-07-31) ────────────────────────────────
#  The fused hypnogram is deliberately kept out of the engine. This function
#  quantifies what wiring it in would do, so that decision can be revisited
#  with evidence rather than re-argued.


def _bio_rows(n: int, sleep: float = 7.0, hrv: float = 45.0, rhr: float = 55.0,
              start: str = "2026-06-01") -> list[dict]:
    d0 = date.fromisoformat(start)
    return [
        {"date": (d0 + timedelta(days=i)).isoformat(), "hrv_ms": hrv,
         "resting_heart_rate": rhr, "sleep_duration_hours": sleep, "steps": 8000}
        for i in range(n)
    ]


def test_shadow_report_reports_nothing_when_no_night_is_fused():
    report = dashboard.sleep_fusion_shadow_report(_bio_rows(30), {})
    assert report["nights_compared"] == 0
    assert report["traffic_light_would_flip"] is False


def test_shadow_report_counts_only_nights_that_actually_have_a_fused_value():
    rows = _bio_rows(30)
    fused = {rows[-1]["date"]: 8.5, rows[-2]["date"]: 8.2}
    report = dashboard.sleep_fusion_shadow_report(rows, fused)
    assert report["nights_compared"] == 2


def test_shadow_report_leaves_unfused_rows_untouched_rather_than_zeroing_them():
    """An un-backfilled night must contribute nothing, not a false "no
    change" produced by substituting a missing value."""
    rows = _bio_rows(30, sleep=7.0)
    report = dashboard.sleep_fusion_shadow_report(rows, {rows[-1]["date"]: 9.0})
    # Only one night differs, so the 28-day traffic-light mean barely moves.
    assert report["traffic_light_now"] == report["traffic_light_fused"]


def test_shadow_report_shows_sleep_debt_falling_when_fused_sleep_is_higher():
    """The direction that matters: more sleep means less debt, which makes
    scheduling.should_shift_session's rest trigger LESS likely to fire.

    Debt is measured against the personal rolling baseline, so it only exists
    when recent nights are short RELATIVE to history — hence the long 8h
    history followed by a run of 5h nights."""
    rows = _bio_rows(30, sleep=8.0, start="2026-06-01")
    short = _bio_rows(7, sleep=5.0, start="2026-07-01")
    rows = rows + short
    fused = {r["date"]: 8.0 for r in short}
    report = dashboard.sleep_fusion_shadow_report(
        rows, fused, today=date.fromisoformat(short[-1]["date"]))
    assert report["sleep_debt_now"] > 0
    assert report["sleep_debt_fused"] < report["sleep_debt_now"]


def test_shadow_report_never_mutates_the_rows_it_was_given():
    """It is a read-only what-if; leaking a fused value into the caller's rows
    would silently wire fusion into the engine by the back door."""
    rows = _bio_rows(30, sleep=6.0)
    before = [dict(r) for r in rows]
    dashboard.sleep_fusion_shadow_report(rows, {r["date"]: 9.0 for r in rows})
    assert rows == before


def test_shadow_report_is_deterministic_for_the_same_inputs():
    rows = _bio_rows(30, sleep=6.5)
    fused = {r["date"]: 8.0 for r in rows}
    assert (dashboard.sleep_fusion_shadow_report(rows, fused)
            == dashboard.sleep_fusion_shadow_report(rows, fused))


def test_partial_fusion_coverage_can_make_the_traffic_light_stricter_not_looser():
    """The counterintuitive result the real shadow report surfaced
    (2026-07-31: green -> yellow, sleep debt 8.04h -> 8.47h).

    traffic_light scores a day against a rolling mean built from the same
    rows. Raising sleep only on the nights that HAVE Garmin data also raises
    that mean, so the uncovered nights look worse by comparison. Partial
    coverage is therefore not "a bit of the full effect" — it is a mixture of
    two measurements in one window, which is why the engine wiring is
    deferred rather than phased in."""
    history = _bio_rows(28, sleep=7.0, start="2026-06-01")
    recent = _bio_rows(4, sleep=7.0, start="2026-06-29")
    rows = history + recent
    # Only the older half gets a fused (higher) value — exactly the partial
    # coverage a May-2026-onward Garmin backfill produces.
    fused = {r["date"]: 9.5 for r in history}
    report = dashboard.sleep_fusion_shadow_report(rows, fused)
    assert report["nights_compared"] == len(history)
    # The uncovered recent nights are now below a raised mean.
    assert report["traffic_light_fused"] is not None


# ─── Sleep drill-down formatting (2026-07-31) ───────────────────────────────

def _breakdown(**overrides):
    """A fully-scored breakdown shaped like sleep_score.sleep_score_breakdown."""
    base = {
        "score": 80.0, "available_weight": 1.0, "missing": [],
        "wake_adjustment_minutes": 0.0, "total_seconds": 21540.0,
        "contributors": [
            {"key": "total_sleep", "label": "Total sleep", "score": 74.0, "weight": 0.25,
             "effective_weight": 0.25, "contribution": 18.5, "raw": 5.98,
             "reference": 7.45, "reference_window": 28},
            {"key": "efficiency", "label": "Efficiency", "score": 74.0, "weight": 0.20,
             "effective_weight": 0.20, "contribution": 14.8, "raw": 74.0,
             "reference": None, "reference_window": 0},
            {"key": "restfulness", "label": "Restfulness", "score": 35.0, "weight": 0.10,
             "effective_weight": 0.10, "contribution": 3.5, "raw": 8.5,
             "reference": None, "reference_window": 0},
            {"key": "rem", "label": "REM sleep", "score": 100.0, "weight": 0.15,
             "effective_weight": 0.15, "contribution": 15.0, "raw": 23.4,
             "reference": None, "reference_window": 0},
            {"key": "deep", "label": "Deep sleep", "score": 90.0, "weight": 0.15,
             "effective_weight": 0.15, "contribution": 13.5, "raw": 13.6,
             "reference": None, "reference_window": 0},
            {"key": "latency", "label": "Latency", "score": 100.0, "weight": 0.10,
             "effective_weight": 0.10, "contribution": 10.0, "raw": 12.0,
             "reference": None, "reference_window": 0},
            {"key": "timing", "label": "Timing", "score": 100.0, "weight": 0.05,
             "effective_weight": 0.05, "contribution": 5.0, "raw": 18.0,
             "reference": 660.0, "reference_window": 28},
        ],
    }
    base.update(overrides)
    return base


def test_durations_render_as_hours_and_minutes_because_5_98_is_not_readable():
    assert dashboard.format_duration(21540) == "5h 59m"
    assert dashboard.format_hours(5.98) == "5h 59m"


def test_durations_keep_the_hour_even_at_zero_so_a_column_stays_comparable():
    assert dashboard.format_duration(2940) == "0h 49m"


def test_sleep_tier_uses_the_same_thresholds_as_sleep_meta():
    """One colour scale for the card, the tier label and every contributor
    bar — a coral bar and a coral tier must mean the same thing."""
    for score in (92, 78, 60, 30):
        colour, _ = dashboard.sleep_tier(score)
        assert colour == dashboard.sleep_meta(score, 8.0, 28)[0]


def test_an_unscored_contributor_gets_the_dim_colour_not_a_bad_one():
    """Grey reads as "no reading"; coral would read as "bad night"."""
    colour, label = dashboard.sleep_tier(None)
    assert colour == "#4A5568"
    assert label == "not scored"


def test_breakdown_rows_keep_all_seven_in_the_breakdowns_own_order():
    rows = dashboard.sleep_breakdown_rows(_breakdown())
    assert [r["key"] for r in rows] == [
        "total_sleep", "efficiency", "restfulness", "rem", "deep", "latency", "timing"]


def test_rem_and_deep_show_duration_and_percentage_the_way_oura_does():
    rows = {r["key"]: r for r in dashboard.sleep_breakdown_rows(_breakdown())}
    assert rows["rem"]["value_display"] == "1h 24m, 23 %"
    assert rows["deep"]["value_display"] == "0h 49m, 14 %"   # 21540s x 13.6%


def test_rem_falls_back_to_percentage_alone_when_total_sleep_is_unknown():
    rows = {r["key"]: r for r in dashboard.sleep_breakdown_rows(_breakdown(total_seconds=None))}
    assert rows["rem"]["value_display"] == "23 %"


def test_restfulness_is_qualitative_because_its_unit_is_unverified():
    """services/sleep_score.py flags restless_periods' unit as a guess.
    Printing "8.5 / h" would state a fact the codebase says it can't stand
    behind."""
    rows = {r["key"]: r for r in dashboard.sleep_breakdown_rows(_breakdown())}
    assert rows["restfulness"]["value_display"] == "Poor"
    assert "8.5" not in rows["restfulness"]["value_display"]


def test_timing_reads_as_optimal_when_bedtime_is_close_to_your_usual():
    rows = {r["key"]: r for r in dashboard.sleep_breakdown_rows(_breakdown())}
    assert rows["timing"]["value_display"] == "Optimal"


def test_timing_names_the_deviation_once_it_stops_being_optimal():
    b = _breakdown()
    b["contributors"][6] = {**b["contributors"][6], "raw": 95.0, "score": 56.0}
    rows = {r["key"]: r for r in dashboard.sleep_breakdown_rows(b)}
    assert rows["timing"]["value_display"] == "95m off usual"


def test_a_missing_contributor_reads_not_scored_rather_than_zero():
    """Zero would render as a maximally bad night; the truth is no reading."""
    b = _breakdown(missing=["efficiency"])
    b["contributors"][1] = {**b["contributors"][1], "score": None, "raw": None,
                            "effective_weight": 0.0, "contribution": None}
    rows = {r["key"]: r for r in dashboard.sleep_breakdown_rows(b)}
    assert rows["efficiency"]["value_display"] == "not scored"
    assert rows["efficiency"]["scored"] is False
    assert rows["efficiency"]["bar_pct"] == 0.0


def test_the_coverage_caption_is_silent_when_every_contributor_scored():
    """A caption that always shows is a caption nobody reads."""
    assert dashboard.sleep_coverage_caption(_breakdown()) == ""


def test_the_coverage_caption_names_how_much_of_the_score_was_measured():
    caption = dashboard.sleep_coverage_caption(_breakdown(missing=["efficiency", "rem"]))
    assert "5 of 7" in caption
    assert "renormalised" in caption


# ─── overnight_series — the HR/HRV chart feed ───────────────────────────────

def test_overnight_series_preserves_gaps_in_values_but_excludes_them_from_stats():
    """Oura pads the start of a night with nulls. The chart must break its
    line across them, but averaging a gap as zero would drag the reported mean
    down by an amount that varies with how long the pad happened to be."""
    s = dashboard.overnight_series(
        {"interval": 300.0, "items": [None, None, 60, 58, 62], "timestamp": "x"})
    assert s["values"] == [None, None, 60, 58, 62]
    assert s["count"] == 3
    assert s["low"] == 58 and s["high"] == 62
    assert s["average"] == 60.0


def test_overnight_series_downsamples_by_striding_not_averaging():
    """A mean would smooth away the dips and excursions that are the entire
    reason to plot the night."""
    items = list(range(1000))
    s = dashboard.overnight_series({"items": items}, max_points=50)
    assert len(s["values"]) == 50
    assert s["high"] == max(s["values"])          # a real sample, not a mean
    assert all(v in items for v in s["values"])


def test_overnight_series_reports_count_zero_rather_than_raising_on_junk():
    """A malformed cell must cost one panel, not the page."""
    for junk in (None, {}, {"items": []}, {"items": [None, None]}, "not-a-dict", 42):
        assert dashboard.overnight_series(junk)["count"] == 0


def test_overnight_series_of_an_all_null_night_still_returns_its_values():
    s = dashboard.overnight_series({"items": [None, None, None]})
    assert s["count"] == 0
    assert s["average"] is None
    assert len(s["values"]) == 3


def test_format_clock_offset_derives_an_axis_end_from_a_duration():
    """garmin_only nights have no Oura bedtime_end to label the axis with."""
    assert dashboard.format_clock_offset("2026-07-27T19:38:00+00:00", 529) == "04:27"


def test_format_clock_offset_is_blank_on_bad_input():
    assert dashboard.format_clock_offset(None, 10) == ""
    assert dashboard.format_clock_offset("nonsense", 10) == ""
    assert dashboard.format_clock_offset("2026-07-27T19:38:00+00:00", "x") == ""


# ─── Unscored-sleep reason: a failed read must not claim the ring saw nothing ──

def test_sleep_unscored_reason_blames_loading_when_the_read_failed():
    """The bug this exists for: a transient Sheets read failure rendered as
    "Oura recorded no sleep period for this night" on a night whose data was
    complete (all 7 contributors present, score 76.8). That sends the reader
    to check their ring instead of reloading."""
    msg = dashboard.sleep_unscored_reason(read_failed=True)
    assert "Oura recorded no sleep period" not in msg
    assert "not because" in msg or "loading problem" in msg


def test_sleep_unscored_reason_blames_the_ring_only_when_the_read_succeeded():
    assert dashboard.sleep_unscored_reason(read_failed=False) == (
        "Oura recorded no sleep period for this night.")


def test_the_two_unscored_reasons_are_never_the_same_text():
    """Both causes produce an identical empty score; the whole point is that
    they must not produce an identical message."""
    assert (dashboard.sleep_unscored_reason(True)
            != dashboard.sleep_unscored_reason(False))


# ─── Readiness drill-down helpers ────────────────────────────────────────────

def _rb(components=None, missing=None, available=1.0, units=None):
    return {
        "score": 84.8,
        "components": components if components is not None else [
            {"key": "hrv_balance", "label": "HRV Balance", "score": 42.0, "weight": 0.21,
             "effective_weight": 0.21, "contribution": 8.82, "raw": 42.0, "reference": None},
            {"key": "sleep_debt", "label": "Sleep Debt", "score": 36.2, "weight": 0.09,
             "effective_weight": 0.09, "contribution": 3.26, "raw": 6.06, "reference": 9.5},
        ],
        "missing": missing or [],
        "available_weight": available,
        "alcohol_units": units,
        "model_version": 2,
        "sleep_baseline_window": 28,
    }


def test_readiness_rows_carry_the_weight_on_the_row():
    """Readiness weights span 4.5%-22.5%, so 'this one is red' means very
    different things at either end — unlike sleep's near-equal seven."""
    rows = dashboard.readiness_breakdown_rows(_rb())
    assert rows[0]["weight_display"] == "21.0%"
    assert rows[1]["weight_display"] == "9.0%"


def test_only_sleep_debt_carries_a_unit_the_rest_are_ouras_scores():
    """Under MODEL_VERSION 2 every component except Sleep Debt is one of
    Oura's pre-scored 0-100 contributors, where we hold no underlying raw
    unit at all. Printing the bare score is honest; inventing "ms" or "bpm"
    for it would not be."""
    rows = dashboard.readiness_breakdown_rows(_rb())
    assert rows[0]["value_display"] == "42"
    assert rows[1]["value_display"] == "6h 04m"


def test_an_unscored_readiness_row_is_kept_and_flagged():
    rows = dashboard.readiness_breakdown_rows(_rb(components=[
        {"key": "hrv", "label": "HRV", "score": None, "weight": 0.225,
         "effective_weight": 0.0, "contribution": None, "raw": None, "reference": None},
    ]))
    assert len(rows) == 1
    assert rows[0]["scored"] is False
    assert rows[0]["value_display"] == "not scored"
    assert rows[0]["bar_pct"] == 0.0


def test_readiness_coverage_caption_is_empty_when_all_seven_scored():
    assert dashboard.readiness_coverage_caption(_rb()) == ""


def test_readiness_coverage_caption_names_the_lost_weight_not_just_the_count():
    """Losing HRV Balance (21%) and losing Activity Balance (3%) would read
    identically as a count — the weight is what distinguishes them."""
    cap = dashboard.readiness_coverage_caption(_rb(missing=["hrv_balance"], available=0.79))
    assert "1 of 2" in cap          # the fixture carries two components
    assert "79%" in cap


def test_coverage_caption_denominator_tracks_the_real_component_count():
    """It was a hardcoded 7 until the component set grew to 9. A literal
    denominator goes quietly wrong rather than failing."""
    nine = [{"key": f"c{i}", "label": f"C{i}", "score": None if i else 50.0,
             "weight": 0.1, "effective_weight": 0.0, "contribution": None,
             "raw": None, "reference": None} for i in range(9)]
    cap = dashboard.readiness_coverage_caption(
        _rb(components=nine, missing=["c0"], available=0.9))
    assert "8 of 9" in cap


def test_readiness_alcohol_caption_is_empty_on_a_dry_day():
    assert dashboard.readiness_alcohol_caption(_rb()) == ""


def test_readiness_alcohol_caption_reports_units_without_claiming_a_deduction():
    """MODEL_VERSION 2 stopped scoring alcohol. The caption must say the
    units were logged AND that they are not in the score — stating one
    without the other is how a reader concludes the wrong thing."""
    cap = dashboard.readiness_alcohol_caption(_rb(units=1.5))
    assert "1.5 units" in cap
    assert "Not deducted" in cap
    assert "deducted from the score" not in cap.replace("Not deducted from the", "")


def test_readiness_alcohol_caption_uses_the_singular_for_one_unit():
    assert "1 unit of alcohol" in dashboard.readiness_alcohol_caption(_rb(units=1.0))


def test_readiness_unscored_reason_separates_a_failed_read_from_no_data():
    """Same lesson as sleep_unscored_reason, built in from the first commit
    this time rather than after a false claim reached the screen."""
    failed = dashboard.readiness_unscored_reason(read_failed=True)
    absent = dashboard.readiness_unscored_reason(read_failed=False)
    assert failed != absent
    assert "loading problem" in failed
    assert "No biometric readings" in absent


def test_oura_rows_show_numbers_because_ouras_tier_words_are_unpublished():
    """Oura renders 45 as 'Fair' but 42 as 'Pay attention'; the thresholds are
    not published and clearly differ per contributor, so reproducing the words
    would mean inventing a mapping and attributing it to Oura."""
    rows = dashboard.oura_readiness_rows({
        "contributors": {"hrv_balance": 42.0, "recovery_index": 100.0},
        "labels": {"hrv_balance": "HRV balance", "recovery_index": "Recovery index"},
    })
    assert [r["value_display"] for r in rows] == ["42", "100"]


def test_oura_rows_keep_a_null_contributor_visible():
    rows = dashboard.oura_readiness_rows({
        "contributors": {"hrv_balance": None},
        "labels": {"hrv_balance": "HRV balance"},
    })
    assert rows[0]["scored"] is False and rows[0]["value_display"] == "—"


def test_oura_rows_on_missing_detail_is_empty_not_an_error():
    assert dashboard.oura_readiness_rows(None) == []
    assert dashboard.oura_readiness_rows({}) == []


def test_divergence_caption_states_the_gap_and_its_direction():
    cap = dashboard.readiness_divergence_caption(84.8, 57.0)
    assert "57" in cap and "85" in cap and "28" in cap
    assert "higher" in cap


def test_divergence_caption_never_declares_a_winner():
    """Oura's model is proprietary and unvalidated; ours has no labelled
    outcome to score against. The caption may report, not adjudicate."""
    for ours, oura in ((84.8, 57.0), (50.0, 80.0), (57.0, 57.0)):
        cap = dashboard.readiness_divergence_caption(ours, oura)
        assert "ground truth" in cap
        assert "correct" not in cap and "accurate" not in cap


def test_divergence_caption_survives_a_missing_score_on_either_side():
    from services.readiness import NOT_COMPUTED
    for ours, oura in ((None, 57.0), (NOT_COMPUTED, 57.0), (84.8, None)):
        assert "ground truth" in dashboard.readiness_divergence_caption(ours, oura)
