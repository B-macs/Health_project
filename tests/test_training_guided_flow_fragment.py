"""
Tests for the guided flow being an st.fragment — views/training.py's
_render_guided_flow and the _rerun_flow helper every handler inside it uses.

WHY THE FRAGMENT EXISTS. Before it, ONE weight/reps stepper tap cost four
uncached Notion round trips plus a full page re-render: two for the checkpoint
(set_config is a find-then-write pair) and two for render()'s prologue,
_get_plan_start() and _get_phases_and_active_phase(), neither of which is
cached. Scoping the rerun to the flow skips the prologue entirely;
_save_checkpoint(durable=False) removes the other two (see
tests/test_training_checkpoint_mirror.py). The two fixes are complementary —
neither alone takes a stepper tap off the network.

THE TRAP THESE TESTS EXIST FOR. st.rerun(scope="fragment") is not a drop-in
replacement for st.rerun(). Streamlit RAISES StreamlitAPIException whenever it
is reached during a full script run rather than a fragment rerun — the guard
is `if not curr_queue: raise` in streamlit/commands/execution_control.py,
where curr_queue is ctx.fragment_ids_this_run and is empty on a full run. A
blanket find-and-replace of st.rerun() would therefore crash the flow in
exactly the situations that are hardest to notice. _rerun_flow's try/except is
what makes it safe, and test_rerun_flow_survives_a_full_app_run proves it
against the REAL runtime rather than against an assumption about it.

That same guard is why streamlit.testing.v1.AppTest cannot exercise a
fragment-scoped rerun at all: AppTest only ever performs full-app runs and
never populates fragment_id_queue. The fallback is consequently not merely
defensive — without it the flow would be untestable.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import streamlit as st
from streamlit.errors import StreamlitAPIException
from streamlit.testing.v1 import AppTest

TRAINING_VIEW = Path(__file__).resolve().parent.parent / "views" / "training.py"


def _view_source() -> str:
    return TRAINING_VIEW.read_text(encoding="utf-8")


def _fn(name: str) -> ast.FunctionDef:
    for node in ast.walk(ast.parse(_view_source())):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in views/training.py")


# ─── _rerun_flow's contract ──────────────────────────────────────────────────

def test_rerun_flow_asks_for_fragment_scope_first(monkeypatch):
    from views import training as V

    seen = []
    monkeypatch.setattr(V.st, "rerun", lambda **kw: seen.append(kw))
    V._rerun_flow()
    assert seen == [{"scope": "fragment"}], (
        "the whole point is to rerun only the flow; an app-scoped rerun here "
        "re-executes render()'s uncached Notion prologue on every tap"
    )


def test_rerun_flow_falls_back_to_app_scope_when_fragment_scope_is_illegal(monkeypatch):
    from views import training as V

    seen = []

    def fake_rerun(**kw):
        seen.append(kw)
        if kw.get("scope") == "fragment":
            raise StreamlitAPIException(
                'scope="fragment" can only be specified from `@st.fragment`-'
                "decorated functions during fragment reruns."
            )

    monkeypatch.setattr(V.st, "rerun", fake_rerun)
    V._rerun_flow()
    assert seen == [{"scope": "fragment"}, {}], (
        "a fragment body also executes during a FULL app run, where the "
        "fragment scope raises — the fallback must complete the rerun"
    )


def test_rerun_flow_does_not_swallow_the_rerun_itself(monkeypatch):
    """st.rerun signals control flow by raising RerunException, which derives
    from BaseException — NOT Exception. If that ever changed, _rerun_flow's
    except clause would silently eat every rerun in the flow and the screen
    would freeze on the current exercise. Pin the class relationship."""
    from streamlit.runtime.scriptrunner_utils.exceptions import RerunException

    assert issubclass(RerunException, BaseException)
    assert not issubclass(RerunException, Exception)
    assert issubclass(StreamlitAPIException, Exception)


def test_rerun_flow_survives_a_full_app_run():
    """END-TO-END against the real Streamlit runtime. AppTest only performs
    full-app runs, so the button click below reaches _rerun_flow inside a
    fragment during a full run — precisely the case that raises without the
    fallback. Asserting on the RENDERED value (not just the absence of an
    exception) also catches the no-rerun-at-all variant, which leaves the
    fragment one tap behind."""
    script = (
        "import streamlit as st\n"
        "from views.training import _rerun_flow\n"
        "@st.fragment\n"
        "def _frag():\n"
        "    if st.button('go', key='go'):\n"
        "        st.session_state['n'] = st.session_state.get('n', 0) + 1\n"
        "        _rerun_flow()\n"
        "    st.text(f\"n={st.session_state.get('n', 0)}\")\n"
        "_frag()\n"
    )
    at = AppTest.from_string(script)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.text[0].value == "n=0"

    at.button[0].click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.text[0].value == "n=1", "the fragment did not repaint after the tap"


# ─── the flow really is a fragment, and its reruns are scoped ────────────────

def test_the_guided_flow_is_decorated_as_a_fragment():
    fn = _fn("_render_guided_flow")
    decorators = {ast.unparse(d) for d in fn.decorator_list}
    assert "st.fragment" in decorators, (
        f"_render_guided_flow must be an st.fragment; found {decorators}"
    )


def test_the_guided_flow_takes_render_locals_as_frozen_arguments():
    """Six, and no more — anything else it needs would be read live from
    session_state and could disagree with what render() decided."""
    fn = _fn("_render_guided_flow")
    assert [a.arg for a in fn.args.args] == [
        "day_num", "exercises", "n_ex",
        "_policy", "_readiness_modifier", "_volume_factor",
    ]


def test_every_handler_in_the_flow_reruns_fragment_scoped_except_the_handoff():
    """ONE bare st.rerun() is correct and required: the tp_ex_idx >= n_ex
    hand-off sets tp_done_today and must rerun the WHOLE app, because the
    completion screen it hands off to is rendered by render() above the
    fragment and a fragment-scoped rerun would never reach it. Every other
    handler must be fragment-scoped or the tap pays render()'s prologue."""
    fn = _fn("_render_guided_flow")

    bare, scoped = [], []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "rerun":
            bare.append(node.lineno)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "_rerun_flow":
            scoped.append(node.lineno)

    assert len(bare) == 1, (
        f"expected exactly one app-scoped st.rerun() in the flow (the "
        f"completion hand-off); found {len(bare)} at lines {bare}"
    )
    assert len(scoped) >= 15, (
        f"expected the flow's handlers to use _rerun_flow(); found {len(scoped)}"
    )

    # ...and the one bare rerun is the hand-off, identified by the assignment
    # that precedes it rather than by a line number.
    handoff = None
    for node in ast.walk(fn):
        if isinstance(node, ast.If):
            src = ast.unparse(node)
            if "tp_ex_idx >= n_ex" in src and "st.rerun()" in src:
                handoff = node
    assert handoff is not None, (
        "the one bare st.rerun() is not the tp_ex_idx >= n_ex completion "
        "hand-off — either it moved, or a different rerun lost its scope"
    )
    assert "tp_done_today = True" in ast.unparse(handoff)


def test_the_flow_never_calls_st_stop():
    """st.stop() raises StopException, which Streamlit deliberately re-raises
    PAST the fragment wrapper — it would kill the whole script run, so the
    bottom nav bar (nav.inject, called by render() after this) would vanish.
    The extraction boundary was chosen to contain no st.stop(); keep it so."""
    fn = _fn("_render_guided_flow")
    stops = [
        n.lineno for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "stop"
    ]
    assert stops == [], f"st.stop() inside the fragment at lines {stops}"


def test_the_status_strip_does_not_read_state_the_fragment_mutates():
    """session_active is rendered OUTSIDE the fragment, so it must not depend
    on tp_ex_idx — which the fragment moves, and which a fragment-scoped rerun
    would therefore leave stale out here. tp_started is already True for every
    render that reaches the flow, so it cannot go stale."""
    src = _view_source()
    strip = src.split("session_active = (", 1)[1].split(")", 1)[0]
    assert "tp_started" in strip
    assert "tp_ex_idx" not in strip, (
        "the status strip reads tp_ex_idx again — it will not repaint under a "
        "fragment-scoped rerun"
    )
