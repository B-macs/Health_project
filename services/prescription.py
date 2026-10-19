"""Today's numbers for one exercise: the proposal and the last session.

The Training page made the reads and called services.sessions.
resolve_prescription in its own `_seed_actuals_if_needed` until 2026-10-19.
The phone's API needs the same numbers, so the reads and the resolution live
here and both call seed_exercise().

TWO THINGS COME FROM THE SAME PAIR OF READS, and they are kept apart on
purpose. `entry` is the PROPOSAL: nudged by readiness, clamped to the ceiling,
the stepper's starting value. `previous` is the RAW previous session, never
touched by any of that, because it is the number the athlete checks the
proposal against. Deriving the second from the first was the bug a "Last
time:" caption once had: it printed the proposal, so a real +2.5 kg step
read as no change.

A failed read never blocks the session: a lookup that fails reads as no data
(the proposal then starts from the plan), and an unreadable check-in BLOCKS a
weight step, like a missing one, because an unread pain score is not a clean
one (Key Rule 23).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from services import sessions as sess

#: Why a weight step waits when today's check-in could not be read.
CHECK_IN_UNREAD = "today's check-in could not be read"


@dataclass(frozen=True)
class Seed:
    """`previous` is sessions.previous_performance's reading of the last
    session. `entry` is the stepper's starting values, or None when only the
    previous reading was asked for. `contradiction` is set when the
    resolution contradicted its own ceiling and the entry fell back to the
    last completed session."""
    previous: dict
    entry: dict | None = None
    contradiction: str | None = None


def _read(read, default=None):
    try:
        return read()
    except Exception:
        return default


def seed_exercise(repo, ex: dict, *, streak_label: str, policy: dict, today: date,
                  lift_entry: dict | None = None, with_entry: bool = True) -> Seed | None:
    """The previous session and today's proposal for one exercise, or None
    for an exercise without a stepper (no equipment and no editable reps).

    `lift_entry` is the entry of the lift a ramp set prepares
    (sessions.ramp_lift_index): the ramp then proposes about 60% of the
    lift's weight for today, whatever it logged last time. An unloaded "reps"
    exercise gets a reps-only entry at today's prescription
    (sessions.bodyweight_entry). A loaded lift with a rep range reads its
    recent sessions for the range's step (engine.range_progression), and a
    step then waits on today's check-in (the pain gate)."""
    loaded = bool(ex.get("equipment_type"))
    if not loaded and not sess.reps_are_editable(ex):
        return None
    last = _read(lambda: repo.get_last_performance(ex["name"]))
    last_session_sets = _read(lambda: repo.get_last_session_all_sets(ex["name"]))
    previous = sess.previous_performance(last, last_session_sets)
    if not with_entry:
        return Seed(previous)
    if lift_entry is not None:
        return Seed(previous, sess.ramp_entry(ex, lift_entry))
    if not loaded:
        return Seed(previous, sess.bodyweight_entry(ex))
    history = None
    if ex.get("rep_min") is not None and ex.get("rep_max") is not None:
        history = _read(lambda: repo.get_recent_session_sets(ex["name"]), default=[])
    step_block = None
    if history:
        # Read per exercise, so a check-in made mid-session counts.
        try:
            step_block = sess.step_block_reason(sess.todays_check_in(
                repo.get_recent_readiness(days=1, today=today), today))
        except Exception:
            step_block = CHECK_IN_UNREAD
    try:
        return Seed(previous, sess.resolve_prescription(
            ex, last, streak_label, policy,
            weight_increment=ex.get("increment_size", 2.5),
            last_session_sets=last_session_sets,
            history=history,
            step_block=step_block,
        ))
    except sess.PrescriptionContradiction as exc:
        # The clamp should make this unreachable, so reaching it means the
        # resolution itself is broken. The caller shows it; the entry falls
        # back to the last completed session, the safe direction by
        # definition, because blocking a session in progress is worse.
        ceiling = sess.last_completed_ceiling(last, last_session_sets)
        return Seed(previous, {
            "reps": ceiling.get("reps"), "weight_kg": ceiling.get("weight_kg"),
            "band_tier": ceiling.get("band_tier"), "source": "last_time",
            "last_seen_date": ceiling.get("session_date"), "clamped": {},
        }, contradiction=str(exc))
