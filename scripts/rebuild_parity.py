# -*- coding: utf-8 -*-
"""Parity between the phone's numbers and the services' own (rebuild Phase 5).

    python scripts/rebuild_parity.py            # the last 14 days, a list of differences
    python scripts/rebuild_parity.py --json     # the same, as JSON (the gate reads this)

For each of the last 14 days it asks the LIVE engine, through the Worker, for
Today's cards, the week strip and the three detail screens, and computes the
same answers here through services/ directly, from a fresh copy of the store,
passed through the same response models the engine uses. Any difference is a
wiring bug, not "close enough".

It prints DATES AND FIELD NAMES ONLY, never a value: its output may be pasted
into a chat. It also counts the Sleep screen's all-or-nothing rule on the
engine's answers: a date whose night has no score but carries a night panel or
the wake-time stepper.

It reads only. The access key comes from Health_project/.env
(HEALTH_ACCESS_KEY) and the store's key from .streamlit/secrets.toml; neither
is printed. A sync that runs between the two reads can show as a difference
on the newest day: run it again before reading anything into one.

    python scripts/rebuild_parity.py --insights --json   # Phase 8: the Insights answers

With --insights it compares every Insights answer and the data tables the
same way, over the last 28 days (rebuild Phase 8): each request carries that
day as the caller's day, and the services compute the same day here. The two
history tables, which hold every row whatever the day, are compared once. An
answer both sides refuse alike (the Strength screen before its reference is
in the store) is listed as such, never as a difference. The local side reads
a throwaway local state file: the flexibility record keeps a mirror in the
repo's .sync_state.json, and this PC's copy is not the store's.
"""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for extra in (ROOT, ROOT / "api", ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

DAYS = 14

#: Each endpoint, the services function behind it and the model that shapes it.
ENDPOINTS = ("today", "week", "readiness", "sleep", "strain")


def _paths(day: date) -> dict[str, str]:
    q = f"?date={day.isoformat()}"
    return {"today": f"/api/today{q}", "week": f"/api/today/week{q}",
            "readiness": f"/api/today/readiness{q}", "sleep": f"/api/today/sleep{q}",
            "strain": f"/api/today/strain{q}"}


def differences(live: Any, local: Any, path: str = "") -> list[str]:
    """The field paths where two JSON answers differ (values never included)."""
    if isinstance(live, dict) and isinstance(local, dict):
        out: list[str] = []
        for key in sorted(set(live) | set(local)):
            sub = f"{path}.{key}" if path else str(key)
            if key not in live or key not in local:
                out.append(sub)
            else:
                out += differences(live[key], local[key], sub)
        return out
    if isinstance(live, list) and isinstance(local, list):
        if len(live) != len(local):
            return [f"{path}[length]"]
        out = []
        for i, (a, b) in enumerate(zip(live, local)):
            out += differences(a, b, f"{path}[{i}]")
        return out
    return [] if live == local else [path or "(answer)"]


def sleep_rule_broken(answer: dict) -> bool:
    """A night with no score that still carries a night panel or the stepper."""
    scored = bool((answer.get("contributors") or {}).get("scored"))
    return not scored and (answer.get("night") is not None or answer.get("wake") is not None)


def local_answers(repo, day: date, today: date) -> dict[str, dict]:
    """The services' own answers for `day`, through the engine's response models."""
    from healthapi.schemas import (ReadinessDetailOut, SleepDetailOut, StrainDetailOut, TodayOut,
                                   TodayWeekOut)
    from services import home, home_detail
    return {
        "today": TodayOut(**home.cards(repo, day, today)).model_dump(mode="json"),
        "week": TodayWeekOut(**home.week_strip(repo, day, today)).model_dump(mode="json"),
        "readiness": ReadinessDetailOut(**home_detail.readiness_detail(repo, day, today)).model_dump(mode="json"),
        "sleep": SleepDetailOut(**home_detail.sleep_detail(repo, day, today)).model_dump(mode="json"),
        "strain": StrainDetailOut(**home_detail.strain_detail(repo, day, today)).model_dump(mode="json"),
    }


def run(days: int = DAYS) -> dict:
    import rebuild_p0_measure as live
    from services.config import load_config
    from services.repository import Repository

    secrets = ROOT / ".streamlit" / "secrets.toml"
    overrides = tomllib.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
    repo = Repository(load_config({**overrides, "HEALTH_SYSTEM_OF_RECORD": "supabase"}))
    today = live.owner_today()
    report: dict = {"today": today.isoformat(), "days": days, "differences": [],
                    "sleep_rule_violations": [], "unanswered": []}
    for back in range(days):
        day = today - timedelta(days=back)
        mine = local_answers(repo, day, today)
        for name, path in _paths(day).items():
            reply = live.call("worker", path)
            if reply.get("status") != 200 or not isinstance(reply.get("answer"), dict):
                report["unanswered"].append({"date": day.isoformat(), "endpoint": name,
                                             "status": reply.get("status")})
                continue
            for field in differences(reply["answer"], mine[name]):
                report["differences"].append({"date": day.isoformat(), "endpoint": name, "field": field})
            if name == "sleep" and sleep_rule_broken(reply["answer"]):
                report["sleep_rule_violations"].append(day.isoformat())
    return report


# ── Phase 8: the Insights answers ────────────────────────────────────────────

INSIGHTS_DAYS = 28
#: Compared on every day: the caller's day changes the answer.
INSIGHTS_DAILY = {
    "strength": "/api/insights/strength", "metabolism": "/api/insights/metabolism",
    "flexibility": "/api/insights/flexibility", "engine": "/api/insights/engine",
    "queue": "/api/insights/queue", "trends": "/api/insights/trends",
    "sleep_architecture": "/api/insights/sleep-architecture",
    "engine_view": "/api/data/tables/engine_view", "session_checks": "/api/data/session-checks",
}
#: Compared once: every row, whatever the day.
INSIGHTS_ONCE = {"blend_history": "/api/data/tables/blend_history",
                 "metrics_history": "/api/data/tables/metrics_history"}


def local_insight(repo, name: str, day: date) -> tuple[int, dict]:
    """(status, answer) the services give for one Insights endpoint with `day` as the
    caller's day, through the engine's response models; a refusal as the engine words it."""
    from healthapi import schemas_insights as si
    from services import flexibility_screen as fxs
    from services import insights_screens as ins
    shaped = {
        "strength": lambda: si.StrengthOut(**ins.strength(repo, day)),
        "metabolism": lambda: si.MetabolismOut(**ins.metabolism(repo, day)),
        "flexibility": lambda: si.FlexibilityOut(**fxs.screen(repo, day)),
        "engine": lambda: si.EngineDataOut(**ins.engine_data(repo, day)),
        "queue": lambda: si.QueueOut(**ins.queue(repo, day)),
        "trends": lambda: si.TrendsOut(**ins.trends(repo, day)),
        "sleep_architecture": lambda: si.SleepArchitectureOut(**ins.sleep_architecture_view(repo, day)),
        "engine_view": lambda: si.DataTableOut(**ins.data_table(repo, day, "engine_view")),
        "blend_history": lambda: si.DataTableOut(**ins.data_table(repo, day, "blend_history")),
        "metrics_history": lambda: si.DataTableOut(**ins.data_table(repo, day, "metrics_history")),
        "session_checks": lambda: si.SessionChecksOut(**ins.session_checks(repo, day)),
    }
    try:
        return 200, shaped[name]().model_dump(mode="json")
    except ins.ReferenceMissing:
        return 409, {"error": "strength_reference_missing"}


def compare_insight(report: dict, name: str, day: date, reply: dict, mine: tuple) -> None:
    """One endpoint's comparison into the report: field differences when both answered,
    a refusal both gave alike, or a mismatch of status (one side answered, the other not)."""
    status, local = mine
    if reply.get("status") == status == 200 and isinstance(reply.get("answer"), dict):
        for field in differences(reply["answer"], local):
            report["differences"].append({"date": day.isoformat(), "endpoint": name, "field": field})
    elif reply.get("status") == status and reply.get("answer") == local:
        report["refused_alike"].append({"date": day.isoformat(), "endpoint": name,
                                        "error": str(local.get("error", ""))})
    else:
        report["unanswered"].append({"date": day.isoformat(), "endpoint": name,
                                     "status": reply.get("status"), "local_status": status})


def run_insights(days: int = INSIGHTS_DAYS) -> dict:
    import tempfile

    import rebuild_p0_measure as live
    from services.clients import local_cache
    from services.config import load_config
    from services.repository import Repository

    secrets = ROOT / ".streamlit" / "secrets.toml"
    overrides = tomllib.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
    today = live.owner_today()
    report: dict = {"today": today.isoformat(), "days": days, "differences": [],
                    "refused_alike": [], "unanswered": []}
    real_state = local_cache._DEFAULT_PATH
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        local_cache._DEFAULT_PATH = Path(tmp) / "sync_state.json"
        try:
            repo = Repository(load_config({**overrides, "HEALTH_SYSTEM_OF_RECORD": "supabase"}))
            for back in range(days):
                day = today - timedelta(days=back)
                for name, path in INSIGHTS_DAILY.items():
                    compare_insight(report, name, day, live.call("worker", path, local_date=day),
                                    local_insight(repo, name, day))
            for name, path in INSIGHTS_ONCE.items():
                compare_insight(report, name, today, live.call("worker", path, local_date=today),
                                local_insight(repo, name, today))
        finally:
            local_cache._DEFAULT_PATH = real_state
    return report


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--days", type=int, default=None)
    ap.add_argument("--insights", action="store_true", help="the Insights answers (Phase 8)")
    args = ap.parse_args()
    if args.insights:
        report = run_insights(args.days or INSIGHTS_DAYS)
        if args.json:
            print(json.dumps(report, indent=2))
            return 0
        print(f"{report['days']} days up to {report['today']}: {len(report['differences'])} differences, "
              f"{len(report['unanswered'])} answered by one side only, "
              f"{len(report['refused_alike'])} refused alike")
        for d in report["differences"]:
            print(f"  {d['date']}  {d['endpoint']:<18}  {d['field']}")
        for u in report["unanswered"]:
            print(f"  {u['date']}  {u['endpoint']:<18}  engine HTTP {u['status']}, services {u['local_status']}")
        for endpoint, error in sorted({(r["endpoint"], r["error"]) for r in report["refused_alike"]}):
            print(f"  refused alike: {endpoint} ({error})")
        return 0
    report = run(args.days or DAYS)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(f"{report['days']} days up to {report['today']}: {len(report['differences'])} differences, "
          f"{len(report['sleep_rule_violations'])} sleep-rule violations, "
          f"{len(report['unanswered'])} requests unanswered")
    for d in report["differences"]:
        print(f"  {d['date']}  {d['endpoint']:<9}  {d['field']}")
    for day in report["sleep_rule_violations"]:
        print(f"  {day}  sleep      a night panel without a score")
    for u in report["unanswered"]:
        print(f"  {u['date']}  {u['endpoint']:<9}  no answer (HTTP {u['status']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
