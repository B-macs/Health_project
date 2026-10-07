"""GET /api/health: the engine's own diagnostics. No personal reading."""

from __future__ import annotations

import os
import platform
import time
from datetime import date

from fastapi import APIRouter

from .. import __version__, engine
from ..schemas import BuildInfo, CacheInfo, HealthOut

router = APIRouter()


@router.get("/api/health", response_model=HealthOut)
def health() -> HealthOut:
    started = engine.STATE.started_at
    return HealthOut(
        status="ok",
        build=BuildInfo(version=__version__,
                        commit=os.environ.get("HEALTH_BUILD_COMMIT") or None,
                        built=os.environ.get("HEALTH_BUILD_TIME") or None),
        python=platform.python_version(),
        server_tz=os.environ.get("TZ") or time.tzname[0],
        # The server's own idea of today, shown so a missing TZ is visible.
        # No route uses it as the caller's day (rebuild rule 3).
        server_local_date=date.today(),
        started_at=started.isoformat(timespec="seconds") if started else None,
        cache_rebuilt=engine.STATE.cache_rebuilt,
        cache=CacheInfo(**engine.cache_info()),
        timings=dict(engine.STATE.timings),
    )
