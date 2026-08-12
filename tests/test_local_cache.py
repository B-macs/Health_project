"""services/clients/local_cache.py — the read-modify-write store's failure mode.

The file behind this module holds sync throttle markers AND the flexibility
assessments, which have no other copy anywhere. What is pinned here is that a
read it cannot complete never turns into a write that empties it.
"""

from __future__ import annotations

import pytest

from services.clients import local_cache

# ── a failed read must never become an empty file ────────────────────────────

def test_a_corrupt_file_aborts_the_write_instead_of_blanking_it(tmp_path):
    """MEASURED LOSS, 2026-08-12. `.sync_state.json` came back holding five sync
    timestamps and nothing else, and the athlete's first flexibility assessment
    — the only copy — was gone. This store is read-modify-WRITE, so a read that
    returns {} on failure does not degrade, it DELETES: update() writes {} plus
    its own key and drops every key it was not given, atomically, silently."""
    path = tmp_path / "state.json"
    path.write_text('{"flexibility_assessments": [{"taken_on": "2026-08-12"}], ')  # truncated

    with pytest.raises(local_cache.CacheUnreadable):
        local_cache.update({"oura_last_synced": "2026-08-12T10:00:00"}, path=path)
    with pytest.raises(local_cache.CacheUnreadable):
        local_cache.mutate("flexibility_assessments", lambda old: [], path=path)

    # The damaged file is left exactly as found — nothing overwrote it, so the
    # bytes are still there to be recovered by hand.
    assert path.read_text().startswith('{"flexibility_assessments"')


def test_a_missing_file_is_still_just_empty(tmp_path):
    """"No file yet" is a real state and must keep working — the very first
    sync on a fresh checkout writes into nothing."""
    path = tmp_path / "absent.json"
    assert local_cache.read(path=path) == {}
    local_cache.update({"first": 1}, path=path)
    assert local_cache.read(path=path) == {"first": 1}


def test_a_plain_read_still_degrades_rather_than_raising(tmp_path):
    """Only the WRITE paths are strict. A corrupt file must not crash a page
    that merely wants to know whether a sync is due."""
    path = tmp_path / "state.json"
    path.write_text("not json at all")
    assert local_cache.read(path=path) == {}
