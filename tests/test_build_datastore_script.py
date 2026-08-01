"""
Tests for scripts/build_datastore.py's build() -- the temp-file +
atomic-replace safety net layered on top of services.datastore.rebuild()
(see that module's docstring for why the swap lives here and not inside
rebuild() itself). This is the first script in scripts/ to get pytest
coverage; the others (backfill_garmin_from_sheet1.py,
merge_duplicate_checkins.py) are validated by a manual dry-run instead,
same as this one was before being wired into the real Notion/Sheets data --
but the atomic-swap-on-failure guarantee here is new, safety-relevant logic
worth locking in with a real test rather than just a one-time manual check.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts.build_datastore import build
from tests.test_datastore import _StubRepository


def test_build_writes_a_fresh_file_and_no_leftover_tmp(tmp_path):
    db_path = tmp_path / "datastore.db"
    stub = _StubRepository(garmin_daily=[{"date": "2026-07-31", "steps": 8000}])

    counts = build(stub, db_path)

    assert db_path.exists()
    assert counts["garmin_daily"] == 1
    assert not (tmp_path / "datastore.db.tmp").exists()


def test_build_failure_leaves_a_pre_existing_good_file_untouched(tmp_path):
    db_path = tmp_path / "datastore.db"
    good_stub = _StubRepository(garmin_daily=[{"date": "2026-07-31", "steps": 8000}])
    build(good_stub, db_path)
    good_mtime = db_path.stat().st_mtime_ns
    good_bytes = db_path.read_bytes()

    failing_stub = _StubRepository(fail_on="get_metrics_history")
    with pytest.raises(RuntimeError, match="simulated failure"):
        build(failing_stub, db_path)

    assert db_path.stat().st_mtime_ns == good_mtime
    assert db_path.read_bytes() == good_bytes
    assert not (tmp_path / "datastore.db.tmp").exists()

    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT steps FROM garmin_daily").fetchone()[0] == 8000


def test_build_failure_with_no_pre_existing_file_leaves_nothing_behind(tmp_path):
    db_path = tmp_path / "datastore.db"
    failing_stub = _StubRepository(fail_on="get_metrics_history")

    with pytest.raises(RuntimeError, match="simulated failure"):
        build(failing_stub, db_path)

    assert not db_path.exists()
    assert not (tmp_path / "datastore.db.tmp").exists()
