"""
services/plan.py — Training phase model. Deterministic, no I/O, no Streamlit.

A Phase is a fixed-length, multiple-of-7-days training block (Phase 1: 14 days,
Phase 2: 28 days, ...). This is distinct from the clinical "Stage" system in
services/rules.py/services/engine.py, which drives ACWR/RPE/volume safety
ceilings via pain-free-streak criteria and stays separate — Phase is purely
calendar/day-numbering for the training plan content, decided by reassessment
between blocks.

Moved from the prior phase.py, now working against services.models.Phase /
DayCell dataclasses instead of plain dicts — the typed boundary the rest of
services/ uses.
"""

from __future__ import annotations

from datetime import date, timedelta

from services.models import DayCell, Phase


def default_phase(start_date: date, length_days: int = 14,
                   phase_number: int = 1, name: str = "Stage 1 Rehab") -> Phase:
    return Phase(
        phase_number=phase_number,
        name=name,
        start_date=start_date.isoformat(),
        length_days=length_days,
        status="active",
    )


def _start(phase: Phase) -> date:
    return date.fromisoformat(phase.start_date)


def _end(phase: Phase) -> date:
    """Last day of the phase, inclusive."""
    return _start(phase) + timedelta(days=phase.length_days - 1)


def phase_end_date(phase: Phase) -> date:
    """Public wrapper on _end — the last day of the phase, inclusive. For
    callers outside this module (e.g. deciding whether a phase has lapsed)."""
    return _end(phase)


def active_phase(phases: list[Phase], today: date) -> Phase | None:
    """The phase whose date range covers today and whose status is 'active'.
    None during a reassessment gap between phases."""
    for ph in phases:
        if ph.status == "active" and _start(ph) <= today <= _end(ph):
            return ph
    return None


def day_number_in_phase(phase: Phase, d: date) -> int:
    """1-indexed day number within the phase (not global)."""
    return (d - _start(phase)).days + 1


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def phase_week_bounds(phase: Phase) -> tuple[date, date]:
    """(Monday of the week containing the phase start, Monday of the week
    containing the phase's last day) — the valid range of week_start values
    for paging. A 28-day phase spans 4 distinct week_start values if the
    phase starts on a Monday."""
    return _monday(_start(phase)), _monday(_end(phase))


def clamp_week_start(candidate: date, phase: Phase) -> date:
    lo, hi = phase_week_bounds(phase)
    if candidate < lo:
        return lo
    if candidate > hi:
        return hi
    return candidate


def get_week_view(week_start: date, phase: Phase | None, sessions: list[dict],
                   today: date | None = None) -> list[DayCell]:
    """Pure. sessions: [{"date": "YYYY-MM-DD", ...}] — a cheap existence lookup,
    not full SessionRecords. today defaults to date.today() but is an explicit
    param for testability."""
    today = today or date.today()
    logged = {s["date"] for s in sessions}

    cells = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        d_iso = d.isoformat()
        day_num = None
        state = "rest"

        if phase is not None:
            candidate = day_number_in_phase(phase, d)
            if 1 <= candidate <= phase.length_days:
                day_num = candidate
                if d_iso in logged:
                    state = "completed"
                elif d < today:
                    state = "missed"
                else:
                    state = "planned"

        cells.append(DayCell(
            date=d,
            weekday_label=d.strftime("%a").upper()[:3],
            state=state,
            day_number_in_phase=day_num,
            session_ref=next((s for s in sessions if s["date"] == d_iso), None),
        ))
    return cells
