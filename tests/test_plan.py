"""
Tests for services/plan.py — Phase model, ported from the original phase.py
tests (tests.py). Same cases, updated for dataclass attribute access instead
of dict-key access now that Phase/DayCell are typed.
"""

import ast
from datetime import date, timedelta

from services import plan
from services.models import Phase


def test_no_streamlit_import():
    tree = ast.parse(open(plan.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"


# ─── day_number_in_phase ────────────────────────────────────────────────────

p14 = plan.default_phase(date(2026, 6, 29), length_days=14, phase_number=1, name="Stage 1 Rehab")

# Anchor the 28-day phase's start to a real Monday: week-paging math only spans
# exactly 4 calendar weeks when a 4-week block starts on a Monday — a misaligned
# start genuinely touches 5 calendar weeks (correct for a real Mon-Sun strip,
# not a bug). Deriving the Monday avoids needing to know 2026-09-01's weekday.
_p28_start = date(2026, 9, 1) - timedelta(days=date(2026, 9, 1).weekday())
p28 = plan.default_phase(_p28_start, length_days=28, phase_number=2, name="Stage 2")


def test_day_1_of_14_day_phase():
    assert plan.day_number_in_phase(p14, date(2026, 6, 29)) == 1


def test_day_14_last_of_14_day_phase():
    assert plan.day_number_in_phase(p14, date(2026, 7, 12)) == 14


def test_day_15_past_end_of_14_day_phase():
    assert plan.day_number_in_phase(p14, date(2026, 7, 13)) == 15


def test_day_1_of_28_day_phase():
    assert plan.day_number_in_phase(p28, _p28_start) == 1


def test_day_28_last_of_28_day_phase():
    assert plan.day_number_in_phase(p28, _p28_start + timedelta(days=27)) == 28


# ─── active_phase (reassessment gaps) ───────────────────────────────────────

# Phase 1: 2026-06-29 .. 2026-07-12 (14 days). Gap. Phase 2 starts 2026-07-20.
p1 = plan.default_phase(date(2026, 6, 29), length_days=14, phase_number=1, name="Stage 1 Rehab")
p2 = plan.default_phase(date(2026, 7, 20), length_days=28, phase_number=2, name="Stage 2")
phases = [p1, p2]


def test_mid_phase_1_date_resolves_to_phase_1():
    assert plan.active_phase(phases, date(2026, 7, 5)).phase_number == 1


def test_phase_1_last_day_still_resolves_to_phase_1():
    assert plan.active_phase(phases, date(2026, 7, 12)).phase_number == 1


def test_day_after_phase_1_ends_before_phase_2_starts_is_a_gap():
    assert plan.active_phase(phases, date(2026, 7, 13)) is None


def test_day_before_phase_2_starts_is_still_a_gap():
    assert plan.active_phase(phases, date(2026, 7, 19)) is None


def test_phase_2_start_date_resolves_to_phase_2():
    assert plan.active_phase(phases, date(2026, 7, 20)).phase_number == 2


def test_no_phases_configured_at_all_returns_none():
    assert plan.active_phase([], date(2026, 7, 5)) is None


def test_completed_status_phase_is_never_returned_as_active():
    p1_completed = Phase(p1.phase_number, p1.name, p1.start_date, p1.length_days, "completed")
    assert plan.active_phase([p1_completed], date(2026, 7, 5)) is None


# ─── phase_week_bounds / clamp_week_start ───────────────────────────────────

lo, hi = plan.phase_week_bounds(p14)


def test_phase_week_bounds_lo_is_a_monday():
    assert lo.weekday() == 0


def test_phase_week_bounds_hi_is_a_monday():
    assert hi.weekday() == 0


def test_los_week_contains_the_phase_start_date():
    assert lo <= date(2026, 6, 29) <= lo + timedelta(days=6)


def test_his_week_contains_the_phases_last_day():
    assert hi <= date(2026, 7, 12) <= hi + timedelta(days=6)


def test_28_day_phase_spans_exactly_4_week_pages():
    lo28, hi28 = plan.phase_week_bounds(p28)
    assert (hi28 - lo28).days // 7 + 1 == 4


def test_clamp_candidate_before_phase_start_clamps_to_lo():
    assert plan.clamp_week_start(lo - timedelta(days=21), p14) == lo


def test_clamp_candidate_after_phase_end_clamps_to_hi():
    assert plan.clamp_week_start(hi + timedelta(days=21), p14) == hi


def test_clamp_candidate_within_range_passes_through_unchanged():
    mid_week = lo + timedelta(days=7)
    assert plan.clamp_week_start(mid_week, p14) == mid_week


# ─── get_week_view state derivation ─────────────────────────────────────────

# Test week starts exactly on the phase's day 1 -- sidesteps needing to know
# the real-world weekday of any date; get_week_view doesn't require week_start
# to be a Monday (that convention is enforced by the caller via phase_week_bounds).
_p_start = date.fromisoformat(p14.start_date)
_sessions = [{"date": (_p_start + timedelta(days=1)).isoformat()}]  # day 2 logged
_fake_today = _p_start + timedelta(days=3)  # day 4 is "today"

cells = plan.get_week_view(_p_start, p14, _sessions, today=_fake_today)


def test_get_week_view_returns_7_cells():
    assert len(cells) == 7


def test_day_1_past_unlogged_in_phase_is_missed():
    assert cells[0].state == "missed"


def test_day_2_past_logged_is_completed():
    assert cells[1].state == "completed"


def test_day_2_session_ref_matches_the_logged_record():
    assert cells[1].session_ref["date"] == _sessions[0]["date"]


def test_day_3_past_unlogged_is_missed():
    assert cells[2].state == "missed"


def test_day_4_is_today_unlogged_is_planned():
    assert cells[3].state == "planned"


def test_day_4_has_no_session_ref():
    assert cells[3].session_ref is None


def test_day_7_future_in_phase_is_planned():
    assert cells[6].state == "planned"


def test_day_number_in_phase_populated_for_an_in_phase_cell():
    assert cells[0].day_number_in_phase == 1


def test_week_entirely_before_phase_start_is_all_rest():
    outside_week_start = _p_start - timedelta(days=21)  # 3 weeks before phase start
    outside_cells = plan.get_week_view(outside_week_start, p14, [], today=_fake_today)
    assert all(c.state == "rest" for c in outside_cells)


def test_rest_cells_carry_no_day_number_in_phase():
    outside_week_start = _p_start - timedelta(days=21)
    outside_cells = plan.get_week_view(outside_week_start, p14, [], today=_fake_today)
    assert all(c.day_number_in_phase is None for c in outside_cells)


def test_no_active_phase_reassessment_gap_is_all_rest():
    gap_cells = plan.get_week_view(_p_start, None, [], today=_fake_today)
    assert all(c.state == "rest" for c in gap_cells)


def test_weekday_label_is_a_3_letter_uppercase_abbreviation():
    assert cells[0].weekday_label == _p_start.strftime("%a").upper()[:3]
