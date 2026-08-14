"""training_constants.EXERCISE_REGION_SHARES — completeness and honesty.

Mirrors tests/test_movement_weight_coverage.py, which does the same job for the
sibling map. The point of both is that a gap in an exercise-name table is
invisible at runtime: a missing name does not raise, it silently changes what a
number means.

The load-bearing test here is test_argmax_agrees_with_the_one_primary_region_map.
Two region maps now exist and they answer different questions —
EXERCISE_BODY_REGION says which ONE sector owns a movement (tonnage's
kilograms, strength's 1RM, flexibility's leg-day boolean), while
EXERCISE_REGION_SHARES says how its STRAIN distributes. They are allowed to
differ in detail and are not allowed to tell different stories.
"""

import pytest

import training_constants as tc
import training_plan as tp
from services import sessions as sess

SHARES = tc.EXERCISE_REGION_SHARES
REGIONS = {"upper_body", "core", "lower_body"}

_NAMES = sorted(SHARES)


@pytest.mark.parametrize("name", _NAMES)
def test_every_entry_sums_to_one(name):
    """The identity upper + core + lower == the movement's whole contribution.
    services/strain_regions.py renormalises a non-unit vector at read time so a
    typo cannot crash a health page — this is what stops it living there."""
    assert abs(sum(SHARES[name].values()) - 1.0) < 1e-9


@pytest.mark.parametrize("name", _NAMES)
def test_every_entry_has_all_three_keys(name):
    """Explicit zeros. A sparse dict makes 'genuinely does not load that
    region' indistinguishable from 'the author forgot a key'."""
    assert set(SHARES[name]) == REGIONS


@pytest.mark.parametrize("name", _NAMES)
def test_every_share_is_on_the_authoring_grid(name):
    """Multiples of 0.05. A 0.02 in an invented table is false precision — it
    claims a resolution nobody has."""
    for region, value in SHARES[name].items():
        assert 0.0 <= value <= 1.0, f"{name}/{region} out of range"
        assert abs(round(value * 20) - value * 20) < 1e-9, (
            f"{name}/{region} = {value} is not a multiple of 0.05"
        )


@pytest.mark.parametrize("name", _NAMES)
def test_no_share_sits_between_zero_and_the_floor(name):
    """0.00 is permitted and MEANS something. Anything non-zero is at least
    0.05, because a smaller claim is not one this table can support."""
    for region, value in SHARES[name].items():
        assert value == 0.0 or value >= 0.05, f"{name}/{region} = {value}"


@pytest.mark.parametrize("name", _NAMES)
def test_argmax_agrees_with_the_one_primary_region_map(name):
    """THE anti-drift test. The two maps must tell one story."""
    primary = max(SHARES[name], key=SHARES[name].get)
    assert primary == tc.EXERCISE_BODY_REGION[name], (
        f"{name!r}: shares say {primary!r}, EXERCISE_BODY_REGION says "
        f"{tc.EXERCISE_BODY_REGION[name]!r}"
    )


@pytest.mark.parametrize("name", _NAMES)
def test_the_primary_region_wins_strictly(name):
    """No tied argmax — a tie makes the test above depend on dict order."""
    ordered = sorted(SHARES[name].values(), reverse=True)
    assert ordered[0] > ordered[1], f"{name} has a tied dominant region"


def test_key_set_matches_the_body_region_map_exactly():
    assert set(SHARES) == set(tc.EXERCISE_BODY_REGION)


def test_only_the_self_assessment_is_weighted_but_unshared():
    """"Week 1 Self-Assessment" is a subjective checkpoint, not a movement. It
    is deliberately absent from BOTH region maps and falls to the unattributed
    bucket, where it is NAMED rather than silently zeroed."""
    assert set(tc.EXERCISE_MOVEMENT_WEIGHT) - set(SHARES) == {"Week 1 Self-Assessment"}


def test_every_planned_exercise_name_has_shares():
    missing = {
        ex["name"]
        # Every authored plan, not a list that has to be remembered — a block
        # missing from this tuple silently stops being covered, which reads
        # exactly like coverage that passed.
        for plan in (tp.PLAN, tp.PLAN_STAGE2, tp.PLAN_STAGE2B)
        for day in plan.values()
        for ex in day.get("exercises", [])
        if ex["name"] not in SHARES and ex["name"] != "Week 1 Self-Assessment"
    }
    assert not missing, f"plan names with no region shares: {sorted(missing)}"


def test_every_outdoor_importer_name_has_shares():
    """No PLAN iteration will ever ask for these — only the Garmin importer
    logs them, so nothing else would notice them going missing."""
    for name in list(sess.OUTDOOR_EXERCISE_BY_TYPE.values()) + [sess.OUTDOOR_FALLBACK_EXERCISE]:
        assert name in SHARES, name


def test_a_hike_is_predominantly_lower_body():
    """The athlete's own founding requirement: a hike adds proportionally more
    to lower body."""
    assert SHARES["Outdoor Hike"]["lower_body"] >= 0.75
    hike = SHARES["Outdoor Hike"]
    assert hike["lower_body"] > hike["core"] + hike["upper_body"]


def test_the_catch_all_outdoor_entry_is_the_least_committed():
    """"Outdoor Activity" fires when the athlete picked something outside the
    known family — its name means 'we do not know what this was', so it must
    lean less hard on lower body than any named activity does."""
    named = ["Outdoor Hike", "Outdoor Walk", "Outdoor Trail Run", "Outdoor Run"]
    catch_all = SHARES["Outdoor Activity"]["lower_body"]
    for name in named:
        assert catch_all < SHARES[name]["lower_body"], name


def test_the_release_protocol_is_lower_body_dominant():
    for name in sess.RELEASE_EXERCISE_NAMES:
        if name in SHARES:
            assert SHARES[name]["lower_body"] >= 0.85, name
            assert SHARES[name]["upper_body"] == 0.0, name


_FAMILIES = [
    ("wall sit", ("Wall Sit", "Wall Sit (Isometric Quad)", "Wall Sit (Extended Duration)")),
    ("cat-cow", ("Cat-Cow", "Cat-Cow (Slow Flow)")),
    ("bird-dog", ("Bird-Dog", "Bird-Dog (Extended Hold)", "Bird-Dog with Full Reach")),
    ("dead bug", ("Dead Bug", "Dead Bug (Progression — 3s Hold)")),
    ("hip capsule", ("Right Posterior Hip Capsule Stretch",
                     "Right Posterior Hip Capsule Stretch (Revised Cue)")),
    ("single-leg balance", ("Single-Leg Balance", "Single-Leg Balance (Eyes Closed)")),
    ("pallof", ("Pallof Press (Cable)", "Pallof Press Hold (Doorframe)")),
    ("walking", ("Controlled Walking", "Walking — Gait Focus",
                 "Assessment Walk + Stair Check", "5-Minute Walk + Stair Assessment",
                 "Outdoor Walk")),
]


@pytest.mark.parametrize("label,names", _FAMILIES, ids=[f[0] for f in _FAMILIES])
def test_movement_families_share_one_triple(label, names):
    """The same movement must not change its split because a training block
    renamed it — the rule EXERCISE_MOVEMENT_WEIGHT already applies to its own
    mobility variants."""
    first = SHARES[names[0]]
    for other in names[1:]:
        assert SHARES[other] == first, f"{label}: {other} differs from {names[0]}"


def test_the_map_is_flagged_as_invented():
    """Every number in this table was authored, not measured. The flag is what
    carries that onto the screen, in the services/battery.py BASIS_PROVISIONAL
    idiom."""
    assert tc.REGION_SHARES_BASIS == "provisional"
    assert isinstance(tc.REGION_SHARES_VERSION, int)
    assert tc.REGION_SHARES_VERSION >= 1


def test_region_display_covers_exactly_the_three_regions():
    assert set(tc.REGION_DISPLAY) == REGIONS
    for meta in tc.REGION_DISPLAY.values():
        assert set(meta) == {"name", "short", "colour", "ratio"}
        assert meta["colour"].startswith("#")
