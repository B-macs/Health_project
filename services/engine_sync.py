"""The engine's device sync and its status (POST /api/sync, GET /api/status;
rebuild Phase 2, milestone 5).

ONLY THE BACKGROUND WRITER SYNCS (rebuild rule 2). Until the switch-over
(Phase 9) the store's background_writer setting names the Streamlit app, and
every sync here refuses: Oura spends its refresh token at every refresh, so
two processes refreshing break the login, and two processes applying the
failed-week rule can judge one week twice. services/background_writer.py
holds the setting; this module asks it first.

WHEN: the owner's rule (services/sync_policy.py, 2026-10-19). The first
request of the caller's day syncs; while last night's numbers are missing
after that, a later request syncs again, at most once an hour; once they are
in, nothing more that day. The phone asks on every open (GET /api/status
says whether a sync is due), so whatever screen opens first starts it.

WHAT: Repository.run_home_syncs, the same chain the Streamlit app runs,
under the BackgroundSyncRunner's one lock, then the failed-week rule (Key
Rule 22), the one automatic write the Training page makes on its own. The
last run is stored in the store's config under STATUS_KEY, because the
engine scales to zero and keeps nothing in memory between requests.
"""

from __future__ import annotations

import json
from datetime import date, datetime

from services import background_writer, sync_policy, week_repeat

#: Where the engine stores its last sync run: {"day", "at", "results", "error"}.
STATUS_KEY = "engine_sync_status"


def read_status(repo) -> dict:
    """The last stored run: {"day": ISO date or None, "at": ISO instant or
    None, "results": {step: [ok, error]}, "error": str or None}. An absent or
    unreadable record reads as no run yet."""
    empty = {"day": None, "at": None, "results": {}, "error": None}
    try:
        raw = repo.get_config_value(STATUS_KEY)
        stored = json.loads(raw) if raw else {}
    except Exception:
        return empty
    return {**empty, **{k: stored.get(k) for k in empty if k in stored}}


def _parse_day(value) -> date | None:
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def _parse_at(value) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def last_night_in(repo, caller_today: date) -> bool:
    """Whether the caller's day already has last night's numbers stored
    (sync_policy.last_night_in). A failed read reads as missing: the safe
    direction, a sync that finds nothing new writes nothing."""
    try:
        rows = repo.get_metrics_history(start=caller_today.isoformat(),
                                        end=caller_today.isoformat())
    except Exception:
        return False
    row = next((r for r in rows if r.get("date") == caller_today.isoformat()), None)
    return sync_policy.last_night_in(row)


def due(repo, caller_today: date, now: datetime, status: dict | None = None) -> str | None:
    """Why a sync is due now (sync_policy.FIRST_OPEN or LAST_NIGHT_MISSING),
    or None. `now` is an instant on the same clock as the stored run's."""
    status = status if status is not None else read_status(repo)
    return sync_policy.sync_due(caller_today, now, _parse_day(status["day"]),
                                _parse_at(status["at"]), last_night_in(repo, caller_today))


def run(repo, runner, caller_today: date, now: datetime, *, force: bool = False) -> dict:
    """Sync when due (always with `force`), as the background writer only.

    Returns {"ran", "reason", "status"}. Raises
    background_writer.NotTheWriterError when the store names another writer,
    before anything is read from a device. The runner re-checks the setting
    on its own Repository, so a switch between the two checks still stops
    the chain."""
    background_writer.require(repo, background_writer.ENGINE)
    status = read_status(repo)
    reason = "asked" if force else due(repo, caller_today, now, status)
    if reason is None:
        return {"ran": False, "reason": None, "status": status}
    results = runner.run_now(caller_today)
    if runner.skipped_for() is not None:
        raise background_writer.NotTheWriterError(
            f"the background writer is {runner.skipped_for()}, not {background_writer.ENGINE}")
    results = {name: list(result) for name, result in results.items()}
    try:
        week_repeat.store_failed_week_rule(repo, repo.get_phases(), caller_today)
        results["failed_week"] = [True, None]
    except Exception as exc:
        results["failed_week"] = [False, str(exc)]
    status = {"day": caller_today.isoformat(), "at": now.isoformat(),
              "results": results, "error": runner.last_error()}
    repo.set_config(STATUS_KEY, json.dumps(status, sort_keys=True), today=caller_today)
    return {"ran": True, "reason": reason, "status": status}


def notices(oura_auth: dict | None, status: dict) -> list[dict]:
    """The sync notices a screen shows, in order (sync_policy.sync_notices),
    from the stored run: {"level": "error" or "caption", "code": ...}. The
    phone holds each code's words."""
    results = status.get("results") or {}
    oura = tuple(results.get("oura") or (True, None))
    garmin = tuple(results.get("garmin") or (True, None))
    return [{"level": level, "code": code}
            for level, code in sync_policy.sync_notices(oura_auth, oura, garmin,
                                                        status.get("error"))]


#: The parts of Repository.oura_auth_status the phone shows; never a token.
OURA_FIELDS = ("kind", "state", "needs_authorisation", "expires_at", "seconds_remaining",
               "oauth_configured")


def app_status(repo, caller_today: date, now: datetime) -> dict:
    """What every screen may need to say about the engine itself: which
    process writes in the background, whether reads come from an offline
    snapshot (and its age), the Oura login's state (a dead login is an error,
    never a "will retry"), the last sync run, its notices, and whether a sync
    is due now (only when the engine is the writer)."""
    writer = background_writer.current(repo)
    try:
        oura = repo.oura_auth_status()
    except Exception:
        oura = None
    status = read_status(repo)
    offline = bool(getattr(repo, "offline", False))
    return {
        "writer": writer,
        "offline": offline,
        "datastore_built_at": repo.datastore_built_at() if offline else None,
        "oura": None if oura is None else {k: oura.get(k) for k in OURA_FIELDS},
        "last_sync": status if status["day"] else None,
        "notices": notices(oura, status),
        "sync_due": (due(repo, caller_today, now, status)
                     if writer == background_writer.ENGINE else None),
    }
