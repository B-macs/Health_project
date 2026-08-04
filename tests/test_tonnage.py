"""Tests for services/tonnage.py — weekly tonnage by primary body sector.

The properties pinned here are the ones that keep tonnage honest: the
formula, one sector per exercise so the three total the overall, unloaded work
counted in reps and never converted to kilograms, and a week with no eligible
work reading zero rather than vanishing from the series.
"""

from __future__ import annotations

from datetime import date

import pytest

from services import tonnage


REGION_MAP = {
    "Lat Pulldown": "upper_body",
    "Incline DB Press": "upper_body",
    "Pallof Press (Cable)": "core",
    "Dead Bug": "core",
    "Hip Thrust (Loaded)": "lower_body",
    "Romanian Deadlift (DB)": "lower_body",
}
TODAY = date(2026, 8, 4)          # a Tuesday; its week starts Mon 3 Aug


def _row(name, day, sets):
    return {"movement_name": name, "session_date": day, "sets": sets}


def _week(series, iso):
    return next(w for w in series if w.week_start == date.fromisoformat(iso))


# ── the formula ─────────────────────────────────────────────────────────────

def test_tonnage_is_load_times_reps_times_sets():
    rows = [_row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 40}] * 3)]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)
    assert _week(series, "2026-07-27").value("upper_body").kg == pytest.approx(1200.0)


def test_sets_at_different_loads_are_summed_per_set_not_averaged():
    """10 reps at 40, 45 and 50 kg is 400 + 450 + 500 = 1,350 kg. Collapsing
    the three to sets x reps x a mean load would give the same answer here
    only because the loads happen to be evenly spaced — the per-set sum is
    what makes it right in general."""
    rows = [_row("Lat Pulldown", "2026-07-27", [
        {"reps": 10, "weight": 40}, {"reps": 10, "weight": 45}, {"reps": 10, "weight": 50},
    ])]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)
    assert _week(series, "2026-07-27").value("upper_body").kg == pytest.approx(1350.0)


def test_a_heavy_top_set_is_not_rounded_into_the_others():
    """8 x 20 then 3 x 60 is 160 + 180 = 340 kg. A "sets x reps x load" model
    reading the first set's load would report 2 x 8 x 20 = 320 and lose the
    top set entirely."""
    rows = [_row("Lat Pulldown", "2026-07-27", [
        {"reps": 8, "weight": 20}, {"reps": 3, "weight": 60},
    ])]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)
    assert _week(series, "2026-07-27").value("upper_body").kg == pytest.approx(340.0)


# ── eligibility ─────────────────────────────────────────────────────────────

def test_unloaded_reps_produce_no_kilograms():
    """There is no defined bodyweight conversion. Inventing one would put
    fictional weight into a real total."""
    rows = [_row("Dead Bug", "2026-07-27", [{"reps": 12, "weight": None}] * 3)]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)
    core = _week(series, "2026-07-27").value("core")
    assert core.kg == 0.0
    assert core.sets == 0


def test_unloaded_reps_are_still_counted_separately():
    """So a week of genuine rehab work does not display as though nothing
    happened just because none of it was loaded."""
    rows = [_row("Dead Bug", "2026-07-27", [{"reps": 12, "weight": None}] * 3)]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)
    assert _week(series, "2026-07-27").value("core").unloaded_reps == 36.0


def test_a_set_with_weight_but_no_reps_does_not_count():
    rows = [_row("Lat Pulldown", "2026-07-27", [{"reps": 0, "weight": 40}])]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)
    assert _week(series, "2026-07-27").value("upper_body").kg == 0.0


# ── sector allocation ───────────────────────────────────────────────────────

def test_a_compound_lift_goes_wholly_to_its_primary_sector():
    """An RDL is not split between lower body and core — that is what makes
    upper + core + lower an identity rather than an approximation."""
    rows = [_row("Romanian Deadlift (DB)", "2026-07-27", [{"reps": 10, "weight": 50}])]
    week = _week(tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)[0], "2026-07-27")
    assert week.value("lower_body").kg == pytest.approx(500.0)
    assert week.value("core").kg == 0.0
    assert week.value("upper_body").kg == 0.0


def test_the_three_sectors_always_total_the_overall():
    rows = [
        _row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 40}]),
        _row("Pallof Press (Cable)", "2026-07-27", [{"reps": 10, "weight": 12.5}]),
        _row("Hip Thrust (Loaded)", "2026-07-28", [{"reps": 10, "weight": 50}]),
    ]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)
    for week in series:
        assert week.overall.kg == pytest.approx(
            sum(week.value(r).kg for r in tonnage.REGIONS)
        )


def test_an_unmapped_exercise_is_reported_rather_than_silently_dropped():
    rows = [_row("Week 1 Self-Assessment", "2026-07-27", [{"reps": 1, "weight": 0}])]
    series, unmapped = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)
    assert unmapped == {"Week 1 Self-Assessment"}
    assert _week(series, "2026-07-27").overall.kg == 0.0


# ── the series ──────────────────────────────────────────────────────────────

def test_a_week_without_eligible_work_is_present_and_reads_zero():
    """Absent from the series and zero in the series are different claims.
    Tonnage is a statement about the week, so the week has to be there."""
    rows = [_row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 40}])]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)
    assert len(series) == 4
    assert _week(series, "2026-08-03").overall.kg == 0.0


def test_the_series_ends_with_the_week_containing_today():
    series, _ = tonnage.weekly_tonnage([], REGION_MAP, today=TODAY, weeks=3)
    assert series[-1].week_start == date(2026, 8, 3)
    assert series[0].week_start == date(2026, 7, 20)


def test_rows_after_today_are_ignored():
    rows = [_row("Lat Pulldown", "2026-08-10", [{"reps": 10, "weight": 40}])]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)
    assert all(w.overall.kg == 0.0 for w in series)


def test_training_days_counts_days_not_exercises():
    rows = [
        _row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 40}]),
        _row("Incline DB Press", "2026-07-27", [{"reps": 10, "weight": 20}]),
        _row("Hip Thrust (Loaded)", "2026-07-29", [{"reps": 10, "weight": 50}]),
    ]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)
    assert _week(series, "2026-07-27").training_days == 2


def test_a_week_with_only_unloaded_work_still_counts_as_a_training_day():
    """The real week of 3 Aug: a session happened, none of it loaded. Zero
    tonnage is true; "no training" would not be."""
    rows = [_row("Dead Bug", "2026-08-03", [{"reps": 12, "weight": None}])]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=2)
    week = _week(series, "2026-08-03")
    assert week.overall.kg == 0.0
    assert week.training_days == 1
    assert week.overall.unloaded_reps == 12.0


# ── week-over-week ──────────────────────────────────────────────────────────

def test_change_reports_absolute_and_percent():
    assert tonnage.change(5595.0, 3315.0) == pytest.approx((2280.0, 68.777), rel=1e-3)


def test_change_has_no_percent_from_a_zero_week():
    """A rise from nothing is not a percentage; printing one would be a
    division by zero dressed up as a number."""
    delta, pct = tonnage.change(3315.0, 0.0)
    assert delta == 3315.0
    assert pct is None


def test_change_to_zero_is_minus_one_hundred_percent():
    assert tonnage.change(0.0, 5595.0) == pytest.approx((-5595.0, -100.0))


# ── axis ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("peak,expected", [
    (5595.0, 6000.0),   # overall
    (2670.0, 3000.0),   # upper body
    (225.0, 240.0),     # core
    (2775.0, 3000.0),   # lower body
])
def test_axis_max_is_four_clean_steps_above_the_peak(peak, expected):
    assert tonnage.nice_axis_max(peak) == pytest.approx(expected)


def test_axis_max_always_contains_the_peak():
    for peak in (1, 7, 99, 101, 999, 1001, 12345):
        assert tonnage.nice_axis_max(float(peak)) >= peak


def test_axis_max_of_an_empty_series_is_still_drawable():
    assert tonnage.nice_axis_max(0.0) > 0
