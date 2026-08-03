"""
services/background_sync.py — runs Repository.run_home_syncs off the request
thread, so opening the app never waits on the device APIs.

Why this exists
---------------
app.py already renders before syncing, so the numbers reach the screen fast.
But the sync still ran inline afterwards, which keeps the Streamlit script
busy for as long as it takes (~50s for Oura, ~27s for Garmin on a cold run).
Streamlit serialises everything in a session behind the running script, so
during that window a nav tap does nothing — the page looks finished and
responds to nothing. Moving the chain to a worker thread makes the session
free the moment the page is painted.

The two rules that make this safe
---------------------------------
1. The worker builds its OWN Repository from the Config, and never touches
   the one the UI thread uses. That matters more than it looks: a Repository
   owns a gspread client (a requests.Session underneath), a Notion client, a
   Garmin session, and two mutable caches (_ws_cache, _read_cache). None of
   that is documented thread-safe, and the UI thread is reading through it
   the whole time the sync would be writing through it. Cloning per run costs
   one client construction against a multi-second network job.

2. Exactly one sync at a time, enforced by one lock that all three entry
   points take. start() takes it non-blocking — a rerun happens on every
   widget interaction, so it is called constantly, and without this a slow
   sync would accumulate a thread per click; returning False means "already
   running", a normal outcome rather than an error. run_now() and
   exclusive() both WAIT for it instead, because their callers (the first
   open of the day, and the manual sync buttons) have explicitly asked for
   the work and would be wrong to skip it.

   exclusive() is what keeps views/insights.py's manual buttons out of the
   automatic chain's way even though they call Repository.sync_* directly
   rather than run_home_syncs — see its docstring for the concrete
   corruption that serialising prevents.

Nothing here imports Streamlit (CLAUDE.md rule 10) and nothing here touches
st.session_state — a worker thread has no ScriptRunContext, so writing
Streamlit state from it is undefined. Results are kept on this object and
read by whichever script run asks next.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import date, datetime

from services.config import Config
from services.repository import Repository

# How long the foreground path will wait for an already-running background
# sync before giving up and rendering with what it has. Generous, because the
# full chain legitimately takes ~77s on a cold run and waiting is the whole
# point of that path — but finite, because a worker stuck on a socket must
# not be able to freeze the page forever.
_FOREGROUND_WAIT_SECONDS = 120.0


class SyncBusyError(RuntimeError):
    """A manual sync could not get the one-at-a-time lock in time.

    Deliberately an error rather than a silent fall-through to running
    anyway: running anyway is precisely the collision exclusive() exists to
    prevent, so a caller that cannot get the lock must not proceed.
    """


class BackgroundSyncRunner:
    """One per process (repo.py holds it in st.cache_resource)."""

    def __init__(self, config: Config, repository_factory=None):
        self._config = config
        # Injectable purely so tests can supply a fake Repository without a
        # network stack; production always gets the real constructor.
        self._repository_factory = repository_factory or Repository
        self._lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._results: dict[str, tuple[bool, str | None]] = {}
        self._last_finished: datetime | None = None
        self._last_error: str | None = None
        self._thread: threading.Thread | None = None

    # ── state, readable from the UI thread at any time ──────────────────

    @property
    def running(self) -> bool:
        return self._lock.locked()

    def results(self) -> dict[str, tuple[bool, str | None]]:
        """The most recent completed run's per-step (ok, error). Empty until
        one has finished. A copy, so a caller can't mutate shared state."""
        with self._state_lock:
            return dict(self._results)

    def last_finished(self) -> datetime | None:
        with self._state_lock:
            return self._last_finished

    def last_error(self) -> str | None:
        """Set only when the run itself blew up, as opposed to an individual
        step reporting (False, msg) — those live in results()."""
        with self._state_lock:
            return self._last_error

    # ── running ─────────────────────────────────────────────────────────

    def run_now(self, today: date | None = None) -> dict[str, tuple[bool, str | None]]:
        """Run the chain synchronously on the calling thread and return its
        results. Used for the foreground path — the first open of the day,
        when the numbers aren't on screen yet and there is nothing to be
        gained by not waiting. Takes the same one-at-a-time lock, so it can
        never overlap a worker that is already going.
        """
        # WAIT for an in-flight run rather than skipping it. Skipping broke
        # the guarantee this method exists for: the caller takes this path
        # precisely because today's numbers aren't on screen yet, so
        # returning the previous run's stale results immediately is the one
        # outcome it must not produce. An in-flight worker is already doing
        # the work being waited for, so joining it is also the cheap answer.
        #
        # Bounded, because a worker blocked on a socket would otherwise
        # freeze the page indefinitely — gspread, garminconnect and
        # notion-client are all built here without an explicit HTTP timeout,
        # so "hung forever" is reachable. On timeout we fall back to the old
        # behaviour and let the page render with what we have.
        if not self._lock.acquire(timeout=_FOREGROUND_WAIT_SECONDS):
            return self.results()
        try:
            return self._execute(today)
        finally:
            self._lock.release()

    @contextmanager
    def exclusive(self, timeout: float = _FOREGROUND_WAIT_SECONDS):
        """Hold the one-at-a-time lock while the caller runs its own sync work.

        For the manual sync buttons in views/insights.py, which call
        Repository.sync_* directly rather than going through run_home_syncs.
        They run the SAME work as the automatic chain, only over a wider
        window — blend days=400 vs 7, sleep fusion 1200 vs 14, Garmin daily
        7 vs 2, and an identical days=7 for Oura. Same source APIs, same
        date-keyed upsert, same skip-unchanged comparison, so serialising
        them against the automatic chain loses no data: the wider window
        writes a superset of the rows the narrower one would.

        What racing WOULD lose is row integrity.
        sheets.upsert_row_by_key is a find-then-write pair, two round-trips
        with a gap. Two chains upserting a date that is not on the tab yet
        both find nothing and both append, so that date ends up with two
        rows and get_all_records hands the engine whichever comes first.
        The date most likely to be missing is today's — exactly the one both
        chains are writing. Sheets' 60-operations-per-minute quota is the
        second reason: two concurrent chains roughly double an already
        bursty write, and a 429 mid-chain reads as missing data, not as an
        error.

        Raises SyncBusyError if the lock cannot be taken within `timeout`.
        Releases the lock however the body exits, so a failing manual sync
        cannot wedge the runner (the bug start() had).
        """
        if not self._lock.acquire(timeout=timeout):
            raise SyncBusyError(
                f"an automatic background sync is still running (waited "
                f"{timeout:.0f}s) — try again in a moment"
            )
        try:
            yield
        finally:
            self._lock.release()

    def start(self, today: date | None = None) -> bool:
        """Kick the chain off on a daemon thread. True if this call started
        one, False if a run was already in flight (normal — every widget
        interaction reruns the script and calls this again).

        Daemon so a sync in progress can never keep the process alive at
        shutdown; the work is all idempotent and durably throttled, so the
        worst case of being killed mid-run is that the next open retries.
        """
        if not self._lock.acquire(blocking=False):
            return False
        try:
            thread = threading.Thread(
                target=self._run_and_release,
                args=(today,),
                name="health-home-sync",
                daemon=True,
            )
            with self._state_lock:
                self._thread = thread
            thread.start()
        except BaseException:
            # Thread creation can fail (RuntimeError at interpreter shutdown,
            # or the OS refusing a thread). The lock is only released by
            # _run_and_release, which now never runs — so without this the
            # runner is wedged for the life of the process and the app never
            # syncs again. Release before re-raising.
            self._lock.release()
            raise
        return True

    def _run_and_release(self, today: date | None) -> None:
        try:
            self._execute(today)
        finally:
            self._lock.release()

    def _execute(self, today: date | None) -> dict[str, tuple[bool, str | None]]:
        """Assumes the lock is held. Never raises: a background failure has
        no user to surface itself to, and must not kill the thread silently
        holding state in an unknown shape."""
        results: dict[str, tuple[bool, str | None]] = {}
        error: str | None = None
        try:
            repository = self._repository_factory(self._config)
            results = repository.run_home_syncs(today=today)
        except Exception as exc:
            error = str(exc)
        with self._state_lock:
            if results:
                self._results = results
            self._last_error = error
            self._last_finished = datetime.now()
        return results
