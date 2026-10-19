"""GET /api/status and POST /api/sync (services/engine_sync.py).

The status is what every screen may need to say about the engine itself; the
phone asks for it on each open and calls POST /api/sync when it says a sync
is due. A sync refuses (409 not_the_writer) unless the store names the engine
as the background writer (rebuild rule 2), and runs under the engine's one
sync runner's lock. The clock read here is an instant (when the run was),
never the caller's day, which always comes from X-Local-Date.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException

from services import background_writer, engine_sync
from services.background_sync import BackgroundSyncRunner
from services.repository import Repository

from ..deps import get_repository, get_sync_runner, local_today
from ..schemas import StatusOut, SyncIn, SyncOut

router = APIRouter()


@router.get("/api/status", response_model=StatusOut)
def get_status(
    today: date = Depends(local_today),
    repo: Repository = Depends(get_repository),
) -> dict:
    return engine_sync.app_status(repo, today, datetime.now(timezone.utc))


@router.post("/api/sync", response_model=SyncOut)
def post_sync(
    body: SyncIn = Body(default_factory=SyncIn),
    today: date = Depends(local_today),
    repo: Repository = Depends(get_repository),
    runner: BackgroundSyncRunner = Depends(get_sync_runner),
) -> dict:
    try:
        return engine_sync.run(repo, runner, today, datetime.now(timezone.utc), force=body.force)
    except background_writer.NotTheWriterError:
        raise HTTPException(status_code=409, detail="not_the_writer") from None
