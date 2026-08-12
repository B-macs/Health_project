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
        data = _read_unlocked(path, strict=True)
        for key, value in changes.items():
            if value is None:
                data.pop(key, None)
            else:
                data[key] = value
        _write_unlocked(data, path)
        return data


def mutate(key: str, fn, path: Path | None = None):
    """Replace ONE key with fn(old_value), the whole read-modify-write held
    under the lock. Returns the new value. Returning None from `fn` deletes
    the key.

    update() is enough when the new value is already known. This exists for
    the callers that must COMPUTE it from the old one — the Home snapshot
    store, the flexibility assessment list — where `read()`, then compute,
    then `write()` is racy twice over:

      * it rewrites the WHOLE file, so a different key written in between is
        silently reverted. That is the one that bites hardest here, because
        the background sync thread rewrites this file (see
        Repository._mark_oura_tab_synced) while the Streamlit script thread
        writes the in-progress training checkpoint on every stepper tap — the
        sync would drop the athlete's last few reps on the floor.
      * two writers of the SAME key interleave and one update is lost.

    Doing the read, the compute and the write inside one lock acquisition
    closes both. `fn` must not block or re-enter this module: the lock is
    reentrant, but holding it across I/O would stall the other thread.
    """
    path = path or _DEFAULT_PATH
    with _LOCK:
        data = _read_unlocked(path, strict=True)
        new = fn(data.get(key))
        if new is None:
            data.pop(key, None)
        else:
            data[key] = new
        _write_unlocked(data, path)
        return new


def write(data: dict, path: Path | None = None) -> None:
    """Replace the ENTIRE file. Prefer update() or mutate() — this clobbers
    every key it was not given, which is a lost update whenever another thread
    owns a different key in the same file."""
    path = path or _DEFAULT_PATH
    with _LOCK:
        _write_unlocked(data, path)


class CacheUnreadable(Exception):
    """The file exists but could not be read. Distinct from "no file yet"."""


def _read_unlocked(path: Path, strict: bool = False) -> dict:
    """Load the file. `strict` decides what a FAILED read means.

    ⚠ THE STRICT FLAG IS DATA SAFETY, NOT TIDINESS. This is a read-modify-WRITE
    store, so a read that quietly returns {} on failure does not degrade — it
    DELETES. update() would write {} plus its own key, dropping every key it was
    not given, atomically and with no error anywhere.

    That is not hypothetical: on 2026-08-12 this file came back holding five
    sync-timestamp keys and nothing else, and the athlete's first flexibility
    assessment — the only copy, taken that morning — was not in it. A missing
    file is genuinely "nothing synced yet" and still returns {}; a file that
    exists and will not parse is a fault, and callers about to write must fail
    rather than treat it as empty.

    The in-process _LOCK cannot help here. The Streamlit app, the background
    sync thread and any CLI script are separate PROCESSES; only the atomic
    replace guards them, and returning {} on a failed read defeats it.
    """
    for attempt in range(_RETRIES):
        try:
            return json.loads(path.read_text())
        except FileNotFoundError:
            return {}                      # genuinely nothing synced yet
        except json.JSONDecodeError as exc:
            # Reachable for a hand-edit, a file from an older version, or a
            # partially-written one left by a crash.
            if strict:
                raise CacheUnreadable(f"{path} exists but is not valid JSON") from exc
            return {}
        except OSError as exc:
            # Another process replacing the file right now.
            if attempt == _RETRIES - 1:
                if strict:
                    raise CacheUnreadable(f"{path} could not be read") from exc
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
