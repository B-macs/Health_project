"""
training_plan.py — 14-Day Progressive Bodyweight Rehab Plan.

Generated for: Patient — Stage 1 Rehab
MRI basis: L5/S1 activated osteochondrosis + retrolisthesis + right dorsolateral
disc protrusion (moderate right foraminal stenosis). L3/4 and L4/5 flat protrusions
left dorsolateral with covered annulus tears. Downstream: psoas/hip flexor
hypertonicity amplifying L5/S1 compression.

EQUIPMENT: Bodyweight only. Household items permitted (rolled towel, chair, book, wall).
ACWR ceiling: 1.2 (Stage 1). Session RPE ceiling: 7/10.

Exercise type keys:
  "reps"       — counted repetitions (user counts)
  "hold"       — single timed isometric hold per set
  "hold_reps"  — X reps each with Y-second hold (e.g., McGill Curl-Up)
  "duration"   — continuous timed activity (walking, breathing)

# DETERMINISTIC-ONLY: all prescriptions derived from MRI findings and evidence-based
# lumbar disc rehabilitation protocols (McGill, Danneels, Hides).
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
    }


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
            name="Supine Figure-4 Piriformis Stretch",
            ex_type="hold",
            laterality="unilateral",
            sets=3, hold_seconds=45, rest_seconds=60,
            mechanics=(
                "Lie on your back, both knees bent. "
                "Cross your RIGHT ankle over your LEFT knee — the crossed leg looks like a figure '4'. "
                "Option A: Push the crossed knee gently AWAY from you with one hand. "
                "Option B: Interlace hands behind the left thigh and draw BOTH legs toward your chest. "
                "Feel the stretch in the outer buttock of the crossed leg. "
                "Hold. Switch sides."
            ),
            biomechanical_focus="Piriformis + external hip rotator release — reduces SI joint compression and downstream neural irritation in the L5/S1 distribution.",
            progression="Pain free → add a gentle ankle dorsiflexion on the crossed foot to add sciatic nerve component.",
            regression="Sharp buttock pain → try Option A only with less push. If still painful, skip.",
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
                "Complete all reps on one side before switching."
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
                "Any score that has increased = flag for physiotherapist review."
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
                "Switch legs. Complete all sets."
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
                "This is ACTIVE mobility — use your muscles to move, not momentum."
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
                "Complete all reps. Switch sides."
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
                "Log this in session notes."
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
