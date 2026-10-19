"""Today's training session for the phone's API (rebuild Phase 2, milestone
5): the session as it runs today, its completion figures, its save, the
Garmin checks and the heart-rate match; and the "+" menu's accessory
session, yoga flows and outdoor activities.

THE PHONE KEEPS THE SESSION, THE ENGINE KEEPS THE RULES. A session lives on
the phone until it is saved (offline at the gym is the normal case), so the
plan is sent whole when the session starts: every exercise as dosed today,
each with its seeded numbers (services/prescription.py) and its captions,
and the guided flow walked in advance (guided_flow.walk), so the phone steps
through a list and holds no step rule of its own. The save is one complete
session with caller-minted ids (services/session_save.py), so the same save
sent three times stores one session (rebuild rule 4).

Garmin reads here are the athlete's own, made on a tap (the watch check
before a save, a walk's minutes, the activity list of a day): each runs
under the engine's sync-runner lock (Key Rule 16), so it never overlaps the
engine's own sync.
"""

from __future__ import annotations

import threading
from datetime import date, datetime, time

from services import accessory as acc
from services import guided_flow, prescription, session_save, strain_regions
from services import sessions as sess
from services import supplementary_save
from services import training_screen as ts
from services import yoga as yg


class SessionRefused(ValueError):
    """A session request that cannot be answered: `code` names why."""

    def __init__(self, code: str, details: list[str] | None = None):
        super().__init__(code if not details else f"{code}: {'; '.join(details)}")
        self.code = code
        self.details = list(details or [])


#: One supplementary save at a time in this process (the Training page's
#: _SUPPLEMENTARY_SAVE_LOCK): with the live read-back in supplementary_save,
#: a second request continues the first one's session instead of starting
#: another.
SUPPLEMENTARY_SAVE_LOCK = threading.Lock()

#: The kinds of session the save takes: the plan day, and the accessory
#: session (the "+" button), stored under its own Type so it never marks a
#: plan day done (Repository.SUPPLEMENTARY_SESSION_TYPES).
PLAN, ACCESSORY = "plan", "accessory"


def _try(read, default):
    try:
        return read()
    except Exception:
        return default


# ─── The session as it runs today ────────────────────────────────────────────

def _warning_strains(repo, today: date) -> tuple[dict | None, dict | None]:
    """(today's, yesterday's) per-region strain for the warning gate
    (strain_regions.warning_strains); (None, None), the gate's fail-open
    signal, when the read fails."""
    try:
        rows = repo.get_daily_region_au(days=31, today=today)["rows"]
        stage = int(repo.get_current_stage())
    except Exception:
        return None, None
    return strain_regions.warning_strains(rows, stage, today)


def timer_kind(ex: dict) -> str | None:
    """Which timer an exercise runs: "stopwatch" for a timed test (it counts
    up and asks for the seconds), "hold" for a held exercise, "duration" for
    an activity, None for reps."""
    if sess.is_timed_test(ex):
        return "stopwatch"
    if ex.get("type") in sess.HOLD_TIMER_TYPES:
        return "hold"
    if ex.get("type") == "duration":
        return "duration"
    return None


#: The exercise fields the phone reads to draw and step an exercise. The
#: reasoning fields are never sent (Key Rule 20).
EXERCISE_FIELDS = ("name", "type", "laterality", "sets", "reps", "reps_in_set", "hold_seconds",
                   "duration_minutes", "rest_seconds", "tempo", "rep_min", "rep_max",
                   "equipment_type", "increment_size", "increment_unit", "weight_kg",
                   "band_tier")


def exercise_out(ex: dict, index: int, seed, lift_index: int | None, strains: tuple,
                 garmin_ok: bool) -> dict:
    """One exercise as the guided flow shows it today: its fields, the
    prescription with the seeded numbers in it (sessions.displayed_
    prescription), the how-to, the safety warning only when its own body
    area is over the strain threshold (Key Rule 20), its timer, the lift a
    ramp set prepares, the stepper's starting values, the previous session
    and the difference, where today's numbers came from, a contradiction the
    resolution reported, and whether a walk or run pulls its minutes from
    the watch."""
    entry = seed.entry if seed is not None else None
    previous = seed.previous if seed is not None else None
    warning = ""
    if ex.get("warning") and strain_regions.warning_is_due(ex["name"], *strains)["due"]:
        warning = ex["warning"]
    pulls = bool(garmin_ok and ex.get("type") == "duration" and sess.is_run_or_walk(ex))
    minutes = ex.get("duration_minutes") or 0
    return {
        "index": index,
        **{k: ex.get(k) for k in EXERCISE_FIELDS},
        "icon": sess.type_icon(ex),
        "warmup": bool(ex.get("warmup")),
        "timed_test": sess.is_timed_test(ex),
        "timer": timer_kind(ex),
        "prescription": sess.prescription_label(sess.displayed_prescription(ex, entry)),
        "mechanics": ex.get("mechanics") or "",
        "warning": warning,
        "ramp_for": lift_index,
        "reps_editable": sess.reps_are_editable(ex),
        "entry": entry,
        "previous": previous,
        "previous_caption": sess.previous_caption(previous) if previous is not None else "",
        "delta": sess.prescription_delta(entry, previous) if previous is not None else "",
        "delta_direction": sess.delta_direction(entry, previous) if previous is not None else "",
        "entry_caption": sess.actual_caption(entry) if entry else "",
        "contradiction": seed.contradiction if seed is not None else None,
        "garmin_pull": pulls,
        "garmin_window": ([max(0, minutes - sess.GARMIN_ACTIVITY_BUFFER_MINUTES),
                           minutes + sess.GARMIN_ACTIVITY_BUFFER_MINUTES] if pulls else None),
        # The save screen's review shows this when the watch verified no time
        # (sessions.review_figures' estimate, fault F20).
        "estimated_minutes": max(1, round(sess.exercise_duration_seconds(ex) / 60)),
    }


def compose(repo, today: date, *, kind: str, day_num: int | None, content: dict,
            decided: dict) -> dict:
    """A session as it runs today, from a plan day's content (or the
    accessory session's, accessory.build_day): every exercise dosed by the
    one load decision (sessions.dosed_day), each seeded in order, a ramp set
    after the lift it prepares; the walk; the modelled minutes and the
    clock's floor; the first side; the banner and the adaptation."""
    policy, modifier = decided["policy"], decided["modifier"]
    plan_ex = content["exercises"]
    dosed = sess.dosed_day(plan_ex, policy["volume_factor"], content.get("day_type"))
    first = sess.first_side(today)
    strains = _warning_strains(repo, today)
    garmin_ok = bool(_try(repo.garmin_configured, False))
    seeds: dict[int, object] = {}

    def seed_for(i: int):
        if i not in seeds:
            lift = sess.ramp_lift_index(plan_ex, i)
            lift_entry = None
            if lift is not None:
                lift_seed = seed_for(lift)
                lift_entry = lift_seed.entry if lift_seed is not None else None
            seeds[i] = prescription.seed_exercise(
                repo, dosed[i], streak_label=modifier.get("streak_label", "unknown"),
                policy=policy, today=today, lift_entry=lift_entry)
        return seeds[i]

    exercises = [exercise_out(ex, i, seed_for(i), sess.ramp_lift_index(plan_ex, i), strains,
                              garmin_ok)
                 for i, ex in enumerate(dosed)]
    return {
        "kind": kind,
        "date": today,
        "day_num": day_num,
        "objective": content.get("objective") or "",
        "phase": content.get("phase") or "",
        "rpe_target": content.get("session_rpe_target"),
        "first_side": first,
        "banner": ts.verdict_banner(decided["verdict"], decided["directive"]),
        "adaptation": ts.adaptation(policy),
        "exercises": exercises,
        "steps": guided_flow.walk(dosed, first),
        "model_minutes": sess.estimate_duration(dosed),
        "min_minutes": sess.MIN_ACCESSORY_MINUTES if kind == ACCESSORY else sess.MIN_SESSION_MINUTES,
        "rest_taken_max_seconds": guided_flow.REST_TAKEN_MAX_SECONDS,
        "garmin_configured": garmin_ok,
        "band_tiers": [{"tier": t, "label": sess.BAND_TIER_LABELS.get(t, "")}
                       for t in sess.BAND_TIERS],
        "reasons": list(content.get("accessory_reasons") or ()),
    }


def session_plan(repo, today: date) -> dict:
    """Today's plan session, or SessionRefused: no readable phases, no block
    today, a rest day, before the block's first day or after its last, or
    today's plan session already logged (the "already logged" lock, T80: a
    logged plan day can never start again)."""
    r = ts.read(repo, today)
    if r.phases_error:
        raise SessionRefused("phases_unreadable", [r.phases_error])
    if r.active is None:
        raise SessionRefused("no_active_block")
    if sess.today_is_rest(r.active, today):
        raise SessionRefused("rest_day")
    screen = sess.today_screen(r.day_num, len(r.plan), False, False)
    if screen != "overview":
        raise SessionRefused(screen)
    if sess.logged_today(repo, today):
        raise SessionRefused("already_logged")
    decided = ts.todays_decision(repo, r.phases, today)
    out = compose(repo, today, kind=PLAN, day_num=r.day_num, content=r.plan[r.day_num],
                  decided=decided)
    following = r.plan.get(r.day_num + 1)
    out["next_day"] = (None if not following else {
        "day_num": r.day_num + 1, "objective": following["objective"],
        "exercises": [ts.exercise_line(ex) for ex in following.get("exercises", [])]})
    return out


def accessory_plan(repo, today: date) -> dict:
    """The accessory session for today (the "+" button), chosen from today's
    projected and yesterday's measured regional strain
    (accessory.read_choice), as a session the same guided flow runs."""
    r = ts.read(repo, today)
    decided = ts.todays_decision(repo, r.phases, today)
    choice = acc.read_choice(repo, r.active, r.day_num, decided["directive"], today)
    day = acc.build_day(choice)
    out = compose(repo, today, kind=ACCESSORY, day_num=None, content=day, decided=decided)
    out["next_day"] = None
    out["note"] = day.get("accessory_note") or ""
    return out


# ─── Completion ──────────────────────────────────────────────────────────────

def completion(model_minutes: int, start_ts: float, end_ts: float, rpe: int,
               kind: str = PLAN) -> dict:
    """The save screen's figures (the completion rules, fault F16): the
    clock's minutes (at least the floor), whether the clock ran so far past
    the plan that the athlete chooses the length to save
    (sessions.duration_needs_a_check), and the session load for each
    choice. The clock readings are the phone's own."""
    floor = sess.MIN_ACCESSORY_MINUTES if kind == ACCESSORY else sess.MIN_SESSION_MINUTES
    clock = (max(floor, int((end_ts - start_ts) / 60)) if start_ts and start_ts > 0
             else int(model_minutes))
    ask = kind == PLAN and sess.duration_needs_a_check(clock, model_minutes)
    choices = ([{"minutes": int(model_minutes), "source": "plan"},
                {"minutes": clock, "source": "clock"}] if ask
               else [{"minutes": clock, "source": "clock"}])
    return {"clock_minutes": clock, "model_minutes": int(model_minutes), "ask_length": ask,
            "choices": [{**c, "au": sess.session_au(rpe, c["minutes"]),
                         "au_by_rpe": au_by_rpe(c["minutes"])} for c in choices]}


def au_by_rpe(minutes: int | float) -> list[float]:
    """The session load at every rating from 1 to 10, so a rating slider
    shows its load without a request and without the rule."""
    return [sess.session_au(rpe, minutes) for rpe in range(1, 11)]


# ─── The save ────────────────────────────────────────────────────────────────

def build_save(body: dict) -> session_save.SessionSave:
    """One SessionSave from the phone's complete session. The phone minted
    every id once, before the first send. Each exercise carries the
    fields the session plan gave it, its stepper's final values (`actual`),
    its recorded sets, its note and its Garmin minutes. A plan exercise is
    stored under its own movement type; the accessory session's under its
    Type (accessory.ACCESSORY_TYPE)."""
    kind = body.get("kind", PLAN)
    if kind not in (PLAN, ACCESSORY):
        raise SessionRefused("unknown_kind", [str(kind)])
    exercises = body.get("exercises") or []
    pending = {"session_id": body["session_id"], "session_date": str(body["date"]),
               "duration_minutes": int(body["duration_minutes"]),
               "session_rpe": int(body["session_rpe"]),
               "exercise_ids": [e["exercise_id"] for e in exercises]}
    flow_ex = [{k: v for k, v in (e.get("exercise") or {}).items()} for e in exercises]
    for ex in flow_ex:
        if not ex.get("name") or not ex.get("type"):
            raise SessionRefused("exercise_incomplete", ["every exercise needs a name and a type"])
    return session_save.build_session(
        pending, flow_ex,
        actuals={i: e.get("actual") for i, e in enumerate(exercises) if e.get("actual")},
        set_log={i: list(e.get("sets") or []) for i, e in enumerate(exercises) if e.get("sets")},
        notes_by_idx={i: e.get("note") or "" for i, e in enumerate(exercises)},
        garmin_minutes={i: e["garmin_minutes"] for i, e in enumerate(exercises)
                        if e.get("garmin_minutes")},
        garmin_detail={i: e["garmin_detail"] for i, e in enumerate(exercises)
                       if e.get("garmin_detail")},
        session_notes=body.get("notes") or "",
        movement_type_override=acc.ACCESSORY_TYPE if kind == ACCESSORY else None)


def save(repo, body: dict, today: date) -> dict:
    """Store a complete session: idempotent on the caller's ids (the same
    body sent again rewrites the same rows), refused for a day after the
    caller's day. A write that fails partway raises
    session_save.SessionSaveError with how many exercises are stored; the
    same body sent again completes it."""
    if date.fromisoformat(str(body["date"])) > today:
        raise SessionRefused("future_day")
    session = build_save(body)
    try:
        session_save.check(session)
    except ValueError as exc:
        raise SessionRefused("invalid_session", [str(exc)]) from None
    written = session_save.save_session(repo, session)
    from services import processing_queue
    processing_queue.parse_after_save(repo)     # the session notes: parse on save (I63)
    return {"stored": True, "session_id": session.session_id, "exercise_ids": written,
            "duration_minutes": session.duration_minutes, "session_rpe": session.session_rpe,
            "au": session.session_au}


# ─── Garmin, on a tap ────────────────────────────────────────────────────────

def open_activity(repo, today: date) -> dict:
    """The watch check before a save (T91): today's longest Garmin activity
    when one is saved on Garmin, else None ("stop your watch, then check
    again": an activity in progress is not on Garmin yet)."""
    found = repo.find_open_garmin_activity(today.isoformat())
    return {"found": found is not None,
            "activity": None if not found else {
                "activity_id": str(found.get("activity_id") or ""),
                "name": found.get("name") or "", "type": found.get("type") or "",
                "duration_minutes": found.get("duration_minutes")}}


def activity_minutes(repo, today: date, planned_minutes: float) -> dict:
    """A walk's or run's minutes from the watch (T75): today's most recent
    activity lasting the planned minutes give or take the buffer, with the
    detail the save stores beside it; 0 minutes when none matches."""
    now = datetime.combine(today, time(23, 59))   # the caller's day, never the server's
    minutes, matched = repo.get_recent_garmin_activity_minutes(
        planned_minutes, sess.GARMIN_ACTIVITY_BUFFER_MINUTES, now=now)
    return {"minutes": minutes,
            "detail": sess.summarize_garmin_activities(matched) if minutes > 0 else None,
            "window": [max(0, planned_minutes - sess.GARMIN_ACTIVITY_BUFFER_MINUTES),
                       planned_minutes + sess.GARMIN_ACTIVITY_BUFFER_MINUTES]}


def _candidate(c: dict) -> dict:
    a = c.get("activity") or {}
    return {"activity_id": str(a.get("activity_id") or ""), "name": a.get("name") or "",
            "type": a.get("type") or "", "start_time_local": str(a.get("start_time_local") or ""),
            "duration_minutes": a.get("duration_minutes"),
            "shift_hours": c.get("shift_hours") or 0, "quality": c.get("quality")}


def heart_rate(repo, session_date: date, sets_by_exercise: dict, duration_minutes: float,
               reported_rpe: int | None, *, activity_id: str | None = None,
               shift_hours: float = 0.0) -> dict:
    """The heart-rate match after a save (T97-T101): the measured figures
    against the athlete's own rating (sessions.hr_comparison), or the day's
    activities to choose from when none lines up with the session's clock
    (the travel case), or no match. Display only: the stored load stays the
    athlete's rating (Key Rule 2b), and the background sync stores the
    session's heart rate on its own."""
    hr = repo.compute_session_hr(session_date, sets_by_exercise,
                                 duration_minutes=duration_minutes,
                                 force_activity_id=activity_id, shift_hours=shift_hours)
    reported_au = (sess.session_au(reported_rpe, duration_minutes)
                   if reported_rpe is not None else None)
    if hr and hr.get("needs_choice"):
        return {"state": "choose", "reason": hr.get("reason") or "",
                "candidates": [_candidate(c) for c in hr.get("candidates") or []],
                "comparison": None}
    comparison = sess.hr_comparison(hr, reported_rpe, reported_au)
    if comparison is None:
        return {"state": "no_match", "reason": (hr or {}).get("reason") or "",
                "candidates": [], "comparison": None}
    return {"state": "matched", "reason": "", "candidates": [], "comparison": comparison}


# ─── The "+" menu: yoga and outdoor ─────────────────────────────────────────

def _stage(repo) -> tuple[int, bool]:
    """The stage a pose's safety is judged at, and whether it was read: the
    strictest one when it was not (fault F23), and the screen says so."""
    try:
        return int(repo.get_current_stage()), True
    except Exception:
        return yg.STAGE_WHEN_UNKNOWN, False


def yoga_catalogue(repo) -> dict:
    """Every yoga flow with its safety notes at the stored stage
    (YogaSession.cautions: advisory, nothing here blocks a flow)."""
    stage, read_ok = _stage(repo)
    return {
        "stage_read": read_ok,
        "flows": [{"slug": s.slug, "name": s.name, "minutes": s.total_duration_minutes,
                   "rpe": s.estimated_rpe, "video_url": s.video_url,
                   "poses": [{"name": p.name} for p in s.poses],
                   "cautions": [{"pose": pose.name, "severity": severity, "note": note}
                                for pose, severity, note in s.cautions(stage)]}
                  for s in yg.YOGA_LIBRARY],
    }


def log_yoga(repo, today: date, slug: str, session_id: str, pose_ids: list[str],
             note: str = "") -> dict:
    """Store a completed yoga flow for the caller's day
    (supplementary_save.save_yoga): written once whatever is sent again;
    `logged` is False when the flow was already fully logged today."""
    flow = yg.get(slug)
    if flow is None:
        raise SessionRefused("unknown_flow", [slug])
    if len(pose_ids) != len(flow.poses):
        raise SessionRefused("pose_ids", [f"{len(flow.poses)} poses need {len(flow.poses)} ids"])
    stage, _read_ok = _stage(repo)
    with SUPPLEMENTARY_SAVE_LOCK:
        logged = supplementary_save.save_yoga(repo, flow, today, stage, session_id, pose_ids,
                                              note)
    return {"logged": bool(logged)}


def outdoor_activities(repo, day: date, today: date) -> dict:
    """A day's Garmin activities for the outdoor import (T111): the hike,
    walk and trail-run family first (supplementary_save.order_activities),
    each with the name it logs under and its minutes."""
    if day > today:
        raise SessionRefused("future_day")
    rows = supplementary_save.order_activities(repo.get_garmin_activities_for_date(day))
    return {"date": day, "activities": [{
        "activity_id": str(a.get("activity_id") or ""), "name": a.get("name") or "",
        "type": a.get("type") or "", "duration_minutes": a.get("duration_minutes"),
        "distance_km": a.get("distance_km"), "avg_hr": a.get("avg_hr"),
        "logs_as": sess.outdoor_exercise_name(a.get("type")),
        "in_family": (a.get("type") or "").lower() in sess.OUTDOOR_EXERCISE_BY_TYPE,
        "minutes": supplementary_save.outdoor_minutes(a),
        "au_by_rpe": au_by_rpe(supplementary_save.outdoor_minutes(a))} for a in rows]}


def log_outdoor(repo, day: date, today: date, activity_id: str, rpe: int, session_id: str,
                exercise_id: str) -> dict:
    """Store one Garmin activity of `day` as an outdoor session
    (supplementary_save.save_outdoor): read again from Garmin by its id,
    written once (the activity id is the duplicate key)."""
    if day > today:
        raise SessionRefused("future_day")
    if not 1 <= int(rpe) <= 10:
        raise SessionRefused("rpe_out_of_range")
    act = next((a for a in repo.get_garmin_activities_for_date(day)
                if str(a.get("activity_id")) == str(activity_id)), None)
    if act is None:
        raise SessionRefused("unknown_activity", [str(activity_id)])
    with SUPPLEMENTARY_SAVE_LOCK:
        logged = supplementary_save.save_outdoor(repo, day, act, int(rpe), session_id,
                                                 exercise_id)
    return {"logged": bool(logged), "au": supplementary_save.outdoor_au(act, int(rpe)),
            "logs_as": sess.outdoor_exercise_name(act.get("type"))}
