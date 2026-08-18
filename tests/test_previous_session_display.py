"""The previous session must be ON SCREEN beside the prescription, and the
previous reading must never be derived from the prescription.

Two properties, and neither is visible from services/sessions.py alone:

  1. The block is rendered UNCONDITIONALLY on the exercise screen — not inside
     an expander, not behind a button. It is a human-in-the-loop verification
     step: the athlete accepts or overrides the engine's proposed increase by
     reading the previous numbers beside it, and a reading one tap away cannot
     do that job. An expander is the specific failure mode ruled out, and this
     file exists because it is a one-line change to reintroduce.

  2. tp_previous is seeded from the RAW repository reads and is separate from
     tp_actuals, which the readiness nudge, the ceiling clamp and every stepper
     tap all mutate. Deriving one from the other is the bug this replaced.
"""

import ast
import io
import os

import pytest
from streamlit.testing.v1 import AppTest

from services import sessions

_TRAINING = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "views", "training.py")


def _tree() -> ast.Module:
    return ast.parse(io.open(_TRAINING, encoding="utf-8").read())


def _is_expander(node: ast.AST) -> bool:
    """True for `with st.expander(...)`, however it is spelled."""
    if not isinstance(node, (ast.With, ast.AsyncWith)):
        return False
    for item in node.items:
        call = item.context_expr
        if isinstance(call, ast.Call):
            func = call.func
            if isinstance(func, ast.Attribute) and func.attr == "expander":
                return True
    return False


def _calls_named(tree: ast.AST, name: str) -> list[ast.Call]:
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == name]


# ── 1. on screen, not behind a tap ───────────────────────────────────────────

def test_the_previous_session_is_rendered_on_the_exercise_screen():
    assert _calls_named(_tree(), "previous_caption"), \
        "views/training.py never calls sessions.previous_caption"


def test_the_delta_is_rendered_too():
    tree = _tree()
    assert _calls_named(tree, "prescription_delta"), \
        "the delta between prescribed and previous is never rendered"


def test_the_previous_block_is_not_inside_an_expander():
    """The one placement explicitly ruled out. Walk every expander in the file
    and fail if a previous_caption/prescription_delta call sits under one."""
    tree = _tree()
    for node in ast.walk(tree):
        if not _is_expander(node):
            continue
        for name in ("previous_caption", "prescription_delta"):
            assert not _calls_named(node, name), (
                f"sessions.{name} is rendered inside an st.expander — the "
                "previous session must be visible without a tap"
            )


# ── 2. the raw reading is kept apart from the proposal ───────────────────────

def test_tp_previous_is_seeded_from_previous_performance():
    tree = _tree()
    seeds = [n for n in ast.walk(tree)
             if isinstance(n, ast.Assign)
             and isinstance(n.value, ast.Call)
             and isinstance(n.value.func, ast.Attribute)
             and n.value.func.attr == "previous_performance"]
    assert seeds, "tp_previous is never seeded from sessions.previous_performance"


def test_previous_performance_is_handed_the_repository_reads_not_the_entry():
    """Its two arguments must be the raw lookups. Handing it the resolved entry
    would reintroduce exactly the bug: a previous reading that has been through
    the readiness nudge and the clamp."""
    tree = _tree()
    call = next(n for n in ast.walk(tree)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == "previous_performance")
    args = [a.id for a in call.args if isinstance(a, ast.Name)]
    assert args == ["last", "last_session_sets"], args


def test_tp_previous_has_an_init_state_default():
    src = io.open(_TRAINING, encoding="utf-8").read()
    assert '"tp_previous":' in src, \
        "tp_previous needs a default or the first .get() raises on a fresh session"


def test_tp_previous_is_deliberately_not_checkpointed():
    """It is a reading of the training log, not session state. Persisting it
    would grow the Notion rich_text checkpoint (written on every transition,
    already carrying tp_set_log) to cache something a re-read produces for
    free — and a restored checkpoint simply re-fetches it."""
    assert "tp_previous" not in sessions.CHECKPOINT_FIELDS


def test_the_seed_guard_is_independent_of_tp_actuals():
    """A restored checkpoint carries tp_actuals but not tp_previous. If the two
    shared one guard, every restored session would show "No previous data" on
    every exercise."""
    src = io.open(_TRAINING, encoding="utf-8").read()
    assert "need_previous" in src and "need_actuals" in src, \
        "_seed_actuals_if_needed must decide the two seeds separately"


# ── 3. the contract the view depends on ──────────────────────────────────────

@pytest.mark.parametrize("name", [
    "previous_performance", "previous_caption", "prescription_delta",
    "delta_direction", "PREVIOUS_NONE_TEXT", "DELTA_NONE_TEXT",
])
def test_the_public_surface_exists(name):
    assert hasattr(sessions, name)


def test_no_previous_data_is_never_a_number():
    """Never 0, never a bare "-" in a numeric slot, never an interpolated
    value — each of those reads as a real reading of zero."""
    empty = sessions.previous_performance(None, None)
    caption = sessions.previous_caption(empty)
    assert caption == "No previous data"
    assert not any(ch.isdigit() for ch in caption)
    assert sessions.prescription_delta({"weight_kg": 40.0, "reps": 10}, empty) == ""


# ── 4. against the real Streamlit runtime ────────────────────────────────────

_SEED_SCRIPT = """
import streamlit as st
from views import training as V
from services import sessions as sess


class _FakeRepo:
    '''Only the two reads _seed_actuals_if_needed makes.'''
    def get_last_performance(self, name):
        return {"session_date": "2026-08-10", "reps": 8,
                "weight_kg": 42.5, "band_tier": None}

    def get_last_session_all_sets(self, name):
        return [{"set_num": 1, "reps": 10, "weight": 45.0},
                {"set_num": 2, "reps": 10, "weight": 45.0},
                {"set_num": 3, "reps": 8,  "weight": 42.5}]


V.repo.get_repository = lambda: _FakeRepo()
V._save_checkpoint = lambda *a, **k: None

st.session_state.setdefault("tp_actuals", {})
st.session_state.setdefault("tp_previous", {})

EX = {"name": "Goblet Squat", "type": "reps", "reps": 10, "sets": 3,
      "equipment_type": "dumbbell", "weight_kg": 20.0}

# A readiness-HIGH day, i.e. the day the engine adds an increment. This is the
# case the old caption got wrong.
V._seed_actuals_if_needed(0, EX, {"streak_label": "high"}, {"reduced": False}, 1)

_entry = st.session_state.tp_actuals[0]
_prev  = st.session_state.tp_previous[0]
st.text("PRESCRIBED " + str(_entry["weight_kg"]))
st.text("PREVIOUS " + sess.previous_caption(_prev))
st.text("DELTA " + sess.prescription_delta(_entry, _prev))
"""


def _run_seed_script() -> list[str]:
    at = AppTest.from_string(_SEED_SCRIPT)
    at.run()
    assert not at.exception, at.exception
    return [t.value for t in at.text]


def test_seeding_runs_under_the_real_runtime_and_keeps_the_two_apart():
    """END-TO-END. _seed_actuals_if_needed writes BOTH slots from the same two
    repository reads, and the previous reading must survive the readiness nudge
    that moves the prescription."""
    out = _run_seed_script()
    assert "PRESCRIBED 45.0" in out, out
    assert "PREVIOUS Last: 45kg × 10, 45kg × 10, 42.5kg × 8 (2026-08-10)" in out, out
    # 42.5 + one 2.5 increment = 45.0, clamped by nothing; the previous top set
    # was also 45.0, so the honest delta is the rep change alone.
    assert "DELTA -2 reps" in out, out


def test_a_restored_checkpoint_refetches_the_previous_reading():
    """tp_previous is not checkpointed, so a restore leaves tp_actuals seeded
    and tp_previous empty. The seed must still fill it in — otherwise every
    exercise reads "No previous data" for the rest of a resumed session."""
    script = _SEED_SCRIPT.replace(
        'st.session_state.setdefault("tp_previous", {})',
        'st.session_state.setdefault("tp_previous", {})\n'
        '# simulate _load_checkpoint: the entry is back, the reading is not\n'
        'st.session_state.tp_actuals[0] = {"reps": 9, "weight_kg": 40.0,\n'
        '    "band_tier": None, "source": "last_time",\n'
        '    "last_seen_date": "2026-08-10", "clamped": {}}',
    )
    at = AppTest.from_string(script)
    at.run()
    assert not at.exception, at.exception
    out = [t.value for t in at.text]
    # The restored entry is untouched...
    assert "PRESCRIBED 40.0" in out, out
    # ...and the previous reading was fetched anyway.
    assert "PREVIOUS Last: 45kg × 10, 45kg × 10, 42.5kg × 8 (2026-08-10)" in out, out
    assert "DELTA -5kg, -1 rep" in out, out
