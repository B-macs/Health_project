"""SUPABASE AS THE SYSTEM OF RECORD (2026-10-09).

The athlete: "Can we work towards disconnecting Notion completely and relying
only on Supabase". Two repairs in three weeks had come from Notion and
Supabase disagreeing: a save reached Notion, its Supabase copy waited in a
queue, a restart lost the queue, and the hosted app — whose local copy is
rebuilt from Supabase — then showed a week of training as one day.

In this mode there is one store. These tests pin what makes it safe:

  * every write goes to Supabase FIRST and is waited for; the local copy is
    written only after Supabase accepted it, so the copy can never hold a row
    Supabase does not;
  * Notion and Google Sheets are never called — the clients refuse;
  * the few reads that must not start from a stale copy read Supabase itself;
  * the local copy is rebuilt from Supabase once per process, every process;
  * nothing is queued, so nothing can be lost in a queue.

Pure: the store is a fake that keeps its own tables. No network.
"""
from __future__ import annotations

import dataclasses
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path

import pytest

from services import record_cache, reconcile, repository as repository_mod, supabase_store
from services import switchover
from services.clients import notion_reader, sheets
from services.config import Config, load_config
from services.models import CheckInRecord
from services.repository import LegacyStoreDisconnectedError, Repository

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = (ROOT / "services" / "datastore_schema.sql").read_text(encoding="utf-8")


class FakeStore:
    """PostgREST, reduced to what the repository calls, over plain lists."""

    def __init__(self, tables: dict | None = None, fail_on=None):
        self.tables = {t: [dict(r) for r in rows] for t, rows in (tables or {}).items()}
        self.log: list[tuple] = []
        self.fail_on = fail_on

    def _check(self, op, table):
        if self.fail_on in ((op, table), table):
            raise supabase_store.SupabaseError(f"boom on {op} {table}")

    def upsert(self, table, rows):
        self._check("upsert", table)
        self.log.append(("upsert", table, len(rows)))
        pk = supabase_store.primary_key(table)
        current = {str(r[pk]): r for r in self.tables.get(table, [])}
        for r in rows:
            current[str(r[pk])] = {**current.get(str(r[pk]), {}), **r}
        self.tables[table] = list(current.values())
        return len(rows)

    def patch(self, table, pk, key, row):
        self._check("patch", table)
        self.log.append(("patch", table, str(key)))
        n = 0
        for r in self.tables.get(table, []):
            if str(r.get(pk)) == str(key):
                r.update(row)
                n += 1
        return n

    def delete_where(self, table, column, value):
        self._check("delete", table)
        self.log.append(("delete", table, str(value)))
        self.tables[table] = [r for r in self.tables.get(table, [])
                              if str(r.get(column)) != str(value)]

    def insert(self, table, rows):
        self._check("insert", table)
        self.log.append(("insert", table, len(rows)))
        self.tables.setdefault(table, []).extend(dict(r) for r in rows)
        return len(rows)

    def select_all(self, table, order=""):
        return [dict(r) for r in self.tables.get(table, [])]

    def select_value(self, table, where, column):
        col, _, value = where.partition("=eq.")
        for r in self.tables.get(table, []):
            if str(r.get(col)) == value:
                return r.get(column)
        return None


@pytest.fixture(autouse=True)
def _empty_outbox():
    supabase_store.OUTBOX.drain()
    yield
    supabase_store.OUTBOX.drain()


@pytest.fixture
def local_copy(tmp_path):
    path = tmp_path / "record_cache.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    record_cache.mark_hydrated(str(path))
    yield str(path)
    record_cache.forget(str(path))


def _record_config(path: str) -> Config:
    return Config(
        notion_api_key="", notion_db_readiness="record:readiness",
        notion_db_training="record:training", notion_db_config="record:config",
        google_sheets_id="", google_service_account={},
        datastore_path=path, datastore_mode="cache",
        supabase_url="https://x.supabase.co", supabase_secret_key="k",
        system_of_record="supabase")


def _repo(path: str, store: FakeStore) -> Repository:
    repo = Repository(_record_config(path))
    repo._supabase_store_obj = store
    return repo


def _local(path: str, sql: str, *args) -> list[tuple]:
    conn = sqlite3.connect(path)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _check_in(day="2026-10-09", pain=2.0, note="") -> CheckInRecord:
    return CheckInRecord(date=day, current_condition="Good", tightness_score=3.0,
                         pain_score=pain, subjective_tightness=note)


# ─── the mode ────────────────────────────────────────────────────────────

def test_the_mode_is_on_only_with_supabase_as_the_record(local_copy):
    assert _repo(local_copy, FakeStore()).supabase_record is True
    legacy = Repository(Config(
        notion_api_key="k", notion_db_readiness="a", notion_db_training="b",
        notion_db_config="d", google_sheets_id="e", google_service_account={},
        datastore_path=local_copy, datastore_mode="cache"))
    assert legacy.supabase_record is False


def test_notion_and_sheets_are_never_called(local_copy):
    repo = _repo(local_copy, FakeStore())
    with pytest.raises(LegacyStoreDisconnectedError):
        repo._nc
    with pytest.raises(LegacyStoreDisconnectedError):
        repo._sc


def test_nothing_is_queued_so_nothing_can_be_lost_in_a_queue(local_copy):
    repo = _repo(local_copy, FakeStore())
    repo.save_check_in(_check_in())
    repo.set_config("phases", "[]")
    assert supabase_store.OUTBOX.size() == 0


# ─── writes: Supabase first, then the local copy ─────────────────────────

def test_a_check_in_goes_to_supabase_then_to_the_local_copy(local_copy):
    store = FakeStore()
    repo = _repo(local_copy, store)
    repo.save_check_in(_check_in(pain=2.0))
    assert store.log == [("upsert", "readiness_checkins", 1)]
    row = store.tables["readiness_checkins"][0]
    assert row["date"] == "2026-10-09" and row["pain_score"] == 2.0 and row["parsed"] == 0
    assert _local(local_copy, "SELECT pain_score FROM readiness_checkins") == [(2.0,)]


def test_a_second_check_in_the_same_day_keeps_the_first_ones_values(local_copy):
    store = FakeStore()
    repo = _repo(local_copy, store)
    repo.save_check_in(_check_in(pain=4.0))
    repo.save_check_in(CheckInRecord(date="2026-10-09", current_condition="Excellent",
                                     tightness_score=0, pain_score=0,
                                     meditation_minutes=10))
    row = store.tables["readiness_checkins"][0]
    assert row["pain_score"] == 4.0, "an untouched default overwrote a real reading"
    assert row["meditation_minutes"] == 10
    assert len(store.tables["readiness_checkins"]) == 1


def test_an_edited_check_in_stores_exactly_what_the_form_shows(local_copy):
    """Fault F3 (2026-10-19): the form opens the day's entry filled in, so its
    save is the whole day, and a value equal to a default is a real answer."""
    store = FakeStore()
    repo = _repo(local_copy, store)
    repo.save_check_in(_check_in(pain=4.0, note="sore"))
    edited = repo.get_check_in("2026-10-09")
    assert edited.pain_score == 4.0 and edited.subjective_tightness == "sore"
    repo.save_check_in(dataclasses.replace(edited, pain_score=0, tightness_score=0),
                       replace=True)
    row = store.tables["readiness_checkins"][0]
    assert row["pain_score"] == 0 and row["tightness_score"] == 0
    assert row["subjective_tightness"] == "sore", "an unchanged field kept its value"
    assert _local(local_copy, "SELECT pain_score FROM readiness_checkins") == [(0.0,)]
    assert len(store.tables["readiness_checkins"]) == 1


def test_a_day_without_a_check_in_reads_back_as_none(local_copy):
    assert _repo(local_copy, FakeStore()).get_check_in("2026-10-09") is None


def test_a_failed_supabase_write_raises_and_leaves_the_local_copy_untouched(local_copy):
    """The whole point: the copy must never hold what Supabase does not."""
    repo = _repo(local_copy, FakeStore(fail_on="readiness_checkins"))
    with pytest.raises(supabase_store.SupabaseError):
        repo.save_check_in(_check_in())
    assert _local(local_copy, "SELECT COUNT(*) FROM readiness_checkins") == [(0,)]


def _save_exercise(repo, sid="2026-10-09-abcd1234", name="Goblet Squat"):
    return repo.save_training_exercise(
        session_id=sid, movement_name=name, movement_type="Squat Pattern",
        planned_sets=3, planned_reps=10, rpe=None,
        sets=[{"set_num": 1, "reps": 10, "weight": 22.5, "rest": 90, "tut": 0,
               "velocity": "controlled"},
              {"set_num": 2, "reps": 10, "weight": 22.5, "rest": 90, "tut": 0,
               "velocity": "controlled"}],
        note="", session_date="2026-10-09", session_duration_minutes=50,
        session_rpe=6, session_au=300.0)


def test_a_training_save_writes_three_tables_and_mints_the_exercise_id(local_copy):
    store = FakeStore()
    repo = _repo(local_copy, store)
    exercise_id = _save_exercise(repo)
    uuid.UUID(exercise_id)                      # Notion used to issue this
    assert [r["session_id"] for r in store.tables["training_sessions"]] == ["2026-10-09-abcd1234"]
    assert [r["exercise_id"] for r in store.tables["training_exercises"]] == [exercise_id]
    assert len(store.tables["training_sets"]) == 2
    assert _local(local_copy, "SELECT COUNT(*) FROM training_sets WHERE exercise_id = ?",
                  exercise_id) == [(2,)]
    # and the local copy reads it back as a logged session
    assert repo.get_logged_session_dates(date(2026, 10, 9), date(2026, 10, 9)) == {"2026-10-09"}


def test_a_save_that_fails_at_its_sets_removes_its_exercise_again(local_copy):
    """The Save button's retry writes the exercise afresh under a new id; a
    set-less row left behind by the failed attempt would be a duplicate."""
    store = FakeStore(fail_on=("insert", "training_sets"))
    repo = _repo(local_copy, store)
    with pytest.raises(supabase_store.SupabaseError):
        _save_exercise(repo)
    assert store.tables.get("training_exercises", []) == []
    assert _local(local_copy, "SELECT COUNT(*) FROM training_exercises") == [(0,)]


def test_session_notes_append_to_the_exercise(local_copy):
    store = FakeStore()
    repo = _repo(local_copy, store)
    exercise_id = _save_exercise(repo)
    repo.save_session_notes(exercise_id, "hip felt fine")
    repo.save_session_notes(exercise_id, "left side slower")
    assert store.tables["training_exercises"][0]["notes"] == "hip felt fine\n\nleft side slower"


def test_config_is_upserted_and_read_back_at_once(local_copy):
    store = FakeStore()
    repo = _repo(local_copy, store)
    repo.set_config("phases", "[]", today=date(2026, 10, 9))
    assert store.tables["config"] == [{"key": "phases", "value": "[]", "updated": "2026-10-09"}]
    assert repo.get_config_value("phases") == "[]"


def test_device_rows_skip_sheets_and_a_rewrite_is_one_request(local_copy):
    store = FakeStore()
    repo = _repo(local_copy, store)
    header = repository_mod._METRICS_HISTORY_HEADER
    ws = repo._ws(sheets.METRICS_HISTORY_WORKSHEET, header)

    def row(d, strain):
        values = [""] * len(header)
        values[header.index("date")] = d
        values[header.index("strain")] = strain
        return values

    repo._upsert_sheet_row(ws, "2026-10-09", row("2026-10-09", 9.1))
    repo._rewrite_sheet(ws, header, [row(f"2026-10-0{i}", i) for i in range(1, 4)])
    assert store.log == [("upsert", "metrics_history", 1), ("upsert", "metrics_history", 3)]
    assert _local(local_copy, "SELECT COUNT(*) FROM metrics_history") == [(4,)]


def test_the_ai_parse_patches_the_check_in_by_its_date(local_copy):
    store = FakeStore()
    repo = _repo(local_copy, store)
    repo.save_check_in(_check_in())
    repo.update_readiness_ai(notion_reader.ID_PREFIX + "readiness:2026-10-09",
                             severity=2.0, body_parts=["hip"], sensation_type=["tight"],
                             warning_level="monitor")
    row = store.tables["readiness_checkins"][0]
    assert row["parsed"] == 1 and row["parsed_severity"] == 2.0
    assert ("patch", "readiness_checkins", "2026-10-09") in store.log


# ─── reads from the record itself ────────────────────────────────────────

def test_the_live_reads_come_from_supabase_not_from_the_local_copy(local_copy):
    """A script, or a second machine, can write Supabase after this process
    built its copy. The readers that write a verdict back must see that."""
    store = FakeStore({
        "config": [{"key": "phases", "value": "[]", "updated": "2026-10-09"}],
        "training_sessions": [{"session_id": "2026-10-08-x", "session_date": "2026-10-08"}],
        "training_exercises": [{"exercise_id": "e1", "session_id": "2026-10-08-x",
                                "session_date": "2026-10-08", "movement_name": "Yoga Flow",
                                "movement_type": "Yoga"}],
    })
    repo = _repo(local_copy, store)
    assert repo.get_config_value("phases") is None          # local copy: empty
    assert repo.get_phases_live() == []                      # Supabase: present, empty list
    assert repo.get_logged_session_dates_live(date(2026, 10, 5), date(2026, 10, 11)) == {"2026-10-08"}
    assert set(repo.get_supplementary_sessions_live(date(2026, 10, 8), "Yoga")) == {"2026-10-08-x"}


def test_duplicate_check_ins_cannot_exist_in_the_record(local_copy):
    assert _repo(local_copy, FakeStore()).find_duplicate_check_in_dates() == {}


def test_two_databases_sharing_one_id_refuse_rather_than_misroute(tmp_path):
    cfg = Config(notion_api_key="", notion_db_readiness="", notion_db_training="",
                 notion_db_config="", google_sheets_id="", google_service_account={})
    with pytest.raises(KeyError):
        Repository(cfg)._db_kind("")


# ─── deletes and the switch marker ───────────────────────────────────────

def test_deleting_training_rows_goes_children_first(local_copy):
    store = FakeStore()
    repo = _repo(local_copy, store)
    exercise_id = _save_exercise(repo)
    store.log.clear()
    repo.delete_training_rows([exercise_id], ["2026-10-09-abcd1234"])
    assert [op[1] for op in store.log] == ["training_sets", "training_exercises", "training_sessions"]
    assert _local(local_copy, "SELECT COUNT(*) FROM training_exercises") == [(0,)]


def test_the_switch_marker_is_written_once(local_copy):
    store = FakeStore()
    repo = _repo(local_copy, store)
    stamp = repo.mark_record_since(datetime(2026, 10, 9, 12, 0))
    assert stamp == "2026-10-09T12:00:00"
    assert repo.mark_record_since(datetime(2026, 10, 10, 9, 0)) is None
    assert record_cache.record_since(store) == "2026-10-09T12:00:00"


def test_only_the_hosted_app_writes_the_switch_marker():
    """A local script run before the push must not set it, or the reconcile
    would refuse the very run that prepares the switch."""
    src = (ROOT / "repo.py").read_text(encoding="utf-8")
    assert "switchover.finish" in src
    for script in (ROOT / "scripts").glob("*.py"):
        text = script.read_text(encoding="utf-8")
        assert "mark_record_since(" not in text and "switchover.finish(" not in text, script.name


# ─── the local copy is rebuilt from Supabase, once per process ───────────

def test_the_copy_is_rebuilt_even_when_a_file_is_there(tmp_path):
    path = tmp_path / "datastore.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE stale (x)")
    old.commit()
    old.close()
    (tmp_path / "datastore.db-wal").write_bytes(b"old log")
    store = FakeStore({"config": [{"key": "phases", "value": "[]", "updated": "2026-10-09"}]})
    cfg = _record_config(str(path))
    try:
        assert record_cache.hydrate_once(cfg, store_factory=lambda url, key: store) == str(path)
        assert record_cache.hydrate_once(cfg, store_factory=lambda url, key: store) is None
    finally:
        record_cache.forget(str(path))
    assert not (tmp_path / "datastore.db-wal").exists(), "an old write-ahead log was left"
    conn = sqlite3.connect(path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "stale" not in tables
    assert conn.execute("SELECT value FROM config WHERE key='phases'").fetchone() == ("[]",)
    conn.close()


# ─── configuration ───────────────────────────────────────────────────────

_ENV_KEYS = ("NOTION_API_KEY", "NOTION_DB_READINESS", "NOTION_DB_TRAINING",
             "NOTION_DB_CONFIG", "GOOGLE_SHEETS_ID", "GOOGLE_SERVICE_ACCOUNT_JSON",
             "SUPABASE_URL", "SUPABASE_SECRET_KEY", "HEALTH_SYSTEM_OF_RECORD",
             "HEALTH_DATASTORE_PATH", "HEALTH_DATASTORE_MODE")


@pytest.fixture
def clean_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


_SUPABASE = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SECRET_KEY": "k"}


def test_supabase_is_the_default_record_once_it_is_configured(clean_env):
    cfg = load_config(dict(_SUPABASE))
    assert cfg.system_of_record == "supabase"
    assert cfg.datastore_mode == "cache" and cfg.datastore_path
    assert len({cfg.notion_db_readiness, cfg.notion_db_training, cfg.notion_db_config}) == 3


def test_the_hosted_settings_become_the_record_mode(clean_env):
    cfg = load_config({**_SUPABASE, "HEALTH_DATASTORE_PATH": "datastore.db",
                       "HEALTH_DATASTORE_MODE": "cache"})
    assert record_cache.is_supabase_record(cfg)
    assert cfg.datastore_path == "datastore.db"


def test_the_offline_snapshot_still_means_offline(clean_env):
    cfg = load_config({**_SUPABASE, "HEALTH_DATASTORE_PATH": "datastore.db"})
    assert cfg.datastore_mode == "readonly"
    assert not record_cache.is_supabase_record(cfg)


def test_notion_can_still_be_named_for_the_migration_tools(clean_env):
    with pytest.raises(EnvironmentError):     # and then it needs its keys
        load_config({**_SUPABASE, "HEALTH_SYSTEM_OF_RECORD": "notion"})


def test_supabase_as_the_record_needs_supabase(clean_env):
    with pytest.raises(EnvironmentError):
        load_config({"HEALTH_SYSTEM_OF_RECORD": "supabase"})
    with pytest.raises(EnvironmentError):
        load_config({**_SUPABASE, "HEALTH_SYSTEM_OF_RECORD": "sheets"})


# ─── the reconcile that runs before the switch ───────────────────────────

def test_values_are_compared_as_values_not_as_representations():
    assert reconcile.same_value(371, 371.0)
    assert reconcile.same_value("", None)
    assert reconcile.same_value("TRUE", 1)
    assert reconcile.same_value('["hip", "back"]', '["hip","back"]')
    assert not reconcile.same_value(5.0, 6.0)
    assert not reconcile.same_value("4412", "4411")


def _db(rows_by_table: dict) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    for table, rows in rows_by_table.items():
        for r in rows:
            cols = ", ".join(r)
            conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({', '.join('?' * len(r))})",
                         tuple(r.values()))
    conn.commit()
    return conn


def test_the_reconcile_finds_missing_extra_and_different_rows_and_fixes_them():
    source = _db({
        "training_sessions": [{"session_id": "s1", "session_date": "2026-10-06"}],
        "training_exercises": [{"exercise_id": "e1", "session_id": "s1",
                                "session_date": "2026-10-06", "movement_name": "RDL"}],
        "training_sets": [{"exercise_id": "e1", "set_num": 1, "reps": 10, "weight": 40}],
        "metrics_history": [{"date": "2026-10-05", "strain": 12.0}],
    })
    target = _db({
        "training_sessions": [{"session_id": "dup", "session_date": "2026-10-05"}],
        "training_exercises": [{"exercise_id": "dupe", "session_id": "dup",
                                "session_date": "2026-10-05", "movement_name": "Yoga"}],
        "training_sets": [{"exercise_id": "dupe", "set_num": 1, "reps": 1, "weight": 0}],
        "metrics_history": [{"date": "2026-10-05", "strain": 21.0}],
    })
    diffs = {d.table: d for d in reconcile.diff_all(source, target)}
    assert diffs["training_exercises"].missing == ["e1"]
    assert diffs["training_exercises"].extra == ["dupe"]
    assert diffs["metrics_history"].different == ["2026-10-05"]
    assert diffs["training_sets"].missing == ["e1"] and diffs["training_sets"].extra == ["dupe"]

    store = FakeStore({t: [dict(r) for r in target.execute(f"SELECT * FROM {t}").fetchall()]
                       for t in ()})
    reconcile.apply(store, source, list(diffs.values()))
    deletes = [op[1] for op in store.log if op[0] == "delete"]
    assert deletes.index("training_sets") < deletes.index("training_exercises") \
        < deletes.index("training_sessions"), "children must go before parents"
    writes = [op[1] for op in store.log if op[0] in ("upsert", "insert")]
    assert writes.index("training_sessions") < writes.index("training_exercises") \
        < writes.index("training_sets"), "parents must go before children"
    assert {"date": "2026-10-05", "strain": 12.0}.items() <= store.tables["metrics_history"][0].items()


# ─── the tools that could overwrite the record ───────────────────────────

@pytest.mark.parametrize("script", ["push_datastore_to_supabase.py",
                                    "pull_datastore_from_supabase.py"])
def test_a_wholesale_push_refuses_with_supabase_as_the_record(script):
    src = (ROOT / "scripts" / script).read_text(encoding="utf-8")
    assert "system_of_record" in src and "--overwrite-record" in src and "REFUSED" in src


@pytest.mark.parametrize("script", ["reconcile_supabase.py", "backfill_mirror_sessions.py",
                                    "prune_mirror_sessions.py"])
def test_the_notion_to_supabase_tools_stop_at_the_switch(script):
    src = (ROOT / "scripts" / script).read_text(encoding="utf-8")
    assert "record_since(" in src and "REFUSED" in src
    assert '"HEALTH_SYSTEM_OF_RECORD": "notion"' in src, (
        "the tool must name Notion explicitly: the default is Supabase")


# ─── the one-time switch at the hosted app's first start ─────────────────

def _finish(local_copy, store, archive, now):
    return switchover.finish(_record_config(local_copy), now=now,
                             read_legacy=lambda cfg: archive,
                             record_factory=lambda cfg: _repo(local_copy, store))


def test_the_switch_marks_first_then_copies_only_what_supabase_lacks(local_copy):
    store = FakeStore()
    _repo(local_copy, store).save_check_in(_check_in(day="2026-10-08", pain=1.0))
    archive = _db({
        "readiness_checkins": [{"date": "2026-10-08", "pain_score": 5.0},
                               {"date": "2026-10-06", "pain_score": 3.0}],
        "config": [{"key": "phases", "value": "[]", "updated": "2026-10-05"}],
    })
    copied = _finish(local_copy, store, archive, datetime(2026, 10, 10, 7, 0))
    assert copied["readiness_checkins"] == 1 and copied["config"] == 1
    rows = {r["date"]: r for r in store.tables["readiness_checkins"]}
    assert rows["2026-10-08"]["pain_score"] == 1.0, "a newer Supabase value was overwritten"
    assert rows["2026-10-06"]["pain_score"] == 3.0
    assert _local(local_copy, "SELECT pain_score FROM readiness_checkins "
                              "WHERE date = '2026-10-06'") == [(3.0,)]
    assert record_cache.record_since(store) == "2026-10-10T07:00:00"
    # A second start copies nothing and leaves the switch time alone.
    assert _finish(local_copy, store, archive, datetime(2026, 10, 11, 7, 0)) == {}
    assert record_cache.record_since(store) == "2026-10-10T07:00:00"


def test_the_switch_never_deletes_a_row_the_archive_lacks(local_copy):
    store = FakeStore()
    exercise_id = _save_exercise(_repo(local_copy, store))
    _finish(local_copy, store, _db({}), datetime(2026, 10, 10, 7, 0))
    assert [r["exercise_id"] for r in store.tables["training_exercises"]] == [exercise_id]


def test_a_failed_catch_up_keeps_the_switch_time_and_runs_again(local_copy):
    store = FakeStore()

    def unreadable(cfg):
        raise RuntimeError("Sheets quota")

    assert switchover.finish(_record_config(local_copy), now=datetime(2026, 10, 10, 7, 0),
                             read_legacy=unreadable,
                             record_factory=lambda cfg: _repo(local_copy, store)) == {}
    assert record_cache.record_since(store) == "2026-10-10T07:00:00"
    assert store.select_value("config", f"key=eq.{switchover.CATCH_UP_KEY}", "value") is None


def test_the_switch_does_nothing_with_notion_as_the_record():
    cfg = Config(notion_api_key="k", notion_db_readiness="a", notion_db_training="b",
                 notion_db_config="d", google_sheets_id="e", google_service_account={})
    assert switchover.finish(cfg) == {}


def test_add_only_fills_blanks_adds_missing_and_never_overwrites_or_deletes():
    source = _db({
        "training_sessions": [{"session_id": "s1", "session_date": "2026-10-06"}],
        "training_exercises": [{"exercise_id": "e1", "session_id": "s1",
                                "session_date": "2026-10-06", "movement_name": "RDL",
                                "notes": "felt good"}],
        "readiness_checkins": [{"date": "2026-10-06", "pain_score": 2.0}],
        "metrics_history": [{"date": "2026-10-05", "strain": 12.0}],
    })
    target = _db({
        "training_sessions": [{"session_id": "s1", "session_date": "2026-10-06"}],
        "training_exercises": [{"exercise_id": "e1", "session_id": "s1",
                                "session_date": "2026-10-06", "movement_name": "RDL",
                                "notes": None}],
        "metrics_history": [{"date": "2026-10-05", "strain": 21.0},
                            {"date": "1999-12-31", "strain": 1.0}],
    })
    diffs = reconcile.diff_all(source, target)
    fills = reconcile.blank_fills(source, target, diffs)
    assert fills == {"training_exercises": {"e1": {"exercise_id": "e1", "notes": "felt good"}}}
    store = FakeStore()
    reconcile.apply_additions(store, source, diffs, fills)
    assert not [op for op in store.log if op[0] == "delete"], "add-only deleted a row"
    assert ("upsert", "metrics_history", 1) not in store.log, "a non-blank value was overwritten"
    assert ("upsert", "readiness_checkins", 1) in store.log
    assert store.tables["training_exercises"] == [{"exercise_id": "e1", "notes": "felt good"}]


def test_the_switch_fills_a_note_supabase_lost(local_copy):
    store = FakeStore()
    exercise_id = _save_exercise(_repo(local_copy, store))
    archive = _db({
        "training_sessions": [{"session_id": "2026-10-09-abcd1234", "session_date": "2026-10-09"}],
        "training_exercises": [{"exercise_id": exercise_id, "session_id": "2026-10-09-abcd1234",
                                "session_date": "2026-10-09", "movement_name": "Goblet Squat",
                                "notes": "hip felt fine"}],
    })
    copied = _finish(local_copy, store, archive, datetime(2026, 10, 10, 7, 0))
    assert copied == {"training_exercises (blanks filled)": 1}
    assert store.tables["training_exercises"][0]["notes"] == "hip felt fine"
    assert _local(local_copy, "SELECT notes FROM training_exercises") == [("hip felt fine",)]
