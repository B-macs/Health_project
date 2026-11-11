"""The evening mobility session's rules (2026-11-11): the evenings it runs on,
and whether it is done today.

THE ATHLETE'S WORDS, 2026-11-11, from the flexibility blueprint's second-best
slot ("Same day, evening, after morning training"): "strength training in the
morning and mobilty in the evening, lets schedule it on the days I have no
strength training the next day ... The mobility training will replace the
tendon training on those days." His two answers the same day:

- "Two evenings, no Sunday": the blueprint allows one or two flexibility
  sessions a week, so the Sunday session stops from week 4
  (goal_block.EVENING_MOBILITY_FROM_WEEK).
- "Follow the rule": the session is due on a day whose SCHEDULED plan day is a
  strength session and whose next day's is not (is_due). It moves when the
  sessions move (date_overrides); in a normal week it is Tuesday and Friday.

THE THREE LAYERS, the daily session's pattern (services/daily_session.py):

    goal_block.py                 WHAT  — the stack, its doses and records
        |
    services/mobility_session.py  WHICH — the evenings, done today
        |
    services/training_session     HOW   — the same guided flow and save

This file DEFINES NO EXERCISE; it reads them from goal_block.py.

IT IS A SESSION OF ITS OWN TYPE, "Evening Mobility" (MOBILITY_TYPE), never
"Mobility": that word is the movement type plan exercises are stored under, and
would make a plan row read as an extra. A supplementary Type, so it never marks
the plan day done and never trips the "already logged" lock; and a Type that
never makes a logged day (Repository.NOT_A_TRAINING_DAY_TYPES), because it sits
on a strength day: counted, an evening session alone would mark a skipped
strength day done. It still counts in strain and the load ratio.

NEVER A LOCK: on the evenings it is due the tile offers it in place of the daily
tendon session; when to do it is the athlete's decision.
"""

from __future__ import annotations

from datetime import date, timedelta

import goal_block as gb
from services import plan as _plan
from services import sessions as sess

#: The Type every row of the evening mobility session is stored under.
MOBILITY_TYPE = "Evening Mobility"

#: The overview's line. Plain words, the blueprint's own timing.
NOTE = ("Strength in the morning, this session in the evening. Each exercise opens the "
        "next one, so do them in this order.")


def build_day() -> dict:
    """The session in the shape a plan day has, so the same guided flow runs it."""
    return gb.evening_mobility_day()


def scheduled_day(phases, d: date) -> dict | None:
    """The plan day scheduled on `d` (date_overrides included, repeated weeks
    read through sessions.calendar_plan), or None: no block covers `d`, or `d`
    is a forced rest (a 0 override)."""
    active = _plan.active_phase(phases, d)
    if active is None or active.date_overrides.get(d.isoformat()) == 0:
        return None
    return sess.calendar_plan(active).get(_plan.day_number_in_phase(active, d))


def is_strength_day(day: dict | None) -> bool:
    return bool(day and day.get("is_gym_session"))


#: Evening sessions a week at most: the blueprint's limit, and his answer "Two
#: evenings, no Sunday".
WEEKLY_EVENINGS = 2


def is_evening(phases, d: date) -> bool:
    """`d`'s scheduled plan day is a strength session and the next day's is not
    (his rule, 2026-11-11). The schedule decides, not the log: a strength day
    not yet trained at the time of asking still has its evening."""
    return (is_strength_day(scheduled_day(phases, d))
            and not is_strength_day(scheduled_day(phases, d + timedelta(days=1))))


def is_due(phases, today: date, done_on=()) -> bool:
    """The evening session is due today.

    A MOVE NEVER ADDS AN EVENING (the athlete, 2026-11-11: "when I move the
    Friday training to Thursday the evening mobility if not performed goes to
    Thursday"). The week owes WEEKLY_EVENINGS, or fewer when it has fewer
    evenings, less the evening sessions done before today (`done_on`, the days
    with one logged); the evenings it still owes are its last ones from today
    on. So with Wednesday's evening done and Friday's C moved to Thursday, the
    one still owed is Saturday's, and Thursday has none; with Wednesday's not
    done, Thursday and Saturday both have one."""
    if not is_evening(phases, today):
        return False
    monday = today - timedelta(days=today.weekday())
    evenings = [d for d in (monday + timedelta(days=i) for i in range(7)) if is_evening(phases, d)]
    done = sum(1 for d in set(done_on) if monday <= d < today)
    owed = min(WEEKLY_EVENINGS, len(evenings)) - done
    if owed <= 0:
        return False
    ahead = [d for d in evenings if d >= today]
    return today in ahead[max(0, len(ahead) - owed):]


def done_today(day_sessions: list[dict]) -> bool:
    """An evening mobility session is logged today."""
    return any(s.get("type") == MOBILITY_TYPE for s in day_sessions)
