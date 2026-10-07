"""Process-wide engine state: the Config, the cache rebuild and its timings.

The local SQLite read cache is rebuilt from Supabase ONCE per container start,
before anything reads it (services/datastore.py:ensure_local_cache). Order
matters: sqlite3.connect creates an empty file, and a connection opened before
the rebuild would stay on that empty file.

A Repository is never shared between threads (Key Rule 12, rebuild rule 6):
FastAPI runs plain `def` routes on a thread pool, so every request gets its own
Repository from new_repository(). Building one is cheap; its clients are lazy.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from services import datastore
from services.config import Config
from services.repository import Repository

from . import settings

log = logging.getLogger("healthapi")


@dataclass
class EngineState:
    config: Config | None = None
    started_at: datetime | None = None
    cache_rebuilt: bool | None = None
    timings: dict[str, float] = field(default_factory=dict)


STATE = EngineState()


def startup(import_seconds: float | None = None) -> None:
    """Config, then the cache rebuild. Logs timings only, never a value."""
    STATE.started_at = datetime.now(timezone.utc)
    if import_seconds is not None:
        STATE.timings["imports_s"] = round(import_seconds, 3)
    t0 = time.perf_counter()
    STATE.config = settings.build_config()
    t1 = time.perf_counter()
    filled = datastore.ensure_local_cache(STATE.config)
    t2 = time.perf_counter()
    STATE.cache_rebuilt = filled is not None
    STATE.timings["config_s"] = round(t1 - t0, 3)
    STATE.timings["cache_rebuild_s"] = round(t2 - t1, 3)
    log.info("startup timings %s (cache rebuilt: %s)", STATE.timings, STATE.cache_rebuilt)


def new_repository() -> Repository:
    if STATE.config is None:
        raise RuntimeError("engine not started")
    return Repository(STATE.config)


def cache_info() -> dict:
    mode = os.environ.get("HEALTH_DATASTORE_MODE", "readonly")
    raw = os.environ.get("HEALTH_DATASTORE_PATH", "")
    if not raw:
        return {"mode": mode, "exists": False, "age_s": None}
    path = Path(raw)
    if not path.exists():
        return {"mode": mode, "exists": False, "age_s": None}
    return {"mode": mode, "exists": True, "age_s": round(time.time() - path.stat().st_mtime, 1)}
