"""
Tests for services/yoga.py — pose timing math, safety cross-checking, and the
deterministic rest-day suggestion rule.
"""

import ast

from services import yoga


def test_total_duration_rounds_up_to_the_minute():
    session = yoga.YOGA_LIBRARY[0]
    last = session.poses[-1]
    assert last.start_seconds + last.hold_seconds == 890  # 14:20 + 30s
    assert session.total_duration_minutes == 15  # ceil(890 / 60)


def test_session_au_is_rpe_times_duration():
    session = yoga.YOGA_LIBRARY[0]
    assert session.session_au == session.estimated_rpe * session.total_duration_minutes


def test_effective_safety_keeps_authored_tag_when_no_rule_matches():
    pose = yoga.YogaPose("Happy Baby", 0, 30, "cleared")
    severity, note = yoga.effective_safety(pose, stage=1)
    assert severity == "cleared"


def test_effective_safety_escalates_via_shared_rules_engine():
    # Not authored as contraindicated here, but "forward fold" is a
    # contraindicated keyword in services.rules — the cross-check must catch it
    # even if this catalogue entry were ever mis-tagged.
    pose = yoga.YogaPose("Some New Forward Fold Variant", 0, 30, "cleared")
    severity, note = yoga.effective_safety(pose, stage=1)
    assert severity == "contraindicated"


def test_cautions_returns_only_non_cleared_poses():
    session = yoga.YOGA_LIBRARY[0]
    cautions = session.cautions(stage=1)
    assert all(severity != "cleared" for _, severity, _ in cautions)
    names = {pose.name for pose, _, _ in cautions}
    assert "Butterfly Forward Fold" in names
    assert "Straddle Forward Fold" in names
    assert "Half Pigeon Pose (Right)" in names
    assert "Half Pigeon Pose (Left)" not in names  # not right-side, no Coxa Saltans mechanism


def test_suggest_for_day_returns_a_rest_day_match():
    suggestion = yoga.suggest_for_day("rest_day")
    assert suggestion is not None
    assert "rest_day" in suggestion.suitable_for


def test_suggest_for_day_returns_none_for_unmatched_kind():
    assert yoga.suggest_for_day("some_unrecognised_day_kind") is None


def test_get_returns_session_by_slug_or_none():
    session = yoga.YOGA_LIBRARY[0]
    assert yoga.get(session.slug) is session
    assert yoga.get("does-not-exist") is None


def test_no_streamlit_import():
    tree = ast.parse(open(yoga.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"
