"""The schedule answers through the phone's outbox (rebuild Phase 7), and the reads behind
the week page:

- a read never writes: the week and every day view ASK before anything moves
  (the athlete's rule, 2026-08-07), so opening the page, paging the weeks or
  opening a day stores nothing, even while a carry or a shift is proposed;
- an answer carries the id the phone minted for it, and is applied once
  (training_screen.once, rebuild rule 4): the outbox sends it again when the
  first answer was lost on the way back, and a swap applied twice would put
  the two days back where they were;
- the ids kept are bounded, and an id has a clean shape.

The gate's unasked_moves counter runs this file. Through the real Repository
over a fake Supabase (tests/_record_store.py), with the 12-week block.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

pytest.importorskip("fastapi")

from services import scheduling  # noqa: E402
from services import training_screen as ts  # noqa: E402
from tests.api.test_api_training import MONDAY, TUESDAY, WEDNESDAY, _empty_outbox, env  # noqa: E402,F401

DAYS = [MONDAY + timedelta(days=i) for i in range(7)]


def test_the_week_and_every_day_view_write_nothing(env, monkeypatch):
    monkeypatch.setattr(scheduling, "should_shift_session", lambda bio, checkin, today: (True, "short sleep"))
    before = len(env.store.log)
    for local in (MONDAY, TUESDAY, WEDNESDAY):
        week = env.ok(monkeypatch, "get", "/api/training/week", local=local)
        env.ok(monkeypatch, "get", f"/api/training/week?week_start={(MONDAY + timedelta(days=7)).isoformat()}",
               local=local)
        for day in DAYS:
            env.ok(monkeypatch, "get", f"/api/training/day?date={day.isoformat()}", local=local)
    assert week["carry_prompt"] is not None, "a move was proposed, so the reads had something to write"
    assert env.store.log[before:] == [], "a read wrote to the store"
    assert env.phase().date_overrides == {}


def test_a_swap_sent_twice_with_one_id_stays_swapped(env, monkeypatch):
    body = {"date": TUESDAY.isoformat(), "action_id": "01JA6Z3M4X9S1Q2W3E4R5T6Y7U"}
    assert env.ok(monkeypatch, "post", "/api/training/swap", body=body) == {"stored": True}
    swapped = dict(env.phase().date_overrides)
    assert swapped
    assert env.ok(monkeypatch, "post", "/api/training/swap", body=body) == {"stored": True}
    assert env.phase().date_overrides == swapped, "the second send swapped the days back"
    # A new id is a new answer: the same swap pressed again swaps back, as it always did.
    env.ok(monkeypatch, "post", "/api/training/swap", body={**body, "action_id": "another-press"})
    assert env.phase().date_overrides != swapped


def test_a_carry_sent_again_after_a_lost_answer_is_stored_once_not_refused(env, monkeypatch):
    body = {"accept": True, "action_id": "carry-1"}
    assert env.ok(monkeypatch, "post", "/api/training/carry", local=TUESDAY, body=body) == {"stored": True}
    moved = dict(env.phase().date_overrides)
    assert env.ok(monkeypatch, "post", "/api/training/carry", local=TUESDAY, body=body) == {"stored": True}
    assert env.phase().date_overrides == moved
    # Without an id, a second answer is a new one, and there is nothing left to carry.
    r = env.call(monkeypatch, "post", "/api/training/carry", local=TUESDAY, body={"accept": True})
    assert r.status_code == 409 and r.json() == {"error": "nothing_to_carry"}


def test_a_refused_answer_keeps_no_id_so_it_can_be_sent_again(env, monkeypatch):
    env.ok(monkeypatch, "post", "/api/training/carry", local=TUESDAY, body={"accept": False})
    r = env.call(monkeypatch, "post", "/api/training/carry", local=TUESDAY,
                 body={"accept": True, "action_id": "carry-2"})
    assert r.status_code == 409
    assert "carry-2" not in ts.applied_actions(env.repo)


def test_an_answer_id_has_a_clean_shape(env, monkeypatch):
    for bad in ("", "has spaces", "x" * 65, "semi;colon"):
        r = env.call(monkeypatch, "post", "/api/training/swap",
                     body={"date": TUESDAY.isoformat(), "action_id": bad})
        assert r.status_code == 422, bad
    assert env.phase().date_overrides == {}


def test_the_ids_kept_are_bounded_newest_last(env):
    for i in range(ts.ACTIONS_KEPT + 5):
        ts.once(env.repo, f"id-{i}", MONDAY, lambda: {"stored": True})
    kept = json.loads(env.repo.get_config_value_live(ts.APPLIED_ACTIONS_KEY))
    assert len(kept) == ts.ACTIONS_KEPT
    assert kept[-1] == f"id-{ts.ACTIONS_KEPT + 4}" and "id-0" not in kept


def test_an_answer_without_an_id_runs_as_before(env):
    runs = []
    ts.once(env.repo, None, MONDAY, lambda: runs.append(1) or {"stored": True})
    ts.once(env.repo, None, MONDAY, lambda: runs.append(1) or {"stored": True})
    assert runs == [1, 1]
    assert ts.applied_actions(env.repo) == []
