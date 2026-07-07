"""
services/metrics_logic.py — Weekly Rollup ("Perfect/Ultimate Week") scoring.
Pure, no I/O, no Streamlit — mirrors the plan.py/sessions.py split, kept
separate from plan.py because this is a distinct concern (weekly adherence
scoring, not phase/day-numbering) and separate from services/metrics.py
(the orchestration module that persists this to Sheets) so these functions
need zero mocking to test.

Weeks run Monday-Sunday. Reuses plan.day_number_in_phase and
plan.phase_week_bounds for all date/week-boundary math rather than
re-deriving it.
"""

from __future__ import annotations

from datetime import date, timedelta

from services import plan as _plan
from services.models import Phase, StreakInfo, WeekScore

_GOOD_STATUSES = ("perfect", "ultimate")


def score_week(week_start: date, today: date, scheduled: int, completed: int,
                phase_number: int | None = None) -> WeekScore:
    """Pure verdict for one week. Integer math only (no float thresholds):
      - current week (week_start <= today <= week_end): "in_progress",
        unconditionally — this overrides even a 0-scheduled week, since the
        live week is always still "in progress", never "no_plan".
      - else scheduled == 0: "no_plan" (reassessment gap / pre-plan)
      - else completed == scheduled: "ultimate"
      - else completed*5 >= scheduled*4 (>=80%): "perfect"
      - else completed*5 >= scheduled*1 (>=20%): "normal"
      - else: "failed"
    """
    week_end = week_start + timedelta(days=6)
    if week_start <= today <= week_end:
        status = "in_progress"
    elif scheduled == 0:
        status = "no_plan"
    elif completed == scheduled:
        status = "ultimate"
    elif completed * 5 >= scheduled * 4:
        status = "perfect"
    elif completed * 5 >= scheduled * 1:
        status = "normal"
    else:
        status = "failed"

    return WeekScore(
        week_start=week_start.isoformat(),
        week_end=week_end.isoformat(),
        phase_number=phase_number,
        scheduled=scheduled,
        completed=completed,
        status=status,
    )


def _phase_covering_date(phases: list[Phase], d: date) -> Phase | None:
    """Status-agnostic variant of plan.active_phase's coverage check — reuses
    plan.day_number_in_phase for the actual day-in-range math, but (unlike
    active_phase) doesn't filter by status=="active", since historical
    scoring needs to see completed/upcoming phases too, not just the
    currently-active one."""
    for p in phases:
        n = _plan.day_number_in_phase(p, d)
        if 1 <= n <= p.length_days:
            return p
    return None


def _majority_phase_number(covering: list[Phase | None]) -> int | None:
    """Most-frequent phase_number across a week's 7 days (a boundary week
    straddles two phases); ties broken by first-encountered, for a
    deterministic result."""
    nums = [c.phase_number for c in covering if c is not None]
    if not nums:
        return None
    order: list[int] = []
    counts: dict[int, int] = {}
    for n in nums:
        if n not in counts:
            counts[n] = 0
            order.append(n)
        counts[n] += 1
    return max(order, key=lambda n: counts[n])


def compute_week_history(today: date, phases: list[Phase], sessions: list[dict]) -> list[WeekScore]:
    """One WeekScore per Monday-anchored week, from the earliest phase's
    first week through the current week (inclusive) — including any gap
    weeks with zero scheduled sessions. `sessions`: [{"date": "YYYY-MM-DD"}],
    the same cheap existence-check shape plan.get_week_view already uses.
    Sessions are attributed to weeks by their own date, independent of which
    phase (if any) covers that date.

    Always stops at the current week, even if a pre-configured future/
    upcoming phase's date range extends further out — weeks that haven't
    happened yet must never be generated (score_week has no "not started
    yet" status; scoring one would wrongly come out "failed")."""
    if not phases:
        return []

    earliest = min(_plan.phase_week_bounds(p)[0] for p in phases)
    current_week = today - timedelta(days=today.weekday())
    latest = current_week

    logged = {s["date"] for s in sessions}

    history: list[WeekScore] = []
    week_start = earliest
    while week_start <= latest:
        days = [week_start + timedelta(days=i) for i in range(7)]
        covering = [_phase_covering_date(phases, d) for d in days]
        scheduled = sum(1 for c in covering if c is not None)
        completed = sum(1 for d in days if d.isoformat() in logged)
        phase_number = _majority_phase_number(covering)
        history.append(score_week(week_start, today, scheduled, completed, phase_number=phase_number))
        week_start += timedelta(days=7)

    return history


def compute_streak(history: list[WeekScore]) -> StreakInfo:
    """current_streak/best_streak count consecutive perfect-or-ultimate
    ended weeks. no_plan and normal weeks pause the streak (skipped, not
    broken); failed weeks reset it. no_plan weeks are excluded from the
    tallies entirely (never scored). The in_progress (current) week is
    excluded from everything here — it isn't "ended" yet."""
    ended = [w for w in history if w.status != "in_progress"]

    perfect_count = sum(1 for w in ended if w.status == "perfect")
    ultimate_count = sum(1 for w in ended if w.status == "ultimate")
    normal_count = sum(1 for w in ended if w.status == "normal")
    failed_count = sum(1 for w in ended if w.status == "failed")

    current_streak = 0
    for w in reversed(ended):
        if w.status in _GOOD_STATUSES:
            current_streak += 1
        elif w.status == "failed":
            break
        # no_plan / normal: pause — skip without incrementing or breaking

    best_streak = 0
    running = 0
    for w in ended:
        if w.status in _GOOD_STATUSES:
            running += 1
            best_streak = max(best_streak, running)
        elif w.status == "failed":
            running = 0
        # no_plan / normal: pause — running carries over unchanged

    return StreakInfo(
        current_streak=current_streak,
        best_streak=best_streak,
        perfect_count=perfect_count,
        ultimate_count=ultimate_count,
        normal_count=normal_count,
        failed_count=failed_count,
    )


def current_streak_is_all_ultimate(history: list[WeekScore]) -> bool:
    """True only if every week contributing to the current streak (the same
    backward walk compute_streak does — pausing over no_plan/normal, stopping
    at failed) is "ultimate" rather than merely "perfect". Used by the UI to
    decide between the "N week streak" and "N week ultimate streak" labels.
    False for a zero-length streak."""
    ended = [w for w in history if w.status != "in_progress"]
    contributing: list[WeekScore] = []
    for w in reversed(ended):
        if w.status in _GOOD_STATUSES:
            contributing.append(w)
        elif w.status == "failed":
            break
    return bool(contributing) and all(w.status == "ultimate" for w in contributing)
