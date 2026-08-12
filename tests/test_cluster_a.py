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
import math
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


#: Gate 0 records the WIDTH of the split and the thresholds are heights off the
#: floor, so the fixtures below are written as the DEPTH they mean and converted
#: — a bare 162.6 would say nothing about which side of the relevance line it
#: falls on. A plausible standing inseam for this athlete's 182 cm.
_LEG_LENGTH = 86.0


def _gate0(gap_cm, key="gate0_neutral"):
    """A gate 0 reading that puts the athlete `gap_cm` off the floor."""
    span = 2.0 * math.sqrt(_LEG_LENGTH ** 2 - gap_cm ** 2)
    return b.Reading(key, round(span, 1), "cm", setup_value=_LEG_LENGTH)


_GATE0_PASS = [_gate0(28.0), _gate0(25.0, "gate0_turned_out")]
_LEVERAGE_PASS = [b.Reading("leverage_bent", 8.0, "cm", side="left"),
                  b.Reading("leverage_bent", 9.0, "cm", side="right"),
                  b.Reading("leverage_straight", 95.0, "cm", side="left"),
                  b.Reading("leverage_straight", 94.0, "cm", side="right")]
_TILT_PASS = [b.Reading("tilt_production", 25.0, "°"),
              b.Reading("tilt_range", 30.0, "°")]
#: Pattern B needs the neutral reading INSIDE the relevance line — above it,
#: bone is not a live question and slot 0 passes on the height alone.
_GATE0_BONY = [_gate0(14.0), _gate0(3.0, "gate0_turned_out")]


def test_a_failing_slot_stops_the_battery_and_the_rest_is_never_evaluated():
    """THE WHOLE DESIGN. Slots below a failure are not lower priority, they are
    meaningless — there is no value in a spectrum profile for a skill a bony
    block had already made unavailable."""
    # Gate 0 fails: turning out gains far more than the threshold.
    a = _assessment(_GATE0_BONY + _LEVERAGE_PASS + _TILT_PASS)
    result = b.run("a", cb.SLOT_EVALUATORS, a)
    assert result.pattern == "B"
    assert result.stopped_at == b.SLOT_STRUCTURE
    assert len(result.slots) == 1, "slots below the failure were evaluated anyway"


def test_each_slot_can_be_the_one_that_stops_it():
    cases = [
        (list(_GATE0_BONY), "B", b.SLOT_STRUCTURE, 1),
        (_GATE0_PASS + [b.Reading("leverage_bent", 20.0, "cm"),
                        b.Reading("leverage_straight", 40.0, "cm")], "C", b.SLOT_REGRESSED, 2),
        (_GATE0_PASS + _LEVERAGE_PASS + [b.Reading("tilt_range", 8.0, "°"),
                                         b.Reading("tilt_production", 4.0, "°")],
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
    # Inside the relevance line so the turned-out attempt is REQUIRED — voiding
    # it must leave the slot unanswerable, not quietly passed.
    a = _assessment([_gate0(14.0),
                     b.Reading("gate0_turned_out", _gate0(3.0).value, "cm",
                               setup_value=_LEG_LENGTH, voided=True)])
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
        b.Reading("tilt_range", 8.0, "°"), b.Reading("tilt_production", 4.0, "°")])
    assert b.run("a", cb.SLOT_EVALUATORS, a, baseline_sessions=1).trusted is False
    assert b.run("a", cb.SLOT_EVALUATORS, a, baseline_sessions=3).trusted is True


# ── the expected landing, stated in advance ──────────────────────────────────

def test_the_athletes_own_baseline_routes_him_to_the_expected_pattern():
    """Written down before measuring so a borderline reading cannot be quietly
    read toward the answer already in mind. His 2026-08-05 report — 'hips stuck
    in flexion with tail bone down, back fully rounds' — is a slot 2 failure."""
    assert cb.EXPECTED_PATTERN == "F"
    a = _assessment(_GATE0_PASS + _LEVERAGE_PASS + [
        b.Reading("tilt_range", 8.0, "°"), b.Reading("tilt_production", 4.0, "°")])
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


# ── the stacking rules, encoded ──────────────────────────────────────────────
#
# The source's own rules (Prescription, "Stacking rules"): each exercise feeds
# the next; ISOLATED BEFORE INTEGRATED — components open first, the full skill
# comes last; bent knee before straight knee, except §E; triangle before
# inline; the stack shrinks. They governed how the stacks were BUILT but lived
# only as prose, so a stack edit could break them silently. Encoded 2026-08-07
# on the athlete's request — and the audit that prompted it found §A
# transcribed in the wrong order, which is the argument for the tests.

#: The full-position expressions of the cluster's two skills.
_INTEGRATED = {"triangle_split", "inline_split", "isometric_split",
               "pancake_own_power", "cossack_bent", "cossack_straight",
               "horse_stance", "horse_stance_weighted"}
#: Bent-knee vs straight-knee adductor work, for the leverage-order rule.
_BENT = {"tailors_pose", "frog_rocks", "butterfly_pir", "butterfly_active",
         "butterfly_press_downs"}
_STRAIGHT = {"wall_straddle", "triangle_split", "inline_split",
             "isometric_split", "cossack_straight"}


def _live_keys(stack) -> list:
    """The stack's live items as library keys, in performed order."""
    return [cm.LIBRARY_BY_NAME[i.exercise].key for i in stack.live_items]


def test_stacks_open_with_a_component_not_the_full_position():
    """Isolated before integrated — components open first. §G and §H are the
    two documented exceptions: strength stacks whose opening triangle is a
    door-opener, and the exemption must stay stated on the stack itself so it
    reads as a decision rather than a drift."""
    for pattern in ("A", "B", "C", "D", "E", "F", "I"):
        first = _live_keys(cp.STACKS[pattern])[0]
        assert first not in _INTEGRATED, (pattern, first)
    for pattern in ("G", "H"):
        assert _live_keys(cp.STACKS[pattern])[0] == "triangle_split"
    assert "open the door" in cp.STACKS["H"].items[0].note.lower()
    assert "end of the session" in cp.STACKS["G"].intro.lower()


def test_stretching_stacks_end_in_the_full_position():
    """Components open, the full skill comes last — the Daniel ladder's shape.
    §G belongs here too: strength ordering in the middle, but it still closes
    on the pancake under his own power."""
    for pattern in ("B", "C", "D", "E", "G"):
        last = _live_keys(cp.STACKS[pattern])[-1]
        assert last in _INTEGRATED, (pattern, last)


def test_f_integrates_through_the_block_not_a_finisher():
    """§F deliberately contains NO full-position item. Pattern F means the
    position is not reachable even with help, so a full-skill finisher would be
    performed through the lumbar rounding — training the compensation. The
    integration is the progression variable instead: the elevated hinge IS the
    pancake, regressed, and the block coming down is what converges on it."""
    keys = _live_keys(cp.STACKS["F"])
    assert not set(keys) & _INTEGRATED, keys
    assert keys[0] == "pelvic_rock", "the isolated movement opens the stack"
    assert "elevated_hinge" in keys, "the regressed pancake is the integration"
    assert "block" in cp.STACKS["F"].outro.lower(), (
        "success must be stated as the block coming down, not the reach")


def test_bent_knee_before_straight_knee_except_e():
    """Bent-knee work opens the rest of the group so the straight-knee work can
    reach gracilis instead of being capped before it gets there. §E is the
    documented exception — straight-knee loading is its entire point, and its
    intro must keep saying so."""
    for pattern in ("C", "D"):
        keys = _live_keys(cp.STACKS[pattern])
        bent = [i for i, k in enumerate(keys) if k in _BENT]
        straight = [i for i, k in enumerate(keys) if k in _STRAIGHT]
        assert bent and straight, pattern
        assert max(bent) < min(straight), (pattern, keys)
    assert "straight" in cp.STACKS["E"].intro.lower()
    assert not [k for k in _live_keys(cp.STACKS["E"]) if k in _BENT], (
        "bent-leg work slackens the exact muscle §E exists to load")


def test_triangle_before_inline_wherever_inline_appears():
    """'Get the triangle position comfortable before adding inline drills.'
    Inline is in no stack today; the guard exists for the day it is added."""
    for pattern, stack in cp.STACKS.items():
        keys = _live_keys(stack)
        if "inline_split" in keys:
            assert "triangle_split" in keys[:keys.index("inline_split")], pattern


def test_every_item_tells_its_stacks_story():
    """Each exercise feeds the next — it shares tissue with the stack or builds
    a prerequisite for it. Tags cannot express 'prerequisite', so the checkable
    form is a per-stack set of limiters an item may touch. What this catches is
    the real failure mode: an exercise pasted into a stack whose diagnosis it
    does not serve."""
    relevant = {
        "A": {"bone", "puller_strength", "adductor_length"},
        "B": {"bone", "seated_tilt", "adductor_length"},
        "C": {"adductor_length", "seated_tilt", "end_range_strength"},
        "D": {"adductor_length", "puller_strength", "bone"},
        "E": {"adductor_length", "end_range_strength", "bone"},
        "F": {"seated_tilt", "puller_strength"},
        "G": {"seated_tilt", "puller_strength", "end_range_strength",
              "adductor_length", "bone"},
        "H": {"end_range_strength", "adductor_length", "bone"},
        "I": {"puller_strength", "adductor_length", "bone"},
    }
    for pattern, stack in cp.STACKS.items():
        for item in stack.items:                      # deferred items included
            ex = cm.exercise(item.exercise)
            assert set(ex.limiters) & relevant[pattern], (pattern, ex.key)


def test_the_stack_ceiling_holds():
    """Three to five exercises, five a hard ceiling; the release block does not
    count toward it. §A sits under the floor deliberately — it is not a
    stretching stack, and padding it to three would invent work."""
    for pattern, stack in cp.STACKS.items():
        assert len(stack.live_items) <= 5, pattern
        if pattern != "A":
            assert len(stack.live_items) >= 3, pattern


def test_a_grooms_the_turn_out_before_it_is_spent_in_the_position():
    """RESTORED 2026-08-07. The source document's §A runs the ER hold first and
    the triangle second; the Python transcription had inverted them, making §A
    the one stack that opened with the integrated position. Isolated before
    integrated, applied to the stack where the audit found it backwards."""
    keys = _live_keys(cp.STACKS["A"])
    assert keys.index("er_holds") < keys.index("triangle_split")


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
_PATIENT_FACING = ("label", "setup", "lock", "measurement", "safety",
                   "input_hint", "setup_input")


#: The athlete's wording rule (2026-08-07): when two options are offered, offer
#: them — never add that it does not matter which. The reader already assumes a
#: free choice unless told otherwise, so the phrase is pure noise.
_HEDGES = ("doesn't matter", "does not matter", "either is fine", "either works",
           "whichever")


def test_the_fields_read_mid_test_stay_in_plain_english():
    """setup / lock / measurement / safety are read while lying on the floor
    holding a tape. Anatomy goes in what_youre_testing; nothing about this
    codebase goes anywhere. LABEL is included — it heads every step, and it was
    the one field a previous version of this test forgot to cover."""
    offences = []
    for key, test in cb.TESTS.items():
        for field in _PATIENT_FACING:
            body = getattr(test, field).lower()
            for word in _JARGON + _REPO_INTERNALS + _HEDGES:
                if word.lower() in body:
                    offences.append(f"{key}.{field}: {word!r}")
    assert offences == [], offences


# ── the exercise library says HOW, not just why ──────────────────────────────
#
# The athlete's direction (2026-08-07), after the §F walkthrough: knowing WHY is
# assumed correct in the background — understanding HOW is the part the user
# needs, and the notes alone did not provide it. Five mandatory fields per
# exercise: where your body is, what you actually do (including what resists
# you), what you should feel, what ends the set, and what progress looks like.

_HOW_FIELDS = ("position", "movement", "feel", "stop", "progress")


def test_every_exercise_says_how_to_do_it_not_just_why():
    for ex in cm.LIBRARY:
        for field in _HOW_FIELDS:
            assert getattr(ex, field).strip(), f"{ex.key}.{field} is empty"
        assert len(ex.movement) >= 40, (
            f"{ex.key}.movement is a stub — it must say what you actually do")


def test_the_how_fields_stay_in_plain_english_and_never_hedge():
    """Same rule as the battery's patient-facing fields — anatomy belongs in
    the note (the why), not in the instructions — plus the wording rule: no
    'it doesn't matter which' after offering options."""
    offences = []
    for ex in cm.LIBRARY:
        for field in _HOW_FIELDS:
            body = getattr(ex, field).lower()
            for word in _JARGON + _REPO_INTERNALS + _HEDGES:
                if word.lower() in body:
                    offences.append(f"{ex.key}.{field}: {word!r}")
    assert offences == [], offences


def test_the_positions_carry_the_athletes_corrections():
    """From the 2026-08-07 review of §F: the straddle hinges must state the
    legs are straight, and the legs-together hinge must say STANDING — the
    original note left the entire body position unstated, and a seated
    legs-together hinge would have zero range for this athlete to train in."""
    for key in ("elevated_hinge", "pancake_own_power", "straddle_lift_offs",
                "loaded_flat_back_hinge"):
        assert "straight" in cm.LIBRARY_BY_KEY[key].position.lower(), key
    assert cm.LIBRARY_BY_KEY["flat_back_hinge"].position.lower().startswith("standing")


def test_the_lift_offs_and_the_hinge_are_distinguishable_from_their_text():
    """The complaint that started this: nothing said how the two differ. The
    lift-offs must name what actually resists you (your own tissue, not
    gravity); the hinge must be standing with the legs together. If either
    stops being true, the two blur back together."""
    lift = cm.LIBRARY_BY_KEY["straddle_lift_offs"]
    hinge = cm.LIBRARY_BY_KEY["flat_back_hinge"]
    assert "gravity is not the resistance" in lift.movement.lower()
    assert "straddle" in lift.position.lower()
    assert "legs together" in hinge.name.lower()
    assert "standing" in hinge.position.lower()


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


def test_the_retest_is_never_the_morning_after_leg_training():
    """The athlete's rule (2026-08-07): a leg day the day before reads as extra
    tightness in exactly the areas being tested, so the reading would measure
    the leg day, not the baseline — the same contamination class as a warm-up,
    one day earlier."""
    last = date(2026, 8, 16)
    assert fx.retest_due_on(last) == date(2026, 9, 13)
    blocked, reason = fx.retest_readiness(last, date(2026, 9, 13),
                                          {date(2026, 9, 12)})
    assert blocked == fx.RETEST_BLOCKED
    assert "yesterday loaded the legs" in reason
    ready, _ = fx.retest_readiness(last, date(2026, 9, 13), set())
    assert ready == fx.RETEST_READY


def test_the_day_before_warns_to_stay_off_the_legs():
    """TOMORROW exists so the training screen can protect the reading while
    today's session can still be moved — by the morning of, it is too late."""
    last = date(2026, 8, 16)
    status, reason = fx.retest_readiness(last, date(2026, 9, 12), set())
    assert status == fx.RETEST_TOMORROW
    assert "off the legs" in reason
    status, reason = fx.retest_readiness(last, date(2026, 9, 12),
                                         {date(2026, 9, 12)})
    assert status == fx.RETEST_TOMORROW
    assert "loaded the legs" in reason.lower()
    assert "swap" in reason.lower()
    status, _ = fx.retest_readiness(last, date(2026, 9, 1), set())
    assert status == fx.RETEST_NOT_DUE


def _leg_session(*names, on="2026-09-12"):
    from services.models import ExerciseEntry, SessionRecord
    return SessionRecord(session_date=on, session_duration_minutes=60.0,
                         session_rpe=6.0, session_au=360.0,
                         exercises=[ExerciseEntry(name=n, movement_type="Strength")
                                    for n in names])


def _counts_as_leg_work(name) -> bool:
    return name not in fx.RELEASE_EXERCISES


def test_leg_days_are_judged_by_the_same_map_the_sectors_read():
    """'A leg day' must mean one thing everywhere, so the judgement reads
    training_constants.EXERCISE_BODY_REGION — the map strength and tonnage
    already depend on — rather than inventing a second definition."""
    import training_constants as tc
    lower = next(n for n, r in tc.EXERCISE_BODY_REGION.items()
                 if r == "lower_body" and _counts_as_leg_work(n))
    upper = next(n for n, r in tc.EXERCISE_BODY_REGION.items() if r == "upper_body")

    assert fx.leg_loading_days([_leg_session(lower)]) == {date(2026, 9, 12)}
    assert fx.leg_loading_days([_leg_session(upper)]) == set()
    assert fx.leg_loading_days(None) == set()


def test_the_release_block_is_not_a_leg_day():
    """MEASURED FAILURE, 2026-08-12, found by the athlete on the capture screen
    the morning he was about to take his first battery readings.

    The cold gate warned "yesterday's session loaded your legs" against
    2026-08-11 — a walk plus the pre-session release block, RPE 2, 102 AU,
    nothing loaded in it. Sector alone calls a piriformis PNF, a TFL
    self-release and Controlled Walking lower_body, and that release block runs
    before EVERY session, so the warning fired on nearly every morning. Worse,
    its stated mechanism ("reads TIGHTER than your real baseline") is backwards
    for the only three items that triggered it.
    """
    assert fx.leg_loading_days([_leg_session(
        "Controlled Walking",
        "Child's Pose",
        "Full Side Bridge",
        "Thread-the-Needle (Thoracic Rotation)",
        "Scapular Wall Slide",
        "Piriformis Contract-Relax (PNF)",
        "Upper Glute / TFL Self-Release",
        on="2026-08-11")]) == set()


def test_loaded_lower_body_work_is_still_a_leg_day():
    """The contamination the rule actually exists for — the real 2026-08-06
    session, RPE 7, 448 AU. The release items are present here too, so this
    also pins that release work does not SUPPRESS a genuine leg day."""
    assert fx.leg_loading_days([_leg_session(
        "Pallof Press Hold (Doorframe)",
        "Single-Arm DB Row",
        "Lat Pulldown",
        "Hip Thrust (Loaded)",
        "Romanian Deadlift (DB)",
        "Piriformis Contract-Relax (PNF)",
        "Upper Glute / TFL Self-Release",
        on="2026-08-06")]) == {date(2026, 8, 6)}


def test_running_and_hiking_are_still_leg_days():
    """The case the exclusion must not swallow. Stage 2B introduces running
    (10 km, 2026-10-11) and the outdoor importer logs it as a real session; a
    run the day before a retest is exactly the tightness the rule guards
    against. These sit at bodyweight_compound (0.5), above the release line."""
    for name in ("Outdoor Run", "Outdoor Trail Run", "Outdoor Hike", "Outdoor Walk"):
        assert fx.leg_loading_days([_leg_session(name)]) == {date(2026, 9, 12)}, name


def test_light_lower_body_isolation_is_still_a_leg_day():
    """The line sits below `isolation`, not below "light". An eccentric calf
    raise and a clamshell are small, but they are still work the tested tissue
    did yesterday — only release and mobility work is excluded."""
    for name in ("Standing Calf Raise (Eccentric Focus)", "Clamshell", "Glute Bridge"):
        assert fx.leg_loading_days([_leg_session(name)]) == {date(2026, 9, 12)}, name


def test_an_exercise_missing_from_the_weight_map_counts_as_loaded():
    """Fail-safe direction, the same one content_weighting.UNMAPPED_EXERCISE_
    WEIGHT takes for the ACWR chain. A new block adds names to both maps and
    the gap between those two edits must read as a dirty morning, never as a
    clean one — silently clearing a retest morning is the expensive error."""
    import training_constants as tc
    name = "Barbell Back Squat (unmapped, next block)"
    assert name not in tc.EXERCISE_MOVEMENT_WEIGHT
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(tc.EXERCISE_BODY_REGION, name, "lower_body")
        assert fx.leg_loading_days([_leg_session(name)]) == {date(2026, 9, 12)}


def test_end_range_hamstring_work_is_a_leg_day_however_cheap_its_strain_weight():
    """WHY THIS IS A NAME LIST AND NOT A CATEGORY. An earlier version excluded
    the whole `mobility_core` weight tier, which cleared these four — and
    `RDL Hip Hinge to Wall` is 3 x 15 on a 3-1-2 tempo whose own mechanics text
    reads "Feel the HAMSTRINGS load as the primary sensation". Slow eccentric
    work at long muscle length is the most reliable producer of next-day
    hamstring stiffness there is, and hamstring length is exactly what the
    straight-knee leverage rung and the seated tilt angle measure. The tier is
    right about STRAIN and says nothing about the tissue under test."""
    for name in ("Hip Hinge Full Range Assessment", "RDL Hip Hinge to Wall",
                 "Standing Hip Hinge (Wall Glute Touch)", "Wall-Supported Hip Hinge"):
        assert fx.leg_loading_days([_leg_session(name)]) == {date(2026, 9, 12)}, name


def test_the_reassessment_morning_is_guarded():
    """PLAN_STAGE2 day 28 IS the 2026-08-16 reassessment, and its only
    lower-body item is the full-range hip hinge. Under the category rule that
    day contained no leg-day exercise at all, so the morning after the block's
    own test session read as clean. Pinned against the real plan, not a
    fixture, so a plan edit that reintroduced the gap fails here."""
    import training_plan as tp
    from services.models import ExerciseEntry, SessionRecord
    for day in (14, 28):
        names = [e["name"] for e in tp.PLAN_STAGE2[day]["exercises"]]
        session = SessionRecord(session_date="2026-08-16",
                                session_duration_minutes=60.0, session_rpe=4.0,
                                session_au=240.0,
                                exercises=[ExerciseEntry(name=n, movement_type="Mobility")
                                           for n in names])
        assert fx.leg_loading_days([session]) == {date(2026, 8, 16)}, (
            f"PLAN_STAGE2 day {day} must count as a leg day; it contains {names}")


def test_every_lower_body_mobility_name_is_classified_explicitly():
    """The mobility tier is the ambiguous zone — it holds both a TFL pressure
    release and 45 reps of eccentric hamstring work. Each name is therefore
    classified by hand into exactly one of the two sets, and this test fails
    when a new block adds one nobody has judged. An unexplained absence must
    never be indistinguishable from an oversight (cluster_a_mechanics.REMOVED's
    rule). Until it is judged, an unlisted name counts as LOADED and warns —
    the safe direction, but a decision owed rather than a decision made."""
    import training_constants as tc
    tier = {n for n, r in tc.EXERCISE_BODY_REGION.items()
            if r == "lower_body"
            and (tc.EXERCISE_MOVEMENT_WEIGHT.get(n) or ("", 0))[0] == "mobility_core"}
    classified = fx.RELEASE_EXERCISES | fx.MOBILITY_TIER_LOADS_LEGS

    assert not (tier - classified), (
        f"unclassified lower-body mobility names: {sorted(tier - classified)} — "
        f"decide whether each leaves the tested tissue tighter, then add it to "
        f"RELEASE_EXERCISES or MOBILITY_TIER_LOADS_LEGS")
    assert not (classified - tier), (
        f"names classified but no longer in the map: {sorted(classified - tier)}")
    assert not (fx.RELEASE_EXERCISES & fx.MOBILITY_TIER_LOADS_LEGS), \
        "a name cannot both release and load"


def test_the_allow_list_fails_safe_for_anything_it_does_not_name():
    """The fail-safe lives in the STRUCTURE, not in a lookup that can fail open
    — which is how the category version let the hinge drills through. An
    unclassified lower-body name warns; only an explicitly named release clears
    the morning. A warning nobody needed costs a morning; a retest silently
    taken on worked tissue costs the reading and every comparison built on it.
    """
    import training_constants as tc
    name = "Nordic Hamstring Curl (unmapped, next block)"
    assert name not in fx.RELEASE_EXERCISES
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(tc.EXERCISE_BODY_REGION, name, "lower_body")
        assert fx.leg_loading_days([_leg_session(name)]) == {date(2026, 9, 12)}


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
    """Inside the relevance line it compares two of his own readings taken
    minutes apart, so it carries its own reference. Every other slot measures
    against a line we drew."""
    result = b.run("a", cb.SLOT_EVALUATORS, _assessment(list(_GATE0_BONY)))
    assert result.pattern == "B"
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


# ── the relevance line: when is bone even a live question? ───────────────────
#
# THE ATHLETE'S CALL (2026-08-07): the neck of the thigh bone meets the socket
# only in the last few centimetres of a FULL side split. At his current height,
# tissue stops him long before bone can — so asking the two-orientation
# comparison up there answers nothing, and the original version of gate 0 was
# wrong to ask it unconditionally.

def test_the_bone_check_is_skipped_above_the_relevance_line():
    """A 28 cm neutral reading passes slot 0 on its own: bone cannot be what
    stops him at that height, and the turned-out attempt is not asked for."""
    alone = _assessment([_gate0(28.0)])
    slot = cb.evaluate_structure(alone)
    assert slot.passed is True
    assert slot.indeterminate is False
    assert "cannot be what stops you" in slot.reason
    assert cb.applicable_tests(alone) == tuple(
        k for k in cb.AVAILABLE_TESTS if k != "gate0_turned_out")


def test_the_bone_check_is_required_inside_the_relevance_line():
    """Under the line the question is live, and a missing turned-out attempt is
    indeterminate — not a pass. And with no neutral reading yet, the session
    plans for both attempts rather than assuming."""
    inside = _assessment([_gate0(14.0)])
    slot = cb.evaluate_structure(inside)
    assert slot.passed is False and slot.indeterminate is True
    assert cb.applicable_tests(inside) == cb.AVAILABLE_TESTS
    assert cb.applicable_tests(None) == cb.AVAILABLE_TESTS


def test_progress_total_shrinks_when_the_bone_check_is_out_of_scope():
    """Counting the skipped comparison would show '8 of 9' forever on a
    finished session."""
    a = _assessment([_gate0(28.0)])
    done, total = fx.capture_progress(a)
    assert done == 1
    assert total == len(cb.AVAILABLE_TESTS) - 1


def test_the_skip_carries_its_reason_in_the_athletes_language():
    note = cb.SKIP_NOTES["gate0_turned_out"]
    assert "not yet a factor" in note
    assert "come back by itself" in note


# ── the tilt: an angle, own power first ──────────────────────────────────────

def test_the_tilt_runs_under_own_power_first():
    """The athlete's requirement (2026-08-07), and the same principle as slot
    3's order: help flatters whatever follows it, so the unassisted trial can
    never come after the assisted one."""
    assert cb.TEST_ORDER.index("tilt_production") < cb.TEST_ORDER.index("tilt_range")


def test_the_tilt_is_an_angle_and_bigger_is_better():
    """Forehead height is exactly the number a rounding spine can fake, and the
    rounding is his documented compensation — which is why the old protocol
    needed a second guard measurement and the angle needs none."""
    for key in ("tilt_production", "tilt_range"):
        test = cb.TESTS[key]
        assert test.unit == "°", key
        assert test.smaller_is_better is False, key
    a = _assessment(_GATE0_PASS + _LEVERAGE_PASS + [
        b.Reading("tilt_range", 8.0, "°"), b.Reading("tilt_production", 4.0, "°")])
    assert b.run("a", cb.SLOT_EVALUATORS, a).pattern == "F"


def test_an_old_centimetre_tilt_reading_is_unreadable_not_misread():
    """40 cm of forehead height is not 40 degrees of tilt. A reading from the
    retired protocol must come back indeterminate rather than be compared
    against the angle target — where it would score, loudly and wrongly."""
    a = _assessment(_GATE0_PASS + _LEVERAGE_PASS + [
        b.Reading("tilt_range", 40.0, "cm"), b.Reading("tilt_production", 55.0, "cm")])
    slot = b.run("a", cb.SLOT_EVALUATORS, a).slots[-1]
    assert slot.indeterminate is True
    assert "centimetres" in slot.reason


def test_the_tilt_captures_the_straddle_width_it_was_taken_at():
    """The width is the uniform base number: every tilt reading is relative to
    it, and a session at a different width is a different test."""
    assert "straddle width" in cb.TESTS["tilt_production"].setup_input.lower()
    assert "same straddle width" in cb.TESTS["tilt_range"].setup.lower()


def test_every_test_says_where_its_number_comes_from():
    """The input hint sits AT the field — 'floor to crotch, in cm' — so the
    athlete does not type a knee height into a crotch-height box."""
    for key, test in cb.TESTS.items():
        assert test.input_hint, key
        if test.unit == "cm":
            assert "cm" in test.input_hint, key
        if test.unit == "°":
            assert "degree" in test.input_hint.lower(), key


# ── the ladder ───────────────────────────────────────────────────────────────
#
# The battery's decision path made visual (athlete's ask, 2026-08-07): rungs
# bottom-up, tightest at the bottom, the working rung = the battery's first
# failure. THE GUARDS BELOW ARE WHAT KEEP IT FROM BECOMING v1/v2 AGAIN: no
# aggregate, no number for an unmeasured muscle, every fraction over a NAMED
# denominator, and the ladder never decides — it displays what run() decided.

_LADDER_KEYS = ("bone", "group_length", "gracilis", "tilt_range",
                "tilt_production", "end_range", "pullers")


def _ladder_for(readings):
    a = _assessment(readings)
    return cb.ladder(a, b.run("a", cb.SLOT_EVALUATORS, a))


def test_the_ladder_reads_bottom_up_and_marks_the_working_rung():
    """Pattern F: everything below the tilt is climbed, the helped tilt is the
    working rung, its own-power twin is context, and everything above is
    unmeasured."""
    rungs = _ladder_for(_GATE0_PASS + _LEVERAGE_PASS + [
        b.Reading("tilt_range", 8.0, "°"), b.Reading("tilt_production", 4.0, "°")])
    assert tuple(r.key for r in rungs) == _LADDER_KEYS
    by = {r.key: r for r in rungs}
    assert by["bone"].state == b.RUNG_PASSED
    assert by["group_length"].state == b.RUNG_PASSED
    assert by["gracilis"].state == b.RUNG_PASSED
    assert by["tilt_range"].state == b.RUNG_LIMITING
    assert by["tilt_range"].pattern == "F"
    assert by["tilt_range"].fraction == pytest.approx(0.4)     # 8° of 20°
    assert by["tilt_production"].state == b.RUNG_CONTEXT
    assert by["end_range"].state == b.RUNG_UNMEASURED
    assert by["pullers"].state == b.RUNG_UNMEASURED


def test_an_unmeasured_rung_has_no_number_ever():
    """None, never zero. Showing 0/100 for a muscle the battery never reached
    would read as 'terrible' when the truth is 'unknown' — the v1 failure with
    the sign flipped."""
    rungs = _ladder_for(_GATE0_PASS + _LEVERAGE_PASS + [
        b.Reading("tilt_range", 8.0, "°"), b.Reading("tilt_production", 4.0, "°")])
    for rung in rungs:
        if rung.state == b.RUNG_UNMEASURED:
            assert rung.fraction is None, rung.key
            assert rung.measured is None, rung.key


def test_keep_going_readings_surface_as_context_not_diagnosis():
    """The athlete's choice (2026-08-07): rungs above the failure fill in when
    he keeps going, labelled context — and the pattern must not move."""
    full = _GATE0_PASS + _LEVERAGE_PASS + [
        b.Reading("tilt_range", 8.0, "°"), b.Reading("tilt_production", 4.0, "°"),
        b.Reading("spectrum_active", 40.0, "°", side="left"),
        b.Reading("spectrum_active", 38.0, "°", side="right"),
        b.Reading("spectrum_isometric", 30.0, "cm"),
        b.Reading("spectrum_passive", 10.0, "cm")]
    a = _assessment(full)
    result = b.run("a", cb.SLOT_EVALUATORS, a)
    assert result.pattern == "F", "extra readings must never move the pattern"
    by = {r.key: r for r in cb.ladder(a, result)}
    assert by["end_range"].state == b.RUNG_CONTEXT
    assert by["end_range"].fraction == pytest.approx(10.0 / 30.0)
    assert by["pullers"].state == b.RUNG_CONTEXT
    assert by["pullers"].fraction == pytest.approx(78.0 / 180.0)


def test_two_muscles_can_share_the_bottom_of_the_ladder():
    """Pattern C fails both leverages, so both rungs read limiting — exactly
    the 'it could be two muscles at the same time' case."""
    by = {r.key: r for r in _ladder_for(_GATE0_PASS + [
        b.Reading("leverage_bent", 20.0, "cm"),
        b.Reading("leverage_straight", 40.0, "cm")])}
    assert by["group_length"].state == b.RUNG_LIMITING
    assert by["gracilis"].state == b.RUNG_LIMITING


def test_fractions_are_clamped_and_direction_aware():
    """A passed rung caps at 100% rather than reading 125%, and on a
    smaller-is-better scale a doubled reading halves the fraction."""
    assert b.fraction_of_target(8.0, 10.0, smaller_is_better=True) == 1.0
    assert b.fraction_of_target(20.0, 10.0, smaller_is_better=True) == 0.5
    assert b.fraction_of_target(8.0, 20.0) == pytest.approx(0.4)
    assert b.fraction_of_target(None, 20.0) is None
    assert b.fraction_of_target(8.0, None) is None


def test_the_ladder_names_its_denominators_honestly():
    """The invented targets stay flagged provisional; the two rungs whose
    denominators are the athlete's own reading (strength at depth) or the
    geometry of the skill (openers vs 180°) do not."""
    provisional = {i["key"]: i["provisional"] for i in cb.LADDER_INFO}
    assert provisional["group_length"] and provisional["gracilis"]
    assert provisional["tilt_range"] and provisional["tilt_production"]
    assert not provisional["end_range"]
    assert not provisional["pullers"]
    assert not provisional["bone"]


def test_the_ladder_produces_no_aggregate():
    """Rungs are never combined: no total, no average, no overall number. The
    battery's output stays one pattern label — the ladder only shows the path."""
    rungs = _ladder_for(_GATE0_PASS + _LEVERAGE_PASS + [
        b.Reading("tilt_range", 8.0, "°"), b.Reading("tilt_production", 4.0, "°")])
    assert isinstance(rungs, tuple)
    for banned in ("overall", "total_", "combined", "average"):
        assert not any(banned in dir(r) for r in rungs), banned
    source = _source(cb)
    assert "sum(r.fraction" not in source
    assert "mean(" not in source


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


# ── gate 0 measures a WIDTH and is judged as a HEIGHT ────────────────────────
#
# The athlete's call, 2026-08-12: finding the crotch by eye mid-split is not
# repeatable and it was asked for every session. The heels are unambiguous, so
# the reading became the width of the split. Every threshold stayed a height off
# the floor, because that is what the mechanism claim is about.

def test_the_width_and_the_height_are_the_same_split_from_two_ends():
    """The conversion is plain geometry — each leg is the hypotenuse from crotch
    to floor — so it must round-trip."""
    for gap in (60.0, 28.0, 15.0, 5.0):
        span = 2.0 * math.sqrt(_LEG_LENGTH ** 2 - gap ** 2)
        assert cb.floor_gap_from_span(span, _LEG_LENGTH) == pytest.approx(gap, abs=1e-6)
    # A full split is two legs laid end to end, and puts you on the floor.
    assert cb.floor_gap_from_span(2 * _LEG_LENGTH - 1e-9, _LEG_LENGTH) \
        == pytest.approx(0.0, abs=1e-3)


def test_a_width_with_no_leg_length_is_indeterminate_not_a_pass():
    """A width alone cannot say how high off the floor it puts you, and the
    thresholds are heights. A missing measurement is not evidence of health —
    the same rule the rest of the battery runs on."""
    orphan = _assessment([b.Reading("gate0_neutral", 162.6, "cm")])
    result = b.run("a", cb.SLOT_EVALUATORS, orphan)
    slot0 = result.slots[0]
    assert slot0.indeterminate and not slot0.passed
    assert "leg length" in slot0.reason.lower()
    assert cb.floor_gap_from_span(162.6, None) is None


def test_a_width_wider_than_two_legs_is_refused_rather_than_squared():
    """sqrt of a negative is the crash; returning a number anyway is worse. A
    split cannot be wider than the two legs making it, so this is a mismeasure
    or a wrong leg length, and either way it is not a reading."""
    assert cb.floor_gap_from_span(2 * _LEG_LENGTH + 5.0, _LEG_LENGTH) is None
    assert cb.floor_gap_from_span(0.0, _LEG_LENGTH) is None


def test_the_orientation_gain_is_compared_as_heights_not_as_widths():
    """WHY THE CONVERSION EARNS ITS KEEP. The same 10 cm of depth is about 5.9 cm
    of width at 30 cm off the floor and 2.3 cm at 15 cm, so a width threshold
    would mean something different at every depth. Two pairs with a near-equal
    WIDTH difference must therefore land on opposite verdicts."""
    deep = _assessment([_gate0(14.0), _gate0(3.0, "gate0_turned_out")])
    assert b.run("a", cb.SLOT_EVALUATORS, deep).pattern == "B"

    # Same widths, ~2.4 cm apart, but taken high up where that is a small gain.
    shallow_n, shallow_t = _gate0(45.0), _gate0(43.0, "gate0_turned_out")
    width_gain = shallow_t.value - shallow_n.value
    assert width_gain < cb.GATE0_ORIENTATION_GAIN_CM, "the point is a SMALL width step"
    gap_gain = (cb.floor_gap_from_span(shallow_n.value, _LEG_LENGTH)
                - cb.floor_gap_from_span(shallow_t.value, _LEG_LENGTH))
    assert gap_gain == pytest.approx(2.0, abs=0.2)


def test_at_the_athletes_real_depth_the_turned_out_step_is_skipped():
    """He reported "over 60cm in the air" on 2026-08-12 and calls a full split
    "2 years or more" away, so the bony question is not live and slot 0 passes
    on the neutral width alone — which is the whole reason the conversion's
    imprecision near the floor does not bite yet."""
    his = _assessment([_gate0(60.0)])
    assert "gate0_turned_out" not in cb.applicable_tests(his)
    slot0 = b.run("a", cb.SLOT_EVALUATORS, his).slots[0]
    assert slot0.passed and not slot0.indeterminate
    assert "off the floor" in slot0.reason
