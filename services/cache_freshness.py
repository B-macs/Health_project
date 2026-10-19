"""When a process pulls its local copy of the store again (rebuild Phase 2,
milestone 5, 2026-10-19).

TWO PROCESSES, TWO COPIES. Until the switch-over the Streamlit app and the
engine both read from a local SQLite copy of Supabase (reads from Postgres
cost ~136 ms a round trip; the copy, ~30 ms for everything). Each copy holds
every row its own process wrote (Supabase first, then the copy) but none of
the other process's since its last pull. So a copy pulled longer ago than
MAX_AGE_MINUTES (a setting, HEALTH_CACHE_MAX_AGE_MINUTES) is pulled again:
by the engine before it answers a request, by the Streamlit app at an open.

UNDER THE SYNC RUNNER'S LOCK, as every sync step is: a pull while a sync
runs would copy half of that sync's writes. The engine waits for a running
sync (up to the caller's limit); the Streamlit app never waits (its page
must not block on a device sync) and tries again at the next open.

NEVER A LOST ROW: record_cache.refresh holds the copy's one write lock for
the whole pull, so a row this process writes meanwhile lands in the new copy
(see record_cache.WRITE_LOCK). NEVER A BROKEN REQUEST: a pull that fails
leaves the copy as it was, is logged without a value, and is tried again
only after RETRY_AFTER_SECONDS, so a store that is down is not asked again
on every request.
"""

from __future__ import annotations

import logging
import os
import time

from services import record_cache
from services.background_sync import SyncBusyError

log = logging.getLogger(__name__)

#: A copy pulled longer ago than this is pulled again.
MAX_AGE_MINUTES = 15.0
#: After a failed pull, the next try waits this long.
RETRY_AFTER_SECONDS = 60.0

#: What refresh_if_stale did.
NOT_RECORD = "not_record"   # no local copy of Supabase in this process
FRESH = "fresh"             # pulled recently enough
REFRESHED = "refreshed"     # pulled again now
BUSY = "busy"               # a sync held the runner's lock past the wait
FAILED = "failed"           # the pull failed, or failed recently: the copy stands

_FAILED_AT: dict[str, float] = {}


def max_age_seconds() -> float:
    """The age limit in seconds: HEALTH_CACHE_MAX_AGE_MINUTES, else MAX_AGE_MINUTES."""
    raw = os.environ.get("HEALTH_CACHE_MAX_AGE_MINUTES", "").strip()
    try:
        minutes = float(raw) if raw else MAX_AGE_MINUTES
    except ValueError:
        minutes = MAX_AGE_MINUTES
    return max(0.0, minutes) * 60.0


def refresh_if_stale(config, runner, *, wait_seconds: float, now: float | None = None,
                     store_factory=None) -> str:
    """Pull the copy again when it is older than the limit; one of FRESH,
    REFRESHED, BUSY, FAILED or NOT_RECORD. `runner` is the process's
    BackgroundSyncRunner; `wait_seconds` how long to wait for a running
    sync (0: never wait)."""
    if not record_cache.is_supabase_record(config):
        return NOT_RECORD
    path = config.datastore_path
    now = time.time() if now is None else now
    limit = max_age_seconds()
    if not record_cache.is_stale(path, limit, now):
        return FRESH
    failed_at = _FAILED_AT.get(path)
    if failed_at is not None and now - failed_at < RETRY_AFTER_SECONDS:
        return FAILED
    try:
        with runner.exclusive(timeout=wait_seconds):
            if not record_cache.is_stale(path, limit):
                return FRESH            # pulled by another request while this one waited
            record_cache.refresh(config, store_factory)
    except SyncBusyError:
        return BUSY
    except Exception as exc:
        _FAILED_AT[path] = now
        log.warning("local copy refresh failed (%s); the copy stands", type(exc).__name__)
        return FAILED
    _FAILED_AT.pop(path, None)
    return REFRESHED


def forget_failures() -> None:
    """Clear the failure back-off (tests)."""
    _FAILED_AT.clear()
