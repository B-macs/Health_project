"""Request and response models: the contract with the phone app.

shared/openapi.json is exported from these (python -m healthapi.export_openapi),
and the TypeScript types in app/src/generated come from that file. Never
hand-edit either; change a model here and export again.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class BuildInfo(BaseModel):
    version: str
    commit: str | None
    built: str | None


class CacheInfo(BaseModel):
    mode: str
    exists: bool
    age_s: float | None


class HealthOut(BaseModel):
    """Diagnostics only: no personal reading, ever."""
    status: str
    build: BuildInfo
    python: str
    server_tz: str | None
    server_local_date: date
    started_at: str | None
    cache_rebuilt: bool | None
    cache: CacheInfo
    timings: dict[str, float]


class ReadinessBand(BaseModel):
    """The words services/dashboard.readiness_meta gives a score. The phone
    shows them; it never maps a number to a band itself."""
    label: str
    header: str
    description: str


class ReadinessOut(BaseModel):
    date: date
    daily: float | None
    trend: float | None
    headline: float | None
    band: ReadinessBand
    model_version: int
    window_days: int


class ErrorOut(BaseModel):
    error: str
