"""The Training screen (services/training_screen.py, services/
training_session.py).

Reads: the week, one day, today's session (and the accessory session's),
the yoga catalogue, a day's Garmin activities. Writes: the schedule answers
(swap, carry, shift, redo, gate 1), the session save, a yoga flow, an
outdoor activity. Every answer is the services' own; a refusal answers the
one error shape with the rule's own words (409 for a state that refuses,
422 for a request that cannot be taken). A Garmin read runs under the
engine's sync-runner lock (Key Rule 16) and answers 409 sync_running while
a sync holds it.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from services import session_save
from services import training_screen as ts
from services import training_session as tsession
from services.background_sync import BackgroundSyncRunner, SyncBusyError
from services.repository import Repository

from ..deps import get_repository, get_sync_runner, local_today
from ..schemas_training import (ActivityMinutesOut, AnswerIn, CompletionIn, CompletionOut,
                                Gate1ReasonIn, HeartRateIn, HeartRateOut, LoggedOut,
                                OpenActivityOut, OutdoorListOut, OutdoorLogIn, OutdoorLogOut,
                                SessionPlanOut, SessionSaveIn, SessionSaveOut, StoredOut,
                                SwapIn, TrainingDayOut, TrainingWeekOut, YogaCatalogueOut,
                                YogaLogIn)

router = APIRouter()

#: Refusals that are a request the engine cannot take (422); every other
#: refusal is a state that refuses it (409).
_INVALID = {"future_day", "invalid_session", "unknown_kind", "exercise_incomplete",
            "pose_ids", "rpe_out_of_range", "unknown_reason", "unknown_flow"}
#: How long a Garmin read waits for a running sync before answering 409.
GARMIN_WAIT_SECONDS = 30.0


def _refused(exc: ts.ActionRefused | tsession.SessionRefused) -> HTTPException:
    return HTTPException(status_code=422 if exc.code in _INVALID else 409, detail=str(exc))


def _garmin(runner: BackgroundSyncRunner, read):
    try:
        with runner.exclusive(timeout=GARMIN_WAIT_SECONDS):
            return read()
    except SyncBusyError:
        raise HTTPException(status_code=409, detail="sync_running") from None


# ── The week and one day ─────────────────────────────────────────────────────

@router.get("/api/training/week", response_model=TrainingWeekOut)
def get_week(
    week_start: date | None = Query(default=None),
    today: date = Depends(local_today),
    repo: Repository = Depends(get_repository),
) -> dict:
    return ts.week_view(repo, today, week_start)


@router.get("/api/training/day", response_model=TrainingDayOut)
def get_day(
    day: date | None = Query(default=None, alias="date"),
    today: date = Depends(local_today),
    repo: Repository = Depends(get_repository),
) -> dict:
    return ts.day_view(repo, day or today, today)


# ── The schedule answers ─────────────────────────────────────────────────────

def _action(run):
    try:
        return run()
    except ts.ActionRefused as exc:
        raise _refused(exc) from None


@router.post("/api/training/swap", response_model=StoredOut)
def post_swap(body: SwapIn, today: date = Depends(local_today),
              repo: Repository = Depends(get_repository)) -> dict:
    return _action(lambda: ts.swap_with_today(repo, today, body.date))


@router.post("/api/training/carry", response_model=StoredOut)
def post_carry(body: AnswerIn, today: date = Depends(local_today),
               repo: Repository = Depends(get_repository)) -> dict:
    return _action(lambda: ts.apply_carry(repo, today, body.accept))


@router.post("/api/training/shift", response_model=StoredOut)
def post_shift(body: AnswerIn, today: date = Depends(local_today),
               repo: Repository = Depends(get_repository)) -> dict:
    return _action(lambda: ts.apply_shift(repo, today, body.accept))


@router.post("/api/training/redo", response_model=StoredOut)
def post_redo(today: date = Depends(local_today),
              repo: Repository = Depends(get_repository)) -> dict:
    return _action(lambda: ts.redo_week(repo, today))


@router.post("/api/training/gate1/reason", response_model=StoredOut)
def post_gate1_reason(body: Gate1ReasonIn, today: date = Depends(local_today),
                      repo: Repository = Depends(get_repository)) -> dict:
    return _action(lambda: ts.record_gate1_reason(repo, today, body.monday, body.reason))


@router.post("/api/training/gate1/flare", response_model=StoredOut)
def post_gate1_flare(today: date = Depends(local_today),
                     repo: Repository = Depends(get_repository)) -> dict:
    return _action(lambda: ts.record_gate1_flare(repo, today))


# ── Today's session ──────────────────────────────────────────────────────────

def _session(run):
    try:
        return run()
    except tsession.SessionRefused as exc:
        raise _refused(exc) from None


@router.get("/api/training/session", response_model=SessionPlanOut)
def get_session(today: date = Depends(local_today),
                repo: Repository = Depends(get_repository)) -> dict:
    return _session(lambda: tsession.session_plan(repo, today))


@router.get("/api/training/accessory", response_model=SessionPlanOut)
def get_accessory(today: date = Depends(local_today),
                  repo: Repository = Depends(get_repository)) -> dict:
    return _session(lambda: tsession.accessory_plan(repo, today))


@router.post("/api/training/completion", response_model=CompletionOut)
def post_completion(body: CompletionIn) -> dict:
    return _session(lambda: tsession.completion(body.model_minutes, body.start_ts,
                                                body.end_ts, body.rpe, body.kind))


@router.post("/api/training/sessions", response_model=SessionSaveOut)
def post_session(body: SessionSaveIn, today: date = Depends(local_today),
                 repo: Repository = Depends(get_repository)) -> dict:
    try:
        return _session(lambda: tsession.save(repo, body.model_dump(), today))
    except session_save.SessionSaveError as exc:
        # Nothing is lost: the same body sent again stores the rest under the
        # same ids (rebuild rule 4). The cause stays in the log, not the answer.
        raise HTTPException(
            status_code=503,
            detail=f"save_incomplete: {exc.written} of {exc.total} exercises stored; "
                   f"send the same session again") from None


@router.get("/api/training/garmin/open-activity", response_model=OpenActivityOut)
def get_open_activity(today: date = Depends(local_today),
                      repo: Repository = Depends(get_repository),
                      runner: BackgroundSyncRunner = Depends(get_sync_runner)) -> dict:
    return _garmin(runner, lambda: tsession.open_activity(repo, today))


@router.get("/api/training/garmin/activity-minutes", response_model=ActivityMinutesOut)
def get_activity_minutes(planned_minutes: float = Query(gt=0),
                         today: date = Depends(local_today),
                         repo: Repository = Depends(get_repository),
                         runner: BackgroundSyncRunner = Depends(get_sync_runner)) -> dict:
    return _garmin(runner, lambda: tsession.activity_minutes(repo, today, planned_minutes))


@router.post("/api/training/heart-rate", response_model=HeartRateOut)
def post_heart_rate(body: HeartRateIn, today: date = Depends(local_today),
                    repo: Repository = Depends(get_repository),
                    runner: BackgroundSyncRunner = Depends(get_sync_runner)) -> dict:
    if body.date > today:
        raise HTTPException(status_code=422, detail="future_day")
    sets = (tsession.sets_by_name(body.session.model_dump(mode="json")) if body.session
            else body.sets_by_exercise)
    return _garmin(runner, lambda: tsession.heart_rate(
        repo, body.date, sets, body.duration_minutes, body.reported_rpe,
        activity_id=body.activity_id, shift_hours=body.shift_hours))


# ── The "+" menu ─────────────────────────────────────────────────────────────

@router.get("/api/training/yoga", response_model=YogaCatalogueOut)
def get_yoga(repo: Repository = Depends(get_repository)) -> dict:
    return tsession.yoga_catalogue(repo)


@router.post("/api/training/yoga", response_model=LoggedOut)
def post_yoga(body: YogaLogIn, today: date = Depends(local_today),
              repo: Repository = Depends(get_repository)) -> dict:
    return _session(lambda: tsession.log_yoga(repo, today, body.slug, body.session_id,
                                              body.pose_ids, body.note))


@router.get("/api/training/outdoor", response_model=OutdoorListOut)
def get_outdoor(day: date | None = Query(default=None, alias="date"),
                today: date = Depends(local_today),
                repo: Repository = Depends(get_repository),
                runner: BackgroundSyncRunner = Depends(get_sync_runner)) -> dict:
    return _session(lambda: _garmin(
        runner, lambda: tsession.outdoor_activities(repo, day or today, today)))


@router.post("/api/training/outdoor", response_model=OutdoorLogOut)
def post_outdoor(body: OutdoorLogIn, today: date = Depends(local_today),
                 repo: Repository = Depends(get_repository),
                 runner: BackgroundSyncRunner = Depends(get_sync_runner)) -> dict:
    return _session(lambda: _garmin(runner, lambda: tsession.log_outdoor(
        repo, body.date, today, body.activity_id, body.rpe, body.session_id, body.exercise_id)))
