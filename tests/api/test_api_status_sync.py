"""GET /api/status and POST /api/sync (rebuild Phase 2, milestone 5).

What it pins:
- a sync refuses unless the store names the engine as the background writer
  (rebuild rule 2), and then nothing reaches a device;
- the owner's rule: the first request of the caller's day syncs; while last
  night is missing a later request syncs again, at most once an hour; once
  it is in, nothing more that day; `force` syncs regardless;
- the run is stored under the caller's day (rule 3), with each step's
  result and the failed-week rule's;
- the status says which process writes, whether a sync is due (only while
  the engine writes), the Oura login without any token, and the notices in
  order: a dead login is an error, a failed step a caption.

Fakes only; no network, no device.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from healthapi.deps import get_repository, get_sync_runner  # noqa: E402
from healthapi.main import create_app  # noqa: E402
from services import background_writer as bw  # noqa: E402
from services import engine_sync, sync_policy  # noqa: E402

KEY = "test-engine-key"
TODAY = date(2026, 10, 19)


class StoreFake:
    """The config table, Metrics History's row for the caller's day, and the
    Oura login's state."""

    def __init__(self, writer=None, night_in=False, oura_dead=False, stored_run=None):
        self.config = {} if writer is None else {bw.CONFIG_KEY: writer}
        if stored_run is not None:
            self.config[engine_sync.STATUS_KEY] = json.dumps(stored_run)
        self.night_in, self.oura_dead = night_in, oura_dead
        self.offline = False

    def get_config_value(self, key):
        return self.config.get(key)

    def get_config_value_live(self, key):
        return self.config.get(key)

    def set_config(self, key, value, today=None):
        self.config[key] = value

    def get_metrics_history(self, start=None, end=None):
        if not self.night_in:
            return []
        return [{"date": start, "readiness_score": 71.0, "sleep_score": 80.0}]

    def get_phases(self):
        return []

    def oura_auth_status(self):
        return {"kind": "oauth", "state": "expired" if self.oura_dead else "valid",
                "needs_authorisation": self.oura_dead, "expires_at": "2026-11-01T00:00:00+00:00",
                "seconds_remaining": 1000.0, "oauth_configured": True, "scope": "daily",
                "can_refresh": True, "persist_error": None, "rejected": None}

    def datastore_built_at(self):
        return None


class RunnerFake:
    def __init__(self, skipped=None):
        self.days: list[date] = []
        self.skipped = skipped

    def run_now(self, today=None):
        self.days.append(today)
        return {"oura": (True, None), "garmin": (False, "429 Too Many Requests")}

    def skipped_for(self):
        return self.skipped

    def last_error(self):
        return None


def _client(monkeypatch, store, runner):
    monkeypatch.setenv("HEALTH_ENGINE_KEY", KEY)
    monkeypatch.delenv("HEALTH_PROBES", raising=False)
    app = create_app(startup=False)
    app.dependency_overrides[get_repository] = lambda: store
    app.dependency_overrides[get_sync_runner] = lambda: runner
    return TestClient(app)


def _headers(local: date = TODAY) -> dict:
    return {"X-Engine-Key": KEY, "X-Local-Date": local.isoformat()}


def _sync(monkeypatch, store, runner, local=TODAY, **body):
    with _client(monkeypatch, store, runner) as c:
        return c.post("/api/sync", headers=_headers(local), json=body or None)


def _status(monkeypatch, store, local=TODAY):
    with _client(monkeypatch, store, RunnerFake()) as c:
        r = c.get("/api/status", headers=_headers(local))
    assert r.status_code == 200, r.text
    return r.json()


def _run(day: date, minutes_ago: float) -> dict:
    at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return {"day": day.isoformat(), "at": at.isoformat(), "results": {}, "error": None}


# ── the writer ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("writer", [None, "streamlit", "both"])
def test_a_sync_refuses_unless_the_engine_is_the_writer(monkeypatch, writer):
    runner = RunnerFake()
    r = _sync(monkeypatch, StoreFake(writer=writer), runner)
    assert r.status_code == 409 and r.json() == {"error": "not_the_writer"}
    assert runner.days == [], "no device was asked"


def test_a_writer_switched_mid_request_stops_the_sync(monkeypatch):
    runner = RunnerFake(skipped="streamlit")
    r = _sync(monkeypatch, StoreFake(writer="engine"), runner)
    assert r.status_code == 409 and r.json() == {"error": "not_the_writer"}


# ── the owner's rule ─────────────────────────────────────────────────────────

def test_the_first_request_of_the_callers_day_syncs_and_stores_the_run(monkeypatch):
    store, runner = StoreFake(writer="engine"), RunnerFake()
    body = _sync(monkeypatch, store, runner).json()
    assert body["ran"] and body["reason"] == sync_policy.FIRST_OPEN
    assert runner.days == [TODAY]
    stored = json.loads(store.config[engine_sync.STATUS_KEY])
    assert stored["day"] == TODAY.isoformat()
    assert stored["results"]["garmin"] == [False, "429 Too Many Requests"]
    assert stored["results"]["failed_week"] == [True, None]


def test_a_request_at_half_past_midnight_in_berlin_syncs_the_berlin_day(monkeypatch):
    # 00:30 in Berlin is 22:30 UTC the day before; yesterday's run must not
    # read as today's.
    berlin_day = date.today() + timedelta(days=1)
    store = StoreFake(writer="engine", stored_run=_run(berlin_day - timedelta(days=1), 30))
    runner = RunnerFake()
    body = _sync(monkeypatch, store, runner, local=berlin_day).json()
    assert body["ran"] and body["reason"] == sync_policy.FIRST_OPEN
    assert runner.days == [berlin_day]


def test_once_last_night_is_in_nothing_more_that_day(monkeypatch):
    store = StoreFake(writer="engine", night_in=True, stored_run=_run(TODAY, 300))
    runner = RunnerFake()
    body = _sync(monkeypatch, store, runner).json()
    assert body == {"ran": False, "reason": None, "status": json.loads(
        store.config[engine_sync.STATUS_KEY])}
    assert runner.days == []


def test_while_last_night_is_missing_a_retry_waits_an_hour(monkeypatch):
    runner = RunnerFake()
    soon = StoreFake(writer="engine", stored_run=_run(TODAY, 20))
    assert not _sync(monkeypatch, soon, runner).json()["ran"]
    later = StoreFake(writer="engine", stored_run=_run(TODAY, sync_policy.RETRY_MINUTES + 1))
    body = _sync(monkeypatch, later, runner).json()
    assert body["ran"] and body["reason"] == sync_policy.LAST_NIGHT_MISSING
    assert runner.days == [TODAY]


def test_force_syncs_regardless(monkeypatch):
    store = StoreFake(writer="engine", night_in=True, stored_run=_run(TODAY, 5))
    runner = RunnerFake()
    body = _sync(monkeypatch, store, runner, force=True).json()
    assert body["ran"] and body["reason"] == "asked" and runner.days == [TODAY]


# ── the status ───────────────────────────────────────────────────────────────

def test_the_status_names_the_writer_and_no_sync_is_due_for_another_writer(monkeypatch):
    body = _status(monkeypatch, StoreFake())
    assert body["writer"] == bw.STREAMLIT and body["sync_due"] is None
    assert body["last_sync"] is None and body["notices"] == []
    assert body["offline"] is False


def test_the_status_says_a_sync_is_due_while_the_engine_writes(monkeypatch):
    body = _status(monkeypatch, StoreFake(writer="engine"))
    assert body["writer"] == bw.ENGINE and body["sync_due"] == sync_policy.FIRST_OPEN


def test_the_oura_login_is_described_without_a_token(monkeypatch):
    oura = _status(monkeypatch, StoreFake())["oura"]
    assert set(oura) == set(engine_sync.OURA_FIELDS)
    assert not any("token" in str(v) for v in oura.values())


def test_a_dead_login_is_an_error_and_a_failed_step_a_caption(monkeypatch):
    run = {**_run(TODAY, 10), "results": {"oura": [True, None],
                                          "garmin": [False, "429 Too Many Requests"]}}
    body = _status(monkeypatch, StoreFake(writer="engine", oura_dead=True, stored_run=run))
    assert body["notices"] == [{"level": "error", "code": sync_policy.OURA_UNAUTHORISED},
                               {"level": "caption", "code": sync_policy.GARMIN_UNAVAILABLE}]
    assert body["last_sync"]["results"]["garmin"] == [False, "429 Too Many Requests"]


def test_a_chain_that_failed_to_run_says_so(monkeypatch):
    run = {**_run(TODAY, 10), "error": "the store did not answer"}
    body = _status(monkeypatch, StoreFake(writer="engine", stored_run=run))
    assert body["notices"] == [{"level": "caption", "code": sync_policy.SYNC_FAILED_TO_RUN}]


def test_an_offline_snapshot_is_named_with_its_age(monkeypatch):
    store = StoreFake()
    store.offline = True
    store.datastore_built_at = lambda: "2026-10-18T06:00:00+00:00"
    body = _status(monkeypatch, store)
    assert body["offline"] and body["datastore_built_at"] == "2026-10-18T06:00:00+00:00"
