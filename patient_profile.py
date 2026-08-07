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
            "status_2026_08_07": (
                "DOWNGRADED, NOT RESOLVED — athlete-reported. The 'constant' in `sensation` "
                "above is no longer accurate: day-to-day tightness has fallen from roughly "
                "8-9/10 gripping to about 3/10, and it is no longer present as a baseline "
                "state. THE DECISIVE DETAIL IS THAT THE RELEASE WORK STILL PRODUCES A RELEASE. "
                "The structure still holds tension that responds to the protocol, which is a "
                "positive test, not a null one — so the drop is evidence the release block is "
                "WORKING and is not an argument for removing it. See symptom_log 2026-08-07 "
                "(finding review) for the reasoning and for the chain this sits in."
            ),
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
            "status_2026_08_07": (
                "STILL PRESENT, FREQUENCY HALVED — athlete-reported. The `timeline` field above "
                "('every few days') is now stale: roughly ONCE A WEEK. Note this is the "
                "finding's own mechanism behaving as written — the crack is described as "
                "requiring ACCUMULATION of joint compression, so less compression accumulating "
                "means longer to reach the trigger, and a lengthening interval is the expected "
                "signature of improvement rather than a contradiction. The finding's "
                "training_implication already treats the release itself as healthy. Opportunity "
                "was not the limiter: Stage 2A runs RDL, Bulgarian split squat and single-leg "
                "glute bridge weekly."
            ),
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
            "status_2026_08_07": (
                "REPORTED CEASED — pending physiotherapist confirmation at the 2026-08-16 "
                "reassessment. The athlete reports the release has not occurred for roughly a "
                "month ('since my lower back relaxed'). The finding above is left UNEDITED on "
                "purpose: an assessed finding is not overwritten by a self-report, and an absent "
                "release is ambiguous between compression resolving and the segment stiffening "
                "until someone examines it. Note the report does not separate this finding's TWO "
                "sites, and the stated cause points at the lumbar one. Full reasoning, "
                "corroborating evidence and the two decisions that depend on this: symptom_log "
                "2026-08-07."
            ),
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
            "status_2026_08_07": (
                "UNCHANGED — athlete-reported, still snapping on EVERY attempt. This is the "
                "only one of the five reviewed findings with no movement in either direction, "
                "which is itself informative: findings #1, #2 and #3 all improved over the same "
                "window while this one did not. Consistent with a tendon-path/mechanical "
                "finding rather than a tone-driven one, and consistent with the "
                "additional_evidence_2026_08_05 reading that the trigger is CONTRACTILE. "
                "NOT separately re-confirmed: whether it remains completely PAINLESS. That is "
                "the whole basis for treating it as benign, so do not carry it forward "
                "unstated — the Stage 2 exit criterion measures frequency on 2026-08-16, and "
                "pain status should be confirmed in the same breath."
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
            "status_2026_08_07": (
                "UNCHANGED — athlete-reported, 'still the same'. Note this does NOT conflict "
                "with the 2026-08-05 flexibility baseline's 'no lumbar pops normally' in seated "
                "twists: that is a different position. This finding is specifically a WIDE "
                "STANCE with the pelvis anchored and dynamic rotational torque, which is the "
                "mechanism above — a seated twist lets the hips share the rotation and does not "
                "reproduce it. The two observations are compatible and neither settles the other."
            ),
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
            "Upper Glute / TFL Self-Release (BALL, seated on floor) — 2 × 90s each side",
            "Piriformis Contract-Relax PNF — 3 × 5 cycles each side",
        ],
        "add_when_hip_focused": [
            "Right Posterior Hip Capsule Stretch (FLOOR VERSION — see method_substitutions) "
            "— 3 × 60s RIGHT ONLY. Ran bilaterally in error until 2026-08-07; athlete "
            "reverted to right-only on being shown the rule. Left capsule is not restricted.",
            "Ischial Tuberosity Hamstring Release — 2 × 90s each side",
        ],

        # ── METHOD SUBSTITUTIONS, athlete-reported 2026-08-07 ────────────────
        # Both are changes of METHOD, not of target, dose or sequencing. They
        # are recorded here because the record must match what is actually
        # being done: a protocol that has silently diverged from practice is
        # worse than one that never specified the method. Carries the
        # adapted_from / reason / reverts_when idiom used in
        # cluster_a_mechanics.py. Neither was prescribed here — see
        # symptom_log 2026-08-07 (finding review) for the sign-off question.
        "method_substitutions_2026_08_07": {
            "upper_glute_tfl_self_release": {
                "adapted_from": "Wall or fist",
                "now": "A ball, sitting on it on the floor",
                "reason": (
                    "Athlete-selected. Floor-seated bodyweight over a ball delivers markedly "
                    "higher and more localised pressure than wall or fist, which are "
                    "self-limiting by how hard you can push."
                ),
                "target_unchanged": "Gluteus medius upper fibres / TFL. Dose unchanged at 2 × 90s per side.",
                "watch": (
                    "Higher pressure over the piriformis region sits near the sciatic nerve, "
                    "and this athlete has MODERATE right L5/S1 foraminal stenosis on MRI "
                    "(10 Nov 2025). No neural symptoms are reported anywhere in the log to "
                    "date. Any radiating, burning or tingling sensation down the leg means "
                    "come off it — that is a different signal from the deep ache of a release "
                    "and must not be trained through. Note the intensity went UP while "
                    "finding #1's tightness went DOWN 8-9 -> 3, so the dose-to-tissue "
                    "relationship has changed at both ends."
                ),
            },
            "right_posterior_hip_capsule": {
                "adapted_from": "Cross-body stretch, pulling the knee toward the chest",
                "now": (
                    "RECORDED IN THE ATHLETE'S OWN WORDS AND DELIBERATELY NOT GIVEN A POSE "
                    "NAME. 2026-08-07: 'knee is on the ground and my knee is twisted outwards "
                    "along with my other leg on top of it', clarified as 'knee pressed to the "
                    "floor, body over it'. A first attempt to name this as a stacked "
                    "figure-4/shoelace position was NOT recognised by the athlete and has been "
                    "withdrawn — naming a position wrong in a clinical record is worse than "
                    "describing it plainly, because the name is what a future reader "
                    "reconstructs the movement from. CONFIRM THE POSITION VISUALLY with the "
                    "physiotherapist on 2026-08-16 and only then give it a name."
                ),
                "reason": (
                    "CORRECTED 2026-08-07, same day, before this entry was relied on. An "
                    "earlier draft of this field said the 2026-07-08 re-evaluation 'never "
                    "happened and the broken version ran for the whole block'. THAT WAS WRONG "
                    "AND THE TRUTH IS MORE USEFUL.\n"
                    "What actually happened: the 2026-07-08 session note recorded the original "
                    "cross-body cue landing at the FRONT/middle of BOTH hips with nothing at "
                    "the back — 'I feel the stretch isn't working as expected'. It was acted on "
                    "PROMPTLY. training_plan.RIGHT_HIP_CAPSULE_REVISED was authored in direct "
                    "response, first appearing at PLAN[15] (Stage 1 Week 3, flare recovery), "
                    "and it is what runs throughout ALL of Stage 2A — all three session "
                    "templates plus the reassessment day. The original broken cue does NOT run "
                    "in this block.\n"
                    "THE POINT THAT MATTERS: the revised cue's own biomechanical_focus calls "
                    "itself 'a diagnostic adjustment based on direct session feedback, NOT A "
                    "CONFIRMED FIX YET', and its mechanics text ends by asking the athlete to "
                    "'note whether this version lands differently'. That is an open diagnostic "
                    "question the exercise asked of itself. THE ATHLETE HAS NOW ANSWERED IT — "
                    "by replacing the revised cue too, with a floor position he reports working "
                    "better. So the flat-back-priority variant also did not fully land. Nobody "
                    "collected the answer; it went into the per-exercise notes and stayed there "
                    "(see the Notion notes item in symptom_log 2026-08-07's plan). The system "
                    "asked a question, the athlete answered it in the field provided, and the "
                    "loop was never closed."
                ),
                "coxa_saltans_check_done": (
                    "The new position puts the right hip in FLEXION + EXTERNAL ROTATION, which "
                    "is finding #4's trigger family and would have been a concern under the "
                    "old reading. It is not one under the current reading: "
                    "additional_evidence_2026_08_05 established the trigger is CONTRACTILE, "
                    "not positional — no snap in 90/90 or half pigeon, both passive, "
                    "floor-supported flexion + external rotation. This substitution is passive "
                    "and floor-supported, i.e. exactly the case that evidence cleared. "
                    "Recorded because the check was made, not assumed."
                ),
                "laterality_deviation_closed_by_athlete_2026_08_07": (
                    "RAISED AND CLOSED THE SAME DAY. The athlete had been running this BOTH "
                    "SIDES, having assumed it was bilateral. On being shown that Key Rule 7 "
                    "makes it right-only he elected to return to RIGHT ONLY going forward. "
                    "Recorded because the assumption is the reusable lesson, not the error: "
                    "the original exercise text DOES say 'RIGHT SIDE ONLY — do not mirror on "
                    "the left. Left posterior capsule is not restricted', so the instruction "
                    "existed and was still read past. A laterality instruction buried in the "
                    "middle of a mechanics paragraph is not a reliable place to put one.\n"
                    "The reasoning below is retained because it is the answer to 'why the "
                    "right at all', which the athlete asked directly and which nothing in the "
                    "profile had stated in one place.\n"
                    "THE CONCERN IS NOT THAT STRETCHING THE LEFT IS DANGEROUS — it is a passive "
                    "floor stretch and the risk is low. It is that (a) the LEFT posterior "
                    "capsule was never identified as restricted anywhere in this profile: "
                    "finding #2 names the RIGHT capsule specifically, and finding #1 is "
                    "bilateral but right-dominant; and (b) "
                    "hypermobility.training_implication explicitly favours controlled-range "
                    "strength over PASSIVE END-RANGE STRETCHING, so mobilising an already-lax "
                    "and unrestricted capsule is the precise thing that rule warns against. At "
                    "Beighton 6/9, adding range where no restriction was found is a cost, not "
                    "a neutral act.\n"
                    "CUTTING THE OTHER WAY: the 2026-08-05 flexibility baseline found NO "
                    "left/right asymmetry in any passive position ('both half pigeons scored "
                    "40 ... right and left are the same'), so the left is not obviously "
                    "restricted AND the right is not obviously more so — in passive positioning "
                    "the sides are indistinguishable. That entry also warned explicitly against "
                    "reading absent asymmetry in a stretch as resolution of a LOADED/ACTIVE "
                    "finding. The passive data therefore does not settle this either way.\n"
                    "FOR THE PHYSIOTHERAPIST 2026-08-16, now a narrower question since the "
                    "athlete has already reverted to right-only: was his 'it works better on "
                    "both' evidence of a LEFT restriction the assessment missed, or simply "
                    "that a well-executed stretch feels better on any hip? Only the first "
                    "would justify changing the rule."
                ),
                "why_the_right_side_at_all": (
                    "Asked directly by the athlete 2026-08-07 ('why am I even doing it for the "
                    "right if there isn't any obvious restriction?'), and worth stating in one "
                    "place because it was scattered across three files. THREE REASONS, all "
                    "still live:\n"
                    "(1) FINDING #2. The tight right posterior capsule is the identified "
                    "MECHANISM of the standing hinge crack — 'femoral head glides backward "
                    "against tight RIGHT posterior capsule' under load-bearing rotational "
                    "torque. That finding was re-confirmed present on 2026-08-07 (still "
                    "cracking, ~weekly). The justification is not historical; it is current.\n"
                    "(2) A LOADED, ACTIVE OBSERVATION — BUT WEAKER THAN IT LOOKS, and this was "
                    "corrected the same day after reading the raw note. "
                    "training_plan.RIGHT_HIP_CAPSULE's biomechanical_focus cites 'the "
                    "resistance felt during single-leg RDL on the right', which stands. What "
                    "does NOT stand as corroboration is the 2026-07-01 session note, recorded "
                    "elsewhere as confirming finding #2's right-side asymmetry. Its actual "
                    "words: 'Right Posterior hip capsule stretch - there was a strong tightness "
                    "in the GROIN. Uncomfortable feeling, it wasn't the case for the left "
                    "side'. THE GROIN IS ANTERIOR. That is the same mistargeting complaint that "
                    "got the exercise revised a week later on 2026-07-08 ('tightness at the "
                    "front hip ... no feeling at the back of the hip or bum'). So 07-01 "
                    "recorded a right-dominant ANTERIOR sensation during a stretch that was "
                    "already failing to reach the posterior capsule — a real asymmetry, but "
                    "not evidence of posterior capsule restriction. See the anterior-hip thread "
                    "in symptom_log 2026-08-07 (note corpus review).\n"
                    "(3) THE SPINE, NOT THE HIP — and this is the one nobody had surfaced. The "
                    "same biomechanical_focus states it 'reduces the compressive force on the "
                    "RIGHT L5/S1 FORAMEN by restoring femoral head position'. The Nov 2025 MRI "
                    "reads moderate foraminal stenosis RIGHT, mild left, at L5/S1. So the "
                    "exercise is asymmetric because the STENOSIS is asymmetric. There is no "
                    "left-sided equivalent because there is no comparable left-sided "
                    "narrowing.\n"
                    "WHY 'NO OBVIOUS RESTRICTION' IS A FALSE PREMISE: it comes from the "
                    "2026-08-05 flexibility baseline finding no left/right asymmetry in any "
                    "PASSIVE position. That entry warned against exactly this inference — the "
                    "asymmetry findings are drawn from LOADED and ACTIVE observations, and "
                    "'do not read their absence in a stretch as resolution'. Finding #2 is "
                    "triggered by load-bearing rotational torque and was never a passive "
                    "finding, so passive screening could not have detected it either way."
                ),
                "note_on_key_rule_7s_other_half": (
                    "Rule 7's first clause — 'all exercises involving right hip flexion >60 "
                    "degrees require a neutral/internal rotation cue' — reads as violated by "
                    "this position, which is deep right hip flexion in EXTERNAL rotation. It is "
                    "not, under the current reading: finding #4's "
                    "additional_evidence_2026_08_05 narrowed the trigger to CONTRACTILE load "
                    "and stated explicitly 'do not treat passive, floor-supported external "
                    "rotation as a risk position'. The rule text in CLAUDE.md has not been "
                    "updated to carry that narrowing and so reads stricter than the evidence "
                    "supports. Flagged as documentation drift; not edited here."
                ),
            },
        },
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
                    "the lumbar spine compensates by rounding.\n"
                    "RESTATED 2026-08-05 (same day) against the Jan-2025 gym goniometry, which "
                    "reads hamstrings 89° left / 86° right and calls them NORMAL. The two agree; "
                    "the first wording here did not. This is NOT short hamstrings — it is NORMAL "
                    "hamstring length with NO RESERVE for the task. Long-sitting upright is "
                    "already ~90° of hip flexion with the knee straight, so at 86-89° he arrives "
                    "at the hamstring limit merely sitting up with his legs out, and every "
                    "further degree of forward fold has to come from the spine. An ordinary "
                    "hamstring paired with an exceptional lumbar flexion is what produces the "
                    "25/100 — the spine writes cheques the hamstring cannot cover, and the "
                    "rounding hides the limit rather than revealing it. Still consistent with "
                    "imbalances.overactive_tight ('Proximal hamstrings at ischial tuberosity'), "
                    "which is a TONE finding and was never a length claim.\n"
                    "CONFIDENCE: the goniometry's protocol is UNRECORDED. If 'Hamstrings 89/86' "
                    "is a passive straight-leg raise the reconciliation above holds; if it is a "
                    "popliteal-angle test the numbers mean something else and this needs redoing. "
                    "Confirm the protocol at the next scan before treating the reconciliation as "
                    "settled — see flexibility_baselines.py."
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
        {
            "date":   "2026-08-07",
            "status": "Finding change — reported ceased, pending physiotherapist confirmation 2026-08-16",
            "region": "Mid-thoracic spine + lumbar base (biomechanical finding #3 territory)",
            "title":  "Sitting Forward-Bend Releases Have CEASED — Finding #3 No Longer Reproducing",

            "mechanism": (
                "Athlete-reported 2026-08-07, unprompted: the seated forward-bend release "
                "described in biomechanical finding #3 'doesn't happen anymore, not since maybe "
                "one month, since my lower back relaxed'. This is a NEGATIVE finding — the "
                "absence of a phenomenon the 2026-06-28 assessment recorded in the present "
                "tense — and it is logged rather than left unrecorded because finding #3 drives "
                "live decisions elsewhere in this profile, so its lapsing is not inert.\n"
                "TIMING IS APPROXIMATE AND CANNOT BE PINNED. '~one month' brackets to roughly "
                "2026-07-07; it is a recalled date, not an observed one, and no check-in field "
                "tracks the release phenomenon, so there is no independent record of when it "
                "stopped. What IS established: it postdates the 2026-06-28 assessment that "
                "recorded the finding, and it falls in the same window as the Stage 1 -> Stage "
                "2A transition (2026-07-20) and the documented low-back improvement."
            ),

            "findings": {
                "two_readings_and_why_one_is_favoured": (
                    "An absent release admits two readings and they have OPPOSITE meanings. "
                    "(A) The chronic seated compression that produced the release has resolved, "
                    "so there is nothing left to release — improvement. (B) The segment has "
                    "stiffened and can no longer release — deterioration presenting as silence. "
                    "(A) is favoured, because (B) would normally arrive with MORE symptoms and "
                    "the symptom load in this region has fallen, not risen. The athlete's own "
                    "attribution ('since my lower back relaxed') is also a causal claim in "
                    "direction (A). This is a judgement, not a measurement — hence 'pending "
                    "confirmation' rather than 'resolved'."
                ),
                "corroborating_evidence_already_on_record": (
                    "Two independent lines, neither collected for this purpose, point the same "
                    "way. (1) Morning check-in 2026-07-24: 'first morning in a while I woke up "
                    "with no stiffness in my back or hips', and docs/training/"
                    "physio_brief_2026-08-16.md section 3 records low back and hips as markedly "
                    "improved. (2) The 2026-08-05 flexibility baseline above found thoracic "
                    "rotation BETTER than finding #3 assumed — seated twists 66-68, 'most of the "
                    "twist comes from the upper body', 'no lumbar pops normally'. That entry "
                    "already flagged the tension with finding #3 without resolving it; this "
                    "entry is the second, independent signal in the same direction."
                ),
                "what_it_changes_if_confirmed": (
                    "Finding #3 is not dormant — it is load-bearing in two live places. (1) It "
                    "is DRIVER 3 of the interscapular endurance mechanism in the 2026-08-03 "
                    "entry above ('thoracic stiffness tilts the scapula forward off the ribcage, "
                    "leaving the retractors holding lengthened all day'), which is the §1 ask "
                    "going to the physiotherapist on 2026-08-16. If the thoracic component is "
                    "resolving, that driver weakens and the four-driver picture becomes three. "
                    "(2) It is the stated rationale for keeping Thoracic Extension (Rolled "
                    "Towel) in the block — training_plan.py's comment justifies it explicitly by "
                    "the recurring mid-back pattern. Neither should be changed self-directed; "
                    "both should be re-derived once the physiotherapist rules on the finding."
                ),
                "unresolved_which_of_the_two_sites": (
                    "Finding #3 names TWO distinct sites — mid-thoracic (T6-T10 facets) and the "
                    "horizontal lumbar base (L5/S1). The report was of the phenomenon as a "
                    "whole and does not separate them, while the stated cause ('since my lower "
                    "back relaxed') points specifically at the lumbar component. It is therefore "
                    "possible the lumbar site has settled and the thoracic site simply is not "
                    "being provoked. This matters because it is the THORACIC site that feeds "
                    "driver 3 above. Ask the physiotherapist to separate them."
                ),
            },

            "plan": [
                "No self-directed exercise changes, and specifically do NOT remove Thoracic "
                "Extension (Rolled Towel) or amend finding #3 on the strength of this entry. A "
                "finding that stops reproducing is a question for the physiotherapist, not a "
                "licence to delete the work that may be why it stopped.",
                "Raise at 2026-08-16 as a finding-status question, and ask for the two sites "
                "(thoracic vs. lumbar base) to be assessed separately — see "
                "docs/training/physio_brief_2026-08-16.md section 12.",
                "If confirmed resolved, re-derive the 2026-08-03 interscapular mechanism from "
                "three drivers rather than four before the next block is authored, and re-state "
                "the rationale for thoracic extension work rather than silently dropping it.",
                "Finding #3 itself is left UNEDITED and carries a status_2026_08_07 flag "
                "instead — same convention as finding #4's additional_evidence fields. An "
                "assessed finding is not overwritten by a self-report.",
            ],

            "notes": [
                "Convention note: this profile has no established way to record a finding that "
                "STOPS. The symptom_log is built for onsets, and biomechanical_findings is "
                "written in the present tense with no status field. A finding quietly ceasing "
                "and nobody noticing is the failure mode this entry exists to prevent — the "
                "2026-06-28 assessment is otherwise carried forward indefinitely as current.",
                "Not recorded here, deliberately: post-training soreness. Normal training "
                "response belongs in the training log, not the clinical record.",
            ],
        },
        {
            "date":   "2026-08-07",
            "status": "Finding review — self-reported; physiotherapist confirmation 2026-08-16",
            "region": "All six biomechanical findings + pre-session release protocol",
            "title":  "Biomechanical Findings Review — Three Improved, Two Unchanged, and They Split Along the Mechanism Line",

            "mechanism": (
                "Second entry dated 2026-08-07. Prompted by the finding #3 report above: if one "
                "assessed finding had quietly stopped reproducing, the others had not been "
                "checked either. THIS IS THE FIRST TIME THE SIX FINDINGS HAVE BEEN REVIEWED AS "
                "A SET since the 2026-06-28 assessment recorded them — six weeks carried "
                "forward as current without anything asking whether they still were.\n"
                "All of it is athlete self-report against the finding descriptions, recalled "
                "rather than measured. No measurement protocol exists for findings #1, #2 or "
                "#5, which is a gap this entry exposes rather than closes."
            ),

            "findings": {
                "results": (
                    "#1 Upper glute / hip crest tightness — DOWNGRADED, NOT RESOLVED. From "
                    "~8-9/10 constant gripping to ~3/10, no longer a day-to-day baseline state. "
                    "Decisively, the release work STILL PRODUCES A RELEASE.\n"
                    "#2 Standing leg hinge crack (right sit-bone) — STILL PRESENT, frequency "
                    "from 'every few days' to roughly ONCE A WEEK.\n"
                    "#3 Sitting forward-bend releases — CEASED. Second and firmer report the "
                    "same day ('no longer there', vs. the earlier 'not since maybe one month'). "
                    "See the preceding entry.\n"
                    "#4 Right 90-degree hip click (Coxa Saltans) — UNCHANGED, every attempt.\n"
                    "#5 Wide-stance windmill twist cracks — UNCHANGED, 'still the same'.\n"
                    "#6 Right shoulder instability — NOT self-assessed. Maintenance-dependent "
                    "by design and not expected to resolve; its live components (left-tilt "
                    "compensation under pressing) are written Stage 2 exit criteria and are "
                    "measured on 2026-08-16 regardless."
                ),
                "the_split_is_along_the_mechanism_line": (
                    "THE MOST INTERESTING RESULT IS NOT ANY SINGLE FINDING, IT IS WHICH ONES "
                    "MOVED. The three that improved — #1, #2, #3 — are precisely the three this "
                    "profile links into ONE causal chain, and they eased in the order the chain "
                    "predicts. #1 is named in its own mechanism as 'the primary anchor driving "
                    "joint compression throughout the chain'; #2's mechanism requires "
                    "'accumulation of joint compression' to trigger; #3 is compression-driven "
                    "facet release. The anchor loosened, and both downstream compression "
                    "phenomena eased — one halving in frequency, one stopping. The low back "
                    "settling (2026-07-24 check-in) sits in the same window.\n"
                    "The two that did NOT move — #4 and #5 — are the two that are not "
                    "compression-accumulation driven: #4 is a tendon path over a bony ridge "
                    "(and per 2026-08-05 a CONTRACTILE trigger), #5 is capsular/symphyseal "
                    "cavitation under rotational torque with the pelvis anchored. Neither "
                    "should have responded to reducing resting tone, and neither did.\n"
                    "This is CONSISTENT WITH the profile's causal model, not proof of it — the "
                    "sample is one athlete's recall over six weeks with several things changing "
                    "at once (Stage 1 completing, Stage 2A starting, desk changes). But the "
                    "model made a structural prediction about which findings share a driver, "
                    "and the observed split matches it. Recorded because a model that predicts "
                    "correctly is worth more than the individual readings."
                ),
                "what_this_does_not_license": (
                    "IT DOES NOT LICENSE REMOVING THE PRE-SESSION RELEASE BLOCK. Finding #1 "
                    "dropped 8-9 -> 3 while under five-days-a-week release work, and the "
                    "release still produces a release — the most likely reading is that the "
                    "protocol is why the tightness fell, which makes removing it the reliable "
                    "way to get it back. Same reasoning as the thoracic extension note in the "
                    "preceding entry. A finding that improved under treatment is not evidence "
                    "the treatment was unnecessary."
                ),
                "protocol_method_substitutions": (
                    "Two SELF-DIRECTED method changes were reported in the same conversation "
                    "and are now recorded in pre_session_release.method_substitutions_2026_08_07: "
                    "(1) upper glute / TFL self-release moved from wall-or-fist to a BALL sat on "
                    "on the floor; (2) the posterior hip capsule stretch moved from the "
                    "cross-body knee pull to a floor position recorded in the athlete's own "
                    "words ('knee pressed to the floor, body over it') and DELIBERATELY LEFT "
                    "UNNAMED — an attempt to name it was not recognised and was withdrawn. It "
                    "is also now run BOTH SIDES, which deviates from Key Rule 7's right-only "
                    "rule and is unresolved.\n"
                    "(2) IS THE SECOND ATTEMPT AT THIS EXERCISE, NOT THE FIRST. The original "
                    "cross-body cue was documented as mistargeting on 2026-07-08 and WAS acted "
                    "on promptly — RIGHT_HIP_CAPSULE_REVISED (flat-back priority over stretch "
                    "distance) replaced it from PLAN[15] and runs throughout Stage 2A. The "
                    "revised cue described itself as 'not a confirmed fix yet' and asked the "
                    "athlete to note whether it landed differently. His substitution IS the "
                    "answer to that question: it did not fully land either. Both substitutions "
                    "change METHOD only — same target, same dose, same position in the "
                    "sequence — so neither is a prescription change in the sense the standing "
                    "instruction restricts. Flagged to the physiotherapist as notification "
                    "rather than as an ask."
                ),
            },

            "plan": [
                "LATERALITY IS ANSWERED AND IS A DEVIATION: the floor version is run BOTH "
                "SIDES against CLAUDE.md Key Rule 7's right-only rule. Physiotherapist decides "
                "on 2026-08-16; do not stop the left side before then on this log's authority. "
                "Full reasoning both ways in "
                "pre_session_release.method_substitutions_2026_08_07.",
                "READ THE PER-EXERCISE NOTION NOTES. The athlete reports maintaining protocol "
                "notes 'attached to every exercise ... during the exercise', which are the "
                "`tp_note_<idx>` field in views/training.py, written to the Training Log row's "
                "`Notes` property per exercise. THIS IS WHY THE PROTOCOL DRIFTED: a live "
                "athlete-authored record of how exercises are actually executed exists, is "
                "readable (Repository.get_recent_raw_notes / get_unparsed_session_notes), and "
                "NOTHING feeds it back into this profile — only an AI sentiment pipeline "
                "consumes it. CORRECTED TWICE ON 2026-08-07, and the second correction found a "
                "BUG. First: the substitutions are not in the corpus (21 notes, 2026-06-30 to "
                "2026-08-06, neither the ball nor the floor capsule version appears). Second, "
                "on asking WHY: THE PER-EXERCISE NOTE FIELD HAS NEVER SAVED ANYTHING. All 21 "
                "notes are session-wide notes written by save_session_notes() onto the LAST "
                "exercise row of each session — the 2026-07-08 note about the capsule stretch, "
                "dead bug and wall sit is filed under 'Side Bridge with Hip Dip'; the "
                "2026-07-21 dead-bug clicking note is filed under 'Controlled Walking'. Zero "
                "per-exercise notes exist. The athlete WAS using the right field; the field "
                "discards its contents. See symptom_log 2026-08-07 (note corpus review) for "
                "the mechanism and for four findings the session-level corpus still yielded.",
                "Confirm finding #4 is still completely PAINLESS when its frequency is measured "
                "at the 2026-08-16 reassessment. Painlessness is the entire basis for treating "
                "the snap as benign and it was not separately re-confirmed in this review.",
                "Do not remove or reduce the pre-session release block on the strength of "
                "finding #1's improvement — see what_this_does_not_license above.",
                "Raise both method substitutions at 2026-08-16 as notification plus the one "
                "laterality question — docs/training/physio_brief_2026-08-16.md section 12.",
                "Build a repeatable way to re-measure findings #1, #2 and #5 before the next "
                "block, even if crude (a 0-10 tightness rating for #1, a frequency count for #2 "
                "and #5). This review had to run on recall because nothing instruments them, "
                "and 'every few days' vs 'once a week' is exactly the kind of change that "
                "should not depend on memory.",
            ],

            "notes": [
                "Findings #1, #2, #4 and #5 now carry status_2026_08_07 flags and are otherwise "
                "UNEDITED, matching the convention used for #3 in the preceding entry and for "
                "#4's earlier additional_evidence fields. The 2026-06-28 assessment text stays "
                "as assessed; self-report annotates it and never overwrites it.",
                "Two of the six findings' own fields are now stale as written and the flags say "
                "so rather than the fields being corrected: #1's sensation says 'constant', #2's "
                "timeline says 'every few days'. Left in place deliberately — the original "
                "wording is what the assessment found.",
            ],
        },
        {
            "date":   "2026-08-07",
            "status": "Retrospective review of existing data — no new symptom",
            "region": "Multiple — anterior right hip, interscapular, upper glute, lower back",
            "title":  "Per-Exercise Note Corpus Read for the First Time — Four Findings, One Correction",

            "mechanism": (
                "Third entry dated 2026-08-07. The athlete identified during conversation that "
                "he maintains notes 'attached to every exercise ... during the exercise'. Those "
                "are the `tp_note_<idx>` field in views/training.py, written to each Training "
                "Log row's `Notes` property in Notion and readable via "
                "Repository.get_recent_raw_notes(). NOTHING HAD EVER READ THEM back into this "
                "profile — only an AI sentiment pipeline consumes the field. Read in full on "
                "2026-08-07: 21 notes spanning 2026-06-30 to 2026-08-06.\n"
                "SCOPE CORRECTION: the substitutions the athlete described (ball; floor capsule "
                "position) are NOT in this corpus. Wherever he maintains those, it is not this "
                "field. That question is still open and the drift it caused is unexplained."
            ),

            "findings": {
                "anterior_right_hip_is_a_thread_not_an_incident": (
                    "THE MOST DECISION-RELEVANT ITEM, and it changes the reading of an existing "
                    "record. THREE independent anterior-hip observations now line up:\n"
                    "2026-07-01, during the right posterior capsule stretch: 'strong tightness "
                    "in the GROIN. Uncomfortable feeling, it wasn't the case for the left side'. "
                    "This was previously filed as confirming finding #2's right-side asymmetry "
                    "— but the groin is ANTERIOR and the intended target is posterior.\n"
                    "2026-07-08, same exercise: 'Tightness at the front hip, it's in the middle "
                    "of the hip and it's happening on both sides, nearly pain in holding the "
                    "stretch and no feeling at the back of the hip or bum'. Note 'NEARLY PAIN' "
                    "— the strongest sensation word anywhere in the corpus.\n"
                    "2026-08-05, butterfly forward fold: scored 82 but sensation reported in the "
                    "HIP FLEXORS rather than the adductors, already flagged as 'as consistent "
                    "with anterior compression as with a stretch'.\n"
                    "The 2026-08-05 entry raised anterior compression as a one-off question. It "
                    "is not a one-off: deep right hip flexion has produced anterior sensation "
                    "across three separate months and two unrelated exercises. This should go "
                    "to the physiotherapist as a THREAD with dates, not as a single curiosity — "
                    "and it means the 07-01 observation cannot be double-counted as evidence "
                    "for the posterior capsule finding it was filed under."
                ),
                "finding_1_corroborated_independently_and_contemporaneously": (
                    "2026-08-06, i.e. YESTERDAY, unprompted: 'Right glute upper was tight going "
                    "into training but feels good now'. This is finding #1 behaving exactly as "
                    "the athlete described it in conversation the following day — no longer a "
                    "constant baseline, still present pre-session, and RESOLVING WITH THE "
                    "RELEASE WORK. Contemporaneous, written before the question was asked, and "
                    "therefore stronger evidence than the recall it corroborates. It also "
                    "independently supports the 'do not remove the release block' conclusion in "
                    "the finding review entry above."
                ),
                "interscapular_series_extends_past_2026_07_31": (
                    "The 2026-08-03 consolidation states severity 'flat and low throughout ... "
                    "on every check-in 2026-07-16 -> 2026-07-31'. The corpus extends that "
                    "series. 2026-08-04: 'Right shoulder at the back between the shoulder blade "
                    "and the spine felt weak or tight or tired. DURING EXERCISE but now I can't "
                    "feel anything wrong, it feels good now.' Two things are new: it is "
                    "RIGHT-sided (the consolidation's CORRECTION 2 established bilateral with "
                    "left dominance, so this supports bilateral), and it is EXERCISE-PROVOKED "
                    "AND SELF-RESOLVING rather than desk-accumulated. 'Weak or tight or tired' "
                    "is a fatigue description, which is consistent with the endurance-gap "
                    "reading the §1 physio ask rests on. Carry this date into the brief — the "
                    "presentation table currently stops at 07-31."
                ),
                "lower_back_improvement_dates_earlier_than_recorded": (
                    "2026-07-14: 'Overall lower back tightness has improved DRAMATICALLY'. The "
                    "improvement has been cited from the 2026-07-24 check-in ('first morning in "
                    "a while ...'); it was already dramatic ten days earlier. This tightens the "
                    "finding #3 timeline in the entry above — the athlete dated the cessation of "
                    "the forward-bend releases to '~one month' ago, i.e. roughly 2026-07-07, and "
                    "attributed it to the lower back relaxing. A 07-14 'dramatic' improvement "
                    "sits directly between the two and makes the athlete's causal sequence "
                    "chronologically coherent rather than merely plausible."
                ),
                "corpus_also_confirms_two_findings_unchanged": (
                    "2026-07-21: 'Clicking still on right side during dead bug' — finding #4, "
                    "consistent with today's 'every attempt' report and with the supine "
                    "additional_evidence_2026_07_08. 2026-07-04: 'Tightness in the thoracic "
                    "rotation' — predates the 07-07 mid-back flare."
                ),
            },

            "plan": [
                "Take the anterior-right-hip THREAD to 2026-08-16 with all three dates, not "
                "just the 2026-08-05 butterfly question. Deep right hip flexion producing "
                "anterior/groin sensation across three months and two exercises, in someone "
                "who cannot achieve anterior pelvic tilt in sitting, is a different question "
                "from a single odd stretch sensation.",
                "Add 2026-08-04 to the interscapular presentation table in "
                "docs/training/physio_brief_2026-08-16.md — the table stops at 07-31 and the "
                "symptom did not.",
                "FIX THE PER-EXERCISE NOTE FIELD — it has never saved anything, and that is "
                "where the athlete put the substitutions. views/training.py renders the note "
                "widget with key tp_note_<idx> for the CURRENT exercise only, and "
                "_auto_log_session reads that same key at the end of the session. Streamlit "
                "discards a keyed widget's session_state entry as soon as the widget stops "
                "being rendered, which happens the instant tp_ex_idx advances — so every note "
                "is gone before it can be read. The reps/weight steppers survive precisely "
                "because they are checkpointed into a PLAIN DICT (st.session_state.tp_actuals) "
                "rather than left in widget state; the notes were not given the same "
                "treatment. The code comment at views/training.py:2396-2400 asserts the notes "
                "persist, which is why this went unnoticed for six weeks. Fix is to mirror the "
                "tp_actuals pattern. THIS IS A CLINICAL DATA-LOSS BUG, not a UI nicety: the "
                "notes it discarded are exercise-level execution feedback in the athlete's own "
                "words, which is the highest-value signal this profile receives and the one it "
                "has least of.",
                "Wire this corpus into the review loop rather than reading it once. It took a "
                "conversational aside to discover a readable, athlete-authored record that had "
                "accumulated 21 entries over six weeks without ever being read.",
            ],

            "notes": [
                "Read via Repository.get_recent_raw_notes(limit=200); 21 non-empty notes "
                "returned. Notion is NOT covered by the offline datastore (see CLAUDE.md), so "
                "this was a live API read.",
                "Nothing in the corpus contradicts any finding. Its value was entirely in "
                "dates, laterality and the athlete's own wording — 'groin', 'front hip', "
                "'nearly pain', 'weak or tight or tired' — none of which survived into the "
                "structured record, and one of which (groin) had been paraphrased into a "
                "conclusion it does not support.",
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
