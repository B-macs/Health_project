"""The checks before the switch-over (rebuild Phase 9, 9.1). Read-only.

    python scripts/switch_check.py [--json] [--today YYYY-MM-DD]

Each check prints a tick or a cross and why. The switch waits until every check
passes and the owner says go (docs/rebuild/switch_plan.md):

1. rows        every KEEP or MOVE row of the screen inventory is built and has a test
               (docs/rebuild/app_rows.json; the owner approved every DROP).
2. parity      the live engine's answers equal the services' own over the last 28 days,
               Today and Insights (scripts/rebuild_parity.py, under the engine's Python).
3. backups     a daily backup on each of the last 7 days (Storage bucket health-backups).
4. oura_login  the Oura login endpoints against a mocked Oura (the engine's API tests).
5. rehearsal   the full sync chain inside one request on Cloud Run with every device call
               mocked, inside the request time limit (recorded by its own run).
6. outbox      the owner's phone: Settings shows no save waiting and none refused in the
               last 7 days. Only he can read it: this script reports it as his.

Nothing here writes: the parity run reads the live engine and the store, the backup
check lists the bucket, the login check runs tests against a fake store and a mocked
Oura. Values are never printed, only counts, days and names.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import rebuild_gate as gate  # noqa: E402

PARITY_DAYS = 28
#: The engine's API tests of the Oura login (a mocked Oura, a fake store).
OURA_LOGIN_TESTS = ("tests/api/test_api_insights.py::test_the_oura_login_is_the_background_writers",
                    "tests/api/test_api_insights.py::test_the_oura_login_ties_the_answer_to_its_request",
                    "tests/api/test_api_status_sync.py::test_the_oura_login_is_described_without_a_token")
#: Where the sync rehearsal records its Cloud Run run (scripts/sync_rehearsal.py --cloud).
REHEARSAL_RECORD = ROOT / "reports" / "rebuild" / "p9" / "rehearsal.json"


def result(name: str, ok: bool | None, detail: str) -> dict:
    """One check: ok True (passed), False (failed) or None (the owner's to do)."""
    return {"check": name, "ok": ok, "detail": detail}


def check_rows() -> dict:
    words = gate.inventory_rows(gate.SCREEN_INVENTORY.read_text(encoding="utf-8"))
    kept = [r for r, w in words.items() if w in ("KEEP", "MOVE")]
    mapping = json.loads(gate.APP_ROWS.read_text(encoding="utf-8"))["rows"]
    owner = gate.DESIGN_MD.read_text(encoding="utf-8") if gate.DESIGN_MD.exists() else ""
    open_ = gate.app_rows_open(kept, mapping, owner)
    return result("rows", not open_, "; ".join(open_) or f"{len(kept)} rows built, each with a test")


def _parity(insights: bool, days: int) -> dict | None:
    args = [str(gate.parity_python()), str(gate.PARITY), "--days", str(days), "--json"]
    if insights:
        args.insert(2, "--insights")
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    try:
        return json.loads(proc.stdout)
    except ValueError:
        return None


def check_parity(days: int = PARITY_DAYS, run=_parity) -> dict:
    parts = []
    found = 0
    for label, insights in (("Today", False), ("Insights", True)):
        report = run(insights, days)
        if report is None:
            return result("parity", False, f"{label}: the parity run gave no report")
        diffs = len(report.get("differences", [])) + len(report.get("unanswered", []))
        diffs += len(report.get("sleep_rule_violations", []))
        found += diffs
        parts.append(f"{label} {days} days: {diffs} differences")
    return result("parity", found == 0, "; ".join(parts))


def _backup_names() -> list[str]:
    from services import backup, supabase_store
    from services.config import load_config
    secrets = ROOT / ".streamlit" / "secrets.toml"
    overrides = tomllib.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
    cfg = load_config({**overrides, "HEALTH_SYSTEM_OF_RECORD": "supabase"})
    return backup.Storage(supabase_store.SupabaseStore(cfg.supabase_url, cfg.supabase_secret_key)).names()


#: Days without a backup that the owner accepted, each with his reason: they no
#: longer fail the check, and its detail still names them. Only he adds one.
ACCEPTED_BACKUP_GAPS: dict[date, str] = {
    date(2026, 10, 17): "accepted by the owner on 2026-10-20 (answer a): the old app makes "
                        "the backup only when its Home page loads to its end",
    date(2026, 10, 20): "accepted by the owner on 2026-10-21 (\"1. Yes\"): the same fault of "
                        "the old app; from the switch on the engine makes the backup",
}


def check_backups(today: date, names=_backup_names, accepted: dict | None = None) -> dict:
    from services import backup
    accepted = ACCEPTED_BACKUP_GAPS if accepted is None else accepted
    try:
        missing = backup.missing_days(names(), today)
    except Exception as exc:
        return result("backups", False, f"the bucket could not be listed: {type(exc).__name__}")
    first = today - timedelta(days=7)
    gaps = [d for d in missing if d not in accepted]
    if gaps:
        return result("backups", False, f"no copy on {', '.join(d.isoformat() for d in gaps)}")
    detail = f"a copy on each day {first.isoformat()} to {(today - timedelta(days=1)).isoformat()}"
    taken = [d for d in missing if d in accepted]
    if taken:
        detail = (f"a copy on every other day {first.isoformat()} to "
                  f"{(today - timedelta(days=1)).isoformat()}; "
                  + "; ".join(f"none on {d.isoformat()}, {accepted[d]}" for d in taken))
    return result("backups", True, detail)


def check_oura_login() -> dict:
    proc = subprocess.run([str(gate.main_python()), "-m", "pytest", "-q", "-p", "no:cacheprovider",
                           *OURA_LOGIN_TESTS], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    last = (proc.stdout.strip().splitlines() or ["no output"])[-1]
    return result("oura_login", proc.returncode == 0, last)


def check_rehearsal(record: Path = REHEARSAL_RECORD) -> dict:
    """Passes only for a run on Cloud Run (scripts/sync_rehearsal.py --cloud)
    with every step done, inside its limit."""
    if not record.exists():
        return result("rehearsal", False, "not run yet")
    run = json.loads(record.read_text(encoding="utf-8"))
    on_cloud_run = run.get("where") == "cloud_run"
    ok = (on_cloud_run and bool(run.get("ok"))
          and float(run.get("seconds", 1e9)) < float(run.get("limit_seconds", 0)))
    detail = f'{run.get("seconds")} s against a limit of {run.get("limit_seconds")} s'
    if not on_cloud_run:
        detail += f' (run {run.get("where") or "somewhere unnamed"}, not on Cloud Run)'
    if not run.get("ok"):
        detail += ": " + str(run.get("error"))
    return result("rehearsal", ok, detail)


def check_outbox() -> dict:
    return result("outbox", None, "the owner's phone: Settings > Saves waiting to send shows none, "
                                  "and no save was refused in the last 7 days")


def run_checks(today: date) -> list[dict]:
    return [check_rows(), check_parity(), check_backups(today), check_oura_login(),
            check_rehearsal(), check_outbox()]


def verdict(checks: list[dict]) -> str:
    """'ready' only when every check passed and the owner confirmed his; else what waits."""
    if any(c["ok"] is False for c in checks):
        return "not ready: " + ", ".join(c["check"] for c in checks if c["ok"] is False)
    if any(c["ok"] is None for c in checks):
        return "waits for the owner: " + ", ".join(c["check"] for c in checks if c["ok"] is None)
    return "ready"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--today", type=date.fromisoformat, default=None)
    args = ap.parse_args()
    import rebuild_p0_measure as live  # the owner's day, as the parity run reads it
    today = args.today or live.owner_today()
    checks = run_checks(today)
    if args.json:
        print(json.dumps({"today": today.isoformat(), "checks": checks, "verdict": verdict(checks)}, indent=2))
        return 0
    for c in checks:
        mark = {True: "✓", False: "✗", None: "…"}[c["ok"]]
        print(f"{mark} {c['check']:<11} {c['detail']}")
    print(verdict(checks))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.exit(main())
