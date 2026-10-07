"""Rebuild Phase 0 diagnostics: can Cloud Run reach Oura and Garmin?

OFF unless HEALTH_PROBES=1. They answer with a status and a count, never a
reading, a token or an error body that could hold one.

⚠ THE OURA PROBE MUST NEVER REFRESH THE TOKEN. Oura uses up its refresh token
at each refresh (services/clients/oura.py), and the hosted Streamlit app holds
it: a refresh from here would break the Streamlit app's Oura login. So this
reads the stored token blob directly (never Repository._oc, which refreshes an
expiring token by itself), and calls Oura only while the access token is valid
for more than an hour. tests/api/test_api.py scans this file for every refresh
path and fails if one appears.

The Garmin probe logs in once per container and refuses a second call; the
owner approves the call before it is made.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services import oura_auth
from services.clients import garmin, oura
from services.repository import Repository

from .. import engine
from ..dates import caller_local_date
from .readiness import get_repository

router = APIRouter()

OURA_TOKEN_KEY = "oura_oauth_token"           # services/repository.py:_OURA_TOKEN_KEY
OURA_MIN_VALID = timedelta(hours=1)
_garmin_probe_used = False


class ProbeOut(BaseModel):
    status: str
    detail: str
    count: int | None = None


class GarminProbeIn(BaseModel):
    confirm: str


@router.get("/api/probe/oura", response_model=ProbeOut)
def probe_oura(local_today: date = Depends(caller_local_date),
               repo: Repository = Depends(get_repository)) -> ProbeOut:
    token = oura_auth.from_json(repo.get_config_value(OURA_TOKEN_KEY))
    if token is None or not token.access_token:
        return ProbeOut(status="skipped", detail="no stored Oura token")
    if token.expires_at is None:
        return ProbeOut(status="skipped", detail="the token has no expiry; not risked")
    left = token.expires_at - datetime.now(timezone.utc)
    if left < OURA_MIN_VALID:
        return ProbeOut(status="skipped", detail="the access token expires within an hour")
    day = (local_today - timedelta(days=1)).isoformat()
    try:
        rows = oura.get_collection(token.access_token, "daily_readiness", day, day)
    except Exception as exc:  # noqa: BLE001 - the type only, never the body
        return ProbeOut(status="error", detail=type(exc).__name__)
    return ProbeOut(status="ok", detail=f"daily_readiness for yesterday, token valid "
                                        f"{int(left.total_seconds() // 3600)} h more",
                    count=len(rows))


def _garmin_failure(exc: Exception) -> str:
    text = str(exc).lower()
    if "403" in text:
        return "blocked_403"
    if "429" in text or "too many" in text or "rate limit" in text:
        return "rate_limited_429"
    if "mfa" in text or "2fa" in text or "verification code" in text:
        return "mfa_required"
    return type(exc).__name__


@router.post("/api/probe/garmin", response_model=ProbeOut)
def probe_garmin(body: GarminProbeIn,
                 local_today: date = Depends(caller_local_date)) -> ProbeOut:
    global _garmin_probe_used
    if body.confirm != "owner-approved":
        raise HTTPException(status_code=400, detail="confirm_missing")
    if _garmin_probe_used:
        raise HTTPException(status_code=409, detail="already_used_in_this_container")
    _garmin_probe_used = True
    try:
        client = garmin.make_client(engine.STATE.config)
    except Exception as exc:  # noqa: BLE001
        return ProbeOut(status="login_failed", detail=_garmin_failure(exc))
    if client is None:
        return ProbeOut(status="skipped", detail="Garmin is not configured")
    stores = hasattr(getattr(client, "client", None), "dumps")
    try:
        summary = garmin.get_daily_summary(client, local_today - timedelta(days=1))
    except Exception as exc:  # noqa: BLE001
        return ProbeOut(status="read_failed", detail=_garmin_failure(exc))
    return ProbeOut(status="ok", detail=f"login and read worked; tokens can be stored: {stores}",
                    count=len(summary))
