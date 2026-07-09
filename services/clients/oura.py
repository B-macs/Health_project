"""
services/clients/oura.py — Oura API v2 client + raw reads.

Official, documented REST API (unlike Garmin's unofficial one) — a Bearer
personal access token, no OAuth flow. Base URL and auth are the only two
things this module knows; endpoint names, date-range params, and JSON field
names all live in services/repository.py, same split as clients/sheets.py
and clients/garmin.py.

Every /v2/usercollection/{endpoint} route uses the same shape:
{"data": [...], "next_token": str | None} — get_collection() follows
next_token until exhausted so a wide date range never silently drops rows.
"""

from __future__ import annotations

import requests

from services.config import Config

BASE_URL = "https://api.ouraring.com/v2/usercollection"
_TIMEOUT_SECONDS = 20


def make_client(config: Config) -> str | None:
    """Returns the bearer token itself (there's no session/login step for a
    personal access token) — None when Oura isn't configured. Callers pass
    this straight through to get_collection()."""
    return config.oura_token or None


def get_collection(token: str, endpoint: str, start_date: str, end_date: str) -> list[dict]:
    """GET /v2/usercollection/{endpoint}?start_date=...&end_date=...,
    following next_token pagination. Returns [] on a 404 (some endpoints,
    e.g. vo2_max, 404 for accounts/devices without that data — treated the
    same as "no data" rather than an error)."""
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
        resp.raise_for_status()
        payload = resp.json()
        out.extend(payload.get("data") or [])
        next_token = payload.get("next_token")
        if not next_token:
            return out
