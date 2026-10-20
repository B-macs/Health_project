"""Gate 1 — the first run (services/gate1.py).

docs/training/goal_system.md, goal A (approved 2026-10-14, changed
2026-10-16): 6 weeks in a row with all 3 core sessions done; a week with
fewer asks its reason, one tap — hips or back resets the count, travel or
illness pauses it, other resets it — and the count does not move until it has
one; each main lift 10% above its first weight in the block.
"""
from dataclasses import replace
from datetime import date, timedelta

import pytest

from services import gate1 as g
from services import scheduling as sch
from services import sessions as sess

START = date(2026, 10, 19)
PHASE = sess.build_phase(5, START)
PLAN = sess.calendar_plan(PHASE)


def _mon(week: int) -> date:
    return START + timedelta(days=7 * (week - 1))


def _w(week, done, reason=None):
    return g.WeekCount(_mon(week), done, reason)


def test_gate_1_reads_the_12_week_block_only():
    assert g.applies(PHASE)
    assert not g.applies(replace(PHASE, phase_number=4))
    assert not g.applies(None)
    assert g.WEEKS_REQUIRED == 6 and g.CORE_REQUIRED == 3


def test_six_full_weeks_in_a_row_meet_part_1():
    assert g.count([_w(i, 3) for i in range(1, 7)]) == {
        "run": 6, "required": 6, "waiting": None, "met": True}
    assert g.count([_w(i, 3) for i in range(1, 6)])["met"] is False


def test_a_flare_up_resets_the_count():
    weeks = [_w(1, 3), _w(2, 3), _w(3, 2, g.REASON_FLARE), _w(4, 3)]
    assert g.count(weeks)["run"] == 1


def test_a_flare_up_in_a_full_week_resets_it_too():
    """A session shortened or changed for the hips or back, all three done."""
    weeks = [_w(1, 3), _w(2, 3, g.REASON_FLARE), _w(3, 3)]
    assert g.count(weeks)["run"] == 1


def test_travel_or_illness_pauses_the_count():
    weeks = [_w(1, 3), _w(2, 3), _w(3, 0, g.REASON_PAUSE), _w(4, 3)]
    assert g.count(weeks)["run"] == 3


def test_other_means_the_week_does_not_count_and_the_count_resets():
    weeks = [_w(1, 3), _w(2, 3), _w(3, 1, g.REASON_OTHER), _w(4, 3)]
    assert g.count(weeks)["run"] == 1


def test_the_count_does_not_move_until_a_short_week_has_its_reason():
    weeks = [_w(1, 3), _w(2, 2), _w(3, 3), _w(4, 3)]
    out = g.count(weeks)
    assert out == {"run": 1, "required": 6, "waiting": _mon(2), "met": False}


def test_the_answers_are_stored_and_read_back():
    raw = g.with_reason(None, _mon(2), g.REASON_PAUSE)
    raw = g.with_reason(raw, _mon(1), g.REASON_FLARE)
    assert g.read_reasons(raw) == {_mon(1).isoformat(): "hips_back",
                                   _mon(2).isoformat(): "travel_illness"}
    with pytest.raises(ValueError):
        g.with_reason(raw, _mon(3), "felt lazy")


@pytest.mark.parametrize("raw", [None, "", "not json", "[1, 2]", '{"2026-10-19": "nonsense"}'])
def test_an_unreadable_row_reads_as_no_answer(raw):
    assert g.read_reasons(raw) == {}


def test_only_ended_weeks_are_counted():
    assert g.week_mondays(PHASE, _mon(1) + timedelta(days=6)) == []
    assert g.week_mondays(PHASE, _mon(2)) == [_mon(1)]
    assert g.week_mondays(PHASE, _mon(3) + timedelta(days=3)) == [_mon(1), _mon(2)]


def test_core_sessions_are_counted_by_the_session_each_day_held():
    week = {_mon(1) + timedelta(days=i) for i in (0, 1, 3, 4)}
    logged = {d.isoformat() for d in week}
    assert g.core_sessions_done(PHASE, PLAN, logged, _mon(1)) == 3
    # D alone is not a core session.
    friday = (_mon(1) + timedelta(days=4)).isoformat()
    assert g.core_sessions_done(PHASE, PLAN, {friday}, _mon(1)) == 0


def test_a_missed_monday_run_in_order_still_reads_three_of_three():
    tuesday = _mon(1) + timedelta(days=1)
    ovr, rsn = sch.in_order_reschedules(PHASE, PLAN, set(), tuesday)
    moved = replace(PHASE, date_overrides=ovr, shift_reasons=rsn)
    logged = {(_mon(1) + timedelta(days=i)).isoformat() for i in (1, 3, 4)}
    assert g.core_sessions_done(moved, PLAN, logged, _mon(1)) == 3


def test_the_first_and_latest_weights_are_read_inside_the_block():
    history = [
        ("2026-11-09", [{"reps": 10, "weight": 66.0}] * 3),
        ("2026-10-26", [{"reps": 10, "weight": 60.0}, {"reps": 6, "weight": 30.0, "is_warmup": True}]),
        ("2026-10-20", [{"reps": 6, "weight": 35.0, "is_warmup": True}, {"reps": 10, "weight": 60.0}]),
        ("2026-10-12", [{"reps": 10, "weight": 40.0}]),     # Block B: not the block's first
    ]
    assert g.lift_weights(history, START) == (60.0, 66.0)
    assert g.lift_weights([], START) == (None, None)


def test_a_lift_meets_part_3_at_ten_percent_above_its_first_weight():
    rows = g.strength_rows({"Hack Squat": (60.0, 66.0), "Machine Chest Press": (40.0, 40.0),
                            "Single-Arm DB Row": (22.5, 24.75)})
    by = {r["lift"]: r for r in rows}
    assert [r["lift"] for r in rows] == list(g.MAIN_LIFTS)
    assert by["Hack Squat"]["target"] == 66.0 and by["Hack Squat"]["met"]
    assert not by["Machine Chest Press"]["met"]
    assert by["Single-Arm DB Row"]["met"]               # 24.75 >= 24.75
    assert by["Machine Shoulder Press"] == {"lift": "Machine Shoulder Press", "first": None,
                                            "latest": None, "target": None, "met": False}
    assert g.steps_to_target(by["Machine Chest Press"], 5.0) == 1


def test_the_gate_needs_both_parts():
    six = g.count([_w(i, 3) for i in range(1, 7)])
    rows = g.strength_rows({lift: (40.0, 44.0) for lift in g.MAIN_LIFTS})
    assert g.passed(six, rows)
    assert not g.passed(six, rows[:-1] + [dict(rows[-1], met=False)])
    assert not g.passed(g.count([_w(1, 3)]), rows)


def test_the_main_lifts_are_in_the_block():
    names = {e["name"] for e in PLAN[1]["exercises"] + PLAN[2]["exercises"]
             + PLAN[4]["exercises"]}
    assert set(g.MAIN_LIFTS) <= names


def test_the_explanation_is_built_from_the_gates_own_numbers():
    """When running starts (rebuild Phase 7): one sentence for the training page and the
    phone, made from WEEKS_REQUIRED, CORE_REQUIRED and STRENGTH_GAIN, so a changed number
    cannot leave an old one on either screen."""
    text = g.how_text()
    assert text == ("Running starts when all of these are true: 6 weeks in a row with all 3 core "
                    "sessions and no flare-up; each main lift 10% above its first weight in this "
                    "block; then a test day (a 30-minute brisk walk, single-leg calf raises and "
                    "hops, all without pain).")
    assert f"{g.WEEKS_REQUIRED} weeks" in text and f"all {g.CORE_REQUIRED} core" in text
