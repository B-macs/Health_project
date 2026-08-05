"""Tests for services/body_composition.py and body_composition_baselines.py.

The arithmetic assertions here are not invented for the test — every one of them
is a fact measured off the real exports on 2026-08-04/05, so a failure means the
model drifted away from the devices rather than that a fixture went stale.
"""

from __future__ import annotations

import math
from datetime import date, datetime

import pytest

import body_composition_baselines as bcb
from services import body_composition as bc


# ── parsing ──────────────────────────────────────────────────────────────────

FITDAYS_HEADER = (
    "Date,Weight,BMI,Body Fat,Subcutaneous fat,Heart rate,Cardiac Index,"
    "Visceral Fat,Body Water,Skeletal Muscle,Muscle mass,Bone Mass,Protein,"
    "BMR,Body age,\n"
)

FITDAYS_ROWS = (
    "07:24 Aug.03 2026,82.2kg,24.5,17.6%,15.3%,--,--,7.5,59.5%,53.2%,64.4kg,"
    "3.4kg,18.8%,1833kcal,29,\n"
    "08:15 Jul.31 2026,81.9kg,24.5,17.6%,15.3%,--,--,7.5,59.5%,53.2%,64.1kg,"
    "3.4kg,18.8%,1827kcal,29,\n"
    "12:10 Jun.07 2024,85.9kg,25.7,19.2%,16.7%,--,--,8.6,58.3%,52.2%,65.9kg,"
    "3.5kg,18.4%,1869kcal,29,\n"
)


def test_parse_returns_oldest_first_with_units_stripped():
    readings = bc.parse_fitdays_csv(FITDAYS_HEADER + FITDAYS_ROWS)
    assert [r.taken_at for r in readings] == [
        datetime(2024, 6, 7, 12, 10),
        datetime(2026, 7, 31, 8, 15),
        datetime(2026, 8, 3, 7, 24),
    ]
    assert readings[-1].weight_kg == 82.2
    assert readings[-1].bmi == 24.5
    assert readings[-1].body_fat_pct == 17.6


def test_parse_skips_unparseable_rows_rather_than_raising():
    text = FITDAYS_HEADER + FITDAYS_ROWS + "not a date,80kg,24,17%,,,,,,,,,,,\n"
    assert len(bc.parse_fitdays_csv(text)) == 3


def test_parse_treats_the_double_dash_cell_as_missing():
    """Heart rate and Cardiac Index are '--' on every row of the real export."""
    assert bc._number("--") is None
    assert bc._number("") is None
    assert bc._number(None) is None
    assert bc._number("1833kcal") == 1833.0


def test_same_minute_duplicates_are_collapsed():
    """The real export contains same-minute repeats; summing them double-counts
    a single weigh-in."""
    dupe = (
        "07:24 Aug.03 2026,82.2kg,24.5,17.6%,,--,--,,,,,,,,\n"
        "07:24 Aug.03 2026,82.4kg,24.6,17.7%,,--,--,,,,,,,,\n"
    )
    readings = bc.parse_fitdays_csv(FITDAYS_HEADER + dupe)
    assert len(readings) == 1


def test_two_readings_a_minute_apart_are_both_kept():
    """2024-06-07 12:10 and 12:12 are distinct weigh-ins and must survive —
    they are the pair that shows 'body age' moving a year in two minutes."""
    pair = (
        "12:10 Jun.07 2024,85.9kg,25.7,19.2%,,--,--,,,,,,,,\n"
        "12:12 Jun.07 2024,84.4kg,25.2,18.4%,,--,--,,,,,,,,\n"
    )
    assert len(bc.parse_fitdays_csv(FITDAYS_HEADER + pair)) == 2


# ── the derived split ────────────────────────────────────────────────────────

def test_fat_and_fat_free_sum_to_the_weight():
    r = bc.ScaleReading(datetime(2026, 8, 3, 7, 24), 82.2, 24.5, 17.6)
    assert r.fat_mass_kg + r.fat_free_mass_kg == pytest.approx(r.weight_kg)
    assert r.fat_mass_kg == pytest.approx(14.467, abs=0.001)
    assert r.fat_free_mass_kg == pytest.approx(67.733, abs=0.001)


def test_split_is_none_when_the_device_printed_no_body_fat():
    r = bc.ScaleReading(datetime(2026, 8, 3, 7, 24), 82.2, 24.5, None)
    assert r.fat_mass_kg is None and r.fat_free_mass_kg is None


def test_implied_height_recovers_the_scale_setting():
    """The Foryond sat at 183.0 cm for the whole export; that is how the 1 cm
    error was found."""
    r = bc.ScaleReading(datetime(2026, 8, 3, 7, 24), 82.2, 24.5)
    assert r.implied_height_m * 100 == pytest.approx(183.2, abs=0.15)


def test_derived_columns_are_documented_not_stored():
    """Nothing arithmetic on weight may become a field on ScaleReading, or a
    future reader will treat one number as several agreeing measurements."""
    fields = set(bc.ScaleReading.__dataclass_fields__)
    assert fields == {"taken_at", "weight_kg", "bmi", "body_fat_pct"}
    for name in ("bmr_kcal", "muscle_mass_kg", "visceral_level", "body_age_years"):
        assert name in bc.DERIVED_COLUMNS
        assert name not in fields


# ── the InBody height defect ─────────────────────────────────────────────────

def test_entered_height_recovers_all_five_gym_entries():
    entered = [round(s.entered_height_m * 100, 1) for s in bcb.SCANS]
    assert entered == [185.5, 175.1, 174.9, 181.6, 181.8]


def test_only_the_last_scan_was_run_at_a_defensible_height():
    errors = [abs(s.height_error_cm()) for s in bcb.SCANS]
    assert errors[-1] < 0.5
    assert sum(1 for e in errors if e > 3.0) == 3


def test_the_eight_minute_pair_disagrees_by_six_points_as_printed():
    """2025-05-21 12:16 and 12:24, identical weight, height re-typed between."""
    first, second = bcb.SCANS[2], bcb.SCANS[3]
    assert first.weight_kg == second.weight_kg == 79.5
    assert (second.taken_at - first.taken_at).total_seconds() == 8 * 60
    assert first.body_fat_pct == pytest.approx(20.0, abs=0.1)
    assert second.body_fat_pct == pytest.approx(14.0, abs=0.1)
    assert first.body_fat_pct - second.body_fat_pct == pytest.approx(6.0, abs=0.15)


def test_correcting_the_height_makes_the_eight_minute_pair_agree():
    """The whole justification for at_height: 6.0 pp apart becomes 0.31 pp."""
    first = bcb.SCANS[2].at_height()
    second = bcb.SCANS[3].at_height()
    assert abs(first.body_fat_pct - second.body_fat_pct) < 0.4


def test_correcting_the_height_shrinks_the_spread_but_does_not_erase_it():
    """3.6 pp was the keyboard; 4.6 pp is the body. If a change ever makes the
    corrected spread vanish, the correction has started deleting signal."""
    printed = [s.body_fat_pct for s in bcb.SCANS]
    corrected = [s.at_height().body_fat_pct for s in bcb.SCANS]
    assert max(printed) - min(printed) == pytest.approx(8.2, abs=0.2)
    assert max(corrected) - min(corrected) == pytest.approx(4.64, abs=0.2)


def test_at_height_leaves_the_measured_weight_alone():
    for scan in bcb.SCANS:
        assert scan.at_height().weight_kg == scan.weight_kg


def test_at_height_is_idempotent():
    once = bcb.SCANS[0].at_height()
    assert once.at_height().body_fat_pct == pytest.approx(once.body_fat_pct, abs=1e-9)


def test_height_immune_pair_is_untouched_by_the_correction():
    """Phase angle and ECW/TBW are quotients of measured values. If a change
    ever lets the entered height move either of them, the model is wrong."""
    for scan in bcb.SCANS:
        fixed = scan.at_height()
        assert fixed.ecw_tbw == scan.ecw_tbw
        assert fixed.phase_angle_deg == scan.phase_angle_deg


def test_phase_angle_never_moved_across_the_scans_that_report_it():
    reported = [s.phase_angle_deg for s in bcb.SCANS if s.phase_angle_deg is not None]
    assert reported == [6.1, 6.1, 6.1]


def test_ecw_tbw_stayed_inside_the_healthy_band():
    ratios = [s.ecw_tbw for s in bcb.SCANS]
    assert min(ratios) >= 0.360 and max(ratios) <= 0.390
    assert max(ratios) - min(ratios) == pytest.approx(0.004, abs=0.0005)


def test_bmr_is_katch_mcardle_on_the_clean_scan():
    """1869 kcal on the sheet; 370 + 21.6 * fat-free mass reproduces it."""
    assert bcb.SCANS[-1].bmr_kcal == pytest.approx(1869.0, abs=1.0)


def test_corrected_january_to_june_is_real_recomposition():
    """-4.22 kg fat and +0.72 kg lean on a -3.5 kg weight change, and the three
    reconcile — the signal the height defect was hiding."""
    start = bcb.SCANS[0].at_height()
    end = bcb.SCANS[-1].at_height()
    d_fat = end.fat_mass_kg - start.fat_mass_kg
    d_lean = end.fat_free_mass_kg - start.fat_free_mass_kg
    d_weight = end.weight_kg - start.weight_kg
    assert d_fat == pytest.approx(-4.22, abs=0.15)
    assert d_lean == pytest.approx(+0.72, abs=0.15)
    assert d_fat + d_lean == pytest.approx(d_weight, abs=1e-9)


# ── windows ──────────────────────────────────────────────────────────────────

TODAY = date(2026, 8, 5)          # a Wednesday


def test_month_window_is_the_calendar_month():
    w = bc.period_window("month", 0, TODAY)
    assert (w.start, w.end) == (date(2026, 8, 1), date(2026, 8, 31))
    assert w.label == "Aug 2026"


def test_month_window_steps_back_across_a_year_boundary():
    w = bc.period_window("month", -8, TODAY)
    assert (w.start, w.end) == (date(2025, 12, 1), date(2025, 12, 31))
    assert w.label == "Dec 2025"


def test_month_window_end_is_correct_for_february():
    w = bc.period_window("month", -6, TODAY)
    assert (w.start, w.end) == (date(2026, 2, 1), date(2026, 2, 28))


def test_week_window_runs_monday_to_sunday():
    w = bc.period_window("week", 0, TODAY)
    assert (w.start, w.end) == (date(2026, 8, 3), date(2026, 8, 9))
    assert w.start.weekday() == 0 and w.end.weekday() == 6


def test_year_window_is_the_calendar_year():
    w = bc.period_window("year", -1, TODAY)
    assert (w.start, w.end) == (date(2025, 1, 1), date(2025, 12, 31))
    assert w.label == "2025"


def test_all_window_spans_the_data():
    w = bc.period_window("all", 0, TODAY, earliest=date(2024, 6, 7))
    assert (w.start, w.end) == (date(2024, 6, 7), TODAY)


def test_unknown_window_kind_raises():
    with pytest.raises(ValueError):
        bc.period_window("fortnight", 0, TODAY)


def test_cannot_step_forward_past_today():
    assert bc.can_step("month", 0, 1, TODAY) is False
    assert bc.can_step("month", -1, 1, TODAY) is True


def test_cannot_step_back_past_the_first_reading():
    first = date(2024, 6, 7)
    assert bc.can_step("year", -1, -1, TODAY, first) is True     # into 2024
    assert bc.can_step("year", -2, -1, TODAY, first) is False    # 2023 is empty


def test_all_never_steps():
    assert bc.can_step("all", 0, -1, TODAY) is False
    assert bc.can_step("all", 0, 1, TODAY) is False


# ── window arithmetic ────────────────────────────────────────────────────────

def _reading(day: date, kg: float) -> bc.ScaleReading:
    return bc.ScaleReading(datetime(day.year, day.month, day.day, 8, 0), kg)


def test_readings_in_window_is_inclusive_at_both_ends():
    window = bc.period_window("month", 0, TODAY)
    rows = [_reading(date(2026, 7, 31), 81.9),
            _reading(date(2026, 8, 1), 82.0),
            _reading(date(2026, 8, 31), 82.5),
            _reading(date(2026, 9, 1), 82.6)]
    assert [r.weight_kg for r in bc.readings_in(rows, window)] == [82.0, 82.5]


def test_window_change_is_last_minus_first():
    assert bc.window_change([81.8, 81.9, 82.2]) == pytest.approx(0.4)


def test_window_change_needs_two_readings():
    assert bc.window_change([82.2]) is None
    assert bc.window_change([]) is None


def test_split_runs_breaks_on_the_injury_gap_and_not_before():
    """2025-10-21 -> 2026-01-27 is 98 days with nothing measured; a line across
    it would invent the 4.4 kg that arrived unobserved."""
    rows = [_reading(date(2025, 10, 20), 79.5),
            _reading(date(2025, 10, 21), 79.3),
            _reading(date(2026, 1, 27), 83.7),
            _reading(date(2026, 1, 28), 83.6)]
    runs = bc.split_runs(rows, bc.SCALE_GAP_BREAK_DAYS)
    assert [len(r) for r in runs] == [2, 2]


def test_split_runs_keeps_the_inbody_scans_connected():
    """At the scale's 21-day rule the five gym scans would be five isolated
    dots and the trend would be invisible."""
    runs = bc.split_runs(list(bcb.SCANS), bc.INBODY_GAP_BREAK_DAYS)
    assert len(runs) == 1


def test_split_runs_on_empty_input():
    assert bc.split_runs([], bc.SCALE_GAP_BREAK_DAYS) == []


# ── guards ───────────────────────────────────────────────────────────────────

def test_true_height_is_the_confirmed_figure():
    assert bc.TRUE_HEIGHT_M == 1.820


def test_module_does_no_io_and_imports_no_streamlit():
    """Belt and braces beside tests/test_no_streamlit_in_services.py — this
    module is the one most likely to grow a convenient open() one day."""
    source = (bc.__file__ and open(bc.__file__, encoding="utf-8").read()) or ""
    assert "import streamlit" not in source
    assert "open(" not in source
    assert "requests" not in source


def test_no_fused_body_composition_number_reappears():
    """The refusal recorded in the module docstring, made checkable. A single
    blended fat percent across two devices, or any composition expressed in
    years, repeats the retired Recovery Score's mistake."""
    banned = ("fused_body_fat", "blended_body_fat", "metabolic_age",
              "body_age_score", "composition_age")
    for name in banned:
        assert not hasattr(bc, name)
