"""
Tests for services/background_sync.py — the worker that runs the Home page's
device-sync chain off the Streamlit script thread.

The properties that matter are concurrency ones, so most of this is about
what happens when start() is called repeatedly (every widget interaction
reruns the script), when a run raises, and whether the worker can ever share
a Repository with the UI thread.
"""

from __future__ import annotations

import threading
import time
from datetime import date

from services.background_sync import BackgroundSyncRunner
from services.config import Config


def _config(**overrides) -> Config:
    base = dict(
        notion_api_key="ntn_test",
        notion_db_readiness="db-readiness",
        notion_db_training="db-training",
        notion_db_biometrics="db-biometrics",
        notion_db_config="db-config",
        google_sheets_id="sheet-id",
        google_service_account={"type": "service_account"},
    )
    base.update(overrides)
    return Config(**base)


OK = {"oura": (True, None), "garmin": (True, None)}


class _FakeRepo:
    """Records the Config it was built from and how long the chain took."""

    instances: list = []

    def __init__(self, config, results=None, delay=0.0, boom=None):
        self.config = config
        self._results = results if results is not None else dict(OK)
        self._delay = delay
        self._boom = boom
        self.calls = []
        _FakeRepo.instances.append(self)

    def run_home_syncs(self, today=None, now=None, hours=2):
        self.calls.append(today)
        if self._delay:
            time.sleep(self._delay)
        if self._boom:
            raise self._boom
        return self._results


def _runner(**kw):
    _FakeRepo.instances = []
    factory = lambda cfg: _FakeRepo(cfg, **kw)  # noqa: E731
    return BackgroundSyncRunner(_config(), repository_factory=factory)


def _join(runner, timeout=5.0):
    deadline = time.time() + timeout
    while runner.running and time.time() < deadline:
        time.sleep(0.01)
    assert not runner.running, "background run did not finish"


# ─── The worker never borrows the UI thread's Repository ─────────────────────

def test_worker_builds_its_own_repository_from_the_config():
    """Not an optimisation detail — a Repository owns a gspread session, a
    Notion client and two mutable caches, none of them thread-safe, and the
    UI thread reads through its own copy the whole time this is running."""
    runner = _runner()
    runner.run_now(today=date(2026, 8, 1))
    assert len(_FakeRepo.instances) == 1
    assert _FakeRepo.instances[0].config is runner._config


def test_each_run_gets_a_fresh_repository():
    runner = _runner()
    runner.run_now()
    runner.run_now()
    assert len(_FakeRepo.instances) == 2
    assert _FakeRepo.instances[0] is not _FakeRepo.instances[1]


# ─── One run at a time ───────────────────────────────────────────────────────

def test_start_returns_true_then_false_while_running():
    runner = _runner(delay=0.4)
    assert runner.start() is True
    assert runner.start() is False    # a rerun mid-sync must not spawn a second
    _join(runner)


def test_repeated_starts_spawn_exactly_one_run():
    """Every widget interaction reruns the script and calls start() again."""
    runner = _runner(delay=0.3)
    started = [runner.start() for _ in range(12)]
    _join(runner)
    assert started.count(True) == 1
    assert len(_FakeRepo.instances) == 1


def test_start_works_again_once_the_previous_run_finished():
    runner = _runner()
    assert runner.start() is True
    _join(runner)
    assert runner.start() is True
    _join(runner)
    assert len(_FakeRepo.instances) == 2


def test_run_now_does_not_overlap_an_in_flight_background_run():
    runner = _runner(delay=0.4)
    runner.start()
    runner.run_now()                       # must not start a second chain
    _join(runner)
    assert len(_FakeRepo.instances) == 1


def test_concurrent_starts_from_many_threads_still_yield_one_run():
    runner = _runner(delay=0.3)
    results = []
    barrier = threading.Barrier(8)

    def _go():
        barrier.wait()
        results.append(runner.start())

    threads = [threading.Thread(target=_go) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    _join(runner)
    assert results.count(True) == 1
    assert len(_FakeRepo.instances) == 1


# ─── Results ─────────────────────────────────────────────────────────────────

def test_results_empty_before_any_run():
    assert _runner().results() == {}


def test_results_available_after_a_background_run():
    runner = _runner()
    runner.start()
    _join(runner)
    assert runner.results() == OK
    assert runner.last_finished() is not None


def test_run_now_returns_results_directly():
    runner = _runner()
    assert runner.run_now() == OK


def test_results_returns_a_copy():
    runner = _runner()
    runner.run_now()
    got = runner.results()
    got["oura"] = ("tampered", None)
    assert runner.results()["oura"] == (True, None)


def test_per_step_failures_are_reported_not_raised():
    failing = {"oura": (False, "429 quota exceeded"), "garmin": (True, None)}
    runner = _runner(results=failing)
    assert runner.run_now()["oura"] == (False, "429 quota exceeded")
    assert runner.last_error() is None    # the step failed, the run did not


# ─── A blown-up run must not wedge the runner ────────────────────────────────

def test_an_exception_releases_the_lock():
    """The failure mode that would be worst: a raise leaves the lock held
    and no sync ever runs again for the life of the process."""
    runner = _runner(boom=RuntimeError("network gone"))
    runner.start()
    _join(runner)
    assert runner.running is False
    assert runner.start() is True         # still usable
    _join(runner)


def test_an_exception_is_recorded_rather_than_propagated():
    runner = _runner(boom=RuntimeError("network gone"))
    runner.run_now()
    assert "network gone" in runner.last_error()


def test_a_failed_run_keeps_the_previous_good_results():
    """A transient blow-up should not erase the last known state the caption
    is rendered from."""
    runner = BackgroundSyncRunner(_config(), repository_factory=lambda cfg: _FakeRepo(cfg))
    runner.run_now()
    assert runner.results() == OK
    runner._repository_factory = lambda cfg: _FakeRepo(cfg, boom=RuntimeError("nope"))
    runner.run_now()
    assert runner.results() == OK


def test_today_is_passed_through_to_the_chain():
    runner = _runner()
    runner.run_now(today=date(2026, 8, 1))
    assert _FakeRepo.instances[0].calls == [date(2026, 8, 1)]


def test_a_thread_that_fails_to_start_does_not_wedge_the_runner():
    """The worst failure mode available: start() holds the lock, thread
    creation raises, _run_and_release never runs to release it, and the app
    silently never syncs again for the life of the process."""
    runner = _runner()
    original = threading.Thread

    class _Refusing:
        def __init__(self, *a, **kw):
            raise RuntimeError("can't start new thread")

    threading.Thread = _Refusing
    try:
        try:
            runner.start()
        except RuntimeError:
            pass
    finally:
        threading.Thread = original

    assert runner.running is False
    assert runner.start() is True      # still usable
    _join(runner)
    assert runner.results() == OK
