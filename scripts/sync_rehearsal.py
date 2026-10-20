# -*- coding: utf-8 -*-
"""The sync rehearsal's driver (rebuild Phase 9; item 5 of docs/rebuild/switch_plan.md).

    python scripts/sync_rehearsal.py --cloud     # Cloud Run: deploy, seed, time, record, delete
    python scripts/sync_rehearsal.py --local     # in this process: a quick look, never the check

It times the engine's REAL sync chain (POST /api/sync with force: every device
step, the blend, session heart rate, the history, the fused nights, the backup,
the failed-week rule and the rollup) over made-up data, with every device and
store call faked (api/healthapi/rehearsal.py), and writes
reports/rebuild/p9/rehearsal.json, which scripts/switch_check.py reads (a
--local run writes rehearsal_local.json beside it, never that file). The
check passes only for a Cloud Run run with every step done and no outgoing
connection tried, inside the limit: the Worker's sync budget
(worker/src/index.ts SYNC_TIMEOUT_MS, read from the file) or the engine's own
Cloud Run timeout, whichever is shorter.

--cloud deploys a SEPARATE service, health-rehearsal, from the image the
engine runs now: no build and no new image. It takes the engine's CPU, memory,
timeout, concurrency, execution environment and start-up boost, and nothing
else: no secret, no environment, no public access (each request carries the
owner's gcloud identity token, which is never printed), at most one instance
(the made-up store lives in that instance's memory), and its own runtime
identity with no role (health-rehearsal@, made the first time), never the
engine's and never the project's default. Its command is
`uvicorn healthapi.rehearsal_service:app`, which refuses every outgoing
connection before it starts. The service is deleted at the end (--keep leaves
it). Nothing the engine or the store holds is read or written.

THE WAITS ARE ASSUMPTIONS, AND THE RECORD SAYS SO. The devices are faked, so
each device call waits --device-latency seconds (2.0 by default, and a Garmin
login --login-latency more, 10.0: neither Oura nor Garmin may be called from
this PC to measure them, and the old app measured about 77 s for both, store
writes included, on 2026-08-01) and each store call --store-latency (0.15: the
store's round trip, measured 2026-08-11).

Prints statuses, timings and call counts of made-up data only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for extra in (ROOT, ROOT / "api"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

RECORD = ROOT / "reports" / "rebuild" / "p9" / "rehearsal.json"
#: A --local run's record: never the one switch_check reads.
LOCAL_RECORD = RECORD.with_name("rehearsal_local.json")
WORKER_INDEX = ROOT / "worker" / "src" / "index.ts"
REGION = "europe-west1"
ENGINE_SERVICE = "health-engine"
SERVICE = "health-rehearsal"
#: The rehearsal's own runtime identity, with no role at all: never the engine's
#: (it may read the real secrets) and never the Compute Engine default (project
#: Editor). Created by ensure_account the first time.
ACCOUNT_NAME = "health-rehearsal"
COMMAND_ARGS = "-c,exec uvicorn healthapi.rehearsal_service:app --host 0.0.0.0 --port 8080 --no-server-header"
KEY = "rehearsal"     # healthapi.rehearsal.KEY: made up, guards nothing real


def worker_limit_seconds(text: str | None = None) -> float:
    """The Worker's budget for a sync request, from worker/src/index.ts."""
    text = text if text is not None else WORKER_INDEX.read_text(encoding="utf-8")
    found = re.search(r"SYNC_TIMEOUT_MS\s*=\s*([\d_]+)", text)
    if not found:
        raise ValueError("SYNC_TIMEOUT_MS not found in worker/src/index.ts")
    return int(found.group(1).replace("_", "")) / 1000


def summarize(*, where: str, status_code: int, answer: dict | None, seconds: float,
              limit_seconds: float, report: dict | None, assumptions: dict,
              service: dict | None = None) -> dict:
    """The record switch_check reads: ok only when the sync answered, every
    step and the run itself report no error, and no outgoing connection was
    tried."""
    status = ((answer or {}).get("status") or {}) if status_code == 200 else {}
    results = status.get("results") or {}
    failed = sorted(name for name, (ok, _err) in results.items() if not ok)
    blocked = (report or {}).get("network_blocked")
    error = None
    if status_code != 200:
        error = f"HTTP {status_code}: {(answer or {}).get('error')}"
    elif not (answer or {}).get("ran"):
        error = "the sync did not run"
    elif status.get("error"):
        error = f"the run: {status['error']}"
    elif failed:
        error = "failed steps: " + ", ".join(f"{n} ({results[n][1]})" for n in failed)
    elif not results:
        error = "no step results"
    elif blocked:
        error = f"{blocked} outgoing connection(s) tried"
    return {
        "where": where, "ok": error is None, "error": error,
        "seconds": round(seconds, 2), "limit_seconds": limit_seconds,
        "steps": {name: bool(ok) for name, (ok, _err) in results.items()},
        "server_seconds": (report or {}).get("last_sync_seconds"),
        "assumptions": assumptions,
        "device_calls": (report or {}).get("device_calls"),
        "device_calls_total": (report or {}).get("device_calls_total"),
        "store_calls": (report or {}).get("store_calls"),
        "oura_refreshes": (report or {}).get("oura_refreshes"),
        "network_blocked": blocked,
        "made_up_history": (report or {}).get("made_up_history"),
        "seed_seconds": (report or {}).get("seed_seconds"),
        "seed_stages": (report or {}).get("seed_stages"),
        "service": service,
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def write_record(run: dict, path: Path = RECORD) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _print(run: dict) -> None:
    print(f"where: {run['where']} | ok: {run['ok']} | {run['seconds']} s against "
          f"{run['limit_seconds']} s | server {run['server_seconds']} s")
    print("steps:", ", ".join(f"{n} {'ok' if ok else 'FAILED'}" for n, ok in run["steps"].items()))
    print(f"device calls {run['device_calls_total']}, store calls {run['store_calls']}, "
          f"Oura refreshes {run['oura_refreshes']}, outgoing connections tried "
          f"{run['network_blocked']}; seed {run['seed_seconds']} s")
    if run["error"]:
        print("error:", run["error"])


# ─── in this process ────────────────────────────────────────────────────────

def run_local(seed: dict, today: date) -> dict:
    """The same app, seed and sync in this process (no Cloud Run): a quick
    look at the chain and its call counts. Never satisfies the check."""
    from fastapi.testclient import TestClient
    from healthapi import rehearsal as rh

    holder: dict = {}
    headers = {"X-Engine-Key": rh.KEY, "X-Local-Date": today.isoformat()}
    with rh.no_network():
        try:
            client = TestClient(rh.build_app(holder), raise_server_exceptions=False)
            r = client.post("/rehearsal/seed", json=seed, headers=headers)
            if r.status_code != 200:
                raise SystemExit(f"seed: HTTP {r.status_code} {r.json()}")
            t0 = time.perf_counter()
            r = client.post("/api/sync", json={"force": True}, headers=headers)
            seconds = time.perf_counter() - t0
            report = client.get("/rehearsal/report", headers=headers).json()
        finally:
            if "rehearsal" in holder:
                holder["rehearsal"].close()
    return summarize(where="local", status_code=r.status_code, answer=r.json(),
                     seconds=seconds, limit_seconds=worker_limit_seconds(), report=report,
                     assumptions=_assumptions(seed))


def _assumptions(seed: dict) -> dict:
    return {"device_latency_s": seed["device_latency_s"],
            "garmin_login_latency_s": seed["garmin_login_latency_s"],
            "store_latency_s": seed["store_latency_s"]}


# ─── on Cloud Run ───────────────────────────────────────────────────────────

def _gcloud() -> str:
    found = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    if found:
        return found
    default = (Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Cloud SDK"
               / "google-cloud-sdk" / "bin" / "gcloud.cmd")
    if default.exists():
        return str(default)
    raise SystemExit("gcloud is not on PATH")


def _run(args: list[str]) -> str:
    """One gcloud call; its output is returned, never printed."""
    proc = subprocess.run([_gcloud(), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        # gcloud's own error lines, which name a flag or a permission, not a value.
        tail = [line for line in proc.stderr.splitlines() if "ERROR" in line][-3:]
        raise SystemExit(f"gcloud {args[0]} {args[1]} failed: {' | '.join(tail) or proc.returncode}")
    return proc.stdout


def engine_settings(description: dict) -> dict:
    """The engine service's image and resources, from `gcloud run services
    describe --format=json`: only what the rehearsal copies."""
    template = description["spec"]["template"]
    container = template["spec"]["containers"][0]
    notes = (template.get("metadata") or {}).get("annotations") or {}
    limits = (container.get("resources") or {}).get("limits") or {}
    engine_account = template["spec"].get("serviceAccountName") or ""
    return {
        "image": container["image"],
        "project": engine_account.split("@", 1)[1].split(".", 1)[0] if "@" in engine_account else None,
        "cpu": limits.get("cpu", "1"),
        "memory": limits.get("memory", "512Mi"),
        "timeout_s": int(template["spec"].get("timeoutSeconds") or 300),
        "concurrency": int(template["spec"].get("containerConcurrency") or 80),
        "execution_environment": notes.get("run.googleapis.com/execution-environment"),
        "cpu_boost": notes.get("run.googleapis.com/startup-cpu-boost") == "true",
        "revision": (description.get("status") or {}).get("latestReadyRevisionName"),
    }


def rehearsal_account(project: str) -> str:
    return f"{ACCOUNT_NAME}@{project}.iam.gserviceaccount.com"


def ensure_account(project: str) -> str:
    """The rehearsal's runtime identity, made the first time (no role is
    granted; it needs none to serve made-up data)."""
    email = rehearsal_account(project)
    try:
        _run(["iam", "service-accounts", "describe", email, f"--project={project}",
              "--format=value(email)"])
    except SystemExit:
        _run(["iam", "service-accounts", "create", ACCOUNT_NAME, f"--project={project}",
              "--display-name=Health sync rehearsal (no role)"])
        print(f"made the service account {ACCOUNT_NAME} (no role)")
    return email


def deploy_args(settings: dict) -> list[str]:
    if not settings.get("project"):
        raise SystemExit("the engine's runtime identity names no project")
    args = ["run", "deploy", SERVICE, f"--image={settings['image']}", f"--region={REGION}",
            f"--service-account={rehearsal_account(settings['project'])}",
            "--no-allow-unauthenticated", "--max-instances=1", "--min-instances=0",
            f"--cpu={settings['cpu']}", f"--memory={settings['memory']}",
            f"--timeout={settings['timeout_s']}", f"--concurrency={settings['concurrency']}",
            "--command=sh", f"--args={COMMAND_ARGS}", "--set-env-vars=TZ=UTC",
            "--cpu-boost" if settings["cpu_boost"] else "--no-cpu-boost", "--quiet"]
    if settings.get("execution_environment"):
        args.append(f"--execution-environment={settings['execution_environment']}")
    return args


def run_cloud(seed: dict, today: date, keep: bool) -> dict:
    import requests

    settings = engine_settings(json.loads(_run(
        ["run", "services", "describe", ENGINE_SERVICE, f"--region={REGION}", "--format=json"])))
    image = settings["image"]
    print(f"engine revision {settings['revision']}: image ...{image[-12:]}, cpu {settings['cpu']}, "
          f"memory {settings['memory']}, timeout {settings['timeout_s']} s")
    ensure_account(settings["project"])
    print(f"deploying {SERVICE} from that image (no build) ...")
    t0 = time.perf_counter()
    _run(deploy_args(settings))
    print(f"deployed in {time.perf_counter() - t0:.0f} s")
    try:
        url = _run(["run", "services", "describe", SERVICE, f"--region={REGION}",
                    "--format=value(status.url)"]).strip()
        token = _run(["auth", "print-identity-token"]).strip()
        headers = {"Authorization": f"Bearer {token}", "X-Engine-Key": KEY,
                   "X-Local-Date": today.isoformat()}
        print("seeding the made-up history ...")
        r = requests.post(f"{url}/rehearsal/seed", json=seed, headers=headers, timeout=960)
        if r.status_code != 200:
            raise SystemExit(f"seed: HTTP {r.status_code} {r.text[:300]}")
        print(f"seeded in {r.json().get('seed_seconds')} s on the service")
        print("timing one sync ...")
        t0 = time.perf_counter()
        r = requests.post(f"{url}/api/sync", json={"force": True}, headers=headers, timeout=960)
        seconds = time.perf_counter() - t0
        try:
            answer = r.json()
        except ValueError:
            answer = {"error": r.text[:200]}
        report = requests.get(f"{url}/rehearsal/report", headers=headers, timeout=120).json()
    finally:
        if keep:
            print(f"kept {SERVICE} (delete: gcloud run services delete {SERVICE} --region={REGION})")
        else:
            _run(["run", "services", "delete", SERVICE, f"--region={REGION}", "--quiet"])
            print(f"deleted {SERVICE}")
    limit = min(worker_limit_seconds(), float(settings["timeout_s"]))
    service = {k: settings[k] for k in ("cpu", "memory", "timeout_s", "concurrency",
                                        "execution_environment", "cpu_boost", "revision")}
    service["image_digest_tail"] = image[-12:]
    return summarize(where="cloud_run", status_code=r.status_code, answer=answer,
                     seconds=seconds, limit_seconds=limit, report=report,
                     assumptions=_assumptions(seed), service=service)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    where = ap.add_mutually_exclusive_group(required=True)
    where.add_argument("--cloud", action="store_true", help="on its own Cloud Run service")
    where.add_argument("--local", action="store_true", help="in this process (never the check)")
    ap.add_argument("--device-latency", type=float, default=2.0)
    ap.add_argument("--login-latency", type=float, default=10.0)
    ap.add_argument("--store-latency", type=float, default=0.15)
    ap.add_argument("--oura-days", type=int, default=700)
    ap.add_argument("--garmin-days", type=int, default=110)
    ap.add_argument("--keep", action="store_true", help="--cloud: leave the service running")
    args = ap.parse_args(argv)
    seed = {"oura_days": args.oura_days, "garmin_days": args.garmin_days,
            "device_latency_s": args.device_latency, "garmin_login_latency_s": args.login_latency,
            "store_latency_s": args.store_latency}
    today = date.today()
    run = run_cloud(seed, today, args.keep) if args.cloud else run_local(seed, today)
    path = write_record(run, RECORD if args.cloud else LOCAL_RECORD)
    _print(run)
    print(f"recorded: {path.relative_to(ROOT)}")
    return 0 if run["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
