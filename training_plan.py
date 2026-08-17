"""
training_plan.py — 14-Day Progressive Bodyweight Rehab Plan.

Generated for: Patient — Stage 1 Rehab
MRI basis: L5/S1 activated osteochondrosis + retrolisthesis + right dorsolateral
disc protrusion (moderate right foraminal stenosis). L3/4 and L4/5 flat protrusions
left dorsolateral with covered annulus tears. Downstream: psoas/hip flexor
hypertonicity amplifying L5/S1 compression.

Biomechanical profile integrated (from patient_profile.py):
  1. Upper glute/hip crest chronic tightness — overactive glute medius + piriformis
     MUST inhibit before activating. Pre-session release precedes every day.
  2. Right posterior hip capsule restriction — causes standing hinge crack / ischial release
  3. Lumbar + thoracic facet compression — addressed by thoracic extension + rotation work
  4. Right Coxa Saltans (iliopsoas snap at 90°) — all right hip flexion cues use neutral/IR
  5. Wide-stance rotational cracks — hip capsule + pubic symphysis + facet end-range
  Primary imbalance: under-firing glute max/deep core → upper glutes over-grip for stability.
  Sequence: INHIBIT overactive structures FIRST, then ACTIVATE underactive ones.

EQUIPMENT: Bodyweight only. Household items permitted (rolled towel, chair, book, wall).
ACWR ceiling: 1.2 (Stage 1). Session RPE ceiling: 7/10.

Exercise type keys:
  "reps"       — counted repetitions (user counts)
  "hold"       — single timed isometric hold per set
  "hold_reps"  — X reps each with Y-second hold (e.g., McGill Curl-Up)
  "duration"   — continuous timed activity (walking, breathing)

# DETERMINISTIC-ONLY: all prescriptions derived from MRI findings and evidence-based
# lumbar disc rehabilitation protocols (McGill, Danneels, Hides) + biomechanical profile.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
#  Helper
# ─────────────────────────────────────────────────────────────────────────────

def _ex(
    name: str,
    ex_type: str,
    mechanics: str,
    biomechanical_focus: str,
    progression: str,
    regression: str,
    sets: int = 3,
    reps: int | None = None,
    hold_seconds: int | None = None,
    reps_in_set: int | None = None,
    tempo: str | None = None,
    rest_seconds: int = 60,
    duration_minutes: int | None = None,
    laterality: str = "bilateral",
    warning: str | None = None,
    weight_kg: float | None = None,
    equipment_type: str | None = None,
    band_tier: str | None = None,
    rep_min: int | None = None,
    rep_max: int | None = None,
    increment_size: float = 2.5,
    increment_unit: str = "kg",
    warmup: bool = False,
) -> dict:
    return {
        "name": name,
        "type": ex_type,
        "laterality": laterality,
        "mechanics": mechanics,
        "sets": sets,
        "reps": reps,
        "hold_seconds": hold_seconds,
        "reps_in_set": reps_in_set,
        "tempo": tempo,
        "rest_seconds": rest_seconds,
        "duration_minutes": duration_minutes,
        "biomechanical_focus": biomechanical_focus,
        "progression": progression,
        "regression": regression,
        "warning": warning,
        "weight_kg": weight_kg,
        "equipment_type": equipment_type,
        "band_tier": band_tier,
        # Double-progression rep range (services/engine.py::double_progression) —
        # None for exercises that don't auto-progress (holds, mobility, bodyweight).
        "rep_min": rep_min,
        "rep_max": rep_max,
        # Per-exercise weight-stepper increment. Most equipment is a flat 2.5kg
        # plate/dumbbell jump; some machines (Face Pull, Pallof Press) are
        # calibrated in their own arbitrary "unit" scale, not kg — flagged via
        # increment_unit="unit" until the real kg-per-unit conversion is measured.
        "increment_size": increment_size,
        "increment_unit": increment_unit,
        # RAMP SET. True marks this whole exercise as preparation, not work:
        # every set it logs carries is_warmup, which weekly tonnage and every
        # 1RM estimate then exclude (services/sessions.py::is_working_set).
        #
        # A ramp is authored as its OWN exercise sitting immediately before the
        # lift it prepares, rather than as the first N sets of that lift. Its
        # weight is a different number from the working weight, and the guided
        # flow carries one weight and one stepper per exercise — folding both
        # into one entry would need a per-set weight machine for the sake of a
        # single set. As separate entries the athlete also SEES the ramp in the
        # session timeline, which is the point of the phase-2 change.
        "warmup": warmup,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Biomechanical Profile Release Exercises
#  Defined once, inserted at the START of each session per the assignment plan.
#  Sequence matters: inhibit overactive → then activate underactive.
# ─────────────────────────────────────────────────────────────────────────────

UPPER_GLUTE_RELEASE = _ex(
    name="Upper Glute / TFL Self-Release",
    ex_type="hold",
    laterality="bilateral",
    sets=2, hold_seconds=90, rest_seconds=30,
    mechanics=(
        "Stand side-on to a wall, 10–15 cm away. "
        "Press the UPPER outer hip (the shelf just below the hip crest — not the side of the thigh) "
        "directly into the wall corner. Adjust until you find the exact area of grip or tightness. "
        "Hold sustained pressure 90 seconds — allow tissue to soften, do not fight it. "
        "You will feel a gradual release or warmth. "
        "RIGHT side will feel significantly tighter — spend extra time. "
        "Alternative: lie on your side and use your OWN fist to apply sustained pressure to the area."
    ),
    biomechanical_focus=(
        "Autogenic inhibition of overactive glute medius + TFL — the chronic gripping pattern "
        "that is the primary source of joint compression in your biomechanical profile. Sustained "
        "pressure triggers the Golgi tendon organ reflex, temporarily reducing resting tone. "
        "Must precede any glute activation work — if done after, the overactive fibres compete."
    ),
    progression="Release felt within 60s → maintain pressure and add 5 slow hip circles.",
    regression="Wall pressure too intense → apply fist pressure while lying on your side.",
)

RIGHT_HIP_CAPSULE = _ex(
    name="Right Posterior Hip Capsule Stretch",
    ex_type="hold",
    laterality="unilateral",
    sets=3, hold_seconds=60, rest_seconds=45,
    mechanics=(
        "Lie on your back. Pull your RIGHT knee DIAGONALLY toward your LEFT shoulder. "
        "This is NOT a standard knee-to-chest — it must cross the midline. "
        "Use both hands behind the thigh. "
        "You should feel a deep stretch inside the BACK of the RIGHT hip joint, not the outer hip. "
        "If feeling it in the outer hip (TFL/IT band area): pull the knee more toward the opposite shoulder. "
        "Add gentle internal rotation of the right thigh (roll slightly inward) to intensify. "
        "RIGHT SIDE ONLY — do not mirror on the left. Left posterior capsule is not restricted."
    ),
    biomechanical_focus=(
        "RIGHT posterior hip capsule release — the tight capsule identified as the cause of the "
        "standing hinge crack and the resistance felt during single-leg RDL on the right. "
        "Also reduces the compressive force on the right L5/S1 foramen by restoring femoral head position."
    ),
    progression="Deep stretch achieved → add 5-second internal rotation hold at end range before releasing.",
    regression="Sharp deep joint pain → reduce diagonal angle, keep knee more toward ipsilateral shoulder.",
)

PIRIFORMIS_PNF = _ex(
    name="Piriformis Contract-Relax (PNF)",
    ex_type="reps",
    laterality="unilateral",
    sets=3, reps=5, rest_seconds=60,
    mechanics=(
        "Lie on your back, right ankle crossed over left knee (figure-4 position). "
        "CYCLE — repeat 5 times per side: "
        "1. CONTRACT — push your RIGHT knee DOWNWARD (away from you) for 5 seconds, "
        "resisting with your LEFT hand. Isometric — no movement. "
        "2. RELAX — immediately release the push entirely. "
        "3. DEEPEN — draw BOTH legs gently toward your chest, going 5–10% deeper than before. "
        "The piriformis is temporarily inhibited post-contraction — this is the window to gain range. "
        "Hold 3 seconds, then contract again. "
        "Complete 5 cycles right side, then repeat left side."
    ),
    biomechanical_focus=(
        "PNF piriformis inhibition — autogenic inhibition post-isometric contraction is significantly "
        "more effective than passive stretch at releasing the chronically overactive piriformis + deep "
        "hip rotators identified in your biomechanical profile. Directly addresses the upper glute "
        "gripping pattern that is the anchor of your joint compression."
    ),
    progression="Gaining range each cycle → perform in 90/90 seated position for greater hip flexion bias.",
    regression="Sharp buttock pain during contraction → remove pressing phase, passive figure-4 only.",
)

ISCHIAL_RELEASE = _ex(
    name="Ischial Tuberosity Hamstring Release",
    ex_type="hold",
    laterality="bilateral",
    sets=2, hold_seconds=90, rest_seconds=45,
    mechanics=(
        "Sit on a hard surface (wooden chair, floor, or firm step). "
        "Place a small rolled sock or folded cloth under your RIGHT sit bone. "
        "Lean slightly forward at the hip — feel your weight load into the sit bone. "
        "Hold 90 seconds. You are applying sustained pressure to the proximal hamstring "
        "attachment at the ischial tuberosity — the exact location of the structural release "
        "identified in your biomechanical profile. "
        "A dull ache or warmth is normal. Sharp pain → stop immediately. "
        "Repeat on the left side with same or smaller object."
    ),
    biomechanical_focus=(
        "Proximal hamstring tendon desensitisation — directly targets the high-tension "
        "upper hamstring attachment that shifts over the ischial tuberosity during the standing hinge. "
        "Sustained compression improves tendon gliding mechanics and reduces the reactive tension "
        "that accumulates with prolonged sitting."
    ),
    progression="Comfortable → lean further forward to increase proximal hamstring load.",
    regression="Too intense → use softer surface, no raised object, shorter hold.",
)

COXA_SALTANS_DRILL = _ex(
    name="Right Hip Tendon Path Drill (Coxa Saltans)",
    ex_type="reps",
    laterality="unilateral",
    sets=2, reps=10, rest_seconds=45,
    mechanics=(
        "Stand beside a wall, fingertip touch for balance. RIGHT leg only. "
        "Slowly raise your RIGHT knee toward 90 degrees. "
        "CRITICAL: keep the hip in NEUTRAL or very slight INTERNAL rotation as you lift. "
        "Do NOT externally rotate (turn the knee outward) as you raise it — "
        "external rotation is what causes the snap by moving the tendon over the bony ridge. "
        "If you feel the click: find the exact angle where it begins (usually 60–80°). "
        "Practice controlling through that range slowly, maintaining neutral rotation. "
        "Lower with the same neutral rotation. RIGHT SIDE ONLY."
    ),
    biomechanical_focus=(
        "Iliopsoas tendon path retraining — the snap occurs when the tendon crosses the "
        "iliopectineal eminence during combined hip flexion + external rotation. "
        "Internal rotation bias shifts the tendon path to prevent the crossing. "
        "Over time this retrains the motor pattern to avoid the snap during daily movement."
    ),
    progression="10 reps without snap → progress to single-leg stand at 90° hip flexion with neutral rotation.",
    regression="Cannot prevent snap → work only to 60° until tendon path ingrains at lower angle first.",
)

RIGHT_HIP_CAPSULE_REVISED = _ex(
    name="Right Posterior Hip Capsule Stretch (Revised Cue)",
    ex_type="hold",
    laterality="unilateral",
    sets=2, hold_seconds=60, rest_seconds=45,
    mechanics=(
        "Revised version — the standard cross-body cue (Days 1-14) reportedly produced tightness "
        "at the FRONT/middle of BOTH hips rather than the intended RIGHT posterior capsule, with "
        "no sensation at the back of the hip/glute (session note, 2026-07-08). Try this instead: "
        "Lie on your back, RIGHT knee bent. Posteriorly tilt your pelvis slightly and keep your "
        "LOWER BACK FLAT on the floor throughout — this is the priority, not stretch distance. "
        "From there, draw the right knee across toward the left shoulder ONLY as far as the lower "
        "back can stay flat — stop the moment the low back wants to arch or twist off the floor. "
        "Target sensation: deep in the BACK of the right hip/buttock, not the front groin. "
        "If you still feel it at the front, the range is too big — reduce it further and prioritise "
        "the flat-back cue over cross-body distance. Note whether this version lands differently."
    ),
    biomechanical_focus=(
        "Same target as the original (right posterior hip capsule, finding #2) — this variant "
        "prioritises pelvic control (flat lower back) over stretch distance, since the prior cueing "
        "may have let the pelvis rotate/tilt, shifting the stretch anteriorly instead of posteriorly. "
        "A diagnostic adjustment based on direct session feedback, not a confirmed fix yet."
    ),
    progression="Deep posterior-hip sensation achieved with flat back → gradually increase cross-body range.",
    regression="Still feels anterior/frontal → reduce range further; flat-back control takes priority over depth.",
)

SCAPULAR_WALL_SLIDE = _ex(
    name="Scapular Wall Slide",
    ex_type="reps",
    sets=2, reps=10, tempo="3-1-3", rest_seconds=45,
    mechanics=(
        "Stand with your head, upper back, and arms against a wall, elbows and wrists touching the "
        "wall in a goalpost/W position. Slowly slide your arms up toward a Y position, keeping the "
        "backs of your wrists and elbows in contact with the wall the whole way. "
        "Shoulder blades should glide smoothly around the ribcage — no shrugging, no arching the "
        "low back off neutral to help the arms up. If contact is lost, only slide as high as you "
        "can keep it. Bodyweight-only scapular control — no external load."
    ),
    biomechanical_focus=(
        "Scapular upward rotation control and lower trapezius/serratus activation — directly "
        "addresses the maintenance-dependent right shoulder (finding #6): stability since the "
        "Latarjet repair comes from muscular control, not passive structure, and symptoms have "
        "recurred specifically when this kind of work lapses."
    ),
    progression="Full wrist-to-Y contact maintained pain-free → add a 2-second hold at the top.",
    regression="Contact lost early or shoulder discomfort → reduce range to where contact holds, or sit for the movement.",
)

PRONE_Y_RAISE = _ex(
    name="Prone Y-Raise (Scapular)",
    ex_type="hold_reps",
    sets=2, reps_in_set=8, hold_seconds=3, rest_seconds=45,
    mechanics=(
        "Lie face down, arms overhead in a Y shape, thumbs pointing up. Lift arms a few inches off "
        "the floor, squeezing the lower shoulder blades down and together. Hold 3 seconds, lower "
        "with control. Keep the low back relaxed — this is a shoulder-blade movement, not a back "
        "extension. If the low back arches to compensate, lift the arms less."
    ),
    biomechanical_focus=(
        "Lower trapezius strengthening — the specific weak link in the right shoulder's eccentric "
        "control flagged in the 2025 strength analysis, and part of the standing requirement for "
        "maintaining Latarjet-repair stability (finding #6)."
    ),
    progression="Clean 8 reps, no low-back compensation → add a 1-second pause at the very top.",
    regression="Low back arches to compensate → reduce lift height, focus purely on the scapular squeeze.",
    warning="Stop if this produces lumbar extension discomfort — reduce lift height immediately.",
)


# ─────────────────────────────────────────────────────────────────────────────
#  14-DAY PLAN
# ─────────────────────────────────────────────────────────────────────────────

PLAN: dict[int, dict] = {}


# ── Week 1: Tissue Tolerance + Neural Desensitisation ─────────────────────────
# Rationale: Reduce neural irritability, restore basic segmental motion, inhibit
# compensatory psoas hypertonicity. No spinal loading. No end-range extension.

PLAN[1] = {
    "objective": "Tissue Tolerance — Baseline Mobility Assessment",
    "phase": "Week 1: Neural Reset",
    "session_rpe_target": 3,
    "exercises": [
        UPPER_GLUTE_RELEASE,
        RIGHT_HIP_CAPSULE,
        _ex(
            name="Supine Knee-to-Chest",
            ex_type="hold",
            laterality="unilateral",
            sets=3, hold_seconds=45, rest_seconds=60,
            mechanics=(
                "Lie flat on your back, both knees bent, feet flat. "
                "Draw ONE knee slowly toward your chest — clasp BOTH hands behind your thigh, not on the knee joint itself. "
                "Hold at a comfortable endpoint. Do NOT pull forcefully. "
                "Keep the opposite leg flat on the floor. "
                "Breathe normally throughout. Release slowly. Repeat on the other side."
            ),
            biomechanical_focus="L5/S1 posterior disc decompression — hip flexion reduces posterior annular tension and opens the right foramen slightly.",
            progression="Pain 0/10 throughout → extend hold to 60 seconds next session.",
            regression="Pain >2/10 → reduce hip flexion range, hold only 20 seconds.",
        ),
        _ex(
            name="Cat-Cow",
            ex_type="reps",
            sets=2, reps=10, tempo="4-0-4", rest_seconds=45,
            mechanics=(
                "On hands and knees — wrists under shoulders, knees under hips. "
                "CAT: Exhale, round your entire spine upward like an angry cat — tuck chin and tailbone. "
                "COW: Inhale, let belly drop, gently lift head and tailbone. "
                "Move only to your COMFORTABLE range. Never force end-range lumbar extension."
            ),
            biomechanical_focus="Segmental lumbar mobilisation — gentle, rhythmic facet joint motion across L1-L5 without axial load.",
            progression="Pain free → increase to 15 reps, add 2-second pause at each end position.",
            regression="Extension causes pain → Cat position ONLY (flexion-bias). No Cow phase.",
        ),
        _ex(
            name="Standing Hip Flexor Release",
            ex_type="hold",
            laterality="unilateral",
            sets=2, hold_seconds=90, rest_seconds=60,
            mechanics=(
                "Stand facing a wall. Step ONE foot forward onto a low raised surface (thick book, bottom stair). "
                "That front knee is at roughly 90 degrees. "
                "The back foot stays on the floor, back knee slightly soft. "
                "Gently shift your hips FORWARD until you feel a deep stretch in the FRONT of your back hip/groin. "
                "Keep your lower back in neutral — pelvis slightly tucked under, do NOT arch the back. "
                "Hold. Switch sides."
            ),
            biomechanical_focus="Psoas (L1-L4 anterior attachment) lengthening — directly reduces anterior lumbar traction that compresses L5/S1 foramen.",
            progression="Pain free → add posterior pelvic tilt (tuck tailbone further under) to intensify during hold.",
            regression="Lower back pain → reduce forward shift, hold 45 seconds only.",
        ),
        _ex(
            name="Prone Decompression Breathing",
            ex_type="duration",
            sets=1, duration_minutes=3, rest_seconds=0,
            mechanics=(
                "Lie face down on the floor. Arms by your sides or folded under your forehead — whichever is comfortable. "
                "Breathe DEEPLY into your lower back, allowing your belly to expand into the floor on each inhale. "
                "This is completely passive — no active movement. "
                "Simply allow gravity to gently extend your lumbar spine. "
                "If uncomfortable, place a folded towel under your abdomen."
            ),
            biomechanical_focus="Passive lumbar extension centralises posterior disc material; diaphragmatic breathing inhibits psoas (they share direct anatomical proximity at L1-L4).",
            progression="Comfortable → next session: add passive cobra (hands under shoulders, gentle elbow push-up).",
            regression="Pain face-down → place pillow under abdomen, or skip and stay supine.",
            warning="Stop immediately if leg tingling or numbness occurs in this position.",
        ),
    ],
}

PLAN[2] = {
    "objective": "Psoas Inhibition + Lumbar Decompression",
    "phase": "Week 1: Neural Reset",
    "session_rpe_target": 3,
    "exercises": [
        UPPER_GLUTE_RELEASE,
        PIRIFORMIS_PNF,
        _ex(
            name="90/90 Hip Flexor Hold",
            ex_type="hold",
            laterality="unilateral",
            sets=3, hold_seconds=60, rest_seconds=60,
            mechanics=(
                "Sit on the floor. Place one knee directly in front of you at 90 degrees, "
                "the other knee out to the side at 90 degrees (figure-4 position). "
                "Sit tall — do NOT round your lower back. "
                "Lean your torso GENTLY forward over your front knee. "
                "Feel the stretch deep in your front hip crease. "
                "Hold. Switch sides by rotating your legs to the opposite 90/90."
            ),
            biomechanical_focus="Hip capsule + iliopsoas lengthening; reduces anterior pelvic tilt that increases lumbar lordosis and compresses L5/S1.",
            progression="Pain free → lean torso further forward over front knee.",
            regression="Lower back pain → sit more upright, reduce forward lean.",
        ),
        _ex(
            name="Side-Lying Hip Abduction",
            ex_type="reps",
            laterality="unilateral",
            sets=3, reps=15, tempo="1-1-3", rest_seconds=45,
            mechanics=(
                "Lie on your side. Bottom knee bent for stability, top leg straight. "
                "Keep your top leg in line with your body — do NOT let it drift forward. "
                "Lift the top leg to about 40cm (16 inches) with toes pointing FORWARD, not to the ceiling. "
                "Pause 1 second at the top. Lower under control over 3 seconds. "
                "Do NOT roll your pelvis backward during the lift."
            ),
            biomechanical_focus="Glute medius endurance — prevents Trendelenburg pattern that increases lateral lumbar shift under load.",
            progression="Pain free, easy → add a 2-second hold at the top position.",
            regression="Lateral hip discomfort → reduce range of motion, lift only 20cm.",
        ),
        _ex(
            name="Supine Knees-to-Chest (Bilateral Rock)",
            ex_type="reps",
            sets=2, reps=12, tempo="2-2-2", rest_seconds=45,
            mechanics=(
                "Lie on your back. Draw BOTH knees to your chest simultaneously. "
                "Gently rock side to side 3-4 times. Hold at centre. Lower both feet. "
                "Breathe throughout. This is a gentle decompression — do NOT perform if painful."
            ),
            biomechanical_focus="Bilateral posterior chain decompression; L3-L5 annular tension relief via combined hip flexion.",
            progression="No pain → add 5-second hold at chest before rocking.",
            regression="Any pain → revert to single-knee-to-chest only (Day 1 exercise).",
        ),
    ],
}

PLAN[3] = {
    "objective": "Neuromuscular Activation — Isometric Foundation (McGill Protocol)",
    "phase": "Week 1: Neural Reset",
    "session_rpe_target": 5,
    "exercises": [
        UPPER_GLUTE_RELEASE,
        RIGHT_HIP_CAPSULE,
        _ex(
            name="McGill Modified Curl-Up",
            ex_type="hold_reps",
            sets=3, reps_in_set=5, hold_seconds=10, rest_seconds=60,
            mechanics=(
                "Lie on your back. ONE knee bent, the other leg flat on the floor. "
                "Slide BOTH hands, palms down, under the natural curve of your lower back. "
                "Do NOT flatten your back into the floor — maintain the curve. "
                "Slowly lift ONLY your head and shoulder blades off the floor. "
                "This is NOT a crunch — it is a tiny lift. "
                "Hold for 10 seconds. Lower. Repeat 5 times = 1 set. "
                "Your lower back should not move — hands confirm this."
            ),
            biomechanical_focus="Rectus abdominis + transversus abdominis isometric co-activation WITHOUT lumbar flexion — builds the anterior stability unit for L5/S1 retrolisthesis control.",
            progression="All reps pain-free → progress to 8 reps per set next session.",
            regression="Any lower back pain → reduce lift height further. Feels effort in neck only → fix form (look at ceiling, not knees).",
        ),
        _ex(
            name="Bird-Dog",
            ex_type="hold_reps",
            laterality="alternating",
            sets=3, reps_in_set=10, hold_seconds=8, rest_seconds=60,
            mechanics=(
                "On hands and knees — wrists under shoulders, knees under hips. Neutral spine. "
                "Simultaneously extend your RIGHT arm forward and LEFT leg back. "
                "Hold 8 seconds. Your hips must NOT rotate — check by balancing a water bottle on your lower back. "
                "Return slowly (3 seconds). Switch to left arm / right leg. "
                "Both arm+leg extensions = 1 rep. "
                "If you cannot hold without wobbling, reduce hold time to 4 seconds."
            ),
            biomechanical_focus="Multifidus + contralateral glute co-activation — the primary segmental stabilisers at L4/5 and L5/S1, directly relevant to the retrolisthesis finding.",
            progression="Perfect form, pain free → extend hold to 10 seconds. Then add reaching further.",
            regression="Hip rotation or lumbar sag → reduce hold to 4 seconds, reduce range of extension.",
        ),
        _ex(
            name="Side Bridge (Modified — Bent Knee)",
            ex_type="hold",
            laterality="unilateral",
            sets=3, hold_seconds=30, rest_seconds=60,
            mechanics=(
                "Lie on your side. Bottom knee bent to 90 degrees (easier variation). Top leg straight. "
                "Support on your forearm — elbow directly under your shoulder. "
                "Lift your hips off the floor until your body forms a straight line from knees to shoulders. "
                "Keep your neck neutral (look straight ahead, not down). "
                "Hold without letting your hips sag. Switch sides."
            ),
            biomechanical_focus="Quadratus lumborum + lateral abdominals — controls lateral spinal stability and resists the left dorsolateral loading at L3-L5.",
            progression="30 seconds easy → extend to 45 seconds, then 60 seconds.",
            regression="Pain or shoulder discomfort → shorten hold to 15 seconds, or do wall-supported version (lean against wall in side position).",
        ),
        _ex(
            name="Supine Hip Flexion (Marching)",
            ex_type="reps",
            sets=2, reps=10, tempo="2-1-3", rest_seconds=45, laterality="alternating",
            mechanics=(
                "Lie flat on your back. Bend ONE knee to 90 degrees, foot still on floor. "
                "Slowly lift that foot until thigh is vertical (knee at 90 degrees, shin parallel to ceiling). "
                "Pause 1 second. Lower slowly over 3 seconds. "
                "The OTHER leg stays flat throughout. "
                "Critical: your lower back must NOT arch off the floor when you lift. Press back down gently."
            ),
            biomechanical_focus="Iliopsoas length + lumbar stability integration — tests whether hip flexion is occurring at the HIP, not at the lumbar spine.",
            progression="No lumbar movement during lift → progress to full leg raise (straight leg).",
            regression="Lumbar arch during lift → press lower back down first, reduce lift height.",
        ),
    ],
}

PLAN[4] = {
    "objective": "Neuromuscular Activation — Gluteal Activation + Hip Dissociation",
    "phase": "Week 1: Neural Reset",
    "session_rpe_target": 5,
    "exercises": [
        ISCHIAL_RELEASE,
        UPPER_GLUTE_RELEASE,
        _ex(
            name="Supine Glute Bridge (Bilateral)",
            ex_type="reps",
            sets=3, reps=15, tempo="1-2-3", rest_seconds=60,
            mechanics=(
                "Lie on your back. Knees bent, feet flat, hip-width apart. "
                "Drive your HEELS firmly into the floor. Squeeze your glutes hard. "
                "Lift your hips until you form a straight line from knees to shoulders. "
                "Hold 2 seconds at the top — feel glutes, not lower back, doing the work. "
                "Lower SLOWLY over 3 seconds — do not drop. "
                "Do NOT hyperextend your lower back at the top."
            ),
            biomechanical_focus="Gluteus maximus primary activation — restores the dominant hip extensor that is inhibited by prolonged sitting and psoas dominance.",
            progression="All reps clean → add a 3-second hold at top, or progress to single-leg bridge.",
            regression="Lower back pain at top → reduce height, do partial bridge to pain-free range only.",
        ),
        _ex(
            name="Clamshell",
            ex_type="reps",
            laterality="unilateral",
            sets=3, reps=20, tempo="1-1-3", rest_seconds=45,
            mechanics=(
                "Lie on your side, hips at 45 degrees forward, knees bent to 90 degrees. Feet together. "
                "Keeping feet together, rotate your TOP knee upward toward the ceiling — like a clamshell opening. "
                "Do NOT let your pelvis roll backward — this is the most common mistake. "
                "Hold 1 second at the top. Lower under control over 3 seconds. "
                "Complete all reps on one side before switching. "
                "RIGHT SIDE NOTE: your right glute medius is overactive — if it fatigues faster "
                "than expected, reduce reps by 5 on the right and focus on quality over quantity."
            ),
            biomechanical_focus="Glute medius isolation — prevents hip drop (Trendelenburg) that creates lateral lumbar shear through L3-L5 during gait.",
            progression="20 reps easy → add a resistance band above the knees, or increase to 25 reps.",
            regression="Pain → reduce to 10 reps, smaller range of motion.",
        ),
        _ex(
            name="Prone Hip Extension (Single Leg)",
            ex_type="reps",
            laterality="unilateral",
            sets=3, reps=15, tempo="1-2-4", rest_seconds=45,
            mechanics=(
                "Lie face down. Place a folded towel or small pillow under your abdomen for support. "
                "Tighten the glute of ONE side first. Then lift that straight leg 10-15cm off the floor. "
                "Critical: do NOT rotate the pelvis or lift the hip — only the leg moves. "
                "Hold 2 seconds at the top. Lower over 4 seconds. "
                "Rest. Complete all reps one side, then switch."
            ),
            biomechanical_focus="Gluteus maximus eccentric load capacity — builds the posterior chain without spinal compression. Directly trains the L5/S1 stability mechanism from the extension side.",
            progression="Pain free → lift slightly higher, increase hold to 4 seconds.",
            regression="Lumbar pain during lift → use pillow under abdomen, reduce height of lift.",
        ),
        _ex(
            name="Standing Hip Hinge (Wall Glute Touch)",
            ex_type="reps",
            sets=3, reps=12, tempo="3-1-2", rest_seconds=60,
            mechanics=(
                "Stand approximately 30cm (1 foot) from a wall. "
                "Soft bend in knees. Hinge at your HIPS — push your glutes BACKWARD toward the wall. "
                "Think: 'close a car door with my butt'. "
                "Arms hang or reach slightly forward. Maintain a neutral, long spine throughout. "
                "When your glutes touch the wall, feel the hamstring stretch. "
                "Drive back to upright by squeezing your glutes. "
                "This is the fundamental movement pattern for all future loading."
            ),
            biomechanical_focus="Hip hinge motor pattern — establishes the correct movement strategy (hip-dominant, not lumbar-dominant) to protect L5/S1 in all future loaded exercises.",
            progression="Smooth, pain-free → move further from wall (45cm). Then add a slight arm reach forward at the bottom.",
            regression="Lumbar rounding during hinge → stay closer to wall, shorter range of motion.",
        ),
    ],
}

PLAN[5] = {
    "objective": "Tissue Tolerance — Progressive Isometric Loading",
    "phase": "Week 1: Neural Reset",
    "session_rpe_target": 6,
    "exercises": [
        UPPER_GLUTE_RELEASE,
        _ex(
            name="Wall Sit (Isometric Quad)",
            ex_type="hold",
            sets=3, hold_seconds=45, rest_seconds=90,
            mechanics=(
                "Stand with your back flat against a wall. "
                "Feet shoulder-width apart, about 60cm from the wall. "
                "Slide your back down the wall until your thighs are PARALLEL to the floor — knees at 90 degrees. "
                "Your knees must track over your second toe — do not allow inward collapse. "
                "Even weight through both feet. Arms crossed at chest or resting on thighs. "
                "Hold without moving. Breathe."
            ),
            biomechanical_focus="Quadriceps + posterior chain isometric loading — builds lower limb capacity without spinal compression. Trains the stance-phase stability needed before progressive hip loading.",
            progression="45 seconds easy → extend to 60 seconds. Then try with one heel slightly raised.",
            regression="Knee pain → reduce thigh depth (higher against wall), hold 20 seconds.",
        ),
        _ex(
            name="Dead Bug",
            ex_type="reps",
            laterality="alternating",
            sets=3, reps=10, tempo="3-1-3", rest_seconds=60,
            mechanics=(
                "Lie on your back. Arms vertical toward ceiling. Knees bent at 90 degrees, lifted so shins are parallel to floor (tabletop position). "
                "Press your lower back INTO the floor — this is critical and must be maintained throughout. "
                "Slowly lower your RIGHT arm overhead AND LEFT leg toward the floor simultaneously. "
                "Lower over 3 seconds. The lower back must NOT arch. "
                "Return to start over 3 seconds. Switch sides. "
                "If your back peels off the floor, you have gone too far."
            ),
            biomechanical_focus="Transversus abdominis + internal oblique — deep anterior core activation that resists lumbar extension and provides direct L5/S1 retrolisthesis control.",
            progression="Back flat throughout → add a 2-second pause at full extension. Then extend both to full reach.",
            regression="Back arches → reduce range of arm/leg movement. Work within the range where back stays flat.",
        ),
        _ex(
            name="Lateral Step Walk",
            ex_type="reps",
            sets=3, reps=10, rest_seconds=60,
            mechanics=(
                "Stand in a wide stance, knees slightly bent — maintain this throughout. "
                "Step sideways to the RIGHT: step right foot out, then bring left foot to meet it (do not cross). "
                "Do 10 steps right, then 10 steps left = 1 set. "
                "Do NOT let your torso sway side to side. "
                "Maintain slight hip/knee bend throughout — this is a controlled, not casual, exercise."
            ),
            biomechanical_focus="Glute medius + hip abductor endurance under light load — replicates lateral force demands of walking and prepares the hip stabilisers for gait rehabilitation.",
            progression="Easy → add slight resistance by holding a book against each thigh during the steps.",
            regression="Balance issues → perform next to a wall for support.",
        ),
        _ex(
            name="Supine Knee Fallout (Butterfly)",
            ex_type="reps",
            sets=2, reps=15, tempo="3-0-3", rest_seconds=45,
            mechanics=(
                "Lie on your back. Feet together, soles touching. "
                "Allow your knees to fall OUTWARD toward the floor — gravity-assisted, no forcing. "
                "Go only to a comfortable range. "
                "Then ACTIVELY bring your knees back together, controlled over 3 seconds. "
                "Feel the inner hip muscles working on the return."
            ),
            biomechanical_focus="Hip internal rotator + adductor activation — restores hip rotation balance that is disrupted by prolonged sitting and protective muscle guarding post-injury.",
            progression="Full range easy → add a 2-second hold at the open position.",
            regression="Groin pain → reduce range, let knees fall only partway.",
        ),
    ],
}

PLAN[6] = {
    "objective": "Mobility + Tissue Quality — Active Recovery",
    "phase": "Week 1: Neural Reset",
    "session_rpe_target": 3,
    "exercises": [
        ISCHIAL_RELEASE,
        _ex(
            name="Cat-Cow (Slow Flow)",
            ex_type="reps",
            sets=2, reps=10, tempo="4-2-4", rest_seconds=45,
            mechanics=(
                "Same as Day 1 — but slower today. 4 seconds per phase with a 2-second pause at each endpoint. "
                "Focus on feeling each individual vertebral level moving sequentially, from tailbone upward. "
                "The goal is segmental motor control, not just global movement."
            ),
            biomechanical_focus="Segmental intervertebral motion — gentle proprioceptive input to the paraspinal mechanoreceptors at each lumbar level.",
            progression="Can isolate each segment moving → add cervical retraction (chin tuck) in cat phase.",
            regression="Any pain → return to Day 1 speed and range.",
        ),
        _ex(
            name="Thoracic Extension (Rolled Towel)",
            ex_type="hold",
            sets=2, hold_seconds=60, rest_seconds=60,
            mechanics=(
                "Tightly roll a bath towel. "
                "Sit on the floor, then lower your mid-back onto the roll so it sits across T6-T8 — the area BETWEEN your shoulder blades. "
                "Arms crossed at your chest. "
                "Gently relax backward over the roll, allowing your thoracic spine to extend. "
                "Do NOT extend your LUMBAR spine over it — keep this targeted to mid-back. "
                "If this feels painful at any point, STOP — you may have the roll too low."
            ),
            biomechanical_focus="Thoracic extension mobility — directly counteracts the thoracic flexion posture of sitting that forces the lumbar spine to compensate with excess lordosis.",
            progression="60 seconds comfortable → move towel to T8-T10 (slightly lower) for a different level.",
            regression="Pain → place rolled towel higher (closer to shoulders/T4-T6).",
        ),
        _ex(
            name="Thread-the-Needle (Thoracic Rotation)",
            ex_type="reps",
            laterality="alternating",
            sets=2, reps=10, tempo="3-2-3", rest_seconds=45,
            mechanics=(
                "On hands and knees. "
                "Take your RIGHT arm and slowly 'thread' it under your body along the floor, sliding it beneath your left arm. "
                "Let your right shoulder drop toward the floor. Let your thoracic spine rotate — do NOT let your lumbar spine rotate. "
                "Hold 2 seconds. Return. Switch sides. "
                "The hips must stay level and square throughout."
            ),
            biomechanical_focus="Thoracic rotation mobility — restores rotational capacity at T-spine to reduce the compensatory lumbar rotation that loads the L3-L5 annuli.",
            progression="Good rotation, pain free → reach further back with the threading arm.",
            regression="Lumbar pain → reduce range, focus only on shoulder drop rather than full thread.",
        ),
        _ex(
            name="Controlled Walking",
            ex_type="duration",
            sets=1, duration_minutes=15, rest_seconds=0,
            mechanics=(
                "Slow, deliberate walking pace. "
                "Focus on: (1) Full hip EXTENSION on each step — push through your big toe and heel at the end of stance phase. "
                "(2) Arms swinging naturally and alternately. "
                "(3) Even step length left and right. "
                "Walk on a flat surface. Stop and rest if pain exceeds 3/10."
            ),
            biomechanical_focus="Gait normalisation — restores the hip extension terminal stance that is lost when L5/S1 pain causes an antalgic gait pattern.",
            progression="15 min pain free → increase by 5 minutes every 2 days.",
            regression="Pain >3/10 during walk → reduce to 10 minutes or walk on softer surface.",
        ),
    ],
}

PLAN[7] = {
    "objective": "Active Recovery + Week 1 Self-Assessment",
    "phase": "Week 1: Neural Reset",
    "session_rpe_target": 2,
    "exercises": [
        PIRIFORMIS_PNF,
        _ex(
            name="Diaphragmatic Breathing",
            ex_type="duration",
            sets=1, duration_minutes=5, rest_seconds=0,
            mechanics=(
                "Lie on your back, knees bent. Or sit comfortably. "
                "Place one hand on your belly, one on your chest. "
                "Breathe IN slowly for 4 counts — feel only your belly hand rise. Chest stays still. "
                "Hold gently for 1 count. "
                "Breathe OUT slowly for 6 counts. "
                "Repeat for 5 minutes. This activates the parasympathetic nervous system and inhibits chronic muscle guarding."
            ),
            biomechanical_focus="Diaphragm-psoas neurological inhibition — the diaphragm and psoas share fascial continuity; diaphragmatic breathing directly reduces resting psoas tone.",
            progression="5 minutes comfortable → extend to 8 minutes.",
            regression="Dizziness → breathe less deeply or reduce hold count to 0.",
        ),
        _ex(
            name="Supine Full-Body Stretch",
            ex_type="hold",
            sets=3, hold_seconds=30, rest_seconds=30,
            mechanics=(
                "Lie on your back, legs extended, arms stretched overhead on the floor. "
                "Simultaneously reach your arms as far overhead as possible and your heels as far away as possible. "
                "Feel a gentle full-body traction from both ends. "
                "Breathe into the stretch. No active movement — just length and breath. "
                "Release and rest 30 seconds between holds."
            ),
            biomechanical_focus="Full kinetic chain elongation — decompresses intervertebral discs through longitudinal traction, reduces resting disc nucleus pressure.",
            progression="Comfortable → hold 45 seconds.",
            regression="Lower back pain → only extend legs, keep arms by sides.",
        ),
        _ex(
            name="Assessment Walk + Stair Check",
            ex_type="duration",
            sets=1, duration_minutes=10, rest_seconds=0,
            mechanics=(
                "Walk for 10 minutes at a comfortable pace. "
                "Then walk up and down a single flight of stairs twice. "
                "Observe: (1) Is pain symmetric left/right? (2) Does it change with different surfaces? "
                "(3) Does pain reduce, stay same, or worsen during/after walking? "
                "Record your pain score (0-10) and note any observations in the session notes."
            ),
            biomechanical_focus="Functional movement baseline — documents your pain-free walking capacity at Week 1 end. This becomes your benchmark for Week 2 comparison.",
            progression="Pain ≤2/10 throughout → increase walk to 15 minutes tomorrow.",
            regression="Pain >4/10 → shorten walk to 5 minutes, avoid stairs, log this in readiness entry.",
        ),
        _ex(
            name="Week 1 Self-Assessment",
            ex_type="reps",
            sets=1, reps=5, rest_seconds=0,
            mechanics=(
                "Rate your pain (0-10) in each of these 5 positions. Hold each for 30 seconds: "
                "(1) Standing still. (2) Sitting on a hard chair. (3) Bending forward at hips. "
                "(4) Lying flat on back. (5) Walking 5 steps. "
                "Write your scores in the Session Notes. Compare these scores with your Day 1 baseline. "
                "Any score that is lower than Day 1 = progress. "
                "Any score that has increased = flag for physiotherapist review. "
                "Also assess the 5 biomechanical patterns from your profile: "
                "(6) Upper glute release — has the grip reduced after 7 days? "
                "(7) Standing hinge — does the sit-bone area feel less restricted?"
            ),
            biomechanical_focus="Self-assessment provides the subjective outcome measure for Stage 1 → 2 progression evaluation.",
            progression="All scores ≤3/10 → excellent progress. Continue to Week 2.",
            regression="Any score >5/10 that worsened from Day 1 → extend Stage 1, do not progress to Week 2 loading.",
        ),
    ],
}

# ── Week 2: Neuromuscular Loading + Progressive Tissue Stress ─────────────────
# Rationale: Build on Week 1 neural desensitisation. Introduce directional
# loading patterns, functional hip hinge, and anterior core endurance.
# Retrolisthesis at L4/5 + L5/S1 makes spinal stability the priority.

PLAN[8] = {
    "objective": "Tissue Tolerance — McGill Protocol Progression",
    "phase": "Week 2: Neuromuscular Loading",
    "session_rpe_target": 6,
    "exercises": [
        UPPER_GLUTE_RELEASE,
        PIRIFORMIS_PNF,
        _ex(
            name="McGill Curl-Up (Progressed)",
            ex_type="hold_reps",
            sets=4, reps_in_set=5, hold_seconds=8, rest_seconds=60,
            mechanics=(
                "Same form as Day 3. "
                "Progress: lift slightly HIGHER than before — aim to clear shoulder blades off floor. "
                "Still NOT a full crunch. Hands still under lumbar curve to confirm no movement. "
                "Breathe OUT as you lift, IN as you lower. Do NOT hold breath during the hold. "
                "4 sets this session."
            ),
            biomechanical_focus="Anterior stability unit progression — increases demand on the TA/rectus/internal oblique system that protects the L5/S1 segment during load.",
            progression="4×5 pain free, good form → increase to 4×8 reps next session.",
            regression="Lower back pain → return to Day 3 height and 3 sets.",
        ),
        _ex(
            name="Bird-Dog (Extended Hold)",
            ex_type="hold_reps",
            laterality="alternating",
            sets=3, reps_in_set=8, hold_seconds=10, rest_seconds=60,
            mechanics=(
                "Same as Day 3. Progress: hold extended to 10 seconds (was 8). "
                "New focus: at the maximum extension endpoint, try to REACH further — as if being pulled from both ends. "
                "Keep breathing throughout the hold. "
                "If your lumbar spine rotates at all, reduce the hold time back to 6 seconds."
            ),
            biomechanical_focus="Multifidus endurance — research shows progressive hold time is the primary training stimulus for multifidus hypertrophy, directly addressing the segmental instability at L4/5 and L5/S1.",
            progression="10-second holds clean → increase to 3×10 reps per side.",
            regression="Hip rotation → reduce hold to 6 seconds, focus on hip levelness.",
        ),
        _ex(
            name="Full Side Bridge",
            ex_type="hold",
            laterality="unilateral",
            sets=3, hold_seconds=30, rest_seconds=60,
            mechanics=(
                "Progress from Day 3 — now with both legs STRAIGHT (no bent bottom knee). "
                "Lie on your side. Support on your forearm, elbow under shoulder. "
                "Stack your feet or place top foot in front of bottom. "
                "Lift hips until your body is a straight plank from ankles to shoulders. "
                "Do NOT allow hips to sag throughout the hold. Switch sides."
            ),
            biomechanical_focus="Full quadratus lumborum + lateral abdominal wall — the complete lateral stability system for resisting left dorsolateral stress at L3-L5.",
            progression="30 seconds solid → extend to 45 seconds.",
            regression="Too difficult → return to bent-knee modified version from Day 3.",
        ),
        _ex(
            name="Glute Bridge (Eccentric Single Load)",
            ex_type="reps",
            sets=3, reps=12, tempo="1-2-5", rest_seconds=60,
            mechanics=(
                "Perform a standard glute bridge to the top position (both feet). "
                "At the TOP: lift your RIGHT foot slightly off the floor (just a hover). "
                "Now lower your hips to the floor on a controlled 5-count eccentric. "
                "Both hips go down, but the right foot hovers = slightly more load on left. "
                "Alternate which foot hovers each rep. "
                "This is NOT a single-leg bridge — it is a weighted eccentric with slight shift."
            ),
            biomechanical_focus="Eccentric gluteal + hamstring loading — the foundational tissue stress for posterior chain adaptation without compression. Eccentric loading is the most potent stimulus for tendon and muscle tissue remodelling.",
            progression="12 reps easy → progress to a true single-leg eccentric bridge.",
            regression="Hip pain → return to standard bilateral bridge with 3-second hold.",
        ),
    ],
}

PLAN[9] = {
    "objective": "Work Capacity — Functional Hip Hinge + Single-Leg Stability",
    "phase": "Week 2: Neuromuscular Loading",
    "session_rpe_target": 6,
    "exercises": [
        COXA_SALTANS_DRILL,
        _ex(
            name="RDL Hip Hinge to Wall",
            ex_type="reps",
            sets=3, reps=15, tempo="3-1-2", rest_seconds=60,
            mechanics=(
                "Stand 30cm from a wall. "
                "Hinge at your hips — push glutes BACKWARD until they touch the wall. "
                "Simultaneously reach your arms down in front of your thighs (not past knees). "
                "Feel the HAMSTRINGS load as the primary sensation — not the lower back. "
                "Squeeze glutes to return to upright. Full glute squeeze at the top. "
                "This is the core hip hinge pattern for all future barbell work when that phase begins."
            ),
            biomechanical_focus="Hip hinge motor pattern + hamstring eccentric capacity — restores the posterior-chain-dominant movement strategy that protects L5/S1 under load.",
            progression="Wall touch easy, pain free → move 45cm from wall. Then 60cm (no wall needed).",
            regression="Lower back rounding → stay closer to wall, smaller range of motion.",
        ),
        _ex(
            name="Single-Leg Balance",
            ex_type="hold",
            laterality="unilateral",
            sets=3, hold_seconds=60, rest_seconds=45,
            mechanics=(
                "Stand on ONE leg. Use only a fingertip on a wall if needed for safety — not for support. "
                "During the hold, make small deliberate shifts: forward, backward, slightly sideways. "
                "Focus on: your hip staying LEVEL — pelvis not dropping on the non-standing side. "
                "If the pelvis drops, it means glute medius is fatiguing. "
                "Switch legs. Complete all sets. "
                "RIGHT HIP NOTE: when balancing on your right leg, keep the hip in slight "
                "internal rotation to prevent the iliopsoas tendon snap. If the click occurs, "
                "externally rotate slightly less."
            ),
            biomechanical_focus="Proprioceptive + glute medius endurance under single-leg stance — essential for controlling lateral lumbar shift during gait, which is the primary functional demand of the L-spine.",
            progression="60 seconds easy with wall → progress to no wall, then eyes closed.",
            regression="Too difficult → reduce to 30 seconds, more wall contact.",
        ),
        _ex(
            name="Lateral Step-Up (Single Stair)",
            ex_type="reps",
            laterality="unilateral",
            sets=3, reps=12, tempo="2-1-3", rest_seconds=60,
            mechanics=(
                "Stand beside the bottom step of a staircase, side-on. "
                "Step your CLOSER foot UP onto the step sideways. "
                "Drive through the heel of that foot to lift your entire body upward. "
                "Do NOT push off the trailing foot — all power comes from the step foot. "
                "Lower back to the floor with control. "
                "Complete all reps one side, then turn and do the other."
            ),
            biomechanical_focus="Single-leg press + hip abductor closed-chain loading — introduces axial load through a hip-dominant pattern without direct spinal compression.",
            progression="12 reps clean → use a higher step (2 stairs).",
            regression="Any pain → reduce step height (use a thick book instead). Or hold the banister.",
        ),
        _ex(
            name="Reverse Lunge",
            ex_type="reps",
            laterality="alternating",
            sets=3, reps=10, tempo="2-0-2", rest_seconds=60,
            mechanics=(
                "Stand upright, feet hip-width. "
                "Step ONE foot BACKWARD, lowering your back knee toward the floor. "
                "Keep your front shin vertical — knee should track over second toe. "
                "Keep your torso upright — do NOT lean forward. "
                "Drive through your FRONT heel to return to standing. "
                "Alternate legs. "
                "The reverse lunge is preferred over forward lunges as it reduces anterior knee force and lumbar flexion demand."
            ),
            biomechanical_focus="Unilateral hip extensor + quad loading in a split-stance pattern — builds functional leg strength with controlled spinal load and hip-dominant mechanics.",
            progression="10 reps easy → increase to 15 reps, or add a 1-second pause at the bottom.",
            regression="Balance difficulty → hold a wall or doorframe for support. Reduce range of descent.",
        ),
    ],
}

PLAN[10] = {
    "objective": "Tissue Tolerance — Isometric Endurance + Anterior Core",
    "phase": "Week 2: Neuromuscular Loading",
    "session_rpe_target": 6,
    "exercises": [
        UPPER_GLUTE_RELEASE,
        RIGHT_HIP_CAPSULE,
        _ex(
            name="Pallof Press Hold (Doorframe)",
            ex_type="hold",
            laterality="unilateral",
            sets=3, hold_seconds=30, rest_seconds=60,
            mechanics=(
                "Tie a towel or exercise band around a door handle at belly-button height. "
                "Stand SIDEWAYS to the door, feet shoulder-width. "
                "Hold the towel at your chest with both hands. "
                "Step away from the door until you feel tension. "
                "Press your arms STRAIGHT out in front of you. "
                "Resist the pull that wants to rotate your body toward the door. "
                "Hold for 30 seconds without rotating. Breathe. Switch sides."
            ),
            biomechanical_focus="Anti-rotation anterior core — directly trains the stability of the L-spine against rotational forces, protecting the covered annular tears at L3/4 and L4/5 from torsional stress.",
            progression="30 seconds → extend to 45 seconds, or step further from the door.",
            regression="Cannot resist rotation → step closer to door (less tension).",
        ),
        _ex(
            name="Dead Bug (Progression — 3s Hold)",
            ex_type="reps",
            laterality="alternating",
            sets=3, reps=8, tempo="3-3-3", rest_seconds=60,
            mechanics=(
                "Same as Day 5. "
                "Progress: now add a 3-second HOLD at full extension before returning. "
                "The hold with lower back flat against the floor is significantly harder. "
                "If your back lifts at ALL during the hold, you have gone too far — reduce range."
            ),
            biomechanical_focus="Anterior core endurance under sustained load — the 3-second hold dramatically increases total time-under-tension for the deep abdominal wall.",
            progression="8 reps each side clean → increase to 10 reps per side.",
            regression="Back lifting → return to the original non-hold version (Day 5).",
        ),
        _ex(
            name="Wall Sit (Extended Duration)",
            ex_type="hold",
            sets=3, hold_seconds=60, rest_seconds=90,
            mechanics=(
                "Same as Day 5. Hold extended to 60 seconds. "
                "If 60 seconds is too easy at the same depth, increase the challenge by adding a slight heel raise (rise up on toes slightly mid-hold). "
                "Breathe throughout — do NOT hold your breath."
            ),
            biomechanical_focus="Quadriceps isometric endurance — builds lower limb capacity that provides the eccentric control for safe stair descent and return-to-sport movements.",
            progression="60 seconds clean → add single heel raise mid-hold.",
            regression="Knee pain → raise height on wall (less knee bend).",
        ),
        _ex(
            name="Side Bridge with Hip Dip",
            ex_type="reps",
            laterality="unilateral",
            sets=3, reps=10, tempo="1-0-3", rest_seconds=60,
            mechanics=(
                "Get into your full side bridge position (Day 8). "
                "From the hold, LOWER your hips toward the floor — controlled 3-count descent. "
                "Bring hips back UP to the plank position. "
                "This is a DYNAMIC variation of the side bridge. "
                "Complete all reps on one side before switching."
            ),
            biomechanical_focus="Dynamic quadratus lumborum + lateral core loading — progresses from static endurance to dynamic lateral strength, preparing the L-spine for varied real-world movements.",
            progression="10 reps each side → increase to 15, or add a 2-second hold at the top.",
            regression="Too difficult → return to static hold only. Do not add the dynamic component yet.",
        ),
    ],
}

PLAN[11] = {
    "objective": "Mobility + Neural Tissue Mobility — Posterior Chain",
    "phase": "Week 2: Neuromuscular Loading",
    "session_rpe_target": 5,
    "exercises": [
        COXA_SALTANS_DRILL,
        ISCHIAL_RELEASE,
        _ex(
            name="Sciatic Nerve Floss",
            ex_type="reps",
            laterality="unilateral",
            sets=3, reps=10, tempo="2-0-2", rest_seconds=60,
            mechanics=(
                "Sit upright on a chair. "
                "Straighten your RIGHT knee while simultaneously tilting your head BACKWARD (looking up). "
                "Then BEND your knee and BOW your head FORWARD simultaneously. "
                "Both movements are coordinated and rhythmic. "
                "You should feel a mild stretch or tension — this is normal. "
                "There should be NO sharp, shooting, or electric sensation. "
                "Complete all reps one side, then switch."
            ),
            biomechanical_focus="Sciatic nerve mechanosensitivity reduction — neural tissue that has been sensitised by L5/S1 disc pressure requires specific mobilisation to restore normal neural tension and reduce the neural component of pain.",
            progression="10 reps easy, no pain → add ankle dorsiflexion (pull toes back) when straightening knee.",
            regression="Any shooting or electric sensation → STOP immediately. Return to this exercise next session only.",
            warning="STOP IMMEDIATELY if any shooting, radiating, electric, or tingling sensation occurs. This indicates neural irritation that needs physiotherapist review.",
        ),
        _ex(
            name="Standing Calf Raise (Eccentric Focus)",
            ex_type="reps",
            laterality="unilateral",
            sets=3, reps=15, tempo="1-0-5", rest_seconds=60,
            mechanics=(
                "Stand on the edge of a step or stair (or flat floor). "
                "Rise up onto BOTH feet (bilateral concentric). "
                "At the top, transfer weight to ONE foot. "
                "Lower on ONE foot only over 5 counts (unilateral eccentric). "
                "Step back to flat. Repeat. Alternate which foot takes the eccentric. "
                "Hold the banister for balance if needed."
            ),
            biomechanical_focus="Soleus + gastrocnemius eccentric loading — the calf complex attaches to the Achilles and is a key contributor to terminal-stance gait mechanics. Its stiffness directly affects the lumbar load transfer pattern.",
            progression="15 reps clean → remove bilateral assist; full single-leg concentric and eccentric.",
            regression="Calf pain or ankle instability → perform bilateral only (both up AND down).",
        ),
        _ex(
            name="Prone Hip Extension (Slow Tempo — 4-3-5)",
            ex_type="reps",
            laterality="unilateral",
            sets=3, reps=12, tempo="4-3-5", rest_seconds=60,
            mechanics=(
                "Same as Day 4, now with controlled SLOW tempo: "
                "4 seconds to lift the leg → 3-second hold at the top → 5-second controlled lower. "
                "This tempo specifically loads the posterior fascial chain with maximum time under tension. "
                "At the top: feel the GLUTE contracting, not the lower back tightening. "
                "If lower back tightens → you are going too high."
            ),
            biomechanical_focus="Posterior fascial chain time-under-tension — the 12-second per-rep tempo is a specific loading stimulus for the thoracolumbar fascia, which provides passive segmental stability across L4-S1.",
            progression="12 reps clean → increase sets to 4.",
            regression="Lower back tightening → reduce height of lift, focus on glute only.",
        ),
        _ex(
            name="Hip 90/90 Flow",
            ex_type="reps",
            laterality="alternating",
            sets=2, reps=5, tempo="3-3-3", rest_seconds=60,
            mechanics=(
                "Sit on the floor. Start in 90/90 — one knee in front at 90°, one knee to the side at 90°. "
                "Rotate your hips so the front knee goes to the side and vice versa — you are now in the opposite 90/90. "
                "Briefly lean over each front knee for 3 seconds. "
                "Continue transitioning. "
                "Each full transition = 1 rep. "
                "This is ACTIVE mobility — use your muscles to move, not momentum. "
                "RIGHT HIP NOTE: during the 90/90 transition, maintain slight internal rotation "
                "bias on the right to prevent the iliopsoas snap identified in your profile."
            ),
            biomechanical_focus="Hip internal + external rotation mobility under bodyweight — restores the full rotational range of the hip joint that is essential for protecting the lumbar spine from rotational stress during daily activities.",
            progression="5 transitions smooth → hold each position for 5 seconds before transitioning.",
            regression="Hip discomfort → use hands on floor to support more weight. Reduce range.",
        ),
    ],
}

PLAN[12] = {
    "objective": "Work Capacity — Functional Integration",
    "phase": "Week 2: Neuromuscular Loading",
    "session_rpe_target": 6,
    "exercises": [
        ISCHIAL_RELEASE,
        _ex(
            name="Chair Sit-to-Stand",
            ex_type="reps",
            sets=3, reps=12, tempo="2-0-3", rest_seconds=60,
            mechanics=(
                "Sit on a standard chair, feet flat, hip-width. "
                "Lean your torso slightly forward — 'nose over toes'. "
                "Drive through your HEELS to stand up fully — do NOT push from the armrests. "
                "At standing: squeeze glutes, stand fully tall — hips through. "
                "Sit back down with CONTROL — over 3 seconds eccentric. "
                "Do NOT plop down onto the chair. "
                "This is a bilateral loaded squat pattern with spinal load control."
            ),
            biomechanical_focus="Bilateral lower-limb loading in a functional closed-chain pattern — trains the sit-to-stand movement that is one of the highest-demand daily activities for the lumbar spine.",
            progression="12 reps easy → use lower seat. Or add a 2-second pause halfway during descent.",
            regression="Knee pain → use a higher chair (less knee bend). Hold a stable surface for light support.",
        ),
        _ex(
            name="Forward Step-Up (Stair)",
            ex_type="reps",
            laterality="unilateral",
            sets=3, reps=15, tempo="2-1-3", rest_seconds=60,
            mechanics=(
                "Stand in front of the bottom stair. "
                "Step your RIGHT foot forward ONTO the step. "
                "Drive through the right heel to lift your full body weight onto the step. "
                "Do NOT push off the trailing left foot. "
                "Step back down with control over 3 seconds. "
                "Complete all reps right leg, then switch to left."
            ),
            biomechanical_focus="Single-leg closed-chain pressing — the most functional lower-body strength exercise, closely replicating stair climbing which is a key return-to-function milestone.",
            progression="15 reps clean → use a higher step (second stair).",
            regression="Pain → hold banister for support, reduce step height.",
        ),
        _ex(
            name="Forearm Plank",
            ex_type="hold",
            sets=3, hold_seconds=30, rest_seconds=60,
            mechanics=(
                "Forearms on the floor, elbows directly under shoulders. "
                "Toes on the floor. "
                "Lift your body into a straight plank position — hips in line with shoulders and ankles. "
                "Do NOT let hips sag down or pike up. "
                "Squeeze your glutes. Breathe. "
                "Do NOT hold your breath."
            ),
            biomechanical_focus="Full anterior core + posterior chain integrated isometric — the plank creates circumferential intra-abdominal pressure that creates direct spinal protection at all lumbar levels simultaneously.",
            progression="30 seconds → extend to 45 seconds, then 60 seconds.",
            regression="Lower back pain → try on knees (knee plank) or elevate hands onto a raised surface.",
        ),
        _ex(
            name="Walking — Gait Focus",
            ex_type="duration",
            sets=1, duration_minutes=15, rest_seconds=0,
            mechanics=(
                "Walk for 15 minutes. "
                "Conscious focus on: glute push-off at toe-off. Slightly longer stride. Natural arm swing. "
                "Check: does your right hip or left hip feel different? Is stride length equal? "
                "Walk on a flat, consistent surface. "
                "Rate pain at the start, 7 minutes, and at the end."
            ),
            biomechanical_focus="Integrated gait normalisation — the culmination of all hip extension, glute activation, and proprioception work from the programme. Full functional walking test.",
            progression="15 minutes, pain ≤2/10 → add a slight incline on the return half.",
            regression="Pain increasing during walk → stop at 10 minutes, rest, assess.",
        ),
    ],
}

PLAN[13] = {
    "objective": "Neuromuscular Activation — Progressive Challenge",
    "phase": "Week 2: Neuromuscular Loading",
    "session_rpe_target": 7,
    "exercises": [
        UPPER_GLUTE_RELEASE,
        PIRIFORMIS_PNF,
        _ex(
            name="Bird-Dog with Full Reach",
            ex_type="hold_reps",
            laterality="alternating",
            sets=3, reps_in_set=8, hold_seconds=8, rest_seconds=60,
            mechanics=(
                "Same as before. Progress: at the maximum extension endpoint, "
                "try to reach even FURTHER — as if someone is pulling your hand forward and foot backward. "
                "Do NOT let this produce any lumbar rotation or sag. "
                "The reach challenge increases the lever arm and demands much more from the stabilisers."
            ),
            biomechanical_focus="Maximum lever-arm demand on multifidus and gluteal stabilisation — at full reach, the rotational moment on the lumbar spine is greatest, providing the highest training stimulus within the safe range.",
            progression="Clean form at max reach → progress to 10-second holds.",
            regression="Any rotation or sag → reduce hold to 4 seconds, focus on levelness over reach.",
        ),
        _ex(
            name="Glute Bridge March",
            ex_type="reps",
            laterality="alternating",
            sets=3, reps=10, tempo="1-2-1", rest_seconds=60,
            mechanics=(
                "Lift into your full glute bridge position. "
                "Hold the bridge steady. "
                "Now lift your RIGHT knee to 90 degrees — thigh vertical, shin parallel to floor. "
                "Hold 2 seconds. Lower. "
                "Switch to LEFT knee. Alternate. "
                "Your bridge height must NOT drop when you lift the knee. If it does, glutes are fatiguing."
            ),
            biomechanical_focus="Contralateral hip flexor + glute co-activation in a single-limb supported bridge — mimics the single-leg stance phase of gait and directly trains the most functionally demanding position for L5/S1.",
            progression="10 reps per leg → try to extend the lifted leg (straight leg hold instead of bent knee).",
            regression="Bridge drops → return to standard static bridge. Glutes not strong enough yet for march.",
        ),
        _ex(
            name="Single-Leg RDL (Wall Support)",
            ex_type="reps",
            laterality="unilateral",
            sets=3, reps=10, tempo="3-1-3", rest_seconds=60,
            mechanics=(
                "Stand beside a wall, fingertip touch for balance ONLY — not support. "
                "Stand on your RIGHT leg. "
                "Hinge forward at the hip, extending your LEFT leg straight behind you. "
                "Aim for a 'T' shape — torso and back leg parallel to floor. "
                "Maintain neutral spine. Arms reach toward floor. "
                "Return to standing by driving through the right heel and squeezing right glute. "
                "Complete all reps. Switch sides. "
                "RIGHT SIDE NOTE: loading the right single-leg RDL will tension the posterior "
                "hip capsule — this may produce the deep ischial/sit-bone release identified in "
                "your profile. This is a structural release, not pain."
            ),
            biomechanical_focus="Single-leg hip hinge under proprioceptive challenge — builds the unilateral posterior chain capacity and hip proprioception essential for protecting L5/S1 during single-leg loading in daily activity.",
            progression="10 reps clean, minimal wall contact → remove wall entirely.",
            regression="Too much balance challenge → use full palm on wall, reduce range of forward lean.",
        ),
        _ex(
            name="Lateral Lunge",
            ex_type="reps",
            laterality="alternating",
            sets=3, reps=10, tempo="2-1-2", rest_seconds=60,
            mechanics=(
                "Stand upright, feet together. "
                "Step your RIGHT foot wide to the side. Shift your weight into it, bending only the RIGHT knee. "
                "Left leg stays STRAIGHT throughout. "
                "Keep your torso upright — do NOT lean sideways. "
                "Push back through the right heel to return to standing. "
                "Alternate sides each rep. "
                "You should feel this in the inner thigh of the straight leg AND the outer hip of the bent-knee leg."
            ),
            biomechanical_focus="Frontal-plane hip loading — addresses the lateral hip and adductor capacity that is typically underdeveloped in patients with lumbar disc pathology who have been protecting through the sagittal plane only.",
            progression="10 reps each → step wider, add 2-second hold at the bottom.",
            regression="Any lower back pain → reduce step width. Keep narrower stance.",
        ),
    ],
}

PLAN[14] = {
    "objective": "Stage Readiness Assessment — 14-Day Completion",
    "phase": "Week 2: Programme Assessment",
    "session_rpe_target": 5,
    "exercises": [
        RIGHT_HIP_CAPSULE,
        COXA_SALTANS_DRILL,
        _ex(
            name="McGill Big 3 — Quality Screen",
            ex_type="reps",
            sets=1, reps=8, rest_seconds=60,
            mechanics=(
                "Perform ONE high-quality set of each: "
                "(1) McGill Curl-Up × 8 reps × 8-second hold each. "
                "(2) Bird-Dog × 8 each side × 8-second hold. "
                "(3) Side Bridge × 40 seconds each side. "
                "This is a QUALITY screen — not for maximum effort. "
                "Focus on form perfection. Note: was this easier than Day 3? Log your observations."
            ),
            biomechanical_focus="Functional assessment of the foundational spinal stability system — comparing quality and ease to Day 3 baseline provides objective evidence of neuromuscular adaptation over 14 days.",
            progression="All performed pain-free with good form → Stage 2 progression criteria partially met.",
            regression="Pain during any exercise → log specific exercise and pain score. Extend Stage 1.",
        ),
        _ex(
            name="Single-Leg Balance (Eyes Closed)",
            ex_type="hold",
            laterality="unilateral",
            sets=2, hold_seconds=60, rest_seconds=45,
            mechanics=(
                "Stand on one leg. Remove the wall (no support). "
                "Close your EYES once you feel stable. "
                "Challenge: make small weight shifts while eyes closed. "
                "If unsafe or too unstable, keep eyes open. "
                "Compare: Day 9 required wall support. Day 14 should be wall-free with ease."
            ),
            biomechanical_focus="Proprioceptive progression under vision deprivation — tests the full integration of hip, ankle, and core proprioception that has been progressively trained over 14 days.",
            progression="60 seconds eyes closed clean → Stage 2 proprioception criterion met.",
            regression="Eyes-closed too unstable → perform eyes-open. Document for physiotherapist.",
        ),
        _ex(
            name="Hip Hinge Full Range Assessment",
            ex_type="reps",
            sets=2, reps=10, tempo="3-1-3", rest_seconds=60,
            mechanics=(
                "Full hip hinge WITHOUT wall (no longer needed). "
                "Stand freely. Hinge at hips to maximum comfortable range — let arms hang past knee level if possible. "
                "Hold 1 second at the bottom. Return with glute squeeze. "
                "Note: what is your maximum pain-free range? How does it compare to Day 4? "
                "Log this in session notes. "
                "BIOMECHANICAL CHECK: compare right vs left hip hinge range. Note if right side "
                "produces the ischial tuberosity release. This data goes to your physiotherapist."
            ),
            biomechanical_focus="Hip hinge range of motion and posterior chain capacity — this is the functional test for whether the L5/S1 pathway is desensitised enough to tolerate progressive loading in Stage 2.",
            progression="Full range, pain ≤2/10 → criteria met for Stage 2 Transition programming.",
            regression="Pain >3/10 at any range → document the range where pain begins. Extend Stage 1.",
        ),
        _ex(
            name="5-Minute Walk + Stair Assessment",
            ex_type="duration",
            sets=1, duration_minutes=7, rest_seconds=0,
            mechanics=(
                "Walk briskly for 5 minutes. "
                "Then walk up and down a flight of stairs TWICE at a normal pace. "
                "Rate pain: (1) Start of walk. (2) End of 5-minute walk. (3) Top of stairs. (4) Bottom of stairs. "
                "Log all scores in session notes. "
                "Compare with Day 7 assessment walk. "
                "This is your functional outcome measure for 14 days of Stage 1 rehabilitation."
            ),
            biomechanical_focus="Integrated functional outcome assessment — walking distance, stair capacity, and pain behaviour during functional tasks are the primary clinical benchmarks for rehabilitation progression.",
            progression="Pain ≤2/10 throughout AND improved from Day 7 scores → Stage 1 COMPLETE. Ready for Stage 2 assessment.",
            regression="Pain >3/10 on stairs or pain worse than Day 7 → discuss with physiotherapist before progressing.",
        ),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
#  WEEK 3 — FLARE RECOVERY & REASSESSMENT PREP (Days 15-21)
#
#  Added 2026-07-13. Day 14's exit criteria were not met on schedule: an active,
#  escalating mid-back/lower-back flare (patient_profile.py symptom_log,
#  3rd occurrence of the same sitting/overuse mechanism) pushed pain_free_streak
#  to 0 and avg_tightness_14d to 4.6 against the required <=3.0. By 2026-07-13
#  the flare is trending down (tightness 8->1 over the window) but the streak
#  and tightness criteria still need a clean week to actually be met.
#
#  This week is still Stage 1 (bodyweight only, ACWR ceiling 1.2, RPE ceiling 7,
#  no spinal loading/end-range extension/loaded rotation) — NOT Stage 2. RPE
#  targets are kept at Week-1 levels (3-5) rather than Week 2's (5-6) given the
#  recent flare, with two new elements layered in:
#    - Right shoulder scapular stability work (SCAPULAR_WALL_SLIDE, PRONE_Y_RAISE)
#      — patient_profile.py finding #6: shoulder stability is maintenance-
#      dependent, not resolved, so this is a standing requirement from here on,
#      not optional conditioning.
#    - RIGHT_HIP_CAPSULE_REVISED in place of the original cross-body cue,
#      testing a flat-back-priority variant per direct 2026-07-08 feedback that
#      the original wasn't landing on the intended structure.
#  Also applied throughout: even rep counts for bilateral/alternating exercises
#  (2026-07-08 feedback), and the neutral/internal-rotation cue extended to
#  supine leg-extension patterns (Dead Bug), not just standing hip flexion, per
#  the 45-degree clicking observed 2026-07-08 (finding #4 additional evidence).
#
#  Day 21 repeats the Day 14 assessment battery (McGill Big 3, single-leg
#  balance, hip hinge, walk+stair) so the actual reassessment has a fresh,
#  directly comparable data point on top of the Day 14 baseline.
# ─────────────────────────────────────────────────────────────────────────────

PLAN[15] = {
    "objective": "Flare Recovery — Gentle Re-Entry",
    "phase": "Week 3: Flare Recovery & Reassessment Prep",
    "session_rpe_target": 3,
    "exercises": [
        UPPER_GLUTE_RELEASE,
        RIGHT_HIP_CAPSULE_REVISED,
        _ex(
            name="Thoracic Extension (Rolled Towel)",
            ex_type="hold",
            sets=2, hold_seconds=60, rest_seconds=45,
            mechanics=(
                "Lie on your back with a rolled towel placed horizontally under your shoulder "
                "blades (not the neck or lower back). Support your head with your hands. "
                "Let your upper back gently extend over the towel — relax into it, do not force. "
                "Breathe slowly. If any point along the towel feels sharp rather than a dull "
                "stretch, shift the towel slightly and try again."
            ),
            biomechanical_focus=(
                "Thoracic facet mobility (T6-T10, finding #3) — gentle passive extension directly "
                "targets the mid-back region involved in the current flare, without any lumbar "
                "loading or end-range lumbar extension."
            ),
            progression="Comfortable throughout → hold 90 seconds next session.",
            regression="Any sharpness → reduce towel thickness or move it to a less sensitive level.",
        ),
        _ex(
            name="Supine Knee-to-Chest (Bilateral)",
            ex_type="hold",
            laterality="bilateral",
            sets=3, hold_seconds=45, rest_seconds=45,
            mechanics=(
                "Lie flat on your back. Draw BOTH knees toward your chest together, clasping "
                "both hands behind your thighs. Hold at a comfortable endpoint — do not pull "
                "forcefully. This is a decompression hold, matching the same mechanism that has "
                "helped the mid-back/lower-back flare settle so far this week."
            ),
            biomechanical_focus="Bilateral L5/S1 and mid-back decompression — gentle posterior pelvic tilt reduces compressive load along the same segments involved in the current flare.",
            progression="Pain-free, easy → extend hold to 60 seconds.",
            regression="Any discomfort → single-leg version (one knee at a time, opposite leg flat).",
        ),
        _ex(
            name="Controlled Walking",
            ex_type="duration",
            sets=1, duration_minutes=10, rest_seconds=0,
            mechanics=(
                "Walk at an easy, comfortable pace for 10 minutes on flat ground. Habitual "
                "posture is fine today — this is not a posture-correction walk. Rate tightness/"
                "pain before and after. Stop early if anything sharpens."
            ),
            biomechanical_focus="Low-impact conditioning that maintains tissue health without axial impact — reintroduces walking volume gently after a rest-heavy stretch.",
            progression="Comfortable throughout → 12 minutes next session.",
            regression="Any sharpening → reduce to 5 minutes, prioritise rest today.",
        ),
    ],
}

PLAN[16] = {
    "objective": "Stability Consolidation — Scapular Introduction",
    "phase": "Week 3: Flare Recovery & Reassessment Prep",
    "session_rpe_target": 4,
    "exercises": [
        UPPER_GLUTE_RELEASE,
        PIRIFORMIS_PNF,
        _ex(
            name="Glute Bridge",
            ex_type="reps",
            sets=3, reps=10, tempo="2-1-2", rest_seconds=60,
            mechanics=(
                "Lie on your back, knees bent, feet flat hip-width apart. "
                "Squeeze glutes FIRST, then lift hips — pelvis to shoulders in one straight line, "
                "no lower back arching. Lower with control. 10 reps, even count both directions."
            ),
            biomechanical_focus="Gluteus maximus activation without spinal loading — begins reversing the underactive-glute-max compensation pattern (imbalances) at a volume appropriate for the current flare.",
            progression="Pain-free, controlled → progress to single-leg version next session.",
            regression="Any lower-back involvement → reduce range, focus on the glute squeeze only.",
        ),
        SCAPULAR_WALL_SLIDE,
        _ex(
            name="Dead Bug",
            ex_type="hold_reps",
            sets=2, reps_in_set=8, hold_seconds=3, rest_seconds=45,
            laterality="alternating",
            mechanics=(
                "Lie on your back, arms toward the ceiling, knees and hips bent to 90 degrees. "
                "Slowly extend one arm overhead and the opposite leg out straight, keeping your "
                "lower back pressed flat into the floor throughout — this is the non-negotiable part. "
                "RIGHT LEG: keep a neutral/slight-internal-rotation bias as the leg extends, "
                "especially around 45 degrees of knee flexion — a clicking sensation has been "
                "noted right around there (finding #4). Move slowly and deliberately through that "
                "point rather than rushing past it. Return and repeat the other side. "
                "8 reps each side, even count."
            ),
            biomechanical_focus=(
                "Deep core (transversus abdominis) activation with contralateral limb movement — "
                "directly targets the underactive deep-core half of the compensation pattern. The "
                "right-side rotation cue now explicitly extends to this supine pattern, not just "
                "standing hip flexion, per the 2026-07-08 finding."
            ),
            progression="8 clean reps each side, no clicking, flat back maintained → add a 2-second hold at full extension.",
            regression="Low back lifts off the floor, or clicking is uncomfortable → reduce leg-extension range on the right.",
        ),
    ],
}

PLAN[17] = {
    "objective": "Thoracic Mobility + Active Recovery",
    "phase": "Week 3: Flare Recovery & Reassessment Prep",
    "session_rpe_target": 3,
    "exercises": [
        UPPER_GLUTE_RELEASE,
        _ex(
            name="Thread-the-Needle (Thoracic Rotation)",
            ex_type="hold",
            laterality="bilateral",
            sets=2, hold_seconds=30, rest_seconds=45,
            mechanics=(
                "On hands and knees. Slide one arm underneath your body, threading it through the "
                "gap between your other arm and knee, rotating your upper back and resting your "
                "shoulder and ear on the floor. Keep the hips still — rotation comes from the "
                "thoracic spine, not the lower back. Hold gently, breathe, then unwind slowly. "
                "Repeat the other side."
            ),
            biomechanical_focus="Rotational thoracic facet mobility (finding #3, #5) — directly addresses the mid-back component of the current flare without any lumbar rotation.",
            progression="Comfortable, smooth rotation → hold 45 seconds.",
            regression="Any pinching → reduce rotation range, keep the resting shoulder higher off the floor.",
        ),
        _ex(
            name="Child's Pose",
            ex_type="hold",
            sets=2, hold_seconds=60, rest_seconds=30,
            mechanics=(
                "Kneel, sit back toward your heels, and walk your hands forward, letting your "
                "chest sink gently toward the floor. Let your back round and lengthen passively — "
                "this is relaxation, not a forced stretch. Breathe into your back on each inhale."
            ),
            biomechanical_focus="Gentle passive lumbar and thoracic flexion decompression — a rest-oriented mobility position rather than an active loading pattern.",
            progression="Comfortable → hold 90 seconds.",
            regression="Knee discomfort → place a cushion behind the knees, or reduce hip-to-heel distance.",
        ),
        _ex(
            name="Controlled Walking",
            ex_type="duration",
            sets=1, duration_minutes=12, rest_seconds=0,
            mechanics=(
                "Easy-pace walk, 12 minutes, flat ground. Rate tightness/pain before and after. "
                "Today is about consistency, not pushing pace or distance."
            ),
            biomechanical_focus="Continued low-impact conditioning, building duration gradually from Day 15's 10 minutes.",
            progression="Comfortable throughout → 15 minutes next session.",
            regression="Any sharpening → return to 10 minutes.",
        ),
    ],
}

PLAN[18] = {
    "objective": "Hip Hinge + Scapular Integration",
    "phase": "Week 3: Flare Recovery & Reassessment Prep",
    "session_rpe_target": 4,
    "exercises": [
        UPPER_GLUTE_RELEASE,
        RIGHT_HIP_CAPSULE_REVISED,
        _ex(
            name="Wall-Supported Hip Hinge",
            ex_type="reps",
            sets=3, reps=10, tempo="3-1-3", rest_seconds=60,
            mechanics=(
                "Stand an arm's length from a wall, facing away from it. Hinge at the hips, "
                "reaching back to gently touch the wall with your hands, keeping the spine neutral "
                "throughout — this is a hip-driven movement, not a spinal one. Return by squeezing "
                "the glutes. 10 reps, controlled tempo."
            ),
            biomechanical_focus="Neutral-spine hip hinge pattern (cleared movement, services.rules) — the wall provides a proprioceptive range limit while lumbar control is re-established after the flare.",
            progression="Full range, pain-free → remove the wall, hinge to a comfortable range freely.",
            regression="Any discomfort → reduce range to a shallower hinge, wall contact sooner.",
        ),
        PRONE_Y_RAISE,
        _ex(
            name="Bird-Dog",
            ex_type="hold_reps",
            sets=3, reps_in_set=8, hold_seconds=5, rest_seconds=45,
            laterality="alternating",
            mechanics=(
                "On hands and knees. Extend one arm forward and the OPPOSITE leg straight back, "
                "keeping your back flat — no arching, no rotating the hips. Hold 5 seconds, "
                "return with control. 8 reps each side, even count."
            ),
            biomechanical_focus="Contralateral spinal stabilisation without spinal loading — a primary rehab movement for L5/S1, reintroduced at low volume after the flare.",
            progression="Stable, flat back throughout → extend hold to 8 seconds.",
            regression="Any wobble or back arching → reduce arm/leg range, keep limbs lower.",
        ),
    ],
}

PLAN[19] = {
    "objective": "Active Recovery — Tissue Quality",
    "phase": "Week 3: Flare Recovery & Reassessment Prep",
    "session_rpe_target": 3,
    "exercises": [
        PIRIFORMIS_PNF,
        ISCHIAL_RELEASE,
        _ex(
            name="Cat-Cow",
            ex_type="reps",
            sets=2, reps=10, tempo="4-0-4", rest_seconds=45,
            mechanics=(
                "On hands and knees. CAT: exhale, round the spine, tuck chin and tailbone. "
                "COW: inhale, let the belly drop, gently lift head and tailbone. Move only to a "
                "comfortable range — never force end-range extension."
            ),
            biomechanical_focus="Gentle segmental lumbar and thoracic mobilisation without axial load — a low-effort maintenance day between the more demanding sessions either side of it.",
            progression="Pain-free → 15 reps, add a 2-second pause at each end.",
            regression="Extension discomfort → Cat position only, skip the Cow phase.",
        ),
        _ex(
            name="Prone Decompression Breathing",
            ex_type="duration",
            sets=1, duration_minutes=4, rest_seconds=0,
            mechanics=(
                "Lie face down, arms by your sides or folded under your forehead. Breathe deeply "
                "into your lower back, letting the belly expand into the floor on each inhale. "
                "Completely passive — no active movement."
            ),
            biomechanical_focus="Passive lumbar extension and psoas inhibition via diaphragmatic breathing — a purely restorative close to a deliberately light day.",
            progression="Comfortable → next session, add passive cobra (hands under shoulders, gentle press-up).",
            regression="Discomfort face-down → place a folded towel under the abdomen, or stay supine instead.",
            warning="Stop immediately if leg tingling or numbness occurs in this position.",
        ),
    ],
}

PLAN[20] = {
    "objective": "Neuromuscular Integration — Glute + Core + Shoulder",
    "phase": "Week 3: Flare Recovery & Reassessment Prep",
    "session_rpe_target": 5,
    "exercises": [
        UPPER_GLUTE_RELEASE,
        COXA_SALTANS_DRILL,
        _ex(
            name="Single-Leg Glute Bridge",
            ex_type="hold_reps",
            laterality="unilateral",
            sets=2, reps_in_set=8, hold_seconds=2, rest_seconds=60,
            mechanics=(
                "Same setup as the bilateral bridge, but extend one leg straight and bridge on "
                "the other. The RIGHT side has been noticeably harder than the left in prior "
                "sessions (2026-07-06) — expect that difference, don't force the right side to "
                "match the left's range, just keep the pelvis level. 8 reps each side, even count."
            ),
            biomechanical_focus="Unilateral glute max strength — directly tests and trains the right-left asymmetry already documented, at a low volume appropriate for this stage.",
            progression="Pelvis stays level both sides → add a 2-second hold at the top.",
            regression="Pelvis drops/rotates on the right → reduce to bilateral bridge for another session.",
        ),
        SCAPULAR_WALL_SLIDE,
        _ex(
            name="Dead Bug",
            ex_type="hold_reps",
            sets=2, reps_in_set=8, hold_seconds=3, rest_seconds=45,
            laterality="alternating",
            mechanics=(
                "Same as Day 16 — lower back flat throughout, neutral/slight-internal rotation "
                "bias on the right leg through the ~45-degree range. 8 reps each side, even count."
            ),
            biomechanical_focus="Repeat exposure to reinforce the neutral-rotation motor pattern through the supine leg-extension range flagged in finding #4.",
            progression="8 clean reps each side, no clicking → add a 2-second hold at full extension.",
            regression="Clicking or discomfort → reduce leg-extension range on the right.",
        ),
        _ex(
            name="Wall Sit",
            ex_type="hold",
            sets=2, hold_seconds=60, rest_seconds=60,
            mechanics=(
                "Back against a wall, knees at roughly 90 degrees, thighs parallel to the floor. "
                "Hold 60 seconds — confirmed as sufficient volume for this exercise (2026-07-08 "
                "feedback), not pushed further without a specific reason to."
            ),
            biomechanical_focus="Isometric quad/glute endurance without spinal loading — a stable, well-tolerated hold at an already-confirmed appropriate dose.",
            progression="Consistently easy at 60s across 2+ sessions → consider single-leg-assisted variation, not just longer duration.",
            regression="Any discomfort → reduce to 45 seconds.",
        ),
    ],
}

PLAN[21] = {
    "objective": "Week 3 Self-Assessment — Reassessment Prep",
    "phase": "Week 3: Flare Recovery & Reassessment Prep",
    "session_rpe_target": 5,
    "exercises": [
        RIGHT_HIP_CAPSULE_REVISED,
        COXA_SALTANS_DRILL,
        _ex(
            name="McGill Big 3 — Quality Screen",
            ex_type="reps",
            sets=1, reps=8, rest_seconds=60,
            mechanics=(
                "One high-quality set of each: (1) McGill Curl-Up x 8 reps x 8-second hold each. "
                "(2) Bird-Dog x 8 each side x 8-second hold. (3) Side Bridge x 40 seconds each side. "
                "A quality screen, not a maximal-effort test. Compare ease and form to both the "
                "Day 3 baseline and the Day 14 screen — log observations, including whether the "
                "recent flare changed anything here."
            ),
            biomechanical_focus="Functional assessment of the foundational spinal stability system — now with two prior data points (Day 3, Day 14) to compare against, giving a genuine trend rather than a single snapshot.",
            progression="Equal or better than Day 14 → supports Stage 2 readiness on this measure.",
            regression="Worse than Day 14 → note the specific exercise/side; flag for physio discussion before advancing.",
        ),
        _ex(
            name="Single-Leg Balance (Eyes Closed)",
            ex_type="hold",
            laterality="unilateral",
            sets=2, hold_seconds=60, rest_seconds=45,
            mechanics=(
                "Stand on one leg, no wall support. Close your eyes once stable. Compare to the "
                "Day 14 result."
            ),
            biomechanical_focus="Proprioceptive re-check — confirms the Day 14 result held (or improved) through the flare and this recovery week.",
            progression="60 seconds eyes closed, clean, matching or beating Day 14 → criterion re-confirmed.",
            regression="Notably worse than Day 14 → perform eyes-open, document for physiotherapist.",
        ),
        _ex(
            name="Hip Hinge Full Range Assessment",
            ex_type="reps",
            sets=2, reps=10, tempo="3-1-3", rest_seconds=60,
            mechanics=(
                "Full hip hinge, no wall, to maximum comfortable range. Hold 1 second at the "
                "bottom, return with a glute squeeze. Compare pain-free range to Day 14 — has it "
                "held up through the flare, or regressed? BIOMECHANICAL CHECK: right vs left range, "
                "and whether the right-side ischial release sensation is still present."
            ),
            biomechanical_focus="Hip hinge range and posterior chain capacity — the same functional test used at Day 14, now re-checked after the flare to confirm it's genuinely safe to progress.",
            progression="Full range, pain <=2/10, matching or beating Day 14 → criterion re-confirmed for Stage 2.",
            regression="Pain >3/10 at any range, or worse than Day 14 → document the range where pain begins, discuss with physiotherapist before advancing.",
        ),
        _ex(
            name="5-Minute Walk + Stair Assessment",
            ex_type="duration",
            sets=1, duration_minutes=7, rest_seconds=0,
            mechanics=(
                "Walk briskly for 5 minutes, then up and down a flight of stairs twice at a "
                "normal pace. Rate pain: start of walk, end of walk, top of stairs, bottom of "
                "stairs. Compare directly to both the Day 7 and Day 14 scores — this is the same "
                "functional outcome measure, now with three data points across the flare."
            ),
            biomechanical_focus="Integrated functional outcome assessment — the primary clinical benchmark, now showing the trend across Day 7, Day 14, and this recovery check.",
            progression="Pain <=2/10 throughout, matching or beating Day 14 → Stage 1 genuinely complete, ready for the Stage 2 reassessment conversation.",
            regression="Pain >3/10 on stairs, or worse than Day 14 → discuss with physiotherapist before progressing; do not start Stage 2 on this data.",
        ),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
#  STAGE 2A — 28-DAY GYM STRENGTH BLOCK (Phase 2, Days 1-28, starts 2026-07-20)
#
#  Cleared 2026-07-19 (Day 21 reassessment passed, physiotherapist signed off
#  on external load — see patient_profile.PROFILE["stage_transitions"]).
#  Deliberately decoupled from the previously-discussed 10km race periodization:
#  NO running is introduced in this block. That decision, and Stage 2B timing,
#  are deferred to a later reassessment conversation (see Day 28 below).
#
#  EQUIPMENT: Commercial gym — dumbbells, cable stack, lat pulldown, bench,
#  barbell/plates for hip thrust. ACWR ceiling: 1.3. Session RPE ceiling: 8/10.
#  Starting loads are a conservative fraction of the 2025 strength-year ceiling
#  (Input_files/2025-training-year.md) — a ceiling, not a starting point, per
#  docs/clinical_profile_weighting.md #3.
#
#  Two right-hip mechanisms, kept distinct (do not conflate their cues):
#    - Coxa Saltans (iliopsoas snap, hip flexion >60° + external rotation,
#      standing OR supine): needs an in-movement neutral/internal-rotation
#      cue. Applies to Goblet Squat depth and Bulgarian Split Squat front leg.
#    - Posterior capsule / ischial click (hip hinge, opposite leg extended):
#      addressed by the pre-session release, not an in-movement cue — a click
#      during RDL is an expected structural release, not a stop signal (a
#      sharp lumbar symptom is the actual stop signal).
#
#  No overhead/standing press this block — deliberate. Overhead press is
#  Stage-2 "caution" per services/rules.py (technically usable), but the
#  Latarjet history + the 2025 log's own note ("overhead press exposes
#  instability, left tilt") + the left rhomboid strain that occurred
#  specifically under overhead load argue for Incline DB Press (back-
#  supported, no lumbar-extension moment) as this block's pressing pattern
#  instead, with heavy scapular-control prerequisite work alongside it.
#
#  Progression: fast-track lifts (documented strengths in the 2025 log — Hip
#  Thrust, Lat Pulldown, DB Row, Face Pull) get +2.5kg every weekly exposure.
#  Slow-track lifts (documented breakdown patterns — Goblet Squat, RDL,
#  Incline Press, Bulgarian Split Squat) get +2.5kg only every OTHER exposure;
#  off-weeks hold load and add a tempo/pause constraint instead. Core work is
#  sequenced LAST in every loaded session, deliberately post-fatigue — trains
#  TA/multifidus endurance under fatigue, since "deep core switches off under
#  fatigue" and "lumbar dominates at moderate load" are the documented weak
#  links in the 2025 movement-pattern analysis, and training them fresh
#  doesn't address that.
# ─────────────────────────────────────────────────────────────────────────────

PLAN_STAGE2: dict[int, dict] = {}

_S2_RELEASE_ALWAYS = [UPPER_GLUTE_RELEASE, PIRIFORMIS_PNF]


def _s2_recovery_day(objective: str, template: str) -> dict:
    """Active-recovery day — always-include release only (not hip-focused/
    loaded enough to need the add-on release work), alternating between two
    light content templates so the 14 recovery days in this block aren't
    pure repetition."""
    walk_minutes = 15 if template == "A" else 20
    exercises = list(_S2_RELEASE_ALWAYS)
    if template == "A":
        exercises += [
            _ex(
                name="Dead Bug",
                ex_type="hold_reps",
                laterality="alternating",
                sets=2, reps_in_set=8, hold_seconds=3, rest_seconds=45,
                mechanics=(
                    "Lower back flat throughout. Neutral/slight-internal-rotation bias on the "
                    "right leg through the ~45-degree knee-extension range (finding #4 — the same "
                    "click mechanism shows up here, not just standing). 8 reps each side, even count."
                ),
                biomechanical_focus="Maintenance dose of the neutral-rotation motor pattern through the supine leg-extension range, on days without loaded hip work.",
                progression="8 clean reps each side, no clicking → add a 2-second hold at full extension.",
                regression="Clicking or discomfort → reduce leg-extension range on the right.",
            ),
            _ex(
                name="Pallof Press Hold (Doorframe)",
                ex_type="hold",
                laterality="unilateral",
                sets=2, hold_seconds=30, rest_seconds=45,
                mechanics="Band or towel anchored at chest height, press straight out and hold, resisting rotation. Bodyweight/band anti-rotation — no cable load, distinct from the loaded cable Pallof press on gym days.",
                biomechanical_focus="Anti-rotation core control on a light day — addresses finding #5 without adding session load.",
                progression="Rock solid at 30s → step further from the anchor to increase lever arm.",
                regression="Trunk rotates → step closer to the anchor.",
            ),
            _ex(
                name="Cat-Cow",
                ex_type="reps",
                sets=2, reps=10, tempo="4-0-4", rest_seconds=45,
                mechanics="Comfortable range only, never forcing end-range lumbar extension.",
                biomechanical_focus="Gentle segmental lumbar mobilisation between loaded sessions.",
                progression="Pain-free → 15 reps, add a 2-second pause at each end.",
                regression="Extension discomfort → Cat position only.",
            ),
            _ex(
                name="Thoracic Extension (Rolled Towel)",
                ex_type="hold",
                sets=2, hold_seconds=60, rest_seconds=45,
                mechanics="Rolled towel under the mid-back, arms overhead, allow gentle passive thoracic extension.",
                biomechanical_focus="Addresses the T6-T10 facet compression finding — kept in the program even though the block's headline is now loaded strength work, since the mid-back strain is a recurring pattern (3rd occurrence), not a one-off.",
                progression="Comfortable → thicker towel roll for more extension.",
                regression="Any lumbar (not thoracic) sensation → thinner towel roll.",
            ),
        ]
    else:
        exercises += [
            _ex(
                name="Scapular Wall Slide",
                ex_type="reps",
                sets=2, reps=10, tempo="3-1-3", rest_seconds=45,
                mechanics="Wrists/elbows stay in contact with the wall throughout — bodyweight-only scapular control, no external load, on a day between loaded sessions.",
                biomechanical_focus="Maintenance dose for the standing scapular-control requirement (finding #6) — this is not optional conditioning, it's how the Latarjet repair stays stable.",
                progression="Full contact maintained → add a 2-second hold at the top.",
                regression="Contact lost early → reduce range.",
            ),
            _ex(
                name="Thread-the-Needle (Thoracic Rotation)",
                ex_type="reps",
                laterality="unilateral",
                sets=2, reps=8, rest_seconds=45,
                mechanics="Hands and knees, thread one arm under the body then rotate it up toward the ceiling, following it with your eyes. Comfortable range only.",
                biomechanical_focus="Thoracic rotation without lumbar rotation under load — segmental mobility maintenance on a light day.",
                progression="Smooth throughout → add a 2-second hold at full rotation.",
                regression="Any lumbar rotation compensation → reduce range.",
            ),
            _ex(
                name="Full Side Bridge",
                ex_type="hold",
                laterality="unilateral",
                sets=2, hold_seconds=30, rest_seconds=45,
                mechanics="Full side plank, both legs extended, hips lifted and held level.",
                biomechanical_focus="Lateral core endurance — the same obliques/QL pattern the 2025 log documents as a genuine strength, maintained on a light day.",
                progression="Stable throughout → increase to 40 seconds.",
                regression="Hips sag → regress to the bent-knee version.",
            ),
            _ex(
                name="Child's Pose",
                ex_type="hold",
                sets=1, hold_seconds=60, rest_seconds=0,
                mechanics="Kneel, sit back toward your heels, arms extended forward, let the low back relax into gentle flexion.",
                biomechanical_focus="Passive restorative close to a light day.",
                progression="N/A — restorative hold, not a progressed exercise.",
                regression="Knee discomfort → wider knee stance or place a cushion behind the knees.",
            ),
        ]
    exercises.append(
        _ex(
            name="Controlled Walking",
            ex_type="duration",
            sets=1, duration_minutes=walk_minutes, rest_seconds=0,
            mechanics=f"Brisk, comfortable-pace walk, {walk_minutes} minutes continuous. No running — running is an explicitly deferred decision for a later block, not part of Stage 2A.",
            biomechanical_focus="Low-impact conditioning and active recovery between loaded sessions, without the axial impact running would introduce.",
            progression="Pain-free throughout → next block may introduce run/walk intervals (separate decision).",
            regression="Any discomfort → reduce to a shorter, slower walk.",
        )
    )
    return {
        "objective": objective,
        "phase": "Stage 2A — Gym Strength Block",
        "session_rpe_target": 3,
        "is_gym_session": False,
        "day_type": "rest",
        "exercises": exercises,
    }


def _s2_session_a(week: int) -> dict:
    """Squat + Press + Core. Goblet Squat and Incline Press are slow-track
    (2025 log's documented breakdown patterns); Face Pull is fast-track."""
    squat_kg  = {1: 10.0, 2: 10.0, 3: 12.5, 4: 12.5}[week]
    squat_tempo = "3-1-1" if week in (1, 3) else "3-2-1"
    press_kg  = {1: 8.0, 2: 8.0, 3: 10.0, 4: 10.0}[week]
    face_pull_kg = {1: 10.0, 2: 12.5, 3: 15.0, 4: 17.5}[week]
    pallof_kg = {1: 7.5, 2: 7.5, 3: 10.0, 4: 10.0}[week]
    side_bridge_hold = {1: 30, 2: 35, 3: 40, 4: 45}[week]
    return {
        "objective": f"Stage 2A Week {week} — Squat + Press + Core",
        "phase": "Stage 2A — Gym Strength Block",
        "session_rpe_target": 6 if week < 4 else 7,
        "is_gym_session": True,
        "day_type": "main",
        "exercises": [
            UPPER_GLUTE_RELEASE, PIRIFORMIS_PNF, RIGHT_HIP_CAPSULE_REVISED, COXA_SALTANS_DRILL,
            _ex(
                name="Goblet Squat",
                ex_type="reps",
                sets=3, reps=8, tempo=squat_tempo, rest_seconds=90,
                weight_kg=squat_kg,
                equipment_type="dumbbell",
                rep_min=8, rep_max=10,
                mechanics=(
                    "Hold one dumbbell vertically at your chest. Squat to a comfortable depth "
                    "with a brief pause at the bottom. At depth your right hip passes >60° "
                    "flexion — actively keep the right thigh neutral or slightly internally "
                    "rotated, do not let it drift into external rotation (Coxa Saltans cue). "
                    "Brace before you descend, not after — the 2025 log shows bracing collapsing "
                    "from rep 6 onward under load; this pause tempo trains bracing before load increases."
                ),
                biomechanical_focus="Squat pattern retraining — excellent depth/mobility already documented, but bracing collapse under load and a right-side hip shift are the identified weak links this directly targets.",
                progression="8 clean reps, brace held through the pause, no right-hip drift → next exposure adds load or tempo per the block's slow-track schedule.",
                regression="Bracing fails before rep 6, or right hip drifts into external rotation → reduce depth slightly and/or hold current load an extra week.",
            ),
            _ex(
                name="Incline DB Press",
                ex_type="reps",
                sets=3, reps=10, rest_seconds=75,
                weight_kg=press_kg,
                equipment_type="dumbbell",
                rep_min=10, rep_max=12,
                mechanics=(
                    "Bench set to a moderate incline. Retract the shoulder blades into the bench "
                    "before every rep. If the right shoulder wants to roll forward or sag at the "
                    "top, reduce range rather than push through it. No standing or seated overhead "
                    "pressing this block — this back-supported incline pattern is the deliberate "
                    "substitute (see block notes above)."
                ),
                biomechanical_focus="Conservative, scapular-control-first pressing given the Latarjet history and the 2025 log's documented left-tilt instability under overhead load — directly ceiling-referenced against the 18kg x12 peak.",
                progression="10 clean reps, scapulae stay retracted, no shoulder roll → next exposure adds load or tempo per the block's slow-track schedule.",
                regression="Shoulder rolls forward or sags at the top → reduce range of motion before reducing load.",
            ),
            _ex(
                name="Face Pull (Cable)",
                ex_type="reps",
                sets=3, reps=12, rest_seconds=60,
                weight_kg=face_pull_kg,
                equipment_type="cable",
                increment_size=1, increment_unit="unit",
                rep_min=12, rep_max=15,
                mechanics="Cable at upper-chest height. Pull toward your face, elbows high, squeezing the shoulder blades together and down at the end.",
                biomechanical_focus="Scapular control and rear-delt/rotator-cuff work — always paired with pressing per finding #6, and a documented strength pattern (fast-track progression).",
                progression="12 clean reps, full scapular squeeze → +1 unit next exposure (fast-track). This machine's scale is arbitrary units, not kg — see increment_unit.",
                regression="Shrugging instead of scapular squeeze → reduce load until the movement is clean.",
            ),
            _ex(
                name="Pallof Press (Cable)",
                ex_type="reps",
                laterality="unilateral",
                sets=3, reps=10, rest_seconds=60,
                weight_kg=pallof_kg,
                equipment_type="cable",
                increment_size=1, increment_unit="unit",
                rep_min=10, rep_max=12,
                mechanics="Cable at chest height, stand side-on, press the handle straight out and back in without letting the cable rotate your trunk.",
                biomechanical_focus="Anti-rotation core control under real load — addresses finding #5 and the rotation-under-load caution with a controlled, non-rotational pattern.",
                progression="10 reps each side with zero trunk rotation → +1 unit next exposure. This machine's scale is arbitrary units, not kg — see increment_unit.",
                regression="Any trunk rotation → reduce load until the press is completely still.",
            ),
            _ex(
                name="McGill Curl-Up (Progressed)",
                ex_type="hold_reps",
                sets=3, reps_in_set=8, hold_seconds=10, rest_seconds=45,
                mechanics="One knee bent, hands under the low back, brace and lift only the head/shoulders slightly — a bracing hold, not a crunch. Deliberately placed last, after the squat/press work, to train bracing under real fatigue rather than fresh.",
                biomechanical_focus="Deep core (TA/multifidus) endurance specifically under fatigue — the documented weak link ('switches off under fatigue') that undertrained core work done fresh doesn't address.",
                progression="10-second holds feel controlled, no lumbar movement → hold for 12 seconds.",
                regression="Low back moves during the hold → reduce hold time, prioritise a still spine.",
            ),
            _ex(
                name="Full Side Bridge",
                ex_type="hold",
                laterality="unilateral",
                sets=3, hold_seconds=side_bridge_hold, rest_seconds=45,
                mechanics="Full side plank, both legs extended, hips lifted and held level, forearm supporting.",
                biomechanical_focus="Lateral core endurance under post-squat/press fatigue — obliques/QL are a documented strength; this trains that strength to hold up when the rest of the system is already tired.",
                progression=f"Full {side_bridge_hold}s stable both sides → increase hold next exposure.",
                regression="Hips sag or shake before time is up → reduce hold time.",
            ),
        ],
    }


def _s2_session_b(week: int) -> dict:
    """Hinge + Pull + Core. RDL is slow-track; Hip Thrust/Lat Pulldown/DB Row
    are fast-track (documented strengths in the 2025 log)."""
    rdl_kg    = {1: 10.0, 2: 10.0, 3: 12.5, 4: 12.5}[week]
    rdl_tempo = "3-1-2" if week in (1, 3) else "3-2-2"
    thrust_kg = {1: 20.0, 2: 22.5, 3: 25.0, 4: 27.5}[week]
    pulldown_kg = {1: 25.0, 2: 27.5, 3: 30.0, 4: 32.5}[week]
    row_kg    = {1: 12.5, 2: 15.0, 3: 17.5, 4: 20.0}[week]
    return {
        "objective": f"Stage 2A Week {week} — Hinge + Pull + Core",
        "phase": "Stage 2A — Gym Strength Block",
        "session_rpe_target": 6 if week < 4 else 7,
        "is_gym_session": True,
        "day_type": "main",
        "exercises": [
            UPPER_GLUTE_RELEASE, PIRIFORMIS_PNF, RIGHT_HIP_CAPSULE_REVISED, ISCHIAL_RELEASE,
            _ex(
                name="Romanian Deadlift (DB)",
                ex_type="reps",
                sets=3, reps=10, tempo=rdl_tempo, rest_seconds=90,
                weight_kg=rdl_kg,
                equipment_type="dumbbell",
                mechanics=(
                    "One dumbbell in each hand, hinge from the hips keeping the DBs close to your "
                    "shins. Stop the descent the instant your lower back wants to round — depth is "
                    "whatever range you can keep neutral. A right posterior-hip/sit-bone sensation "
                    "here is an expected structural release (finding #2), not a stop signal; a sharp "
                    "lumbar symptom is the actual stop signal. Kept well below the 70-90kg range "
                    "where the 2025 log shows the lumbar taking over and the glutes not finishing lockout."
                ),
                biomechanical_focus="Hinge pattern retraining at light load, where the 2025 log shows form is genuinely good — the goal is to keep it good as load returns, not to rush toward the range where it previously broke down.",
                progression="10 clean reps, neutral spine throughout, glutes finish the lockout → next exposure adds load or tempo per the block's slow-track schedule.",
                regression="Lower back rounds or glutes don't finish lockout → hold current load, add the tempo constraint instead.",
            ),
            _ex(
                name="Hip Thrust (Loaded)",
                ex_type="reps",
                sets=3, reps=10, rest_seconds=75,
                weight_kg=thrust_kg,
                equipment_type="plate",
                mechanics="Upper back on a bench, bar/plate across the hips. Drive through the heels, squeeze the glutes hard at lockout with a 2-second pause, don't hyperextend the lower back at the top.",
                biomechanical_focus="A documented strength pattern (2025 log: glutes strong in isolation, 50kg+ tolerated well) — fast-tracked accordingly, and it directly trains the hip-extension lockout that under-fires in the RDL and squat.",
                progression="10 clean reps, full glute lockout, no lumbar hyperextension → +2.5kg next exposure (fast-track).",
                regression="Lumbar hyperextends at lockout → reduce load until the glutes (not the low back) are finishing the rep.",
            ),
            _ex(
                name="Lat Pulldown",
                ex_type="reps",
                sets=3, reps=10, rest_seconds=60,
                weight_kg=pulldown_kg,
                equipment_type="cable",
                mechanics="Wide or neutral grip, pull to the upper chest, squeeze the shoulder blades down and together at the bottom before controlling the return.",
                biomechanical_focus="Scapular depression strengthening — the specific weakness flagged in the 2025 log's scapular analysis, and a well-tolerated pattern (fast-track).",
                progression="10 clean reps, full scapular depression each rep → +2.5kg next exposure (fast-track).",
                regression="Using momentum instead of scapular depression → reduce load.",
            ),
            _ex(
                name="Single-Arm DB Row",
                ex_type="reps",
                laterality="unilateral",
                sets=3, reps=10, rest_seconds=60,
                weight_kg=row_kg,
                equipment_type="dumbbell",
                mechanics="Supported on a bench, row the dumbbell to your hip, leading with the elbow, full control on the way down. Even rep count both arms.",
                biomechanical_focus="Unilateral pulling strength and scapular retraction — complements the bilateral pulldown, fast-tracked as a well-tolerated pattern.",
                progression="10 clean reps each arm, no trunk rotation → +2.5kg next exposure (fast-track).",
                regression="Trunk rotates to complete the rep → reduce load.",
            ),
            _ex(
                name="Dead Bug",
                ex_type="hold_reps",
                laterality="alternating",
                sets=3, reps_in_set=8, hold_seconds=3, rest_seconds=45,
                mechanics="Placed after the hinge work, deliberately — lower back flat throughout, neutral/slight-internal-rotation bias on the right leg through the ~45-degree knee-extension range. 8 reps each side, even count.",
                biomechanical_focus="Bracing under post-hinge fatigue, and continued reinforcement of the neutral-rotation motor pattern through the supine leg-extension range (finding #4).",
                progression="8 clean reps each side, flat back maintained, no clicking → add a 2-second hold at full extension.",
                regression="Low back arches off the floor, or clicking → reduce leg-extension range on the right.",
            ),
            _ex(
                name="Pallof Press Hold (Doorframe)",
                ex_type="hold",
                laterality="unilateral",
                sets=3, hold_seconds=30, rest_seconds=45,
                mechanics="Band or towel anchored at chest height, press straight out and hold, resisting rotation. Bodyweight/band — the lighter anti-rotation variant, done after the loaded Pallof work already appears in Session A's weekly rotation.",
                biomechanical_focus="Anti-rotation endurance under post-hinge fatigue.",
                progression="Rock solid at 30s → step further from the anchor.",
                regression="Trunk rotates → step closer to the anchor.",
            ),
        ],
    }


def _s2_session_c(week: int) -> dict:
    """Unilateral/Glute + Scapular + Core. Bulgarian Split Squat is slow-
    track and stays bodyweight through Week 2 per the block design."""
    bss_kg = {1: None, 2: None, 3: 2.5, 4: 2.5}[week]
    bss_note = "bodyweight" if bss_kg is None else f"a {bss_kg}kg dumbbell in each hand"
    bridge_hold = {1: 2, 2: 2, 3: 3, 4: 3}[week]
    yraise_kg = {1: None, 2: None, 3: 1.0, 4: 1.0}[week]
    band_tier = "Green" if week <= 2 else "Blue"
    band_label = "Light" if week <= 2 else "Medium"
    return {
        "objective": f"Stage 2A Week {week} — Unilateral/Glute + Scapular + Core",
        "phase": "Stage 2A — Gym Strength Block",
        "session_rpe_target": 5 if week < 4 else 6,
        "is_gym_session": True,
        "day_type": "main",
        "exercises": [
            UPPER_GLUTE_RELEASE, PIRIFORMIS_PNF, RIGHT_HIP_CAPSULE_REVISED, COXA_SALTANS_DRILL,
            _ex(
                name="Bulgarian Split Squat",
                ex_type="reps",
                laterality="unilateral",
                sets=3, reps=8, rest_seconds=75,
                weight_kg=bss_kg,
                equipment_type="dumbbell",
                mechanics=(
                    f"Rear foot elevated on a bench, {bss_note}. When the RIGHT leg is forward, "
                    "the working hip crosses 60 degrees of flexion at the bottom of the rep — apply "
                    "the same neutral/slight-internal-rotation cue as the goblet squat (Coxa Saltans). "
                    "8 reps each leg, even count."
                ),
                biomechanical_focus="Single-leg strength and right-side monitoring in a loaded, hip-flexion-heavy pattern — the same mechanism as the standing coxa saltans finding, now under real single-leg load.",
                progression="8 clean reps each leg, no click on the right, level pelvis → progress load per the block's slow-track schedule (bodyweight through Week 2, then add load).",
                regression="Click on the right, or pelvis drops → reduce depth before reducing load.",
            ),
            _ex(
                name="Single-Leg Glute Bridge",
                ex_type="hold_reps",
                laterality="unilateral",
                sets=3, reps_in_set=8, hold_seconds=bridge_hold, rest_seconds=60,
                mechanics=(
                    "One leg extended straight, bridge on the other. The right side has been "
                    "noticeably harder than the left in prior sessions — expect that difference, "
                    "keep the pelvis level rather than forcing the right to match the left's range. "
                    "8 reps each side, even count."
                ),
                biomechanical_focus="Unilateral glute max strength, continuing to test and train the documented right-left asymmetry, now within the loaded block.",
                progression="Pelvis stays level both sides → increase hold duration next exposure.",
                regression="Pelvis drops or rotates on the right → reduce hold time, prioritise level pelvis.",
            ),
            _ex(
                name="Scapular Wall Slide",
                ex_type="reps",
                sets=2, reps=10, tempo="3-1-3", rest_seconds=45,
                mechanics="Wrists/elbows stay in contact with the wall throughout — bodyweight-only, no external load.",
                biomechanical_focus="Standing scapular-control requirement for the Latarjet-repaired shoulder (finding #6) — maintained every week regardless of loaded-lift progression.",
                progression="Full contact maintained pain-free → add a 2-second hold at the top.",
                regression="Contact lost early or shoulder discomfort → reduce range.",
            ),
            _ex(
                name="Prone Y-Raise (Scapular)",
                ex_type="hold_reps",
                sets=2, reps_in_set=8, hold_seconds=3, rest_seconds=45,
                weight_kg=yraise_kg,
                equipment_type="dumbbell",
                mechanics="Face down, arms overhead in a Y, lift a few inches and squeeze the lower shoulder blades together, hold, lower with control. Low back stays relaxed — this is a scapular movement, not a back extension.",
                biomechanical_focus="Lower trapezius strengthening — the specific weak link in the right shoulder's eccentric control flagged in the 2025 log.",
                progression="Clean reps, no lumbar compensation → small load addition next exposure.",
                regression="Low back arches to compensate → reduce lift height and/or load before adding more.",
                warning="Stop if this produces lumbar extension discomfort — reduce lift height immediately.",
            ),
            _ex(
                name="Lateral Band Walk",
                ex_type="reps",
                sets=2, reps=10, rest_seconds=45,
                equipment_type="band",
                band_tier=band_tier,
                mechanics=f"Band around the ankles or just above the knees, athletic stance, step sideways maintaining tension throughout — {band_tier} band ({band_label}). 10 steps each direction.",
                biomechanical_focus="Glute medius strengthening, complementing the release-then-activate sequencing — the upper glute/TFL is released pre-session, this activates glute max's synergist without letting the overactive medius take back over.",
                progression="Full tension held, no hip hike → step up a band level.",
                regression="Hip hikes or band tension is lost → step down a band level.",
            ),
            _ex(
                name="Bird-Dog",
                ex_type="hold_reps",
                laterality="alternating",
                sets=3, reps_in_set=8, hold_seconds=8, rest_seconds=45,
                mechanics="Hands and knees, extend opposite arm and leg, neutral spine throughout, hold, return with control.",
                biomechanical_focus="Contralateral core stability — a documented strength pattern, used here as the week's final core finisher after unilateral leg and scapular work.",
                progression="8 clean reps each side, no lumbar rotation → add a 2-second hold.",
                regression="Lumbar rotates or hips shift → reduce reach distance.",
            ),
            _ex(
                name="Side Bridge with Hip Dip",
                ex_type="hold_reps",
                laterality="unilateral",
                sets=2, reps_in_set=6, hold_seconds=3, rest_seconds=45,
                mechanics="Side plank position, dip the hips toward the floor and lift back to the held position, controlled throughout.",
                biomechanical_focus="Lateral core control through a small range of motion — closes out the session's core work with a dynamic (not purely static) lateral pattern.",
                progression="Clean control both sides → add a rep.",
                regression="Loss of control on the dip → reduce range of the dip.",
            ),
        ],
    }


for _week in (1, 2, 3, 4):
    _base = (_week - 1) * 7
    PLAN_STAGE2[_base + 1] = _s2_session_a(_week)
    PLAN_STAGE2[_base + 2] = _s2_recovery_day(f"Active Recovery — Week {_week}", "A")
    PLAN_STAGE2[_base + 3] = _s2_session_b(_week)
    PLAN_STAGE2[_base + 4] = _s2_recovery_day(f"Active Recovery — Week {_week}", "B")
    PLAN_STAGE2[_base + 5] = _s2_session_c(_week)
    PLAN_STAGE2[_base + 6] = _s2_recovery_day(f"Active Recovery — Week {_week}", "A")
    PLAN_STAGE2[_base + 7] = _s2_recovery_day(f"Active Recovery — Week {_week}", "B")

# Day 14 — mid-block checkpoint. Light functional re-check, not a full
# battery: confirms nothing has regressed under the new external load before
# continuing into weeks 3-4, and gives an explicit place to log working
# loads reached so far.
PLAN_STAGE2[14] = {
    "objective": "Mid-Block Checkpoint — Light Functional Re-Check",
    "phase": "Stage 2A — Gym Strength Block",
    "session_rpe_target": 2,
    "day_type": "test",
    "exercises": [
        UPPER_GLUTE_RELEASE, PIRIFORMIS_PNF,
        _ex(
            name="Hip Hinge Full Range Assessment",
            ex_type="reps",
            sets=1, reps=10, tempo="3-1-3", rest_seconds=60,
            mechanics="Full hip hinge to maximum comfortable range, light effort only. Compare pain-free range and any right-side sensation to before this block started.",
            biomechanical_focus="Confirms the hinge pattern is holding up under two weeks of real external load before progressing further.",
            progression="Pain-free, matching or better than block start → continue into Weeks 3-4 as planned.",
            regression="Worse than block start → hold current loads for Week 3 rather than progressing, and flag to physiotherapist if it doesn't recover by Week 3.",
        ),
        _ex(
            name="Single-Leg Balance (Eyes Closed)",
            ex_type="hold",
            laterality="unilateral",
            sets=1, hold_seconds=60, rest_seconds=45,
            mechanics="Stand on one leg, eyes closed once stable. Compare to your Stage 1 baseline.",
            biomechanical_focus="Proprioceptive check that loaded training hasn't degraded balance/control.",
            progression="Matching or beating the Stage 1 baseline → no concerns.",
            regression="Notably worse → note it and mention at the Day 28 reassessment.",
        ),
        _ex(
            name="Controlled Walking",
            ex_type="duration",
            sets=1, duration_minutes=15, rest_seconds=0,
            mechanics="Log working loads reached on all six primary lifts so far (Goblet Squat, Incline DB Press, RDL, Hip Thrust, Lat Pulldown, Single-Arm DB Row) during this walk's cool-down, then walk 15 minutes at a comfortable pace.",
            biomechanical_focus="Low-impact conditioning; the walk itself is also the natural pause point to log the checkpoint data.",
            progression="N/A — logging checkpoint.",
            regression="N/A.",
        ),
    ],
}

# Day 28 — full reassessment. Mirrors Stage 1's Day 21 battery format so the
# same functional measures are comparable across both stages, plus final
# working-load logging on every primary lift. Output feeds two decisions
# explicitly NOT made in this plan: running introduction, and Stage 2B vs.
# extending Stage 2A.
PLAN_STAGE2[28] = {
    "objective": "Stage 2A Reassessment — Final Working Loads + Functional Screen",
    "phase": "Stage 2A — Gym Strength Block",
    "session_rpe_target": 4,
    "day_type": "test",
    "exercises": [
        RIGHT_HIP_CAPSULE_REVISED,
        COXA_SALTANS_DRILL,
        _ex(
            name="McGill Big 3 — Quality Screen",
            ex_type="reps",
            sets=1, reps=8, rest_seconds=60,
            mechanics=(
                "One high-quality set of each: McGill Curl-Up x8 x8-second hold each, Bird-Dog "
                "x8 each side x8-second hold, Side Bridge x40 seconds each side. Compare to the "
                "Stage 1 Day 21 screen — four weeks of loaded training should hold this steady or "
                "better, not worse."
            ),
            biomechanical_focus="Functional re-check of the foundational spinal stability system after a full block of external load.",
            progression="Equal or better than the Stage 1 Day 21 screen → supports continued progression.",
            regression="Worse than Day 21 → flag for physiotherapist discussion before any further loading increase.",
        ),
        _ex(
            name="Single-Leg Balance (Eyes Closed)",
            ex_type="hold",
            laterality="unilateral",
            sets=2, hold_seconds=60, rest_seconds=45,
            mechanics="Stand on one leg, eyes closed once stable. Compare to Day 14 of this block and to the Stage 1 baseline.",
            biomechanical_focus="Proprioceptive re-check across the whole loaded block.",
            progression="Matching or beating both prior checkpoints → criterion re-confirmed.",
            regression="Notably worse → document for the physiotherapist conversation before deciding Stage 2B.",
        ),
        _ex(
            name="Hip Hinge Full Range Assessment",
            ex_type="reps",
            sets=2, reps=10, tempo="3-1-3", rest_seconds=60,
            mechanics="Full hip hinge, no wall, maximum comfortable range, 1-second pause at the bottom. Compare pain-free range and right-side sensation to the Day 14 checkpoint and the Stage 1 baseline.",
            biomechanical_focus="The same functional hinge test used throughout, now with a full block of loaded RDL work behind it.",
            progression="Full range, pain <=2/10, matching or beating prior checkpoints → supports Stage 2B / further loading.",
            regression="Worse than prior checkpoints → discuss with physiotherapist before increasing load further.",
        ),
        _ex(
            name="5-Minute Walk + Stair Assessment",
            ex_type="duration",
            sets=1, duration_minutes=7, rest_seconds=0,
            mechanics=(
                "Walk briskly 5 minutes, then up and down a flight of stairs twice at a normal "
                "pace. Rate pain at each point. Compare to Stage 1's Day 7/14/21 scores. Also log "
                "final working loads on all six primary lifts here (Goblet Squat, Incline DB Press, "
                "RDL, Hip Thrust, Lat Pulldown, Single-Arm DB Row) as the new baseline — this data, "
                "plus the screens above, is what feeds the (separate, not decided here) conversation "
                "about running introduction and Stage 2B vs. extending Stage 2A."
            ),
            biomechanical_focus="Integrated functional outcome measure, now with a full loaded block's worth of trend data.",
            progression="Pain <=2/10 throughout, matching or beating prior checkpoints → Stage 2A genuinely complete.",
            regression="Pain >3/10 on stairs, or worse than prior checkpoints → discuss with physiotherapist before deciding next steps; do not decide Stage 2B or running introduction on this data.",
        ),
    ],
}


# ═════════════════════════════════════════════════════════════════════════════
#  STAGE 2B — 28-DAY BLOCK, PHASE 3.  2026-08-17 (Mon) → 2026-09-13 (Sun)
#
#  Confirmed by athlete + physiotherapist 2026-08-12: Stage 2B REPLACES Stage
#  2A rather than extending it. Clinical stage stays 2 — the block changes, the
#  ACWR/RPE/volume ceilings do not (services/sessions.py::PHASE_META).
#
#  THREE THINGS MAKE THIS BLOCK UNLIKE 2A, and all three are why it starts on a
#  Monday rather than the day after 2A's last day:
#
#  1. TWELVE DAYS WITHOUT A GYM. The athlete is in Ireland 2026-08-19 -> 08-30
#     with long bands and mini-bands only. That is days 3-14 — the back half of
#     week 1 and all of week 2 — so gym work resumes exactly at the top of week
#     3 and no session is stranded mid-week. Weeks 1-2 hold ground; they do not
#     progress. The progression during them is the running.
#  2. RUNNING IS INTRODUCED, from day 5, toward a 10 km on 2026-10-11 (which is
#     day 28 of the NEXT block — the race is that block's own test day). Volume
#     progresses conservatively: the left Sartorius strain has recurred once
#     already, from running overuse, and docs/clinical_profile_weighting.md #1's
#     re-stress carve-out makes that a full-weight finding again the moment
#     running enters a plan.
#  3. THE SESSION SHAPE CHANGES. Every day is authored as
#         [ quiet things down ] -> [ wake things back up ] -> [ load ]
#     Phase 2 did not exist before and is the deliverable of
#     docs/training/warmup_evidence_review_2026-08-10.md. It is mandatory in
#     every session and was specified FIRST, with everything else fitted around
#     it (review section 3.0, athlete's direction). Total preparation, first
#     movement to first working rep: 10-15 min, 15 a ceiling not a target.
#
#  WEEK SHAPE (athlete's decision, 2026-08-14): 2 gym + 2 runs + flexibility.
#      Mon  main    gym/band, lower
#      Tue  stretch run
#      Wed  rest    mobility
#      Thu  stretch cluster flexibility session
#      Fri  main    gym/band, upper
#      Sat  stretch run
#      Sun  rest
#  Five sessions, inside STAGE_CONSTRAINTS[2]["session_freq_max"]. The cluster
#  sits on Thursday because leg-loading days are Monday and the run days — and
#  RUNNING COUNTS AS LEG LOADING (services/flexibility.py::leg_loading_days) —
#  so Thursday is the only day two clear days after leg work that is not itself
#  a rest day, which is the top of flexibility_window's ranking.
#
#  ONE NEW STRESSOR PER WEEK. Running is week 1's, so the cluster session does
#  not start until week 2 (flexibility_integration_2026-08-16.md step 3). The
#  SECOND weekly cluster session is earned, never scheduled — two clean weeks —
#  which is why it can only appear in week 4, and then folded onto day 28's
#  evening rather than added as a sixth session.
#
#  REST: unchanged from 2A except Goblet Squat and RDL, which step 90 -> 120 s
#  in WEEK 4 ONLY, and only once the load is genuinely near-maximal
#  (rest_interval_evidence_review_2026-08-13.md section 3.0 — Grgic 2018).
#  Everything else stays; core, scapular and release work stay at 45 s
#  deliberately, because there is no evidence bearing on them in either
#  direction. Both the right/left split and the 3-5 min proposal were refused
#  on evidence and priced in minutes.
# ═════════════════════════════════════════════════════════════════════════════

_S2B_PHASE = "Stage 2B — Strength + Running Build"

# ─── PHASE 1: quiet things down, at the 5 minutes the profile always said ────
#
# patient_profile.py prescribes a "5-minute release block before every
# session"; the coded doses had drifted to 16-22 min. The physiotherapist
# confirmed the 5 minutes on 2026-08-12 and the dose question is CLOSED, so
# these are the same items at the documented dose. This is a RESTORATION, not a
# cut — and it is what buys the room phase 2 needs inside a 10-15 min ceiling.
#
# Two corrections ride along:
#   - UPPER_GLUTE_RELEASE was coded laterality="bilateral" while its own
#     mechanics text and the profile both say EACH SIDE. Unilateral here, which
#     is what makes the guided flow actually run both sides.
#   - Order. The capsule stretch is the only >=60 s stretch in the block and now
#     runs FIRST, with the pressure releases after it, putting four minutes
#     between the one stiffness-reducing item and the first loaded rep. The
#     warm-up review calls this the free win: it costs nothing.

UPPER_GLUTE_RELEASE_5MIN = _ex(
    name="Upper Glute / TFL Self-Release",
    ex_type="hold",
    laterality="unilateral",
    sets=1, hold_seconds=90, rest_seconds=15,
    mechanics=(
        "Stand side-on to a wall, 10-15 cm away. Press the UPPER outer hip — the shelf just "
        "below the hip crest, not the side of the thigh — into the wall corner. Adjust until "
        "you find the exact area of grip. Hold 90 seconds of steady pressure and let the "
        "tissue soften; do not fight it. The RIGHT side will feel tighter. Then the LEFT. "
        "One round per side at this dose — the block is five minutes, not twenty."
    ),
    biomechanical_focus=(
        "Autogenic inhibition of the overactive glute medius and TFL — the primary anchor of "
        "the compression pattern. Must precede glute activation, or the overactive fibres "
        "compete with the muscle you are trying to wake up."
    ),
    progression="Release felt inside 60 s → hold the pressure and add 5 slow hip circles.",
    regression="Wall pressure too intense → lie on your side and use your own fist instead.",
)

PIRIFORMIS_PNF_5MIN = _ex(
    name="Piriformis Contract-Relax (PNF)",
    ex_type="reps",
    laterality="unilateral",
    sets=1, reps=5, rest_seconds=15,
    mechanics=(
        "Lie on your back, right ankle crossed over the left knee (figure-4). Five cycles per "
        "side: push the RIGHT knee away from you for 5 seconds against your LEFT hand — "
        "isometric, nothing moves — then release completely and draw both legs 5-10% deeper "
        "toward your chest. Hold 3 seconds. That post-contraction window is the whole point. "
        "Five cycles on the right, then five on the left."
    ),
    biomechanical_focus=(
        "Post-isometric inhibition of the chronically overactive piriformis and deep hip "
        "rotators — more effective than passive stretch, and the direct counter to the "
        "upper-glute gripping pattern."
    ),
    progression="Gaining range every cycle → run it seated in 90/90 for more hip flexion bias.",
    regression="Sharp buttock pain on the contraction → drop the pressing phase, passive figure-4 only.",
)

RIGHT_HIP_CAPSULE_5MIN = _ex(
    name="Right Posterior Hip Capsule Stretch (Quadruped)",
    ex_type="hold",
    laterality="unilateral",
    sets=2, hold_seconds=45, rest_seconds=20,
    mechanics=(
        "FIRST item of the session, before anything else. On your hands and knees on a mat. "
        "Bring the RIGHT knee slightly inward, across the midline, and let the right shin trail "
        "out behind you — knee in, foot out. That shin angle keeps the hip in neutral or slight "
        "INTERNAL rotation, which is the rotation that does not snap. Take the LEFT leg straight "
        "back or out wide for balance. Chest tall. Now shift your weight slowly BACKWARD and "
        "across toward the RIGHT — think of the thigh bone gliding back into the socket rather "
        "than of bending further. Stop at deep tension in the back pocket of the right hip and "
        "breathe there for 45 seconds; do not push into it. Pinching at the FRONT of the groin "
        "means you have gone too far back — come forward until it moves to the back pocket. "
        "RIGHT SIDE ONLY."
    ),
    biomechanical_focus=(
        "Right posterior hip capsule (finding #2), the cause of the standing hinge crack. "
        "Runs first so that the block's only long stretch is followed by four minutes of other "
        "work before anything is loaded — stretch-induced slack matters most at Beighton 6/9, "
        "where muscle is the primary restraint. "
        "QUADRUPED, NOT SUPINE, from 2026-08-17 on the athlete's own report: the supine "
        "cross-body version was run for seven weeks and the 2026-07-08 session note records it "
        "reaching the wrong tissue — 'no feeling at the back of the hip or bum. So I feel the "
        "stretch isn't working as expected', with the sensation at the front of the hip and "
        "BILATERAL, which a right-only capsule stretch cannot produce. The (Revised Cue) "
        "rewrite answered that note by changing the CUES and keeping the position, and the "
        "report did not change. Bodyweight over the joint loads the capsule in a way an arm "
        "pulling the knee across does not. REVERT to the supine version if the quadruped one "
        "provokes the Coxa Saltans click, which the supine position cannot reach."
    ),
    progression="Deep back-pocket tension with no groin pinch → sit further back before shifting across.",
    regression="Felt at the front of the groin, or the click appears → less backward shift, and check the shin is trailing OUT.",
    warning=(
        "Neutral or slightly internal rotation at the right hip, never external — this is the "
        "position the Coxa Saltans snap lives in (key rule 7). Knee in, foot out. If the hip "
        "clicks as you settle, come out and reset the shin."
    ),
)

ANTERIOR_HIP_RELEASE = _ex(
    name="Anterior Hip Pressure Release",
    ex_type="hold",
    laterality="unilateral",
    sets=1, hold_seconds=60, rest_seconds=0,
    mechanics=(
        "UNGATED 2026-08-17 (athlete): this waited on the flexibility battery baseline, and "
        "he has captured it — four cold mornings, of which the app lost all but the last. "
        "The surviving reading is the record. Running the release IS how you find out "
        "whether there is anything here to respond; if two weeks find no tender point that "
        "quiets down, skip it from then on and record that, because the null is the finding. "
        "Lie face down with a massage ball between the floor and the front of the hip, on the "
        "meaty pocket-corner just below and outside the point of the hip bone. Settle your "
        "weight onto it slowly and wait 60 seconds, breathing, until the tissue lets go under "
        "you. Then a few slow knee-bends of that leg with the pressure still on. "
        "GO STRAIGHT TO THE OTHER SIDE — no pause between right and left. "
        "One zone per side here; the second zone stays in the daily protocol, which has the "
        "time for it."
    ),
    biomechanical_focus=(
        "The one overactive structure in the profile with no release anywhere in the block "
        "until now. The MRI names psoas and hip-flexor hypertonicity as what amplifies the "
        "L5/S1 compression, and 'deep right hip flexors / TFL' sits on the overactive list — "
        "yet the release block inhibited the glute medius, the piriformis and the posterior "
        "capsule and left the front of the hip alone. Added on the physiotherapist's own "
        "recommendation (2026-08-10): sustained pressure at the front of the hip, to release "
        "the pressure from sitting. Six to eight hours a day holds this tissue short; that is "
        "wear, not training, and part of the seated tilt deficit is held TONE rather than "
        "tissue length."
    ),
    progression=("Tender points quieting and standing up straight after sitting getting easier "
                 "→ it is working; the daily protocol keeps doing the volume."),
    regression=("Nothing tender to find, or no change after four weeks → retire it and record "
                "the null. It would mean the sitting-tone hypothesis is wrong for this body."),
    warning=(
        "THE SHARP EDGE OF THIS ONE. The inner front of the hip carries the leg's main artery "
        "and nerve. NEVER press anywhere you can feel a pulse. Stop immediately on any "
        "tingling, numbness or electric feeling down the leg. Stay on the OUTER half of the "
        "front of the hip, on tissue that pushes back like muscle — the crease at the very "
        "front, middle third, is off-limits entirely. Pain never above 2/10."
    ),
)


# ─── PHASE 2: wake things back up.  NEW — the deliverable of this block ──────
#
# JOB A (restore) runs in every session and is what "mandatory" means: undo the
# acute slack phase 1 leaves and get glute max and the deep core contracting
# before the bar asks. Warneke 2024 (83 studies) is about the PRESENCE of a
# subsequent active warm-up and specifies no duration, so this is short.
#
# JOB B (maximise) is the 15-min low-intensity raise that buys +3-8% near 1RM
# and is worth about nothing at ten reps. It is NOT bought here. What is bought
# is a per-exercise ramp on the heavy compounds only, in week 4 — see
# GOBLET_RAMP / RDL_RAMP. "Mandatory" means the phase exists every session, not
# that every exercise gets a ramp: ramping the face pull is pure fatigue.
#
# MODALITY. The literature's best general raise is 15 min of low-intensity
# cycling. The athlete's own 2025 log names cycling as what tightens his hip
# flexors and inhibits his glutes — the exact muscle this phase exists to wake
# up — so cycling is excluded on his own evidence and the raise is a walk.

PREP_RAISE = _ex(
    name="Walking Raise (Incline)",
    ex_type="duration",
    sets=1, duration_minutes=4, rest_seconds=0,
    mechanics=(
        "Four minutes of brisk walking on an incline — treadmill at a real gradient, or any "
        "uphill outdoors. Warm enough to notice, nowhere near breathless. You are raising "
        "muscle temperature and getting the hips moving through range under your own power, "
        "not training."
    ),
    biomechanical_focus=(
        "General raise, biased toward the pattern about to be trained. Deliberately NOT "
        "cycling: the 2025 log names cycling as what tightens the hip flexors and inhibits "
        "the glutes, which is the one muscle this phase exists to switch on."
    ),
    progression="Feels like nothing → raise the gradient, never the speed. This is not conditioning.",
    regression="Breathing hard → slow down. If it costs anything, it is too hard.",
)

PREP_GLUTE_ACTIVATION = _ex(
    name="Single-Leg Glute Bridge",
    ex_type="hold_reps",
    laterality="unilateral",
    sets=1, reps_in_set=8, hold_seconds=2, rest_seconds=20,
    mechanics=(
        "Lie on your back, one foot planted, the other leg held off the floor. Drive through "
        "the planted heel and lift the hips until the body is in one line. Squeeze the glute "
        "hard for 2 seconds at the top, then lower with control. Eight per side. The hips stay "
        "level — if the free side drops, you have lost the muscle you came for."
    ),
    biomechanical_focus=(
        "Glute max activation, and the single most load-bearing item in phase 2. The 2025 log "
        "names 'glutes not warmed up before squats' as a direct cause of the squat breakdown, "
        "and glute max is the primary underactive muscle in the profile. This is the muscle "
        "the release block just made room for."
    ),
    progression="Both sides clean with level hips → hold the top for 3 seconds.",
    regression="Hamstring cramps or the hip drops → go to a two-leg bridge for the same 8 reps.",
)

PREP_DEAD_BUG = _ex(
    name="Dead Bug",
    ex_type="reps",
    laterality="alternating",
    sets=1, reps=6, rest_seconds=20,
    mechanics=(
        "On your back, knees and hips at 90 degrees, arms up. Press the lower back gently into "
        "the floor and keep it there. Lower the opposite arm and leg slowly, only as far as the "
        "back stays flat, then return. Six each side. Breathe out on the way down."
    ),
    biomechanical_focus=(
        "Deep core switched on before the spine is loaded — the second of the two underactive "
        "structures, and the one the 2025 log records as turning off under fatigue."
    ),
    progression="Six clean each side with a flat back → extend the leg further before returning.",
    regression="Back lifts off the floor → keep the heel closer, or move only the legs.",
    warning=("Keep the right hip cued neutral or slightly internally rotated as the leg extends — "
             "the Coxa Saltans click has been reported in this pattern at around 45 degrees."),
)

PREP_SCAPULAR = _ex(
    name="Scapular Wall Slide",
    ex_type="reps",
    sets=1, reps=8, tempo="3-1-3", rest_seconds=20,
    mechanics=(
        "Head, upper back and arms against a wall, elbows and wrists touching in a goalpost. "
        "Slide the arms up toward a Y, keeping wrists and elbows on the wall the whole way. No "
        "shrugging, no arching off neutral to help the arms up. Only go as high as contact holds."
    ),
    biomechanical_focus=(
        "Scapular upward rotation and lower trapezius before anything is pressed or pulled — "
        "the maintenance-dependent right shoulder (finding #6) gets its stability from muscular "
        "control, and symptoms recur specifically when this work lapses."
    ),
    progression="Full contact to Y, pain-free → add a 2-second hold at the top.",
    regression="Contact lost early → shorten the range to where it holds, or do it seated.",
)

# ─── RAMP SETS.  Week 4's Gym A only, and they carry warmup=True ─────────────
#
# One set of six at ~62% of the working weight, reps MATCHED to the working set
# rather than reduced (Ribeiro 2020 — load comes down, volume does not). Only
# the two heavy compounds: the ramp pays near maximal loads and pays about
# nothing at ten reps, so scaling is per exercise, never per session.
#
# warmup=True is what keeps these out of weekly tonnage and out of every 1RM
# estimate. Without it a ramp set is reps at a real load and would read as work
# — the accounting hazard the warm-up review calls a prerequisite rather than a
# follow-up (services/tonnage.py, services/strength.py).

GOBLET_RAMP = _ex(
    name="Goblet Squat (Ramp Set)",
    ex_type="reps",
    sets=1, reps=6, tempo="3-1-1", rest_seconds=90,
    weight_kg=12.5, equipment_type="dumbbell", warmup=True,
    mechanics=(
        "One set of six at about 62% of today's working weight, at the same tempo and the same "
        "depth you intend to use. This is a rehearsal of the pattern under light load, not a "
        "set. Rest fully afterwards, then start the working sets."
    ),
    biomechanical_focus=(
        "The per-exercise half of phase 2. Ramps the two heavy compounds only, and only in the "
        "week the loads are actually near-maximal."
    ),
    progression="Working weight goes up → the ramp goes up with it, staying near 62%.",
    regression=("Anything feels off in the ramp → that is the ramp doing its job. Reduce the "
                "working weight rather than pressing on."),
)

RDL_RAMP = _ex(
    name="Romanian Deadlift (Ramp Set)",
    ex_type="reps",
    sets=1, reps=6, tempo="3-1-1", rest_seconds=90,
    weight_kg=27.5, equipment_type="dumbbell", warmup=True,
    mechanics=(
        "One set of six at about 62% of today's working weight, same tempo, same range. Feel "
        "the hamstrings take the load and the back stay neutral. Rest fully, then work."
    ),
    biomechanical_focus=(
        "Hinge rehearsal under light load. The 2025 log records that when tired or cold the "
        "back is the first thing to complain in this pattern — this is the cold half of that."
    ),
    progression="Working weight goes up → the ramp goes up with it.",
    regression=("Back rounds under the ramp → stop and reduce the working weight; do not train "
                "into it."),
)

SCAPULAR_ISOMETRIC = _ex(
    name="Scapular Retraction Isometric",
    ex_type="hold_reps",
    sets=3, reps_in_set=4, hold_seconds=3, rest_seconds=45,
    mechanics=(
        "Sit or stand tall, arms by your sides, head in NEUTRAL — never in the position that "
        "provokes the symptom. Draw the shoulder blades down and together, building the effort "
        "over 3 seconds, hold hard for 3, then release over 3. Four of those per set. Change "
        "the arm angle between sets. High intent, not a long squeeze."
    ),
    biomechanical_focus=(
        "FOUR SHORT EFFORTS, NOT ONE LONG HOLD, and that is the whole point. At matched loading "
        "time four 3-second contractions more than doubled the stiffness gain of one 12-second "
        "hold (Bohm 2014, +57% vs +25%); intensity is the variable, not duration. The "
        "45-second hold in circulation is n=6, about analgesia, and has failed to replicate "
        "three times. And the target tissue here is not a tendon — it is left trapezius, "
        "position-loaded and perfusion-limited, where a sustained low-level contraction is the "
        "PROVOCATIVE mechanism (symptom_log 2026-08-13). Both sides, right-biased: the right is "
        "the weaker and the left is overcompensating."
    ),
    progression="Four clean efforts at full intent → add a fourth set, never a longer hold.",
    regression=("Symptom rises during or after → shorten to 2 seconds and check the head "
                "position first; the position is usually the problem, not the load."),
    warning=("Load in NEUTRAL only. If the interscapular area is symptomatic today this is still "
             "fine — but stop if it climbs during the set rather than after it."),
)


# ─── Band work.  Weeks 1-2, Ireland: HOLD GROUND, do not progress ────────────
#
# Bands were already a first-class path — equipment_type="band" plus band_tier
# on services/engine.py's Green/Blue/Yellow/Red/Black ladder — so none of this
# needs new engine code, only names in the three training_constants maps.
#
# A band set writes weight=0, so these weeks read 0 kg of tonnage with real
# unloaded reps. That is true rather than alarming (services/tonnage.py) and is
# the honest record of a fortnight with no external load.
#
# TIERS ARE PRESCRIBED BY FEEL, not by colour, because the athlete's own bands
# have not been measured against this ladder. Pick the band where the last two
# reps are genuinely hard at the prescribed count, then record the colour — the
# recorded colour is what the stepper progresses from next time.

def _band(name, reps, *, tier="Blue", sets=3, laterality="bilateral",
          rest_seconds=60, mechanics="", focus="", progression="", regression="",
          warning=None):
    return _ex(
        name=name, ex_type="reps", laterality=laterality,
        sets=sets, reps=reps, rest_seconds=rest_seconds,
        equipment_type="band", band_tier=tier,
        mechanics=mechanics, biomechanical_focus=focus,
        progression=progression, regression=regression, warning=warning,
    )


BAND_FRONT_SQUAT = _band(
    "Band Front Squat", 12, tier="Blue", rest_seconds=75,
    mechanics=(
        "Stand on the middle of a long band, feet shoulder-width. Bring the ends up over the "
        "shoulders and hold them at collarbone height, elbows up. Squat to the depth you own "
        "with a flat back, then stand and squeeze the glutes. The band fights you hardest at "
        "the top, which is where the glutes should finish the movement."
    ),
    focus=(
        "Keeps the squat pattern alive for twelve days without a rack. The band's resistance "
        "curve is the opposite of a dumbbell's — hardest at lockout, easiest in the hole — "
        "which suits a back whose injuries all came from the bottom of the squat."
    ),
    progression="12 clean reps with a flat back → step to the next band up.",
    regression="Back rounds or the heels lift → shorten the range, or step to a lighter band.",
)

BAND_RDL = _band(
    "Band Romanian Deadlift", 12, tier="Blue", rest_seconds=75,
    mechanics=(
        "Stand on the middle of the band, hold an end in each hand at thigh height. Push the "
        "hips back with a flat back and soft knees, feel the hamstrings load, then drive the "
        "hips forward and squeeze the glutes. Hinge, never round."
    ),
    focus=(
        "Hinge maintenance. The pattern the 2025 log flags as the one where the back complains "
        "first when tired or cold, so it keeps running even in a week with no external load."
    ),
    progression="12 reps with the back flat throughout → next band up.",
    regression="Any lumbar rounding → reduce the range and go back to a lighter band.",
    warning="Stop at the first sign of the back taking over from the hamstrings.",
)

BAND_HIP_THRUST = _band(
    "Band Hip Thrust", 15, tier="Blue",
    mechanics=(
        "Sit with your upper back against a sofa or bed, band across the hips and both ends "
        "anchored under your feet. Drive through the heels, lift the hips to a straight line "
        "from knee to shoulder, and squeeze hard for a beat at the top. Ribs down."
    ),
    focus="Direct glute max loading — the primary underactive muscle, and the one that has "
          "moved most this year.",
    progression="15 reps with a hard squeeze at the top → next band up.",
    regression="Cramping hamstrings → move the feet closer and think about pushing the floor away.",
)

BAND_PALLOF = _band(
    "Band Pallof Press", 10, tier="Green", laterality="unilateral", rest_seconds=45,
    mechanics=(
        "Anchor the band at chest height — a door handle or a post. Stand side-on, hands "
        "together at the chest, and press straight out. The band tries to rotate you; do not "
        "let it. Hold the press for a beat, return. Ten each side."
    ),
    focus="Anti-rotation trunk control, unchanged in intent from the cable version.",
    progression="Rock solid at 10 → step further from the anchor.",
    regression="Trunk rotates → step closer to the anchor.",
)

BAND_CHEST_PRESS = _band(
    "Band Chest Press", 12, tier="Green", rest_seconds=75,
    mechanics=(
        "Anchor the band behind you at chest height, or run it across your back. Press both "
        "hands forward and slightly together, elbows at about 45 degrees from the ribs — not "
        "flared. Control the way back. Keep the shoulder blades set down and back."
    ),
    focus=(
        "Pressing pattern maintenance with the scapula controlled. The right shoulder's "
        "stability is maintenance-dependent, so twelve days without pressing is not the plan."
    ),
    progression="12 controlled reps → next band up.",
    regression="Shoulder feels unstable → shorten the range and keep the hands lower.",
    warning="Never press from a position with the arm out at 90 degrees and turned outward — "
            "that is the position the right shoulder's repair exists to protect.",
)

BAND_LAT_PULLDOWN = _band(
    "Band Lat Pulldown", 12, tier="Green", rest_seconds=60,
    mechanics=(
        "Anchor the band high — a door top, a beam, a banister. Kneel or sit far enough back "
        "that the band is tight with the arms overhead. Pull the elbows down and toward the "
        "ribs, leading with the shoulder blades rather than the hands. Control the way up."
    ),
    focus="Vertical pull, and the closest a band gets to the movement bands do worst.",
    progression="12 reps leading with the shoulder blades → next band up.",
    regression="Shrugging to start the pull → lighter band, and start from a set scapula.",
)

BAND_ROW = _band(
    "Band Single-Arm Row", 12, tier="Green", laterality="unilateral", rest_seconds=60,
    mechanics=(
        "Anchor the band at waist height. One hand, stand in a split stance, pull the elbow "
        "back past the ribs and squeeze the shoulder blade in. Control the return all the way "
        "to a full stretch. Twelve each side."
    ),
    focus=(
        "Horizontal pull, both sides. The right is the weaker side and the left overcompensates "
        "— train both, and expect the left to want more."
    ),
    progression="12 each side with a clean squeeze → next band up.",
    regression="Trunk rotates to help → shorten the range, lighter band.",
)

BAND_FACE_PULL = _band(
    "Band Face Pull", 15, tier="Green", rest_seconds=45,
    mechanics=(
        "Anchor the band at face height. Pull the ends toward your forehead, elbows high and "
        "wide, and finish with the shoulder blades drawn down and together. Slow on the way "
        "back. Fifteen reps."
    ),
    focus=(
        "The one movement the symptom log records as giving ACUTE RELIEF to the interscapular "
        "area — and a band is the ideal tool for it, so this is one item that does not degrade "
        "at all away from a gym."
    ),
    progression="15 easy reps with the blades finishing down → next band up.",
    regression="Upper traps take over → drop a band and lower the anchor slightly.",
)


# ─── The three session shapes, and their two equipment variants ──────────────

def _s2b_prep(lower: bool) -> list:
    """Phase 2. Job A only — restore, in every session. The raise leads, then
    the pattern about to be trained."""
    if lower:
        return [PREP_RAISE, PREP_GLUTE_ACTIVATION, PREP_DEAD_BUG]
    return [PREP_RAISE, PREP_SCAPULAR, PRONE_Y_RAISE]


def _s2b_release(hip_loaded: bool, anterior: bool = False) -> list:
    """Phase 1. Pressure releases, with the ischial-tuberosity release leading
    on hip-loaded days. About 5 min, 9.4 on hip days — the anterior-hip item now
    runs from DAY 1 rather than week 3.

    ── 2026-08-17: THE HIP-LOADED HEAD WAS REPLACED, ON MEASUREMENT ──────────
    It was [capsule stretch, Coxa Saltans drill]. Both were retired the same
    morning, each for its own reason, and both reasons are readings rather than
    judgements:

    CAPSULE STRETCH OUT — its target was refuted. Finding #2 attributes the
    standing hinge crack to a tight RIGHT posterior hip capsule, which had never
    once been measured in the seven weeks it was being treated. A tight
    posterior capsule is what restricts hip INTERNAL rotation, so that is the
    test; run prone on 2026-08-17 it came back **past 45 degrees on BOTH sides
    with no clear asymmetry** — at or above normal range, and no side
    difference. There is no capsular restriction to treat.
      REVERT: a measured right-left internal-rotation gap beyond ~10 degrees, or
      a firm abrupt capsular end-feel on the right. The exercise itself is kept
      (RIGHT_HIP_CAPSULE_QUADRUPED) rather than deleted, so restoring it is one
      line. Note the deep squat CANNOT be used as the test either way — it is
      flexion + abduction + EXTERNAL rotation, the directions a posterior
      capsule does not restrict, so a full squat is silent on the question.

    COXA SALTANS DRILL OUT — it achieved its stated purpose. Its own mechanics
    say the job is to "retrain the motor pattern to avoid the snap during daily
    movement", and daily movement is neutral rotation. Athlete, 2026-08-17: the
    click is GONE in neutral and remains only under deliberate external
    rotation, where originally it was present in both. The residual is a tendon
    crossing a bony ridge — painless per finding #4, and the ridge does not
    move, so it is not a training target.
      NOTE the cue survives the drill: key rule 7 still requires neutral or
      slight internal rotation on every right hip flexion past 60 degrees. That
      is a cue on other exercises, not this drill.
      REVERT: the click reappearing in neutral rotation.

    ISCHIAL TUBEROSITY RELEASE IN — finding #2 names TWO structures, and
    clearing the capsule leaves the other one: "proximal hamstring tendon at
    the ischial tuberosity". The crack itself is still present (athlete,
    2026-08-17: slight, both directions, right, better than before), so the
    symptom is real and now has one candidate mechanism instead of two. This
    item was in Stage 2A, was cut from 2B on the five-minute budget rather than
    on evidence, and pre_session_release records it as physio-confirmed for
    this site and owed back at the next contact. The two removals above pay for
    it almost exactly: 3.2 min out, 3.75 min in.

    ── original note ────────────────────────────────────────────────────────

    `anterior` adds the front-of-hip release. It USED to wait until week 3, on
    one condition only: the seated tilt is the flexibility battery's central
    measurement, and starting a new anterior-hip intervention before the
    baseline was captured would contaminate it. That condition is now MET —
    the athlete ran the battery cold on four separate mornings and the app
    lost every recording but the last (the same persistence failure that lost
    the session notes). His direction, 2026-08-17: the surviving reading is the
    record, treat the baseline as complete. Making him repeat four cold
    mornings because this system dropped them is not a clinical requirement,
    it is a bug charging interest.

    ⚠ WHAT IS GENUINELY LOST, and no instruction repairs it: three mornings
    established the NOISE FLOOR, not just the baseline value. With one stored
    reading there is no measured spread, so `BatteryResult.trusted` stays False
    and a future change cannot be judged against ~2x the observed spread the
    way services/battery.py intends. Future deltas need either a rebuilt
    spread or a deliberately wider margin — they cannot be read as results on
    a single point.

    It brings the release forward to day 1 for a second reason on the same day:
    the athlete's psoas hypothesis for the standing hinge crack. Finding #4 is
    already an iliopsoas tendon on the right, the MRI names psoas hypertonicity
    as what amplifies the L5/S1 compression, and 'deep right hip flexors / TFL'
    sits on the overactive list. This is the only release aimed there.

    It is also off on the day-28 assessment: that screen's value is
    comparability with the Stage 1 and Stage 2A versions of itself, and a new
    hip-flexor release immediately before a hinge assessment would move the
    number for a reason that has nothing to do with the athlete."""
    head = [ISCHIAL_RELEASE] if hip_loaded else []
    tail = [ANTERIOR_HIP_RELEASE] if anterior else []
    return head + [UPPER_GLUTE_RELEASE_5MIN, PIRIFORMIS_PNF_5MIN] + tail


def _s2b_gym_a(week: int) -> dict:
    """Squat + Hinge + Core. Weeks 1, 3 and 4.

    Week 3 is the re-entry session and runs one increment down on the squat and
    thrust and two on the RDL. Twelve days without external load costs almost
    no strength — decay is suspended and the first week without stimulus is a
    documented grace period — but "weight increased too quickly" is a named
    cause of the squat breakdown in the athlete's own log, and the RDL is both
    the lift sitting at RPE 7 and the one loading the segment with the annular
    tears, so it takes the deeper step back.
    """
    squat_kg = {1: 20.0, 3: 17.5, 4: 20.0}[week]
    rdl_kg = {1: 45.0, 3: 40.0, 4: 45.0}[week]
    thrust_kg = {1: 42.5, 3: 40.0, 4: 42.5}[week]
    # 90 s everywhere except week 4, where the loads are genuinely near-maximal
    # and Grgic 2018's ">2 min to maximise strength" applies. It does not apply
    # at 12.5 kg and RPE 6, which is why this is conditional on the week.
    heavy_rest = 120 if week == 4 else 90
    ramp = [GOBLET_RAMP, RDL_RAMP] if week == 4 else []
    objective = {
        1: "Stage 2B Week 1 — Squat + Hinge + Core (last loaded session before travel)",
        3: "Stage 2B Week 3 — Squat + Hinge + Core (re-entry, one step down)",
        4: "Stage 2B Week 4 — Squat + Hinge + Core (full load, ramped)",
    }[week]
    return {
        "objective": objective,
        "phase": _S2B_PHASE,
        "session_rpe_target": 7 if week == 4 else 6,
        "is_gym_session": True,
        "day_type": "main",
        "exercises": _s2b_release(hip_loaded=True, anterior=True)
                      + _s2b_prep(lower=True) + ramp + [
            _ex(
                name="Goblet Squat",
                ex_type="reps",
                sets=3, reps=10, tempo="3-1-1", rest_seconds=heavy_rest,
                weight_kg=squat_kg, equipment_type="dumbbell", rep_min=8, rep_max=12,
                mechanics=(
                    "Dumbbell held at the chest, feet shoulder-width. Sit down between the hips "
                    "to the depth you own with a flat back, then stand and finish with the "
                    "glutes. Three seconds down, a beat at the bottom, drive up."
                ),
                biomechanical_focus=(
                    "The primary lower-body strength lift of the block. Brace quality is the "
                    "thing being watched: the 2025 log records the brace collapsing from rep 6 "
                    "onward, and phase 2 exists partly to move that number."
                ),
                progression="All three sets at 12 clean reps → add 2.5 kg and drop back to 8.",
                regression="Brace collapses before rep 8 → stop the set there and reduce the load.",
                warning="Back injuries have all come from the bottom of the squat. Stop the set at "
                        "the first loss of a flat back rather than finishing the reps.",
            ),
            _ex(
                name="Romanian Deadlift (DB)",
                ex_type="reps",
                sets=3, reps=10, tempo="3-1-1", rest_seconds=heavy_rest,
                weight_kg=rdl_kg, equipment_type="dumbbell", rep_min=8, rep_max=12,
                mechanics=(
                    "A dumbbell in each hand, soft knees. Push the hips back and let the weight "
                    "travel down the thighs, back flat throughout. Go as far as the hamstrings "
                    "allow without the back moving, then drive the hips forward. Hinge, never "
                    "round."
                ),
                biomechanical_focus=(
                    "Hinge strength and hamstring load. This lift sits over the annular tears, "
                    "which is why it steps back furthest after the travel weeks and progresses "
                    "on the widest rep span."
                ),
                progression="All three sets at 12 with a flat back → add 2.5 kg and drop back to 8.",
                regression="Any rounding → reduce the range first, the load second.",
            ),
            _ex(
                name="Hip Thrust (Loaded)",
                ex_type="reps",
                sets=3, reps=10, rest_seconds=75,
                weight_kg=thrust_kg, equipment_type="plate", rep_min=10, rep_max=12,
                mechanics=(
                    "Upper back on a bench, bar or plate across the hips with a pad. Drive "
                    "through the heels to a straight line from knee to shoulder, squeeze hard "
                    "for a beat, lower with control. Ribs down, chin tucked."
                ),
                biomechanical_focus="Direct glute max loading in the range the squat does not reach.",
                progression="All three sets at 12 → add 2.5 kg and drop back to 10.",
                regression="Lower back does the lifting → reduce the load and shorten the top range.",
            ),
            _ex(
                name="Pallof Press (Cable)",
                ex_type="reps",
                laterality="unilateral",
                sets=3, reps=10, rest_seconds=45,
                weight_kg=5.0, equipment_type="cable",
                increment_size=1, increment_unit="unit", rep_min=10, rep_max=12,
                mechanics=(
                    "Cable at chest height, stand side-on, hands together at the chest. Press "
                    "straight out and refuse to rotate. Hold a beat at full extension. Ten each "
                    "side."
                ),
                biomechanical_focus="Anti-rotation trunk control under load, without loaded spinal rotation.",
                progression="Rock solid at 12 → up one unit on the stack.",
                regression="Trunk rotates → down one unit, or step closer to the machine.",
            ),
            _ex(
                name="McGill Curl-Up (Progressed)",
                ex_type="hold_reps",
                sets=3, reps_in_set=8, hold_seconds=10, rest_seconds=45,
                mechanics=(
                    "Lie on your back, one knee bent, hands under the small of the back to keep "
                    "the natural curve. Lift the head and shoulders as one unit — no neck "
                    "flexion, no flattening the back into the floor. Hold 10 seconds, lower. "
                    "Eight of those."
                ),
                biomechanical_focus="Lumbar endurance without lumbar flexion — the one abdominal "
                                    "pattern safe over the annular tears.",
                progression="Eight clean 10-second holds → swap the bent knee halfway through.",
                regression="Neck fatigues first → shorten to 6 seconds and keep the head heavier "
                           "in the hands.",
            ),
            _ex(
                name="Full Side Bridge",
                ex_type="hold",
                laterality="unilateral",
                sets=3, hold_seconds=45, rest_seconds=45,
                mechanics=(
                    "On your side, forearm down, body in one straight line from ankle to head. "
                    "Hips high, do not let them sag or roll. Hold 45 seconds each side."
                ),
                biomechanical_focus="Lateral trunk endurance — the quadratus and obliques that "
                                    "stop the pelvis dropping in single-leg stance and in running.",
                progression="45 s solid both sides → add 10 s, never load it.",
                regression="Hips sag → drop to the bent-knee version for the same time.",
            ),
        ],
    }


def _s2b_gym_b(week: int) -> dict:
    """Press + Pull + Scapular. Weeks 3 and 4 only — there is no loaded upper
    session in weeks 1-2 because the flight lands on day 3.

    Incline DB Press does NOT step. It has sat at 15 kg for three sessions and
    dropped a rep on the last one; the rep span is the axis that moves here,
    not the load.
    """
    return {
        "objective": f"Stage 2B Week {week} — Press + Pull + Scapular",
        "phase": _S2B_PHASE,
        "session_rpe_target": 7 if week == 4 else 6,
        "is_gym_session": True,
        "day_type": "main",
        "exercises": _s2b_release(hip_loaded=False) + _s2b_prep(lower=False) + [
            _ex(
                name="Incline DB Press",
                ex_type="reps",
                sets=3, reps=10, rest_seconds=75,
                weight_kg=15.0, equipment_type="dumbbell", rep_min=10, rep_max=12,
                mechanics=(
                    "Bench at about 30 degrees, a dumbbell in each hand. Set the shoulder blades "
                    "down and back into the bench and keep them there. Elbows about 45 degrees "
                    "from the ribs, never flared wide. Press up and slightly together."
                ),
                biomechanical_focus=(
                    "The block's pressing lift, and the one being watched for the left tilt the "
                    "2025 log records under overhead load. Held at 15 kg on purpose: three "
                    "sessions without moving and a dropped rep say add reps, not kilograms."
                ),
                progression="All three sets at 12 clean reps → then, and only then, add 2.5 kg.",
                regression="Shoulder blades lose contact with the bench → reduce the load.",
                warning="Stop on any instability sensation or a left-side tilt appearing under the "
                        "press — that is a Stage 2 exit criterion, not a training sensation.",
            ),
            _ex(
                name="Lat Pulldown",
                ex_type="reps",
                sets=3, reps=11, rest_seconds=60,
                weight_kg=45.0, equipment_type="cable", rep_min=10, rep_max=12,
                mechanics=(
                    "Set the knees under the pad. Start from a full stretch with the shoulder "
                    "blades relaxed up, then pull the elbows down and in, leading with the "
                    "blades. Chest tall, no leaning back to finish the rep."
                ),
                biomechanical_focus=(
                    "Vertical pull, and the lift with the most documented 2025 history behind it "
                    "(60 kg × 12). Scapular depression is the specific weak link — lead with the "
                    "blades, not the hands."
                ),
                progression="All three sets at 12 → up one increment and back to 10.",
                regression="Leaning back to finish → reduce the load; the range is the point.",
            ),
            _ex(
                name="Single-Arm DB Row",
                ex_type="reps",
                laterality="unilateral",
                sets=3, reps=10, rest_seconds=60,
                weight_kg=22.5, equipment_type="dumbbell", rep_min=10, rep_max=12,
                mechanics=(
                    "One knee and one hand on a bench, flat back. Pull the dumbbell to the ribs, "
                    "elbow past the body, and squeeze the shoulder blade in. Lower all the way "
                    "to a full stretch. Ten each side."
                ),
                biomechanical_focus=(
                    "Horizontal pull, both sides. The right is the weaker side and the left "
                    "overcompensates — if the left side needs a different number, use the Edit "
                    "left side control so the log records both rather than overwriting one."
                ),
                progression="All three sets at 12 both sides → add 2.5 kg and back to 10.",
                regression="Trunk rotates to help → reduce the load.",
            ),
            _ex(
                name="Face Pull (Cable)",
                ex_type="reps",
                sets=3, reps=12, rest_seconds=45,
                weight_kg=6.0, equipment_type="cable",
                increment_size=1, increment_unit="unit", rep_min=12, rep_max=15,
                mechanics=(
                    "Rope at face height. Pull toward the forehead with the elbows high and "
                    "wide, finishing with the shoulder blades down and together. Slow on the "
                    "way back."
                ),
                biomechanical_focus=(
                    "Deliberately paired with the pressing work — a clinical pairing for the "
                    "right shoulder, not a time-efficiency one. Also the movement the symptom "
                    "log records as giving acute relief to the interscapular area."
                ),
                progression="All three sets at 15 with the blades finishing down → up one unit.",
                regression="Upper traps take over → down one unit and lower the rope slightly.",
            ),
            SCAPULAR_ISOMETRIC,
            _ex(
                name="Full Side Bridge",
                ex_type="hold",
                laterality="unilateral",
                sets=3, hold_seconds=45, rest_seconds=45,
                mechanics=(
                    "On your side, forearm down, body in one straight line from ankle to head. "
                    "Hips high, do not let them sag or roll. Hold 45 seconds each side."
                ),
                biomechanical_focus="Lateral trunk endurance, carried on every session type.",
                progression="45 s solid both sides → add 10 s, never load it.",
                regression="Hips sag → drop to the bent-knee version for the same time.",
            ),
        ],
    }


def _s2b_band_a(week: int) -> dict:
    """Ireland, lower body. Holds ground — no progression targets."""
    return {
        "objective": f"Stage 2B Week {week} — Bands: Squat + Hinge + Core (away)",
        "phase": _S2B_PHASE,
        "session_rpe_target": 5,
        "is_gym_session": True,
        "day_type": "main",
        "exercises": _s2b_release(hip_loaded=True, anterior=True) + _s2b_prep(lower=True) + [
            BAND_FRONT_SQUAT,
            BAND_RDL,
            BAND_HIP_THRUST,
            BAND_PALLOF,
            _ex(
                name="McGill Curl-Up (Progressed)",
                ex_type="hold_reps",
                sets=3, reps_in_set=8, hold_seconds=10, rest_seconds=45,
                mechanics=(
                    "Lie on your back, one knee bent, hands under the small of the back to keep "
                    "the natural curve. Lift the head and shoulders as one unit, hold 10 "
                    "seconds, lower. Eight of those."
                ),
                biomechanical_focus="Lumbar endurance without lumbar flexion — unchanged away from home.",
                progression="Eight clean holds → swap the bent knee halfway through.",
                regression="Neck fatigues first → shorten to 6 seconds.",
            ),
            _ex(
                name="Full Side Bridge",
                ex_type="hold",
                laterality="unilateral",
                sets=3, hold_seconds=45, rest_seconds=45,
                mechanics=("On your side, forearm down, one straight line from ankle to head. "
                           "Hips high. 45 seconds each side."),
                biomechanical_focus="Lateral trunk endurance — needs nothing but a floor.",
                progression="45 s solid → add 10 s.",
                regression="Hips sag → bent-knee version, same time.",
            ),
        ],
    }


def _s2b_band_b(week: int) -> dict:
    """Ireland, upper body. The one session type that loses least to a band."""
    return {
        "objective": f"Stage 2B Week {week} — Bands: Press + Pull + Scapular (away)",
        "phase": _S2B_PHASE,
        "session_rpe_target": 5,
        "is_gym_session": True,
        "day_type": "main",
        "exercises": _s2b_release(hip_loaded=False) + _s2b_prep(lower=False) + [
            BAND_CHEST_PRESS,
            BAND_LAT_PULLDOWN,
            BAND_ROW,
            BAND_FACE_PULL,
            SCAPULAR_ISOMETRIC,
            _ex(
                name="Full Side Bridge",
                ex_type="hold",
                laterality="unilateral",
                sets=3, hold_seconds=45, rest_seconds=45,
                mechanics=("On your side, forearm down, one straight line from ankle to head. "
                           "Hips high. 45 seconds each side."),
                biomechanical_focus="Lateral trunk endurance — needs nothing but a floor.",
                progression="45 s solid → add 10 s.",
                regression="Hips sag → bent-knee version, same time.",
            ),
        ],
    }


# ─── Running.  Introduced day 5, conservatively, and here is why ─────────────
#
# The names all contain "running" on purpose. services/rules.py matches
# movement keywords by substring, so "Easy Run" would return `unknown` — not a
# block, but not the caution verdict either. Naming a session so it misses a
# safety keyword is the vocabulary failure this repo has already been burned
# by; these names make check_movement actually fire and return caution.
# They also match services/sessions.py::is_run_or_walk, so the guided flow
# pulls the real duration off the watch on Complete.
#
# THE PROGRESSION IS DELIBERATELY SLOW. The left Sartorius has strained twice,
# both times from running overuse, and clinical_profile_weighting.md #1 makes a
# resolved injury full-weight again the moment a plan would re-stress it. Three
# run/walk sessions before the first continuous run; two runs a week, never
# three; one variable moves at a time.

def _s2b_run(day_label: str, name: str, minutes: int, mechanics: str,
             focus: str, progression: str, regression: str, rpe: int = 4,
             anterior: bool = False) -> dict:
    return {
        "objective": f"Stage 2B — {day_label}",
        "phase": _S2B_PHASE,
        "session_rpe_target": rpe,
        "is_gym_session": False,
        "day_type": "stretch",
        "exercises": _s2b_release(hip_loaded=True, anterior=anterior) + [
            PREP_RAISE, PREP_GLUTE_ACTIVATION,
            _ex(
                name=name,
                ex_type="duration",
                sets=1, duration_minutes=minutes, rest_seconds=0,
                mechanics=mechanics,
                biomechanical_focus=focus,
                progression=progression,
                regression=regression,
                warning=("Stop and walk home at any front-of-hip or groin pain on the LEFT — that "
                         "is the Sartorius, it has gone twice before, and both times it was "
                         "running volume. A missed run costs nothing; a third strain costs the "
                         "race."),
            ),
        ],
    }


_RUN_DAYS = {
    5: ("Run 1 — first run/walk", "Running Intervals (Run/Walk)", 20,
        "Twenty minutes total: one minute of easy running, two minutes of walking, seven times "
        "through. The running should feel almost too easy — you should be able to talk in full "
        "sentences. This is the first running in months; the point is that the tissue meets it, "
        "not that it is hard.",
        "First exposure. Run/walk keeps the total impact low while the pattern is re-learned, "
        "which is the conservative introduction the twice-strained left hip flexor requires.",
        "Twenty minutes finished comfortably with no next-day hip flexor soreness → the next "
        "session lengthens the run interval.",
        "Any left front-hip soreness the next day → repeat this session rather than progressing."),
    9: ("Run 2 — run/walk", "Running Intervals (Run/Walk)", 25,
        "Twenty-five minutes: two minutes of easy running, two minutes of walking, six times "
        "through. Same easy pace as the first session — the interval got longer, the effort did "
        "not.",
        "One variable moves per session, and this session moves duration only.",
        "Clean and comfortable → the walk shortens next time.",
        "Anything sore on the left hip flexor → go back to one-minute intervals."),
    13: ("Run 3 — run/walk", "Running Intervals (Run/Walk)", 30,
         "Thirty minutes: three minutes of easy running, one minute of walking. The walk is now "
         "a break rather than half the session. Still conversational throughout.",
         "The last run/walk session. If this is comfortable the next one is continuous.",
         "Comfortable, no next-day soreness → first continuous run next week.",
         "Not comfortable → stay on run/walk another week. The race is eight weeks out; there "
         "is room."),
    16: ("Run 4 — first continuous run", "Easy Running", 20,
         "Twenty minutes of continuous easy running. No walk breaks. Slower than you think — if "
         "you cannot talk, you are running too fast for this block.",
         "First continuous run. The step from run/walk is the one most likely to produce "
         "soreness, which is why it lands the week after the travel block rather than during it.",
         "Comfortable → extend the duration, never the pace.",
         "Sore → drop back to three-minute intervals for one session."),
    20: ("Run 5 — easy", "Easy Running", 30,
         "Thirty minutes continuous, conversational throughout. This one follows an upper-body "
         "gym day rather than a squat day, which is why it is the week's longer run.",
         "Building continuous time on feet. Pace stays where it is for the whole block.",
         "Comfortable → 35 minutes next week.",
         "Fatigue accumulating across the week → shorten this one rather than the gym session."),
    23: ("Run 6 — the block's longest", "Long Easy Running", 35,
         "Thirty-five minutes, easy the whole way. This is the block's longest run and the last "
         "one before the reassessment — roughly 4.5 km at this pace.",
         "The block's endurance checkpoint. Note what it does NOT do: it does not go near the "
         "race distance. Block A gets to 35 minutes continuous and Block B builds from there, "
         "which is the pace the twice-strained left hip flexor sets rather than the calendar.",
         "Comfortable at 35 minutes → Block B extends the long run toward the distance.",
         "Struggled → Block B starts with more run/walk, and that is a normal outcome rather "
         "than a setback.", 5),
}


def _s2b_run_day(day: int) -> dict:
    label, name, minutes, mech, focus, prog, regr, *rest = _RUN_DAYS[day]
    return _s2b_run(label, name, minutes, mech, focus, prog, regr,
                    rpe=rest[0] if rest else 4, anterior=True)


def _s2b_mobility(week: int, away: bool = False) -> dict:
    """Wednesday. The release block, thoracic work and a walk — no loading.

    Deliberately not called a rest day in the objective: it is the day the desk
    interventions and the two release protocols actually get run.
    """
    return {
        "objective": f"Stage 2B Week {week} — Mobility + Release" + (" (away)" if away else ""),
        "phase": _S2B_PHASE,
        "session_rpe_target": 3,
        "is_gym_session": False,
        "day_type": "rest",
        "exercises": _s2b_release(hip_loaded=False) + [
            _ex(
                name="Thoracic Extension (Rolled Towel)",
                ex_type="hold",
                sets=3, hold_seconds=45, rest_seconds=30,
                mechanics=(
                    "Lie back over a rolled towel placed across the mid-back, arms overhead, "
                    "knees bent. Breathe into the position for 45 seconds, then move the towel "
                    "a few centimetres and repeat. Three positions up the thoracic spine."
                ),
                biomechanical_focus=(
                    "Thoracic extension over the T6-T10 segments that release in the seated "
                    "forward bend (finding #3). Also the counter to the desk position that is "
                    "the dominant driver of the interscapular symptom."
                ),
                progression="Comfortable → hold the arms further overhead.",
                regression="Ribs flare or the low back arches → bend the knees more and breathe out longer.",
            ),
            _ex(
                name="Thread-the-Needle (Thoracic Rotation)",
                ex_type="hold_reps",
                laterality="unilateral",
                sets=2, reps_in_set=6, hold_seconds=3, rest_seconds=30,
                mechanics=(
                    "On hands and knees, slide one arm under the body and let the shoulder and "
                    "head follow to the floor. Hold three seconds, then open back up reaching "
                    "the same arm toward the ceiling. Six each side. Rotation comes from the "
                    "ribs, not the lower back."
                ),
                biomechanical_focus="Thoracic rotation, unloaded — the segment that should rotate "
                                    "so the lumbar spine does not have to.",
                progression="Easy → pause three seconds at the top of the open position too.",
                regression="Lower back twists → shorten the range and keep the hips square.",
            ),
            _ex(
                name="Controlled Walking",
                ex_type="duration",
                sets=1, duration_minutes=25, rest_seconds=0,
                mechanics=(
                    "Twenty-five minutes at a natural pace, outdoors if possible. Not a "
                    "workout — this is the movement dose that the symptom log records as the "
                    "one thing that reliably settles the interscapular area."
                ),
                biomechanical_focus=(
                    "Perfusion, not conditioning. The mechanism behind the left trapezius "
                    "symptom is occlusion under sustained low-level contraction, and movement "
                    "is what pumps it — which is why walking helps and eight hours of holding "
                    "still does not."
                ),
                progression="Fine → take it earlier in the day, before the symptom appears "
                            "rather than after.",
                regression="Time-limited → three 8-minute walks beat one 25-minute one for this.",
            ),
        ],
    }


def _s2b_travel_day(day_label: str, note: str) -> dict:
    """Flight days. The release block and a walk, nothing else."""
    return {
        "objective": f"Stage 2B — {day_label}",
        "phase": _S2B_PHASE,
        "session_rpe_target": 2,
        "is_gym_session": False,
        "day_type": "rest",
        "exercises": _s2b_release(hip_loaded=False) + [
            _ex(
                name="Controlled Walking",
                ex_type="duration",
                sets=1, duration_minutes=20, rest_seconds=0,
                mechanics=("Twenty minutes of walking, broken up however the day allows. After a "
                           "flight, several short walks beat one long one."),
                biomechanical_focus=note,
                progression="Feeling good on arrival → take the full twenty in one go.",
                regression="No time → even ten minutes counts. Do not skip it entirely.",
            ),
        ],
    }


def _s2b_cluster(week: int) -> dict:
    """Thursday. The Cluster A flexibility session joins the block here.

    THE STACK IS NOT AUTHORED IN THIS FILE, and that is deliberate. The battery
    has never been run, and cluster_a_prescription.prescribe(None) raises rather
    than guessing — a prescription without a pattern is a guess. What this day
    does is RESERVE THE SLOT inside the five-per-week ceiling, which is the
    integration protocol's step 1: capacity does not depend on which stack ends
    up filling it. The Flexibility screen renders the real stack once three cold
    baseline mornings have produced a pattern.
    """
    return {
        "objective": f"Stage 2B Week {week} — Cluster A Flexibility Session",
        "phase": _S2B_PHASE,
        "session_rpe_target": 4,
        "is_gym_session": False,
        "day_type": "stretch",
        "exercises": _s2b_release(hip_loaded=True, anterior=True) + [PREP_RAISE] + [
            _ex(
                name="Cluster A Flexibility Session",
                ex_type="duration",
                sets=1, duration_minutes=25, rest_seconds=0,
                mechanics=(
                    "Open the Flexibility screen and follow the stack it shows. Three to five "
                    "exercises, in the order given — isolated work first, the full position "
                    "last. The release block above is the precondition and does not count "
                    "toward those five. If the screen has no stack yet, the battery has not been "
                    "run: do that instead, cold, first thing on a morning that did not follow "
                    "leg training."
                ),
                biomechanical_focus=(
                    "The organising claim, now physio-endorsed: the lack of hip flexibility is "
                    "what drives the lower back to sit stuck in position. Success here is the "
                    "block coming down, not the reach going further — the number that should "
                    "move first is the height at which the lower back stops being flat."
                ),
                progression=("Two clean weeks — no symptom entry attributable to this work, no "
                             "readiness downtrend, no ACWR advisory — earns a second session a "
                             "week. It is earned, never scheduled."),
                regression=("Any of those three appear → back to one session a week, or pause. "
                            "A pause is a hold on evidence, not a deletion."),
            ),
        ],
    }


# ─── The 28 days ─────────────────────────────────────────────────────────────
#
# Assembled explicitly rather than in a week loop, because this block's weeks
# are NOT the same shape as each other: the flight lands mid-week 1, weeks 1-2
# are band-only, and the cluster does not start until week 2. A loop would hide
# exactly the thing that makes this block what it is.
#
# EVERY DAY CARRIES A day_type, in this one commit. Partial adoption silently
# disables the readiness auto-shift (services/scheduling.py).

PLAN_STAGE2B: dict[int, dict] = {}

# ── Week 1: two days at home, then the flight. Running is week 1's stressor. ─
PLAN_STAGE2B[1] = _s2b_gym_a(1)
PLAN_STAGE2B[2] = _s2b_mobility(1)
PLAN_STAGE2B[3] = _s2b_travel_day(
    "Travel day — Ireland",
    "Post-flight decompression. Sitting still for hours is the exact exposure the lumbar "
    "findings and the trapezius symptom both respond worst to.",
)
PLAN_STAGE2B[4] = _s2b_band_a(1)
PLAN_STAGE2B[5] = _s2b_run_day(5)
PLAN_STAGE2B[6] = _s2b_band_b(1)
PLAN_STAGE2B[7] = {
    "objective": "Stage 2B Week 1 — Rest",
    "phase": _S2B_PHASE,
    "session_rpe_target": 2,
    "is_gym_session": False,
    "day_type": "rest",
    "exercises": _s2b_release(hip_loaded=False) + [
        _ex(
            name="Controlled Walking",
            ex_type="duration",
            sets=1, duration_minutes=20, rest_seconds=0,
            mechanics="Twenty minutes, easy, outdoors. Nothing else is prescribed today.",
            biomechanical_focus="A genuine rest day with the release block kept, because the "
                                "release block precedes every session and skipping it on the "
                                "quiet days is how the habit erodes.",
            progression="Feeling good → a longer walk is fine. Running is not.",
            regression="Tired → the release block alone is a complete day.",
        ),
    ],
}

# ── Week 2: all away. The cluster joins here — one stressor per week. ────────
PLAN_STAGE2B[8] = _s2b_band_a(2)
PLAN_STAGE2B[9] = _s2b_run_day(9)
PLAN_STAGE2B[10] = _s2b_mobility(2, away=True)
PLAN_STAGE2B[11] = _s2b_cluster(2)
PLAN_STAGE2B[12] = _s2b_band_b(2)
PLAN_STAGE2B[13] = _s2b_run_day(13)
PLAN_STAGE2B[14] = _s2b_travel_day(
    "Travel day — home",
    "The return flight. Same reasoning as the outbound: get up and walk, and run the release "
    "block whatever else the day does.",
)

# ── Week 3: home, gym resumes, one step down on the loads. ───────────────────
PLAN_STAGE2B[15] = _s2b_gym_a(3)
PLAN_STAGE2B[16] = _s2b_run_day(16)
PLAN_STAGE2B[17] = _s2b_mobility(3)
PLAN_STAGE2B[18] = _s2b_cluster(3)
PLAN_STAGE2B[19] = _s2b_gym_b(3)
PLAN_STAGE2B[20] = _s2b_run_day(20)
PLAN_STAGE2B[21] = {
    "objective": "Stage 2B Week 3 — Rest",
    "phase": _S2B_PHASE,
    "session_rpe_target": 2,
    "is_gym_session": False,
    "day_type": "rest",
    "exercises": _s2b_release(hip_loaded=False) + [
        _ex(
            name="Controlled Walking",
            ex_type="duration",
            sets=1, duration_minutes=20, rest_seconds=0,
            mechanics="Twenty minutes, easy. A restorative yoga flow is fine today if you want one.",
            biomechanical_focus="Rest between the re-entry week and the block's heaviest week.",
            progression="Feeling good → nothing changes. This day is doing its job.",
            regression="Tired → the release block alone is a complete day.",
        ),
    ],
}

# ── Week 4: full loads, ramp sets, and the reassessment. ─────────────────────
PLAN_STAGE2B[22] = _s2b_gym_a(4)
PLAN_STAGE2B[23] = _s2b_run_day(23)
PLAN_STAGE2B[24] = _s2b_mobility(4)
PLAN_STAGE2B[25] = _s2b_cluster(4)
PLAN_STAGE2B[26] = _s2b_gym_b(4)
# Day 27 is a REST day, not the block's seventh run. Week 4 already holds two
# gym days, a run, the cluster session and the day-28 assessment — five, which
# is STAGE_CONSTRAINTS[2]["session_freq_max"] exactly. A run here would make it
# six. It is also the better methodology: the functional screen on day 28
# should measure the block, not the previous day.
PLAN_STAGE2B[27] = {
    "objective": "Stage 2B Week 4 — Rest (day before the reassessment)",
    "phase": _S2B_PHASE,
    "session_rpe_target": 2,
    "is_gym_session": False,
    "day_type": "rest",
    "exercises": _s2b_release(hip_loaded=False) + [
        _ex(
            name="Controlled Walking",
            ex_type="duration",
            sets=1, duration_minutes=20, rest_seconds=0,
            mechanics=("Twenty minutes, easy. Nothing else — tomorrow's screen is only worth "
                       "running on a rested body."),
            biomechanical_focus=("Deliberate rest before the reassessment. A functional screen "
                                 "taken on fatigue measures the fatigue."),
            progression="Feeling good → still nothing. This day is doing its job.",
            regression="Tired → the release block alone is a complete day.",
        ),
    ],
}

PLAN_STAGE2B[28] = {
    "objective": "Stage 2B Reassessment — Final Working Loads + Functional Screen",
    "phase": _S2B_PHASE,
    "session_rpe_target": 4,
    "day_type": "test",
    "exercises": _s2b_release(hip_loaded=True) + [
        _ex(
            name="McGill Big 3 — Quality Screen",
            ex_type="reps",
            sets=1, reps=8, rest_seconds=60,
            mechanics=(
                "Curl-up, side bridge and bird-dog, eight quality reps of each. Judge the "
                "QUALITY, not the count: does the brace hold, does the pelvis stay level, does "
                "anything shake that did not last time."
            ),
            biomechanical_focus="Trunk control screen, comparable to the Stage 1 Day 21 and "
                                "Stage 2A Day 28 versions of the same test.",
            progression="Matching or beating the last screen → the trunk work is doing its job.",
            regression="Worse → say so before the next block is authored, not after.",
        ),
        _ex(
            name="Single-Leg Balance (Eyes Closed)",
            ex_type="hold",
            laterality="unilateral",
            sets=2, hold_seconds=60, rest_seconds=45,
            mechanics="Stand on one leg, eyes closed, 60 seconds each side. Record which side "
                      "is worse and by how much.",
            biomechanical_focus="Proprioceptive control, and a standing requirement at Beighton 6/9.",
            progression="Both sides steady → unchanged; this is a monitor, not a target.",
            regression="Markedly worse on one side → record it against the hip findings.",
        ),
        _ex(
            name="Hip Hinge Full Range Assessment",
            ex_type="reps",
            sets=2, reps=10, tempo="3-1-3", rest_seconds=60,
            mechanics=(
                "Ten slow unloaded hinges to full range. Note whether the standing hinge crack "
                "appears, and whether the Coxa Saltans click has changed under a block that "
                "loaded squats and split squats."
            ),
            biomechanical_focus=(
                "THE HIP-CLICK EXIT CRITERION. No increase in Coxa Saltans frequency under "
                "loaded squat work is what releases the horse-stance and Cossack deferrals in "
                "the flexibility cluster. Record a clean or not-clean verdict either way — the "
                "hold is judged on its condition, never expired by a date."
            ),
            progression="No increase in click frequency → the deferred movements can be reconsidered.",
            regression="More frequent or newly painful → the deferrals stand and the physio hears "
                       "about it.",
        ),
        _ex(
            name="5-Minute Walk + Stair Assessment",
            ex_type="duration",
            sets=1, duration_minutes=7, rest_seconds=0,
            mechanics=(
                "Walk briskly five minutes, then up and down a flight of stairs twice. Rate pain "
                "at each point and compare against the Stage 2A Day 28 numbers. Log the final "
                "working loads on all six primary lifts here as the new baseline. If the second "
                "weekly cluster session has been earned by two clean weeks, this evening is "
                "where it goes — the integration protocol's same-day-evening slot, rather than "
                "a sixth session in the week."
            ),
            biomechanical_focus=(
                "Integrated functional outcome, plus the data Block B is authored from: final "
                "loads, the hip-click verdict, how the band fortnight actually went, and "
                "whether the running introduction produced any left hip flexor signal."
            ),
            progression="Pain <=2/10 throughout and the run progression on track → Block B builds "
                        "toward the 10 km from here.",
            regression="Pain >3/10, or a left hip flexor signal from the running → Block B starts "
                       "with more run/walk, and that is a normal outcome rather than a setback.",
        ),
    ],
}


# ═════════════════════════════════════════════════════════════════════════════
#  THE ACCESSORY SESSION — content only.  Added 2026-08-16.
# ═════════════════════════════════════════════════════════════════════════════
#
# A second, short session offered on the training page's "+" button, chosen
# automatically from today's and yesterday's REGIONAL strain. This module holds
# the WHAT; services/accessory.py holds the choosing, and views/training.py
# renders it through the same guided flow the plan session uses. The split is
# the mechanics -> battery -> prescription idiom the flexibility cluster already
# runs on, and a test fails if the choosing leaks in here.
#
# WHY IT IS NOT A SIXTH SESSION. STAGE_CONSTRAINTS[2]["session_freq_max"] is 5
# and weeks 3-4 of this block already sit at exactly 5. What this session is,
# instead, is the family the repo already runs daily and the physiotherapist
# already cleared: release work at ~50% effort inside a ~10-minute dose, which
# docs/training/release_protocols_2026-08-10.md states in terms is "not a
# training stressor". Two such protocols were already prescribed and lived only
# in a document, i.e. only in memory. This puts them in the app and lets the
# regional strain decide what, if anything, gets ACTIVATED beside them.
#
# THREE RULES SHAPE EVERY ITEM BELOW, and none of them is a preference:
#
#   1. NEVER A HELD CORRECTED POSTURE. The athlete asked for a fix for rounded
#      shoulders and an arched back, and the obvious answer — hold the corrected
#      position — is the one route the record already shows failing: the
#      2026-07-06 entry is a genuine left iliocostalis/QL strain produced by
#      carrying a swayback correction through a whole walk, and its own lesson
#      is that "a comfortable posture change is not a conditioned one". So the
#      fix here is release plus SHORT-EFFORT activation, and nothing is cued to
#      be carried into the rest of the day.
#
#   2. SHORT EFFORTS, NOT LONG HOLDS. SCAPULAR_ISOMETRIC carries the argument in
#      full: at matched loading time four 3-second contractions more than
#      doubled the stiffness gain of one 12-second hold, the 45-second hold is
#      n=6 about analgesia with three failed replications, and the tissue here
#      is perfusion-limited left trapezius, where a sustained low-level
#      contraction is the PROVOCATIVE mechanism. Scapular holds stay under 30 s.
#
#   3. ~50% EFFORT, PAIN <=2/10, RAMP IN AND OUT OVER 3-5 s. The annex's shared
#      conduct rules. This is the line between a release session and a sixth
#      training session, and it is why the session RPE target is 2-3.
#
# NAMES ARE REUSED DELIBERATELY. Where an exercise already exists in a plan its
# NAME is kept exactly, even where the accessory dose is shorter, so that
# training_constants' three maps and services/flexibility's leg-day allow-list
# carry one definition of each name rather than two that can drift.

# ─── Slot 1: decompress.  THE HANG LADDER ────────────────────────────────────
#
# Cluster D section A prescribes hanging outright, names feet-supported hangs as
# a legitimate starting point, and says daily short exposures beat one long
# weekly block. Against that: three anterior dislocations, a failed capsular
# wrap and a Latarjet on a shallow glenoid, with stability now MUSCULAR rather
# than ligamentous — so a fully passive hang asks the restraint that is not
# there to hold the joint, which is also what the hypermobility profile says to
# avoid.
#
# Both are true, so the hang is a LADDER rather than a yes or a no. Step 3 is
# authored but held: services/accessory.HANG_MAX_STEP keeps it out of any
# session until it is earned, in the cluster_a_mechanics.DEFERRED idiom, because
# it is the only step that is genuinely passive end-range loading on a
# stabilised shoulder.
#
# ADVANCE ON TWO CLEAN WEEKS, never on a good day. Drop a step on any
# apprehension, any instability sensation, any right-shoulder ache that outlasts
# the session, or any rise in the interscapular reading; twice means back to
# step 1 and an entry in symptom_log. Re-test at EIGHT weeks, not four — the
# source's own timescale, and it says to treat a null as informative rather than
# as a reason to try harder.

HANG_FEET_SUPPORTED = _ex(
    name="Dead Hang (Feet Supported)",
    ex_type="hold",
    sets=3, hold_seconds=20, rest_seconds=45,
    mechanics=(
        "Set the bar low enough, or use a box, that your feet stay on the ground and take "
        "some of your weight. Take an overhand grip a little wider than your shoulders. "
        "BOTH HANDS, ALWAYS. Let the weight come onto your arms gradually — never a "
        "shrug-and-drop — and keep the shoulders ACTIVE: shoulder blades gently pulled down "
        "away from your ears, not collapsed up around them. Twenty seconds, then stand up "
        "and let go. Take as much weight through the feet as you need to keep that position."
    ),
    biomechanical_focus=(
        "Axial decompression and overhead exposure, entered at the step the shoulder cluster "
        "itself names as a legitimate start. Feet on the floor is what makes this a "
        "controlled-range position rather than passive end-range loading — which at Beighton "
        "6/9, on a shoulder whose stability is muscular rather than ligamentous, is the "
        "distinction that matters."
    ),
    progression=("Two clean weeks at this step, no apprehension and no right-shoulder ache "
                 "afterwards -> Active Hang. Never advance on one good day."),
    regression=("Anything at the right shoulder -> take more weight through the feet and "
                "shorten to 10 seconds. There is no rush; this works on a months timescale."),
    warning=(
        "STOP the hang for the day on any of these at the RIGHT shoulder: a hard, abrupt, "
        "unspringy end-feel; any sense the joint might go; any apprehension. On a stabilised "
        "shoulder a hard end-feel may be doing load-bearing work, and it is not something to "
        "push on. Never hang from one arm."
    ),
)

HANG_ACTIVE = _ex(
    name="Active Hang",
    ex_type="hold",
    sets=3, hold_seconds=15, rest_seconds=60,
    mechanics=(
        "Full bodyweight now, feet off the floor, overhand grip, BOTH HANDS. Step up to the "
        "bar rather than jumping to it. Keep the shoulders ON the whole time — blades pulled "
        "down and back so your ears stay clear of your shoulders — and hold that. Fifteen "
        "seconds. Step down under control; do not drop off."
    ),
    biomechanical_focus=(
        "The same exposure with the muscles doing the holding. This is the step that suits "
        "this body: control rather than range is where the return is on a post-Latarjet "
        "shoulder, and the cluster's own reading is that the scapular, cuff and puller "
        "patterns — all control — are the likely priorities here."
    ),
    progression=("Two clean weeks holding the shoulders on for the full fifteen seconds -> "
                 "the passive step becomes reviewable. It is held, not scheduled."),
    regression="Shoulders creep up toward the ears -> back to the feet-supported step.",
    warning=(
        "STOP the hang for the day on a hard, abrupt end-feel at the right shoulder, on any "
        "apprehension, or on any instability sensation. Never one arm at a time."
    ),
)

HANG_PASSIVE = _ex(
    name="Passive Dead Hang",
    ex_type="hold",
    sets=3, hold_seconds=30, rest_seconds=60,
    mechanics=(
        "Full bodyweight, BOTH HANDS, and this time the shoulders are allowed to relax up "
        "toward the ears. Step up to the bar, settle, and let the tissue take it for thirty "
        "seconds. Accumulate two to three minutes across the sets. Step down under control."
    ),
    biomechanical_focus=(
        "The source's own endpoint, and the only step that is genuinely passive end-range "
        "loading. Held out of the session by services/accessory.HANG_MAX_STEP until the "
        "active step has run clean for two weeks — not because the physio prohibited it, but "
        "because nobody has been asked, and this is the one item here where the shoulder "
        "history and the source document disagree."
    ),
    progression="Accumulating 2-3 minutes comfortably -> that is the dose asked for; hold there.",
    regression="Any right-shoulder complaint -> straight back to the active step and stay there.",
    warning=(
        "HELD BY DESIGN. If this ever appears in a session, the two-clean-week condition was "
        "met deliberately. Both hands always — never one arm, at any step of this ladder. "
        "Stop on any apprehension, any instability sensation, or any hard, abrupt end-feel "
        "on the right."
    ),
)

#: The three steps, easiest first. services/accessory.py picks one; it never
#: picks more than one, and HANG_MAX_STEP bounds which are reachable.
ACCESSORY_HANG_LADDER = (HANG_FEET_SUPPORTED, HANG_ACTIVE, HANG_PASSIVE)


# ─── Slot 3: release B, upper.  Protocol 1, out of the document ──────────────
#
# docs/training/release_protocols_2026-08-10.md Techniques A and B, which the
# physiotherapist prescribed on 2026-08-10 and which have run daily from a
# document ever since. They are one prescription in two techniques and are kept
# together for that reason, which is why the upper recipe is the only one that
# runs to seven items.

PEC_SCAR_RELEASE = _ex(
    name="Pec & Scar Release (Right)",
    ex_type="hold",
    sets=2, hold_seconds=60, rest_seconds=15,
    mechanics=(
        "Stand facing a wall with a massage ball between the wall and the upper-RIGHT chest, "
        "just below the outer third of the collarbone, angled in toward the bony knob at the "
        "front of the shoulder. This is not rolling. Pin one tender spot with steady pressure "
        "and then MOVE THE ARM slowly — from resting at your side to reaching forward and "
        "slightly up, palm turning out — five or six slow passes, then find the next spot. "
        "For the scar itself: lie on your back and use fingertips beside the scar line, not "
        "raking along it, with small slow circles and gentle skin-glide each way."
    ),
    biomechanical_focus=(
        "The diagnosis is scar adhesion plus high resting tone in a shortened range — not a "
        "short muscle — which is why release applied THROUGH movement is expected to "
        "outperform stretching here. This is also the front half of the rounded-shoulder "
        "answer: the retractors are being asked to work against a front wall that is gripping."
    ),
    progression="Spots that talked back going quiet -> drop to twice a week; that is the endpoint.",
    regression=("A week of finding nothing tender -> the local job is done. Unchanged after two "
                "weeks means self-release is not enough and it goes to the physio for hands-on "
                "work, which is the shoulder cluster's own answer."),
    warning=(
        "Pain never above 2/10. Move off immediately on any point-specific ice-pick feeling, on "
        "any tingling, numbness or ache running into the arm — that is nerve — and on any pulse "
        "under the pressure, which is a vessel. Never press into the hollow of the armpit."
    ),
)

ANTERIOR_SHOULDER_RECIPROCATION = _ex(
    name="Anterior Shoulder Reciprocation (Right)",
    ex_type="reps",
    sets=3, reps=1, rest_seconds=30,
    mechanics=(
        "Sit with the RIGHT elbow resting on the right knee, forearm hanging, elbow and "
        "shoulder in one vertical line — the arm stays LOW and close to the body throughout. "
        "One cycle: press the palm gently inward against your other hand, building over 3-5 "
        "seconds, hold 5 seconds at tension rather than maximum — about half effort, no "
        "shaking — then ease out over 3-5 seconds. Then actively rotate the forearm OUTWARD "
        "to its comfortable end range under its own power and HOLD ten seconds. That is one "
        "cycle. Three of them, varying the elbow angle each time — more open, more closed — "
        "biased toward wherever the front of the shoulder feels LONG."
    ),
    biomechanical_focus=(
        "Active work biased toward the long position, which is the opposite of the position "
        "that cramps. The arm stays low because external rotation at 90 degrees of abduction "
        "is the apprehension position the Latarjet exists to protect, and that is a geometric "
        "limit rather than a matter of load."
    ),
    progression="Comfortable at ten seconds -> build the outward hold toward thirty over two weeks.",
    regression=("The lock-out cramp appears -> the position has drifted too short. Open the "
                "elbow angle rather than pushing through it."),
    warning=(
        "NEVER external rotation at 90 degrees of abduction on this side. Stop on any "
        "ice-pick sensation, anything running into the arm, any instability feeling, or any "
        "hard, abrupt, unspringy end-feel on the outward rotation — on a stabilised shoulder "
        "that restriction may be load-bearing."
    ),
)


# ─── Slot 3: release B, lower.  The other half of the arched back ────────────
#
# Stage 1 carried three hip-flexor items; they vanished at the Stage 2A
# transition with no recorded reason, leaving the deep hip flexors the only
# structure on the overactive list with no release anywhere in the block — while
# the imaging names psoas hypertonicity as what amplifies the L5/S1 compression.
# ANTERIOR_HIP_RELEASE closed half of that in week 3. This closes the other half
# at a dose the accessory budget can carry: 45 s a side rather than Stage 1's 90.

ACC_STANDING_HIP_FLEXOR = _ex(
    name="Standing Hip Flexor Release",
    ex_type="hold",
    laterality="unilateral",
    sets=1, hold_seconds=45, rest_seconds=15,
    mechanics=(
        "Stand facing a wall and step ONE foot forward onto a low step or a thick book, that "
        "knee at about 90 degrees. Back foot on the floor, back knee soft. TUCK THE PELVIS "
        "UNDER FIRST — tailbone down, lower back long — and only then shift the hips forward "
        "until you feel a deep stretch at the FRONT of the back hip. The tuck is the "
        "exercise; if you arch the lower back to get more range you have taken the stretch "
        "off the hip flexor and put it into the spine. Forty-five seconds, then the other side."
    ),
    biomechanical_focus=(
        "Psoas lengthening at its L1-L4 anterior attachment. This is the direct answer to the "
        "arched back: the habitual standing pattern is anterior pelvic tilt with short psoas, "
        "iliacus and rectus femoris against relatively underactive glutes and anterior core, "
        "so the correction is to lengthen the front and switch on the back — never to hold a "
        "corrected posture."
    ),
    progression="Comfortable and the tuck holds -> deepen the tuck rather than reaching further forward.",
    regression="Lower back complains -> shorten the forward shift; the tuck matters, the range does not.",
    warning=(
        "Your sense of neutral is calibrated to the habitual anterior tilt, so a genuinely "
        "neutral pelvis will feel further tucked than it is. Trust the cue, not the feeling."
    ),
)


# ─── Slot 4: activate.  Shorter doses of the block's own items ───────────────
#
# Every name here already exists in the block. The doses are cut so the session
# lands in the release family rather than becoming training: this is meant to
# support the day's real session, not compete with it.

ACC_THORACIC_EXTENSION = _ex(
    name="Thoracic Extension (Rolled Towel)",
    ex_type="hold",
    sets=2, hold_seconds=45, rest_seconds=20,
    mechanics=(
        "Lie back over a rolled towel placed across the MID-back, knees bent, arms overhead. "
        "Breathe into it for forty-five seconds, then move the towel a few centimetres up or "
        "down the spine and repeat. Ribs stay down — if they flare, or the lower back starts "
        "taking it, bend the knees more and breathe out longer."
    ),
    biomechanical_focus=(
        "The T6-T10 segments that sitting stiffens. A thoracic spine stuck in flexion tilts "
        "the shoulder blade forward off the ribcage and leaves the retractors holding "
        "LENGTHENED all day, which is a mechanically losing position — so this is the "
        "mobility half of the rounded-shoulder answer and the retraction work is the strength "
        "half."
    ),
    progression="Comfortable -> reach the arms further overhead, not further into extension.",
    regression="Ribs flare or the low back arches -> more knee bend, longer exhale, smaller range.",
    warning=(
        "THORACIC ONLY. End-range lumbar extension is contraindicated against the L5/S1 "
        "retrolisthesis and the narrowed right foramen. Stop where the lower back starts to "
        "take it."
    ),
)

ACC_SIDE_BRIDGE_SHORT = _ex(
    name="Full Side Bridge",
    ex_type="hold",
    laterality="unilateral",
    sets=2, hold_seconds=20, rest_seconds=30,
    mechanics=(
        "On your side, elbow under the shoulder, feet stacked. Lift the hips until head, hips "
        "and feet are in one line and hold twenty seconds. Then the other side. Deliberately "
        "well short of the block's own dose — this is a reminder for the lateral trunk, not a "
        "set."
    ),
    biomechanical_focus=(
        "Lateral trunk endurance at a dose that costs nothing. The deep core stabilisers are "
        "the second of the two underactive structures, and the record shows them turning off "
        "under fatigue rather than being absent."
    ),
    progression="Twenty seconds a side is easy -> that is the block's job, not this session's.",
    regression="Hips sag -> drop to the knees and keep the line.",
)

ACC_BREATHING = _ex(
    name="Prone Decompression Breathing",
    ex_type="duration",
    sets=1, duration_minutes=2, rest_seconds=0,
    mechanics=(
        "Lie face down, arms by your sides or folded under your forehead. Breathe deeply into "
        "your lower back and let the belly expand into the floor on each inhale. Completely "
        "passive — no movement at all. Two minutes. A folded towel under the abdomen if it is "
        "uncomfortable."
    ),
    biomechanical_focus=(
        "The close. Diaphragmatic breathing inhibits the psoas — they sit against each other "
        "at L1-L4 — so this both finishes the session and re-states its whole point: this "
        "session down-regulates, and the day's real session is where the work happens."
    ),
    progression="Comfortable -> stay for the full two minutes rather than adding anything.",
    regression=("Uncomfortable face down -> towel under the abdomen, or lie on your back with "
                "the knees bent instead."),
    warning="Stop immediately on any tingling or numbness in a leg in this position.",
)
