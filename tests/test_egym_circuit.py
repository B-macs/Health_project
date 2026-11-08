"""The EGYM session (2026-11-08): egym_circuit.py (WHAT) and
services/egym_session.py (WHICH).

The athlete, 2026-11-08: "I should be presented a order but I can change it up
as I please, The numbers I calculate at the end is the tonage that I do per
exercise", then "All I want to add in is the tonnage", "add it to the weekly
tonnage", and after the first build: "Unfortunately it can't be a circuit
because of the current usage; I will have to do both sets just after each
other".
"""
from __future__ import annotations

import re
from datetime import date

import pytest

import egym_circuit as ec
import training_constants as tc
from services import egym_session as egs
from services import strength, tonnage
from services.repository import Repository

N = len(ec.MACHINES)


# ─── What runs ───────────────────────────────────────────────────────────────

def test_the_session_is_his_fourteen_machines_once_each_in_order():
    """"it can't be a circuit": each machine once, its two sets together."""
    assert N == 14 and ec.SETS == 2
    entries = ec.entries()
    assert [e["name"] for e in entries] == list(ec.names())
    assert len(set(ec.names())) == N


def test_every_machine_is_two_sets_back_to_back_that_record_a_tonnage_only():
    """"All I want to add in is the tonnage", "both sets just after each other":
    two sets, each one "rep" that carries the set's tonnage, a short rest
    between them that a tap ends."""
    for ex in ec.entries():
        assert ex["type"] == "reps" and ex["sets"] == 2 and ex["reps"] == 1, ex["name"]
        assert ex["rest_seconds"] == ec.REST_SECONDS == 60, ex["name"]
        assert ex["tonnage_entry"] is True, ex["name"]
        assert ex["equipment_type"] is None, "no weight stepper: EGYM sets the weight"


def test_the_entries_are_fresh_copies():
    a, b = ec.entries(), ec.entries()
    a[0]["name"] = "changed"
    assert b[0]["name"] == "EGYM Squat" and ec.SQUAT["name"] == "EGYM Squat"


def test_every_name_says_egym_and_stays_apart_from_the_blocks_machines():
    """"No, they're all different machines, so keep them apart": own names, own history."""
    import goal_block as gb
    block = {ex["name"] for day in gb.PLAN_GOAL_BLOCK.values() for ex in day.get("exercises") or []}
    for name in ec.names():
        assert name.startswith("EGYM ") and name not in block, name


def test_the_order_ends_with_the_core():
    assert ec.names()[-2:] == ("EGYM Back Extension", "EGYM Abdominal Crunch")
    assert ec.names()[0] == "EGYM Squat"


def test_every_how_to_says_auto_mode_and_the_tonnage():
    """His answers of 2026-11-08: "Yes auto for all", "I can still see the tonnage
    at the end of an auto set"."""
    for ex in ec.MACHINES:
        assert ex["mechanics"].endswith(ec._TAIL), ex["name"]
        assert "Auto mode" in ex["mechanics"] and "tonnage" in ex["mechanics"]
        assert "Classic" not in ex["mechanics"], ex["name"]
        assert "machine" not in ex["mechanics"].lower(), "the session screen never names a machine"
    assert "Auto mode" in ec.NOTE and "Classic" not in ec.NOTE


# ─── The maps and the record ─────────────────────────────────────────────────

def test_the_tonnage_only_names_are_the_circuits():
    assert ec.TONNAGE_ONLY == tc.TONNAGE_ONLY_EXERCISES == frozenset(tc._EGYM_MACHINES)


@pytest.mark.parametrize("name", ec.names())
def test_every_name_is_in_the_three_maps(name):
    assert name in tc.EXERCISE_BODY_REGION
    assert name in tc.EXERCISE_REGION_SHARES
    assert name in tc.EXERCISE_MOVEMENT_WEIGHT


def test_every_exercise_has_a_complete_workflow_record():
    """Key Rule 25: no exercise without its goal, reason, source and check."""
    assert set(ec.EGYM_PICKS) == set(ec.names())
    for name, p in ec.EGYM_PICKS.items():
        assert p.goal == "egym" and p.area and p.job and p.reason, name
        assert re.search(r"20\d\d-\d\d-\d\d", p.source), name
        assert p.better and p.better.startswith("checked 20"), name


@pytest.mark.parametrize("name", ec.names())
def test_every_name_lands_on_a_safety_rule(name):
    """A name with no rule reads "unknown", which is not "cleared"."""
    from services import rules
    assert rules.check_movement(name, 2)["severity"] in ("cleared", "caution"), name


def test_the_right_shoulder_machines_carry_the_right_arms_limit():
    from services import rules
    for name in ("EGYM Chest Press", "EGYM Triceps Dip"):
        r = rules.check_movement(name, 2)
        assert r["severity"] == "caution" and r["laterality"] == "right", name


# ─── The type ────────────────────────────────────────────────────────────────

def test_the_circuit_is_extra_and_a_logged_day():
    """His answers 1 and 2: "No, it's extra" (it never marks a plan day done)
    and "Yes, it does" (it counts as a training day for the failed-week rule)."""
    assert egs.EGYM_TYPE in Repository.SUPPLEMENTARY_SESSION_TYPES
    assert egs.EGYM_TYPE not in Repository.NOT_A_TRAINING_DAY_TYPES


# ─── The order ───────────────────────────────────────────────────────────────

def test_any_machine_may_run_next():
    """"I can change it up as I please": every machine its own group, none
    waiting on another; a move takes both its sets."""
    moves = egs.move_groups(ec.entries())
    assert moves == [{"group": i, "movable": True, "after": []} for i in range(N)]


def test_the_label_under_each_machine():
    assert egs.prescription() == "2 sets, one after the other"


def test_the_session_models_at_about_seventy_minutes():
    """28 EGYM sets of 60 s, a minute's rest between a machine's sets and his
    measured change to a gym station before each machine: a full session."""
    assert 65 <= egs.modelled_minutes(ec.entries()) <= 73


# ─── The tonnage ─────────────────────────────────────────────────────────────

def _row(name, day, sets, session="2026-11-09-egym0001", kind=egs.EGYM_TYPE):
    """A stored machine: each set one rep at its tonnage."""
    return {"session_id": session, "session_date": day, "movement_name": name, "movement_type": kind,
            "sets": [{"set_num": n, "reps": 1, "weight": kg, "rest": 60, "tut": 0,
                      "velocity": "controlled", "ts": ts} for n, (kg, ts) in enumerate(sets, start=1)]}


def test_the_last_session_gives_each_machine_its_tonnage_set_by_set():
    rows = [
        _row("EGYM Squat", "2026-11-02", [(900, "2026-11-02T08:00:00+01:00")], session="old"),
        _row("EGYM Squat", "2026-11-09", [(1240, "2026-11-09T08:00:00+01:00"),
                                          (1300, "2026-11-09T08:02:00+01:00")]),
        _row("EGYM Row", "2026-11-09", []),
        _row("Machine Chest Press", "2026-11-10", [(60, "2026-11-10T08:00:00+01:00")], kind="Push"),
    ]
    last = egs.last_tonnage(rows, date(2026, 11, 10))
    assert last == {"EGYM Squat": [1240.0, 1300.0]}, "a skipped machine has no line"
    assert egs.last_tonnage(rows, date(2026, 11, 5)) == {"EGYM Squat": [900.0]}
    assert egs.last_tonnage([], date(2026, 11, 5)) == {}


def test_the_caption_reads_the_last_tonnage_set_by_set():
    assert egs.tonnage_caption([1240.0, 1300.0]) == "Last time 1,240 kg and 1,300 kg"
    assert egs.tonnage_caption([900.0]) == "Last time 900 kg"
    assert egs.tonnage_caption(None) == "" and egs.tonnage_caption([]) == ""


def test_the_weekly_tonnage_counts_the_typed_tonnage():
    """"Yeah, add it to the weekly tonnage": a stored set is one rep at the tonnage."""
    rows = [_row("EGYM Squat", "2026-11-09", [(1240, "2026-11-09T08:00:00+01:00"),
                                              (1300, "2026-11-09T08:02:00+01:00")]),
            _row("EGYM Lat Pulldown", "2026-11-09", [(700, "2026-11-09T08:05:00+01:00")])]
    series, unmapped = tonnage.weekly_tonnage(rows, tc.EXERCISE_BODY_REGION,
                                              today=date(2026, 11, 9), weeks=1, traits={})
    assert not unmapped
    week = series[-1]
    assert week.sectors["lower_body"].kg == pytest.approx(2540)
    assert week.sectors["upper_body"].kg == pytest.approx(700)


def test_no_strength_reader_reads_a_tonnage_as_a_lift():
    """"1 rep at 1,240 kg" is a tonnage: it must never give a 1RM."""
    rows = [{**_row("EGYM Squat", "2026-11-09", [(1240, "2026-11-09T08:00:00+01:00")]),
             "exercise_rpe": None, "session_rpe": 6}]
    assert list(strength.qualifying_rows(rows, date(2026, 11, 9))) == []
    assert strength.best_observations(rows, today=date(2026, 11, 9)) == {}
