"""
services/content_weighting.py — content-aware Session AU weighting.

Pure functions only — no I/O, no Streamlit, no hidden clock reads (mirrors
services/engine.py's conventions). Computes how much of a logged day's total
exercise time was genuinely loaded lifting vs. release/mobility/core work,
and turns that into a single multiplier applied to that day's raw Foster
Session AU (session_rpe * duration_minutes) before it feeds
services.engine.acwr() and services.dashboard's strain functions.

Why this exists: the uniform Foster method treats every minute of a mixed
Stage 2A session (loaded lifting + release/mobility/core) as equally
strain-inducing, which over-counts Strain/ACWR for sessions that are mostly
low-intensity work (2026-07-20 Session A: RPE 4, 66 min, Strain 15.3 for
content that's 6/10 exercises release/core work). This module re-weights by
how much of the day's exercise TIME was spent in each exercise's own
movement-category multiplier (training_constants.EXERCISE_MOVEMENT_WEIGHT),
read live from each day's own persisted Sets JSON via
services.sessions.exercise_seconds_from_sets — never a static
per-session-type lookup, so it's naturally correct for whatever was
actually logged. See docs/training/Training_System.md:104-105 for the
original movement_multiplier sketch this extends (as a time-weighting of
the existing Foster AU, not the doc's literal weight_kg-based formula,
which can't work for bodyweight/isometric release work).
"""

from __future__ import annotations

import training_constants as tc

# Multiplier applied to any exercise name absent from
# tc.EXERCISE_MOVEMENT_WEIGHT — 1.0 ("assume fully loaded"), the
# conservative direction for the ACWR safety chain: an uncategorized
# exercise must never silently suppress a day's computed strain/ACWR by
# defaulting to a low mobility-like weight. Surfaced (not swallowed) via
# the result's "unmapped_names" list rather than raised, so a data-
# completeness gap can never crash a safety-relevant page load.
UNMAPPED_EXERCISE_WEIGHT: float = 1.0


def day_content_multiplier(exercise_seconds: list[dict]) -> dict:
    """
    exercise_seconds: [{"name": str, "seconds": int}, ...] — one entry per
    exercise actually logged in ONE physical session.

    Returns:
      multiplier       : float — weighted_seconds / plain_seconds, or 1.0
                          if plain_seconds is 0 (no reconstructable logged
                          time at all — a neutral no-op rather than a
                          division error or an arbitrary guess)
      plain_seconds    : int
      weighted_seconds : float
      unmapped_names   : list[str] — exercise names with no
                          EXERCISE_MOVEMENT_WEIGHT entry, each contributing
                          at UNMAPPED_EXERCISE_WEIGHT
    """
    plain_seconds = sum(e["seconds"] for e in exercise_seconds)
    if plain_seconds <= 0:
        return {"multiplier": 1.0, "plain_seconds": 0, "weighted_seconds": 0.0, "unmapped_names": []}

    weighted_seconds = 0.0
    unmapped: list[str] = []
    for e in exercise_seconds:
        entry = tc.EXERCISE_MOVEMENT_WEIGHT.get(e["name"])
        if entry is None:
            unmapped.append(e["name"])
            weight = UNMAPPED_EXERCISE_WEIGHT
        else:
            _category, weight = entry
        weighted_seconds += e["seconds"] * weight

    return {
        "multiplier": round(weighted_seconds / plain_seconds, 3),
        "plain_seconds": plain_seconds,
        "weighted_seconds": round(weighted_seconds, 1),
        "unmapped_names": unmapped,
    }
