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
therefore doesn't reliably throttle at all: repository.py's sync-due checks
read/write this file instead, so "synced within the last 2 hours" survives
both restarts and unrelated cache clears.

Concurrency
-----------
These markers are now written by the BACKGROUND sync thread
(services/background_sync.py) while the Streamlit script thread reads them,
so this module has to be safe against that. Three things make it so:

  * One process-wide RLock, held across the WHOLE read-modify-write in
    update(). An atomic write alone doesn't prevent a lost update — two
    threads read the same snapshot, both write back, one key vanishes.

  * Writes go to a temp file in the same directory and are os.replace()d
    into position, so a reader never observes a truncated file. Plain
    write_text() truncates first, and a reader landing in that window gets
    {} — which reads as "never synced" and triggers exactly the redundant
    sync these markers exist to prevent.

  * read() takes the same lock. That is not paranoia on Windows: os.replace
    FAILS with PermissionError if another handle has the destination open,
    so an unsynchronised reader doesn't just risk a bad read, it breaks the
    WRITER. Both sides additionally retry, which covers a second process
    (a stray `streamlit run`) that this lock cannot reach.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / ".sync_state.json"

# Reentrant so a future nested call can't self-deadlock; nothing nests today.
_LOCK = threading.RLock()

# Cross-PROCESS contention only — within this process the lock above already
# serialises everything. A handful of milliseconds covers the window in which
# Windows reports the file busy.
_RETRIES = 5
_RETRY_SECONDS = 0.01


def read(path: Path | None = None) -> dict:
    # `path` resolves against the module-level _DEFAULT_PATH at call time,
    # not as a bound default argument, so tests can monkeypatch
    # local_cache._DEFAULT_PATH and actually have it take effect — a mutable
    # default (`path: Path = _DEFAULT_PATH`) would capture the original
    # value once at import time and ignore any later monkeypatch.
    path = path or _DEFAULT_PATH
    with _LOCK:
        return _read_unlocked(path)


def update(changes: dict, path: Path | None = None) -> dict:
    """Apply `changes` as ONE atomic read-modify-write. A key mapped to None
    is deleted. Returns the resulting dict.

    Every caller wants "set/clear one key, leave the rest alone". Doing that
    as a separate read() then write() is a lost-update race the moment the
    background sync thread and the script thread both touch a marker.
    """
    path = path or _DEFAULT_PATH
    with _LOCK:
        data = _read_unlocked(path)
        for key, value in changes.items():
            if value is None:
                data.pop(key, None)
            else:
                data[key] = value
        _write_unlocked(data, path)
        return data


def write(data: dict, path: Path | None = None) -> None:
    path = path or _DEFAULT_PATH
    with _LOCK:
        _write_unlocked(data, path)


def _read_unlocked(path: Path) -> dict:
    for attempt in range(_RETRIES):
        try:
            return json.loads(path.read_text())
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            # Only reachable for a genuinely corrupt file now that writes are
            # atomic — a hand-edit, or one left by an older version.
            return {}
        except OSError:
            # Another process replacing the file right now. Reporting {} here
            # would read as "never synced"; retrying is the honest answer.
            if attempt == _RETRIES - 1:
                return {}
            time.sleep(_RETRY_SECONDS)
    return {}


def _write_unlocked(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".sync_state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        _replace_with_retry(tmp, path)
    except BaseException:
        # Never leave a stray temp file behind on a failed write.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _replace_with_retry(tmp: str, path: Path) -> None:
    """os.replace, retried. On Windows it raises PermissionError when any
    other handle has `path` open — including a reader in another process."""
    for attempt in range(_RETRIES):
        try:
            os.replace(tmp, path)
            return
        except OSError:
            if attempt == _RETRIES - 1:
                raise
            time.sleep(_RETRY_SECONDS)
