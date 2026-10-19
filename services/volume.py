"""
services/volume.py — weekly volume load (tonnage: Σ reps × weight per set).

Pure function, no I/O. Complements the Foster-AU-based ACWR/strain engine
(services.engine) with an actual-load view — total kg moved per week —
which is only meaningful once loaded, countable-reps exercises exist
(Stage 2A+ double-progression exercises; see training_plan.py's rep_min/
rep_max fields and services.engine.range_progression).
"""

from __future__ import annotations

from datetime import date, timedelta

from services.models import SessionRecord


def weekly_volume_load(sessions: list[SessionRecord], week_start: date) -> float:
    """
    Sum of (reps x weight) across every logged set, across every session,
    whose session_date falls in [week_start, week_start + 6 days] inclusive.

    `sessions`: the same shape Repository.get_recent_sessions() returns --
    a list of SessionRecord, each holding ExerciseEntry rows. Each
    ExerciseEntry.total_volume_kg is ALREADY the per-exercise sum of
    reps*weight across its own logged sets (see
    Repository.get_recent_sessions, which computes it straight from the
    parsed Sets JSON), so this sums that field across every exercise in
    every session inside the week window rather than re-parsing raw set
    data.

    Returns 0.0 for an empty sessions list, or a week with no logged
    volume in range.
    """
    week_end = week_start + timedelta(days=6)
    total = 0.0
    for session in sessions:
        try:
            session_date = date.fromisoformat(session.session_date)
        except (TypeError, ValueError):
            continue
        if not (week_start <= session_date <= week_end):
            continue
        for ex in session.exercises:
            total += ex.total_volume_kg or 0.0
    return round(total, 1)


def weekly_volume_series(sessions: list[SessionRecord], today: date,
                         weeks: int = 8) -> list[tuple[date, float]]:
    """(Monday, kg) for the last `weeks` Monday-anchored weeks ending with the
    one holding `today`, oldest first, through weekly_volume_load."""
    current = today - timedelta(days=today.weekday())
    starts = [current - timedelta(weeks=n) for n in range(weeks - 1, -1, -1)]
    return [(start, weekly_volume_load(sessions, start)) for start in starts]
