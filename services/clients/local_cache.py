"""
services/clients/local_cache.py — tiny local JSON key/value store.

Generic read/write of a dict to a JSON file on local disk — same spirit as
clients/sheets.py and clients/notion.py being generic I/O primitives, with
the actual keys/meaning living in repository.py.

Why this exists: Streamlit's st.cache_data is an in-memory, per-process
cache. It resets on every process restart, and — more importantly — gets
wiped by any unrelated st.cache_data.clear() call anywhere in the app (e.g.
views/checkin.py clears it after every check-in save to refresh Home's
readiness score). A sync throttle built only on st.cache_data's TTL
therefore doesn't reliably throttle at all: repository.py's Oura sync-due
check reads/writes this file instead, so "synced within the last 2 hours"
survives both restarts and unrelated cache clears.
"""

from __future__ import annotations

import json
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / ".sync_state.json"


def read(path: Path | None = None) -> dict:
    # `path` resolves against the module-level _DEFAULT_PATH at call time,
    # not as a bound default argument, so tests can monkeypatch
    # local_cache._DEFAULT_PATH and actually have it take effect — a mutable
    # default (`path: Path = _DEFAULT_PATH`) would capture the original
    # value once at import time and ignore any later monkeypatch.
    path = path or _DEFAULT_PATH
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write(data: dict, path: Path | None = None) -> None:
    path = path or _DEFAULT_PATH
    path.write_text(json.dumps(data, indent=2))
