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


# ─── sleep_debt_hours ───────────────────────────────────────────────────────
# Moved here from services/scheduling.py 2026-07-30, alongside its constants
# (SLEEP_DEBT_THRESHOLD_HOURS/SLEEP_DEBT_WINDOW_DAYS) — compute_readiness now
# uses this as its own sleep_debt component, and services.scheduling already
# imports readiness for sleep_baseline, so having readiness depend back on
# scheduling would be circular.

def test_sleep_debt_hours_sums_trailing_window_shortfall_against_baseline():
    # 7 clean nights ending at for_date: three short (4.0h) nights and four
    # long (11.0h) nights -> baseline (mean) = (3*4 + 4*11)/7 = 8.0h. Debt =
    # sum of shortfalls below the mean only (overages don't offset it)
    # = 3 * (8.0 - 4.0) = 12.0.
    rows = [
        {"date": "2026-07-01", "sleep_duration_hours": 4.0},
        {"date": "2026-07-02", "sleep_duration_hours": 4.0},
        {"date": "2026-07-03", "sleep_duration_hours": 4.0},
        {"date": "2026-07-04", "sleep_duration_hours": 11.0},
        {"date": "2026-07-05", "sleep_duration_hours": 11.0},
        {"date": "2026-07-06", "sleep_duration_hours": 11.0},
        {"date": "2026-07-07", "sleep_duration_hours": 11.0},
    ]
    for_date = date(2026, 7, 7)
    assert readiness.sleep_debt_hours(rows, for_date) == 12.0


def test_sleep_debt_hours_reuses_sleep_baseline_not_a_duplicate_computation():
    # Same rows sleep_baseline would compute a baseline from directly --
    # sleep_debt_hours must agree with it exactly, not some separately-
    # derived figure.
    rows = [
        {"date": f"2026-06-{d:02d}", "sleep_duration_hours": h}
        for d, h in zip(range(1, 8), [6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0])
    ]
    for_date = date(2026, 6, 7)
    baseline, _window = readiness.sleep_baseline(rows)
    expected_debt = round(sum(max(0.0, baseline - h) for h in [6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0]), 2)
    assert readiness.sleep_debt_hours(rows, for_date) == expected_debt


def test_sleep_debt_hours_none_when_baseline_cannot_be_computed():
    # Only 3 clean nights -- sleep_baseline needs >= 7 to trust a baseline.
    # None (not 0.0!) -- a "can't compute" state must never look identical
    # to "we checked and there's genuinely no deficit," since compute_
    # readiness relies on that distinction to exclude (not fake-perfect-
    # score) this component when there isn't enough history yet.
    rows = [
        {"date": "2026-07-05", "sleep_duration_hours": 4.0},
        {"date": "2026-07-06", "sleep_duration_hours": 4.0},
        {"date": "2026-07-07", "sleep_duration_hours": 4.0},
    ]
    assert readiness.sleep_debt_hours(rows, date(2026, 7, 7)) is None


def test_sleep_debt_hours_ignores_rows_after_for_date():
    # A future row (relative to for_date) must never inflate/deflate a past
    # debt figure -- mirrors compute_readiness's own "rows on or before
    # for_date only" filtering.
    rows = [
        {"date": "2026-07-01", "sleep_duration_hours": 4.0},
        {"date": "2026-07-02", "sleep_duration_hours": 4.0},
        {"date": "2026-07-03", "sleep_duration_hours": 4.0},
        {"date": "2026-07-04", "sleep_duration_hours": 11.0},
        {"date": "2026-07-05", "sleep_duration_hours": 11.0},
        {"date": "2026-07-06", "sleep_duration_hours": 11.0},
        {"date": "2026-07-07", "sleep_duration_hours": 11.0},
        {"date": "2026-07-08", "sleep_duration_hours": 1.0},  # after for_date
    ]
    assert readiness.sleep_debt_hours(rows, date(2026, 7, 7)) == 12.0


def test_sleep_debt_hours_skips_missing_nights_in_the_window():
    # 7 clean nights (all 8.0h -> baseline 8.0) with one calendar date inside
    # the trailing 7-day window (07-05) having no row at all. A missing night
    # must be skipped, not treated as 0h -- if it were, this would report an
    # 8.0h debt (max(0, 8.0 - 0)) instead of the correct 0.0.
    rows = [
        {"date": "2026-06-30", "sleep_duration_hours": 8.0},
        {"date": "2026-07-01", "sleep_duration_hours": 8.0},
        {"date": "2026-07-02", "sleep_duration_hours": 8.0},
        {"date": "2026-07-03", "sleep_duration_hours": 8.0},
        {"date": "2026-07-04", "sleep_duration_hours": 8.0},
        # 2026-07-05 missing entirely.
        {"date": "2026-07-06", "sleep_duration_hours": 8.0},
        {"date": "2026-07-07", "sleep_duration_hours": 8.0},
    ]
    assert readiness.sleep_debt_hours(rows, date(2026, 7, 7)) == 0.0


# ─── compute_readiness: sleep_debt component (2026-07-30) ─────────────────────
# Added because same-night sleep_s alone missed a genuine multi-night
# deficit that was individually "not terrible" each night -- e.g. a weekend
# of 5-6h nights, none short enough to trip sleep_s's own floor, that still
# adds up to real accumulated debt.

def test_compute_readiness_high_sleep_debt_drags_score_down():
    # 7 nights at baseline (8.0h), then today itself also logs a poor-but-
    # not-catastrophic night -- isolate sleep_debt_s's effect by comparing
    # against the same setup with a full night's sleep instead.
    good_rows = [_day(n, 30.0, 55.0, 8.0) for n in range(1, 8)]
    good_rows.append(_day(8, 30.0, 55.0, 8.0))
    today = date(2026, 6, 8)
    good_score = readiness.compute_readiness(today, good_rows)

    debt_rows = [_day(n, 30.0, 55.0, 8.0) for n in range(1, 8)]
    debt_rows.append(_day(8, 30.0, 55.0, 4.5))  # today: short night
    debt_score = readiness.compute_readiness(today, debt_rows)

    assert debt_score < good_score


def test_compute_readiness_sleep_debt_none_is_excluded_not_defaulted():
    # Only 3 nights of history -- sleep_baseline (and therefore sleep_debt_
    # hours) can't be trusted yet. The component must be excluded from the
    # weighted average (renormalised away), not silently treated as a
    # perfect 100 or a zero.
    rows = [_day(n, 30.0, 55.0, 7.5) for n in range(1, 4)]
    today = date(2026, 6, 3)
    assert readiness.sleep_debt_hours(rows, today) is None
    score = readiness.compute_readiness(today, rows)
    assert score != readiness.NOT_COMPUTED
    # HRV/RHR baselines also can't be trusted yet with only 3 days below
    # _MIN_DAYS... actually 3 == _MIN_DAYS, so those ARE trusted; sleep_s
    # itself needs >= 7 clean nights same as sleep_debt, so both are
    # excluded here -- a perfect HRV/RHR-only day still scores high.
    assert score > 90.0


def _rows_with_trailing_short_nights(n_good: int, n_short: int, short_hours: float) -> tuple[list[dict], date]:
    """n_good nights at an 8.0h baseline (days 1..n_good of June 2026),
    followed immediately by n_short nights at short_hours -- a good-night
    pool large enough that the short nights don't drag the baseline itself
    down to meet them (unlike a small pool, where "debt" and "baseline"
    chase each other and a hand-predicted debt figure becomes unreliable).
    Returns (rows, last_date) -- last_date is the final short night, i.e.
    "today" for a caller evaluating debt/readiness as of that point.
    n_good + n_short must stay <= 28 to keep every date inside June."""
    rows = [_day(n, 30.0, 55.0, 8.0) for n in range(1, n_good + 1)]
    rows += [_day(n_good + n, 30.0, 55.0, short_hours) for n in range(1, n_short + 1)]
    return rows, date(2026, 6, n_good + n_short)


def test_compute_readiness_sleep_debt_clamps_at_zero_beyond_the_threshold():
    # Once cumulative debt reaches SLEEP_DEBT_THRESHOLD_HOURS, sleep_debt_s
    # bottoms out at 0 -- verified by manually reproducing compute_
    # readiness's weighted average with sleep_debt_s forced to 0.0 and
    # confirming it matches exactly (rather than comparing two black-box
    # scenarios, where sleep_s -- a different component, same 30.0/55.0/
    # 8.0-baseline family but its OWN baseline shifts with the fixture --
    # would also legitimately differ and make the comparison unreliable).
    # 25 good nights keep the baseline close to 8.0h despite 3 trailing
    # short (4.0h) nights inside the 28-night window sleep_baseline uses.
    rows, today = _rows_with_trailing_short_nights(25, 3, 4.0)
    debt = readiness.sleep_debt_hours(rows, today)
    assert debt is not None and debt >= readiness.SLEEP_DEBT_THRESHOLD_HOURS

    score = readiness.compute_readiness(today, rows)

    hrv_base = readiness.hrv_baseline(rows)
    rhr_base = readiness.rhr_baseline(rows)
    sleep_base, _ = readiness.sleep_baseline(rows)
    hrv_s   = min(100.0, (30.0 / hrv_base) * 100.0)
    rhr_s   = min(100.0, (rhr_base / 55.0) * 100.0)
    sleep_s = min(100.0, (4.0 / sleep_base) * 100.0)  # today's own short night
    sleep_debt_s = 0.0  # clamped -- debt is well past the threshold

    total_w = 0.225 + 0.18 + 0.135 + 0.10
    expected = round(
        (hrv_s * 0.225 + sleep_s * 0.18 + rhr_s * 0.135 + sleep_debt_s * 0.10) / total_w,
        1,
    )
    assert score == expected


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


def test_compute_readiness_matches_manual_seven_component_weighted_average():
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
    # Every row in this fixture (including "today") sleeps exactly 7.5h --
    # matches the baseline exactly, so trailing 7-night debt is 0.0 and
    # sleep_debt_s scores a perfect 100.
    debt = readiness.sleep_debt_hours(rows, today)
    assert debt == 0.0
    sleep_debt_s = 100.0

    expected = round(
        hrv_s * 0.225 + sleep_s * 0.18 + rhr_s * 0.135
        + 40.0 * 0.18 + 60.0 * 0.135 + 80.0 * 0.045
        + sleep_debt_s * 0.10,
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
    # No sleep history at all (single row) -> sleep_debt_s is also None/
    # excluded here, same as the legacy HRV/RHR/Sleep baselines -- only the
    # three Oura contributors renormalise against each other.
    expected = round((70.0 * 0.18 + 90.0 * 0.135 + 85.0 * 0.045) / (0.18 + 0.135 + 0.045), 1)
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


# ─── readiness_breakdown — the seven components made visible ─────────────────

def _full_rows(n: int = 30) -> list[dict]:
    """Ascending rows where every component is scorable."""
    return [{
        "date": f"2026-07-{i + 1:02d}",
        "hrv_ms": 40.0, "resting_heart_rate": 55.0, "sleep_duration_hours": 7.5,
        "oura_recovery_index": 80.0, "oura_body_temperature": 90.0,
        "oura_previous_day_activity": 70.0,
    } for i in range(n)]


def test_weights_sum_to_one():
    """If they ever don't, renormalisation quietly changes meaning: a day with
    every component present would no longer be scored on the full weight."""
    assert abs(sum(readiness._WEIGHTS.values()) - 1.0) < 1e-9


def test_display_order_and_summation_order_hold_the_same_seven():
    """They are deliberately different orders (see _SUM_ORDER's comment) but
    must never drift into different SETS."""
    assert set(readiness.COMPONENT_ORDER) == set(readiness._SUM_ORDER)
    assert set(readiness.COMPONENT_ORDER) == set(readiness._WEIGHTS)
    assert set(readiness.COMPONENT_ORDER) == set(readiness.COMPONENT_LABELS)
    assert len(readiness.COMPONENT_ORDER) == 7


def test_summation_order_is_not_display_order():
    """Pins the thing most likely to be 'tidied' by a future reader. Float
    addition is not associative, so aligning these would risk moving the
    composite in its last decimal — which is user-visible and feeds
    engine.traffic_light."""
    assert readiness._SUM_ORDER != readiness.COMPONENT_ORDER


def test_breakdown_score_equals_compute_readiness():
    rows = _full_rows()
    d = date(2026, 7, 30)
    assert readiness.readiness_breakdown(d, rows)["score"] == readiness.compute_readiness(d, rows)


def test_breakdown_always_reports_all_seven_components():
    """A component that could not be computed keeps its row — on that panel
    the gap is the most informative thing on screen."""
    rows = [{"date": "2026-07-01", "oura_recovery_index": 80.0}]
    b = readiness.readiness_breakdown(date(2026, 7, 1), rows)
    assert len(b["components"]) == 7
    assert [c["key"] for c in b["components"]] == list(readiness.COMPONENT_ORDER)


def test_an_unscorable_component_contributes_nothing_and_is_listed_missing():
    rows = [{"date": "2026-07-01", "oura_recovery_index": 80.0}]
    b = readiness.readiness_breakdown(date(2026, 7, 1), rows)
    hrv = next(c for c in b["components"] if c["key"] == "hrv")
    assert hrv["score"] is None
    assert hrv["effective_weight"] == 0.0
    assert hrv["contribution"] is None
    assert "hrv" in b["missing"]


def test_available_weight_reflects_only_scored_components():
    rows = [{"date": "2026-07-01", "oura_recovery_index": 80.0,
             "oura_body_temperature": 90.0}]
    b = readiness.readiness_breakdown(date(2026, 7, 1), rows)
    assert abs(b["available_weight"] - (0.18 + 0.135)) < 1e-9


def test_effective_weights_of_scored_components_sum_to_one():
    """Renormalisation is what lets a partial day still produce a 0-100."""
    rows = [{"date": "2026-07-01", "oura_recovery_index": 80.0,
             "oura_body_temperature": 90.0}]
    b = readiness.readiness_breakdown(date(2026, 7, 1), rows)
    eff = sum(c["effective_weight"] for c in b["components"] if c["score"] is not None)
    assert abs(eff - 1.0) < 1e-4


def test_no_data_returns_all_seven_unscored_rather_than_an_empty_list():
    b = readiness.readiness_breakdown(date(2026, 7, 1), [])
    assert b["score"] == readiness.NOT_COMPUTED
    assert len(b["components"]) == 7
    assert b["missing"] == list(readiness.COMPONENT_ORDER)
    assert b["available_weight"] == 0.0


# ─── Alcohol is reported, never rendered as a component ──────────────────────

def test_alcohol_is_not_one_of_the_components():
    rows = _full_rows()
    for r in rows:
        r["alcohol_units"] = 2.0
    b = readiness.readiness_breakdown(date(2026, 7, 30), rows)
    assert len(b["components"]) == 7
    assert all("alcohol" not in c["key"] for c in b["components"])


def test_alcohol_penalty_points_are_reported_separately():
    rows = _full_rows()
    for r in rows:
        r["alcohol_units"] = 1.5
    b = readiness.readiness_breakdown(date(2026, 7, 30), rows)
    assert b["alcohol_units"] == 1.5
    assert b["alcohol_penalty_points"] == 15.0


def test_contributions_exceed_the_score_by_exactly_the_alcohol_penalty():
    """The reason the caption exists: without it the seven rows cannot be
    reconciled with the number above them."""
    rows = _full_rows()
    for r in rows:
        r["alcohol_units"] = 1.0
    b = readiness.readiness_breakdown(date(2026, 7, 30), rows)
    total = sum(c["contribution"] for c in b["components"] if c["contribution"] is not None)
    assert abs((total - b["alcohol_penalty_points"]) - b["score"]) < 0.15


def test_a_dry_day_reports_no_penalty():
    b = readiness.readiness_breakdown(date(2026, 7, 30), _full_rows())
    assert b["alcohol_penalty_points"] == 0.0


# ─── The refactor must not have moved compute_readiness ──────────────────────

def test_component_scores_and_compute_readiness_agree_on_a_partial_day():
    """_component_scores was split out of compute_readiness; this pins that
    both still walk the same seven in the same order."""
    rows = _full_rows()
    rows[-1]["hrv_ms"] = None
    rows[-1]["oura_body_temperature"] = None
    d = date(2026, 7, 30)
    b = readiness.readiness_breakdown(d, rows)
    assert b["score"] == readiness.compute_readiness(d, rows)
    assert set(b["missing"]) == {"hrv", "body_temp"}
