"""The daily tendon session's rules (WP-40, 2026-10-28): the day it runs, its
time, the 8-hour reminder and whether it is done today.

THE THREE LAYERS, the "+" session's pattern (services/accessory.py):

    daily_tendon.py             WHAT  — the exercises, their doses and records
        |
    services/daily_session.py   WHICH — the day, the time, the reminder
        |
    services/training_session   HOW   — the same guided flow and save

This file DEFINES NO EXERCISE; it reads them from daily_tendon.py.

IT IS A SESSION OF ITS OWN TYPE, "Daily" (DAILY_TYPE): a supplementary Type, so
it never marks a training day done, and a Type that never makes a logged day
(Repository.NOT_A_TRAINING_DAY_TYPES), so a week of daily sessions cannot pass
the failed-week rule. It still counts in strain and the load ratio.

THE 8-HOUR GAP IS A REMINDER, NEVER A LOCK (the athlete, 2026-10-28: "Reminder
only let me make the desicion on when to do it and never locked").
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import daily_tendon as dt
from services import sessions as sess

#: The Type every row of the daily session is stored under.
DAILY_TYPE = "Daily"

#: The reminder's kinds: today's gym session is logged ("after", with the time
#: the gap ends), or still to come today ("before").
AFTER, BEFORE = "after", "before"


def build_day() -> dict:
    """The session in the shape a plan day has, so the same guided flow runs
    it. `day_type` "stretch" for the reason accessory.build_day gives."""
    return {
        "objective": dt.OBJECTIVE,
        "phase": dt.PHASE,
        "session_rpe_target": dt.RPE_TARGET,
        "is_gym_session": False,
        "day_type": "stretch",
        "exercises": dt.entries(),
    }


def entry_seconds(ex: dict) -> int:
    """One entry's working time: every set on every side, each hold with its
    slow start (the phone's hold timer runs the lead-in and the hold as one)."""
    lead = int(ex.get("lead_in_seconds") or 0)
    work = sess.set_work_seconds(ex)
    if ex.get("type") == "hold":
        work += lead
    n = int(ex.get("sets") or 1)
    return n * work * sess.sides(ex) + (n - 1) * int(ex.get("rest_seconds") or 0)


def modelled_seconds(exercises: list[dict]) -> int:
    """The whole session: every entry, and the change before every entry but
    the first. No set-up time: the session starts where he stands. Its own
    model, not sessions.session_seconds: the gym's changeovers were measured
    walking between stations (daily_tendon.CHANGE_SECONDS)."""
    return (sum(entry_seconds(ex) for ex in exercises)
            + dt.CHANGE_SECONDS * max(0, len(exercises) - 1))


def modelled_minutes(exercises: list[dict]) -> int:
    return max(1, round(modelled_seconds(exercises) / 60))


def _parse(ts: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(ts) if ts else None
    except ValueError:
        return None


def reminder(day_sessions: list[dict], plan_still_to_do: bool) -> dict | None:
    """The 8-hour line on the tile, or None (a rest day, or nothing known).

    day_sessions      Repository.get_day_sessions(today).
    plan_still_to_do  today has a plan session that is not logged yet.

    After today's gym session: {"kind": "after", "time": "HH:MM"}, the end
    of the gym session (its last set's time, in the phone's own offset) plus
    daily_tendon.GAP_HOURS. Before it: {"kind": "before", "time": None}. A
    gym session logged with no set time gives no line rather than a guessed
    time."""
    plan = [s for s in day_sessions
            if s.get("type") not in _supplementary() and s.get("last_set_ts")]
    ends = [t for s in plan if (t := _parse(s["last_set_ts"])) is not None]
    if ends:
        free = max(ends) + timedelta(hours=dt.GAP_HOURS)
        return {"kind": AFTER, "time": free.strftime("%H:%M")}
    if any(s.get("type") not in _supplementary() for s in day_sessions):
        return None
    return {"kind": BEFORE, "time": None} if plan_still_to_do else None


def done_today(day_sessions: list[dict]) -> bool:
    """A daily session is logged today."""
    return any(s.get("type") == DAILY_TYPE for s in day_sessions)


def _supplementary() -> frozenset[str]:
    from services.repository import Repository
    return Repository.SUPPLEMENTARY_SESSION_TYPES


def read_day_sessions(repo, today: date) -> list[dict]:
    """Today's sessions, or [] when the read fails: the tile then shows no
    reminder and no "Done today", never an error."""
    try:
        return list(repo.get_day_sessions(today))
    except Exception:
        return []
