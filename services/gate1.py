"""Gate 1 — the first run (goal A, stage 1 to stage 2).

docs/training/goal_system.md, goal A, approved by the athlete on 2026-10-14
and changed on 2026-10-16. Stage 1 is the 12-week block: four strength
sessions and one flexibility session a week, no running. Running starts when
gate 1 passes, and all of these must be true:

1. **Regular training:** 6 weeks in a row with all 3 core sessions (A, B and C)
   done — "Gate 1 now counts the 3 core sessions (3 of 3), not 4 of 4"
   (2026-10-16).
2. **No flare-up in those 6 weeks.** A flare-up is a planned session missed,
   shortened or changed because of the hips or the back. A week with fewer
   than 3 core sessions asks for its reason, one tap (his answer, 2026-10-16):
   hips or back is a flare-up and the count resets; travel or illness pauses
   it; other — the week does not count and the count resets. The count does
   not move past a week until it has its reason. A session shortened or
   changed in a full week is reported the same way (`REASON_FLARE`).
3. **Strength:** each main lift's working weight 10% above its weight on the
   block's first day of it — the lift weights, read directly, not the
   strength score.
4. **The test day before the first run** (a 30-minute brisk walk, then
   single-leg calf raises and hops, without pain) — built when 1-3 pass.

No I/O and no Streamlit, like the rest of services/.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, timedelta

import goal_block as gb
from services import plan
from services.models import Phase

#: The blocks gate 1 reads: the goal system's stage 1.
PHASES = frozenset({5})
WEEKS_REQUIRED = 6
CORE_REQUIRED = len(gb.CORE_LETTERS)
STRENGTH_GAIN = 0.10
#: The gate-1 main lifts (the drop order's third group, 2026-10-16).
MAIN_LIFTS = ("Hack Squat", "Machine Chest Press", "Machine Shoulder Press", "Single-Arm DB Row")

REASON_FLARE = "hips_back"
REASON_PAUSE = "travel_illness"
REASON_OTHER = "other"
#: What each one-tap answer says on screen, and what it does to the count.
REASONS = {
    REASON_FLARE: "Hips or back",
    REASON_PAUSE: "Travel or illness",
    REASON_OTHER: "Other",
}
#: Where the answers are kept: one config row, JSON {monday iso: reason}.
CONFIG_KEY = "gate1_week_reasons"


def applies(phase: Phase | None) -> bool:
    return phase is not None and phase.phase_number in PHASES


def read_reasons(raw: str | None) -> dict[str, str]:
    """The stored answers; an unreadable or absent row reads as none, so a
    week asks again rather than counting on a guess."""
    try:
        data = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}
    return {k: v for k, v in data.items() if v in REASONS} if isinstance(data, dict) else {}


def with_reason(raw: str | None, monday: date, reason: str) -> str:
    if reason not in REASONS:
        raise ValueError(f"{reason!r} is not one of {sorted(REASONS)}")
    data = read_reasons(raw)
    data[monday.isoformat()] = reason
    return json.dumps(dict(sorted(data.items())))


def week_mondays(phase: Phase, today: date) -> list[date]:
    """The Mondays of the block's weeks that have ENDED (their Sunday is
    before today), oldest first."""
    start = date.fromisoformat(phase.start_date)
    monday = start - timedelta(days=start.weekday())
    end = plan.phase_end_date(phase)
    out = []
    while monday + timedelta(days=6) < today and monday <= end:
        out.append(monday)
        monday += timedelta(days=7)
    return out


def core_sessions_done(phase: Phase, plan_dict: dict, logged_dates: set[str],
                       monday: date) -> int:
    """How many of the core sessions (A, B, C) were logged in the week. A
    logged day counts as the session it held (after any move), so a missed
    Monday whose sessions ran in order still reads 3 of 3. `logged_dates` is
    the PLAN-day set: a yoga session is not a core session."""
    done = set()
    for i in range(7):
        d = monday + timedelta(days=i)
        num = plan.day_number_in_phase(phase, d)
        if not (1 <= num <= phase.length_days) or d.isoformat() not in logged_dates:
            continue
        letter = (plan_dict.get(num) or {}).get("session_letter")
        if letter in gb.CORE_LETTERS:
            done.add(letter)
    return len(done)


@dataclass(frozen=True)
class WeekCount:
    monday: date
    core_done: int
    reason: str | None


def count(weeks: list[WeekCount]) -> dict:
    """Part 1 and part 2: the weeks in a row so far, oldest first.

    Returns {"run", "required", "waiting", "met"}: `waiting` is the Monday of
    the first week that needs a reason and has none — the count stops there
    until it has one, his rule ("the count does not move until it has one")."""
    run, waiting = 0, None
    for w in weeks:
        if w.reason == REASON_FLARE:
            run = 0
        elif w.core_done >= CORE_REQUIRED:
            run += 1
        elif w.reason == REASON_PAUSE:
            pass
        elif w.reason == REASON_OTHER:
            run = 0
        else:
            waiting = w.monday
            break
    return {"run": run, "required": WEEKS_REQUIRED, "waiting": waiting,
            "met": waiting is None and run >= WEEKS_REQUIRED}


def _working_weight(sets: list[dict]) -> float | None:
    work = [s for s in sets or [] if not s.get("is_warmup")]
    w = work[-1].get("weight") if work else None
    return None if w is None else float(w)


def lift_weights(history: list[tuple[str, list[dict]]], since: date) -> tuple[float | None, float | None]:
    """(first, latest) working weight of a lift inside the block, from its
    history NEWEST FIRST (Repository.get_recent_session_sets). The working
    weight is the last working set's, as the rep-range rule reads it."""
    inside = [(d, s) for d, s in history or []
              if str(d)[:10] >= since.isoformat() and _working_weight(s) is not None]
    if not inside:
        return None, None
    return _working_weight(inside[-1][1]), _working_weight(inside[0][1])


def strength_rows(weights: dict[str, tuple[float | None, float | None]]) -> list[dict]:
    """Part 3, one row per main lift: its first weight, its latest, the
    target (10% above the first) and whether it is met. A lift not yet
    logged in the block is not met."""
    rows = []
    for lift in MAIN_LIFTS:
        first, latest = weights.get(lift, (None, None))
        target = None if first is None else round(first * (1 + STRENGTH_GAIN), 2)
        met = target is not None and latest is not None and latest >= target - 1e-9
        rows.append({"lift": lift, "first": first, "latest": latest, "target": target,
                     "met": met})
    return rows


def passed(week_count: dict, rows: list[dict]) -> bool:
    """Parts 1-3. Part 4 is a test day of its own, run after these."""
    return week_count["met"] and all(r["met"] for r in rows)


def steps_to_target(row: dict, step: float) -> int | None:
    """How many weight steps stand between the latest weight and the target."""
    if row["target"] is None or row["latest"] is None or not step:
        return None
    return max(0, math.ceil((row["target"] - row["latest"]) / step - 1e-9))
