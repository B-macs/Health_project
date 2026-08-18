# -*- coding: utf-8 -*-
"""A structural config write must reach Supabase before the process can end.

FOUND LIVE 2026-08-18, on the morning of day 2 of the block. The athlete
opened the hosted app and it showed "Reassessment — no phase active", offering
to begin Stage 2B starting Mon 24 Aug — a week late, and pressing it would
have overwritten the real Phase 3 in Notion.

Notion was correct throughout: Phase 3, active, starting 2026-08-17. Supabase
was not. Its `phases` row was last updated 2026-08-14 and still showed Stage
2A active.

THE MECHANISM. The mirror had exactly ONE flush site — the last step of
run_home_syncs — against NINE config write sites in views/training.py. A
write from a UI button queues a row into a process-memory outbox and returns;
if the process ends before any sync runs, the row is gone. Notion keeps the
write, Supabase never sees it.

WHY THAT IS WORSE THAN A LOST BACKUP. The hosted app READS from a SQLite
cache hydrated out of Supabase (key rule 18 — the filesystem is ephemeral, so
a redeploy wipes the disk and re-pulls). So a dropped mirror row does not
merely lose a copy: the next redeploy silently REVERTS the app's view to an
older state while the system of record disagrees with it, and nothing errors.
Exactly the same shape as the flexibility-assessment loss fixed the day
before, arriving through the config lane instead.

These tests pin the fix and its deliberate exclusion.
"""
from __future__ import annotations

import inspect

import pytest

from services.repository import Repository

SRC = inspect.getsource(Repository.set_config)


class _FakeConfig:
    notion_db_config = "config-db"


class _FakeRepo:
    """Enough of Repository to exercise set_config's flush decision without a
    Notion client. The real method is bound in below, so these tests exercise
    the shipping code rather than a copy of it."""

    _FLUSH_IMMEDIATELY = Repository._FLUSH_IMMEDIATELY

    def __init__(self):
        self.flushes = 0
        self.mirrored: list[str] = []
        self.notion_calls: list[tuple[str, str]] = []
        self.pages: dict[str, str] = {}          # key -> page id
        self.config = _FakeConfig()
        self._nc = object()

    def _config_page(self, key):
        return {"id": self.pages[key]} if key in self.pages else None

    def _live_page_id(self, page_id):
        return page_id

    def mirror_notion_write(self, table, key, props):
        self.mirrored.append(key)

    def flush_supabase_mirror(self):
        self.flushes += 1
        return {}

    def _invalidate_config_cache(self):
        pass

    set_config = Repository.set_config


@pytest.fixture
def repo(monkeypatch):
    r = _FakeRepo()
    import services.repository as rp

    class _FakeNotion:
        @staticmethod
        def title(v):
            return {"title": v}

        @staticmethod
        def rich_text(v):
            return {"rich_text": v}

        @staticmethod
        def date_prop(v):
            return {"date": v}

        @staticmethod
        def update_page(nc, page_id, props):
            r.notion_calls.append(("update", page_id))

        @staticmethod
        def create_page(nc, db, properties=None):
            r.notion_calls.append(("create", db))

    monkeypatch.setattr(rp, "notion", _FakeNotion)
    return r


@pytest.mark.parametrize("key", sorted(Repository._FLUSH_IMMEDIATELY))
def test_structural_keys_flush_immediately(repo, key):
    """phases, current_stage and plan_start_date decide which block the app
    thinks you are in. A redeploy between the write and the next sync must not
    be able to lose them."""
    repo.set_config(key, "value")
    assert repo.notion_calls, "the Notion write must still happen"
    assert repo.flushes == 1, (
        f"{key!r} did not flush — a redeploy before the next run_home_syncs "
        f"would revert the hosted app to the previous value"
    )


def test_the_training_checkpoint_does_not_flush(repo):
    """DELIBERATE EXCLUSION. training_progress is written on every transition
    of the guided flow — the hot path _save_checkpoint keeps off the network —
    it is regenerated continuously, and it already has a durable local mirror.
    Flushing it would add a network round trip to every set completion."""
    repo.set_config("training_progress", "{}")
    assert repo.flushes == 0
    assert "training_progress" in repo.mirrored, "it must still be QUEUED"


def test_phases_is_covered_because_set_phases_routes_through_set_config():
    """set_phases is the only way a phase reaches storage and it delegates to
    set_config('phases', ...), so covering the key covers the method."""
    assert 'self.set_config("phases"' in inspect.getsource(Repository.set_phases)
    assert "phases" in Repository._FLUSH_IMMEDIATELY


def test_the_flush_happens_after_the_notion_write():
    """Ordering is the contract the rest of the mirror keeps: never ship a row
    to Postgres that Notion does not hold."""
    assert SRC.index("mirror_notion_write") < SRC.index("if key in self._FLUSH_IMMEDIATELY")


def test_the_flush_is_inside_the_try_so_a_notion_failure_skips_it():
    """Matched on the STATEMENT, not the bare word — 'finally:' also appears
    in a comment above, and the first version of this test matched that and
    failed against correct code."""
    finally_block = SRC.index("\n        finally:")
    assert SRC.index("if key in self._FLUSH_IMMEDIATELY") < finally_block


def test_a_notion_failure_does_not_flush(repo, monkeypatch):
    """The row must not ship when the write it mirrors did not land."""
    import services.repository as rp

    def _boom(*a, **k):
        raise RuntimeError("notion down")

    monkeypatch.setattr(rp.notion, "create_page", _boom)
    with pytest.raises(RuntimeError):
        repo.set_config("phases", "[]")
    assert repo.flushes == 0


def test_a_mirror_failure_cannot_break_a_config_write():
    """flush_supabase_mirror never raises by contract. If that ever changes, a
    Supabase outage would start breaking phase writes — the failure the mirror
    exists to be harmless against."""
    assert "except" in inspect.getsource(Repository.flush_supabase_mirror), (
        "flush_supabase_mirror must swallow — set_config now calls it inline"
    )
