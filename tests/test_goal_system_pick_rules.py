"""Every exercise picked by the goal system's step 5 lands on a known rule.

Step 5's first filter (docs/training/goal_system.md): the safety rules know the
exercise and do not block it — "unknown" is not a clearance, and "caution" means
allowed (athlete, 2026-10-15). On 2026-10-16 the athlete approved a list of rules
for the picks that read "unknown", after asking to see it first. These tests pin
each verdict, and the three ways the new keywords could have gone wrong.
"""
import pytest

from services import rules, yoga

#: name -> (severity, laterality), exactly as approved on 2026-10-16.
_APPROVED = {
    "Walking Lunge (DB)": ("caution", "right"),
    "High-to-Low Cable Woodchop": ("caution", "bilateral"),
    "Side Plank with Hip Raises": ("caution", "bilateral"),
    "Machine Hip Thrust": ("caution", "bilateral"),
    "Seated Leg Curl": ("cleared", "bilateral"),
    "Machine Shoulder Press": ("cleared", "bilateral"),
    "Seated Dumbbell Shoulder Press": ("cleared", "bilateral"),
    "Cable Lateral Raise": ("caution", "right"),
    "Reverse Cable Crossover": ("caution", "right"),
    "Neck Working Stretch (Right)": ("caution", "right"),
}


@pytest.mark.parametrize("name", sorted(_APPROVED))
def test_each_pick_lands_on_its_approved_rule(name):
    got = rules.check_movement(name, 2)
    assert (got["severity"], got["laterality"]) == _APPROVED[name], (name, got)


def test_plain_walking_is_still_cleared():
    """The lunge rule is keyed "lunge (db)", not "walking lunge": a caution
    keyword matches any name it contains, so "walking lunge" would have turned
    plain walking into a caution with a lunge's reason."""
    assert rules.check_movement("walking", 1)["severity"] == "cleared"
    assert rules.check_movement("Walking", 2)["severity"] == "cleared"


def test_the_yoga_lunges_keep_their_own_tags():
    """A bare "lunge" keyword would have caught the yoga lunges, whose tags
    were authored on the pose."""
    hip = yoga.get("hip_spine_flow_15min")
    for pose in hip.poses:
        if "Lunge" in pose.name:
            assert rules.check_movement(pose.name, 2)["severity"] == "unknown", pose.name


def test_the_plain_side_bridge_stays_cleared():
    """Only the hip-raise version is a side bend; the held side bridge keeps
    its clearance."""
    assert rules.check_movement("Full Side Bridge", 2)["severity"] == "cleared"


def test_no_pick_reads_unknown_at_the_current_stage():
    for name in _APPROVED:
        assert rules.check_movement(name, 2)["severity"] != "unknown", name
