# -*- coding: utf-8 -*-
"""Flexibility assessments must survive a redeploy.

Written 2026-08-17. They lived ONLY in .sync_state.json — gitignored, local,
wiped by any hosted redeploy (key rule 18: the filesystem is ephemeral) — and
that cost three of the athlete's four cold-morning battery captures. The one
surviving entry is itself stamped "RECONSTRUCTED 2026-08-12 after the only
copy was lost from .sync_state.json". Losing the mornings did not only lose
data: three mornings were the NOISE FLOOR, so it lost the ability to call a
future change a result.

The fix is the training checkpoint's exact two-tier idiom:

    save:  local mirror FIRST, then the Notion Config row — a Notion failure
           leaves the fresher copy on disk, so local is never older than
           Notion and read's fixed local-first precedence is safe.
    read:  local wins; an empty local falls back to config (the
           redeploy-recovery path) and heals the local mirror on the way.

These tests drive the REAL methods against a temp local-cache file and a fake
Notion config, so the contract is behavioural rather than a source grep.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from services import flexibility
from services.battery import Assessment, Reading
from services.clients import local_cache
from services.repository import Repository

_KEY = "flexibility_assessments"


def _assessment(day: str, note: str = "") -> Assessment:
    return Assessment(
        cluster="a", taken_on=dt.date.fromisoformat(day), cold=True, note=note,
        readings=(Reading(test_key="tilt_production", value=93.0, unit="°"),),
    )


class _FakeRepo:
    """Just enough of Repository for the two methods under test: they touch
    self.get_config_value / self.set_config and nothing else of self."""

    def __init__(self, stored: str | None = None):
        self.config_store = {}
        if stored is not None:
            self.config_store[_KEY] = stored
        self.set_config_calls = []
        self.fail_set_config = False

    def get_config_value(self, key):
        return self.config_store.get(key)

    def set_config(self, key, value, today=None):
        if self.fail_set_config:
            raise RuntimeError("notion down")
        self.set_config_calls.append(key)
        self.config_store[key] = value

    # the real methods, bound to this fake
    get_flexibility_assessments = Repository.get_flexibility_assessments
    save_flexibility_assessment = Repository.save_flexibility_assessment


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    """Point the module-level default at a temp file — local_cache resolves
    `path or _DEFAULT_PATH` at CALL time precisely so this works."""
    monkeypatch.setattr(local_cache, "_DEFAULT_PATH", tmp_path / "state.json")
    return tmp_path / "state.json"


def test_save_writes_both_sinks(tmp_cache):
    repo = _FakeRepo()
    repo.save_flexibility_assessment(_assessment("2026-08-17"))

    local = local_cache.read().get(_KEY)
    assert local and local[0]["taken_on"] == "2026-08-17"
    assert repo.set_config_calls == [_KEY]
    assert json.loads(repo.config_store[_KEY]) == local


def test_local_is_written_before_notion_so_a_notion_failure_loses_nothing(tmp_cache):
    """The order IS the contract. A 40-minute assessment must be on disk before
    the network is trusted, and the failure must still surface to the caller —
    swallowing it would recreate exactly the silent loss this fixes."""
    repo = _FakeRepo()
    repo.fail_set_config = True
    with pytest.raises(RuntimeError):
        repo.save_flexibility_assessment(_assessment("2026-08-17"))
    local = local_cache.read().get(_KEY)
    assert local and local[0]["taken_on"] == "2026-08-17"


def test_read_falls_back_to_config_when_local_is_empty(tmp_cache):
    """The redeploy: disk wiped, Notion intact."""
    stored = json.dumps([flexibility.assessment_to_dict(_assessment("2026-08-12"))])
    repo = _FakeRepo(stored=stored)

    got = repo.get_flexibility_assessments()
    assert [a.taken_on.isoformat() for a in got] == ["2026-08-12"]
    # ...and the local mirror is healed, so the next read is local again.
    assert local_cache.read().get(_KEY)


def test_local_wins_and_config_is_not_even_consulted(tmp_cache):
    """Local is written first on save, so it is never older than Notion —
    consulting config when local exists could only replace fresher with
    staler."""
    repo = _FakeRepo(stored=json.dumps(
        [flexibility.assessment_to_dict(_assessment("2026-01-01", "stale"))]))
    local_cache.update({_KEY: [flexibility.assessment_to_dict(
        _assessment("2026-08-17", "fresh"))]})

    got = repo.get_flexibility_assessments()
    assert [a.taken_on.isoformat() for a in got] == ["2026-08-17"]


def test_same_date_replaces_in_both_sinks(tmp_cache):
    repo = _FakeRepo()
    repo.save_flexibility_assessment(_assessment("2026-08-17", "first"))
    repo.save_flexibility_assessment(_assessment("2026-08-17", "corrected"))

    local = local_cache.read().get(_KEY)
    assert len(local) == 1 and local[0]["note"] == "corrected"
    assert len(json.loads(repo.config_store[_KEY])) == 1


def test_unparseable_config_degrades_to_no_assessments(tmp_cache):
    """A corrupt config row must read as "none recorded", the state the screen
    already renders honestly — not raise on every page load."""
    repo = _FakeRepo(stored="{not json")
    assert repo.get_flexibility_assessments() == ()
