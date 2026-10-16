"""Which side a one-side exercise starts on alternates by the day.

The athlete, 2026-10-16: "We need to switch the right and left so that some
days I start with left and others right side to balance out which arm goes
first." Until then every unilateral exercise started on the right.

services/sessions.py holds the rule (first_side) and the two helpers the
training screen uses to keep each side's numbers (side_keys, ready_side);
these tests pin the rule, the numbers each side records, and that the screen
has no hard-coded right-then-left order left in it.
"""
import ast
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from services import sessions

_VIEW = Path(__file__).resolve().parent.parent / "views" / "training.py"
_SRC = _VIEW.read_text(encoding="utf-8")


# ── the rule ─────────────────────────────────────────────────────────────────

def test_the_first_side_changes_every_day():
    day = date(2026, 10, 19)
    sides = [sessions.first_side(day + timedelta(days=i)) for i in range(6)]
    assert set(sides) == {"left", "right"}
    assert all(a != b for a, b in zip(sides, sides[1:]))


def test_each_weekday_starts_on_each_side_once_in_two_weeks():
    monday = date(2026, 10, 19)
    for weekday in range(7):
        one = sessions.first_side(monday + timedelta(days=weekday))
        two = sessions.first_side(monday + timedelta(days=weekday + 7))
        assert {one, two} == {"left", "right"}, weekday


def test_his_usual_week_starts_two_days_on_each_side():
    monday = date(2026, 10, 19)
    week = [sessions.first_side(monday + timedelta(days=d)) for d in (0, 1, 3, 4)]
    assert week.count("left") == 2 and week.count("right") == 2


def test_the_same_day_always_gives_the_same_side():
    assert sessions.first_side(date(2026, 10, 16)) == sessions.first_side(date(2026, 10, 16))


def test_other_side():
    assert (sessions.other_side("right"), sessions.other_side("left")) == ("left", "right")


def test_the_overview_names_the_first_side_only_when_it_matters():
    day = date(2026, 10, 16)
    uni = [{"name": "Single-Arm DB Row", "laterality": "unilateral"}]
    note = sessions.first_side_note(uni, day)
    assert f"on the {sessions.first_side(day)} side today" in note
    assert sessions.first_side_note([{"name": "Lat Pulldown", "laterality": "bilateral"}],
                                    day) == ""


# ── each side keeps its own numbers ──────────────────────────────────────────

def test_the_right_side_owns_the_entry_and_the_left_its_own_pair():
    assert sessions.side_keys("right") == ("reps", "weight_kg")
    assert sessions.side_keys("left") == ("reps_left", "weight_kg_left")


def test_right_first_the_left_mirrors_the_right():
    entry = {"reps": 10, "weight_kg": 22.5}
    sessions.ready_side(entry, "right", "right")
    sessions.ready_side(entry, "left", "right")
    assert (entry["reps_left"], entry["weight_kg_left"]) == (10, 22.5)


def test_left_first_the_left_starts_from_the_prescription_and_the_right_mirrors_it():
    entry = {"reps": 10, "weight_kg": 22.5}
    sessions.ready_side(entry, "left", "left")
    assert (entry["reps_left"], entry["weight_kg_left"]) == (10, 22.5)
    entry["reps_left"] = 9                      # the left side did 9 on the stepper
    sessions.ready_side(entry, "right", "left")
    assert (entry["reps"], entry["weight_kg"]) == (9, 22.5)


def test_an_unedited_second_side_follows_the_first_from_set_to_set():
    # The quirk this fixed: a right side cut from 10 to 9 in set 2 left the
    # unedited left at 10, shown as "edited" and logged as 10.
    entry = {"reps": 10, "weight_kg": 22.5}
    sessions.ready_side(entry, "left", "right")      # set 1, second side
    entry["reps"] = 9                                # set 2, first side
    sessions.ready_side(entry, "left", "right")      # set 2, second side
    assert entry["reps_left"] == 9


def test_an_edited_second_side_keeps_its_own_numbers():
    entry = {"reps": 10, "weight_kg": 22.5}
    sessions.ready_side(entry, "left", "right")
    entry["weight_kg_left"] = 20.0                   # the weaker side, edited
    entry["reps"] = 9
    sessions.ready_side(entry, "left", "right")
    assert (entry["reps_left"], entry["weight_kg_left"]) == (10, 20.0)


@pytest.mark.parametrize("first", ["right", "left"])
def test_the_set_record_means_the_same_whichever_side_went_first(first):
    """The record's reps/weight are the right side's and reps_left/weight_left
    the left's, on a left-first day as on a right-first day."""
    ex = {"type": "reps", "reps": 10, "weight_kg": 22.5, "laterality": "unilateral",
          "rest_seconds": 60}
    entry = {"reps": 10, "weight_kg": 22.5}
    second = sessions.other_side(first)
    sessions.ready_side(entry, first, first)
    sessions.ready_side(entry, second, first)
    entry[sessions.side_keys("left")[0]] = 8          # the left side made 8
    rec = sessions.build_set_record(ex, 1, entry, "2026-10-16T10:00:00")
    assert (rec["reps"], rec["reps_left"]) == (10, 8)


# ── the bell swaps after the FIRST side ──────────────────────────────────────

@pytest.mark.parametrize("first,side,expected", [
    ("right", "right", "switch"), ("right", "left", "finish"),
    ("left", "left", "switch"), ("left", "right", "finish"),
])
def test_the_hold_swaps_after_the_first_side(first, side, expected):
    assert sessions.hold_ending("hold", is_uni=True, side=side, cur_set=1, total_sets=2,
                                first=first) == expected


def test_a_left_first_last_set_ends_on_the_right():
    assert sessions.hold_ending("hold_reps", is_uni=True, side="right", cur_set=3,
                                total_sets=3, cur_rep=8, reps_per_set=8,
                                first="left") == "done"


# ── the screen has no fixed right-then-left order left ───────────────────────

def test_the_screen_never_sets_the_side_to_a_fixed_value():
    fixed = re.findall(r'tp_side\s*=\s*"(?:left|right)"', _SRC)
    assert fixed == [], fixed


def test_both_start_buttons_fix_the_first_side_from_the_rule():
    assert _SRC.count("st.session_state.tp_first_side = sess.first_side(date.today())") == 2


def test_both_hold_timers_pass_the_first_side():
    assert _SRC.count("first=_first)") == 2


def test_no_button_or_caption_names_a_fixed_first_side():
    for text in ('_btn_label = "✓ Right Side Done"', '"Edit left side"', 'f"Left side:',
                 '"same as right side"'):
        assert text not in _SRC, text


def test_the_first_side_is_checkpointed_with_the_session():
    assert "tp_first_side" in sessions.CHECKPOINT_FIELDS
    tree = ast.parse(_SRC)
    init = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_init_state")
    assert '"tp_first_side"' in ast.get_source_segment(_SRC, init)
