"""
front_split_battery.py — the front split's test: five readings, two slots.

The athlete, 2026-11-11, choosing the start reading: "one cold test morning at
home, about 10 minutes: the split height on each side and two leg checks on
each side", so the stack works the weaker part first. It is the exception to
his rule of 2026-11-08 ("I dont want another test until im finished the 12
week block"), and it was his choice. The retest is twelve weeks after it
(front_split_prescription.RETEST_INTERVAL_DAYS), after the block ends.

NAMES NO EXERCISE AND CARRIES NO DOSE: the how-to-test layer, the general
method in services/battery.py. tests/test_front_split.py checks both.

THE FIVE TESTS, IN THE ORDER THEY ARE TAKEN
-------------------------------------------
    slr_active     straight-leg raise under its own power     (the range he can use)
    slr_passive    straight-leg raise pulled with a towel     (front leg: hamstrings)
    hanging_thigh  thigh angle, leg hanging off a bed         (back leg: deep hip flexors)
    hanging_shin   shin angle in the same position            (back leg: front of the thigh)
    split_span     the front split, front heel to back toes   (the skill: the goal's proof)

Active before passive, the split last: help and stretching leave the tissue
looser and flatter whatever is measured after them (flexibility_baselines.
MEASURE_ORDER). Every test is taken on both sides, and the worse side decides;
sides are never averaged.

TWO SLOTS, STOPPING AT THE FIRST FAILURE (services/battery.run)
--------------------------------------------------------------
  Slot 1, REGRESSED: which tissue is short at low demand. Front leg against
  back leg, and for the back leg the deep group against the two-joint muscle
  (the knee bend is the one thing true of that muscle alone).
      both legs short           -> B
      front leg only            -> H
      back leg, deep group      -> P   (the shin cannot be read while the thigh is up)
      back leg, front of thigh  -> R
  Slot 3, SPECTRUM: the lengths are adequate; can he use them? The towel raise
  against the raise under his own power.
      big gap                   -> A   (range he cannot control yet)
      small gap                 -> S   (the split itself is what to train)

There is no structure slot and no prerequisite slot. A bony block in a front
split is not on his record and nothing in it calls for a gate; the technique
rung (square hips) is coached in every stack rather than tested, because the
blueprint gives it as a rule, not a measurement.

EVERY CUT POINT IS PROVISIONAL (services/battery.BASIS_PROVISIONAL), and only
the split's own fraction has a sound denominator: two straight legs reach the
floor when the span is twice the leg length.

THE NERVE IS A DIFFERENTIATOR, NOT A PATTERN. Pulling the toes up at the end of
the towel raise changes the nerve's tension and not the hamstrings' length. A
change there is a finding to stop and record, as in Cluster A's NERVE_CHECK,
and no stack trains it: rules.py's 'nerve glide' rule forbids nerve work added
on speculation for a symptom no log has recorded.
"""

from __future__ import annotations

from dataclasses import dataclass

from cluster_a_battery import BatteryTest
from services import battery as _b

CLUSTER_KEY = "front_split"

# ── pattern labels ───────────────────────────────────────────────────────────

PATTERNS: dict[str, str] = {
    "B": "Both legs short",
    "H": "Front leg — hamstrings",
    "P": "Back leg — deep hip flexors",
    "R": "Back leg — front of the thigh",
    "A": "Range you cannot control yet",
    "S": "The split itself",
}

#: Written down BEFORE measuring, so a borderline reading cannot be read toward
#: it (Cluster A's own rule). Hamstrings at normal length with no reserve
#: (89/86°, January 2025) and the sit-bone tightness of 2026-10-05 point at the
#: front leg; the Thomas test of the same day read the hip flexors normal.
EXPECTED_PATTERN: str = "H"
EXPECTED_PATTERN_BASIS: str = (
    "The hamstrings read normal length with no reserve on the January 2025 goniometry "
    "(89° left, 86° right), and the sit-bone tightness of 2026-10-05 reads as the "
    "hamstring origin working short on both sides. The Thomas test the same day read the "
    "hip flexors normal and equal, though warm. So the front leg is expected to fail "
    "slot 1 alone. A back-leg pattern would say the warm reading flattered him."
)


# ── tests ────────────────────────────────────────────────────────────────────

_PHONE = ("Put your phone on the front of the shin, just below the knee, with the level "
          "in your phone's measure app open: it reads 0 with the leg flat on the floor.")

TESTS: dict[str, BatteryTest] = {
    "slr_active": BatteryTest(
        key="slr_active", slot=_b.SLOT_SPECTRUM,
        label="Straight-leg raise, own power", unit="°", bilateral=True,
        setup="Lie on your back on a mat, both legs straight. " + _PHONE,
        lock="The other leg stays straight and pressed into the mat, and your lower back "
             "stays down. **The tell: the back of the other knee leaves the mat, or the "
             "lifted knee bends.**",
        measurement="Tighten the front of the thigh, kneecap and toes pointing straight "
                    "up. Lift the straight leg as high as it goes under its own power and "
                    "hold the top for 2 seconds. Read the angle on the phone at the top. "
                    "Left and right separately, to the nearest degree. **Take this test "
                    "first**: the towel and the split stretch the leg and would flatter it.",
        input_hint="The angle on the phone at the top of the lift, in degrees — left and "
                   "right separately",
        what_youre_testing="How high your hip muscles can lift a straight leg against the "
                           "pull of the hamstrings: the range you can USE. The towel raise "
                           "next reads the range you can reach with help, and the gap "
                           "between them says which end of the work you need.",
        safety="A click or a snap at the front of the right hip: lower the leg and write it "
               "down. Keep the kneecap pointing straight up, not turned out.",
    ),
    "slr_passive": BatteryTest(
        key="slr_passive", slot=_b.SLOT_REGRESSED,
        label="Straight-leg raise, with a towel", unit="°", bilateral=True,
        setup="The same position: on your back, both legs straight, the phone on the shin. "
              "Loop a towel round the ball of the foot of the leg you test and hold an end "
              "in each hand.",
        lock="The other leg stays straight and pressed into the mat, the lifted knee stays "
             "straight, and the leg itself relaxes: the towel does the lifting. **The tell: "
             "the back of the other knee leaves the mat.**",
        measurement="Pull the straight leg up with the towel, slowly, until you feel a firm "
                    "stretch, not pain, or the other leg starts to lift. Hold 2 seconds and "
                    "read the angle. Then, still there, pull your toes toward your shin: if "
                    "the stretch spreads into the calf or the foot, or anything tingles, "
                    "stop the test and write it down. Left and right separately.",
        input_hint="The angle on the phone at the firm stretch, in degrees — left and "
                   "right separately",
        what_youre_testing="The length of the hamstrings, the front leg of your split. A "
                           "straight knee loads them and the towel takes away the strength "
                           "question, so this reads length alone. Pulling the toes up "
                           "stretches the big nerve at the back of the leg without "
                           "lengthening the hamstrings, so a change at that moment is the "
                           "nerve, not the muscle.",
        safety="An electric or burning feeling down the leg: stop, record where it was, and "
               "do not stretch into it.",
    ),
    "hanging_thigh": BatteryTest(
        key="hanging_thigh", slot=_b.SLOT_REGRESSED,
        label="Hanging leg, thigh angle", unit="°", bilateral=True,
        setup="Sit on the very end of a firm bed or bench. Lie back and hug one knee to "
              "your chest with both hands until your lower back is flat on the bed. Let the "
              "other leg hang off the end, relaxed, knee bent. Put the phone flat on the "
              "front of the hanging thigh, halfway between the hip and the knee.",
        lock="The hugged knee stays at your chest and your lower back stays flat on the "
             "bed. **The tell: your lower back lifts off the bed, or you hold the hanging "
             "leg up instead of letting it hang.**",
        measurement="Let the hanging leg relax completely for 10 seconds, then read the "
                    "angle on the phone. Type it as degrees BELOW the line of the bed: a "
                    "thigh that hangs below the edge is a plus number, a thigh that stays "
                    "above the line is a minus number. The side is the leg that hangs; "
                    "left and right separately.",
        input_hint="Degrees the hanging thigh sits below the line of the bed (above the "
                   "line is a minus number) — left and right separately",
        what_youre_testing="The deep hip flexors, the back leg of your split: the muscles "
                           "that cross only the hip. With the knee bent the front-of-thigh "
                           "muscle is slack, so this reads the deep group alone. Your check "
                           "on 5 October read them normal and equal, warm; this reads them "
                           "cold.",
        safety="A painless click in the right hip as the leg goes down is the click you "
               "already know at about 45 degrees: let the leg settle and read it. A pinch or "
               "pain at the front of the hip ends the test on that side; write it down.",
    ),
    "hanging_shin": BatteryTest(
        key="hanging_shin", slot=_b.SLOT_REGRESSED,
        label="Hanging leg, shin angle", unit="°", bilateral=True,
        smaller_is_better=True,
        setup="The same position as the thigh test: one knee hugged to your chest, the "
              "other leg hanging off the end of the bed. Move the phone to the front of the "
              "hanging shin, just below the knee, held upright against it.",
        lock="The hugged knee stays at your chest, your lower back stays flat on the bed, "
             "and the hanging leg stays relaxed. **The tell: the foot swings because you "
             "moved it.**",
        measurement="Let the leg hang relaxed for 10 seconds, then read the shin's angle "
                    "from straight down: a shin that hangs straight down reads 0, and the "
                    "number grows as the foot swings forward. Left and right separately.",
        input_hint="The shin's angle forward of straight down, in degrees — left and right "
                   "separately",
        what_youre_testing="The front-of-thigh muscle of the back leg of your split. It "
                           "crosses both the hip and the knee, so when it is short it pulls "
                           "the knee straighter and the foot swings forward. The thigh "
                           "reading names the deep group; this one names this muscle, and "
                           "it can only be read when the thigh hangs down.",
    ),
    "split_span": BatteryTest(
        key="split_span", slot=_b.SLOT_SPECTRUM,
        label="Front split, heel to toes", unit="cm", bilateral=True,
        setup="Lay a tape measure on the floor along the line of the split. Hands on two "
              "blocks or two stacks of books, one each side of your hips. Front leg straight "
              "with the heel on the tape and the toes up; back leg straight behind you with "
              "the toes tucked under, on the tape.",
        lock="Both hip points face straight ahead, the back kneecap faces the floor, and "
             "your lower back does not arch. **The tell: the back foot rolls onto its side, "
             "or the back hip swings open.**",
        measurement="Slide your legs apart slowly until a firm stretch, not pain, and hold "
                    "5 seconds. Read the tape at the back of the front heel and at the tip "
                    "of the back toes, and type the distance between them. The side is the "
                    "leg in front. **Take this test last**: it stretches the most, and it "
                    "would flatter any test after it.",
        input_hint="The distance from the back of the front heel to the tip of the back "
                   "toes, in cm — left leg in front, then right",
        setup_input="Your leg length: standing, the floor to the top of the inside of your "
                    "thigh (cm)",
        what_youre_testing="The split itself, the number the goal is proved on. Two straight "
                           "legs of your length reach the floor when the gap is twice your "
                           "leg length, so the gap against twice your leg length is how far "
                           "along you are to a full split.",
        safety="A sharp pinch at the front of either hip, or tingling down a leg: come up "
               "and write it down.",
    ),
}

TEST_ORDER: tuple[str, ...] = (
    "slr_active", "slr_passive", "hanging_thigh", "hanging_shin", "split_span",
)

AVAILABLE_TESTS: tuple[str, ...] = tuple(k for k in TEST_ORDER if TESTS[k].available)
DEFERRED_TESTS: tuple[str, ...] = tuple(k for k, t in TESTS.items() if not t.available)


def applicable_tests(assessment=None) -> tuple[str, ...]:
    """Every test, every session: no reading puts another out of scope."""
    return AVAILABLE_TESTS


#: Which tests each slot needs before it can answer. The split is the goal's
#: proof and decides no pattern, so no slot waits on it.
SLOT_TESTS: dict[int, tuple[str, ...]] = {
    _b.SLOT_REGRESSED: ("slr_passive", "hanging_thigh", "hanging_shin"),
    _b.SLOT_SPECTRUM: ("slr_active", "slr_passive"),
}

SKIP_NOTES: dict[str, str] = {}


@dataclass(frozen=True)
class MissingInput:
    """One reading the battery is waiting on before it can answer."""
    test_key: str
    side: str = ""
    setup: bool = False

    @property
    def label(self) -> str:
        test = TESTS[self.test_key]
        if self.setup:
            return test.setup_input
        return f"{test.label} — {self.side}" if self.side else test.label

    @property
    def hint(self) -> str:
        test = TESTS[self.test_key]
        return test.setup_input if self.setup else test.input_hint


def missing_inputs(assessment, result) -> tuple[MissingInput, ...]:
    """The readings an indeterminate slot is waiting on; () when a pattern was
    reached or a slot failed (a failure is an answer)."""
    if assessment is None or result is None or result.pattern:
        return ()
    stopped = next((s for s in result.slots if s.indeterminate), None)
    if stopped is None:
        return ()
    return tuple(MissingInput(key, side)
                 for key in SLOT_TESTS.get(stopped.slot, ())
                 for side in ("left", "right")
                 if assessment.reading(key, side) is None)


# ── what is recorded alongside, never scored ─────────────────────────────────

NERVE_CHECK: str = (
    "**A differentiator, not a provocation.** At the end of the towel raise, pull your "
    "toes toward your shin. The hamstrings' length does not change, and the nerve's "
    "tension does, so a stretch that spreads into the calf or the foot at that moment is "
    "the nerve. **Stop at the first change in the quality of the feeling.** An electric or "
    "burning sensation is a finding: stop, record where it was, and do not train into it. "
    "Your right nerve exit at the base of the back is narrowed, and no log has ever "
    "recorded a sign from it."
)

#: The capture screen's second note (Cluster A's is about the inside of the knee).
FRONT_HIP_NOTE: str = (
    "Record any sharp pinch at the front of a hip. **It is a finding, not a training "
    "sensation.** A stretch feels long and spreads; a pinch is sharp and sits in one spot, "
    "and it means the joint, not the muscle, is at its end."
)

#: Numbers taken once and kept the same every session, so two sessions compare.
FROZEN_CONSTANTS: tuple[tuple[str, str], ...] = (
    ("leg_length_cm",
     "Standing, the floor to the top of the inside of your thigh. It turns the split's "
     "heel-to-toe distance into how far along you are, and it does not change: measure it "
     "once and type the same number every session."),
    ("blocks",
     "The same two blocks or stacks of books under your hands every session. Higher "
     "supports let you sit higher, so a change of support changes the split's number "
     "without the legs being any longer."),
)

PROGRESSION_VARIABLE: tuple[str, str] = (
    "split_span_cm",
    "The distance from the back of the front heel to the tip of the back toes, hips "
    "square. It grows toward twice your leg length, where two straight legs reach the "
    "floor. Lower blocks in training are the way there; the test keeps its blocks the same.",
)


def test_for(key: str) -> BatteryTest | None:
    return TESTS.get(key)


# ── cut points, all PROVISIONAL until three baseline mornings exist ─────────

#: A straight leg raised to vertical: the front leg of a split needs at least
#: that much hip bend with the knee straight.
FRONT_LEG_TARGET_DEG: float = 90.0
#: The hanging thigh level with the bed: the usual reading of this test's
#: normal. Below the line is plus.
THIGH_TARGET_DEG: float = 0.0
#: The hanging shin within this many degrees of straight down: the knee bent to
#: about a right angle with the thigh level.
SHIN_TARGET_DEG: float = 10.0
#: The towel raise minus the raise under his own power, worse side, before the
#: gap rather than the split itself is called the limiter.
SPECTRUM_GAP_DEG: float = 15.0


def _values(assessment, key) -> dict[str, float]:
    return {r.side: r.value for r in assessment.readings_for(key)}


def _lowest(assessment, key) -> float | None:
    v = _values(assessment, key)
    return min(v.values()) if len(v) == 2 else None


def _highest(assessment, key) -> float | None:
    v = _values(assessment, key)
    return max(v.values()) if len(v) == 2 else None


def evaluate_regressed(assessment):
    front = _lowest(assessment, "slr_passive")
    thigh = _lowest(assessment, "hanging_thigh")
    shin = _highest(assessment, "hanging_shin")
    if front is None or thigh is None or shin is None:
        return _b.SlotResult(slot=_b.SLOT_REGRESSED, passed=False, indeterminate=True,
                             reason="The towel raise and both hanging-leg readings are "
                                    "needed on both sides: front leg against back leg is "
                                    "what names the part that is short.")
    front_short = front < FRONT_LEG_TARGET_DEG
    deep_short = thigh < THIGH_TARGET_DEG
    # The shin can only name the front of the thigh while the thigh hangs down:
    # with the thigh held up by the deep group, the knee angle reads that group.
    thigh_short = not deep_short and shin > SHIN_TARGET_DEG
    back_short = deep_short or thigh_short
    if front_short and back_short:
        return _b.SlotResult(slot=_b.SLOT_REGRESSED, passed=False, pattern="B",
                             reason="Both legs are short at low demand: the hamstrings of "
                                    "the front leg and the hip flexors of the back leg.")
    if front_short:
        return _b.SlotResult(slot=_b.SLOT_REGRESSED, passed=False, pattern="H",
                             reason=f"The towel raise reaches {front:.0f}° on the worse "
                                    f"side, short of the {FRONT_LEG_TARGET_DEG:.0f}° a front "
                                    f"leg needs; the back leg is fine. The hamstrings.")
    if deep_short:
        return _b.SlotResult(slot=_b.SLOT_REGRESSED, passed=False, pattern="P",
                             reason="The hanging thigh stays above the line of the bed: the "
                                    "deep hip flexors of the back leg.")
    if thigh_short:
        return _b.SlotResult(slot=_b.SLOT_REGRESSED, passed=False, pattern="R",
                             reason="The thigh hangs down but the shin swings forward: the "
                                    "front-of-thigh muscle of the back leg.")
    return _b.SlotResult(slot=_b.SLOT_REGRESSED, passed=True,
                         reason="Both legs are long enough at low demand.")


def control_gap(assessment) -> float | None:
    """The towel raise minus the raise under his own power, on the side where
    the gap is larger; None until both are in on both sides."""
    active, passive = _values(assessment, "slr_active"), _values(assessment, "slr_passive")
    if len(active) < 2 or len(passive) < 2:
        return None
    return max(passive[s] - active[s] for s in ("left", "right"))


def evaluate_spectrum(assessment):
    gap = control_gap(assessment)
    if gap is None:
        return _b.SlotResult(slot=_b.SLOT_SPECTRUM, passed=False, indeterminate=True,
                             reason="Both straight-leg raises are needed on both sides; "
                                    "the spectrum is a comparison, not one number.")
    if gap >= SPECTRUM_GAP_DEG:
        return _b.SlotResult(slot=_b.SLOT_SPECTRUM, passed=False, pattern="A",
                             reason=f"The towel takes the leg {gap:.0f}° higher than you "
                                    f"can lift it. The range is there and you cannot "
                                    f"control it yet: strength at length.")
    return _b.SlotResult(slot=_b.SLOT_SPECTRUM, passed=False, pattern="S",
                         reason="The legs are long enough and you control the range: the "
                                "split itself is what to train.")


#: Passed to services.battery.run, in order. The list IS the method.
SLOT_EVALUATORS = [
    evaluate_regressed,
    evaluate_spectrum,
]


# ── the ladder ───────────────────────────────────────────────────────────────

LADDER_INFO: tuple[dict, ...] = (
    {"key": "front_leg", "label": "Front leg — straight knee",
     "muscle": "hamstrings", "unit": "°", "provisional": True},
    {"key": "deep_hip_flexors", "label": "Back leg — thigh hanging",
     "muscle": "deep hip flexors", "unit": "°", "provisional": True},
    {"key": "front_thigh", "label": "Back leg — shin hanging",
     "muscle": "the front of the thigh", "unit": "°", "provisional": True},
    {"key": "control", "label": "Own power against the towel",
     "muscle": "strength at length", "unit": "°", "provisional": False},
    {"key": "split", "label": "The front split",
     "muscle": "the whole split", "unit": "cm", "provisional": False},
)

#: Which pattern makes which rung the one to work.
_LIMITING_RUNG: dict[str, tuple[str, ...]] = {
    "B": ("front_leg", "deep_hip_flexors"), "H": ("front_leg",),
    "P": ("deep_hip_flexors",), "R": ("front_thigh",), "A": ("control",), "S": ("split",),
}


def leg_length(assessment):
    """The leg length typed on the split's reading (its setup number)."""
    if assessment is None:
        return None
    return next((r.setup_value for r in assessment.readings_for("split_span")
                 if r.setup_value), None)


def ladder(assessment, result) -> tuple:
    """The decision path as rungs, bottom-up. The state comes from the battery's
    result; the ladder never decides anything. A rung with no reading has no
    number."""
    thigh_low = _lowest(assessment, "hanging_thigh")
    deep_short = thigh_low is not None and thigh_low < THIGH_TARGET_DEG
    limiting = set(_LIMITING_RUNG.get(result.pattern or "", ()))
    if result.pattern == "B" and not deep_short:
        # Both legs, and the back leg failed on the shin: name that rung.
        limiting = {"front_leg", "front_thigh"}
    #: Slots that reached an answer. An indeterminate slot judged nothing, so a
    #: reading in it is context, never a pass.
    judged = {s.slot for s in result.slots if not s.indeterminate}
    length = leg_length(assessment)
    span = _lowest(assessment, "split_span")
    gap = control_gap(assessment)
    active = _values(assessment, "slr_active")
    passive = _values(assessment, "slr_passive")
    own_share = (min(active[s] / passive[s] for s in ("left", "right") if passive[s] > 0)
                 if len(active) == 2 and len(passive) == 2 and all(passive.values())
                 else None)
    readings = {
        "front_leg": (_lowest(assessment, "slr_passive"), FRONT_LEG_TARGET_DEG,
                      _b.fraction_of_target(_lowest(assessment, "slr_passive"),
                                            FRONT_LEG_TARGET_DEG), _b.SLOT_REGRESSED,
                      "Towel raise, worse side, against a straight leg raised to "
                      "vertical."),
        "deep_hip_flexors": (_lowest(assessment, "hanging_thigh"), THIGH_TARGET_DEG, None,
                             _b.SLOT_REGRESSED,
                             "Worse side; the line of the bed is the target, below it "
                             "is plus."),
        "front_thigh": (_highest(assessment, "hanging_shin"), SHIN_TARGET_DEG, None,
                        _b.SLOT_REGRESSED,
                        "Worse side; straight down is 0."),
        "control": (gap, SPECTRUM_GAP_DEG,
                    max(0.0, min(1.0, own_share)) if own_share is not None else None,
                    _b.SLOT_SPECTRUM,
                    "The lift under your own power over the towel raise, worse side: "
                    "your own reading is the yardstick."),
        "split": (span, 2 * length if length else None,
                  _b.fraction_of_target(span, 2 * length) if length else None, None,
                  "Heel to toes, worse side, against twice your leg length: a full "
                  "split."),
    }
    rungs = []
    for info in LADDER_INFO:
        key = info["key"]
        measured, target, fraction, slot, detail = readings[key]
        if measured is None:
            state = _b.RUNG_UNMEASURED
        elif key in limiting:
            state = _b.RUNG_LIMITING
        elif key == "front_thigh" and deep_short:
            # The shin cannot name the front of the thigh while the deep group
            # holds the thigh up.
            state = _b.RUNG_CONTEXT
            detail = "Not readable while the thigh is held up; read it again later."
        elif slot is not None and slot in judged:
            state = _b.RUNG_PASSED
        else:
            state = _b.RUNG_CONTEXT
        rungs.append(_b.LadderRung(
            key=key, label=info["label"], muscle=info["muscle"], state=state,
            unit=info["unit"], measured=measured, target=target,
            fraction=fraction if measured is not None else None, detail=detail,
            pattern=result.pattern if key in limiting else "",
            provisional=info["provisional"]))
    return tuple(rungs)
