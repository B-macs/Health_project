"""The EGYM session's rules (2026-11-08): its moves, its time and the last
session's tonnage.

THE THREE LAYERS, the "+" session's pattern (services/accessory.py):

    egym_circuit.py             WHAT  — the machines, the sets, the records
        |
    services/egym_session.py    WHICH — the moves, the time, the last tonnage
        |
    services/training_session   HOW   — the same guided flow and save

This file DEFINES NO EXERCISE; it reads them from egym_circuit.py.

IT IS A SESSION OF ITS OWN TYPE, "EGYM" (EGYM_TYPE): a supplementary Type, so it
never marks a plan day done (his answer 1, 2026-11-08: "No, it's extra"), and a
logged day like any other session (his answer 2: "Yes, it does"), so it counts
toward the failed-week rule. It counts in strain and the load ratio.

THE ORDER ("I should be presented a order but I can change it up as I please"):
every machine is a move group of its own, and any machine may run before any
other. Both sets of a machine run one after the other ("I will have to do both
sets just after each other"), so a move takes the machine's two sets together.
"""

from __future__ import annotations

from datetime import date

import egym_circuit as ec
from services import sessions as sess

#: The Type every row of the session is stored under.
EGYM_TYPE = "EGYM"


def build_day() -> dict:
    """The session in the shape a plan day has, so the same guided flow runs
    it."""
    return {
        "objective": ec.OBJECTIVE,
        "phase": ec.PHASE,
        "session_rpe_target": ec.RPE_TARGET,
        "is_gym_session": True,
        "day_type": "main",
        "exercises": ec.entries(),
    }


def move_groups(exercises: list[dict]) -> list[dict]:
    """Every machine's move group (the phone's "In use? Do another first"):
    one group per machine, every one movable, none waiting on another."""
    return [{"group": i, "movable": True, "after": []} for i, _ex in enumerate(exercises)]


def modelled_seconds(exercises: list[dict]) -> int:
    """The whole session: the set-up, every EGYM set (egym_circuit.SET_SECONDS)
    and the rest between a machine's sets, and the measured change to a gym
    station before every machine but the first (sessions.CHANGEOVER_SECONDS,
    his own log)."""
    work = 0
    for ex in exercises:
        n = int(ex.get("sets") or 1)
        work += n * ec.SET_SECONDS + (n - 1) * int(ex.get("rest_seconds") or 0)
    return (sess.SESSION_SETUP_SECONDS + work
            + sess.CHANGEOVER_SECONDS["gym"] * max(0, len(exercises) - 1))


def modelled_minutes(exercises: list[dict]) -> int:
    return max(1, round(modelled_seconds(exercises) / 60))


def last_tonnage(rows: list[dict], today: date) -> dict[str, list[float]]:
    """The newest EGYM session on or before `today`: each machine's tonnage,
    set by set in the order the sets were done (each stored set is one rep at
    its tonnage, egym_circuit.py). `rows` is Repository.get_all_training_
    exercises_raw()'s shape. {} when none is stored."""
    sessions: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("movement_type") != EGYM_TYPE:
            continue
        day = str(row.get("session_date") or "")[:10]
        if not day or day > today.isoformat():
            continue
        sessions.setdefault(str(row.get("session_id")), []).append(row)
    if not sessions:
        return {}

    def last_ts(rs: list[dict]) -> str:
        return max((str(s.get("ts") or "") for r in rs for s in r.get("sets") or []), default="")

    newest = max(sessions.values(), key=lambda rs: (str(rs[0].get("session_date"))[:10], last_ts(rs)))
    sets: dict[str, list[dict]] = {}
    for row in newest:
        name = row.get("movement_name") or ""
        sets.setdefault(name, []).extend(s for s in row.get("sets") or [] if not s.get("is_warmup"))
    return {name: [float(s.get("reps") or 0) * float(s.get("weight") or 0)
                   for s in sorted(rs, key=lambda s: (str(s.get("ts") or ""), s.get("set_num") or 0))]
            for name, rs in sets.items() if rs}


def tonnage_caption(values: list[float] | None) -> str:
    """The line under a machine: the last session's tonnage, set by set."""
    if not values:
        return ""
    return "Last time " + " and ".join(f"{round(v):,} kg" for v in values)


def prescription() -> str:
    return f"{ec.SETS} sets, one after the other"
