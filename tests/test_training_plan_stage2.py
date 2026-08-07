"""
Tests for training_plan.PLAN_STAGE2 — the Stage 2A 28-day gym strength block.

Scoped to PLAN_STAGE2 only: PLAN (Stage 1) predates the always-include
release-protocol convention being applied uniformly (e.g. PLAN[9] omits it),
an existing inconsistency out of scope here. These tests lock in that the
new Stage 2 content is internally consistent, not that Stage 1 is.
"""

from services import rules
import training_constants as tc
import training_plan as tp


def test_plan_stage2_has_exactly_28_days():
    assert sorted(tp.PLAN_STAGE2.keys()) == list(range(1, 29))


def test_every_day_has_a_nonempty_exercise_list():
    for day_num, day in tp.PLAN_STAGE2.items():
        assert day["exercises"], f"Day {day_num} has no exercises"


def test_every_exercise_carries_a_weight_kg_key():
    # Present (even if None for bodyweight work) — this is the field
    # make_sets_data reads to populate ExerciseEntry.total_volume_kg.
    for day_num, day in tp.PLAN_STAGE2.items():
        for ex in day["exercises"]:
            assert "weight_kg" in ex, f"Day {day_num} exercise {ex['name']!r} missing weight_kg"


def test_every_day_includes_the_always_release_protocol():
    from training_plan import UPPER_GLUTE_RELEASE, PIRIFORMIS_PNF
    # Day 28 mirrors Stage 1's Day 21 reassessment format (which itself leads
    # with the hip-capsule/coxa-saltans check, not the always-release block)
    # — an intentional, pre-existing convention for assessment days, not
    # scoped here.
    for day_num, day in tp.PLAN_STAGE2.items():
        if day_num == 28:
            continue
        names = {ex["name"] for ex in day["exercises"]}
        assert UPPER_GLUTE_RELEASE["name"] in names, f"Day {day_num} missing upper glute release"
        assert PIRIFORMIS_PNF["name"] in names, f"Day {day_num} missing piriformis PNF"


def test_loaded_sessions_never_use_the_original_mistargeted_hip_capsule_cue():
    # RIGHT_HIP_CAPSULE (the original cross-body cue) was confirmed on
    # 2026-07-08 to mistarget the front of both hips — Stage 2A must only
    # ever use RIGHT_HIP_CAPSULE_REVISED.
    from training_plan import RIGHT_HIP_CAPSULE
    for day_num, day in tp.PLAN_STAGE2.items():
        names = {ex["name"] for ex in day["exercises"]}
        assert RIGHT_HIP_CAPSULE["name"] not in names, (
            f"Day {day_num} uses the original (mistargeted) hip capsule cue"
        )


def test_no_overhead_or_standing_press_anywhere_in_stage2():
    # Deliberate design decision (Latarjet history, documented left-tilt
    # instability under overhead load) — regression-lock that no exercise
    # name in the whole block trips the "overhead press" rule.
    for day in tp.PLAN_STAGE2.values():
        for ex in day["exercises"]:
            result = rules.check_movement(ex["name"], current_stage=2)
            assert not (result["severity"] == "caution" and "overhead" in result["reason"].lower()), (
                f"{ex['name']!r} matches the overhead-press rule"
            )


def test_no_contraindicated_exercise_anywhere_in_stage2():
    always_contra = set(rules.get_contraindicated_always())
    for day_num, day in tp.PLAN_STAGE2.items():
        for ex in day["exercises"]:
            name_lower = ex["name"].lower()
            for banned in always_contra:
                assert not (banned in name_lower or name_lower in banned), (
                    f"Day {day_num} exercise {ex['name']!r} matches always-contraindicated {banned!r}"
                )


def test_bulgarian_split_squat_is_bodyweight_through_week_2():
    # Per the block's slow-track progression design: bodyweight Weeks 1-2,
    # +2.5kg from Week 3.
    for day_num in (5, 12):  # Session C, Weeks 1 and 2
        day = tp.PLAN_STAGE2[day_num]
        bss = next(ex for ex in day["exercises"] if ex["name"] == "Bulgarian Split Squat")
        assert bss["weight_kg"] is None
    for day_num in (19, 26):  # Session C, Weeks 3 and 4
        day = tp.PLAN_STAGE2[day_num]
        bss = next(ex for ex in day["exercises"] if ex["name"] == "Bulgarian Split Squat")
        assert bss["weight_kg"] == 2.5


def test_fast_track_lifts_progress_every_week():
    # Face Pull (Cable) is fast-track: +2.5kg every weekly exposure.
    session_a_days = [1, 8, 15, 22]
    loads = []
    for day_num in session_a_days:
        day = tp.PLAN_STAGE2[day_num]
        face_pull = next(ex for ex in day["exercises"] if ex["name"] == "Face Pull (Cable)")
        loads.append(face_pull["weight_kg"])
    assert loads == [10.0, 12.5, 15.0, 17.5]


def test_day_28_is_a_reassessment_day_not_a_loaded_session():
    day28 = tp.PLAN_STAGE2[28]
    names = {ex["name"] for ex in day28["exercises"]}
    assert "5-Minute Walk + Stair Assessment" in names
    assert "McGill Big 3 — Quality Screen" in names


def test_all_stage2_exercise_names_are_mapped_to_a_body_region():
    for day_num, day in tp.PLAN_STAGE2.items():
        for ex in day["exercises"]:
            assert ex["name"] in tc.EXERCISE_BODY_REGION, (
                f"Day {day_num} exercise {ex['name']!r} missing from EXERCISE_BODY_REGION"
            )


def test_all_stage2_exercise_names_are_mapped_to_a_movement_weight():
    for day_num, day in tp.PLAN_STAGE2.items():
        for ex in day["exercises"]:
            assert ex["name"] in tc.EXERCISE_MOVEMENT_WEIGHT, (
                f"Day {day_num} exercise {ex['name']!r} missing from EXERCISE_MOVEMENT_WEIGHT"
            )


# ─── equipment_type / band_tier tagging (live-session steppers feature) ────

_EXPECTED_EQUIPMENT_TYPE = {
    "Goblet Squat": "dumbbell", "Incline DB Press": "dumbbell",
    "Romanian Deadlift (DB)": "dumbbell", "Single-Arm DB Row": "dumbbell",
    "Bulgarian Split Squat": "dumbbell", "Prone Y-Raise (Scapular)": "dumbbell",
    "Face Pull (Cable)": "cable", "Lat Pulldown": "cable", "Pallof Press (Cable)": "cable",
    "Hip Thrust (Loaded)": "plate",
    "Lateral Band Walk": "band",
}


def test_every_weighted_exercise_has_the_expected_equipment_type():
    for day_num, day in tp.PLAN_STAGE2.items():
        for ex in day["exercises"]:
            if ex["name"] in _EXPECTED_EQUIPMENT_TYPE:
                assert ex.get("equipment_type") == _EXPECTED_EQUIPMENT_TYPE[ex["name"]], (
                    f"Day {day_num} {ex['name']!r} equipment_type={ex.get('equipment_type')!r}"
                )


def test_no_unexpected_exercise_carries_equipment_type():
    # Regression guard: catches a future _ex() call accidentally tagged
    # equipment_type without being added to _EXPECTED_EQUIPMENT_TYPE above.
    for day_num, day in tp.PLAN_STAGE2.items():
        for ex in day["exercises"]:
            if ex.get("equipment_type"):
                assert ex["name"] in _EXPECTED_EQUIPMENT_TYPE, (
                    f"Day {day_num} {ex['name']!r} has equipment_type={ex['equipment_type']!r} "
                    f"but isn't in the expected-tag test list"
                )


def test_stage1_plan_exercises_never_have_equipment_type():
    for day_num, day in tp.PLAN.items():
        for ex in day["exercises"]:
            assert ex.get("equipment_type") is None, f"Stage 1 day {day_num} {ex['name']!r} unexpectedly tagged"


# ─── per-exercise weight increment (feature 8: machines calibrated in their
#     own arbitrary units, not kg) ──────────────────────────────────────────

_EXPECTED_UNIT_BASED = {"Face Pull (Cable)", "Pallof Press (Cable)"}


def test_face_pull_and_pallof_press_are_unit_based_not_kg():
    for day_num, day in tp.PLAN_STAGE2.items():
        for ex in day["exercises"]:
            if ex["name"] in _EXPECTED_UNIT_BASED:
                assert ex["increment_unit"] == "unit", (
                    f"Day {day_num} {ex['name']!r} increment_unit={ex['increment_unit']!r}"
                )
                assert ex["increment_size"] == 1, (
                    f"Day {day_num} {ex['name']!r} increment_size={ex['increment_size']!r}"
                )


def test_no_unexpected_exercise_is_unit_based():
    # Regression guard, same pattern as test_no_unexpected_exercise_carries_
    # equipment_type above: catches a future _ex() call accidentally left
    # unit-based (or a new one that should be) without updating this list.
    for day_num, day in tp.PLAN_STAGE2.items():
        for ex in day["exercises"]:
            if ex.get("increment_unit") != "kg":
                assert ex["name"] in _EXPECTED_UNIT_BASED, (
                    f"Day {day_num} {ex['name']!r} increment_unit={ex.get('increment_unit')!r} "
                    f"but isn't in the expected unit-based list"
                )


def test_every_other_weighted_exercise_defaults_to_2_5kg_increment():
    for day_num, day in tp.PLAN_STAGE2.items():
        for ex in day["exercises"]:
            if ex.get("equipment_type") and ex["name"] not in _EXPECTED_UNIT_BASED:
                assert ex["increment_size"] == 2.5, (
                    f"Day {day_num} {ex['name']!r} increment_size={ex['increment_size']!r}"
                )
                assert ex["increment_unit"] == "kg"


def test_band_exercise_never_carries_weight_kg():
    for day_num, day in tp.PLAN_STAGE2.items():
        for ex in day["exercises"]:
            if ex.get("equipment_type") == "band":
                assert ex.get("weight_kg") is None, f"Day {day_num} {ex['name']!r} band exercise has weight_kg"


def test_lateral_band_walk_tier_progresses_green_to_blue():
    # Weeks 1-2 -> Green (light), Weeks 3-4 -> Blue (medium), per the
    # existing per-week band_note progression this field replaced.
    for day_num in (5, 12):  # Session C, Weeks 1-2
        walk = next(ex for ex in tp.PLAN_STAGE2[day_num]["exercises"] if ex["name"] == "Lateral Band Walk")
        assert walk["band_tier"] == "Green"
    for day_num in (19, 26):  # Session C, Weeks 3-4
        walk = next(ex for ex in tp.PLAN_STAGE2[day_num]["exercises"] if ex["name"] == "Lateral Band Walk")
        assert walk["band_tier"] == "Blue"


def test_non_band_exercises_never_carry_a_band_tier():
    for day_num, day in tp.PLAN_STAGE2.items():
        for ex in day["exercises"]:
            if ex.get("equipment_type") not in (None, "band"):
                assert ex.get("band_tier") is None, f"Day {day_num} {ex['name']!r} unexpectedly has band_tier"


# ─── day_type — the session-priority taxonomy (services/scheduling.py) ──────
# All-or-nothing by design: with recovery days typed but gym days not (or
# vice versa), scheduling.swap_pairs_for_shift's hardened partner check sees
# a known partner and an unknown mover and silently refuses every live
# readiness shift. This coverage test makes partial adoption a test failure.

def test_every_stage2_day_carries_a_valid_day_type():
    from services import scheduling
    for day_num, day in tp.PLAN_STAGE2.items():
        assert day.get("day_type") in scheduling.SESSION_PRIORITY, (
            f"Day {day_num} day_type={day.get('day_type')!r} is not a valid session type"
        )


def test_day_type_main_if_and_only_if_is_gym_session_true():
    # Days 14/28 carry no is_gym_session key at all (an authoring accident
    # day_type now makes explicit): absent reads False, and their type is
    # "test", so the biconditional holds across all 28 days.
    for day_num, day in tp.PLAN_STAGE2.items():
        assert (day.get("day_type") == "main") == bool(day.get("is_gym_session")), (
            f"Day {day_num}: day_type={day.get('day_type')!r} "
            f"vs is_gym_session={day.get('is_gym_session')!r}"
        )
    assert tp.PLAN_STAGE2[14]["day_type"] == "test"
    assert tp.PLAN_STAGE2[28]["day_type"] == "test"


def test_stage1_plan_days_never_carry_day_type():
    # Stage 1 is deliberately untyped: the priority machinery is inert for
    # it, and typing it now would be a behaviour change to a finished block.
    for day_num, day in tp.PLAN.items():
        assert "day_type" not in day, f"Stage 1 day {day_num} unexpectedly carries day_type"


def test_every_stage2_gym_day_is_followed_by_a_strictly_lower_priority_day():
    # The live-plan property the readiness auto-shift's continued operation
    # depends on: every gym day's swap partner (the next calendar day) must
    # be strictly outranked, or the hardened partner check would refuse the
    # swap and the auto-shift would silently stop firing.
    from services import scheduling
    for day_num, day in tp.PLAN_STAGE2.items():
        if day.get("is_gym_session"):
            neighbor = tp.PLAN_STAGE2.get(day_num + 1)
            assert neighbor is not None, f"Gym day {day_num} has no next-day partner"
            assert scheduling.can_overwrite(
                scheduling.day_type(day), scheduling.day_type(neighbor)
            ), f"Gym day {day_num}'s partner (day {day_num + 1}) is not strictly lower priority"
