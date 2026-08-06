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
    squat = next(s for s in fx.report(a, TODAY).skills if s.key == "squat")

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
                  if s.key == "squat")
    assert before.limiting_rung == "calves_ankle"

    fixed = dict(base, calves_ankle=8.4)          # ankle up to ~70
    after = next(s for s in fx.report(_assessment(fixed), TODAY).skills
                 if s.key == "squat")
    assert after.limiting_rung == "adductors"
    assert after.score > before.score


def test_the_worse_side_limits_and_sides_are_never_averaged():
    a = fb.Assessment(taken_on=TODAY, readings=(
        fb.RungReading("hamstrings", active=72.0, side="left"),    # -> 80
        fb.RungReading("hamstrings", active=36.0, side="right"),   # -> 40
        fb.RungReading("lumbar", active=0.5),
    ))
    pike = next(s for s in fx.report(a, TODAY).skills if s.key == "pike")
    assert pike.limiting_rung == "hamstrings"
    assert pike.score == pytest.approx(40.0, abs=0.5)   # not the 60 an average gives


def test_a_partial_ladder_is_reported_as_incomplete():
    """A skill scored on some of its rungs is only an UPPER BOUND — an
    unmeasured rung might be lower than anything seen."""
    a = _assessment({"calves_ankle": 12.0})
    squat = next(s for s in fx.report(a, TODAY).skills if s.key == "squat")
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
    assert "squat_depth" not in fb.SKILLS["squat"].ladder


def test_the_eight_skills_are_the_athletes_own_list():
    """Goals, not lift-transfer capacities. The previous four were correct as
    ladders and wrong as goals — "deep squat" is something he can already hold
    and "hip extension" is not a position anybody aims at. NO NEW RUNGS were
    needed to fix it, which is the evidence the failure was in the naming."""
    assert set(fb.SKILLS) == {
        "pancake", "pike", "front_split", "side_split", "squat",
        "shoulder_flexion", "shoulder_extension", "bridge"}


def test_a_blocked_skill_is_still_tracked_and_still_scores():
    """Bridge and shoulder extension are the athlete's own stated goals and are
    NOT deleted. What they cannot do is be chosen as the thing being trained
    toward, because the route to each runs through a direction his imaging rules
    out. Hiding them would lose the regression signal, which is the only reason
    to track a skill nobody is training toward."""
    for key in ("bridge", "shoulder_extension"):
        s = fb.SKILLS[key]
        assert s.needs_signoff is True
        assert s.selectable is False
        assert len(s.blocked_reason) > 40, key
        assert "2026-08-16" in s.blocked_reason, key   # names what unblocks it
    assert set(fb.BLOCKED_SKILLS) == {"bridge", "shoulder_extension"}

    # It still appears in the report, with a score, like any other skill.
    a = _assessment({"hip_flexors": -6.0, "shoulders_overhead": 120.0,
                     "thoracic_rotation": 30.0})
    bridge = next(s for s in fx.report(a, TODAY).skills if s.key == "bridge")
    assert bridge.score is not None
    assert bridge.needs_signoff is True


def test_only_a_cleared_skill_with_a_built_stack_can_be_a_target():
    """An unbuilt skill is not selectable either — there is no point aiming at
    a goal with no route to it, and offering one would produce a limiting rung
    with nothing to do about it."""
    assert fb.SELECTABLE_SKILLS == ("pancake",)
    assert fb.DEFAULT_TARGET_SKILL == "pancake"
    for key in fb.UNBUILT_SKILLS:
        s = fb.SKILLS[key]
        assert s.status == fb.SKILL_AVAILABLE and not s.built
        assert s.selectable is False


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
    # The anchor is our own estimate, not a published norm. Pinned as a FIELD:
    # asserting a word appeared in the prose made rewriting that prose into
    # plain English look like a regression, when the fact had not changed.
    assert lats.anchor_provisional is True
    assert lats.anchor_provisional is not fb.RUNGS["hamstrings"].anchor_provisional


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


# ── the protocol text is read by a person, on the floor, holding a tape ──────
#
# These four tests exist because the first draft of the protocols failed
# review by the only person who will ever run them. Verbatim: "the Lock and
# explanation is too scientific", "the english is very convoluted and difficult
# to understand", "'at which the knee still touches' — the knee still touches
# WHAT?", "'binary and externally detectable' — what does that even mean?", and
# "remove any mention of python scripts and what it's replacing, this is for a
# patient". A test he cannot follow does not produce a wrong number — it
# produces a plausible one, which is worse, because nothing downstream can tell.

#: Anatomical names and codebase internals that must never appear in the four
#: fields the athlete reads while performing the test. Every one of these was
#: present in the first draft. They are not banned from the file — they belong
#: in `what_youre_testing`, which is where someone who wants the anatomy looks.
_JARGON = (
    "supine", "prone", "gluteal fold", "lateral aspect", "ulnar", "acromion",
    "styloid", "inclinometer", "pes planus", "contracture", "shank",
    "subtalar", "dorsiflexion", "abduction", "adduction", "rectus femoris",
    "posterior tilt", "anterior tilt", "lumbar", "cervical", "thoracic",
    "coxa saltans", "contraindicat", "end range", "midfoot",
)
_REPO_INTERNALS = (
    ".py", "rules.py", "symptom_log", "patient_profile", "finding #",
    "_score", "RUNGS", "SKILLS", "shoulders_overhead", "calves_ankle",
)
_PATIENT_FACING = ("setup", "lock", "measurement", "safety")


def test_the_patient_facing_fields_stay_in_plain_english():
    """setup / lock / measurement / safety are read mid-assessment. Anatomy
    goes in what_youre_testing; nothing about this codebase goes anywhere."""
    offences = []
    for key, test in fb.RUNGS.items():
        for field in _PATIENT_FACING:
            body = getattr(test, field).lower()
            for word in _JARGON + _REPO_INTERNALS:
                if word.lower() in body:
                    offences.append(f"{key}.{field}: {word!r}")
    assert offences == [], offences


def test_every_rung_says_what_it_is_actually_testing():
    """The scientific explanation is not deleted, it is relocated. Every rung
    owes the athlete an answer to 'what is this for', separately from 'how do
    I do it' — asked for directly, and the reason the anatomy can leave the
    instructions without the information being lost."""
    for key, test in fb.RUNGS.items():
        assert test.what_youre_testing.strip(), key
        assert len(test.what_youre_testing) > 80, key


def test_every_lock_states_the_tell_that_says_the_trial_is_void():
    """A lost lock makes the reading BETTER, not worse, so nothing warns you.
    That is why each lock must name something externally observable — a towel,
    a sheet of paper, a heel leaving the floor — rather than a feeling. The
    athlete's question was 'if the lock is lost can't you just redo the test?'
    Yes; the difficulty was never redoing it, it was noticing."""
    for key, test in fb.RUNGS.items():
        assert "tell" in test.lock.lower(), key
        assert "void" in test.lock.lower(), key
    assert "just reset and take the reading again" in fb.LOCK_EXPLAINED


def test_the_butterfly_heel_distance_is_a_frozen_number_not_a_floor_mark():
    """Found by the athlete reading the protocol: the adductor test set the
    heels to 'a marked position' and recorded nothing about where that was, so
    a re-mark by eye at the next session silently invalidates the comparison.
    Heels further out drop the knees without the groin being any longer."""
    names = {n for n, _ in fb.FROZEN_CONSTANTS}
    assert "butterfly_heel_distance_cm" in names
    adductors = fb.RUNGS["adductors"]
    assert "tailbone" in adductors.lock.lower()
    assert "mark" in adductors.lock.lower()      # says why a mark is not enough


def test_the_three_measures_are_explained_somewhere_the_athlete_can_see():
    """passive / isometric / active are the whole model and were previously
    explained nowhere on screen. 'Active' does not obviously mean 'under your
    own power' to anyone who has not read the module docstring."""
    explained = {m for m, _, _ in fb.MEASURES_EXPLAINED}
    assert explained == set(fb.MEASURES)
    for _measure, short, long in fb.MEASURES_EXPLAINED:
        assert short and len(long) > 80
    assert "hypermobile" in fb.GAP_EXPLAINED


# ── one target at a time ─────────────────────────────────────────────────────
#
# The athlete's design, 2026-08-06: the target skill is chosen BEFORE the tests
# are taken, and at the next assessment he is shown what moved and then decides
# whether to stay on the skill (take the next rung) or switch (get a different
# ladder entirely). His objection to the previous design is what forced it:
# "when you say Chest / pecs is the limiting factor — what skill am I working
# towards? Chest and pecs are only the limiting factor if I want to do a
# handstand or a bridge, but if my first goal is a pancake then chest and pecs
# wouldn't be that important compared to hamstrings."

def test_the_same_readings_prescribe_differently_for_different_targets():
    """THE POINT OF THE WHOLE REDESIGN. One set of numbers, two goals, two
    different answers — because a limiting rung is only meaningful against a
    target."""
    a = fb.Assessment(taken_on=TODAY, target_skill="pancake", readings=(
        fb.RungReading("hamstrings", active=27.0),         # -> 30, poor
        fb.RungReading("adductors", active=10.0),          # -> 60
        fb.RungReading("hip_rotation", active=32.0),       # -> 80
        fb.RungReading("lumbar", active=1.0),              # -> 80
        fb.RungReading("chest_horizontal", active=12.0),   # -> 20, worse
        fb.RungReading("shoulders_overhead", active=119.0),
        fb.RungReading("lats", active=112.0),
        fb.RungReading("thoracic_rotation", active=27.0),
    ))
    rep = fx.report(a, TODAY)

    pancake = fx.prescribe(rep, "pancake")
    shoulder = fx.prescribe(rep, "shoulder_flexion")

    # Chest is the lowest rung in the whole assessment, and it is IRRELEVANT to
    # the pancake — it is not on that ladder at all.
    assert pancake.limiting_rung == "hamstrings"
    assert shoulder.limiting_rung == "chest_horizontal"
    assert "chest_horizontal" not in fb.SKILLS["pancake"].ladder


def test_the_target_defaults_to_the_one_recorded_on_the_assessment():
    a = fb.Assessment(taken_on=TODAY, target_skill="pancake",
                      readings=(fb.RungReading("hamstrings", active=27.0),))
    rep = fx.report(a, TODAY)
    assert rep.target_skill == "pancake"
    assert fx.prescribe(rep).skill_key == "pancake"


def test_only_the_stretches_that_move_the_limiting_rung_are_returned():
    """Handing over the whole stack when one rung is the blocker is how "come
    to conclusions on where to focus" turns back into a list."""
    a = fb.Assessment(taken_on=TODAY, target_skill="pancake", readings=(
        fb.RungReading("hamstrings", active=81.0),      # -> 90, fine
        fb.RungReading("adductors", active=20.0),       # -> 20, the blocker
        fb.RungReading("hip_rotation", active=32.0),
        fb.RungReading("lumbar", active=1.0),
    ))
    p = fx.prescribe(fx.report(a, TODAY))
    assert p.limiting_rung == "adductors"
    assert p.stretches, "a built skill must offer a route"
    for s in p.stretches:
        assert "adductors" in s.targets, s.key
    # The pelvic-tilt step does not target adductors, so it must not appear.
    assert "pancake_tilt" not in {s.key for s in p.stretches}


def test_an_unmeasured_target_offers_the_whole_stack_rather_than_nothing():
    rep = fx.report(fb.Assessment(taken_on=TODAY, target_skill="pancake"), TODAY)
    p = fx.prescribe(rep)
    assert p.limiting_rung is None
    assert len(p.stretches) == len(fb.SKILLS["pancake"].stack)


def test_a_blocked_target_scores_but_has_no_route():
    p = fx.prescribe(fx.report(fb.Assessment(
        taken_on=TODAY, readings=(fb.RungReading("hip_flexors", active=-6.0),)),
        TODAY), "bridge")
    assert p is not None
    assert p.stretches == ()


def test_compare_shows_what_moved_between_two_assessments():
    """Shown after a re-test, before the stay-or-switch decision. That decision
    is where the model pays off and it cannot be made from one column."""
    before = fx.report(fb.Assessment(taken_on=date(2026, 8, 6), readings=(
        fb.RungReading("hamstrings", active=27.0),      # 30
        fb.RungReading("adductors", active=10.0),       # 60
    )), TODAY)
    after = fx.report(fb.Assessment(taken_on=date(2026, 10, 15), readings=(
        fb.RungReading("hamstrings", active=45.0),      # 50
        fb.RungReading("lumbar", active=1.0),           # new this time
    )), date(2026, 10, 15))

    deltas = {d.key: d for d in fx.compare(before, after)}
    assert deltas["hamstrings"].delta == pytest.approx(20.0, abs=0.5)
    assert deltas["hamstrings"].improved is True
    # Measured before but not after, and vice versa: both kept, with a None on
    # the missing side. Dropping them makes a partial re-test look complete.
    assert deltas["adductors"].after is None
    assert deltas["adductors"].delta is None
    assert deltas["lumbar"].before is None


def test_a_stack_is_ordered_cumulative_and_weighted_to_the_resisted_end():
    """The athlete's own instruction: "remember the heavily assisted to heavily
    resisted training". At Beighton 6/9 the ASSISTED half of that spectrum
    solves a problem he does not have — his passive range is fine and the
    active gap is the deficit — so no step in a stack of his may be assisted."""
    stack = fb.SKILLS["pancake"].stack
    assert len(stack) >= 3
    assert {s.spectrum for s in stack} <= set(fb.SPECTRUM)
    assert fb.ASSISTED not in {s.spectrum for s in stack}
    assert any(s.spectrum == fb.RESISTED for s in stack)
    # The resisted work is the destination, so it comes last.
    spectra = [s.spectrum for s in stack]
    assert spectra.index(fb.RESISTED) >= len(stack) - 2
    for s in stack:
        assert s.advance_when.strip(), s.key
        for t in s.targets:
            assert t in fb.RUNGS, s.key


def test_no_stack_step_is_a_forward_fold():
    """services.rules contraindicates 'forward fold', 'seated forward fold' and
    'toe touch' outright — end-range lumbar flexion on the covered annulus
    tears. The conventional pancake finishes as exactly that, so the flat-back
    redefinition is the only reason this skill is trainable at all."""
    from services import rules as _rules
    banned = {r.movement for r in _rules.MOVEMENT_RULES
              if r.severity == "contraindicated"}
    for skill in fb.SKILLS.values():
        for step in skill.stack:
            text = f"{step.name} {step.setup}".lower()
            for movement in banned:
                assert movement not in text, f"{step.key}: {movement!r}"


def test_the_target_survives_a_save_and_reload_and_an_unknown_one_does_not():
    a = fb.Assessment(taken_on=TODAY, target_skill="pancake",
                      readings=(fb.RungReading("hamstrings", active=45.0),))
    assert fx.assessment_from_dict(fx.assessment_to_dict(a)).target_skill == "pancake"

    # A renamed skill must not delete a session's worth of floor measurements.
    d = fx.assessment_to_dict(a)
    d["target_skill"] = "handstand"
    back = fx.assessment_from_dict(d)
    assert back is not None
    assert back.target_skill == ""
    assert len(back.readings) == 1
