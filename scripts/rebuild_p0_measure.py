"""scripts/rebuild_p0_measure.py -- rebuild Phase 0's measurements against the live engine.

    python scripts/rebuild_p0_measure.py cold [--via auto|direct|worker] [--runs 5] [--gap-min 20] [--wait-first-min 0]
    python scripts/rebuild_p0_measure.py warm [--runs 5]
    python scripts/rebuild_p0_measure.py oura
    python scripts/rebuild_p0_measure.py garmin --confirm owner-approved
    python scripts/rebuild_p0_measure.py usage [--hours 24]
    python scripts/rebuild_p0_measure.py project --start-s 11
    python scripts/rebuild_p0_measure.py summary [--build COMMIT]

Every sample is one line in reports/rebuild/p0_measure.jsonl (gitignored). A
sample holds timings, status codes and the engine's own startup timings only:
never a key, never the engine's address (a Worker secret, kept out of this
public repo), never a reading. `summary` prints the numbers the gate reads
from docs/rebuild/p0_proof.json.

The keys are used without being shown: the engine key comes from Secret
Manager through gcloud, the access key from Health_project/.env, and both go
straight into a request header (CLAUDE.md rebuild rule 12).

A COLD start is a request whose answering instance started inside that
request's own time window (`started_at` from /api/health). A deploy starts an
instance to check the new revision, so the first request after a deploy is
usually WARM; the only clean cold start is one after Cloud Run has let the
idle instance go (up to 15 minutes). `cold` therefore waits `--gap-min`
between samples and records a warm hit as warm, never as cold. A warm hit
resets the idle clock, so the wait starts again after it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import ssl
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG = REPO_ROOT / "reports" / "rebuild" / "p0_measure.jsonl"
WORKER_URL = "https://health.lauscher-worker.workers.dev"
ENGINE_SERVICE = "health-engine"
REGION = "europe-west1"
ENGINE_KEY_SECRET = "health-engine-key"
ENGINE_KEY_VERSION = "1"
OWNER_TZ = "Europe/Berlin"
# A started_at is written to the second; an instance whose start falls this
# close before the request was sent still counts as started by it.
COLD_MARGIN_S = 2.0
USER_AGENT = "health-rebuild-p0-measure/1.0"


def _gcloud() -> str:
    path = shutil.which("gcloud")
    if not path:
        sys.exit("gcloud is not on PATH.")
    return path


def _gcloud_out(*args: str) -> bytes:
    proc = subprocess.run([_gcloud(), *args], capture_output=True)
    if proc.returncode != 0:
        sys.exit(f"gcloud {args[0]} {args[1]} failed ({proc.returncode}).")
    return proc.stdout.strip()


def engine_target() -> tuple[str, str]:
    url = _gcloud_out("run", "services", "describe", ENGINE_SERVICE, f"--region={REGION}",
                      "--format=value(status.url)").decode("ascii")
    if not url.startswith("https://"):
        sys.exit("Cloud Run did not return an https address.")
    key = _gcloud_out("secrets", "versions", "access", ENGINE_KEY_VERSION,
                      f"--secret={ENGINE_KEY_SECRET}").decode("ascii")
    return url, key


def access_key(env_path: Path = REPO_ROOT / ".env") -> str:
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip().startswith("HEALTH_ACCESS_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return value
    sys.exit("HEALTH_ACCESS_KEY is not in Health_project/.env.")


def owner_today() -> date:
    return datetime.now(ZoneInfo(OWNER_TZ)).date()


def _ssl_context() -> ssl.SSLContext:
    """certifi's roots when present. On this PC (2026-10-19) the default
    context refuses the Worker's address with "certificate has expired": the
    Windows store leads OpenSSL through ISRG Root X2's cross-signature of
    Let's Encrypt's Root YE, which expired 2025-09-15, while Windows itself and
    Safari accept the same certificate through ISRG Root X1."""
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def call(via: str, path: str, *, method: str = "GET", body: dict | None = None,
         target: tuple[str, str] | None = None, timeout: float = 90.0,
         local_date: date | None = None) -> dict:
    """One timed request. Returns the status, the seconds it took and the JSON
    answer; the address and the key never leave this function. `local_date` is
    the caller's day the request carries (the owner's today without it)."""
    # Cloudflare answers Python's default User-Agent ("Python-urllib/3.x") with a
    # 403 challenge page before the Worker runs (checked 2026-10-19).
    headers = {"Accept": "application/json",
               "X-Local-Date": (local_date or owner_today()).isoformat(),
               "User-Agent": USER_AGENT}
    if via == "direct":
        base, key = target or engine_target()
        headers["X-Engine-Key"] = key
    elif via == "worker":
        base = WORKER_URL
        headers["Authorization"] = f"Bearer {access_key()}"
    else:
        raise ValueError(via)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    sent = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_ssl_context()) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"sent": sent.isoformat(timespec="seconds"), "status": None,
                "error": type(exc).__name__, "seconds": round(time.perf_counter() - t0, 3)}
    seconds = time.perf_counter() - t0
    try:
        answer = json.loads(raw.decode("utf-8")) if raw else None
    except ValueError:
        answer = None
    return {"sent": sent.isoformat(timespec="seconds"), "status": status,
            "seconds": round(seconds, 3), "answer": answer}


def is_cold(sent_iso: str, seconds: float, started_at: str | None) -> bool | None:
    """True when the answering instance started inside the request's window."""
    if not started_at:
        return None
    sent = datetime.fromisoformat(sent_iso)
    started = datetime.fromisoformat(started_at)
    return sent - timedelta(seconds=COLD_MARGIN_S) <= started <= sent + timedelta(seconds=seconds)


def health_sample(kind: str, via: str, target: tuple[str, str] | None = None) -> dict:
    result = call(via, "/api/health", target=target)
    answer = result.pop("answer", None) or {}
    sample = {"kind": kind, "via": via, **result}
    if result.get("status") not in (None, 200):
        # The Worker's and the engine's errors are JSON {"error": code}.
        sample["error_code"] = answer.get("error") if isinstance(answer, dict) else None
    if result.get("status") == 200:
        sample["cold"] = is_cold(result["sent"], result["seconds"], answer.get("started_at"))
        sample["engine_timings"] = answer.get("timings")
        sample["cache_rebuilt"] = answer.get("cache_rebuilt")
        sample["server_tz"] = answer.get("server_tz")
        sample["server_local_date"] = answer.get("server_local_date")
        sample["owner_local_date"] = owner_today().isoformat()
        sample["python"] = answer.get("python")
        sample["build"] = (answer.get("build") or {}).get("commit")
    return sample


def record(sample: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(sample) + "\n")
    shown = {k: v for k, v in sample.items() if k in
             ("kind", "via", "status", "seconds", "cold", "engine_timings", "error", "probe",
              "hours", "billable_instance_s", "requests")}
    print(json.dumps(shown), flush=True)


def cold_sample(via: str, target: tuple[str, str]) -> dict:
    """One cold-start try. `auto` goes through the Worker once the Worker holds
    its keys, and straight to the engine before that: a Worker without its keys
    answers 503 not_configured itself and never wakes the engine, so trying it
    costs nothing. ANY other failure through the Worker is a failed cold start
    and is returned as one: on 2026-10-19 Google refused the first request after
    the engine slept, and treating that 503 as "not ready" timed the direct
    request that followed, which met an engine already half started (3.0 s)."""
    if via == "auto":
        sample = health_sample("cold", "worker")
        if sample.get("error_code") != "not_configured":
            return sample
        record({**sample, "kind": "worker_not_ready"})
        via = "direct"
    return health_sample("cold", via, target if via == "direct" else None)


def cmd_cold(args) -> None:
    target = engine_target()
    time.sleep(args.wait_first_min * 60)
    got = 0
    for attempt in range(args.runs * 3):
        sample = cold_sample(args.via, target)
        record(sample)
        if sample.get("cold"):
            got += 1
            # Warm follow-ups: the engine alone, and the Worker's extra hop.
            record(health_sample("warm_after_cold", "direct", target))
            if sample["via"] == "worker":
                record(health_sample("warm_after_cold", "worker"))
        if got >= args.runs:
            break
        time.sleep(args.gap_min * 60)


def cmd_warm(args) -> None:
    target = engine_target()
    for _ in range(args.runs):
        record(health_sample("warm", "direct", target))
        record(health_sample("warm", "worker"))


def cmd_oura(_args) -> None:
    result = call("direct", "/api/probe/oura")
    answer = result.pop("answer", None) or {}
    record({"kind": "probe_oura", "via": "direct", **result,
            "probe": {k: answer.get(k) for k in ("status", "detail", "count")}})


def cmd_garmin(args) -> None:
    if args.confirm != "owner-approved":
        sys.exit("The Garmin probe logs in to Garmin once: run it only with the owner's OK "
                 "(--confirm owner-approved).")
    result = call("direct", "/api/probe/garmin", method="POST",
                  body={"confirm": "owner-approved"}, timeout=120.0)
    answer = result.pop("answer", None) or {}
    record({"kind": "probe_garmin", "via": "direct", **result,
            "probe": {k: answer.get(k) for k in ("status", "detail", "count")}})


MONITORED = {
    # Cloud Run's own meters: what the free tier is counted against.
    "billable_instance_s": ("run.googleapis.com/container/billable_instance_time", "ALIGN_SUM"),
    "requests": ("run.googleapis.com/request_count", "ALIGN_SUM"),
}


def monitored_total(metric: str, aligner: str, hours: float) -> float:
    """The sum of one Cloud Run metric for health-engine over the last `hours`,
    from the Cloud Monitoring API. The access token goes into the header only."""
    token = _gcloud_out("auth", "print-access-token").decode("ascii")
    project = _gcloud_out("config", "get-value", "project").decode("ascii")
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(hours=hours)
    params = urllib.parse.urlencode({
        "filter": (f'metric.type="{metric}" AND resource.type="cloud_run_revision" '
                   f'AND resource.labels.service_name="{ENGINE_SERVICE}"'),
        "interval.startTime": start.isoformat().replace("+00:00", "Z"),
        "interval.endTime": end.isoformat().replace("+00:00", "Z"),
        "aggregation.alignmentPeriod": f"{int(hours * 3600)}s",
        "aggregation.perSeriesAligner": aligner,
        "aggregation.crossSeriesReducer": "REDUCE_SUM",
    })
    request = urllib.request.Request(
        f"https://monitoring.googleapis.com/v3/projects/{project}/timeSeries?{params}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60, context=_ssl_context()) as resp:
        return series_total(json.loads(resp.read()).get("timeSeries", []))


def series_total(series: list[dict]) -> float:
    """Every point of every series added up; a DOUBLE or an INT64 metric (the
    API sends an int64 as a string)."""
    total = 0.0
    for s in series:
        for point in s.get("points", []):
            value = point["value"]
            total += float(value.get("doubleValue", value.get("int64Value", 0)))
    return total


def cmd_usage(args) -> None:
    out = {"hours": args.hours, "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    for name, (metric, aligner) in MONITORED.items():
        out[name] = round(monitored_total(metric, aligner, args.hours), 1)
    record({"kind": "usage", **out})


# The free amounts a month (checked on Google's and Supabase's pages 2026-10-19;
# docs/rebuild/stack.md). Per billing account; Cloudflare's is per day.
FREE = {
    "cloud_run_vcpu_s": 180_000,
    "cloud_run_gib_s": 360_000,
    "cloud_run_requests": 2_000_000,
    "artifact_registry_mb": 500,
    "cloud_build_minutes": 2_500,
    "secret_versions": 6,
    "secret_accesses": 10_000,
    "supabase_egress_gb": 5,
    "worker_requests_per_day": 100_000,
}
# Data sent out of Belgium has no free amount (Premium tier, $0.12 a GiB).
EGRESS_USD_PER_GB = 0.12


def project(*, start_s: float, cold_starts_per_day: float = 10, syncs_per_day: float = 2,
            sync_s: float = 160, requests_per_day: float = 60, request_s: float = 0.3,
            copy_mb: float = 1.36, image_mb: float = 186, deploys_per_month: float = 30,
            build_min: float = 1.2, secret_versions: int = 2) -> dict:
    """A 30-day month of use against each free amount, from measured unit costs.

    The defaults are the owner's pattern, generous on purpose: one sync a day
    at the first morning open plus one retry (2026-10-19), each sync at twice
    the 77 s the Streamlit chain took (2026-08-01), ten cold starts a day.
    Startup CPU boost is on, so each start is billed one extra vCPU for the
    start and the 10 s after it."""
    days = 30
    starts = cold_starts_per_day * days
    requests = (requests_per_day + syncs_per_day) * days
    billed_s = starts * start_s + syncs_per_day * days * sync_s + requests_per_day * days * request_s
    use = {
        "cloud_run_vcpu_s": billed_s + starts * (start_s + 10),
        "cloud_run_gib_s": billed_s,
        "cloud_run_requests": requests,
        "artifact_registry_mb": image_mb,
        "cloud_build_minutes": deploys_per_month * build_min,
        "secret_versions": secret_versions,
        "secret_accesses": starts * 2,
        "supabase_egress_gb": starts * copy_mb / 1000,
        "worker_requests_per_day": requests_per_day + syncs_per_day,
    }
    share = {k: round(use[k] / FREE[k], 3) for k in FREE}
    # Out of Belgium: ~20 KB an answer, ~200 KB of writes a sync, the daily 1.1 MB backup.
    egress_gb = (requests * 20e3 + syncs_per_day * days * 200e3 + days * 1.1e6) / 1e9
    return {"use": {k: round(v, 3) for k, v in use.items()}, "share": share,
            "max_share": max(share.values()), "max_share_item": max(share, key=share.get),
            "egress_out_gb": round(egress_gb, 3),
            "egress_out_usd": round(egress_gb * EGRESS_USD_PER_GB, 3)}


def cmd_project(args) -> None:
    print(json.dumps(project(start_s=args.start_s), indent=2))


def summarise(samples: list[dict]) -> dict:
    """The proof numbers from the samples: cold starts as the caller saw them."""
    cold = [s["seconds"] for s in samples if s.get("kind") == "cold" and s.get("cold")]

    def warm(s: dict, via: str) -> bool:
        # A follow-up is warm by construction: one instance at most, and it has
        # just answered. Its own cold flag can read True, because started_at is
        # written to the second and COLD_MARGIN_S reaches back 2 s.
        return (s.get("via") == via and s.get("status") == 200
                and (s.get("kind") == "warm_after_cold"
                     or (s.get("kind") == "warm" and s.get("cold") is False)))

    warm_direct = [s["seconds"] for s in samples if warm(s, "direct")]
    warm_worker = [s["seconds"] for s in samples if warm(s, "worker")]
    out = {
        "cold_start_failures": sum(1 for s in samples
                                   if s.get("kind") == "cold" and s.get("status") != 200),
        "cold_start_runs_s": [round(x, 2) for x in cold],
        "cold_start_median_s": round(statistics.median(cold), 2) if cold else None,
        "cold_start_worst_s": round(max(cold), 2) if cold else None,
        "warm_request_ms": round(statistics.median(warm_direct) * 1000) if warm_direct else None,
        "worker_to_engine_ms": (round((statistics.median(warm_worker)
                                       - statistics.median(warm_direct)) * 1000)
                                if warm_worker and warm_direct else None),
    }
    timings = [s["engine_timings"] for s in samples
               if s.get("kind") == "cold" and s.get("cold") and s.get("engine_timings")]
    if timings:
        out["cold_start_engine_timings_median_s"] = {
            k: round(statistics.median(t[k] for t in timings if k in t), 2)
            for k in sorted({k for t in timings for k in t})}
    return out


def cmd_summary(args) -> None:
    samples = [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines()
               if line.strip()] if LOG.exists() else []
    if args.build:
        # One revision's numbers: a sample names the commit its engine was built from.
        samples = [s for s in samples if s.get("build") == args.build]
    print(json.dumps(summarise(samples), indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("cold")
    p.add_argument("--via", choices=("auto", "direct", "worker"), default="auto")
    p.add_argument("--runs", type=int, default=5)
    p.add_argument("--gap-min", type=float, default=20.0)
    p.add_argument("--wait-first-min", type=float, default=0.0)
    p.set_defaults(func=cmd_cold)
    p = sub.add_parser("warm")
    p.add_argument("--runs", type=int, default=5)
    p.set_defaults(func=cmd_warm)
    sub.add_parser("oura").set_defaults(func=cmd_oura)
    p = sub.add_parser("garmin")
    p.add_argument("--confirm", default="")
    p.set_defaults(func=cmd_garmin)
    p = sub.add_parser("usage")
    p.add_argument("--hours", type=float, default=24.0)
    p.set_defaults(func=cmd_usage)
    p = sub.add_parser("project")
    p.add_argument("--start-s", type=float, required=True, help="billed seconds of one cold start")
    p.set_defaults(func=cmd_project)
    p = sub.add_parser("summary")
    p.add_argument("--build", default="", help="only the samples of the engine built from this commit")
    p.set_defaults(func=cmd_summary)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
