"""
The three write paths that were deliberately left unmirrored, now mirrored.

They were left out because a full push repaired them. That stops being true
the moment Notion and Sheets stop being written — there is no longer anything
to push FROM — so they have to land BEFORE any cutover, not after. That is the
whole reason this file exists now rather than later.

  WHOLE-TAB REWRITES  rebuild_tab, sync_sleep_fusion and rebuild_oura_tabs
                      replace a tab in one shot. Safe as plain upserts ONLY
                      because every one of them MERGES — each carries the
                      existing rows through and applies fresh over them, so
                      the result is always a superset and no row disappears. A
                      rewrite that could SHRINK a tab would need
                      delete-then-insert, the way training_sets does.

  APPEND BATCH        sync_oura_all's append path, same shape.

  apply_check_in_merge  could not name its own row: _CHECKIN_FIELD_MAP has no
                      "Date" entry, and readiness_checkins is keyed BY date.
                      merge_check_in_group now writes the Date back
                      explicitly, which is a no-op in Notion (every page in
                      the group already holds that exact value — it is what
                      they were grouped on) and makes the merged property set
                      self-identifying.

  CLI SCRIPTS         five of them write mirrored tables and then simply exit,
                      never running a sync chain. An atexit hook flushes once
                      per process, so the sixth script does not have to
                      remember.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services import supabase_store
from services.clients import notion
from services.clients import notion_reader as nr
from services.config import Config
from services.repository import Repository

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _empty_outbox():
    supabase_store.OUTBOX.drain()
    yield
    supabase_store.OUTBOX.drain()


class FakeWorksheet:
    def __init__(self, title):
        self.title = title


def _repo() -> Repository:
    return Repository(Config(
        notion_api_key="k", notion_db_readiness="a", notion_db_training="b", notion_db_config="d", google_sheets_id="e",
        google_service_account={},
        supabase_url="https://x.supabase.co", supabase_secret_key="secret",
    ))


def _rows(table, mode=supabase_store.UPSERT):
    with supabase_store.OUTBOX._lock:
        return dict(supabase_store.OUTBOX._rows.get((table, mode), {}))


# ─── whole-tab rewrites ──────────────────────────────────────────────────

def test_a_rewritten_tab_queues_every_row():
    repo = _repo()
    header = ["date", "readiness_score", "sleep_pct", "sleep_score", "strain"]
    rows = [["2026-08-08", 62, 90, 80, 7.4],
            ["2026-08-09", 66, 91, 82, 5.1],
            ["2026-08-10", 70, 88, 79, 6.0]]
    repo._queue_mirror_rows(FakeWorksheet("Metrics History"), header, rows)

    queued = _rows("metrics_history")
    assert set(queued) == {"2026-08-08", "2026-08-09", "2026-08-10"}
    assert queued["2026-08-10"]["strain"] == 6.0


def test_the_first_column_is_the_key():
    """Every tab in _DATASTORE_TABLE_BY_TAB is keyed on its first column —
    the same assumption upsert_row_by_key's key_col=1 already makes at all
    eleven row-at-a-time sites."""
    repo = _repo()
    repo._queue_mirror_rows(FakeWorksheet("Garmin Daily"),
                            ["date", "steps"], [["2026-08-10", 9182]])
    assert list(_rows("garmin_daily")) == ["2026-08-10"]


def test_a_column_the_datastore_does_not_have_is_dropped_not_sent():
    """rebuild_oura_tabs rewrites against the tab's OWN header, which can
    have drifted from the datastore's columns. PostgREST rejects the WHOLE
    batch on one unknown key, so a single drifted column would take out every
    row. Filtering matches services/datastore.py::_insert_rows, which selects
    the table's columns and ignores the rest."""
    repo = _repo()
    header = ["date", "steps", "a_column_the_sheet_gained_first"]
    repo._queue_mirror_rows(FakeWorksheet("Garmin Daily"), header,
                            [["2026-08-10", 9182, "surprise"]])
    row = _rows("garmin_daily")["2026-08-10"]
    assert "a_column_the_sheet_gained_first" not in row
    assert row == {"date": "2026-08-10", "steps": 9182}


def test_blank_cells_in_a_rewrite_become_null():
    repo = _repo()
    repo._queue_mirror_rows(FakeWorksheet("Metrics History"),
                            ["date", "strain"], [["2026-08-10", ""]])
    assert _rows("metrics_history")["2026-08-10"]["strain"] is None


def test_an_unmapped_tab_queues_nothing():
    repo = _repo()
    repo._queue_mirror_rows(FakeWorksheet("Sheet1"), ["date"], [["2026-08-10"]])
    assert supabase_store.OUTBOX.size() == 0


def test_an_empty_rewrite_queues_nothing():
    repo = _repo()
    repo._queue_mirror_rows(FakeWorksheet("Metrics History"), ["date"], [])
    assert supabase_store.OUTBOX.size() == 0


# ─── the merged check-in can now name its own row ────────────────────────

def test_the_merged_properties_carry_the_date():
    """Without it the mirror cannot name the row it just rewrote —
    readiness_checkins is keyed by date and _CHECKIN_FIELD_MAP has no entry
    for it."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    body = src.split("def merge_check_in_group")[1].split("\n    def ")[0]
    assert 'properties["Date"] = notion.date_prop(merged_date)' in body


def test_the_merged_row_is_patched_not_upserted():
    """It writes 18 of 24 columns and must not reset the AI-parser ones."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    body = src.split("def apply_check_in_merge")[1].split("\n    def ")[0]
    assert "mirror_notion_write" in body
    assert "supabase_store.PATCH" in body
    assert body.index("notion.update_page") < body.index("mirror_notion_write")


def test_archiving_a_duplicate_needs_no_delete():
    """Every page in the group carries the SAME date — that is what they were
    grouped on — so the duplicates never had rows of their own. A delete here
    would remove the surviving merged row."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    body = src.split("def apply_check_in_merge")[1].split("\n    def ")[0]
    assert "delete_where" not in body, (
        "apply_check_in_merge deletes — but the archived duplicates share the "
        "surviving row's primary key, so that would delete the survivor"
    )


def test_the_merged_date_decodes_back_out_of_the_properties():
    """End to end through the decoder, since that is what the mirror uses to
    find the key."""
    props = {"Date": notion.date_prop("2026-08-10"),
             "Tightness": notion.number(4)}
    assert nr.row_from_properties(nr.READINESS, props)["date"] == "2026-08-10"


# ─── CLI scripts flush at exit ───────────────────────────────────────────

def test_queueing_registers_a_process_exit_flush():
    """Five scripts write mirrored tables and then exit without running a sync
    chain. Without this their rows are silently dropped."""
    import services.repository as repo_module
    repo_module._MIRROR_ATEXIT_REGISTERED = False
    registered = []
    original = repo_module.atexit.register
    repo_module.atexit.register = lambda fn, *a, **k: registered.append(fn) or fn
    try:
        repo = _repo()
        repo.queue_mirror("config", "k", {"key": "k", "value": "v"})
        assert registered, "no exit flush was registered"
    finally:
        repo_module.atexit.register = original


def test_the_exit_flush_is_registered_only_once_per_process():
    """A Repository is built per background sync run; one hook per run would
    pile up for the life of the process."""
    import services.repository as repo_module
    repo_module._MIRROR_ATEXIT_REGISTERED = False
    registered = []
    original = repo_module.atexit.register
    repo_module.atexit.register = lambda fn, *a, **k: registered.append(fn) or fn
    try:
        for _ in range(5):
            _repo().queue_mirror("config", "k", {"key": "k", "value": "v"})
        assert len(registered) == 1, f"registered {len(registered)} hooks"
    finally:
        repo_module.atexit.register = original


def test_the_exit_hook_does_not_hold_a_repository():
    """A Repository owns a gspread session and a Notion client, none of them
    thread-safe, and the background sync builds its own. Capturing one in a
    process-lifetime hook would keep an arbitrary instance alive."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    body = src.split("def _register_mirror_flush_at_exit")[1].split("\n    def ")[0]
    assert "config = self.config" in body
    assert "Repository(config)" in body, "the hook must build a fresh Repository"


# ─── the seam still holds, now for bulk writes too ───────────────────────

def test_every_bulk_write_goes_through_the_seam():
    """rewrite_worksheet and append_rows may only be called inside
    _rewrite_sheet / _append_sheet_rows. A direct call writes the tab and
    skips the mirror, and the Postgres copy silently starts missing whole
    rebuilds."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    allowed = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in (
                "_rewrite_sheet", "_append_sheet_rows"):
            allowed[node.name] = (node.lineno, node.end_lineno or node.lineno)

    stray = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("rewrite_worksheet", "append_rows")
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "sheets"):
            if not any(lo <= node.lineno <= hi for lo, hi in allowed.values()):
                stray.append((node.func.attr, node.lineno))
    assert not stray, (
        f"sheets.{stray} is called outside the mirror seam — those rows are "
        f"written to the tab and never mirrored"
    )


def test_the_rewrite_seam_is_documented_as_superset_only():
    """The safety argument is load-bearing: plain upserts are correct ONLY
    because these rewrites merge. If a shrinking rewrite is ever added it
    needs delete-then-insert, and the next person has to know that."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    body = src.split("def _rewrite_sheet")[1].split("\n    def ")[0]
    assert "superset" in body.lower()
