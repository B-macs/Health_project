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

from services.config import load_config
from services.repository import Repository


@st.cache_resource(show_spinner=False)
def get_repository() -> Repository:
    config = load_config(dict(st.secrets))
    return Repository(config)
