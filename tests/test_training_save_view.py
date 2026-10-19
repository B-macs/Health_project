"""The Training page's own save, run in Streamlit's test runtime.

tests/test_session_save.py proves services/session_save.py. This runs the
page's `_auto_log_session` itself, against a fake Supabase in record mode
(tests/_record_store.py), with the flow's state in session_state: the first
press of Save loses its connection in the middle, the second press completes
it, and the store holds ONE session with every exercise, the stepped values
and the notes. No network and no secrets.
"""

from __future__ import annotations

import os

from streamlit.testing.v1 import AppTest

from services import record_cache
from tests._record_store import new_local_copy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SCRIPT = '''
import sys
sys.path.insert(0, r"{root}")
import repo
import streamlit as st
from services import supabase_store
from tests._record_store import FakeStore, record_repo


class _DropsOnce(FakeStore):
    """The second set list sent is lost once: a connection that drops."""
    def insert(self, table, rows):
        if table == "training_sets":
            self.calls = getattr(self, "calls", 0) + 1
            if self.calls == 2:
                raise supabase_store.SupabaseError("connection dropped")
        return super().insert(table, rows)


if "_store" not in st.session_state:
    st.session_state["_store"] = _DropsOnce()
    st.session_state["_repo"] = record_repo(r"{db}", st.session_state["_store"])
repo.get_repository = lambda: st.session_state["_repo"]

from views import training

st.session_state.setdefault("tp_pending_session", None)
st.session_state.setdefault("tp_actuals", {{0: {{"reps": 9, "weight_kg": 25.0, "source": "plan"}}}})
st.session_state.setdefault("tp_set_log", {{}})
st.session_state.setdefault("tp_notes", {{1: "Left side shook"}})
EXERCISES = [
    {{"name": "Goblet Squat", "type": "reps", "sets": 3, "reps": 10, "weight_kg": 22.5,
      "equipment_type": "dumbbell", "rest_seconds": 90}},
    {{"name": "Forearm Plank", "type": "hold", "sets": 2, "hold_seconds": 30,
      "rest_seconds": 30}},
]
if st.button("Save"):
    try:
        training._auto_log_session(1, EXERCISES, 6, 52, "Hips loose")
        st.session_state["_result"] = "saved"
    except Exception as exc:
        st.session_state["_result"] = "stopped after " + str(getattr(exc, "written", "?"))
    st.session_state["_pending"] = st.session_state.get("tp_pending_session")
'''


def test_a_save_that_stops_partway_is_completed_by_the_next_press(tmp_path):
    db = new_local_copy(tmp_path)
    try:
        at = AppTest.from_string(_SCRIPT.format(root=_ROOT, db=db), default_timeout=60)
        at.run()
        assert not at.exception, at.exception

        at.button[0].click().run()
        assert not at.exception, at.exception
        assert at.session_state["_result"] == "stopped after 1"
        pending = at.session_state["_pending"]
        assert pending and len(pending["exercise_ids"]) == 2

        at.button[0].click().run()
        assert not at.exception, at.exception
        assert at.session_state["_result"] == "saved"
        assert at.session_state["_pending"] is None          # spent, so the next session is new

        store = at.session_state["_store"]
        assert [r["session_id"] for r in store.tables["training_sessions"]] == [
            pending["session_id"]]
        assert sorted(r["exercise_id"] for r in store.tables["training_exercises"]) == sorted(
            pending["exercise_ids"])
        notes = {r["movement_name"]: r.get("notes") for r in store.tables["training_exercises"]}
        assert notes["Forearm Plank"] == "Left side shook\n\nHips loose"
        goblet = [s for s in store.tables["training_sets"]
                  if s["exercise_id"] == pending["exercise_ids"][0]]
        assert [(s["reps"], s["weight"]) for s in goblet] == [(9, 25.0)] * 3
    finally:
        record_cache.forget(db)
