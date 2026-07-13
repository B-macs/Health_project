"""
services/clients/garmin.py — Garmin Connect client + raw reads.

Uses the community `garminconnect` package (unofficial — Garmin's real
Health API is partner/B2B-only and has no personal-account onboarding path).
Login is native email/password via Garmin's SSO, the same flow Garmin
Connect Mobile uses. There is no official personal-use OAuth alternative.

Caveats worth knowing before relying on this:
  - If the account has MFA/2FA enabled, login() raises — this client does not
    implement an MFA prompt flow. Use an account/app-password without MFA,
    or extend make_client() with garminconnect's prompt_mfa callback.
  - Garmin's JSON field names are not officially documented and have shifted
    across API versions in the past; the field mapping lives in
    services/repository.py so a future drift only needs fixing in one place.

Raw access only: no field renaming here — that (and all Garmin-JSON-key
knowledge) lives in services/repository.py, same split as clients/sheets.py
and clients/notion.py.
"""

from __future__ import annotations

from services.config import Config

try:
    import garminconnect
except ImportError:  # pragma: no cover - exercised only if the dep isn't installed
    garminconnect = None


def make_client(config: Config):
    """None when Garmin isn't configured (blank email/password) or the
    dependency isn't installed — callers must handle that, not treat it as
    an error. Raises on a real login failure (bad credentials, MFA, network)."""
    if garminconnect is None or not config.garmin_email or not config.garmin_password:
        return None
    client = garminconnect.Garmin(config.garmin_email, config.garmin_password)
    client.login()
    return client


def get_daily_summary(client, d) -> dict:
    return client.get_stats(d.isoformat()) or {}


def get_sleep_data(client, d) -> dict:
    return client.get_sleep_data(d.isoformat()) or {}


def get_stress_data(client, d) -> dict:
    return client.get_stress_data(d.isoformat()) or {}


def get_hrv_data(client, d) -> dict:
    """Unverified against a live payload — field names in repository.py's
    extraction (hrvSummary.lastNightAvg) match garminconnect's documented
    /hrv-service/hrv/{date} shape, but should be confirmed with
    scripts/garmin_login_test.py before being fully trusted."""
    return client.get_hrv_data(d.isoformat()) or {}


def get_recent_activities(client, limit: int = 20) -> list[dict]:
    """Most recent `limit` activities, newest first (Garmin's own default sort)."""
    activities = client.get_activities(0, limit)
    return activities or []
