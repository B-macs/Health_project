"""Tests for services/dashboard.py — pure Home-page computation extracted
from app.py's previously undocumented, unparameterized dashboard-math cluster."""

import ast
from datetime import date

from services import dashboard


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


def test_sleep_meta_none_pct():
    _, val, lbl, _, _ = dashboard.sleep_meta(None, 8.0, None)
    assert lbl == "No Readings"
    assert val == "--%"


def test_sleep_meta_optimal_tier_with_baseline_window():
    _, val, lbl, _, desc = dashboard.sleep_meta(90, 7.8, 28)
    assert lbl == "Optimal"
    assert val == "90%"
    assert "28d avg" in desc


def test_sleep_meta_no_baseline_window_uses_target_copy():
    _, _, _, _, desc = dashboard.sleep_meta(90, 8.0, None)
    assert "target" in desc


# ─── compute_daily_metrics_snapshot ─────────────────────────────────────────

def test_snapshot_returns_all_four_keys_with_minimal_data():
    snap = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows=[], au_rows=[], stage=1,
    )
    assert set(snap) == {"readiness_score", "sleep_pct", "strain", "strain_is_rolling"}


def test_snapshot_no_data_everything_none():
    snap = dashboard.compute_daily_metrics_snapshot(
        date(2026, 7, 20), bio_rows=[], au_rows=[], stage=1,
    )
    assert snap["readiness_score"] is None
    assert snap["sleep_pct"] is None
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
