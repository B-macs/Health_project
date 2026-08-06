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

import re
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
#  Name normalisation
# ─────────────────────────────────────────────────────────────────────────────

def normalise_movement(name: str) -> str:
    """Lowercase, punctuation and hyphens to spaces, whitespace collapsed.

    WHY THIS EXISTS. `check_movement` matches by substring, and a raw substring
    test is defeated by a single punctuation mark. Measured 2026-08-06 against
    the Cluster A source documents:

        check_movement("good morning", 2)   -> contraindicated (cap 3 vs stage 2)
        check_movement("good-mornings", 2)  -> unknown

    "Seated straddle good-mornings holding a plate" is a loaded lumbar-flexion
    movement over two covered annulus tears, and one hyphen was the difference
    between a hard block and silence. `unknown` is not a block — services/yoga.py
    discards it entirely — so a false negative here is indistinguishable from
    "no rule applies".

    Possessives are also stripped ("tailor's pose" -> "tailors pose") so a rule
    can be authored either way round without a second entry.
    """
    lowered = name.lower().replace("'", "").replace("’", "")
    spaced = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", spaced).strip()


def _heads_the_name(name: str, keyword: str) -> bool:
    """True when `keyword` is the head of `name`, tolerating a plural 's'.

    Used only for CLEARED rules, where a fragment match is dangerous. Token-wise
    rather than by string prefix, because a string prefix is defeated by exactly
    the plural these names carry: "adductor squeezes at width" does not start
    with "adductor squeeze " (the 's' lands where the space should be).
    """
    name_tokens, kw_tokens = name.split(), keyword.split()
    if len(name_tokens) < len(kw_tokens):
        return False
    for got, want in zip(name_tokens, kw_tokens):
        if got != want and got != want + "s" and want != got + "s":
            return False
    return True


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
        movement="side bend",
        reason="Lateral flexion in either direction has a mechanism here — right narrows the "
               "stenotic L5/S1 foramen, left loads the dorsolateral protrusions at L3/4 and L4/5. "
               "Generalises 'right lateral'/'left lateral' to catch named variants that don't "
               "spell out the word (e.g. yoga poses), the same way 'forward fold' generalises "
               "'seated forward fold'.",
        stage_cap=1, severity="caution", laterality="bilateral",
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

    # ── Flexibility-skill vocabulary (added 2026-08-06) ──────────────────────
    #
    # WHY THESE EXIST. The rules above speak MOVEMENT DESCRIPTIONS; flexibility
    # source material speaks SKILL NAMES, and nothing bridged the two. Measured
    # across the Cluster A documents on 2026-08-06:
    #
    #     check_movement("Straddle Forward Fold", 2) -> contraindicated
    #     check_movement("Pancake", 2)               -> unknown
    #
    # The same movement, under two names, with opposite verdicts. 70 of 78
    # names in those documents returned `unknown`, and `unknown` is not a block
    # — services/yoga.py discards it. Every entry below is a bridge from a
    # skill name to a mechanism already ruled on above.
    #
    # SEVERITY IS CHOSEN FOR THE MOVEMENT AS NAMED, and most of these are
    # `caution` rather than contraindicated on purpose: the skill is trainable,
    # the DEFAULT EXECUTION is not, and the reason string carries the cue that
    # makes the difference. A blanket contraindication on "pancake" would block
    # the flat-back version this athlete is specifically training toward, which
    # is the wrong answer to the right worry.
    MovementRule(
        movement="weight behind",
        reason="Axial load carried behind the neck or across the shoulders while seated "
               "and folding. The load, not the athlete's own tilt, produces the depth — "
               "over covered annulus tears at L3/4 and L4/5, and with a placement the "
               "post-Latarjet right shoulder should not be holding either.",
        stage_cap=1, severity="contraindicated", laterality="bilateral",
    ),
    MovementRule(
        movement="pancake",
        reason="Seated wide-leg fold. Trainable ONLY as a flat-back hinge from an "
               "elevated seat — the rounded-spine version is a seated forward fold and "
               "loads the covered annulus tears at L3/4 and L4/5. The elevation supplies "
               "the pelvic tilt; the spine must not. Never loaded, never strap-assisted.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="straddle",
        reason="Wide-leg seated position. Safe sitting tall or hinging with a flat back; "
               "the folded version is a seated forward fold. Also a wide-stance position "
               "— introduce slowly per the anterior hip capsule / pubic symphysis finding.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="pike",
        reason="Named in the source material as 'touching your toes; forward fold'. That "
               "execution is contraindicated end-range lumbar flexion. Trainable only as a "
               "flat-back hip hinge.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="lift off",
        reason="Repeated concentric lift out of a deep seated fold. From a rounded spine "
               "this is a bodyweight seated good-morning over two annulus tears. Only "
               "permissible from a flat back, and it is active hip flexion under iliopsoas "
               "load — cue neutral or slight internal rotation on the right.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="side split",
        reason="Wide-stance hip abduction under full bodyweight. Align the joint by "
               "EXTERNAL ROTATION, never by arching the lumbar spine — both routes reach "
               "the same joint position and only one collides with the L5/S1 "
               "retrolisthesis and narrowed right foramen.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="anterior tilt",
        reason="Forward pelvic tilt drives lumbar extension, which compresses the already "
               "narrowed right L5/S1 foramen. Already this athlete's habitual standing "
               "posture. Train the movement, never the end range, and never held under "
               "bodyweight at depth.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="pelvic rock",
        reason="Mid-range pelvic tilt drill. Safe as a movement rehearsal; the arched end "
               "of it is lumbar extension against the L5/S1 retrolisthesis. Train the "
               "movement, not the depth.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="horse stance",
        reason="Wide stance with the feet turned out, loaded, at depth. Active hip flexion "
               "in external rotation is the contractile trigger for the right snapping hip "
               "— cue neutral or slight internal rotation. Also a squat pattern under the "
               "wide-stance caution.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="cossack",
        reason="Deep unilateral squat in abduction and external rotation. Active, loaded "
               "right hip flexion past 60° — the snapping-hip trigger. Trailing leg "
               "straight also loads the proximal hamstring at the ischial tuberosity.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="tailors pose",
        reason="Seated butterfly against a wall. Passive floor-supported external rotation "
               "is NOT a snapping-hip risk position. Unloaded only: external load onto a "
               "passively held end-range hip is the practice the hypermobility profile "
               "specifically rules out, and the anterior-hip sensation reported here on "
               "2026-08-05 is an open question.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="butterfly",
        reason="Supine or seated soles-together hip abduction. Floor-supported and "
               "unloaded it is safe. The 2026-08-05 report of anterior HIP FLEXOR "
               "sensation rather than adductor stretch is unresolved — do not add load "
               "until that is answered.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="frog",
        reason="Deep hip flexion with abduction. Floor-supported and self-limited, but it "
               "is the same anterior-hip compression question as the butterfly position.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="nerve glide",
        reason="Neurodynamic technique. Legitimate, but this athlete has moderate right "
               "L5/S1 foraminal stenosis and every symptom log to date records no neural "
               "signs — electric or burning sensations are an escalation to the "
               "physiotherapist, never a training variable. Physio-directed only.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="copenhagen",
        reason="Side-lying adductor plank. Clean mechanically — spine neutral, no lumbar "
               "flexion or extension, no axial load. The caution is dose: last performed "
               "May/June 2025 at 30 s × 3, and a back injury plus a full rehab block sit "
               "between then and now.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="adductor squeeze",
        reason="Isometric adduction at a controlled width. No spinal load, no end-range "
               "passive hold — the controlled-range strength work the hypermobility "
               "profile asks for in place of passive stretching.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="side leg raise",
        reason="Active hip abduction, spine neutral. Loads glute medius, which the "
               "biomechanical assessment lists as overactive and right-dominant — release "
               "before activating, per the pre-session protocol.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="banded abduction",
        reason="Resisted hip abduction. Same glute medius sequencing note as the side leg "
               "raise: inhibit before you activate.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="terminal knee extension",
        reason="Banded knee extension for VMO. Knee-local, no spinal or hip load. Named "
               "here so it is not caught by the lumbar 'back extension' rule.",
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
    name_lower = normalise_movement(movement_name)

    # Find the strictest matching rule.
    #
    # A CLEARED rule must NAME the movement — it may match the whole name or
    # head it, never appear as a fragment buried inside a description.
    # Measured 2026-08-06: the assessment battery's most flexion-loaded item
    # reads "hands walking forward on the floor", which contains the substring
    # "walking" and therefore matched the `walking` CLEARED rule — returning an
    # affirmative "Low-impact movement — maintains tissue health" on a movement
    # that loads two covered annulus tears. A wrong green light is worse than
    # silence, because silence at least reads as "apply clinical judgment".
    #
    # Head-matching, not exact, so ordinary variants keep their clearance:
    # "Glute Bridge (Single Leg)" and "Pallof Press Hold (Doorframe)" still
    # clear. A cleared rule that fails to fire degrades to `unknown`, which is
    # the safe direction; a cleared rule that fires wrongly is not.
    #
    # Contraindicated and caution rules keep the permissive substring match:
    # over-catching there fails safe, and the generalising keywords
    # ("forward fold" catching named variants) depend on it.
    matched: list[MovementRule] = []
    for rule in MOVEMENT_RULES:
        keyword = normalise_movement(rule.movement)
        if rule.severity == "cleared":
            hit = _heads_the_name(name_lower, keyword)
        else:
            hit = keyword in name_lower or name_lower in keyword
        if hit:
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
