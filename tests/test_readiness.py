"""Tests for services/readiness.py — HRV/RHR/sleep baselines and compute_readiness.

Covers the 2026-07-14 fix: hrv_baseline/rhr_baseline previously required 14
observations before trusting a baseline at all. With sparse wearable history
(e.g. Garmin HRV only recently starting to report), this silently dropped HRV
out of compute_readiness's weighted average entirely — letting RHR/Sleep alone
determine the score, and inflating it well above what services/engine.py's
traffic_light() (no such minimum) would independently signal for the same day.
"""

from datetime import date

from services import readiness


def _rows(hrv_vals: list[float | None], rhr: float = 55.0, sleep: float = 7.5) -> list[dict]:
    """Builds ascending-date biometric rows; hrv_vals[-1] is "today"."""
    out = []
    for i, hrv in enumerate(hrv_vals):
        out.append({
            "date": f"2026-06-{i + 1:02d}",
            "hrv_ms": hrv,
            "resting_heart_rate": rhr,
            "sleep_duration_hours": sleep,
        })
    return out


# ─── hrv_baseline / rhr_baseline ───────────────────────────────────────────────

def test_hrv_baseline_none_below_minimum_days():
    rows = _rows([40.0, 42.0])  # only 2 valid days, minimum is 3
    assert readiness.hrv_baseline(rows) is None


def test_hrv_baseline_computed_at_exactly_minimum_days():
    rows = _rows([40.0, 42.0, 44.0])  # exactly 3
    assert readiness.hrv_baseline(rows) == 42.0  # avg of 3, not divided by 14


def test_hrv_baseline_averages_thin_history_correctly_not_over_a_stale_denominator():
    # Regression case: 6 valid HRV days should average over 6, not silently
    # divide by a fixed 14-day window it doesn't have data to fill.
    rows = _rows([24.0, 19.0, 21.0, 19.0, 24.0, 18.0])
    baseline = readiness.hrv_baseline(rows)
    assert baseline == round(sum([24.0, 19.0, 21.0, 19.0, 24.0, 18.0]) / 6, 2)


def test_hrv_baseline_caps_window_at_28_days():
    rows = _rows([50.0] * 20 + [10.0] * 20)  # 40 days total
    baseline = readiness.hrv_baseline(rows)
    # Last 28 = 8 more of 50.0 then 20 of 10.0
    expected = round((8 * 50.0 + 20 * 10.0) / 28, 2)
    assert baseline == expected


def test_rhr_baseline_ignores_none_entries_and_respects_minimum():
    rows = [
        {"date": "2026-06-01", "resting_heart_rate": None},
        {"date": "2026-06-02", "resting_heart_rate": 55.0},
        {"date": "2026-06-03", "resting_heart_rate": 57.0},
    ]
    assert readiness.rhr_baseline(rows) is None  # only 2 non-null values

    rows.append({"date": "2026-06-04", "resting_heart_rate": 56.0})
    assert readiness.rhr_baseline(rows) == 56.0  # (55+57+56)/3


# ─── compute_readiness: HRV must not be silently dropped with thin history ────

def test_compute_readiness_includes_degraded_hrv_even_with_thin_history():
    """Regression for the exact bug: 6 days of HRV history, today's HRV well
    below baseline. Previously hrv_baseline() returned None (needed 14 days),
    so HRV's 40% weight was silently reassigned to RHR/Sleep, which looked
    fine, inflating the score to ~97 even though HRV had dropped ~14%. It
    must now be included and pull the score down."""
    rows = _rows([24.0, 19.0, 21.0, 19.0, 24.0, 18.0], rhr=57.0, sleep=7.1)
    # Make RHR/sleep baseline rows match "today" almost exactly (near-perfect
    # on their own), isolating HRV's degradation as the only signal.
    for r in rows[:-1]:
        r["resting_heart_rate"] = 57.0
        r["sleep_duration_hours"] = 7.1
    today = date(2026, 6, 6)

    score = readiness.compute_readiness(today, rows)
    assert score != readiness.NOT_COMPUTED

    hrv_base = readiness.hrv_baseline(rows)
    assert hrv_base is not None
    expected_hrv_component = min(100.0, (18.0 / hrv_base) * 100.0)
    assert expected_hrv_component < 100.0  # today's HRV (18.0) is below the 6-day baseline

    # With RHR/Sleep both at ~100 and HRV degraded, weighted average must
    # land below what a HRV-excluded score would give (which would be ~100
    # since RHR/Sleep alone are perfect).
    assert score < 97.0


def test_compute_readiness_not_computed_with_no_rows():
    assert readiness.compute_readiness(date.today(), []) == readiness.NOT_COMPUTED


def test_compute_readiness_deterministic_for_same_inputs():
    rows = _rows([40.0, 42.0, 44.0, 41.0])
    today = date(2026, 6, 4)
    assert readiness.compute_readiness(today, rows) == readiness.compute_readiness(today, rows)


# ─── compute_readiness_trend ───────────────────────────────────────────────────

def _day(n: int, hrv: float, rhr: float, sleep: float) -> dict:
    return {"date": f"2026-06-{n:02d}", "hrv_ms": hrv,
            "resting_heart_rate": rhr, "sleep_duration_hours": sleep}


def test_compute_readiness_trend_not_computed_with_no_rows():
    assert readiness.compute_readiness_trend(date.today(), []) == readiness.NOT_COMPUTED


def test_compute_readiness_trend_seeds_from_first_available_day():
    # A single day of history: trend must equal that day's own raw score
    # (nothing to blend with yet).
    rows = [_day(n, 30.0, 55.0, 7.5) for n in range(1, 11)]  # baseline days
    today = date(2026, 6, 10)
    raw   = readiness.compute_readiness(today, rows)
    trend = readiness.compute_readiness_trend(today, rows, lookback_days=0)
    assert trend == raw


def test_compute_readiness_trend_matches_manual_ema_recurrence():
    # Establish a stable baseline, then a bad/bad/good/bad pattern —
    # verify the EMA recurrence exactly, day by day.
    rows = [_day(n, 30.0, 55.0, 7.5) for n in range(1, 11)]        # days 1-10: baseline
    rows += [
        _day(11, 15.0, 65.0, 5.0),   # Sat — bad
        _day(12, 14.0, 66.0, 4.8),   # Sun — bad
        _day(13, 32.0, 54.0, 8.5),   # Mon — recovery day, good raw score
        _day(14, 16.0, 64.0, 5.2),   # Tue (today) — out again, bad
    ]
    alpha = 0.5
    expected_trend = None
    for n in range(1, 15):
        raw = readiness.compute_readiness(date(2026, 6, n), rows)
        if raw == readiness.NOT_COMPUTED:
            continue  # e.g. days 1-2: not enough history yet for any baseline
        expected_trend = (
            float(raw) if expected_trend is None
            else alpha * float(raw) + (1 - alpha) * expected_trend
        )
    expected_trend = round(expected_trend, 1)

    actual = readiness.compute_readiness_trend(date(2026, 6, 14), rows, alpha=alpha, lookback_days=13)
    assert actual == expected_trend


def test_compute_readiness_trend_does_not_fully_recover_after_one_good_day():
    # The user's exact scenario: two bad days, one recovery day, then
    # another bad night. Today's trend must stay well below the recovery
    # day's own raw score — recovery debt shouldn't clear in a single day.
    rows = [_day(n, 30.0, 55.0, 7.5) for n in range(1, 11)]
    rows += [
        _day(11, 15.0, 65.0, 5.0),
        _day(12, 14.0, 66.0, 4.8),
        _day(13, 32.0, 54.0, 8.5),
        _day(14, 16.0, 64.0, 5.2),
    ]
    raw_recovery_day = readiness.compute_readiness(date(2026, 6, 13), rows)
    trend_today       = readiness.compute_readiness_trend(date(2026, 6, 14), rows, lookback_days=13)

    assert trend_today != readiness.NOT_COMPUTED
    assert trend_today < float(raw_recovery_day) - 15  # meaningfully suppressed, not "recovered"


def test_compute_readiness_trend_skips_days_with_no_data_without_resetting():
    rows = [_day(n, 30.0, 55.0, 7.5) for n in range(1, 6)]
    # Gap: days 6-9 have no rows at all (e.g. wearable not worn).
    rows += [_day(10, 31.0, 55.0, 7.4)]
    trend = readiness.compute_readiness_trend(date(2026, 6, 10), rows, lookback_days=9)
    # Should equal the plain EMA of day-5 baseline reading folded with day 10
    # (the gap days contribute nothing, they don't zero the trend out).
    assert trend != readiness.NOT_COMPUTED
    assert trend > 90.0  # both real readings are essentially at baseline


def test_compute_readiness_trend_deterministic_for_same_inputs():
    rows = [_day(n, 30.0, 55.0, 7.5) for n in range(1, 11)]
    today = date(2026, 6, 10)
    r1 = readiness.compute_readiness_trend(today, rows)
    r2 = readiness.compute_readiness_trend(today, rows)
    assert r1 == r2


# ─── Oura readiness-contributor enrichment (2026-07-14) ───────────────────────
# Regression for the exact scenario that motivated this: on a day Oura's own
# readiness_score crashed to 49 (recovery_index cratering to 10), this app's
# HRV/RHR/Sleep-only formula scored 95.7+ because it had no visibility into
# temperature/recovery/prior-activity signals Oura already computes.

def _rows_with_contributors(n_history: int, today_extra: dict) -> list[dict]:
    """n_history days of perfect-baseline HRV/RHR/Sleep, then one more day
    ("today") carrying today_extra's Oura contributor fields on top of the
    same perfect HRV/RHR/Sleep readings — isolates the contributors' effect."""
    rows = [_day(n, 30.0, 55.0, 7.5) for n in range(1, n_history + 1)]
    today_row = _day(n_history + 1, 30.0, 55.0, 7.5)
    today_row.update(today_extra)
    rows.append(today_row)
    return rows


def test_compute_readiness_pulled_down_by_low_recovery_index_alone():
    # HRV/RHR/Sleep all at their own perfect baseline (~100 each), but
    # Oura's recovery_index contributor crashed to 10 that day.
    rows  = _rows_with_contributors(10, {"oura_recovery_index": 10.0})
    today = date(2026, 6, 11)
    score = readiness.compute_readiness(today, rows)
    assert score != readiness.NOT_COMPUTED
    # Previously (HRV/RHR/Sleep only) this would score ~100. With
    # recovery_index at 20% weight pulling in a 10, it must drop well below
    # what an HRV/RHR/Sleep-only score would give.
    assert score < 90.0


def test_compute_readiness_matches_manual_six_component_weighted_average():
    rows = _rows_with_contributors(10, {
        "oura_recovery_index": 40.0,
        "oura_body_temperature": 60.0,
        "oura_previous_day_activity": 80.0,
    })
    today = date(2026, 6, 11)
    score = readiness.compute_readiness(today, rows)

    hrv_base = readiness.hrv_baseline(rows)
    rhr_base = readiness.rhr_baseline(rows)
    sleep_base, _ = readiness.sleep_baseline(rows)
    hrv_s   = min(100.0, (30.0 / hrv_base) * 100.0)
    rhr_s   = min(100.0, (rhr_base / 55.0) * 100.0)
    sleep_s = min(100.0, (7.5 / sleep_base) * 100.0)

    expected = round(
        hrv_s * 0.25 + sleep_s * 0.20 + rhr_s * 0.15
        + 40.0 * 0.20 + 60.0 * 0.15 + 80.0 * 0.05,
        1,
    )
    assert score == expected


def test_compute_readiness_renormalises_when_only_some_contributors_present():
    # Only recovery_index present (body_temperature/previous_day_activity
    # missing that day) — must still compute, renormalising across whatever
    # is available rather than returning NOT_COMPUTED or silently zeroing
    # the missing ones out.
    rows  = _rows_with_contributors(10, {"oura_recovery_index": 50.0})
    today = date(2026, 6, 11)
    score = readiness.compute_readiness(today, rows)
    assert score != readiness.NOT_COMPUTED
    assert 0.0 <= score <= 100.0


def test_compute_readiness_computable_from_oura_contributors_alone():
    # Regression for the early-baseline-gate removal: a day with zero
    # HRV/RHR/Sleep history at all (so hrv_base/rhr_base/sleep_base are all
    # None) must still compute a score purely from Oura's contributors,
    # not bail out to NOT_COMPUTED just because the legacy 3 baselines
    # don't exist.
    rows = [{
        "date": "2026-06-01",
        "oura_recovery_index": 70.0,
        "oura_body_temperature": 90.0,
        "oura_previous_day_activity": 85.0,
    }]
    score = readiness.compute_readiness(date(2026, 6, 1), rows)
    assert score != readiness.NOT_COMPUTED
    expected = round((70.0 * 0.20 + 90.0 * 0.15 + 85.0 * 0.05) / (0.20 + 0.15 + 0.05), 1)
    assert score == expected


def test_compute_readiness_backward_compatible_without_oura_fields():
    # Rows with no oura_* keys at all (pre-enrichment shape) must still
    # compute — the new fields are absent, not present-and-zero.
    rows = [_day(n, 30.0, 55.0, 7.5) for n in range(1, 11)]
    today = date(2026, 6, 10)
    score = readiness.compute_readiness(today, rows)
    assert score != readiness.NOT_COMPUTED
    assert score > 90.0  # perfect baseline-matching day, no degraded contributors


# ─── Alcohol penalty (2026-07-14) ──────────────────────────────────────────────
# -5 points per 0.5 units (-10/unit), applied as a flat deduction after the
# weighted average — not folded in as another weighted component.

def test_alcohol_penalty_five_points_per_half_unit():
    rows = [_day(n, 30.0, 55.0, 7.5) for n in range(1, 10)]
    today_row = _day(10, 30.0, 55.0, 7.5)
    rows.append(today_row)
    today = date(2026, 6, 10)

    baseline_score = readiness.compute_readiness(today, rows)

    today_row["alcohol_units"] = 0.5
    score_half_unit = readiness.compute_readiness(today, rows)
    assert score_half_unit == round(baseline_score - 5.0, 1)

    today_row["alcohol_units"] = 2.0
    score_two_units = readiness.compute_readiness(today, rows)
    assert score_two_units == round(baseline_score - 20.0, 1)


def test_alcohol_penalty_floors_at_zero_not_negative():
    rows = [_day(n, 30.0, 55.0, 7.5) for n in range(1, 10)]
    today_row = _day(10, 30.0, 55.0, 7.5)
    today_row["alcohol_units"] = 20.0  # far more than enough to blow past 0
    rows.append(today_row)
    today = date(2026, 6, 10)

    score = readiness.compute_readiness(today, rows)
    assert score == 0.0


def test_alcohol_penalty_zero_units_is_a_no_op():
    rows = [_day(n, 30.0, 55.0, 7.5) for n in range(1, 10)]
    today_row = _day(10, 30.0, 55.0, 7.5)
    rows.append(today_row)
    today = date(2026, 6, 10)
    baseline_score = readiness.compute_readiness(today, rows)

    today_row["alcohol_units"] = 0.0
    score = readiness.compute_readiness(today, rows)
    assert score == baseline_score


def test_alcohol_penalty_flows_into_trend():
    # Since compute_readiness_trend() recomputes each day's raw score via
    # compute_readiness(), a boozy night must suppress the EMA trend too,
    # not just that single day's raw snapshot.
    rows = [_day(n, 30.0, 55.0, 7.5) for n in range(1, 10)]
    heavy_night = _day(10, 30.0, 55.0, 7.5)
    heavy_night["alcohol_units"] = 4.0
    rows.append(heavy_night)
    today = date(2026, 6, 10)

    trend_with_alcohol = readiness.compute_readiness_trend(today, rows, lookback_days=9)

    rows_sober = [_day(n, 30.0, 55.0, 7.5) for n in range(1, 11)]
    trend_sober = readiness.compute_readiness_trend(today, rows_sober, lookback_days=9)

    assert trend_with_alcohol < trend_sober - 15
