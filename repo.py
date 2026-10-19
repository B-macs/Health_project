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

import threading

import streamlit as st

from services import datastore
from services import switchover
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
    config = get_config()
    # With Supabase as the record the copy is rebuilt at EVERY process start,
    # so there is no notice to show; the "Rebuilt the local read cache" toast
    # of the legacy cache mode was dropped 2026-10-19 (inventory H3).
    datastore.ensure_local_cache(config)
    repository = Repository(config)
    # The switch to Supabase as the only store — the marker, then the one-time
    # add-only catch-up from Notion and Sheets (services/switchover.py). Only
    # under a Streamlit server: a test that imported app.py wrote the marker
    # on 2026-10-09. On its own thread with its own Repository (key rule 12),
    # so the first open never waits for a read of Notion and Sheets; after the
    # first successful run it costs one config read per process.
    if st.runtime.exists() and repository.supabase_record:
        threading.Thread(target=switchover.finish, args=(config,),
                         name="switchover", daemon=True).start()
    return repository


@st.cache_resource(show_spinner=False)
def get_sync_runner() -> BackgroundSyncRunner:
    """Process-wide, so the "one sync at a time" lock and the last run's
    results are actually shared across reruns and sessions.

    st.cache_resource (not cache_data) for the same reason get_repository
    uses it: this is a stateful object with a thread and a lock, not a
    value. It must NOT be recreated per session — two runners would each
    hold their own lock and defeat the one-at-a-time guarantee."""
    return BackgroundSyncRunner(get_config())
