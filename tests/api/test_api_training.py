"""The Training screen through the engine API (rebuild Phase 2, milestone 5):
the week, one day, today's session, the schedule answers, completion, the
Garmin taps, the heart-rate match and the "+" menu.

Through the real Repository over a fake Supabase (tests/_record_store.py),
seeded with the 12-week block (phase 5, starting Monday 2026-10-19). What it
pins, each against the services the Streamlit page draws from:

- the week: the banner, the strip (a planned rest day reads "rest", F24),
  gate 1, and the prompts, which ASK before anything moves (2026-08-07);
- one day: rest, future (with the swap onto today), today's overview with
  the day's dosed values (F20), and the "already logged" lock (T80);
- the actions store through scheduling.apply_schedule_change, rebuilt from
  the live phases, and a refused one stores nothing;
- today's session: every exercise with its timer and seeded numbers, and
  the guided flow walked in advance;
- every day is the caller's (rule 3).

No network.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import goal_block as gb  # noqa: E402
from healthapi.deps import get_repository, get_sync_runner  # noqa: E402
from healthapi.main import create_app  # noqa: E402
from services import gate1 as g1  # noqa: E402
from services import guided_flow, record_cache, scheduling, supabase_store  # noqa: E402
from services import sessions as sess  # noqa: E402
from services import training_session as tsession  # noqa: E402
from services import yoga as yg  # noqa: E402
from services.background_sync import BackgroundSyncRunner  # noqa: E402
from tests._record_store import FakeStore, new_local_copy, record_config, record_repo  # noqa: E402

KEY = "test-engine-key"
MONDAY = gb.START                       # 2026-10-19, day 1 (session A)
TUESDAY = MONDAY + timedelta(days=1)    # day 2 (session B)
WEDNESDAY = MONDAY + timedelta(days=2)  # day 3, a planned rest day


@pytest.fixture(autouse=True)
def _empty_outbox():
    supabase_store.OUTBOX.drain()
    yield
    supabase_store.OUTBOX.drain()


class Env:
    def __init__(self, path: str):
        self.path, self.store = path, FakeStore()
        self.repo = record_repo(path, self.store)
        self.repo.set_phases([sess.build_phase(5, MONDAY)])
        self.repo.set_config("current_stage", "2")
        self.runner = BackgroundSyncRunner(record_config(path))

    def client(self, monkeypatch):
        monkeypatch.setenv("HEALTH_ENGINE_KEY", KEY)
        monkeypatch.delenv("HEALTH_PROBES", raising=False)
        app = create_app(startup=False)
        app.dependency_overrides[get_repository] = lambda: self.repo
        app.dependency_overrides[get_sync_runner] = lambda: self.runner
        return TestClient(app)

    def call(self, monkeypatch, method, path, *, local=MONDAY, body=None):
        headers = {"X-Engine-Key": KEY, "X-Local-Date": local.isoformat()}
        with self.client(monkeypatch) as c:
            if method == "get":
                return c.get(path, headers=headers)
            return getattr(c, method)(path, json=body, headers=headers)

    def ok(self, monkeypatch, method, path, **kw):
        r = self.call(monkeypatch, method, path, **kw)
        assert r.status_code == 200, r.text
        return r.json()

    def phase(self):
        return self.repo.get_phases_live()[0]


@pytest.fixture
def env(tmp_path):
    path = new_local_copy(tmp_path)
    yield Env(path)
    record_cache.forget(path)


def _log_plan_session(env, monkeypatch, day: date):
    """A logged plan session on `day`, saved the way the phone saves one."""
    body = {"session_id": f"{day}-0000abcd", "date": day.isoformat(), "kind": "plan",
            "duration_minutes": 50, "session_rpe": 6, "exercises": [{
                "exercise_id": f"ex-{day}", "exercise": {"name": "Hack Squat", "type": "reps",
                                                          "sets": 3, "reps": 10,
                                                          "equipment_type": "machine"},
                "sets": [{"set_num": i, "reps": 10, "weight": 80, "ts": f"{day}T08:1{i}:00"}
                         for i in (1, 2, 3)]}]}
    env.ok(monkeypatch, "post", "/api/training/sessions", local=day, body=body)


# ── the week ─────────────────────────────────────────────────────────────────

def test_the_week_shows_the_block_its_strip_and_gate_one(env, monkeypatch):
    week = env.ok(monkeypatch, "get", "/api/training/week")
    assert week["phases_readable"] and week["phase"]["number"] == 5
    assert week["phase"]["day_num"] == 1 and week["week_start"] == MONDAY.isoformat()
    markers = [d["marker"] for d in week["strip"]]
    assert markers[0] == "today"
    assert markers[2] == "rest" and markers[5] == "rest", "planned rest days read rest (F24)"
    assert week["banner"]["scheduled"] >= 4 and week["banner"]["completed"] == 0
    assert week["gate1"] is not None and week["gate1"]["waiting"] is None
    assert [r["key"] for r in week["gate1"]["reasons"]] == list(g1.REASONS)
    assert week["carry_prompt"] is None and week["shift_prompt"] is None
    assert week["is_current_week"]


def test_the_week_pages_within_the_block_only(env, monkeypatch):
    before = env.ok(monkeypatch, "get", f"/api/training/week?week_start={MONDAY - timedelta(days=14)}")
    assert before["week_start"] == MONDAY.isoformat() and not before["can_go_back"]
    later = env.ok(monkeypatch, "get", f"/api/training/week?week_start={MONDAY + timedelta(days=7)}")
    assert later["week_start"] == (MONDAY + timedelta(days=7)).isoformat()
    assert not later["is_current_week"]


def test_unreadable_phases_say_so_and_offer_nothing(env, monkeypatch):
    def broken():
        raise ValueError("the stored phases are not JSON")
    monkeypatch.setattr(env.repo, "get_phases", broken)
    assert env.ok(monkeypatch, "get", "/api/training/week") == {
        **env.ok(monkeypatch, "get", "/api/training/week"), "phases_readable": False}
    day = env.ok(monkeypatch, "get", "/api/training/day")
    assert day["route"] == "phases_unreadable"
    r = env.call(monkeypatch, "get", "/api/training/session")
    assert r.status_code == 409 and r.json()["error"].startswith("phases_unreadable")


# ── one day ──────────────────────────────────────────────────────────────────

def test_today_opens_the_overview_with_todays_dosed_values(env, monkeypatch):
    day = env.ok(monkeypatch, "get", "/api/training/day")
    assert day["route"] == "today"
    ov = day["overview"]
    assert ov["screen"] == "overview" and ov["day_num"] == 1
    assert ov["card"]["minutes"] > 0 and ov["card"]["exercise_count"] == len(
        ov["release"]) + len(ov["main"])
    assert ov["first_side"] == sess.first_side(MONDAY)
    assert ov["headline"] and ov["objective"]
    content = sess.calendar_plan(sess.build_phase(5, MONDAY))[1]
    dosed = sess.dosed_day(content["exercises"], ov["adaptation"]["volume_factor"],
                           content.get("day_type"))
    assert [x["prescription"] for x in ov["release"] + ov["main"]] == [
        sess.prescription_label(ex) for part in sess.split_release_and_main(dosed)
        for ex in part], "today's dosed values (F20)"
    assert len(ov["home"]) == len(content.get("home") or [])
    assert ov["banner"]["kind"] in ("", "info", "warning", "error", "neutral")
    assert ov["adaptation"]["volume_factor"] > 0
    assert all("biomechanical_focus" not in line for line in ov["main"]), "Key Rule 20"


def test_a_planned_rest_day_opens_the_rest_view(env, monkeypatch):
    day = env.ok(monkeypatch, "get", f"/api/training/day?date={WEDNESDAY}")
    assert day["route"] == "rest" and not day["rest"]["is_today"]
    today = env.ok(monkeypatch, "get", "/api/training/day", local=WEDNESDAY)
    assert today["route"] == "rest" and today["rest"]["is_today"], "never an empty Start"


def test_a_future_day_previews_and_offers_the_swap_onto_today(env, monkeypatch):
    day = env.ok(monkeypatch, "get", f"/api/training/day?date={TUESDAY}")
    assert day["route"] == "future"
    assert day["planned"]["day_num"] == 2 and day["planned"]["exercises"]
    assert day["swap"]["available"] and day["swap"]["today_objective"]


def test_a_logged_day_locks_the_session_and_shows_what_was_logged(env, monkeypatch):
    _log_plan_session(env, monkeypatch, MONDAY)
    today = env.ok(monkeypatch, "get", "/api/training/day")
    assert today["overview"]["screen"] == "logged"
    # WP-32: today shows what was done, as a past day does.
    assert today["logged"]["au"] == 300 and today["logged"]["exercises"][0]["name"] == "Hack Squat"
    r = env.call(monkeypatch, "get", "/api/training/session")
    assert r.status_code == 409 and r.json() == {"error": "already_logged"}
    past = env.ok(monkeypatch, "get", f"/api/training/day?date={MONDAY}", local=TUESDAY)
    assert past["route"] == "past_completed"
    assert past["logged"]["au"] == 300 and past["logged"]["exercises"][0]["name"] == "Hack Squat"


# ── the schedule answers ─────────────────────────────────────────────────────

def test_a_swap_moves_tuesdays_session_onto_today(env, monkeypatch):
    stored = env.ok(monkeypatch, "post", "/api/training/swap", body={"date": TUESDAY.isoformat()})
    assert stored == {"stored": True}
    overrides = env.phase().date_overrides
    assert overrides == scheduling.manual_swap_entries(
        sess.build_phase(5, MONDAY), TUESDAY, MONDAY)[0]


def test_no_swap_once_today_has_trained(env, monkeypatch):
    _log_plan_session(env, monkeypatch, MONDAY)
    r = env.call(monkeypatch, "post", "/api/training/swap", body={"date": TUESDAY.isoformat()})
    assert r.status_code == 409 and r.json()["error"].startswith("swap_blocked")
    assert env.phase().date_overrides == {}


def test_a_missed_session_asks_before_the_rest_move_along(env, monkeypatch):
    week = env.ok(monkeypatch, "get", "/api/training/week", local=TUESDAY)
    prompt = week["carry_prompt"]
    assert prompt is not None and prompt["in_order"] and prompt["lines"]
    assert env.phase().date_overrides == {}, "a read never moves a session"
    assert env.ok(monkeypatch, "post", "/api/training/carry", local=TUESDAY,
                  body={"accept": True}) == {"stored": True}
    assert env.phase().date_overrides, "the answer stored the move"
    moved = env.ok(monkeypatch, "get", "/api/training/day", local=TUESDAY)
    assert moved["note"] is not None and moved["note"]["text"]
    assert env.ok(monkeypatch, "get", "/api/training/week", local=TUESDAY)["carry_prompt"] is None


def test_keeping_as_planned_records_it_and_stops_asking(env, monkeypatch):
    env.ok(monkeypatch, "post", "/api/training/carry", local=TUESDAY, body={"accept": False})
    assert env.ok(monkeypatch, "get", "/api/training/week", local=TUESDAY)["carry_prompt"] is None
    r = env.call(monkeypatch, "post", "/api/training/carry", local=TUESDAY,
                 body={"accept": True})
    assert r.status_code == 409 and r.json() == {"error": "nothing_to_carry"}


def test_the_readiness_shift_asks_then_stores_the_answer(env, monkeypatch):
    monkeypatch.setattr(scheduling, "should_shift_session",
                        lambda bio, checkin, today: (True, "short sleep last night"))
    week = env.ok(monkeypatch, "get", "/api/training/week")
    assert week["shift_prompt"] == {"reason": "short sleep last night"}
    assert env.ok(monkeypatch, "post", "/api/training/shift",
                  body={"accept": False}) == {"stored": True}
    assert MONDAY.isoformat() in env.phase().shift_reasons
    assert env.ok(monkeypatch, "get", "/api/training/week")["shift_prompt"] is None


def test_a_failed_week_is_offered_again_on_its_monday(env, monkeypatch):
    next_monday = MONDAY + timedelta(days=7)
    week = env.ok(monkeypatch, "get", "/api/training/week", local=next_monday)
    assert week["redo"]["offered"] and week["redo"]["consequences"]
    assert week["gate1"]["waiting"]["monday"] == MONDAY.isoformat()
    assert env.ok(monkeypatch, "post", "/api/training/redo",
                  local=next_monday) == {"stored": True}
    assert env.phase().length_days == 84 + 7


def test_the_redo_is_offered_on_that_monday_and_on_no_other_day(env, monkeypatch):
    """Key Rule 22 through the API (rebuild Phase 7): the week after a failed week offers
    the redo on its Monday only; the phone shows it only when the engine offers it."""
    next_monday = MONDAY + timedelta(days=7)
    assert env.ok(monkeypatch, "get", "/api/training/week", local=next_monday)["redo"]["offered"]
    for day in (next_monday + timedelta(days=1), next_monday + timedelta(days=3)):
        week = env.ok(monkeypatch, "get", "/api/training/week", local=day)
        assert week["redo"] == {"offered": False, "consequences": []}, day


def test_the_redo_is_not_offered_after_a_week_with_three_logged_days(env, monkeypatch):
    for day in (MONDAY, TUESDAY, MONDAY + timedelta(days=3)):
        _log_plan_session(env, monkeypatch, day)
    week = env.ok(monkeypatch, "get", "/api/training/week", local=MONDAY + timedelta(days=7))
    assert week["redo"] == {"offered": False, "consequences": []}


def test_gate_one_takes_its_reason_and_a_flare_up(env, monkeypatch):
    next_monday = MONDAY + timedelta(days=7)
    env.ok(monkeypatch, "post", "/api/training/gate1/reason", local=next_monday,
           body={"monday": MONDAY.isoformat(), "reason": g1.REASON_PAUSE})
    card = env.ok(monkeypatch, "get", "/api/training/week", local=next_monday)["gate1"]
    assert card["waiting"] is None
    env.ok(monkeypatch, "post", "/api/training/gate1/flare", local=next_monday)
    assert env.ok(monkeypatch, "get", "/api/training/week",
                  local=next_monday)["gate1"]["flare_this_week"]
    r = env.call(monkeypatch, "post", "/api/training/gate1/reason", local=next_monday,
                 body={"monday": MONDAY.isoformat(), "reason": "bored"})
    assert r.status_code == 422 and r.json()["error"].startswith("unknown_reason")


# ── today's session ──────────────────────────────────────────────────────────

def test_todays_session_carries_every_exercise_and_the_walk(env, monkeypatch):
    plan = env.ok(monkeypatch, "get", "/api/training/session")
    assert plan["kind"] == "plan" and plan["day_num"] == 1
    assert plan["plan_days"] == len(sess.calendar_plan(sess.build_phase(5, MONDAY)))
    content = sess.calendar_plan(sess.build_phase(5, MONDAY))[1]
    assert [e["name"] for e in plan["exercises"]] == [e["name"] for e in content["exercises"]]
    for e in plan["exercises"]:
        assert e["timer"] == tsession.timer_kind(e) and e["prescription"]
    dosed = sess.dosed_day(content["exercises"], plan["adaptation"]["volume_factor"],
                           content.get("day_type"))
    assert plan["steps"] == json.loads(json.dumps(guided_flow.walk(dosed, plan["first_side"])))
    assert plan["model_minutes"] == sess.estimate_duration(dosed)
    # The length question's threshold rides with the plan (the phone asks it offline),
    # and it is the completion rule's own: just past it, the engine asks too.
    above = plan["ask_length_above_minutes"]
    assert above == sess.DURATION_CHECK_RATIO * plan["model_minutes"]
    assert sess.duration_needs_a_check(int(above) + 1, plan["model_minutes"])
    assert not sess.duration_needs_a_check(int(above), plan["model_minutes"])
    assert plan["next_day"]["day_num"] == 2
    tests = [e for e in plan["exercises"] if e["timed_test"]]
    assert tests and all(e["timer"] == "stopwatch" for e in tests), "the plank test counts up"
    assert all(e["estimated_minutes"] >= 1 for e in plan["exercises"])
    assert [b["tier"] for b in plan["band_tiers"]] == list(sess.BAND_TIERS)


def test_the_hack_squats_day_carries_the_v_squat_in_its_place(env, monkeypatch):
    """WP-28: the swap rides with the session, dosed, seeded and walked by the
    engine, numbered from 0, with the hack squat group's move; the session's
    own list stays the plan's (the phone adds the swap only when it is taken)."""
    plan = env.ok(monkeypatch, "get", "/api/training/session", local=TUESDAY)
    hack = next(e for e in plan["exercises"] if e["name"] == "Hack Squat")
    [alt] = plan["alternatives"]
    assert alt["name"] == "V Squat" and alt["for_group"] == hack["move"]["group"]
    assert [e["name"] for e in alt["exercises"]] == ["V Squat (Ramp Set)", "V Squat"]
    assert [e["index"] for e in alt["exercises"]] == [0, 1] and alt["exercises"][0]["ramp_for"] == 1
    assert all(e["move"] == hack["move"] for e in alt["exercises"])
    dosed = sess.dosed_day(gb.ALTERNATIVES["Hack Squat"], plan["adaptation"]["volume_factor"], "main")
    assert alt["steps"] == json.loads(json.dumps(guided_flow.walk(dosed, plan["first_side"])))
    assert "V Squat" not in [e["name"] for e in plan["exercises"]]
    assert env.ok(monkeypatch, "get", "/api/training/session")["alternatives"] == [], "no hack squat on Monday"

def test_thursdays_farmer_walk_may_run_before_the_adductor_machine(env, monkeypatch):
    """2026-11-07, his note from the adductor machine: "there was no option to go to
    farmer walk". Session C sends the farmer walk with a group that moves, after the
    adductor machine in the plan's own order; the hip airplane after it does not move."""
    plan = env.ok(monkeypatch, "get", "/api/training/session", local=MONDAY + timedelta(days=3))
    names = [e["name"] for e in plan["exercises"]]
    farmer = plan["exercises"][names.index("Farmer Walk (DB)")]
    adductor = plan["exercises"][names.index("Adductor Machine (Seated)")]
    assert adductor["index"] < farmer["index"]
    assert farmer["move"]["movable"] and adductor["move"]["movable"] and farmer["move"]["after"] == []
    assert not plan["exercises"][names.index("Hip Airplane (Weighted)")]["move"]["movable"]


def test_a_rest_day_has_no_session(env, monkeypatch):
    r = env.call(monkeypatch, "get", "/api/training/session", local=WEDNESDAY)
    assert r.status_code == 409 and r.json() == {"error": "rest_day"}


def test_the_accessory_session_runs_through_the_same_flow(env, monkeypatch):
    plan = env.ok(monkeypatch, "get", "/api/training/accessory")
    assert plan["kind"] == "accessory" and plan["exercises"] and plan["steps"]
    assert plan["min_minutes"] == sess.MIN_ACCESSORY_MINUTES and plan["reasons"]
    # Every kind asks the length past its own model (2026-11-09).
    assert plan["ask_length_above_minutes"] == sess.DURATION_CHECK_RATIO * plan["model_minutes"]
    assert plan["plan_days"] is None


def test_the_daily_session_runs_through_the_same_flow(env, monkeypatch):
    """WP-40: the same session every day, each 30-second hold with its slow
    start, about 11 minutes, and on a gym day before the gym session the line
    "keep 8 hours before"."""
    import daily_tendon as dt
    plan = env.ok(monkeypatch, "get", "/api/training/daily")
    assert plan["kind"] == "daily" and plan["steps"] and plan["plan_days"] is None
    assert [e["name"] for e in plan["exercises"]] == [e["name"] for e in dt.entries()]
    holds = [e for e in plan["exercises"] if e["type"] == "hold"]
    assert holds and all(e["hold_seconds"] == dt.HOLD_SECONDS
                         and e["lead_in_seconds"] == dt.LEAD_IN_SECONDS for e in holds)
    assert all(e["lead_in_seconds"] is None for e in plan["exercises"] if e["type"] == "hold_reps")
    assert plan["min_minutes"] == sess.MIN_ACCESSORY_MINUTES
    assert 9 <= plan["model_minutes"] <= 12
    # The session of 2026-11-03 was saved at 850 minutes because the daily
    # session never asked the length (the owner, 2026-11-09: it asks now).
    assert plan["ask_length_above_minutes"] == sess.DURATION_CHECK_RATIO * plan["model_minutes"]
    assert sess.duration_needs_a_check(850, plan["model_minutes"])
    assert plan["reminder"] == {"kind": "before", "time": None}, "Monday's gym session is to come"
    assert plan["done_today"] is False and plan["note"] == dt.NOTE


def test_the_daily_sessions_reminder_is_eight_hours_after_todays_gym_session(env, monkeypatch):
    _log_plan_session(env, monkeypatch, MONDAY)          # last set 08:13
    plan = env.ok(monkeypatch, "get", "/api/training/daily")
    assert plan["reminder"] == {"kind": "after", "time": "16:13"}


def test_a_rest_day_offers_the_daily_session_with_no_reminder(env, monkeypatch):
    plan = env.ok(monkeypatch, "get", "/api/training/daily", local=WEDNESDAY)
    assert plan["kind"] == "daily" and plan["exercises"] and plan["reminder"] is None


def test_a_saved_daily_session_is_done_today_counts_in_strain_and_is_never_a_logged_day(
        env, monkeypatch):
    """WP-40, the athlete's decision of 2026-10-28: a daily session counts in
    strain and never makes a logged day — the failed-week rule counts logged
    days, and a session every day would pass every week."""
    import daily_tendon as dt
    hang = dt.entries()[0]
    body = {"session_id": f"{WEDNESDAY}-dai10001", "date": WEDNESDAY.isoformat(), "kind": "daily",
            "duration_minutes": 11, "session_rpe": 4, "exercises": [{
                "exercise_id": "ex-daily-1", "exercise": hang,
                "sets": [{"set_num": 1, "reps": 1, "weight": 0, "tut": 30,
                          "ts": f"{WEDNESDAY}T19:00:00"}]}]}
    env.ok(monkeypatch, "post", "/api/training/sessions", local=WEDNESDAY, body=body)
    assert env.ok(monkeypatch, "get", "/api/training/daily", local=WEDNESDAY)["done_today"]
    assert not env.repo.has_logged_session(WEDNESDAY)
    week = (MONDAY, MONDAY + timedelta(days=6))
    assert WEDNESDAY.isoformat() not in env.repo.get_logged_session_dates(*week)
    assert WEDNESDAY.isoformat() not in env.repo.get_logged_session_dates_live(*week)
    thursday = MONDAY + timedelta(days=3)
    strip = env.ok(monkeypatch, "get", "/api/training/week", local=thursday)["strip"]
    assert strip[2]["marker"] == "rest", "a day with only a daily session is not 'done'"
    rows = env.repo.get_daily_region_au(days=7, today=WEDNESDAY)["rows"]
    assert any(r["date"] == WEDNESDAY.isoformat() and r["total_au"] > 0 for r in rows)


def test_a_strength_day_before_a_rest_day_offers_the_evening_mobility_session(env, monkeypatch):
    """The athlete, 2026-11-11: "strength training in the morning and mobilty in
    the evening ... on the days I have no strength training the next day ...
    The mobility training will replace the tendon training on those days."
    Tuesday (B) is before Wednesday's rest: the second tile's address answers
    with the Sunday stack, no 8-hour line and the plan's own time model."""
    from services import mobility_session as mob
    plan = env.ok(monkeypatch, "get", "/api/training/daily", local=TUESDAY)
    assert plan["kind"] == "mobility" and plan["plan_days"] is None
    assert [e["name"] for e in plan["exercises"]] == [e["name"] for e in gb.FLEX_STACK]
    assert plan["reminder"] is None and plan["done_today"] is False and plan["note"] == mob.NOTE
    assert plan["steps"] and 20 <= plan["model_minutes"] <= 30
    assert plan["ask_length_above_minutes"] == sess.DURATION_CHECK_RATIO * plan["model_minutes"]
    # Monday (A) is before Tuesday's strength: the daily tendon session.
    assert env.ok(monkeypatch, "get", "/api/training/daily")["kind"] == "daily"


def test_an_evening_done_before_a_move_is_not_offered_again(env, monkeypatch):
    """The athlete, 2026-11-11: "when I move the Friday training to Thursday
    the evening mobility if not performed goes to Thursday". In week 1: the
    evening session done on Tuesday, then Thursday's C moved to Wednesday.
    Tuesday's tile still shows it done; Wednesday, now before Thursday's rest,
    has none, because the week's other evening is Friday's."""
    thursday, friday = MONDAY + timedelta(days=3), MONDAY + timedelta(days=4)
    plan = env.ok(monkeypatch, "get", "/api/training/daily", local=TUESDAY)
    first = plan["exercises"][0]
    env.ok(monkeypatch, "post", "/api/training/sessions", local=TUESDAY, body={
        "session_id": f"{TUESDAY}-mob00002", "date": TUESDAY.isoformat(), "kind": "mobility",
        "duration_minutes": 26, "session_rpe": 4, "exercises": [{
            "exercise_id": "ex-mob-2", "exercise": first,
            "sets": [{"set_num": 1, "reps": 1, "weight": 0, "tut": 90,
                      "ts": f"{TUESDAY}T19:00:00"}]}]})
    assert env.ok(monkeypatch, "post", "/api/training/swap", local=TUESDAY,
                  body={"date": thursday.isoformat(), "to": WEDNESDAY.isoformat()}) == {"stored": True}
    tuesday = env.ok(monkeypatch, "get", "/api/training/daily", local=TUESDAY)
    assert tuesday["kind"] == "mobility" and tuesday["done_today"]
    assert env.ok(monkeypatch, "get", "/api/training/daily", local=WEDNESDAY)["kind"] == "daily"
    assert env.ok(monkeypatch, "get", "/api/training/daily", local=friday)["kind"] == "mobility"


def test_a_session_moved_to_a_later_day_takes_the_evening_mobility_with_it(env, monkeypatch):
    """The athlete, 2026-11-11: "if I move Friday training of this week C to
    tomorrow, the Friday becomes the rest day and mobility goes to tomorrow
    evening instead of tonight, and D training stays on Saturday morning ...
    It needs to be able to handle it." The same move in week 1: on Tuesday
    (B, before Wednesday's rest), Thursday's C moves to Wednesday."""
    from services import plan as ph
    thursday, friday = MONDAY + timedelta(days=3), MONDAY + timedelta(days=4)
    assert env.ok(monkeypatch, "get", "/api/training/daily", local=TUESDAY)["kind"] == "mobility"
    day = env.ok(monkeypatch, "get", f"/api/training/day?date={thursday}", local=TUESDAY)
    moves = {m["date"]: m for m in day["moves"]}
    assert list(moves) == [(MONDAY + timedelta(days=i)).isoformat() for i in (2, 4, 5, 6)]
    assert moves[WEDNESDAY.isoformat()]["available"]
    assert moves[WEDNESDAY.isoformat()]["holds"] == "rest day"
    assert moves[friday.isoformat()]["holds"] == "session D"
    assert env.ok(monkeypatch, "post", "/api/training/swap", local=TUESDAY,
                  body={"date": thursday.isoformat(), "to": WEDNESDAY.isoformat()}) == {"stored": True}
    stored = env.phase()
    assert [ph.day_number_in_phase(stored, MONDAY + timedelta(days=i)) for i in range(7)] == [
        1, 2, 4, 3, 5, 6, 7]
    assert env.ok(monkeypatch, "get", "/api/training/daily", local=TUESDAY)["kind"] == "daily"
    assert env.ok(monkeypatch, "get", "/api/training/daily", local=WEDNESDAY)["kind"] == "mobility"
    assert env.ok(monkeypatch, "get", "/api/training/daily", local=thursday)["kind"] == "daily"
    assert env.ok(monkeypatch, "get", "/api/training/daily", local=friday)["kind"] == "mobility"


def test_a_move_to_a_past_day_or_into_the_next_week_stores_nothing(env, monkeypatch):
    thursday = MONDAY + timedelta(days=3)
    r = env.call(monkeypatch, "post", "/api/training/swap", local=WEDNESDAY,
                 body={"date": thursday.isoformat(), "to": TUESDAY.isoformat()})
    assert r.status_code == 409 and r.json()["error"].startswith("swap_blocked")
    r = env.call(monkeypatch, "post", "/api/training/swap", local=TUESDAY,
                 body={"date": thursday.isoformat(),
                       "to": (MONDAY + timedelta(days=8)).isoformat()})
    assert r.status_code == 409
    assert env.phase().date_overrides == {}


def test_a_saved_evening_session_is_done_counts_in_strain_and_leaves_the_strength_day_open(
        env, monkeypatch):
    """Its own Type, an extra: the morning's strength session is still offered,
    the evening alone never makes a logged day, and it counts in strain."""
    from services import mobility_session as mob
    plan = env.ok(monkeypatch, "get", "/api/training/daily", local=TUESDAY)
    first = plan["exercises"][0]
    body = {"session_id": f"{TUESDAY}-mob00001", "date": TUESDAY.isoformat(), "kind": "mobility",
            "duration_minutes": 26, "session_rpe": 4, "exercises": [{
                "exercise_id": "ex-mob-1", "exercise": first,
                "sets": [{"set_num": i, "reps": 1, "weight": 0, "tut": 90,
                          "ts": f"{TUESDAY}T19:0{i}:00"} for i in (1, 2, 3, 4)]}]}
    env.ok(monkeypatch, "post", "/api/training/sessions", local=TUESDAY, body=body)
    rows = [r for r in env.repo.get_all_training_exercises_raw()
            if r["session_id"] == body["session_id"]]
    assert [r["movement_type"] for r in rows] == [mob.MOBILITY_TYPE]
    assert env.ok(monkeypatch, "get", "/api/training/daily", local=TUESDAY)["done_today"]
    assert not env.repo.has_logged_session(TUESDAY)
    assert env.ok(monkeypatch, "get", "/api/training/session", local=TUESDAY)["kind"] == "plan"
    week = (MONDAY, MONDAY + timedelta(days=6))
    assert TUESDAY.isoformat() not in env.repo.get_logged_session_dates(*week)
    assert TUESDAY.isoformat() not in env.repo.get_logged_session_dates_live(*week)
    day = env.repo.get_daily_region_au(days=7, today=TUESDAY)["rows"]
    assert any(r["date"] == TUESDAY.isoformat() and r["total_au"] > 0 for r in day)


def test_from_week_4_sunday_is_a_rest_day(env, monkeypatch):
    """"Two evenings, no Sunday" (2026-11-11)."""
    sunday = MONDAY + timedelta(days=(gb.EVENING_MOBILITY_FROM_WEEK - 1) * 7 + 6)
    assert sunday == date(2026, 11, 15)
    r = env.call(monkeypatch, "get", "/api/training/session", local=sunday)
    assert r.status_code == 409 and r.json() == {"error": "rest_day"}


def test_the_egym_session_runs_through_the_same_flow_on_any_day(env, monkeypatch):
    """The EGYM session (2026-11-08): his gym's fourteen machines, two sets one
    after the other on each ("it can't be a circuit because of the current
    usage"), each set's tonnage typed from the machine; offered on a rest day too
    ("No, it's extra"); any machine may run next."""
    import egym_circuit as ec
    plan = env.ok(monkeypatch, "get", "/api/training/egym", local=WEDNESDAY)
    assert plan["kind"] == "egym" and plan["plan_days"] is None and plan["note"] == ec.NOTE
    assert [e["name"] for e in plan["exercises"]] == list(ec.names())
    assert all(e["tonnage_entry"] and not e["reps_editable"] and e["timer"] is None
               and e["sets"] == 2 and e["prescription"] == "2 sets, one after the other"
               for e in plan["exercises"])
    assert plan["exercises"][3]["move"] == {"group": 3, "movable": True, "after": []}
    # Each machine: set 1, the rest, set 2.
    assert len(plan["steps"]) == 3 * 14
    first = [st for st in plan["steps"] if st["ex_idx"] == 0]
    assert [(st["phase"], st["record_set"]) for st in first] == [
        ("intro", 1), ("resting", None), ("intro", 2)]
    assert 65 <= plan["model_minutes"] <= 73
    assert plan["ask_length_above_minutes"] == sess.DURATION_CHECK_RATIO * plan["model_minutes"]
    assert plan["rpe_target"] == ec.RPE_TARGET


def test_a_saved_egym_session_stores_its_tonnage_and_is_a_logged_day_that_marks_no_plan_day(
        env, monkeypatch):
    """His answers of 2026-11-08: only the tonnage is typed, the session counts as
    a training day, it is extra to the plan day, and it goes into the weekly
    tonnage. The next session shows each machine's last tonnage, set by set."""
    import training_constants as tc
    from services import tonnage
    plan = env.ok(monkeypatch, "get", "/api/training/egym", local=WEDNESDAY)
    squat = plan["exercises"][0]
    body = {"session_id": f"{WEDNESDAY}-egym0001", "date": WEDNESDAY.isoformat(), "kind": "egym",
            "duration_minutes": 70, "session_rpe": 6, "exercises": [
                {"exercise_id": "ex-egym-1", "exercise": squat, "raw_sets": [
                    {"set_num": 1, "completed_at": f"{WEDNESDAY}T18:00:00+01:00",
                     "right": {"reps": 1, "weight_kg": 1240, "seconds": None},
                     "rest_started_at": 1000.0, "rest_ended_at": 1050.0},
                    {"set_num": 2, "completed_at": f"{WEDNESDAY}T18:02:00+01:00",
                     "right": {"reps": 1, "weight_kg": 1300, "seconds": None}}]}]}
    out = env.ok(monkeypatch, "post", "/api/training/sessions", local=WEDNESDAY, body=body)
    assert out["stored"] and len(out["exercise_ids"]) == 1
    rows = [r for r in env.repo.get_all_training_exercises_raw()
            if r["session_id"] == body["session_id"]]
    assert [r["movement_type"] for r in rows] == ["EGYM"]
    assert rows[0]["total_volume_kg"] == 2540.0
    assert [(s["set_num"], s["reps"], s["weight"]) for s in rows[0]["sets"]] == [
        (1, 1, 1240), (2, 1, 1300)]
    assert not env.repo.has_logged_session(WEDNESDAY), "extra: it never marks a plan day done"
    week = (MONDAY, MONDAY + timedelta(days=6))
    assert WEDNESDAY.isoformat() in env.repo.get_logged_session_dates(*week)
    assert WEDNESDAY.isoformat() in env.repo.get_logged_session_dates_live(*week)
    series, _ = tonnage.weekly_tonnage(env.repo.get_all_training_exercises_raw(),
                                       tc.EXERCISE_BODY_REGION, today=WEDNESDAY, weeks=1)
    assert series[-1].sectors["lower_body"].kg == pytest.approx(2540)
    again = env.ok(monkeypatch, "get", "/api/training/egym", local=WEDNESDAY)
    assert again["exercises"][0]["previous_caption"] == "Last time 1,240 kg and 1,300 kg"
    assert again["exercises"][1]["previous_caption"] == ""


def test_session_d_from_week_4_is_the_egym_session_and_its_save_marks_d_done(env, monkeypatch):
    """The athlete, 2026-11-11: "Can we make this training Training day D". From
    Friday 13 November (week 4) the plan session on a Friday is the EGYM session:
    the same machines, the tonnage typed, the machines free to move, EGYM's own
    time model; saved as the plan session, it marks D done, and the next session
    reads its tonnage."""
    import egym_circuit as ec
    import goal_block as gbk
    friday = MONDAY + timedelta(days=(gbk.EGYM_D_FROM_WEEK - 1) * 7 + 4)
    assert friday == date(2026, 11, 13)
    plan = env.ok(monkeypatch, "get", "/api/training/session", local=friday)
    assert plan["kind"] == "plan" and plan["objective"] == "Session D — EGYM (week 4)"
    assert [e["name"] for e in plan["exercises"]] == list(ec.names())
    assert all(e["tonnage_entry"] and not e["reps_editable"] and e["entry"] is None
               and e["prescription"] == "2 sets, one after the other" for e in plan["exercises"])
    assert plan["exercises"][5]["move"] == {"group": 5, "movable": True, "after": []}
    assert 65 <= plan["model_minutes"] <= 73 and plan["alternatives"] == []
    squat = plan["exercises"][0]
    body = {"session_id": f"{friday}-d0000001", "date": friday.isoformat(), "kind": "plan",
            "duration_minutes": 70, "session_rpe": 7, "exercises": [
                {"exercise_id": "ex-d-1", "exercise": squat, "raw_sets": [
                    {"set_num": 1, "completed_at": f"{friday}T08:00:00+01:00",
                     "right": {"reps": 1, "weight_kg": 1240, "seconds": None}},
                    {"set_num": 2, "completed_at": f"{friday}T08:02:00+01:00",
                     "right": {"reps": 1, "weight_kg": 1300, "seconds": None}}]}]}
    env.ok(monkeypatch, "post", "/api/training/sessions", local=friday, body=body)
    assert env.repo.has_logged_session(friday), "session D is done"
    rows = [r for r in env.repo.get_all_training_exercises_raw()
            if r["session_id"] == body["session_id"]]
    assert rows[0]["movement_type"] != "EGYM" and rows[0]["total_volume_kg"] == 2540.0
    r = env.call(monkeypatch, "get", "/api/training/session", local=friday)
    assert r.status_code == 409 and r.json() == {"error": "already_logged"}
    extra = env.ok(monkeypatch, "get", "/api/training/egym", local=friday)
    assert extra["exercises"][0]["previous_caption"] == "Last time 1,240 kg and 1,300 kg"


def test_completion_asks_the_length_when_the_clock_ran_far_past_the_plan(env, monkeypatch):
    body = {"model_minutes": 60, "start_ts": 1000.0, "end_ts": 1000.0 + 150 * 60, "rpe": 7}
    out = env.ok(monkeypatch, "post", "/api/training/completion", body=body)
    assert out["clock_minutes"] == 150 and out["ask_length"]
    assert [c["source"] for c in out["choices"]] == ["plan", "clock"]
    assert out["choices"][1]["au"] == 7 * 150
    assert out["choices"][0]["au_by_rpe"] == [r * 60.0 for r in range(1, 11)]
    short = env.ok(monkeypatch, "post", "/api/training/completion",
                   body={**body, "end_ts": 1000.0 + 61 * 60})
    assert not short["ask_length"] and [c["minutes"] for c in short["choices"]] == [61]


# ── the Garmin taps and the heart-rate match ─────────────────────────────────

def test_the_watch_check_reads_the_callers_day(env, monkeypatch):
    asked = []
    monkeypatch.setattr(env.repo, "find_open_garmin_activity", lambda day: asked.append(day) or {
        "activity_id": 9, "name": "Strength", "type": "strength_training",
        "duration_minutes": 55.0})
    out = env.ok(monkeypatch, "get", "/api/training/garmin/open-activity", local=TUESDAY)
    assert out["found"] and out["activity"]["activity_id"] == "9"
    assert asked == [TUESDAY.isoformat()]


def test_a_walks_minutes_come_from_the_callers_day(env, monkeypatch):
    seen = []

    def minutes(target, buffer, now=None):
        seen.append(now)
        return 14.2, [{"duration": 852, "averageHR": 101, "maxHR": 120}]

    monkeypatch.setattr(env.repo, "get_recent_garmin_activity_minutes", minutes)
    out = env.ok(monkeypatch, "get", "/api/training/garmin/activity-minutes?planned_minutes=15",
                 local=TUESDAY)
    assert out["minutes"] == 14.2 and out["detail"]["avg_hr"] == 101
    assert out["window"] == [10, 20] and seen[0].date() == TUESDAY


def test_a_garmin_tap_waits_for_no_running_sync(env, monkeypatch):
    monkeypatch.setattr("healthapi.routes.training.GARMIN_WAIT_SECONDS", 0.0)
    with env.runner.exclusive():
        r = env.call(monkeypatch, "get", "/api/training/garmin/open-activity")
    assert r.status_code == 409 and r.json() == {"error": "sync_running"}


def test_the_heart_rate_match_compares_or_asks(env, monkeypatch):
    body = {"date": MONDAY.isoformat(), "sets_by_exercise": {"Hack Squat": []},
            "duration_minutes": 50, "reported_rpe": 6}
    monkeypatch.setattr(env.repo, "compute_session_hr", lambda *a, **k: {
        "hr_rpe": 6.8, "hr_au": 340.0, "hr_active_minutes": 48.0, "hr_coverage": 0.95,
        "activity_name": "Strength", "hr_covered_exercises": 9, "hr_total_exercises": 10})
    matched = env.ok(monkeypatch, "post", "/api/training/heart-rate", body=body)
    assert matched["state"] == "matched" and matched["comparison"]["verdict"] == "under"
    assert matched["comparison"]["au_delta"] == 340.0 - 300.0
    monkeypatch.setattr(env.repo, "compute_session_hr", lambda *a, **k: {
        "needs_choice": True, "reason": "no activity lines up with this session's clock",
        "candidates": [{"activity": {"activity_id": 7, "name": "Strength", "type": "strength",
                                     "start_time_local": "2026-10-19 07:05:00",
                                     "duration_minutes": 52}, "shift_hours": -1,
                        "quality": 0.8}]})
    choose = env.ok(monkeypatch, "post", "/api/training/heart-rate", body=body)
    assert choose["state"] == "choose" and choose["candidates"][0]["shift_hours"] == -1
    picked = []
    monkeypatch.setattr(env.repo, "compute_session_hr",
                        lambda *a, **k: picked.append(k) or None)
    env.ok(monkeypatch, "post", "/api/training/heart-rate",
           body={**body, "activity_id": "7", "shift_hours": -1})
    assert picked[0]["force_activity_id"] == "7" and picked[0]["shift_hours"] == -1
    monkeypatch.setattr(env.repo, "compute_session_hr", lambda *a, **k: None)
    assert env.ok(monkeypatch, "post", "/api/training/heart-rate",
                  body=body)["state"] == "no_match"


def test_the_heart_rate_match_reads_the_session_the_phone_saved(env, monkeypatch):
    """The phone sends the session it saved; the match gets the set records the
    save builds from its raw facts, keyed by exercise name, with their times."""
    from services import session_save
    split = {"name": "Split Squat", "type": "reps", "laterality": "unilateral", "sets": 1,
             "reps": 8, "weight_kg": 9.0, "equipment_type": "dumbbell", "rest_seconds": 60}
    raw = [{"set_num": 1, "completed_at": "2026-10-19T08:05:00+02:00",
            "right": {"reps": 8, "weight_kg": 9.0}, "left": {"reps": 7, "weight_kg": 9.0}}]
    saved = {"session_id": "2026-10-19-1a2b3c4d", "date": MONDAY.isoformat(), "kind": "plan",
             "duration_minutes": 40, "session_rpe": 7, "notes": "",
             "exercises": [{"exercise_id": "ex-1", "exercise": split, "raw_sets": raw},
                           {"exercise_id": "ex-2", "exercise": {**split, "name": "Skipped"}}]}
    seen = []
    monkeypatch.setattr(env.repo, "compute_session_hr", lambda d, sets, **k: seen.append(sets) or None)
    body = {"date": MONDAY.isoformat(), "session": saved, "duration_minutes": 40, "reported_rpe": 7}
    assert env.ok(monkeypatch, "post", "/api/training/heart-rate", body=body)["state"] == "no_match"
    assert list(seen[0]) == ["Split Squat"], "keyed by name; a skipped exercise is left out"
    assert seen[0]["Split Squat"] == json.loads(json.dumps(session_save.records_from_raw(split, raw)))


def _saved_session(kind="plan", session_id="2026-10-19-1a2b3c4d"):
    split = {"name": "Split Squat", "type": "reps", "laterality": "bilateral", "sets": 1,
             "reps": 8, "weight_kg": 9.0, "equipment_type": "dumbbell", "rest_seconds": 60}
    raw = [{"set_num": 1, "completed_at": "2026-10-19T08:05:00+02:00",
            "right": {"reps": 8, "weight_kg": 9.0}}]
    return {"session_id": session_id, "date": MONDAY.isoformat(), "kind": kind,
            "duration_minutes": 40, "session_rpe": 7, "notes": "",
            "exercises": [{"exercise_id": "ex-1", "exercise": split, "raw_sets": raw}]}


def _storing(env, monkeypatch, summary, plan_ids=("2026-10-19-1a2b3c4d",)):
    stored, read = [], []
    monkeypatch.setattr(env.repo, "compute_session_hr", lambda *a, **k: dict(summary))
    monkeypatch.setattr(env.repo, "store_session_hr", lambda d, s: stored.append((d, s)))
    monkeypatch.setattr(env.repo, "get_plan_session_ids",
                        lambda d: read.append(d) or set(plan_ids))
    return stored, read


_MATCH = {"date": MONDAY.isoformat(), "hr_rpe": 6.8, "hr_au": 340.0, "hr_coverage": 0.95,
          "activity_name": "Strength", "per_exercise": {"Split Squat": {"rpe": 6.1}}}


def test_a_match_of_the_stored_plan_session_is_kept_at_once(env, monkeypatch):
    """The athlete, 2026-11-11: "why didnt it take the data over at that stage ?".
    The match after a save stores the day's heart-rate row and each exercise's own
    effort (Repository.store_session_hr, as the morning sync does), and the same
    match sent again from the phone's outbox writes the same row."""
    stored, read = _storing(env, monkeypatch, _MATCH)
    body = {"date": MONDAY.isoformat(), "session": _saved_session(), "duration_minutes": 40,
            "reported_rpe": 7}
    assert env.ok(monkeypatch, "post", "/api/training/heart-rate", body=body)["state"] == "matched"
    env.ok(monkeypatch, "post", "/api/training/heart-rate", body=body)
    assert stored == [(MONDAY, _MATCH), (MONDAY, _MATCH)]
    assert read == [MONDAY, MONDAY]


def test_the_athletes_pick_in_the_travel_case_is_stored_too(env, monkeypatch):
    stored, _read = _storing(env, monkeypatch, _MATCH)
    body = {"date": MONDAY.isoformat(), "session": _saved_session(), "duration_minutes": 40,
            "reported_rpe": 7, "activity_id": "7", "shift_hours": -1}
    env.ok(monkeypatch, "post", "/api/training/heart-rate", body=body)
    assert stored == [(MONDAY, _MATCH)]


@pytest.mark.parametrize("case", ["refused_save", "extra_session", "no_session", "asks_which"])
def test_a_match_with_no_stored_plan_session_behind_it_stores_nothing(env, monkeypatch, case):
    """A save the engine refused (its id is not one of the day's plan sessions), an
    extra session (the "+" menu's), a match sent with the sets only, and a session the
    watch cannot place: shown, never stored. The morning sync keeps those days its own way."""
    summary = ({"needs_choice": True, "reason": "made-up", "candidates": []}
               if case == "asks_which" else _MATCH)
    stored, read = _storing(env, monkeypatch, summary,
                            plan_ids=() if case == "refused_save" else ("2026-10-19-1a2b3c4d",))
    session = _saved_session(kind="accessory" if case == "extra_session" else "plan")
    body = {"date": MONDAY.isoformat(), "duration_minutes": 40, "reported_rpe": 7,
            **({"sets_by_exercise": {"Split Squat": []}} if case == "no_session" else {"session": session})}
    env.ok(monkeypatch, "post", "/api/training/heart-rate", body=body)
    assert stored == []
    if case in ("extra_session", "no_session", "asks_which"):
        assert read == [], "the day's plan sessions are read only for a plan session's match"


# ── the "+" menu ─────────────────────────────────────────────────────────────

def test_the_yoga_catalogue_names_each_flows_cautions(env, monkeypatch):
    out = env.ok(monkeypatch, "get", "/api/training/yoga")
    assert out["stage_read"] and [f["slug"] for f in out["flows"]] == [
        s.slug for s in yg.YOGA_LIBRARY]
    flow = yg.YOGA_LIBRARY[0]
    assert len(out["flows"][0]["cautions"]) == len(flow.cautions(2))
    # The full routine shows each pose's hold, as the Streamlit page does (T110).
    assert [p["hold_seconds"] for p in out["flows"][0]["poses"]] == [
        p.hold_seconds for p in flow.poses]


def test_the_outdoor_list_puts_the_walking_family_first(env, monkeypatch):
    rows = [{"activity_id": 1, "name": "Gym", "type": "strength_training",
             "duration_minutes": 50.0},
            {"activity_id": 2, "name": "Mittenwald Walking", "type": "walking",
             "duration_minutes": 95.4, "distance_km": 7.2, "avg_hr": 118}]
    monkeypatch.setattr(env.repo, "get_garmin_activities_for_date", lambda d: rows)
    out = env.ok(monkeypatch, "get", f"/api/training/outdoor?date={MONDAY}")
    assert out["activities"][0]["activity_id"] == "2" and out["activities"][0]["in_family"]
    assert out["activities"][0]["logs_as"] == sess.outdoor_exercise_name("walking")
    assert out["activities"][0]["au_by_rpe"][3] == 4 * out["activities"][0]["minutes"]
    r = env.call(monkeypatch, "get", f"/api/training/outdoor?date={TUESDAY}")
    assert r.status_code == 422 and r.json() == {"error": "future_day"}


# ── more of the week and the day ─────────────────────────────────────────────

def test_a_failed_weeks_repeat_says_so_on_its_monday_and_holds_the_load(env, monkeypatch):
    from services import week_repeat
    next_monday = MONDAY + timedelta(days=7)
    assert week_repeat.store_failed_week_rule(env.repo, env.repo.get_phases(), next_monday)
    week = env.ok(monkeypatch, "get", "/api/training/week", local=next_monday)
    assert week["repeat_notice"] and week["load_held"]
    assert week["banner"]["last_week"] == "failed", "a failed week's line, on its Monday"
    paged = env.ok(monkeypatch, "get", f"/api/training/week?week_start={MONDAY}",
                   local=next_monday)
    assert paged["viewed_week_status"] == "failed"
    tuesday = env.ok(monkeypatch, "get", "/api/training/week",
                     local=next_monday + timedelta(days=1))
    assert tuesday["repeat_notice"] is None and tuesday["load_held"], "the hold runs all week"


def test_a_missed_day_shows_what_was_planned_and_the_swap(env, monkeypatch):
    day = env.ok(monkeypatch, "get", f"/api/training/day?date={MONDAY}", local=TUESDAY)
    assert day["route"] == "past_missed" and day["planned"]["day_num"] == 1
    assert day["swap"]["available"]


def test_no_block_today_shows_the_gap_and_a_stranded_block(env, monkeypatch):
    lapsed = sess.build_phase(5, MONDAY - timedelta(days=84), status="completed")
    lapsed.date_overrides[MONDAY.isoformat()] = 84
    upcoming = sess.build_phase(5, MONDAY + timedelta(days=7), status="upcoming")
    env.repo.set_phases([lapsed, upcoming])
    week = env.ok(monkeypatch, "get", "/api/training/week")
    assert week["phase"] is None and week["gap"]["next"]["days_away"] == 7
    assert week["gap"]["stranded"]["name"] == lapsed.name
    day = env.ok(monkeypatch, "get", "/api/training/day")
    assert day["route"] == "no_phase" and day["gap"]["next"]["start_date"] == upcoming.start_date


def test_a_day_past_the_blocks_content_reads_complete(env, monkeypatch):
    import dataclasses
    env.repo.set_phases([dataclasses.replace(sess.build_phase(5, MONDAY), length_days=91)])
    day = env.ok(monkeypatch, "get", "/api/training/day", local=MONDAY + timedelta(days=85))
    assert day["route"] == "today" and day["overview"]["screen"] == "complete"


def test_a_priority_block_carries_a_missed_session_forward(env, monkeypatch):
    block_b = sess.build_phase(4, date(2026, 9, 21))
    env.repo.set_phases([block_b])
    week = env.ok(monkeypatch, "get", "/api/training/week", local=date(2026, 9, 22))
    prompt = week["carry_prompt"]
    assert prompt is not None and not prompt["in_order"] and prompt["lines"]


def test_the_flexibility_retest_notice_rides_with_the_week(env, monkeypatch):
    from services import training_screen
    monkeypatch.setattr(env.repo, "get_flexibility_assessments", lambda: ("an assessment",))
    monkeypatch.setattr(training_screen.fx, "retest_notice",
                        lambda stored, recent, today: ("info", "ready", "84 days since the last"))
    retest = env.ok(monkeypatch, "get", "/api/training/week")["retest"]
    assert retest == {"kind": "info", "status": "ready", "reason": "84 days since the last"}


# ── seeding, ramps and the warning gate ──────────────────────────────────────

def _log(env, monkeypatch, day: date, name: str, reps: int, weight: float, sets: int = 3):
    body = {"session_id": f"{day}-{name[:4].lower()}0001", "date": day.isoformat(),
            "kind": "plan", "duration_minutes": 45, "session_rpe": 6, "exercises": [{
                "exercise_id": f"ex-{day}-{name}", "exercise": {
                    "name": name, "type": "reps", "sets": sets, "reps": reps,
                    "equipment_type": "machine"},
                "actual": {"reps": reps, "weight_kg": weight},
                "sets": [{"set_num": i, "reps": reps, "weight": weight,
                          "ts": f"{day}T08:1{i}:00"} for i in range(1, sets + 1)]}]}
    env.ok(monkeypatch, "post", "/api/training/sessions", local=day, body=body)


def test_a_lift_is_seeded_from_its_last_session_and_says_where_from(env, monkeypatch):
    for day in (MONDAY - timedelta(days=5), MONDAY - timedelta(days=3)):
        _log(env, monkeypatch, day, "Machine Chest Press", 12, 50.0)
    plan = env.ok(monkeypatch, "get", "/api/training/session")
    press = next(e for e in plan["exercises"] if e["name"] == "Machine Chest Press")
    assert press["entry"] is not None and press["previous"] is not None
    assert press["previous_caption"] and press["entry_caption"]
    assert press["entry"]["weight_kg"] is not None
    # Every set at the top of the range in both sessions: the weight steps, with
    # no check-in today (the athlete, 2026-11-11: "remove it its not required").
    assert press["entry"]["weight_kg"] == 52.5 and press["entry"]["action"] == "step_up"


def test_a_ramp_set_proposes_from_the_lift_it_prepares(env, monkeypatch):
    plan = env.ok(monkeypatch, "get", "/api/training/session", local=TUESDAY)
    content = sess.calendar_plan(sess.build_phase(5, MONDAY))[2]["exercises"]
    ramps = [e for e in plan["exercises"] if e["ramp_for"] is not None]
    assert ramps and [e["index"] for e in ramps] == [
        i for i, ex in enumerate(content) if sess.ramp_lift_index(content, i) is not None]
    for ramp in ramps:
        assert ramp["ramp_for"] == sess.ramp_lift_index(content, ramp["index"])
        lift = plan["exercises"][ramp["ramp_for"]]
        if ramp["entry"] and lift["entry"] and lift["entry"].get("weight_kg"):
            assert ramp["entry"]["weight_kg"] <= lift["entry"]["weight_kg"]


def test_the_warning_shows_only_while_its_area_is_strained():
    ex = {"name": "Incline DB Press", "type": "reps", "sets": 3, "reps": 10,
          "laterality": "bilateral", "rest_seconds": 90, "tempo": "2-0-2",
          "warning": "Stop at any shoulder pinch.",
          "mechanics": "Press."}
    hot = {"upper_body": 18.0, "core": 2.0, "lower_body": 2.0}
    cool = {"upper_body": 4.0, "core": 2.0, "lower_body": 2.0}
    shown = tsession.exercise_out(ex, 0, None, None, (hot, cool), False)
    hidden = tsession.exercise_out(ex, 0, None, None, (cool, cool), False)
    assert shown["warning"] == "Stop at any shoulder pinch." and hidden["warning"] == ""


# ── Weight steps and replacements (WP-46) ────────────────────────────────────

def _equipment_body(env, monkeypatch, **steps):
    got = env.ok(monkeypatch, "get", "/api/settings/equipment")
    items = [{k: i[k] for k in ("id", "name", "step", "unit", "kind")} for i in got["items"]]
    for i in items:
        i["step"] = steps.get(i["id"], i["step"])
    return {"items": items, "links": {}}


def test_the_weight_steps_are_the_blocks_until_changed_and_a_change_reaches_the_session(env, monkeypatch):
    got = env.ok(monkeypatch, "get", "/api/settings/equipment")
    assert {i["id"] for i in got["items"]} >= {"dumbbells", "machines", "cables", "new_cable_machine"}
    hack = next(e for e in got["exercises"] if e["name"] == "Hack Squat")
    assert (hack["item_id"], hack["step"]) == ("machines", 2.5)
    body = _equipment_body(env, monkeypatch, machines=5.0)
    saved = env.ok(monkeypatch, "put", "/api/settings/equipment", body=body)
    assert next(e for e in saved["exercises"] if e["name"] == "Hack Squat")["step"] == 5.0
    assert env.ok(monkeypatch, "put", "/api/settings/equipment", body=body) == saved, "the same list twice"
    plan = env.ok(monkeypatch, "get", "/api/training/session", local=TUESDAY)
    assert next(e for e in plan["exercises"] if e["name"] == "Hack Squat")["increment_size"] == 5.0


def test_a_list_the_engine_refuses_is_answered_with_its_reason(env, monkeypatch):
    body = _equipment_body(env, monkeypatch)
    body["items"] = body["items"][1:]
    r = env.call(monkeypatch, "put", "/api/settings/equipment", body=body)
    assert r.status_code == 422 and "default items cannot be removed" in r.json()["error"]


def test_a_replacement_made_in_a_session_is_offered_today_and_every_time_after(env, monkeypatch):
    body = {"lift": "Hack Squat", "name": "Smith Machine Squat", "item_id": "machines"}
    got = env.ok(monkeypatch, "post", "/api/training/replacements", body=body, local=TUESDAY)
    assert got["replacement"]["name"] == "Smith Machine Squat"
    alt = got["alternative"]
    assert [e["name"] for e in alt["exercises"]] == ["Smith Machine Squat (Ramp Set)", "Smith Machine Squat"]
    plan = env.ok(monkeypatch, "get", "/api/training/session", local=TUESDAY)
    hack = next(e for e in plan["exercises"] if e["name"] == "Hack Squat")
    names = [a["name"] for a in plan["alternatives"]]
    assert names == ["V Squat", "Smith Machine Squat"]
    assert all(a["for_group"] == hack["move"]["group"] for a in plan["alternatives"])
    again = env.ok(monkeypatch, "post", "/api/training/replacements", body=body, local=TUESDAY)
    assert again["replacement"] == got["replacement"], "the same name twice stores one"
    r = env.call(monkeypatch, "post", "/api/training/replacements",
                 body={**body, "name": "Machine Chest Press"}, local=TUESDAY)
    assert r.status_code == 422 and "already called" in r.json()["error"]
