"""One save of a complete training session, the same whoever sends it.

The Streamlit Training page and the phone's API both build a SessionSave and
hand it to save_session(). The CALLER mints every id once, before the first
send: the session's and each exercise's. The store keys the session row and
each exercise row on those ids and replaces each exercise's sets, so the same
SessionSave sent three times stores one session (rebuild rule 4), and a send
that stopped partway is completed by the next send of the same SessionSave.

2026-09-10 is why: a Save that stopped partway was pressed again, every press
minted fresh ids and wrote every exercise again, and one 82-minute session
was stored three times (1,306 AU, strain 17.1 for the day). The Training
page then kept a list of the exercises already written and skipped them on
the next press; ids minted by the caller make that list unnecessary, and they
are the only form that works for a phone that resends a save it never heard
back about.

The session note is joined to the last exercise's note HERE, once, rather
than appended by a second write (Repository.save_session_notes), which would
append it again on every resend.

Pure apart from save_session(), which writes through the Repository it is
given: the Supabase-first path (rebuild rule 5).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from services import sessions as sess

#: The longest note the Notes column is given, kept from
#: Repository.save_session_notes.
NOTE_LIMIT = 2000


@dataclass(frozen=True)
class ExerciseSave:
    """One exercise as it is stored: its sets are the per-set records."""
    exercise_id: str
    name: str
    movement_type: str
    planned_sets: int
    planned_reps: int
    sets: tuple = ()
    note: str = ""
    garmin_avg_hr: float | None = None
    garmin_max_hr: float | None = None
    garmin_distance_km: float | None = None
    garmin_calories: float | None = None


@dataclass(frozen=True)
class SessionSave:
    """A complete session: every exercise, in the order it was trained."""
    session_id: str
    session_date: str
    duration_minutes: int
    session_rpe: int
    exercises: tuple = field(default_factory=tuple)
    notes: str = ""

    @property
    def session_au(self) -> float:
        """Foster's session load: RPE x minutes."""
        return float(self.session_rpe * self.duration_minutes)


class SessionSaveError(Exception):
    """A send that stopped partway. `written` of `total` exercises are stored
    under their final ids; sending the same SessionSave again completes it."""

    def __init__(self, written: int, total: int, cause: Exception):
        super().__init__(str(cause))
        self.written = written
        self.total = total
        self.cause = cause


def new_session_id(session_date: date | str) -> str:
    """The session id the Training page mints: the date, then 8 hex digits."""
    return f"{session_date}-{uuid.uuid4().hex[:8]}"


def new_exercise_ids(count: int) -> list[str]:
    return [str(uuid.uuid4()) for _ in range(count)]


def pending_save(session_date: date | str, duration_minutes: int, session_rpe: int,
                 exercise_count: int, earlier: dict | None = None) -> dict:
    """The ids and figures of one save, minted on the first press of Save and
    sent again unchanged on every retry: the session id, the date, the
    duration and RPE of the FIRST press, and one id per exercise.

    `earlier` is the pending save of an earlier press, returned unchanged. One
    without exercise ids for every exercise (begun before 2026-10-19, when the
    store minted them) keeps its session id, duration and RPE and gets new
    exercise ids."""
    earlier = earlier or {}
    exercise_ids = list(earlier.get("exercise_ids") or ())
    if len(exercise_ids) != exercise_count:
        exercise_ids = new_exercise_ids(exercise_count)
    return {
        "session_id": earlier.get("session_id") or new_session_id(session_date),
        "session_date": str(earlier.get("session_date") or session_date),
        "duration_minutes": int(earlier.get("duration_minutes", duration_minutes)),
        "session_rpe": int(earlier.get("session_rpe", session_rpe)),
        "exercise_ids": exercise_ids,
    }


def with_session_note(note: str, session_note: str) -> str:
    """The exercise's note with the session's note after it, joined the way
    Repository.save_session_notes appends one, and cut to NOTE_LIMIT."""
    extra = (session_note or "").strip()
    if not extra:
        return note or ""
    own = (note or "").strip()
    return (f"{own}\n\n{extra}" if own else extra)[:NOTE_LIMIT]


def exercise_from_flow(ex: dict, exercise_id: str, *, actual: dict | None = None,
                       logged_sets: list | None = None, user_note: str = "",
                       garmin_minutes: float | None = None, garmin_detail: dict | None = None,
                       movement_type_override: str | None = None) -> ExerciseSave:
    """One plan exercise as the guided flow finished it.

    The Garmin-verified minutes and the live reps, weight and band steppers
    replace the prescription, on a copy, so the plan's own dict is never
    changed. The per-set records captured as each set was finished are the
    sets; when none were captured (a session saved without the guided flow,
    or a checkpoint from before per-set capture), the prescription is repeated
    with the stepped values (sessions.make_sets_data).

    `movement_type_override` stores every exercise under one Type: the
    accessory session's, which keeps it from marking a plan day done
    (Repository.SUPPLEMENTARY_SESSION_TYPES)."""
    log_ex = dict(ex, duration_minutes=garmin_minutes) if garmin_minutes else dict(ex)
    if actual and (ex.get("equipment_type") or sess.reps_are_editable(ex)):
        if ex["type"] == "hold_reps":
            if actual.get("reps") is not None:
                log_ex["reps_in_set"] = actual["reps"]
        elif actual.get("reps") is not None:
            log_ex["reps"] = actual["reps"]
        if ex.get("equipment_type") == "band":
            if actual.get("band_tier"):
                log_ex["band_tier"] = actual["band_tier"]
        elif actual.get("weight_kg") is not None:
            log_ex["weight_kg"] = actual["weight_kg"]
    garmin_note = (
        f"Garmin-verified duration: {garmin_minutes:.0f} min "
        f"(planned {ex.get('duration_minutes')} min)."
    ) if garmin_minutes else ""
    note = "\n".join(n for n in (garmin_note, (user_note or "").strip()) if n)
    detail = garmin_detail or {}
    return ExerciseSave(
        exercise_id=exercise_id,
        name=ex["name"],
        movement_type=movement_type_override or sess.movement_category(ex),
        planned_sets=ex.get("sets", 1),
        planned_reps=sess.planned_reps(ex),
        sets=tuple(logged_sets or sess.make_sets_data(log_ex)),
        note=note,
        garmin_avg_hr=detail.get("avg_hr"),
        garmin_max_hr=detail.get("max_hr"),
        garmin_distance_km=detail.get("distance_km"),
        garmin_calories=detail.get("calories"),
    )


def build_session(pending: dict, exercises: list, *, actuals: dict | None = None,
                  set_log: dict | None = None, notes_by_idx: dict | None = None,
                  garmin_minutes: dict | None = None, garmin_detail: dict | None = None,
                  session_notes: str = "",
                  movement_type_override: str | None = None) -> SessionSave:
    """The Training page's finished session as one SessionSave. The flow's
    state is keyed by exercise index: actuals, set_log, notes_by_idx,
    garmin_minutes and garmin_detail."""
    actuals, set_log = actuals or {}, set_log or {}
    notes_by_idx, garmin_minutes = notes_by_idx or {}, garmin_minutes or {}
    garmin_detail = garmin_detail or {}
    ids = pending["exercise_ids"]
    if len(ids) != len(exercises):
        raise ValueError(f"{len(ids)} exercise ids for {len(exercises)} exercises")
    return SessionSave(
        session_id=pending["session_id"],
        session_date=str(pending["session_date"]),
        duration_minutes=int(pending["duration_minutes"]),
        session_rpe=int(pending["session_rpe"]),
        exercises=tuple(
            exercise_from_flow(
                ex, ids[idx], actual=actuals.get(idx), logged_sets=set_log.get(idx),
                user_note=notes_by_idx.get(idx) or "", garmin_minutes=garmin_minutes.get(idx),
                garmin_detail=garmin_detail.get(idx), movement_type_override=movement_type_override)
            for idx, ex in enumerate(exercises)),
        notes=session_notes or "",
    )


def check(session: SessionSave) -> None:
    """Refuse a save that cannot be stored whole, before anything is written:
    no session id, a date that is not a date, no exercises, an exercise
    without an id, or two exercises with one id (the second would replace
    the first)."""
    if not str(session.session_id or "").strip():
        raise ValueError("the session has no id")
    date.fromisoformat(str(session.session_date))
    if not session.exercises:
        raise ValueError("a session with no exercises stores nothing")
    ids = [str(ex.exercise_id or "").strip() for ex in session.exercises]
    if not all(ids):
        raise ValueError("an exercise has no id")
    if len(set(ids)) != len(ids):
        raise ValueError("two exercises share one id")


def save_session(repo, session: SessionSave) -> list[str]:
    """Store `session` and return the ids of the exercises written, in order.

    Raises SessionSaveError when a write fails partway; the exercises before
    it are stored under their final ids, and sending the same SessionSave
    again stores the rest and leaves the others as they are."""
    check(session)
    exercises = list(session.exercises)
    written: list[str] = []
    for position, ex in enumerate(exercises):
        last = position == len(exercises) - 1
        try:
            repo.save_training_exercise(
                session_id=session.session_id,
                movement_name=ex.name,
                movement_type=ex.movement_type,
                planned_sets=ex.planned_sets,
                planned_reps=ex.planned_reps,
                # None until the heart-rate sync assigns each exercise its own
                # (Repository.reassign_exercise_rpe_from_hr). The session's one
                # rating copied onto every exercise asserted a per-exercise
                # measurement nobody made: a 90-second release and a top set of
                # RDLs both read 8. services/strength.py falls back to the
                # session RPE, which gives the numbers the copy used to write.
                rpe=None,
                sets=list(ex.sets),
                note=with_session_note(ex.note, session.notes) if last else ex.note,
                session_date=session.session_date,
                session_duration_minutes=session.duration_minutes,
                session_rpe=session.session_rpe,
                session_au=session.session_au,
                garmin_avg_hr=ex.garmin_avg_hr,
                garmin_max_hr=ex.garmin_max_hr,
                garmin_distance_km=ex.garmin_distance_km,
                garmin_calories=ex.garmin_calories,
                exercise_id=ex.exercise_id,
            )
        except Exception as exc:
            raise SessionSaveError(len(written), len(exercises), exc) from exc
        written.append(ex.exercise_id)
    return written
