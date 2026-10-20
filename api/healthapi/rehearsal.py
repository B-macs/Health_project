"""The sync rehearsal (rebuild Phase 9; item 5 of docs/rebuild/switch_plan.md).

The engine's own app and its REAL sync chain (POST /api/sync: Repository.
run_home_syncs, then the failed-week rule and the weekly rollup), over
made-up data, with every device and store call faked. It answers one question
before the switch-over: does the chain finish inside the time the Worker
allows a sync (worker/src/index.ts SYNC_TIMEOUT_MS, 280 s)?

NEVER THE REAL ENGINE, NEVER THE REAL STORE. On Cloud Run it is a separate
service, deployed with no secret at all (scripts/sync_rehearsal.py), and this
module never reads one: its Config is built here, its store is
services/memory_store.MemoryStore and its devices are
healthapi.rehearsal_devices. On top of that, every outgoing connection and
name lookup the process tries is refused (no_network), so a call that got
past the fakes fails its step instead of reaching a real service.

TWO REQUESTS. POST /rehearsal/seed builds the made-up history with the
devices' clock at yesterday and no latency (not timed): two years of ring
nights, four months of watch days, the block's sessions, check-ins,
heart-rate matches, the blend, the history, the fused nights and the
failed-week verdicts and rollup, all through the real sync and save code.
It ends as a real morning starts: every step due, the devices' clock at
today, the chosen latencies set, and an Oura login due a refresh. POST
/api/sync with force true is then the timed run; GET /rehearsal/report says
what it called.

The service starts from healthapi.rehearsal_service; this module has no side
effect on import, so the tests run the same code in-process.
"""

from __future__ import annotations

import os
import random
import socket
import tempfile
import threading
import time
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from services import (background_writer, backup, metrics, record_cache, sessions,
                      training_session, week_repeat)
from services import checkin_form as cf
from services.background_sync import BackgroundSyncRunner
from services.clients import garmin as garmin_client
from services.clients import local_cache
from services.clients import oura as oura_client
from services.config import Config
from services.memory_store import MemoryStore
from services.repository import Repository

from .deps import get_repository, get_sync_runner, local_today
from .main import create_app
from .rehearsal_devices import GYM_MINUTES, GYM_START, UTC, Devices, Scenario
from .schemas_training import SessionSaveIn

#: The engine key this app asks for. Made up, and guarding nothing real: on
#: Cloud Run the service takes no request without the owner's own identity.
KEY = "rehearsal"
#: The block the made-up athlete trains (the 12-week block).
PHASE = 5


# ─── no network ─────────────────────────────────────────────────────────────

class NetworkBlocked(ConnectionError):
    """The rehearsal tried to reach another machine."""


#: Every refused attempt, by address (the report counts them).
BLOCKED: list[str] = []


def _local_host(host) -> bool:
    if isinstance(host, bytes):
        host = host.decode(errors="replace")
    host = str(host or "")
    return host in ("", "localhost", "0.0.0.0", "::", "::1") or host.startswith("127.")


@contextmanager
def no_network():
    """Refuse every outgoing connection and every name lookup but the
    machine's own while the block runs (the service: for its whole life)."""
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo
    unix = getattr(socket, "AF_UNIX", None)

    def _allowed(sock, address) -> bool:
        if unix is not None and sock.family == unix:
            return True
        return _local_host(address[0] if isinstance(address, tuple) else address)

    def _refuse(where):
        BLOCKED.append(str(where))
        raise NetworkBlocked(f"rehearsal: no network ({where})")

    def connect(sock, address):
        if not _allowed(sock, address):
            _refuse(address)
        return real_connect(sock, address)

    def connect_ex(sock, address):
        if not _allowed(sock, address):
            _refuse(address)
        return real_connect_ex(sock, address)

    def getaddrinfo(host, *args, **kwargs):
        if not _local_host(host):
            _refuse(host)
        return real_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
    socket.getaddrinfo = getaddrinfo
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex = real_connect, real_connect_ex
        socket.getaddrinfo = real_getaddrinfo


# ─── the fakes, in place of the real clients ────────────────────────────────

class MemoryStorage:
    """backup.Storage over a dict: the bucket of the daily copy. Each call
    waits one store round trip."""

    def __init__(self, store: MemoryStore):
        self._store = store
        self.saved: dict[str, bytes] = {}

    def ensure_bucket(self) -> None:
        self._store.round_trip()

    def upload(self, name: str, data: bytes) -> None:
        self._store.round_trip()
        self.saved[name] = data

    def objects(self) -> list[dict]:
        self._store.round_trip()
        return [{"name": n} for n in sorted(self.saved)]

    def names(self) -> list[str]:
        return [o["name"] for o in self.objects()]

    def download(self, name: str) -> bytes:
        self._store.round_trip()
        return self.saved[name]

    def delete(self, names: list[str]) -> None:
        if names:
            self._store.round_trip()
            for n in names:
                self.saved.pop(n, None)


@contextmanager
def fakes_installed(devices: Devices, storage: MemoryStorage):
    """The real clients' entry points pointed at the fakes, and put back after."""
    saved = [(oura_client, "get_collection"), (oura_client, "refresh_access_token"),
             (oura_client, "make_client"), (garmin_client, "make_client"),
             (backup, "Storage")]
    originals = [(module, name, getattr(module, name)) for module, name in saved]

    def garmin_login(_config):
        devices.garmin.login()
        return devices.garmin

    oura_client.get_collection = devices.oura.get_collection
    oura_client.refresh_access_token = devices.oura.refresh_access_token
    oura_client.make_client = lambda _config: None
    garmin_client.make_client = garmin_login
    backup.Storage = lambda _store, *args, **kwargs: storage
    try:
        yield
    finally:
        for module, name, value in originals:
            setattr(module, name, value)


@contextmanager
def local_cache_at(path: Path):
    """This process's state file (markers, the Oura login's local copy) in the
    rehearsal's own folder, never beside the code."""
    real = local_cache._DEFAULT_PATH
    local_cache._DEFAULT_PATH = path
    try:
        yield
    finally:
        local_cache._DEFAULT_PATH = real


def rehearsal_config(path: str) -> Config:
    """A Supabase-record engine Config with nothing real in it: the store is
    injected (Rehearsal.repository), the address below is never contacted,
    and the device credentials are placeholders the fakes ignore."""
    return Config(
        notion_api_key="", notion_db_readiness="record:readiness",
        notion_db_training="record:training", notion_db_config="record:config",
        google_sheets_id="", google_service_account={},
        garmin_email="rehearsal@example.invalid", garmin_password="made-up",
        oura_client_id="rehearsal", oura_client_secret="made-up",
        datastore_path=path, datastore_mode="cache",
        supabase_url="https://rehearsal.invalid", supabase_secret_key="made-up",
        timezone="UTC", system_of_record="supabase", background_process="engine")


# ─── one rehearsal ──────────────────────────────────────────────────────────

class Rehearsal:
    """The made-up store, devices, Config and sync runner of one rehearsal.
    close() puts back every client and file path it replaced."""

    def __init__(self, today: date, oura_days: int = 700, garmin_days: int = 110,
                 block_weeks: int = 9, work_dir: Path | None = None):
        self.scenario = Scenario(today, oura_days=oura_days, garmin_days=garmin_days,
                                 block_weeks=block_weeks)
        self.work_dir = Path(work_dir or tempfile.mkdtemp(prefix="rehearsal_"))
        self.store = MemoryStore()
        self.storage = MemoryStorage(self.store)
        self.devices = Devices(self.scenario, until=today - timedelta(days=1))
        copy = record_cache.empty_copy(str(self.work_dir / "record_cache.db"))
        self.config = rehearsal_config(copy)
        self.runner = BackgroundSyncRunner(self.config, repository_factory=self.repository)
        self._stack = ExitStack()
        self._stack.enter_context(local_cache_at(self.work_dir / "sync_state.json"))
        self._stack.enter_context(fakes_installed(self.devices, self.storage))
        self._stack.callback(record_cache.forget, copy)
        self.seed_seconds: float | None = None
        self.seed_stages: dict[str, float] = {}
        self.seed_device_calls = 0
        self.seed_store_calls = 0
        self.device_latency_s = 0.0
        self.login_latency_s = 0.0
        self.store_latency_s = 0.0
        self.last_sync_seconds: float | None = None

    def close(self) -> None:
        self._stack.close()

    def repository(self, _config: Config | None = None) -> Repository:
        """A Repository over the made-up store: one per request and one per
        sync run, never shared between threads (Key Rule 12)."""
        repo = Repository(self.config)
        repo._supabase_store_obj = self.store
        return repo

    # ── the made-up history ────────────────────────────────────────────────
    @staticmethod
    def _token(**lifetime) -> dict:
        return {"access_token": "made-up-access-0", "refresh_token": "made-up-refresh-0",
                "expires_in": int(timedelta(**lifetime).total_seconds()),
                "token_type": "bearer", "scope": "daily heartrate"}

    @staticmethod
    def _sides(ex: dict) -> dict:
        kind = ex.get("type")
        if kind == "reps":
            side = {"reps": int(ex.get("reps") or ex.get("rep_min") or 10),
                    "weight_kg": ex.get("weight_kg")}
        elif kind in ("hold", "hold_reps"):
            side = {"seconds": float(ex.get("hold_seconds") or 30)}
            if kind == "hold_reps":
                side["reps"] = int(ex.get("reps") or 5)
        else:
            side = {"seconds": float((ex.get("duration_minutes") or 5) * 60)}
        return {"right": side, "left": dict(side) if ex.get("laterality") == "unilateral" else None}

    def _session_body(self, day: date, plan_day: dict) -> dict:
        clock = datetime.combine(day, GYM_START, UTC) + timedelta(minutes=5)
        exercises = []
        for i, ex in enumerate(plan_day.get("exercises") or []):
            raw = []
            for n in range(1, int(ex.get("sets") or 1) + 1):
                clock += timedelta(seconds=75)
                raw.append({"set_num": n, "completed_at": clock.isoformat(), **self._sides(ex)})
            exercises.append({"exercise_id": f"rehearsal-{day}-{i}", "exercise": ex,
                              "raw_sets": raw})
        return SessionSaveIn(session_id=f"rehearsal-{day}", date=day, kind="plan",
                             duration_minutes=GYM_MINUTES, session_rpe=7,
                             exercises=exercises).model_dump()

    def _seed_sessions(self, repo: Repository, last: date) -> list[date]:
        phase = repo.get_phases()[0]
        plan = sessions.calendar_plan(phase)
        logged, day = [], self.scenario.phase_start
        while day <= last:
            plan_day = plan.get((day - self.scenario.phase_start).days + 1) or {}
            if self.scenario.trains_on(day) and plan_day.get("is_gym_session"):
                training_session.save(repo, self._session_body(day, plan_day), day)
                logged.append(day)
            day += timedelta(days=1)
        return logged

    @staticmethod
    def _seed_checkins(repo: Repository, last: date, days: int = 45) -> None:
        for back in range(days):
            day = last - timedelta(days=back)
            if random.Random(f"checkin|{day}").random() < 0.9:
                cf.submit(repo, day, day, dict(cf.FORM_DEFAULTS), opened_entry=False)

    @staticmethod
    def _clear_step_markers() -> None:
        """Every step due, as on a morning after yesterday's sync. The
        heart-rate catch-up's weekly markers stay: a real morning has them."""
        state = local_cache.read()
        local_cache.update({k: None for k in state
                            if k.endswith(("_last_synced", "_last_attempted"))
                            and not k.startswith("session_hr_catch_up_")})

    def seed(self, device_latency_s: float = 0.0, store_latency_s: float = 0.0,
             login_latency_s: float = 0.0) -> None:
        """Build the history through the real code, then set the morning."""
        t0 = time.perf_counter()
        sc = self.scenario
        yesterday = sc.today - timedelta(days=1)
        repo = self.repository()
        stages: dict[str, float] = {}

        def stage(name, work):
            started = time.perf_counter()
            result = work()
            stages[name] = round(time.perf_counter() - started, 2)
            return result

        def setup():
            repo.set_config(background_writer.CONFIG_KEY, background_writer.ENGINE, today=yesterday)
            repo.set_config("current_stage", str(sessions.PHASE_META[PHASE]["stage"]), today=yesterday)
            repo.set_config("plan_start_date", sc.phase_start.isoformat(), today=yesterday)
            repo.set_phases([sessions.build_phase(PHASE, sc.phase_start)], today=yesterday)
            repo.save_oura_oauth_token(self._token(days=30), today=yesterday)

        def heart_rate():
            # As the routine sync and its weekly catch-up left it: every
            # session of the last 35 days but the last two days' asked.
            for day in logged:
                if 2 <= (sc.today - day).days <= 35:
                    repo.sync_session_hr_for_date(day)
                    repo.mark_synced(f"session_hr_catch_up_{day.isoformat()}")

        stage("setup", setup)
        stage("oura", lambda: repo.sync_oura_all(days=sc.oura_days, today=yesterday))
        stage("garmin_daily", lambda: repo.sync_garmin_daily(days=sc.garmin_days, today=yesterday,
                                                             force=True))
        stage("garmin_activities", lambda: repo.sync_garmin_activities(limit=40))
        logged = stage("sessions", lambda: self._seed_sessions(repo, yesterday))
        stage("checkins", lambda: self._seed_checkins(repo, yesterday))
        stage("session_hr", heart_rate)
        stage("blend", lambda: repo.sync_biometric_blend(days=sc.garmin_days, today=yesterday))
        stage("metrics_history", lambda: repo.sync_metrics_history(
            days=min(130, sc.oura_days), today=yesterday))
        stage("sleep_fusion", lambda: repo.sync_sleep_fusion(days=sc.oura_days, today=yesterday))
        stage("failed_week", lambda: week_repeat.store_failed_week_rule(
            repo, repo.get_phases(), yesterday))
        stage("weekly_rollup", lambda: metrics.sync_weekly_rollup(repo, today=yesterday))
        # The morning: every step due, last night on the devices, the chosen
        # latencies, and an Oura login that has to be refreshed.
        self._clear_step_markers()
        repo.save_oura_oauth_token(self._token(hours=12), today=yesterday)
        self.seed_device_calls = self.devices.total_calls()
        self.seed_store_calls = self.store.round_trips
        self.devices.calls.clear()
        self.store.round_trips = 0
        self.devices.until = sc.today
        self.devices.latency_s = self.device_latency_s = float(device_latency_s)
        self.devices.login_latency_s = self.login_latency_s = float(login_latency_s)
        self.store.latency_s = self.store_latency_s = float(store_latency_s)
        self.seed_stages = stages
        self.seed_seconds = round(time.perf_counter() - t0, 2)

    def report(self) -> dict:
        return {
            "today": self.scenario.today.isoformat(),
            "made_up_history": {"oura_days": self.scenario.oura_days,
                                "garmin_days": self.scenario.garmin_days,
                                "block_weeks": self.scenario.block_weeks,
                                "phase_start": self.scenario.phase_start.isoformat()},
            "rows": {t: len(rows) for t, rows in sorted(self.store.tables.items())},
            "seed_seconds": self.seed_seconds,
            "seed_stages": self.seed_stages,
            "seed_device_calls": self.seed_device_calls,
            "seed_store_calls": self.seed_store_calls,
            "device_latency_s": self.device_latency_s,
            "garmin_login_latency_s": self.login_latency_s,
            "store_latency_s": self.store_latency_s,
            "device_calls": dict(sorted(self.devices.calls.items())),
            "device_calls_total": self.devices.total_calls(),
            "store_calls": self.store.round_trips,
            "oura_refreshes": self.devices.oura.refreshes,
            "backups_saved": sorted(self.storage.saved),
            "network_blocked": len(BLOCKED),
            "last_sync_seconds": self.last_sync_seconds,
        }


# ─── the app ────────────────────────────────────────────────────────────────

class SeedIn(BaseModel):
    oura_days: int = Field(default=700, ge=7, le=1200)
    garmin_days: int = Field(default=110, ge=7, le=400)
    block_weeks: int = Field(default=9, ge=1, le=11)
    #: What each device call and each store call waits in the timed run.
    device_latency_s: float = Field(default=0.0, ge=0, le=10)
    garmin_login_latency_s: float = Field(default=0.0, ge=0, le=60)
    store_latency_s: float = Field(default=0.0, ge=0, le=5)


def build_app(holder: dict | None = None) -> FastAPI:
    """The engine's app with its store and devices made up. `holder` keeps
    the one Rehearsal (the tests pass their own and close it)."""
    os.environ["HEALTH_ENGINE_KEY"] = KEY
    holder = holder if holder is not None else {}
    lock = threading.Lock()
    app = create_app(startup=False, with_probes=False)

    def current() -> Rehearsal:
        if "rehearsal" not in holder:
            raise HTTPException(status_code=409, detail="not_seeded")
        return holder["rehearsal"]

    app.dependency_overrides[get_repository] = lambda: current().repository()
    app.dependency_overrides[get_sync_runner] = lambda: current().runner

    @app.middleware("http")
    async def _time_the_sync(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        if request.url.path == "/api/sync" and "rehearsal" in holder:
            holder["rehearsal"].last_sync_seconds = round(time.perf_counter() - t0, 2)
        return response

    @app.post("/rehearsal/seed")
    def seed(body: SeedIn = Body(default_factory=SeedIn),
             today: date = Depends(local_today)) -> dict:
        with lock:
            if "rehearsal" not in holder:
                rehearsal = Rehearsal(today, oura_days=body.oura_days,
                                      garmin_days=body.garmin_days,
                                      block_weeks=body.block_weeks)
                try:
                    rehearsal.seed(body.device_latency_s, body.store_latency_s,
                                   body.garmin_login_latency_s)
                except Exception as exc:
                    rehearsal.close()
                    # Made-up data only, so the cause may be said in full.
                    raise HTTPException(status_code=500,
                                        detail=f"seed_failed: {type(exc).__name__}: {exc}") from exc
                holder["rehearsal"] = rehearsal
        return current().report()

    @app.get("/rehearsal/report")
    def report() -> dict:
        return current().report()

    return app
