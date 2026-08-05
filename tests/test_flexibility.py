"""
Tests for services/flexibility.py — the v2 ladder model.

v1's tests pinned semantics the athlete refuted (a two-sided band that scored
high range DOWN). They are deleted, not weakened: a test pinning wrong
behaviour is a defect, and the replacement guard below fails loudly if any of
it returns. Same pattern as tests/test_bioage.py's guard over the retired
Stage-Adjusted Recovery Score.
"""

import ast
from datetime import date

import pytest

import flexibility_baselines as fb
from services import flexibility as fx

TODAY = date(2026, 8, 5)


# ── the guard ────────────────────────────────────────────────────────────────

def test_the_refuted_two_sided_band_is_gone_and_stays_gone():
    """v1 scored a self-rated depth on a band with full marks in 50-70 and a
    penalty ABOVE it, so a rating of 88 scored 46. The athlete refuted it: his
    rating measured how far he got, and penalising high values treated it as if
    it measured absence of muscular control. Achievement is monotonic now, and
    the hypermobility concern lives in the passive-active gap where it can be
    measured rather than assumed."""
    for name in ("band_score", "control_score", "CONTROL_BAND", "OVERSHOOT_SLOPE",
                 "UNDERSHOOT_EXPONENT", "RANGE_OVERSHOOT_SLOPE_PER_DEG",
                 "DIRECTION_UNSTABLE", "MIN_CONTROL_EVIDENCE"):
        assert not hasattr(fx, name), (
            f"{name} is back — read services/flexibility.py's docstring on why the "
            "two-sided band was removed before wiring it up again"
        )


def test_rung_scoring_is_monotonic_in_both_scale_directions():
    """The property the guard above exists to protect. More achievement can
    never score less, whichever way the test's own scale runs."""
    for key in ("calves_ankle", "shoulders_overhead"):
        test = fb.RUNGS[key]
        lo, hi = sorted((test.value_at_0, test.value_at_100))
        samples = [lo + (hi - lo) * i / 20 for i in range(21)]
        scores = [fx.rung_score(v, test) for v in samples]
        ordered = scores if test.value_at_100 > test.value_at_0 else scores[::-1]
        assert ordered == sorted(ordered), f"{key} is not monotonic"


def test_rung_score_anchors_and_clamps():
    ankle = fb.RUNGS["calves_ankle"]            # 12 cm = 100, 0 cm = 0
    assert fx.rung_score(12.0, ankle) == pytest.approx(100.0)
    assert fx.rung_score(0.0, ankle) == pytest.approx(0.0)
    assert fx.rung_score(6.0, ankle) == pytest.approx(50.0)
    assert fx.rung_score(30.0, ankle) == 100.0     # clamped, never >100
    assert fx.rung_score(-5.0, ankle) == 0.0

    quads = fb.RUNGS["quads"]                  # 0 cm = 100, 25 cm = 0 (inverted)
    assert quads.inverted is True
    assert fx.rung_score(0.0, quads) == pytest.approx(100.0)
    assert fx.rung_score(25.0, quads) == pytest.approx(0.0)
    assert fx.rung_score(12.5, quads) == pytest.approx(50.0)

    hips = fb.RUNGS["hip_flexors"]             # +15 deg = 100, -20 deg = 0
    assert hips.inverted is False
    assert fx.rung_score(15.0, hips) == pytest.approx(100.0)
    assert fx.rung_score(-20.0, hips) == pytest.approx(0.0)
    assert fx.rung_score(-2.5, hips) == pytest.approx(50.0)


def test_a_degenerate_scale_raises_rather_than_dividing_by_zero():
    bad = fb.RungTest(key="x", label="x", test_name="x", unit="cm",
                      value_at_100=5.0, value_at_0=5.0, setup="", lock="",
                      measurement="", bilateral=False, safety="")
    with pytest.raises(ValueError):
        fx.rung_score(5.0, bad)


# ── minimum, not mean ────────────────────────────────────────────────────────

def _reading(rung, active, passive=None):
    return fb.RungReading(rung=rung, active=active, passive=passive)


def _assessment(pairs, taken_on=TODAY):
    """pairs: {rung_key: active_raw}."""
    return fb.Assessment(taken_on=taken_on,
                         readings=tuple(_reading(k, v) for k, v in pairs.items()))


def test_a_skill_scores_its_lowest_rung_and_names_it():
    """The whole model. One broken rung must not be carried by healthy ones —
    that is exactly how v1 hid hip extension behind a hip score of 79."""
    a = _assessment({
        "calves_ankle": 4.56,    # -> 38
        "adductors":    9.5,     # -> 62
        "hip_rotation": 35.1,    # -> 88
        "lumbar":       1.45,    # -> 71
        "quads":        4.0,     # -> 84
    })
    squat = next(s for s in fx.report(a, TODAY).skills if s.key == "deep_squat")

    assert squat.score == pytest.approx(38.0, abs=0.5)
    assert squat.limiting_rung == "calves_ankle"
    assert squat.limiting_label == "Calves / ankle"
    # The mean would have been ~66.6 and would have said nothing actionable.
    assert squat.score < 66.6


def test_clearing_the_limiter_re_points_it_to_the_next_rung():
    """The re-pointing IS the training programme, so it has to be pinned."""
    base = {"calves_ankle": 4.56, "adductors": 9.5, "hip_rotation": 35.1,
            "lumbar": 1.45, "quads": 4.0}
    before = next(s for s in fx.report(_assessment(base), TODAY).skills
                  if s.key == "deep_squat")
    assert before.limiting_rung == "calves_ankle"

    fixed = dict(base, calves_ankle=8.4)          # ankle up to ~70
    after = next(s for s in fx.report(_assessment(fixed), TODAY).skills
                 if s.key == "deep_squat")
    assert after.limiting_rung == "adductors"
    assert after.score > before.score


def test_the_worse_side_limits_and_sides_are_never_averaged():
    a = fb.Assessment(taken_on=TODAY, readings=(
        fb.RungReading("hamstrings", active=72.0, side="left"),    # -> 80
        fb.RungReading("hamstrings", active=36.0, side="right"),   # -> 40
        fb.RungReading("lumbar", active=0.5),
    ))
    pike = next(s for s in fx.report(a, TODAY).skills if s.key == "active_pike")
    assert pike.limiting_rung == "hamstrings"
    assert pike.score == pytest.approx(40.0, abs=0.5)   # not the 60 an average gives


def test_a_partial_ladder_is_reported_as_incomplete():
    """A skill scored on some of its rungs is only an UPPER BOUND — an
    unmeasured rung might be lower than anything seen."""
    a = _assessment({"calves_ankle": 12.0})
    squat = next(s for s in fx.report(a, TODAY).skills if s.key == "deep_squat")
    assert squat.score is not None
    assert squat.complete is False
    assert set(squat.unmeasured_rungs) == {"adductors", "hip_rotation", "lumbar", "quads"}


# ── the gap ──────────────────────────────────────────────────────────────────

def test_the_gap_is_passive_minus_active_and_drives_the_prescription():
    wide = fb.RungReading("hamstrings", passive=85.5, active=36.0)    # 95 vs 40
    narrow = fb.RungReading("hamstrings", passive=49.5, active=40.5)  # 55 vs 45

    w, n = fx.score_reading(wide), fx.score_reading(narrow)
    assert w.gap == pytest.approx(55.0, abs=0.5)
    assert n.gap == pytest.approx(10.0, abs=0.5)
    assert w.prescription == fx.PRESCRIPTION_STRENGTH
    assert n.prescription == fx.PRESCRIPTION_RANGE


def test_the_gap_is_unknown_rather_than_zero_when_a_measure_is_missing():
    r = fx.score_reading(fb.RungReading("hamstrings", passive=72.0))
    assert r.gap is None
    assert r.prescription == fx.PRESCRIPTION_UNKNOWN


def test_a_rung_scores_from_usable_range_not_from_its_passive_ceiling():
    """A passive ceiling nobody can enter under their own power does not limit
    a skill any less for being high."""
    r = fx.score_reading(fb.RungReading("hamstrings", passive=85.5, active=36.0))
    assert r.score == pytest.approx(40.0, abs=0.5)      # active, not the 95 passive
    assert r.passive.score == pytest.approx(95.0, abs=0.5)


def test_isometric_is_used_when_active_is_absent():
    r = fx.score_reading(fb.RungReading("hamstrings", passive=85.5, isometric=54.0))
    assert r.score == pytest.approx(60.0, abs=0.5)


# ── the empty state ──────────────────────────────────────────────────────────

def test_no_assessment_yields_none_everywhere_and_never_a_zero():
    """0 is a measurement meaning 'could not begin the movement'. Absent data
    must not be indistinguishable from it."""
    rep = fx.report(None, TODAY)
    assert rep.assessed_on is None
    assert rep.measured_rung_count == 0
    assert rep.gap_count == 0
    for s in rep.skills:
        assert s.score is None
        assert s.limiting_rung is None
        assert s.complete is False


def test_the_shipped_state_really_is_empty():
    assert fb.ASSESSMENTS == ()
    rep = fx.report(today=TODAY)
    assert all(s.score is None for s in rep.skills)


# ── structure ────────────────────────────────────────────────────────────────

def test_every_skill_ladder_references_real_rungs():
    for skill in fb.SKILLS.values():
        assert skill.ladder, skill.key
        for rung in skill.ladder:
            assert rung in fb.RUNGS, f"{skill.key} -> unknown rung {rung}"


def test_squat_depth_is_never_a_rung_on_the_squat_ladder():
    """It is the OUTCOME of that ladder. Including it would let the symptom vote
    on its own diagnosis."""
    assert "squat_depth" not in fb.SKILLS["deep_squat"].ladder


def test_excluded_skills_are_tracked_but_flagged_with_a_reason():
    for key in ("bridge", "shoulder_extension"):
        s = fb.SKILLS[key]
        assert s.excluded is True
        assert len(s.excluded_reason) > 40, key
    assert set(fb.ACTIVE_SKILLS) == {
        "deep_squat", "hip_extension", "shoulder_flexion", "active_pike"}


def test_every_rung_names_a_lock():
    """An unlocked joint lets a neighbour substitute and the test measures
    nothing — the failure that broke this model twice."""
    for key, t in fb.RUNGS.items():
        assert len(t.lock) > 30, f"{key} has no meaningful lock"
        assert len(t.measurement) > 30, f"{key} has no measurement protocol"
        assert t.value_at_100 != t.value_at_0, key


def test_the_fourteen_rungs_are_all_present():
    assert len(fb.RUNGS) == 14
    assert set(fb.RUNGS) == {
        "neck", "shoulders_overhead", "lats", "chest_horizontal", "thoracic_rotation",
        "lumbar", "lateral_trunk", "hip_flexors", "quads", "hip_rotation",
        "adductors", "hamstrings", "calves_ankle", "squat_depth"}


def test_the_lat_rung_closes_the_overhead_ladder():
    """The hole this used to declare is filled. All three tissues that limit an
    overhead reach now have a rung, and the lat one isolates by taking the
    lumbar spine into full flexion — the lats are the only one of the three
    crossing the lower back."""
    ladder = fb.SKILLS["shoulder_flexion"].ladder
    for rung in ("shoulders_overhead", "lats", "chest_horizontal"):
        assert rung in ladder, rung
    assert "INCOMPLETE" not in fb.SKILLS["shoulder_flexion"].note.upper()

    lats = fb.RUNGS["lats"]
    assert "lower back" in lats.lock          # the isolation mechanism, stated
    assert "PROVISIONAL" in lats.safety.upper()  # the anchor is not a published norm


def test_the_contraindicated_replacements_are_recorded():
    """Four tests replace a standard that is contraindicated here. The
    replacement must say what it replaced, or the reasoning is lost."""
    replacing = {k: t for k, t in fb.RUNGS.items() if t.replaces}
    assert set(replacing) == {"hamstrings", "quads", "chest_horizontal",
                              "thoracic_rotation", "hip_flexors", "neck"}
    assert "forward fold" in fb.RUNGS["hamstrings"].replaces.lower()


# ── refusals ─────────────────────────────────────────────────────────────────

def test_none_of_the_legacy_pose_ratings_feed_a_score():
    """They answer neither question — 'how far did I get AND how much did I
    feel' is not passive range and not active range. Reinterpreting them would
    be inventing data."""
    assert len(fb.LEGACY_POSE_DEPTH_RATINGS_2026_08_05) == 22
    source = open(fx.__file__, encoding="utf-8").read()
    body = source.split('"""', 2)[-1]
    assert "LEGACY_POSE_DEPTH_RATINGS" not in body
    assert "LEGACY_GYM_READINGS" not in body


def test_no_flexibility_age_in_years_is_produced():
    source = open(fx.__file__, encoding="utf-8").read()
    names = {n.name for n in ast.walk(ast.parse(source))
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    for banned in ("flexibility_age", "bio_age", "bioage", "age_years"):
        assert not any(banned in n.lower() for n in names), banned
    assert fb.AGE_AT_SCAN_YEARS == 30
    assert fb.VENDOR_BIOAGE_COMPARED_AGAINST_AGE == 31


def test_the_legacy_gym_readings_are_provenance_and_name_their_successor():
    assert len(fb.LEGACY_GYM_READINGS) == 5
    for r in fb.LEGACY_GYM_READINGS:
        assert r.superseded_by in fb.RUNGS, r.label


# ── serialisation and the resumable draft ────────────────────────────────────

def test_an_assessment_round_trips_through_the_store_format():
    a = fb.Assessment(taken_on=TODAY, cold=True, note="n", readings=(
        fb.RungReading("hamstrings", passive=85.5, active=36.0, side="left"),
        fb.RungReading("lumbar", active=0.5),
    ))
    assert fx.assessment_from_dict(fx.assessment_to_dict(a)) == a


def test_an_unreadable_assessment_degrades_to_none_rather_than_half_parsing():
    """"No assessment" is a state the screen renders honestly. A half-parsed one
    would silently score a ladder against rungs it does not have."""
    assert fx.assessment_from_dict({}) is None
    assert fx.assessment_from_dict({"schema": 99, "taken_on": "2026-08-05"}) is None
    assert fx.assessment_from_dict({"schema": 1, "taken_on": "not-a-date"}) is None
    assert fx.assessment_from_dict({"schema": 1}) is None


def test_a_reading_for_a_retired_rung_is_dropped_not_kept():
    a = fx.assessment_from_dict({
        "schema": 1, "taken_on": "2026-08-05",
        "readings": [{"rung": "some_removed_rung", "active": 10},
                     {"rung": "hamstrings", "active": 45}],
    })
    assert [r.rung for r in a.readings] == ["hamstrings"]


def test_re_entering_a_test_overwrites_rather_than_accumulating():
    """A corrected trial must not leave the bad one in the record, where the
    worse-side rule would pick it up."""
    a = fb.Assessment(taken_on=TODAY, readings=(
        fb.RungReading("hamstrings", active=36.0, side="left"),
    ))
    b = fx.merge_reading(a, fb.RungReading("hamstrings", active=72.0, side="left"))
    assert len(b.readings) == 1
    assert b.readings[0].active == 72.0

    # ...but the other side is a different reading and must survive.
    c = fx.merge_reading(b, fb.RungReading("hamstrings", active=50.0, side="right"))
    assert len(c.readings) == 2


def test_the_report_counts_distinct_rungs_not_readings():
    """A bilateral test produces two readings for one rung. Counting readings
    displayed "19 of 14 rungs" on the first real end-to-end run."""
    a = fb.Assessment(taken_on=TODAY, readings=(
        fb.RungReading("hamstrings", passive=85.5, active=36.0, side="left"),
        fb.RungReading("hamstrings", passive=84.0, active=35.0, side="right"),
        fb.RungReading("lumbar", active=0.5),
    ))
    rep = fx.report(a, TODAY)
    assert len(rep.rungs) == 3            # three readings...
    assert rep.measured_rung_count == 2   # ...but two rungs
    assert rep.gap_count == 1             # only hamstrings has passive AND active
    assert rep.measured_rung_count <= len(fb.RUNGS)


def test_progress_counts_rungs_with_any_measure_not_readings():
    a = fb.Assessment(taken_on=TODAY, readings=(
        fb.RungReading("hamstrings", active=45.0, side="left"),
        fb.RungReading("hamstrings", active=44.0, side="right"),
        fb.RungReading("lumbar"),                       # empty — not progress
    ))
    assert fx.assessment_progress(a) == (1, len(fb.RUNGS))
    assert fx.assessment_progress(None) == (0, len(fb.RUNGS))


# ── the scheduling window ────────────────────────────────────────────────────

def test_the_window_reads_the_training_log():
    hard = {date(2026, 8, 3)}
    assert fx.flexibility_window(date(2026, 8, 4), hard)[0] == fb.WINDOW_POOR
    assert fx.flexibility_window(date(2026, 8, 5), hard)[0] == fb.WINDOW_GOOD
    assert fx.flexibility_window(date(2026, 8, 3), hard)[0] == fb.WINDOW_OK
    assert fx.flexibility_window(date(2026, 8, 3), hard, same_day_pm=True)[0] == fb.WINDOW_GOOD


def test_a_rest_day_alone_does_not_downgrade_the_window():
    """A restorative flow on a rest day is fine; only an adaptation-seeking
    session is the thing the rule calls worst, and nothing yet distinguishes
    them. Downgrading here would penalise the harmless case."""
    assert fb.REST_DAY_CONFLICT_UNRESOLVED is True
    window, _ = fx.flexibility_window(date(2026, 8, 9), {date(2026, 8, 5)}, is_rest_day=True)
    assert window == fb.WINDOW_GOOD


def test_staleness_halves_and_cannot_exceed_one():
    assert fx.staleness_confidence(TODAY, TODAY) == 1.0
    year_ago = date.fromordinal(TODAY.toordinal() - 365)
    assert fx.staleness_confidence(year_ago, TODAY) == pytest.approx(0.5, abs=0.01)
    future = date.fromordinal(TODAY.toordinal() + 400)
    assert fx.staleness_confidence(future, TODAY) == 1.0


def test_no_streamlit_import():
    tree = ast.parse(open(fx.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"
