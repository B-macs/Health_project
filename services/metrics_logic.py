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
from services import sessions as _sess
from services.models import Phase, StreakInfo, WeekScore

_GOOD_STATUSES = ("perfect", "ultimate")

#: A week with this many logged days or fewer is a FAILED week, and a failed
#: week repeats (services/week_repeat.py). The athlete's number, 2026-09-15:
#: "change the failed week to 0-2 days" — "if I performed 3 days it's not a
#: failed week". A COUNT of days, not a share: it replaced the old <20% line,
#: which let one logged day in seven read as a normal week.
FAILED_WEEK_MAX_DAYS = 2


#: A week is perfect at 80% of its planned sessions: completed * 5 >=
#: scheduled * 4, integer math.
PERFECT_SHARE = (4, 5)


def _is_perfect(scheduled: int, completed: int) -> bool:
    num, den = PERFECT_SHARE
    return completed * den >= scheduled * num


def week_status(scheduled: int, completed: int, logged_days: int | None = None) -> str:
    """The verdict of an ENDED week, integer math only:
      - scheduled == 0: "no_plan" (reassessment gap / pre-plan)
      - completed == scheduled: "ultimate"
      - completed*5 >= scheduled*4 (>=80%): "perfect"
      - logged_days > FAILED_WEEK_MAX_DAYS (3 or more days): "normal"
      - else: "failed"
    `completed` is the planned sessions done; `logged_days` every day with a
    logged session (Key Rule 22: all seven days count toward passing), and
    defaults to `completed`."""
    logged_days = completed if logged_days is None else logged_days
    if scheduled == 0:
        return "no_plan"
    if completed == scheduled:
        return "ultimate"
    if _is_perfect(scheduled, completed):
        return "perfect"
    if logged_days > FAILED_WEEK_MAX_DAYS:
        return "normal"
    return "failed"


def week_progress(scheduled: int, completed: int,
                  logged_days: int | None = None) -> tuple[str, int]:
    """The live week's line, from the same thresholds as week_status:
    (kind, sessions to go). kind is "no_plan", "ultimate", "perfect" (to go:
    to ultimate), "failing" (to go: to pass the week, Key Rule 22) or
    "normal" (to go: to a perfect week, at least 1)."""
    logged_days = completed if logged_days is None else logged_days
    status = week_status(scheduled, completed, logged_days)
    if status in ("no_plan", "ultimate"):
        return status, 0
    if status == "perfect":
        return "perfect", max(0, scheduled - completed)
    if status == "failed":
        return "failing", FAILED_WEEK_MAX_DAYS + 1 - logged_days
    num, den = PERFECT_SHARE
    needed = -(-(scheduled * num) // den)  # ceil(scheduled * 4 / 5)
    return "normal", max(1, needed - completed)


def score_week(week_start: date, today: date, scheduled: int, completed: int,
               phase_number: int | None = None, logged_days: int | None = None) -> WeekScore:
    """Pure verdict for one week: "in_progress" for the current week
    (week_start <= today <= week_end), unconditionally — this overrides even
    a 0-scheduled week, since the live week is always still "in progress",
    never "no_plan" — else week_status."""
    week_end = week_start + timedelta(days=6)
    if week_start <= today <= week_end:
        status = "in_progress"
    else:
        status = week_status(scheduled, completed, logged_days)

    return WeekScore(
        week_start=week_start.isoformat(),
        week_end=week_end.isoformat(),
        phase_number=phase_number,
        scheduled=scheduled,
        completed=completed,
        status=status,
        logged_days=completed if logged_days is None else logged_days,
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
    contents: dict[int, dict] = {}

    history: list[WeekScore] = []
    week_start = earliest
    while week_start <= latest:
        days = [week_start + timedelta(days=i) for i in range(7)]
        covering = [_phase_covering_date(phases, d) for d in days]
        # A PLANNED REST day is not a scheduled session (fault F25, found
        # 2026-10-19): the 12-week block's Wednesday and Saturday have
        # nothing to do, and counting them made a perfect week impossible
        # (5 of 7 is under 80%). A session logged on one still counts toward
        # passing the week, never toward a perfect or ultimate one. No block
        # before the 12-week block has an empty rest day, so no earlier week
        # changes.
        rest = {d for d, c in zip(days, covering)
                if c is not None and _planned_rest(c, d, contents)}
        scheduled = sum(1 for d, c in zip(days, covering) if c is not None and d not in rest)
        logged_days = sum(1 for d in days if d.isoformat() in logged)
        completed = logged_days - sum(1 for d in rest if d.isoformat() in logged)
        phase_number = _majority_phase_number(covering)
        history.append(score_week(week_start, today, scheduled, completed,
                                  phase_number=phase_number, logged_days=logged_days))
        week_start += timedelta(days=7)

    return history


def _planned_rest(phase: Phase, d: date, contents: dict[int, dict]) -> bool:
    """Whether `d` is a planned rest day of `phase` (sessions.is_planned_rest),
    reading each phase's content once. A phase whose content cannot be read
    has no planned rest day, which is how every week was counted before."""
    key = id(phase)
    if key not in contents:
        try:
            contents[key] = _sess.calendar_plan(phase)
        except Exception:
            contents[key] = {}
    return _sess.is_planned_rest(contents[key].get(_plan.day_number_in_phase(phase, d)))


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
