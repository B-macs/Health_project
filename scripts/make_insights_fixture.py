# -*- coding: utf-8 -*-
"""Made-up Insights answers for the phone app's mock engine (rebuild Phase 8).

    python scripts/make_insights_fixture.py           # write app/dev/insights_fixture.json
    python scripts/make_insights_fixture.py --check   # 1 when the file is not this output

The phone draws what the engine sends and holds no rule. So the mock's Insights
answers are the engine's OWN answers, over a made-up store: the real routes,
the real services and the real response models, run against a fake Supabase
seeded with invented sessions, weigh-ins, check-ins and a flexibility capture
walked step by step through the battery. A phone test that reads this file
reads exactly the shapes and the words the engine would send. Every name and
number in the seed is invented; the protocol words are the engine's own.

The capture is walked with readings that make the battery stop early, so the
mock can show the early answer ("that is your answer, stop here"), and the
engine's order after every step is kept, so the phone is tested against the
order the engine gives, never one it works out itself.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for extra in (ROOT, ROOT / "api"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

OUT = ROOT / "app" / "dev" / "insights_fixture.json"
#: The fixture's day: a Tuesday of the 12-week block's first week.
TODAY = date(2026, 10, 20)
KEY = "fixture-engine-key"

#: A made-up strength reference in strength_baselines' shapes (no personal value).
REFERENCE = {
    "peaks": {"Machine Chest Press": (60.0, 10, 1.0, "same exercise"),
              "Hack Squat": (100.0, 10, 1.0, "same exercise"),
              "Single-Arm DB Row": (30.0, 10, 1.0, "same exercise")},
    "region_prior": {"upper_body": 0.4, "core": 0.2, "lower_body": 0.4},
    "pr_rir": 1.0, "anchor_date": date(2026, 7, 30), "anchor_value": 50.0,
    "hold_baselines": {"Bunkie — Medial Stabilizing Line (Timed)": (30.0, "made up")},
    "imbalances": {"overactive_tight": ["Made-up tight muscle"],
                   "underactive_weak": ["Made-up weak muscle", "Another made-up muscle"]},
}


class _Client:
    """The engine app over the made-up store, answering like the Worker would pass on."""

    def __init__(self, repo, runner):
        import os
        from fastapi.testclient import TestClient
        from healthapi.deps import get_repository, get_sync_runner
        from healthapi.main import create_app
        os.environ["HEALTH_ENGINE_KEY"] = KEY
        os.environ.pop("HEALTH_PROBES", None)
        app = create_app(startup=False)
        app.dependency_overrides[get_repository] = lambda: repo
        app.dependency_overrides[get_sync_runner] = lambda: runner
        self.client = TestClient(app)

    def __call__(self, method: str, path: str, body=None, local: date = TODAY) -> dict:
        headers = {"X-Engine-Key": KEY, "X-Local-Date": local.isoformat()}
        if method in ("get", "delete"):
            r = getattr(self.client, method)(path, headers=headers)
        else:
            r = getattr(self.client, method)(path, json=body, headers=headers)
        if r.status_code != 200:
            raise RuntimeError(f"{method.upper()} {path}: {r.status_code} {r.text[:200]}")
        return r.json()


def _seed(repo, ask) -> None:
    from services import insights_screens as ins
    from services import sessions as sess
    from services.body_composition import ScaleReading
    import goal_block as gb

    repo.set_phases([sess.build_phase(5, gb.START)])
    repo.set_config("current_stage", "2")
    repo.set_config(ins.REFERENCE_KEY, ins.reference_json(REFERENCE))
    # Six weeks of made-up lifting: three lifts, rising a little each week.
    lifts = (("Machine Chest Press", 45.0), ("Hack Squat", 80.0), ("Single-Arm DB Row", 22.5))
    for week in range(6):
        for offset, (name, base) in enumerate(lifts):
            day = TODAY - timedelta(days=7 * (5 - week) + offset + 1)
            weight = base + 2.5 * week
            ask("post", "/api/training/sessions", {
                "session_id": f"{day}-{abs(hash(name)) % 10**8:08d}", "date": day.isoformat(),
                "kind": "plan", "duration_minutes": 45, "session_rpe": 6, "exercises": [{
                    "exercise_id": f"ex-{day}-{name}", "exercise": {
                        "name": name, "type": "reps", "sets": 3, "reps": 10,
                        "equipment_type": "machine"},
                    "sets": [{"set_num": i, "reps": 10, "weight": weight,
                              "ts": f"{day}T08:1{i}:00"} for i in (1, 2, 3)]}]}, local=day)
    # Made-up weigh-ins, every few days over three months.
    repo.save_scale_readings([
        ScaleReading(taken_at=datetime(2026, 7, 20, 7, 0) + timedelta(days=4 * i),
                     weight_kg=round(82.0 - 0.06 * i, 2), body_fat_pct=round(18.5 - 0.04 * i, 2))
        for i in range(24)])
    # Two made-up gym scans on a made-up machine.
    from services.body_composition import InBodyScan
    repo.save_inbody_scans([
        InBodyScan(taken_at=datetime(2026, 8, 1, 9, 0), weight_kg=81.4, bmi=24.6,
                   total_body_water_l=48.2, skeletal_muscle_kg=37.6, ecw_tbw=0.374,
                   phase_angle_deg=6.4, device="Made-up scanner"),
        InBodyScan(taken_at=datetime(2026, 9, 26, 9, 0), weight_kg=80.9, bmi=24.4,
                   total_body_water_l=48.6, skeletal_muscle_kg=37.9, ecw_tbw=0.372,
                   phase_angle_deg=6.6, device="Made-up scanner")])
    # A made-up check-in with a note, parsed on save: it reaches the warnings calendar.
    from services import checkin_form as cf
    ask("put", "/api/checkin", {"date": TODAY.isoformat(), "opened_entry": False, "values": {
        **cf.FORM_DEFAULTS, "tightness_score": 4, "subjective_tightness": "slight tightness lower back"}})


def _bio(day: date):
    """A made-up night's blended readings: each day's numbers come from its date."""
    from services.models import BiometricRecord
    i = day.toordinal()
    return BiometricRecord(
        date=day.isoformat(), hrv_ms=40.0 + i % 6, resting_heart_rate=54.0 + i % 4,
        sleep_duration_hours=6.75 + (i % 4) * 0.25, steps=7000 + 250 * (i % 9),
        oura_hrv_balance=70.0 + i % 7, oura_recovery_index=80.0, oura_previous_night=75.0,
        oura_resting_heart_rate_score=85.0, oura_body_temperature=90.0,
        oura_previous_day_activity=65.0, oura_sleep_regularity=70.0,
        oura_activity_balance=72.0, oura_temperature_deviation=round(-0.1 + 0.05 * (i % 5), 2))


def _made_up_reads(repo) -> None:
    """The reads a fake store cannot answer from its tables (the devices' blend, the
    fused nights, the trend window, the history tables), answered with made-up rows."""
    def rolling(days=28, today=None):
        end = today or TODAY
        return [_bio(end - timedelta(days=days - 1 - k)) for k in range(days)]

    def history():
        return [{"date": (TODAY - timedelta(days=13 - k)).isoformat(), "hrv_ms": 40.0 + k % 6,
                 "resting_heart_rate": 54.0 + k % 4, "sleep_duration_hours": 7.0 + (k % 3) * 0.25,
                 "steps": 8000 + 100 * k} for k in range(14)]

    def metrics():
        return [{"date": (TODAY - timedelta(days=13 - k)).isoformat(),
                 "readiness": 70.0 + k % 9, "sleep_score": 75.0 + k % 7, "strain": 8.0 + k % 6}
                for k in range(14)]

    nights = [
        {"date": "2026-10-18", "source": "fused", "phantom_wake_minutes": 12,
         "master_sleep_hours": 7.1, "oura_sleep_hours": 6.9,
         "oura_hypnogram": "4222331222333112224", "master_hypnogram": "4222331222333112224",
         "garmin_hypnogram": "2222331222333112222", "agreement_pct": 74, "cohen_kappa": 0.41,
         "window_overlap_pct": 95, "garmin_covered_minutes": 410, "minutes": 430},
        {"date": "2026-10-19", "source": "fused", "phantom_wake_minutes": 0,
         "master_sleep_hours": 7.4, "oura_sleep_hours": 7.4,
         "oura_hypnogram": "4222233112222331224", "master_hypnogram": "4222233112222331224",
         "garmin_hypnogram": "2222233112222331222", "agreement_pct": 81, "cohen_kappa": 0.52,
         "window_overlap_pct": 97, "garmin_covered_minutes": 440, "minutes": 450},
        {"date": "2026-10-20", "source": "garmin_only", "master_hypnogram": "2223"},
    ]
    days = [TODAY - timedelta(days=30 - k) for k in range(30)]
    trend = {
        "biometrics": [{"date": d.isoformat(), "hrv_ms": 40.0 + k % 7, "resting_heart_rate": 55.0 + k % 3,
                        "sleep_duration_hours": 7.0 + (k % 4) * 0.25, "sleep_deep_hours": 1.2,
                        "active_energy_kcal": 500.0, "weight_kg": 81.0, "steps": 8000}
                       for k, d in enumerate(days)],
        "readiness": [{"date": d.isoformat(), "avg_tightness": 2.0 + k % 3, "max_pain": k % 2,
                       "avg_stress": 2.0 + (k % 3) * 0.5, "travel": 0, "avg_alcohol": 0.0}
                      for k, d in enumerate(days)],
        "sessions": [{"date": d.isoformat(), "total_au": 300.0 + 10 * (k % 5)}
                     for k, d in enumerate(days) if k % 2 == 0],
    }
    repo.get_biometric_rolling = rolling
    repo.get_biometric_blend_history = lambda *a, **k: history()
    repo.get_metrics_history = lambda *a, **k: metrics()
    repo.get_sleep_fusion_history = lambda *a, **k: nights
    repo.get_macro_trend_data = lambda days=90, today=None: trend


def _capture(ask) -> dict:
    """A capture walked through the battery: the engine's answer after the start and
    after every step, until the battery answers early."""
    states = [ask("post", "/api/insights/flexibility/capture", {"cold": True})]
    # Made-up readings: the first slot's tests pass, the next stop the battery.
    values = {"left": 30.0, "right": 32.0}
    for _ in range(12):
        state = states[-1]
        if state["early_pattern"]:
            break
        todo = [t for t in state["order"] if t["key"] not in state["done"]]
        if not todo:
            break
        test = todo[0]
        entered = values if test["bilateral"] else {"": 45.0}
        body = {"test_key": test["key"], "entered": entered,
                "setup_value": 60.0 if test["setup_input"] else None,
                "load": 2.0 if test["takes_load"] else None}
        states.append(ask("put", "/api/insights/flexibility/capture", body))
        values = {"left": values["left"] + 25.0, "right": values["right"] + 25.0}
    return {"states": states}


def build() -> dict:
    from services import background_sync, record_cache
    from services.clients import local_cache
    from tests._record_store import FakeStore, new_local_copy, record_config, record_repo

    # A Repository keeps its SQLite file open until the process ends (Windows refuses to
    # delete an open file), so the folder is left for the system to clear.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        path = new_local_copy(Path(tmp))
        # The flexibility record and its draft keep a local mirror in .sync_state.json at
        # the repo root, beside the owner's own: the build reads and writes a throwaway one
        # (as tests/conftest.py does), never the real file.
        real_state = local_cache._DEFAULT_PATH
        local_cache._DEFAULT_PATH = Path(tmp) / "sync_state.json"
        try:
            store = FakeStore()
            repo = record_repo(path, store)
            runner = background_sync.BackgroundSyncRunner(record_config(path))
            ask = _Client(repo, runner)
            out: dict = {"today": TODAY.isoformat()}
            out["flexibility_empty"] = ask("get", "/api/insights/flexibility")
            _seed(repo, ask)
            out["strength"] = {m["label"]: ask("get", f"/api/insights/strength?metric={m['label']}")
                               for m in ask("get", "/api/insights/strength")["metrics"]}
            metab = ask("get", "/api/insights/metabolism")
            # Each measure over all time, and the weight over every period, one step back too:
            # what the screen's pickers and arrows ask for (the mock answers the nearest).
            asks = [(m["label"], "all", 0) for m in metab["metrics"]]
            asks += [("Weight", r["kind"], off) for r in metab["ranges"] if r["kind"] != "all"
                     for off in (0, -1)]
            out["metabolism"] = {
                f"{metric}|{kind}|{off}": ask(
                    "get", f"/api/insights/metabolism?metric={metric}&kind={kind}&offset={off}")
                for metric, kind, off in asks}
            out["capture"] = _capture(ask)
            out["flexibility_capturing"] = ask("get", "/api/insights/flexibility")
            out["flexibility_populated"] = ask("post", "/api/insights/flexibility/capture/finish")
            out["trends_closed"] = ask("get", "/api/insights/trends")
            out["sleep_architecture_empty"] = ask("get", "/api/insights/sleep-architecture")
            _made_up_reads(repo)
            out["engine"] = ask("get", "/api/insights/engine")
            out["queue"] = ask("get", "/api/insights/queue")
            out["trends"] = ask("get", "/api/insights/trends")
            out["sleep_architecture"] = ask("get", "/api/insights/sleep-architecture")
            out["tables"] = {t: ask("get", f"/api/data/tables/{t}")
                             for t in ("engine_view", "blend_history", "metrics_history")}
            out["session_checks"] = ask("get", "/api/data/session-checks")
            out["settings"] = ask("get", "/api/settings")
            return out
        finally:
            local_cache._DEFAULT_PATH = real_state
            record_cache.forget(path)


def text() -> str:
    return json.dumps(build(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 when the file is not this output")
    args = ap.parse_args()
    fresh = text()
    if args.check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8").replace("\r\n", "\n") == fresh
        print("insights_fixture.json is current" if same else "insights_fixture.json is stale: run the script")
        return 0 if same else 1
    OUT.write_text(fresh, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
