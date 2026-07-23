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
#  Exercise → body region — feeds services/bioage.py's per-region Strength
#  BioAge score. Every exercise name that appears in training_plan.py's PLAN
#  is listed once below (primary region only — no multi-tagging in v1).
#  training_plan.py is a self-contained exercise universe (doesn't reference
#  EXERCISES above), so this map is scoped to its names, not EXERCISES'.
#
#  Maintenance: Stage 2 (training_plan.PLAN_STAGE2) is now built and its new
#  exercise names are included below. Any *future* block's new exercise names
#  need an entry here too, or services.bioage will silently skip them (an
#  exercise absent from this map counts toward no region at all, rather than
#  raising).
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
)

EXERCISE_BODY_REGION: dict[str, str] = {
    **{name: "upper_body" for name in _UPPER_BODY_EXERCISES},
    **{name: "core" for name in _CORE_EXERCISES},
    **{name: "lower_body" for name in _LOWER_BODY_EXERCISES},
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
}
