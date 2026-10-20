"""The guided training flow as one pure step (move TRN-9, rebuild Phase 2,
2026-10-19).

A session in progress is a POSITION: the exercise, the set, the rep inside a
held set, the side, and whether the athlete is working or resting. Every tap
is an EVENT that moves it: "complete" (a set, a side, a rep or an activity is
done), "next_set" (the rest is over) or "skip". step() takes the position, the
exercise as it runs today and the event, and returns the next position with
what the tap means for the record: the set it completed, whether a rest
begins, and whether the rest that just ended belongs to the set before it.

The Streamlit page and the phone apply the same steps, so a session cannot
advance differently on the two. This module reads no clock: a set's time and
a rest's length come from the caller (the phone sends its own clock).

The hold timer's bell (sessions.hold_ending) announces what the next
"complete" will do; tests/test_guided_flow.py checks the two agree in every
position, so the bell cannot promise something the button then does not do.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from services import sessions

INTRO, RESTING = "intro", "resting"
COMPLETE, NEXT_SET, SKIP = "complete", "next_set", "skip"
EVENTS = (COMPLETE, NEXT_SET, SKIP)

#: When an entry's timer starts by itself (walk's "timer_starts"): a rest
#: starts whenever the flow reaches it; a hold starts when the flow reaches it
#: because the timer before it ran out (a rest, or the hold before it in the
#: same set); anything else waits for the athlete's tap.
ON_ARRIVAL, AFTER_TIMER = "on_arrival", "after_timer"

#: A rest longer than this was an interruption (the phone put down, a call),
#: not an inter-set rest: it is dropped rather than stored. Far above any
#: prescribed rest (the ceiling is 180 s) and far below a session gap.
REST_TAKEN_MAX_SECONDS = 1200


@dataclass(frozen=True)
class Position:
    ex_idx: int = 0
    set_num: int = 1
    rep: int = 1          # the rep inside a held set ("hold_reps"); 1 otherwise
    phase: str = INTRO    # INTRO while working, RESTING between sets
    side: str = "right"


@dataclass(frozen=True)
class Step:
    position: Position
    #: The set number this tap completed, to record; None when it completed
    #: only a side or a rep.
    record_set: int | None = None
    #: A rest begins now: stamp its start.
    rest_begins: bool = False
    #: The rest that just ended: attach its length to the last recorded set.
    rest_ends: bool = False


def _next_exercise(pos: Position, first: str) -> Position:
    return Position(ex_idx=pos.ex_idx + 1, set_num=1, rep=1, phase=INTRO, side=first)


def start(first: str) -> Position:
    """The first position of a session, on the day's first side."""
    return Position(side=first)


def step(pos: Position, ex: dict, event: str, *, first: str) -> Step:
    """The position after `event` on exercise `ex` (as it runs today, after
    sessions.readiness_dose). `first` is the day's first side
    (sessions.first_side). Raises ValueError on an event the position does
    not take: a rest ends only with "next_set", and "next_set" only ends a
    rest."""
    if event not in EVENTS:
        raise ValueError(f"unknown event {event!r}")
    if event == SKIP:
        return Step(_next_exercise(pos, first))
    if event == NEXT_SET:
        if pos.phase != RESTING:
            raise ValueError("next_set ends a rest, and there is no rest")
        return Step(replace(pos, phase=INTRO, side=first, rep=1), rest_ends=True)
    if pos.phase == RESTING:
        raise ValueError("a rest ends with next_set")

    ex_type = ex["type"]
    if ex_type == "duration":
        return Step(_next_exercise(pos, first), record_set=1)
    if ex_type == "hold_reps" and pos.rep < ex.get("reps_in_set", 5):
        return Step(replace(pos, rep=pos.rep + 1))
    if ex.get("laterality") == "unilateral" and pos.side == first:
        return Step(replace(pos, side=sessions.other_side(first), rep=1))
    # Both sides done (or one-sided): the set is complete.
    if pos.set_num >= ex.get("sets", 1):
        return Step(_next_exercise(pos, first), record_set=pos.set_num)
    return Step(Position(pos.ex_idx, pos.set_num + 1, 1, RESTING, first),
                record_set=pos.set_num, rest_begins=True)


def hold_starts_next(ex: dict, pos: Position, first: str) -> bool:
    """Whether this hold, when its timer runs out by itself, starts the next
    hold by itself: the next rep of the set, or the second side's first rep
    (the Training page's auto-start, rebuild Phase 6 move). A set's last hold
    starts nothing itself: a rest follows, and the rest's own end starts the
    next set's hold. A timed test (the plank test) never starts by itself."""
    if ex.get("type") not in sessions.HOLD_TIMER_TYPES or sessions.is_timed_test(ex):
        return False
    if pos.phase != INTRO:
        return False
    nxt = step(pos, ex, COMPLETE, first=first).position
    return (nxt.ex_idx, nxt.set_num, nxt.phase) == (pos.ex_idx, pos.set_num, INTRO)


def timer_starts(exercises: list[dict], prev: Position | None, pos: Position,
                 first: str) -> str | None:
    """When the timer at `pos` starts by itself, after `prev` (None at the
    session's start): ON_ARRIVAL for a rest, AFTER_TIMER for a hold that
    follows a rest of its exercise or a hold that starts the next one
    (hold_starts_next), None for everything the athlete starts."""
    if pos.phase == RESTING:
        return ON_ARRIVAL
    ex = exercises[pos.ex_idx]
    if (prev is None or prev.ex_idx != pos.ex_idx
            or ex.get("type") not in sessions.HOLD_TIMER_TYPES or sessions.is_timed_test(ex)):
        return None
    if prev.phase == RESTING or hold_starts_next(ex, prev, first):
        return AFTER_TIMER
    return None


def finished(pos: Position, n_exercises: int) -> bool:
    """Every exercise is behind the position: the save screen is next."""
    return pos.ex_idx >= n_exercises


def rest_taken(started_at: float, now: float) -> int | None:
    """The rest's length in whole seconds, from the caller's two clock
    readings; None when no rest was timed or it was an interruption."""
    if not started_at:
        return None
    elapsed = int(now - started_at)
    return elapsed if 0 < elapsed <= REST_TAKEN_MAX_SECONDS else None


def attach_rest(set_rows: list[dict], seconds: int | None) -> None:
    """Put a measured rest on the set it FOLLOWED: the highest set number
    recorded so far, matching the record's own "rest after set N". No rest
    measured, or no set recorded, changes nothing: an absent value means "not
    measured", which keeps it apart from a genuinely short rest."""
    if seconds is None or not set_rows:
        return
    last = max(set_rows, key=lambda r: r.get("set_num") or 0)
    last["rest_taken_seconds"] = seconds


def walk(exercises: list[dict], first: str) -> list[dict]:
    """Every position of a session in order, for a phone that walks the
    session offline (rebuild Phase 2, milestone 5): no step rule is copied
    into the phone; it reads this list.

    Each entry is one position and the event that leaves it ("complete"
    while working, "next_set" in a rest), with what that event records
    (step()'s record_set, rest_begins, rest_ends), for a hold, the ending
    its timer's bell announces (sessions.hold_ending), and when its timer
    starts by itself (timer_starts). The walk is linear:
    the event leads to entry `index + 1`, and the last entry's event finishes
    the session. "skip" from any entry leads to `skip_to`, the next
    exercise's first entry, or len(list) (finished) from the last exercise.
    `exercises` are as they run today (sessions.readiness_dose)."""
    raw: list[tuple[Position, str, Step]] = []
    pos = start(first)
    while not finished(pos, len(exercises)):
        event = NEXT_SET if pos.phase == RESTING else COMPLETE
        nxt = step(pos, exercises[pos.ex_idx], event, first=first)
        raw.append((pos, event, nxt))
        pos = nxt.position
    first_entry: dict[int, int] = {}
    for i, (p, _event, _nxt) in enumerate(raw):
        first_entry.setdefault(p.ex_idx, i)
    out = []
    for i, (p, event, nxt) in enumerate(raw):
        ex = exercises[p.ex_idx]
        ending = None
        if ex["type"] in sessions.HOLD_TIMER_TYPES and p.phase == INTRO:
            ending = sessions.hold_ending(
                ex["type"], is_uni=ex.get("laterality") == "unilateral", side=p.side,
                cur_set=p.set_num, total_sets=ex.get("sets", 1), cur_rep=p.rep,
                reps_per_set=ex.get("reps_in_set", 5) if ex["type"] == "hold_reps" else 1,
                first=first)
        prev = raw[i - 1][0] if i else None
        out.append({"index": i, "ex_idx": p.ex_idx, "set_num": p.set_num, "rep": p.rep,
                    "phase": p.phase, "side": p.side, "event": event,
                    "record_set": nxt.record_set, "rest_begins": nxt.rest_begins,
                    "rest_ends": nxt.rest_ends, "ending": ending,
                    "timer_starts": timer_starts(exercises, prev, p, first),
                    "skip_to": first_entry.get(p.ex_idx + 1, len(raw))})
    return out
