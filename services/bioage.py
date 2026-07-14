"""
services/bioage.py — Strength BioAge scoring engine.

Pure functions only — no I/O, no Streamlit, no hidden clock reads (mirrors
services/engine.py's conventions: every date-dependent function takes an
explicit `today` param). Computes the per-body-region "Stage-Adjusted
Recovery Score" (0-100) and the muscle-imbalance count for the Strength
BioAge detail screen (views/insights.py, ?bioage=strength).

Deliberately weight-volume-based, not effort/RPE-based: Stage 1's actual
training plan (training_plan.py) is bodyweight-only rehab work, so
ExerciseEntry.total_volume_kg is 0 throughout it. Rather than papering over
that with a bodyweight-compatible proxy metric, every region's score stays
None ("—" on screen) until that region has real logged weighted volume —
bodyweight reps/sets are not "clear data" for a strength trend. Scores
activate automatically the moment real weight training begins, whichever
stage that turns out to be, with no code change required here.
"""

from __future__ import annotations

from datetime import date, timedelta

from services import rules as _rules
from services.models import SessionRecord

REGIONS: tuple[str, ...] = ("upper_body", "core", "lower_body")

# Mirrors services/engine.py's MIN_OBSERVATION_DAYS convention for "not
# enough history yet" gating elsewhere in the app. Also the window used for
# both "current effort" and the self-referential historical-ceiling baseline
# below — the same 28-day chronic window services.engine.acwr already uses,
# for consistency across the app's stats.
BASELINE_WINDOW_DAYS: int = 28


def region_effort(sessions: list[SessionRecord], region: str, exercise_region_map: dict[str, str]) -> float:
    """Total logged weighted volume (kg) across every exercise tagged to
    `region` in `exercise_region_map` (training_constants.EXERCISE_BODY_REGION
    in practice), summed across `sessions`. Exercise names absent from the
    map are silently skipped — they don't count toward any region rather
    than raising, since not every logged exercise needs a region tag yet."""
    total = 0.0
    for session in sessions:
        for exercise in session.exercises:
            if exercise_region_map.get(exercise.name) == region:
                total += exercise.total_volume_kg or 0.0
    return total


def has_weighted_training(sessions: list[SessionRecord], region: str, exercise_region_map: dict[str, str]) -> bool:
    """True once at least one exercise tagged to `region` has logged
    non-zero weighted volume, anywhere in `sessions`. Bodyweight-only
    history (total_volume_kg always 0 or None) returns False — see module
    docstring for why that's deliberate, not a bug."""
    for session in sessions:
        for exercise in session.exercises:
            if (
                exercise_region_map.get(exercise.name) == region
                and (exercise.total_volume_kg or 0.0) > 0
            ):
                return True
    return False


def _sessions_in_window(sessions: list[SessionRecord], window_end: date, window_days: int) -> list[SessionRecord]:
    window_start = window_end - timedelta(days=window_days)
    return [
        s for s in sessions
        if window_start < date.fromisoformat(s.session_date) <= window_end
    ]


def current_window_effort(
    sessions: list[SessionRecord],
    region: str,
    exercise_region_map: dict[str, str],
    today: date | None = None,
    window_days: int = BASELINE_WINDOW_DAYS,
) -> float:
    """region_effort over the trailing `window_days` ending today — "how
    much have you lifted in this region recently."""
    today = today or date.today()
    windowed = _sessions_in_window(sessions, today, window_days)
    return region_effort(windowed, region, exercise_region_map)


def region_baseline_ceiling(
    sessions: list[SessionRecord],
    region: str,
    exercise_region_map: dict[str, str],
    today: date | None = None,
    window_days: int = BASELINE_WINDOW_DAYS,
) -> float:
    """The best `window_days`-wide trailing window of region_effort found
    anywhere in `sessions` history, ending on or before `today` — a
    self-referential "your best stretch to date" baseline, rather than an
    external/population reference. Naturally starts accumulating the moment
    weight training begins and only ever grows as a new personal best is set.
    0.0 when there's no session history at all."""
    today = today or date.today()
    if not sessions:
        return 0.0
    session_dates = [date.fromisoformat(s.session_date) for s in sessions]
    earliest = min(session_dates)
    best = 0.0
    d = earliest
    while d <= today:
        window_effort = region_effort(_sessions_in_window(sessions, d, window_days), region, exercise_region_map)
        best = max(best, window_effort)
        d += timedelta(days=1)
    return best


def region_recovery_score(
    current_effort: float,
    baseline_ceiling_effort: float,
    stage: int,
) -> float | None:
    """% of what's safely achievable at the given rehab stage (reuses
    services.rules.STAGE_CONSTRAINTS' volume_cap_pct), capped at 100. None
    when there's no baseline yet to compare against. Callers should check
    has_weighted_training first and skip calling this entirely (pass None
    straight through) when it's False — this function has no way to
    distinguish "no weighted training yet" from "an unlucky light week" on
    its own."""
    if baseline_ceiling_effort <= 0:
        return None
    volume_cap_pct = _rules.STAGE_CONSTRAINTS.get(stage, {}).get("volume_cap_pct", 1.0)
    ceiling = baseline_ceiling_effort * volume_cap_pct
    if ceiling <= 0:
        return None
    return round(min(100.0, current_effort / ceiling * 100.0), 1)


def hero_score(region_scores: list[float | None]) -> float | None:
    """Simple average of the region scores that aren't None — the simplest
    defensible combination for v1, not a weighted formula. None if every
    region is None (e.g. training is still entirely bodyweight)."""
    real_scores = [s for s in region_scores if s is not None]
    if not real_scores:
        return None
    return round(sum(real_scores) / len(real_scores), 1)


def muscle_imbalance_count(imbalances: dict) -> int:
    """Count of individually flagged structures in patient_profile.PROFILE's
    "imbalances" dict (overactive_tight + underactive_weak) — a count of
    real flagged findings from the documented clinical assessment, not
    curated antagonist "pairs"."""
    return len(imbalances.get("overactive_tight", [])) + len(imbalances.get("underactive_weak", []))
