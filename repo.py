"""
repo.py — Streamlit-layer bootstrap for the services/ package.

The only place in the app that adapts st.secrets into a services.config.Config
(rule 5 of the refactor: services/ must not read st.secrets directly). Every
page calls get_repository() instead of constructing db.py/sync_sheets.py
clients itself.

st.cache_resource (not cache_data) is the correct Streamlit primitive for a
stateful client object — same one-Repository-per-session behavior as any
other cached resource, and strictly cheaper than db.py's/sync_sheets.py's
prior per-call Client() construction, not a user-visible behavior change.
"""

import streamlit as st

from services import datastore
from services.background_sync import BackgroundSyncRunner
from services.config import load_config
from services.repository import Repository


@st.cache_resource(show_spinner=False)
def get_config():
    """The single adaptation of st.secrets into a Config. Exposed separately
    from get_repository because the background sync runner needs a Config to
    build its OWN Repository per run — see services/background_sync.py for
    why it must not borrow this thread's."""
    return load_config(dict(st.secrets))


# Set by get_repository() when it hydrates the cache, drained by
# pop_cache_hydration_notice(). A module global rather than a return value
# because get_repository's result is what every caller wants, and rather than
# session_state because the hydration happens on whichever session opened the
# process first — see pop_cache_hydration_notice for why it cannot simply be
# rendered where it is produced.
_cache_hydration_notice: str | None = None


@st.cache_resource(show_spinner=False)
def get_repository() -> Repository:
    """The one Repository per process.

    In cache mode this also HYDRATES the local read cache from Supabase when
    it is missing, before anything can read through it. A hosted filesystem is
    typically ephemeral, so a redeploy wipes datastore.db — and an empty
    datastore returns [] rather than raising, which would render as though the
    athlete had never logged anything. Here rather than in Repository because
    it must happen once per process, and @st.cache_resource is what guarantees
    that; it is a no-op in every other mode.

    ⚠ NOTHING IN HERE MAY CALL st.toast (or st.chat_input). A cache-decorated
    function RECORDS the st elements it emits and REPLAYS them on every later
    cache hit, and the replay seeds its DeltaGenerator map with the main and
    sidebar containers only (streamlit/runtime/caching/cached_message_replay.py
    — `returned_dgs` at the top of replay_cached_messages). Toast renders on the
    EVENT container, which is in neither, so the replay raises KeyError and
    Streamlit re-raises it as CacheReplayClosureError. That kills the app at
    app.py's very first line of work, on the SECOND script run and every one
    after — so the first paint looks fine and the first navigation dies. It
    only bites where the hydration actually runs, i.e. on the hosted deploy
    after a redeploy has wiped the disk, which is exactly where it is hardest
    to see. Ordinary elements (st.warning, st.write) replay fine; this is not a
    general ban on drawing from a cached function.
    """
    global _cache_hydration_notice
    config = get_config()
    filled = datastore.ensure_local_cache(config)
    if filled:
        _cache_hydration_notice = (
            f"Rebuilt the local read cache from Supabase ({filled})."
        )
    return Repository(config)


def pop_cache_hydration_notice() -> str | None:
    """The hydration message, once, for the caller to render.

    Returns None every time after the first. The rebuild happens once per
    process, so the notice is worth exactly one showing — and it has to be
    rendered by the caller rather than by get_repository itself, because a
    toast emitted inside a cache-decorated function is replayed on every
    subsequent cache hit and crashes the app (see get_repository's docstring).
    """
    global _cache_hydration_notice
    notice, _cache_hydration_notice = _cache_hydration_notice, None
    return notice


@st.cache_resource(show_spinner=False)
def get_sync_runner() -> BackgroundSyncRunner:
    """Process-wide, so the "one sync at a time" lock and the last run's
    results are actually shared across reruns and sessions.

    st.cache_resource (not cache_data) for the same reason get_repository
    uses it: this is a stateful object with a thread and a lock, not a
    value. It must NOT be recreated per session — two runners would each
    hold their own lock and defeat the one-at-a-time guarantee."""
    return BackgroundSyncRunner(get_config())
