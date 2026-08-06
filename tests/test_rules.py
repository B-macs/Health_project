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


def test_side_bend_rule_matches_named_variants():
    # Added 2026-08-05. "right lateral"/"left lateral" only fire on names that
    # literally spell out "lateral" — the yoga catalogue's opening pose is a
    # seated cross-legged side bend and matched NOTHING, so it sat at `cleared`
    # despite being the same lateral-flexion mechanism as the two Seated Side
    # Stretches. Same generalisation "forward fold" makes over "seated forward
    # fold" above.
    for name in (
        "Seated Cross-Legged Side Bend (Shoulder Drop)",
        "Standing Side Bend",
        "side bend",
    ):
        result = rules.check_movement(name, current_stage=2)
        assert result["severity"] == "caution", name
        assert result["stage_ok"] is True, name

    # stage_cap=1, so it is a caution from Stage 1 onward rather than a hard
    # stop that later clears — mirrors the two lateral rules it generalises.
    assert rules.check_movement("Standing Side Bend", current_stage=1)["severity"] == "caution"


def test_side_bend_rule_does_not_swallow_unrelated_movements():
    # check_movement matches BOTH directions (`rule.movement in name` OR
    # `name in rule.movement`), so a short unrelated name could be captured by
    # the new keyword. Nothing in the exercise catalogue may start matching it.
    for name in ("Side Plank", "Side-Lying Hip Abduction", "Lateral Raise", "Bent-Over Row"):
        matched = [r for r in rules.MOVEMENT_RULES
                   if r.movement == "side bend"
                   and (r.movement in name.lower() or name.lower() in r.movement)]
        assert matched == [], name


def test_every_movement_rule_keyword_is_reachable():
    # A keyword that no name can match is dead weight pretending to be a
    # guardrail. Each rule must at least match its own movement string.
    for rule in rules.MOVEMENT_RULES:
        result = rules.check_movement(rule.movement, current_stage=5)
        assert result["severity"] != "unknown", rule.movement


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


# ── the matcher itself ───────────────────────────────────────────────────────
#
# Added 2026-08-06 after auditing the Cluster A flexibility documents against
# this rule set. 78 movement names were run through check_movement at the live
# stage: 8 matched anything at all, 70 returned `unknown`, and `unknown` is not
# a block — services/yoga.py:107 discards it. Zero of the 14 movements that are
# contraindicated on mechanism were caught by the rule written for them.
#
# Three defects, one test each. All three were live in shipped code.

def test_punctuation_cannot_defeat_a_contraindication():
    """A single hyphen was the difference between a hard block and silence.

    "Seated straddle good-mornings holding a plate" loads the lumbar spine in
    flexion over two covered annulus tears. `"good morning" in "good-mornings"`
    is False, so it returned `unknown` while the spaced spelling returned
    contraindicated. Names are normalised on both sides now.
    """
    hyphen = rules.check_movement("Seated straddle good-mornings holding a plate", 2)
    spaced = rules.check_movement("Seated straddle good mornings holding a plate", 2)
    assert hyphen["severity"] == spaced["severity"] == "contraindicated"
    assert hyphen["stage_available"] == 3          # caution rule, gated by stage

    # Possessives too, so a rule can be authored either way round.
    assert rules.normalise_movement("Tailor's pose") == "tailors pose"
    assert rules.normalise_movement("good-mornings") == "good mornings"


def test_a_cleared_rule_cannot_fire_on_a_fragment_of_a_description():
    """The dangerous failure is not silence, it is a wrong green light.

    The assessment battery's most flexion-loaded instruction reads "hands
    walking forward on the floor". That contains "walking", which matched the
    `walking` CLEARED rule and returned an affirmative "Low-impact movement —
    maintains tissue health without axial impact" on a movement that loads two
    covered annulus tears.
    """
    assert rules.check_movement("hands walking forward on the floor", 2)["severity"] != "cleared"
    assert rules.check_movement("pulling on a strap, hands walking forward", 2)["severity"] != "cleared"

    # The whole class, not just the one instance that was found.
    for fragment_carrier in ("arms swimming through the water overhead",
                             "hips cycling through the position",
                             "face pulled toward the floor"):
        assert rules.check_movement(fragment_carrier, 2)["severity"] != "cleared", fragment_carrier


def test_the_fragment_fix_did_not_cost_legitimate_clearances():
    """A cleared rule must still HEAD a longer name, plurals included —
    otherwise the fix trades a false positive for a pile of false negatives."""
    for name in ("Walking", "Cat-Cow", "Dead Bug", "Bird-Dog Hold",
                 "Glute Bridge (Single Leg)", "Pallof Press Hold (Doorframe)",
                 "Adductor squeezes at width", "Terminal knee extension with a band"):
        assert rules.check_movement(name, 2)["severity"] == "cleared", name


def test_a_skill_name_resolves_to_the_mechanism_it_actually_is():
    """The rules spoke movement descriptions; the flexibility material speaks
    skill names, and nothing bridged them. `Straddle Forward Fold` was
    contraindicated while `Pancake` — the same movement — was unknown."""
    for skill in ("Pancake", "Straddle", "Pike", "Side split", "Horse stance",
                  "Cossack squat", "Tailor's pose", "Butterfly", "Copenhagen plank",
                  "Seated pelvic rock", "Anterior tilt drill", "Nerve glide"):
        assert rules.check_movement(skill, 2)["severity"] != "unknown", skill


def test_an_axial_load_behind_the_neck_is_contraindicated_however_it_is_spelled():
    """The load, not the athlete's own tilt, produces the depth — and the
    placement sits on a post-Latarjet right shoulder."""
    for name in ("Elevated-hip pancake, weight behind the neck",
                 "Elevated-hip pancake, weight behind neck",
                 "Seated fold with weight behind the head"):
        assert rules.check_movement(name, 2)["severity"] == "contraindicated", name


def test_adding_vocabulary_never_loosened_an_existing_verdict():
    """Every rule added on 2026-08-06 is a bridge to a mechanism already ruled
    on. None of them may make anything MORE permissive than it was."""
    for name, expected in (("seated forward fold", "contraindicated"),
                           ("Straddle Forward Fold", "contraindicated"),
                           ("Butterfly Forward Fold", "contraindicated"),
                           ("toe touch", "contraindicated"),
                           ("hyperextension", "contraindicated"),
                           ("barbell deadlift", "contraindicated"),
                           ("box jump", "contraindicated")):
        assert rules.check_movement(name, 3)["severity"] == expected, name
