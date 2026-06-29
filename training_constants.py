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
