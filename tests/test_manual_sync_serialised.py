"""
Source-level invariant: every user-triggered device sync in views/ runs
inside the background runner's one-at-a-time lock.

Same genre as tests/test_no_streamlit_in_services.py — the property is
architectural, so it is checked against the source rather than by executing
a Streamlit page.

Why it needs a test at all. The manual sync buttons in views/insights.py
call Repository.sync_* DIRECTLY rather than going through run_home_syncs, so
nothing about their shape stops them running while the background chain is
mid-write; only taking the lock does. And the failure they cause is silent
data corruption, not an exception: sheets.upsert_row_by_key is a
find-then-write pair, so two chains upserting a date that is not on the tab
yet both find nothing and both append, leaving that date with two rows.
The date most likely to be missing is today's — exactly the one both chains
are writing.

Adding a new sync button is the obvious way to reintroduce this, which is
what this test is here to catch.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

VIEWS = Path(__file__).resolve().parent.parent / "views"

# Methods that write a Sheet tab the automatic chain (Repository.run_home_syncs)
# also writes. A call to one of these from a Streamlit page must hold the lock.
GUARDED_SYNC_METHODS = {
    "sync_oura_all",
    "sync_garmin_daily",
    "sync_garmin_daily_if_due",
    "sync_garmin_activities",
    "sync_biometric_blend",
    "sync_sleep_fusion",
    "sync_metrics_history",
    "sync_session_hr_recent",
    # Read-only but rate-limited: the hike importer's date-scoped Garmin
    # fetch is an explicit button press, so it takes the waiting lock.
    "get_garmin_activities_for_date",
}

# Names that, appearing in a `with` item, mean the lock is held for that
# block — _manual_sync is views/insights.py's helper, which wraps exclusive().
LOCK_HOLDERS = {"_manual_sync", "exclusive"}


def _lock_held_line_ranges(tree: ast.Module) -> list[tuple[int, int]]:
    """Line spans of every `with` block that holds the runner's lock."""
    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.With, ast.AsyncWith)):
            continue
        holds = any(
            isinstance(sub, ast.Name) and sub.id in LOCK_HOLDERS
            or isinstance(sub, ast.Attribute) and sub.attr in LOCK_HOLDERS
            for item in node.items
            for sub in ast.walk(item.context_expr)
        )
        if holds:
            spans.append((node.lineno, node.end_lineno or node.lineno))
    return spans


def _guarded_sync_calls(tree: ast.Module) -> list[tuple[str, int]]:
    return [
        (node.func.attr, node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in GUARDED_SYNC_METHODS
    ]


@pytest.mark.parametrize("path", sorted(VIEWS.glob("*.py")), ids=lambda p: p.name)
def test_every_manual_sync_holds_the_runner_lock(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    spans = _lock_held_line_ranges(tree)

    unguarded = [
        (name, line)
        for name, line in _guarded_sync_calls(tree)
        if not any(start <= line <= end for start, end in spans)
    ]

    assert not unguarded, (
        f"{path.name}: these device syncs run without the background runner's "
        f"lock, so they can collide with the automatic chain mid-write "
        f"(duplicate rows via upsert_row_by_key's find-then-append): "
        + ", ".join(f"{name}() at line {line}" for name, line in unguarded)
        + ". Wrap the call in `with _manual_sync(...)` (waits — for an "
        "explicit button press) or `with repo.get_sync_runner().exclusive("
        "timeout=0)` (skips — for something that fires on every render)."
    )


def test_the_check_actually_finds_the_calls_it_is_guarding():
    """Guards the guard: if the method names above drift out of date this
    test file would pass vacuously while checking nothing."""
    found = {
        name
        for path in VIEWS.glob("*.py")
        for name, _ in _guarded_sync_calls(ast.parse(path.read_text(encoding="utf-8")))
    }
    assert found, "no guarded sync calls found in views/ — has the naming changed?"


def test_an_unguarded_call_would_be_caught():
    """Guards the guard, second half: prove a bare call fails the check,
    so the parametrised test above can't be passing for the wrong reason."""
    tree = ast.parse("repo.get_repository().sync_oura_all(days=7)\n")
    calls = _guarded_sync_calls(tree)
    assert calls == [("sync_oura_all", 1)]
    assert _lock_held_line_ranges(tree) == []
