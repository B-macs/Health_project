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

THE SECOND OF TWO TRAINING DAYS IN A ROW (the athlete, 2026-11-18: "mobility
only when there is a rest day the next day after the two days of training";
his answer the same day: yesterday trained, today a strength day, tomorrow
rest). Until then the day before was never read, so a missed Monday put the
evening on Tuesday (B still there, rest on Wednesday) until the week was moved,
and the moved B put it on Wednesday too: two evenings in a row, in the weeks of
9 and 16 Nov. A day before today counts as a training day only when a plan
session was logged on it (is_training_day); today and the days after it count
by the schedule. A strength day alone (after a missed day, or after a rest day)
has no evening. On its evenings the session still replaces the tendon session
(his answer the same day: "Mobility replaces tendon").

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

A DAY'S SESSION CAN BE SWAPPED WITH ANOTHER DAY'S (the athlete, 2026-11-19: "If
for what ever reason I dont want to do Evening mobility today or if I dont want
to do daily tendon, I should be able to swap with another day"). A swap trades
the second-tile sessions of two days of the same week, today or later
(training_session.swap_evening); the swaps are kept in config (SWAPS_KEY) as
pairs of days and applied over the rule's own answer (apply_swaps), so the week
still holds the same evenings, only on other days, and a later move of the
sessions trades whatever the two days then hold.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import goal_block as gb
from services import plan as _plan
from services import sessions as sess

#: The Type every row of the evening mobility session is stored under.
MOBILITY_TYPE = "Evening Mobility"

#: The overview's line. Plain words, the blueprint's own timing.
NOTE = ("Strength in the morning, this session in the evening. Each exercise opens the "
        "next one, so do them in this order.")

#: The overview's line before the first front split test (2026-11-11): the goal
#: is the front split, and its stack waits for the test that picks it.
NOTE_BEFORE_TEST = ("Your flexibility goal is now the front split. Take its test first, on "
                    "a cold morning after a day with no leg training (Insights, "
                    "Flexibility). Until then this is the side split stack you had.")


def build_day(front_split_pattern: str | None = None) -> dict:
    """The session in the shape a plan day has, so the same guided flow runs it:
    the front split stack for the latest front split test's pattern, or, before
    the first test, the last stack a test prescribed (goal_block.
    evening_mobility_day)."""
    return gb.evening_mobility_day(front_split_pattern)


def note(front_split_pattern: str | None) -> str:
    return NOTE if front_split_pattern else NOTE_BEFORE_TEST


def front_split_pattern(repo, today: date) -> str | None:
    """The pattern of the latest front split test, or None: no test yet, no
    pattern reached, or the store could not be read (the last stack runs, never
    a guessed one)."""
    from services import flexibility as fx
    try:
        latest = fx.latest(repo.get_flexibility_assessments(), fx.GOAL_CLUSTER)
    except Exception:
        return None
    if latest is None:
        return None
    return fx.assess(latest, today).pattern


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


def is_training_day(phases, d: date, today: date | None = None, trained_on=None) -> bool:
    """`d` counts as a training day. Before `today`, a plan session was logged
    on it (`trained_on`, the dates); `today` and the days after it, its
    scheduled plan day is a strength session (today also when one is logged
    there). Without `trained_on` (None) every day counts by the schedule: the
    plan's own week."""
    if trained_on is None or today is None:
        return is_strength_day(scheduled_day(phases, d))
    if d < today:
        return d in trained_on
    return is_strength_day(scheduled_day(phases, d)) or (d == today and d in trained_on)


def is_evening(phases, d: date, today: date | None = None, trained_on=None) -> bool:
    """`d` is the second of two training days in a row and the next day is not
    one (his rule, 2026-11-18): the day before was trained, `d` is a strength
    day, the day after is a rest day (is_training_day). A strength day not yet
    trained at the time of asking still has its evening."""
    def training(x: date) -> bool:
        return is_training_day(phases, x, today, trained_on)
    return (training(d - timedelta(days=1)) and training(d)
            and not training(d + timedelta(days=1)))


def is_due(phases, today: date, done_on=(), trained_on=None, asked_on: date | None = None) -> bool:
    """The evening session is due today.

    A MOVE NEVER ADDS AN EVENING (the athlete, 2026-11-11: "when I move the
    Friday training to Thursday the evening mobility if not performed goes to
    Thursday"). The week owes WEEKLY_EVENINGS, or fewer when it has fewer
    evenings, less the evening sessions done before today (`done_on`, the days
    with one logged); the evenings it still owes are its last ones from today
    on. So with Tuesday's evening done and Thursday's C moved to Wednesday,
    Wednesday (B Tuesday, C Wednesday, rest Thursday) has none; with Tuesday's
    not done, Wednesday has one. `trained_on`: the days with a logged plan
    session (is_training_day).

    `asked_on`: the day the question is asked, when it is not `today` (the week
    page's tile for another day, 2026-11-18: "When I select each day today every
    one of them is mobility ? Tomorrow should be tendon?"). The days before it
    count by the log, it and the days after it by the plan."""
    asked = asked_on or today
    if not is_evening(phases, today, asked, trained_on):
        return False
    monday = today - timedelta(days=today.weekday())
    evenings = [d for d in (monday + timedelta(days=i) for i in range(7))
                if is_evening(phases, d, asked, trained_on)]
    done = sum(1 for d in set(done_on) if monday <= d < today)
    owed = min(WEEKLY_EVENINGS, len(evenings)) - done
    if owed <= 0:
        return False
    ahead = [d for d in evenings if d >= today]
    return today in ahead[max(0, len(ahead) - owed):]


def done_today(day_sessions: list[dict]) -> bool:
    """An evening mobility session is logged today."""
    return any(s.get("type") == MOBILITY_TYPE for s in day_sessions)


# ─── Swaps between two days (2026-11-19) ─────────────────────────────────────

#: The config row of the swaps, in the order made: [{"a": "YYYY-MM-DD", "b": ...}].
SWAPS_KEY = "evening_swaps"
#: The newest swaps kept. Each one acts inside its own week, so a short list is plenty.
SWAPS_KEPT = 60


def _parse_swaps(raw) -> list[tuple[date, date]]:
    try:
        items = json.loads(raw) if raw else []
    except ValueError:
        return []
    out = []
    for item in items if isinstance(items, list) else []:
        try:
            out.append((date.fromisoformat(item["a"]), date.fromisoformat(item["b"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def read_swaps(repo, live: bool = False) -> list[tuple[date, date]]:
    """The stored swaps, oldest first. `live` reads the store itself (before a
    write); the screen reads the local copy."""
    raw = (repo.get_config_value_live if live else repo.get_config_value)(SWAPS_KEY)
    return _parse_swaps(raw)


def store_swap(repo, a: date, b: date, today: date) -> None:
    swaps = read_swaps(repo, live=True) + [(a, b)]
    repo.set_config(SWAPS_KEY, json.dumps(
        [{"a": x.isoformat(), "b": y.isoformat()} for x, y in swaps[-SWAPS_KEPT:]]), today)


def apply_swaps(kinds: dict, swaps) -> dict:
    """`kinds` ({day: session}) with each swap's two days trading their
    sessions, in the order the swaps were made. A swap with a day outside
    `kinds` (another week) changes nothing."""
    out = dict(kinds)
    for a, b in swaps:
        if a in out and b in out:
            out[a], out[b] = out[b], out[a]
    return out
