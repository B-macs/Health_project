"""WP-44, the muscle balance (the athlete, 2026-11-03): "if I can do 100kg row
and 20kg press, it is clear there is an imbalance, Bar Chart should show which
side is stronger and which is weaker"; "both the data from training and the
seca profile should add to this metric"; method "A" (each lift against a
published standard at his body weight); "Ok start with 5" pairs."""
from __future__ import annotations

from datetime import date

import pytest

from services import imbalance, strength
from services import strength_standards as standards

TODAY = date(2026, 11, 3)
ONE_ARM = {"Single-Arm DB Row", "Single-Arm Cable Y Raise"}
REGION = {"Single-Arm DB Row": "upper_body", "Single-Arm Cable Y Raise": "upper_body",
          "Machine Chest Press": "upper_body", "Hack Squat": "lower_body"}


def _row(name, weight, reps=10, day="2026-11-01", **left):
    sets = [{"reps": reps, "weight": weight, **left}] * 3
    return {"movement_name": name, "session_date": day, "sets": sets}


def _pairs(rows, body_weight=85.0, seca=None):
    out = imbalance.balance(rows, today=TODAY, body_weight_kg=body_weight, seca_segments=seca,
                            one_arm=ONE_ARM, region_of=REGION)
    return {p["key"]: p for p in out["pairs"]}, out


def test_the_five_pairs_in_screen_order():
    _, out = _pairs([])
    assert [p["key"] for p in out["pairs"]] == [
        "chest_back", "front_rear_shoulder", "quads_hamstrings", "arms", "legs"]


def test_a_standard_is_read_at_his_body_weight_between_the_rows():
    assert imbalance.standard_kg("Machine Chest Press", 85.0) == 93
    assert imbalance.standard_kg("Machine Chest Press", 82.5) == pytest.approx(91.0)
    assert imbalance.standard_kg("Machine Chest Press", 60.0) == 80, "the nearest row below the table"
    assert imbalance.standard_kg("Machine Chest Press", 85.0, "Beginner") == 42
    assert imbalance.standard_kg("Lat Pulldown", 85.0) is None


def test_every_lift_of_a_muscle_pair_has_a_standard():
    for pair in imbalance.MUSCLE_PAIRS:
        for name in pair.left_lifts + pair.right_lifts:
            assert name in standards.STANDARDS, name


def test_his_example_a_heavy_row_and_a_light_press_reads_back_stronger():
    """Two machines: each lift against its own standard, never kilogram against kilogram."""
    pairs, _ = _pairs([_row("Machine Chest Press", 45.0), _row("Single-Arm DB Row", 35.0)])
    chest = pairs["chest_back"]
    assert chest["stronger"] == "right" and chest["right"] == "Back"
    assert chest["left_share"] < 0.5
    assert chest["words"].startswith("Back is ") and "stronger than chest" in chest["words"]


def test_under_ten_percent_apart_reads_about_even():
    std_press = imbalance.standard_kg("Machine Chest Press", 85.0)
    std_row = imbalance.standard_kg("Single-Arm DB Row", 85.0)
    # Weights whose one-rep maxes sit at the same share of their standards.
    press, row = std_press * 0.6, std_row * 0.6
    pairs, _ = _pairs([_row("Machine Chest Press", press), _row("Single-Arm DB Row", row)])
    assert pairs["chest_back"]["stronger"] is None
    assert pairs["chest_back"]["words"].startswith("About even")


def test_a_lift_under_the_beginner_standard_is_left_out_and_says_why():
    """The shoulder press logged at 5 kg would read the pair hundreds of percent apart."""
    pairs, _ = _pairs([_row("Machine Shoulder Press", 5.0), _row("Reverse Cable Crossover", 6.0, reps=15)])
    shoulders = pairs["front_rear_shoulder"]
    assert shoulders["stronger"] is None and shoulders["left_share"] is None
    assert any("under the beginner standard" in p for p in shoulders["parts"])


def test_a_pair_without_data_says_so_and_draws_no_bar():
    pairs, _ = _pairs([_row("Hack Squat", 70.0)])
    quads = pairs["quads_hamstrings"]
    assert quads["left_share"] is None and quads["words"].startswith("Not enough data")


def test_training_and_the_seca_scan_count_equally_for_left_and_right():
    seca = {"left_arm": 2.2, "right_arm": 2.0, "left_leg": 6.6, "right_leg": 6.4}
    # Training: the left arm 10 reps where the right did 12, same weight.
    rows = [_row("Single-Arm DB Row", 25.0, reps=12, reps_left=10)]
    pairs, _ = _pairs(rows, seca=seca)
    arms = pairs["arms"]
    trained = strength.estimated_1rm(25.0, 10, 9.0)[0] / strength.estimated_1rm(25.0, 12, 9.0)[0]
    assert arms["left_value"] == pytest.approx(100 * (trained + 1.1) / 2, abs=0.1)
    assert arms["right_value"] == 100.0
    assert any(p.startswith("SECA scan") for p in arms["parts"])
    assert any(p.startswith("Single-Arm DB Row") for p in arms["parts"])
    legs = pairs["legs"]
    assert legs["left_value"] == pytest.approx(100 * 6.6 / 6.4, abs=0.1), "the scan alone"


def test_a_left_arm_stored_only_where_it_differs_reads_as_the_right():
    pairs, _ = _pairs([_row("Single-Arm DB Row", 25.0)])
    assert pairs["arms"]["left_value"] == 100.0 and pairs["arms"]["stronger"] is None


def test_without_a_body_weight_the_muscle_pairs_wait_and_left_right_still_reads():
    pairs, out = _pairs([_row("Machine Chest Press", 45.0), _row("Single-Arm DB Row", 35.0)],
                        body_weight=None, seca={"left_arm": 2.2, "right_arm": 2.0})
    assert pairs["chest_back"]["left_share"] is None
    assert pairs["arms"]["left_share"] is not None
    assert out["body_weight_kg"] is None


def test_sessions_older_than_eight_weeks_do_not_count():
    pairs, _ = _pairs([_row("Machine Chest Press", 45.0, day="2026-08-01"),
                       _row("Single-Arm DB Row", 35.0)])
    assert pairs["chest_back"]["left_share"] is None


def test_the_method_names_the_source():
    _, out = _pairs([])
    assert "Strength Level" in out["method"] and "about even" in out["method"]
