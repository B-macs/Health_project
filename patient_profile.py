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

2026-08-05: first structured FLEXIBILITY baseline added (symptom_log, 22-pose
  self-rated ROM assessment). Two things in this file were being read wrongly
  and the entry's `notes` say so explicitly: the Beighton score is a laxity
  screen, not a hamstring-length measurement, and `imbalances.overactive_tight`
  is resting TONE, not shortness. Net new clinical content: seated anterior
  pelvic tilt is the dominant restriction (proximal hamstrings), the documented
  right>left asymmetry does not appear in passive stretch, finding #4's Coxa
  Saltans trigger is contractile rather than positional, and interscapular
  fatigue onset under bodyweight is measured at 50-60s.

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
  below — decide Stage 2B vs. extending Stage 2A, the running-introduction
  question, AND endurance-biased scapular programming (see the 2026-08-03
  symptom_log entry: five days a week of scapular work already runs and the
  interscapular symptom persists through it, so the gap is endurance under
  sustained low-load holding, not volume — this needs long isometric holds,
  which is a prescription change and therefore a physio decision, not a
  self-directed one). All three are explicit deferred decisions, not
  oversights; settle them with the physiotherapist before authoring the block.
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
                          "Stage 2B vs. extending Stage 2A, the running-introduction question, and "
                          "endurance-biased scapular programming (2026-08-03 symptom_log entry — an "
                          "endurance gap, not a volume gap), with the physiotherapist — see module "
                          "docstring and docs/training/physio_brief_2026-08-16.md",

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
            "additional_evidence_2026_08_05": (
                "NEGATIVE finding, and it sharpens the trigger definition: across a 22-pose "
                "yoga flow the athlete reported NO snap and NO anterior-hip pinch in 90/90 "
                "hip rotation ('able to bring both knees to the ground with ease') or in "
                "Half Pigeon right ('no pinch or click at the front of the right hip'), and "
                "scored both sides identically. Both positions place the right hip in "
                "flexion + external rotation, so POSITION ALONE DOES NOT TRIGGER IT. Every "
                "positive observation on record — standing 90° knee lift, Dead Bug leg "
                "extension — involves ACTIVE hip flexion under iliopsoas contraction. "
                "Read the trigger as CONTRACTILE, not positional: cue neutral/internal "
                "rotation wherever the right hip flexes under its own muscular effort, and "
                "do not treat passive, floor-supported external rotation as a risk position. "
                "Does not downgrade the finding — it narrows where it applies."
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
        {
            "date":   "2026-07-21",
            "status": "New — monitoring",
            "region": "Left interscapular region and base of the neck (posterior, left side)",
            "title":  "Left Interscapular Tightness / Dull Ache (Desk-Posture Triggered)",

            "mechanism": (
                "Onset after desk work — consistent across sitting, standing, and treadmill "
                "use (not tied to one specific posture or piece of furniture). No loading "
                "event, no acute onset — a static ache that builds during prolonged desk time "
                "rather than a movement-triggered strain. A ~20-minute natural-pace walk "
                "provided relief to the interscapular tightness — but a new tightness then "
                "appeared at the base of the neck, posterior, left side, along the same "
                "left-sided corridor. Notably, lower back and hip symptoms have improved "
                "markedly since Stage 2A began; this upper-back/neck pattern persists "
                "independent of that improvement, suggesting a separate driver."
            ),

            "symptoms": {
                "location": (
                    "Left interscapular region (between the shoulder blades, left worse than "
                    "right) extending to the base of the neck, posterior, left side"
                ),
                "painful_with":   ["Prolonged desk work generally — sitting, standing, and treadmill walking alike"],
                "pain_free_with": ["Natural-pace walking (~20 min) — relieved the interscapular component"],
                "neural":         "None reported — no arm symptoms, numbness, or tingling",
            },

            "assessment": {
                "likely_tissue": [
                    "Left rhomboid / mid-trapezius — same region flagged in finding #6's Jul 2025 "
                    "left rhomboid strain, now presenting as a static ache rather than a loading injury",
                    "Left levator scapulae — anatomically bridges the cervical spine (base of neck) "
                    "and the medial scapular border, a plausible link between the two symptom sites "
                    "given they sit along the same left-sided line",
                ],
                "mechanism": (
                    "Occurring across sitting, standing, AND treadmill use (not posture-specific) "
                    "points toward under-recruitment of the left scapular stabilizers during "
                    "prolonged low-load positions, rather than a fresh acute strain — consistent "
                    "with finding #6's documented weak scapular control (right eccentric control "
                    "flagged there; this is the left side, same underlying stability deficit). "
                    "That walking relieved the interscapular tightness (dynamic movement rhythmically "
                    "engaging the same stabilizers that seize up under static holding) supports a "
                    "stiffness-from-stillness pattern over a structural issue — the neck-base tightness "
                    "appearing afterward, along the same corridor, reads as the same underlying pattern "
                    "shifting location rather than a second, unrelated finding."
                ),
                "underlying_pattern": (
                    "Finding #6 explicitly frames scapular control work as 'a STANDING requirement, "
                    "not optional conditioning.' Current Stage 2A active-recovery day rotation only "
                    "includes scapular-specific work (Scapular Wall Slide) within Session C (Friday), "
                    "not in the daily active-recovery templates — a gap worth raising with physio "
                    "given this symptom's timing."
                ),
            },

            "plan": [
                "No self-directed exercise changes — raise with physiotherapist at next check-in, "
                "referencing finding #6's existing scapular-control note.",
                "Track whether frequency/duration of desk work correlates with symptom severity "
                "day-to-day via Morning Check-in (Body Areas / Sensations tags).",
                "Note whether short walking breaks during desk work reduce onset/severity — "
                "observation only, not a prescribed intervention.",
                "Do not conflate with finding #3 (thoracic facet/sitting) — that finding is "
                "bilateral/midline; this is left-lateralised and not sitting-specific.",
            ],

            "escalation_criteria": [
                "No improvement after continued monitoring → raise explicitly with physio",
                "Any radiating pain into the arm, numbness, or tingling",
                "Sharp pain or any acute onset (as opposed to the current dull, gradual ache)",
                "Headache, dizziness, or any symptom suggesting cervical (not just muscular) involvement",
            ],

            "notes": [
                "Positive signal: lower back and hip symptoms have improved noticeably since "
                "Stage 2A began — this upper-back/neck symptom is independent of that, not a "
                "sign the current training block is causing harm.",
                "Symptom migrated from interscapular to neck-base after a relieving walk, both "
                "on the left side — tracking this as one evolving pattern, not two separate entries.",
            ],
        },
        {
            "date":   "2026-07-31",
            "status": "New — monitoring",
            "region": "Cervical spine — left mid-to-lower cervical (flexion)",
            "title":  "Cervical Spine Assessment — Asymmetric Flexion Tightness (Left) + Mechanical Crepitus",

            "mechanism": (
                "Formal range-of-motion self-assessment across cervical movements. "
                "Lateral rotation (right-to-left): 4-5/10 moderate tightness, centralized at "
                "mid-cervical spine. Flexion (chin to chest): strongest tightness/soreness, "
                "markedly asymmetric — significantly stronger on the LEFT, localized "
                "immediately lateral to the spine. Circumduction: variable, with frequent "
                "audible crepitus (crackling/popping) throughout."
            ),

            "symptoms": {
                "location": (
                    "Left mid-to-lower cervical spine (flexion, dominant finding); "
                    "mid-cervical spine centrally (lateral rotation)"
                ),
                "painful_with": [
                    "Cervical flexion (chin to chest) — left side, high intensity, immediately lateral to spine",
                    "Lateral rotation (right-to-left) — centralized mid-cervical, moderate (4-5/10)",
                    "Circumduction — frequent mechanical crepitus, intensity variable",
                ],
                "pain_free_with": None,
                "neural": (
                    "None reported — no radiating pain, numbness, or tingling. Crepitus is "
                    "painless/mechanical (gas cavitation in facet-joint synovial fluid, or "
                    "tendon/ligament gliding over bony prominences) and, absent sharp or "
                    "radiating pain, is treated as benign per standard interpretation."
                ),
            },

            "assessment": {
                "likely_tissue": [
                    "Left posterior cervical extensors/paraspinals, or left levator scapulae — "
                    "flexion tightness lateral to the spine on the left matches the same "
                    "left-sided corridor already flagged in the 2026-07-21 entry above "
                    "(levator scapulae bridges the cervical spine base and the medial "
                    "scapular border)",
                ],
                "mechanism": (
                    "The left-sided flexion pull points to tightness/strain in the posterior "
                    "cervical extensors/paraspinals or levator scapulae on the left."
                ),
                "underlying_pattern": (
                    "Extends the 2026-07-21 entry (left interscapular region and base of neck, "
                    "desk-posture triggered) with a formal ROM breakdown — this confirms that "
                    "entry's left-sided flexion/tightness component in more detail, consistent "
                    "with finding #6's documented left scapular-stabilizer under-recruitment "
                    "(levator scapulae link)."
                ),
            },

            "plan": [
                "No self-directed exercise changes — raise with physiotherapist at next check-in, "
                "presenting this ROM breakdown together with the 2026-07-21 entry as one "
                "evolving cervical/upper-back pattern, not two unrelated findings.",
                "Continue monitoring whether desk-work load correlates with the left flexion "
                "tightness specifically, as already being tracked for the interscapular/neck-base "
                "pattern.",
                "Track crepitus frequency/location day-to-day if useful, alongside the existing "
                "left-side tracking.",
            ],

            "escalation_criteria": [
                "Crepitus accompanied by sharp or radiating pain (as opposed to the current "
                "painless mechanical crackling)",
                "Any numbness, tingling, or radiating pain into the arm",
                "Headache, dizziness, or vertigo associated with neck movement",
                "No improvement after continued monitoring → raise explicitly with physio",
            ],

            "notes": [
                "Same left-sided corridor as the 2026-07-21 entry (interscapular -> neck base), "
                "now documented with a formal flexion/rotation/circumduction breakdown.",
                "Crepitus during circumduction is common and, in the absence of sharp or "
                "radiating pain, is not itself a red flag.",
                "Right-sided extension discomfort at the base of the neck was initially noted "
                "on 2026-07-31 but had resolved by the time this entry was finalized — not "
                "included above as an active finding.",
            ],
        },
        {
            "date":   "2026-08-03",
            "status": "Active — monitoring; carried forward to the post-Stage-2A block",
            "region": "Interscapular, bilateral (left dominant) + left cervical base",
            "title":  "Interscapular Endurance Gap — Consolidated Pattern (Desk-Exposure Driven)",

            "mechanism": (
                "Consolidation of the 2026-07-21 and 2026-07-31 entries above against the "
                "actual check-in record, which changes three things those entries got wrong "
                "(see notes). No loading event and no acute onset at any point — a static "
                "ache that accumulates across the working day and is provoked by cervical "
                "flexion. 2026-07-16: 'tightness that has lasted a few days now right between "
                "my shoulder blades, worse towards the end of the day'. 2026-07-31: 'still "
                "tight in traps left side down my spine when I put my head foreward'. "
                "Desk exposure is the constant: symptomatic across sitting, standing AND "
                "treadmill use, which rules out the chair and rules in duration. Forearms "
                "confirmed UNSUPPORTED at the desk (user, 2026-08-03) — elbows floating while "
                "typing, so the scapular retractors hold roughly 4kg of arm weight per side "
                "for the length of the working day."
            ),

            "symptoms": {
                "location": (
                    "Medial scapular border, both sides — RIGHT on 2026-07-16 and 2026-07-23 "
                    "('a little towards the bottom'), LEFT from 2026-07-21 onward — extending "
                    "to the base of the neck, posterior, left side"
                ),
                "painful_with": [
                    "Prolonged desk work — sitting, standing and treadmill walking alike",
                    "Cumulative through the day ('worse towards the end of the day')",
                    "Cervical flexion / head-forward position",
                ],
                "pain_free_with": ["Natural-pace walking (~20 min)"],
                "neural":         "None — no arm symptoms, numbness, or tingling",
                "severity":       "Flat and low throughout: tightness 1-3/10, pain 0/10 on every check-in 2026-07-16 → 2026-07-31",
            },

            "assessment": {
                "likely_tissue": [
                    "Left rhomboid major/minor and mid-trapezius at the medial scapular border "
                    "— same tissue reasoned in the 2026-07-21 entry, not re-derived here",
                    "Levator scapulae — the anatomical bridge between the cervical spine and the "
                    "superior medial scapular angle, and why the ache migrates between the two "
                    "sites along one corridor (established in the 2026-07-21 and 2026-07-31 entries)",
                ],
                "mechanism": (
                    "FOUR CONVERGING DRIVERS, all already documented elsewhere in this profile:\n"
                    "(1) The right post-Latarjet shoulder sag shifts postural work onto the LEFT. "
                    "The tell is injury_profile.md #11 — the July 2025 rhomboid strain was on the "
                    "LEFT despite the damaged shoulder being the RIGHT — together with the 2025 "
                    "log's documented left TILT under overhead load. Cross-references finding #6; "
                    "do not double-count as a separate caution.\n"
                    "(2) Confirmed hypermobility (Beighton 6/9) means stability is muscular rather "
                    "than ligamentous, so sustained low-load holding is the worst load case — "
                    "muscle fatigues, ligament does not. Identical mechanism to the mid-back "
                    "episodes (which flare after a day of sitting, not after the sprints) and to "
                    "the 2026-07-06 left QL strain (isometric holding for the length of a walk).\n"
                    "(3) Finding #3's sitting-driven T6-T10 thoracic stiffness tilts the scapula "
                    "forward off the ribcage, leaving the retractors holding LENGTHENED all day — "
                    "a mechanically losing position.\n"
                    "(4) Desk exposure with unsupported forearms (above) is the unchanged variable."
                ),
                "underlying_pattern": (
                    "NOT a volume gap — an ENDURANCE gap. Scapular work already runs five days a "
                    "week (see notes), and the symptom persists through all of it, because every "
                    "one of those is a short high-quality set while the provocation is ~8 hours of "
                    "continuous low-load holding. Nothing in the block trains that capacity. This "
                    "is the 2025 movement-pattern analysis's documented 'lumbar endurance low / "
                    "deep core turns off under fatigue' finding appearing in a new region."
                ),
            },

            "plan": [
                "Forearm support at the desk — both forearms resting on desk or armrests, elbows "
                "under the shoulders, monitor top at eye level. Highest-leverage intervention and "
                "needs no sign-off: it removes the arm-weight load the retractors are holding.",
                "Movement break every 30-45 minutes, taken BEFORE onset rather than after. The "
                "~20-minute walk that relieved the interscapular component on 2026-07-21 is the "
                "proven dose — it was simply mistimed, taken once the ache had already built.",
                "Do NOT chase posture correction. The 2026-07-06 entry records this exact route "
                "producing a genuine strain in a different region, and its own lesson — 'a "
                "comfortable posture change is not a conditioned one' — applies unchanged here. "
                "Vary position frequently; do not hold a corrected one.",
                "Release the overactive upper trapezius / levator scapulae BEFORE scapular "
                "activation work, not instead of it — the same inhibit-then-activate sequencing "
                "the pre-session release protocol already uses for glute medius/piriformis, "
                "applied upstream.",
                "No self-directed exercise changes — endurance-biased scapular loading (long "
                "isometric holds rather than more reps) is an exercise-prescription change and "
                "goes to the physiotherapist at the Day 28 reassessment (2026-08-16). See "
                "docs/training/physio_brief_2026-08-16.md.",
                "Recheck ferritin — 29 ng/mL (Aug 2023) with CRP 0.9, i.e. a true low-normal "
                "reading rather than an inflammation-masked one, and now three years stale. "
                "Low-optimal iron worsens exactly this kind of muscular fatigue-tightness. "
                "Already an open action in Input_files/hypermobility-profile.md section 6.",
            ],

            "escalation_criteria": [
                "Any radiating pain into the arm, numbness, or tingling",
                "Sharp pain or any acute onset (as opposed to the current dull, gradual ache)",
                "Headache, dizziness, or any symptom suggesting cervical (not just muscular) involvement",
                "Severity trending up from the current flat 1-3/10 tightness, or no improvement "
                "after the desk/movement changes above → raise explicitly with physio",
            ],

            "notes": [
                "CORRECTION 1 — onset was 2026-07-16, four days BEFORE Stage 2A began on "
                "2026-07-20. The first symptom_log entry above is dated 2026-07-21, which implies "
                "the loaded block caused this. It did not.",
                "CORRECTION 2 — this is BILATERAL with left dominance, not left-lateralised as the "
                "2026-07-21 entry states. Right side on 2026-07-16 and 2026-07-23, left from "
                "2026-07-21 on. A bilateral migrating presentation favours a postural-endurance "
                "driver over a discrete left-sided strain, and the left-lateralised framing is "
                "what obscured that.",
                "CORRECTION 3 — the 2026-07-21 entry's claim that scapular-specific work appears "
                "only in Session C is wrong. training_plan.PLAN_STAGE2 runs Face Pull (Day 1), "
                "Lat Pulldown + Single-Arm DB Row (Day 3), Scapular Wall Slide (Days 4, 5 and 7) "
                "and Prone Y-Raise (Day 5) — five days a week. That the symptom persists THROUGH "
                "that dose is the finding, and is what reframes it as endurance rather than volume.",
                "Entries above are left as written per the append-only convention — these "
                "corrections live here, not in the original entries.",
                "Positive signal, unchanged from 2026-07-21: lower back and hip symptoms have "
                "improved markedly since Stage 2A began (2026-07-24 check-in: 'first morning in a "
                "while I woke up with no stiffness in my back or hips'). The block is helping; "
                "this pattern is independent of it.",
            ],
        },
        {
            "date":   "2026-08-05",
            "status": "Baseline established — not a symptom; a measurement",
            "region": "Whole-body passive range of motion",
            "title":  "Flexibility Baseline — 22-Pose Self-Rated ROM Assessment",

            "mechanism": (
                "Not an injury entry. The athlete rated every pose of the 15-minute hip/spine "
                "yoga flow (services/yoga.py, YOGA_LIBRARY[0]) on a 1-100 scale where 1 = can "
                "barely enter the position and 100 = at the physical limit with no stretch "
                "sensation left, and gave a free-text reason for each. Same self-assessment "
                "format as the 2026-07-31 cervical ROM entry above. Recorded because it is the "
                "first structured flexibility baseline in this profile and it CORRECTS two "
                "long-standing assumptions. Full per-pose table: docs/training/Yoga_Library.md."
            ),

            "findings": {
                "primary": (
                    "SEATED ANTERIOR PELVIC TILT IS THE DOMINANT RESTRICTION, and it is the "
                    "hamstrings. Three independent seated positions produced the same report: "
                    "straddle forward fold 25/100 ('hips stuck in flexion with tail bone down, "
                    "back fully rounds, unable to get shoulders over the hips unless greatly "
                    "bending the knees — one of the worst stretches in this list'); both seated "
                    "side stretches ~60-65 ('the hips are in flexion with tail bone under me'); "
                    "the opening seated side bend 40 ('only can go about 60-70 percent down, "
                    "restriction in hips'). The pelvis cannot reach anterior tilt in sitting and "
                    "the lumbar spine compensates by rounding. This is the classic presentation "
                    "of proximal hamstring restriction — ALREADY LISTED in imbalances."
                    "overactive_tight ('Proximal hamstrings at ischial tuberosity'), now with a "
                    "functional measurement behind it."
                ),
                "does_not_contradict_anterior_tilt": (
                    "The habitual ANTERIOR pelvic tilt documented in standing (2026-07-06 entry, "
                    "and imbalances.compensation_pattern) is not in conflict. Tight hip flexors "
                    "drive anterior tilt in standing; tight hamstrings drive posterior tilt in "
                    "long-sitting. Both are true, in different postures, and the yoga ratings "
                    "show both — hip-flexor-length poses (deep lunges 50-57, hip openers 46) sit "
                    "in the same restricted band as the seated hamstring poses."
                ),
                "no_passive_lateral_asymmetry": (
                    "The documented right > left asymmetry (findings #1, #2, #4) did NOT appear "
                    "in any passive stretch. Both half pigeons scored 40, both deep lunges 57, "
                    "and the athlete stated it explicitly: 'right and left are the same — no "
                    "blocking sensation on right side'. The asymmetry findings are drawn from "
                    "LOADED and ACTIVE observations and remain valid there; do not expect them "
                    "to show up in passive positioning, and do not read their absence in a "
                    "stretch as resolution."
                ),
                "coxa_saltans_is_contractile": (
                    "See finding #4's additional_evidence_2026_08_05 — no snap in any passive "
                    "flexion+external-rotation position. Trigger requires active iliopsoas load."
                ),
                "thoracic_rotation_better_than_assumed": (
                    "Seated twists scored 66-68 with 'most of the twist comes from the upper "
                    "body' and 'no lumbar pops normally'. Finding #3's sitting-driven T6-T10 "
                    "stiffness had been expected to force the rotation down into the lumbar "
                    "facets; it does not, at least unloaded. Mildly encouraging for the "
                    "interscapular question going to physio on 2026-08-16."
                ),
                "scapular_fatigue_onset_measured": (
                    "MOST DECISION-RELEVANT NUMBER HERE. Down Dog (bodyweight through the "
                    "shoulder girdle) produces interscapular burn at 50-60 SECONDS, not 20-30. "
                    "That is the first quantified endurance threshold for the region in the "
                    "2026-08-03 entry above, and it means the 30s holds elsewhere in this flow "
                    "sit BELOW threshold. Carried into docs/training/physio_brief_2026-08-16.md "
                    "as a dosing anchor for the endurance-biased scapular ask."
                ),
                "open_question_anterior_hip": (
                    "Butterfly forward fold scored 82 but with the sensation reported in the "
                    "HIP FLEXORS ('slight tightness in my hip flexors but nearly at the end of "
                    "the stretch') rather than the adductors. Anterior-hip sensation at deep "
                    "hip flexion in someone who cannot anteriorly tilt is as consistent with "
                    "anterior compression as with a stretch. NOT a claim — a question for the "
                    "physiotherapist, and cheap to ask while the 2026-08-16 appointment is open."
                ),
            },

            "plan": [
                "No self-directed exercise changes. This is a baseline measurement, and the "
                "corrective implication (loaded hamstring lengthening vs. passive stretching in "
                "a hypermobile athlete) is a prescription question, not a self-directed one.",
                "Re-rate the same 22 poses at the next reassessment for a like-for-like "
                "comparison — the value of this baseline is entirely in it being repeated with "
                "the identical instrument.",
                "Raise the anterior-hip sensation in deep hip flexion (above) at 2026-08-16.",
                "Note the hypermobility constraint before acting on any of this: "
                "hypermobility.training_implication explicitly favours controlled-range "
                "strength over passive end-range stretching. A low ROM score here is NOT "
                "automatically an argument for more stretching, and the poses scoring 80-88 are "
                "positions where the athlete is already at end range with no muscular stop.",
            ],

            "notes": [
                "Instrument caveat — a Beighton score is a LAXITY SCREEN, not a ROM "
                "measurement. The palms-flat-to-floor positive scores the whole flexion chain "
                "(hips + lumbar flexion + gravity + locked knees) and does not establish "
                "hamstring length. Using it as a hamstring proxy over-predicted the straddle "
                "fold by 55 points in the 2026-08-05 prediction pass. Do not reuse it that way.",
                "Second instrument caveat — imbalances.overactive_tight is a list of muscles "
                "with high resting TONE, not short muscles. Reading 'overactive' as 'restricted "
                "range' under-predicted 90/90 hip rotation by 52 points. Tone findings predict "
                "behaviour under active control and load; they do not predict passive range.",
                "Prediction accuracy for the record, since it calibrates how far this profile "
                "can be trusted to forecast ROM: 12 of 21 comparable poses predicted exactly, "
                "19 of 21 within 10 points, mean absolute error 2.05 excluding the two "
                "structural misses above, with near-zero signed bias. The profile predicts this "
                "athlete's flexibility well EXCEPT where a laxity screen or a tone finding was "
                "substituted for a length measurement.",
                "One pose was misidentified in services/yoga.py and has been corrected: what "
                "was authored as 'Spine Mobilisation' (tagged cleared, assumed cat-cow family) "
                "is a seated cross-legged side bend with a shoulder drop — lateral flexion, the "
                "same mechanism as the two Seated Side Stretches, now tagged caution and caught "
                "by a new 'side bend' keyword in services/rules.py.",
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
