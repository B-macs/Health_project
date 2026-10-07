"""Rebuild Phase 0: the engine API skeleton in api/healthapi.

What these pin, and why each matters before anything is deployed:
- Every route needs the Worker's shared key, and a server with no key set
  refuses rather than letting traffic through.
- The caller's day comes from X-Local-Date and the server clock is never the
  source of "today" (rebuild rule 3): Cloud Run runs on UTC.
- /api/readiness gives exactly the numbers the services/ chain gives, with the
  Home card's two windows (14 days for today, 60 for any other day).
- /api/health carries no personal field.
- The Oura probe cannot reach any code path that refreshes the Oura token:
  a refresh from the engine would break the hosted Streamlit app's login.
- shared/openapi.json is the current contract.

No network, no Notion, no Supabase: a fake Repository stands in through
FastAPI's dependency override, with synthetic readings.
"""

from __future__ import annotations

import ast
import tomllib
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from healthapi import export_openapi, settings  # noqa: E402
from healthapi.main import create_app  # noqa: E402
from healthapi.routes import readiness as readiness_route  # noqa: E402
from services import dashboard, readiness  # noqa: E402
from services.models import BiometricRecord  # noqa: E402

KEY = "test-engine-key"
TODAY = date(2026, 10, 7)


def _rows(end: date, days: int) -> list[BiometricRecord]:
    rows = []
    for i in range(days):
        d = end - timedelta(days=days - 1 - i)
        rows.append(BiometricRecord(
            date=d.isoformat(), hrv_ms=40.0 + i % 5, resting_heart_rate=55.0,
            sleep_duration_hours=7.0 + (i % 3) * 0.25,
            oura_hrv_balance=70.0 + i % 7, oura_recovery_index=80.0,
            oura_previous_night=75.0, oura_resting_heart_rate_score=85.0,
            oura_body_temperature=90.0, oura_previous_day_activity=65.0,
            oura_sleep_regularity=70.0, oura_activity_balance=72.0))
    return rows


class FakeRepository:
    def __init__(self):
        self.calls: list[tuple[int, date | None]] = []

    def get_biometric_rolling(self, days: int = 28, today: date | None = None):
        self.calls.append((days, today))
        return _rows(today or date.today(), days)


@pytest.fixture
def fake_repo():
    return FakeRepository()


@pytest.fixture
def client(monkeypatch, fake_repo):
    monkeypatch.setenv("HEALTH_ENGINE_KEY", KEY)
    monkeypatch.delenv("HEALTH_PROBES", raising=False)
    app = create_app(startup=False)
    app.dependency_overrides[readiness_route.get_repository] = lambda: fake_repo
    with TestClient(app) as c:
        yield c


def _get(client, path, key=KEY, local=TODAY):
    headers = {}
    if key is not None:
        headers["X-Engine-Key"] = key
    if local is not None:
        headers["X-Local-Date"] = local.isoformat()
    return client.get(path, headers=headers)


# ── the shared key ───────────────────────────────────────────────────────────

def test_no_key_is_refused(client):
    r = _get(client, "/api/health", key=None)
    assert r.status_code == 401 and r.json() == {"error": "unauthorized"}


def test_a_wrong_key_is_refused(client):
    assert _get(client, "/api/health", key="nope").status_code == 401


def test_a_server_without_a_key_refuses_everything(monkeypatch, fake_repo):
    monkeypatch.delenv("HEALTH_ENGINE_KEY", raising=False)
    with TestClient(create_app(startup=False)) as c:
        r = c.get("/api/health", headers={"X-Engine-Key": KEY})
    assert r.status_code == 503 and r.json() == {"error": "not_configured"}


def test_answers_are_never_cached(client):
    assert _get(client, "/api/health").headers["Cache-Control"] == "no-store"
    assert _get(client, "/api/health", key=None).headers["Cache-Control"] == "no-store"


def test_no_docs_route_publishes_the_engine(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert _get(client, path).status_code == 404


# ── /api/health ──────────────────────────────────────────────────────────────

def test_health_carries_no_personal_field(client):
    r = _get(client, "/api/health")
    assert r.status_code == 200
    assert set(r.json()) == {"status", "build", "python", "server_tz", "server_local_date",
                             "started_at", "cache_rebuilt", "cache", "timings"}


# ── /api/readiness ───────────────────────────────────────────────────────────

def test_readiness_needs_the_callers_day(client):
    r = _get(client, f"/api/readiness?date={TODAY}", local=None)
    assert r.status_code == 400 and r.json() == {"error": "x_local_date_missing"}
    bad = client.get(f"/api/readiness?date={TODAY}",
                     headers={"X-Engine-Key": KEY, "X-Local-Date": "07/10/2026"})
    assert bad.status_code == 400 and bad.json() == {"error": "x_local_date_invalid"}


def test_today_uses_the_14_day_window_anchored_on_the_callers_day(client, fake_repo):
    # A caller whose day is NOT the server's: the server must use the caller's.
    caller_day = date(2031, 1, 2)
    r = _get(client, f"/api/readiness?date={caller_day}", local=caller_day)
    assert r.status_code == 200
    assert fake_repo.calls == [(60, caller_day), (14, caller_day)]
    assert r.json()["window_days"] == 14


def test_another_day_uses_the_60_day_window(client, fake_repo):
    day = TODAY - timedelta(days=3)
    r = _get(client, f"/api/readiness?date={day}")
    assert fake_repo.calls == [(60, TODAY)]
    assert r.json()["window_days"] == 60


def test_readiness_equals_the_service_chain(client):
    day = TODAY - timedelta(days=1)
    body = _get(client, f"/api/readiness?date={day}").json()
    rows_60 = [asdict(r) for r in _rows(TODAY, 60)]
    daily = readiness.compute_readiness(for_date=day, bio_rows=rows_60)
    trend = readiness.compute_readiness_trend(day, rows_60)
    assert body["daily"] == daily and body["trend"] == trend
    assert body["headline"] == daily
    _c, _v, label, header, description, _ = dashboard.readiness_meta(daily)
    assert body["band"] == {"label": label, "header": header, "description": description}
    assert body["model_version"] == readiness.MODEL_VERSION


def test_today_readiness_equals_the_home_cards_today_path(client):
    body = _get(client, f"/api/readiness?date={TODAY}").json()
    rows_14 = [asdict(r) for r in _rows(TODAY, 14)]
    # today.py:today_readiness_raw, with the caller's day in place of the clock
    assert body["daily"] == readiness.compute_readiness(for_date=TODAY, bio_rows=rows_14)


def test_an_unmeasured_day_has_no_score_and_says_so(client):
    future = TODAY + timedelta(days=5)        # no row: nothing was measured
    body = _get(client, f"/api/readiness?date={future}").json()
    assert body["daily"] is None and body["trend"] is None and body["headline"] is None
    assert body["band"]["label"] == dashboard.readiness_meta(None)[2]


# ── the probes ───────────────────────────────────────────────────────────────

_PROBES = Path(__file__).resolve().parents[2] / "api" / "healthapi" / "routes" / "probes.py"
_REFRESH_PATHS = {"_oc", "_refresh_oura_token", "refresh_access_token", "_load_oura_token",
                  "_store_oura_token", "run_home_syncs", "sync_oura_all",
                  "sync_oura_all_if_due", "fetch_oura_history", "BackgroundSyncRunner"}


def test_the_oura_probe_cannot_reach_a_token_refresh():
    tree = ast.parse(_PROBES.read_text(encoding="utf-8"))
    used = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    used |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    used |= {a.name.split(".")[-1] for n in ast.walk(tree)
             if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    assert not (used & _REFRESH_PATHS), used & _REFRESH_PATHS


def test_probes_are_off_by_default(client):
    assert _get(client, "/api/probe/oura").status_code == 404


def test_probes_turn_on_only_with_the_setting(monkeypatch):
    monkeypatch.setenv("HEALTH_ENGINE_KEY", KEY)
    monkeypatch.setenv("HEALTH_PROBES", "1")
    with TestClient(create_app(startup=False)) as c:
        # The routes exist now: without the caller's day they ask for it,
        # where a missing route would answer 404.
        oura_r = c.get("/api/probe/oura", headers={"X-Engine-Key": KEY})
        garmin_r = c.post("/api/probe/garmin", headers={"X-Engine-Key": KEY},
                          json={"confirm": "owner-approved"})
    assert oura_r.status_code == 400 and garmin_r.status_code == 400


def test_the_garmin_probe_needs_the_owners_confirmation(monkeypatch):
    monkeypatch.setenv("HEALTH_ENGINE_KEY", KEY)
    monkeypatch.setenv("HEALTH_PROBES", "1")
    with TestClient(create_app(startup=False)) as c:
        r = c.post("/api/probe/garmin", json={"confirm": "yes"},
                   headers={"X-Engine-Key": KEY, "X-Local-Date": TODAY.isoformat()})
    assert r.status_code == 400 and r.json() == {"error": "confirm_missing"}


# ── settings ─────────────────────────────────────────────────────────────────

def test_the_secrets_file_keeps_only_what_load_config_reads(tmp_path):
    path = tmp_path / "secrets.toml"
    path.write_text(
        'NOTION_API_KEY = "x"\nGARMIN_EMAIL = "y"\n'
        '[voxplot_supabase]\nurl = "u"\n'
        '[google_service_account]\ntype = "service_account"\n', encoding="utf-8")
    out = settings.secrets_overrides(path)
    assert out == {"NOTION_API_KEY": "x", "GARMIN_EMAIL": "y",
                   "google_service_account": {"type": "service_account"}}
    assert tomllib.loads(path.read_text(encoding="utf-8"))   # the fixture is valid TOML


def test_a_missing_secrets_file_falls_back_to_the_environment(tmp_path):
    assert settings.secrets_overrides(tmp_path / "absent.toml") == {}


# ── the contract ─────────────────────────────────────────────────────────────

def test_shared_openapi_json_is_current():
    current = export_openapi.OPENAPI_PATH.read_text(encoding="utf-8")
    assert current == export_openapi.render(), \
        "shared/openapi.json is stale: run PYTHONPATH=api python -m healthapi.export_openapi"


def test_the_contract_does_not_include_the_probes():
    assert "/api/probe/oura" not in export_openapi.render()
