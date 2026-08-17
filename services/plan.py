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


# ── EVERY BLOCK RUNS MONDAY TO SUNDAY ────────────────────────────────────────
#
# Athlete's rule, 2026-08-17. The module docstring has always described a phase
# as "a fixed-length, multiple-of-7-days training block", and every phase ever
# stored has in fact started on a Monday — but nothing enforced either half,
# and both are load-bearing rather than tidy.
#
# WHY IT MATTERS MORE THAN IT LOOKS: week_of_phase_date counts weeks from the
# PHASE START, not from calendar Mondays. So key rule 18b — "a rescheduled day
# moves within its week or not at all" — only means a Monday-to-Sunday week
# when the phase starts on a Monday. Start a block on a Tuesday and its
# "weeks" are Tue-Mon windows that straddle every calendar weekend, so the one
# guard against drift silently starts guarding the wrong boundary. The rule and
# the alignment are the same rule.
#
# The hole was reachable: default_phase took whatever date the caller passed,
# and views/training.py passed date.today() — the day the button happened to
# be pressed. Stage 2B was begun on a Monday by luck, not by construction.
#
# REFUSED, NOT CLAMPED, matching reject_violating_overrides. Silently shifting
# a start to the nearest Monday changes which day the athlete's content lands
# on without telling them, and silently padding length_days to a multiple of 7
# invents training days that were never authored.
_MONDAY = 0


class WeekAlignmentError(ValueError):
    """A phase that would not run Monday to Sunday."""


def week_alignment_errors(start_date: date, length_days: int) -> list[str]:
    """Every way (start_date, length_days) breaks the Monday-to-Sunday rule.

    Returns reasons rather than a bool so a caller can say WHICH half is
    wrong — "starts on a Tuesday" and "is 26 days long" need different fixes,
    and a bare False sends the reader to check both.
    """
    out = []
    if start_date.weekday() != _MONDAY:
        out.append(
            f"a block must start on a Monday; {start_date.isoformat()} is a "
            f"{start_date.strftime('%A')}"
        )
    if length_days <= 0 or length_days % 7:
        out.append(
            f"a block must be a whole number of weeks so it ends on a Sunday; "
            f"{length_days} days is {length_days / 7:.2f} weeks"
        )
    return out


def assert_week_aligned(start_date: date, length_days: int) -> None:
    """Raise WeekAlignmentError unless the block runs Monday to Sunday."""
    errors = week_alignment_errors(start_date, length_days)
    if errors:
        raise WeekAlignmentError("; ".join(errors))


def next_block_start(today: date) -> date:
    """The Monday a block beginning "now" must start on — today when today is
    already a Monday, otherwise the NEXT one.

    Forward, never backward. Rewinding to the Monday just past would make the
    block silently already-underway, skipping days 1..N of authored content
    that were never presented; going forward costs a short gap that is visible
    on the calendar and can be discussed, which is the failure worth having.
    """
    return today + timedelta(days=(_MONDAY - today.weekday()) % 7)


def default_phase(start_date: date, length_days: int = 14,
                   phase_number: int = 1, name: str = "Stage 1 Rehab") -> Phase:
    """Build a Phase, refusing anything that would not run Monday to Sunday.

    The check lives here rather than only at the call site because this is the
    one constructor every path goes through — see assert_week_aligned's block
    comment for why the alignment and key rule 18b are the same rule.
    """
    assert_week_aligned(start_date, length_days)
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


def current_stage_start(phases: list[Phase], today: date) -> date | None:
    """First day of the stage `today` falls in, or None during a reassessment
    gap between phases.

    Feeds engine.acwr's `stage_start`, which scopes the chronic baseline to
    the current stage rather than a flat 28-day calendar window. None is a
    safe answer, not a failure: acwr() falls back to the calendar window,
    which is the pre-existing behaviour.
    """
    active = active_phase(phases, today)
    return _start(active) if active is not None else None


def day_number_in_phase(phase: Phase, d: date) -> int:
    """1-indexed day number within the phase (not global). A date_overrides
    entry for d wins over the formula — see Phase.date_overrides."""
    override = phase.date_overrides.get(d.isoformat())
    if override is not None:
        return override
    return (d - _start(phase)).days + 1


def stranded_override_days(phase: Phase) -> list[tuple[str, int]]:
    """Overrides that schedule a plan day PAST the phase's own last date.

    Every reschedule pushes day numbers later without lengthening the phase, so
    a block that absorbs enough shifts runs out of calendar before it runs out
    of content — and nothing said so. `active_phase` stops matching on the last
    date, so from the next morning the athlete gets the reassessment-gap screen
    and the stranded days are simply never presented. It is silent in both
    directions: the override map still claims those dates, and the day-number
    formula still agrees with it.

    Found live on 2026-08-14. Stage 2A had absorbed a forced rest day and one
    session that had nowhere to move, which shifted its numbering two days; its
    overrides put day 27 on 2026-08-17 and **day 28 — the reassessment, which
    produces the final working loads and the functional screen two exit criteria
    are judged on — on 2026-08-18**, while the phase's own calendar ended
    2026-08-16. Both days would have vanished without anyone being told.

    Returns (iso_date, day_number) pairs, sorted, for dates after the phase's
    last day. Empty for a phase that fits, which is the normal case.
    """
    last = _end(phase)
    return sorted(
        (iso, day) for iso, day in phase.date_overrides.items()
        if day and date.fromisoformat(iso) > last
    )


# ── THE WEEK IS ITSELF A BLOCK ───────────────────────────────────────────────
#
# Athlete's rule, 2026-08-14: a rescheduled day may move WITHIN its week and
# nowhere else. "Every week is itself a block" — the seven days are a unit of
# training design (two gym days, two runs, the flexibility slot, the spacing
# between them), and a day that slides into the following week does not arrive
# in a week that had room for it. It arrives in a week already carrying its own
# full complement, and pushes that week's last day into the week after.
#
# That is exactly how Stage 2A ended up two days out of step: a forced rest on
# 2026-08-09 renumbered the tail, week 3's days 20 and 21 were run in week 4's
# calendar slots, and the far end of the block walked off its own last date
# taking the day-28 reassessment with it.
#
# services/scheduling.py already treats the week's Sunday as "the hard boundary
# no scheduling move ever crosses" for the day it is MOVING. What it does not
# bound is the cumulative renumbering that a forced rest leaves behind. This is
# that bound, applied where overrides are written rather than where they are
# generated, so no path can reach the stored phase without passing it.

def week_of_day_number(day_number: int) -> int:
    """1-indexed week a plan day belongs to. Day 1-7 -> 1, 8-14 -> 2, ..."""
    return (day_number - 1) // 7 + 1


def week_of_phase_date(phase: Phase, d: date) -> int:
    """1-indexed week a DATE falls in, counted from the phase's start."""
    return (d - _start(phase)).days // 7 + 1


def override_violations(phase: Phase,
                        overrides: dict[str, int] | None = None) -> list[dict]:
    """Every override that breaks one of the two rules, with its reason.

    `overrides` defaults to the phase's own. Pass a PROPOSED map to check it
    before it is written — which is what reject_violating_overrides does.

    Value 0 is a forced rest, not plan day 0. It schedules nothing, so it can
    break neither rule and is always allowed.
    """
    last, out = _end(phase), []
    for iso, day in sorted((overrides if overrides is not None
                            else phase.date_overrides).items()):
        if not day:
            continue
        d = date.fromisoformat(iso)
        if d > last:
            out.append({"date": iso, "day": day, "rule": "past_block_end",
                        "detail": f"day {day} falls on {iso}, after the block's "
                                  f"last date {last.isoformat()}"})
            continue
        want, got = week_of_phase_date(phase, d), week_of_day_number(day)
        if want != got:
            out.append({"date": iso, "day": day, "rule": "crossed_week",
                        "detail": f"day {day} belongs to week {got} but {iso} is "
                                  f"in week {want} of the block"})
    return out


def reject_violating_overrides(phase: Phase,
                               proposed: dict[str, int]) -> tuple[dict[str, int], list[dict]]:
    """Split a proposed override map into (allowed, rejected).

    Rejects rather than clamps. A day number nudged to fit is a different
    session from the one the athlete was offered, silently substituted; a
    rejected move leaves the schedule as it was, which is a state they can see
    and act on. The caller is expected to surface the rejections.
    """
    merged = {**phase.date_overrides, **proposed}
    bad = {v["date"] for v in override_violations(phase, merged)
           if v["date"] in proposed}
    return ({k: v for k, v in proposed.items() if k not in bad},
            [v for v in override_violations(phase, merged) if v["date"] in bad])


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
