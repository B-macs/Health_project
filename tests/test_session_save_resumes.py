"""A session save that stops partway resumes under the SAME session id.

2026-09-10 was logged three times. A Save that stopped partway — 8 exercises
written, then 2 — was pressed again, and every press minted a fresh session id
via Repository.create_training_session and rewrote every exercise from the
top. Three session rows carried 486 + 410 + 410 AU for one 82-minute session;
the day's stored strain was 17.1 against 15.5 for a heavier single-row day.

The repair is in views/training.py, which is Streamlit and cannot be imported
here, so this pins the SHAPE of the fix at the source: the pending session is
minted once and reused, an exercise already written is skipped, the markers
are checkpointed so a reload resumes too, and both Save buttons keep what was
written and say so instead of dying. scripts/archive_duplicate_sessions.py is
the data repair for the three copies already in the log.
"""

from __future__ import annotations

import ast
import pathlib

from services import sessions as sess

_SRC = (pathlib.Path(__file__).resolve().parent.parent / "views" / "training.py").read_text(
    encoding="utf-8")


def _function_source(name: str) -> str:
    tree = ast.parse(_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(_SRC, node)
    raise AssertionError(f"{name} not found in views/training.py")


def test_the_session_id_is_minted_once_and_reused_on_retry():
    body = _function_source("_auto_log_session")
    assert 'st.session_state.get("tp_pending_session")' in body
    # create_training_session runs ONLY inside the "no pending session" branch.
    before, _, after = body.partition("r.create_training_session(")
    assert "if not session_info:" in before.splitlines()[-1] or "if not session_info:" in before[-200:]
    assert "st.session_state.tp_pending_session = session_info" in after


def test_an_exercise_already_written_is_skipped_and_each_write_is_remembered():
    body = _function_source("_auto_log_session")
    assert "if idx in saved:" in body and "continue" in body
    assert "saved.add(idx)" in body
    assert "st.session_state.tp_saved_exercise_idx = sorted(saved)" in body
    # ...and remembered AFTER the Notion write, not before it.
    assert body.index("r.save_training_exercise(") < body.index("saved.add(idx)")


def test_the_markers_are_cleared_only_after_everything_is_written():
    body = _function_source("_auto_log_session")
    clear = body.index("st.session_state.tp_pending_session = None")
    assert body.index("r.save_session_notes(") < clear
    assert body.rindex("saved.add(idx)") < clear


def test_the_markers_survive_a_reload():
    """They are checkpointed, so a phone that reloads mid-save resumes too."""
    for field in ("tp_pending_session", "tp_saved_exercise_idx", "tp_last_saved_exercise_id"):
        assert field in sess.CHECKPOINT_FIELDS, field
        assert f'"{field}"' in _function_source("_init_state"), (
            f"{field} has no default in _init_state; building the checkpoint payload "
            f"indexes session_state with every CHECKPOINT_FIELDS name and a missing one "
            f"silently stops the whole checkpoint saving")


def test_both_save_buttons_keep_what_was_written_and_say_so():
    # The plan session: a try around the save, a checkpoint on failure, an
    # error that tells him to press Save again, no rerun that would lose it.
    plan_save = _SRC[_SRC.index('with st.form("log_session_form")'):]
    plan_save = plan_save[:plan_save.index("st.balloons()")]
    assert "try:" in plan_save and "_auto_log_session(day_num" in plan_save
    assert "_save_checkpoint(day_num)" in plan_save
    assert "press Save again" in plan_save
    # The accessory session's Save resumes the same way.
    acc_save = _SRC[_SRC.index('with st.form("log_accessory_form")'):]
    acc_save = acc_save[:acc_save.index("_exit_accessory_session()")]
    assert "_save_checkpoint(acc.ACCESSORY_DAY_KEY)" in acc_save
    assert "press Save again" in acc_save


def test_a_restored_checkpoint_carries_the_markers_through():
    state = {k: None for k in sess.CHECKPOINT_FIELDS}
    state.update({"tp_pending_session": {"session_id": "2026-09-10-abc"},
                  "tp_saved_exercise_idx": [0, 1, 2], "tp_last_saved_exercise_id": "page"})
    payload = sess.checkpoint_payload(22, state)
    restored = sess.restore_from_checkpoint(payload, 22)
    assert restored["tp_pending_session"] == {"session_id": "2026-09-10-abc"}
    assert restored["tp_saved_exercise_idx"] == [0, 1, 2]
    assert restored["tp_last_saved_exercise_id"] == "page"
