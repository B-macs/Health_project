"""The sync rehearsal (rebuild Phase 9, switch plan item 5).

The rehearsal runs the engine's REAL sync chain over made-up data with every
device and store call faked (api/healthapi/rehearsal.py), and its driver
(scripts/sync_rehearsal.py) times it on its own Cloud Run service. These tests
run the same app in this process over a short made-up history: every step of
the chain must finish, the Oura login must be refreshed through the fake, the
day's rows must land in the made-up store, nothing may leave the machine, and
every real client must be put back afterwards. Made-up data only.
"""

from __future__ import annotations

import socket
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from healthapi import rehearsal as rh
from services import backup
from services.clients import garmin as garmin_client
from services.clients import local_cache
from services.clients import oura as oura_client

from scripts import switch_check as sc
from scripts import sync_rehearsal as drv

ROOT = Path(__file__).resolve().parents[2]

#: A Tuesday; the day before is one of the block's gym days.
TODAY = date(2026, 10, 20)
HEADERS = {"X-Engine-Key": rh.KEY, "X-Local-Date": TODAY.isoformat()}
STEPS = {"oura", "garmin", "garmin_activities", "blend", "session_hr", "metrics_history",
         "sleep_fusion", "backup", "supabase_mirror", "failed_week", "weekly_rollup"}


@pytest.fixture
def rehearsal_app(monkeypatch):
    monkeypatch.delenv("HEALTH_PROBES", raising=False)
    holder: dict = {}
    with rh.no_network():
        try:
            yield TestClient(rh.build_app(holder), raise_server_exceptions=False), holder
        finally:
            if "rehearsal" in holder:
                holder["rehearsal"].close()


def _seed(client, **extra):
    body = {"oura_days": 14, "garmin_days": 10, "block_weeks": 2, **extra}
    r = client.post("/rehearsal/seed", json=body, headers=HEADERS)
    assert r.status_code == 200, r.text
    return r.json()


def test_the_real_chain_runs_over_made_up_data(rehearsal_app):
    client, holder = rehearsal_app
    seeded = _seed(client, device_latency_s=0.001, garmin_login_latency_s=0.002,
                   store_latency_s=0.001)
    assert seeded["rows"]["oura_sleep_periods"] > 0 and seeded["rows"]["training_sessions"] > 0
    assert seeded["device_calls_total"] == 0, "the seed's calls are counted apart"
    # The chosen waits are set for the timed run only, after the seed.
    assert (seeded["device_latency_s"], seeded["garmin_login_latency_s"],
            seeded["store_latency_s"]) == (0.001, 0.002, 0.001)
    assert seeded["seed_seconds"] is not None and seeded["seed_store_calls"] > 0

    r = client.post("/api/sync", json={"force": True}, headers=HEADERS)
    assert r.status_code == 200, r.text
    answer = r.json()
    assert answer["ran"] is True and answer["status"]["error"] is None
    results = answer["status"]["results"]
    assert set(results) == STEPS
    assert all(ok for ok, _err in results.values()), results

    report = client.get("/rehearsal/report", headers=HEADERS).json()
    assert report["oura_refreshes"] == 1, "the login due a refresh was refreshed, once"
    assert report["device_calls"]["oura.sleep"] == 1
    assert report["device_calls"]["garmin.get_sleep_data"] >= 1
    assert report["device_calls"]["garmin.get_activity_details"] >= 1, \
        "yesterday's session met its watch record"
    assert report["store_calls"] > 0 and report["network_blocked"] == 0
    assert report["backups_saved"] == [backup.object_name(TODAY)]

    store = holder["rehearsal"].store.tables
    day = TODAY.isoformat()
    assert any(str(r.get("date")) == day for r in store["metrics_history"])
    assert any(str(r.get("date")) == day for r in store["garmin_daily"])
    assert any(str(r.get("day")) == day for r in store["oura_sleep_periods"]), "last night arrived"


def test_a_sync_before_the_seed_is_refused(rehearsal_app):
    client, _holder = rehearsal_app
    r = client.post("/api/sync", json={"force": True}, headers=HEADERS)
    assert r.status_code == 409 and r.json() == {"error": "not_seeded"}


def test_no_network_refuses_every_outgoing_connection():
    real = socket.getaddrinfo
    before = len(rh.BLOCKED)
    with rh.no_network():
        with pytest.raises(rh.NetworkBlocked):
            socket.getaddrinfo("example.com", 443)
        with pytest.raises(rh.NetworkBlocked):
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("93.184.215.14", 443))
        assert socket.getaddrinfo("127.0.0.1", 80)
    assert socket.getaddrinfo is real, "put back"
    assert len(rh.BLOCKED) == before + 2


def test_every_real_client_is_put_back(tmp_path):
    originals = (oura_client.get_collection, oura_client.refresh_access_token,
                 oura_client.make_client, garmin_client.make_client, backup.Storage,
                 local_cache._DEFAULT_PATH)
    rehearsal = rh.Rehearsal(TODAY, oura_days=7, garmin_days=7, work_dir=tmp_path)
    assert oura_client.get_collection == rehearsal.devices.oura.get_collection
    assert local_cache._DEFAULT_PATH == tmp_path / "sync_state.json"
    rehearsal.close()
    assert (oura_client.get_collection, oura_client.refresh_access_token,
            oura_client.make_client, garmin_client.make_client, backup.Storage,
            local_cache._DEFAULT_PATH) == originals


def test_the_config_names_nothing_real():
    config = rh.rehearsal_config("x.db")
    assert config.supabase_url.endswith(".invalid")
    assert config.garmin_email.endswith(".invalid")
    assert config.background_process == "engine" and config.system_of_record == "supabase"


def test_the_service_refuses_the_network_before_it_serves():
    """The service's module enters no_network on import (checked in a fresh
    process: in this one it would stay on for every later test)."""
    code = ("import socket, healthapi.rehearsal_service as s\n"
            "try:\n    socket.getaddrinfo('example.com', 443)\nexcept ConnectionError:\n"
            "    print('refused')\nelse:\n    print('reached')\n")
    env_path = f"{ROOT}{';' if sys.platform == 'win32' else ':'}{ROOT / 'api'}"
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          env={**_clean_env(), "PYTHONPATH": env_path}, cwd=ROOT, timeout=120)
    assert proc.stdout.strip().splitlines()[-1] == "refused", proc.stderr[-500:]


def _clean_env() -> dict:
    import os
    return {k: v for k, v in os.environ.items() if not k.startswith(("HEALTH_", "SUPABASE"))}


def test_the_engine_never_imports_the_rehearsal():
    import ast
    for path in (ROOT / "api" / "healthapi").rglob("*.py"):
        if path.name.startswith("rehearsal"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [a.name for a in node.names]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            else:
                continue
            assert not any("rehearsal" in n for n in names), path.name


# ─── the driver ─────────────────────────────────────────────────────────────

def test_the_limit_is_the_workers_sync_budget():
    assert drv.worker_limit_seconds() == 280
    assert drv.worker_limit_seconds("export const SYNC_TIMEOUT_MS = 120_000") == 120


def _answer(**results):
    return {"ran": True, "status": {"results": {k: [v, None if v else "boom"]
                                                for k, v in results.items()},
                                    "error": None}}


def _summary(status_code=200, answer=None, report=None):
    return drv.summarize(where="cloud_run", status_code=status_code,
                         answer=answer if answer is not None else _answer(oura=True, garmin=True),
                         seconds=80.0, limit_seconds=280.0,
                         report=report if report is not None else {"network_blocked": 0},
                         assumptions={"device_latency_s": 2.0})


def test_a_record_is_ok_only_when_every_step_finished():
    assert _summary()["ok"] is True
    failed = _summary(answer=_answer(oura=True, garmin=False))
    assert failed["ok"] is False and "garmin (boom)" in failed["error"]
    assert _summary(status_code=500, answer={"error": "internal"})["ok"] is False
    assert _summary(answer={"ran": False, "status": {}})["ok"] is False
    tried = _summary(report={"network_blocked": 2})
    assert tried["ok"] is False and "outgoing" in tried["error"]


def test_a_cloud_record_passes_the_switch_check(tmp_path):
    record = drv.write_record(_summary(), tmp_path / "rehearsal.json")
    assert sc.check_rehearsal(record)["ok"] is True
    local = dict(_summary(), where="local")
    assert sc.check_rehearsal(drv.write_record(local, tmp_path / "r2.json"))["ok"] is False
    assert drv.LOCAL_RECORD != drv.RECORD, "a local look never overwrites the checked record"


_DESCRIBED = {
    "spec": {"template": {
        "metadata": {"annotations": {"run.googleapis.com/execution-environment": "gen2",
                                     "run.googleapis.com/startup-cpu-boost": "true"}},
        "spec": {"timeoutSeconds": 900, "containerConcurrency": 80,
                 "serviceAccountName": "health-engine@made-up-project.iam.gserviceaccount.com",
                 "containers": [{
            "image": "region-docker.pkg.dev/made-up/repo/health-engine@sha256:0123456789abcdef",
            "resources": {"limits": {"cpu": "1000m", "memory": "1Gi"}},
            "env": [{"name": "MADE_UP", "value": "never copied"}]}]}}},
    "status": {"latestReadyRevisionName": "health-engine-00099-abc"},
}


def test_the_service_copies_the_engines_resources_and_nothing_else():
    settings = drv.engine_settings(_DESCRIBED)
    assert settings["memory"] == "1Gi" and settings["timeout_s"] == 900
    args = drv.deploy_args(settings)
    joined = " ".join(args)
    assert "--no-allow-unauthenticated" in args and "--max-instances=1" in args
    assert "healthapi.rehearsal_service:app" in joined
    assert "--set-env-vars=TZ=UTC" in args and "MADE_UP" not in joined
    assert not any(a.startswith(("--set-secrets", "--update-secrets", "--allow-unauthenticated",
                                 "--update-env-vars")) for a in args)
    accounts = [a for a in args if a.startswith("--service-account=")]
    assert accounts == ["--service-account=health-rehearsal@made-up-project.iam.gserviceaccount.com"],         "its own identity: never the engine's, never the project's default"
    assert args[2] == drv.SERVICE != drv.ENGINE_SERVICE, "never the engine's own service"
