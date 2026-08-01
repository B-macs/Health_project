"""
readiness.py — Daily Readiness Score.

Computes a 0-100 readiness score from biometric data using adaptive rolling
baselines. Returns NOT_COMPUTED when insufficient data exists.

Baseline logic
--------------
Sleep      : Progressive — 7 → 14 → 28 → 56 nights as clean data accumulates.
             Outliers <4 h or >11 h are excluded from baseline computation.
Sleep debt : Cumulative deficit over the trailing SLEEP_DEBT_WINDOW_DAYS (7)
             nights against that sleep_baseline, scored 100 at zero debt down
             to 0 at SLEEP_DEBT_THRESHOLD_HOURS (9.5h). The only component
             this module still computes itself.
HRV / RHR  : hrv_baseline() and rhr_baseline() remain exported and tested but
             NO LONGER feed compute_readiness — MODEL_VERSION 2 takes both
             from Oura's own trend-aware contributors instead of deriving a
             saturating ratio here (see below). They are kept because they are
             the natural tool for measuring a device changeover, which is
             exactly what the Garmin 265 will need.

MODEL_VERSION 2 (2026-08-01) — scored from Oura's contributors
--------------------------------------------------------------
Weights (normalised when individual metrics are missing)

HRV Balance (Oura)         21%  primary autonomic recovery marker
Recovery Index (Oura)      17%  Oura's own overnight-recovery contributor
Previous Night (Oura)      16%  last night's sleep, quality-aware
Resting Heart Rate (Oura)  13%  supporting cardiovascular indicator
Body Temperature (Oura)    12%  thermal load against personal norm
Sleep Debt (OURS)           9%  trailing 7-night cumulative deficit
Previous Day Activity (Oura) 5% training-load spillover
Sleep Regularity (Oura)     4%  circadian consistency
Activity Balance (Oura)     3%  accumulated training load

Version 1 derived its own HRV and RHR components as ratios against a 28-day
personal mean: `min(100, today/baseline*100)` for HRV and
`min(100, baseline/today*100)` for RHR. Both were **one-sided and
saturating** — any day at or above baseline scored a flat 100, so they could
only ever penalise and never distinguish among good days. Measured on
2026-08-01: HRV 20.0 ms against an 18.46 baseline is 108%, clipped to 100.
That was a large part of why version 1 read 84.8 on a day Oura read 57.

Both are now taken from Oura's own hrv_balance and resting_heart_rate
contributors, which are trend-aware and not clipped. This is not a loss of
independence: the underlying HRV and RHR readings were ALWAYS Oura's (see
services/biometrics.py — the documented Oura-70/Garmin-30 blend has been
100% Oura for every night of this app's history, and is deliberately held
there by HRV_GARMIN_HOLD), so version 1 was deriving a worse-conditioned
score from the same sensor rather than adding a second opinion.

Four contributors Oura publishes were being synced and ignored entirely —
hrv_balance, sleep_regularity, activity_balance and previous_night. They are
now used.

**This is deliberately NOT "take Oura's readiness score".** Every input is
Oura's, but the weighting and the composite are ours, which is what makes
the score tunable — most immediately for the Garmin 265, whose HRV will need
its own weight once biometrics.HRV_GARMIN_HOLD lifts.

**One row per metric, never one per source.** The drill-down briefly showed
our components beside Oura's nine as a side-by-side comparison; that was
removed once this model landed. A reader should see a single authoritative
number for HRV, and the blend behind it is the model's business, not the
screen's. This holds when Garmin joins: a second device widens the input to
a component, it does not add a second row. The comparison remains available
for auditing via Repository.get_oura_readiness_detail — it is just not a
thing the page shows.

Sleep Debt stays OURS rather than using Oura's sleep_balance, which measures
roughly the same thing: ours is computed here against this module's own
progressive baseline, and services.scheduling's auto-shift shares its exact
threshold (SLEEP_DEBT_THRESHOLD_HOURS), so "zeroes out this component" and
"would trigger a reschedule" continue to mean the same thing.

Alcohol is NO LONGER deducted (removed 2026-08-01). It was a flat
-10 points/unit applied after the weighted average — self-reported, and the
one input Oura cannot see, which made our score and Oura's incomparable on
exactly the days most worth comparing. The units are still read and still
displayed alongside the score as context; they are simply not scored here.
Nothing safety-relevant was lost: services.scheduling reads alcohol
independently from the check-in rows and still triggers a session shift on
CONSECUTIVE_ALCOHOL_DAYS.

Version 1, for the record (weights that no longer apply):
HRV 22.5% · Sleep 18% · Recovery Index 18% · RHR 13.5% · Body Temperature
13.5% · Sleep Debt 10% · Previous Day Activity 4.5%, less 10 points per
alcohol unit.

Trend (compute_readiness_trend, 2026-07-14)
--------------------------------------------
compute_readiness() alone scores each day in isolation, so a recovery day
right after a bad stretch reads as "fully recovered" even when it isn't.
compute_readiness_trend() carries recovery debt forward via exponential
smoothing (same e^(-lambda*t)-style decay used for injury_weight in
engine.py): trend = alpha*today's raw score + (1-alpha)*yesterday's trend.
One good day only partially repays a multi-day deficit.

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

# Removed with MODEL_VERSION 2: alcohol is no longer deducted from readiness
# (it was 10 points per unit). Kept as a comment rather than a dead constant
# so the history of the number is not lost — see this module's header.

# Cumulative sleep deficit (against this module's own sleep_baseline) over the
# trailing window — feeds both compute_readiness's sleep_debt component below
# and services.scheduling's auto-shift trigger (same threshold, same meaning
# in both places: this is the debt level considered clearly bad).
SLEEP_DEBT_THRESHOLD_HOURS = 9.5
SLEEP_DEBT_WINDOW_DAYS = 7


# ─── Component weights — the single source of truth ───────────────────────────
#  Same shape as services/sleep_score.py's _WEIGHTS, and for the same reason:
#  the drill-down shows a weight beside every component, and a second copy of
#  these numbers anywhere would drift. See this module's header for the
#  rationale behind each value.
#
#  Bumped whenever these weights or the component set change, so a stored
#  readiness figure can be traced to the model that produced it — the same
#  auditability sleep_fusion.RULES_VERSION and the movement cut points give.
MODEL_VERSION = 2

#  Tiers, so the numbers are reviewable rather than arbitrary:
#    autonomic recovery      0.38  (hrv_balance + recovery_index)
#    sleep                   0.29  (previous_night + sleep_debt + regularity)
#    cardiovascular/thermal  0.25  (resting HR + body temperature)
#    training-load spillover 0.08  (previous day activity + activity balance)
_WEIGHTS = {
    "hrv_balance":   0.21,
    "recovery":      0.17,
    "prev_night":    0.16,
    "rhr":           0.13,
    "body_temp":     0.12,
    "sleep_debt":    0.09,
    "prev_activity": 0.05,
    "sleep_reg":     0.04,
    "activity_bal":  0.03,
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
    "hrv_balance", "prev_night", "rhr", "recovery", "body_temp",
    "prev_activity", "sleep_reg", "activity_bal", "sleep_debt",
)

# DISPLAY order for the breakdown — descending weight, so the row that moves
# the score most is read first. Deliberately NOT Oura's own contributor order
# (which sleep_score.CONTRIBUTOR_ORDER does follow): Oura's readiness screen
# carries no visible weights, and weight is the whole point of this panel.
COMPONENT_ORDER = (
    "hrv_balance", "recovery", "prev_night", "rhr", "body_temp",
    "sleep_debt", "prev_activity", "sleep_reg", "activity_bal",
)
COMPONENT_LABELS = {
    "hrv_balance":   "HRV Balance",
    "recovery":      "Recovery Index",
    "prev_night":    "Previous Night",
    "rhr":           "Resting Heart Rate",
    "body_temp":     "Body Temperature",
    "sleep_debt":    "Sleep Debt",
    "prev_activity": "Previous Day Activity",
    "sleep_reg":     "Sleep Regularity",
    "activity_bal":  "Activity Balance",
}
# Components passed through already scored 0-100 by Oura, against Oura's own
# personal-norm model. The breakdown shows no `reference` for these because
# there isn't one to show — the baseline lives inside Oura, not here.
# Sleep Debt is the only component we still compute ourselves, and the only
# one with a reference (SLEEP_DEBT_THRESHOLD_HOURS).
OURA_PASSTHROUGH = frozenset(_WEIGHTS) - {"sleep_debt"}


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

    # No alcohol deduction as of MODEL_VERSION 2 — see this module's header.
    # The units are still read and still shown beside the score; they are just
    # not scored, so this number is comparable with Oura's, which cannot see
    # them. services.scheduling still shifts sessions on consecutive-day
    # alcohol, reading the check-in rows directly.
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

    `alcohol_units` is returned alongside but is NOT scored — see this
    module's header. It is carried so the drill-down can show it as context
    beside the score; it must never appear in `components`.
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

    # sleep_baseline is still needed: sleep_debt_hours scores against it, and
    # the drill-down reports which window it used. HRV/RHR baselines are gone
    # with MODEL_VERSION 2's ratio components.
    _sleep_base, _win = sleep_baseline(rows_to_date)

    # No early bail-out on baselines: every Oura contributor below needs none,
    # so a day is computable from those alone. compute_readiness's `available`
    # check is the real gate.

    def _get(key):
        if today_row is None or today_row.get(key) is None:
            return None
        return float(today_row[key])

    # Oura's contributor sub-scores — already 0-100 against Oura's own
    # personal-norm model, so no baseline computation here, just clamp.
    def _clamped100(key):
        v = _get(key)
        return None if v is None else max(0.0, min(100.0, v))

    hrv_balance_s    = _clamped100("oura_hrv_balance")
    recovery_s       = _clamped100("oura_recovery_index")
    prev_night_s     = _clamped100("oura_previous_night")
    rhr_s            = _clamped100("oura_resting_heart_rate_score")
    body_temp_s      = _clamped100("oura_body_temperature")
    prev_activity_s  = _clamped100("oura_previous_day_activity")
    sleep_reg_s      = _clamped100("oura_sleep_regularity")
    activity_bal_s   = _clamped100("oura_activity_balance")

    # Cumulative sleep debt (trailing SLEEP_DEBT_WINDOW_DAYS nights) — the one
    # component still computed here rather than taken from Oura. Distinct from
    # prev_night above, which only looks at LAST NIGHT: a multi-night deficit
    # that is individually "not terrible" each night needs its own component
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

    # ── Assemble, in _SUM_ORDER ───────────────────────────────────────────────
    # (score, raw, reference). Oura's pre-scored contributors have no reference
    # of ours to show — their baseline lives inside Oura — so raw IS the score
    # for those, and reference is None.
    built = {
        "hrv_balance":   (hrv_balance_s,   hrv_balance_s,   None),
        "recovery":      (recovery_s,      recovery_s,      None),
        "prev_night":    (prev_night_s,    prev_night_s,    None),
        "rhr":           (rhr_s,           rhr_s,           None),
        "body_temp":     (body_temp_s,     body_temp_s,     None),
        "sleep_debt":    (sleep_debt_s,    debt,            SLEEP_DEBT_THRESHOLD_HOURS),
        "prev_activity": (prev_activity_s, prev_activity_s, None),
        "sleep_reg":     (sleep_reg_s,     sleep_reg_s,     None),
        "activity_bal":  (activity_bal_s,  activity_bal_s,  None),
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
    """The composite plus every component sub-score that produced it.

    `score` is identical to compute_readiness(...) for the same inputs — both
    walk _component_scores' dict in the same order and apply the same
    renormalisation.

    Components are always all of COMPONENT_ORDER, so the UI can show what is
    MISSING as readily as what scored. A component that could not be computed
    has score None and effective_weight 0.0 — it cannot silently contribute,
    and it must not be dropped from the list: on that panel the gap is the
    most informative thing on screen.

    `alcohol_units` is carried for display only and is NOT scored (see this
    module's header). There is deliberately no `alcohol_penalty_points`:
    reporting a penalty that is no longer applied would be worse than
    reporting nothing.

    `contribution` is a component's share of the composite after
    renormalisation. Contributions will not sum exactly to `score` (the
    composite is rounded once, the parts are not), so present it as a
    contribution, never as exact arithmetic.
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
            "model_version": MODEL_VERSION,
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

    return {
        "score": compute_readiness(for_date, bio_rows),
        "components": components,
        "available_weight": round(sum(w for _, w in available), 4),
        "missing": [k for k in COMPONENT_ORDER if by_key[k]["score"] is None],
        "alcohol_units": scored["alcohol_units"],
        "model_version": MODEL_VERSION,
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
