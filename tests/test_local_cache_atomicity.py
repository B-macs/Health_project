"""
.sync_state.json is written by TWO threads, and every read-modify-write on it
has to be one atomic step.

THE CONCRETE HAZARD. The background sync thread (services/background_sync.py)
records Oura progress a tab at a time via Repository._mark_oura_tab_synced,
while the Streamlit script thread writes the in-progress training checkpoint —
Repository.save_training_checkpoint_local — into the SAME file on every
weight/reps stepper tap. Both used to be, or sat beside, a `local_cache.read()`
… `local_cache.write(data)` pair, which rewrites the whole file: whichever
thread wrote last silently reverted the other's key. Losing an Oura marker
costs one redundant sync; losing the checkpoint costs the athlete their last
few reps, and does it while the phone is mid-session with no error shown.

The lock is what makes it safe, but only if it is held across the READ, the
COMPUTE and the WRITE together — local_cache.mutate does that, and
local_cache.update does it for the simpler set-a-known-value case. A plain
read()/write() pair releases the lock in between, which is the bug these tests
reproduce.

tests/conftest.py points local_cache._DEFAULT_PATH at a tmp_path per test.
"""

from __future__ import annotations

import ast
import json
import threading
from pathlib import Path

import pytest

from services.clients import local_cache
from services.config import Config
from services.repository import Repository

ROOT = Path(__file__).resolve().parent.parent


def _config() -> Config:
    return Config(
        notion_api_key="ntn_test",
        notion_db_readiness="db-readiness",
        notion_db_training="db-training",
        notion_db_biometrics="db-biometrics",
        notion_db_config="db-config",
        google_sheets_id="sheet-id",
        google_service_account={"type": "service_account"},
    )


# ─── the primitive ───────────────────────────────────────────────────────────

def test_mutate_computes_the_new_value_from_the_old_one():
    local_cache.update({"k": [1, 2]})
    assert local_cache.mutate("k", lambda old: (old or []) + [3]) == [1, 2, 3]
    assert local_cache.read()["k"] == [1, 2, 3]


def test_mutate_sees_none_for_a_missing_key():
    seen = {}
    local_cache.mutate("absent", lambda old: seen.setdefault("old", old) or "new")
    assert seen["old"] is None


def test_mutate_returning_none_deletes_the_key():
    local_cache.update({"k": "v"})
    local_cache.mutate("k", lambda _old: None)
    assert "k" not in local_cache.read()


def test_mutate_leaves_every_other_key_alone():
    """The whole point. A writer of one key must not be able to revert
    another — that is how the training checkpoint was losing reps."""
    local_cache.update({"other": "keep me"})
    local_cache.mutate("mine", lambda _old: "mine")
    data = local_cache.read()
    assert data["other"] == "keep me" and data["mine"] == "mine"


def test_concurrent_mutates_of_one_key_lose_nothing():
    """Twenty threads each appending. Under a read/compute/write that dropped
    the lock, appends interleave and entries vanish."""
    local_cache.update({"log": []})

    def append(i):
        local_cache.mutate("log", lambda old: (old or []) + [i])

    threads = [threading.Thread(target=append, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(local_cache.read()["log"]) == list(range(20))


def test_a_checkpoint_survives_a_concurrent_sync_marker_write():
    """The exact two-thread interleaving from the docstring, against the real
    Repository methods rather than a mock of them."""
    repo = Repository(_config())
    stop = threading.Event()
    lost: list[str] = []

    def sync_thread():
        i = 0
        while not stop.is_set():
            repo._mark_oura_tab_synced("2026-08-10", f"tab{i % 4}", i)
            i += 1

    def checkpoint_thread():
        for i in range(60):
            payload = json.dumps({"day_num": 3, "tp_ex_idx": i})
            repo.save_training_checkpoint_local(payload)
            back = repo.get_training_checkpoint_local()
            if back is None:
                lost.append("checkpoint vanished")
            elif json.loads(back)["tp_ex_idx"] != i:
                # An older payload reappearing IS the lost update.
                if json.loads(back)["tp_ex_idx"] < i:
                    lost.append(f"reverted to {json.loads(back)['tp_ex_idx']} at {i}")

    s = threading.Thread(target=sync_thread)
    c = threading.Thread(target=checkpoint_thread)
    s.start()
    c.start()
    c.join()
    stop.set()
    s.join()

    assert not lost, f"the sync thread reverted the training checkpoint: {lost[:5]}"


# ─── nobody reintroduces the pattern ─────────────────────────────────────────

def test_repository_never_pairs_a_cache_read_with_a_whole_file_write():
    """local_cache.write() replaces the ENTIRE file, so pairing it with a
    read() is the lost update by construction. Repository must go through
    update() or mutate(); write() is left in the module for tests and for a
    deliberate wholesale replacement, not for read-modify-write."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "local_cache"
    ]
    assert not offenders, (
        "local_cache.write() in repository.py at lines "
        f"{offenders} — use update() (known value) or mutate() (computed from "
        "the old one); a read()/write() pair reverts whatever another thread "
        "wrote in between"
    )
