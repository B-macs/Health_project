"""
engine.py — Strict Deterministic Autoregulation Engine.

Pure functions only. No database access, no Streamlit. Takes plain Python
data structures and returns plain Python structures. Every output is
reproducible given the same inputs.

Separation of concerns:
  - This module: deterministic math & rules
  - Bucket 5: probabilistic AI parsing layer (calls this module's output as constraints)
  - db.py: data retrieval
  - pages/: display layer
"""

import math
from datetime import date, timedelta
from services import rules as _rules
from services import readiness as _readiness


# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTS — single source of truth for thresholds and display mappings
# ─────────────────────────────────────────────────────────────────────────────

# Minimum biometric days before the engine issues recommendations
MIN_OBSERVATION_DAYS: int = 14

# Signal → hex colour (dark-theme palette)
SIGNAL_COLORS: dict[str, str] = {
    "green":  "#00D4AA",
    "yellow": "#FFD700",
    "orange": "#FF8C00",
    "red":    "#FF4B4B",
    "grey":   "#6B7280",
}

# Signal → emoji indicator
SIGNAL_ICONS: dict[str, str] = {
    "green":  "🟢",
    "yellow": "🟡",
    "red":    "🔴",
    "grey":   "⚫",
}

# Warning level → emoji (used across AI Insights page)
WARNING_LEVEL_ICONS: dict[str, str] = {
    "none":    "🟢",
    "monitor": "🟡",
    "flag":    "🔴",
}

# ACWR status string → display colour
ACWR_STATUS_COLORS: dict[str, str] = {
    "optimal":                  "green",
    "undertraining":            "yellow",
    "overreach_risk":           "red",
    "insufficient_data":        "grey",
    "insufficient_chronic_data":"grey",
}

# Correlation strength → emoji
CORRELATION_STRENGTH_ICONS: dict[str, str] = {
    "weak":     "🟡",
    "moderate": "🟠",
    "strong":   "🔴",
}


# ─────────────────────────────────────────────────────────────────────────────
#  SIMPLE DETERMINISTIC HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def compute_session_au(rpe: int, duration_minutes: int) -> float:
    """Foster Arbitrary Units = Session-RPE × session duration (minutes)."""
    return float(rpe * duration_minutes)


# Cardiovascular Load Factor per stage.
# Scales raw Foster AU before strain conversion because the Foster method was
# calibrated for sport/endurance training; rehab exercises generate a fraction
# of the cardiovascular and systemic stress at equivalent RPE × duration.
#   Stage 1: isolated bodyweight rehab — minimal HR elevation → 10% of sport load
#   Stage 2: transition (mixed cardio + loaded strength)      → 40%
#   Stage 3: performance (full sport/strength loads)          → 100%
STAGE_CLF: dict[int, float] = {1: 0.04, 2: 0.40, 3: 1.0}


# Load at which the 0-21 curve below saturates at 21.0.
STRAIN_CURVE_ANCHOR: float = 601.0


def load_to_strain(effective_load: float) -> float:
    """The shared 0-21 log curve, taking a load that is ALREADY in
    physiological-effort units (i.e. any source-specific scaling has been
    applied by the caller).

    Split out of au_to_strain so heart-rate-derived load
    (services.hr_load.hr_strain) lands on the identical curve rather than a
    parallel one — the two sources have to stay directly comparable, since
    strain silently falls back from HR to RPE whenever a session has no
    matched Garmin activity, and a curve mismatch would show up as an
    unexplained jump in the number on exactly those days.
    """
    if effective_load <= 0:
        return 0.0
    return round(
        min(21.0, math.log(effective_load + 1) / math.log(STRAIN_CURVE_ANCHOR) * 21.0), 1
    )


def au_to_strain(raw_au: float, stage: int = 1) -> float:
    """
    Convert Foster AU to a 0-21 strain score with stage-specific CLF scaling.

    The database always stores raw Foster AU (RPE × duration) so historical
    comparisons stay valid. CLF is applied at display/computation time only.
    """
    return load_to_strain(raw_au * STAGE_CLF.get(stage, 1.0))


def step_strain_modifier(
    yesterday_steps: int | None,
    baseline_steps: list[int],
) -> float:
    """
    Additive modifier for strain based on how yesterday's step count compares
    to the personal 7-day baseline (days today-8 through today-2).
    Returns 0.0 if data is insufficient (< 4 baseline days or std == 0).

    Thresholds: 0.75σ / 1.5σ.  Asymmetric caps: +1.5 high, -1.0 low
    (excess walking adds compressive load for L5/S1; low steps is less critical).
    """
    if yesterday_steps is None or len(baseline_steps) < 4:
        return 0.0
    mean = sum(baseline_steps) / len(baseline_steps)
    variance = sum((x - mean) ** 2 for x in baseline_steps) / len(baseline_steps)
    std = math.sqrt(variance)
    if std == 0:
        return 0.0
    z = (yesterday_steps - mean) / std
    if z >= 1.5:
        return 1.5
    if z >= 0.75:
        return 0.75
    if z <= -1.5:
        return -1.0
    if z <= -0.75:
        return -0.5
    return 0.0


def injury_weight_signal(weight: float) -> str:
    """Classify injury weight into a traffic-light signal for display."""
    if weight > 0.50:
        return "red"
    if weight > 0.20:
        return "yellow"
    return "green"


# ─────────────────────────────────────────────────────────────────────────────
#  READINESS-TO-TRAINING MODIFIER
#  Adjusts session volume based on the last 3 days of readiness scores.
#  Positive adjustments require multi-day confirmation; negatives compound immediately.
# ─────────────────────────────────────────────────────────────────────────────

# (bucket, streak_days) → (volume_factor, rpe_delta, description)
_READINESS_MODIFIER_TABLE: dict[tuple, tuple] = {
    ("high",  3): (1.12, +0.5, "Strong 3-day readiness -- +12% volume"),
    ("high",  2): (1.08, +0.5, "Strong 2-day readiness -- +8% volume"),
    ("high",  1): (1.04,  0.0, "Good readiness -- +4% volume"),
    ("below", 1): (0.90, -0.5, "Below baseline -- -10% volume"),
    ("below", 2): (0.82, -1.0, "2-day low readiness -- -18% volume"),
    ("below", 3): (0.75, -1.0, "3-day low readiness -- -25% volume"),
    ("low",   1): (0.75, -1.0, "Poor readiness -- -25% volume"),
    ("low",   2): (0.60, -1.5, "2-day poor readiness -- -40% volume"),
    ("low",   3): (0.50, -1.5, "3-day poor readiness -- mobility only"),
}


def _bucket_readiness(score) -> str:
    """Classify a 0-100 readiness score into a training bucket."""
    if score is None or score == _readiness.NOT_COMPUTED:
        return "unknown"
    s = float(score)
    if s >= 80.0:  return "high"
    if s >= 60.0:  return "normal"
    if s >= 40.0:  return "below"
    return "low"


def _readiness_modifier_from_buckets(buckets: list[str]) -> dict:
    """
    Pure helper: compute modifier dict from a list of readiness bucket labels.
    buckets[0] = today, buckets[1] = yesterday, buckets[2] = day before.
    Exposed as a non-underscore name so tests.py can call it directly.
    """
    today_bucket = buckets[0] if buckets else "unknown"

    if today_bucket in ("unknown", "normal"):
        return {"volume_factor": 1.0, "rpe_delta": 0.0,
                "streak_days": 0, "streak_label": today_bucket, "description": ""}

    neg_buckets = {"below", "low"}
    streak = 1
    if today_bucket == "high":
        if len(buckets) > 1 and buckets[1] == "high":
            streak = 2
            if len(buckets) > 2 and buckets[2] == "high":
                streak = 3
    elif today_bucket in neg_buckets:
        if len(buckets) > 1 and buckets[1] in neg_buckets:
            streak = 2
            if len(buckets) > 2 and buckets[2] in neg_buckets:
                streak = 3

    streak = min(streak, 3)
    factor, rpe_delta, description = _READINESS_MODIFIER_TABLE.get(
        (today_bucket, streak), (1.0, 0.0, "")
    )
    return {
        "volume_factor": factor,
        "rpe_delta":     rpe_delta,
        "streak_days":   streak,
        "streak_label":  today_bucket,
        "description":   description,
    }


def readiness_training_modifier(bio_rows: list[dict], today: date | None = None) -> dict:
    """
    Compute a training volume modifier from the last 3 days of readiness scores.

    Returns volume_factor, rpe_delta, streak_days, streak_label, description.
    volume_factor is in [0.50, 1.12]; rpe_delta is advisory only.
    """
    today  = today or date.today()
    scores = []
    for delta in range(3):
        d = today - timedelta(days=delta)
        rows_up_to = [r for r in bio_rows if r.get("date") and r["date"] <= d.isoformat()]
        scores.append(_readiness.compute_readiness(d, rows_up_to))
    buckets = [_bucket_readiness(s) for s in scores]
    return _readiness_modifier_from_buckets(buckets)


def apply_exercise_volume_modifier(ex: dict, volume_factor: float) -> dict:
    """
    Return a shallow copy of ex with reps/hold_seconds/reps_in_set/duration_minutes
    scaled by volume_factor. Sets and rest_seconds are unchanged.
    Returns the same object when volume_factor == 1.0 (fast path).
    """
    if volume_factor == 1.0:
        return ex
    m = dict(ex)
    if m.get("reps") is not None:
        m["reps"] = max(1, round(m["reps"] * volume_factor))
    if m.get("hold_seconds") is not None:
        m["hold_seconds"] = max(5, round(m["hold_seconds"] * volume_factor))
    if m.get("reps_in_set") is not None:
        m["reps_in_set"] = max(1, round(m["reps_in_set"] * volume_factor))
    if m.get("duration_minutes") is not None:
        m["duration_minutes"] = max(5, round(m["duration_minutes"] * volume_factor))
    return m


BAND_TIERS = ("Green", "Blue", "Yellow", "Red", "Black")
BAND_TIER_LABELS = {
    "Green": "Light", "Blue": "Medium", "Yellow": "Heavy",
    "Red": "X Heavy", "Black": "XX Heavy",
}


def suggested_weight_kg(
    current_weight_kg: float | None,
    streak_label: str,
    increment: float = 2.5,
    allow_increase: bool = True,
) -> float | None:
    """
    Deterministic next-session weight suggestion for a loaded (dumbbell/
    cable/plate) exercise, nudging by one `increment` based on the
    readiness engine's own streak_label (readiness_training_modifier's
    output) -- reusing that existing signal rather than a new ad-hoc system.

    streak_label -> delta:
      "high"             -> +increment  (only if allow_increase)
      "low" | "below"    -> -increment
      anything else       -> unchanged

    allow_increase lets the caller suppress the upward nudge (e.g. on a
    red-signal engine-directive day, or when there's no existing load to
    build on). It never suppresses the downward nudge.

    Returns None if current_weight_kg is None. "Unchanged" returns
    current_weight_kg exactly (floored at 0, rounded for float cleanliness)
    -- NOT snapped to the increment grid, since some exercises legitimately
    prescribe a weight off that grid (e.g. 1kg dumbbells for a scapular
    accessory lift) and a "no change" suggestion must never silently alter
    it. Only an actual +/-increment move snaps to the nearest multiple of
    `increment` (protects against float drift across repeated moves).
    """
    if current_weight_kg is None:
        return None
    if streak_label == "high" and allow_increase:
        delta = increment
    elif streak_label in ("low", "below"):
        delta = -increment
    else:
        return round(max(0.0, current_weight_kg), 2)
    raw = current_weight_kg + delta
    stepped = round(raw / increment) * increment if increment else raw
    return round(max(0.0, stepped), 2)


def double_progression(
    current_weight: float,
    current_target_reps: int,
    rep_min: int,
    rep_max: int,
    last_session_sets: list[dict] | None,
    prescribed_sets: int = 1,
    increment: float = 2.5,
    allow_increase: bool = True,
) -> tuple[float, int]:
    """
    Standard double-progression check for one loaded, countable-reps
    exercise (training_plan._ex's rep_min/rep_max fields).

    If the last logged session hit the TOP of the rep range (>= rep_max) on
    EVERY prescribed set, the next session progresses: weight goes up by
    one `increment` and the target reps reset to the bottom of the range
    (rep_min). Otherwise the inputs are returned completely unchanged --
    the caller (services.sessions.seed_actual_entry) falls through to the
    existing last_performance/readiness-nudge seeding path when this
    doesn't fire.

    last_session_sets: the full per-set array for the movement's most
    recent logged session (Repository.get_last_session_all_sets's shape --
    a list of {"reps": .., "weight": .., ...} dicts), not just the last
    set, since "every prescribed set" must all clear rep_max.

    prescribed_sets: how many sets this exercise is actually prescribed for
    (ex["sets"]). A session logged with FEWER sets than prescribed (cut
    short) never progresses even if every logged set hit rep_max --
    `all()` over a short list is vacuously true, so without this check a
    partial session would read identically to a full clean one.

    The weight progression increments FROM is the actual last-lifted
    weight (last_session_sets' own "weight" on its last set) when
    available, not the caller-supplied current_weight -- current_weight
    may be a static, plan-authored value (training_plan.py's per-week
    dicts) that's gone stale once real logged history exists; basing the
    increment on it instead of what was actually lifted would silently
    discard weight the user already earned. Falls back to current_weight
    only if the logged set is missing a weight value.

    allow_increase gates the upward move exactly like suggested_weight_kg's
    own allow_increase param (e.g. suppressed on a red-signal engine-
    directive day) -- it never suppresses anything else, since this
    function has no downward direction: it either progresses or leaves the
    inputs untouched.

    Returns (current_weight, current_target_reps) unchanged when
    last_session_sets is None/empty, has fewer sets than prescribed_sets,
    when any logged set fell short of rep_max, or when allow_increase is
    False.
    """
    if (not last_session_sets or not allow_increase
            or len(last_session_sets) < prescribed_sets):
        return current_weight, current_target_reps
    if all((s.get("reps") or 0) >= rep_max for s in last_session_sets):
        last_weight = last_session_sets[-1].get("weight")
        base_weight = last_weight if last_weight is not None else current_weight
        return base_weight + increment, rep_min
    return current_weight, current_target_reps


def suggested_band_tier(
    current_tier: str | None,
    streak_label: str,
    allow_increase: bool = True,
) -> str | None:
    """
    Band-resistance counterpart to suggested_weight_kg -- steps one
    position through the fixed Green/Blue/Yellow/Red/Black tier scale
    instead of a kg increment, same streak_label -> direction mapping,
    clamped at both ends. Returns None if current_tier is None or not a
    recognised tier.
    """
    if current_tier not in BAND_TIERS:
        return None
    idx = BAND_TIERS.index(current_tier)
    if streak_label == "high" and allow_increase:
        idx += 1
    elif streak_label in ("low", "below"):
        idx -= 1
    idx = max(0, min(len(BAND_TIERS) - 1, idx))
    return BAND_TIERS[idx]


def observation_days_remaining(data_days: int) -> int:
    """Days of additional biometric logging needed before engine activates."""
    return max(0, MIN_OBSERVATION_DAYS - data_days)


# ─────────────────────────────────────────────────────────────────────────────
#  TRAFFIC LIGHT SYSTEM
#  Evaluates daily morning biometrics vs 7-day and 28-day rolling baselines.
# ─────────────────────────────────────────────────────────────────────────────

_SIGNAL_PRIORITY = {"red": 0, "yellow": 1, "grey": 2, "green": 3}

# Thresholds: what % deviation from 28-day baseline triggers each signal.
# Applied directionally (see _metric_signal).
YELLOW_THRESHOLD = 0.10   # >10% degradation → yellow
RED_THRESHOLD    = 0.25   # >25% degradation → red

# ── Body-temperature deviation (°C, Oura's raw figure vs its own personal
#    norm) — an ABSOLUTE-threshold metric, unlike the three ratio-to-baseline
#    metrics above, for two independent reasons:
#
#    1. It is already a deviation. Dividing a deviation by the mean of other
#       deviations is meaningless, and the mean sits near zero (measured:
#       0.034 °C over 357 nights), so the ratio explodes on ordinary days.
#    2. A ratio metric is definitionally relative to recent history, which is
#       exactly the property you do NOT want for a fever signal — a week of
#       elevated temperature would raise the baseline and hide the eighth day.
#
#    Cut points are calibrated on 357 nights of this athlete's own history:
#    +0.35 °C fires on 8.7% of nights, +0.60 °C on 2.0%. Deliberately
#    one-sided — a NEGATIVE deviation (cooler than norm) is not a training
#    risk and stays green, so this metric can only ever make the light
#    stricter, never looser.
TEMP_DEVIATION_YELLOW_C = 0.35
TEMP_DEVIATION_RED_C    = 0.60

# ── Baseline-drift guard ────────────────────────────────────────────────────
# The three ratio metrics score today against a 28-day rolling mean, so a
# slow decline is invisible to them: the baseline follows you down and
# "green" quietly comes to mean "consistently as bad as recently" rather
# than "well". This guard compares the recent window against the window
# BEFORE it (disjoint, not nested — overlapping windows dampen exactly the
# signal being measured) and reports adverse movement in the baseline itself.
#
# It can only ever downgrade green → yellow, never yellow → green and never
# green → red. Drift is chronic context, not an acute reading; it justifies
# holding volume, not prescribing rest.
#
# Self-clearing by construction: the comparison window rolls forward, so a
# decline that becomes the new normal stops registering as drift after
# roughly DRIFT_PRIOR_DAYS. That is intended — this detects "you have
# changed recently", not "you are worse than your all-time best".
DRIFT_RECENT_DAYS      = 28
DRIFT_PRIOR_DAYS       = 62   # days 29-90 back: disjoint from the recent window
DRIFT_MIN_PRIOR_DAYS   = 21   # below this the prior window is too thin to trust
DRIFT_SEVERE_PCT       = 10.0  # one metric this far adverse → downgrade
DRIFT_MODERATE_PCT     = 5.0   # ...or two metrics this far adverse

# What a caller should pass to get_biometric_rolling() to feed the guard.
# The windows above count ROWS, not calendar days, because a biometric row
# only exists for a day a device was actually worn — so a calendar-day
# window would silently shrink to nothing during a sparse stretch. This
# figure is calendar days and is deliberately generous: measured against
# this athlete's own history, 400 calendar days yields 97 rows, where 90
# days yields only 39 (the ring was worn intermittently before mid-2026).
# Over-fetching costs nothing — get_biometric_rolling reads whole tabs and
# filters in Python either way.
DRIFT_RECOMMENDED_FETCH_DAYS = 400

# Metrics the drift guard watches: key → higher_is_better.
_DRIFT_METRICS = {
    "hrv_ms":               True,
    "resting_heart_rate":   False,
    "sleep_duration_hours": True,
}


def _metric_signal(value, baseline, higher_is_better: bool) -> str:
    if value is None or baseline is None or baseline == 0:
        return "grey"
    ratio = value / baseline
    if higher_is_better:
        if ratio >= (1 - YELLOW_THRESHOLD): return "green"
        if ratio >= (1 - RED_THRESHOLD):    return "yellow"
        return "red"
    else:  # lower is better (RHR)
        if ratio <= (1 + YELLOW_THRESHOLD): return "green"
        if ratio <= (1 + RED_THRESHOLD):    return "yellow"
        return "red"


def _temperature_signal(deviation) -> str:
    """Signal for a raw °C temperature deviation against absolute cut points.

    Separate from _metric_signal because this metric carries no baseline —
    see the TEMP_DEVIATION_* comment above for why a ratio is the wrong
    shape here. One-sided: only warmth counts against you.
    """
    if deviation is None:
        return "grey"
    if deviation >= TEMP_DEVIATION_RED_C:    return "red"
    if deviation >= TEMP_DEVIATION_YELLOW_C: return "yellow"
    return "green"


def _worst_signal(*signals) -> str:
    return min(signals, key=lambda s: _SIGNAL_PRIORITY.get(s, 2))


def _safe_avg(rows: list[dict], key: str):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def baseline_drift(biometric_rows: list[dict]) -> dict:
    """Has the 28-day baseline itself moved adversely against the window
    before it?

    Returns dict with keys:
        status        : "ok" | "insufficient_data"
        drifted       : bool  — True when the movement is material enough to
                        justify downgrading an otherwise-green light
        severity      : "none" | "moderate" | "severe"
        metrics       : per-metric {recent, prior, delta_pct, adverse_pct,
                        adverse} — adverse_pct is signed so that POSITIVE
                        always means "worse", whichever direction the raw
                        metric moves in
        prior_days    : int — how many rows backed the prior window
        message       : str

    Pure and windowless-by-index: operates on however many rows it is
    handed, taking the last DRIFT_RECENT_DAYS as "recent" and the
    DRIFT_PRIOR_DAYS before those as "prior". A caller passing only 28
    rows gets status "insufficient_data" and drifted False — the guard
    degrades to a no-op rather than guessing, which is why adding it to
    traffic_light cannot change behaviour for any existing caller that
    hasn't widened its window.
    """
    recent = biometric_rows[-DRIFT_RECENT_DAYS:]
    prior  = biometric_rows[-(DRIFT_RECENT_DAYS + DRIFT_PRIOR_DAYS):-DRIFT_RECENT_DAYS]

    if len(prior) < DRIFT_MIN_PRIOR_DAYS:
        return {
            "status": "insufficient_data",
            "drifted": False,
            "severity": "none",
            "metrics": {},
            "prior_days": len(prior),
            "message": (
                f"Need {DRIFT_MIN_PRIOR_DAYS} days of history before the current "
                f"28-day window to detect baseline drift. Have {len(prior)}."
            ),
        }

    metrics: dict[str, dict] = {}
    severe = moderate = 0
    for key, higher_is_better in _DRIFT_METRICS.items():
        recent_avg = _safe_avg(recent, key)
        prior_avg  = _safe_avg(prior, key)
        if recent_avg is None or not prior_avg:
            continue
        delta_pct = (recent_avg - prior_avg) / prior_avg * 100.0
        # Flip sign for lower-is-better metrics so positive always means worse
        adverse_pct = -delta_pct if higher_is_better else delta_pct
        if adverse_pct >= DRIFT_SEVERE_PCT:
            severe += 1
        elif adverse_pct >= DRIFT_MODERATE_PCT:
            moderate += 1
        metrics[key] = {
            "recent":      round(recent_avg, 2),
            "prior":       round(prior_avg, 2),
            "delta_pct":   round(delta_pct, 1),
            "adverse_pct": round(adverse_pct, 1),
            "adverse":     adverse_pct >= DRIFT_MODERATE_PCT,
        }

    if severe >= 1:
        severity = "severe"
    elif (moderate + severe) >= 2:
        severity = "severe" if severe else "moderate"
    elif moderate >= 1:
        severity = "moderate"
    else:
        severity = "none"

    # One severe metric, or any two adverse metrics, is enough to act on.
    drifted = severe >= 1 or (moderate + severe) >= 2

    worst = sorted(metrics.items(), key=lambda kv: -kv[1]["adverse_pct"])
    if drifted and worst:
        detail = ", ".join(
            f"{k} {v['delta_pct']:+.1f}%" for k, v in worst if v["adverse"]
        )
        message = (
            f"Your 28-day baseline has moved against you vs the previous "
            f"{len(prior)} days ({detail}). Today reads 'normal' against a "
            f"baseline that is itself declining."
        )
    else:
        message = "28-day baseline is stable against the preceding window."

    return {
        "status": "ok",
        "drifted": drifted,
        "severity": severity,
        "metrics": metrics,
        "prior_days": len(prior),
        "message": message,
    }


def traffic_light(biometric_rows: list[dict], drift_rows: list[dict] | None = None) -> dict:
    """
    Evaluate daily biometrics against rolling baselines.

    Args:
        biometric_rows: list of dicts from get_biometric_rolling(), sorted
                        ascending by date. Must include: hrv_ms,
                        resting_heart_rate, sleep_duration_hours.
                        oura_temperature_deviation is optional — absent or
                        None simply greys that one metric, exactly as a
                        missing HRV reading already does.

        drift_rows:     longer history for the baseline-drift guard, which
                        needs rows from BEFORE the current 28-day baseline
                        window to have anything to compare against. Fetch it
                        with get_biometric_rolling(days=
                        DRIFT_RECOMMENDED_FETCH_DAYS).

                        A separate parameter rather than "just pass a longer
                        biometric_rows" on purpose: callers routinely hand
                        the SAME list to readiness.compute_readiness, whose
                        sleep_baseline widens from a 28- to a 56-night window
                        once enough rows are present — so silently lengthening
                        the shared list would move readiness scores as a side
                        effect of enabling a traffic-light feature. Opting in
                        explicitly keeps the two independent.

                        None (the default) falls back to biometric_rows, under
                        which a typical 28-row list yields status
                        "insufficient_data" and the guard is a no-op. Existing
                        callers therefore see no behaviour change.

    Returns dict with keys:
        overall         : "green" | "yellow" | "red" | "grey"
        status          : "ok" | "insufficient_data"
        volume_multiplier_from_traffic : float
        metrics         : dict per metric with value/baseline/signal/delta_pct
        drift           : baseline_drift() result (see that function)
        drift_applied   : bool — True when drift actually downgraded `overall`
        data_days       : int
        message         : str
    """
    MIN_DAYS = 7  # minimum baseline days before engine activates

    if len(biometric_rows) < MIN_DAYS:
        return {
            "overall": "grey",
            "status": "insufficient_data",
            "volume_multiplier_from_traffic": 1.0,
            "metrics": {},
            "drift": baseline_drift(drift_rows if drift_rows is not None else biometric_rows),
            "drift_applied": False,
            "data_days": len(biometric_rows),
            "message": f"Need {MIN_DAYS} days of biometric data to activate. "
                       f"Currently have {len(biometric_rows)}.",
        }

    today = biometric_rows[-1]
    baseline_rows = biometric_rows[-28:]  # up to 28 days, whatever is available

    metric_specs = [
        ("hrv_ms",             "HRV",   True,  "ms"),
        ("resting_heart_rate", "RHR",   False, "bpm"),
        ("sleep_duration_hours","Sleep",True,  "h"),
    ]

    metrics = {}
    signals = []
    for key, label, higher, unit in metric_specs:
        baseline = _safe_avg(baseline_rows, key)
        value    = today.get(key)
        sig      = _metric_signal(value, baseline, higher)
        delta    = ((value - baseline) / baseline * 100) if (value and baseline) else None
        signals.append(sig)
        metrics[key] = {
            "label":       label,
            "unit":        unit,
            "value":       value,
            "baseline_28d": round(baseline, 1) if baseline else None,
            "signal":      sig,
            "delta_pct":   round(delta, 1) if delta is not None else None,
            "higher_is_better": higher,
        }

    # Fourth metric: body-temperature deviation. Absolute cut points, no
    # baseline — see the TEMP_DEVIATION_* block for why. Shaped identically
    # to the three above so every existing consumer that iterates
    # `metrics` renders it without a change; baseline_28d is None because
    # the reading is ALREADY a deviation from Oura's own personal norm.
    temp_dev = today.get("oura_temperature_deviation")
    temp_sig = _temperature_signal(temp_dev)
    # Unlike the three required metrics, a MISSING temperature reading does
    # not grey the overall light. Temperature is Oura-exclusive (the Garmin
    # 645 reports skinTempDataExists False on 53/53 archived nights), so
    # folding a grey into _worst_signal would turn every ring-off night grey
    # — degrading the light for a device gap rather than a physiological
    # one. Contributes only when it has something to say, which keeps the
    # one-way-stricter property intact.
    if temp_sig != "grey":
        signals.append(temp_sig)
    metrics["oura_temperature_deviation"] = {
        "label":        "Body temp",
        "unit":         "°C",
        "value":        temp_dev,
        "baseline_28d": None,
        "signal":       temp_sig,
        "delta_pct":    None,
        "higher_is_better": False,
        "absolute_thresholds": {
            "yellow": TEMP_DEVIATION_YELLOW_C,
            "red":    TEMP_DEVIATION_RED_C,
        },
    }

    overall = _worst_signal(*signals)

    # Baseline-drift guard — strictly one-directional: green → yellow only.
    # Never touches yellow or red (already at-or-below where drift would put
    # it) and never upgrades anything, so it cannot loosen a guardrail.
    drift = baseline_drift(drift_rows if drift_rows is not None else biometric_rows)
    drift_applied = drift["drifted"] and overall == "green"
    if drift_applied:
        overall = "yellow"

    vol_mult = {"green": 1.0, "yellow": 0.75, "red": 0.0, "grey": 1.0}[overall]

    messages = {
        "green":  "Biometrics at or above baseline. Full training capacity.",
        "yellow": "Biometrics slightly below baseline. Volume reduction applied.",
        "red":    "Biometrics significantly degraded. Rest or mobility only.",
        "grey":   "Some metrics unavailable. Engine using available data.",
    }
    message = drift["message"] if drift_applied else messages[overall]
    if temp_sig in ("yellow", "red") and overall == temp_sig:
        message = (
            f"Body temperature {temp_dev:+.2f} °C vs your personal norm. "
            + ("Possible illness onset — no loaded training today."
               if temp_sig == "red" else
               "Elevated. Hold volume and re-check tomorrow.")
        )

    return {
        "overall":  overall,
        "status":   "ok",
        "volume_multiplier_from_traffic": vol_mult,
        "metrics":  metrics,
        "drift":    drift,
        "drift_applied": drift_applied,
        "data_days": len(biometric_rows),
        "message":  message,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  ACWR — Acute-to-Chronic Workload Ratio
#  Foster method: session_au = session_rpe × session_duration_minutes
# ─────────────────────────────────────────────────────────────────────────────

# Sweet spot range per sport science literature (Blanch & Gabbett, 2016)
ACWR_OPTIMAL_LOW  = 0.8
ACWR_OPTIMAL_HIGH = 1.3   # overridden to 1.2 for Stage 1

def acwr(daily_au_rows: list[dict], stage: int = 1, today: date | None = None) -> dict:
    """
    Compute ACWR from session AU history.

    Args:
        daily_au_rows: list of {date: str (ISO), total_au: float} from
                       get_daily_session_au(). Rest days must be present
                       as gaps — this function fills them with 0.
        stage        : current rehabilitation stage (1|2|3)

    Returns dict with keys:
        acwr          : float | None
        acute_avg     : float  (7-day avg AU)
        chronic_avg   : float  (28-day avg AU)
        ceiling       : float  (stage-specific ACWR hard cap)
        status        : str
        hard_locked   : bool
        daily_au_28   : list[float]  (28 entries, day -27 to today)
    """
    ceiling = _rules.STAGE_CONSTRAINTS.get(stage, {}).get("acwr_ceiling", 1.3)

    # Build a fully-populated 28-day calendar (rest days = 0 AU)
    today     = today or date.today()
    au_by_date = {row["date"]: float(row["total_au"]) for row in daily_au_rows}
    daily_au_28 = [
        au_by_date.get((today - timedelta(days=27 - i)).isoformat(), 0.0)
        for i in range(28)
    ]

    if not any(daily_au_rows):
        return {
            "acwr": None, "acute_avg": 0.0, "chronic_avg": 0.0,
            "ceiling": ceiling, "status": "insufficient_data",
            "hard_locked": False, "daily_au_28": daily_au_28,
        }

    chronic_avg = sum(daily_au_28) / 28
    acute_avg   = sum(daily_au_28[-7:]) / 7

    if chronic_avg == 0:
        return {
            "acwr": None, "acute_avg": round(acute_avg, 1), "chronic_avg": 0.0,
            "ceiling": ceiling, "status": "insufficient_chronic_data",
            "hard_locked": False, "daily_au_28": daily_au_28,
        }

    ratio       = acute_avg / chronic_avg
    hard_locked = ratio > ceiling

    if ratio < ACWR_OPTIMAL_LOW:
        status = "undertraining"
    elif ratio <= ceiling:
        status = "optimal"
    else:
        status = "overreach_risk"

    return {
        "acwr":        round(ratio, 3),
        "acute_avg":   round(acute_avg, 1),
        "chronic_avg": round(chronic_avg, 1),
        "ceiling":     ceiling,
        "status":      status,
        "hard_locked": hard_locked,
        "daily_au_28": [round(v, 1) for v in daily_au_28],
    }


# ─────────────────────────────────────────────────────────────────────────────
#  VOLUME RECOMMENDATION
#  Combines traffic light + ACWR into a single daily output.
# ─────────────────────────────────────────────────────────────────────────────

def volume_recommendation(
    traffic: dict,
    acwr_result: dict,
    stage: int = 1,
    observation_days_remaining: int = 0,
    injury_weight_val: float = 1.0,
) -> dict:
    """
    Synthesise traffic light + ACWR + injury weight into today's volume directive.

    injury_weight_val: output of injury_weight() — 0.0 (healed) to 1.0 (acute).
      > 0.7 : injury very active — cap at conservative load even on green days
      0.4–0.7: standard stage constraints apply
      < 0.2 : injury background-only; stage constraints drive decision

    Returns dict with keys:
        label         : str
        multiplier    : float (1.05 = overload, 1.0 = maintain, 0.85 = conservative,
                                0.75 = reduced, 0.0 = rest)
        action        : str
        signal_color  : str  ("green"|"orange"|"red"|"grey")
        injury_weight_active: bool  (True when injury_weight_val raised the constraint)
    """
    # Observation mode — not enough baseline data yet
    if observation_days_remaining > 0:
        return {
            "label":              "OBSERVATION MODE",
            "multiplier":         1.0,
            "action":             f"Collecting baseline data. Recommendations activate in "
                                  f"{observation_days_remaining} more day(s). Train at comfortable "
                                  f"effort and log consistently.",
            "signal_color":       "grey",
            "injury_weight_active": False,
        }

    tl_status   = traffic.get("status")
    overall     = traffic.get("overall", "grey")
    hard_locked = acwr_result.get("hard_locked", False)
    acwr_val    = acwr_result.get("acwr")
    ceiling     = acwr_result.get("ceiling", 1.3)

    # Insufficient biometric data
    if tl_status == "insufficient_data":
        return {
            "label":              "OBSERVATION MODE",
            "multiplier":         1.0,
            "action":             traffic.get("message", "Log biometrics daily to activate the engine."),
            "signal_color":       "grey",
            "injury_weight_active": False,
        }

    # Red traffic light → systemic fatigue → rest only (injury weight cannot override rest)
    if overall == "red":
        return {
            "label":              "REST / DELOAD",
            "multiplier":         0.0,
            "action":             "Biometrics indicate systemic fatigue or distress. "
                                  "No loaded training. Mobility and light walking only.",
            "signal_color":       "red",
            "injury_weight_active": False,
        }

    # ACWR hard lock overrides yellow/green signal
    if hard_locked and acwr_val is not None:
        return {
            "label":              "VOLUME HARD-LOCKED",
            "multiplier":         0.75,
            "action":             f"ACWR {acwr_val:.2f} exceeds Stage {stage} ceiling of {ceiling}. "
                                  f"Upper training limits capped. Maintain current loads — no increases.",
            "signal_color":       "red",
            "injury_weight_active": False,
        }

    # Yellow biometrics — reduce volume, hold intensity
    if overall == "yellow":
        return {
            "label":              "REDUCED VOLUME  (−25%)",
            "multiplier":         0.75,
            "action":             "Biometrics are below baseline. Scale total volume down 20–30%. "
                                  "Hold intensity targets unchanged — do not increase load today.",
            "signal_color":       "orange",
            "injury_weight_active": False,
        }

    # ── Green biometrics: injury weight determines whether overload is safe ──
    # Injury weight > 0.7: tissue is still significantly loaded from pathology.
    # Even green biometrics don't justify a full overload prescription.
    if injury_weight_val > 0.7:
        iw_pct = int(injury_weight_val * 100)
        return {
            "label":              f"CONSERVATIVE LOAD  (injury weight {iw_pct}%)",
            "multiplier":         0.85,
            "action":             f"Biometrics nominal but injury baseline weight is {iw_pct}% — "
                                  f"tissue tolerance is still primary. Maintain current load. "
                                  f"Full progressive overload unlocks when injury weight drops below 70%.",
            "signal_color":       "yellow",
            "injury_weight_active": True,
        }

    # All clear — standard progressive overload
    return {
        "label":              "PROGRESSIVE OVERLOAD",
        "multiplier":         1.05,
        "action":             "All systems nominal. Apply standard progressive overload: "
                              "+2.5 kg (Stage 2+) or +1 rep per set (Stage 1).",
        "signal_color":       "green",
        "injury_weight_active": False,
    }


def apply_volume_recommendation(
    planned_sets: int,
    planned_reps: int,
    planned_weight_kg: float,
    rec: dict,
    stage: int = 1,
) -> dict:
    """
    Translate today's volume recommendation into specific training targets.

    Multiplier semantics:
      0.0  → REST — no loaded training
      0.75 → Reduce SETS, preserve weight (hold intensity, cut volume)
      0.85 → Conservative — reduce sets slightly, hold weight
      1.0  → Maintain exactly
      1.05 → Progressive overload: +1 rep/set (Stage 1) or +2.5 kg (Stage 2+)

    Returns dict with keys:
        sets, reps, weight_kg, note
    """
    mult = rec.get("multiplier", 1.0)

    if mult == 0.0:
        return {
            "sets": 0, "reps": 0, "weight_kg": 0.0,
            "note": "REST DAY — no loaded training.",
        }

    if mult > 1.0:
        # Progressive overload — Stage 1: add reps (tissue tolerance); Stage 2+: add weight
        if stage == 1:
            return {
                "sets":      planned_sets,
                "reps":      planned_reps + 1,
                "weight_kg": planned_weight_kg,
                "note":      f"+1 rep per set (Stage 1 tissue tolerance progression).",
            }
        increment = 2.5
        return {
            "sets":      planned_sets,
            "reps":      planned_reps,
            "weight_kg": round(planned_weight_kg + increment, 2),
            "note":      f"+{increment} kg overload (Stage {stage}).",
        }

    # Volume reduction — cut sets proportionally, preserve weight (intensity baseline)
    adjusted_sets = max(1, round(planned_sets * mult))
    return {
        "sets":      adjusted_sets,
        "reps":      planned_reps,
        "weight_kg": planned_weight_kg,
        "note":      f"Reduced to {adjusted_sets}/{planned_sets} sets. Weight maintained at {planned_weight_kg} kg.",
    }


# ─────────────────────────────────────────────────────────────────────────────
#  INJURY WEIGHT DECAY
#  e^(-λt) — weight approaches 0 as pain-free training accumulates.
#  At λ=0.05: t=0 → 1.00, t=14 → 0.50, t=28 → 0.25, t=60 → 0.05
# ─────────────────────────────────────────────────────────────────────────────

def injury_weight(lambda_val: float, days_pain_free: int) -> float:
    return round(math.exp(-lambda_val * max(0, days_pain_free)), 4)


# ─────────────────────────────────────────────────────────────────────────────
#  STAGE STATE MACHINE
#  Evaluated every 14 days. Criteria are conservative — physiotherapist
#  confirmation is recommended before advancing.
# ─────────────────────────────────────────────────────────────────────────────

STAGE_LABELS = {
    1: "Stage 1 — Rehab (Tissue Tolerance)",
    2: "Stage 2 — Transition (Work Capacity)",
    3: "Stage 3 — Performance & Growth",
}

# Minimum thresholds to qualify for stage advancement
_ADVANCE_CRITERIA = {
    1: {"min_days_pain_free": 14, "max_avg_tightness": 3.0, "next": 2},
    2: {"min_days_pain_free": 28, "max_avg_tightness": 2.0, "next": 3},
    3: {"min_days_pain_free": None, "max_avg_tightness": None, "next": None},
}


def stage_status(
    current_stage: int,
    days_pain_free: int,
    avg_tightness_14d: float,
) -> dict:
    """
    Evaluate whether criteria for stage advancement are met.

    Returns dict with keys:
        current_stage   : int
        stage_label     : str
        advance_ready   : bool
        next_stage      : int | None
        progress_days   : str
        progress_tightness : str
        days_progress_pct  : float 0-1 (for progress bar)
        tight_progress_pct : float 0-1
        message         : str
    """
    criteria = _ADVANCE_CRITERIA.get(current_stage, _ADVANCE_CRITERIA[3])
    req_days  = criteria["min_days_pain_free"]
    req_tight = criteria["max_avg_tightness"]

    if req_days is None:
        return {
            "current_stage":       3,
            "stage_label":         STAGE_LABELS[3],
            "advance_ready":       False,
            "next_stage":          None,
            "progress_days":       "—",
            "progress_tightness":  "—",
            "days_progress_pct":   1.0,
            "tight_progress_pct":  1.0,
            "message": "Peak stage. Injury baseline active as silent background watcher.",
        }

    days_ok  = days_pain_free >= req_days
    tight_ok = avg_tightness_14d <= req_tight

    days_pct  = min(days_pain_free / req_days, 1.0)
    # Tightness progress: 0 is best (10 = worst). Invert so bar fills towards goal.
    tight_pct = max(0.0, 1.0 - (avg_tightness_14d / req_tight)) if req_tight else 1.0

    return {
        "current_stage":       current_stage,
        "stage_label":         STAGE_LABELS[current_stage],
        "advance_ready":       days_ok and tight_ok,
        "next_stage":          criteria["next"],
        "progress_days":       f"{min(days_pain_free, req_days)}/{req_days} pain-free days",
        "progress_tightness":  f"Avg tightness {avg_tightness_14d:.1f} / max {req_tight:.1f}",
        "days_progress_pct":   round(days_pct, 3),
        "tight_progress_pct":  round(tight_pct, 3),
        "message": (
            "Advancement criteria met. Confirm with physio before progressing."
            if (days_ok and tight_ok)
            else "Keep logging. Criteria not yet met."
        ),
    }


def check_auto_stage_advance(
    current_stage: int,
    days_pain_free: int,
    avg_tightness_14d: float,
) -> dict:
    """
    Evaluate whether the stage should advance and return the verdict.

    This function only computes — it does NOT write to the database.
    The caller (Autoregulation page) is responsible for persisting the advance
    after the user confirms.

    Returns dict with keys:
        should_advance  : bool
        current_stage   : int
        next_stage      : int | None
        criteria_summary: str  (human-readable criteria status)
    """
    status = stage_status(current_stage, days_pain_free, avg_tightness_14d)
    return {
        "should_advance":   status["advance_ready"],
        "current_stage":    current_stage,
        "next_stage":       status.get("next_stage"),
        "criteria_summary": f"{status['progress_days']} — {status['progress_tightness']}",
    }
