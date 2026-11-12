"""A past day's sessions, apart and in the order done (the owner, 2026-11-12:
*"when I review previous training days they should be in order or performed"*).

Repository.get_recent_sessions puts every session of a date in one list, in
the order the store returned the rows, under the figures of whichever row came
first: on 2026-11-09 the A session and the daily tendon session read as one
interleaved list under the daily session's effort 3, 9 min, load 27.
services.training_screen.order_logged_sessions is the rule."""

from __future__ import annotations

from services import training_screen as ts


def _ex(name, ts_, movement_type="Upper Body Push"):
    return {"name": name, "movement_type": movement_type, "planned_sets": 3,
            "first_set_ts": ts_}


def _session(sid, rpe, minutes, au, exercises):
    return {"session_id": sid, "rpe": rpe, "minutes": minutes, "au": au, "exercises": exercises}


# The 9 November day, as the store returned it: interleaved, out of order.
NOV_9 = [
    _session("2026-11-09-ca192a0e", 3, 9, 27, [
        _ex("Active Hang", "2026-11-09T15:57:44+01:00", "Daily"),
        _ex("Half Push-Up Hold", "2026-11-09T16:05:53+01:00", "Daily"),
        _ex("Half Push-Up Hold", "2026-11-09T15:58:33+01:00", "Daily"),
    ]),
    _session("2026-11-09-84665617", 7, 59, 413, [
        _ex("Machine Shoulder Press", "2026-11-09T08:49:31+01:00"),
        _ex("Standing Psoas March", "2026-11-09T08:21:08+01:00", "Mobility"),
        _ex("Walking Lunge (DB)", "2026-11-09T08:23:52+01:00", "Conditioning"),
    ]),
]


def test_sessions_come_apart_in_the_order_done():
    out = ts.order_logged_sessions(NOV_9)
    assert [s["kind"] for s in out] == ["plan", "daily"], "the morning session first"
    assert [(s["rpe"], s["minutes"], s["au"]) for s in out] == [(7, 59, 413), (3, 9, 27)], \
        "each session keeps its own effort, minutes and load"


def test_exercises_follow_their_first_set():
    plan, daily = ts.order_logged_sessions(NOV_9)
    assert [e["name"] for e in plan["exercises"]] == [
        "Standing Psoas March", "Walking Lunge (DB)", "Machine Shoulder Press"]
    assert [e["name"] for e in daily["exercises"]] == [
        "Active Hang", "Half Push-Up Hold", "Half Push-Up Hold"]
    assert set(plan["exercises"][0]) == {"name", "movement_type", "planned_sets"}


def test_an_exercise_with_no_timed_set_keeps_its_place_after_the_timed_ones():
    out = ts.order_logged_sessions([_session("s", 6, 50, 300, [
        _ex("Skipped", None), _ex("Second", "2026-11-09T08:30:00+01:00"),
        _ex("Also untimed", None), _ex("First", "2026-11-09T08:10:00+01:00")])])
    assert [e["name"] for e in out[0]["exercises"]] == ["First", "Second", "Skipped", "Also untimed"]


def test_history_with_no_set_times_keeps_its_read_order():
    out = ts.order_logged_sessions([_session("s", 6, 50, 300, [
        _ex("B", None), _ex("A", None), _ex("C", None)])])
    assert [e["name"] for e in out[0]["exercises"]] == ["B", "A", "C"]


def test_times_compare_as_instants_and_a_time_with_no_offset_reads_as_utc():
    # 07:30 UTC (the hosted server's August stamps) is before 08:40+01:00 (07:40 UTC).
    out = ts.order_logged_sessions([
        _session("b", 6, 50, 300, [_ex("Phone", "2026-08-06T08:40:00+01:00")]),
        _session("a", 3, 9, 27, [_ex("Server", "2026-08-06T07:30:00", "Daily")]),
    ])
    assert [s["kind"] for s in out] == ["daily", "plan"]


def test_a_session_with_no_timed_set_comes_last():
    out = ts.order_logged_sessions([
        _session("a", 4, 30, 120, [_ex("Old", None, "Yoga")]),
        _session("b", 6, 50, 300, [_ex("Timed", "2026-11-09T18:00:00+01:00")]),
    ])
    assert [s["kind"] for s in out] == ["plan", "yoga"]


def test_each_supplementary_type_names_its_kind():
    for stored, kind in [("Daily", "daily"), ("Evening Mobility", "mobility"),
                         ("Accessory", "accessory"), ("EGYM", "egym"),
                         ("Yoga", "yoga"), ("Outdoor", "outdoor")]:
        out = ts.order_logged_sessions([_session("s", 3, 10, 30, [_ex("x", None, stored)])])
        assert out[0]["kind"] == kind, stored


def test_a_session_of_one_plan_movement_type_is_the_plan_session():
    # A flexibility day stores every exercise as "Mobility": still the plan session.
    out = ts.order_logged_sessions([_session("s", 3, 40, 120, [
        _ex("Pancake", None, "Mobility"), _ex("Pigeon", None, "Mobility")])])
    assert out[0]["kind"] == "plan"


def test_a_session_with_no_exercises_is_left_out():
    assert ts.order_logged_sessions([_session("s", 3, 10, 30, [])]) == []


class _Repo:
    def __init__(self, raw):
        self.raw = raw

    def get_day_logged_sessions(self, d):
        return self.raw


def test_the_logged_answer_leads_with_the_plan_session_and_lists_every_exercise_in_order():
    from datetime import date
    out = ts._logged_session(_Repo(NOV_9), date(2026, 11, 9), date(2026, 11, 12))
    assert (out["rpe"], out["minutes"], out["au"]) == (7, 59, 413), "the plan session's figures"
    assert [e["name"] for e in out["exercises"]] == [
        "Standing Psoas March", "Walking Lunge (DB)", "Machine Shoulder Press",
        "Active Hang", "Half Push-Up Hold", "Half Push-Up Hold"]
    assert [s["kind"] for s in out["sessions"]] == ["plan", "daily"]


def test_no_detail_reads_none():
    from datetime import date
    assert ts._logged_session(_Repo([]), date(2026, 11, 9), date(2026, 11, 12)) is None
