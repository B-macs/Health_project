"""No test may run app.py, and app.py syncs devices only under a server.

app.py is a Streamlit script, not a module: importing it runs the whole Home
page with whatever secrets the checkout holds — repo.get_repository(), every
read on the page, and the device sync at its foot. FOUND 2026-10-09:
tests/test_strain_screen.py imported it for one HTML helper, so every full
test run on a machine with real secrets had been syncing Oura, Garmin and the
derived tabs for real since 2026-08-10. CLAUDE.md forbids running the app
locally for exactly this reason: an Oura token refresh on a second machine
spends the refresh token the hosted app holds. That day it also rebuilt a copy
of the real Supabase and wrote a row there.

Two layers. Tests read app.py's source (ast) or load single definitions from
it (test_strain_screen._app_helpers), never the page. And app.py itself starts
the sync, and repo.py writes the switch marker, only when st.runtime.exists().
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _runs_the_app(tree: ast.AST) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name == "app"]
        elif isinstance(node, ast.ImportFrom) and node.module == "app":
            found.append("from app import")
        elif isinstance(node, ast.Call):
            text = ast.unparse(node)
            if ("import_module('app')" in text or 'import_module("app")' in text
                    or ("from_file" in text and "app.py" in text)
                    or ("run_path" in text and "app.py" in text)):
                found.append(text[:60])
    return found


def test_no_test_file_runs_app_py():
    offenders = {}
    for path in (ROOT / "tests").rglob("*.py"):
        hits = _runs_the_app(ast.parse(path.read_text(encoding="utf-8")))
        if hits:
            offenders[str(path.relative_to(ROOT))] = hits
    assert not offenders, offenders


def test_the_guard_sees_an_import():
    assert _runs_the_app(ast.parse("import app as app_module")) == ["app"]
    assert _runs_the_app(ast.parse("from app import _panel")) == ["from app import"]


def test_the_device_sync_starts_only_under_a_streamlit_server():
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    calls = [n for n in tree.body if isinstance(n, ast.Expr)
             and isinstance(n.value, ast.Call)
             and getattr(n.value.func, "id", "") == "_run_startup_sync"]
    assert not calls, "_run_startup_sync() is called at top level without the server check"
    guarded = [n for n in tree.body if isinstance(n, ast.If)
               and "st.runtime.exists()" in ast.unparse(n.test)
               and "_run_startup_sync()" in ast.unparse(n)]
    assert guarded, "the startup sync must sit under `if st.runtime.exists():`"


def test_the_switch_marker_is_written_only_under_a_streamlit_server():
    src = (ROOT / "repo.py").read_text(encoding="utf-8")
    body = src.split("def get_repository")[1].split("\ndef ")[0]
    guard = "if st.runtime.exists() and repository.supabase_record:"
    assert guard in body
    assert body.index(guard) < body.index("switchover.finish")
