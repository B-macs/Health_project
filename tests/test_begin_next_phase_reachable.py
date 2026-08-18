"""
tests/test_begin_next_phase_reachable.py — there must be a door out of the
reassessment gap. Since 2026-08-18 the door is a DATE, not a button.

THE ORIGINAL BUG (2026-08-17). The morning Stage 2B was due to start, the app
had no active phase and no way to create one: `_render_begin_next_phase_button`
was called only from the "plan complete" branch, which needs an ACTIVE phase,
while the screen that actually fires when a phase lapses rendered nothing
below its own promise of "Ready to begin the next block below". The fix added
the second call site, and these tests pinned both.

WHY THE BUTTON IS NOW GONE. It failed again the very next morning, in the
other direction. Day 2 of the block, the athlete opened the app, and a stale
mirror made it believe Stage 2A was still the newest phase — so the button
offered to begin Stage 2B starting the FOLLOWING Monday, and pressing it would
have written a second Phase 3 over the real one. A control whose whole job is
to create a block, driven by whatever the phase list happens to say, can
create the wrong one.

His instruction: "lets remove this begin button from now on, its not required,
blocks always start on a Monday and ill have them already in the system prior
to the monday so it is seemless."

THE DOOR THAT REPLACED IT. `plan.active_phase` now resolves on the DATE —
any phase whose range covers today and which is not 'completed'. A block
seeded ahead of time becomes today's block on its own start date, with nothing
to press and nothing to get wrong. The invariant these tests defend is
unchanged ("no wall without a door"); only the door moved, so this file is
rewritten rather than deleted.
"""

from __future__ import annotations

import ast
import pathlib
from datetime import date

import pytest

from services import plan as ph, sessions as sess
from services.models import Phase

_SRC = pathlib.Path(__file__).resolve().parent.parent / "views" / "training.py"
_TEXT = _SRC.read_text(encoding="utf-8")
_TREE = ast.parse(_TEXT)


def _phase(number, start, length, status, name=None):
    return Phase(phase_number=number, name=name or f"P{number}", start_date=start,
                 length_days=length, status=status, date_overrides={},
                 shift_reasons={})


# ── the door: a seeded block starts itself ──────────────────────────────────

def test_an_upcoming_block_activates_on_its_own_start_date():
    """THE WHOLE POINT. Seeded before its Monday, active on its Monday, with
    no press. Under the old status check this returned None and the athlete
    got the reassessment screen on day 1 of a block that existed."""
    seeded = _phase(4, "2026-09-14", 28, "upcoming")
    assert ph.active_phase([seeded], date(2026, 9, 13)) is None, "not before it starts"
    assert ph.active_phase([seeded], date(2026, 9, 14)) is seeded, "active on the day"
    assert ph.active_phase([seeded], date(2026, 10, 11)) is seeded, "still active on its last day"
    assert ph.active_phase([seeded], date(2026, 10, 12)) is None, "done after it ends"


def test_the_live_stage_2b_case_resolves_without_a_button():
    """The real stored list on the morning this changed."""
    phases = [
        _phase(1, "2026-06-29", 14, "completed", "Stage 1 Rehab"),
        _phase(2, "2026-07-20", 28, "completed", "Stage 2A"),
        _phase(3, "2026-08-17", 28, "active", "Stage 2B"),
    ]
    active = ph.active_phase(phases, date(2026, 8, 18))
    assert active is not None and active.phase_number == 3
    assert ph.day_number_in_phase(active, date(2026, 8, 18)) == 2


def test_a_completed_block_never_reactivates():
    """The one status that must still exclude. A block abandoned early keeps
    its nominal length, so its date range can still cover today — a pure date
    match would resurrect it. Marking it completed is how a block is ended
    before its calendar runs out, which is exactly what Stage 2A needed."""
    abandoned = _phase(2, "2026-08-03", 28, "completed")
    assert ph.active_phase([abandoned], date(2026, 8, 18)) is None


def test_two_live_phases_may_not_be_stored_overlapping(monkeypatch):
    """Date-based activation makes overlap ambiguous — active_phase would
    return whichever came first in the list. set_phases refuses instead."""
    from services.repository import Repository

    class _R:
        set_phases = Repository.set_phases
        _FLUSH_IMMEDIATELY = Repository._FLUSH_IMMEDIATELY

        def set_config(self, *a, **k):
            raise AssertionError("must refuse before writing")

    with pytest.raises(ph.WeekAlignmentError) as exc:
        _R().set_phases([_phase(3, "2026-08-17", 28, "active"),
                         _phase(4, "2026-09-07", 28, "upcoming")])
    assert "overlapping" in str(exc.value).lower()


def test_adjacent_blocks_are_fine():
    """Block A ends 2026-09-13, Block B starts 2026-09-14 — the real plan, and
    it must not trip the overlap guard."""
    from services.repository import Repository

    written = {}

    class _R:
        set_phases = Repository.set_phases
        _FLUSH_IMMEDIATELY = Repository._FLUSH_IMMEDIATELY

        def set_config(self, key, value, today=None):
            written[key] = value

    _R().set_phases([_phase(3, "2026-08-17", 28, "active"),
                     _phase(4, "2026-09-14", 28, "upcoming")])
    assert "phases" in written


# ── the button is gone, and stays gone ──────────────────────────────────────

@pytest.mark.parametrize("name", [
    "_render_begin_next_phase_button",
    "_stage2_offer_available",
    "_write_failure_detail",
])
def test_the_begin_block_machinery_is_removed(name):
    """Removed 2026-08-18. A control that creates a block from whatever the
    phase list says can create the wrong block — it tried to, the morning
    after it was made reachable."""
    assert name not in _TEXT, (
        f"{name} is back. Blocks are seeded ahead and activate by date; a "
        f"begin-block control would be a second, contradictory route in."
    )


def test_no_screen_asks_the_athlete_to_start_a_block():
    """The reassessment screen reports a gap now; it does not ask anyone to
    close one. A gap means exactly one thing: nothing was seeded."""
    for node in ast.walk(_TREE):
        if isinstance(node, ast.FunctionDef) and node.name == "_render_no_active_phase":
            src = ast.get_source_segment(_TEXT, node) or ""
            break
    else:
        raise AssertionError("_render_no_active_phase not found")
    assert "st.button" not in src
    # Matched on a contiguous fragment: the sentence is split across two
    # string literals in the source, and the first version of this test
    # searched for a phrase that spans the join and failed against correct
    # code — the same mistake as the mirror tests the same morning.
    assert "nothing to press" in src, (
        "the screen should say the next block needs no action"
    )


def test_phase_one_keeps_its_start_screen():
    """The one block that still needs a press, because it is the only one that
    has to ASK for a start date rather than being seeded with one."""
    assert "seed_default_phase" in _TEXT


# ── what seeds a block, now that no screen does ─────────────────────────────

def test_next_phase_offer_survives_as_the_seeding_helper():
    """It no longer drives a button, but it is still how a seeding script
    knows which block comes next — and it still refuses to skip one."""
    phases = [
        _phase(1, "2026-06-29", 14, "completed"),
        _phase(2, "2026-07-20", 28, "completed"),
        _phase(3, "2026-08-17", 28, "active"),
    ]
    # None TODAY, and for the right reason: Block B (phase 4) is not authored
    # yet, and next_phase_offer refuses to name a block whose content does not
    # exist. Seeding Block B therefore starts with authoring it, which is the
    # correct order and is what the day-28 review produces.
    assert sess.next_phase_offer(phases) is None
    assert 4 not in sess.PHASE_META, "when Block B is authored, update this test"
    # It still refuses to skip: with phase 3 absent it will not offer 3's slot
    # to a phase-4 block either.
    assert sess.next_phase_offer(phases[:1]) == 2
    assert sess.next_phase_offer([]) is None, "the first phase needs a start date"


def test_the_seeding_script_exists():
    """The replacement route has to be real, not a plan to type JSON into
    Notion by hand."""
    script = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "seed_next_block.py"
    assert script.exists(), "scripts/seed_next_block.py is the route that replaced the button"


def test_beginning_the_next_phase_retires_the_previous_one():
    """Still true and still needed: the seeding path marks a lapsed phase
    completed, which is what keeps the overlap guard satisfiable and stops a
    stale 'active' phase shadowing a new one."""
    existing = [_phase(3, "2026-08-17", 28, "active")]
    new = ph.default_phase(date(2026, 9, 14), length_days=28, phase_number=4,
                           name="Block B")
    result = sess.begin_new_phase(existing, new)
    assert [p.phase_number for p in result] == [3, 4]
