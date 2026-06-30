"""
readiness.py — Daily Readiness Score.

Computes a 0-100 readiness score from biometric data using adaptive rolling
baselines. Returns NOT_COMPUTED when insufficient data exists.

Baseline logic
--------------
HRV / RHR  : 14-day average until 28 days of data are available; 28-day thereafter.
Sleep      : Progressive — 7 → 14 → 28 → 56 nights as clean data accumulates.
             Outliers <4 h or >11 h are excluded from baseline computation.

Weights (normalised when individual metrics are missing)
--------------------------------------------------------
HRV    40%   primary autonomic recovery marker
Sleep  35%   vs personal progressive baseline
RHR    25%   supporting cardiovascular indicator
"""

from __future__ import annotations
from datetime import date

NOT_COMPUTED = "NOT_COMPUTED"

_SLEEP_MIN_H    = 4.0
_SLEEP_MAX_H    = 11.0
_MIN_DAYS       = 14          # minimum observations before HRV/RHR baseline is trusted
_MIN_SLEEP      = 7           # minimum clean nights before sleep baseline is trusted
_SLEEP_WINDOWS  = (7, 14, 28, 56)


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
    """14-day average until 28 days available; 28-day thereafter."""
    vals = [float(r["hrv_ms"]) for r in rows if r.get("hrv_ms") is not None]
    n = len(vals)
    if n < _MIN_DAYS:
        return None
    window = 28 if n >= 28 else 14
    return round(sum(vals[-window:]) / window, 2)


def rhr_baseline(rows: list[dict]) -> float | None:
    """14-day average until 28 days available; 28-day thereafter."""
    vals = [
        float(r["resting_heart_rate"])
        for r in rows
        if r.get("resting_heart_rate") is not None
    ]
    n = len(vals)
    if n < _MIN_DAYS:
        return None
    window = 28 if n >= 28 else 14
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

    if hrv_base is None and rhr_base is None and sleep_base is None:
        return NOT_COMPUTED

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

    # ── Weighted average (re-normalise when metrics are missing) ──────────────
    candidates = [(hrv_s, 0.40), (sleep_s, 0.35), (rhr_s, 0.25)]
    available  = [(s, w) for s, w in candidates if s is not None]

    if not available:
        return NOT_COMPUTED

    total_w      = sum(w for _, w in available)
    weighted_sum = sum(s * (w / total_w) for s, w in available)

    return round(weighted_sum, 1)
