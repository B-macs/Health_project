"""
services/bioage.py — the muscle-imbalance count for the Strength screen.

One function. It counts the individually flagged structures in
patient_profile.PROFILE's "imbalances" dict, which is documented clinical
assessment data, not training history — no dates, no sessions, no network.
That independence is why the count still renders when the training log cannot
be read at all.

WHAT USED TO BE HERE, AND WHY IT IS GONE
----------------------------------------
This module also held the per-region "Stage-Adjusted Recovery Score":
region_effort, has_weighted_training, current_window_effort,
region_baseline_ceiling, region_recovery_score and hero_score. Removed
2026-08-04. Do not reintroduce that approach.

It was `min(100, current_28d / (best_ever_28d * cap) * 100)`, and
region_baseline_ceiling maximised over every trailing 28-day window INCLUDING
today's. The current window was therefore inside the set its own denominator
maximised over, so the ratio could not exceed 1: the score read a flat 100 for
the whole first 28 days of any block and at every new peak. Measured on
2026-08-04 it had returned exactly one distinct value, 100.0, across all 16
days it had existed. Same one-sided saturating ratio that readiness
MODEL_VERSION 2 removed.

It also measured the wrong quantity. Tonnage-in-a-window is training VOLUME,
and volume is not strength — a deload lowers it, and a heavier month raises
numerator and denominator together and moves nothing.

Strength capacity now lives in services/strength.py (estimated 1RM against a
fixed 2025 baseline) and training volume in services/tonnage.py (kilograms
completed per week, by sector). They are deliberately separate metrics that
share no term. Read services/strength.py's module docstring before changing
either.
"""

from __future__ import annotations


def muscle_imbalance_count(imbalances: dict) -> int:
    """Count of individually flagged structures in patient_profile.PROFILE's
    "imbalances" dict (overactive_tight + underactive_weak) — a count of
    real flagged findings from the documented clinical assessment, not
    curated antagonist "pairs"."""
    return len(imbalances.get("overactive_tight", [])) + len(imbalances.get("underactive_weak", []))
