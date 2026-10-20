"""Yoga flows and Garmin outdoor activities, each saved once.

Both are SUPPLEMENTARY sessions (Repository.SUPPLEMENTARY_SESSION_TYPES):
real AU toward strain and ACWR, counted as training days, never a plan day
done. The Training page saved them inline (moves TRN-17 and TRN-18); the
phone's API saves them the same way, so both live here.

WRITTEN ONCE, TWO WAYS. On 2026-10-05 one yoga Complete press wrote 51
sessions and 407 rows in a minute: every run minted its own id, and runs that
stopped partway left partial copies. Now (1) the caller mints the ids, so the
same save sent again rewrites the same rows (rebuild rule 4), and (2) the
day's yoga or outdoor sessions are read back LIVE first (Repository.
get_supplementary_sessions_live), so a second save carrying other ids (a
second browser session, a second phone) continues the first one's session
and writes nothing twice. The caller holds one process-wide lock around each
save (views/training.py's _SUPPLEMENTARY_SAVE_LOCK).
"""

from __future__ import annotations

from datetime import date

from services import session_save
from services import sessions as sess
from services import yoga as yg

#: The movement types these sessions are stored under.
YOGA_TYPE = "Yoga"
OUTDOOR_TYPE = "Outdoor"


# ─── Yoga (move TRN-18) ─────────────────────────────────────────────────────

def save_yoga(repo, flow: yg.YogaSession, day: date, stage: int, session_id: str,
              pose_ids: list[str], note: str = "") -> bool:
    """Store a completed yoga flow; False when it is already fully logged by
    another save. The same save sent again (its session id already holds the
    whole flow) answers True, as it did the first time (rebuild rule 4: the
    phone's outbox sends a save again when the first answer was lost).

    One exercise per pose under one session id, each with the pose's hold as
    its one set and its safety note when the pose is not cleared at `stage`
    (yoga.effective_safety). The flow's estimated RPE is each pose's rating:
    unlike a plan session, nothing measures a pose on its own. The
    whole-session note is joined once to the last pose written.

    An earlier write of this flow today is continued under ITS session id,
    with its written poses skipped."""
    if len(pose_ids) != len(flow.poses):
        raise ValueError(f"{len(pose_ids)} ids for {len(flow.poses)} poses")
    existing_id, written = sess.yoga_save_plan(
        repo.get_supplementary_sessions_live(day, YOGA_TYPE), [p.name for p in flow.poses])
    todo = [(pose, pid) for pose, pid in zip(flow.poses, pose_ids) if pose.name not in written]
    if not todo:
        if existing_id == session_id:
            return True     # this save, sent again: stored, nothing written now
        return False
    sid = existing_id or session_id
    duration = flow.total_duration_minutes
    for position, (pose, pose_id) in enumerate(todo):
        severity, pose_note = yg.effective_safety(pose, stage)
        pose_note = pose_note if severity != "cleared" else ""
        if position == len(todo) - 1:
            pose_note = session_save.with_session_note(pose_note, note)
        repo.save_training_exercise(
            session_id=sid, movement_name=pose.name, movement_type=YOGA_TYPE,
            planned_sets=1, planned_reps=1, rpe=flow.estimated_rpe,
            sets=[{"set_num": 1, "reps": 1, "weight": 0.0, "rest": 10,
                   "tut": pose.hold_seconds, "velocity": "isometric"}],
            note=pose_note, session_date=day.isoformat(),
            session_duration_minutes=duration, session_rpe=flow.estimated_rpe,
            session_au=float(flow.estimated_rpe * duration), exercise_id=pose_id)
    return True


# ─── Garmin outdoor activities (move TRN-17) ────────────────────────────────

def order_activities(rows: list[dict]) -> list[dict]:
    """The day's Garmin activities, the hike/walk/trail-run family first:
    the type is advice, the athlete's pick is the decision, so every activity
    stays pickable."""
    outdoor = [r for r in rows if (r.get("type") or "").lower() in sess.OUTDOOR_EXERCISE_BY_TYPE]
    return outdoor + [r for r in rows if r not in outdoor]


def outdoor_minutes(activity: dict) -> int:
    """The minutes an activity is stored with: whole minutes, at least one.
    The AU preview uses the same number, so it is the AU that is stored."""
    return max(1, int(round(float(activity.get("duration_minutes") or 0))))


def outdoor_au(activity: dict, session_rpe: int) -> float:
    """Foster's load for the activity: RPE x stored minutes."""
    return float(session_rpe * outdoor_minutes(activity))


def outdoor_note(activity: dict) -> str:
    """The stored note. It carries the Garmin activity id, which is how a
    second save of the same activity is recognised
    (sessions.outdoor_activity_logged)."""
    return (f"Garmin import: {activity.get('name') or activity.get('type')} "
            f"[{activity.get('type')}], started {activity.get('start_time_local')}, "
            f"activity {activity.get('activity_id')}")


def _number(value) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def save_outdoor(repo, day: date, activity: dict, session_rpe: int, session_id: str,
                 exercise_id: str) -> bool:
    """Store a Garmin activity as one supplementary session; False when
    another save already put it in the log (the same save sent again, under its
    own session id, answers True as it did the first time). The canonical exercise name
    (sessions.outdoor_exercise_name) carries the movement weight and the
    leg-day classification; AU is RPE x minutes (Key Rule 2b: the activity's
    heart rate is kept as context, never fed into AU)."""
    existing = repo.get_supplementary_sessions_live(day, OUTDOOR_TYPE)
    if sess.outdoor_activity_logged(existing, activity.get("activity_id")):
        if session_id in existing:
            return True     # this save, sent again: stored, nothing written now
        return False
    minutes = outdoor_minutes(activity)
    name = sess.outdoor_exercise_name(activity.get("type"))
    repo.save_training_exercise(
        session_id=session_id, movement_name=name, movement_type=OUTDOOR_TYPE,
        planned_sets=1, planned_reps=1, rpe=session_rpe,
        sets=sess.make_sets_data({"name": name, "type": "duration", "duration_minutes": minutes}),
        note=outdoor_note(activity), session_date=day.isoformat(),
        session_duration_minutes=minutes, session_rpe=session_rpe,
        session_au=outdoor_au(activity, session_rpe),
        garmin_avg_hr=_number(activity.get("avg_hr")),
        garmin_max_hr=_number(activity.get("max_hr")),
        garmin_distance_km=_number(activity.get("distance_km")),
        garmin_calories=_number(activity.get("calories")),
        exercise_id=exercise_id)
    return True
