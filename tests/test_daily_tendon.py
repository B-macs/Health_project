"""The daily tendon session (WP-40, 2026-10-28): what runs, its records, its
safety rules and maps, its time, its 8-hour line, and the rule that keeps it
out of the logged-day count.

The athlete, 2026-10-28: "the other tile will be the daily training day ... at
only 10mins per day", "In all cases follow Baars studies", "Reminder only let
me make the desicion on when to do it and never locked".
"""
import ast
import re
from pathlib import Path

import pytest

import daily_tendon as dt
import goal_week as gw
import training_constants as tc
from services import accessory as acc
from services import daily_session as dly
from services import rules
from services import training_session as tsession
from services.repository import Repository

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = dt.entries()


# ─── What runs ───────────────────────────────────────────────────────────────

def test_three_rounds_in_the_approved_order():
    hang, push, calf, bent, neck = ("Active Hang", "Half Push-Up Hold", "Single-Leg Calf Hold",
                                    "Single-Leg Calf Hold (Bent Knee)", "Neck Working Stretch (Right)")
    assert [e["name"] for e in ENTRIES] == [hang, push, calf, neck,
                                            hang, push, bent, neck,
                                            hang, push, calf]


def test_every_hold_is_thirty_seconds_with_a_slow_start():
    """Baar: about 30 s for a large tendon or a long-standing injury, and a
    slow start. One set each: the rounds are the sets."""
    holds = [e for e in ENTRIES if e["type"] == "hold"]
    assert len(holds) == 9
    for e in holds:
        assert e["hold_seconds"] == 30 and e["lead_in_seconds"] == 5 and e["sets"] == 1, e["name"]
        assert e["rest_seconds"] == dt.CHANGE_SECONDS


def test_the_calves_are_one_side_at_a_time_and_change_angle_in_round_two():
    calves = [e for e in ENTRIES if "Calf" in e["name"]]
    assert [e["name"] for e in calves] == ["Single-Leg Calf Hold", "Single-Leg Calf Hold (Bent Knee)",
                                           "Single-Leg Calf Hold"]
    assert all(e["laterality"] == "unilateral" for e in calves)


def test_the_neck_keeps_its_dose_two_sets_of_four_ten_second_pushes():
    necks = [e for e in ENTRIES if e["name"] == "Neck Working Stretch (Right)"]
    assert len(necks) == 2
    for e in necks:
        assert (e["type"], e["sets"], e["reps_in_set"], e["hold_seconds"]) == ("hold_reps", 1, 4, 10)
        assert "lead_in_seconds" not in e


def test_the_push_up_hold_stops_at_the_line_of_the_body():
    """The right arm's measured limit (2026-08-13): never deeper."""
    how = dt.HALF_PUSH_UP_HOLD["mechanics"]
    assert "level with your body" in how and "Never lower" in how


def test_the_hang_is_both_hands_and_the_active_step():
    assert "Both hands" in dt.ACTIVE_HANG["mechanics"]
    assert "shoulder blades pulled down" in dt.ACTIVE_HANG["mechanics"]


def test_no_weight_is_used():
    assert all(not e.get("equipment_type") and not e.get("weight_kg") for e in ENTRIES)


def test_each_entry_is_a_fresh_copy():
    a, b = dt.entries(), dt.entries()
    assert a[0] is not b[0] and a[0] is not a[4]


def test_the_session_takes_about_eleven_minutes():
    """His limit: about 10 minutes a day. The daily session's own model: the
    gym's measured changeovers were walking between stations."""
    assert 9 <= dly.modelled_minutes(ENTRIES) <= 12
    # The hold's slow start counts: the phone runs the two as one timer.
    hang = dt.ACTIVE_HANG
    assert dly.entry_seconds(hang) == 35
    assert dly.entry_seconds(dt.CALF_HOLD) == 70


# ─── Nothing is copied (Key Rule 25) ─────────────────────────────────────────

def test_every_exercise_has_a_complete_workflow_record():
    assert set(dt.DAILY_PICKS) == set(dt.names())
    for name, p in dt.DAILY_PICKS.items():
        assert p.goal in {"tendons", "B"}, (name, p.goal)
        assert p.area and p.job and p.reason, name
        assert re.search(r"20\d\d-\d\d-\d\d", p.source), name
        assert p.better and p.better.startswith("checked 20"), name


def test_the_neck_record_moved_with_the_neck_stretch():
    assert "Neck Working Stretch (Right)" not in gw.PICKS
    assert dt.DAILY_PICKS["Neck Working Stretch (Right)"].goal == "B"


def test_the_session_imports_no_exercise_from_another_plan():
    tree = ast.parse((ROOT / "daily_tendon.py").read_text(encoding="utf-8"))
    imported = {(n.module, a.name) for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                for a in n.names}
    assert imported <= {("__future__", "annotations"), ("goal_week", "Pick"),
                        ("training_plan", "_ex")}, imported
    assert not any(isinstance(n, ast.Import) for n in ast.walk(tree))


def test_the_hang_is_its_own_object_not_the_plus_sessions():
    import training_plan as tp
    assert dt.ACTIVE_HANG is not tp.HANG_ACTIVE
    assert dt.ACTIVE_HANG["hold_seconds"] == 30 and tp.HANG_ACTIVE["hold_seconds"] == 15


# ─── Safety rules and maps ───────────────────────────────────────────────────

@pytest.mark.parametrize("name", dt.names())
def test_every_name_lands_on_a_safety_rule(name):
    assert rules.check_movement(name, 2)["severity"] in ("cleared", "caution"), name


@pytest.mark.parametrize("name", dt.names())
def test_every_name_is_in_the_three_maps(name):
    assert name in tc.EXERCISE_BODY_REGION
    assert name in tc.EXERCISE_REGION_SHARES
    assert name in tc.EXERCISE_MOVEMENT_WEIGHT


def test_the_push_up_rule_carries_the_right_arms_limit():
    r = rules.check_movement("Half Push-Up Hold", 2)
    assert r["severity"] == "caution" and r["laterality"] == "right"


def test_a_warning_shown_on_screen_has_its_body_area():
    """Key Rule 20: a warning shows only while its own area is strained, which
    needs its share entry."""
    for ex in dt.LIBRARY:
        if ex.get("warning"):
            assert ex["name"] in tc.EXERCISE_REGION_SHARES


def test_no_back_warning_in_any_text():
    """Key Rule 24."""
    for ex in dt.LIBRARY:
        for field in ("mechanics", "warning"):
            assert not re.search(r"\bback\b(?! of)", (ex.get(field) or "").lower().replace(
                "back and down", "").replace("down and back", "")), (ex["name"], field)


# ─── The hang step (his report, 2026-10-28) ──────────────────────────────────

def test_the_hang_ladder_is_at_step_two_and_the_passive_hang_stays_held():
    assert acc.HANG_STEP == 2 and acc.HANG_MAX_STEP == 2


# ─── The save and the logged-day count ───────────────────────────────────────

def test_the_daily_kind_is_stored_under_its_own_type():
    body = {"session_id": "2026-10-28-dai10001", "date": "2026-10-28", "kind": "daily",
            "duration_minutes": 11, "session_rpe": 4,
            "exercises": [{"exercise_id": "ex-1", "exercise": ENTRIES[0]}]}
    saved = tsession.build_save(body)
    assert {e.movement_type for e in saved.exercises} == {dly.DAILY_TYPE}


def test_the_daily_type_never_marks_a_plan_day_and_never_makes_a_logged_day():
    assert dly.DAILY_TYPE in Repository.SUPPLEMENTARY_SESSION_TYPES
    assert Repository.NOT_A_TRAINING_DAY_TYPES == frozenset({dly.DAILY_TYPE})


def test_a_week_of_daily_sessions_and_two_gym_days_still_fails():
    """The failed-week count reads the logged dates; a Daily-only day is not
    one, so seven daily sessions and two gym sessions are two days."""
    from datetime import date

    from services import metrics_logic
    from services import week_repeat as wr

    monday = date(2026, 10, 26)
    days = [date(2026, 10, 26 + i).isoformat() if i < 6 else "2026-11-01" for i in range(7)]
    rows = [(d, "Daily") for d in days]
    rows += [("2026-10-26", "Hack Squat"), ("2026-10-27", "Romanian Deadlift")]
    repo = Repository.__new__(Repository)
    repo.config = type("C", (), {"notion_db_training": "training"})()
    repo._query = lambda db, filter_=None, **kw: [
        {"properties": {"Session Date": {"date": {"start": d}},
                        "Type": {"select": {"name": t}}}} for d, t in rows]
    dates = repo.get_logged_session_dates(monday, date(2026, 11, 1))
    assert dates == {"2026-10-26", "2026-10-27"}
    assert wr.days_logged(dates, monday) == 2 <= metrics_logic.FAILED_WEEK_MAX_DAYS


# ─── The 8-hour line and "done today" ────────────────────────────────────────

GYM = {"session_id": "s-gym", "type": "Romanian Deadlift", "last_set_ts": "2026-10-28T09:41:12+01:00"}
DAILY = {"session_id": "s-daily", "type": "Daily", "last_set_ts": "2026-10-28T20:05:00+01:00"}


def test_after_the_gym_session_the_line_is_eight_hours_after_its_last_set():
    assert dly.reminder([GYM], plan_still_to_do=False) == {"kind": "after", "time": "17:41"}


def test_the_time_is_the_phones_own_clock():
    utc = {**GYM, "last_set_ts": "2026-10-28T08:41:12+00:00"}
    assert dly.reminder([utc], False) == {"kind": "after", "time": "16:41"}


def test_the_latest_plan_set_counts_and_the_daily_sessions_own_sets_do_not():
    later = {**GYM, "session_id": "s-gym2", "last_set_ts": "2026-10-28T10:02:00+01:00"}
    assert dly.reminder([GYM, later, DAILY], False) == {"kind": "after", "time": "18:02"}


def test_before_the_gym_session_the_line_says_keep_eight_hours():
    assert dly.reminder([], plan_still_to_do=True) == {"kind": "before", "time": None}
    assert dly.reminder([DAILY], plan_still_to_do=True) == {"kind": "before", "time": None}


def test_a_rest_day_has_no_line():
    assert dly.reminder([], plan_still_to_do=False) is None


def test_a_gym_session_with_no_set_time_gives_no_guessed_time():
    assert dly.reminder([{**GYM, "last_set_ts": None}], plan_still_to_do=False) is None


def test_done_today_reads_the_daily_type():
    assert dly.done_today([DAILY]) and not dly.done_today([GYM]) and not dly.done_today([])


def test_a_failed_read_gives_no_line_and_not_done():
    class Broken:
        def get_day_sessions(self, d):
            raise OSError("offline")
    assert dly.read_day_sessions(Broken(), None) == []


def test_the_session_never_locks():
    """'never locked': nothing in the plan or the module refuses a time."""
    src = (ROOT / "services" / "daily_session.py").read_text(encoding="utf-8")
    assert "SessionRefused" not in src and "raise" not in src
