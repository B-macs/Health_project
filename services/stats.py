"""
stats.py — Deterministic Statistical Engine.

Pure Python / NumPy / Pandas computations. No AI calls, no side effects.
Feeds pre-computed statistics into ai.py for clinical interpretation only.

Responsibilities:
  - Lag correlation between any two time series
  - Trend slope (linear regression)
  - Recovery direction classification
  - Session tonnage
  - Neural / urgent symptom keyword detection (deterministic pre-filter before LLM)
  - Full correlation pre-computation for macro trend analysis
"""

from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
#  Neural / urgent symptom detection
#  These rules are hard clinical criteria, not subjective assessments.
#  Match → deterministic "flag" before any LLM call is made.
# ─────────────────────────────────────────────────────────────────────────────

# Neurological symptoms associated with nerve root compression / cauda equina
NEURAL_KEYWORDS: tuple[str, ...] = (
    "shooting", "radiating", "radiate", "electric", "numb", "numbness",
    "tingling", "pins and needles", "weakness", "weak leg", "foot drop",
    "dead leg", "burning down", "sciatica", "sciatic", "nerve pain",
    "down my leg", "down the leg", "into my foot", "into the foot",
)

# Cauda equina red flags — require immediate medical attention
URGENT_KEYWORDS: tuple[str, ...] = (
    "bowel", "bladder", "incontinence", "saddle numbness", "saddle anaesthesia",
    "can't walk", "cannot walk", "loss of sensation", "paralysis", "paralysed",
    "cauda equina",
)


def detect_neural_symptoms(text: str) -> bool:
    """True if text contains neurological symptom keywords."""
    t = text.lower()
    return any(kw in t for kw in NEURAL_KEYWORDS)


def detect_urgent_symptoms(text: str) -> bool:
    """True if text contains cauda equina or other red-flag keywords."""
    t = text.lower()
    return any(kw in t for kw in URGENT_KEYWORDS)


def auto_warning_level(text: str) -> Optional[str]:
    """
    Deterministic pre-filter applied before any LLM call.

    Returns:
        "flag"    — urgent or neural symptoms detected
        "monitor" — (reserved for future rule expansion)
        None      — no clear deterministic signal; let LLM decide
    """
    if not text or not text.strip():
        return None
    if detect_urgent_symptoms(text):
        return "flag"
    if detect_neural_symptoms(text):
        return "flag"
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Time-series statistics
# ─────────────────────────────────────────────────────────────────────────────

def lag_correlation(
    series_a: list,
    series_b: list,
    lags: list[int] | None = None,
) -> dict[int, Optional[float]]:
    """
    Pearson correlation between series_a[t] and series_b[t - lag].

    Positive lag means: "did series_b some days ago predict series_a today?"
    Example: lag_correlation(hrv_series, au_series, [1,2,3])
             asks "does AU 1/2/3 days ago predict today's HRV?"

    Args:
        series_a: target (dependent) variable, one value per day
        series_b: predictor (lagged) variable, one value per day
        lags: list of lag offsets to test (default [1, 2, 3])

    Returns:
        {lag_days: correlation_coefficient | None}
    """
    if lags is None:
        lags = [1, 2, 3]

    MIN_OVERLAP = 5
    results: dict[int, Optional[float]] = {}

    s_a = pd.Series([float(v) if v is not None else np.nan for v in series_a])
    s_b = pd.Series([float(v) if v is not None else np.nan for v in series_b])

    for lag in lags:
        s_b_lagged = s_b.shift(lag)
        paired = pd.concat([s_a, s_b_lagged], axis=1).dropna()
        if len(paired) < MIN_OVERLAP:
            results[lag] = None
        else:
            corr = paired.iloc[:, 0].corr(paired.iloc[:, 1])
            results[lag] = round(float(corr), 3) if not np.isnan(corr) else None

    return results


def trend_slope(values: list) -> Optional[float]:
    """
    Linear regression slope across a time series.

    Positive → increasing over time, negative → decreasing.
    For pain/tightness: negative slope = improving.
    For HRV: positive slope = improving.

    Returns None if fewer than 3 non-null values.
    """
    clean = [float(v) for v in values if v is not None and not np.isnan(float(v))]
    if len(clean) < 3:
        return None
    x = np.arange(len(clean), dtype=float)
    slope = float(np.polyfit(x, np.array(clean), 1)[0])
    return round(slope, 5)


def recovery_direction(
    pain_values: list,
    tightness_values: list,
    slope_threshold: float = 0.05,
) -> str:
    """
    Deterministic recovery trajectory classification from pain and tightness trends.

    Returns: "improving" | "stable" | "degrading" | "insufficient_data"
    """
    pain_slope  = trend_slope(pain_values)
    tight_slope = trend_slope(tightness_values)

    available = [s for s in [pain_slope, tight_slope] if s is not None]
    if not available:
        return "insufficient_data"

    avg_slope = sum(available) / len(available)

    if avg_slope < -slope_threshold:
        return "improving"
    if avg_slope >  slope_threshold:
        return "degrading"
    return "stable"


# ─────────────────────────────────────────────────────────────────────────────
#  Workload computations
# ─────────────────────────────────────────────────────────────────────────────

def session_tonnage(set_rows: list[dict]) -> float:
    """
    Total volume load = Σ(reps_completed × weight_kg) across all sets.
    Standard tonnage metric in strength science.
    """
    return round(
        sum(
            (r.get("reps_completed") or 0) * (r.get("weight_kg") or 0.0)
            for r in set_rows
        ),
        1,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Full correlation pre-computation (fed to LLM for interpretation only)
# ─────────────────────────────────────────────────────────────────────────────

def _safe_series(rows: list[dict], key: str) -> list:
    return [r.get(key) for r in rows]


def _correlation_strength(r: Optional[float]) -> Optional[str]:
    """Classify Pearson r into weak / moderate / strong."""
    if r is None:
        return None
    abs_r = abs(r)
    if abs_r >= 0.6:
        return "strong"
    if abs_r >= 0.3:
        return "moderate"
    return "weak"


def compute_all_correlations(trend_data: dict) -> dict:
    """
    Pre-compute all lag correlations and trend slopes from the macro trend dataset.
    Returns a fully structured dict of computed statistics.
    This is passed to the LLM for clinical interpretation — not raw data rows.

    Correlation keys follow: "<predictor>_lag<N>_vs_<target>"
    """
    bio       = trend_data.get("biometrics", [])
    readiness = trend_data.get("readiness", [])
    sessions  = trend_data.get("sessions", [])

    # Extract aligned daily series
    hrv    = _safe_series(bio,       "hrv_ms")
    rhr    = _safe_series(bio,       "resting_heart_rate")
    sleep  = _safe_series(bio,       "sleep_duration_hours")
    pain   = _safe_series(readiness, "max_pain")
    tight  = _safe_series(readiness, "avg_tightness")
    stress = _safe_series(readiness, "avg_stress")
    au     = _safe_series(sessions,  "total_au")

    # Build lag correlation matrix
    lags = [1, 2, 3]
    raw_corrs: dict[str, dict] = {
        "au_to_hrv":    lag_correlation(hrv,   au,     lags),
        "au_to_rhr":    lag_correlation(rhr,   au,     lags),
        "au_to_pain":   lag_correlation(pain,  au,     lags),
        "au_to_tight":  lag_correlation(tight, au,     lags),
        "sleep_to_hrv": lag_correlation(hrv,   sleep,  [0, 1]),
        "sleep_to_pain":lag_correlation(pain,  sleep,  [1, 2]),
        "stress_to_hrv":lag_correlation(hrv,   stress, [0, 1]),
        "stress_to_pain":lag_correlation(pain, stress, [0, 1, 2]),
        "stress_to_tight":lag_correlation(tight,stress,[0, 1, 2]),
    }

    # Filter to statistically meaningful correlations (|r| ≥ 0.3)
    notable: list[dict] = []
    for pair, lag_dict in raw_corrs.items():
        for lag, r in lag_dict.items():
            strength = _correlation_strength(r)
            if strength in ("moderate", "strong"):
                notable.append({
                    "pair":     pair,
                    "lag_days": lag,
                    "r":        r,
                    "strength": strength,
                    "direction": "positive" if (r or 0) > 0 else "negative",
                })

    # Trend slopes
    slopes = {
        "pain_slope":      trend_slope(pain),
        "tightness_slope": trend_slope(tight),
        "hrv_slope":       trend_slope(hrv),
        "sleep_slope":     trend_slope(sleep),
        "au_slope":        trend_slope(au),
    }

    # Summary statistics (for context in LLM prompt)
    def _stats(vals: list) -> dict:
        clean = [v for v in vals if v is not None]
        if not clean:
            return {"n": 0}
        return {
            "n":    len(clean),
            "mean": round(float(np.mean(clean)), 2),
            "min":  round(float(np.min(clean)), 2),
            "max":  round(float(np.max(clean)), 2),
        }

    return {
        "notable_correlations": notable,
        "all_lag_correlations": raw_corrs,
        "slopes":               slopes,
        "recovery_direction":   recovery_direction(pain, tight),
        "summary_stats": {
            "hrv":    _stats(hrv),
            "pain":   _stats(pain),
            "tight":  _stats(tight),
            "sleep":  _stats(sleep),
            "au":     _stats(au),
            "stress": _stats(stress),
        },
        "data_quality": {
            "n_bio_days":       len([v for v in hrv if v is not None]),
            "n_readiness_days": len([v for v in pain if v is not None]),
            "n_session_days":   len([v for v in au if v is not None]),
        },
    }
