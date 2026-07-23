"""Tests for services/content_weighting.py — content-aware Session AU
weighting for Strain/ACWR."""

from services import content_weighting as cw


def test_day_content_multiplier_zero_total_returns_neutral_one():
    result = cw.day_content_multiplier([{"name": "Anything", "seconds": 0}])
    assert result["multiplier"] == 1.0
    assert result["plain_seconds"] == 0


def test_day_content_multiplier_empty_list_returns_neutral_one():
    assert cw.day_content_multiplier([])["multiplier"] == 1.0


def test_day_content_multiplier_unmapped_name_contributes_at_full_weight():
    result = cw.day_content_multiplier([{"name": "Brand New Exercise", "seconds": 100}])
    assert result["multiplier"] == 1.0
    assert result["unmapped_names"] == ["Brand New Exercise"]


def test_day_content_multiplier_mixed_mapped_and_unmapped():
    # 100s at 1.3 (Goblet Squat) + 100s at 1.0 fallback (unmapped) = 230/200
    result = cw.day_content_multiplier([
        {"name": "Goblet Squat", "seconds": 100},
        {"name": "Something New", "seconds": 100},
    ])
    assert result["multiplier"] == 1.15
    assert result["unmapped_names"] == ["Something New"]


def test_day_content_multiplier_simple_two_exercise_weighted_average():
    # 60s squat (1.3) + 60s mobility_core (0.25): (78+15)/120 = 0.775
    result = cw.day_content_multiplier([
        {"name": "Goblet Squat", "seconds": 60},
        {"name": "Bird-Dog", "seconds": 60},
    ])
    assert result["multiplier"] == 0.775


# ─── Integration: locks in the exact confirmed Session A/B/C multipliers ───

def _day_exercise_seconds(day: dict) -> list[dict]:
    from services import sessions as sess
    return [
        {"name": ex["name"], "seconds": sess.exercise_seconds_from_sets(sess.make_sets_data(ex))}
        for ex in day["exercises"]
    ]


def test_session_a_week2_multiplier_matches_confirmed_value():
    import training_plan as tp
    result = cw.day_content_multiplier(_day_exercise_seconds(tp._s2_session_a(2)))
    assert result["multiplier"] == 0.435
    assert result["unmapped_names"] == []


def test_session_b_week2_multiplier_matches_confirmed_value():
    import training_plan as tp
    result = cw.day_content_multiplier(_day_exercise_seconds(tp._s2_session_b(2)))
    assert result["multiplier"] == 0.509
    assert result["unmapped_names"] == []


def test_session_c_week2_multiplier_matches_confirmed_value():
    import training_plan as tp
    result = cw.day_content_multiplier(_day_exercise_seconds(tp._s2_session_c(2)))
    assert result["multiplier"] == 0.384
    assert result["unmapped_names"] == []
