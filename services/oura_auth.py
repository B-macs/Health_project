"""
services/oura_auth.py — Oura OAuth2 token lifecycle, as pure logic.

Oura retired Personal Access Tokens. This app authenticated with a static
bearer string until 2026-08-12, when that token began returning 401 on every
endpoint; five nights went unrecorded before anyone noticed, and readiness
went UP rather than blank while they did (see repository.oura_auth_status and
CLAUDE.md's Known Open Issues row). OAuth2 replaces it, and unlike a PAT,
OAuth2 has state: an access token that expires and a refresh token that buys
the next one.

This module owns the RULES about that state and nothing else — when a token
is due for replacement, what a token response means, and what to carry
forward when the response is partial. The HTTP lives in clients/oura.py and
the storage lives in repository.py, the same three-way split the rest of this
package uses. No I/O, no clock reads that aren't an explicit `now` parameter,
no Streamlit.

⚠ THE REFRESH TOKEN IS SINGLE USE. Oura invalidates it the moment it is
redeemed and returns a replacement in the same response. Two consequences
shape everything here:

  * A refresh that SUCCEEDS but whose result is not persisted is
    unrecoverable. The old refresh token is already dead and the new one was
    never written down, so the only repair is a human logging into Oura
    again. That is why repository.py persists before it uses the result, and
    why REFRESH_SKEW_SECONDS is a day rather than a minute — a wide skew
    means a failed refresh has many more chances before the access token it
    was replacing actually lapses.

  * Two concurrent refreshes race, and the loser is left holding a burned
    token. This app has exactly that shape: the background sync thread builds
    its OWN Repository (key rule 12) while the script thread holds another,
    so both can reach a refresh at the same moment. This module deliberately
    cannot serialise that for them — it holds no state and no lock. The
    caller must, and repository._OURA_REFRESH_LOCK is where that happens.

TIMES ARE UTC-AWARE HERE, deliberately unlike the naive local datetimes the
.sync_state.json sync markers use. An expiry is an absolute instant, not a
wall-clock reading: the app runs hosted (key rule 18) on a server whose zone
is not the athlete's, and this repo has already been bitten once by a naive
datetime.now() recording a 13:08 set as 11:08 (see config.Config.timezone).
A token that is compared against the wrong clock either refreshes constantly
or expires unnoticed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

#: How long BEFORE expiry a token counts as due for refresh.
#:
#: A day, not a minute. The point is not to cut it fine — it is to leave a
#: wide margin in which a failed refresh can be retried while the current
#: access token still works. Oura's access tokens run ~30 days, so this
#: refreshes roughly monthly and still gives 24 hours of grace if the refresh
#: call itself fails.
REFRESH_SKEW_SECONDS = 86_400

#: Assumed lifetime when a token response omits `expires_in`.
#:
#: Oura documents that it always sends one, so this is defence rather than an
#: expected path — but the failure it prevents is severe. Leaving expires_at
#: unset would make needs_refresh() true forever, and since every refresh
#: burns a single-use refresh token, that is an infinite loop that destroys
#: the credential rather than merely spinning. 30 days matches Oura's own
#: documented lifetime.
DEFAULT_EXPIRES_IN_SECONDS = 30 * 86_400

#: Scopes to request. The app reads daily summaries, sleep periods, workouts,
#: sessions and rest-mode periods, so it needs `daily`, `workout`, `session`
#: and `spo2`; `personal` is what makes the zero-cost auth probe in
#: clients/oura.verify_token possible; `heartrate` and `tag` are requested
#: because widening scope later costs a full re-authorisation and these are
#: the two endpoints most likely to be wanted next. `email` is NOT requested
#: — nothing here reads it.
DEFAULT_SCOPES = ("personal", "daily", "heartrate", "workout", "tag", "session", "spo2")


class OuraTokenError(ValueError):
    """A token response or stored blob that cannot be used as a credential."""


@dataclass(frozen=True)
class OAuthToken:
    """One Oura credential. Frozen because a refresh produces a NEW token
    rather than mutating the old one — the old one may still be in use on
    another thread, and mutating it in place would change what that thread
    is about to send mid-flight."""

    access_token: str
    refresh_token: str = ""
    #: None means UNKNOWN, which is treated as due (see needs_refresh). Only
    #: reachable from a legacy or hand-edited stored blob; from_response
    #: always sets one.
    expires_at: datetime | None = None
    scope: str = ""
    token_type: str = "Bearer"
    obtained_at: datetime | None = None


def _utc(now: datetime | None) -> datetime:
    """The current instant as UTC-aware. A naive `now` is read as UTC rather
    than as local time: every caller in this package passes either nothing or
    an already-UTC value, and guessing local for a naive one would silently
    shift every comparison by the host's offset."""
    if now is None:
        return datetime.now(timezone.utc)
    return now if now.tzinfo else now.replace(tzinfo=timezone.utc)


def from_response(payload: dict, now: datetime | None = None,
                  previous: OAuthToken | None = None) -> OAuthToken:
    """Build a token from Oura's /oauth/token JSON.

    `previous` supplies the refresh token when the response omits one. Oura
    documents that it rotates on every use, but carrying the old value
    forward on an absent key is strictly safer than storing "" — a blank
    refresh token is indistinguishable from "this credential can never be
    renewed", which forces a manual re-authorisation that may not be needed.

    Raises OuraTokenError when there is no access token, rather than
    returning a token whose access_token is "" — that would sail on and fail
    later as a 401, i.e. as the exact symptom this whole module exists to
    stop being mysterious.
    """
    access = (payload or {}).get("access_token") or ""
    if not access:
        raise OuraTokenError(
            f"Oura token response carried no access_token (keys: {sorted((payload or {}).keys())})"
        )
    issued = _utc(now)
    try:
        lifetime = int(payload.get("expires_in") or DEFAULT_EXPIRES_IN_SECONDS)
    except (TypeError, ValueError):
        lifetime = DEFAULT_EXPIRES_IN_SECONDS
    return OAuthToken(
        access_token=access,
        refresh_token=payload.get("refresh_token")
        or (previous.refresh_token if previous else ""),
        expires_at=issued + timedelta(seconds=lifetime),
        scope=payload.get("scope") or (previous.scope if previous else ""),
        token_type=payload.get("token_type") or "Bearer",
        obtained_at=issued,
    )


def can_refresh(token: OAuthToken | None) -> bool:
    """True when there is something to refresh WITH. False here means the
    only way back is a human re-authorising in a browser, which is worth
    saying differently from "expired"."""
    return bool(token and token.refresh_token)


def is_expired(token: OAuthToken | None, now: datetime | None = None) -> bool:
    """True when the access token is past its expiry — i.e. dead, not merely
    due. Distinct from needs_refresh: between the two, the credential still
    works, which is the window a failed refresh gets to recover in."""
    if token is None or not token.access_token:
        return True
    if token.expires_at is None:
        return False
    return _utc(now) >= _utc(token.expires_at)


def needs_refresh(token: OAuthToken | None, now: datetime | None = None,
                  skew_seconds: int = REFRESH_SKEW_SECONDS) -> bool:
    """True when `token` should be replaced before the next API call.

    An unknown expiry counts as due. An unknown expiry can only arise from a
    stored blob written by something other than from_response, and on a
    credential that has already failed once in this project's history the
    safe reading of "unknown" is "replace it", not "assume it is good".
    """
    if token is None or not token.access_token:
        return True
    if not can_refresh(token):
        # Nothing to refresh with, so "due" would be a lie that makes the
        # caller burn a request to discover it. Report not-due and let the
        # 401 (or oura_auth_status) be what says the credential is finished.
        return False
    if token.expires_at is None:
        return True
    return _utc(now) >= _utc(token.expires_at) - timedelta(seconds=skew_seconds)


def to_json(token: OAuthToken) -> str:
    """Serialise for storage. Datetimes go out as UTC ISO strings so a blob
    written by one host is read identically by another — see this module's
    header on why that is not the naive format the sync markers use."""
    return json.dumps({
        "access_token": token.access_token,
        "refresh_token": token.refresh_token,
        "expires_at": _utc(token.expires_at).isoformat() if token.expires_at else None,
        "scope": token.scope,
        "token_type": token.token_type,
        "obtained_at": _utc(token.obtained_at).isoformat() if token.obtained_at else None,
    }, sort_keys=True)


def _parse_dt(raw) -> datetime | None:
    if not raw:
        return None
    try:
        return _utc(datetime.fromisoformat(str(raw)))
    except (TypeError, ValueError):
        return None


def from_json(raw: str | None) -> OAuthToken | None:
    """Inverse of to_json. Returns None for anything unusable — absent,
    unparseable, or carrying no access token.

    None rather than raising, because every caller's next move is the same
    either way (fall back to the PAT, then report unauthenticated), and a
    corrupt blob in the config store must not be able to take the whole app
    down on import of a page that merely wanted to show a sync status.
    """
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get("access_token"):
        return None
    return OAuthToken(
        access_token=str(data["access_token"]),
        refresh_token=str(data.get("refresh_token") or ""),
        expires_at=_parse_dt(data.get("expires_at")),
        scope=str(data.get("scope") or ""),
        token_type=str(data.get("token_type") or "Bearer"),
        obtained_at=_parse_dt(data.get("obtained_at")),
    )


def status(token: OAuthToken | None, now: datetime | None = None) -> dict:
    """A display-ready summary. Never includes the token values themselves —
    this is rendered on the Sync page and must be safe to screenshot.

    `state` is the one field a caller should branch on:

      unauthenticated  no credential at all; a human must authorise.
      expired          access token lapsed AND no refresh token; same repair.
      stale            lapsed but refreshable; the next sync fixes it.
      due              still valid, refresh scheduled on next use.
      ok               valid, nothing to do.
    """
    if token is None or not token.access_token:
        return {"state": "unauthenticated", "expires_at": None,
                "can_refresh": False, "scope": "", "seconds_remaining": None}
    now_utc = _utc(now)
    exp = _utc(token.expires_at) if token.expires_at else None
    remaining = int((exp - now_utc).total_seconds()) if exp else None
    refreshable = can_refresh(token)
    if is_expired(token, now_utc):
        state = "stale" if refreshable else "expired"
    elif needs_refresh(token, now_utc):
        state = "due"
    else:
        state = "ok"
    return {
        "state": state,
        "expires_at": exp.isoformat() if exp else None,
        "can_refresh": refreshable,
        "scope": token.scope,
        "seconds_remaining": remaining,
    }
