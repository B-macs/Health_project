"""
Cluster A — the three layers, and the boundaries between them.

The layer rule is one-directional and is stated in every module docstring:

    MECHANICS (why) -> BATTERY (how to test) -> PRESCRIPTION (what to do)

Stating it is not enough. This repo already has the pattern for making a rule
like that executable — tests/test_no_streamlit_in_services.py — and the four
guards below do the same job for these layers, because a boundary nobody checks
is a boundary that erodes on the first inconvenient afternoon.
"""

import ast
import inspect
from datetime import date

import pytest

import cluster_a_battery as cb
import cluster_a_mechanics as cm
import cluster_a_prescription as cp
import flexibility_baselines as fb
from services import battery as b
from services import flexibility as fx
from services import rules

TODAY = date(2026, 8, 6)


def _source(module) -> str:
    return inspect.getsource(module)


# ── guard 1: the retired models must not come back ───────────────────────────

def test_the_rung_and_skill_model_is_gone_and_stays_gone():
    """v2 measured fourteen rungs and took min() per skill. It was deleted, not
    disabled — the battery is a decision tree with early exit and min() is a
    scoring function over everything, so a failing slot 0 makes the rest
    MEANINGLESS rather than lower-priority."""
    for name in ("rung_score", "score_skill", "SkillScore", "WIDE_GAP_POINTS",
                 "RungTest", "RUNGS", "SKILLS", "Stretch", "SELECTABLE_SKILLS",
                 "DEFAULT_TARGET_SKILL", "ASSESSMENTS"):
        assert not hasattr(fx, name), f"{name} is back on services.flexibility"
    for name in ("RUNGS", "SKILLS", "RungTest", "Skill", "Stretch",
                 "SELECTABLE_SKILLS", "BLOCKED_SKILLS", "DEFAULT_TARGET_SKILL",
                 "ASSESSMENTS", "RungReading"):
        assert not hasattr(fb, name), f"{name} is back on flexibility_baselines"


def test_the_refuted_two_sided_band_is_still_gone():
    """v1 scored a self-rated depth on a band with a penalty ABOVE it, so a
    rating of 88 scored 46. The athlete refuted it: his rating measured how far
    he got, not whether he controlled it. Two models later, the guard stays."""
    for name in ("band_score", "control_score", "CONTROL_BAND", "OVERSHOOT_SLOPE",
                 "UNDERSHOOT_EXPONENT"):
        assert not hasattr(fx, name), name


def test_no_score_out_of_one_hundred_is_produced_anywhere():
    """The battery's output is a pattern label and, in the source's words,
    'nothing else'. A score would re-import the averaging the model was
    replaced for."""
    for module in (fx, b, cb, cp):
        tree = ast.parse(_source(module))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                lowered = node.name.lower()
                assert "score" not in lowered, f"{module.__name__}.{node.name}"
                assert "bioage" not in lowered and "age_years" not in lowered


# ── guard 2: the battery names no exercise ───────────────────────────────────

def test_the_battery_layer_names_no_exercise():
    """The Battery says how to MEASURE. If it named exercises it would be
    prescribing, and the one-directional dependency would be a circle."""
    library_names = {e.name.lower() for e in cm.LIBRARY}
    for module in (b, cb):
        source = _source(module).lower()
        for name in library_names:
            assert name not in source, f"{module.__name__} names the exercise {name!r}"


def test_the_battery_layer_carries_no_doses():
    """Sets and reps are the Prescription's business. A dose in the Battery is
    the same boundary violation as an exercise, wearing a number."""
    for module in (b, cb):
        source = _source(module)
        for dose in (" × 8", " × 12", " × 90 s", "3 x 8", "sets", "reps"):
            assert dose not in source, f"{module.__name__} carries a dose: {dose!r}"


# ── guard 3: the prescription defines nothing it names ───────────────────────

def test_every_prescribed_exercise_resolves_in_the_mechanics_library():
    """THE load-bearing guard. The Prescription references exercises by NAME and
    must not define them; a name that does not resolve in Mechanics means it
    invented one, which is how two documents end up defining the same thing."""
    unresolved = []
    for pattern, stack in cp.STACKS.items():
        for item in stack.items:
            if cm.exercise(item.exercise) is None:
                unresolved.append((pattern, item.exercise))
    assert unresolved == [], unresolved


def test_the_prescription_layer_holds_no_tests():
    """It takes a pattern in. Producing one would make it a battery."""
    source = _source(cp).lower()
    for banned in ("def evaluate_", "slotresult", "slot_evaluators", "def run("):
        assert banned not in source, f"cluster_a_prescription contains {banned!r}"


def test_the_mechanics_layer_holds_no_doses_and_no_patterns():
    """Mechanics is why. A dose makes it a prescription; a pattern label makes
    it a battery.

    Checked STRUCTURALLY — an Exercise simply has nowhere to put a dose — rather
    than by scanning for "× 8" in the text. A scan would fire on the Copenhagen
    note recording what he last performed in 2025, and on the removal table
    recording the dose that made an exercise unsafe. Those are history and
    rationale, which is exactly what this layer is for; the boundary that
    matters is that nothing here can be READ as a prescription.
    """
    exercise_fields = {f for f in cm.Exercise.__dataclass_fields__}
    assert "dose" not in exercise_fields
    assert "sets" not in exercise_fields and "reps" not in exercise_fields

    assert not hasattr(cm, "PATTERNS")
    assert not hasattr(cm, "STACKS")
    assert not hasattr(cm, "prescribe")
    source = _source(cm)
    assert "def prescribe" not in source
    assert "SlotResult" not in source


# ── guard 4: a prescription without a pattern is a guess ─────────────────────

def test_prescribing_without_a_pattern_refuses_rather_than_guessing():
    """The source is explicit: 'a prescription without a pattern is a guess. Say
    so rather than guessing.' No default stack, no most-likely fallback, no
    starter programme — those are exactly the plausible-looking output the
    four-slot method exists to replace."""
    for nothing in (None, "", "   "):
        with pytest.raises(cp.NoPatternError):
            cp.prescribe(nothing)

    with pytest.raises(cp.NoPatternError):
        cp.prescribe("Z")          # not a Cluster A label

    # And through the service layer, from an empty report.
    empty = fx.assess(None, TODAY)
    with pytest.raises(cp.NoPatternError):
        fx.prescribe(empty)


def test_the_refusal_says_what_to_do_about_it():
    """A refusal that does not name the next action is an error message."""
    with pytest.raises(cp.NoPatternError) as caught:
        cp.prescribe(None)
    assert "run the battery" in str(caught.value).lower()


# ── the method: stop at the first failure ────────────────────────────────────

def _assessment(readings, taken_on=TODAY):
    return b.Assessment(cluster="a", taken_on=taken_on, readings=tuple(readings))


_GATE0_PASS = [b.Reading("gate0_neutral", 28.0, "cm"),
               b.Reading("gate0_turned_out", 25.0, "cm")]
_LEVERAGE_PASS = [b.Reading("leverage_bent", 8.0, "cm", side="left"),
                  b.Reading("leverage_bent", 9.0, "cm", side="right"),
                  b.Reading("leverage_straight", 95.0, "cm", side="left"),
                  b.Reading("leverage_straight", 94.0, "cm", side="right")]
_TILT_PASS = [b.Reading("tilt_range", 20.0, "cm"),
              b.Reading("tilt_production", 22.0, "cm")]


def test_a_failing_slot_stops_the_battery_and_the_rest_is_never_evaluated():
    """THE WHOLE DESIGN. Slots below a failure are not lower priority, they are
    meaningless — there is no value in a spectrum profile for a skill a bony
    block had already made unavailable."""
    # Gate 0 fails: turning out gains far more than the threshold.
    a = _assessment([b.Reading("gate0_neutral", 40.0, "cm"),
                     b.Reading("gate0_turned_out", 25.0, "cm")] + _LEVERAGE_PASS + _TILT_PASS)
    result = b.run("a", cb.SLOT_EVALUATORS, a)
    assert result.pattern == "B"
    assert result.stopped_at == b.SLOT_STRUCTURE
    assert len(result.slots) == 1, "slots below the failure were evaluated anyway"


def test_each_slot_can_be_the_one_that_stops_it():
    cases = [
        ([b.Reading("gate0_neutral", 40.0, "cm"),
          b.Reading("gate0_turned_out", 25.0, "cm")], "B", b.SLOT_STRUCTURE, 1),
        (_GATE0_PASS + [b.Reading("leverage_bent", 20.0, "cm"),
                        b.Reading("leverage_straight", 40.0, "cm")], "C", b.SLOT_REGRESSED, 2),
        (_GATE0_PASS + _LEVERAGE_PASS + [b.Reading("tilt_range", 40.0, "cm"),
                                         b.Reading("tilt_production", 55.0, "cm")],
         "F", b.SLOT_PREREQUISITE, 3),
        (_GATE0_PASS + _LEVERAGE_PASS + _TILT_PASS + [
            b.Reading("spectrum_active", 40.0, "°", side="left"),
            b.Reading("spectrum_active", 38.0, "°", side="right"),
            b.Reading("spectrum_isometric", 30.0, "cm"),
            b.Reading("spectrum_passive", 10.0, "cm")], "H", b.SLOT_SPECTRUM, 4),
    ]
    for readings, expected, slot, slots_run in cases:
        result = b.run("a", cb.SLOT_EVALUATORS, _assessment(readings))
        assert result.pattern == expected, (expected, result.pattern)
        assert result.stopped_at == slot
        assert len(result.slots) == slots_run


def test_gracilis_is_named_by_the_difference_between_two_leverages():
    """The crossing rule. Gracilis is the only adductor crossing the knee, so a
    pass-bent / fail-straight pattern names it — which is why length is tested
    at more than one leverage and why the deferred middle one costs resolution
    rather than the diagnosis."""
    a = _assessment(_GATE0_PASS + [b.Reading("leverage_bent", 8.0, "cm"),
                                   b.Reading("leverage_straight", 40.0, "cm")])
    assert b.run("a", cb.SLOT_EVALUATORS, a).pattern == "E"


def test_a_missing_reading_is_indeterminate_and_never_a_pass():
    """A measurement that was not taken is not evidence of health. This is the
    failure that would let an incomplete session look like a clean bill."""
    result = b.run("a", cb.SLOT_EVALUATORS, _assessment([]))
    assert result.pattern is None
    assert result.slots[0].indeterminate is True
    assert result.slots[0].passed is False
    assert result.complete is False


def test_the_worse_side_decides_and_sides_are_never_averaged():
    a = _assessment(_GATE0_PASS + [
        b.Reading("leverage_bent", 8.0, "cm", side="left"),
        b.Reading("leverage_bent", 22.0, "cm", side="right"),   # this one fails
        b.Reading("leverage_straight", 95.0, "cm", side="left"),
        b.Reading("leverage_straight", 94.0, "cm", side="right")])
    # The mean of 8 and 22 is 15, which would pass. The worse side must decide.
    assert b.run("a", cb.SLOT_EVALUATORS, a).pattern == "D"


def test_a_voided_trial_is_not_used():
    a = _assessment([b.Reading("gate0_neutral", 28.0, "cm"),
                     b.Reading("gate0_turned_out", 25.0, "cm", voided=True)])
    assert b.run("a", cb.SLOT_EVALUATORS, a).slots[0].indeterminate is True


# ── the load window ──────────────────────────────────────────────────────────

def test_an_isometric_as_deep_as_passive_means_the_load_was_too_light():
    """Not a result, a botched measurement: passive tissue absorbed the load and
    you measured passive twice. The slot must say so rather than reporting a
    gap of zero as if it meant something."""
    a = _assessment(_GATE0_PASS + _LEVERAGE_PASS + _TILT_PASS + [
        b.Reading("spectrum_active", 40.0, "°"),
        b.Reading("spectrum_isometric", 10.0, "cm"),
        b.Reading("spectrum_passive", 10.0, "cm")])
    slot = b.run("a", cb.SLOT_EVALUATORS, a).slots[-1]
    assert slot.indeterminate is True
    assert "too light" in slot.reason


def test_the_load_and_the_measurement_are_one_datum():
    """An isometric number without the load that produced it cannot be compared
    with anything, including itself next month."""
    r = b.Reading("spectrum_isometric", 22.0, "cm", load_kg=10.0)
    assert r.load_kg == 10.0
    back = fx.assessment_from_dict(fx.assessment_to_dict(_assessment([r])))
    assert back.readings[0].load_kg == 10.0


def test_isometric_shallower_handles_both_scale_directions():
    assert b.isometric_is_shallower(10.0, 22.0, smaller_is_better=True) is True
    assert b.isometric_is_shallower(10.0, 8.0, smaller_is_better=True) is False
    assert b.isometric_is_shallower(90.0, 70.0, smaller_is_better=False) is True
    assert b.isometric_is_shallower(90.0, 95.0, smaller_is_better=False) is False


# ── the noise floor ──────────────────────────────────────────────────────────

def test_no_noise_figure_until_three_mornings_and_nothing_is_a_result_before_then():
    assert b.noise_floor([12.0]) is None
    assert b.noise_floor([12.0, 13.0]) is None
    assert b.noise_floor([12.0, 13.0, 15.0]) == pytest.approx(3.0)

    # Before a floor exists, no change counts — the safe direction, because the
    # cost of a wrong True is changing a programme for no reason.
    assert b.is_a_result(50.0, None) is False


def test_a_change_inside_twice_the_noise_is_not_a_result():
    spread = b.noise_floor([12.0, 13.0, 15.0])        # 3.0
    assert b.is_a_result(5.0, spread) is False        # under 2x
    assert b.is_a_result(6.0, spread) is False        # exactly 2x is not enough
    assert b.is_a_result(7.0, spread) is True


def test_a_pattern_from_one_morning_is_a_hypothesis_not_a_verdict():
    a = _assessment(_GATE0_PASS + _LEVERAGE_PASS + [
        b.Reading("tilt_range", 40.0, "cm"), b.Reading("tilt_production", 55.0, "cm")])
    assert b.run("a", cb.SLOT_EVALUATORS, a, baseline_sessions=1).trusted is False
    assert b.run("a", cb.SLOT_EVALUATORS, a, baseline_sessions=3).trusted is True


# ── the expected landing, stated in advance ──────────────────────────────────

def test_the_athletes_own_baseline_routes_him_to_the_expected_pattern():
    """Written down before measuring so a borderline reading cannot be quietly
    read toward the answer already in mind. His 2026-08-05 report — 'hips stuck
    in flexion with tail bone down, back fully rounds' — is a slot 2 failure."""
    assert cb.EXPECTED_PATTERN == "F"
    a = _assessment(_GATE0_PASS + _LEVERAGE_PASS + [
        b.Reading("tilt_range", 40.0, "cm"), b.Reading("tilt_production", 55.0, "cm")])
    assert b.run("a", cb.SLOT_EVALUATORS, a).pattern == cb.EXPECTED_PATTERN


def test_pattern_f_is_the_tilt_specific_method_not_a_filtered_pancake_stack():
    """The rebuild, pinned. Every step must move the tilt, none may be a fold
    reached by external assistance, and the resisted end must be present —
    otherwise it has drifted back into the source's version."""
    stack = cp.prescribe("F")
    names = [i.exercise for i in stack.live_items]
    assert len(names) >= 4

    for name in names:
        ex = cm.exercise(name)
        assert ex is not None
        # Every prong touches the tilt or the pullers that produce it.
        assert {"seated_tilt", "puller_strength"} & set(ex.limiters), name

    spectra = {cm.exercise(n).spectrum for n in names}
    assert fb.RESISTED in spectra, "the tilt is produced by strength; it must be here"

    # The three removed assists must not have crept back.
    joined = " ".join(names).lower()
    for gone in ("behind the neck", "strap", "weight behind"):
        assert gone not in joined


# ── safety, at build time ────────────────────────────────────────────────────

STAGE = 2


def test_no_exercise_in_the_library_is_contraindicated_at_the_live_stage():
    """The substitutions are baked into the documents rather than filtered at
    runtime, so nothing contraindicated should survive to be filtered. If one
    does, the adaptation missed it."""
    bad = [e.name for e in cm.LIBRARY
           if rules.check_movement(e.name, STAGE)["severity"] == "contraindicated"]
    assert bad == [], bad


def test_no_exercise_in_the_library_is_unknown_to_the_rule_set():
    """`unknown` reads as 'no rule applies' and is not a block — services/yoga
    discards it outright. A movement the rules have never heard of is
    indistinguishable from one they cleared."""
    unknown = [e.name for e in cm.LIBRARY
               if rules.check_movement(e.name, STAGE)["severity"] == "unknown"]
    assert unknown == [], unknown


def test_every_stack_carries_the_mandatory_release_block():
    """It comes from patient_profile, not from any flexibility source — which is
    exactly why all nine stacks omitted it in the original."""
    for pattern in cp.STACKS:
        stack = cp.prescribe(pattern)
        block = fx.release_block_for(stack)
        assert len(block) >= 4, pattern
        names = [r.name for r in block]
        assert "Upper glute / TFL self-release" in names
        assert "Piriformis contract-relax (PNF)" in names


def test_a_stack_loading_the_right_hip_adds_the_tendon_path_drill():
    """Derived from the stack's contents rather than hard-coded per pattern, so
    a stack edit cannot leave the protocol behind."""
    tilt = fx.release_block_for(cp.prescribe("F"))       # contains lift-offs
    assert any("tendon-path" in r.name.lower() for r in tilt)


def test_every_deferral_names_the_event_that_lifts_it():
    """A hold is meant to be lifted. One with no stated condition becomes
    permanent by nobody looking."""
    assert cm.DEFERRED, "expected the ER-cued loaded squats to be held"
    for ex in cm.DEFERRED:
        assert ex.deferred_until, ex.name
        assert ex.reverts_when, ex.name
    for ex in cm.ADAPTED:
        assert ex.reverts_when, ex.name
    for removal in cm.REMOVED:
        assert removal.reverts_when, removal.name


def test_the_deferred_squats_are_held_on_a_condition_not_a_date():
    """The deferral is a MEASUREMENT decision, not a permission one. The right
    hip has an open question about snapping under loaded squat work, the gym
    block already contains squat work answering it, and adding a second new
    externally-rotated squat now would make a change impossible to attribute.

    Held on the condition rather than on a calendar date, because a date passes
    whether or not the thing it was waiting for has happened — which is how a
    hold becomes permanent, or lifts too early, by nobody looking."""
    deferred = {e.key for e in cm.DEFERRED}
    assert {"horse_stance", "cossack_bent", "cossack_straight"} <= deferred
    for ex in cm.DEFERRED:
        assert ex.deferred_until, ex.name
        assert not any(ch.isdigit() for ch in ex.deferred_until), (
            f"{ex.name} is held until a date; hold it on the condition instead")


# ── plain English, in the fields the athlete reads mid-test ──────────────────

_JARGON = ("supine", "prone", "gluteal fold", "lateral aspect", "ulnar", "acromion",
           "styloid", "inclinometer", "pes planus", "dorsiflexion", "adduction",
           "rectus femoris", "posterior tilt", "anterior tilt", "lumbar", "cervical",
           "thoracic", "contraindicat", "gracilis", "adductor magnus", "femoroacetabular")
#: Deliberately NOT including bare words like "tests" or "library" — those are
#: ordinary English and a protocol is allowed to say "the other two tests still
#: name the muscle". Only strings that could not appear in prose about a
#: movement belong here.
_REPO_INTERNALS = (".py", "rules.py", "symptom_log", "patient_profile", "finding #",
                   "slot_", "_fb.", "services.", "cluster_a_", "dataclass")
_PATIENT_FACING = ("label", "setup", "lock", "measurement", "safety")


def test_the_fields_read_mid_test_stay_in_plain_english():
    """setup / lock / measurement / safety are read while lying on the floor
    holding a tape. Anatomy goes in what_youre_testing; nothing about this
    codebase goes anywhere. LABEL is included — it heads every step, and it was
    the one field a previous version of this test forgot to cover."""
    offences = []
    for key, test in cb.TESTS.items():
        for field in _PATIENT_FACING:
            body = getattr(test, field).lower()
            for word in _JARGON + _REPO_INTERNALS:
                if word.lower() in body:
                    offences.append(f"{key}.{field}: {word!r}")
    assert offences == [], offences


def test_every_test_says_what_it_is_actually_testing():
    for key, test in cb.TESTS.items():
        assert len(test.what_youre_testing) > 80, key


def test_every_test_names_a_lock_with_a_tell():
    """A lost lock makes the reading BETTER, not worse, so nothing warns you.
    That is why each lock must name something observable from outside."""
    for key, test in cb.TESTS.items():
        assert "tell" in test.lock.lower(), key
        assert "void" in test.lock.lower(), key
    assert "just reset and take the reading again" in fb.LOCK_EXPLAINED


def test_the_measure_order_is_active_isometric_passive():
    """Passive work leaves tissue looser for an hour, so a passive trial taken
    first flatters everything after it. This is the procedural rule most likely
    to be broken by working through the tests in written order."""
    assert fb.MEASURE_ORDER == (fb.ACTIVE, fb.ISOMETRIC, fb.PASSIVE)
    spectrum = [k for k in cb.TEST_ORDER if cb.TESTS[k].slot == b.SLOT_SPECTRUM]
    assert spectrum == ["spectrum_active", "spectrum_isometric", "spectrum_passive"]


def test_the_nerve_check_is_a_differentiator_not_a_provocation():
    """The original said to push until you produce a sharp, electric or burning
    sensation and read that as a result. Those words are the deterministic
    neural keywords in services/stats.py, which hard-flags on them before
    anything else runs.

    The programme is self-directed now, so the instruction is no longer "take it
    to someone" — but the STOP survives unchanged, because an electric or
    burning sensation is a different CATEGORY of event rather than a permission
    question. Losing the stop while removing the referral would have been the
    wrong half to drop.
    """
    text = cb.NERVE_CHECK.lower()
    assert "differentiator, not a provocation" in text
    assert "submaximal" in text
    assert "stop" in text
    assert "do not train into it" in text
    assert "finding, not a number" in text


# ── serialisation ────────────────────────────────────────────────────────────

def test_an_assessment_round_trips():
    a = _assessment(_GATE0_PASS + _TILT_PASS)
    assert fx.assessment_from_dict(fx.assessment_to_dict(a)) == a


def test_the_retired_schema_is_dropped_rather_than_migrated():
    """Version 1 held the rung model. A v1 payload is not convertible — its
    readings measured different positions with different landmarks — and none
    was ever recorded, so dropping it costs nothing and guessing would not."""
    assert fx.SCHEMA_VERSION == 2
    assert fx.assessment_from_dict({"schema": 1, "taken_on": "2026-08-06"}) is None


def test_unreadable_payloads_degrade_to_none_rather_than_half_parsing():
    for payload in ({}, {"schema": 2}, {"schema": 2, "taken_on": "not-a-date"},
                    {"schema": 2, "taken_on": "2026-08-06", "cluster": "zz"}):
        assert fx.assessment_from_dict(payload) is None


def test_a_reading_for_a_retired_test_is_dropped_not_kept():
    payload = fx.assessment_to_dict(_assessment(_GATE0_PASS))
    payload["readings"].append({"test_key": "no_such_test", "value": 1.0, "unit": "cm"})
    back = fx.assessment_from_dict(payload)
    assert [r.test_key for r in back.readings] == ["gate0_neutral", "gate0_turned_out"]


def test_re_entering_a_test_overwrites_and_carries_every_field_through():
    """merge_reading must not silently drop a field. The version of this in the
    model it replaced dropped one, masked because it had only one possible
    value at the time."""
    a = b.Assessment(cluster="a", taken_on=TODAY, cold=False, note="second attempt",
                     readings=(b.Reading("leverage_bent", 8.0, "cm", side="left"),
                               b.Reading("leverage_bent", 9.0, "cm", side="right")))
    merged = fx.merge_reading(a, b.Reading("leverage_bent", 6.0, "cm", side="left"))

    assert merged.cluster == "a" and merged.cold is False and merged.note == "second attempt"
    assert merged.taken_on == TODAY
    left = [r for r in merged.readings if r.side == "left"]
    assert len(left) == 1 and left[0].value == 6.0
    assert any(r.side == "right" and r.value == 9.0 for r in merged.readings)


def test_progress_counts_distinct_tests_not_readings():
    """A bilateral test writes two readings for one test. Counting readings
    displayed '19 of 14' in the model this replaced."""
    a = _assessment([b.Reading("leverage_bent", 8.0, "cm", side="left"),
                     b.Reading("leverage_bent", 9.0, "cm", side="right")])
    done, total = fx.capture_progress(a)
    assert done == 1
    assert total == len(cb.AVAILABLE_TESTS)


# ── scheduling ───────────────────────────────────────────────────────────────

def test_a_rest_day_is_now_the_worst_slot_rather_than_ignored():
    """RESOLVED 2026-08-06. This used to accept is_rest_day and deliberately
    ignore it, because nothing distinguished a restorative flow from an
    adaptation-seeking session. The Prescription settles it: a cluster session
    is adaptation-seeking by definition."""
    window, reason = fx.flexibility_window(date(2026, 8, 9), set(), is_rest_day=True)
    assert window == fb.WINDOW_POOR
    assert "not recovery" in reason
    assert not hasattr(fb, "REST_DAY_CONFLICT_UNRESOLVED")


def test_the_window_reads_the_training_log():
    hard = {date(2026, 8, 5)}
    assert fx.flexibility_window(date(2026, 8, 6), hard)[0] == fb.WINDOW_POOR
    assert fx.flexibility_window(date(2026, 8, 7), hard)[0] == fb.WINDOW_GOOD
    assert fx.flexibility_window(date(2026, 8, 5), hard)[0] == fb.WINDOW_OK
    assert fx.flexibility_window(date(2026, 8, 5), hard, same_day_pm=True)[0] == fb.WINDOW_GOOD


def test_staleness_halves_and_decays_weight_not_value():
    assert fx.staleness_confidence(TODAY, TODAY) == 1.0
    year_ago = date.fromordinal(TODAY.toordinal() - 365)
    assert fx.staleness_confidence(year_ago, TODAY) == pytest.approx(0.5, abs=0.01)
    future = date.fromordinal(TODAY.toordinal() + 400)
    assert fx.staleness_confidence(future, TODAY) == 1.0


# ── provenance ───────────────────────────────────────────────────────────────

def test_the_legacy_readings_are_provenance_and_feed_nothing():
    """22 pose ratings and 5 gym readings, kept as history. A battery asks for
    passive/isometric/active in a locked position measured cold; a self-rating
    of a yoga pose answers none of the three."""
    assert len(fb.LEGACY_POSE_DEPTH_RATINGS_2026_08_05) == 22
    assert len(fb.LEGACY_GYM_READINGS) == 5
    for module in (fx, b, cb, cp, cm):
        source = _source(module)
        assert "LEGACY_POSE_DEPTH_RATINGS" not in source.split('"""', 2)[-1]


def test_no_flexibility_age_in_years():
    """The gym ships one: 28 against a live age of 31, but measured when he was
    30 — a stale measurement against a moving comparator, so the gap widens
    every birthday without anybody moving."""
    assert fb.AGE_AT_SCAN_YEARS == 30
    assert fb.VENDOR_BIOAGE_COMPARED_AGAINST_AGE == 31
    tree = ast.parse(_source(fx))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            assert "age" not in node.name.lower()


def test_no_streamlit_in_the_service_modules():
    for module in (fx, b):
        tree = ast.parse(_source(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or node.module.split(".")[0] != "streamlit"


# ── what a verdict rests on ──────────────────────────────────────────────────
#
# Added after the first real run of this battery returned Pattern E off a cut
# point of 90 cm that nobody had validated. The source specifies Test 1 entirely
# qualitatively — "fails both", "fails bent, straight relatively better",
# "passes bent, fails straight badly" — and gives NO numbers. They were invented
# so the code could run, and then the code handed out a diagnosis.

def test_the_source_gives_no_numbers_for_the_leverage_test():
    """The premise of everything below. If the source ever does supply cut
    points, this test should fail and the thresholds should come from there."""
    import io, os
    doc = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "Input_files", "assessment_battery.md")
    if not os.path.exists(doc):
        pytest.skip("Input_files/ is gitignored and absent from this checkout")
    text = io.open(doc, encoding="utf-8").read()
    table = text.split("| Pattern of results | Reading |")[1].split("\n\n")[0]
    assert "cm" not in table, "the source now gives numbers — use them"
    assert "Fails both" in table and "fails straight badly" in table


def test_gate_zero_is_the_only_slot_that_needs_no_invented_number():
    """It compares two of his own readings taken minutes apart, so it carries
    its own reference. Every other slot measures against a line we drew."""
    a = _assessment([b.Reading("gate0_neutral", 40.0, "cm"),
                     b.Reading("gate0_turned_out", 25.0, "cm")])
    result = b.run("a", cb.SLOT_EVALUATORS, a)
    assert result.basis == b.BASIS_RELATIVE
    assert result.rests_on_an_invented_number is False


def test_a_leverage_verdict_declares_that_it_rests_on_an_invented_number():
    """Pattern E specifically — the one that actually came out — must carry the
    caveat rather than reading as a finding about his gracilis."""
    a = _assessment(_GATE0_PASS + [b.Reading("leverage_bent", 8.0, "cm"),
                                   b.Reading("leverage_straight", 40.0, "cm")])
    result = b.run("a", cb.SLOT_EVALUATORS, a)
    assert result.pattern == "E"
    assert result.basis == b.BASIS_PROVISIONAL
    assert result.rests_on_an_invented_number is True


def test_the_two_reasons_a_pattern_is_untrusted_are_kept_separate():
    """More mornings fixes one; a validated threshold fixes the other. Conflating
    them would let three repeat measurements look like they had confirmed a
    number nobody had checked."""
    a = _assessment(_GATE0_PASS + [b.Reading("leverage_bent", 8.0, "cm"),
                                   b.Reading("leverage_straight", 40.0, "cm")])
    settled = b.run("a", cb.SLOT_EVALUATORS, a, baseline_sessions=3)
    assert settled.trusted is True                       # enough mornings
    assert settled.rests_on_an_invented_number is True   # still an invented line


def test_a_slot_that_forgets_to_declare_its_basis_reads_as_provisional():
    """The safe default. A slot with no stated basis should not be mistaken for
    one that compares the athlete against himself."""
    assert b.SlotResult(slot=0, passed=True).basis == b.BASIS_PROVISIONAL


# ── the setup number that decides the pattern ────────────────────────────────

def test_the_bent_leverage_asks_for_the_heel_distance():
    """Pattern E is 'passes bent, fails straight'. Heels pulled closer than the
    reference drop the knees further, so the bent test passes too easily and a
    whole-group restriction comes out looking like a gracilis one. The number
    that was not being captured is the one that chose the diagnosis."""
    test = cb.TESTS["leverage_bent"]
    assert test.setup_input, "the bent leverage must capture its heel distance"
    assert "heel" in test.setup_input.lower()
    assert "heel" in test.what_youre_testing.lower()


def test_the_setup_value_round_trips_and_older_payloads_still_parse():
    """Added WITHOUT a schema bump on purpose: bumping would have silently
    dropped the athlete's first recorded session, which is far worse than a
    missing setup number."""
    a = _assessment([b.Reading("leverage_bent", 8.0, "cm", side="left", setup_value=34.0)])
    back = fx.assessment_from_dict(fx.assessment_to_dict(a))
    assert back.readings[0].setup_value == 34.0

    stale = fx.assessment_to_dict(a)
    for reading in stale["readings"]:
        reading.pop("setup_value", None)
    recovered = fx.assessment_from_dict(stale)
    assert recovered is not None
    assert recovered.readings[0].setup_value is None
