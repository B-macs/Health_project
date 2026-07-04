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
import rules as _rules


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


def au_to_strain(raw_au: float, stage: int = 1) -> float:
    """
    Convert Foster AU to a 0-21 strain score with stage-specific CLF scaling.

    The database always stores raw Foster AU (RPE × duration) so historical
    comparisons stay valid. CLF is applied at display/computation time only.
    """
    clf          = STAGE_CLF.get(stage, 1.0)
    effective_au = raw_au * clf
    if effective_au <= 0:
        return 0.0
    return round(min(21.0, math.log(effective_au + 1) / math.log(601.0) * 21.0), 1)


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


def _worst_signal(*signals) -> str:
    return min(signals, key=lambda s: _SIGNAL_PRIORITY.get(s, 2))


def _safe_avg(rows: list[dict], key: str):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def traffic_light(biometric_rows: list[dict]) -> dict:
    """
    Evaluate daily biometrics against rolling baselines.

    Args:
        biometric_rows: list of dicts from get_biometric_rolling(), sorted
                        ascending by date. Must include: hrv_ms,
                        resting_heart_rate, sleep_duration_hours.

    Returns dict with keys:
        overall         : "green" | "yellow" | "red" | "grey"
        status          : "ok" | "insufficient_data"
        volume_multiplier_from_traffic : float
        metrics         : dict per metric with value/baseline/signal/delta_pct
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

    overall = _worst_signal(*signals)
    vol_mult = {"green": 1.0, "yellow": 0.75, "red": 0.0, "grey": 1.0}[overall]

    messages = {
        "green":  "Biometrics at or above baseline. Full training capacity.",
        "yellow": "Biometrics slightly below baseline. Volume reduction applied.",
        "red":    "Biometrics significantly degraded. Rest or mobility only.",
        "grey":   "Some metrics unavailable. Engine using available data.",
    }

    return {
        "overall":  overall,
        "status":   "ok",
        "volume_multiplier_from_traffic": vol_mult,
        "metrics":  metrics,
        "data_days": len(biometric_rows),
        "message":  messages[overall],
    }


# ─────────────────────────────────────────────────────────────────────────────
#  ACWR — Acute-to-Chronic Workload Ratio
#  Foster method: session_au = session_rpe × session_duration_minutes
# ─────────────────────────────────────────────────────────────────────────────

# Sweet spot range per sport science literature (Blanch & Gabbett, 2016)
ACWR_OPTIMAL_LOW  = 0.8
ACWR_OPTIMAL_HIGH = 1.3   # overridden to 1.2 for Stage 1

def acwr(daily_au_rows: list[dict], stage: int = 1) -> dict:
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
    today     = date.today()
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
