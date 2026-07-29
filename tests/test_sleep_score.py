"""Tests for services/sleep_score.py — the deterministic Sleep Score that
replaced the Home page's uncapped "% of baseline" figure
(services/dashboard.py::sleep_percent). Mirrors tests/test_readiness.py's
style: baseline helpers, then the composite's per-contributor behavior and
missing-data re-normalization.
"""

from datetime import date

from services import sleep_score


def _row(d: str, **fields) -> dict:
    return {"date": d, **fields}


# ─── _bedtime_minutes_since_noon ────────────────────────────────────────────

def test_bedtime_before_midnight_measured_from_same_day_noon():
    # 11:15 PM -> 11h15m after noon = 675 minutes
    m = sleep_score._bedtime_minutes_since_noon("2026-07-20T23:15:00+00:00")
    assert m == 675.0


def test_bedtime_after_midnight_continues_past_the_previous_evening():
    # 1:00 AM "belongs" to the night before -> anchored to noon the day
    # before, landing later than an 11:15 PM bedtime (780 > 675), not a
    # jump backwards the way naive clock-time comparison would produce.
    m = sleep_score._bedtime_minutes_since_noon("2026-07-21T01:00:00+00:00")
    assert m == 780.0


def test_bedtime_none_or_unparseable_returns_none():
    assert sleep_score._bedtime_minutes_since_noon(None) is None
    assert sleep_score._bedtime_minutes_since_noon("") is None
    assert sleep_score._bedtime_minutes_since_noon("not-a-datetime") is None


# ─── bedtime_baseline ────────────────────────────────────────────────────────

def test_bedtime_baseline_insufficient_nights_is_none():
    rows = [_row(f"2026-06-{i+1:02d}", oura_sleep_bedtime_start=f"2026-06-{i+1:02d}T23:00:00+00:00")
            for i in range(6)]  # minimum window is 7
    assert sleep_score.bedtime_baseline(rows) == (None, 0)


def test_bedtime_baseline_averages_exactly_seven_nights():
    rows = [_row(f"2026-06-{i+1:02d}", oura_sleep_bedtime_start=f"2026-06-{i+1:02d}T23:00:00+00:00")
            for i in range(7)]
    baseline, window = sleep_score.bedtime_baseline(rows)
    assert window == 7
    assert baseline == 660.0  # 11:00 PM every night -> 660 minutes since noon


# ─── compute_sleep_score ─────────────────────────────────────────────────────

def _baseline_rows(n: int = 10, hours: float = 8.0) -> list[dict]:
    return [_row(f"2026-06-{i+1:02d}", sleep_duration_hours=hours) for i in range(n)]


def test_no_bio_rows_is_not_computed():
    assert sleep_score.compute_sleep_score(date(2026, 7, 20), []) == sleep_score.NOT_COMPUTED


def test_no_row_for_the_date_is_not_computed():
    rows = _baseline_rows()
    assert sleep_score.compute_sleep_score(date(2026, 7, 25), rows) == sleep_score.NOT_COMPUTED


def test_row_present_but_no_sleep_fields_is_not_computed():
    rows = _baseline_rows() + [_row("2026-07-20")]
    assert sleep_score.compute_sleep_score(date(2026, 7, 20), rows) == sleep_score.NOT_COMPUTED


def test_total_sleep_alone_is_capped_at_100_when_sleeping_more_than_baseline():
    # Regression case for the bug this module replaced: sleeping longer than
    # your recent average must never push the score over 100.
    rows = _baseline_rows(hours=8.0) + [_row("2026-07-20", sleep_duration_hours=12.0)]
    score = sleep_score.compute_sleep_score(date(2026, 7, 20), rows)
    assert score == 100.0  # only contributor available (Total Sleep), capped


def test_total_sleep_scales_linearly_below_baseline():
    rows = _baseline_rows(hours=8.0) + [_row("2026-07-20", sleep_duration_hours=6.0)]
    score = sleep_score.compute_sleep_score(date(2026, 7, 20), rows)
    # Today's own 6h reading also feeds its own baseline average (last 7 of
    # [8.0]*10 + [6.0] = six 8.0s + one 6.0 -> baseline 7.714...), same
    # behavior as readiness.sleep_baseline -- not a flat 6/8.
    assert score == 77.8


def test_full_good_night_scores_near_100():
    rows = _baseline_rows(hours=8.0) + [_row(
        "2026-07-20",
        sleep_duration_hours=8.0,
        oura_sleep_efficiency=95.0,
        oura_sleep_total_seconds=28800.0,   # 8h
        oura_sleep_rem_seconds=6336.0,      # 22% of total -> top of REM band
        oura_sleep_deep_seconds=4320.0,     # 15% of total -> top of Deep band
        oura_sleep_restless_periods=1.0,    # 0.125/hr -> well under the 2/hr floor
        oura_sleep_latency_seconds=900.0,   # 15 min -> dead centre of ideal band
        oura_sleep_bedtime_start="2026-07-20T23:00:00+00:00",
    )]
    score = sleep_score.compute_sleep_score(date(2026, 7, 20), rows)
    assert score == 98.9  # timing excluded (no 7-night bedtime baseline yet); efficiency (95) the rest


def test_full_bad_night_scores_low():
    rows = _baseline_rows(hours=8.0) + [_row(
        "2026-07-20",
        sleep_duration_hours=4.0,           # 50% of an 8h baseline
        oura_sleep_efficiency=60.0,
        oura_sleep_total_seconds=14400.0,   # 4h
        oura_sleep_rem_seconds=0.0,         # 0% -> below REM floor
        oura_sleep_deep_seconds=0.0,        # 0% -> below Deep floor
        oura_sleep_restless_periods=48.0,   # 12/hr -> at/over the restless ceiling
        oura_sleep_latency_seconds=0.0,     # fell asleep instantly -> latency floor
        oura_sleep_bedtime_start="2026-07-21T03:00:00+00:00",  # far off an 11 PM baseline
    )]
    score = sleep_score.compute_sleep_score(date(2026, 7, 20), rows)
    # Today's own 4h reading also feeds its own baseline average (same
    # behavior as readiness.sleep_baseline), pulling it below a flat 8.0 --
    # total_sleep and efficiency are the only nonzero contributors, timing
    # excluded (no 7-night bedtime baseline yet), re-normalized over the 6
    # available weights.
    assert score == 26.8


def test_missing_contributor_renormalizes_rather_than_dragging_score_down():
    # Same "perfect" inputs as the good-night test but efficiency is simply
    # absent (e.g. a payload gap) -- the remaining 6 contributors should
    # re-normalise the weights among themselves rather than being averaged
    # against a phantom zero.
    rows = _baseline_rows(hours=8.0) + [_row(
        "2026-07-20",
        sleep_duration_hours=8.0,
        oura_sleep_total_seconds=28800.0,
        oura_sleep_rem_seconds=6336.0,
        oura_sleep_deep_seconds=4320.0,
        oura_sleep_restless_periods=1.0,
        oura_sleep_latency_seconds=900.0,
        oura_sleep_bedtime_start="2026-07-20T23:00:00+00:00",
    )]
    score = sleep_score.compute_sleep_score(date(2026, 7, 20), rows)
    assert score == 100.0  # every available contributor is maxed


def test_latency_too_fast_is_penalised_same_as_too_slow():
    base = _baseline_rows(hours=8.0)
    fast = base + [_row("2026-07-20", oura_sleep_latency_seconds=0.0)]
    slow = base + [_row("2026-07-20", oura_sleep_latency_seconds=60 * 60.0)]  # 60 min
    ideal = base + [_row("2026-07-20", oura_sleep_latency_seconds=15 * 60.0)]  # 15 min
    assert sleep_score.compute_sleep_score(date(2026, 7, 20), fast) == 0.0
    assert sleep_score.compute_sleep_score(date(2026, 7, 20), slow) == 0.0
    assert sleep_score.compute_sleep_score(date(2026, 7, 20), ideal) == 100.0
