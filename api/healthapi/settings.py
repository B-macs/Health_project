"""Builds the engine's Config without Streamlit.

The hosted engine reads the SAME secrets.toml the Streamlit app reads, mounted
from Google Secret Manager as a file at HEALTH_SECRETS_FILE. Only the top-level
string keys and the google_service_account table are kept, exactly what
scripts/authorize_oura.py:_load_overrides keeps, so a section that belongs to
another app never reaches load_config. Everything the TOML
does not carry (HEALTH_DATASTORE_MODE, HEALTH_DATASTORE_PATH, HEALTH_TIMEZONE)
comes from environment variables, as services/config.py already expects.

Nothing here prints or logs a value.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from services.config import Config, load_config

DEFAULT_SECRETS_FILE = "/secrets/health/secrets.toml"


def secrets_file() -> Path:
    return Path(os.environ.get("HEALTH_SECRETS_FILE", DEFAULT_SECRETS_FILE))


def secrets_overrides(path: Path | None = None) -> dict:
    """The TOML as load_config's overrides; {} when the file is absent, so
    environment variables apply (the same fallback services/config.py has)."""
    path = path or secrets_file()
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    overrides = {k: v for k, v in data.items() if isinstance(v, str)}
    if isinstance(data.get("google_service_account"), dict):
        overrides["google_service_account"] = data["google_service_account"]
    return overrides


def build_config(path: Path | None = None) -> Config:
    return load_config(secrets_overrides(path))


def engine_key() -> str | None:
    """The shared key the Worker must send. Cloud Run sets it from the
    health-engine-key secret; nothing else ever reads it."""
    value = os.environ.get("HEALTH_ENGINE_KEY", "")
    return value or None


def probes_enabled() -> bool:
    """The Phase 0 diagnostics in routes/probes.py are off unless this is set."""
    return os.environ.get("HEALTH_PROBES") == "1"
