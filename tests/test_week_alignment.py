"""
tests/test_week_alignment.py — every block runs Monday to Sunday.

Athlete's rule, 2026-08-17: a block must start on a Monday and end on a
Sunday, and it must be impossible for one to push into the following week by
a day or two.

WHY THIS IS STRUCTURAL AND NOT TIDINESS. services/plan.py's
week_of_phase_date counts weeks from the PHASE START, not from calendar
Mondays. Key rule 18b — "a rescheduled day moves within its week or not at
all" — is expressed in those weeks. So a block that starts on a Tuesday has
Tue-Mon "weeks" that straddle every calendar weekend, and the single guard
against a block drifting into the next week silently begins guarding the
wrong boundary. The alignment and 18b are one rule; this file pins the half
that was documented ("a fixed-length, multiple-of-7-days training block") but
never enforced.

The hole was reachable: default_phase accepted any date, and the begin-block
button passed date.today() — whichever day it happened to be pressed. Stage
2B was begun on a Monday by luck, not by construction.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from services import plan as ph
from services import sessions as sess
from services.models import Phase

MON = date(2026, 8, 17)


# ─── the invariant itself ─────────────────────────────────────────────────

def test_a_monday_start_and_whole_weeks_are_accepted():
    p = ph.default_phase(MON, length_days=28, phase_number=3, name="Stage 2B")
    assert p.start_date == "2026-08-17"
    assert ph.phase_end_date(p) == date(2026, 9, 13)
    assert ph.phase_end_date(p).weekday() == 6, "must end on a Sunday"


@pytest.mark.parametrize("offset,day", [
    (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"),
    (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
])
def test_every_non_monday_start_is_refused(offset, day):
    with pytest.raises(ph.WeekAlignmentError, match="must start on a Monday"):
        ph.default_phase(MON + timedelta(days=offset), length_days=28)


@pytest.mark.parametrize("length", [1, 6, 8, 13, 26, 27, 29, 30])
def test_a_length_that_is_not_whole_weeks_is_refused(length):
    """26 is the live case: Stage 2A had 28 authored days but only 26
    reachable after two stranded entries were removed. Storing that as the
    length would have ended the block on a Friday."""
    with pytest.raises(ph.WeekAlignmentError, match="ends on a Sunday"):
        ph.default_phase(MON, length_days=length)


def test_zero_and_negative_lengths_are_refused():
    for bad in (0, -7):
        with pytest.raises(ph.WeekAlignmentError):
            ph.default_phase(MON, length_days=bad)


def test_both_faults_are_reported_together():
    """A bare False would send the reader to check both halves; "starts on a
    Tuesday" and "is 26 days long" need different fixes."""
    errs = ph.week_alignment_errors(MON + timedelta(days=1), 26)
    assert len(errs) == 2
    assert any("Monday" in e for e in errs) and any("Sunday" in e for e in errs)


def test_the_error_names_the_actual_weekday():
    errs = ph.week_alignment_errors(date(2026, 8, 19), 28)
    assert "Wednesday" in errs[0], "naming the day is what makes the fix obvious"


# ─── refused, never clamped ───────────────────────────────────────────────

def test_a_bad_start_raises_rather_than_being_moved_to_a_monday():
    """Silently shifting the start moves every authored day onto a different
    date; silently padding the length invents sessions. Both are worse than a
    refusal the athlete can see — the same reasoning as
    reject_violating_overrides."""
    with pytest.raises(ph.WeekAlignmentError):
        ph.default_phase(date(2026, 8, 18), length_days=28)


# ─── next_block_start ─────────────────────────────────────────────────────

def test_next_block_start_is_today_when_today_is_monday():
    assert ph.next_block_start(MON) == MON


@pytest.mark.parametrize("offset,expected_offset", [
    (1, 6), (2, 5), (3, 4), (4, 3), (5, 2), (6, 1),
])
def test_next_block_start_goes_forward_never_back(offset, expected_offset):
    """Rewinding to the Monday just past would make the block already
    underway, skipping authored days 1..N that were never presented. A
    forward gap is visible on the calendar and can be discussed."""
    got = ph.next_block_start(MON + timedelta(days=offset))
    assert got == MON + timedelta(days=offset + expected_offset)
    assert got.weekday() == 0
    assert got > MON + timedelta(days=offset)


def test_next_block_start_always_yields_a_constructible_phase():
    for i in range(14):
        start = ph.next_block_start(MON + timedelta(days=i))
        ph.default_phase(start, length_days=28)   # must not raise


# ─── every authored block is a whole number of weeks ──────────────────────

@pytest.mark.parametrize("phase_number", sorted(sess.PHASE_META))
def test_every_authored_plan_is_a_whole_number_of_weeks(phase_number):
    """The length the begin-block button uses comes from the authored content
    (`len(plan_dict_for_phase)`), so a plan authored with a non-multiple of 7
    would make the button un-pressable. Catch it here rather than at the
    click."""
    days = len(sess.plan_dict_for_phase(phase_number))
    assert days and days % 7 == 0, (
        f"phase {phase_number} has {days} authored days, which cannot end on a Sunday"
    )


def test_the_authored_plans_have_contiguous_day_numbers():
    """A gap would make len() disagree with the highest day number, so the
    stored length_days would not describe the content it indexes."""
    for phase_number in sess.PHASE_META:
        plan = sess.plan_dict_for_phase(phase_number)
        assert sorted(plan) == list(range(1, len(plan) + 1)), (
            f"phase {phase_number} day numbers are not 1..N"
        )


# ─── the drift this prevents ──────────────────────────────────────────────

def test_a_monday_block_makes_block_weeks_equal_calendar_weeks():
    """The reason the alignment IS key rule 18b: week_of_phase_date counts
    from the start, so only a Monday start makes 'week' mean Mon-Sun."""
    p = ph.default_phase(MON, length_days=28)
    for i in range(28):
        d = MON + timedelta(days=i)
        block_week = ph.week_of_phase_date(p, d)
        calendar_week = (d - (d - timedelta(days=d.weekday()))).days  # 0..6 within week
        assert calendar_week == (d - MON).days % 7
        assert block_week == (d - MON).days // 7 + 1
        # the week's Monday, derived either way, must agree
        assert d - timedelta(days=d.weekday()) == MON + timedelta(days=7 * (block_week - 1))


def test_an_override_cannot_push_a_day_into_the_following_week():
    """The 18b guard, restated against an aligned block: day 7 (Sunday of week
    1) may not be moved to Monday of week 2."""
    p = ph.default_phase(MON, length_days=28, phase_number=3, name="Stage 2B")
    allowed, rejected = ph.reject_violating_overrides(
        p, {(MON + timedelta(days=7)).isoformat(): 7})
    assert allowed == {}
    assert rejected and rejected[0]["rule"] == "crossed_week"


def test_an_override_cannot_point_past_the_blocks_last_sunday():
    p = ph.default_phase(MON, length_days=28, phase_number=3, name="Stage 2B")
    beyond = ph.phase_end_date(p) + timedelta(days=1)
    allowed, rejected = ph.reject_violating_overrides(p, {beyond.isoformat(): 28})
    assert allowed == {}
    assert rejected[0]["rule"] == "past_block_end"


def test_a_forced_rest_is_still_allowed_anywhere():
    """0 schedules nothing, so it can break neither rule."""
    p = ph.default_phase(MON, length_days=28)
    allowed, rejected = ph.reject_violating_overrides(
        p, {(MON + timedelta(days=9)).isoformat(): 0})
    assert rejected == [] and allowed


# ─── the persistence gate ─────────────────────────────────────────────────

def _repo(monkeypatch):
    from services.config import Config
    from services.repository import Repository

    repo = Repository(Config(
        notion_api_key="k", notion_db_readiness="r", notion_db_training="t",
        notion_db_config="c", google_sheets_id="s",
        google_service_account={"type": "service_account"}))
    monkeypatch.setattr(Repository, "set_config", lambda self, k, v, today=None: None)
    return repo


def test_set_phases_refuses_a_misaligned_phase(monkeypatch):
    """The constructor check alone can be walked around — by building a Phase
    directly, by an edit made in the Notion UI and re-saved, or by a future
    caller that assembles the dataclass itself. This is the only way a phase
    reaches storage."""
    repo = _repo(monkeypatch)
    bad = Phase(phase_number=3, name="Stage 2B", start_date="2026-08-18",
                length_days=28, status="active", date_overrides={}, shift_reasons={})
    with pytest.raises(ph.WeekAlignmentError, match="phase 3"):
        repo.set_phases([bad])


def test_set_phases_refuses_a_non_whole_week_length(monkeypatch):
    repo = _repo(monkeypatch)
    bad = Phase(phase_number=3, name="Stage 2B", start_date="2026-08-17",
                length_days=26, status="active", date_overrides={}, shift_reasons={})
    with pytest.raises(ph.WeekAlignmentError):
        repo.set_phases([bad])


def test_set_phases_refuses_an_unreadable_start_date(monkeypatch):
    repo = _repo(monkeypatch)
    bad = Phase(phase_number=3, name="x", start_date="not-a-date",
                length_days=28, status="active", date_overrides={}, shift_reasons={})
    with pytest.raises(ph.WeekAlignmentError, match="unreadable"):
        repo.set_phases([bad])


def test_the_live_phases_all_satisfy_the_rule():
    """The two real stored phases. If either failed, adding this gate would
    have locked the athlete out of every reschedule."""
    live = [
        ("Stage 1 Rehab", date(2026, 6, 29), 14),
        ("Stage 2A", date(2026, 7, 20), 28),
        ("Stage 2B", date(2026, 8, 17), 28),
    ]
    for name, start, length in live:
        assert ph.week_alignment_errors(start, length) == [], name
        assert (start + timedelta(days=length - 1)).weekday() == 6, f"{name} ends Sunday"


def test_the_two_race_blocks_tile_exactly_onto_race_day():
    """Block A 2026-08-17..09-13, Block B 09-14..10-11 = race day. Both
    Monday-aligned and contiguous, which only works because both are whole
    weeks."""
    a = ph.default_phase(date(2026, 8, 17), length_days=28, phase_number=3, name="A")
    b_start = ph.phase_end_date(a) + timedelta(days=1)
    assert b_start.weekday() == 0, "Block B must also start on a Monday"
    b = ph.default_phase(b_start, length_days=28, phase_number=4, name="B")
    assert ph.phase_end_date(b) == date(2026, 10, 11), "race day"
    assert ph.phase_end_date(b).weekday() == 6
