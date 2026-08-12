"""
CACHE MODE — reads served locally, writes going live, cache written through.

The third mode, and the one hosting needs. Until now there were two, and they
were mutually exclusive:

    datastore_path unset   reads live (~8,884 ms)   writes live
    datastore_path set     reads local (32 ms)      writes RAISE

A hosted server wants the left column of row two and the right column of row
one. clients/datastore_reader.py's docstring calls that combination "worse
still" than either, and it is right ABOUT A SNAPSHOT: log a session, and the
next page reads a cache that has never heard of it — so strain, ACWR and
tomorrow's prescription are computed from data that is already wrong, with no
error and entirely plausible numbers.

Cache mode is safe because the cache is WRITTEN THROUGH, not merely refreshed.
Every write lands in the local copy synchronously, in the same call as the
backend write, so it cannot be behind for a value this app wrote. That is the
property this file exists to pin, and the round-trip test at the bottom is the
one that actually proves it: write through Repository, read back through
Repository, require the new value.

The write-through applies the SAME rows the Supabase mirror sends, through the
same three modes. SQLite's ON CONFLICT DO UPDATE has PostgREST's
merge-duplicates semantics — a partial upsert leaves unnamed columns alone —
which is what lets one row description serve both sinks.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from services import datastore, supabase_store
from services.clients import datastore_writer
from services.clients.datastore_reader import DatastoreReadOnlyError
from services.config import Config
from services.repository import Repository

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = (ROOT / "services" / "datastore_schema.sql").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _empty_outbox():
    supabase_store.OUTBOX.drain()
    yield
    supabase_store.OUTBOX.drain()


@pytest.fixture
def cache_db(tmp_path):
    path = tmp_path / "cache.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return str(path)


def _config(path, mode, **extra):
    return Config(
        notion_api_key="k", notion_db_readiness="db-readiness",
        notion_db_training="db-training", notion_db_config="db-config",
        google_sheets_id="e", google_service_account={},
        datastore_path=path, datastore_mode=mode, **extra)


def _repo(path, mode="cache", **extra):
    return Repository(_config(path, mode, **extra))


# ─── the modes are distinct and backward-compatible ──────────────────────

def test_the_default_mode_is_the_old_read_only_behaviour(cache_db):
    """Every existing checkout, script and test sets datastore_path and
    nothing else. They must keep refusing writes exactly as before."""
    repo = _repo(cache_db, mode="readonly")
    assert repo.offline is True
    assert repo.cached is False
    assert repo.local_datastore is True
    with pytest.raises(DatastoreReadOnlyError):
        _ = repo._nc


def test_cache_mode_reads_locally_but_does_not_refuse_writes(cache_db):
    repo = _repo(cache_db)
    assert repo.offline is False, "cache mode must not refuse writes"
    assert repo.cached is True
    assert repo.local_datastore is True, "reads still come from the datastore"


def test_no_datastore_means_neither_mode(cache_db):
    repo = Repository(Config(
        notion_api_key="k", notion_db_readiness="a", notion_db_training="b",
        notion_db_config="d", google_sheets_id="e", google_service_account={}))
    assert (repo.offline, repo.cached, repo.local_datastore) == (False, False, False)


# ─── write-through ───────────────────────────────────────────────────────

def _rows(path, table):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
    finally:
        conn.close()


def test_a_written_row_lands_in_the_local_cache_immediately(cache_db):
    repo = _repo(cache_db)
    repo.queue_mirror("metrics_history", "2026-08-12",
                      {"date": "2026-08-12", "strain": 7.4, "readiness_score": 62})
    rows = _rows(cache_db, "metrics_history")
    assert rows == [{"date": "2026-08-12", "readiness_score": 62.0,
                     "sleep_pct": None, "sleep_score": None, "strain": 7.4}]


def test_writing_the_same_key_twice_updates_rather_than_duplicating(cache_db):
    repo = _repo(cache_db)
    repo.queue_mirror("metrics_history", "2026-08-12", {"date": "2026-08-12", "strain": 1.0})
    repo.queue_mirror("metrics_history", "2026-08-12", {"date": "2026-08-12", "strain": 7.4})
    rows = _rows(cache_db, "metrics_history")
    assert len(rows) == 1 and rows[0]["strain"] == 7.4


def test_a_partial_write_does_not_blank_the_columns_it_omits(cache_db):
    """The local twin of the orphan hazard. INSERT OR REPLACE would wipe
    every column the row did not name — so an AI note update carrying four
    columns would erase the session, the movement and the sets."""
    repo = _repo(cache_db)
    repo.queue_mirror("metrics_history", "2026-08-12",
                      {"date": "2026-08-12", "strain": 7.4, "readiness_score": 62,
                       "sleep_score": 80})
    repo.queue_mirror("metrics_history", "2026-08-12",
                      {"date": "2026-08-12", "strain": 9.9})
    row = _rows(cache_db, "metrics_history")[0]
    assert row["strain"] == 9.9
    assert row["readiness_score"] == 62.0, "an unnamed column was blanked"
    assert row["sleep_score"] == 80.0


def test_a_patch_updates_an_existing_row(cache_db):
    repo = _repo(cache_db)
    repo.queue_mirror("readiness_checkins", "2026-08-12",
                      {"date": "2026-08-12", "tightness_score": 3.0})
    repo.queue_mirror("readiness_checkins", "2026-08-12",
                      {"parsed": 1, "parsed_severity": 4.0},
                      mode=supabase_store.PATCH)
    row = _rows(cache_db, "readiness_checkins")[0]
    assert row["parsed"] == 1 and row["parsed_severity"] == 4.0
    assert row["tightness_score"] == 3.0, "the patch overwrote untouched columns"


def test_a_patch_against_a_missing_row_inserts_nothing(cache_db):
    """Same contract as PATCH against Postgres: it must never invent a row
    out of the handful of columns an update happened to carry."""
    repo = _repo(cache_db)
    repo.queue_mirror("readiness_checkins", "1999-01-01",
                      {"parsed": 1}, mode=supabase_store.PATCH)
    assert _rows(cache_db, "readiness_checkins") == []


def test_child_rows_are_replaced_not_appended(cache_db):
    repo = _repo(cache_db)
    sets = [{"exercise_id": "ex-1", "set_num": 1, "reps": 10, "weight": 20.0,
             "rest": 90, "tut": 0, "velocity": "controlled",
             "band_tier": None, "ts": None},
            {"exercise_id": "ex-1", "set_num": 2, "reps": 9, "weight": 20.0,
             "rest": 90, "tut": 0, "velocity": "controlled",
             "band_tier": None, "ts": None}]
    repo.queue_mirror("training_sets", "ex-1", sets, mode=supabase_store.REPLACE)
    assert len(_rows(cache_db, "training_sets")) == 2
    repo.queue_mirror("training_sets", "ex-1", sets[:1], mode=supabase_store.REPLACE)
    remaining = _rows(cache_db, "training_sets")
    assert len(remaining) == 1, "re-logging duplicated instead of replacing"
    assert remaining[0]["set_num"] == 1


def test_an_empty_child_list_still_clears_the_old_rows(cache_db):
    repo = _repo(cache_db)
    repo.queue_mirror("training_sets", "ex-1", [
        {"exercise_id": "ex-1", "set_num": 1, "reps": 10, "weight": 20.0,
         "rest": 90, "tut": 0, "velocity": "controlled", "band_tier": None, "ts": None}],
        mode=supabase_store.REPLACE)
    repo.queue_mirror("training_sets", "ex-1", [], mode=supabase_store.REPLACE)
    assert _rows(cache_db, "training_sets") == []


def test_blank_becomes_null_in_the_cache_too(cache_db):
    """The cache must hold the row a rebuild would write, or the two copies
    disagree on data neither got wrong."""
    repo = _repo(cache_db)
    repo.queue_mirror("training_exercises", "ex-1",
                      {"exercise_id": "ex-1", "movement_name": "Squat", "notes": ""})
    assert _rows(cache_db, "training_exercises")[0]["notes"] is None


def test_nothing_is_written_through_in_readonly_mode(cache_db):
    repo = _repo(cache_db, mode="readonly")
    repo.queue_mirror("metrics_history", "2026-08-12", {"date": "2026-08-12", "strain": 7.4})
    assert _rows(cache_db, "metrics_history") == []


def test_a_failed_cache_write_RAISES_unlike_a_failed_mirror(cache_db):
    """Deliberately different from flush_supabase_mirror, which swallows. A
    mirror falling behind leaves a replica stale; a cache falling behind
    leaves the thing the app READS FROM disagreeing with the system of
    record, and the next page renders a number that is quietly wrong."""
    repo = _repo(cache_db)
    conn = sqlite3.connect(cache_db)
    conn.execute("DROP TABLE metrics_history")
    conn.commit()
    conn.close()
    with pytest.raises(datastore_writer.DatastoreWriteError, match="local datastore"):
        repo.queue_mirror("metrics_history", "2026-08-12",
                          {"date": "2026-08-12", "strain": 7.4})


# ─── the property that makes cache mode safe ─────────────────────────────

def test_a_write_is_visible_to_the_very_next_READ(cache_db):
    """THE test. Everything else is machinery; this is the guarantee.

    Written through Repository's own write seam, read back through
    Repository's own getter. If this fails, cache mode is the stale-snapshot
    hazard that offline mode refuses writes to avoid.
    """
    repo = _repo(cache_db)
    assert repo.get_metrics_history() == []

    repo._ws_headers["Metrics History"] = [
        "date", "readiness_score", "sleep_pct", "sleep_score", "strain"]
    repo._queue_mirror_row("Metrics History", "2026-08-12",
                           ["2026-08-12", 62, 90, 80, 7.4])

    got = repo.get_metrics_history()
    assert len(got) == 1, "the write was not visible to the next read"
    assert got[0]["date"] == "2026-08-12"
    assert got[0]["strain"] == 7.4


def test_a_notion_write_is_visible_to_the_very_next_read(cache_db):
    """Same guarantee through the Notion seam, which fans one page into three
    tables — the path most likely to lose a row on the way."""
    from services.clients import notion
    from services.clients import notion_reader as nr

    repo = _repo(cache_db)
    props = {
        "Movement": notion.title("Goblet Squat"),
        "Session Date": notion.date_prop("2026-08-12"),
        "Session ID": notion.rich_text("2026-08-12-abc"),
        "Type": notion.select("Squat"),
        "Sets": notion.rich_text("[]"),
        "Session Duration": notion.number(61),
        "Session RPE": notion.number(5),
        "Session AU": notion.number(305),
    }
    sets = [{"set_num": 1, "reps": 10, "weight": 20.0, "rest": 90, "tut": 0,
             "velocity": "controlled"}]
    repo.mirror_notion_write(nr.TRAINING, "ex-1", props, sets=sets)

    sessions = repo.get_recent_sessions(days=30, today=__import__("datetime").date(2026, 9, 1))
    assert len(sessions) == 1, "the logged exercise was not readable back"
    s = sessions[0]
    assert s.session_date == "2026-08-12" and s.session_au == 305.0
    assert [e.name for e in s.exercises] == ["Goblet Squat"]
    assert s.exercises[0].actual_sets == 1
    assert s.exercises[0].total_volume_kg == 200.0


# ─── hydration ───────────────────────────────────────────────────────────

class _FakeStore:
    def select_all(self, table):
        return [{"date": "2026-08-12", "strain": 7.4}] if table == "metrics_history" else []


def test_hydration_is_a_no_op_outside_cache_mode(tmp_path):
    cfg = _config(str(tmp_path / "nope.db"), "readonly",
                  supabase_url="https://x", supabase_secret_key="k")
    assert datastore.ensure_local_cache(cfg) is None
    assert not (tmp_path / "nope.db").exists()


def test_hydration_leaves_an_existing_cache_alone(cache_db, monkeypatch):
    """A present cache may hold rows this process just wrote through.
    Replacing it silently would throw them away."""
    called = []
    monkeypatch.setattr(supabase_store, "pull",
                        lambda *a, **k: called.append(1))
    cfg = _config(cache_db, "cache", supabase_url="https://x",
                  supabase_secret_key="k")
    assert datastore.ensure_local_cache(cfg) is None
    assert called == [], "an existing cache was rebuilt"


def test_hydration_refuses_without_supabase_credentials(tmp_path):
    """Cache mode rebuilds FROM Supabase. Without it a cold start would serve
    reads from an empty database — which returns [] rather than raising, so
    the app would render as though nothing had ever been logged."""
    cfg = _config(str(tmp_path / "c.db"), "cache")
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        datastore.ensure_local_cache(cfg)


def test_hydration_fills_a_missing_cache_from_supabase(tmp_path, monkeypatch):
    path = tmp_path / "cold.db"
    monkeypatch.setattr(
        supabase_store, "SupabaseStore", lambda url, key: _FakeStore())
    cfg = _config(str(path), "cache", supabase_url="https://x",
                  supabase_secret_key="k")

    assert datastore.ensure_local_cache(cfg) == str(path)
    assert path.exists()
    assert _rows(str(path), "metrics_history")[0]["strain"] == 7.4


def test_a_failed_hydration_leaves_no_half_filled_cache(tmp_path, monkeypatch):
    """os.replace only after success, the same contract build_datastore.py
    has — a partly-filled cache reads as real data."""
    path = tmp_path / "cold.db"
    monkeypatch.setattr(supabase_store, "SupabaseStore", lambda url, key: _FakeStore())
    monkeypatch.setattr(supabase_store, "pull",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    cfg = _config(str(path), "cache", supabase_url="https://x",
                  supabase_secret_key="k")
    with pytest.raises(RuntimeError, match="boom"):
        datastore.ensure_local_cache(cfg)
    assert not path.exists()
    assert not list(tmp_path.glob("*.hydrating")), "a temp file was left behind"


def test_the_bootstrap_hydrates_before_handing_back_a_repository():
    """It has to happen before anything can read through the cache, and once
    per process — which is what @st.cache_resource guarantees."""
    src = (ROOT / "repo.py").read_text(encoding="utf-8")
    body = src.split("def get_repository")[1].split("\ndef ")[0]
    assert "ensure_local_cache" in body
    assert body.index("ensure_local_cache") < body.index("return Repository")


def test_hydration_names_an_unwritable_path_as_a_setting_not_a_crash(tmp_path, monkeypatch):
    """The most likely hosting misconfiguration. Left to fail on its own it
    surfaces as an OSError from tempfile in the middle of a page render, which
    reads like a bug in the app rather than a setting on the server."""
    monkeypatch.setattr("os.access", lambda p, mode: False)
    cfg = _config(str(tmp_path / "c.db"), "cache",
                  supabase_url="https://x", supabase_secret_key="k")
    with pytest.raises(RuntimeError, match="WRITABLE"):
        datastore.ensure_local_cache(cfg)
