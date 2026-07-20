"""
Tests for services/rules.py, ported verbatim from the old flat tests.py runner.
"""

import ast

from services import rules
from tests._legacy_check import check


def test_rules_check_movement():
    # Always contraindicated
    heavy_dl = rules.check_movement("heavy deadlift", current_stage=1)
    check("heavy deadlift Stage 1 -> contraindicated",   heavy_dl["severity"], "contraindicated")

    barbell_dl = rules.check_movement("barbell deadlift", current_stage=3)
    check("barbell deadlift Stage 3 -> still contraindicated (stage_cap=1)", barbell_dl["severity"], "contraindicated")

    # Cleared
    bird_dog = rules.check_movement("bird-dog", current_stage=1)
    check("bird-dog Stage 1 -> cleared",               bird_dog["severity"], "cleared")

    cat_cow = rules.check_movement("cat-cow", current_stage=1)
    check("cat-cow Stage 1 -> cleared",                cat_cow["severity"], "cleared")

    walking = rules.check_movement("walking", current_stage=1)
    check("walking Stage 1 -> cleared",                walking["severity"], "cleared")

    # Caution — not available in Stage 1 but clears from Stage 2
    rdl_s1 = rules.check_movement("romanian deadlift", current_stage=1)
    check("RDL Stage 1 -> contraindicated (stage_cap=2)", rdl_s1["severity"], "contraindicated")

    rdl_s2 = rules.check_movement("romanian deadlift", current_stage=2)
    check("RDL Stage 2 -> caution",                    rdl_s2["severity"], "caution")

    # Unknown movement
    unknown = rules.check_movement("underwater basket weaving", current_stage=1)
    check("unknown movement -> severity unknown",       unknown["severity"], "unknown")

    # Stage constraints
    s1_constraints = rules.get_stage_constraints(1)
    check("Stage 1 ACWR ceiling = 1.2",                s1_constraints["acwr_ceiling"], 1.2)
    check("Stage 2 ACWR ceiling = 1.3",                rules.get_stage_constraints(2)["acwr_ceiling"], 1.3)
    check("Stage 3 ACWR ceiling = 1.5",                rules.get_stage_constraints(3)["acwr_ceiling"], 1.5)
    check("Stage 1 RPE ceiling = 7",                   s1_constraints["rpe_ceiling"], 7)

    # Cleared list for Stage 1 contains known safe movements
    cleared_s1 = rules.get_cleared_for_stage(1)
    check("bird-dog in Stage 1 cleared list",          "bird-dog" in cleared_s1, True)
    check("walking in Stage 1 cleared list",           "walking" in cleared_s1, True)

    # Contraindicated list
    always_contra = rules.get_contraindicated_always()
    check("heavy deadlift always contraindicated",     "heavy deadlift" in always_contra, True)
    check("jumping always contraindicated",            "jumping" in always_contra, True)


def test_forward_fold_rule_matches_named_variants():
    # Generic "forward fold" rule must catch pose names that aren't the exact
    # "seated forward fold" keyword (e.g. yoga poses authored in services/yoga.py).
    butterfly = rules.check_movement("Butterfly Forward Fold", current_stage=1)
    assert butterfly["severity"] == "contraindicated"

    straddle = rules.check_movement("Straddle Forward Fold", current_stage=3)
    assert straddle["severity"] == "contraindicated"  # stage_cap=1, always contraindicated


def test_stage2_gym_exercises_clear_correctly_at_stage_2():
    # Goblet Squat and Bulgarian Split Squat both match the "squat" caution
    # rule (stage_cap=2) — confirm they're usable at Stage 2, not just
    # theoretically caution-flagged.
    goblet = rules.check_movement("Goblet Squat", current_stage=2)
    assert goblet["severity"] == "caution"
    assert goblet["stage_ok"] is True

    bss = rules.check_movement("Bulgarian Split Squat", current_stage=2)
    assert bss["severity"] == "caution"
    assert bss["stage_ok"] is True


def test_romanian_deadlift_db_does_not_collide_with_hard_deadlift_stops():
    # "Romanian Deadlift (DB)" must match the "romanian deadlift" caution
    # rule, not the always-contraindicated heavy/barbell/conventional
    # deadlift rules — check_movement takes the strictest MATCHING rule, so
    # this locks in that the naming choice doesn't accidentally match both.
    rdl = rules.check_movement("Romanian Deadlift (DB)", current_stage=2)
    assert rdl["severity"] == "caution"
    assert rdl["stage_ok"] is True


def test_incline_db_press_does_not_match_overhead_press_rule():
    # Regression lock for the deliberate no-overhead-press design in Stage 2A
    # (patient_profile.py finding #6 — Latarjet history, documented left-tilt
    # instability under overhead load): Incline DB Press must NOT trip the
    # "overhead press" caution rule, since it's a different, back-supported
    # pattern intentionally substituted in its place.
    incline = rules.check_movement("Incline DB Press", current_stage=2)
    assert incline["severity"] == "unknown"


def test_hip_thrust_and_pulling_exercises_are_unrestricted_by_omission():
    # No MOVEMENT_RULES entry matches these — intentional (hip thrust, lat
    # pulldown, DB row are sagittal-plane/controlled patterns with no
    # matching contraindication), not an authoring gap.
    for name in ("Hip Thrust (Loaded)", "Lat Pulldown", "Single-Arm DB Row"):
        result = rules.check_movement(name, current_stage=2)
        assert result["severity"] == "unknown"


def test_face_pull_cable_is_cleared():
    face_pull = rules.check_movement("Face Pull (Cable)", current_stage=1)
    assert face_pull["severity"] == "cleared"


def test_no_streamlit_import():
    tree = ast.parse(open(rules.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"
