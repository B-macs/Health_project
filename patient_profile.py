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
  Saltans trigger is contractile rather than positional. (A fourth claim —
  an interscapular burn-onset time — was recorded here and REMOVED 2026-08-10:
  no basis, not reproducible on retest; its tombstone is in the entry.)

2026-08-07: first anterior-chest signal on the post-Latarjet right shoulder
  put on record (symptom_log entry + finding #6 addendum): a LONG-STANDING,
  painless, position-specific cramp/'lock-out' in the pec-minor region just
  medial to the surgical scar, right only — present since the years after the
  surgeries, well before the recent injury era, and never provoked by pressing
  (it coexisted with active Incline DB pressing eras), so it does not bear on
  the Stage 2 shoulder exit criterion. The location is surgically altered
  anatomy — the Latarjet transferred the coracoid, pec minor's insertion — so
  the plan is tissue identification by the physio at 2026-08-16 (brief §13),
  not self-treatment, and explicitly NO pec stretching until then. Trend was
  never observed before now; the entry is the baseline for watching it.

2026-08-10: the physiotherapist answered ALL 13 questions in the Day-28 brief,
  six days early (symptom_log 2026-08-10; the Day 28 stage-gate decisions are
  NOT in it and still land 2026-08-16). Headlines: scapular holds APPROVED,
  and the earlier interscapular burn-onset claim (50-60s) is REMOVED outright
  — no basis, not reproducible: the studio retest held Down Dog 4+ minutes,
  arms would fail first, shoulder blades can train normally to failure (the
  issue is stillness/stiffness, not weakness, and
  the chair's forearm supports already removed most of the pressure). §8
  settled: the right is weaker, the left overcompensates — train BOTH sides.
  The Cluster A organising claim is CONFIRMED (hips drive the lumbar
  rounding). The butterfly anterior-hip sensation is a normal short-hip-flexor
  stretch, unblocking the battery's first test. Horse stance and Cossack are
  cleared (no rotation cue named — the ER cue stands). The 25-point wide-gap
  threshold holds; overhead reach shows NO capsular issue. The pec cramp is
  diagnosed (positional ischemic cramp / scar adhesion lockout) with a
  release + active-reciprocation prescription expected to OUTPERFORM
  stretching (stretching permitted, not preferred — athlete's clarification
  of the physio's intent) — the one item cleared for self-directed use.
  Ferritin stays with the GP. Same day: the athlete resolved the brief's §15
  follow-ups himself and two release protocols were authored as pre-registered
  hypothesis tests (docs/training/release_protocols_2026-08-10.md) — the pec
  work starts immediately, the anterior-hip work only AFTER the battery
  baseline is captured. Prescriptions still get encoded at the next block
  build, not before.

2026-08-13: THE INTERSCAPULAR SYMPTOM IS SOLVED TO A TISSUE, and this file's
  append-only convention changed to let that land. The athlete marked the area
  on an anatomy plate and ran discriminating tests; the answer is LEFT
  TRAPEZIUS (upper/middle fibres and the C7-T3 aponeurosis), position-loaded
  and PERFUSION-limited — sustained low-level contraction occludes flow, which
  is why movement and heat relieve it and eight hours of holding does not.
  Rhomboid, levator scapulae and the deep cervicothoracic layer are each ruled
  out by a named test. CONVENTION CHANGE, the athlete's direction — "this was
  all guess work; what we are doing now should overwrite that as it is real
  planning and tests": ASSESSMENTS that testing has refuted are now replaced
  IN PLACE with a tombstone naming what went and what would reinstate it,
  while OBSERVATIONS are still never overwritten. Four things in this file were
  wrong and are corrected: the location was NOT the medial scapular border (it
  is ~2-4cm lateral to the spinous processes, and the 2026-07-31 entry had it
  right before the 2026-08-03 entry moved it); "sitting, standing AND treadmill
  alike" does NOT mean duration-not-posture (all three load the same tissue by
  different routes, and a standing desk is WORSE than sitting here); driver (1)
  of the 2026-08-03 entry is now MEASURED rather than inferred (at matched lift
  height the left works harder than the right — that is why it is the left);
  and "five days a week of scapular work" IS FALSE — the log says 4, then 3,
  then 2, then 2, a figure taken from training_plan.py rather than from
  training_exercises. NOTE the second half of that claim was itself corrected
  the same day: a first pass counted off a two-day-stale datastore snapshot,
  read "0 scapular days this week", and wrongly overturned the 2026-08-03
  entry's "the symptom persists through the dose" — which is CORRECT. Scapular
  Wall Slide ran 2026-08-11 and Face Pull 2026-08-12, and 2026-08-12 is the
  worst day on record (first pain above 0/10 in three weeks). Prone Y-Raise,
  last run 2026-07-24, is the one genuine omission. REBUILD THE SNAPSHOT
  BEFORE COUNTING. Training is
  exonerated by the log (six interscapular reports, six weekdays; three clean
  weekends; a 10km hike with no symptoms), which also means running is not
  implicated for Stage 2B. The tendon question is answered LESS LIKELY, NOT
  EXCLUDED, with two cheap tests still open. Everything prescribed is
  self-directed and already cleared: the physiotherapist may not be available
  until September or later, so questions are worked out here rather than
  deferred.

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
  question, AND endurance-biased scapular programming (see the 2026-08-13
  symptom_log entry, which REPLACES the 2026-08-03 framing: the claim that
  five days a week of scapular work already runs is false — the log shows 4,
  3, 2 then 0, and the two low-load holding items dropped out entirely — so
  volume was never ruled out, and the mechanism is perfusion rather than an
  endurance shortfall. The isometric-hold direction for Stage 2B is already
  physio-confirmed, so this points an agreed decision at this region rather
  than opening a new one). All three are explicit deferred decisions, not
  oversights; settle them at the block build. NOTE the physiotherapist is not
  available on demand — possibly not until September or later (athlete,
  2026-08-13) — so a decision that can be reasoned from the log and the
  clinical documents is made here rather than deferred indefinitely.
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
                          "endurance-biased scapular programming (2026-08-13 symptom_log entry, "
                          "which supersedes the 2026-08-03 'endurance gap, not volume gap' framing "
                          "— the five-days-a-week premise is false and the mechanism is perfusion) "
                          "— see module docstring and docs/training/physio_brief_2026-08-16.md",

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
            "additional_evidence_2026_08_07": (
                "First ANTERIOR signal RECORDED on this shoulder: a LONG-STANDING, "
                "position-specific, painless cramp / 'locking out' burn in the pec-minor "
                "region just medial to the surgical scar — right only, the identical "
                "position on the left is completely clear (prayer hands at the chest, "
                "fingers forward, forearms ~45° up toward the face). Chronicity: present "
                "since the years after the surgeries and well before the 2025/2026 injury "
                "era — attention to it is recent, so trend is unobserved; onset after the "
                "Latarjet is consistent with, not proof of, the transferred pec minor "
                "insertion being involved. Documented negative: never appeared during "
                "pressing, across past eras of active Incline DB pressing — it does NOT "
                "bear on the Stage 2 shoulder exit criterion. Everything previously "
                "recorded here is posterior/scapular. Reads as CONTRACTILE (active "
                "contraction in a shortened position), not positional — finding #4's "
                "framing. Tissue identification belongs to the physio (2026-08-16, brief "
                "§13). Full entry: symptom_log 2026-08-07. Does not change the training "
                "implication above — scapular-control-first, conservative pressing — but is "
                "direct new evidence on the physio brief's §8 right-vs-left question."
            ),
            "additional_evidence_2026_08_10": (
                "The physiotherapist ANSWERED the 2026-08-07 question set (symptom_log "
                "2026-08-10). The anterior cramp is diagnosed: POSITIONAL ISCHEMIC CRAMP / "
                "SCAR ADHESION LOCKOUT — shortened tissue firing hard in a shortened range, "
                "catching on dense surgical scar tissue and briefly cutting off blood flow; "
                "no structural pain. Entirely safe to address; release and active work are "
                "expected to OUTPERFORM stretching (stretching permitted, not preferred) — "
                "targeted scar & pec minor self-myofascial release plus subscapularis / "
                "anterior-wall active reciprocation with isometric holds. Two further "
                "answers touch this finding directly: overhead reach shows NO capsular "
                "restriction (reach fully overhead, stretch as normal), and the §8 "
                "question is settled — the RIGHT is the weaker side, the left is "
                "overcompensating, and BOTH sides get strengthened rather than isolating "
                "one side. The training implication above stands, now with sign-off "
                "attached."
            ),
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
                # ─── ASSESSMENT REPLACED 2026-08-13 ──────────────────────────
                # The athlete's direction: "this was all guess work; what we
                # are doing now should overwrite that as it is real planning
                # and tests." Observations in this entry are UNTOUCHED — only
                # the reasoning below was replaced, because it was inferred
                # from a symptom description and has since been refuted by
                # testing. See the 2026-08-13 entry for the tested finding;
                # it is the single place that finding lives.
                # ────────────────────────────────────────────────────────────
                "likely_tissue": [
                    "SUPERSEDED 2026-08-13 — the tissue is left TRAPEZIUS (upper/middle fibres "
                    "and the C7-T3 aponeurosis). See the 2026-08-13 entry.",
                    "REMOVED: 'left rhomboid / mid-trapezius'. A protraction stretch with the "
                    "neck neutral lengthens rhomboid directly and does NOT reproduce the "
                    "symptom (tested 2026-08-13). REINSTATE IF that test turns positive.",
                    "REMOVED: 'left levator scapulae' as the local generator. Levator inserts at "
                    "the SUPERIOR ANGLE of the scapula — outside the band the athlete marked on "
                    "an anatomy plate (~2-4cm lateral to the spinous processes, C7/T1 to T4/T5). "
                    "It cannot generate pain there, though it may still explain the neck-base "
                    "migration. REINSTATE IF the marked location moves to the superior angle.",
                ],
                "mechanism": (
                    "SUPERSEDED 2026-08-13. What was removed: the reading that symptoms across "
                    "sitting, standing AND treadmill prove the driver is DURATION rather than "
                    "posture. It is not. The athlete described the three positions on 2026-08-13 "
                    "and each loads the same tissue by a DIFFERENT route — sitting drives head "
                    "forward; standing lets the arms dangle, which is unsupported arm weight at "
                    "its maximum; the treadmill fixes the hands on a keyboard while the legs "
                    "move, so the shoulder girdle cancels every footfall. Changing position "
                    "never helped because all three converge on trapezius. The 'stiffness-from-"
                    "stillness over a structural issue' half of the old text SURVIVES and was "
                    "correct — see the 2026-08-13 entry, which sharpens it to a perfusion "
                    "mechanism rather than an endurance one."
                ),
                "underlying_pattern": (
                    "VINDICATED, not removed — and the 2026-08-03 entry below was WRONG to "
                    "overrule it. This entry's observation that scapular work sits in the gym "
                    "sessions rather than in the daily active-recovery templates is confirmed by "
                    "the training log (counted 2026-08-13): there are two active-recovery "
                    "templates, only one carries Scapular Wall Slide, and only the one WITHOUT "
                    "it has run since 2026-07-31. The gap this entry flagged on 2026-07-21 has "
                    "since widened rather than closed."
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
                # ─── ASSESSMENT REPLACED 2026-08-13 ──────────────────────────
                # Same treatment as the 2026-07-21 entry above: the athlete's
                # ROM observations here are UNTOUCHED, only the reasoning was
                # replaced. See the 2026-08-13 entry for the tested finding.
                # ────────────────────────────────────────────────────────────
                "likely_tissue": [
                    "SUPERSEDED 2026-08-13 — left TRAPEZIUS (upper/middle fibres and the C7-T3 "
                    "aponeurosis). See the 2026-08-13 entry.",
                    "REMOVED: 'left levator scapulae'. It inserts at the superior angle of the "
                    "scapula, outside the marked band — it cannot be the local generator.",
                    "REMOVED: 'left posterior cervical extensors/paraspinals' as the primary. "
                    "Splenius cervicis and semispinalis attach spine-to-spine with NO "
                    "shoulder-girdle connection, so stabilising the shoulder blade could not "
                    "change a stretch of them. On 2026-08-13 it did — pinning the blade "
                    "abolished the symptom at the identical neck end-range. REINSTATE IF that "
                    "blade-pinned test turns positive.",
                ],
                "mechanism": (
                    "SUPERSEDED 2026-08-13. THIS ENTRY'S OBSERVATION IS THE ONE THAT WAS RIGHT "
                    "ALL ALONG and it is worth reading before the later entries: 'flexion "
                    "tightness … localized immediately lateral to the spine' describes exactly "
                    "the band the athlete marked on an anatomy plate on 2026-08-13. The "
                    "2026-08-03 entry below then relocated it to the 'medial scapular border', "
                    "which is two finger-widths further out and is wrong. Raw observations here "
                    "beat the interpretations layered on them."
                ),
                "underlying_pattern": (
                    "SUPERSEDED 2026-08-13. The levator-scapulae link is withdrawn (see above). "
                    "This entry and the 2026-08-03 one may be describing ONE finding rather than "
                    "two: both place the symptom in the same paraspinal band, and the 2026-08-13 "
                    "testing found a single tissue that accounts for both presentations."
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
                # ─── likely_tissue AND underlying_pattern REPLACED 2026-08-13 ─
                # The four drivers below SURVIVE and are annotated in place —
                # driver (1) is now directly MEASURED rather than inferred.
                # Observations in this entry are untouched.
                # ────────────────────────────────────────────────────────────
                "likely_tissue": [
                    "SUPERSEDED 2026-08-13 — left TRAPEZIUS (upper/middle fibres and the C7-T3 "
                    "aponeurosis). See the 2026-08-13 entry.",
                    "REMOVED: 'rhomboid major/minor'. Ruled out by a protraction stretch test.",
                    "REMOVED: 'at the medial scapular border' — THE LOCATION IN THIS ENTRY IS "
                    "WRONG. On 2026-08-13 the athlete marked the area on an anatomy plate: a "
                    "vertical band ~2-4cm lateral to the spinous processes, C7/T1 to T4/T5. The "
                    "medial scapular border is two finger-widths further out. The 2026-07-31 "
                    "entry above had it right ('immediately lateral to the spine') and this "
                    "entry moved it.",
                    "REMOVED: 'levator scapulae' — inserts at the superior angle, outside the "
                    "marked band.",
                ],
                "mechanism": (
                    "FOUR CONVERGING DRIVERS, all already documented elsewhere in this profile. "
                    "ALL FOUR STAND as of 2026-08-13; driver (1) is now measured, not inferred:\n"
                    "(1) The right post-Latarjet shoulder sag shifts postural work onto the LEFT. "
                    "The tell is injury_profile.md #11 — the July 2025 rhomboid strain was on the "
                    "LEFT despite the damaged shoulder being the RIGHT — together with the 2025 "
                    "log's documented left TILT under overhead load. Cross-references finding #6; "
                    "do not double-count as a separate caution. *** MEASURED DIRECTLY "
                    "2026-08-13: prone single-arm raise, arm out at shoulder height, thumb up — "
                    "the athlete reports the LEFT side working harder than the right AT THE SAME "
                    "LIFT HEIGHT, i.e. matched for range. That is this driver, observed rather "
                    "than deduced, and it is the answer to 'why the left'. Separately the left "
                    "lifts 40cm and the right only 20cm; read the right's ceiling as the LATARJET "
                    "restricting horizontal extension plus external rotation — the exact arc a "
                    "transferred coracoid and its tendon sling limit — NOT as weakness to train "
                    "through. This does not contradict the physio's 2026-08-10 'no capsular "
                    "restriction': that was tested OVERHEAD, a different plane. ***\n"
                    "(2) Confirmed hypermobility (Beighton 6/9) means stability is muscular rather "
                    "than ligamentous, so sustained low-load holding is the worst load case — "
                    "muscle fatigues, ligament does not. Identical mechanism to the mid-back "
                    "episodes (which flare after a day of sitting, not after the sprints) and to "
                    "the 2026-07-06 left QL strain (isometric holding for the length of a walk).\n"
                    "(3) Finding #3's sitting-driven T6-T10 thoracic stiffness tilts the scapula "
                    "forward off the ribcage, leaving the retractors holding LENGTHENED all day — "
                    "a mechanically losing position.\n"
                    "(4) Desk exposure with unsupported forearms (above) is the unchanged "
                    "variable. *** REFINED 2026-08-13: the athlete switched to supported "
                    "forearms and got IMMEDIATE relief, then it recurred — which confirms the "
                    "mechanism rather than refuting it, because only ONE of two loads was "
                    "removed and head-forward was never addressed. The measurable cause is that "
                    "THE DESK IS TOO LOW: below elbow height the forearms cannot carry their own "
                    "weight without dropping and rounding the shoulders, so the reach goes down "
                    "and forward, holding the scapula protracted and depressed — which IS driver "
                    "(3)'s losing position, arriving by a second route. Set the surface at "
                    "standing elbow height measured ON the treadmill deck (the deck adds 10-15cm; "
                    "a desk set from floor-standing height is exactly one deck-height too low), "
                    "and raise the monitor by the same amount or load A is simply traded for "
                    "load B. ***"
                ),
                "underlying_pattern": (
                    "AMENDED 2026-08-13, then CORRECTED THE SAME DAY against fresh data — read "
                    "the correction, because the first pass overturned this entry wrongly.\n"
                    "WHAT IS WRONG HERE: the 'five days a week' figure. Counted from the log, "
                    "Stage 2A actually ran scapular work on 4 days in week 1, then 3, then 2, "
                    "then 2 — never five. That number came from training_plan.py rather than "
                    "from training_exercises.\n"
                    "WHAT IS RIGHT HERE, and was briefly and wrongly overturned: 'the symptom "
                    "persists THROUGH that dose'. It does. Scapular Wall Slide ran 2026-08-11 "
                    "and Face Pull ran 2026-08-12 — and 2026-08-12 is the worst day on record "
                    "(tightness 3, pain 1). The symptom peaked the day after a wall-slide "
                    "session and on the same day as face pulls. So the endurance-over-volume "
                    "reading STANDS on its substance; only its arithmetic was inflated.\n"
                    "THE ONE GENUINE OMISSION: Prone Y-Raise, last run 2026-07-24 and three "
                    "weeks stale. Wall Slide and Face Pull are both current.\n"
                    "The mechanism is nonetheless sharper than 'endurance' — see the 2026-08-13 "
                    "entry, which finds a PERFUSION pattern (sustained low-level contraction is "
                    "ischaemic; movement, face pulls and heat all relieve it) rather than a "
                    "capacity shortfall. That refines this entry rather than refuting it, and it "
                    "explains why the dose can be adequate and the symptom persist anyway: short "
                    "high-quality sets pump the tissue for minutes, against eight hours of load."
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
                "CORRECTION 3 — PARTLY RETRACTED 2026-08-13. Its FIGURE is wrong: it cited "
                "PLAN_STAGE2's five prescribed days, but the plan is not the log, and "
                "training_exercises shows 4 scapular days in week 1, then 3, then 2, then 2. "
                "Its CONCLUSION stands: scapular work does run through the symptom. Wall Slide "
                "ran 2026-08-11 and Face Pull 2026-08-12, and 2026-08-12 is the worst day on "
                "record. Prone Y-Raise is the one real omission, last run 2026-07-24. The "
                "lesson is general: never verify a dose against training_plan.py when the log "
                "is queryable — AND make sure the log you query is current. An earlier pass on "
                "2026-08-13 counted off a datastore snapshot built two days prior, concluded "
                "'0 scapular days this week', and overturned this correction on that basis. "
                "Both the 2026-08-11 and 2026-08-12 sessions were missing from that snapshot. "
                "Rebuild before counting: scripts/build_datastore.py.",
                "CONVENTION CHANGED 2026-08-13, at the athlete's direction — 'this was all guess "
                "work; what we are doing now should overwrite that as it is real planning and "
                "tests.' The append-only rule no longer applies to ASSESSMENTS: reasoning that "
                "testing has refuted is replaced in place, with a tombstone naming what was "
                "removed and what would reinstate it. OBSERVATIONS are still never overwritten — "
                "verbatim check-ins, dates, severity scores and locations stay exactly as "
                "recorded, and they are what proved the case.",
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
                "scapular_fatigue_onset_removed": (
                    "REMOVED 2026-08-10 on the athlete's direction. This finding claimed a "
                    "measured interscapular burn onset in Down Dog and carried it into the "
                    "physio brief as the dosing anchor for the scapular ask. It had no basis "
                    "as a measurement — one casual self-observation inside a 15-minute flow, "
                    "never a fresh test — and it could not be reperformed: the in-studio "
                    "retest (2026-08-10 entry below) held Down Dog past FOUR MINUTES with no "
                    "interscapular burn, the physio judging the arms would fail before the "
                    "shoulder blades. Removed outright rather than left as superseded so no "
                    "future reader treats it as a threshold; this tombstone is the recorded, "
                    "deliberate exception to the log's append-only convention."
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
            "status": "Longstanding — first recorded 2026-08-07; trend unobserved until now",
            "region": "Right anterior chest / front of the shoulder — upper right, just medial to the right-shoulder surgical scar",
            "title":  "Right Pec-Minor-Region Cramp / Lock-Out (Position-Specific, Painless)",

            "mechanism": (
                "LONG-STANDING, and reliably reproduced by ONE specific position: hands "
                "together in a prayer position in front of the chest, but with the fingers "
                "pointing FORWARD — away from the body — rather than up, and the forearms "
                "angled ~45° upward toward the face rather than sitting horizontal at 90° "
                "from the elbows. In that position a strong burning, 'muscle locking out' "
                "sensation builds in the upper right chest — just before the surgical scar, "
                "connecting toward the shoulder — 'almost like a cramp'. No pain at any "
                "point, and the identical position on the left produces nothing. "
                "Chronicity, per the athlete: present since the years AFTER the shoulder "
                "surgeries and well BEFORE the 2025/2026 back/hip injury era — but attention "
                "to it is recent, so whether it has changed over that span is unknown; this "
                "entry is the baseline for observing trend, not the onset. Documented "
                "negative: it has NEVER appeared during pressing — the sensation coexisted "
                "with past eras of regular, active Incline DB pressing without ever showing "
                "up in the lift."
            ),

            "symptoms": {
                "location": (
                    "Upper right chest, just medial to the right-shoulder surgical scar, "
                    "extending toward the shoulder. The athlete's own tissue read is PEC "
                    "MINOR — recorded as self-identified, not diagnosed (see assessment)."
                ),
                "character":      "Strong burn + 'muscle locking out', cramp-like — a sensation, not pain",
                "provoked_by":    ["Prayer hands at the chest, fingers forward, forearms ~45° up toward the face — reliably, right side only"],
                "painful_with":   None,
                "laterality":     "RIGHT ONLY — the identical position on the left is completely clear",
                "neural":         "None reported — no numbness, tingling, or radiation into the arm",
            },

            "assessment": {
                "likely_tissue": [
                    "Right pectoralis minor — the athlete's own read, and anatomically plausible: "
                    "the position combines shoulder flexion + horizontal adduction + an isometric "
                    "palm press, i.e. pec activation in a SHORTENED position, and pec minor is "
                    "also a scapular protractor (cramping in a shortened position under active "
                    "contraction is classic contractile behaviour). A HYPOTHESIS, not a diagnosis.",
                    "The region is not anatomically standard tissue: finding #6's Latarjet "
                    "transferred the coracoid — pec minor's insertion — so the immediate area "
                    "also contains the conjoint-tendon transfer site, pec major's upper fibres, "
                    "and surgical scar tissue. Tissue identification belongs to the physio.",
                ],
                "mechanism": (
                    "A cramp/lock under ACTIVE contraction in a shortened position, with no "
                    "report from any passive or loaded context to date, reads as CONTRACTILE "
                    "rather than positional — the same framing finding #4's "
                    "additional_evidence_2026_08_05 established for the hip: position alone "
                    "does not trigger it; contraction in a specific configuration does."
                ),
                "underlying_pattern": (
                    "FIRST ANTERIOR-CHEST SIGNAL RECORDED on the post-Latarjet shoulder — "
                    "everything previously recorded for that shoulder (sag, eccentric-control "
                    "weakness, left tilt under overhead load) is posterior/scapular. The "
                    "chronicity DECOUPLES it from the current injury cascade: it predates the "
                    "2025/2026 back/hip era entirely, so it is a long-standing feature, not a "
                    "development of this block, and it does NOT bear on the Stage 2 shoulder "
                    "exit criterion. Onset in the years after the Latarjet is CONSISTENT "
                    "with — not proof of — the surgically altered pec minor insertion being "
                    "involved; record that as consistency, never causation. Chronic + "
                    "painless + pressing-tolerant together support the benign contractile "
                    "reading. Right-only laterality is consistent with the documented "
                    "right-side asymmetry under ACTIVE/loaded conditions (findings #1, #2, "
                    "#4), and per the 2026-08-05 baseline's no_passive_lateral_asymmetry "
                    "note, its absence in passive stretching would say nothing either way. "
                    "Direct new evidence on the physio brief's §8 open question: a "
                    "right-sided anterior finding supports the 'left load is downstream of a "
                    "right-side deficit' reading."
                ),
            },

            "plan": [
                "No self-directed exercise or stretching changes — in particular NO pec "
                "stretching: physio brief §11 already records that post-Latarjet a capsular "
                "restriction changes the prescription from 'stretch it' to 'do not', and the "
                "tissue here is not yet identified.",
                "Raise with the physiotherapist at the 2026-08-16 Day 28 reassessment "
                "(physio brief §13) — the position is easy to demonstrate in the room.",
                "Do not deliberately re-provoke between now and then; note any appearance in "
                "OTHER positions, or during the block's pressing work, if it happens on its own.",
            ],

            "escalation_criteria": [
                "Any PAIN from the position or the region — the current presentation is "
                "explicitly pain-free, so pain is a change of kind, not degree",
                "Any neural signs — numbness, tingling, or radiation into the arm",
                "Any instability sensation in the right shoulder (finding #6)",
                "Appearance during pressing work — NOT a live expectation (the documented "
                "negative history spans past eras of active Incline DB pressing with zero "
                "occurrences), so showing up there would be a BREAK in a long-established "
                "pattern, which is exactly what makes it worth escalating",
                "Any strengthening or easier triggering now that attention is on it — trend "
                "was never observed before this entry, so this record is the baseline",
                "Spreading to new positions or to the left side",
            ],

            "notes": [
                "Cross-references finding #6 (addendum additional_evidence_2026_08_07, added "
                "the same day): the scar is the right-shoulder surgery scar, and the "
                "sensation sits on surgically altered anatomy — which is exactly why the "
                "plan is identification-first rather than self-treatment.",
                "Painless + position-specific + reliably reproducible makes this a candidate "
                "CLINICAL RE-CHECK, not just a symptom: if the physio names the tissue, the "
                "position itself becomes a cheap repeatable test.",
            ],
        },
        {
            "date":   "2026-08-10",
            "status": "Recorded — not a symptom; the physiotherapist's answers to the Day-28 brief",
            "region": "Multiple — interscapular, right shoulder/anterior chest, proximal hamstring, anterior hip, hips/lumbar",
            "title":  "Physiotherapist Responses — All 13 Brief Questions Answered (Ahead of the 2026-08-16 Reassessment)",

            "mechanism": (
                "Not an injury entry. The physiotherapist answered every question in "
                "docs/training/physio_brief_2026-08-16.md, six days ahead of the Day 28 "
                "reassessment, including an in-studio retest of the Down Dog fatigue "
                "measurement. The stage-gate decisions themselves — Stage 2B vs. extending "
                "2A, the running introduction — were NOT part of this response and remain "
                "for the 2026-08-16 sitting. Recorded here because several answers correct "
                "or close earlier entries in this log; per the append-only convention those "
                "corrections live in this entry, not in the originals."
            ),

            "findings": {
                "scapular_holds_approved": (
                    "Brief §1 APPROVED: strengthening the interscapular muscles is "
                    "recommended. Two additions from the physio: (1) the chair's side "
                    "forearm supports have ALREADY taken away most of the pressure on the "
                    "shoulder blades — the §6 ergonomic change is doing the load-bearing "
                    "work; (2) the residual pressure is a ROUNDING pressure, and any "
                    "exercise that strengthens those muscles will help it. 30-second hard "
                    "holds are explicitly fine — 'patient has strength enough to do this.' "
                    "The physio's reframe of the whole finding: the issue is STILLNESS and "
                    "STIFFNESS, not weakness. That narrows the 2026-08-03 entry's "
                    "endurance-gap hypothesis: strengthening is still the endorsed tool, "
                    "but the driver is the stillness exposure, not a capacity deficit."
                ),
                "fatigue_onset_claim_removed": (
                    "MEASUREMENT CORRECTION: the athlete was underestimating his Down Dog "
                    "time. Retested in the studio: 4+ MINUTES without interscapular burn, "
                    "and the physio's judgement was that the elbows and arms would fail "
                    "before the shoulder blades. Verdict: no issue in the shoulder "
                    "blades — they can be trained NORMALLY, TO FAILURE. On the athlete's "
                    "direction the original 50-60s claim is REMOVED from the 2026-08-05 "
                    "entry outright (tombstoned in place), not merely superseded — there "
                    "was no basis for it and it could not be reperformed. It came from "
                    "one self-observed hold inside a 15-minute flow, not a fresh maximal "
                    "test — the same instrument lesson as the three-baseline-mornings "
                    "rule: one casual self-observation is not a measurement."
                ),
                "left_vs_right_answered": (
                    "Brief §8 ANSWERED: the left is overcompensating for the right, and "
                    "the right is WEAKER than the left. Train BOTH — do not isolate one "
                    "side; both need to be strengthened. This settles which side gets "
                    "programmed in the next block: both, with the deficit understood to "
                    "sit on the right."
                ),
                "hamstring_and_anterior_hip": (
                    "Proximal hamstring: yes, isometric holds would help, combined with "
                    "increased movement and high-rep strengthening to activate the "
                    "movement. The existing Ischial Tuberosity Hamstring Release "
                    "(sustained pressure, pre-session Days 3/10) is confirmed as right "
                    "for that site. NEW RECOMMENDATION: sustained-pressure testing for "
                    "the FRONT of the hip as well, to release the pressure from sitting — "
                    "a candidate for the pre-session release block at the next block "
                    "build."
                ),
                "organising_claim_confirmed": (
                    "Brief §12's one-thing-to-check CONFIRMED: lack of flexibility in the "
                    "hips is driving the lower back to 'fall inwards and be stuck in this "
                    "position' (physio's words). The Cluster A organising claim — the "
                    "lumbar rounding is the compensation, the pelvis that will not rotate "
                    "forward is the problem — now carries the physiotherapist's "
                    "endorsement, not just the athlete's own read."
                ),
                "anterior_hip_sensation_cleared": (
                    "The butterfly-fold anterior-hip sensation is a NORMAL STRETCH "
                    "SENSATION — 'exactly where you would expect the stretch to start for "
                    "short hip flexors.' Not bone, not anterior compression. This "
                    "adjudicates the question that was blocking the top of the "
                    "flexibility battery (the stop-and-record rule on the first test was "
                    "written pending exactly this answer)."
                ),
                "horse_and_cossack_cleared": (
                    "Horse stance and Cossack squat can BOTH come off deferral — 'patient "
                    "can comfortably do both.' Gap to note honestly: the brief also asked "
                    "WITH WHAT ROTATION CUE, and the response does not name one — the "
                    "external-rotation cue recorded in the cluster documents stands until "
                    "the physio says otherwise. Lifting the deferral in "
                    "cluster_a_mechanics is a code change that lands with the block "
                    "build, not with this record."
                ),
                "thresholds_confirmed_no_capsular_issue": (
                    "The 25-point wide-gap threshold is 'a good estimate — continue to "
                    "test and re-evaluate later.' And the overhead-reach question closes "
                    "cleanly: the patient can reach fully overhead, continue to stretch "
                    "as normal, NO JOINT CAPSULE ISSUES — the post-Latarjet capsular "
                    "worry that §11 flagged (which would have turned 'stretch it' into "
                    "'do not') does not apply to overhead reach."
                ),
                "pec_cramp_diagnosed": (
                    "The 2026-08-07 entry's question is ANSWERED. Diagnosis: POSITIONAL "
                    "ISCHEMIC CRAMP / SCAR ADHESION LOCKOUT — the shortened tissue fires "
                    "hard in a shortened range, catches on dense surgical scar tissue, "
                    "and briefly cuts off blood flow, producing the deep, intense "
                    "lock-out burn without structural pain. ENTIRELY SAFE to address. "
                    "Release and active work are expected to have a BETTER IMPACT than "
                    "stretching — stretching is permitted, just the weaker tool here "
                    "(athlete's clarification of the physio's intent, 2026-08-10). "
                    "Recommended: (1) targeted scar & pectoralis minor self-myofascial "
                    "release; (2) subscapularis / anterior-wall active reciprocation with "
                    "isometric holds — active end-range isometric holds and control. "
                    "Physio's words: these 'would greatly improve the situation.'"
                ),
                "specialization_trial_endorsed": (
                    "Arms-only is a good trial. The physio adds a design point: trial "
                    "not just fatigue but the patient's WANT and ABILITY to train every "
                    "day — adherence and appetite are part of what the trial measures. "
                    "Reconvene after the trial. Timing unchanged: after the 10 km on "
                    "2026-10-11."
                ),
                "ferritin_out_of_scope": (
                    "Unanswerable from the physio side — remains open with the GP. The "
                    "physio's overall view of the path: 'the patient just needs regular "
                    "targeted training to get back to clean active training.'"
                ),
                "athlete_decisions_same_day": (
                    "The athlete resolved the five §15 follow-ups himself the same day. "
                    "What remains for 2026-08-16 is NOT an appointment — it is "
                    "PLAN_STAGE2[28], the plan's own self-administered test session, "
                    "whose data then goes to the physio for the format-free sign-off "
                    "stage_2_exit_criteria requires (remote is fine; the brief was "
                    "answered remotely). The decisions: (1) the "
                    "pec techniques are built IN-HOUSE from the Cluster D source "
                    "documents and the Baar annex rather than waiting for a demo — "
                    "docs/training/release_protocols_2026-08-10.md, a pre-registered "
                    "two-week hypothesis test with the standardised prayer position as "
                    "its instrument; (2) the anterior-hip pressure work is a second "
                    "pre-registered hypothesis test in the same document, sequenced "
                    "AFTER the battery baseline so it cannot contaminate the tilt "
                    "measurement; (3) the ER cue for horse stance and Cossack is "
                    "CONFIRMED by the athlete ('active external rotation of hips is "
                    "correct') — noting the standing tension with Key Rule 7's "
                    "neutral-rotation cue for active right hip flexion: if the Coxa "
                    "Saltans click appears under either movement, the cue question "
                    "REOPENS; (4) scapular programming trials ONE arm first and returns "
                    "with data — recorded as right-biased emphasis, the interventional "
                    "arm, since the physio named the right as weaker (flip at the block "
                    "build if the intended arm was symmetric); (5) thoracic mobility "
                    "stays as-is — the movement-break protocol already covers the "
                    "stillness half."
                ),
            },

            "plan": [
                "The approved prescriptions get ENCODED AT THE NEXT BLOCK BUILD, after "
                "the 2026-08-16 Day 28 reassessment settles the stage-gate decisions: "
                "scapular strengthening on both sides (holds may go to failure), "
                "proximal-hamstring isometrics plus high-rep activation work, "
                "anterior-hip sustained-pressure testing in the release block, and the "
                "two pec interventions — every new movement name run through "
                "rules.check_movement and mapped in EXERCISE_MOVEMENT_WEIGHT / "
                "EXERCISE_BODY_REGION per the integration protocol.",
                "The pec release + active-reciprocation work is cleared for self-directed "
                "use by the physio's explicit answer — the one exception to this log's "
                "usual no-self-directed-changes rule. Stretching the region is permitted "
                "too; release and isometrics are simply expected to work better.",
                "The removed burn-onset claim was scrubbed the same day from everywhere "
                "it had propagated as a threshold: services/yoga.py's rationale and "
                "retest strings, tests/test_yoga.py, docs/training/Yoga_Library.md and "
                "the physio brief. Hold DURATIONS are unchanged everywhere — lengthening "
                "the scapular holds is still a block-build prescription change, now with "
                "the approval in hand.",
                "Code consequences still open (each changes behaviour and needs its own "
                "pass): the horse/Cossack deferrals in cluster_a_mechanics — movement "
                "AND cue are both cleared now, but the deferral holds until after the "
                "2026-08-16 sitting regardless, because the exit criterion judged there "
                "is Coxa-Saltans frequency under loaded squats and two new ER-cued "
                "squats inside the assessment window would confound it; and the "
                "battery's stop-and-record wording for the anterior-hip sensation.",
            ],

            "notes": [
                "Corrections landing with this entry: the 2026-08-05 burn-onset claim is "
                "REMOVED at the athlete's direction — tombstoned in place rather than "
                "left as superseded, a recorded exception to the append-only convention, "
                "because a baseless number left standing reads as a threshold. The "
                "2026-08-07 pec entry's raise-with-physio plan is fulfilled and that "
                "entry stands as written.",
                "The physio response arrived six days EARLY — nothing here is the Day 28 "
                "reassessment itself. Stage 2B vs. extending 2A, the running "
                "introduction, and the formal exit-criteria evaluation all still land on "
                "2026-08-16.",
            ],
        },
        {
            "date":   "2026-08-13",
            "status": "Tested — supersedes the assessments in the 2026-07-21, 2026-07-31 and 2026-08-03 entries",
            "region": "Left paraspinal band, C7/T1 to T4/T5 (~2-4cm lateral to the spinous processes)",
            "title":  "Interscapular Symptom SOLVED to a Tissue — Left Trapezius, Position-Loaded, Perfusion-Limited",

            "mechanism": (
                "The athlete marked the area on a posterior anatomy plate, then ran a series of "
                "discriminating tests. This entry replaces guesswork with measurement and is the "
                "single place the finding lives; the three earlier entries carry tombstones "
                "pointing here. IT IS A LOAD PROBLEM, NOT AN INJURY: there has never been an "
                "incident, pain has been 0/10 for a month, and nothing reproduces it except "
                "sustained position. The absence of a singular moment is not a puzzle — it is the "
                "diagnosis. A damaged tissue has a moment; an overworked one accumulates.\n"
                "WHY THIS REGION, WHY NOW: the driver is not the lumbar injury and not the "
                "training block (onset 2026-07-16, four days BEFORE Stage 2A). At Beighton 6/9 "
                "stability is muscular everywhere, so whichever region holds longest fails first. "
                "The lumbar went first because sitting loads it hardest; it has since improved "
                "markedly (2026-07-24: 'first morning in a while I woke up with no stiffness in "
                "my back or hips') and the next region still holding all day is the one now "
                "complaining. Same body, same laxity, same failure mode, different region because "
                "the exposure moved."
            ),

            "symptoms": {
                "location": (
                    "LEFT, a vertical band ~2-4cm lateral to the spinous processes running C7/T1 "
                    "to about T4/T5. NOT the medial scapular border, which is two finger-widths "
                    "further out and is what the 2026-08-03 entry wrongly recorded. The "
                    "2026-07-31 entry's 'immediately lateral to the spine' was correct."
                ),
                "painful_with": [
                    "Sustained head-forward desk posture — the dominant exposure",
                    "Reaching the neck down and to the right (contralateral side-bend)",
                    "Shrugging while in that neck position — worse during, WORSE AGAIN AFTER RELEASE",
                    "Standing with the arms dangling; treadmill-desk walking with hands fixed",
                    "Holding a phone unsupported, especially while walking",
                ],
                "pain_free_with": [
                    "Natural-pace walking",
                    "Face pulls — acute relief, observed the week of 2026-08-03",
                    "Heat applied before bed — abolished it entirely ('couldn't feel it')",
                    "A 10km weekend hike — no symptoms at all",
                ],
                "neural":   "None — no arm symptoms, numbness or tingling",
                "severity": (
                    "Tightness 1-3/10 throughout. Pain had been 0/10 on every check-in since "
                    "2026-07-23 — and 2026-08-12 broke that at PAIN 1/10, tightness 3, the worst "
                    "day on record. Still low, but it is the first movement off zero in three "
                    "weeks and is the number to watch. That day's check-in, verbatim: 'Left side "
                    "between the shoulder blade and the spine, was ok in the morning but now "
                    "tired after working until 2pm' — sensation tags Dull Ache and Mild "
                    "Tiredness. Note it says the morning was OK, which is contemporaneous and "
                    "more reliable than the same-day recollection of being sore before the walk."
                ),
            },

            "assessment": {
                "likely_tissue": [
                    "LEFT TRAPEZIUS — upper and middle fibres and the C7-T3 aponeurosis they "
                    "converge on. The only candidate that (i) lies in the marked band, (ii) "
                    "lengthens as the neck goes forward and away, AND (iii) is loaded by "
                    "unsupported arm weight. The athlete named it himself on 2026-07-31 before "
                    "any of this: 'still tight in TRAPS left side down my spine when I put my "
                    "head foreward'.",
                    "RULED OUT — rhomboid: a protraction stretch with the neck neutral lengthens "
                    "it directly and does not reproduce the symptom.",
                    "RULED OUT — levator scapulae as the local generator: it inserts at the "
                    "superior angle, outside the marked band. It may still explain the "
                    "neck-base migration.",
                    "RULED OUT — splenius cervicis / semispinalis: they attach spine-to-spine "
                    "with no shoulder-girdle connection, so pinning the shoulder blade could not "
                    "change a stretch of them. It abolished the symptom at identical neck "
                    "end-range. THIS IS THE DECISIVE TEST.",
                    "RULED OUT as primary — thoracic facet / deep rotators: rotation toward the "
                    "sore side does not reproduce it.",
                ],
                "mechanism": (
                    "PERFUSION, NOT CAPACITY — this supersedes the 2026-08-03 entry's 'endurance "
                    "gap'. Sustained low-level contraction occludes flow through the muscle; "
                    "movement pumps it. That is why a 20-minute walk relieves it and eight hours "
                    "of holding does not, and it is a sharper claim than a capacity shortfall.\n"
                    "THE SHRUG TEST IS THE TELL: head down-and-right, then shrug and hold 20-30s "
                    "— worse during, and WORSE AGAIN AFTER RELEASE, in the marked band. A "
                    "post-release increase is reperfusion. This is the physiotherapist's own "
                    "diagnosed mechanism from 2026-08-10, applied to a different muscle: "
                    "'positional ischemic cramp — shortened tissue firing hard in a shortened "
                    "range … briefly cutting off blood flow; no structural pain.'\n"
                    "24-HOUR COURSE, 2026-08-12/13, seven transitions all one direction: sore "
                    "after sleep (stillness) -> walk, not clearly worse -> CONSIDERABLY WORSE "
                    "1-3pm at the desk -> gym at 3pm, tolerated, then migrated to mid-back -> "
                    "HEAT ABOLISHED IT before bed -> sore again at 4am (stillness) -> resolved "
                    "this morning on getting up and moving. Stillness and holding worsen it; "
                    "movement and heat relieve it."
                ),
                "underlying_pattern": (
                    "THREE POSITIONS, THREE ROUTES TO THE SAME TISSUE (athlete, 2026-08-13) — "
                    "which is why changing between them never helped, and why the 2026-08-03 "
                    "entry's reading of 'sitting, standing AND treadmill alike' as proof of "
                    "DURATION rather than posture is wrong. Sitting drives head-forward. "
                    "Standing lets the arms dangle, which is unsupported arm weight at its "
                    "MAXIMUM — so for this problem a standing desk is WORSE than sitting unless "
                    "the arms are supported, inverting the usual advice. The treadmill desk "
                    "fixes the hands on a keyboard while the legs move, so the girdle cancels "
                    "every footfall: continuous low-load stabilisation, the worst case at "
                    "Beighton 6/9.\n"
                    "WHY THE LEFT: driver (1) of the 2026-08-03 entry, now measured rather than "
                    "inferred — at matched lift height the left works harder than the right. "
                    "The right post-Latarjet side is not carrying its share, and the left has "
                    "been absorbing it all day, in all three positions."
                ),
                "tendon_question": (
                    "The athlete asked whether the tissue is tendon, and whether that explains "
                    "slow resolution. Honest answer: LESS LIKELY, NOT EXCLUDED — and an earlier "
                    "reading in this conversation OVERCLAIMED, which he correctly challenged.\n"
                    "WHAT DOES NOT DISCRIMINATE: heat helping (a non-specific analgesic that "
                    "relieves tendinopathy too, and symptomatic tendons often show "
                    "neovascularisation rather than ischaemia); morning stiffness easing with "
                    "movement (that IS the classic tendinopathy history, not evidence against "
                    "it); and insidious onset with no incident (also typical of tendinopathy).\n"
                    "WHAT ACTUALLY ARGUES AGAINST IT: (a) loading the C7-T3 sheet in NEUTRAL — "
                    "prone single-arm retraction — leaves the ache present but UNCHANGED, 'no "
                    "major change during or after'. Tendinopathy escalates under load. (b) Pain "
                    "0/10 for a month with tightness as the dominant descriptor; tendinopathy is "
                    "a pain condition. (c) The dissociation: the tissue that DID escalate was "
                    "upper trapezius loaded in the provocative position, not the sheet loaded in "
                    "neutral.\n"
                    "STILL OPEN, and cheap to close: a three-round retraction hold a minute "
                    "apart (round 3 worse than round 1 is the specific tendinopathy signal — the "
                    "athlete may have run only one round), and palpation for a FOCAL coin-sized "
                    "tender point reproducing the familiar symptom versus broad even tenderness.\n"
                    "IT DOES NOT CHANGE THE PRESCRIPTION EITHER WAY, which is why the "
                    "uncertainty is tolerable: perfusion wants a pump, an aponeurotic component "
                    "wants the saturating dose, and both are brief light ramped isometrics "
                    "repeated through the day. See the Baar annex note in `plan` below."
                ),
                "training_is_exonerated": (
                    "Established from the log on 2026-08-13, not by argument. SIX interscapular "
                    "reports, six WEEKDAYS; three weekend check-ins, three clean (2026-08-08 "
                    "reads tightness 1 but the athlete himself wrote 'not between the shoulders "
                    "but lower'). Training AU predicts nothing: 290 AU on 2026-07-24 produced "
                    "the no-stiffness morning, 402 AU on 2026-07-30 came with tightness 3, 0 AU "
                    "on 2026-07-25 with 0. A 10km weekend hike — more exertion, arm swing and "
                    "ventilation than the 3x3 interval walk that preceded a bad day — produced "
                    "nothing. And the exception seals it: 2026-08-03 is a MONDAY reading 'after "
                    "sitting alot yesterday', a Sunday. It is not work, it is the POSITION, "
                    "wherever it occurs.\n"
                    "CONSEQUENCE FOR THE BLOCK: running is NOT implicated. Stage 2B introduces "
                    "running for the 10km on 2026-10-11 and this symptom does not constrain it."
                ),
            },

            "plan": [
                "RAISE THE DESK — the athlete reports it is too LOW, which is worse than too "
                "high. Target the surface at standing elbow height measured ON the treadmill "
                "deck (the deck adds 10-15cm), upper arm vertical, shoulders relaxed, elbow ~90 "
                "degrees. RAISE THE MONITOR BY THE SAME AMOUNT, or arm-weight load is simply "
                "traded for head-forward load and a real fix will read as a failed one. "
                "Self-directed; the 2026-08-03 entry already records desk changes as needing no "
                "sign-off.",
                "Phone: raise it to chest/eye level, brace the holding elbow into the ribs or "
                "rest that forearm across the chest, increase text size, and not while walking. "
                "A SECONDARY exposure — the athlete is normally lying down with forearms and "
                "neck supported (the unloaded position, found by feel) and under 30 min/day is "
                "unsupported — but potent while it runs.",
                "Movement breaks BEFORE onset, not after. The proven dose is already in the "
                "2026-08-03 entry and was simply mistimed.",
                "HEAT is now a tool as well as evidence — it abolished the symptom on 2026-08-12 "
                "and does so for the right reason.",
                "REINSTATE PRONE Y-RAISE — last run 2026-07-24 and the one scapular item that "
                "has genuinely lapsed. Scapular Wall Slide (2026-08-11) and Face Pull "
                "(2026-08-12) are both current, so this is a single gap, not the collapse an "
                "earlier reading of stale data claimed.",
                "LOAD IN NEUTRAL, NEVER IN THE PROVOCATIVE POSITION — neutral retraction is "
                "asymptomatic, the shrug in the head-down-and-right position is not.",
                "TENDON LOADING, recorded here for the SHOULDER work at the athlete's direction "
                "(2026-08-13) rather than actioned now: Input_files/baar_tendon_annex.md §7.5 "
                "(brief light isometrics as a decongestant — written for precisely what the "
                "shrug test demonstrated), §2.2/§6.3 (connective-tissue signal saturates at ~10 "
                "min and resets after 6-8h, so a 10-minute routine is a COMPLETE dose and fits "
                "INSIDE the working day rather than competing with training), §4 (ramp 3-5s in "
                "and out, 'tension not max' at ~50 percent effort, overcoming over yielding). "
                "DOSE AND FREQUENCY ARE DELIBERATELY NOT WRITTEN HERE — the annex forbids taking "
                "them directly from itself; that belongs to the Prescription layer at the block "
                "build. Nothing new needs approving: Stage 2B's isometric-hold direction is "
                "already physio-confirmed and this only points it at this region.",
                "Right side: read the 20cm prone-raise ceiling as a Latarjet restriction in that "
                "plane, NOT as weakness to train through.",
            ],

            "escalation_criteria": [
                "Any radiating pain into the arm, numbness, or tingling",
                "Sharp pain or any acute onset, as opposed to the current dull gradual ache",
                "Headache, dizziness, or any symptom suggesting cervical involvement",
                "Pain rising above the flat 0/10, or tightness trending above 3/10",
                "No improvement after the desk height change → the load model is wrong and the "
                "tendon question reopens",
            ],

            "notes": [
                "CONVENTION: this entry supersedes the ASSESSMENTS in the 2026-07-21, 2026-07-31 "
                "and 2026-08-03 entries, at the athlete's direction ('this was all guess work'). "
                "Every observation in those entries is untouched — and the observations are what "
                "proved the case, twice over: the 2026-07-31 'immediately lateral to the spine' "
                "was the correct location all along, and the 2026-07-21 note about scapular work "
                "missing from the daily templates was correct and was wrongly overruled.",
                "UNRECORDED OBSERVATION RECOVERED — the athlete noticed the week of 2026-08-03 "
                "that it felt better AFTER face pulls than before. His notes for that period "
                "were lost, so this entry is its only record. Face pulls are rhythmic contraction "
                "of the congested group, i.e. the same pump as walking applied directly.",
                "This dissolves an apparent contradiction rather than adding one: acute relief "
                "from face pulls and an eight-hour daily load answer different questions. The "
                "scapular work was never failing — it simply was not aimed at the driver.",
                "METHOD NOTE, and it cost a wrong conclusion the same day it was written. "
                "'Five days a week of scapular work' was taken from training_plan.py and is "
                "false in the log (4/3/2/2). But the first attempt to correct it counted off a "
                "datastore snapshot built two days earlier, reported '0 scapular days this "
                "week', and used that to overturn the 2026-08-03 entry's 'the symptom persists "
                "through the dose' — which is CORRECT and should not have been overturned. The "
                "missing rows were 2026-08-11 (Scapular Wall Slide) and 2026-08-12 (Face Pull), "
                "i.e. the two most recent sessions, and 2026-08-12 is the worst symptom day on "
                "record. So: verify a dose against training_exercises rather than the plan, AND "
                "rebuild the snapshot first (scripts/build_datastore.py). A stale local read "
                "does not look like an error, it looks like absent data — the exact failure "
                "mode the offline datastore was introduced to prevent, arriving by the other "
                "door.",
                "The physiotherapist is not available on demand — possibly not until September or "
                "later (athlete, 2026-08-13). Everything in `plan` above is self-directed and "
                "already cleared; none of it waits on a visit.",
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
