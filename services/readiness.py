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
Sleep debt : Cumulative deficit over the trailing SLEEP_DEBT_WINDOW_DAYS (7)
             nights against the same sleep_baseline, scored 100 at zero debt
             down to 0 at SLEEP_DEBT_THRESHOLD_HOURS (9.5h) — distinct from
             Sleep above, which only looks at last night; this catches a
             multi-night deficit that's individually mild each night.

Weights (normalised when individual metrics are missing)
--------------------------------------------------------
HRV                       22.5% primary autonomic recovery marker (personal-baseline ratio)
Sleep                     18%   last night vs personal progressive baseline
Sleep Debt                10%   trailing 7-night cumulative deficit vs the same baseline
RHR                       13.5% supporting cardiovascular indicator (personal-baseline ratio)
Recovery Index (Oura)     18%   Oura's own overnight-recovery contributor (0-100, pre-scored)
Body Temperature (Oura)   13.5% Oura's own temperature-deviation contributor (0-100, pre-scored)
Previous Day Activity (Oura) 4.5% Oura's own training-load-spillover contributor (0-100, pre-scored)

2026-07-14: added the three Oura contributor sub-scores above. HRV/Sleep/RHR
were re-weighted down (was 40/35/25) to make room rather than bolted on
alongside unchanged — Recovery Index in particular tracked a real same-day
crash (Oura readiness_score 49) that HRV/RHR/Sleep alone missed entirely
because HRV data was absent that day. Unlike HRV/RHR (ratio-to-baseline,
computed here) these three are Oura-exclusive and already 0-100-scored by
Oura itself — no baseline math needed, just clamped and used directly.
Garmin has no equivalent, so they're simply absent (None) on any day Oura
itself didn't compute them.

2026-07-30: added Sleep Debt (see above). Same-night sleep duration alone
missed a genuine multi-night deficit that was individually "not terrible"
each night; every other weight scaled by 0.9 (proportional, preserving
relative importance) to make room for the new 10%.

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

# Cumulative sleep deficit (against this module's own sleep_baseline) over the
# trailing window — feeds both compute_readiness's sleep_debt component below
# and services.scheduling's auto-shift trigger (same threshold, same meaning
# in both places: this is the debt level considered clearly bad).
SLEEP_DEBT_THRESHOLD_HOURS = 9.5
SLEEP_DEBT_WINDOW_DAYS = 7


# ─── Component weights — the single source of truth ───────────────────────────
#  Hoisted out of compute_readiness's inline `candidates` list, which was the
#  only place these numbers existed and was unreachable from the UI. Same shape
#  as services/sleep_score.py's _WEIGHTS, for the same reason: the drill-down
#  has to show a weight beside every component, and a second copy would drift.
#  Values and their rationale are unchanged — see this module's header.
_WEIGHTS = {
    "hrv":           0.225,
    "sleep":         0.18,
    "recovery":      0.18,
    "rhr":           0.135,
    "body_temp":     0.135,
    "sleep_debt":    0.10,
    "prev_activity": 0.045,
}

# ⚠ SUMMATION order — the order compute_readiness adds the weighted terms in,
#   preserved EXACTLY from the `candidates` list this replaced. Not cosmetic:
#   floating-point addition is not associative, so reordering these terms can
#   move the composite in the last decimal, and that decimal is user-visible
#   and feeds engine.traffic_light / scheduling. It differs from
#   COMPONENT_ORDER below (rhr and recovery are swapped, sleep_debt sits last),
#   which is why the two are separate constants rather than one shared tuple.
#   See services/sleep_score.py::_composite for the same hazard written up.
_SUM_ORDER = (
    "hrv", "sleep", "rhr", "recovery", "body_temp", "prev_activity", "sleep_debt",
)

# DISPLAY order for the breakdown — descending weight, so the row that moves
# the score most is read first. Deliberately NOT Oura's own contributor order
# (which sleep_score.CONTRIBUTOR_ORDER does follow): Oura's readiness screen
# lists nine contributors that are not ours and carry no visible weights, so
# matching its sequence here would imply a correspondence that does not exist.
COMPONENT_ORDER = (
    "hrv", "sleep", "recovery", "rhr", "body_temp", "sleep_debt", "prev_activity",
)
COMPONENT_LABELS = {
    "hrv":           "HRV",
    "sleep":         "Sleep",
    "recovery":      "Recovery Index",
    "rhr":           "Resting Heart Rate",
    "body_temp":     "Body Temperature",
    "sleep_debt":    "Sleep Debt",
    "prev_activity": "Previous Day Activity",
}
# Which of the three Oura-supplied components are passed through already
# scored by Oura (no baseline of ours behind them) — the breakdown shows no
# `reference` for these, because there isn't one to show.
OURA_PASSTHROUGH = frozenset({"recovery", "body_temp", "prev_activity"})


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


def sleep_debt_hours(bio_rows: list[dict], for_date: date,
                      window_days: int = SLEEP_DEBT_WINDOW_DAYS) -> float | None:
    """Cumulative sleep deficit over the trailing `window_days` nights ending
    on for_date (inclusive), against the personal nightly need computed by
    this module's own sleep_baseline.

    Only rows on or before for_date feed the baseline itself, mirroring
    compute_readiness's own "historical views stay accurate" filtering — a
    future row must never influence a past debt figure.

    Returns None when no baseline can be computed (insufficient clean sleep
    history) — deliberately NOT 0.0, which would be indistinguishable from
    "we checked and there's genuinely no deficit." compute_readiness relies
    on this distinction to correctly exclude the component (not silently
    score it as a perfect night) when there isn't enough history yet.
    Returns 0.0 when there's simply no deficit over the window.

    Moved here from services/scheduling.py (which still uses this — see its
    own should_shift_session) so services.readiness can also use it in
    compute_readiness without a circular import (scheduling already imports
    readiness for sleep_baseline)."""
    date_str = for_date.isoformat()
    rows_to_date = [r for r in bio_rows if r.get("date") and r["date"] <= date_str]
    baseline, _window_used = sleep_baseline(rows_to_date)
    if baseline is None:
        return None

    by_date = {r["date"]: r for r in rows_to_date if r.get("date")}
    debt = 0.0
    for delta in range(window_days):
        d = for_date - timedelta(days=delta)
        row = by_date.get(d.isoformat())
        actual = row.get("sleep_duration_hours") if row else None
        if actual is None:
            continue
        debt += max(0.0, baseline - float(actual))
    return round(debt, 2)


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
    scored = _component_scores(for_date, bio_rows)
    if scored is None:
        return NOT_COMPUTED

    available = [
        (c["score"], c["weight"])
        for c in scored["components"].values() if c["score"] is not None
    ]
    if not available:
        return NOT_COMPUTED

    total_w      = sum(w for _, w in available)
    weighted_sum = sum(s * (w / total_w) for s, w in available)

    # ── Alcohol penalty — flat deduction, not a weighted component ────────────
    if scored["alcohol_units"]:
        weighted_sum = max(
            0.0, weighted_sum - scored["alcohol_units"] * _ALCOHOL_PENALTY_PER_UNIT)

    return round(weighted_sum, 1)


def _component_scores(
    for_date: date | None,
    bio_rows: list[dict] | None,
) -> dict | None:
    """Every component sub-score, plus the raw value and baseline each was
    scored against. None when there is no usable row at all — the two cases
    that returned NOT_COMPUTED before any component was computed.

    Split out of compute_readiness so readiness_breakdown can show the seven
    components without that function's public float changing by a decimal —
    it feeds engine.traffic_light, engine.readiness_training_modifier and
    services.scheduling, so the split is deliberately mechanical. Mirrors
    services/sleep_score.py::_contributor_scores.

    `alcohol_units` is returned alongside rather than folded in: the penalty
    is a flat post-hoc deduction, NOT a weighted component (see this module's
    header for why), so it must not appear in `components` where the UI would
    render it as one.
    """
    if not bio_rows:
        return None

    for_date = for_date or date.today()
    date_str  = str(for_date)

    # Only use rows on or before for_date so historical views are accurate
    rows_to_date = [r for r in bio_rows if r.get("date") and r["date"] <= date_str]
    if not rows_to_date:
        return None

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

    # Cumulative sleep debt (trailing SLEEP_DEBT_WINDOW_DAYS nights) — distinct
    # from sleep_s above, which only looks at LAST NIGHT. A short single night
    # already dents sleep_s, but a multi-night deficit (e.g. a rough weekend
    # that's individually "not terrible" each night) needs its own component
    # to register at all. Scored 100 at zero debt, linearly down to 0 at
    # SLEEP_DEBT_THRESHOLD_HOURS — the same threshold services.scheduling uses
    # to decide a session should auto-shift, so "zeroes out this component"
    # and "would trigger a reschedule" mean the same thing. None (excluded,
    # not scored as a perfect night) when no baseline exists yet.
    debt = sleep_debt_hours(rows_to_date, for_date)
    sleep_debt_s = (
        max(0.0, 100.0 * (1.0 - debt / SLEEP_DEBT_THRESHOLD_HOURS))
        if debt is not None else None
    )

    # Oura's own contributor sub-scores — already 0-100 against Oura's own
    # personal-norm model, so no baseline computation here, just clamp.
    def _clamped100(key):
        v = _get(key)
        return None if v is None else max(0.0, min(100.0, v))

    recovery_s       = _clamped100("oura_recovery_index")
    body_temp_s      = _clamped100("oura_body_temperature")
    prev_activity_s  = _clamped100("oura_previous_day_activity")

    # ── Assemble, in _SUM_ORDER ───────────────────────────────────────────────
    # Weights are _WEIGHTS (rebalanced 2026-07-30 to make room for sleep_debt:
    # every prior weight scaled by 0.9, proportional, preserving relative
    # importance, with the freed 10% going to sleep debt -- same tier as
    # RHR/Body Temperature, a real vote without dominating the average).
    built = {
        "hrv":           (hrv_s,           today_hrv,   hrv_base),
        "sleep":         (sleep_s,         today_sleep, sleep_base),
        "recovery":      (recovery_s,      recovery_s,      None),
        "rhr":           (rhr_s,           today_rhr,   rhr_base),
        "body_temp":     (body_temp_s,     body_temp_s,     None),
        "sleep_debt":    (sleep_debt_s,    debt,        SLEEP_DEBT_THRESHOLD_HOURS),
        "prev_activity": (prev_activity_s, prev_activity_s, None),
    }
    components = {
        key: {
            "key": key,
            "label": COMPONENT_LABELS[key],
            "score": built[key][0],
            "weight": _WEIGHTS[key],
            "raw": built[key][1],
            "reference": built[key][2],
        }
        for key in _SUM_ORDER
    }
    return {
        "components": components,
        "alcohol_units": _get("alcohol_units"),
        "sleep_baseline_window": _win,
    }


def readiness_breakdown(
    for_date: date | None = None,
    bio_rows: list[dict] | None = None,
) -> dict:
    """The composite plus the seven component sub-scores that produced it.

    `score` is identical to compute_readiness(...) for the same inputs — both
    walk _component_scores' dict in the same order and apply the same
    renormalisation and alcohol deduction.

    Components are always all seven, in COMPONENT_ORDER, so the UI can show
    what is MISSING as readily as what scored. A component that could not be
    computed has score None and effective_weight 0.0 — it cannot silently
    contribute, and it must not be dropped from the list: on that panel the
    gap is the most informative thing on screen.

    `alcohol_penalty_points` is reported SEPARATELY from the components and
    is never one of them. It is a flat post-hoc deduction (see this module's
    header), so without it the contributions cannot be reconciled with the
    score — which is exactly the "two numbers a few centimetres apart"
    problem the Sleep drill-down's wake-time note already solves.

    `contribution` is a component's share of the composite after
    renormalisation. Contributions will not sum exactly to `score` (the
    composite is rounded once, the parts are not, and the alcohol penalty
    lands outside them entirely), so present it as a contribution, never as
    exact arithmetic.
    """
    scored = _component_scores(for_date, bio_rows)
    if scored is None:
        return {
            "score": NOT_COMPUTED,
            "components": [
                {"key": k, "label": COMPONENT_LABELS[k], "score": None,
                 "weight": _WEIGHTS[k], "effective_weight": 0.0, "contribution": None,
                 "raw": None, "reference": None}
                for k in COMPONENT_ORDER
            ],
            "available_weight": 0.0,
            "missing": list(COMPONENT_ORDER),
            "alcohol_units": None,
            "alcohol_penalty_points": 0.0,
            "sleep_baseline_window": 0,
        }

    by_key = scored["components"]
    available = [(c["score"], c["weight"]) for c in by_key.values() if c["score"] is not None]
    total_w = sum(w for _, w in available) or 1.0

    components = []
    for key in COMPONENT_ORDER:
        c = by_key[key]
        ok = c["score"] is not None
        eff = (c["weight"] / total_w) if ok else 0.0
        components.append({
            **c,
            "effective_weight": round(eff, 4),
            "contribution": round(c["score"] * eff, 2) if ok else None,
        })

    units = scored["alcohol_units"] or 0.0
    return {
        "score": compute_readiness(for_date, bio_rows),
        "components": components,
        "available_weight": round(sum(w for _, w in available), 4),
        "missing": [k for k in COMPONENT_ORDER if by_key[k]["score"] is None],
        "alcohol_units": scored["alcohol_units"],
        "alcohol_penalty_points": round(units * _ALCOHOL_PENALTY_PER_UNIT, 1),
        "sleep_baseline_window": scored["sleep_baseline_window"],
    }


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
