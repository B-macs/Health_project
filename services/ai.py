"""
ai.py -- Deterministic Rule-Based Text Parsers.

Replaces all external AI/API calls with explicit keyword matching,
scoring tables, and if/else decision trees.

No external services. No API keys. No probabilistic outputs.
The same input always produces the same output.

All four public functions maintain identical signatures and return structures
to the original API-based versions, so no other file requires changes.

# DETERMINISTIC-ONLY: text parsing via keyword tables and explicit rules.
# AI layer would be added on top only if documented limitation is found.
"""

from __future__ import annotations
from services import stats as _stats
from services import rules as _rules


# Placeholder constants kept for DB field `model_used` compatibility
MODEL_FAST  = "rules-based"
MODEL_SMART = "rules-based"


# ─────────────────────────────────────────────────────────────────────────────
#  KEYWORD TABLES
#  All tables are plain lists/dicts — edit directly to adjust behaviour.
#  No recompilation, no retraining, no model update required.
# ─────────────────────────────────────────────────────────────────────────────

# Severity keyword -> score (0-10).
# Checked in order — multi-word phrases before single words.
# First match that scores highest wins (worst-case clinical conservatism).
# DETERMINISTIC-ONLY: update this table to recalibrate severity scoring.
_SEVERITY_TABLE: list[tuple[str, int]] = [
    ("no pain",         0),
    ("pain free",       0),
    ("pain-free",       0),
    ("no tightness",    0),
    ("feels normal",    0),
    ("feels good",      0),
    ("feeling good",    0),
    ("all good",        0),
    ("excruciating",   10),
    ("unbearable",      9),
    ("agonising",       9),
    ("agony",           9),
    ("very sharp",      8),
    ("severe",          8),
    ("very tight",      7),
    ("very tightened",  7),   # from SENSATION_TAGS
    ("sharp",           7),
    ("intense",         7),
    ("radiating",       7),
    ("significant",     6),
    ("persistent",      5),
    ("constant",        5),
    ("moderate",        5),
    ("dull ache",       4),
    ("aching",          4),
    ("ache",            4),
    ("sore",            4),
    ("tight",           4),
    ("tightened",       4),
    ("stiff",           3),
    ("uncomfortable",   3),
    ("slightly tight",  2),
    ("slightly tired",  2),   # from SENSATION_TAGS
    ("mild tiredness",  2),   # from SENSATION_TAGS
    ("mild",            2),
    ("slight",          2),
    ("slightly",        2),
    ("minimal",         1),
    ("barely",          1),
    ("normal",          0),
    ("fine",            0),
    ("good",            0),
]

# Sensation phrase -> sensation_type enum value.
# Checked in order — more specific / higher priority entries first.
# DETERMINISTIC-ONLY: add new terms here to expand recognition.
_SENSATION_MAP: list[tuple[str, str]] = [
    # Neural — highest priority (safety-critical)
    ("pins and needles", "neural"),
    ("shooting pain",    "neural"),
    ("shooting",         "neural"),
    ("radiating",        "neural"),
    ("radiate",          "neural"),
    ("electric",         "neural"),
    ("numbness",         "neural"),
    ("numb",             "neural"),
    ("tingling",         "neural"),
    ("burning",          "neural"),
    ("sciatica",         "neural"),
    ("down my leg",      "neural"),
    ("down the leg",     "neural"),
    ("into my foot",     "neural"),
    ("into the foot",    "neural"),
    ("weakness",         "neural"),
    ("weak leg",         "neural"),
    # Sharp
    ("very sharp",       "sharp"),
    ("sharp",            "sharp"),
    # Tight
    ("very tightened",   "tight"),
    ("very tight",       "tight"),
    ("tightened",        "tight"),
    ("tight",            "tight"),
    # Stiff
    ("stiff",            "stiff"),
    # Dull ache
    ("dull ache",        "dull_ache"),
    ("aching",           "dull_ache"),
    ("throbbing",        "dull_ache"),
    ("sore",             "dull_ache"),
    ("ache",             "dull_ache"),
    ("dull",             "dull_ache"),
    # Fatigue
    ("exhausted",        "fatigue"),
    ("fatigued",         "fatigue"),
    ("fatigue",          "fatigue"),
    ("heavy legs",       "fatigue"),
    ("heavy",            "fatigue"),
    ("tired",            "fatigue"),
    # Normal
    ("feels normal",     "normal"),
    ("normal",           "normal"),
    ("comfortable",      "normal"),
    ("fine",             "normal"),
    ("good",             "normal"),
]

# Body-part phrases -> canonical location string.
# More specific phrases first to prevent partial matches.
# DETERMINISTIC-ONLY: add laterality-qualified phrases before generic ones.
_BODY_PART_MAP: list[tuple[list[str], str]] = [
    # ── Lumbar spine (level-specific, laterality-qualified first) ────────────
    (["right l5", "l5/s1 right", "l5 right", "right side l5"],
     "Lumbar -- L5/S1 (Right -- Primary)"),
    (["left l5", "l5/s1 left", "l5 left", "left side l5"],
     "Lumbar -- L5/S1 (Left)"),
    (["l5/s1", "l5-s1", "l5 s1", "s1 junction", "lumbosacral junction"],
     "Lumbar -- L5/S1 (Right -- Primary)"),
    (["l5"],
     "Lumbar -- L5/S1 (Right -- Primary)"),
    (["l4/l5", "l4-l5", "l4 l5"],
     "Lumbar -- L4/L5 (Left)"),
    (["l4"],
     "Lumbar -- L4/L5 (Left)"),
    (["l3/l4", "l3-l4", "l3 l4"],
     "Lumbar -- L3/L4 (Left)"),
    (["l3"],
     "Lumbar -- L3/L4 (Left)"),
    (["lower back", "lumbar", "lumbosacral", "l-spine", "low back"],
     "Central Lower Back"),
    # ── Hip flexor / psoas ────────────────────────────────────────────────────
    (["right hip flexor", "right psoas", "right iliopsoas"],
     "Hip Flexor / Psoas -- Right"),
    (["left hip flexor", "left psoas", "left iliopsoas",
      "hip flexor", "psoas", "iliopsoas"],
     "Hip Flexor / Psoas -- Left"),
    # ── Sacroiliac joint ──────────────────────────────────────────────────────
    (["right sacroiliac", "right si joint", "right si"],
     "Sacroiliac Joint -- Right"),
    (["left sacroiliac", "left si joint", "left si",
      "sacroiliac", "si joint", "sij"],
     "Sacroiliac Joint -- Left"),
    # ── Glute (medius before general glute) ───────────────────────────────────
    (["right glute medius", "right glute med"],
     "Glute Medius -- Right"),
    (["left glute medius", "left glute med", "glute medius", "glute med"],
     "Glute Medius -- Left"),
    (["right glute", "right buttock"],
     "Glute -- Right"),
    (["left glute", "left buttock", "glute", "buttock", "gluteus"],
     "Glute -- Left"),
    # ── Piriformis ────────────────────────────────────────────────────────────
    (["right piriformis"],
     "Piriformis -- Right"),
    (["left piriformis", "piriformis"],
     "Piriformis -- Left"),
    # ── Hamstring ─────────────────────────────────────────────────────────────
    (["right hamstring"],
     "Hamstring -- Right"),
    (["left hamstring", "hamstring"],
     "Hamstring -- Left"),
    # ── Calf ─────────────────────────────────────────────────────────────────
    (["right calf", "right gastrocnemius", "right soleus"],
     "Calf -- Right"),
    (["left calf", "left gastrocnemius", "left soleus",
      "calf", "gastrocnemius", "soleus"],
     "Calf -- Left"),
    # ── Thoracic / mid back ───────────────────────────────────────────────────
    (["mid back", "midback", "thoracic", "upper back",
      "between shoulder", "middle back", "t-spine"],
     "Thoracic / Mid Back"),
]

# Sentiment words for session note scoring.
# Positive: +0.1 each. Negative: -0.15 each.
# DETERMINISTIC-ONLY: extend these lists to improve scoring accuracy.
_POSITIVE_WORDS: list[str] = [
    "good", "great", "strong", "controlled", "comfortable", "easy",
    "better", "improved", "looser", "loose", "flexible", "progressing",
    "confident", "smooth", "positive", "solid", "clean", "nice", "well",
    "pain free", "pain-free", "no pain", "felt good", "felt strong",
]
_NEGATIVE_WORDS: list[str] = [
    "pain", "painful", "sore", "hurt", "hurting", "aching",
    "struggling", "struggled", "difficult", "compensating", "compensated",
    "backed off", "stopped early", "couldn't", "unable", "cannot",
    "heavy", "exhausted", "failed", "bad", "worse", "worsening",
    "concerning", "worried",
]

# Known MRI injury areas for correlates_with_injury detection.
# Derived from diagnostic_profile MRI findings (10.11.2025).
# DETERMINISTIC-ONLY: update if injury profile changes.
_MRI_INJURY_KEYWORDS: tuple[str, ...] = (
    "l5", "s1", "l4", "l3",
    "lower back", "lumbar",
    "hip flexor", "psoas",
    "glute", "sacroiliac", "si joint",
    "right side", "right leg", "right hip", "right back",
)

# Headline templates keyed by recovery_direction (from stats.py).
_HEADLINES: dict[str, str] = {
    "improving":          "Recovery metrics trending positively -- pain and tightness on a downward trajectory.",
    "stable":             "Recovery plateau detected -- metrics are stable but not progressing.",
    "degrading":          "Warning: pain and tightness trending negatively -- load management review required.",
    "insufficient_data":  "Insufficient data for trend analysis -- 14+ days of consistent logging required.",
}

# Load management notes keyed by AU slope direction.
_LOAD_NOTES: dict[str, str] = {
    "rising":   "Session training load is trending upward. Monitor ACWR ceiling to prevent overreach.",
    "falling":  "Session training load is trending downward. Ensure volume stays above minimum tissue stimulus.",
    "stable":   "Session training load is stable. Current periodisation is consistent.",
    "no_data":  "No training session data available. Begin logging sessions to enable load analysis.",
}

# Recommendations keyed by recovery_direction.
_RECOMMENDATIONS: dict[str, list[str]] = {
    "improving": [
        "Continue current protocol -- pain and tightness trend is improving.",
        "Review Stage advancement criteria if pain-free streak is approaching 14+ days.",
        "Maintain sleep consistency as the primary biometric readiness driver.",
    ],
    "stable": [
        "Plateau detected -- introduce variability in movement selection or session structure.",
        "Check whether ACWR has been consistently below 0.8 (undertraining stalling adaptation).",
        "Prioritise sleep and stress management to break the stable plateau.",
    ],
    "degrading": [
        "Reduce training load immediately -- bring ACWR back within optimal range (0.8-1.2).",
        "Audit lifestyle factors: sleep disruption, elevated stress, and travel commonly precede metric degradation.",
        "If degradation persists beyond 5 days, implement a structured deload week.",
        "Cross-reference daily readiness notes for specific aggravating movement patterns.",
    ],
    "insufficient_data": [
        "Log daily readiness (tightness, pain score) and biometrics every day.",
        "Target at least 14 consecutive data days before expecting pattern output.",
        "Session notes do not need to be long -- a single descriptive sentence per session is sufficient.",
    ],
}

# Correlation interpretation templates.
# Key: (pair_name, direction). Value: template with {lag} placeholder.
# DETERMINISTIC-ONLY: edit templates to adjust clinical language.
_CORR_TEMPLATES: dict[tuple[str, str], str] = {
    # Training load -> HRV
    ("au_to_hrv", "negative"): (
        "Training load ({lag}d lag) suppresses HRV -- acute load is compressing biometric recovery time. Review inter-session spacing."
    ),
    ("au_to_hrv", "positive"): (
        "Training load ({lag}d lag) positively associates with HRV -- possible cardiovascular adaptation response. Maintain current load."
    ),
    # Training load -> RHR
    ("au_to_rhr", "positive"): (
        "Training load ({lag}d lag) correlates with elevated RHR -- cardiovascular recovery may be insufficient between sessions."
    ),
    ("au_to_rhr", "negative"): (
        "Training load ({lag}d lag) negatively associated with RHR -- possible cardiovascular conditioning effect."
    ),
    # Training load -> pain
    ("au_to_pain", "positive"): (
        "Training load ({lag}d lag) correlates with increased pain -- monitor the recovery window and reduce load if pain persists."
    ),
    ("au_to_pain", "negative"): (
        "Training load ({lag}d lag) negatively associated with pain -- movement is providing therapeutic benefit to tissue."
    ),
    # Training load -> tightness
    ("au_to_tight", "positive"): (
        "Training load ({lag}d lag) predicts elevated tightness -- add targeted mobility work in the {lag}-day post-session window."
    ),
    ("au_to_tight", "negative"): (
        "Training load ({lag}d lag) negatively associated with tightness -- training is reducing tissue restriction over time."
    ),
    # Sleep -> HRV
    ("sleep_to_hrv", "positive"): (
        "Sleep duration ({lag}d lag) positively correlated with HRV -- sleep is a primary biometric readiness driver. Protect it."
    ),
    ("sleep_to_hrv", "negative"): (
        "Negative sleep-to-HRV pattern ({lag}d lag) -- review sleep quality alongside duration; quantity alone may be insufficient."
    ),
    # Sleep -> pain
    ("sleep_to_pain", "negative"): (
        "Better sleep ({lag}d lag) associates with lower pain -- sleep quality is directly influencing pain sensitivity."
    ),
    ("sleep_to_pain", "positive"): (
        "Poor sleep ({lag}d lag) correlates with elevated pain -- sleep deprivation is amplifying pain perception."
    ),
    # Stress -> HRV
    ("stress_to_hrv", "negative"): (
        "Psychological stress ({lag}d lag) predicts lower HRV -- autonomic suppression from cognitive load is measurable."
    ),
    ("stress_to_hrv", "positive"): (
        "Unexpected positive stress-to-HRV association ({lag}d lag) -- possible arousal effect or data anomaly. Review context."
    ),
    # Stress -> pain
    ("stress_to_pain", "positive"): (
        "Psychological stress ({lag}d lag) correlates with pain elevation -- central sensitisation pattern from cortisol load."
    ),
    ("stress_to_pain", "negative"): (
        "Higher stress negatively associated with pain ({lag}d lag) -- possible distraction effect. Monitor for trend reversal."
    ),
    # Stress -> tightness
    ("stress_to_tight", "positive"): (
        "Psychological stress ({lag}d lag) correlates with muscle tightness -- cortisol-driven muscle guarding pattern."
    ),
    ("stress_to_tight", "negative"): (
        "Stress negatively associated with tightness ({lag}d lag) -- unexpected pattern, check data completeness."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
#  INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _lower(text: str) -> str:
    return text.lower()


def extract_body_parts(text: str) -> list[str]:
    """
    Match text against _BODY_PART_MAP and return unique canonical location strings.
    Checks multi-word phrases before single keywords to prevent partial matches.
    """
    t = _lower(text)
    found: list[str] = []
    for phrases, canonical in _BODY_PART_MAP:
        if any(phrase in t for phrase in phrases):
            if canonical not in found:
                found.append(canonical)
    return found


def extract_sensation_types(text: str) -> list[str]:
    """
    Match text against _SENSATION_MAP and return unique sensation type strings.
    Order in _SENSATION_MAP controls priority (neural first).
    """
    t = _lower(text)
    found: list[str] = []
    for phrase, sensation in _SENSATION_MAP:
        if phrase in t and sensation not in found:
            found.append(sensation)
    return found


def infer_severity(text: str) -> float:
    """
    Scan text against _SEVERITY_TABLE and return the highest severity score found.
    Clinically conservative: returns worst-case (highest) match.
    Returns 0.0 if no severity keywords detected.
    """
    t = _lower(text)
    max_score = 0
    for phrase, score in _SEVERITY_TABLE:
        if phrase in t:
            max_score = max(max_score, score)
    return float(max_score)


def compute_sentiment(text: str) -> float:
    """
    Deterministic sentiment score (-1.0 to 1.0) from keyword presence.
    Positive words: +0.1 each. Negative words: -0.15 each.
    Neural symptoms: automatic -0.5 penalty.
    Score clamped to [-1.0, 1.0].
    """
    t = _lower(text)
    score = 0.0
    for w in _POSITIVE_WORDS:
        if w in t:
            score += 0.1
    for w in _NEGATIVE_WORDS:
        if w in t:
            score -= 0.15
    if _stats.detect_neural_symptoms(text):
        score -= 0.5
    if _stats.detect_urgent_symptoms(text):
        score -= 1.0
    return round(max(-1.0, min(1.0, score)), 2)


def _rules_warning_level(sensations: list[str], severity: float) -> str:
    """
    If/else decision tree for warning level.
    stats.auto_warning_level() handles neural/urgent before this is called.
    DETERMINISTIC-ONLY: thresholds are explicit and editable.
    """
    if "neural" in sensations:
        return "flag"
    if severity >= 8:
        return "flag"
    if severity >= 5:
        return "monitor"
    if "sharp" in sensations:
        return "monitor"
    if severity >= 3:
        return "monitor"
    return "none"


def _correlates_with_injury(body_parts: list[str]) -> bool:
    """
    True if any detected body part overlaps with documented MRI injury areas.
    Based on L5/S1 primary pathology and L3-L5 secondary pathology.
    """
    for part in body_parts:
        part_lower = part.lower()
        if any(kw in part_lower for kw in _MRI_INJURY_KEYWORDS):
            return True
    return False


def _generate_session_summary(
    raw_text: str,
    body_parts: list[str],
    sensations: list[str],
    warning_level: str,
) -> str:
    """
    Template-based summary. No prose generation — uses structured extracted data.
    """
    excerpt = raw_text[:100].strip().rstrip(".,")
    if len(raw_text) > 100:
        excerpt += "..."
    parts_str = ", ".join(body_parts) if body_parts else "no specific areas"
    sens_str  = ", ".join(s.replace("_", " ") for s in sensations) if sensations else "not specified"

    if warning_level == "flag":
        return f"FLAGGED: {parts_str} -- {sens_str} detected. Note: '{excerpt}'"
    if warning_level == "monitor":
        return f"Monitor: {parts_str}. Sensation: {sens_str}. Note: '{excerpt}'"
    return f"Session logged. Areas: {parts_str}. Sensation: {sens_str}. Note: '{excerpt}'"


# ─────────────────────────────────────────────────────────────────────────────
#  PUBLIC API  (same signatures as original API-based version)
# ─────────────────────────────────────────────────────────────────────────────

def parse_session_note(raw_text: str, injury_profile: dict) -> dict:
    """
    Parse a gym session note into structured clinical fields.
    Uses keyword matching against _BODY_PART_MAP, _SENSATION_MAP, _SEVERITY_TABLE.
    Neural/urgent symptoms detected by stats.auto_warning_level() always escalate to 'flag'.

    Returns: {summary, sentiment_score, flagged_body_parts, warning_level}
    """
    if not raw_text or not raw_text.strip():
        return {
            "summary":           "No note provided.",
            "sentiment_score":   0.0,
            "flagged_body_parts": [],
            "warning_level":     "none",
        }

    body_parts = extract_body_parts(raw_text)
    sensations = extract_sensation_types(raw_text)
    severity   = infer_severity(raw_text)
    sentiment  = compute_sentiment(raw_text)

    # Deterministic pre-filter: neural/urgent symptoms always → "flag"
    auto_level    = _stats.auto_warning_level(raw_text)
    warning_level = auto_level if auto_level else _rules_warning_level(sensations, severity)

    return {
        "summary":            _generate_session_summary(raw_text, body_parts, sensations, warning_level),
        "sentiment_score":    sentiment,
        "flagged_body_parts": body_parts,
        "warning_level":      warning_level,
    }


def parse_tightness(text: str, injury_profile: dict) -> dict:
    """
    Parse a subjective tightness description into structured severity and body map.
    Uses keyword matching against _BODY_PART_MAP, _SENSATION_MAP, _SEVERITY_TABLE.
    Neural/urgent symptoms detected by stats.auto_warning_level() always escalate to 'flag'.

    Returns: {severity, body_parts, sensation_type, warning_level, correlates_with_injury, auto_flagged}
    """
    if not text or not text.strip():
        return {
            "severity":              0.0,
            "body_parts":            [],
            "sensation_type":        ["normal"],
            "warning_level":         "none",
            "correlates_with_injury": False,
            "auto_flagged":          False,
        }

    body_parts = extract_body_parts(text)
    sensations = extract_sensation_types(text)
    severity   = infer_severity(text)

    # Deterministic pre-filter: neural/urgent symptoms always → "flag"
    auto_level    = _stats.auto_warning_level(text)
    auto_flagged  = auto_level is not None
    warning_level = auto_level if auto_level else _rules_warning_level(sensations, severity)

    return {
        "severity":              severity,
        "body_parts":            body_parts,
        "sensation_type":        sensations if sensations else ["normal"],
        "warning_level":         warning_level,
        "correlates_with_injury": _correlates_with_injury(body_parts),
        "auto_flagged":          auto_flagged,
    }


def analyze_macro_trends(trend_data: dict, injury_profile: dict) -> dict:
    """
    Deterministic macro trend analysis.
    Step 1: stats.compute_all_correlations() computes all lag correlations in Python.
    Step 2: Template lookup maps computed statistics to clinical interpretation strings.
    recovery_direction is always from stats.recovery_direction() -- not inferred from text.

    Returns: {headline, correlation_interpretations, load_management_note,
              recommendations, recovery_direction, computed_correlations}
    """
    computed     = _stats.compute_all_correlations(trend_data)
    notable      = computed.get("notable_correlations", [])
    slopes       = computed.get("slopes", {})
    recovery_dir = computed["recovery_direction"]
    dq           = computed.get("data_quality", {})

    # Headline from recovery direction lookup table
    headline = _HEADLINES.get(recovery_dir, _HEADLINES["insufficient_data"])

    # Correlation interpretations from template table
    interpretations: list[dict] = []
    for c in notable:
        template = _CORR_TEMPLATES.get((c["pair"], c["direction"]))
        if template:
            interpretations.append({
                "variable_pair": c["pair"].replace("_to_", " -> ").replace("_", " "),
                "lag_days":      c["lag_days"],
                "clinical_note": template.format(lag=c["lag_days"]),
            })

    # Load management note from AU slope
    au_slope = slopes.get("au_slope")
    if au_slope is None or dq.get("n_session_days", 0) == 0:
        load_note = _LOAD_NOTES["no_data"]
    elif au_slope > 0.05:
        load_note = _LOAD_NOTES["rising"]
    elif au_slope < -0.05:
        load_note = _LOAD_NOTES["falling"]
    else:
        load_note = _LOAD_NOTES["stable"]

    return {
        "headline":                 headline,
        "correlation_interpretations": interpretations,
        "load_management_note":     load_note,
        "recommendations":          _RECOMMENDATIONS.get(recovery_dir, []),
        "recovery_direction":       recovery_dir,
        "computed_correlations":    computed,
    }


def assess_movement_risk(
    injury_profile: dict,
    recent_notes_summary: str,
    stage: int = 1,
) -> dict:
    """
    Deterministic movement risk assessment from rules.py + keyword analysis of notes.
    No probabilistic scoring. All outputs are derived from documented injury rules.

    Returns: {risk_summary, flagged_movements, safe_movements, correlation_notes}
    """
    safety      = _rules.movement_safety_summary(stage)
    constraints = safety["constraints"]

    # Standard MRI-derived risk summary (deterministic from injury profile + stage)
    risk_summary = (
        f"Stage {stage} movement profile -- deterministic rules applied from MRI findings (10.11.2025). "
        f"L5/S1 right dorsolateral disc protrusion with moderate foraminal stenosis: "
        f"axial compression, hyperextension, and right lateral loading contraindicated at all stages. "
        f"Covered annulus tears L3/4 and L4/5: end-range lumbar flexion and rotation under load contraindicated. "
        f"ACWR ceiling: {constraints['acwr_ceiling']}. "
        f"RPE ceiling: {constraints['rpe_ceiling']}. "
        f"Volume cap: {int(constraints['volume_cap_pct'] * 100)}% of baseline."
    )

    # Keyword analysis of recent notes to identify frequently mentioned areas
    problem_areas = extract_body_parts(recent_notes_summary) if recent_notes_summary else []

    # Check if flagged areas overlap with MRI injury pathway
    mri_overlap = [
        a for a in problem_areas
        if any(kw in a.lower() for kw in _MRI_INJURY_KEYWORDS)
    ]

    if mri_overlap:
        corr_note = (
            f"Keyword analysis of recent session notes detected these injury-relevant areas: "
            f"{', '.join(mri_overlap)}. "
            f"These align with documented MRI pathology (L-spine to hip kinetic chain). "
            f"Apply movement constraints for these regions accordingly."
        )
    elif problem_areas:
        corr_note = (
            f"Recent session notes mention: {', '.join(problem_areas)}. "
            f"No direct MRI-pathway overlap detected in note keywords. Continue monitoring."
        )
    else:
        corr_note = (
            "No specific anatomical areas detected in recent session notes. "
            "Ensure notes include location-specific descriptions "
            "(e.g. 'lower back', 'right hip', 'L5') to enable keyword detection."
        )

    return {
        "risk_summary":      risk_summary,
        "flagged_movements": safety["always_contraindicated"] + safety["caution"],
        "safe_movements":    safety["cleared"],
        "correlation_notes": corr_note,
    }
