"""
services/clients/oura.py — Oura API v2 client + raw reads + the OAuth2 flow.

Official, documented REST API (unlike Garmin's unofficial one). Base URLs,
auth and the token exchange are the only things this module knows; endpoint
names, date-range params, and JSON field names all live in
services/repository.py, same split as clients/sheets.py and
clients/garmin.py. The token LIFECYCLE rules (when to refresh, what to carry
forward) live in services/oura_auth.py — this module only makes the calls.

Every /v2/usercollection/{endpoint} route uses the same shape:
{"data": [...], "next_token": str | None} — get_collection() follows
next_token until exhausted so a wide date range never silently drops rows.

TWO CREDENTIAL KINDS, and the older one is on its way out. A Personal Access
Token is a static bearer string needing no flow at all; Oura deprecated them
in December 2025 and this project's own PAT started returning 401 on
2026-08-12. OAuth2 is the replacement: authorize once in a browser, then
exchange and refresh forever. make_client() still returns a PAT when one is
configured so a working legacy token is not broken by this module existing,
but repository.py prefers OAuth whenever both are present.
"""

from __future__ import annotations

from urllib.parse import urlencode

import requests

from services.config import Config

BASE_URL = "https://api.ouraring.com/v2/usercollection"
#: Where the athlete's browser goes to grant access. Note the host differs
#: from the API's — cloud.ouraring.com serves the consent screen,
#: api.ouraring.com serves the token exchange. Sending either to the other
#: returns a redirect to a sign-in page rather than an error, which reads
#: like a wrong password rather than a wrong URL.
AUTHORIZE_URL = "https://cloud.ouraring.com/oauth/authorize"
TOKEN_URL = "https://api.ouraring.com/oauth/token"
_TIMEOUT_SECONDS = 20


class OuraAuthError(RuntimeError):
    """The credential itself is the problem — not the network, not Oura.

    Separated from a plain requests exception because the two need opposite
    handling and only one of them is worth interrupting the athlete about. A
    timeout or a 502 means try again later and change nothing. This means the
    stored credential will never work again and a human has to re-authorise,
    which is the state that went unnoticed for five days when every failure
    looked alike.
    """


def make_client(config: Config) -> str | None:
    """The legacy Personal Access Token, or None when one isn't configured.

    Kept because a PAT that still works should keep working. repository.py
    calls this only after the OAuth path has come up empty.
    """
    return config.oura_token or None


# ─── OAuth2 ──────────────────────────────────────────────────────────────
#  Authorization-code flow. Oura's refresh tokens are SINGLE USE — see
#  services/oura_auth.py's header for what that forces on every caller.


def authorize_url(client_id: str, redirect_uri: str, scopes, state: str) -> str:
    """The URL to open in a browser to grant this app access.

    `state` is required, not optional-with-a-default: it is the only thing
    that ties the redirect the app receives back to the request it made, and
    a default value would be the same for every caller, which is the same as
    not having one.
    """
    if not client_id:
        raise OuraAuthError("no Oura client_id configured")
    if not state:
        raise OuraAuthError("authorize_url needs a state value — see its docstring")
    return f"{AUTHORIZE_URL}?" + urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
    })


def _post_token(client_id: str, client_secret: str, form: dict) -> dict:
    """POST to the token endpoint and return the parsed JSON.

    Credentials go in the FORM BODY rather than as HTTP Basic. Oura accepts
    both; the body is the variant that survives being logged by a proxy that
    strips Authorization headers, and it keeps the two Oura auth styles
    (Bearer for the API, form creds here) from looking interchangeable.

    A 400 or 401 becomes OuraAuthError. That is the whole reason this
    function exists rather than a raise_for_status at each call site: at the
    token endpoint those two codes mean "this credential is finished", and
    they must not be retried the way a 5xx should be.
    """
    if not client_id or not client_secret:
        raise OuraAuthError(
            "Oura OAuth is not configured — OURA_CLIENT_ID and OURA_CLIENT_SECRET "
            "(or CLIENT_ID/CLIENT_SECRET) must be set in .streamlit/secrets.toml."
        )
    payload = dict(form, client_id=client_id, client_secret=client_secret)
    resp = requests.post(
        TOKEN_URL, data=payload, timeout=_TIMEOUT_SECONDS,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code in (400, 401):
        # Oura returns {"error": "...", "error_description": "..."} here.
        # Surfacing both matters: `invalid_grant` on a refresh means the
        # single-use token was already spent, which is a different repair
        # from `invalid_client` (wrong secret) even though both are 400.
        try:
            body = resp.json()
            detail = body.get("error_description") or body.get("error") or resp.text
        except ValueError:
            detail = resp.text
        raise OuraAuthError(f"Oura rejected the credential ({resp.status_code}): {detail}")
    resp.raise_for_status()
    return resp.json()


def exchange_code(client_id: str, client_secret: str, code: str,
                  redirect_uri: str) -> dict:
    """Trade an authorization code for the first token pair. The code is
    single-use and short-lived; a second attempt with the same one is a 400."""
    return _post_token(client_id, client_secret, {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    })


def refresh_access_token(client_id: str, client_secret: str,
                         refresh_token: str) -> dict:
    """Redeem a refresh token for a new pair.

    ⚠ This CONSUMES `refresh_token`. Oura invalidates it on use and returns
    the replacement in the response, so a caller that does not persist the
    result has destroyed the credential — there is no way to ask for the same
    one twice. Callers must serialise (repository._OURA_REFRESH_LOCK) and
    persist before use.
    """
    if not refresh_token:
        raise OuraAuthError("no Oura refresh token stored — re-authorisation is required")
    return _post_token(client_id, client_secret, {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })


def verify_token(token: str) -> dict:
    """GET /personal_info purely to find out whether `token` authenticates.

    The cheapest possible probe: no date range, one small row, and it is the
    call whose 401 identified the dead PAT in the first place. Raises
    OuraAuthError on 401 so a caller can tell "credential is dead" from
    "Oura is down".
    """
    resp = requests.get(
        f"{BASE_URL}/personal_info",
        headers={"Authorization": f"Bearer {token}"},
        timeout=_TIMEOUT_SECONDS,
    )
    if resp.status_code == 401:
        raise OuraAuthError(_unauthorised_detail(resp))
    resp.raise_for_status()
    return resp.json()


def _unauthorised_detail(resp) -> str:
    try:
        return f"Oura rejected the access token (401): {resp.json().get('detail') or resp.text}"
    except ValueError:
        return f"Oura rejected the access token (401): {resp.text}"


def get_collection(token: str, endpoint: str, start_date: str, end_date: str) -> list[dict]:
    """GET /v2/usercollection/{endpoint}?start_date=...&end_date=...,
    following next_token pagination. Returns [] on a 404 (some endpoints,
    e.g. vo2_max, 404 for accounts/devices without that data — treated the
    same as "no data" rather than an error).

    A 401 raises OuraAuthError rather than a generic HTTPError. The
    distinction is what lets the sync chain report "your Oura login needs
    renewing" instead of the indistinguishable "sync unavailable — will retry
    next visit" that hid a dead credential for five days.
    """
    headers = {"Authorization": f"Bearer {token}"}
    params = {"start_date": start_date, "end_date": end_date}
    out: list[dict] = []
    next_token = None
    while True:
        if next_token:
            params["next_token"] = next_token
        resp = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params, timeout=_TIMEOUT_SECONDS)
        if resp.status_code == 404:
            return out
        if resp.status_code == 401:
            raise OuraAuthError(_unauthorised_detail(resp))
        resp.raise_for_status()
        payload = resp.json()
        out.extend(payload.get("data") or [])
        next_token = payload.get("next_token")
        if not next_token:
            return out
