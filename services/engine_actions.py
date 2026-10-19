"""The engine's own actions on the Sync tab and in Settings (rebuild Phase 2,
milestone 5): the five manual syncs, the Oura login, and the plan's start.

THE DEVICE SYNCS AND THE OURA LOGIN ARE THE BACKGROUND WRITER'S (rebuild
rule 2). Each refuses with background_writer.NotTheWriterError unless the
store names the engine: Oura spends its refresh token at every refresh, so a
sync from a second process breaks the login, and a new login replaces the
token the other process holds. A manual sync runs under the sync runner's
lock (Key Rule 16): it runs the same work as the automatic step over a wider
window, so waiting for the automatic chain loses nothing, and racing it can
write a date twice.

A token or a secret never leaves this module: the Oura answers carry the
login's state, never a credential.
"""

from __future__ import annotations

import hmac
import json
import secrets
from datetime import date

from services import background_writer, oura_auth
from services import plan as _plan
from services import sessions as sess
from services.clients import oura


class ActionRefused(ValueError):
    """An action that cannot be taken: `code` names why."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# ─── The manual syncs (Sync tab, I84 and I89-I93) ───────────────────────────

#: Each manual sync, as its button runs it: the wider window of the automatic
#: step it repeats.
MANUAL_SYNCS = {
    "garmin_daily": lambda repo, today: repo.sync_garmin_daily(days=7, today=today),
    "garmin_activities": lambda repo, today: repo.sync_garmin_activities(limit=20),
    "sleep_fusion": lambda repo, today: repo.sync_sleep_fusion(days=1200, today=today),
    "oura_weekly": lambda repo, today: repo.sync_oura_all(days=7, today=today),
    "blend_backfill": lambda repo, today: repo.sync_biometric_blend(days=400, today=today),
}
#: The syncs that call a device, and so need it configured.
_NEEDS = {"garmin_daily": "garmin", "garmin_activities": "garmin", "oura_weekly": "oura"}


def manual_sync(repo, runner, kind: str, today: date, *, wait_seconds: float = 120.0) -> dict:
    """Run one manual sync now, as the background writer only, under the
    runner's lock. Returns {"kind", "result"}: the count it reports, or the
    counts by kind for a sync that reports several. ActionRefused for an
    unknown kind or a device that is not configured; NotTheWriterError
    unless the engine writes; SyncBusyError when the lock stays held."""
    if kind not in MANUAL_SYNCS:
        raise ActionRefused("unknown_sync")
    background_writer.require(repo, background_writer.ENGINE)
    device = _NEEDS.get(kind)
    if device == "garmin" and not repo.garmin_configured():
        raise ActionRefused("garmin_not_configured")
    if device == "oura" and not repo.oura_configured():
        raise ActionRefused("oura_not_configured")
    with runner.exclusive(timeout=wait_seconds):
        result = MANUAL_SYNCS[kind](repo, today)
    return {"kind": kind, "result": result if isinstance(result, dict) else {"count": result}}


# ─── The Oura login (H21's re-authorise path) ───────────────────────────────

#: The config row that holds a login in progress: its state and redirect.
LOGIN_KEY = "oura_login_state"


def _oauth_configured(repo) -> bool:
    return bool(repo.config.oura_client_id and repo.config.oura_client_secret)


def start_oura_login(repo, redirect_uri: str, today: date) -> dict:
    """The address to open to grant Oura access, with a fresh state that
    ties the answer to this request (stored in the config row, so the
    answer may reach another engine instance). The redirect must be one
    registered on the Oura application; Oura refuses any other."""
    background_writer.require(repo, background_writer.ENGINE)
    if not _oauth_configured(repo):
        raise ActionRefused("oauth_not_configured")
    if not redirect_uri.startswith("https://"):
        raise ActionRefused("redirect_not_https")
    state = secrets.token_urlsafe(24)
    repo.set_config(LOGIN_KEY, json.dumps({"state": state, "redirect_uri": redirect_uri}),
                    today=today)
    return {"authorize_url": oura.authorize_url(repo.config.oura_client_id, redirect_uri,
                                                oura_auth.DEFAULT_SCOPES, state)}


def finish_oura_login(repo, code: str, state: str, today: date) -> dict:
    """Trade the code Oura sent back for the token pair and store it
    (Repository.save_oura_oauth_token), when the state is the one this
    login started with. The login row is cleared either way once it is
    used: a code is single-use. Answers the login's status, never a token."""
    background_writer.require(repo, background_writer.ENGINE)
    try:
        stored = json.loads(repo.get_config_value(LOGIN_KEY) or "{}")
    except ValueError:
        stored = {}
    if not stored.get("state") or not hmac.compare_digest(str(stored["state"]), str(state)):
        raise ActionRefused("state_mismatch")
    repo.set_config(LOGIN_KEY, "", today=today)
    payload = oura.exchange_code(repo.config.oura_client_id, repo.config.oura_client_secret,
                                 code, stored["redirect_uri"])
    repo.save_oura_oauth_token(payload, today=today)
    status = repo.oura_auth_status()
    return {k: status.get(k) for k in ("kind", "state", "needs_authorisation", "expires_at",
                                       "seconds_remaining", "oauth_configured")}


# ─── Settings: the plan's start (T29) ────────────────────────────────────────

def settings(repo) -> dict:
    """What Settings shows: the plan's start, the background writer, and
    which devices are configured."""
    return {"plan_start_date": repo.get_config_value("plan_start_date") or None,
            "writer": background_writer.current(repo),
            "garmin_configured": bool(repo.garmin_configured()),
            "oura_configured": bool(repo.oura_configured())}


def set_plan_start(repo, start: date, today: date) -> dict:
    """Set the plan's start date, and on a first run (no block stored) seed
    the first block from it, tied to this one confirmed request: a block is
    never seeded as a side effect of a read, which once replaced a real block
    when a read came back empty. Refused once blocks exist: they start by
    date, and a new start date would move none of them."""
    if repo.get_phases_live():
        raise ActionRefused("plan_already_running")
    repo.set_config("plan_start_date", start.isoformat(), today=today)
    seeded = sess.seed_default_phase([], start)
    if seeded:
        repo.set_phases(seeded)
    active = _plan.active_phase(seeded, today) if seeded else None
    return {**settings(repo), "seeded": bool(seeded),
            "active_phase": None if active is None else active.name}
