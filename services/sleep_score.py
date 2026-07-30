"""
services/sleep_score.py — Deterministic Sleep Score, our own composite
mirroring Oura's 7 real contributors (see services/repository.py's
_oura_daily_row: total_sleep, efficiency, restfulness, rem_sleep,
deep_sleep, latency, timing) — computed from the raw sleep-architecture
data Oura already reports (services/models.py's oura_sleep_* fields), not
from Oura's own pre-computed score or contributor sub-scores. Same
philosophy as services/readiness.py::compute_readiness: build our own
0-100 composite from raw values rather than relaying a third party's
finished number.

All 7 contributors are Oura-exclusive (no Garmin equivalent — same
situation as readiness.py's oura_recovery_index trio), sourced from the
*main* sleep period Oura reports (services.biometrics.pick_main_sleep_period
already picked it out, before this data reaches here). The whole score is
NOT_COMPUTED on any day Oura has no sleep-period reading.

Weights and band thresholds below are this project's own reasoned
defaults, not published Oura constants — Oura doesn't disclose their exact
algorithm. Each is called out so they're easy to recalibrate later against
real logged nights, same spirit as the Garmin HRV field-shape caveat in
services/repository.py::_garmin_daily_row.

Weights
-------
Total Sleep   25%   blended sleep_duration_hours vs personal baseline (capped at 100)
Efficiency    20%   Oura's own raw efficiency reading (already 0-100), used directly
REM Sleep     15%   rem seconds as % of total sleep, ramped over an ideal band
Deep Sleep    15%   deep seconds as % of total sleep, ramped over an ideal band
Restfulness   10%   restless periods per hour of sleep, inverted — UNVERIFIED unit,
                    see caveat below
Latency       10%   seconds to fall asleep, banded (too fast or too slow both penalised)
Timing         5%   bedtime deviation from your own rolling-average bedtime

Restfulness caveat: Oura's `restless_periods` field's exact unit/scale
isn't verified against a live payload (same caveat class as the Garmin HRV
field mapping) — the per-hour rate and band below are a starting guess,
worth confirming against a real logged night before trusting at the
margins.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from services import readiness

NOT_COMPUTED = readiness.NOT_COMPUTED

_BEDTIME_WINDOWS = (7, 14, 28, 56)   # same progressive schedule as sleep_baseline

# (x, y) knots, piecewise-linear, clamped to the nearest endpoint outside range.
_REM_PCT_BAND  = ((10.0, 0.0), (22.0, 100.0))               # % of total sleep
_DEEP_PCT_BAND = ((5.0, 0.0), (15.0, 100.0))                # % of total sleep
_LATENCY_BAND  = ((0.0, 0.0), (10.0, 100.0), (20.0, 100.0), (45.0, 0.0))  # minutes
_RESTLESS_BAND = ((2.0, 100.0), (12.0, 0.0))                # restless periods / hour
_TIMING_BAND   = ((30.0, 100.0), (180.0, 0.0))              # minutes deviation from your average bedtime

_WEIGHTS = {
    "total_sleep": 0.25,
    "efficiency":  0.20,
    "rem":         0.15,
    "deep":        0.15,
    "restfulness": 0.10,
    "latency":     0.10,
    "timing":      0.05,
}


def _interp(value: float, points: tuple[tuple[float, float], ...]) -> float:
    """Piecewise-linear interpolation over sorted (x, y) knots; clamps to
    the nearest endpoint's y outside the knots' x-range."""
    if value <= points[0][0]:
        return points[0][1]
    if value >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= value <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return points[-1][1]  # unreachable given the bounds checks above


def _bedtime_minutes_since_noon(bedtime_start: str | None) -> float | None:
    """Expresses a bedtime as minutes since noon on the evening it belongs
    to, so realistic bedtimes (evening through the following early morning)
    increase monotonically with no midnight-wraparound discontinuity — e.g.
    11:15 PM -> 675, 1:00 AM the same night -> 780."""
    if not bedtime_start:
        return None
    try:
        bedtime = datetime.fromisoformat(bedtime_start)
    except ValueError:
        return None
    anchor_date = bedtime.date() if bedtime.hour >= 12 else bedtime.date() - timedelta(days=1)
    anchor = datetime.combine(anchor_date, time(12, 0), tzinfo=bedtime.tzinfo)
    return (bedtime - anchor).total_seconds() / 60.0


def bedtime_baseline(rows: list[dict]) -> tuple[float | None, int]:
    """Progressive personal bedtime baseline (minutes since noon — see
    _bedtime_minutes_since_noon), same 7->14->28->56-night schedule as
    services.readiness.sleep_baseline. Returns (baseline_minutes,
    window_nights_used) — (None, 0) when insufficient data."""
    clean = [
        m for r in rows
        for m in [_bedtime_minutes_since_noon(r.get("oura_sleep_bedtime_start"))]
        if m is not None
    ]
    n = len(clean)
    for window in reversed(_BEDTIME_WINDOWS):
        if n >= window:
            return round(sum(clean[-window:]) / window, 1), window
    return None, 0


def compute_sleep_score(
    for_date: date | None = None,
    bio_rows: list[dict] | None = None,
    wake_time_adjustments: dict[str, float] | None = None,
) -> float | str:
    """
    Compute a 0-100 Sleep Score for for_date — see module docstring for the
    7-contributor design.

    wake_time_adjustments: {ISO date string: minutes to subtract from
    recorded awake time}, keyed the same way as CLAUDE.md rule 4's narrow
    manual-entry exception (services.repository.get_wake_time_adjustment /
    get_wake_time_adjustments) — a per-night correction for Oura's known
    wake-time-overestimation pattern. Kept as a plain dict param (not a
    repository read) so this function stays pure/testable. None (the
    default) or no entry for for_date's own date behaves identically to
    never having this parameter at all. When an entry does exist, it's
    floored at the date's own raw oura_sleep_awake_seconds so it can never
    subtract more awake-time than was actually recorded, and only ever
    affects for_date's own row — never the historical rows baselines are
    computed from.

    Returns:
        float        — sleep score 0-100
        NOT_COMPUTED — no contributor could be computed for this day
                       (no Oura sleep-period reading)
    """
    if not bio_rows:
        return NOT_COMPUTED

    for_date = for_date or date.today()
    date_str = str(for_date)
    rows_to_date = [r for r in bio_rows if r.get("date") and r["date"] <= date_str]
    if not rows_to_date:
        return NOT_COMPUTED

    today_row = next((r for r in rows_to_date if r["date"] == date_str), None)

    def _get(key):
        if today_row is None or today_row.get(key) is None:
            return None
        return float(today_row[key])

    # ── Wake-time adjustment — CLAUDE.md rule 4's narrow manual-entry
    #    exception, correcting Oura's known wake-time-overestimation
    #    pattern. Floored at the date's own raw awake seconds so it can
    #    never subtract more awake-time than was actually recorded. Stays
    #    0.0 (no-op) whenever wake_time_adjustments is None or has no entry
    #    for date_str — the default, and every pre-existing caller/test —
    #    so this is 100% behavior-preserving in that case. ─────────────────
    adjustment_seconds = 0.0
    if wake_time_adjustments and today_row is not None and date_str in wake_time_adjustments:
        adjustment_seconds = min(
            wake_time_adjustments[date_str] * 60,
            today_row.get("oura_sleep_awake_seconds") or 0,
        )

    # ── Total Sleep — blended hours vs personal baseline, capped ─────────────
    sleep_base, _win = readiness.sleep_baseline(rows_to_date)
    today_sleep = _get("sleep_duration_hours")
    if adjustment_seconds and today_sleep is not None:
        today_sleep = today_sleep + adjustment_seconds / 3600.0
    total_sleep_s = (
        min(100.0, (today_sleep / sleep_base) * 100.0)
        if today_sleep is not None and sleep_base and sleep_base > 0
        else None
    )

    # ── Efficiency — Oura's own raw reading, already 0-100. When a
    #    wake-time adjustment applies, scaled by the same effective-total-
    #    sleep-seconds ratio as Total Sleep above: efficiency = sleep-time /
    #    time-in-bed, so a proportional increase in sleep seconds (time in
    #    bed held fixed) scales efficiency by that same ratio. ───────────────
    efficiency_raw = _get("oura_sleep_efficiency")
    raw_total_seconds = _get("oura_sleep_total_seconds")
    if adjustment_seconds and efficiency_raw is not None and raw_total_seconds:
        effective_total_seconds = raw_total_seconds + adjustment_seconds
        efficiency_raw = efficiency_raw * (effective_total_seconds / raw_total_seconds)
    efficiency_s = None if efficiency_raw is None else max(0.0, min(100.0, efficiency_raw))

    # ── REM / Deep — % of Oura's own total sleep, ramped over an ideal band ──
    total_s   = _get("oura_sleep_total_seconds")
    rem_raw   = _get("oura_sleep_rem_seconds")
    deep_raw  = _get("oura_sleep_deep_seconds")
    rem_s  = _interp(rem_raw / total_s * 100.0, _REM_PCT_BAND) if rem_raw is not None and total_s else None
    deep_s = _interp(deep_raw / total_s * 100.0, _DEEP_PCT_BAND) if deep_raw is not None and total_s else None

    # ── Restfulness — restless periods per hour of sleep, inverted ───────────
    restless_raw = _get("oura_sleep_restless_periods")
    restfulness_s = (
        _interp(restless_raw / (total_s / 3600.0), _RESTLESS_BAND)
        if restless_raw is not None and total_s else None
    )

    # ── Latency — minutes to fall asleep, banded both sides ──────────────────
    latency_raw = _get("oura_sleep_latency_seconds")
    latency_s = _interp(latency_raw / 60.0, _LATENCY_BAND) if latency_raw is not None else None

    # ── Timing — bedtime deviation from your own rolling-average bedtime ─────
    bedtime_base, _bwin = bedtime_baseline(rows_to_date)
    today_bedtime = _bedtime_minutes_since_noon(today_row.get("oura_sleep_bedtime_start") if today_row else None)
    timing_s = (
        _interp(abs(today_bedtime - bedtime_base), _TIMING_BAND)
        if today_bedtime is not None and bedtime_base is not None else None
    )

    candidates = [
        (total_sleep_s, _WEIGHTS["total_sleep"]),
        (efficiency_s,  _WEIGHTS["efficiency"]),
        (rem_s,         _WEIGHTS["rem"]),
        (deep_s,        _WEIGHTS["deep"]),
        (restfulness_s, _WEIGHTS["restfulness"]),
        (latency_s,     _WEIGHTS["latency"]),
        (timing_s,      _WEIGHTS["timing"]),
    ]
    available = [(s, w) for s, w in candidates if s is not None]
    if not available:
        return NOT_COMPUTED

    total_w = sum(w for _, w in available)
    weighted_sum = sum(s * (w / total_w) for s, w in available)
    return round(weighted_sum, 1)
