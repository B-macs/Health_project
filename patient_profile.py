"""
patient_profile.py — Clinical input file.

Single source of truth for MRI findings and biomechanical assessment.
Referenced by training_plan.py when designing sessions.
Update this file before generating each new training block.

Current block: 14-Day Stage 1 Rehab (bodyweight only)
Next block:    4-Week Stage 2 Transition (reassess after Day 14)
"""

PROFILE = {

    # ─────────────────────────────────────────────────────────────────────────
    #  Patient
    # ─────────────────────────────────────────────────────────────────────────

    "patient": "Patient",
    "current_stage": 1,
    "current_block": "14-Day Stage 1 Rehab",
    "next_reassessment": "After Day 14 — progress to 4-Week Stage 2 if criteria met",

    # ─────────────────────────────────────────────────────────────────────────
    #  MRI Findings
    # ─────────────────────────────────────────────────────────────────────────

    "mri": {
        "primary": {
            "level": "L5/S1",
            "pathology": "Activated osteochondrosis + retrolisthesis",
            "disc": "Right dorsolateral protrusion — moderate right foraminal stenosis",
            "downstream": "Psoas/hip flexor hypertonicity amplifying L5/S1 compression",
        },
        "secondary": [
            {
                "level": "L3/L4",
                "disc": "Flat protrusion left dorsolateral — covered annulus tear",
            },
            {
                "level": "L4/L5",
                "disc": "Flat protrusion left dorsolateral — covered annulus tear",
            },
        ],
        "constraints": [
            "No spinal loading in Stage 1",
            "No end-range lumbar extension",
            "No loaded rotation",
            "ACWR ceiling 1.2 — Stage 1",
            "Session RPE ceiling 7/10",
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    #  Biomechanical Profile — 5 assessed movement patterns
    # ─────────────────────────────────────────────────────────────────────────

    "biomechanical_findings": [
        {
            "id": 1,
            "title": "Upper Glute / Hip Crest Tightness",
            "location": "Top shelf of buttock, horizontal band just below posterior pelvic crest",
            "sensation": "Constant deep muscular tightness and gripping tension",
            "structures": ["Gluteus medius (upper fibres)", "Piriformis"],
            "mechanism": (
                "Chronic compensatory contraction — hip flexors tight from sitting, "
                "so upper glutes over-fire to hold the pelvis stable. "
                "This gripping is the primary anchor driving joint compression throughout the chain."
            ),
            "training_implication": (
                "Must INHIBIT these structures before activating them. "
                "Self-release and PNF stretching must precede any glute activation work."
            ),
            "laterality": "bilateral — RIGHT significantly tighter",
        },
        {
            "id": 2,
            "title": "Standing Leg Hinge Crack (Sit-Bone Area)",
            "location": "Deep at base of pelvis — ischial tuberosity / sit-bone area",
            "method": "Single-leg RDL / standing hinge with opposite leg extended behind",
            "timeline": "Only occurs every few days — requires accumulation of joint compression",
            "structures": [
                "Posterior hip capsule (right — beneath tight upper glute)",
                "Proximal hamstring tendon at ischial tuberosity",
            ],
            "mechanism": (
                "Under load-bearing rotational torque: femoral head glides backward against "
                "tight RIGHT posterior capsule, OR upper hamstring tendon shifts over ischial tuberosity."
            ),
            "training_implication": (
                "Right posterior hip capsule needs direct mobilisation. "
                "Ischial tuberosity hamstring attachment needs desensitisation via sustained pressure. "
                "Single-leg RDL on right will eventually trigger — this is a healthy structural release."
            ),
            "laterality": "RIGHT — primary finding",
        },
        {
            "id": 3,
            "title": "Sitting Forward-Bend Releases",
            "location": "Two distinct sites: mid-thoracic spine + horizontal lumbar base",
            "structures": [
                "Thoracic facet joints (T6-T10 range)",
                "Lumbar facet joints at L5/S1 horizontal plane",
            ],
            "mechanism": (
                "Thoracic: seated compression forces vertebrae into extension during forward bend — "
                "satisfying facet release. "
                "Lumbar base: horizontal facet joint sliding under chronic compressive load from sitting."
            ),
            "training_implication": (
                "Thoracic extension mobility (rolled towel) directly addresses thoracic facets. "
                "Thread-the-needle addresses rotational facet loading. "
                "Lumbar base requires deliberate posterior pelvic tilt to decompress horizontal facet slides."
            ),
            "laterality": "bilateral",
        },
        {
            "id": 4,
            "title": "90-Degree Active Hip Click — Right Side Only",
            "location": "Deep in right groin crease",
            "method": "Standing, lift right knee to 90°, add external rotation",
            "timeline": "Repeatable on every attempt — completely painless",
            "structures": ["Iliopsoas tendon over iliopectineal eminence / femoral head"],
            "mechanism": (
                "Classic Coxa Saltans (Snapping Hip Syndrome). "
                "Tendon snapping over bony ridge — NOT a gas release. "
                "Triggered by combined hip flexion + external rotation."
            ),
            "training_implication": (
                "All exercises involving right hip flexion >60° must cue NEUTRAL or slight INTERNAL rotation. "
                "External rotation triggers the snap. "
                "Retraining the motor path gradually reduces tendon tension and snap frequency."
            ),
            "laterality": "RIGHT ONLY",
        },
        {
            "id": 5,
            "title": "Wide-Stance Windmill Torso Twist Cracks",
            "location": "Deep groin / inner thigh + smaller pops along lumbar spine",
            "method": "Wide stance, slight forward lean, dynamic torso rotation (windmill arms)",
            "structures": [
                "Hip joint capsule (anterior) — cavitation",
                "Pubic symphysis — cavitation",
                "Lumbar facet joints — rotational end-range",
            ],
            "mechanism": (
                "Wide stance locks adductors and anchors lower pelvis. "
                "Dynamic torso swing creates massive rotational torque. "
                "Forces pressure release in anterior hip capsule or pubic symphysis. "
                "Spine cracks because wide stance prevents hips sharing the rotation."
            ),
            "training_implication": (
                "Lateral lunge and hip 90/90 flow directly address this. "
                "Pallof press anti-rotation targets the lumbar facet component. "
                "Wide stance positions should be introduced slowly."
            ),
            "laterality": "bilateral",
        },
    ],

    # ─────────────────────────────────────────────────────────────────────────
    #  Muscle Imbalance Summary
    # ─────────────────────────────────────────────────────────────────────────

    "imbalances": {
        "overactive_tight": [
            "Gluteus medius — upper fibres (bilateral, right > left)",
            "Piriformis (bilateral)",
            "Deep right hip flexors / TFL",
            "Right posterior hip capsule",
            "Proximal hamstrings at ischial tuberosity",
            "Lumbar facet joint capsules — horizontal L5/S1 base",
        ],
        "underactive_weak": [
            "Gluteus maximus — primary hip extensor",
            "Deep core stabilisers (transversus abdominis, multifidus)",
        ],
        "compensation_pattern": (
            "Under-firing glute max + deep core → upper glutes and hip flexors over-grip "
            "to create artificial stability → compressed joints and snapping tendons. "
            "The rehab sequence must FIRST inhibit/release the overactive structures, "
            "THEN activate the underactive ones."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    #  Pre-Session Release Protocol (runs at the START of every session)
    # ─────────────────────────────────────────────────────────────────────────

    "pre_session_release": {
        "rationale": (
            "Overactive glute medius/piriformis will compete with and inhibit "
            "glute max during activation work unless released first. "
            "5-minute release block before every session."
        ),
        "always_include": [
            "Upper Glute / TFL Self-Release (wall or fist) — 2 × 90s each side",
            "Piriformis Contract-Relax PNF — 3 × 5 cycles each side",
        ],
        "add_when_hip_focused": [
            "Right Posterior Hip Capsule Cross-Body Stretch — 3 × 60s right only",
            "Ischial Tuberosity Hamstring Release — 2 × 90s each side",
        ],
        "add_when_right_hip_loaded": [
            "Right Hip Tendon Path Drill (Coxa Saltans) — 2 × 10 reps right only",
        ],
    },

    # ─────────────────────────────────────────────────────────────────────────
    #  Symptom Log
    # ─────────────────────────────────────────────────────────────────────────

    "symptom_log": [
        {
            "date":   "2026-07-06",
            "status": "Active — monitoring",
            "region": "Left lower/mid back — from under left glute up the left side of the spine",
            "title":  "Left Back Strain (Walking Posture Change)",

            "mechanism": (
                "Went for a walk with habitual anterior pelvic tilt. "
                "Attempted posture correction: shifted trunk/ribcage back over the hips "
                "(swayback-type correction) — no deliberate pelvic tuck; felt unrestricted at the time. "
                "First 10–15 min: hip flexor stretch sensation bilaterally (expected — relative hip extension). "
                "Progressive onset thereafter: sensation migrated under left glute → low back → "
                "up left side of back. No pop, no sharp event. "
                "Reverted to habitual pattern mid-walk once discomfort built."
            ),

            "symptoms": {
                "location": (
                    "Soreness along a line running up the centre-left of the back, "
                    "angling laterally (away from spine toward side of body), ending below mid-back. "
                    "Consistent with iliocostalis fibre direction."
                ),
                "painful_with":   ["Walking", "Side-bending RIGHT (stretching left side)"],
                "pain_free_with": ["Side-bending LEFT (stretching right side)"],
                "neural":         "None — no leg symptoms, no numbness, no tingling",
            },

            "assessment": {
                "likely_tissue": [
                    "Left erector spinae — iliocostalis (lateral column; matches line angling away from spine)",
                    "Left quadratus lumborum (QL) — possible co-involvement",
                ],
                "mechanism": (
                    "Trunk held behind base of support forced spinal erectors/QL to contract "
                    "isometrically in a shortened position for the duration of the walk → "
                    "fatigue overload strain. Not a stretch injury."
                ),
                "why_left": (
                    "Pre-existing left-side asymmetry; left QL likely already working harder at baseline."
                ),
                "underlying_pattern": (
                    "Anterior pelvic tilt with tight/short psoas, iliacus, rectus femoris; "
                    "relatively underactive glutes and anterior core."
                ),
            },

            "plan": [
                "Let area settle 3–5 days; keep walking in normal pattern, gentle movement only.",
                "No forced posture corrections on walks until strength work is established.",
                "Hip flexor lengthening separately: couch stretch, half-kneeling hip flexor stretch.",
                "Glute + anterior core strengthening: glute bridges, dead bugs.",
                "When reintroducing posture changes: 2–3 min doses maximum, not full walks.",
            ],

            "escalation_criteria": [
                "Still sore after ~1 week with no improvement → see physio",
                "Pain becomes sharp or radiates down a leg",
                "Any numbness or tingling",
            ],

            "notes": [
                (
                    "Baseline activity is high (~16k steps/day, single-leg glute bridges in current "
                    "physio work, extended dancing 2 days prior without issue) — this is a task-specific "
                    "overload of sustained isometric postural holding, not a general capacity problem."
                ),
                (
                    "Proprioception note: position felt like hips stacked under shoulders but was "
                    "actually a slight trunk lean back. Internal sense of 'neutral' is calibrated to "
                    "habitual anterior tilt — genuinely neutral/corrected positions feel further back "
                    "than they are. Expect this miscalibration when reintroducing posture drills."
                ),
                (
                    "Lesson: a comfortable posture change is not a conditioned one. "
                    "Tissues need weeks of graded exposure to adapt — exposure dose matters."
                ),
            ],
        },
    ],

    # ─────────────────────────────────────────────────────────────────────────
    #  Stage Advancement Criteria (to be evaluated at Day 14)
    # ─────────────────────────────────────────────────────────────────────────

    "stage_1_exit_criteria": {
        "pain": "All 5 functional positions ≤ 2/10 consistently",
        "tightness": "Average tightness score ≤ 3/10 over last 7 days",
        "pain_free_days": "≥ 14 consecutive pain-free training days",
        "hip_click": "Coxa Saltans snap controllable with neutral rotation cue",
        "upper_glute": "Measurable reduction in resting grip/tightness of upper glute",
        "hinge": "Pain-free hip hinge to full range (arms past knees)",
        "physio_sign_off": "Required before advancing to Stage 2",
    },
}
