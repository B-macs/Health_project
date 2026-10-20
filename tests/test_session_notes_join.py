"""The session notes a save stores (rebuild Phase 7): the session plan's own
note first, then what the athlete typed (sessions.join_notes).

The accessory session writes why it was chosen into the session note, so an
upper-body accessory day that could confound the interscapular reading says so
in the record. The Streamlit page joined the two in its view; the phone sends
the plan's note beside the typed one (`plan_note`), and the engine joins them
with the same function, so the two apps store the same text.
"""

from __future__ import annotations

from pathlib import Path

from services import sessions as sess
from services import training_session as tsession

ROOT = Path(__file__).resolve().parent.parent


def test_the_plan_note_comes_first_then_what_was_typed():
    assert sess.join_notes("Chosen for the upper body.", "  felt easy  ") == (
        "Chosen for the upper body.\nfelt easy")


def test_either_side_may_be_empty():
    assert sess.join_notes("", "felt easy") == "felt easy"
    assert sess.join_notes("Chosen for the upper body.", "   ") == "Chosen for the upper body."
    assert sess.join_notes("", "") == ""


def _body(**extra) -> dict:
    return {"session_id": "2026-10-20-acc00001", "date": "2026-10-20", "kind": "accessory",
            "duration_minutes": 12, "session_rpe": 3, "exercises": [{
                "exercise_id": "ex-acc-1",
                "exercise": {"name": "Dead Bug", "type": "reps", "sets": 2, "reps": 8}}],
            **extra}


def test_the_save_stores_the_plan_note_before_the_typed_notes():
    saved = tsession.build_save(_body(plan_note="Chosen for the upper body.", notes="felt easy"))
    assert saved.notes == "Chosen for the upper body.\nfelt easy"


def test_a_save_without_a_plan_note_keeps_the_typed_notes():
    assert tsession.build_save(_body(notes="felt easy")).notes == "felt easy"


def test_the_streamlit_accessory_save_joins_with_the_same_function():
    source = (ROOT / "views" / "training.py").read_text(encoding="utf-8")
    assert 'sess.join_notes(day.get("accessory_note") or "", extra)' in source
