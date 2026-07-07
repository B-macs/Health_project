"""
phase.py — Training phase model. Deterministic, no I/O, no Streamlit.

A Phase is a fixed-length, multiple-of-7-days training block (Phase 1: 14 days,
Phase 2: 28 days, ...). This is distinct from the clinical "Stage" system in
rules.py/engine.py, which drives ACWR/RPE/volume safety ceilings via pain-free-
streak criteria and stays untouched — Phase is purely calendar/day-numbering for
the training plan content, decided by reassessment between blocks.

Phase dict shape:    {phase_number, name, start_date (ISO str), length_days, status}
                      status: "active" | "completed" | "upcoming"
DayCell dict shape:  {date, weekday_label, state, day_number_in_phase, session_ref}
                      state: "completed" | "missed" | "planned" | "rest"
SessionRecord shape (input to get_week_view): {"date": "YYYY-MM-DD", ...}
"""

from __future__ import annotations

from datetime import date, timedelta


def default_phase(start_date: date, length_days: int = 14,
                   phase_number: int = 1, name: str = "Stage 1 Rehab") -> dict:
    return {
        "phase_number": phase_number,
        "name": name,
        "start_date": start_date.isoformat(),
        "length_days": length_days,
        "status": "active",
    }


def _start(phase: dict) -> date:
    return date.fromisoformat(phase["start_date"])


def _end(phase: dict) -> date:
    """Last day of the phase, inclusive."""
    return _start(phase) + timedelta(days=phase["length_days"] - 1)


def active_phase(phases: list[dict], today: date) -> dict | None:
    """The phase whose date range covers today and whose status is 'active'.
    None during a reassessment gap between phases."""
    for ph in phases:
        if ph.get("status") == "active" and _start(ph) <= today <= _end(ph):
            return ph
    return None


def day_number_in_phase(phase: dict, d: date) -> int:
    """1-indexed day number within the phase (not global)."""
    return (d - _start(phase)).days + 1


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def phase_week_bounds(phase: dict) -> tuple[date, date]:
    """(Monday of the week containing the phase start, Monday of the week
    containing the phase's last day) — the valid range of week_start values
    for paging. A 28-day phase spans 4 distinct week_start values."""
    return _monday(_start(phase)), _monday(_end(phase))


def clamp_week_start(candidate: date, phase: dict) -> date:
    lo, hi = phase_week_bounds(phase)
    if candidate < lo:
        return lo
    if candidate > hi:
        return hi
    return candidate


def get_week_view(week_start: date, phase: dict | None, sessions: list[dict],
                   today: date | None = None) -> list[dict]:
    """Pure. today defaults to date.today() but is an explicit param for testability."""
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
            if 1 <= candidate <= phase["length_days"]:
                day_num = candidate
                if d_iso in logged:
                    state = "completed"
                elif d < today:
                    state = "missed"
                else:
                    state = "planned"

        cells.append({
            "date": d,
            "weekday_label": d.strftime("%a").upper()[:3],
            "state": state,
            "day_number_in_phase": day_num,
            "session_ref": next((s for s in sessions if s["date"] == d_iso), None),
        })
    return cells
