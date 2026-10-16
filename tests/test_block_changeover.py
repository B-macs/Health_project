"""The 12-week block replaces Block B (services/block_changeover.py).

The athlete, 2026-10-16: "When we push this new session block that will be 12
weeks long, it will overwrite all of the current block ... it starts on the
next monday." On goal_block.START Block B ends the day before, its last week
is recorded as not judged (so the failed-week rule cannot repeat it and move
the new block), and the 12-week block runs from START.
"""
from dataclasses import replace
from datetime import date, timedelta

import pytest

import goal_block as gb
from services import block_changeover as bc
from services import plan as ph
from services import sessions as sess
from services import week_repeat

START = date(2026, 10, 19)
B_START = date(2026, 9, 21)


def _block_b(weeks=(1, 1, 1, 2, 3, 4), **extra):
    """Block B as stored after its repeats: six calendar weeks from 2026-09-21."""
    base = sess.build_phase(4, B_START, status="active")
    return replace(base, length_days=7 * len(weeks), week_plan=list(weeks), **extra)


def _older():
    return [replace(sess.build_phase(3, date(2026, 8, 17), status="completed"),
                    length_days=35, week_plan=[1, 2, 3, 4, 4])]


def _storable(phases):
    """Repository.set_phases' own checks: week alignment, a week plan that
    describes the block, and no two live blocks overlapping."""
    for p in phases:
        assert not ph.week_alignment_errors(date.fromisoformat(p.start_date), p.length_days), p
        if p.week_plan is not None:
            assert len(p.week_plan) * 7 == p.length_days, p
    live = sorted((date.fromisoformat(p.start_date), ph.phase_end_date(p))
                  for p in phases if p.status != "completed")
    for (_, a_end), (b_start, _) in zip(live, live[1:]):
        assert b_start > a_end


def test_the_start_is_the_monday_after_the_push():
    assert gb.START == START and gb.START.weekday() == 0


def test_block_b_ends_the_day_before_and_the_block_starts_on_start():
    phases = _older() + [_block_b()]
    out = bc.changeover(phases, START)
    _storable(out)
    b = next(p for p in out if p.phase_number == 4)
    new = next(p for p in out if p.phase_number == 5)
    assert ph.phase_end_date(b) == START - timedelta(days=1)
    assert b.length_days == 28 and b.week_plan == [1, 1, 1, 2]
    assert date.fromisoformat(new.start_date) == START
    assert new.length_days == 84 and new.status == "upcoming" and new.week_plan is None
    assert len(sess.calendar_plan(new)) == 84


def test_the_weeks_block_b_ran_keep_their_day_numbers():
    before = _block_b()
    after = next(p for p in bc.changeover([before], START) if p.phase_number == 4)
    d = B_START
    while d < START:
        assert ph.day_number_in_phase(after, d) == ph.day_number_in_phase(before, d), d
        d += timedelta(days=1)
    for d in (START, START + timedelta(days=5)):
        assert ph.active_phase(bc.changeover([before], START), d).phase_number == 5


def test_moves_after_the_end_go_and_the_ones_before_stay():
    b = _block_b(date_overrides={"2026-10-14": 9, "2026-10-21": 0},
                 shift_reasons={"2026-10-14": "moved", "2026-10-22": "later"})
    out = next(p for p in bc.changeover([b], START) if p.phase_number == 4)
    assert out.date_overrides == {"2026-10-14": 9}
    assert out.shift_reasons == {"2026-10-14": "moved"}


def test_block_b_s_last_week_cannot_be_repeated_into_the_new_block():
    """With no session logged in Block B's last week, the failed-week rule
    would repeat it and start the new block a week late. Recorded as not
    judged, the week is skipped and the block stays on START."""
    out = bc.changeover([_block_b()], START)
    b = next(p for p in out if p.phase_number == 4)
    assert b.week_results["2026-10-12"] == bc.REPLACED_OUTCOME
    logged = {"2026-09-22", "2026-09-23", "2026-09-24", "2026-09-29", "2026-09-30",
              "2026-10-01", "2026-10-06", "2026-10-07", "2026-10-08"}
    judged, events = week_repeat.apply_failed_week_rule(out, logged, START + timedelta(days=1))
    assert "2026-10-12" not in {m for m, _ in events}
    assert next(p for p in judged if p.phase_number == 5).start_date == START.isoformat()


def test_it_runs_once():
    out = bc.changeover([_block_b()], START)
    assert bc.changeover(out, START) is None
    assert bc.due(out) is None


def test_no_block_b_means_nothing_to_replace():
    assert bc.changeover(_older(), START) is None


def test_a_block_b_that_already_ended_is_left_as_it_is():
    short = _block_b(weeks=(1, 2, 3, 4))          # ends 2026-10-18 already
    out = bc.changeover([short], START)
    b = next(p for p in out if p.phase_number == 4)
    assert b.length_days == 28 and b.week_plan == [1, 2, 3, 4]
    _storable(out)


def test_the_start_must_be_a_monday_inside_block_b_s_reach():
    with pytest.raises(ValueError):
        bc.changeover([_block_b()], START + timedelta(days=1))
    with pytest.raises(ValueError):
        bc.changeover([_block_b()], B_START - timedelta(days=7))


def test_the_training_page_runs_it_before_the_failed_week_rule():
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "views" / "training.py").read_text(
        encoding="utf-8")
    assert src.index("block_changeover.due(") < src.index("week_repeat.apply_failed_week_rule(")
    block = src[src.index("block_changeover.due("):src.index("week_repeat.apply_failed_week_rule(")]
    assert "get_phases_live()" in block, "the write must be rebuilt from a live read"
