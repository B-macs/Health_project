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


def test_no_streamlit_import():
    tree = ast.parse(open(rules.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"
