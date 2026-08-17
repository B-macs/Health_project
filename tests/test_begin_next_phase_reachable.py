"""
tests/test_begin_next_phase_reachable.py — there must be a door out of the
reassessment gap.

THE BUG. On 2026-08-17, the morning Stage 2B was due to start, the app had no
active phase and no way to create one. Stage 2A's calendar had lapsed the day
before, so views/training.py rendered _render_no_active_phase — a screen whose
own text reads "Ready to begin the next block below" and which then rendered
nothing below. `_render_begin_next_phase_button` was called from exactly one
place: the "plan complete" branch, reached only when `day_num > _plan_days` on
an ACTIVE phase. A lapsed phase is not active, so that branch was unreachable
precisely when it was needed.

The button's own docstring claimed it was "called from both" and even named
the reassessment screen as the one that fires in practice. Prose is not a call
site, which is why this is a test.

It is the "no wall without a door" class of failure: every gate between the
athlete and training needs a way through, and the way through must be on the
screen that actually renders.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

_SRC = pathlib.Path(__file__).resolve().parent.parent / "views" / "training.py"
_TREE = ast.parse(_SRC.read_text(encoding="utf-8"))


def _func(name: str) -> ast.FunctionDef:
    for node in ast.walk(_TREE):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in views/training.py")


def _calls_within(func: ast.FunctionDef) -> set[str]:
    out = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            out.add(node.func.id)
    return out


def test_the_reassessment_screen_offers_the_next_block():
    """The screen that actually fires when a phase lapses must render the
    button. This is the one that was missing."""
    assert "_render_begin_next_phase_button" in _calls_within(
        _func("_render_no_active_phase")
    ), (
        "_render_no_active_phase tells the athlete the next block is ready "
        "'below' and must actually put it there — without this the app has no "
        "route to a new phase once the old one lapses"
    )


def test_the_plan_complete_screen_still_offers_it():
    """The original call site. Kept so a fix to one does not quietly move the
    door rather than adding a second one."""
    src = ast.get_source_segment(_SRC.read_text(encoding="utf-8"), _func("render")) or ""
    assert "_render_begin_next_phase_button" in src, (
        "the plan-complete branch must keep offering the next block"
    )


def test_the_button_is_reachable_from_at_least_two_screens():
    whole = _SRC.read_text(encoding="utf-8")
    calls = whole.count("_render_begin_next_phase_button(")
    # one def + at least two call sites
    assert calls >= 3, (
        f"expected the begin-block button to be called from at least two screens, "
        f"found {calls - 1} call site(s)"
    )


def test_a_lapsed_phase_is_not_active_which_is_why_this_matters():
    """Pins the premise. If a lapsed phase were still 'active' the
    plan-complete branch would cover it and none of the above would be
    load-bearing."""
    from datetime import date

    from services import plan as ph
    from services.models import Phase

    lapsed = Phase(phase_number=2, name="Stage 2A", start_date="2026-07-20",
                   length_days=28, status="active", date_overrides={},
                   shift_reasons={})
    assert ph.active_phase([lapsed], date(2026, 8, 17)) is None


def test_the_offer_exists_for_the_real_stage_2b_case():
    """The concrete situation: phases 1 and 2 stored, 2B unstarted. The old
    hard-wired check returned False here forever."""
    from services import sessions as sess
    from services.models import Phase

    phases = [
        Phase(phase_number=1, name="Stage 1 Rehab", start_date="2026-06-29",
              length_days=14, status="completed", date_overrides={}, shift_reasons={}),
        Phase(phase_number=2, name="Stage 2A", start_date="2026-07-20",
              length_days=28, status="active", date_overrides={}, shift_reasons={}),
    ]
    assert sess.next_phase_offer(phases) == 3
    meta = sess.PHASE_META[3]
    assert meta["stage"] == 2, "Stage 2B is a new BLOCK at the same clinical stage"
    assert len(sess.plan_dict_for_phase(3)) == 28


@pytest.mark.parametrize("phase_number", [1, 2])
def test_beginning_the_next_phase_retires_the_previous_one(phase_number):
    """A lapsed phase left 'active' alongside a new one would make
    active_phase's answer depend on list order."""
    from datetime import date

    from services import plan as ph, sessions as sess
    from services.models import Phase

    existing = [Phase(phase_number=n, name=f"P{n}", start_date="2026-06-29",
                      length_days=14, status="active", date_overrides={},
                      shift_reasons={})
                for n in range(1, phase_number + 1)]
    new = ph.default_phase(date(2026, 8, 17), length_days=28,
                           phase_number=phase_number + 1, name="next")
    result = sess.begin_new_phase(existing, new)
    actives = [p.phase_number for p in result if p.status == "active"]
    assert actives == [phase_number + 1], f"exactly one active phase, got {actives}"
