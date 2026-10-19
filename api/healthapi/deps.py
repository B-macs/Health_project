"""The dependencies every route shares.

One Repository per request (Key Rule 12, rebuild rule 6): FastAPI runs plain
`def` routes on a thread pool, and nothing in a Repository is thread-safe.
Tests override `get_repository` once for every route.

The caller's day comes from X-Local-Date (rebuild rule 3, dates.py); a route
whose answer depends on "today" takes `local_today` and never reads the
server's clock.
"""

from __future__ import annotations

from datetime import date

from fastapi import Depends

from services.background_sync import BackgroundSyncRunner
from services.repository import Repository

from . import engine
from .dates import caller_local_date


def get_repository() -> Repository:
    return engine.new_repository()


def get_sync_runner() -> BackgroundSyncRunner:
    """The engine's one sync runner (engine.sync_runner); tests override it."""
    return engine.sync_runner()


def local_today(day: date = Depends(caller_local_date)) -> date:
    return day
