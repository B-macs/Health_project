"""
services/config.py — Credentials/settings loader.

Backend access needs 6 values: the Notion API key + 4 database IDs, and the
Google Sheets ID + service-account JSON. load_config() reads them from OS
environment variables first, falling back to an injected `overrides` dict —
the Streamlit layer builds that dict from st.secrets at startup. This module
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
    notion_db_biometrics: str
    notion_db_config: str
    google_sheets_id: str
    google_service_account: dict
    # Optional — Garmin sync is disabled (not an error) when either is blank.
    garmin_email: str = ""
    garmin_password: str = ""
    # Optional — Oura sync is disabled (not an error) when blank.
    oura_token: str = ""


_STR_KEYS = (
    "NOTION_API_KEY",
    "NOTION_DB_READINESS",
    "NOTION_DB_TRAINING",
    "NOTION_DB_BIOMETRICS",
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
        notion_db_biometrics=_resolve_str("NOTION_DB_BIOMETRICS", overrides),
        notion_db_config=_resolve_str("NOTION_DB_CONFIG", overrides),
        google_sheets_id=_resolve_str("GOOGLE_SHEETS_ID", overrides),
        google_service_account=_resolve_service_account(overrides),
        garmin_email=_resolve_optional_str("GARMIN_EMAIL", overrides),
        garmin_password=_resolve_optional_str("GARMIN_PASSWORD", overrides),
        oura_token=_resolve_optional_str("OURA_TOKEN", overrides),
    )
