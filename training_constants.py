"""
training_constants.py — Deterministic training reference data.

Moved from pages/1_Training_Entry.py — these are data, not display logic.
Import from here in any page or module that needs exercise lists or enums.
"""

# Exercise catalogue grouped by movement type
EXERCISES: dict[str, list[str]] = {
    "Rehab": [
        "Cat-Cow",
        "Bird-Dog",
        "Dead Bug",
        "McGill Curl-Up",
        "McGill Side Bridge",
        "Glute Bridge",
        "Single-Leg Glute Bridge",
        "Hip Flexor Stretch",
        "Piriformis Stretch (Figure 4)",
        "Child's Pose",
        "Knee-to-Chest",
        "Pallof Press",
        "Clamshell",
        "Lateral Band Walk",
        "Standing Hip Flexor Hold (Isometric)",
        "Wall Sit",
        "Prone Hip Extension",
    ],
    "Weight": [
        "Romanian Deadlift",
        "Hip Hinge",
        "Goblet Squat",
        "Bulgarian Split Squat",
        "Step-Up",
        "Good Morning",
        "Face Pull",
        "Reverse Hyper",
    ],
    "Conditioning": [
        "Walking",
        "Swimming",
        "Stationary Cycling",
        "Rowing (Light)",
    ],
    "Stretch": [
        "Hip Flexor Stretch",
        "Hamstring Stretch",
        "Piriformis Stretch",
        "Thoracic Rotation",
        "Child's Pose",
        "Doorway Pec Stretch",
    ],
}

# Flat list for selectboxes
ALL_EXERCISES: list[str] = [ex for exs in EXERCISES.values() for ex in exs]

MOVEMENT_TYPES: list[str] = list(EXERCISES.keys())

# Movement velocity — proxy for execution quality; fed into trend analysis
VELOCITY_OPTIONS: list[str] = [
    "Smooth/Controlled",
    "Explosive",
    "Sluggish",
    "Compensated",
]

# Anatomical location picker — injury-specific (L-spine → hip kinetic chain from MRI)
ANATOMICAL_LOCATIONS: list[str] = [
    "Lumbar — L3/L4 (Left)",
    "Lumbar — L4/L5 (Left)",
    "Lumbar — L5/S1 (Right — Primary)",
    "Lumbar — L5/S1 (Left)",
    "Central Lower Back",
    "Sacroiliac Joint — Right",
    "Sacroiliac Joint — Left",
    "Hip Flexor / Psoas — Right",
    "Hip Flexor / Psoas — Left",
    "Glute — Right",
    "Glute — Left",
    "Glute Medius — Right",
    "Glute Medius — Left",
    "Piriformis — Right",
    "Piriformis — Left",
    "Hamstring — Right",
    "Hamstring — Left",
    "Calf — Right",
    "Calf — Left",
    "Thoracic / Mid Back",
    "Upper Back — General",
    "Upper Back — Rhomboids",
    "Upper Back — Trapezius",
    "Other",
]

# Sensation tags for daily readiness
SENSATION_TAGS: list[str] = [
    "Normal",
    "Tight",
    "Stiff",
    "Dull Ache",
    "Sharp",
    "Neural",
    "Mild Tiredness",
    "Very Tight",
    "Slightly Tired",
]

# ─────────────────────────────────────────────────────────────────────────────
#  Exercise → body region — feeds services/strength.py (which region an
#  estimated 1RM belongs to) and services/tonnage.py (which sector a week's
#  kilograms are credited to). ONE primary region per exercise: that is what
#  makes upper + core + lower == overall an identity in tonnage rather than an
#  approximation, so a compound lift's whole tonnage goes to its primary sector
#  and is never split. Every exercise name that appears in training_plan.py's
#  PLAN is listed once below.
#  training_plan.py is a self-contained exercise universe (doesn't reference
#  EXERCISES above), so this map is scoped to its names, not EXERCISES'.
#
#  Maintenance: Stage 2 (training_plan.PLAN_STAGE2) is now built and its new
#  exercise names are included below. Any *future* block's new exercise names
#  need an entry here too, or services.strength and services.tonnage will
#  silently skip them (an exercise absent from this map counts toward no region
#  at all, rather than raising). services.tonnage.weekly_tonnage returns the
#  names it could not map as its second value, which is the cheapest way to
#  notice; "Week 1 Self-Assessment" is the only expected member of that set.
#
#  "Week 1 Self-Assessment" is deliberately absent — it's a subjective
#  checkpoint (pain/tightness self-rating), not a physical exercise with a
#  muscle target, so it shouldn't count toward any region.
# ─────────────────────────────────────────────────────────────────────────────

_UPPER_BODY_EXERCISES: tuple[str, ...] = (
    "Scapular Wall Slide",
    "Prone Y-Raise (Scapular)",
    "Thoracic Extension (Rolled Towel)",
    "Thread-the-Needle (Thoracic Rotation)",
    # Stage 2A additions
    "Incline DB Press",
    "Face Pull (Cable)",
    "Lat Pulldown",
    "Single-Arm DB Row",
)

_CORE_EXERCISES: tuple[str, ...] = (
    "Supine Knee-to-Chest",
    "Supine Knee-to-Chest (Bilateral)",
    "Cat-Cow",
    "Cat-Cow (Slow Flow)",
    "Prone Decompression Breathing",
    "Supine Knees-to-Chest (Bilateral Rock)",
    "McGill Modified Curl-Up",
    "Bird-Dog",
    "Bird-Dog (Extended Hold)",
    "Bird-Dog with Full Reach",
    "Side Bridge (Modified — Bent Knee)",
    "Dead Bug",
    "Dead Bug (Progression — 3s Hold)",
    "Diaphragmatic Breathing",
    "Supine Full-Body Stretch",
    "McGill Curl-Up (Progressed)",
    "Full Side Bridge",
    "Pallof Press Hold (Doorframe)",
    "Side Bridge with Hip Dip",
    "Forearm Plank",
    "McGill Big 3 — Quality Screen",
    "Child's Pose",
    # Stage 2A additions
    "Pallof Press (Cable)",
)

_LOWER_BODY_EXERCISES: tuple[str, ...] = (
    "Upper Glute / TFL Self-Release",
    "Right Posterior Hip Capsule Stretch",
    "Piriformis Contract-Relax (PNF)",
    "Ischial Tuberosity Hamstring Release",
    "Right Hip Tendon Path Drill (Coxa Saltans)",
    "Right Posterior Hip Capsule Stretch (Revised Cue)",
    "Standing Hip Flexor Release",
    "90/90 Hip Flexor Hold",
    "Side-Lying Hip Abduction",
    "Supine Hip Flexion (Marching)",
    "Supine Glute Bridge (Bilateral)",
    "Clamshell",
    "Prone Hip Extension (Single Leg)",
    "Standing Hip Hinge (Wall Glute Touch)",
    "Wall Sit (Isometric Quad)",
    "Wall Sit (Extended Duration)",
    "Wall Sit",
    "Lateral Step Walk",
    "Supine Knee Fallout (Butterfly)",
    "Controlled Walking",
    "Assessment Walk + Stair Check",
    "Glute Bridge (Eccentric Single Load)",
    "Glute Bridge",
    "Glute Bridge March",
    "Single-Leg Glute Bridge",
    "RDL Hip Hinge to Wall",
    "Single-Leg RDL (Wall Support)",
    "Single-Leg Balance",
    "Single-Leg Balance (Eyes Closed)",
    "Lateral Step-Up (Single Stair)",
    "Forward Step-Up (Stair)",
    "Reverse Lunge",
    "Lateral Lunge",
    "Sciatic Nerve Floss",
    "Standing Calf Raise (Eccentric Focus)",
    "Prone Hip Extension (Slow Tempo — 4-3-5)",
    "Hip 90/90 Flow",
    "Chair Sit-to-Stand",
    "Walking — Gait Focus",
    "Hip Hinge Full Range Assessment",
    "5-Minute Walk + Stair Assessment",
    "Wall-Supported Hip Hinge",
    # Stage 2A additions
    "Goblet Squat",
    "Romanian Deadlift (DB)",
    "Hip Thrust (Loaded)",
    "Bulgarian Split Squat",
    "Lateral Band Walk",
    # Garmin-imported outdoor activities (services/sessions.py
    # OUTDOOR_EXERCISE_BY_TYPE) — lower_body so an imported hike counts as
    # a leg day everywhere one definition of "a leg day" is read
    # (flexibility retest spacing, sector tonnage).
    "Outdoor Hike",
    "Outdoor Walk",
    "Outdoor Trail Run",
    "Outdoor Run",
    "Outdoor Activity",
)

EXERCISE_BODY_REGION: dict[str, str] = {
    **{name: "upper_body" for name in _UPPER_BODY_EXERCISES},
    **{name: "core" for name in _CORE_EXERCISES},
    **{name: "lower_body" for name in _LOWER_BODY_EXERCISES},
}

# ─────────────────────────────────────────────────────────────────────────────
#  The regions' DISPLAY identity — one definition, read by views/insights.py's
#  Strength screen and by the Strain drill-down. Colour, label and faceplate
#  geometry live here beside EXERCISE_BODY_REGION because they name the same
#  three things; two copies would eventually disagree, and a core that is one
#  yellow on one screen and another yellow on the next is a bug the eye notices
#  long before any test does.
#
#  `ratio` is each faceplate's NATIVE aspect ratio
#  (background_templates/body_faceplates_v2/). The three plates stack into one
#  continuous figure ONLY where they render at the same displayed width — true
#  on the 1600px Strength screen, deliberately abandoned in the 480px Home
#  column, where the text block is taller than two of the three plates.
# ─────────────────────────────────────────────────────────────────────────────

REGION_DISPLAY: dict[str, dict] = {
    "upper_body": {"name": "Upper body", "short": "Upper",
                   "colour": "#FF8C42", "ratio": "893/640"},
    "core":       {"name": "Core",       "short": "Core",
                   "colour": "#E8B04B", "ratio": "893/428"},
    "lower_body": {"name": "Lower body", "short": "Lower",
                   "colour": "#D9663A", "ratio": "893/534"},
}

# ─────────────────────────────────────────────────────────────────────────────
#  Exercise → how its load DISTRIBUTES across the three regions.
#
#  A REFINEMENT of EXERCISE_BODY_REGION, never a replacement. That map answers
#  "which one sector owns this movement" and three things need exactly that
#  answer: services/tonnage.py (splitting a lift's kilograms across regions
#  would put fictional weight in a sector), services/strength.py (an e1RM is a
#  property of one movement pattern), and services/flexibility.py's
#  leg_loading_days, which reads == "lower_body" as the boolean that sets the
#  retest calendar. This map answers a different question — "where did the
#  STRAIN of this movement land" — and only services/strain_regions.py reads it.
#
#  The two are bound by test, not by convention: tests/test_region_shares_
#  coverage.py asserts that every entry's dominant region equals its
#  EXERCISE_BODY_REGION value, with a STRICT winner. They cannot drift.
#
#  ⚠ EVERY NUMBER BELOW IS INVENTED. No source supplies them; there is no
#  per-region load measurement anywhere in this system to validate them
#  against, and there is no ground truth to acquire (that is the same blocking
#  problem services/sleep_fusion.py records for the quiet-wake rule). So they
#  are flagged REGION_SHARES_BASIS = "provisional" in the
#  services/battery.py BASIS_PROVISIONAL sense, the flag reaches the screen,
#  and the REVERT CONDITION is written in the HRV_GARMIN_HOLD idiom:
#  revise on the athlete's or the physiotherapist's review of this table, or on
#  measured per-region evidence — never on a date.
#
#  Three authoring rules, all enforced by test:
#
#  1. ALL THREE KEYS ALWAYS PRESENT, explicit zeros. A sparse dict makes
#     "0.00 because this genuinely does not load that region" indistinguishable
#     from "the author forgot a key", and an unexplained absence must never be
#     indistinguishable from an oversight (cluster_a_mechanics.REMOVED's rule).
#  2. EVERY VALUE IS A MULTIPLE OF 0.05, and nothing lies strictly between 0.00
#     and 0.05. A 0.02 in an invented table is false precision — it claims a
#     resolution nobody has. 0.00 is permitted and MEANS something: "this does
#     not load that region in any way worth counting". 0.05 is the floor for
#     any non-zero claim.
#  3. EVERY ENTRY SUMS TO 1.0 EXACTLY. That is what keeps
#     upper + core + lower == the session's whole AU an identity rather than an
#     approximation — the same property tonnage.py protects by never splitting
#     a lift. services/strain_regions.py renormalises a non-unit vector at read
#     time AND reports the name, so a typo degrades rather than crashing a
#     health page; the test is what stops it living there forever.
#
#  A MOVEMENT FAMILY SHARES ONE TRIPLE. Both Right Posterior Hip Capsule
#  Stretch entries, the three Wall Sits, the two Cat-Cows, the three Bird-Dogs,
#  the two Dead Bugs, the two Single-Leg Balances, and the whole walking family
#  (Controlled Walking / Walking — Gait Focus / the two walk assessments /
#  Outdoor Walk) are identical, so the same movement never changes its split
#  because a training block renamed it. Pinned by test.
#
#  "Week 1 Self-Assessment" is deliberately absent, exactly as it is absent
#  from EXERCISE_BODY_REGION — it is a subjective checkpoint, not a movement.
#  It falls to the even-thirds default and is NAMED in the result's
#  unmapped_names, never silently zeroed.
# ─────────────────────────────────────────────────────────────────────────────

REGION_SHARES_BASIS: str = "provisional"
#: Bump on ANY numeric revision below, so a stored or cached figure can be told
#: apart from one computed under different weights.
REGION_SHARES_VERSION: int = 1

EXERCISE_REGION_SHARES: dict[str, dict[str, float]] = {
    # ── Upper body ──────────────────────────────────────────────────────────
    # Scapular/thoracic work: the thoracic drills are half trunk and say so.
    "Scapular Wall Slide":                    {"upper_body": 0.90, "core": 0.10, "lower_body": 0.00},
    "Prone Y-Raise (Scapular)":               {"upper_body": 0.90, "core": 0.10, "lower_body": 0.00},
    "Thoracic Extension (Rolled Towel)":      {"upper_body": 0.70, "core": 0.30, "lower_body": 0.00},
    "Thread-the-Needle (Thoracic Rotation)":  {"upper_body": 0.65, "core": 0.35, "lower_body": 0.00},
    # Loaded upper: bench-supported and pad-restrained lifts give the legs
    # nothing to do; the standing/unilateral ones are anti-rotation tasks.
    "Incline DB Press":                       {"upper_body": 0.85, "core": 0.15, "lower_body": 0.00},
    "Lat Pulldown":                           {"upper_body": 0.90, "core": 0.10, "lower_body": 0.00},
    "Face Pull (Cable)":                      {"upper_body": 0.90, "core": 0.10, "lower_body": 0.00},
    "Single-Arm DB Row":                      {"upper_body": 0.75, "core": 0.20, "lower_body": 0.05},

    # ── Core ────────────────────────────────────────────────────────────────
    # The only 1.00s in the table: single-region by design, nothing else works.
    "McGill Modified Curl-Up":                {"upper_body": 0.00, "core": 1.00, "lower_body": 0.00},
    "McGill Curl-Up (Progressed)":            {"upper_body": 0.00, "core": 1.00, "lower_body": 0.00},
    "Diaphragmatic Breathing":                {"upper_body": 0.00, "core": 1.00, "lower_body": 0.00},
    "Prone Decompression Breathing":          {"upper_body": 0.05, "core": 0.95, "lower_body": 0.00},
    # Side bridges and planks: the SUPPORT SHOULDER takes real load — which is
    # why the full version is regressed to bent-knee rather than to a shorter
    # hold. A 0.00 upper here would deny the reason for the regression.
    "Full Side Bridge":                       {"upper_body": 0.20, "core": 0.75, "lower_body": 0.05},
    "Side Bridge with Hip Dip":               {"upper_body": 0.20, "core": 0.75, "lower_body": 0.05},
    "Side Bridge (Modified — Bent Knee)":     {"upper_body": 0.15, "core": 0.80, "lower_body": 0.05},
    "Forearm Plank":                          {"upper_body": 0.20, "core": 0.75, "lower_body": 0.05},
    # Contralateral reach genuinely loads a shoulder and a glute.
    "Bird-Dog":                               {"upper_body": 0.15, "core": 0.70, "lower_body": 0.15},
    "Bird-Dog (Extended Hold)":               {"upper_body": 0.15, "core": 0.70, "lower_body": 0.15},
    "Bird-Dog with Full Reach":               {"upper_body": 0.15, "core": 0.70, "lower_body": 0.15},
    "Dead Bug":                               {"upper_body": 0.05, "core": 0.90, "lower_body": 0.05},
    "Dead Bug (Progression — 3s Hold)":       {"upper_body": 0.05, "core": 0.90, "lower_body": 0.05},
    # It IS the anti-rotation exercise; the arms hold the handle, the stance
    # resists. Both Pallof variants share one triple.
    "Pallof Press (Cable)":                   {"upper_body": 0.15, "core": 0.75, "lower_body": 0.10},
    "Pallof Press Hold (Doorframe)":          {"upper_body": 0.15, "core": 0.75, "lower_body": 0.10},
    "Cat-Cow":                                {"upper_body": 0.10, "core": 0.85, "lower_body": 0.05},
    "Cat-Cow (Slow Flow)":                    {"upper_body": 0.10, "core": 0.85, "lower_body": 0.05},
    # Supine knee-to-chest is lumbar decompression driven by hip flexion.
    "Supine Knee-to-Chest":                   {"upper_body": 0.00, "core": 0.70, "lower_body": 0.30},
    "Supine Knee-to-Chest (Bilateral)":       {"upper_body": 0.00, "core": 0.75, "lower_body": 0.25},
    "Supine Knees-to-Chest (Bilateral Rock)": {"upper_body": 0.00, "core": 0.75, "lower_body": 0.25},
    # Genuinely whole-body positions. Argmax still core, which is what keeps
    # them agreeing with EXERCISE_BODY_REGION.
    "Supine Full-Body Stretch":               {"upper_body": 0.20, "core": 0.55, "lower_body": 0.25},
    "Child's Pose":                           {"upper_body": 0.20, "core": 0.55, "lower_body": 0.25},
    "McGill Big 3 — Quality Screen":          {"upper_body": 0.05, "core": 0.90, "lower_body": 0.05},

    # ── Lower body: the pre-session release protocol ────────────────────────
    # Direct pressure on one structure, on the floor. The 0.00 UPPER is an
    # assertion worth making. The 0.05-0.10 core is not a measurement — a hard
    # 0.00 would read as "no trunk involvement at all", and this protocol is
    # explicitly a lumbo-pelvic intervention, which is a stronger claim than
    # the evidence supports in either direction.
    "Upper Glute / TFL Self-Release":                    {"upper_body": 0.00, "core": 0.10, "lower_body": 0.90},
    "Piriformis Contract-Relax (PNF)":                   {"upper_body": 0.00, "core": 0.10, "lower_body": 0.90},
    "Right Posterior Hip Capsule Stretch":               {"upper_body": 0.00, "core": 0.10, "lower_body": 0.90},
    "Right Posterior Hip Capsule Stretch (Revised Cue)": {"upper_body": 0.00, "core": 0.10, "lower_body": 0.90},
    "Right Hip Tendon Path Drill (Coxa Saltans)":        {"upper_body": 0.00, "core": 0.10, "lower_body": 0.90},
    # The most local of the six: one tissue under direct pressure.
    "Ischial Tuberosity Hamstring Release":              {"upper_body": 0.00, "core": 0.05, "lower_body": 0.95},

    # ── Lower body: hip mobility and activation ─────────────────────────────
    "Standing Hip Flexor Release":            {"upper_body": 0.00, "core": 0.15, "lower_body": 0.85},
    "90/90 Hip Flexor Hold":                  {"upper_body": 0.00, "core": 0.15, "lower_body": 0.85},
    "Hip 90/90 Flow":                         {"upper_body": 0.00, "core": 0.20, "lower_body": 0.80},
    "Supine Knee Fallout (Butterfly)":        {"upper_body": 0.00, "core": 0.20, "lower_body": 0.80},
    "Supine Hip Flexion (Marching)":          {"upper_body": 0.00, "core": 0.30, "lower_body": 0.70},
    "Side-Lying Hip Abduction":               {"upper_body": 0.00, "core": 0.15, "lower_body": 0.85},
    "Clamshell":                              {"upper_body": 0.00, "core": 0.15, "lower_body": 0.85},
    "Lateral Band Walk":                      {"upper_body": 0.00, "core": 0.15, "lower_body": 0.85},
    "Lateral Step Walk":                      {"upper_body": 0.00, "core": 0.15, "lower_body": 0.85},
    "Sciatic Nerve Floss":                    {"upper_body": 0.00, "core": 0.10, "lower_body": 0.90},
    "Standing Calf Raise (Eccentric Focus)":  {"upper_body": 0.00, "core": 0.05, "lower_body": 0.95},

    # ── Lower body: bridges and hip extension ───────────────────────────────
    # Unilateral bridging adds anti-rotation the bilateral version does not.
    "Supine Glute Bridge (Bilateral)":        {"upper_body": 0.00, "core": 0.20, "lower_body": 0.80},
    "Glute Bridge":                           {"upper_body": 0.00, "core": 0.20, "lower_body": 0.80},
    "Glute Bridge March":                     {"upper_body": 0.00, "core": 0.25, "lower_body": 0.75},
    "Glute Bridge (Eccentric Single Load)":   {"upper_body": 0.00, "core": 0.25, "lower_body": 0.75},
    "Single-Leg Glute Bridge":                {"upper_body": 0.00, "core": 0.25, "lower_body": 0.75},
    "Prone Hip Extension (Single Leg)":       {"upper_body": 0.00, "core": 0.20, "lower_body": 0.80},
    "Prone Hip Extension (Slow Tempo — 4-3-5)": {"upper_body": 0.00, "core": 0.20, "lower_body": 0.80},

    # ── Lower body: hinges, squats, steps ───────────────────────────────────
    # A hinge is where the erectors work, and this body carries two annulus
    # tears — the trunk share here is the highest of any lower-body family.
    "Romanian Deadlift (DB)":                 {"upper_body": 0.10, "core": 0.25, "lower_body": 0.65},
    "RDL Hip Hinge to Wall":                  {"upper_body": 0.05, "core": 0.25, "lower_body": 0.70},
    "Single-Leg RDL (Wall Support)":          {"upper_body": 0.05, "core": 0.25, "lower_body": 0.70},
    "Standing Hip Hinge (Wall Glute Touch)":  {"upper_body": 0.00, "core": 0.25, "lower_body": 0.75},
    "Wall-Supported Hip Hinge":               {"upper_body": 0.05, "core": 0.25, "lower_body": 0.70},
    "Hip Hinge Full Range Assessment":        {"upper_body": 0.05, "core": 0.25, "lower_body": 0.70},
    # The front-rack goblet position is a genuine anterior-core brace, and is
    # most of why this squat variant is the one prescribed for this athlete.
    "Goblet Squat":                           {"upper_body": 0.05, "core": 0.25, "lower_body": 0.70},
    "Bulgarian Split Squat":                  {"upper_body": 0.05, "core": 0.20, "lower_body": 0.75},
    # The most isolated loaded lift in the block.
    "Hip Thrust (Loaded)":                    {"upper_body": 0.00, "core": 0.20, "lower_body": 0.80},
    "Reverse Lunge":                          {"upper_body": 0.00, "core": 0.20, "lower_body": 0.80},
    "Lateral Lunge":                          {"upper_body": 0.00, "core": 0.20, "lower_body": 0.80},
    "Forward Step-Up (Stair)":                {"upper_body": 0.00, "core": 0.15, "lower_body": 0.85},
    "Lateral Step-Up (Single Stair)":         {"upper_body": 0.00, "core": 0.15, "lower_body": 0.85},
    "Chair Sit-to-Stand":                     {"upper_body": 0.00, "core": 0.15, "lower_body": 0.85},
    "Wall Sit":                               {"upper_body": 0.00, "core": 0.15, "lower_body": 0.85},
    "Wall Sit (Isometric Quad)":              {"upper_body": 0.00, "core": 0.15, "lower_body": 0.85},
    "Wall Sit (Extended Duration)":           {"upper_body": 0.00, "core": 0.15, "lower_body": 0.85},
    # Balance is a trunk task as much as a foot task.
    "Single-Leg Balance":                     {"upper_body": 0.00, "core": 0.30, "lower_body": 0.70},
    "Single-Leg Balance (Eyes Closed)":       {"upper_body": 0.00, "core": 0.30, "lower_body": 0.70},

    # ── Lower body: the walking family ──────────────────────────────────────
    # ONE triple across every name for the same movement, including the
    # Garmin-imported Outdoor Walk. A stroll does not change what it loads
    # because a training block called it something else.
    "Controlled Walking":                     {"upper_body": 0.05, "core": 0.10, "lower_body": 0.85},
    "Walking — Gait Focus":                   {"upper_body": 0.05, "core": 0.10, "lower_body": 0.85},
    "Assessment Walk + Stair Check":          {"upper_body": 0.05, "core": 0.10, "lower_body": 0.85},
    "5-Minute Walk + Stair Assessment":       {"upper_body": 0.05, "core": 0.10, "lower_body": 0.85},
    "Outdoor Walk":                           {"upper_body": 0.05, "core": 0.10, "lower_body": 0.85},

    # ── Lower body: the rest of the Garmin outdoor imports ──────────────────
    # The hike is the athlete's own worked example and is taken as given:
    # uneven ground and a pack make trunk stabilisation real, arm swing does
    # not. Trail running has the highest trunk demand of the five (impact plus
    # terrain plus rotation). "Outdoor Activity" is the catch-all — its name
    # means "we do not know what this was", so it is deliberately the LEAST
    # committed of the five, pulled toward even. Pinned by test.
    "Outdoor Hike":                           {"upper_body": 0.05, "core": 0.15, "lower_body": 0.80},
    "Outdoor Run":                            {"upper_body": 0.05, "core": 0.15, "lower_body": 0.80},
    "Outdoor Trail Run":                      {"upper_body": 0.05, "core": 0.20, "lower_body": 0.75},
    "Outdoor Activity":                       {"upper_body": 0.10, "core": 0.20, "lower_body": 0.70},
}

# ─────────────────────────────────────────────────────────────────────────────
#  Movement-category weight table — content-aware AU weighting for Strain/ACWR
#  (extends the movement_multiplier sketch in docs/training/Training_System.md
#  :104-105, which was never implemented and was itself weight_kg-based --
#  impossible for bodyweight/isometric release-protocol work with no weight_kg
#  at all. Applied here instead as a TIME-weighting: see
#  services/content_weighting.py for how this becomes a day-level multiplier
#  on top of the existing raw Foster session_au, not a replacement formula.)
#
#  Every exercise name appearing anywhere in training_plan.PLAN_STAGE2 has an
#  explicit entry here, including every unloaded/mobility/assessment exercise
#  (weight 0.25) -- no fallback default, same completeness convention as
#  EXERCISE_BODY_REGION above (see tests/test_training_plan_stage2.py::
#  test_all_stage2_exercise_names_are_mapped_to_a_movement_weight).
#
#  Categories (docs/training/Training_System.md:105, extended):
#    squat=1.3, hinge=1.0, upper_push=0.7, pull=0.7 (NEW -- the doc only
#    covered pushing), isolation=0.3, mobility_core=0.25 (NEW -- release
#    protocol + core/scapular finishers + walking/assessment work the doc
#    never covered).
#
#  Prone Y-Raise (Scapular): fixed at mobility_core/0.25 regardless of its
#  real weight_kg from Week 3 onward (1.0-2.5kg) -- NOT load-dependent. The
#  load involved is trivial (still a 2x8x3s-hold scapular activation drill),
#  a weight-based threshold has no natural physiological cliff, and it would
#  break the table's "one name -> one static weight, always" invariant for
#  one exercise. Update this entry directly if a future block genuinely
#  increases this exercise's load tier.
# ─────────────────────────────────────────────────────────────────────────────

EXERCISE_MOVEMENT_WEIGHT: dict[str, tuple[str, float]] = {
    # -- Loaded, Session A/B/C --
    "Goblet Squat":                ("squat", 1.3),
    "Bulgarian Split Squat":       ("squat", 1.3),
    "Romanian Deadlift (DB)":      ("hinge", 1.0),
    "Hip Thrust (Loaded)":         ("hinge", 1.0),
    "Incline DB Press":            ("upper_push", 0.7),
    "Lat Pulldown":                ("pull", 0.7),
    "Single-Arm DB Row":           ("pull", 0.7),
    "Face Pull (Cable)":           ("isolation", 0.3),
    "Pallof Press (Cable)":        ("isolation", 0.3),
    # -- Release protocol (always-include, every loaded day) --
    "Upper Glute / TFL Self-Release":                    ("mobility_core", 0.25),
    "Piriformis Contract-Relax (PNF)":                   ("mobility_core", 0.25),
    "Right Posterior Hip Capsule Stretch (Revised Cue)": ("mobility_core", 0.25),
    "Ischial Tuberosity Hamstring Release":              ("mobility_core", 0.25),
    "Right Hip Tendon Path Drill (Coxa Saltans)":        ("mobility_core", 0.25),
    # -- Core / scapular finishers, Session A/B/C --
    "McGill Curl-Up (Progressed)":       ("mobility_core", 0.25),
    "Full Side Bridge":                  ("mobility_core", 0.25),
    "Dead Bug":                          ("mobility_core", 0.25),
    "Pallof Press Hold (Doorframe)":     ("mobility_core", 0.25),
    "Single-Leg Glute Bridge":           ("mobility_core", 0.25),
    "Scapular Wall Slide":               ("mobility_core", 0.25),
    "Prone Y-Raise (Scapular)":          ("mobility_core", 0.25),
    "Lateral Band Walk":                 ("mobility_core", 0.25),
    "Bird-Dog":                          ("mobility_core", 0.25),
    "Side Bridge with Hip Dip":          ("mobility_core", 0.25),
    # -- Active-recovery-day content (_s2_recovery_day, both templates) --
    "Cat-Cow":                               ("mobility_core", 0.25),
    "Thoracic Extension (Rolled Towel)":     ("mobility_core", 0.25),
    "Thread-the-Needle (Thoracic Rotation)": ("mobility_core", 0.25),
    "Child's Pose":                          ("mobility_core", 0.25),
    "Controlled Walking":                    ("mobility_core", 0.25),
    # -- Day 14 checkpoint / Day 28 reassessment (unloaded functional screens) --
    "Hip Hinge Full Range Assessment":     ("mobility_core", 0.25),
    "Single-Leg Balance (Eyes Closed)":    ("mobility_core", 0.25),
    "McGill Big 3 — Quality Screen":       ("mobility_core", 0.25),
    "5-Minute Walk + Stair Assessment":    ("mobility_core", 0.25),

    # ── Stage 1 (training_plan.PLAN) ────────────────────────────────────────
    # Added 2026-08-01. These 46 names were previously ABSENT from this table
    # and therefore scored at content_weighting.UNMAPPED_EXERCISE_WEIGHT (1.0)
    # -- i.e. every Supine Knee-to-Chest and Diaphragmatic Breathing drill was
    # counted as fully-loaded barbell work. 34 of the 63 exercise names in the
    # logged history were affected, all of them Stage 1 rehab content, which
    # inflated Strain and the ACWR chronic term for the entire Stage 1 era.
    # The 1.0 default is the safe direction for an UNKNOWN name (never
    # silently suppress load) but it is simply wrong for a KNOWN mobility
    # drill; the fix is coverage, not a smaller default.
    # bodyweight_compound (0.5) -- NEW tier. Multi-joint, bearing
    # bodyweight, genuinely fatiguing, but nowhere near a loaded lift.
    # Sits between isolation (0.3) and pull/upper_push (0.7): scoring a
    # bodyweight chair sit-to-stand at squat=1.3 would be as wrong in
    # the other direction as the 1.0 default it replaces.
    "Chair Sit-to-Stand":                       ("bodyweight_compound", 0.5),
    "Forward Step-Up (Stair)":                  ("bodyweight_compound", 0.5),
    "Glute Bridge (Eccentric Single Load)":     ("bodyweight_compound", 0.5),
    "Lateral Lunge":                            ("bodyweight_compound", 0.5),
    "Lateral Step-Up (Single Stair)":           ("bodyweight_compound", 0.5),
    "Reverse Lunge":                            ("bodyweight_compound", 0.5),
    "Single-Leg RDL (Wall Support)":            ("bodyweight_compound", 0.5),
    "Wall Sit":                                 ("bodyweight_compound", 0.5),
    "Wall Sit (Extended Duration)":             ("bodyweight_compound", 0.5),
    "Wall Sit (Isometric Quad)":                ("bodyweight_compound", 0.5),

    # isolation (0.3) -- single-joint activation work, banded or lightly
    # loaded.
    "Clamshell":                                ("isolation", 0.3),
    "Glute Bridge":                             ("isolation", 0.3),
    "Glute Bridge March":                       ("isolation", 0.3),
    "Prone Hip Extension (Single Leg)":         ("isolation", 0.3),
    "Prone Hip Extension (Slow Tempo — 4-3-5)": ("isolation", 0.3),
    "Side-Lying Hip Abduction":                 ("isolation", 0.3),
    "Standing Calf Raise (Eccentric Focus)":    ("isolation", 0.3),
    "Supine Glute Bridge (Bilateral)":          ("isolation", 0.3),

    # mobility_core (0.25) -- release, stretch, breathing, balance,
    # assessment, and core-stability holds. Stage 1 variants are pinned to
    # the same 0.25 as their already-mapped Stage 2 counterparts (Bird-Dog,
    # Dead Bug, McGill Curl-Up, Full Side Bridge) so the same movement never
    # changes weight just because the block changed.
    "90/90 Hip Flexor Hold":                    ("mobility_core", 0.25),
    "Assessment Walk + Stair Check":            ("mobility_core", 0.25),
    "Bird-Dog (Extended Hold)":                 ("mobility_core", 0.25),
    "Bird-Dog with Full Reach":                 ("mobility_core", 0.25),
    "Cat-Cow (Slow Flow)":                      ("mobility_core", 0.25),
    "Dead Bug (Progression — 3s Hold)":         ("mobility_core", 0.25),
    "Diaphragmatic Breathing":                  ("mobility_core", 0.25),
    "Forearm Plank":                            ("mobility_core", 0.25),
    "Hip 90/90 Flow":                           ("mobility_core", 0.25),
    "Lateral Step Walk":                        ("mobility_core", 0.25),
    "McGill Modified Curl-Up":                  ("mobility_core", 0.25),
    "Prone Decompression Breathing":            ("mobility_core", 0.25),
    "RDL Hip Hinge to Wall":                    ("mobility_core", 0.25),
    "Right Posterior Hip Capsule Stretch":      ("mobility_core", 0.25),
    "Sciatic Nerve Floss":                      ("mobility_core", 0.25),
    "Side Bridge (Modified — Bent Knee)":       ("mobility_core", 0.25),
    "Single-Leg Balance":                       ("mobility_core", 0.25),
    "Standing Hip Flexor Release":              ("mobility_core", 0.25),
    "Standing Hip Hinge (Wall Glute Touch)":    ("mobility_core", 0.25),
    "Supine Full-Body Stretch":                 ("mobility_core", 0.25),
    "Supine Hip Flexion (Marching)":            ("mobility_core", 0.25),
    "Supine Knee Fallout (Butterfly)":          ("mobility_core", 0.25),
    "Supine Knee-to-Chest":                     ("mobility_core", 0.25),
    "Supine Knee-to-Chest (Bilateral)":         ("mobility_core", 0.25),
    "Supine Knees-to-Chest (Bilateral Rock)":   ("mobility_core", 0.25),
    "Walking — Gait Focus":                     ("mobility_core", 0.25),
    "Wall-Supported Hip Hinge":                 ("mobility_core", 0.25),
    "Week 1 Self-Assessment":                   ("mobility_core", 0.25),

    # ── Garmin-imported outdoor activities (never authored in any PLAN;
    #    logged only by the hike/walk importer, services/sessions.py
    #    OUTDOOR_EXERCISE_BY_TYPE). bodyweight_compound 0.5, NOT the
    #    mobility 0.25 of the plan's short recovery strolls: a multi-hour
    #    hike is sustained unloaded lower-body work — step-ups at scale —
    #    and Foster AU already carries intensity via RPE and duration.
    #    tests/test_movement_weight_coverage.py pins every importer name
    #    into this dict, because no PLAN iteration will ever ask for them. ──
    "Outdoor Hike":                             ("bodyweight_compound", 0.5),
    "Outdoor Walk":                             ("bodyweight_compound", 0.5),
    "Outdoor Trail Run":                        ("bodyweight_compound", 0.5),
    "Outdoor Run":                              ("bodyweight_compound", 0.5),
    "Outdoor Activity":                         ("bodyweight_compound", 0.5),
}
