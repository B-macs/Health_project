"""The training page's week (move TRN-10, rebuild Phase 2, 2026-10-19): the
rollup banner, the verdict of a week paged to, and the day strip, so the
phone's week screen and the Streamlit page read one composition. Every
threshold is metrics_logic's; nothing here re-codes one.

Two faults found in the move, both from the 12-week block's EMPTY rest days
(Wednesday and Saturday, `sessions.is_planned_rest`), which no earlier block
had:

- F24: the strip drew a planned rest day as a planned session, and as missed
  once it had passed. A planned rest day is "rest", the way the day view
  (sessions.day_route) already reads it.
- F25: the banner counted the rest days as scheduled sessions, so a perfect
  week was impossible. metrics_logic.compute_week_history now leaves them
  out (see its note).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from services import metrics_logic as _ml
from services import plan as _plan
from services import sessions as _sess
from services import week_repeat as _wr
from services.models import DayCell, Phase, WeekScore


def week_history(phases: list[Phase], today: date, logged_dates) -> list[WeekScore]:
    """Every week from the first block's first Monday to this week, scored."""
    if not phases:
        return []
    return _ml.compute_week_history(today, phases, [{"date": d} for d in sorted(logged_dates)])


def read_week_history(repo, phases: list[Phase], today: date, logged_dates=None) -> list[WeekScore]:
    """week_history with the logged dates read (every logged session counts
    toward a day, Key Rule 22); a caller with a cached read passes it."""
    if not phases:
        return []
    if logged_dates is None:
        earliest = min(date.fromisoformat(p.start_date) for p in phases)
        logged_dates = repo.get_logged_session_dates(earliest, today)
    return week_history(phases, today, logged_dates)


def banner(history: list[WeekScore], today: date) -> dict:
    """The rollup banner: this week's planned sessions done of scheduled and
    its progress line (metrics_logic.week_progress), the streak, the
    lifetime tallies, and last week's verdict when it shows (a failed week's
    line is Monday's only, week_repeat.last_week_line_is_due)."""
    streak = _ml.compute_streak(history)
    current = next((w for w in history if w.status == "in_progress"), None)
    scheduled = current.scheduled if current else 0
    completed = current.completed if current else 0
    logged_days = (current.logged_days if current is not None and current.logged_days is not None
                   else completed)
    kind, to_go = _ml.week_progress(scheduled, completed, logged_days)
    ended = [w for w in history if w.status not in ("in_progress", "no_plan")]
    last = max(ended, key=lambda w: w.week_start) if ended else None
    return {
        "scheduled": scheduled,
        "completed": completed,
        "progress": kind,
        "to_go": to_go,
        "streak_weeks": streak.current_streak,
        "streak_all_ultimate": _ml.current_streak_is_all_ultimate(history),
        "perfect_count": streak.perfect_count,
        "ultimate_count": streak.ultimate_count,
        "last_week": (last.status if last is not None
                      and _wr.last_week_line_is_due(last.status, today) else None),
    }


def viewed_week_status(history: list[WeekScore], viewed_monday: date | None,
                       today: date) -> str | None:
    """The stored verdict of a week paged to, or None: the current week's
    status is the banner's, and a week not in the history has none."""
    if viewed_monday is None or viewed_monday == today - timedelta(days=today.weekday()):
        return None
    week = next((w for w in history if w.week_start == viewed_monday.isoformat()), None)
    if week is None or week.status == "in_progress":
        return None
    return week.status


def week_strip(week_start: date, phase: Phase | None, logged_dates, today: date) -> list[DayCell]:
    """The seven cells of the day strip (plan.get_week_view), with a planned
    rest day that has no session as "rest" (fault F24)."""
    cells = _plan.get_week_view(week_start, phase, [{"date": d} for d in sorted(logged_dates)],
                                today=today)
    if phase is None:
        return cells
    content = _sess.calendar_plan(phase)
    return [replace(c, state="rest")
            if c.state in ("missed", "planned")
            and _sess.is_planned_rest(content.get(c.day_number_in_phase)) else c
            for c in cells]


#: What a strip cell shows.
MARKERS = ("done", "today", "missed", "planned", "rest")


def strip_marker(cell: DayCell, today: date) -> str:
    """One of MARKERS: a logged day is "done", else today is "today", else
    the cell's own state."""
    if cell.state == "completed":
        return "done"
    if cell.date == today:
        return "today"
    if cell.state in ("missed", "planned"):
        return cell.state
    return "rest"
