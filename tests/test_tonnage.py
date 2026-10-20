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


# ── held and timed work is not a rep ────────────────────────────────────────

def test_a_hold_is_counted_in_seconds_not_as_one_rep():
    """services/sessions.py writes a hold as reps=1 with the work in `tut`, so
    a 60-second plank and a single dead bug are both "1 rep". Summing reps
    alone misrepresents exactly the work the counter exists to represent."""
    rows = [_row("Dead Bug", "2026-07-27", [{"reps": 1, "weight": None, "tut": 60}] * 3)]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)
    core = _week(series, "2026-07-27").value("core")
    assert core.unloaded_seconds == 180.0
    assert core.unloaded_reps == 0.0
    assert core.kg == 0.0


def test_a_set_of_held_reps_counts_every_hold():
    """A hold_reps set (bird dog: 6 reps, 5 s each) is written reps=6, tut=5
    by both sessions.build_set_record and sessions.make_sets_data. The work is
    30 s; counted once per set it read as 5 (WP-15, 2026-10-13)."""
    rows = [_row("Dead Bug", "2026-07-27",
                 [{"reps": 6, "weight": None, "tut": 5, "velocity": "isometric"}] * 2)]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)
    core = _week(series, "2026-07-27").value("core")
    assert core.unloaded_seconds == 60.0
    assert core.unloaded_reps == 0.0, "held reps are time, never also reps"


def test_held_time_follows_the_set_builders_shape():
    """The rule rests on what the builders write: per-rep hold time in tut and
    the rep count in reps. If either builder changes shape, this fails first."""
    from services import sessions
    ex = {"type": "hold_reps", "sets": 2, "reps_in_set": 6, "hold_seconds": 5,
          "rest_seconds": 30}
    built = sessions.build_set_record(ex, 1, None, "2026-07-27T10:00:00")
    assert (built["reps"], built["tut"]) == (6, 5)
    assert [(s["reps"], s["tut"]) for s in sessions.make_sets_data(ex)] == [(6, 5), (6, 5)]
    plank = sessions.build_set_record(
        {"type": "hold", "sets": 1, "hold_seconds": 45}, 1, None, "2026-07-27T10:00:00")
    assert (plank["reps"], plank["tut"]) == (1, 45)


def test_reps_and_seconds_are_never_added_together():
    """No exchange rate between a rep and a second is defined here, so the two
    counters stay apart — the same reason a bodyweight hold never becomes kg."""
    rows = [
        _row("Dead Bug", "2026-07-27", [{"reps": 12, "weight": None, "tut": 0}] * 3),
        _row("Pallof Press (Cable)", "2026-07-27",
             [{"reps": 1, "weight": None, "tut": 45}] * 2),
    ]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)
    core = _week(series, "2026-07-27").value("core")
    assert core.unloaded_reps == 36.0
    assert core.unloaded_seconds == 90.0


def test_a_loaded_set_that_also_has_tut_still_counts_as_tonnage():
    """`tut` is recorded on loaded sets too. The load branch has to win, or a
    weighted lift would fall out of tonnage entirely."""
    rows = [_row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 40, "tut": 30}])]
    series, _ = tonnage.weekly_tonnage(rows, REGION_MAP, today=TODAY, weeks=4)
    upper = _week(series, "2026-07-27").value("upper_body")
    assert upper.kg == pytest.approx(400.0)
    assert upper.unloaded_seconds == 0.0


@pytest.mark.parametrize("peak", [4.1, 9.99, 25.0, 60.0, 225.0, 999.0, 2775.0, 12345.0])
def test_every_gridline_is_a_whole_number_of_kilograms(peak):
    """The axis labels are formatted as integers, so a fractional quarter-step
    prints wrong: a 25 kg core week gave a top of 30 with lines at
    30/22.5/15/7.5/0 and labels reading 30/22/15/8/0."""
    top = tonnage.nice_axis_max(peak)
    assert top >= peak
    for i in range(5):
        line = top * i / 4
        assert line == pytest.approx(round(line)), f"gridline {line} is not whole"


# ── work without load, on the page (WP-15, 2026-10-13) ──────────────────────

@pytest.mark.parametrize("seconds, text", [
    (45, "45 s"), (60, "1 min"), (245, "4 min 5 s"), (59.6, "1 min"), (0.4, "0 s"),
])
def test_held_time_reads_as_a_person_says_it(seconds, text):
    assert tonnage.held_text(seconds) == text


def test_the_unloaded_line_names_held_time_and_reps_apart():
    cell = tonnage.SectorWeek(unloaded_seconds=245.0, unloaded_reps=36.0)
    assert tonnage.unloaded_text(cell) == "4 min 5 s held, 36 reps"
    assert tonnage.unloaded_text(tonnage.SectorWeek(unloaded_reps=1.0)) == "1 rep"


def test_a_week_with_only_loaded_work_has_no_unloaded_line():
    assert tonnage.unloaded_text(tonnage.SectorWeek(kg=400.0, sets=4)) is None



# ── both sides, and machines in stack units (the owner, 2026-10-20) ─────────

TWO_SIDED = {"Made-up Row": {"sides": 2, "unit": "kg"},
             "Made-up Cable": {"sides": 1, "unit": "unit"},
             "Made-up Side Hold": {"sides": 2, "unit": "kg"}}
MAP = {"Made-up Row": "upper_body", "Made-up Cable": "upper_body", "Made-up Side Hold": "core"}


def _one(name, sets):
    return [{"movement_name": name, "session_date": TODAY.isoformat(), "sets": sets}]


def test_a_one_side_exercise_counts_both_sides():
    """The left side is written only where it differs, so a missing left value
    is the right's."""
    rows = _one("Made-up Row", [{"reps": 10, "weight": 20.0},
                                {"reps": 10, "weight": 20.0, "reps_left": 8, "weight_left": 18.0}])
    series, _ = tonnage.weekly_tonnage(rows, MAP, today=TODAY, weeks=1, traits=TWO_SIDED)
    assert series[-1].value("upper_body").kg == 10 * 20 * 2 + 10 * 20 + 8 * 18
    assert series[-1].value("upper_body").sets == 2


def test_a_one_side_hold_counts_both_sides_seconds():
    rows = _one("Made-up Side Hold", [{"reps": 1, "weight": 0, "tut": 30, "tut_left": 25}])
    series, _ = tonnage.weekly_tonnage(rows, MAP, today=TODAY, weeks=1, traits=TWO_SIDED)
    assert series[-1].value("core").unloaded_seconds == 55


def test_stack_units_are_never_kilograms():
    rows = _one("Made-up Cable", [{"reps": 12, "weight": 6}, {"reps": 12, "weight": 6}])
    series, _ = tonnage.weekly_tonnage(rows, MAP, today=TODAY, weeks=1, traits=TWO_SIDED)
    cell = series[-1].value("upper_body")
    assert cell.kg == 0 and cell.unit_reps == 24
    assert series[-1].overall.unit_reps == 24
    assert tonnage.unloaded_text(cell) == "24 cable reps in stack units"


def test_without_traits_every_set_counts_once_in_kilograms():
    rows = _one("Made-up Row", [{"reps": 10, "weight": 20.0, "reps_left": 8, "weight_left": 18.0}])
    series, _ = tonnage.weekly_tonnage(rows, MAP, today=TODAY, weeks=1)
    assert series[-1].value("upper_body").kg == 200


def test_the_plans_name_their_sides_and_units():
    from services import sessions
    traits = sessions.exercise_traits()
    assert traits["Face Pull (Cable)"]["unit"] == "unit"
    assert traits["Single-Arm DB Row"]["sides"] == 2
    assert traits["Right Posterior Hip Capsule Stretch (Revised Cue)"]["sides"] == 1, "right only"
    assert all(t["sides"] in (1, 2) and t["unit"] in ("kg", "unit") for t in traits.values())


def test_the_strength_estimate_leaves_out_stack_units_until_their_kg_is_known():
    from services import strength_screen as ss
    rows = [{"movement_name": "Made-up Cable", "sets": [{"reps": 12, "weight": 6}]},
            {"movement_name": "Made-up Row", "sets": [{"reps": 10, "weight": 20.0}]}]
    assert [r["movement_name"] for r in ss.kilogram_rows(rows, TWO_SIDED, unit_kg={})] == ["Made-up Row"]
    converted = ss.kilogram_rows(rows, TWO_SIDED, unit_kg={"Made-up Cable": 2.5})
    assert converted[0]["sets"][0]["weight"] == 15.0
    assert rows[0]["sets"][0]["weight"] == 6, "the log itself is not changed"
