"""A session save that stops partway is completed under the SAME session.

2026-09-10 was logged three times. A Save that stopped partway — 8 exercises
written, then 2 — was pressed again, and every press minted a fresh session id
via Repository.create_training_session and rewrote every exercise from the
top. Three session rows carried 486 + 410 + 410 AU for one 82-minute session;
the day's stored strain was 17.1 against 15.5 for a heavier single-row day.

Since 2026-10-19 the Training page saves through services/session_save.py, the
save the phone's API uses too, and the ids are minted ONCE by the caller: the
session's and each exercise's. tests/test_session_save.py proves the save
itself (sent three times, one session; stopped partway, completed by the next
send). The Training page is Streamlit and cannot be imported here, so this
pins the page's side at the source: it mints the ids once and resends them,
it saves only through the shared save, the ids are checkpointed so a reload
resends them too, and both Save buttons keep what was written and say so.
scripts/archive_duplicate_sessions.py is the data repair for the three copies
already in the log.
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
    # The earlier press's pending save is passed back in, and pending_save
    # returns it unchanged when it holds an id for every exercise.
    assert 'earlier=st.session_state.get("tp_pending_session")' in body
    assert body.index("session_save.pending_save(") < body.index(
        "st.session_state.tp_pending_session = pending") < body.index(
        "session_save.save_session(")


def test_an_exercise_already_written_is_skipped_and_each_write_is_remembered():
    """Renamed in substance on 2026-10-19: nothing is skipped any more. A
    resend writes every exercise again under its own id, which replaces the
    row instead of adding one. The page must reach the store ONLY through the
    shared save, or a second path could mint its own ids again."""
    body = _function_source("_auto_log_session")
    assert "session_save.save_session(r, session)" in body
    for direct in ("create_training_session(", "save_training_exercise(", "save_session_notes("):
        assert direct not in body, direct


def test_the_markers_are_cleared_only_after_everything_is_written():
    body = _function_source("_auto_log_session")
    clear = body.index("st.session_state.tp_pending_session = None")
    assert body.index("session_save.save_session(") < clear


def test_the_markers_survive_a_reload():
    """The pending save is checkpointed, so a phone that reloads mid-save
    resends the same ids."""
    assert "tp_pending_session" in sess.CHECKPOINT_FIELDS
    assert '"tp_pending_session"' in _function_source("_init_state"), (
        "tp_pending_session has no default in _init_state; building the checkpoint "
        "payload indexes session_state with every CHECKPOINT_FIELDS name and a missing "
        "one silently stops the whole checkpoint saving")


def test_both_save_buttons_keep_what_was_written_and_say_so():
    # The plan session: a try around the save, a checkpoint on failure, an
    # error that tells him to press Save again, no rerun that would lose it.
    plan_save = _SRC[_SRC.index('with st.form("log_session_form")'):]
    plan_save = plan_save[:plan_save.index("st.balloons()")]
    assert "try:" in plan_save and "_auto_log_session(day_num" in plan_save
    assert "_save_checkpoint(day_num)" in plan_save
    assert "press Save again" in plan_save and "nothing is stored twice" in plan_save
    # The accessory session's Save resumes the same way.
    acc_save = _SRC[_SRC.index('with st.form("log_accessory_form")'):]
    acc_save = acc_save[:acc_save.index("_exit_accessory_session()")]
    assert "_save_checkpoint(acc.ACCESSORY_DAY_KEY)" in acc_save
    assert "press Save again" in acc_save and "nothing is stored twice" in acc_save


def test_a_restored_checkpoint_carries_the_markers_through():
    state = {k: None for k in sess.CHECKPOINT_FIELDS}
    pending = {"session_id": "2026-09-10-abc", "session_date": "2026-09-10",
               "duration_minutes": 82, "session_rpe": 5, "exercise_ids": ["a", "b", "c"]}
    state["tp_pending_session"] = pending
    payload = sess.checkpoint_payload(22, state)
    restored = sess.restore_from_checkpoint(payload, 22)
    assert restored["tp_pending_session"] == pending
