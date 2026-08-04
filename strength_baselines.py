"""
strength_baselines.py — the 2025 peak that "100" on the Overall Strength Score
means, one entry per exercise.

Reference data, alongside training_constants.py and training_plan.py. Values
transcribed from Input_files/2025-training-year.md (gitignored, local-only),
which is the full-year strength log. They live in code rather than being
re-derived from Notion because **Notion does not contain 2025** — the training
DB starts at 2026-06-29. Lose this file and every index loses its denominator.

The scale, stated once: **100 = the 2025 peak for that exercise**, so an index
of 50 means "half of what I could do at my best last year" and 51 is a 2%
improvement on 50. It is deliberately NOT a 0-100 percentile.

`comparability` is how safely the 2025 set can be set against the current one,
and it is the honest part of this table:

  1.00  same exercise, same equipment, same logged form
  0.70  same movement pattern, different implement (barbell then, dumbbell now)
  0.60  machine-dependent load — the 2025 log itself records a range
  0.40  the 2025 rep count was never written down and had to be assumed
  0.00  no kilogram baseline exists at all (a band, a bodyweight hold)

It feeds services.strength.region_confidence, so a region built out of weak
comparisons cannot reach the confidence needed to exit calibration. That is the
point: the fix for a 0.40 is to remember the reps, not to round it up.
"""

from __future__ import annotations

from datetime import date

# ── the anchor ──────────────────────────────────────────────────────────────
# The day the Overall Strength Score was set, and what it was set to. 50 is a
# STATED position ("100 was last year, I'm about half of it now"), deliberately
# the conservative end of what the lifts actually measure — the currently
# cleared lifts read ~68 against these baselines, but the 2025 log also holds a
# Back Squat 80x5 and a Front Squat 60x8 that the L5/S1 findings rule out, and
# counting those as strength that cannot currently be expressed pulls the
# honest figure down to ~54. Anchoring at 50 costs nothing and claims nothing.
ANCHOR_DATE: date = date(2026, 7, 30)
ANCHOR_VALUE: float = 50.0

# The value every regional index displays at during calibration lives in
# services/strength.py as CALIBRATION_INDEX, NOT here. It is the model's own
# constant, not a measured baseline, and a second copy in this file would be a
# duplicate nothing reads — every other constant here is injected into the pure
# service by the caller, while that one is resolved inside it.

# name -> (weight_kg, reps, comparability, why)
# reps is the REPS PERFORMED in the 2025 PR set, not a prescription.
PEAKS_2025: dict[str, tuple[float, int, float, str]] = {
    # -- upper body --
    "Lat Pulldown":           (60.0, 12, 1.00, "same exercise"),
    "Single-Arm DB Row":      (32.5,  8, 1.00, "same exercise"),
    "Incline DB Press":       (18.0, 12, 1.00, "same exercise"),
    "Face Pull (Cable)":      (21.0, 15, 0.60, "machine-dependent; 2025 log records 15-24 kg"),
    # -- lower body --
    "Hip Thrust (Loaded)":    (50.0, 12, 1.00, "same exercise"),
    "Romanian Deadlift (DB)": (60.0, 12, 0.70, "barbell in 2025, dumbbell now"),
    "Goblet Squat":           (22.5, 10, 0.40, "reps not recorded in 2025; x10 assumed"),
    "Bulgarian Split Squat":  (15.0, 12, 1.00, "logged as Split Squat in 2025"),
    # -- core --
    # Pallof Press's 2025 entry is "orange band x 15". A band is not a
    # kilogram and there is no defined conversion, so it gets NO baseline
    # rather than an invented one. Core therefore runs on the prior alone
    # until a loaded or repeatable core measurement is logged; the two
    # candidates already in the 2025 log are the Copenhagen plank (30s x 3)
    # and the side plank + march (15/15 x 3), neither of which needs a 1RM.
}

# A 2025 PR set has no logged RPE. "Best ever" is taken to be one rep from
# failure, which is the conservative reading — assuming it was a true all-out
# set would inflate the 2025 e1RM and make today look better than it is.
PR_RIR: float = 1.0

# How overall strength is assumed to divide across the three sectors before
# any evidence arrives. A judgement, not a measurement, and labelled as such
# wherever it surfaces. Core is weighted above a generic split because the
# 2025 movement-pattern analysis names the abs-to-lower-back ratio as a
# recurring cause of the back injuries, i.e. core is load-bearing here in a
# way a generic template would not capture.
REGION_PRIOR: dict[str, float] = {
    "upper_body": 0.35,
    "core":       0.20,
    "lower_body": 0.45,
}
