"""
rules.py — Deterministic Movement Safety Rules.

Hard clinical constraints derived directly from the MRI report (10.11.2025)
and established sports medicine guidelines for lumbar disc pathology.

These rules fire before and independently of any AI call.
No LLM should override a "contraindicated" ruling — that is a hard stop.

MRI reference summary:
  L5/S1: activated osteochondrosis, retrolisthesis, right dorsolateral disc
         protrusion, moderate right foraminal stenosis.
  L4/5:  flat protrusion left dorsolateral, covered annulus tear, retrolisthesis,
         mild foraminal stenosis.
  L3/4:  flat protrusion left dorsolateral, covered annulus tear, mild foraminal
         stenosis.
  Cleared: spinal canal, facet joints, ISG, back musculature (no atrophy).
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────────────
#  Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MovementRule:
    movement: str           # name or keyword (matched case-insensitively)
    reason: str             # clinical justification
    stage_cap: int          # safest from this stage onwards (1=always, 3=perf only)
    severity: str           # "contraindicated" | "caution" | "cleared"
    laterality: str = "bilateral"  # "left" | "right" | "bilateral" | "axial"


# ─────────────────────────────────────────────────────────────────────────────
#  Hard movement rules (derived from MRI + clinical guidelines)
# ─────────────────────────────────────────────────────────────────────────────

MOVEMENT_RULES: list[MovementRule] = [
    # ── Contraindicated (any stage) ──────────────────────────────────────────
    MovementRule(
        movement="heavy deadlift",
        reason="High axial compression on L5/S1 osteochondrosis. Retrolisthesis risks further posterior shear.",
        stage_cap=1, severity="contraindicated", laterality="axial",
    ),
    MovementRule(
        movement="barbell deadlift",
        reason="High axial compression on L5/S1 osteochondrosis.",
        stage_cap=1, severity="contraindicated", laterality="axial",
    ),
    MovementRule(
        movement="conventional deadlift",
        reason="High axial compression on L5/S1 osteochondrosis.",
        stage_cap=1, severity="contraindicated", laterality="axial",
    ),
    MovementRule(
        movement="hyperextension",
        reason="L5/S1 retrolisthesis — lumbar hyperextension compresses already-narrowed right foramen.",
        stage_cap=1, severity="contraindicated", laterality="right",
    ),
    MovementRule(
        movement="back extension",
        reason="L5/S1 retrolisthesis — lumbar hyperextension compresses already-narrowed right foramen.",
        stage_cap=1, severity="contraindicated", laterality="right",
    ),
    MovementRule(
        movement="seated forward fold",
        reason="End-range lumbar flexion loads covered annulus tears at L3/4 and L4/5.",
        stage_cap=1, severity="contraindicated", laterality="bilateral",
    ),
    MovementRule(
        movement="forward fold",
        reason="End-range lumbar flexion loads covered annulus tears at L3/4 and L4/5. "
               "Generalizes 'seated forward fold' to catch named variants (e.g. yoga poses).",
        stage_cap=1, severity="contraindicated", laterality="bilateral",
    ),
    MovementRule(
        movement="toe touch",
        reason="End-range lumbar flexion loads covered annulus tears at L3/4 and L4/5.",
        stage_cap=1, severity="contraindicated", laterality="bilateral",
    ),
    MovementRule(
        movement="leg press",
        reason="Hip flexion at end-range under load increases intradiscal pressure at L3-L5.",
        stage_cap=1, severity="contraindicated", laterality="bilateral",
    ),
    MovementRule(
        movement="sit up",
        reason="Spinal flexion under load — contraindicated with covered annulus tears.",
        stage_cap=1, severity="contraindicated", laterality="bilateral",
    ),
    MovementRule(
        movement="crunch",
        reason="Spinal flexion under load — contraindicated with covered annulus tears.",
        stage_cap=1, severity="contraindicated", laterality="bilateral",
    ),
    MovementRule(
        movement="impact",
        reason="Axial impact loads activate L5/S1 osteochondrosis.",
        stage_cap=1, severity="contraindicated", laterality="axial",
    ),
    MovementRule(
        movement="jumping",
        reason="Axial impact loads activate L5/S1 osteochondrosis.",
        stage_cap=1, severity="contraindicated", laterality="axial",
    ),
    MovementRule(
        movement="box jump",
        reason="Axial impact loads activate L5/S1 osteochondrosis.",
        stage_cap=1, severity="contraindicated", laterality="axial",
    ),
    MovementRule(
        movement="running",
        reason="Repetitive axial impact — contraindicated in Stage 1 with active osteochondrosis.",
        stage_cap=2, severity="contraindicated", laterality="axial",
    ),

    # ── Caution: Stage 1 — cleared from Stage 2 with monitoring ─────────────
    MovementRule(
        movement="romanian deadlift",
        reason="Hip hinge with light load acceptable. Watch for right-side L5/S1 symptoms. No lumbar rounding.",
        stage_cap=2, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="hip hinge",
        reason="Neutral-spine hip hinge is a rehab fundamental. Heavy versions require Stage 2+.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="squat",
        reason="Axial load in spinal flexion. Light goblet squat acceptable Stage 1; barbell squat Stage 3 only.",
        stage_cap=2, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="good morning",
        reason="Loads the lumbar spine in flexion under load — annulus tear risk.",
        stage_cap=3, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="right lateral",
        reason="Right foraminal stenosis at L5/S1 — right lateral flexion narrows foramen further.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="left lateral",
        reason="Left dorsolateral protrusions L3-L5 — left lateral flexion under load risks annulus progression.",
        stage_cap=1, severity="caution", laterality="left",
    ),
    MovementRule(
        movement="rotation under load",
        reason="Rotational shear with active disc pathology at L3-L5.",
        stage_cap=2, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="overhead press",
        reason="Lumbar extension moment under load compresses L5/S1 foramen.",
        stage_cap=2, severity="caution", laterality="axial",
    ),
    MovementRule(
        movement="bulgarian split squat",
        reason="Hip flexion loading — acceptable if neutral lumbar maintained. Monitor right-side symptoms.",
        stage_cap=2, severity="caution", laterality="right",
    ),

    # ── Cleared: safe across stages with correct technique ───────────────────
    MovementRule(
        movement="cat-cow",
        reason="Gentle controlled spinal mobility — standard L-spine rehab movement.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="bird-dog",
        reason="Neutral spine, contralateral stabilisation — primary rehab movement for L5/S1.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="dead bug",
        reason="Neutral spine core activation — no lumbar loading.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="glute bridge",
        reason="Hip extension without spinal compression — primary rehab movement.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="clamshell",
        reason="Glute medius activation — unloaded hip external rotation.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="pallof press",
        reason="Anti-rotation core — neutral spine, no compressive load.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="walking",
        reason="Low-impact movement — maintains tissue health without axial impact.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="swimming",
        reason="Unloaded spinal movement — ideal for active recovery.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="stationary cycling",
        reason="Cardiovascular without axial impact. Maintain neutral lumbar position.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="mcgill",
        reason="McGill Big 3 — evidence-based protocol for lumbar disc pathology.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="hip flexor stretch",
        reason="Psoas release — directly addresses L1-L4 tightness driving L5/S1 compression.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="piriformis stretch",
        reason="Piriformis release — reduces hip lateral rotator tension downstream of L-spine.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="face pull",
        reason="Posterior shoulder without lumbar load. Maintain upright posture.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="lateral band walk",
        reason="Glute medius activation — minimal spinal load.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
#  Stage-specific volume caps and ACWR ceilings (single source of truth)
#  engine.py references these via get_stage_constraints()
# ─────────────────────────────────────────────────────────────────────────────

STAGE_CONSTRAINTS: dict[int, dict] = {
    1: {
        "label":            "Rehab — Tissue Tolerance",
        "acwr_ceiling":     1.2,
        "volume_cap_pct":   0.70,   # max 70% of projected baseline volume
        "rpe_ceiling":      7,      # RPE hard cap per session
        "session_freq_max": 4,      # max sessions per week
        "description":      "Conservative tissue tolerance phase. Strict ACWR ceiling.",
    },
    2: {
        "label":            "Transition — Work Capacity",
        "acwr_ceiling":     1.3,
        "volume_cap_pct":   0.90,
        "rpe_ceiling":      8,
        "session_freq_max": 5,
        "description":      "Graduated loading. Rehab movements blend into training.",
    },
    3: {
        "label":            "Performance & Growth",
        "acwr_ceiling":     1.5,
        "volume_cap_pct":   1.0,
        "rpe_ceiling":      10,
        "session_freq_max": 6,
        "description":      "Full performance focus. Injury baseline passive background watcher.",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────────

def check_movement(movement_name: str, current_stage: int) -> dict:
    """
    Evaluate a movement against the deterministic rule set.

    Returns:
        {
            severity:  "contraindicated" | "caution" | "cleared" | "unknown",
            reason:    str,
            laterality: str,
            stage_available: int | None,  (which stage it becomes appropriate)
        }
    """
    name_lower = movement_name.lower()

    # Find the strictest matching rule
    matched: list[MovementRule] = []
    for rule in MOVEMENT_RULES:
        if rule.movement in name_lower or name_lower in rule.movement:
            matched.append(rule)

    if not matched:
        return {
            "severity":        "unknown",
            "reason":          "No matching rule found. Apply clinical judgment.",
            "laterality":      "bilateral",
            "stage_available": None,
        }

    # Take the most conservative matched rule
    priority = {"contraindicated": 0, "caution": 1, "cleared": 2, "unknown": 3}
    strictest = min(matched, key=lambda r: priority.get(r.severity, 3))

    # Check if this movement is available in the current stage
    stage_ok = current_stage >= strictest.stage_cap

    return {
        "severity":        strictest.severity if stage_ok else "contraindicated",
        "reason":          strictest.reason,
        "laterality":      strictest.laterality,
        "stage_available": strictest.stage_cap,
        "stage_ok":        stage_ok,
    }


def get_contraindicated_always() -> list[str]:
    """Movements that are contraindicated regardless of stage."""
    return [r.movement for r in MOVEMENT_RULES if r.severity == "contraindicated" and r.stage_cap == 1]


def get_cleared_for_stage(stage: int) -> list[str]:
    """Movements explicitly cleared at or below the given stage."""
    return [r.movement for r in MOVEMENT_RULES if r.severity == "cleared" and r.stage_cap <= stage]


def get_caution_movements(stage: int) -> list[str]:
    """Movements in the caution zone for the given stage."""
    return [
        r.movement for r in MOVEMENT_RULES
        if r.severity == "caution" and r.stage_cap <= stage
    ]


def get_stage_constraints(stage: int) -> dict:
    """Return stage-specific volume/load constraints."""
    return STAGE_CONSTRAINTS.get(stage, STAGE_CONSTRAINTS[1])


def movement_safety_summary(stage: int) -> dict:
    """
    Return a full safety summary for the given stage.
    Used by the Autoregulation page and as context for AI movement risk assessment.
    """
    return {
        "stage":              stage,
        "constraints":        get_stage_constraints(stage),
        "always_contraindicated": get_contraindicated_always(),
        "cleared":            get_cleared_for_stage(stage),
        "caution":            get_caution_movements(stage),
    }
