"""
Every row this app writes is also mirrored to Supabase.

WHY A MIRROR AND NOT A CUTOVER. Notion and Sheets are still the system of
record and nothing reads from Postgres — this runs the new write path BESIDE
the old one so the Postgres copy stays current instead of being whatever the
last manual push left behind. Same staging idiom as HRV_GARMIN_HOLD, ACWR
advisory mode and measured-RPE-beside-self-reported: switch on evidence, not
on a date.

WHY BUFFERED. A PostgREST round trip costs ~136 ms regardless of payload
(measured 2026-08-11), so mirroring row-by-row would add minutes to a sync
that writes a week of nights.

THREE FAILURES THIS FILE EXISTS TO PIN, all found by auditing the first
version rather than by running it — none would have raised:

  A. NOTHING WOULD EVER FLUSH what the UI thread wrote. The buffer was
     per-Repository, but services/background_sync.py builds its OWN
     Repository per run (it must — key rule 12), and flush ran only inside
     run_home_syncs. Every Notion write and every manual sync button runs on
     repo.get_repository()'s instance, so those rows had no path to a flush.
     No error, no row. The outbox is now process-wide.

  B. HETEROGENEOUS KEY SETS IN ONE REQUEST. PostgREST requires uniform keys
     across a bulk body. Sheet rows are always full-width so this never bit
     there, but Notion partial updates are not: update_session_note_ai
     carries 4 columns and save_training_exercise ~16, both into
     training_exercises.

  C. A PARTIAL UPSERT CAN INSERT AN ORPHAN. merge-duplicates INSERTs when the
     key is absent, so mirroring an AI note update against a page logged
     before the mirror existed would create a training_exercises row with
     four columns filled and NULL session_id, movement_name and sets — which
     looks like a real logged exercise to anything counting rows. Partial
     updates PATCH instead, which changes nothing when the row is absent.

These tests are pure: the store is a fake, nothing touches the network.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services import supabase_store
from services.config import Config
from services.repository import Repository

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _empty_outbox():
    """The outbox is process-wide by design, so a test that left rows in it
    would leak into the next one."""
    supabase_store.OUTBOX.drain()
    yield
    supabase_store.OUTBOX.drain()


class FakeStore:
    """Records what would have been sent."""

    def __init__(self, fail_on: str | None = None, existing: set | None = None):
        self.upserts: list[tuple[str, list[dict]]] = []
        self.patches: list[tuple[str, str, str, dict]] = []
        self.fail_on = fail_on
        #: primary keys that already exist, for PATCH's 0-or-1 return
        self.existing = existing if existing is not None else set()

    def upsert(self, table, rows):
        if table == self.fail_on:
            raise supabase_store.SupabaseError(f"boom on {table}")
        assert len({frozenset(r) for r in rows}) <= 1, (
            "PostgREST requires uniform keys across a bulk body; this batch "
            "mixes column sets"
        )
        self.upserts.append((table, rows))
        return len(rows)

    def patch(self, table, pk_column, pk_value, row):
        if table == self.fail_on:
            raise supabase_store.SupabaseError(f"boom on {table}")
        self.patches.append((table, pk_column, str(pk_value), row))
        return 1 if str(pk_value) in self.existing else 0


def _repo(supabase=True, store=None) -> Repository:
    repo = Repository(Config(
        notion_api_key="k", notion_db_readiness="a", notion_db_training="b", notion_db_config="d", google_sheets_id="e",
        google_service_account={},
        supabase_url="https://x.supabase.co" if supabase else "",
        supabase_secret_key="secret" if supabase else "",
    ))
    if store is not None:
        repo._supabase_store_obj = store
    repo._ws_headers["Metrics History"] = ["date", "strain", "readiness_score"]
    repo._ws_headers["Garmin Daily"] = ["date", "steps", "resting_hr"]
    return repo


def _outbox_rows(table, mode=supabase_store.UPSERT):
    with supabase_store.OUTBOX._lock:
        return dict(supabase_store.OUTBOX._rows.get((table, mode), {}))


# ─── A: the outbox is process-wide ───────────────────────────────────────

def test_a_row_queued_on_one_repository_is_flushed_by_ANOTHER():
    """THE bug. background_sync builds its own Repository, so a per-instance
    buffer never sent anything the UI thread wrote — every Notion write and
    every manual sync button. Silent: no error, no row."""
    ui = _repo()                       # what repo.get_repository() hands out
    ui._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 7.4, 62])

    store = FakeStore()
    background = _repo(store=store)    # background_sync's own instance
    sent = background.flush_supabase_mirror()

    assert sent == {"metrics_history": 1}, "the UI thread's row was lost"
    assert store.upserts[0][1][0]["strain"] == 7.4


def test_the_outbox_drains_atomically():
    """drain() must take and clear in one step, or a row queued between the
    read and the clear is swept into a batch that has already been sent."""
    repo = _repo()
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 7.4, 62])
    first = supabase_store.OUTBOX.drain()
    assert len(first) == 1
    assert supabase_store.OUTBOX.drain() == {}


def test_the_outbox_is_not_repository_state():
    """A source check, because the whole failure was that it looked fine."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    assert "self._mirror_buffer" not in src, (
        "the mirror buffer is back on the Repository instance — rows written "
        "on the UI thread would never be flushed by the background one"
    )


# ─── queueing ────────────────────────────────────────────────────────────

def test_a_written_row_is_queued_against_its_datastore_table():
    repo = _repo()
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 7.4, 62])
    assert _outbox_rows("metrics_history") == {
        "2026-08-10": {"date": "2026-08-10", "strain": 7.4, "readiness_score": 62}}


def test_the_header_names_the_columns():
    """The sheet's header IS the datastore's column list — already
    load-bearing (services/datastore.py inserts _read_records output straight
    into these tables). A positional list would silently shift every value one
    column left the first time a column was inserted."""
    repo = _repo()
    repo._queue_mirror_row("Garmin Daily", "2026-08-10", ["2026-08-10", 9182, 54])
    assert _outbox_rows("garmin_daily")["2026-08-10"] == {
        "date": "2026-08-10", "steps": 9182, "resting_hr": 54}


def test_rewriting_the_same_key_twice_sends_one_row():
    repo = _repo()
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 1.0, 50])
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 7.4, 62])
    rows = _outbox_rows("metrics_history")
    assert len(rows) == 1 and rows["2026-08-10"]["strain"] == 7.4


def test_nothing_is_queued_when_supabase_is_not_configured():
    repo = _repo(supabase=False)
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 7.4, 62])
    assert supabase_store.OUTBOX.size() == 0
    assert repo.flush_supabase_mirror() == {}


def test_an_unmapped_tab_is_ignored_rather_than_guessed():
    repo = _repo()
    repo._ws_headers["Some New Tab"] = ["date"]
    repo._queue_mirror_row("Some New Tab", "2026-08-10", ["2026-08-10"])
    assert supabase_store.OUTBOX.size() == 0


def test_an_empty_row_is_never_queued():
    """A Notion update whose properties all map to nothing must not queue a
    keyless row — PATCH with an empty body would be a request for nothing."""
    repo = _repo()
    repo.queue_mirror("training_exercises", "ex-1", {})
    assert supabase_store.OUTBOX.size() == 0


# ─── B: uniform column sets per request ──────────────────────────────────

def test_rows_with_different_columns_go_in_separate_requests():
    """PostgREST requires uniform keys across a bulk body. Notion writes to
    one table do not all carry the same columns: an AI note update has 4 and
    a full exercise write has ~16."""
    store = FakeStore()
    repo = _repo(store=store)
    repo.queue_mirror("training_exercises", "ex-1",
                      {"exercise_id": "ex-1", "movement_name": "Squat", "notes": "x"})
    repo.queue_mirror("training_exercises", "ex-2",
                      {"exercise_id": "ex-2", "note_summary": "ok"})

    sent = repo.flush_supabase_mirror()
    assert sent == {"training_exercises": 2}
    assert len(store.upserts) == 2, "two column sets were put in one body"
    # FakeStore.upsert asserts uniformity itself, so reaching here proves it.


def test_rows_with_the_SAME_columns_still_share_one_request():
    store = FakeStore()
    repo = _repo(store=store)
    for d in ("2026-08-08", "2026-08-09", "2026-08-10"):
        repo._queue_mirror_row("Metrics History", d, [d, 7.4, 62])
    repo.flush_supabase_mirror()
    assert len(store.upserts) == 1, "one round trip per column set, not per row"
    assert len(store.upserts[0][1]) == 3


# ─── C: a partial update patches, it does not upsert ─────────────────────

def test_a_partial_update_patches_so_it_cannot_insert_an_orphan():
    """upsert INSERTs when the key is absent. Mirroring an AI note update
    against a page logged before the mirror existed would create a
    training_exercises row with four columns and NULL session_id,
    movement_name and every set — indistinguishable from a real logged
    exercise to anything counting rows."""
    store = FakeStore(existing=set())          # the row does NOT exist
    repo = _repo(store=store)
    repo.queue_mirror("training_exercises", "ex-old",
                      {"note_summary": "ok", "sentiment_score": 0.5},
                      mode=supabase_store.PATCH)

    repo.flush_supabase_mirror()
    assert store.upserts == [], "a partial update was upserted — orphan risk"
    assert store.patches == [
        ("training_exercises", "exercise_id", "ex-old",
         {"note_summary": "ok", "sentiment_score": 0.5})]


def test_a_patch_uses_the_tables_real_primary_key():
    store = FakeStore()
    repo = _repo(store=store)
    repo.queue_mirror("readiness_checkins", "2026-08-10",
                      {"parsed": 1, "parsed_severity": 3.0},
                      mode=supabase_store.PATCH)
    repo.flush_supabase_mirror()
    assert store.patches[0][1] == "date"


def test_patch_and_upsert_for_one_table_do_not_collide():
    """They are separate outbox entries: a full write must not be downgraded
    to a patch, nor a patch promoted to an insert."""
    store = FakeStore()
    repo = _repo(store=store)
    repo.queue_mirror("training_exercises", "ex-1", {"exercise_id": "ex-1", "notes": "a"})
    repo.queue_mirror("training_exercises", "ex-1", {"note_summary": "b"},
                      mode=supabase_store.PATCH)
    repo.flush_supabase_mirror()
    assert len(store.upserts) == 1
    assert len(store.patches) == 1


# ─── the flush ───────────────────────────────────────────────────────────

def test_the_outbox_is_emptied_so_rows_are_not_sent_twice():
    store = FakeStore()
    repo = _repo(store=store)
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 7.4, 62])
    repo.flush_supabase_mirror()
    assert supabase_store.OUTBOX.size() == 0
    assert repo.flush_supabase_mirror() == {}
    assert len(store.upserts) == 1


def test_values_are_coerced_the_same_way_the_full_push_coerces_them():
    """One coercion, both paths. PostgreSQL will not accept "" in a numeric
    column."""
    store = FakeStore()
    repo = _repo(store=store)
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", "", 62])
    repo.flush_supabase_mirror()
    assert store.upserts[0][1][0]["strain"] is None
    assert store.upserts[0][1][0]["date"] == "2026-08-10"


def test_a_failed_flush_never_raises_and_is_recorded():
    store = FakeStore(fail_on="metrics_history")
    repo = _repo(store=store)
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 7.4, 62])
    repo._queue_mirror_row("Garmin Daily", "2026-08-10", ["2026-08-10", 9182, 54])

    sent = repo.flush_supabase_mirror()
    assert sent == {"garmin_daily": 1}, "one table failing stopped the others"
    assert repo.mirror_last_error[0] == "metrics_history"
    assert "boom" in repo.mirror_last_error[1]


def test_a_failed_flush_drops_its_rows_rather_than_growing_forever():
    store = FakeStore(fail_on="metrics_history")
    repo = _repo(store=store)
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 7.4, 62])
    repo.flush_supabase_mirror()
    assert supabase_store.OUTBOX.size() == 0


# ─── the seam holds ──────────────────────────────────────────────────────

def test_every_sheet_row_write_goes_through_the_one_seam():
    """A twelfth direct upsert would write the tab and skip the mirror."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    direct = [n.lineno for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == "upsert_row_by_key"
              and isinstance(n.func.value, ast.Name) and n.func.value.id == "sheets"]
    assert len(direct) == 1, (
        f"sheets.upsert_row_by_key is called directly at lines {direct}; it "
        f"must only be called inside Repository._upsert_sheet_row"
    )
    fn = [n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == "_upsert_sheet_row"][0]
    assert fn.lineno < direct[0] <= (fn.end_lineno or direct[0])


def test_the_flush_runs_at_the_end_of_the_sync_chain_and_is_UNTHROTTLED():
    """Last, so it sends everything the chain wrote in one pass per table —
    and OUTSIDE the six *_if_due steps, which is what keeps the window short.

    app.py runs _run_startup_sync() on EVERY render, which fires a background
    run. The sync steps are individually throttled to 2h and no-op cheaply
    when not due; the flush is not throttled, so a row queued on the UI thread
    reaches Postgres on the next render rather than the next 2-hour cadence.
    Wrapping it in run_sync_if_due would make that window two hours again,
    silently — the rows would still be there, just late."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    body = src.split("def run_home_syncs")[1].split("\n    def ")[0]
    assert "flush_supabase_mirror()" in body
    assert body.index("sleep_fusion") < body.index("flush_supabase_mirror")

    call = [l for l in body.splitlines()
            if "flush_supabase_mirror()" in l and not l.strip().startswith("#")][0]
    assert "if_due" not in call, (
        "the flush is throttled — rows would sit in the outbox for the "
        "throttle window instead of leaving on the next render"
    )


def test_the_mirror_is_write_only_and_nothing_reads_from_postgres():
    """Reads come from Sheets/Notion live, or from the local datastore
    offline — never from Supabase, measured 132x slower than SQLite."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    reads = {"select", "select_all", "select_value", "count"}
    found = [(n.func.attr, n.lineno) for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr in reads
             and isinstance(n.func.value, ast.Attribute)
             and n.func.value.attr in ("_sb", "_supabase_store_obj")]
    assert not found, f"repository.py reads from Supabase at {found}"


# ─── blank -> NULL, the way a rebuild writes it ──────────────────────────

def test_a_blank_text_value_is_queued_as_NULL_not_empty_string():
    """services/datastore.py:135 normalizes a blank to NULL in EVERY column,
    so a mirrored row must too or it disagrees with the row the next full
    rebuild writes — on data neither of them got wrong.

    Measured on the real datastore: every Notion-backed TEXT column uses NULL
    and NEVER '' (training_exercises.notes NULL on 173/194, '' on 0). Yet
    repository.py writes `notion.rich_text(note or "")` on EVERY exercise, so
    preserving '' would put it in a column nothing else ever holds — and
    `IS NULL` would stop matching the rows the mirror wrote."""
    repo = _repo()
    repo.queue_mirror("training_exercises", "ex-1",
                      {"exercise_id": "ex-1", "notes": "", "movement_name": "Squat"})
    row = _outbox_rows("training_exercises")["ex-1"]
    assert row["notes"] is None, "a blank was mirrored as '' where a rebuild writes NULL"
    assert row["movement_name"] == "Squat"


def test_a_blank_sheet_cell_is_queued_as_NULL_too():
    """The same defect existed on the Sheets half: gspread returns '' for a
    blank cell, and the mirror sent it verbatim."""
    repo = _repo()
    repo._ws_headers["Metrics History"] = ["date", "strain", "readiness_score"]
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", "", ""])
    row = _outbox_rows("metrics_history")["2026-08-10"]
    assert row["strain"] is None and row["readiness_score"] is None


def test_a_real_zero_and_a_real_empty_list_survive():
    """Only the EMPTY STRING becomes NULL. 0 is a reading and "[]" is an
    answered question — blanking either would be a different bug."""
    repo = _repo()
    repo.queue_mirror("readiness_checkins", "2026-08-10",
                      {"date": "2026-08-10", "pain_score": 0,
                       "anatomical_locations": "[]", "travel_flag": 0})
    row = _outbox_rows("readiness_checkins")["2026-08-10"]
    assert row["pain_score"] == 0
    assert row["anatomical_locations"] == "[]"
    assert row["travel_flag"] == 0


def test_the_mirror_row_matches_what_a_rebuild_would_write():
    """The property that actually matters, stated directly: for the same
    Notion payload, the mirror and services/datastore.py must produce the
    same row."""
    from services.clients import notion
    from services.clients import notion_reader as nr

    props = {
        "Date": notion.date_prop("2026-08-10"),
        "Note": notion.rich_text(""),          # the blank case
        "Tightness": notion.number(3),
        "Body Areas": notion.multi_select([]),
        "Travel": notion.checkbox(False),
    }
    decoded = supabase_store.blank_to_null(
        nr.row_from_properties(nr.READINESS, props))

    # What datastore.py would store for the same page: get_all_readiness_
    # checkins_raw's shape, then _insert_rows' blank->NULL rule.
    from services.clients.notion import get_property
    page = {"properties": props}
    rebuilt = {
        "date": get_property(page, "Date", "date"),
        "subjective_tightness": get_property(page, "Note", "rich_text"),
        "tightness_score": get_property(page, "Tightness", "number"),
        "anatomical_locations": __import__("json").dumps(
            get_property(page, "Body Areas", "multi_select") or []),
        "travel_flag": 1 if get_property(page, "Travel", "checkbox") else 0,
    }
    rebuilt = {k: (None if v == "" else v) for k, v in rebuilt.items()}

    assert decoded == rebuilt


def test_a_mirror_failure_is_actually_RENDERED_not_just_recorded():
    """The attribute existed for a commit before anything displayed it, which
    made "failures are visible" false. Nothing reads from Postgres, so a
    broken mirror produces no wrong number and no error anywhere in the app —
    it is invisible by construction unless something shows it."""
    src = (ROOT / "views" / "insights.py").read_text(encoding="utf-8")
    assert "mirror_last_error" in src, (
        "no view renders mirror_last_error — a mirror that stopped working "
        "looks exactly like one that is up to date"
    )
    assert "supabase_configured()" in src, (
        "the panel must not claim anything when Supabase is unconfigured"
    )
