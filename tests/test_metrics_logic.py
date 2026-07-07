"""
Tests for services/metrics_logic.py — Weekly Rollup ("Perfect/Ultimate Week")
scoring. Pure functions only; no I/O, no fixtures beyond plain dates/Phases.
"""

import ast
from datetime import date, timedelta

from services import metrics_logic as ml
from services import plan
from services.models import Phase, WeekScore

# ─── no streamlit import ────────────────────────────────────────────────────


def test_no_streamlit_import():
    tree = ast.parse(open(ml.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"


# ─── score_week — status thresholds (integer math, per-spec boundaries) ────

_WK = date(2026, 6, 29)  # a Monday; week ends 2026-07-05
_LATER_TODAY = date(2026, 7, 20)  # safely after _WK's week has ended


def test_5_of_5_is_ultimate():
    assert ml.score_week(_WK, _LATER_TODAY, scheduled=5, completed=5).status == "ultimate"


def test_4_of_5_is_perfect():
    assert ml.score_week(_WK, _LATER_TODAY, scheduled=5, completed=4).status == "perfect"


def test_2_of_5_is_normal():
    assert ml.score_week(_WK, _LATER_TODAY, scheduled=5, completed=2).status == "normal"


def test_0_of_5_is_failed():
    assert ml.score_week(_WK, _LATER_TODAY, scheduled=5, completed=0).status == "failed"


def test_1_of_5_lands_on_normal_not_failed():
    # The 20% boundary: 1*5 >= 5*1 is True, so this is "normal", not
    # "failed" — despite the shorthand "1/5 failed" in the original task
    # description, the spec's own integer-math formulas put exactly 20% in
    # the "normal" bucket (>= 20%). This test locks in that the boundary
    # lands where the formulas say it does.
    assert ml.score_week(_WK, _LATER_TODAY, scheduled=5, completed=1).status == "normal"


def test_current_week_is_in_progress_regardless_of_ratio():
    today_in_week = _WK + timedelta(days=3)
    result = ml.score_week(_WK, today_in_week, scheduled=5, completed=3)
    assert result.status == "in_progress"


def test_current_week_in_progress_even_with_zero_scheduled():
    today_in_week = _WK + timedelta(days=3)
    result = ml.score_week(_WK, today_in_week, scheduled=0, completed=0)
    assert result.status == "in_progress"


def test_zero_scheduled_ended_week_is_no_plan():
    assert ml.score_week(_WK, _LATER_TODAY, scheduled=0, completed=0).status == "no_plan"


def test_week_end_is_six_days_after_week_start():
    result = ml.score_week(_WK, _LATER_TODAY, scheduled=5, completed=5)
    assert result.week_end == (_WK + timedelta(days=6)).isoformat()


def test_computed_at_is_none_from_pure_scoring():
    assert ml.score_week(_WK, _LATER_TODAY, scheduled=5, completed=5).computed_at is None


def test_phase_number_defaults_to_none():
    assert ml.score_week(_WK, _LATER_TODAY, scheduled=5, completed=5).phase_number is None


def test_phase_number_passthrough():
    result = ml.score_week(_WK, _LATER_TODAY, scheduled=5, completed=5, phase_number=2)
    assert result.phase_number == 2


# ─── compute_week_history — 14-day and 28-day phases ────────────────────────

_p14 = plan.default_phase(date(2026, 6, 29), length_days=14, phase_number=1, name="Stage 1 Rehab")
# today == the phase's own last day, so "current_week" doesn't stretch the
# generated range past the phase's own 2 weeks with extra no_plan gap weeks.
_p14_history = ml.compute_week_history(date(2026, 7, 12), [_p14], sessions=[])


def test_14_day_phase_produces_exactly_2_weeks():
    assert len(_p14_history) == 2


def test_14_day_phase_weeks_are_fully_scheduled():
    assert all(w.scheduled == 7 for w in _p14_history)


def test_14_day_phase_first_week_starts_on_phase_start():
    assert _p14_history[0].week_start == _p14.start_date


_p28_start = date(2026, 9, 1) - timedelta(days=date(2026, 9, 1).weekday())
_p28 = plan.default_phase(_p28_start, length_days=28, phase_number=2, name="Stage 2")
# today == the phase's own last day, same reasoning as the 14-day case above.
_p28_history = ml.compute_week_history(_p28_start + timedelta(days=27), [_p28], sessions=[])


def test_28_day_phase_produces_exactly_4_weeks():
    assert len(_p28_history) == 4


def test_28_day_phase_weeks_are_fully_scheduled():
    assert all(w.scheduled == 7 for w in _p28_history)


# ─── compute_week_history — week straddling a phase boundary ────────────────

# Phase A: 10 days, Mon 2026-06-29 .. Wed 2026-07-08.
# Phase B: 7 days, Thu 2026-07-09 .. Wed 2026-07-15 (starts the very next day
# after A ends — no gap). The week of Mon 2026-07-06 .. Sun 2026-07-12
# straddles the boundary: 3 days in A (Mon/Tue/Wed), 4 days in B
# (Thu/Fri/Sat/Sun).
_phase_a = Phase(phase_number=1, name="A", start_date="2026-06-29", length_days=10, status="completed")
_phase_b = Phase(phase_number=2, name="B", start_date="2026-07-09", length_days=7, status="completed")
_straddle_sessions = [{"date": d} for d in [
    "2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10", "2026-07-11", "2026-07-12",
]]
_straddle_history = ml.compute_week_history(date(2026, 8, 1), [_phase_a, _phase_b], _straddle_sessions)
_straddle_week = next(w for w in _straddle_history if w.week_start == "2026-07-06")


def test_straddling_week_counts_all_7_days_as_scheduled():
    assert _straddle_week.scheduled == 7


def test_straddling_week_attributes_to_majority_phase():
    # 4 of the 7 days belong to Phase B vs 3 for Phase A.
    assert _straddle_week.phase_number == 2


def test_straddling_week_with_full_attendance_is_ultimate():
    assert _straddle_week.status == "ultimate"


def test_sessions_attributed_by_own_date_not_by_phase_coverage():
    # Phase A covers only Mon/Tue/Wed (3 days) of the week 2026-07-06..07-12
    # (days 8-10 of its 10-day span). A session logged on Friday 2026-07-10
    # -- a day Phase A doesn't cover -- must still count toward that week's
    # completed tally: completed is driven purely by the session's own
    # date, not gated by whether a phase happens to cover that day.
    history = ml.compute_week_history(date(2026, 8, 1), [_phase_a], sessions=[{"date": "2026-07-10"}])
    week = next(w for w in history if w.week_start == "2026-07-06")
    assert week.scheduled == 3
    assert week.completed == 1


# ─── compute_week_history — gap weeks / no scheduled sessions ──────────────


def test_gap_week_between_phases_or_no_phases_is_no_plan():
    single_phase = Phase(phase_number=1, name="A", start_date="2026-06-29", length_days=7, status="completed")
    history = ml.compute_week_history(date(2026, 7, 27), [single_phase], sessions=[])
    # Weeks after the 1-week phase ends, up through "today"'s week, have no
    # covering phase at all.
    gap_weeks = [w for w in history if w.week_start != "2026-06-29"]
    assert gap_weeks  # at least one generated
    assert all(w.status in ("no_plan", "in_progress") for w in gap_weeks)
    assert all(w.scheduled == 0 for w in gap_weeks if w.status == "no_plan")


def test_no_phases_returns_empty_history():
    assert ml.compute_week_history(date(2026, 7, 20), [], sessions=[]) == []


def test_upcoming_future_phase_does_not_generate_unstarted_weeks():
    # A pre-configured "upcoming" phase starting well after today (e.g. a
    # planned Stage 2 block) must not cause weeks that haven't happened yet
    # to be generated and scored — those would wrongly come out "failed"
    # (0 completed) despite not having started.
    past_phase = Phase(phase_number=1, name="Stage 1", start_date="2026-06-29", length_days=7, status="completed")
    future_phase = Phase(phase_number=2, name="Stage 2", start_date="2026-12-07", length_days=28, status="upcoming")
    history = ml.compute_week_history(date(2026, 7, 6), [past_phase, future_phase], sessions=[])
    assert max(w.week_start for w in history) <= "2026-07-06"
    assert all(w.status != "failed" for w in history if date.fromisoformat(w.week_start) > date(2026, 7, 6))


# ─── compute_streak ──────────────────────────────────────────────────────────


def _wk(week_start: str, status: str) -> WeekScore:
    w_start = date.fromisoformat(week_start)
    w_end = w_start + timedelta(days=6)
    scheduled = 0 if status == "no_plan" else 5
    completed = {"ultimate": 5, "perfect": 4, "normal": 2, "failed": 0, "no_plan": 0, "in_progress": 3}[status]
    return WeekScore(week_start=week_start, week_end=w_end.isoformat(), phase_number=1,
                      scheduled=scheduled, completed=completed, status=status)


def test_streak_pauses_on_no_plan():
    # Chronological ascending order (oldest first), as compute_week_history produces.
    history = [_wk("2026-06-01", "ultimate"), _wk("2026-06-08", "no_plan"), _wk("2026-06-15", "perfect")]
    streak = ml.compute_streak(history)
    assert streak.current_streak == 2  # no_plan skipped, not a break


def test_streak_pauses_on_normal():
    history = [_wk("2026-06-01", "ultimate"), _wk("2026-06-08", "normal"), _wk("2026-06-15", "perfect")]
    streak = ml.compute_streak(history)
    assert streak.current_streak == 2


def test_streak_resets_on_failed():
    history = [_wk("2026-06-01", "ultimate"), _wk("2026-06-08", "failed"), _wk("2026-06-15", "perfect")]
    streak = ml.compute_streak(history)
    assert streak.current_streak == 1  # only the trailing perfect week counts


def test_best_streak_retained_after_reset():
    history = [
        _wk("2026-06-01", "ultimate"), _wk("2026-06-08", "ultimate"),
        _wk("2026-06-15", "failed"), _wk("2026-06-22", "perfect"),
    ]
    streak = ml.compute_streak(history)
    assert streak.current_streak == 1
    assert streak.best_streak == 2  # the earlier 2-week run before the reset


def test_no_plan_excluded_from_tallies():
    history = [_wk("2026-06-01", "ultimate"), _wk("2026-06-08", "no_plan"), _wk("2026-06-15", "failed")]
    streak = ml.compute_streak(history)
    assert streak.ultimate_count == 1
    assert streak.failed_count == 1
    assert streak.perfect_count == 0
    assert streak.normal_count == 0


def test_in_progress_week_excluded_from_streak_and_tallies():
    history = [_wk("2026-06-01", "ultimate"), _wk("2026-06-08", "in_progress")]
    streak = ml.compute_streak(history)
    assert streak.current_streak == 1
    assert streak.ultimate_count == 1


def test_empty_history_has_zero_streaks():
    streak = ml.compute_streak([])
    assert streak.current_streak == 0
    assert streak.best_streak == 0


# ─── current_streak_is_all_ultimate ─────────────────────────────────────────


def test_all_ultimate_streak_is_flagged():
    history = [_wk("2026-06-01", "ultimate"), _wk("2026-06-08", "ultimate")]
    assert ml.current_streak_is_all_ultimate(history) is True


def test_mixed_perfect_and_ultimate_streak_is_not_flagged():
    history = [_wk("2026-06-01", "ultimate"), _wk("2026-06-08", "perfect")]
    assert ml.current_streak_is_all_ultimate(history) is False


def test_zero_streak_is_not_flagged_ultimate():
    history = [_wk("2026-06-01", "failed")]
    assert ml.current_streak_is_all_ultimate(history) is False


def test_no_plan_pause_inside_all_ultimate_streak_still_flags_true():
    history = [_wk("2026-06-01", "ultimate"), _wk("2026-06-08", "no_plan"), _wk("2026-06-15", "ultimate")]
    assert ml.current_streak_is_all_ultimate(history) is True
