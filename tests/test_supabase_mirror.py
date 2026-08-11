"""
Every Sheets row this app writes is also mirrored to Supabase.

WHY A MIRROR AND NOT A CUTOVER. Notion and Sheets are still the system of
record and nothing reads from Postgres — this runs the new write path BESIDE
the old one so the Postgres copy stays current instead of being whatever the
last manual push left behind. Same staging idiom as HRV_GARMIN_HOLD, ACWR
advisory mode and measured-RPE-beside-self-reported: switch on evidence, not
on a date.

WHY BUFFERED. A PostgREST round trip costs ~136 ms regardless of payload
(measured 2026-08-11), so mirroring row-by-row would add minutes to a sync
that writes a week of nights. Rows accumulate per table and flush in one
request each.

WHY A SEAM. Eleven call sites wrote rows by upsert-by-key; a mirror bolted
onto each would be eleven obligations to remember. _upsert_sheet_row is the
one path, the same way _ws is for reads and _query is for Notion — and the
source test below fails if a twelfth appears beside it.

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


class FakeStore:
    """Records what would have been sent."""

    def __init__(self, fail_on: str | None = None):
        self.upserts: list[tuple[str, list[dict]]] = []
        self.fail_on = fail_on

    def upsert(self, table, rows):
        if table == self.fail_on:
            raise supabase_store.SupabaseError(f"boom on {table}")
        self.upserts.append((table, rows))
        return len(rows)


def _repo(supabase=True, store=None) -> Repository:
    repo = Repository(Config(
        notion_api_key="k", notion_db_readiness="a", notion_db_training="b",
        notion_db_biometrics="c", notion_db_config="d", google_sheets_id="e",
        google_service_account={},
        supabase_url="https://x.supabase.co" if supabase else "",
        supabase_secret_key="secret" if supabase else "",
    ))
    if store is not None:
        repo._supabase_store_obj = store
    # _ws records headers; do it directly rather than opening a worksheet.
    repo._ws_headers["Metrics History"] = ["date", "strain", "readiness_score"]
    repo._ws_headers["Garmin Daily"] = ["date", "steps", "resting_hr"]
    return repo


# ─── the buffer ──────────────────────────────────────────────────────────

def test_a_written_row_is_queued_against_its_datastore_table():
    repo = _repo()
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 7.4, 62])
    assert repo._mirror_buffer == {
        "metrics_history": {"2026-08-10": {
            "date": "2026-08-10", "strain": 7.4, "readiness_score": 62}}}


def test_the_header_names_the_columns():
    """The sheet's header IS the datastore's column list — already
    load-bearing (services/datastore.py inserts _read_records output straight
    into these tables). A positional list would silently shift every value one
    column left the first time a column was inserted."""
    repo = _repo()
    repo._queue_mirror_row("Garmin Daily", "2026-08-10", ["2026-08-10", 9182, 54])
    row = repo._mirror_buffer["garmin_daily"]["2026-08-10"]
    assert row == {"date": "2026-08-10", "steps": 9182, "resting_hr": 54}


def test_rewriting_the_same_key_twice_sends_one_row():
    """Keyed by primary key, so a sync that touches today twice does not send
    today twice — and the LAST write wins, matching what the tab now holds."""
    repo = _repo()
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 1.0, 50])
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 7.4, 62])
    assert len(repo._mirror_buffer["metrics_history"]) == 1
    assert repo._mirror_buffer["metrics_history"]["2026-08-10"]["strain"] == 7.4


def test_a_short_row_queues_only_the_columns_it_wrote():
    """upsert_row_by_key overwrites just the first len(values) columns, and
    the mirror must not invent the rest — an upsert with a partial column set
    leaves the others alone."""
    repo = _repo()
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 7.4])
    assert repo._mirror_buffer["metrics_history"]["2026-08-10"] == {
        "date": "2026-08-10", "strain": 7.4}


def test_nothing_is_queued_when_supabase_is_not_configured():
    """A checkout without the keys must behave exactly as before, including
    not growing a buffer nobody will ever flush."""
    repo = _repo(supabase=False)
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 7.4, 62])
    assert repo._mirror_buffer == {}
    assert repo.flush_supabase_mirror() == {}


def test_an_unmapped_tab_is_ignored_rather_than_guessed():
    """Only the fourteen tabs with a datastore table are mirrored. Guessing a
    table name would create rows in the wrong place."""
    repo = _repo()
    repo._ws_headers["Some New Tab"] = ["date"]
    repo._queue_mirror_row("Some New Tab", "2026-08-10", ["2026-08-10"])
    assert repo._mirror_buffer == {}


# ─── the flush ───────────────────────────────────────────────────────────

def test_flush_sends_one_request_per_table_not_per_row():
    """The whole reason for buffering: ~136 ms per round trip."""
    store = FakeStore()
    repo = _repo(store=store)
    for d in ("2026-08-08", "2026-08-09", "2026-08-10"):
        repo._queue_mirror_row("Metrics History", d, [d, 7.4, 62])
    repo._queue_mirror_row("Garmin Daily", "2026-08-10", ["2026-08-10", 9182, 54])

    sent = repo.flush_supabase_mirror()
    assert sent == {"metrics_history": 3, "garmin_daily": 1}
    assert len(store.upserts) == 2, "one request per table"


def test_the_buffer_is_emptied_so_rows_are_not_sent_twice():
    store = FakeStore()
    repo = _repo(store=store)
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 7.4, 62])
    repo.flush_supabase_mirror()
    assert repo._mirror_buffer == {}
    assert repo.flush_supabase_mirror() == {}
    assert len(store.upserts) == 1


def test_values_are_coerced_the_same_way_the_full_push_coerces_them():
    """One coercion, used by both paths. A blank cell is "" in a numeric
    column and PostgreSQL will not accept it."""
    store = FakeStore()
    repo = _repo(store=store)
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", "", 62])
    repo.flush_supabase_mirror()
    _table, rows = store.upserts[0]
    assert rows[0]["strain"] is None, "an empty numeric cell was sent as ''"
    assert rows[0]["date"] == "2026-08-10"


def test_a_failed_flush_never_raises_and_is_recorded():
    """The Sheets write it mirrors ALREADY SUCCEEDED and is the system of
    record. Taking a sync down because a replica was unreachable trades a
    working app for a consistent copy nothing reads yet."""
    store = FakeStore(fail_on="metrics_history")
    repo = _repo(store=store)
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 7.4, 62])
    repo._queue_mirror_row("Garmin Daily", "2026-08-10", ["2026-08-10", 9182, 54])

    sent = repo.flush_supabase_mirror()          # must not raise
    assert sent == {"garmin_daily": 1}, "one table failing stopped the others"
    assert repo.mirror_last_error[0] == "metrics_history"
    assert "boom" in repo.mirror_last_error[1]


def test_a_failed_flush_drops_its_rows_rather_than_growing_forever():
    """A Repository lives for a whole Streamlit process. Retrying forever
    would be an unbounded buffer; the full push is the repair path."""
    store = FakeStore(fail_on="metrics_history")
    repo = _repo(store=store)
    repo._queue_mirror_row("Metrics History", "2026-08-10", ["2026-08-10", 7.4, 62])
    repo.flush_supabase_mirror()
    assert repo._mirror_buffer == {}


def test_a_mirror_failure_is_visible_rather_than_silent():
    """A mirror that quietly stopped working looks exactly like one that is up
    to date, which is the failure this attribute exists to prevent."""
    repo = _repo(store=FakeStore())
    assert repo.mirror_last_error is None
    assert hasattr(repo, "mirror_last_error")


# ─── the seam holds ──────────────────────────────────────────────────────

def test_every_row_write_goes_through_the_one_seam():
    """The guard, in the idiom of tests/test_manual_sync_serialised.py and
    test_repository_offline_datastore.py's fourteen-getter check: a twelfth
    direct upsert would write the tab and skip the mirror, and the Postgres
    copy would silently start missing that one kind of row."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    direct = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if (isinstance(f, ast.Attribute) and f.attr == "upsert_row_by_key"
                and isinstance(f.value, ast.Name) and f.value.id == "sheets"):
            direct.append(node.lineno)
    assert len(direct) == 1, (
        f"sheets.upsert_row_by_key is called directly at lines {direct}; it "
        f"must only be called inside Repository._upsert_sheet_row, or that "
        f"row is written to Sheets and never mirrored"
    )
    fn = [n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == "_upsert_sheet_row"][0]
    assert fn.lineno < direct[0] < (fn.end_lineno or direct[0]) + 1, (
        "the one remaining call is not the one inside _upsert_sheet_row"
    )


def test_the_flush_runs_at_the_end_of_the_sync_chain():
    """Last, so it sends everything the chain wrote in one pass per table."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    body = src.split("def run_home_syncs")[1].split("\n    def ")[0]
    assert "flush_supabase_mirror()" in body
    assert body.index("sleep_fusion") < body.index("flush_supabase_mirror")


def test_the_mirror_is_write_only_and_nothing_reads_from_postgres():
    """The staging rule. Reads come from Sheets/Notion live, or from the local
    datastore offline — never from Supabase, which was measured 132x slower
    than SQLite on 2026-08-11 and is not the system of record."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    reads = {"select", "select_all", "select_value", "count"}
    found = []
    for node in ast.walk(ast.parse(src)):
        # Any read call made ON the Supabase client — self._sb.select(...) or
        # self._supabase_store_obj.count(...). Matched structurally, because a
        # substring search for ".select(" also hits notion.select().
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in reads
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr in ("_sb", "_supabase_store_obj")):
            found.append((node.func.attr, node.lineno))
    assert not found, (
        f"repository.py reads from Supabase at {found} — Postgres is a "
        f"mirror, not a read path (measured 132x slower than the local "
        f"datastore on 2026-08-11)"
    )
