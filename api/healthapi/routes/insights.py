"""The Insights screens, the Sync tab's data and actions, the Oura login and
Settings (services/insights_screens.py, services/flexibility_screen.py,
services/engine_actions.py).

Every answer is the services' own. A device sync and the Oura login refuse
(409 not_the_writer) unless the store names the engine as the background
writer (rebuild rule 2); a manual sync waits for the sync runner's lock and
answers 409 sync_running when it stays held. A refusal names its reason in
the one error shape.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from services import background_writer, data_check, engine_actions, load_warnings
from services import flexibility_screen as fxs
from services import insights_screens as ins
from services.background_sync import BackgroundSyncRunner, SyncBusyError
from services.clients import oura
from services.repository import Repository

from ..deps import get_repository, get_sync_runner, local_today
from ..schemas_insights import (CaptureStartIn, CaptureStepIn, ClearedOut, DataCheckOut,
                                DataTableOut, EngineDataOut, FlexCapture, FlexibilityOut,
                                ManualSyncOut, MetabolismOut, MissingIn, OuraCallbackIn, OuraLoginIn,
                                OuraLoginOut, OuraLoginStatus, PlanStartIn, ProcessOut,
                                QueueOut, SessionChecksOut, SettingsOut, SleepArchitectureOut,
                                StrengthOut, TrendsOut, WarningsOut)

router = APIRouter()

#: Refusals of a request the engine cannot take (422); every other refusal is
#: a state that refuses it (409).
_INVALID = {"unknown_test", "unknown_side", "unknown_sync", "redirect_not_https",
            "nothing_entered"}


def _refused(code: str, message: str | None = None) -> HTTPException:
    return HTTPException(status_code=422 if code in _INVALID else 409, detail=message or code)


# ── Strength and Metabolism ──────────────────────────────────────────────────

@router.get("/api/insights/strength", response_model=StrengthOut)
def get_strength(metric: str = Query(default=ins.DEFAULT_STRENGTH_METRIC),
                 today: date = Depends(local_today),
                 repo: Repository = Depends(get_repository)) -> dict:
    try:
        return ins.strength(repo, today, metric)
    except ins.ReferenceMissing:
        # The personal 2025 reference is not in the store yet:
        # scripts/upload_strength_reference.py writes it.
        raise _refused("strength_reference_missing") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid_request: {exc}") from None


@router.get("/api/insights/metabolism", response_model=MetabolismOut)
def get_metabolism(metric: str = Query(default="Weight"), kind: str = Query(default="all"),
                   offset: int = Query(default=0, le=0),
                   today: date = Depends(local_today),
                   repo: Repository = Depends(get_repository)) -> dict:
    try:
        return ins.metabolism(repo, today, metric, kind, offset)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid_request: {exc}") from None


# ── Flexibility ──────────────────────────────────────────────────────────────

def _capture(run):
    try:
        return run()
    except fxs.CaptureRefused as exc:
        raise _refused(exc.code, str(exc)) from None


@router.get("/api/insights/flexibility", response_model=FlexibilityOut)
def get_flexibility(today: date = Depends(local_today),
                    repo: Repository = Depends(get_repository)) -> dict:
    return fxs.screen(repo, today)


@router.post("/api/insights/flexibility/capture", response_model=FlexCapture)
def post_capture(body: CaptureStartIn, today: date = Depends(local_today),
                 repo: Repository = Depends(get_repository)) -> dict:
    return fxs.start_capture(repo, today, body.cold)


@router.put("/api/insights/flexibility/capture", response_model=FlexCapture)
def put_capture(body: CaptureStepIn, today: date = Depends(local_today),
                repo: Repository = Depends(get_repository)) -> dict:
    return _capture(lambda: fxs.record_step(repo, today, body.test_key, body.entered,
                                            load=body.load, setup_value=body.setup_value,
                                            void=body.void))


@router.delete("/api/insights/flexibility/capture", response_model=ClearedOut)
def delete_capture(repo: Repository = Depends(get_repository)) -> dict:
    fxs.cancel_capture(repo)
    return {"cleared": True}


@router.post("/api/insights/flexibility/capture/finish", response_model=FlexibilityOut)
def post_capture_finish(today: date = Depends(local_today),
                        repo: Repository = Depends(get_repository)) -> dict:
    return _capture(lambda: fxs.finish_capture(repo, today))


@router.post("/api/insights/flexibility/missing", response_model=FlexibilityOut)
def post_missing(body: MissingIn, today: date = Depends(local_today),
                 repo: Repository = Depends(get_repository)) -> dict:
    return _capture(lambda: fxs.add_missing(repo, today,
                                            [e.model_dump() for e in body.entries]))


# ── Engine Data, the queue, trends and sleep architecture ────────────────────

@router.get("/api/insights/engine", response_model=EngineDataOut)
def get_engine(today: date = Depends(local_today),
               repo: Repository = Depends(get_repository)) -> dict:
    return ins.engine_data(repo, today)


@router.get("/api/insights/queue", response_model=QueueOut)
def get_queue(year: int | None = Query(default=None, ge=2000, le=2100),
              month: int | None = Query(default=None, ge=1, le=12),
              today: date = Depends(local_today),
              repo: Repository = Depends(get_repository)) -> dict:
    return ins.queue(repo, today, year, month)


@router.post("/api/insights/queue/process", response_model=ProcessOut)
def post_queue_process(repo: Repository = Depends(get_repository)) -> dict:
    return ins.process_queue(repo)


@router.get("/api/insights/warnings", response_model=WarningsOut)
def get_warnings(year: int | None = Query(default=None, ge=2000, le=2100),
                 month: int | None = Query(default=None, ge=1, le=12),
                 today: date = Depends(local_today),
                 repo: Repository = Depends(get_repository)) -> dict:
    """The days the app told him to lower the load, one month at a time
    (services/load_warnings.py; the owner, 2026-10-21)."""
    return load_warnings.calendar(repo, today, year, month)


@router.get("/api/insights/trends", response_model=TrendsOut)
def get_trends(today: date = Depends(local_today),
               repo: Repository = Depends(get_repository)) -> dict:
    return ins.trends(repo, today)


@router.get("/api/insights/sleep-architecture", response_model=SleepArchitectureOut)
def get_sleep_architecture(night: str | None = Query(default=None),
                           today: date = Depends(local_today),
                           repo: Repository = Depends(get_repository)) -> dict:
    return ins.sleep_architecture_view(repo, today, night)


# ── The Sync tab's data and actions ──────────────────────────────────────────

@router.get("/api/data/session-checks", response_model=SessionChecksOut)
def get_session_checks(today: date = Depends(local_today),
                       repo: Repository = Depends(get_repository)) -> dict:
    return ins.session_checks(repo, today)


@router.get("/api/data/check", response_model=DataCheckOut)
def get_data_check(repo: Repository = Depends(get_repository)) -> dict:
    """The daily data check: the rows of the newest backup the store no longer
    holds. Reads only; the Worker's daily trigger and Settings' "Check now"
    call it. Ages are in hours, so it needs no caller day."""
    try:
        return repo.data_check(datetime.now(timezone.utc))
    except data_check.DataCheckFailed:
        raise HTTPException(status_code=503, detail="store_unavailable") from None


@router.get("/api/data/tables/{table}", response_model=DataTableOut)
def get_table(table: str, start: date | None = Query(default=None),
              end: date | None = Query(default=None),
              today: date = Depends(local_today),
              repo: Repository = Depends(get_repository)) -> dict:
    try:
        return ins.data_table(repo, today, table, start, end)
    except ValueError:
        raise HTTPException(status_code=404, detail="unknown_table") from None


@router.post("/api/data/sync/{kind}", response_model=ManualSyncOut)
def post_manual_sync(kind: str, today: date = Depends(local_today),
                     repo: Repository = Depends(get_repository),
                     runner: BackgroundSyncRunner = Depends(get_sync_runner)) -> dict:
    try:
        return engine_actions.manual_sync(repo, runner, kind, today)
    except engine_actions.ActionRefused as exc:
        raise _refused(exc.code) from None
    except background_writer.NotTheWriterError:
        raise _refused("not_the_writer") from None
    except SyncBusyError:
        raise _refused("sync_running") from None


# ── The Oura login and Settings ──────────────────────────────────────────────

@router.post("/api/oura/login", response_model=OuraLoginOut)
def post_oura_login(body: OuraLoginIn, today: date = Depends(local_today),
                    repo: Repository = Depends(get_repository)) -> dict:
    try:
        return engine_actions.start_oura_login(repo, body.redirect_uri, today)
    except engine_actions.ActionRefused as exc:
        raise _refused(exc.code) from None
    except background_writer.NotTheWriterError:
        raise _refused("not_the_writer") from None


@router.post("/api/oura/callback", response_model=OuraLoginStatus)
def post_oura_callback(body: OuraCallbackIn,
                       x_local_date: str | None = Header(default=None),
                       repo: Repository = Depends(get_repository)) -> dict:
    # The Worker's return page (GET /oura/callback) calls this with no phone date: the day
    # is the one the phone sent when the login started (engine_actions.finish_oura_login).
    try:
        fallback = date.fromisoformat(x_local_date) if x_local_date else None
    except ValueError:
        raise HTTPException(status_code=400, detail="x_local_date_invalid") from None
    try:
        return engine_actions.finish_oura_login(repo, body.code, body.state, fallback)
    except engine_actions.ActionRefused as exc:
        raise _refused(exc.code) from None
    except background_writer.NotTheWriterError:
        raise _refused("not_the_writer") from None
    except oura.OuraAuthError:
        # Oura's own words can carry request detail; the answer stays generic.
        raise _refused("oura_refused_the_code") from None


@router.get("/api/settings", response_model=SettingsOut)
def get_settings(repo: Repository = Depends(get_repository)) -> dict:
    return engine_actions.settings(repo)


@router.put("/api/settings/plan-start", response_model=SettingsOut)
def put_plan_start(body: PlanStartIn, today: date = Depends(local_today),
                   repo: Repository = Depends(get_repository)) -> dict:
    try:
        return engine_actions.set_plan_start(repo, body.start_date, today)
    except engine_actions.ActionRefused as exc:
        raise _refused(exc.code) from None
