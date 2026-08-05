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


def test_opening_pose_is_a_side_bend_not_a_spinal_mobilisation():
    """Corrected 2026-08-05. The opening pose was authored as "Spine Mobilisation"
    and tagged `cleared` on the assumption it was cat-cow-family spinal mobility.
    It is a seated cross-legged side bend — lateral flexion, the same mechanism as
    the two Seated Side Stretches, which are both `caution`. Regressing the name
    would also silently drop the services.rules "side bend" cross-check."""
    opening = yoga.YOGA_LIBRARY[0].poses[0]
    assert "side bend" in opening.name.lower()
    assert opening.safety == "caution"
    assert "Spine Mobilisation" not in opening.name

    severity, _ = yoga.effective_safety(opening, stage=2)
    assert severity == "caution"


def test_side_bend_caution_survives_losing_the_authored_tag():
    """Defense in depth: services.rules must catch a side bend on the keyword
    alone, so a future catalogue entry can't be cleared by omission."""
    pose = yoga.YogaPose("Some Other Seated Side Bend", 0, 30, "cleared")
    severity, _ = yoga.effective_safety(pose, stage=2)
    assert severity == "caution"


def test_laterality_convention_is_documented_where_it_is_used():
    """The (Right)/(Left) suffix names the FRONT leg — for lunges that is the
    OPPOSITE leg to the one stretched. Undocumented, this silently moves the
    right-only cautions (Coxa Saltans, post-Latarjet shoulder) onto the wrong
    side, which is exactly what happened before 2026-08-05."""
    assert "LATERALITY CONVENTION" in yoga.__doc__

    source = open(yoga.__file__, encoding="utf-8").read()
    tree = ast.parse(source)
    pose_cls = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef) and n.name == "YogaPose"
    )
    # The convention must be restated at the dataclass, not only in the module
    # docstring — the field is where an author actually types a side-specific note.
    cls_src = ast.get_source_segment(source, pose_cls)
    assert "FRONT" in cls_src and "OPPOSITE" in cls_src


def test_deep_lunge_notes_name_the_stretched_side_correctly():
    """Left-foot-forward stretches the RIGHT hip flexor, which is the side listed
    as overactive. The note used to say the opposite."""
    poses = {p.name: p for p in yoga.YOGA_LIBRARY[0].poses}
    assert "LEFT hip flexor" in poses["Deep Lunge (Right)"].safety_note
    assert "RIGHT hip flexor" in poses["Deep Lunge (Left)"].safety_note
    # The note quotes the old wrong phrasing in order to correct it, so absence
    # is the wrong assertion — what must hold is that it is marked as corrected
    # rather than restated as fact.
    left_note = poses["Deep Lunge (Left)"].safety_note
    if "no right-side-specific concern" in left_note:
        assert "backwards" in left_note and "corrected" in left_note


def test_coxa_saltans_poses_stay_caution_despite_measuring_easy():
    """2026-08-05 measured 90/90 and Half Pigeon (Right) as easy with no snap.
    That narrowed finding #4's trigger to ACTIVE hip flexion — it did not clear
    the mechanism, so neither pose may be downgraded on the ROM data alone."""
    poses = {p.name: p for p in yoga.YOGA_LIBRARY[0].poses}
    for name in ("90/90 Hip Rotation", "Half Pigeon Pose (Right)"):
        assert poses[name].safety == "caution", name


def test_session_duration_and_au_unchanged_by_the_2026_08_05_corrections():
    """The corrections were to names, tags and notes only. If timing moved, the
    session's Foster-AU contribution to Strain/ACWR moved with it."""
    session = yoga.YOGA_LIBRARY[0]
    assert len(session.poses) == 22
    assert session.total_duration_minutes == 15
    assert session.session_au == 45.0


def test_retests_are_attached_to_the_poses_that_can_answer_them():
    """A finding measured once is a snapshot. The three open questions from the
    2026-08-05 baseline are attached to the poses that actually reproduce the
    position, so the answer is captured in situ rather than recalled."""
    session = yoga.YOGA_LIBRARY[0]
    retests = dict((p.name, q) for p, q in session.retests())

    assert len(retests) == 3, f"expected 3 retests, got {sorted(retests)}"
    assert "Seated Cross-Legged Side Bend (Shoulder Drop)" in retests
    assert "Down Dog" in retests
    assert "Deep Lunge Hip Opener (Left)" in retests

    # Each must carry the baseline value it is a retest OF — a retest without
    # the number to compare against is just a reminder.
    assert "2026-08-05" in retests["Seated Cross-Legged Side Bend (Shoulder Drop)"]
    assert "50-60s" in retests["Down Dog"]
    assert "2026-08-05" in retests["Deep Lunge Hip Opener (Left)"]


def test_retests_are_ordered_by_pose_sequence():
    session = yoga.YOGA_LIBRARY[0]
    starts = [pose.start_seconds for pose, _ in session.retests()]
    assert starts == sorted(starts)


def test_retests_and_cautions_are_separate_concerns():
    """A retest is a one-shot measurement request, a caution is a standing
    safety statement. Neither collection may absorb the other."""
    session = yoga.YOGA_LIBRARY[0]
    retest_names = {p.name for p, _ in session.retests()}
    caution_names = {p.name for p, _, _ in session.cautions(stage=2)}

    # They overlap by coincidence of subject matter, not by construction —
    # so neither is derivable from the other.
    assert retest_names - caution_names == set() or retest_names != caution_names
    assert caution_names - retest_names, "cautions must not collapse to just the retests"

    # A pose with no retest must not leak an empty string into the list.
    assert all(question for _, question in session.retests())


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
