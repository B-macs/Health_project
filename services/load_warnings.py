"""Insights › Warnings: the days the app told him to lower the load, and why.

The owner, 2026-10-21: "Oh I thought the warning was the days that it says
reduce load because of tiredness or other reason strain? Can we change it to
this? This is more relevant", and "Let's make this warning a clearer way to do
it then types or tightness mapping". Until then the calendar showed the keyword
parse of his typed notes (services/processing_queue.py), which he rarely
writes; that parse stays, for Trends.

A day's warning is that day's own decision, the one Home and Training show
(services/decision.day_verdict), worked out again from the readings stored for
the day:

  * "rest"     the light was red: rest advised;
  * "reduced"  the readings asked for less: reduced load;
  * "held"     the load stayed at the last session: the injury cap, while the
               days without pain are too few.

A clear day carries no warning, and neither does a day with no reading: having
nothing to judge is not a warning about him. Days after the caller's day are
never worked out. Each day costs one decision (about 25 ms over the local copy,
measured 2026-10-21), so a month is about a second.

Nothing here decides anything: it reads the decision each day had.
"""

from __future__ import annotations

from datetime import date

from services import decision, processing_queue

#: The day's banner kind -> the calendar's level, strongest first.
LEVELS: dict[str, str] = {"error": "rest", "warning": "reduced", "info": "held"}


def day_warning(repo, day: date) -> tuple[str | None, str]:
    """(level, cause) for `day`: the decision's level, or None on a clear day or
    a day with no reading; and the reading the engine named for a rest or a
    reduced day ("" for the injury cap, which names none)."""
    verdict = decision.day_verdict(repo, day)
    level = LEVELS.get(verdict.banner_kind)
    return level, (verdict.cause if level else "")


def calendar(repo, today: date, year: int | None = None, month: int | None = None) -> dict:
    """One month of warnings: today's month unless one is asked for, each day of
    its weeks up to `today` with its level and cause, and how many days of the
    month carry each level."""
    if year is None or month is None:
        year, month = processing_queue.calendar_anchor(today)
    prev_y, prev_m = processing_queue.step_month(year, month, -1)
    next_y, next_m = processing_queue.step_month(year, month, 1)
    weeks = []
    counts = {level: 0 for level in LEVELS.values()}
    for week in processing_queue.month_weeks(year, month):
        row = []
        for d in week:
            level, cause = day_warning(repo, d) if d <= today else (None, "")
            if level and d.month == month:
                counts[level] += 1
            row.append({"date": d, "in_month": d.month == month, "is_today": d == today,
                        "level": level, "cause": cause})
        weeks.append(row)
    return {"year": year, "month": month,
            "previous": {"year": prev_y, "month": prev_m}, "next": {"year": next_y, "month": next_m},
            "weeks": weeks, "counts": counts}
