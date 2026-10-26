"""The Insights screens, the Sync tab, the Oura login and Settings through
the engine API (rebuild Phase 2, milestone 5).

Through the real Repository over a fake Supabase (tests/_record_store.py).
What it pins, each against the service the Streamlit page draws from:

- Strength reads its personal reference from the store (rule 7: the files
  stay out of the image) and says so when it is not there;
- Metabolism's period and its change's tone (F11);
- Flexibility: the empty screen with its guide, the capture flow kept in
  the store (F13), the battery's early answer, the report once finished;
- Engine Data shows the shared verdict's words (F4);
- the queue, trends, sleep architecture and the data tables answer from
  the store, and a failed read says so;
- a manual sync and the Oura login refuse unless the engine is the
  background writer (rule 2), and the login never answers a token;
- the plan's start seeds a first block once, never over a running one.

Synthetic readings only; no network.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import goal_block as gb  # noqa: E402
from healthapi.deps import get_repository, get_sync_runner  # noqa: E402
from healthapi.main import create_app  # noqa: E402
from services import background_writer as bw  # noqa: E402
from services import insights_screens as ins  # noqa: E402
from services import record_cache, supabase_store  # noqa: E402
from services import sessions as sess  # noqa: E402
from services.background_sync import BackgroundSyncRunner  # noqa: E402
from services.body_composition import ScaleReading  # noqa: E402
from services.clients import oura  # noqa: E402
from tests._record_store import FakeStore, new_local_copy, record_config, record_repo  # noqa: E402

KEY = "test-engine-key"
TODAY = gb.START      # Monday 2026-10-19

#: A made-up reference in strength_baselines' shapes (no personal value).
REFERENCE = {
    "peaks": {"Machine Chest Press": (60.0, 10, 1.0, "same exercise"),
              "Hack Squat": (100.0, 10, 1.0, "same exercise")},
    "region_prior": {"upper_body": 0.4, "core": 0.2, "lower_body": 0.4},
    "pr_rir": 1.0, "anchor_date": date(2026, 7, 30), "anchor_value": 50.0,
    "hold_baselines": {"Bunkie — Medial Stabilizing Line (Timed)": (30.0, "made up")},
    "imbalances": {"overactive_tight": ["a made-up muscle"], "underactive_weak": []},
}


@pytest.fixture(autouse=True)
def _empty_outbox():
    supabase_store.OUTBOX.drain()
    yield
    supabase_store.OUTBOX.drain()


class Env:
    def __init__(self, path: str):
        self.store = FakeStore()
        self.repo = record_repo(path, self.store)
        self.repo.set_phases([sess.build_phase(5, TODAY)])
        self.repo.set_config("current_stage", "2")
        self.runner = BackgroundSyncRunner(record_config(path))

    def call(self, monkeypatch, method, path, body=None, local=TODAY):
        monkeypatch.setenv("HEALTH_ENGINE_KEY", KEY)
        monkeypatch.delenv("HEALTH_PROBES", raising=False)
        app = create_app(startup=False)
        app.dependency_overrides[get_repository] = lambda: self.repo
        app.dependency_overrides[get_sync_runner] = lambda: self.runner
        headers = {"X-Engine-Key": KEY, "X-Local-Date": local.isoformat()}
        with TestClient(app) as c:
            if method in ("get", "delete"):
                return getattr(c, method)(path, headers=headers)
            return getattr(c, method)(path, json=body, headers=headers)

    def ok(self, monkeypatch, method, path, body=None, local=TODAY):
        r = self.call(monkeypatch, method, path, body, local)
        assert r.status_code == 200, r.text
        return r.json()

    def write_as(self, writer: str):
        self.repo.set_config(bw.CONFIG_KEY, writer)


@pytest.fixture
def env(tmp_path):
    path = new_local_copy(tmp_path)
    yield Env(path)
    record_cache.forget(path)


def _log(env, monkeypatch, day: date, name: str, reps: int, weight: float):
    body = {"session_id": f"{day}-{abs(hash(name)) % 10**8:08d}", "date": day.isoformat(),
            "kind": "plan", "duration_minutes": 45, "session_rpe": 6, "exercises": [{
                "exercise_id": f"ex-{day}-{name}", "exercise": {
                    "name": name, "type": "reps", "sets": 3, "reps": reps,
                    "equipment_type": "machine"},
                "sets": [{"set_num": i, "reps": reps, "weight": weight,
                          "ts": f"{day}T08:1{i}:00"} for i in (1, 2, 3)]}]}
    env.ok(monkeypatch, "post", "/api/training/sessions", body, local=day)


# ── Strength ─────────────────────────────────────────────────────────────────

def test_strength_says_when_its_reference_is_not_in_the_store(env, monkeypatch):
    r = env.call(monkeypatch, "get", "/api/insights/strength")
    assert r.status_code == 409 and r.json() == {"error": "strength_reference_missing"}


def test_strength_reads_its_reference_from_the_store(env, monkeypatch):
    env.repo.set_config(ins.REFERENCE_KEY, ins.reference_json(REFERENCE))
    for back in (14, 7, 2):
        _log(env, monkeypatch, TODAY - timedelta(days=back), "Machine Chest Press", 10, 50.0)
    body = env.ok(monkeypatch, "get", "/api/insights/strength")
    assert body["metric"] == ins.DEFAULT_STRENGTH_METRIC and body["load_error"] is None
    assert len(body["tonnage"]) == 6 and body["readout"]["points"]
    assert [m["label"] for m in body["metrics"]][0] == ins.DEFAULT_STRENGTH_METRIC
    assert body["imbalance_count"] == 1 and {c["region"] for c in body["regions"]}
    # The redone page (2026-10-20): the whole page in every answer, whatever metric asked.
    assert {a["region"] for a in body["areas"]} == {"upper_body", "core", "lower_body"}
    assert len(body["trend"]) == 6 and body["trend_axis"]["hi"] > body["trend_axis"]["lo"]
    assert body["volume"]["last_full"]["kg"] == 2 * 3 * 10 * 50.0, "the last full week"
    assert body["volume"]["this_week"]["kg"] == 0.0, "this week so far, apart: nothing yet"
    upper = env.ok(monkeypatch, "get", "/api/insights/strength?metric=Upper Body Tonnage")
    assert upper["volume"] == body["volume"] and upper["areas"] == body["areas"]
    assert not upper["readout"]["points"] and upper["axis"]["lo"] == 0.0
    assert upper["tonnage"][-2]["upper_body"]["kg"] == 2 * 3 * 10 * 50.0, "two sessions last week"
    r = env.call(monkeypatch, "get", "/api/insights/strength?metric=Biceps")
    assert r.status_code == 422


def test_the_stored_reference_reads_back_as_written():
    class Store:
        value = ins.reference_json(REFERENCE)

        def get_config_value(self, key):
            return self.value if key == ins.REFERENCE_KEY else None
    assert ins.reference_from_store(Store()) == REFERENCE


# ── Metabolism ───────────────────────────────────────────────────────────────

def test_metabolism_shows_the_period_and_colours_the_change_by_its_measure(env, monkeypatch):
    env.repo.save_scale_readings([
        ScaleReading(taken_at=datetime(2026, 10, d, 7, 0), weight_kg=82.0 - 0.1 * d,
                     body_fat_pct=18.0 - 0.05 * d) for d in (5, 9, 12, 16)])
    body = env.ok(monkeypatch, "get", "/api/insights/metabolism?metric=Fat mass&kind=month")
    assert body["latest"]["date"] == "2026-10-16" and body["split"]["fat"] > 0
    series = body["series"]
    assert series["window"]["kind"] == "month" and len(series["points"]) == 4
    assert series["change"] < 0 and series["tone"] == "good", "less fat is better (F11)"
    weight = env.ok(monkeypatch, "get", "/api/insights/metabolism?metric=Weight&kind=month")
    assert weight["series"]["tone"] == "neutral", "weight is not a goal"
    assert env.call(monkeypatch, "get", "/api/insights/metabolism?kind=decade").status_code == 422
    assert env.call(monkeypatch, "get", "/api/insights/metabolism?offset=1").status_code == 422


# ── Flexibility ──────────────────────────────────────────────────────────────

def test_flexibility_opens_empty_with_its_guide(env, monkeypatch):
    body = env.ok(monkeypatch, "get", "/api/insights/flexibility")
    assert body["state"] == "empty" and body["report"] is None and body["capture"] is None
    assert body["guide"]["slots"] and body["guide"]["measures"]


def test_a_capture_is_kept_in_the_store_and_finishes_into_a_report(env, monkeypatch):
    capture = env.ok(monkeypatch, "post", "/api/insights/flexibility/capture", {"cold": True})
    first = capture["order"][0]
    assert capture["cold"] and first["lock"] and first["bilateral"]
    again = env.ok(monkeypatch, "post", "/api/insights/flexibility/capture", {"cold": False})
    assert again["cold"], "an assessment in progress is answered, never replaced"
    step = env.ok(monkeypatch, "put", "/api/insights/flexibility/capture",
                  {"test_key": first["key"], "entered": {"left": 30.0, "right": 32.0}})
    assert {r["side"] for r in step["readings"]} == {"left", "right"}
    assert first["key"] in step["done"]
    stored = env.repo.get_config_value("flexibility_draft")
    assert stored and json.loads(stored)["readings"], "kept in the store (F13)"
    bad = env.call(monkeypatch, "put", "/api/insights/flexibility/capture",
                   {"test_key": first["key"], "entered": {"middle": 1.0}})
    assert bad.status_code == 422 and bad.json()["error"].startswith("unknown_side")
    done = env.ok(monkeypatch, "post", "/api/insights/flexibility/capture/finish")
    assert done["state"] == "populated" and done["capture"] is None
    report = done["report"]
    assert report["slots_total"] >= len(report["slots"]), "the battery's own count (F10)"
    assert report["retest_text"]


def test_the_capture_names_its_tests_and_says_why_it_stopped(env, monkeypatch):
    """The phone shows what the Streamlit screen shows: each reading by its test's name,
    the cluster, why the slot that stopped answered early, and the slot it stopped at."""
    assert env.ok(monkeypatch, "get", "/api/insights/flexibility")["guide"]["cluster_label"]
    state = env.ok(monkeypatch, "post", "/api/insights/flexibility/capture", {"cold": True})
    assert state["early_pattern"] is None and state["early_reason"] == ""
    labels = {t["key"]: t["label"] for t in state["order"]}
    values = {"left": 30.0, "right": 32.0}
    for _ in range(12):
        if state["early_pattern"]:
            break
        test = next(t for t in state["order"] if t["key"] not in state["done"])
        state = env.ok(monkeypatch, "put", "/api/insights/flexibility/capture", {
            "test_key": test["key"],
            "entered": values if test["bilateral"] else {"": 45.0},
            "setup_value": 60.0 if test["setup_input"] else None,
            "load": 2.0 if test["takes_load"] else None})
        values = {side: v + 25.0 for side, v in values.items()}
    assert state["early_pattern"] and state["early_reason"], "the early answer says why"
    assert all(r["label"] == labels[r["test_key"]] for r in state["readings"])
    report = env.ok(monkeypatch, "post", "/api/insights/flexibility/capture/finish")["report"]
    assert report["cluster_label"] and report["stopped_at"] == report["slots"][-1]["label"]
    assert report["reason"] == state["early_reason"]
    assert all(r["label"] == labels[r["test_key"]] for r in report["readings"])


def test_a_capture_can_be_dropped(env, monkeypatch):
    env.ok(monkeypatch, "post", "/api/insights/flexibility/capture", {"cold": True})
    assert env.ok(monkeypatch, "delete", "/api/insights/flexibility/capture") == {"cleared": True}
    assert env.ok(monkeypatch, "get", "/api/insights/flexibility")["capture"] is None
    r = env.call(monkeypatch, "post", "/api/insights/flexibility/capture/finish")
    assert r.status_code == 409 and r.json() == {"error": "no_capture"}


def test_missing_readings_are_added_without_repeating_the_slot(env, monkeypatch):
    capture = env.ok(monkeypatch, "post", "/api/insights/flexibility/capture", {"cold": True})
    first = capture["order"][0]
    env.ok(monkeypatch, "put", "/api/insights/flexibility/capture",
           {"test_key": first["key"], "entered": {"left": 30.0}})
    done = env.ok(monkeypatch, "post", "/api/insights/flexibility/capture/finish")
    missing = done["report"]["missing"]
    if not missing:
        pytest.skip("the battery answered without waiting on a reading")
    entries = [{**{k: m[k] for k in ("test_key", "side", "setup")}, "value": 31.0}
               for m in missing]
    filled = env.ok(monkeypatch, "post", "/api/insights/flexibility/missing", {"entries": entries})
    assert filled["report"]["missing"] != missing


# ── Engine Data, the queue, trends, sleep architecture ───────────────────────

def test_engine_data_shows_the_shared_verdicts_words(env, monkeypatch):
    from services import decision, insights
    body = env.ok(monkeypatch, "get", "/api/insights/engine")
    assert body["load_error"] is None
    assert body["directive"]["words"] == insights.directive_words(
        decision.day_verdict(env.repo, TODAY))
    assert body["traffic_light"]["no_reading"] and len(body["traffic_light"]["cards"]) == 4
    assert len(body["acwr"]["chart"]["au"]) == 28 and body["stage"]
    chart = body["acwr"]["chart"]
    assert chart["hi"] >= max(chart["au"]) and chart["hi"] > 0, "the chart's top, from the engine"
    assert body["volume_hi"] >= max(w["kg"] for w in body["volume"])


def test_engine_data_says_when_its_reads_fail(env, monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("the store did not answer")
    monkeypatch.setattr(env.repo, "get_biometric_rolling", broken)
    body = env.ok(monkeypatch, "get", "/api/insights/engine")
    assert body["load_error"].startswith("RuntimeError") and body["directive"] is None


def test_the_queue_opens_on_a_month_and_steps(env, monkeypatch):
    body = env.ok(monkeypatch, "get", "/api/insights/queue")
    assert (body["year"], body["month"]) == (2026, 10)
    assert body["previous"] == {"year": 2026, "month": 9}
    assert any(d["is_today"] for week in body["weeks"] for d in week)
    assert env.ok(monkeypatch, "get", "/api/insights/queue?year=2026&month=12")["month"] == 12
    assert env.ok(monkeypatch, "post", "/api/insights/queue/process") == {"total": 0, "errors": []}


def test_the_warnings_are_the_days_the_load_was_lowered(env, monkeypatch):
    """The owner, 2026-10-21: "I thought the warning was the days that it says reduce
    load because of tiredness or other reason strain". Each day's own decision, with the
    reading it named; a day with no reading, a clear day and a day after his are none."""
    import types
    from services import load_warnings
    kinds = {TODAY - timedelta(days=2): ("error", "Made-up reading A."),
             TODAY - timedelta(days=1): ("warning", "Made-up reading B."),
             TODAY - timedelta(days=5): ("info", ""),
             TODAY: ("neutral", "")}
    asked: list[date] = []

    def verdict(repo, day):
        asked.append(day)
        kind, cause = kinds.get(day, ("", ""))
        return types.SimpleNamespace(banner_kind=kind, cause=cause)
    monkeypatch.setattr(load_warnings.decision, "day_verdict", verdict)
    body = env.ok(monkeypatch, "get", "/api/insights/warnings")
    assert (body["year"], body["month"]) == (TODAY.year, TODAY.month), "opens on his month"
    days = {d["date"]: d for week in body["weeks"] for d in week}
    assert days[(TODAY - timedelta(days=2)).isoformat()]["level"] == "rest"
    assert days[(TODAY - timedelta(days=2)).isoformat()]["cause"] == "Made-up reading A."
    assert days[(TODAY - timedelta(days=1)).isoformat()]["level"] == "reduced"
    assert days[(TODAY - timedelta(days=5)).isoformat()]["level"] == "held"
    assert days[TODAY.isoformat()]["level"] is None and days[TODAY.isoformat()]["is_today"]
    assert body["counts"] == {"rest": 1, "reduced": 1, "held": 1}
    assert max(asked) == TODAY, "no day after his is worked out"
    later = env.ok(monkeypatch, "get", f"/api/insights/warnings?year={TODAY.year}&month={TODAY.month % 12 + 1}")
    assert all(d["level"] is None for week in later["weeks"] for d in week)


def test_trends_wait_for_enough_data(env, monkeypatch):
    body = env.ok(monkeypatch, "get", "/api/insights/trends")
    assert not body["gate"]["enough"] and body["analysis"] is None


def test_sleep_architecture_counts_and_says_when_its_read_fails(env, monkeypatch):
    body = env.ok(monkeypatch, "get", "/api/insights/sleep-architecture")
    assert body["counts"] == {"fused": 0, "oura_only": 0, "watch_only": 0}
    assert body["night"] is None and body["shadow"] is not None

    def broken():
        raise RuntimeError("the fusion table did not answer")
    monkeypatch.setattr(env.repo, "get_sleep_fusion_history", broken)
    failed = env.ok(monkeypatch, "get", "/api/insights/sleep-architecture")
    assert failed["load_error"].startswith("RuntimeError") and failed["counts"] is None


# ── the Sync tab ─────────────────────────────────────────────────────────────

def test_the_data_tables_answer_and_filter(env, monkeypatch):
    for table in ("engine_view", "blend_history", "metrics_history"):
        assert env.ok(monkeypatch, "get", f"/api/data/tables/{table}")["table"] == table
    r = env.call(monkeypatch, "get", "/api/data/tables/sheet1")
    assert r.status_code == 404 and r.json() == {"error": "unknown_table"}
    assert env.ok(monkeypatch, "get", "/api/data/session-checks") == {"warnings": []}


def test_the_data_check_reads_the_store_and_says_when_it_cannot(env, monkeypatch):
    """GET /api/data/check (rebuild Phase 4): the Repository hands its own store
    and the time to services/data_check.py; a failed read is 503 store_unavailable."""
    from services import data_check
    seen = []
    result = {"checked_at": "2026-10-20T06:00:00+00:00", "backup_name": "health-2026-10-19.db.gz",
              "backup_day": "2026-10-19", "backup_stale": False, "missing_rows": 1,
              "tables": [{"table": "config", "backup_rows": 2, "store_rows": 1, "missing": 1,
                          "examples": ["lost"]}]}
    monkeypatch.setattr(data_check, "run", lambda store, now: seen.append((store, now)) or result)
    out = env.ok(monkeypatch, "get", "/api/data/check")
    assert out["missing_rows"] == 1 and out["tables"][0]["examples"] == ["lost"]
    assert out["backup_day"] == "2026-10-19" and out["backup_stale"] is False
    store, now = seen[0]
    assert store is env.store and now.tzinfo is not None

    def failed(store, now):
        raise data_check.DataCheckFailed("download health-2026-10-19.db.gz: HTTP 500")

    monkeypatch.setattr(data_check, "run", failed)
    r = env.call(monkeypatch, "get", "/api/data/check")
    assert r.status_code == 503 and r.json() == {"error": "store_unavailable"}


def test_a_manual_sync_is_the_background_writers(env, monkeypatch):
    r = env.call(monkeypatch, "post", "/api/data/sync/sleep_fusion")
    assert r.status_code == 409 and r.json() == {"error": "not_the_writer"}
    env.write_as(bw.ENGINE)
    ran = []
    monkeypatch.setattr(env.repo, "sync_sleep_fusion",
                        lambda days=7, today=None: ran.append((days, today)) or {"fused": 3})
    out = env.ok(monkeypatch, "post", "/api/data/sync/sleep_fusion")
    assert out == {"kind": "sleep_fusion", "result": {"fused": 3}}
    assert ran == [(1200, TODAY)]
    r = env.call(monkeypatch, "post", "/api/data/sync/garmin_daily")
    assert r.status_code == 409 and r.json() == {"error": "garmin_not_configured"}
    assert env.call(monkeypatch, "post", "/api/data/sync/sheet1").status_code == 422


def test_a_manual_sync_waits_for_no_running_sync(env, monkeypatch):
    env.write_as(bw.ENGINE)
    monkeypatch.setattr(env.repo, "sync_sleep_fusion", lambda days=7, today=None: {})
    from services import engine_actions
    with env.runner.exclusive():
        with pytest.raises(Exception) as exc:
            engine_actions.manual_sync(env.repo, env.runner, "sleep_fusion", TODAY,
                                       wait_seconds=0.0)
    assert type(exc.value).__name__ == "SyncBusyError"


# ── the Oura login and Settings ──────────────────────────────────────────────

def _oauth(env):
    env.repo.config = dataclasses.replace(env.repo.config, oura_client_id="client-id",
                                          oura_client_secret="client-secret")


def test_the_oura_login_is_the_background_writers(env, monkeypatch):
    _oauth(env)
    body = {"redirect_uri": "https://health.example/oura/callback"}
    r = env.call(monkeypatch, "post", "/api/oura/login", body)
    assert r.status_code == 409 and r.json() == {"error": "not_the_writer"}


def test_the_oura_login_ties_the_answer_to_its_request(env, monkeypatch):
    env.write_as(bw.ENGINE)
    r = env.call(monkeypatch, "post", "/api/oura/login",
                 {"redirect_uri": "https://health.example/oura/callback"})
    assert r.status_code == 409 and r.json() == {"error": "oauth_not_configured"}
    _oauth(env)
    start = env.ok(monkeypatch, "post", "/api/oura/login",
                   {"redirect_uri": "https://health.example/oura/callback"})
    assert "client_id=client-id" in start["authorize_url"]
    state = json.loads(env.repo.get_config_value("oura_login_state"))["state"]
    wrong = env.call(monkeypatch, "post", "/api/oura/callback", {"code": "c", "state": "x"})
    assert wrong.status_code == 409 and wrong.json() == {"error": "state_mismatch"}
    exchanged = []
    monkeypatch.setattr(oura, "exchange_code", lambda cid, secret, code, redirect: (
        exchanged.append((code, redirect)) or {"access_token": "a-token", "refresh_token":
                                               "r-token", "expires_in": 86400,
                                               "scope": "daily"}))
    status = env.ok(monkeypatch, "post", "/api/oura/callback", {"code": "the-code",
                                                                 "state": state})
    assert exchanged == [("the-code", "https://health.example/oura/callback")]
    assert status["kind"] == "oauth" and not status["needs_authorisation"]
    assert "token" not in json.dumps(status).replace("needs_authorisation", "")
    reused = env.call(monkeypatch, "post", "/api/oura/callback", {"code": "c", "state": state})
    assert reused.status_code == 409, "a login is used once"


def test_the_oura_return_page_needs_no_phone_date(env, monkeypatch):
    """The Worker's return page (GET /oura/callback) has no phone date to send: the day
    the phone sent when the login started is used (rebuild rule 3)."""
    env.write_as(bw.ENGINE)
    _oauth(env)
    env.ok(monkeypatch, "post", "/api/oura/login",
           {"redirect_uri": "https://health.example/oura/callback"}, local=date(2026, 10, 18))
    stored = json.loads(env.repo.get_config_value("oura_login_state"))
    assert stored["date"] == "2026-10-18"
    monkeypatch.setattr(oura, "exchange_code", lambda *_a: {
        "access_token": "a", "refresh_token": "r", "expires_in": 86400, "scope": "daily"})
    days = []
    monkeypatch.setattr(env.repo, "save_oura_oauth_token",
                        lambda payload, today=None: days.append(today))
    monkeypatch.setenv("HEALTH_ENGINE_KEY", KEY)
    app = create_app(startup=False)
    app.dependency_overrides[get_repository] = lambda: env.repo
    app.dependency_overrides[get_sync_runner] = lambda: env.runner
    with TestClient(app) as c:
        r = c.post("/api/oura/callback", json={"code": "c", "state": stored["state"]},
                   headers={"X-Engine-Key": KEY})
    assert r.status_code == 200, r.text
    assert days == [date(2026, 10, 18)]


def test_settings_names_the_manual_syncs_by_the_names_the_engine_takes(env, monkeypatch):
    """The phone draws one button per sync from this list, so its names cannot drift from
    POST /api/data/sync/{kind} (they had: "oura" and "biometric_blend")."""
    from services import engine_actions
    assert env.ok(monkeypatch, "get", "/api/settings")["manual_syncs"] == list(engine_actions.MANUAL_SYNCS)


def test_the_plan_start_seeds_a_first_block_once(env, monkeypatch):
    settings = env.ok(monkeypatch, "get", "/api/settings")
    assert settings["writer"] == bw.STREAMLIT and settings["plan_running"]
    r = env.call(monkeypatch, "put", "/api/settings/plan-start", {"start_date": "2026-10-19"})
    assert r.status_code == 409 and r.json() == {"error": "plan_already_running"}
    env.repo.set_phases([])
    assert not env.ok(monkeypatch, "get", "/api/settings")["plan_running"], "a first run asks"
    seeded = env.ok(monkeypatch, "put", "/api/settings/plan-start", {"start_date": "2026-10-19"})
    assert seeded["seeded"] and seeded["plan_start_date"] == "2026-10-19"
    assert len(env.repo.get_phases_live()) == 1 and seeded["plan_running"]


def test_an_unreadable_plan_never_offers_the_first_run(env, monkeypatch):
    """A plan that cannot be read is not "no plan": Settings never offers to start one."""
    monkeypatch.setattr(env.repo, "get_phases", _broken)
    assert env.ok(monkeypatch, "get", "/api/settings")["plan_running"]


# ── read failures say so (I6, I17, I26) ─────────────────────────────────────

def _broken(*_a, **_k):
    raise RuntimeError("the store did not answer")


def test_a_failed_training_read_is_named_on_strength(env, monkeypatch):
    env.repo.set_config(ins.REFERENCE_KEY, ins.reference_json(REFERENCE))
    monkeypatch.setattr(env.repo, "get_all_training_exercises_raw", _broken)
    body = env.ok(monkeypatch, "get", "/api/insights/strength")
    assert body["load_error"].startswith("RuntimeError")


def test_metabolism_names_a_failed_read_and_shows_the_latest_scan(env, monkeypatch):
    from services.body_composition import InBodyScan
    env.repo.save_inbody_scans([InBodyScan(
        taken_at=datetime(2026, 9, 1, 8, 0), weight_kg=81.0, bmi=24.0,
        total_body_water_l=47.0, skeletal_muscle_kg=37.0, ecw_tbw=0.375,
        phase_angle_deg=6.4, device="InBody 770")])
    cell = env.ok(monkeypatch, "get", "/api/insights/metabolism")["cellular"]
    assert cell["device"] == "InBody 770" and cell["days_old"] == (TODAY - date(2026, 9, 1)).days
    assert cell["phase_angle_deg"] == 6.4
    monkeypatch.setattr(env.repo, "get_scale_readings", _broken)
    failed = env.ok(monkeypatch, "get", "/api/insights/metabolism")
    assert failed["load_error"].startswith("scale readings") and failed["latest"] is None


def test_an_unreadable_flexibility_record_is_not_an_empty_one(env, monkeypatch):
    monkeypatch.setattr(env.repo, "get_flexibility_assessments", _broken)
    body = env.ok(monkeypatch, "get", "/api/insights/flexibility")
    assert body["state"] == "unreadable" and body["load_error"].startswith("RuntimeError")


def test_a_leg_day_yesterday_warns_the_cold_reading(env, monkeypatch):
    _log(env, monkeypatch, TODAY - timedelta(days=1), "Hack Squat", 10, 100.0)
    assert env.ok(monkeypatch, "get", "/api/insights/flexibility")["legs_loaded_yesterday"]


# ── parse on save, the calendar and trends (I62-I72) ────────────────────────

def test_a_check_in_note_is_parsed_on_save_and_reaches_the_calendar(env, monkeypatch):
    from services import checkin_form as cf
    env.ok(monkeypatch, "put", "/api/checkin", {
        "date": TODAY.isoformat(), "opened_entry": False,
        "values": {**cf.FORM_DEFAULTS, "tightness_score": 4,
                   "subjective_tightness": "slight tightness lower back",
                   "anatomical_locations": ["Glute Medius — Right"]}})
    queue = env.ok(monkeypatch, "get", "/api/insights/queue")
    assert queue["pending_readiness"] == 0, "parsed on save (I63)"
    today = next(d for week in queue["weeks"] for d in week if d["date"] == TODAY.isoformat())
    assert today["level"] == "monitor" and today["entries"][0]["source"] == "readiness"
    trends = env.ok(monkeypatch, "get", "/api/insights/trends")
    # The areas he selected, never the keyword reading of the note (the note names the lower
    # back; he selected the right glute).
    assert [r["region"] for r in trends["regions"]] == ["Glute Medius — Right"]
    assert max(r["share"] for r in trends["regions"]) == 1.0
    dates = [t["date"] for t in trends["timeline"]]
    assert dates == sorted(dates), "the timeline reads oldest first"
    assert trends["levels"]["monitor"][0]["date"] == TODAY.isoformat()
    assert trends["timeline"][0]["self_reported"] == 4


def test_a_check_in_whose_note_was_never_read_is_on_the_timeline(env, monkeypatch):
    """The timeline draws every check-in of the last 90 days (the owner, 2026-10-20): one
    whose note no parse has read keeps its tightness and pain, without a severity. (A save
    through the API parses every waiting note, so the unread one is stored after it.)"""
    from services import checkin_form as cf
    from services.models import CheckInRecord
    env.ok(monkeypatch, "put", "/api/checkin", {
        "date": TODAY.isoformat(), "opened_entry": False,
        "values": {**cf.FORM_DEFAULTS, "tightness_score": 4,
                   "subjective_tightness": "slight tightness lower back"}})
    earlier = TODAY - timedelta(days=3)
    env.repo.save_check_in(CheckInRecord(date=earlier.isoformat(), current_condition=None,
                                         tightness_score=6, pain_score=2,
                                         subjective_tightness="stiff all day"))
    trends = env.ok(monkeypatch, "get", "/api/insights/trends")
    assert [(t["date"], t["self_reported"], t["pain"]) for t in trends["timeline"]] == [
        (earlier.isoformat(), 6, 2), (TODAY.isoformat(), 4, cf.FORM_DEFAULTS["pain_score"])]
    assert trends["timeline"][0]["parsed_severity"] is None, "its note was never read"
    assert trends["timeline"][1]["parsed_severity"] is not None, "read on save (I63)"
    assert trends["timeline_axis"]["start"] == earlier.isoformat()
    # The levels stay the parse's own classification: only the note read on save is there.
    assert [e["date"] for level in trends["levels"].values() for e in level] == [TODAY.isoformat()]


def test_the_trend_analysis_runs_once_the_gate_opens(env, monkeypatch):
    days = [TODAY - timedelta(days=30 - i) for i in range(30)]
    data = {
        "biometrics": [{"date": d.isoformat(), "hrv_ms": 40.0 + i % 7,
                        "resting_heart_rate": 55.0 + i % 3,
                        "sleep_duration_hours": 7.0 + (i % 4) * 0.25,
                        "sleep_deep_hours": 1.2, "active_energy_kcal": 500.0,
                        "weight_kg": 81.0, "steps": 8000} for i, d in enumerate(days)],
        "readiness": [{"date": d.isoformat(), "avg_tightness": 2.0 + i % 3, "max_pain": i % 2,
                       "avg_stress": 2.0 + (i % 3) * 0.5, "travel": 0, "avg_alcohol": 0.0}
                      for i, d in enumerate(days)],
        "sessions": [{"date": d.isoformat(), "total_au": 300.0 + 10 * (i % 5)}
                     for i, d in enumerate(days) if i % 2 == 0],
    }
    monkeypatch.setattr(env.repo, "get_macro_trend_data", lambda days=90, today=None: data)
    body = env.ok(monkeypatch, "get", "/api/insights/trends")
    assert body["gate"]["enough"]
    analysis = body["analysis"]
    assert analysis["recovery_label"] and analysis["interpretation"]["headline"]


# ── sleep architecture's nights, the data tables, the session checks ─────────

def test_a_fused_night_shows_its_three_strips(env, monkeypatch):
    rows = [{"date": "2026-10-17", "source": "fused", "phantom_wake_minutes": 10,
             "master_sleep_hours": 7.0, "oura_sleep_hours": 6.8,
             "oura_hypnogram": "4222331", "master_hypnogram": "2222331",
             "garmin_hypnogram": "2222231", "agreement_pct": 71, "cohen_kappa": 0.4,
             "window_overlap_pct": 96, "garmin_covered_minutes": 400, "minutes": 420},
            {"date": "2026-10-18", "source": "garmin_only", "master_hypnogram": "2223"}]
    monkeypatch.setattr(env.repo, "get_sleep_fusion_history", lambda *a, **k: rows)
    body = env.ok(monkeypatch, "get", "/api/insights/sleep-architecture")
    assert body["counts"] == {"fused": 1, "oura_only": 0, "watch_only": 1}
    assert [s["codes"] for s in body["night"]["strips"]] == ["4222331", "2222331", "2222231"]
    first = body["night"]["strips"][0]
    assert first["runs"][0]["code"] == "4" and first["bands"], "drawn as the Sleep screen's strip"
    assert body["night"]["phantom_wake_minutes"] == 10 and body["nights"] == ["2026-10-17"]


def test_a_history_table_filters_by_its_dates(env, monkeypatch):
    rows = [{"date": f"2026-10-{d:02d}", "hrv_ms": 40.0} for d in range(1, 11)]
    monkeypatch.setattr(env.repo, "get_biometric_blend_history", lambda *a, **k: rows)
    body = env.ok(monkeypatch, "get",
                  "/api/data/tables/blend_history?start=2026-10-03&end=2026-10-05")
    assert [r["date"] for r in body["rows"]] == ["2026-10-03", "2026-10-04", "2026-10-05"]
    assert (body["earliest"], body["latest"]) == ("2026-10-01", "2026-10-10")


def test_the_session_checks_name_a_repeat_save(env, monkeypatch):
    """A day with two plan sessions. The save refuses a second one since WP-32
    (2026-10-26), so the second is written past it, as one stored before then."""
    from services import session_save
    from services import training_session as tsession
    day = TODAY - timedelta(days=2)
    _log(env, monkeypatch, day, "Hack Squat", 10, 100.0)
    body = {"session_id": f"{day}-00000002", "date": day.isoformat(), "kind": "plan",
            "duration_minutes": 45, "session_rpe": 6, "exercises": [{
                "exercise_id": f"ex-{day}-second", "exercise": {
                    "name": "Machine Chest Press", "type": "reps", "sets": 3, "reps": 10,
                    "equipment_type": "machine"},
                "sets": [{"set_num": i, "reps": 10, "weight": 50.0,
                          "ts": f"{day}T09:1{i}:00"} for i in (1, 2, 3)]}]}
    r = env.call(monkeypatch, "post", "/api/training/sessions", body, local=day)
    assert r.status_code == 409 and r.json() == {"error": "already_logged"}
    session_save.save_session(env.repo, tsession.build_save(body))
    warnings = env.ok(monkeypatch, "get", "/api/data/session-checks")["warnings"]
    assert warnings and day.isoformat() in " ".join(warnings)


# ── the manual syncs, configured (I84, I89, I90, I93) ────────────────────────

@pytest.mark.parametrize("kind,method,device", [
    ("garmin_daily", "sync_garmin_daily", "garmin"),
    ("garmin_activities", "sync_garmin_activities", "garmin"),
    ("oura_weekly", "sync_oura_all", "oura"),
    ("blend_backfill", "sync_biometric_blend", None),
])
def test_each_manual_sync_runs_its_wider_window(env, monkeypatch, kind, method, device):
    env.write_as(bw.ENGINE)
    if device:
        monkeypatch.setattr(env.repo, f"{device}_configured", lambda: True)
    monkeypatch.setattr(env.repo, method, lambda *a, **k: 5)
    assert env.ok(monkeypatch, "post", f"/api/data/sync/{kind}") == {
        "kind": kind, "result": {"count": 5}}


# ── the SECA scan (WP-37) ────────────────────────────────────────────────────

def test_a_seca_export_is_stored_once_and_shown_in_its_own_lane(env, monkeypatch):
    from tests.test_seca_scans import EXPORT
    first = env.ok(monkeypatch, "post", "/api/insights/metabolism/seca", {"csv": EXPORT})
    again = env.ok(monkeypatch, "post", "/api/insights/metabolism/seca", {"csv": EXPORT})
    assert first["seca"]["count"] == again["seca"]["count"] == 1
    assert first["headline"] == {"date": "2026-03-03", "weight_kg": 80.0, "source": "seca"}
    shown = env.ok(monkeypatch, "get", "/api/insights/metabolism")
    assert shown["seca"]["date"] == "2026-03-03" and shown["seca"]["sides"][0]["label"] == "Arms"
    r = env.call(monkeypatch, "post", "/api/insights/metabolism/seca", {"csv": "not,a,scan"})
    assert r.status_code == 422
