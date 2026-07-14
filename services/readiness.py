"""
readiness.py — Daily Readiness Score.

Computes a 0-100 readiness score from biometric data using adaptive rolling
baselines. Returns NOT_COMPUTED when insufficient data exists.

Baseline logic
--------------
HRV / RHR  : Average of whatever history exists, up to a 28-day cap, once at
             least 3 observations are available. (Previously required 14
             observations before trusting a baseline at all — with sparse
             wearable history this silently dropped HRV out of
             compute_readiness's weighted average entirely, letting RHR/Sleep
             alone dictate the score. See 2026-07-14 fix.)
Sleep      : Progressive — 7 → 14 → 28 → 56 nights as clean data accumulates.
             Outliers <4 h or >11 h are excluded from baseline computation.

Weights (normalised when individual metrics are missing)
--------------------------------------------------------
HRV                       25%   primary autonomic recovery marker (personal-baseline ratio)
Sleep                     20%   vs personal progressive baseline
RHR                       15%   supporting cardiovascular indicator (personal-baseline ratio)
Recovery Index (Oura)     20%   Oura's own overnight-recovery contributor (0-100, pre-scored)
Body Temperature (Oura)   15%   Oura's own temperature-deviation contributor (0-100, pre-scored)
Previous Day Activity (Oura) 5% Oura's own training-load-spillover contributor (0-100, pre-scored)

2026-07-14: added the three Oura contributor sub-scores above. HRV/Sleep/RHR
were re-weighted down (was 40/35/25) to make room rather than bolted on
alongside unchanged — Recovery Index in particular tracked a real same-day
crash (Oura readiness_score 49) that HRV/RHR/Sleep alone missed entirely
because HRV data was absent that day. Unlike HRV/RHR (ratio-to-baseline,
computed here) these three are Oura-exclusive and already 0-100-scored by
Oura itself — no baseline math needed, just clamped and used directly.
Garmin has no equivalent, so they're simply absent (None) on any day Oura
itself didn't compute them.

Trend (compute_readiness_trend, 2026-07-14)
--------------------------------------------
compute_readiness() alone scores each day in isolation, so a recovery day
right after a bad stretch reads as "fully recovered" even when it isn't.
compute_readiness_trend() carries recovery debt forward via exponential
smoothing (same e^(-lambda*t)-style decay used for injury_weight in
engine.py): trend = alpha*today's raw score + (1-alpha)*yesterday's trend.
One good day only partially repays a multi-day deficit.

Alcohol penalty (2026-07-14)
-----------------------------
Self-reported alcohol units from the morning check-in apply a flat point
deduction AFTER the weighted average above, rather than being folded in as
another weighted component: -5 points per 0.5 units (-10/unit), floored at
0. A flat subtraction rather than a component keeps the penalty's size
exact and undiluted — a weighted component would get re-normalised away
(or amplified) depending on how many other metrics are missing that day,
which a fixed "you drank, this costs you N points" rule shouldn't do.
Because this lives inside compute_readiness(), it automatically flows into
compute_readiness_trend() (the EMA walk recomputes each day's raw score,
alcohol penalty included) and engine.readiness_training_modifier() without
either needing its own change.
"""

from __future__ import annotations
from datetime import date, timedelta

NOT_COMPUTED = "NOT_COMPUTED"

_SLEEP_MIN_H    = 4.0
_SLEEP_MAX_H    = 11.0
_MIN_DAYS       = 3           # minimum observations before HRV/RHR baseline is trusted
_HRV_RHR_WINDOW_CAP = 28      # baseline uses up to this many most-recent observations
_MIN_SLEEP      = 7           # minimum clean nights before sleep baseline is trusted
_SLEEP_WINDOWS  = (7, 14, 28, 56)

_TREND_ALPHA         = 0.5    # weight given to each new day's raw score in the EMA
_TREND_LOOKBACK_DAYS = 14     # days walked forward to seed/accumulate the trend

_ALCOHOL_PENALTY_PER_UNIT = 10.0   # points deducted per unit (-5 per 0.5 units)


# ─── Exported baseline helpers ────────────────────────────────────────────────

def sleep_baseline(rows: list[dict]) -> tuple[float | None, int]:
    """
    Compute the progressive personal sleep baseline.

    Args:
        rows: biometric rows sorted ascending by date; must have 'sleep_duration_hours'.

    Returns:
        (baseline_hours, window_nights_used) — (None, 0) when insufficient data.

    Outliers outside [4, 11] h are excluded before averaging.
    Longest available window among 7, 14, 28, 56 is used.
    """
    clean = [
        float(r["sleep_duration_hours"])
        for r in rows
        if r.get("sleep_duration_hours") is not None
        and _SLEEP_MIN_H <= float(r["sleep_duration_hours"]) <= _SLEEP_MAX_H
    ]
    n = len(clean)
    for window in reversed(_SLEEP_WINDOWS):   # 56 → 28 → 14 → 7
        if n >= window:
            return round(sum(clean[-window:]) / window, 2), window
    return None, 0


def hrv_baseline(rows: list[dict]) -> float | None:
    """Average of up to the last 28 observations; requires >= _MIN_DAYS to trust."""
    vals = [float(r["hrv_ms"]) for r in rows if r.get("hrv_ms") is not None]
    n = len(vals)
    if n < _MIN_DAYS:
        return None
    window = min(n, _HRV_RHR_WINDOW_CAP)
    return round(sum(vals[-window:]) / window, 2)


def rhr_baseline(rows: list[dict]) -> float | None:
    """Average of up to the last 28 observations; requires >= _MIN_DAYS to trust."""
    vals = [
        float(r["resting_heart_rate"])
        for r in rows
        if r.get("resting_heart_rate") is not None
    ]
    n = len(vals)
    if n < _MIN_DAYS:
        return None
    window = min(n, _HRV_RHR_WINDOW_CAP)
    return round(sum(vals[-window:]) / window, 2)


# ─── Main computation ─────────────────────────────────────────────────────────

def compute_readiness(
    for_date: date | None = None,
    bio_rows: list[dict] | None = None,
) -> float | str:
    """
    Compute a 0–100 readiness score for for_date.

    Args:
        for_date : Target date. Defaults to today.
        bio_rows : Biometric rows from sync_sheets.get_biometric_rolling(),
                   sorted ascending by date.

    Returns:
        float        — readiness score 0–100
        NOT_COMPUTED — insufficient data for any calculation
    """
    if not bio_rows:
        return NOT_COMPUTED

    for_date = for_date or date.today()
    date_str  = str(for_date)

    # Only use rows on or before for_date so historical views are accurate
    rows_to_date = [r for r in bio_rows if r.get("date") and r["date"] <= date_str]
    if not rows_to_date:
        return NOT_COMPUTED

    today_row = next((r for r in rows_to_date if r["date"] == date_str), None)

    # ── Baselines ─────────────────────────────────────────────────────────────
    hrv_base            = hrv_baseline(rows_to_date)
    rhr_base            = rhr_baseline(rows_to_date)
    sleep_base, _win    = sleep_baseline(rows_to_date)

    # No early bail-out on baselines alone: the Oura contributor sub-scores
    # below need no baseline at all, so a day could still be computable from
    # those even with hrv_base/rhr_base/sleep_base all None. The bottom
    # `if not available` check is the real gate — covers all 6 candidates.

    # ── Today's readings ──────────────────────────────────────────────────────
    def _get(key):
        if today_row is None or today_row.get(key) is None:
            return None
        return float(today_row[key])

    today_hrv   = _get("hrv_ms")
    today_rhr   = _get("resting_heart_rate")
    today_sleep = _get("sleep_duration_hours")

    # ── Per-metric 0–100 component scores ─────────────────────────────────────
    hrv_s = (
        min(100.0, (today_hrv / hrv_base) * 100.0)
        if today_hrv is not None and hrv_base and hrv_base > 0
        else None
    )
    rhr_s = (
        # Lower RHR = better; elevated RHR compresses the score proportionally
        min(100.0, (rhr_base / today_rhr) * 100.0)
        if today_rhr is not None and rhr_base and rhr_base > 0
        else None
    )
    if today_sleep is not None and sleep_base and sleep_base > 0:
        sleep_s = 0.0 if today_sleep < _SLEEP_MIN_H else min(100.0, (today_sleep / sleep_base) * 100.0)
    else:
        sleep_s = None

    # Oura's own contributor sub-scores — already 0-100 against Oura's own
    # personal-norm model, so no baseline computation here, just clamp.
    def _clamped100(key):
        v = _get(key)
        return None if v is None else max(0.0, min(100.0, v))

    recovery_s       = _clamped100("oura_recovery_index")
    body_temp_s      = _clamped100("oura_body_temperature")
    prev_activity_s  = _clamped100("oura_previous_day_activity")

    # ── Weighted average (re-normalise when metrics are missing) ──────────────
    candidates = [
        (hrv_s, 0.25), (sleep_s, 0.20), (rhr_s, 0.15),
        (recovery_s, 0.20), (body_temp_s, 0.15), (prev_activity_s, 0.05),
    ]
    available  = [(s, w) for s, w in candidates if s is not None]

    if not available:
        return NOT_COMPUTED

    total_w      = sum(w for _, w in available)
    weighted_sum = sum(s * (w / total_w) for s, w in available)

    # ── Alcohol penalty — flat deduction, not a weighted component ────────────
    today_alcohol = _get("alcohol_units")
    if today_alcohol:
        weighted_sum = max(0.0, weighted_sum - today_alcohol * _ALCOHOL_PENALTY_PER_UNIT)

    return round(weighted_sum, 1)


# ─── Trend — carries recovery debt forward across days ────────────────────────

def compute_readiness_trend(
    for_date: date | None = None,
    bio_rows: list[dict] | None = None,
    alpha: float = _TREND_ALPHA,
    lookback_days: int = _TREND_LOOKBACK_DAYS,
) -> float | str:
    """
    Exponentially-weighted readiness trend for for_date.

    Unlike compute_readiness() (a same-day snapshot), this walks forward
    day by day from (for_date - lookback_days) through for_date, folding
    each day's raw compute_readiness() score into a running EMA:
    trend = alpha*today's raw + (1-alpha)*yesterday's trend.

    A single good day only partially repays a multi-day deficit — e.g. two
    low-readiness days followed by one strong recovery day still returns a
    trend well below the recovery day's own raw score, and a bad night right
    after keeps it suppressed rather than resetting to that day's snapshot.

    Days where compute_readiness() returns NOT_COMPUTED (no data that day)
    are skipped — they neither seed nor update the trend.

    Returns NOT_COMPUTED if no day in the lookback window has a computed
    raw score.
    """
    if not bio_rows:
        return NOT_COMPUTED

    for_date = for_date or date.today()
    trend: float | None = None

    for delta in range(lookback_days, -1, -1):   # oldest -> newest, ending at for_date
        d   = for_date - timedelta(days=delta)
        raw = compute_readiness(d, bio_rows)
        if raw == NOT_COMPUTED:
            continue
        trend = float(raw) if trend is None else alpha * float(raw) + (1 - alpha) * trend

    return round(trend, 1) if trend is not None else NOT_COMPUTED
