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
        self.started_at = None
        self.finished_at = None
        _FakeRepo.instances.append(self)

    def run_home_syncs(self, today=None, now=None, hours=2):
        self.calls.append(today)
        self.started_at = time.monotonic()
        if self._delay:
            time.sleep(self._delay)
        self.finished_at = time.monotonic()
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
    """The invariant is that two chains never run AT THE SAME TIME — they
    would be two sets of clients writing the same Sheets tabs. run_now waits
    for the in-flight one and then proceeds, so asserting "only one ran" would
    pin the old skip-instead-of-wait behaviour rather than the guarantee.
    Assert the guarantee: no temporal overlap."""
    runner = _runner(delay=0.3)
    runner.start()
    runner.run_now()
    _join(runner)

    ran = [r for r in _FakeRepo.instances if r.started_at is not None]
    assert len(ran) >= 1
    ran.sort(key=lambda r: r.started_at)
    for earlier, later in zip(ran, ran[1:]):
        assert earlier.finished_at <= later.started_at, "two chains overlapped"


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


def test_run_now_waits_for_an_in_flight_run_instead_of_skipping_it():
    """The foreground path exists to WAIT — today's numbers aren't on screen
    yet. Returning the previous run's stale results immediately is the one
    outcome it must not produce."""
    runner = _runner(delay=0.5)
    runner.start()
    t0 = time.time()
    runner.run_now()
    waited = time.time() - t0
    _join(runner)
    assert waited >= 0.4, f"returned after {waited:.2f}s without waiting"


def test_run_now_gives_up_rather_than_hanging_forever(monkeypatch):
    """A worker stuck on a socket must not freeze the page indefinitely —
    none of the HTTP clients are built with an explicit timeout."""
    import services.background_sync as bs
    monkeypatch.setattr(bs, "_FOREGROUND_WAIT_SECONDS", 0.2)
    runner = _runner(delay=1.5)
    runner.start()
    t0 = time.time()
    runner.run_now()
    waited = time.time() - t0
    assert waited < 1.0, f"waited {waited:.2f}s, should have bailed at 0.2s"
    _join(runner)


# ─── exclusive(): manual sync buttons queue behind the automatic chain ──────
#
#  views/insights.py's buttons call Repository.sync_* directly rather than
#  run_home_syncs, so this lock is the only thing that can serialise them
#  against the background chain. Racing corrupts rows rather than merely
#  wasting calls: upsert_row_by_key is find-then-write, so two chains
#  appending the same not-yet-present date give that date two rows.


def test_exclusive_blocks_start_while_held():
    """A manual sync in progress must stop the automatic chain launching on
    top of it — every widget interaction reruns the script and calls start()."""
    runner = _runner()
    with runner.exclusive():
        assert runner.running is True
        assert runner.start() is False
    assert runner.start() is True     # free again the moment the body exits
    _join(runner)


def test_exclusive_waits_for_an_in_flight_background_run():
    """The manual button QUEUES rather than forcing through. It costs nothing
    to wait: every button runs the same work as the automatic step over a
    window at least as wide, so the wider window writes a superset."""
    runner = _runner(delay=0.5)
    runner.start()
    t0 = time.time()
    with runner.exclusive():
        waited = time.time() - t0
    assert waited >= 0.4, f"took the lock after {waited:.2f}s without waiting"
    _join(runner)


def test_exclusive_and_background_run_never_overlap_in_time():
    """The actual guarantee, stated as an invariant rather than a call count:
    no two chains touch the Sheets tabs at the same moment."""
    runner = _runner(delay=0.3)
    manual_window: list[tuple[float, float]] = []

    runner.start()
    with runner.exclusive():
        start = time.monotonic()
        time.sleep(0.1)
        manual_window.append((start, time.monotonic()))
    _join(runner)

    repo_run = _FakeRepo.instances[0]
    m_start, m_end = manual_window[0]
    assert repo_run.finished_at <= m_start or repo_run.started_at >= m_end, (
        "manual sync overlapped the background chain"
    )


def test_exclusive_releases_the_lock_when_the_body_raises():
    """A failing manual sync must not wedge the runner for the life of the
    process — the bug start() had before its try/except."""
    runner = _runner()
    try:
        with runner.exclusive():
            raise ValueError("sync blew up")
    except ValueError:
        pass
    assert runner.running is False
    assert runner.start() is True
    _join(runner)


def test_exclusive_raises_rather_than_running_anyway_on_timeout():
    """Falling through to running anyway is precisely the collision this
    exists to prevent, so a caller that can't get the lock must not proceed."""
    from services.background_sync import SyncBusyError

    runner = _runner(delay=1.0)
    runner.start()
    try:
        with runner.exclusive(timeout=0.1):
            raise AssertionError("body ran despite the lock being held")
    except SyncBusyError as exc:
        assert "still running" in str(exc)
    _join(runner)


def test_exclusive_timeout_zero_is_a_non_blocking_try():
    """views/training.py's Garmin call uses timeout=0: it fires on every
    render, so waiting would block the page — and a busy runner means the
    Home chain is already syncing that exact tab."""
    from services.background_sync import SyncBusyError

    runner = _runner(delay=0.5)
    runner.start()
    t0 = time.time()
    try:
        with runner.exclusive(timeout=0):
            raise AssertionError("body ran despite the lock being held")
    except SyncBusyError:
        pass
    assert time.time() - t0 < 0.2, "timeout=0 should not wait at all"
    _join(runner)

    # ...and still takes the lock normally when nothing is running.
    with runner.exclusive(timeout=0):
        assert runner.running is True


def test_exclusive_does_not_disturb_the_last_background_run_state():
    """results()/last_finished() describe the automatic chain. A manual sync
    runs its own work and must not overwrite that record."""
    runner = _runner()
    runner.start()
    _join(runner)
    before_results, before_finished = runner.results(), runner.last_finished()

    with runner.exclusive():
        pass

    assert runner.results() == before_results
    assert runner.last_finished() == before_finished
