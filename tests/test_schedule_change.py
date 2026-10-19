"""services/scheduling.apply_schedule_change: the one write path for a move.

The manual swap, the missed-session carry and the readiness shift all change
`date_overrides` through it (moved out of views/training.py on 2026-10-19), and
the phone's API will too. What it pins:

  * a change Key Rule 18b allows is stored with its reasons, and no other
    phase changes;
  * a refused change stores nothing, and no reason: before the move, the
    page merged every reason even for a refused move, so a day that did not
    move could say "Session moved" (inventory fault F2);
  * a change is applied whole or not at all: with today a forced rest, a
    swap with a day in another week used to be applied half, and the swapped
    session disappeared from the schedule (inventory fault F22);
  * a declined proposal (a record, no move) is stored, so the prompt does
    not return.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from services import plan as ph
from services import scheduling

MON = date(2026, 10, 19)                       # the 12-week block's first Monday


def _block(**changes):
    return replace(ph.default_phase(MON, length_days=84, phase_number=5,
                                    name="12-week block"), **changes)


def _days(phase) -> list[int]:
    """The plan day on each date of the block, in date order."""
    return [ph.day_number_in_phase(phase, MON + timedelta(days=i))
            for i in range(phase.length_days)]


def test_an_allowed_change_is_stored_with_its_reasons_and_other_phases_are_untouched():
    block = _block()
    earlier = replace(ph.default_phase(MON - timedelta(days=28), length_days=28,
                                       phase_number=4, name="Block B"), status="completed")
    today, other = MON + timedelta(days=2), MON + timedelta(days=4)
    overrides, reasons = scheduling.manual_swap_entries(block, other, today)
    phases, rejected = scheduling.apply_schedule_change([earlier, block], block,
                                                        overrides, reasons)
    assert rejected == []
    assert phases[0] is earlier
    assert phases[1].date_overrides == overrides and phases[1].shift_reasons == reasons
    assert (ph.day_number_in_phase(phases[1], today),
            ph.day_number_in_phase(phases[1], other)) == (5, 3)


def test_a_refused_change_writes_nothing_and_records_no_reason():
    """F2: the page used to merge the reason of a move the rule had refused."""
    block = _block()
    next_monday = (MON + timedelta(days=7)).isoformat()
    phases, rejected = scheduling.apply_schedule_change(
        [block], block, {next_monday: 7}, {next_monday: "Carried forward from Sunday"})
    assert phases == [block]
    assert phases[0].shift_reasons == {} and phases[0].date_overrides == {}
    assert [r["rule"] for r in rejected] == ["crossed_week"]


def test_a_swap_refused_on_one_side_is_refused_whole_and_no_session_is_lost():
    """F22. Today (Wednesday, week 1) is a forced rest; the athlete swaps it with
    Monday of week 2 (day 8). The rest may move anywhere, so that side passed;
    day 8 may not land in week 1, so today's side was refused. Applied half,
    day 8's date became a rest and today stayed one: day 8 was in no date."""
    block = _block(date_overrides={"2026-10-21": 0})
    overrides, reasons = scheduling.manual_swap_entries(block, date(2026, 10, 26),
                                                        date(2026, 10, 21))
    assert overrides == {"2026-10-26": 0, "2026-10-21": 8}
    half, _refused = ph.reject_violating_overrides(block, overrides)
    assert 8 not in _days(replace(block, date_overrides={**block.date_overrides, **half}))

    phases, rejected = scheduling.apply_schedule_change([block], block, overrides, reasons)
    assert phases == [block]
    assert [r["date"] for r in rejected] == ["2026-10-21"]
    assert 8 in _days(phases[0])


def test_a_declined_proposal_is_recorded_so_the_prompt_does_not_return():
    block = _block()
    wednesday = MON + timedelta(days=2)
    overrides, reasons = scheduling.declined_entries(block, [wednesday], "Short sleep")
    phases, rejected = scheduling.apply_schedule_change([block], block, overrides, reasons)
    assert rejected == []
    assert wednesday.isoformat() in phases[0].shift_reasons
    assert _days(phases[0]) == _days(block)                 # nothing moved
