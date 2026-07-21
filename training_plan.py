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
        "exercises": [
            UPPER_GLUTE_RELEASE, PIRIFORMIS_PNF, RIGHT_HIP_CAPSULE_REVISED, COXA_SALTANS_DRILL,
            _ex(
                name="Goblet Squat",
                ex_type="reps",
                sets=3, reps=8, tempo=squat_tempo, rest_seconds=90,
                weight_kg=squat_kg,
                equipment_type="dumbbell",
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
                mechanics="Cable at upper-chest height. Pull toward your face, elbows high, squeezing the shoulder blades together and down at the end.",
                biomechanical_focus="Scapular control and rear-delt/rotator-cuff work — always paired with pressing per finding #6, and a documented strength pattern (fast-track progression).",
                progression="12 clean reps, full scapular squeeze → +2.5kg next exposure (fast-track).",
                regression="Shrugging instead of scapular squeeze → reduce load until the movement is clean.",
            ),
            _ex(
                name="Pallof Press (Cable)",
                ex_type="reps",
                laterality="unilateral",
                sets=3, reps=10, rest_seconds=60,
                weight_kg=pallof_kg,
                equipment_type="cable",
                mechanics="Cable at chest height, stand side-on, press the handle straight out and back in without letting the cable rotate your trunk.",
                biomechanical_focus="Anti-rotation core control under real load — addresses finding #5 and the rotation-under-load caution with a controlled, non-rotational pattern.",
                progression="10 reps each side with zero trunk rotation → small load increase next exposure.",
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
