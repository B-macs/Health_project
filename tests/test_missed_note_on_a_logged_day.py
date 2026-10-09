"""A "missed" note is not shown on a day that has a logged session.

2026-10-09: a restart rebuilt the hosted app's data without three sessions,
the app offered to move two of them, the athlete pressed "Leave as missed",
and "Declined: left as missed by choice" then stood on two days he had
trained. Such a note can only have been written while the app could not see
the session, so services.scheduling.shift_note withholds it on a logged day,
and only it: a note that stays true is still shown.
"""
from pathlib import Path

from services import scheduling

ROOT = Path(__file__).resolve().parent.parent
LEFT = scheduling.DECLINED_REASON_PREFIX + scheduling.LEFT_AS_MISSED


def test_left_as_missed_is_withheld_on_a_logged_day():
    assert scheduling.shift_note({"2026-10-06": LEFT}, "2026-10-06", logged=True) is None


def test_not_rescheduled_is_withheld_on_a_logged_day():
    note = scheduling.DROPPED_REASON_PREFIX + "no free lower-priority day this week"
    assert scheduling.shift_note({"2026-10-08": note}, "2026-10-08", logged=True) is None


def test_the_same_notes_still_show_on_a_day_with_no_session():
    assert scheduling.shift_note({"2026-10-06": LEFT}, "2026-10-06", logged=False) == LEFT


def test_a_note_that_stays_true_is_still_shown_on_a_logged_day():
    for note in (scheduling.DECLINED_REASON_PREFIX + "sleep debt over 3 h",
                 scheduling.HELD_REASON_PREFIX + "next day already loaded",
                 "Moved from 2026-09-21 (missed)"):
        assert scheduling.shift_note({"2026-10-07": note}, "2026-10-07", logged=True) == note


def test_the_page_passes_the_logged_days_and_writes_the_shared_text():
    src = (ROOT / "views" / "training.py").read_text(encoding="utf-8")
    assert "_render_shift_banner(active, _selected, logged=_selected.isoformat() in _logged)" in src
    assert "scheduling.shift_note(" in src
    assert "scheduling.LEFT_AS_MISSED" in src
    assert '"left as missed by choice"' not in src
