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
