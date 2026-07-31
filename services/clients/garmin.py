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

import random
import time

from services.config import Config

try:
    import garminconnect
except ImportError:  # pragma: no cover - exercised only if the dep isn't installed
    garminconnect = None


class RateLimited(RuntimeError):
    """Garmin returned HTTP 429. Distinct from a generic failure because the
    correct response is different in kind: back off for hours, don't retry on
    the next page load. Raised out of this module rather than swallowed so
    services/repository.py can open its circuit breaker."""


_RETRY_ATTEMPTS = 3
_RETRY_BASE_SECONDS = 1.5


def _rate_limit_errors() -> tuple[type[BaseException], ...]:
    """garminconnect's 429 exception, when the dependency exposes one. Falls
    back to an empty tuple so a version without it degrades to the string
    sniff below rather than raising AttributeError at import time."""
    exc = getattr(garminconnect, "GarminConnectTooManyRequestsError", None)
    return (exc,) if isinstance(exc, type) else ()


def _is_rate_limit(exc: BaseException) -> bool:
    """429s reach us two ways: garminconnect's own typed exception, or a bare
    requests error whose text carries the status. The live failure observed
    2026-07-31 was the latter ("Mobile login returned 429"), so the string
    sniff is load-bearing, not belt-and-braces."""
    if _rate_limit_errors() and isinstance(exc, _rate_limit_errors()):
        return True
    text = str(exc).lower()
    return "429" in text or "too many requests" in text or "rate limit" in text


def _retrying(fn, *args, attempts: int = _RETRY_ATTEMPTS, **kwargs):
    """Calls fn, converting a rate-limit into RateLimited IMMEDIATELY.

    Deliberately does not retry a 429. A 429 means "stop calling", not "try
    again in a moment", and the right backoff is the hours-long circuit
    breaker in services/repository.py, not seconds of sleeping inside a page
    render. An earlier version retried three times with exponential backoff;
    against a throttled account that added several seconds of blocking sleep
    per call to every cold app start, for calls that were never going to
    succeed. Failing fast reaches the breaker sooner and keeps the page
    responsive.

    Genuinely transient failures (a dropped connection, a 5xx) DO get
    retried, with jitter so several syncs throttled together don't retry in
    lockstep."""
    for attempt in range(attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if _is_rate_limit(exc):
                raise RateLimited(str(exc)) from exc
            if attempt == attempts - 1:
                raise
            time.sleep(_RETRY_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 0.5))


def make_client(config: Config):
    """None when Garmin isn't configured (blank email/password) or the
    dependency isn't installed — callers must handle that, not treat it as
    an error. Raises on a real login failure (bad credentials, MFA, network)."""
    if garminconnect is None or not config.garmin_email or not config.garmin_password:
        return None
    client = garminconnect.Garmin(config.garmin_email, config.garmin_password)
    _retrying(client.login)
    return client


def get_daily_summary(client, d) -> dict:
    return _retrying(client.get_stats, d.isoformat()) or {}


def get_sleep_data(client, d) -> dict:
    """The whole sleep payload — dailySleepDTO plus the sleepLevels stage
    segments, sleepMovement, sleepHeartRate and sleepStress series. Callers
    take what they need; services/repository.py maps the fields."""
    return _retrying(client.get_sleep_data, d.isoformat()) or {}


def get_stress_data(client, d) -> dict:
    return _retrying(client.get_stress_data, d.isoformat()) or {}


def get_hrv_data(client, d) -> dict:
    """Unverified against a live payload — field names in repository.py's
    extraction (hrvSummary.lastNightAvg) match garminconnect's documented
    /hrv-service/hrv/{date} shape, but should be confirmed with
    scripts/garmin_login_test.py before being fully trusted."""
    return _retrying(client.get_hrv_data, d.isoformat()) or {}


def get_recent_activities(client, limit: int = 20) -> list[dict]:
    """Most recent `limit` activities, newest first (Garmin's own default sort)."""
    activities = _retrying(client.get_activities, 0, limit)
    return activities or []


def get_activity_hr_zones(client, activity_id) -> list[dict]:
    """Garmin's own per-activity time-in-heart-rate-zone summary.

    Fallback source for Edwards' load when the full sample series isn't
    available — note the zone boundaries are whatever the Garmin ACCOUNT is
    configured with, not the observed HRmax used elsewhere (see
    services/hr_load.py::seconds_in_zone_from_garmin_zones).

    Returns [] rather than raising when the endpoint is unavailable for an
    activity — plenty of activity types have no zone breakdown at all. A
    RateLimited is the one exception that still propagates: swallowing it
    would make a throttled account look like an account with no zone data,
    and the caller would keep calling.
    """
    try:
        return _retrying(client.get_activity_hr_in_timezones, activity_id) or []
    except RateLimited:
        raise
    except Exception:
        return []


def get_activity_details(client, activity_id, max_points: int = 2000) -> dict:
    """Full per-activity detail payload, including the sampled metric series
    that carries heart rate over time.

    max_points caps Garmin's own downsampling — 2000 points across a
    60-90 minute session is roughly one sample every 2-3 seconds, ample for
    zone bucketing and far cheaper than the raw series.

    Returns {} rather than raising: this is an unofficial API and a single
    activity failing must not take down a whole sync. RateLimited still
    propagates — see get_activity_hr_zones for why.
    """
    try:
        return _retrying(client.get_activity_details, activity_id, maxchart=max_points) or {}
    except RateLimited:
        raise
    except Exception:
        return {}
