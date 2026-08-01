"""Coverage tests for training_constants.EXERCISE_MOVEMENT_WEIGHT.

The table drives services/content_weighting.py, which scales raw Foster
Session AU before it reaches engine.acwr() and the Strain figure. A name
missing from the table is NOT inert — it falls back to
UNMAPPED_EXERCISE_WEIGHT (1.0), i.e. it is counted as fully-loaded lifting.
That default is correct for an UNKNOWN name (never silently suppress load)
and wrong for a KNOWN mobility drill, so the only real protection is
completeness.

tests/test_training_plan_stage2.py already pins this for PLAN_STAGE2. This
file pins it for PLAN (Stage 1), which was entirely absent until 2026-08-01
— 34 of the 63 exercise names in the logged history scored at 1.0, inflating
Strain and the ACWR chronic term across the whole Stage 1 era.
"""

import training_constants as tc
import training_plan as tp
from services import content_weighting as cw


_VALID_CATEGORIES = {
    "squat", "hinge", "pull", "upper_push",
    "bodyweight_compound", "isolation", "mobility_core",
}


def _plan_names(plan):
    return {ex["name"] for day in plan.values() for ex in day.get("exercises", [])}


def test_all_stage1_exercise_names_are_mapped_to_a_movement_weight():
    for day_num, day in tp.PLAN.items():
        for ex in day["exercises"]:
            assert ex["name"] in tc.EXERCISE_MOVEMENT_WEIGHT, (
                f"Day {day_num} exercise {ex['name']!r} missing from "
                f"EXERCISE_MOVEMENT_WEIGHT — it would be counted as fully-loaded "
                f"lifting by services.content_weighting"
            )


def test_every_entry_uses_a_known_category_and_a_sane_weight():
    for name, entry in tc.EXERCISE_MOVEMENT_WEIGHT.items():
        category, weight = entry
        assert category in _VALID_CATEGORIES, f"{name!r} has unknown category {category!r}"
        assert 0.0 < weight <= 1.5, f"{name!r} has implausible weight {weight}"


def test_category_to_weight_mapping_is_consistent():
    """One category must mean one weight everywhere, or the multiplier stops
    being interpretable."""
    by_category: dict[str, set[float]] = {}
    for category, weight in tc.EXERCISE_MOVEMENT_WEIGHT.values():
        by_category.setdefault(category, set()).add(weight)
    for category, weights in by_category.items():
        assert len(weights) == 1, f"category {category!r} has multiple weights: {weights}"


def test_bodyweight_compound_sits_between_isolation_and_loaded_upper_body():
    """The tier exists precisely to stop a bodyweight chair sit-to-stand
    being scored as either release work or a barbell squat."""
    weights = {c: w for c, w in tc.EXERCISE_MOVEMENT_WEIGHT.values()}
    assert weights["isolation"] < weights["bodyweight_compound"] < weights["pull"]
    assert weights["bodyweight_compound"] < weights["squat"]


def test_mobility_variants_of_the_same_movement_share_one_weight():
    """A movement must not change weight just because the training block
    changed its name suffix."""
    families = [
        ("Bird-Dog", "Bird-Dog (Extended Hold)", "Bird-Dog with Full Reach"),
        ("Dead Bug", "Dead Bug (Progression — 3s Hold)"),
        ("McGill Curl-Up (Progressed)", "McGill Modified Curl-Up"),
    ]
    for family in families:
        present = [tc.EXERCISE_MOVEMENT_WEIGHT[n][1]
                   for n in family if n in tc.EXERCISE_MOVEMENT_WEIGHT]
        assert len(set(present)) == 1, f"{family} disagree on weight: {present}"


def test_a_pure_mobility_day_is_weighted_far_below_a_loaded_day():
    """End-to-end through content_weighting, using real Stage 1 and Stage 2
    exercise names and equal time per exercise."""
    mobility_day = [
        {"name": "Supine Knee-to-Chest", "seconds": 180},
        {"name": "Cat-Cow (Slow Flow)",  "seconds": 180},
        {"name": "Diaphragmatic Breathing", "seconds": 180},
    ]
    loaded_day = [
        {"name": "Romanian Deadlift (DB)", "seconds": 180},
        {"name": "Goblet Squat",           "seconds": 180},
        {"name": "Lat Pulldown",           "seconds": 180},
    ]
    m = cw.day_content_multiplier(mobility_day)
    loaded = cw.day_content_multiplier(loaded_day)
    assert m["unmapped_names"] == []
    assert loaded["unmapped_names"] == []
    assert m["multiplier"] == 0.25
    assert loaded["multiplier"] > 3 * m["multiplier"]


def test_stage1_names_no_longer_hit_the_unmapped_fallback():
    """The specific regression: before 2026-08-01 this day scored 1.0."""
    day = [{"name": n, "seconds": 120} for n in sorted(_plan_names(tp.PLAN))]
    result = cw.day_content_multiplier(day)
    assert result["unmapped_names"] == []
    assert result["multiplier"] < cw.UNMAPPED_EXERCISE_WEIGHT
