"""A test is one reading per entry (WP-33, the athlete, 2026-10-26: "Always
split a retest into its individual items; never add it to the training block
as a single combined item. Make this a mandatory validation gate before a
retest can be added to the training block").

sessions.measurement_violations is the check, run here over every plan from
MEASUREMENT_SPLIT_FROM_PHASE on, so a block with a combined test entry cannot
pass the suite. The two entries that prompted it are pinned as failing it."""

from __future__ import annotations

from datetime import date

import pytest

import cluster_a_battery as cba
import goal_block as gb
import goal_week as gw
import training_constants as tc
from services import flexibility_screen as fxs
from services import sessions as s

GOVERNED = sorted(n for n in s.PHASE_META if n >= s.MEASUREMENT_SPLIT_FROM_PHASE)


def test_at_least_one_block_is_governed():
    assert GOVERNED


@pytest.mark.parametrize("phase_number", GOVERNED)
def test_every_test_entry_of_every_governed_block_is_one_reading(phase_number):
    plan = s.plan_dict_for_phase(phase_number)
    bad = {d: s.measurement_violations(plan[d]) for d in sorted(plan)}
    bad = {d: v for d, v in bad.items() if v}
    assert not bad, bad


def test_the_two_combined_tests_would_fail_it():
    """The 20-minute retest that sent him to Insights, and the rib and pelvis
    test's four checks under one timer."""
    retest = {"name": "Flexibility Retest (Test)", "type": "duration", "sets": 1,
              "duration_minutes": 20}
    rib = {"name": "Rib and Pelvis Test (Test)", "type": "duration", "sets": 1,
           "duration_minutes": 10}
    for entry in (retest, rib):
        assert s.measurement_violations({"exercises": [entry]}), entry["name"]


def test_a_timed_line_and_one_battery_test_are_one_reading_each():
    line = {"name": "Bunkie — Lateral Stabilizing Line (Timed)", "type": "hold", "sets": 1}
    one = dict(gb.FLEXIBILITY_TESTS[0])
    assert s.measurement_violations({"exercises": [line, one]}) == []
    assert s.measurement_violations({"exercises": [dict(one, sets=2)]})


def test_the_retest_is_the_battery_in_its_own_order_each_with_a_record():
    order = fxs.capture_order(fxs.begin(date(2026, 11, 1), cold=True))
    assert [e["battery_test"] for e in gb.FLEXIBILITY_TESTS] == order
    assert tc.FLEXIBILITY_TEST_NAMES == gb.FLEXIBILITY_TEST_NAMES
    for name in gb.FLEXIBILITY_TEST_NAMES:
        assert name in gw.PICKS, name
        assert name in tc.EXERCISE_REGION_SHARES and name in tc.EXERCISE_MOVEMENT_WEIGHT, name
    sunday = s.plan_dict_for_phase(5)[7]["exercises"]
    assert "Flexibility Retest (Test)" not in [e["name"] for e in sunday]


def test_no_entry_sends_him_out_of_the_session():
    for e in gb.FLEXIBILITY_TESTS:
        assert "Insights" not in e["mechanics"] and "**" not in e["mechanics"], e["name"]


def test_a_session_reading_asks_for_the_test_s_own_input():
    bent = fxs.session_reading("leverage_bent", (), date(2026, 11, 1))
    assert bent["sides"] == ["left", "right"] and bent["unit"] == cba.TESTS["leverage_bent"].unit
    assert bent["setup_input"]
    straight = fxs.session_reading("leverage_straight", (), date(2026, 11, 1))
    assert straight["sides"] == [""] and straight["setup_input"] is None


def test_the_readings_become_one_cold_assessment_of_the_morning():
    day = date(2026, 11, 1)
    a = fxs.readings_from_session([
        {"test_key": "leverage_bent", "values": {"left": 20.0, "right": 22.0}, "setup_value": 30.0},
        {"test_key": "leverage_straight", "values": {"": 40.0, "left": None}},
    ], day)
    assert a.taken_on == day and a.cold is True
    assert sorted((r.test_key, r.side, r.value) for r in a.readings) == [
        ("leverage_bent", "left", 20.0), ("leverage_bent", "right", 22.0),
        ("leverage_straight", "", 40.0)]
    assert all(r.setup_value == 30.0 for r in a.readings if r.test_key == "leverage_bent")


def test_an_unknown_test_or_side_is_refused():
    with pytest.raises(fxs.CaptureRefused):
        fxs.readings_from_session([{"test_key": "made_up", "values": {"": 1.0}}], date(2026, 11, 1))
    with pytest.raises(fxs.CaptureRefused):
        fxs.readings_from_session([{"test_key": "leverage_straight", "values": {"left": 1.0}}],
                                  date(2026, 11, 1))


def test_the_early_answer_reads_the_battery():
    out = fxs.session_check([], date(2026, 11, 1))
    assert out == {"pattern": None, "label": "", "reason": ""}
