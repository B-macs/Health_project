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
    return Repository(get_config())


@st.cache_resource(show_spinner=False)
def get_sync_runner() -> BackgroundSyncRunner:
    """Process-wide, so the "one sync at a time" lock and the last run's
    results are actually shared across reruns and sessions.

    st.cache_resource (not cache_data) for the same reason get_repository
    uses it: this is a stateful object with a thread and a lock, not a
    value. It must NOT be recreated per session — two runners would each
    hold their own lock and defeat the one-at-a-time guarantee."""
    return BackgroundSyncRunner(get_config())
