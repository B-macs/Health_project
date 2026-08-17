"""Per-exercise notes must SURVIVE to the save.

Written 2026-08-17, after the athlete reported losing notes for the second
time. The old code typed a note into a Streamlit widget keyed
`tp_note_<idx>` and read it back at save time from that same key. That never
worked, and the failure was invisible from the code:

  * Streamlit removes a widget's value from session_state on any run in which
    that widget is not instantiated.
  * views/training.py renders exactly ONE exercise per run (`_eidx` is
    `st.session_state.tp_ex_idx`).
  * The save screen is `tp_ex_idx >= n_ex`, where NO note widget exists.

So `_auto_log_session` read None for every index, always. The proof is in the
logged data rather than in any traceback: across all 24 sessions that carry a
note, not one carries TWO — because the only note that ever survived was the
session-wide field, stamped onto the last row by `save_session_notes`.

These tests pin the two properties that make notes durable: the notes live in
a plain dict, and that dict is checkpointed.
"""
import json

import pytest

from services import sessions as sess


# ── the durable store is checkpointed ────────────────────────────────────────

def test_tp_notes_is_a_checkpoint_field():
    """Without this a backgrounded phone loses every note — the SECOND,
    independent way they were being dropped."""
    assert "tp_notes" in sess.CHECKPOINT_FIELDS


def test_notes_round_trip_through_the_checkpoint():
    state = {k: None for k in sess.CHECKPOINT_FIELDS}
    state["tp_notes"] = {0: "capsule stretch did nothing at the back of the hip",
                         3: "no snapping at all today"}
    payload = sess.checkpoint_payload(7, state)

    # The checkpoint is JSON-encoded into Notion/local config, which is where
    # the int keys get stringified.
    restored = sess.restore_from_checkpoint(json.loads(json.dumps(payload)), 7)

    assert restored is not None
    notes = {int(k): v for k, v in restored["tp_notes"].items()}
    assert notes == {0: "capsule stretch did nothing at the back of the hip",
                     3: "no snapping at all today"}


def test_a_checkpoint_for_another_day_does_not_restore_notes():
    """A note written yesterday must never reappear on today's session."""
    state = {k: None for k in sess.CHECKPOINT_FIELDS}
    state["tp_notes"] = {0: "yesterday"}
    assert sess.restore_from_checkpoint(sess.checkpoint_payload(7, state), 8) is None


# ── the source itself: the regression that caused the loss ───────────────────

def _training_source() -> str:
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    return (root / "views" / "training.py").read_text(encoding="utf-8")


def test_the_save_does_not_read_notes_out_of_widget_state():
    """The exact regression. `_auto_log_session` runs on the save screen,
    where no note widget is instantiated, so reading `tp_note_<idx>` there
    can only ever yield None."""
    src = _training_source()
    start = src.index("def _auto_log_session")
    end = src.index("def _record_note")
    body = src[start:end]
    assert 'get(f"tp_note_' not in body, (
        "_auto_log_session must read tp_notes, not the tp_note_<idx> widget "
        "keys — those are garbage-collected before the save screen renders."
    )
    assert 'st.session_state.get("tp_notes"' in body


def test_the_note_widget_is_mirrored_into_the_durable_dict():
    """The widget may exist, but something has to copy its value out while it
    is still live."""
    src = _training_source()
    assert "on_change=_record_note" in src, (
        "the note text_area must mirror into tp_notes on change"
    )
    # ...and on every run, because a value typed and then abandoned by a tap
    # on "Complete set" arrives in the same batch as the button press.
    widget = src.index('key=_note_key')
    tail = src[widget:widget + 1200]
    assert "_record_note(_eidx, day_num)" in tail, (
        "the note must also be harvested on every run of the exercise screen"
    )


def test_the_widget_is_reseeded_from_the_durable_copy():
    """Going '← Back' to an exercise, or restoring a checkpoint, must put the
    existing note back in the box rather than showing it blank."""
    src = _training_source()
    assert "st.session_state.tp_notes.get(_eidx" in src


def test_tp_notes_has_an_init_default():
    """sess.CHECKPOINT_FIELDS is turned into a payload by indexing
    session_state with every name in it — a missing default silently stops the
    WHOLE checkpoint from saving, not just the notes."""
    src = _training_source()
    assert '"tp_notes":' in src


def test_note_int_keys_are_restored_from_json():
    """Same hazard tp_actuals/tp_set_log already carry: JSON turns the int
    exercise index into a string, and every lookup then misses."""
    src = _training_source()
    assert '("tp_actuals", "tp_set_log", "tp_notes")' in src


def test_a_stale_accessory_session_clears_its_notes():
    src = _training_source()
    start = src.index("_acc_day = st.session_state.get")
    assert '"tp_actuals", "tp_set_log", "tp_notes"' in src[start:start + 700]


# ── behaviour of the mirror itself ───────────────────────────────────────────

class _FakeState(dict):
    """Enough of st.session_state for _record_note's logic."""
    def __getattr__(self, k):
        return self[k]


@pytest.mark.parametrize("typed,expected", [
    ("  no snapping today  ", {2: "no snapping today"}),   # trimmed
    ("", {}),                                              # blank clears
    ("   ", {}),                                           # whitespace clears
])
def test_mirror_semantics(typed, expected):
    """Reimplements _record_note's core so the contract is pinned without a
    Streamlit runtime: a note is stored trimmed, and clearing the box REMOVES
    the entry rather than storing an empty string that would later be joined
    into the saved note as a stray blank line."""
    state = _FakeState({"tp_notes": {}, "tp_note_2": typed})
    text = (state.get("tp_note_2") or "").strip()
    if text:
        state["tp_notes"][2] = text
    else:
        state["tp_notes"].pop(2, None)
    assert state["tp_notes"] == expected
