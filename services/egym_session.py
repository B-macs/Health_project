"""The EGYM circuit's rules (2026-11-08): its moves, its time and the last
circuit's tonnage.

THE THREE LAYERS, the "+" session's pattern (services/accessory.py):

    egym_circuit.py             WHAT  — the machines, the rounds, the records
        |
    services/egym_session.py    WHICH — the moves, the time, the last tonnage
        |
    services/training_session   HOW   — the same guided flow and save

This file DEFINES NO EXERCISE; it reads them from egym_circuit.py.

IT IS A SESSION OF ITS OWN TYPE, "EGYM" (EGYM_TYPE): a supplementary Type, so it
never marks a plan day done (his answer 1, 2026-11-08: "No, it's extra"), and a
logged day like any other session (his answer 2: "Yes, it does"), so it counts
toward the failed-week rule. It counts in strain and the load ratio.

THE ORDER (his answer 6: "round two always follows round one ... if I switch
them around in round one, then in round two, they should be the same"): every
entry is a group of its own; a round-1 group may run before any other round-1
group, a round-2 group only after every round-1 group, and each round-2 group
`mirror_of` its round-1 machine, so the phone moves it the same way when the
round-1 machine moves. In round 2 he may still change the order.
"""

from __future__ import annotations

from datetime import date

import egym_circuit as ec
from services import sessions as sess

#: The Type every row of the circuit is stored under.
EGYM_TYPE = "EGYM"


def build_day() -> dict:
    """The circuit in the shape a plan day has, so the same guided flow runs
    it."""
    return {
        "objective": ec.OBJECTIVE,
        "phase": ec.PHASE,
        "session_rpe_target": ec.RPE_TARGET,
        "is_gym_session": True,
        "day_type": "main",
        "exercises": ec.entries(),
    }


def round_of(index: int) -> int:
    """1 or 2: the round an entry of entries() runs in."""
    return index // len(ec.MACHINES) + 1


def move_groups(exercises: list[dict]) -> list[dict]:
    """Every entry's move group (the phone's "In use? Do another first"):
    one group per entry, all movable; round 2 after every round-1 group, each
    round-2 group the mirror of the same machine in round 1."""
    per_round = len(ec.MACHINES)
    first_round = list(range(min(per_round, len(exercises))))
    out = []
    for i, _ex in enumerate(exercises):
        later = i >= per_round
        out.append({"group": i, "movable": True,
                    "after": first_round if later else [],
                    "mirror_of": i - per_round if later else None})
    return out


def modelled_seconds(exercises: list[dict]) -> int:
    """The whole circuit: the set-up, one EGYM set on every entry
    (egym_circuit.SET_SECONDS) and the measured change to a gym station before
    every entry but the first (sessions.CHANGEOVER_SECONDS, his own log)."""
    sets = sum(int(ex.get("sets") or 1) for ex in exercises)
    return (sess.SESSION_SETUP_SECONDS + sets * ec.SET_SECONDS
            + sess.CHANGEOVER_SECONDS["gym"] * max(0, len(exercises) - 1))


def modelled_minutes(exercises: list[dict]) -> int:
    return max(1, round(modelled_seconds(exercises) / 60))


def tonnage_of(sets: list[dict] | None) -> float | None:
    """The tonnage a stored circuit set holds (reps x weight), or None when
    the entry was skipped."""
    total = sum(float(s.get("reps") or 0) * float(s.get("weight") or 0) for s in sets or []
                if not s.get("is_warmup"))
    return total if sets else None


def last_tonnage(rows: list[dict], today: date) -> dict[str, list[float | None]]:
    """The newest circuit on or before `today`: each machine's tonnage, round
    by round, in the order the rounds ran (the sets' own times). `rows` is
    Repository.get_all_training_exercises_raw()'s shape. {} when no circuit
    is stored."""
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

    def first_ts(row: dict) -> str:
        return min((str(s.get("ts") or "") for s in row.get("sets") or []), default="")

    newest = max(sessions.values(),
                 key=lambda rs: (str(rs[0].get("session_date"))[:10], max(first_ts(r) for r in rs)))
    out: dict[str, list[float | None]] = {}
    # A skipped entry has no set and no time: it goes last.
    for row in sorted(newest, key=lambda r: (first_ts(r) == "", first_ts(r))):
        out.setdefault(row.get("movement_name") or "", []).append(tonnage_of(row.get("sets")))
    return out


def tonnage_caption(value: float | None) -> str:
    """The line under a machine: the same round of the last circuit."""
    return "" if value is None else f"Last time {round(value):,} kg"


def prescription(index: int) -> str:
    return f"Round {round_of(index)} of {ec.ROUNDS}"
