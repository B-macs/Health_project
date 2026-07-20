"""
patient_profile.py — Clinical input file.

Single source of truth for MRI findings and biomechanical assessment.
Referenced by training_plan.py when designing sessions.
Update this file before generating each new training block.

Updated 2026-07-13 against docs/clinical_profile_weighting.md, incorporating
Input_files/injury_profile.md, Input_files/hypermobility-profile.md, and
Input_files/2025-training-year.md (all local-only, gitignored — read those
directly for full detail; only what's currently weight-relevant is
synthesized here). Recent Notion readiness/training-log data (last 14 days)
is NOT duplicated here — see Input_files/stage1_recent_data_summary.md.

Stage 1 history: Rehab extended by 7 days (Days 15-21, "Week 3: Flare
  Recovery & Reassessment Prep" in training_plan.py) — decided 2026-07-13.
  Day 14's exit criteria were not met on the original schedule
  (pain_free_streak=0, avg_tightness_14d=4.6 vs required <=3.0) because of an
  active mid-back/lower-back flare (see symptom_log below). By 2026-07-13 the
  flare was trending down (tightness 8->1 over the window) with that day's
  check-in showing pain=0, tightness=1. Decision made with the user: extend
  rehab one more week rather than jump to Stage 2, then reassess.
  Phase 1's length_days was extended from 14 to 21 in the Notion config to
  match (still phase_number=1 — a continuation, not a new phase).
  Agreed handling of pain_free_streak specifically: informative, not a hard
  blocker, if tightness (<=3.0) and pain (<=2/10) are met and physio signs
  off — a single reversed bad day within an otherwise-improving trend
  shouldn't be treated the same as a fresh injury restarting the clock.

Current block: Stage 2A — 28-Day Gym Strength Block (Phase 2, Days 1-28,
  training_plan.PLAN_STAGE2), started 2026-07-20. Day 21 reassessment
  (2026-07-19) passed and the physiotherapist signed off on external load —
  see stage_transitions below. Pure gym-strength content: goblet/DB squat,
  Romanian deadlift, hip thrust, incline DB press, lat pulldown/row,
  Bulgarian split squat, scapular + lumbar-endurance core work. No overhead
  pressing this block (Latarjet history + documented left-tilt instability
  under overhead load — see finding #6 below). Deliberately decoupled from
  the previously-discussed 10km race periodization (Oct 11 2026): running is
  NOT introduced in this block. That is an explicit deferred decision (the
  periodization had assumed a 2026-07-12 Stage 2A start; this is ~9 days
  behind that schedule), not an oversight — revisit at the Day 28
  reassessment alongside the Stage 2B decision.
Next block: reassess at Day 28 (2026-08-16) against stage_2_exit_criteria
  below — decide Stage 2B vs. extending Stage 2A, and the running-
  introduction question, with the physiotherapist before authoring either.
"""

PROFILE = {

    # ─────────────────────────────────────────────────────────────────────────
    #  Patient
    # ─────────────────────────────────────────────────────────────────────────

    "patient": "Patient",
    "current_stage": 2,
    "current_block": "Stage 2A — 28-Day Gym Strength Block (Days 1-28, started 2026-07-20). "
                      "Goblet/DB squat, RDL, hip thrust, incline DB press, lat pulldown/row, "
                      "Bulgarian split squat, scapular + lumbar-endurance core work. No overhead "
                      "pressing (finding #6) and no running this block — running is an explicit "
                      "deferred decision (see next_reassessment), not an oversight.",
    "next_reassessment": "Day 28 (2026-08-16) — reassess against stage_2_exit_criteria; decide "
                          "Stage 2B vs. extending Stage 2A, and the running-introduction question, "
                          "with the physiotherapist — see module docstring",

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
    #  Hypermobility — foundational, persistent (NOT time-decayed like the
    #  injury history below — see docs/clinical_profile_weighting.md #2).
    #  Full detail: Input_files/hypermobility-profile.md
    # ─────────────────────────────────────────────────────────────────────────

    "hypermobility": {
        "status": "Confirmed generalised joint hypermobility",
        "beighton_score": "6/9 (adult threshold >=5) — palms flat to floor, "
                           "thumb-to-forearm, 5th-finger and elbow hyperextension all positive",
        "joint_notes": [
            "Elbows hyperextend; knees do not",
            "Flat feet (pes planus)",
            "Possible HSD/hEDS-spectrum — not yet assessed against 2017 criteria",
        ],
        "training_implication": (
            "Stability-first, proprioception-focused programming throughout — this is a "
            "standing modifier on every block, not something that resolves or gets "
            "reassessed away like a healing injury. Favour controlled-range strength/"
            "stability work over passive end-range stretching or ballistic movement into "
            "end range. Applies broadly, not just to the joints already symptomatic."
        ),
        "autonomic_cluster_note": (
            "Suspected mild autonomic/low-blood-volume features (low HRV, orthostatic "
            "lightheadedness on standing transitions, fluid-handling irregularities) "
            "commonly associated with hypermobility — self-observed, not diagnosed. "
            "Relevant context for interpreting the readiness engine's HRV-weighted score: "
            "a personally low HRV baseline may reflect this rather than poor recovery. "
            "readiness.py's adaptive baseline already calibrates to the individual, so no "
            "code change implied — just don't over-interpret a low-vs-population-norm HRV "
            "reading in isolation."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    #  Biomechanical Profile — 6 assessed movement patterns
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
            "additional_evidence_2026_07_08": (
                "Same right-side click also observed during Dead Bug at ~45° knee flexion "
                "(supine, both legs raised, extending the right leg) — not just standing 90° "
                "external rotation. No click when the right leg extends alone from a "
                "bird-dog-style position with the left leg flat. Suggests the snap-triggering "
                "range may be broader than originally characterised — cue neutral/internal "
                "rotation on the right through supine leg-extension patterns too, not only "
                "standing hip flexion drills."
            ),
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
        {
            "id": 6,
            "title": "Right Shoulder Instability — Maintenance-Dependent, Full Weight",
            "location": "Right glenohumeral joint / scapula",
            "history": (
                "3x anterior dislocations (ages 17/18/21 — bike fall, rugby, surfing) with "
                "2 surgeries: a capsular stabilisation 'wrap' (shallow glenoid noted "
                "intra-operatively) which still permitted a 3rd dislocation, then a Latarjet "
                "coracoid transfer. No dislocations since. Full detail: Input_files/injury_profile.md."
            ),
            "structures": ["Right glenohumeral capsule/labrum (post-Latarjet)", "Scapular stabilisers"],
            "mechanism": (
                "Escalation to a bony (Latarjet) procedure after a soft-tissue repair failed is "
                "the standard pathway when connective-tissue laxity undermines capsular repair — "
                "consistent with the confirmed hypermobility above. Stability now comes from "
                "muscular control, not passive ligamentous restraint."
            ),
            "training_implication": (
                "NOT a resolved/historical finding despite no dislocations since Latarjet — "
                "residual shoulder sag, side pain, and right hip pain recur specifically 'if "
                "training lapses' per injury_profile.md, i.e. stability is maintenance-dependent, "
                "not permanent. Scapular control/stability work is therefore a STANDING "
                "requirement, not optional conditioning — especially relevant once Stage 2 "
                "introduces external load and pressing patterns. Cross-references the 2025 "
                "strength analysis (Input_files/2025-training-year.md): right scap eccentric "
                "control still weak, overhead pressing exposes instability with a left tilt, "
                "and a left rhomboid strain (Jul 2025) occurred under overhead load — same "
                "underlying issue, do not double-count as a separate caution. Overhead/pressing "
                "progression in Stage 2 should be conservative and scapular-control-first."
            ),
            "laterality": "RIGHT ONLY",
        },
    ],

    # ─────────────────────────────────────────────────────────────────────────
    #  Historical Injuries — low weight per docs/clinical_profile_weighting.md
    #  #1 (fully resolved, regardless of age). Context only; full detail in
    #  Input_files/injury_profile.md. Not itemised in biomechanical_findings
    #  above because none currently shape exercise selection, except the
    #  conditional note below.
    # ─────────────────────────────────────────────────────────────────────────

    "historical_injuries_low_weight": {
        "resolved_no_current_effect": [
            "Left clavicle dislocation (age 14) — residual mild elevation, asymptomatic",
            "Left wrist carpal fracture (age 15-16) — residual plane-to-plane click, asymptomatic",
            "Right thumb CMC joint surgery (age 25) — asymptomatic",
        ],
        "conditional_relevance": (
            "Left hip flexor (Sartorius) strain, twice (age 26, running/skiing overuse), "
            "currently resolved with no ongoing symptoms — low weight for THIS block. "
            "Becomes relevant again only if/when running-type conditioning is introduced "
            "(services.rules clears 'running' from Stage 2 onward): progress running "
            "volume conservatively given the prior recurrence, per "
            "docs/clinical_profile_weighting.md #1's re-stress carve-out."
        ),
    },

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
        {
            "date":   "2026-07-07",
            "status": "Active — monitoring, escalating as of 2026-07-10",
            "region": "Migrating between central lower back and mid-back (right side specifically noted)",
            "title":  "Mid-Back Re-Injury (Delayed Onset) — Active, Full Weight",

            "mechanism": (
                "Per Input_files/injury_profile.md #13: delayed-onset flare (~3 days after "
                "sprints, following a full day of sitting/working then sitting on a bar stool) — "
                "this is a re-injury of the same mid-back region first strained Oct 2025 "
                "(#12, MRI'd 10 Nov 2025, resolved ~March 2026 after serious rehab). "
                "Recent check-in/training-log evidence (full detail: "
                "Input_files/stage1_recent_data_summary.md): "
                "2026-07-07 readiness note 'sore but not bad, where I spoke about before'; "
                "2026-07-09 'same from the strain a few days ago'; "
                "2026-07-10 pain escalated to 3/10, explicitly migrating between lower back "
                "and mid-back, mid-back described as worse on the RIGHT side; skipped training "
                "2026-07-09 due to soreness; using heat pads/15min heat as self-management."
            ),

            "symptoms": {
                "location": "Central lower back and mid-back/thoracic, right-side mid-back flagged specifically",
                "painful_with":   ["Prolonged sitting", "Sprint-type effort (delayed 3 days)", "Day-long low activity/rest — got worse, not better, on 2026-07-10"],
                "pain_free_with": None,
                "neural":         "None reported — no leg symptoms, numbness, or tingling",
            },

            "assessment": {
                "likely_tissue": [
                    "Thoracic/lumbar paraspinals and facet structures already flagged in "
                    "biomechanical finding #3 (thoracic T6-T10 + L5/S1 horizontal facet base)",
                ],
                "mechanism": (
                    "Same overuse + sustained-sitting trigger pattern as the Oct 2025 index "
                    "episode and the resolved left-back strain above — recurring rather than "
                    "a one-off, and per docs/clinical_profile_weighting.md #1 this makes it "
                    "FULL WEIGHT, not context-only, unlike a truly resolved old injury."
                ),
                "underlying_pattern": (
                    "Hip-flexor/glute activation deficits from prolonged sitting (established "
                    "pattern, see imbalances above) combined with confirmed hypermobility's "
                    "stability-under-fatigue vulnerability — segmental control breaks down "
                    "under sustained low-load posture before it breaks down under acute load."
                ),
            },

            "plan": [
                "Do not assume Stage 1 exit criteria are met on Day-14 timing alone — "
                "pain_free_streak and avg_tightness_14d both currently fail the documented "
                "thresholds (see stage_1_exit_criteria) because of this flare.",
                "Continue heat/rest self-management; monitor for the migration pattern "
                "(lower back <-> mid-back) settling rather than continuing to move.",
                "Re-evaluate posture/sitting breaks given the identical trigger to the "
                "resolved Oct 2025 and 2026-06 left-back episodes — this is now a 3rd "
                "occurrence of the same mechanism.",
                "Do not author Stage 2 (external load) while this is actively escalating; "
                "reassess once pain returns to <=2/10 and tightness trend reverses.",
            ],

            "escalation_criteria": [
                "No improvement after another week → see physio (physio already involved "
                "per injury_profile.md #13, ongoing)",
                "Pain becomes sharp or radiates down a leg",
                "Any numbness or tingling",
            ],

            "notes": [
                "This is the 3rd distinct episode of the same mid-back/prolonged-sitting "
                "mechanism (Oct 2025 index event, a 2026-06 left-back variant above, now "
                "this one) — treat the pattern itself, not just each individual flare, as "
                "the thing to design around in Stage 2.",
            ],
        },
    ],

    # ─────────────────────────────────────────────────────────────────────────
    #  Stage Advancement Criteria
    #  stage_1_exit_criteria: evaluated at Day 21 (2026-07-19) — MET. Physio
    #  signed off on external load; see stage_transitions below for the record.
    #  stage_2_exit_criteria: to be evaluated at Day 28 (2026-08-16).
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

    # Draft — evaluated at the Day 28 reassessment (2026-08-16), mirroring
    # stage_1_exit_criteria's shape. Not yet evaluated.
    "stage_2_exit_criteria": {
        "pain": "≤ 2/10 across all working lifts, no worsening trend through the block",
        "hip_click": "No increase in Coxa Saltans frequency under loaded squat/split-squat work",
        "shoulder": "No instability sensation or left-tilt compensation under the incline-press loading introduced this block",
        "working_loads": "Final working loads logged on all six primary lifts (Goblet Squat, Incline DB Press, RDL, Hip Thrust, Lat Pulldown, Single-Arm DB Row) as the new baseline",
        "functional_screen": "McGill Big 3, Single-Leg Balance, Hip Hinge Full Range, Walk+Stair — matching or beating the Day 21 Stage 1 screen",
        "physio_sign_off": "Required before deciding Stage 2B vs. extending Stage 2A, and before introducing running",
    },

    # ─────────────────────────────────────────────────────────────────────────
    #  Stage Transitions — append-only record of actual advancement events
    #  (mirrors the symptom_log convention above: a running list, never
    #  overwritten). This is the record that a transition's *requirement*
    #  (stage_N_exit_criteria) was actually satisfied, not just stated.
    # ─────────────────────────────────────────────────────────────────────────

    "stage_transitions": [
        {
            "date": "2026-07-19",
            "event": "Day 21 reassessment passed; physiotherapist sign-off obtained "
                     "for Stage 1 -> Stage 2 advancement (external load cleared).",
            "signed_off_by": "physiotherapist (per user confirmation to this app; "
                              "not independently verified by the app itself)",
        },
    ],
}
