"""Load app.py's definitions for a test WITHOUT running the Home page.

app.py is a Streamlit script, not a module. Importing it runs the Home page
with the checkout's real secrets: repo.get_repository() (which, with Supabase
as the system of record, rebuilds a local copy from the real project), every
read on the page, and, until 2026-10-09, the device sync at its foot. Three
test files imported it — one at collection time, before tests/conftest.py's
per-test isolation of the sync-state file could apply — so a full run on a
machine with real secrets had been syncing Oura and Garmin for real since
2026-08-10. tests/test_no_test_runs_the_app.py keeps it from coming back.

What this executes, in source order: every top-level import, every function
and class definition, and every top-level assignment that calls nothing in
repo, today or st and none of app.py's own functions, and reads only names
already defined. Everything else at top level is the page itself and is
skipped; a name it would have
assigned starts as None, so a test sets the page state it needs with
monkeypatch.setattr exactly as it did on the imported module.
"""
from __future__ import annotations

import ast
import types
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app.py"

#: Calls through these reach the store, the clock or the page.
_PAGE_MODULES = frozenset({"repo", "today", "st"})


def _keeps(value: ast.AST, known: set[str], app_functions: set[str]) -> bool:
    """A top-level assignment is part of the module, not of the page, when it
    calls nothing in repo/today/st and none of app.py's own functions (which
    may read the store), and reads only names already defined."""
    for node in ast.walk(value):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in app_functions:
                return False
            root = func
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in _PAGE_MODULES:
                return False
    local = {n.id for n in ast.walk(value)
             if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    reads = {n.id for n in ast.walk(value)
             if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)} - local
    return reads <= known


def _assigned_names(node: ast.stmt) -> list[str]:
    """Every name a skipped statement would have bound at module level —
    including inside its if/with/try blocks, where the page sets most of its
    state (selected_date is assigned in an if/else)."""
    return [n.id for n in ast.walk(node)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]


def _bound_names(node: ast.stmt) -> list[str]:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return [(a.asname or a.name).split(".")[0] for a in node.names]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    return _assigned_names(node)


def load_app() -> types.ModuleType:
    """A fresh module holding app.py's definitions, the page not run."""
    import builtins
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    kept, skipped = [], []
    known = set(dir(builtins)) | {"__file__", "__name__"}
    app_functions = {n.name for n in tree.body
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef,
                             ast.AsyncFunctionDef, ast.ClassDef)):
            kept.append(node)
            known.update(_bound_names(node))
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            # `is_today = (selected_date == _today)` calls nothing and is
            # still page state: it reads a name only the page defines.
            if _keeps(node.value, known, app_functions):
                kept.append(node)
                known.update(_bound_names(node))
                continue
        skipped += _assigned_names(node)
    module = types.ModuleType("app_definitions")
    module.__file__ = str(APP)
    exec(compile(ast.Module(body=kept, type_ignores=[]), str(APP), "exec"), module.__dict__)
    for name in skipped:
        module.__dict__.setdefault(name, None)
    return module
