"""The bottom nav bar is the only way off a page, so it must outlive the page.

Reported 2026-08-18: an UnserializableReturnValueError inside views/insights.py
left the athlete on the Insights page with an error box and no Home / Training /
Insights / Voice buttons at all — the only escape was hand-editing the URL. The
error is a separate bug; this file is about the fact that it was UNRECOVERABLE.

app.py's dispatch used to read

    styles.inject_css(); _v.render(); nav.inject("insights"); st.stop()

so anything render() raised jumped straight over nav.inject. That included
st.stop() and st.rerun(), whose StopException/RerunException derive from
BaseException — which is why views/training.py had already grown ten explicit
nav.inject calls of its own, and why the one before its plan-start st.stop() was
simply missing.

Two properties are pinned here:
  1. nav.inject runs in a `finally`, so it runs however render() ends.
  2. nav.inject is idempotent within a script run, so app.py's fallback and
     training.py's ten explicit calls cannot draw two stacked bars.
"""

from __future__ import annotations

import ast
import io
import os

from streamlit.testing.v1 import AppTest

import nav

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP = os.path.join(_ROOT, "app.py")

_N_TABS = len(nav._ITEMS)


def _app_tree() -> ast.Module:
    return ast.parse(io.open(_APP, encoding="utf-8").read())


def _nav_inject_calls(node: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(node)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "inject"
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "nav"]


def _renders_a_view(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == "render"
               for n in ast.walk(node))


# ── 1. the dispatch shape ────────────────────────────────────────────────────

def test_the_view_dispatch_injects_nav_in_a_finally():
    """Not merely 'nav.inject appears after render()' — it must be in the
    finalbody, which is the only placement that survives an exception."""
    tries = [n for n in ast.walk(_app_tree()) if isinstance(n, ast.Try)]
    dispatch = [t for t in tries
                if _renders_a_view(t) and any(_renders_a_view(b) for b in [t])]
    assert dispatch, "app.py no longer calls a view's render() inside a try"
    ok = [t for t in dispatch
          if t.finalbody and _nav_inject_calls(ast.Module(body=t.finalbody, type_ignores=[]))]
    assert ok, (
        "the view dispatch calls render() but does not inject the nav bar in "
        "its finally — an exception in a view would strand the athlete on it"
    )


def test_the_dispatch_no_longer_injects_nav_only_on_the_happy_path():
    """Guards the exact regression: a bare `_v.render(); nav.inject(...)`
    sequence at statement level, which is what shipped and what broke."""
    src = io.open(_APP, encoding="utf-8").read()
    assert "_v.render(); nav.inject(" not in src


def test_start_run_is_called_before_the_dispatch():
    """The once-per-run flag lives in session_state, so it survives the run
    that set it. Without a reset the bar renders once and never again."""
    tree = _app_tree()
    starts = [n for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == "start_run"]
    assert starts, "app.py never calls nav.start_run()"
    first_inject = min((c.lineno for c in _nav_inject_calls(tree)), default=10**9)
    assert min(c.lineno for c in starts) < first_inject


# ── 2. behaviour, against the real Streamlit runtime ─────────────────────────

_RAISING_VIEW = """
import sys, os
sys.path.insert(0, os.getcwd())
import nav

nav.start_run()
try:
    raise RuntimeError("the view exploded")
finally:
    nav.inject("insights")
"""


def test_the_nav_bar_is_drawn_even_though_the_view_raised():
    at = AppTest.from_string(_RAISING_VIEW)
    at.run()
    assert at.exception, "the error must still surface — this is not a swallow"
    assert len(at.button) == _N_TABS, (
        f"expected {_N_TABS} nav buttons after a failing view, got {len(at.button)}"
    )


_DOUBLE_INJECT = """
import sys, os
sys.path.insert(0, os.getcwd())
import nav

nav.start_run()
nav.inject("training")     # the view's own call, as views/training.py makes it
nav.inject("training")     # app.py's fallback in its finally
"""


def test_two_injects_in_one_run_draw_one_bar():
    at = AppTest.from_string(_DOUBLE_INJECT)
    at.run()
    assert not at.exception, at.exception
    assert len(at.button) == _N_TABS, (
        f"idempotence broken: {len(at.button)} buttons, expected {_N_TABS}"
    )


_ACROSS_RUNS = """
import sys, os
sys.path.insert(0, os.getcwd())
import streamlit as st
import nav

nav.start_run()
nav.inject("home")
st.text("runs=" + str(st.session_state.get("_runs", 0)))
st.session_state["_runs"] = st.session_state.get("_runs", 0) + 1
"""


def test_the_guard_is_cleared_on_the_next_run():
    """The failure this would otherwise cause is worse than a double bar: the
    bar renders on the first run of a session and never again."""
    at = AppTest.from_string(_ACROSS_RUNS)
    at.run()
    assert len(at.button) == _N_TABS
    at.run()
    assert not at.exception, at.exception
    assert len(at.button) == _N_TABS, (
        "start_run() did not clear the guard — the nav bar vanished on the "
        "second script run"
    )


def test_injected_this_run_reports_the_flag():
    script = (
        "import sys, os\n"
        "sys.path.insert(0, os.getcwd())\n"
        "import streamlit as st\n"
        "import nav\n"
        "nav.start_run()\n"
        "st.text('before=' + str(nav.injected_this_run()))\n"
        "nav.inject('sync')\n"
        "st.text('after=' + str(nav.injected_this_run()))\n"
    )
    at = AppTest.from_string(script)
    at.run()
    assert not at.exception, at.exception
    values = [t.value for t in at.text]
    assert "before=False" in values and "after=True" in values, values
