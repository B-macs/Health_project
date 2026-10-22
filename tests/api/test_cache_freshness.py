"""The local copy's freshness rule (rebuild Phase 2, milestone 5;
services/cache_freshness.py and record_cache.refresh).

The Streamlit app and the engine each read a local copy of Supabase, and
each copy holds none of the other process's writes since its last pull. So
a copy older than the limit is pulled again. What this pins:

- a stale copy is pulled again, a fresh one is not;
- an open Repository reads the pulled rows, and still writes after;
- a pull waits for a running sync, and the Streamlit app never waits;
- a row this process writes while a pull runs is never lost;
- a failed pull leaves the copy as it was and is not retried at once;
- the engine pulls before it answers; the Streamlit app at an open.

Against a fake Supabase (tests/_record_store.py). No network.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from services import cache_freshness as cf
from services import record_cache, supabase_store
from services.background_sync import BackgroundSyncRunner
from tests._record_store import FakeStore, local_rows, new_local_copy, record_config, record_repo

ROOT = Path(__file__).resolve().parents[2]
LIMIT = cf.MAX_AGE_MINUTES * 60


@pytest.fixture(autouse=True)
def _clean():
    supabase_store.OUTBOX.drain()
    cf.forget_failures()
    yield
    supabase_store.OUTBOX.drain()
    cf.forget_failures()


@pytest.fixture
def copy_path(tmp_path):
    path = new_local_copy(tmp_path)
    yield path
    record_cache.forget(path)


def _age(path: str, seconds: float) -> None:
    """Mark the copy as pulled `seconds` ago."""
    record_cache._PULLED_AT[record_cache._key(path)] = time.time() - seconds


def _config_row(key: str, value: str) -> dict:
    return {"key": key, "value": value, "updated": "2026-10-19"}


def _local_config(path: str, key: str):
    rows = local_rows(path, "SELECT value FROM config WHERE key = ?", key)
    return rows[0][0] if rows else None


def _runner(path: str) -> BackgroundSyncRunner:
    return BackgroundSyncRunner(record_config(path))


def test_a_stale_copy_is_pulled_again_and_a_fresh_one_is_not(copy_path):
    store = FakeStore({"config": [_config_row("written_elsewhere", "by the other process")]})
    factory = lambda url, key: store              # noqa: E731
    _age(copy_path, LIMIT + 1)
    out = cf.refresh_if_stale(record_config(copy_path), _runner(copy_path), wait_seconds=0.0,
                              store_factory=factory)
    assert out == cf.REFRESHED
    assert _local_config(copy_path, "written_elsewhere") == "by the other process"
    again = cf.refresh_if_stale(record_config(copy_path), _runner(copy_path), wait_seconds=0.0,
                                store_factory=factory)
    assert again == cf.FRESH


def test_a_pull_counts_as_a_write_for_the_reads(copy_path):
    # A read shared while it is computed (api/healthapi/shared_reads.py) is keyed on the
    # write counter: one asked after a pull never takes an answer computed before it.
    from services.clients import sheets
    before = sheets.write_generation()
    record_cache.refresh(record_config(copy_path), lambda url, key: FakeStore())
    assert sheets.write_generation() > before


def test_an_open_repository_reads_the_pulled_rows_and_still_writes(copy_path):
    store = FakeStore()
    repo = record_repo(copy_path, store)
    assert repo.get_config_value("written_elsewhere") is None   # its connection is open now
    store.tables["config"] = [_config_row("written_elsewhere", "by the other process")]
    record_cache.refresh(record_config(copy_path), lambda url, key: store)
    repo._invalidate_config_cache()
    assert repo.get_config_value("written_elsewhere") == "by the other process"
    repo.set_config("written_here", "after the pull")
    assert _local_config(copy_path, "written_here") == "after the pull"


def test_a_pull_waits_for_a_running_sync_and_the_page_never_does(copy_path):
    store = FakeStore()
    runner = _runner(copy_path)
    _age(copy_path, LIMIT + 1)
    held = threading.Event()

    def sync():
        with runner.exclusive():
            held.set()
            time.sleep(0.5)

    worker = threading.Thread(target=sync)
    worker.start()
    held.wait()
    assert cf.refresh_if_stale(record_config(copy_path), runner, wait_seconds=0.0,
                               store_factory=lambda u, k: store) == cf.BUSY
    started = time.time()
    out = cf.refresh_if_stale(record_config(copy_path), runner, wait_seconds=5.0,
                              store_factory=lambda u, k: store)
    worker.join()
    assert out == cf.REFRESHED and time.time() - started >= 0.3


class SlowStore(FakeStore):
    """A pull that stops after reading the config table until `go` is set,
    so a write can land between the pull's read and the copy's replacement.
    `wrote` is set when a write reaches the store, so the test waits for the
    event itself rather than for a fixed time (a 0.2 s sleep failed under a
    loaded machine on 2026-10-20 while the behaviour was right)."""

    def __init__(self, tables=None):
        super().__init__(tables)
        self.config_read = threading.Event()
        self.go = threading.Event()
        self.wrote = threading.Event()

    def select_all(self, table, order=""):
        rows = super().select_all(table, order)
        if table == "config" and not self.go.is_set():
            self.config_read.set()
            self.go.wait(timeout=10)
        return rows

    def upsert(self, table, rows):
        out = super().upsert(table, rows)
        self.wrote.set()
        return out


def test_a_row_written_while_a_pull_runs_is_never_lost(copy_path):
    store = SlowStore({"config": [_config_row("before", "the pull")]})
    repo = record_repo(copy_path, store)
    puller = threading.Thread(target=record_cache.refresh,
                              args=(record_config(copy_path), lambda u, k: store))
    puller.start()
    assert store.config_read.wait(timeout=10), "the pull read the config table"
    writer = threading.Thread(target=repo.set_config, args=("during", "the pull"))
    writer.start()
    assert store.wrote.wait(timeout=10), "the write reached Supabase"
    assert any(r["key"] == "during" for r in store.tables["config"])
    time.sleep(0.05)                    # its copy write now waits on the pull's lock
    store.go.set()
    puller.join(timeout=10)
    writer.join(timeout=10)
    assert _local_config(copy_path, "before") == "the pull"
    assert _local_config(copy_path, "during") == "the pull", "applied to the new copy"


def test_a_failed_pull_leaves_the_copy_and_is_not_retried_at_once(copy_path):
    repo = record_repo(copy_path, FakeStore())
    repo.set_config("kept", "as it was")
    calls = []

    class Down(FakeStore):
        def select_all(self, table, order=""):
            calls.append(table)
            raise supabase_store.SupabaseError("the store is down")

    _age(copy_path, LIMIT + 1)
    factory = lambda u, k: Down()                # noqa: E731
    assert cf.refresh_if_stale(record_config(copy_path), _runner(copy_path), wait_seconds=0.0,
                               store_factory=factory) == cf.FAILED
    assert _local_config(copy_path, "kept") == "as it was"
    tried = len(calls)
    assert cf.refresh_if_stale(record_config(copy_path), _runner(copy_path), wait_seconds=0.0,
                               store_factory=factory) == cf.FAILED
    assert len(calls) == tried, "not asked again within the back-off"


def test_the_limit_is_a_setting(monkeypatch):
    monkeypatch.setenv("HEALTH_CACHE_MAX_AGE_MINUTES", "5")
    assert cf.max_age_seconds() == 300
    monkeypatch.delenv("HEALTH_CACHE_MAX_AGE_MINUTES")
    assert cf.max_age_seconds() == cf.MAX_AGE_MINUTES * 60


def test_off_turns_the_pull_off(copy_path, monkeypatch):
    """Switch step 7 (rebuild Phase 9): once the engine is the only writer, its copy
    holds every write and is never pulled again. Any case; a wrong value is the default."""
    monkeypatch.setenv("HEALTH_CACHE_MAX_AGE_MINUTES", "Off")
    assert cf.max_age_seconds() is None
    pulled = []
    out = cf.refresh_if_stale(record_config(copy_path), _runner(copy_path), wait_seconds=0.0,
                              now=time.time() + 10 ** 9,
                              store_factory=lambda *_a, **_k: pulled.append(1))
    assert out == cf.OFF and pulled == []
    monkeypatch.setenv("HEALTH_CACHE_MAX_AGE_MINUTES", "never")
    assert cf.max_age_seconds() == cf.MAX_AGE_MINUTES * 60


def test_the_engine_pulls_before_it_answers(monkeypatch):
    pytest.importorskip("fastapi")
    import sys
    if str(ROOT / "api") not in sys.path:
        sys.path.insert(0, str(ROOT / "api"))
    from healthapi import engine
    asked = []
    monkeypatch.setattr(engine.STATE, "config", object())
    monkeypatch.setattr(engine, "sync_runner", lambda: "the runner")
    monkeypatch.setattr(engine.cache_freshness, "refresh_if_stale",
                        lambda config, runner, wait_seconds: asked.append((runner, wait_seconds)))
    monkeypatch.setattr(engine, "Repository", lambda config: "a repository")
    assert engine.new_repository() == "a repository"
    assert asked == [("the runner", engine.REFRESH_WAIT_SECONDS)]


def test_the_streamlit_app_pulls_at_an_open_and_never_waits():
    app_src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "if st.runtime.exists():\n    repo.refresh_copy_if_stale()" in app_src
    repo_src = (ROOT / "repo.py").read_text(encoding="utf-8")
    body = repo_src.split("def refresh_copy_if_stale")[1]
    assert "wait_seconds=0.0" in body
