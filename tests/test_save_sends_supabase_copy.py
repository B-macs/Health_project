"""A save sends its Supabase copy before the page moves on.

Found 2026-10-09. The athlete trained Monday to Thursday and the hosted app
showed Monday only. Notion held all four sessions; Supabase held Monday's.
The Training page QUEUES the Supabase copy, and the queue was sent only as the
last step of run_home_syncs, which only the Home page starts. A Community
Cloud restart before the next Home visit lost the queue, and the same restart
rebuilt the hosted read cache from Supabase, so the sessions of 2026-10-06,
10-07 and 10-08 disappeared from the app while Notion still held them.

Repository.send_mirror_now sends the queue at once and returns the error text
of a failed send. Every saver that writes a training session or a check-in
calls it, and these tests fail if one stops.
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
    supabase_store.OUTBOX.drain()
    yield
    supabase_store.OUTBOX.drain()


class FakeStore:
    def __init__(self, fail_on: str | None = None):
        self.fail_on = fail_on
        self.sent: list[tuple[str, int]] = []

    def _check(self, table):
        if table == self.fail_on:
            raise supabase_store.SupabaseError(f"boom on {table}")

    def upsert(self, table, rows):
        self._check(table)
        self.sent.append((table, len(rows)))
        return len(rows)

    def patch(self, table, pk_column, pk_value, row):
        self._check(table)
        return 1

    def delete_where(self, table, column, value):
        self._check(table)

    def insert(self, table, rows):
        self._check(table)
        self.sent.append((table, len(rows)))
        return len(rows)


def _repo(store) -> Repository:
    repo = Repository(Config(
        notion_api_key="k", notion_db_readiness="a", notion_db_training="b",
        notion_db_config="d", google_sheets_id="e", google_service_account={},
        supabase_url="https://x.supabase.co", supabase_secret_key="secret",
    ))
    repo._supabase_store_obj = store
    return repo


def _queue_training_exercise(repo: Repository) -> None:
    """What save_training_exercise queues: one Notion page, three tables."""
    repo._mirror_training_write("ex-1", {
        "session_id": "2026-10-06-aa0c1c5c", "session_date": "2026-10-06",
        "movement_name": "Goblet Squat", "session_duration_minutes": 53,
        "session_rpe": 7, "session_au": 371.0,
    }, sets=[{"set_num": 1, "reps": 10, "weight": 22.5}])


def test_a_saved_session_reaches_supabase_with_its_three_tables():
    store = FakeStore()
    repo = _repo(store)
    _queue_training_exercise(repo)
    assert repo.send_mirror_now() is None
    assert {t for t, _n in store.sent} == {
        "training_sessions", "training_exercises", "training_sets"}
    assert supabase_store.OUTBOX.size() == 0


def test_a_failed_send_is_reported_not_swallowed():
    repo = _repo(FakeStore(fail_on="training_sessions"))
    _queue_training_exercise(repo)
    err = repo.send_mirror_now()
    assert err and err.startswith("training_sessions:")


def test_an_old_error_is_not_reported_for_a_send_that_worked():
    repo = _repo(FakeStore())
    repo.mirror_last_error = ("config", "an earlier failure")
    _queue_training_exercise(repo)
    assert repo.send_mirror_now() is None


def test_nothing_queued_is_not_an_error():
    assert _repo(FakeStore()).send_mirror_now() is None


# ─── every saver sends ──────────────────────────────────────────────────────

def _function(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path.name}")


def _calls(node: ast.AST) -> set[str]:
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            fn = sub.func
            names.add(fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", ""))
    return names


@pytest.mark.parametrize("saver", [
    "_auto_log_session", "_log_yoga_completion", "_log_outdoor_activity"])
def test_every_training_saver_sends_the_copy(saver):
    assert "_send_backup_copy" in _calls(_function(ROOT / "views" / "training.py", saver))


def test_the_send_helper_uses_the_repository_send():
    helper = _function(ROOT / "views" / "training.py", "_send_backup_copy")
    assert "send_mirror_now" in _calls(helper)


def test_the_training_page_shows_a_failed_send():
    assert "_render_backup_warning" in _calls(
        _function(ROOT / "views" / "training.py", "render"))


def test_the_warning_survives_the_tp_resets():
    src = (ROOT / "views" / "training.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if (isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "_BACKUP_SEND_ERROR") or (
                isinstance(node, ast.Assign)
                and any(getattr(t, "id", "") == "_BACKUP_SEND_ERROR" for t in node.targets)):
            assert not node.value.value.startswith("tp_")
            return
    raise AssertionError("_BACKUP_SEND_ERROR not found")


def test_the_check_in_sends_after_it_saves():
    src = (ROOT / "views" / "checkin.py").read_text(encoding="utf-8")
    save = src.index("save_check_in(")
    assert "send_mirror_now()" in src[save:], "the check-in no longer sends its copy"

