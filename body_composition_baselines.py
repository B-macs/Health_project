"""
body_composition_baselines.py — the InBody 770 scans, transcribed.

Same reason `strength_baselines.py` exists: the source is not machine-readable
and cannot be re-derived from anything the app can reach. The InBody prints a
paper sheet, there is no export path, and the phone app that syncs from it drops
the raw impedance table, the scan history, the waist figure and the fitness
score. Lose this file and the only body-composition measurements that were ever
made on a real instrument are gone.

Source: `Input_files/BodyScan Primetime 27-June-2025.pdf` — InBody 770,
S/N I81800091, five scans 2025-01-13 to 2025-06-27, read 2026-08-05.

THE HEIGHT COLUMN IS BACK-SOLVED, NOT PRINTED
---------------------------------------------
The sheet does not record what height it was told; it prints BMI, and BMI is
weight / height^2, so `sqrt(weight / bmi)` recovers it exactly. Doing that gives
185.5, 175.1, 174.9, 181.6 and 181.8 cm against a true 182.0. Height enters
InBody's first step squared, so four of these five scans are wrong in every
kilogram they print. `services.body_composition.InBodyScan.at_height` corrects
them; `entered_height_m` is what they were run against.

The two scans eight minutes apart on 2025-05-21 are the proof and are kept
BOTH, not deduplicated: at an identical 79.5 kg they print 20.0% and 14.0% body
fat, because the operator corrected the height between them. Any future reader
tempted to drop one as a duplicate should read `at_height`'s docstring first.

WHAT SURVIVED THE DEFECT
------------------------
`phase_angle_deg` and `ecw_tbw`. Both are quotients of directly measured
quantities, so the entered height cannot reach them: 6.1 deg on all three scans
that report it, and 0.375-0.379 across all five. They are the only readings on
either of this athlete's two devices that no console entry can move.
"""

from __future__ import annotations

from datetime import datetime

from services.body_composition import InBodyScan

#: The gym's machine. Never pool readings across models — the same rule the
#: Garmin 645 -> 265 upgrade note in CLAUDE.md sets for the movement calibration.
DEVICE: str = "InBody 770"
DEVICE_SERIAL: str = "I81800091"

#: Chronological age the sheet was run against, and the operator-entered sex.
#: Recorded because both are inputs to InBody's regressions.
SCAN_AGE_YEARS: int = 30
SCAN_SEX: str = "male"

SCANS: tuple[InBodyScan, ...] = (
    InBodyScan(
        taken_at=datetime(2025, 1, 13, 12, 25),
        weight_kg=82.2, bmi=23.9, total_body_water_l=52.5,
        skeletal_muscle_kg=40.5, ecw_tbw=0.379, phase_angle_deg=None,
        note="height 185.5 cm entered — 3.5 cm too tall, reads too lean",
    ),
    InBodyScan(
        taken_at=datetime(2025, 3, 13, 12, 19),
        weight_kg=82.2, bmi=26.8, total_body_water_l=48.3,
        skeletal_muscle_kg=37.1, ecw_tbw=0.378, phase_angle_deg=None,
        note="height 175.1 cm entered — 6.9 cm too short, reads too fat",
    ),
    InBodyScan(
        taken_at=datetime(2025, 5, 21, 12, 16),
        weight_kg=79.5, bmi=26.0, total_body_water_l=46.7,
        skeletal_muscle_kg=35.9, ecw_tbw=0.377, phase_angle_deg=6.1,
        note="height 174.9 cm entered — 7.1 cm too short",
    ),
    InBodyScan(
        taken_at=datetime(2025, 5, 21, 12, 24),
        weight_kg=79.5, bmi=24.1, total_body_water_l=50.2,
        skeletal_muscle_kg=38.8, ecw_tbw=0.377, phase_angle_deg=6.1,
        note="re-run 8 minutes later with the height corrected to 181.6 cm",
    ),
    InBodyScan(
        taken_at=datetime(2025, 6, 27, 10, 6),
        weight_kg=78.7, bmi=23.8, total_body_water_l=51.0,
        skeletal_muscle_kg=39.5, ecw_tbw=0.375, phase_angle_deg=6.1,
        note="height 181.8 cm entered — 0.2 cm off, the only clean scan",
    ),
)

#: Figures the 27 Jun 2025 sheet prints that the phone app never synced. Kept so
#: a future tape-measure baseline has something to be compared against, and so
#: the "waist is empty" reading of the app screen is not repeated in the engine.
SHEET_2025_06_27: dict[str, float] = {
    "waist_cm": 82.8,
    "waist_hip_ratio": 0.84,
    "visceral_fat_area_cm2": 40.6,
    "body_cell_mass_kg": 45.6,
    "ffmi_kg_m2": 21.0,
    "skeletal_muscle_index_kg_m2": 8.8,
    "fitness_score": 88.0,
}

#: Impedance in ohms at 50 kHz, by segment: right arm, left arm, trunk, right
#: leg, left leg. The actual measurement everything above is modelled from, and
#: the only row of the sheet that owes nothing to any entered value.
IMPEDANCE_50KHZ_OHM: dict[str, float] = {
    "right_arm": 255.6,
    "left_arm": 250.5,
    "trunk": 19.0,
    "right_leg": 227.8,
    "left_leg": 225.4,
}
