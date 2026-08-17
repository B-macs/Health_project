"""
services/config.py — Credentials/settings loader.

Backend access needs 5 values: the Notion API key + 3 database IDs (Readiness,
Training, Config), and the Google Sheets ID + service-account JSON.

The Notion BIOMETRICS database was retired on 2026-08-12 -- it held ten pages
with every column NULL and had no live writer. NOTION_DB_BIOMETRICS is no
longer read, so an existing secrets.toml can keep or drop it freely. load_config() reads them from the injected
`overrides` dict FIRST — the Streamlit layer builds that from st.secrets at
startup — and falls back to OS environment variables. That order matters when
choosing where to put a setting: anything present in secrets.toml CANNOT be
overridden per-environment by an env var, so host-specific settings
(HEALTH_DATASTORE_PATH, HEALTH_DATASTORE_MODE) belong in the environment and
credentials belong in secrets. This module
itself never imports streamlit, so the identical services/ code works
unmodified behind FastAPI + env vars later.

Never log, print, or persist a Config's contents.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    notion_api_key: str
    notion_db_readiness: str
    notion_db_training: str
    notion_db_config: str
    google_sheets_id: str
    google_service_account: dict
    # Optional — Garmin sync is disabled (not an error) when either is blank.
    garmin_email: str = ""
    garmin_password: str = ""
    # Optional — the LEGACY Oura Personal Access Token. Oura deprecated PATs
    # in December 2025 and this one stopped authenticating on 2026-08-12, so
    # it is no longer the primary path: repository.py prefers OAuth whenever
    # oura_client_id/secret are set, and falls back here only for a PAT that
    # still works. Blank disables Oura sync, which is not an error.
    oura_token: str = ""
    # Optional — the Oura OAuth2 application. New PATs cannot be created, so
    # this is the only way to authenticate a fresh install.
    #
    # ⚠ These are the STATIC half of the credential. The access and refresh
    # tokens the flow produces are NOT here and must not be: a refresh token
    # rotates on every use (see services/oura_auth.py), and a value that
    # changes cannot live in a file the deploy treats as immutable. Those are
    # stored through Repository.set_config so they survive the hosted
    # filesystem being wiped on redeploy (key rule 18).
    oura_client_id: str = ""
    oura_client_secret: str = ""
    # Optional — path to a locally-built datastore.db (scripts/build_datastore.py).
    # When set, Repository serves every Google Sheets READ from it and makes no
    # Google API call at all; writes raise. For testing and offline iteration
    # against real data without spending the 60-per-minute Sheets quota. Blank
    # (the default, and what the deployed app runs with) means live Sheets.
    # Deliberately NOT a fallback for a failed live read — see Repository._ws.
    datastore_path: str = ""
    # How that datastore is used. Only meaningful when datastore_path is set.
    #
    #   "readonly"  (default) reads are served locally and every write RAISES.
    #               The testing/offline mode, unchanged since 2026-08-01.
    #   "cache"     reads are served locally AND writes go through to the
    #               backend, with the local copy written through in the same
    #               call so the next read sees them. This is the HOSTED mode:
    #               a server needs 32 ms reads without the stale-cache hazard
    #               that made "readonly" refuse writes in the first place.
    #
    # Defaulting to "readonly" keeps every existing checkout, script and test
    # behaving exactly as before — the new mode is opt-in.
    datastore_mode: str = "readonly"
    # Optional — the Supabase (PostgreSQL) project the datastore is pushed to.
    # Blank means "not configured", which is not an error: nothing in the live
    # app reads from Postgres yet, so a checkout without these keys behaves
    # exactly as before.
    #
    # supabase_secret_key is SERVER-ONLY and must never reach browser code.
    # The publishable key is the one safe to expose, and is deliberately NOT
    # carried here — nothing server-side has a use for it, and holding it
    # would invite using the wrong one.
    supabase_url: str = ""
    supabase_secret_key: str = ""
    # IANA zone name for the ATHLETE's wall clock (e.g. "Europe/Berlin").
    #
    # Exists because the app does not run where the athlete trains. Per-set
    # timestamps were stamped with a naive datetime.now(), which is the
    # SERVER's clock — on a UTC host that recorded a 13:08 set as 11:08. The
    # error is invisible in isolation (an ISO string with no offset looks
    # local) and only surfaced when the sets were aligned against a Garmin
    # activity and sat two hours off.
    #
    # Blank keeps the host's own zone, which is correct for local runs and is
    # what the tests use. Set HEALTH_TIMEZONE in the deployed environment.
    # An IANA name rather than a fixed offset so DST is handled — a
    # +02:00 constant would be an hour wrong for half the year.
    timezone: str = ""


_STR_KEYS = (
    "NOTION_API_KEY",
    "NOTION_DB_READINESS",
    "NOTION_DB_TRAINING",
    "NOTION_DB_CONFIG",
    "GOOGLE_SHEETS_ID",
)


def _resolve_str(key: str, overrides: dict) -> str:
    if overrides.get(key):
        return str(overrides[key])
    val = os.getenv(key)
    if val:
        return val
    raise EnvironmentError(f"'{key}' not found in environment or config overrides.")


def _resolve_optional_str(key: str, overrides: dict) -> str:
    """Same lookup as _resolve_str but returns "" instead of raising — for
    settings that are genuinely optional (the app must keep working without
    them), not just missing-by-mistake."""
    if overrides.get(key):
        return str(overrides[key])
    return os.getenv(key) or ""


def _resolve_first_optional_str(keys: tuple[str, ...], overrides: dict) -> str:
    """First non-empty value among `keys`, or "".

    Exists for the Oura OAuth credentials specifically. The registered
    application predates this code and its keys are in secrets.toml under the
    bare names CLIENT_ID / CLIENT_SECRET — generic enough to belong to
    anything, which is why the OURA_-prefixed names are checked first and are
    the ones to use going forward. Accepting both means the existing
    secrets.toml authenticates untouched instead of needing a hand-edit on
    the hosted deploy at the same moment the credential is already broken.
    """
    for key in keys:
        val = _resolve_optional_str(key, overrides)
        if val:
            return val
    return ""


def _resolve_service_account(overrides: dict) -> dict:
    if overrides.get("google_service_account"):
        return dict(overrides["google_service_account"])
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        return json.loads(raw)
    raise EnvironmentError(
        "'google_service_account' not found in config overrides, and "
        "GOOGLE_SERVICE_ACCOUNT_JSON is not set in the environment."
    )


def load_config(overrides: dict | None = None) -> Config:
    """Build a Config. `overrides` is typically st.secrets (as a plain dict) in
    the Streamlit layer, or omitted entirely to read purely from environment
    variables — the path a non-Streamlit deployment would use."""
    overrides = overrides or {}
    return Config(
        notion_api_key=_resolve_str("NOTION_API_KEY", overrides),
        notion_db_readiness=_resolve_str("NOTION_DB_READINESS", overrides),
        notion_db_training=_resolve_str("NOTION_DB_TRAINING", overrides),
        notion_db_config=_resolve_str("NOTION_DB_CONFIG", overrides),
        google_sheets_id=_resolve_str("GOOGLE_SHEETS_ID", overrides),
        google_service_account=_resolve_service_account(overrides),
        garmin_email=_resolve_optional_str("GARMIN_EMAIL", overrides),
        garmin_password=_resolve_optional_str("GARMIN_PASSWORD", overrides),
        oura_token=_resolve_optional_str("OURA_TOKEN", overrides),
        oura_client_id=_resolve_first_optional_str(
            ("OURA_CLIENT_ID", "CLIENT_ID"), overrides),
        oura_client_secret=_resolve_first_optional_str(
            ("OURA_CLIENT_SECRET", "CLIENT_SECRET"), overrides),
        datastore_path=_resolve_optional_str("HEALTH_DATASTORE_PATH", overrides),
        datastore_mode=_resolve_optional_str("HEALTH_DATASTORE_MODE", overrides) or "readonly",
        supabase_url=_resolve_optional_str("SUPABASE_URL", overrides),
        supabase_secret_key=_resolve_optional_str("SUPABASE_SECRET_KEY", overrides),
        timezone=_resolve_optional_str("HEALTH_TIMEZONE", overrides),
    )
