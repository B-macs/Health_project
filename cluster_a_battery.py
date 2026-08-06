"""
cluster_a_battery.py — Cluster A's four slots. Side split and pancake.

The machine-readable form of `Input_files/assessment_battery.md` Part 2, adapted
for this athlete on 2026-08-06. Part 1 of that document — the general method —
is `services/battery.py` and is unchanged; nothing in this athlete's file bears
on it.

NAMES NO EXERCISE. This is the HOW-TO-TEST layer. It says what to measure and
what the answer means; it never says what to train. A test fails if any exercise
name from cluster_a_mechanics.LIBRARY appears in this file's source.

PLAIN ENGLISH IS A REQUIREMENT, NOT A NICETY
--------------------------------------------
`setup`, `lock` and `measurement` are read by the athlete while he is on the
floor holding a tape measure. A test he misunderstands does not produce an
obviously wrong number — it produces a plausible one, and nothing downstream can
tell the difference. Anatomical vocabulary belongs in `what_youre_testing`;
nothing about this codebase belongs in any of them. tests/test_cluster_a.py
scans for both.

THE ADAPTATIONS, each with what reverts it
------------------------------------------
  B1  Gate 0 turns the legs out instead of arching the back. The Mechanics
      document calls the two routes equivalent, and only one collides with an
      L5/S1 retrolisthesis. Reverts: never — it is an equal option.
  B2  The 90° leverage is HELD until the right hip has been observed under the
      loaded squat work already in the block. It is an externally-rotated loaded
      squat and the right hip has an open snapping question; adding a second
      new one now would make it impossible to tell which produced a change.
      A measurement argument, not a permission one. Reverts: once the current
      block's squat work has run clean.
  B3  Test 2 is KEPT AS WRITTEN on the athlete's call, with his reason recorded
      as a falsifiable prediction and a stop rule added.
  B4  The nerve check is a differentiator, not a provocation. An electric or
      burning sensation is a FINDING — stop, record, and do not train through
      it. That is a different category of event, not a permission gate.
  B5  Every threshold is provisional until three baseline mornings exist, and
      they are OURS to set from his own readings rather than borrowed.
"""

from __future__ import annotations

from dataclasses import dataclass

import flexibility_baselines as _fb
from services import battery as _b

CLUSTER_KEY = "a"

# ── pattern labels ───────────────────────────────────────────────────────────

PATTERNS: dict[str, str] = {
    "A": "Bone",
    "B": "Orientation",
    "C": "Whole adductor group",
    "D": "Short adductors and rotators",
    "E": "Gracilis",
    "F": "Tilt range",
    "G": "Tilt production — hip flexor strength",
    "H": "Adductor end-range strength",
    "I": "Puller strength — hip abductors",
}

#: Written down BEFORE measuring, so a borderline reading cannot be quietly read
#: toward the answer already in mind. His 2026-08-05 straddle report — "hips
#: stuck in flexion with tail bone down, back fully rounds" — is a slot 2
#: failure, so F or G, most likely F. If the battery lands somewhere else, that
#: is a finding about the model rather than a surprise to explain away.
EXPECTED_PATTERN: str = "F"
EXPECTED_PATTERN_BASIS: str = (
    "Seated anterior pelvic tilt is the dominant restriction on record, reported "
    "independently in four seated positions on 2026-08-05. That is a slot 2 failure, "
    "which yields F or G. Note this DISAGREES with the generic lax-tissue prediction "
    "of H or I — he has a specific range deficit inside an otherwise hypermobile body, "
    "and the disagreement is worth watching rather than resolving in advance."
)


# ── tests ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BatteryTest:
    """One measurement within a slot."""
    key: str
    slot: int
    label: str
    unit: str
    setup: str
    lock: str
    measurement: str
    what_youre_testing: str
    bilateral: bool = False
    smaller_is_better: bool = False
    safety: str = ""
    #: A second number this test needs beside the measurement — the setup it was
    #: taken at. Empty for tests that have none. See Reading.setup_value.
    setup_input: str = ""
    deferred_until: str = ""
    adapted_from: str = ""

    @property
    def available(self) -> bool:
        return not self.deferred_until


TESTS: dict[str, BatteryTest] = {

    # ── Slot 0 — Structure ──────────────────────────────────────────────────
    "gate0_neutral": BatteryTest(
        key="gate0_neutral", slot=_b.SLOT_STRUCTURE,
        label="Side split, legs neutral", unit="cm", smaller_is_better=True,
        setup="Slide into a side split with your legs in a **neutral rotation** — kneecaps "
              "pointing forward, not turned up. Go to where it stops, not past it. Hands on "
              "blocks in front of you so your chest stays up.",
        lock="Your pelvis and lower back must be **identical between this attempt and the "
             "next one**. The whole reading is the difference the leg rotation makes, so "
             "anything else that moves contaminates it. **The tell: if your back position "
             "changes between the two attempts, the trial is void** — reset and take both "
             "again.",
        measurement="Measure the gap from the floor up to your crotch. Smaller is deeper. "
                    "To the nearest half centimetre.",
        what_youre_testing="Whether the thing stopping you is the shape of your hip joint "
                           "rather than tissue length. The neck of the thigh bone eventually "
                           "meets the rim of the socket, and where that happens varies a lot "
                           "between healthy people. Bone does not stretch, so if this is your "
                           "limit the answer is alignment rather than more stretching.",
        safety="**A sharp pinch at the front of the hip with a sudden hard stop is a "
               "finding, not a result — stop and record it.** It is not a pattern to train "
               "against and it is not a number. The same sensation was reported in a deep "
               "butterfly on 2026-08-05 and has never been explained; if it appears again, "
               "note what position produced it and go no further into that position today. "
               "Repeated collision with a bony end causes joint irritation, and it is the "
               "reason people stall permanently rather than slowly.",
    ),
    "gate0_turned_out": BatteryTest(
        key="gate0_turned_out", slot=_b.SLOT_STRUCTURE,
        label="Side split, legs turned out", unit="cm", smaller_is_better=True,
        setup="The same position, but now **turn both legs out from the hips** — let the "
              "kneecaps rotate toward the ceiling. Keep your back exactly as it was in the "
              "first attempt.",
        lock="As above: pelvis and lower back unchanged between the two. **The tell is the "
             "same** — if your back moves, the comparison is void.",
        measurement="Same measurement: floor to crotch, to the nearest half centimetre. "
                    "**The reading is the difference between the two attempts.**",
        what_youre_testing="The same question, asked with the joint aligned differently. "
                           "There are two ways to give the hip more room — turn the leg out, "
                           "or tilt the pelvis — and they reach the same place. This uses the "
                           "turn-out because tilting means arching your lower back under your "
                           "full bodyweight, which your imaging rules out. A large jump "
                           "between the two attempts means alignment was the limit, not "
                           "tissue.",
        adapted_from="the original asked for a deliberate anterior pelvic tilt with the "
                     "back arched",
    ),

    # ── Slot 1 — Regressed, at multiple leverages ───────────────────────────
    "leverage_bent": BatteryTest(
        key="leverage_bent", slot=_b.SLOT_REGRESSED,
        label="Knees fully bent", unit="cm", smaller_is_better=True, bilateral=True,
        setup="Sit with your back flat against a wall, soles of your feet together, heels "
              "pulled in to **your recorded heel distance**. Press your knees down toward "
              "the floor **without using your hands**.",
        lock="Your back stays flat on the wall, and your heels stay at the recorded "
             "distance. **The tell for the heels is a number, not a chalk mark** — measure "
             "from your tailbone to the back of your heels and match the figure. Heels "
             "further out drop the knees without your groin being one millimetre longer, so "
             "a session that re-places them by eye is void against the last one.",
        measurement="Measure from the floor up to **the outside of each calf**. Smaller is "
                    "better. Left and right separately, to the nearest half centimetre. "
                    "**Also record the heel distance you actually used** — it decides what "
                    "this reading means.",
        setup_input="Tailbone to the back of your heels (cm)",
        what_youre_testing="Your groin muscles with the knee fully bent. Bending the knee "
                           "slackens gracilis — the one groin muscle that crosses the knee — "
                           "so this loads everything except it. Comparing this against the "
                           "straight-knee test is what names which part of the group is "
                           "short. **That comparison is why the heel distance matters more "
                           "here than anywhere else**: heels pulled closer than your "
                           "reference drop the knees further, so this test passes too "
                           "easily, and a whole-group restriction comes out looking like a "
                           "gracilis one.",
    ),
    "leverage_90": BatteryTest(
        key="leverage_90", slot=_b.SLOT_REGRESSED,
        label="Knees at 90 degrees", unit="cm", smaller_is_better=True,
        setup="Feet wide, toes slightly out, knees bent to a right angle. Sink and hold for "
              "five seconds, then measure.",
        lock="Your knees track out over your feet, and your back stays upright rather than "
             "leaning forward. **The tell: if a knee drifts inward toward the other, or your "
             "chest drops toward the floor, the trial is void** — you have found the depth "
             "with your knee and your back rather than your hips.",
        measurement="Measure from the floor up to your hip crease. Smaller is deeper. To the "
                    "nearest half centimetre.",
        what_youre_testing="The middle leverage — the same muscle group loaded at a knee "
                           "angle between the other two tests.",
        deferred_until="the block's own loaded squat work has run clean",
        safety="**Held for now, and the reason is measurement rather than caution.** "
               "This is a wide, turned-out, loaded squat held at depth. Your right hip has "
               "an open question about snapping under exactly that pattern, and the gym "
               "block already contains loaded squat work that is answering it. Adding a "
               "second new externally-rotated squat now would make it impossible to tell "
               "which one produced a change. Bring it back once the block's squat work has "
               "run clean. Meanwhile the bent and straight tests still name the muscle "
               "between them — this one adds resolution, not the diagnosis.",
    ),
    "leverage_straight": BatteryTest(
        key="leverage_straight", slot=_b.SLOT_REGRESSED,
        label="Knees fully straight", unit="cm", smaller_is_better=False,
        setup="Lie on your back with your backside against a wall and your legs straight up "
              "it. Lock your knees straight, kneecaps facing the ceiling. Let your legs "
              "slide apart under their own weight for 30 seconds. **No ankle weights.**",
        lock="Your backside stays against the wall and your knees stay straight. **The tell: "
             "if your backside slides away from the wall or a knee bends, the trial is "
             "void.** Kneecaps stay facing the ceiling — letting them roll in cheats the "
             "load off the groin.",
        measurement="Measure from the inside of one ankle to the inside of the other. "
                    "**Bigger is better here** — this is the one test on the list where a "
                    "larger number is the good direction.",
        what_youre_testing="Your groin muscles with the knee straight, which is what puts "
                           "gracilis under the most stretch. Read against the bent-knee test: "
                           "if the bent version is fine and this one is much worse, gracilis "
                           "is the limit. If both are poor, the whole group is short.",
        safety="Unloaded and gravity-driven. The weighted version was removed — external "
               "load onto a passively held end-range hip is the practice your profile rules "
               "out.",
        adapted_from="the original used ankle weights",
    ),

    # ── Slot 2 — Prerequisite, run two ways ─────────────────────────────────
    "tilt_range": BatteryTest(
        key="tilt_range", slot=_b.SLOT_PREREQUISITE,
        label="Tilt — with help", unit="cm", smaller_is_better=True,
        setup="Sit with your legs straight and open to **your recorded straddle width**. "
              "Kneecaps and toes pointing up. Now fold forward, **using your hands walking "
              "forward on the floor or pulling on a strap anchored in front of you**.",
        lock="Your knees stay straight and your kneecaps stay pointing up. **The tell: if "
             "your knees bend or roll inward, the trial is void.**",
        measurement="Measure from the floor up to your forehead. **Also record, separately, "
                    "the height at which your lower back stops being flat.** Two numbers, "
                    "not one — the second is the one that should move first.",
        what_youre_testing="Whether you can get into the position at all when something else "
                           "helps. Paired with the next test, it separates 'cannot reach it' "
                           "from 'can reach it but cannot produce it' — and those two answers "
                           "send you to completely different training.",
        safety="**Stop where it lands. Do not chase depth once your lower back has "
               "rounded.** Past that point you are measuring your spine rather than your "
               "hip, which is both the wrong variable and the one your discs cannot take. "
               "You predicted on 2026-08-06 that you would fail before reaching the deep "
               "position at all — this test is what checks that. If you get significantly "
               "past upright, say so, because the decision to keep this test rests on that "
               "prediction being right.",
    ),
    "tilt_production": BatteryTest(
        key="tilt_production", slot=_b.SLOT_PREREQUISITE,
        label="Tilt — under your own power", unit="cm", smaller_is_better=True,
        setup="The same position, same width. **Arms crossed on your chest. No hands, no "
              "strap, nothing to pull on.** Roll your pelvis forward and fold as far as you "
              "can under your own power.",
        lock="Arms stay crossed and the knees stay straight. **The tell: if a hand comes "
             "down to the floor, even briefly, the trial is void.**",
        measurement="Floor to forehead again, and again the height at which the lower back "
                    "stops being flat.",
        what_youre_testing="Whether you can PRODUCE the position, not just be placed in it. "
                           "This is the half that matters most for you: your file records "
                           "that you cannot roll the pelvis forward in sitting, and that the "
                           "rounding everyone notices is the compensation for it rather than "
                           "the problem itself. If this fails and the previous test passed, "
                           "the fix is strength at the end of the range, done last in the "
                           "session.",
    ),

    # ── Slot 3 — Spectrum ───────────────────────────────────────────────────
    #
    # ORDER: active, then isometric, then passive. Passive work leaves tissue
    # looser for an hour, so taking it first flatters everything after it.
    "spectrum_active": BatteryTest(
        key="spectrum_active", slot=_b.SLOT_SPECTRUM,
        label="Active — leg raise to the side", unit="°", bilateral=True,
        setup="Stand tall with no support. Lift one leg out to the side as high as you can. "
              "**No swing, no lean.** Hold it three seconds at the top.",
        lock="Your torso stays upright. **The tell: if you lean away from the lifting leg, "
             "the trial is void** — that buys height from your spine rather than your hip.",
        measurement="The angle of the raised leg from vertical. Bigger is better. Left and "
                    "right separately, to the nearest degree.",
        what_youre_testing="Not just how far you go, but **how strong the muscles that OPEN "
                           "you are**. Something has to pull the legs apart, and if those "
                           "muscles are weak the groin will not release however much you "
                           "stretch it. A poor number here is a strength problem wearing a "
                           "flexibility costume. Add your left and right angles together and "
                           "compare the sum against your passive split — a passive 160° with "
                           "an active sum of 70° is a very different athlete from one at 140°.",
    ),
    "spectrum_isometric": BatteryTest(
        key="spectrum_isometric", slot=_b.SLOT_SPECTRUM,
        label="Isometric — split, hands off", unit="cm", smaller_is_better=True,
        setup="Slide into a side split at depth and **take your hands off everything**, "
              "holding your own weight. Five seconds, then measure.",
        lock="Hands off. **The tell is obvious and that is the point** — if a hand goes back "
             "down, the trial is void.",
        measurement="Floor to crotch. **If you are using any added load, write the load down "
                    "beside the number** — they are one measurement and neither means "
                    "anything alone.",
        what_youre_testing="Whether the range is defended by muscle or only propped up from "
                           "outside. Your body will not let a muscle relax into a position it "
                           "cannot support, so end-range strength is not something running "
                           "alongside flexibility — it is what permits it.",
        safety="**If your isometric number comes out as deep as your passive one, the load "
               "is too light** and passive tissue absorbed it — you have measured passive "
               "twice. Take weight off and repeat.",
    ),
    "spectrum_passive": BatteryTest(
        key="spectrum_passive", slot=_b.SLOT_SPECTRUM,
        label="Passive — split, supported", unit="cm", smaller_is_better=True,
        setup="Side split with a bench or blocks taking your upper body weight, legs "
              "relaxed. **Go to firm resistance, not to the floor.**",
        lock="Legs stay relaxed — this is the one trial where you are not holding yourself "
             "up. **The tell: if you are working to stay there, you are measuring the "
             "isometric again and the trial is void.** Let the support take the weight.",
        measurement="Floor to crotch, to the nearest half centimetre.",
        what_youre_testing="Your ceiling — the furthest the joint goes when something else "
                           "does the work. On its own it says little; its value is as the "
                           "reference the other two are compared against.",
        safety="**Taken LAST, and taken once.** Passive work leaves tissue looser for an "
               "hour or more, so doing it first would flatter every reading after it. It is "
               "also the one item here that is deliberately passive end-range with "
               "bodyweight driving it — a measurement, not a stretch to sink into, and never "
               "held for time. With lax tissue nothing complains on the approach, so the "
               "usual warning is absent.",
    ),
}

#: The order they are performed in. Slot by slot, and within slot 3 the measure
#: order is active → isometric → passive, which is not the order they are
#: written in the source.
TEST_ORDER: tuple[str, ...] = (
    "gate0_neutral", "gate0_turned_out",
    "leverage_bent", "leverage_straight",          # leverage_90 deferred
    "tilt_range", "tilt_production",
    "spectrum_active", "spectrum_isometric", "spectrum_passive",
)

AVAILABLE_TESTS: tuple[str, ...] = tuple(k for k in TEST_ORDER if TESTS[k].available)
DEFERRED_TESTS: tuple[str, ...] = tuple(k for k, t in TESTS.items() if not t.available)


# ── extras recorded alongside, never scored ──────────────────────────────────

NERVE_CHECK: str = (
    "**A differentiator, not a provocation.** Do the tilt test twice at a COMFORTABLE, "
    "submaximal depth — once with your ankles pointed away and chin lifted, once with "
    "ankles pulled back and chin tucked. Muscle length is identical in both, so any "
    "difference in range is nerve rather than muscle. **Stop at the first change in the "
    "QUALITY of the sensation.** The original said to push until you produce a sharp, "
    "electric or burning feeling and read that as a result. Do not. Those are the exact "
    "words your own symptom logs have always treated as the line between a training "
    "sensation and something else, and you have a narrowed nerve exit on the right at L5/S1 "
    "with no neural signs on any log to date. **If one appears at any depth: stop, record "
    "the position and the quality, and do not train into it.** It is a finding, not a "
    "number, and nothing in this programme is worth producing one to obtain."
)

MEDIAL_KNEE_NOTE: str = (
    "Record any discomfort on the inside of the knee. **It is a finding, not a training "
    "sensation.** Two causes lead in opposite directions — gracilis crosses the knee, so "
    "some sensation there is mechanically expected, but a weak VMO produces pain in the "
    "same place for a different reason and needs strengthening instead of less volume."
)


def test_for(key: str) -> BatteryTest | None:
    return TESTS.get(key)


# ── slot evaluators ──────────────────────────────────────────────────────────
#
# One callable per slot. services.battery.run walks them IN ORDER and stops at
# the first that does not pass — so a failing gate 0 means slots 1-3 are never
# evaluated at all.
#
# `indeterminate` is a third outcome beside pass and fail: the readings needed
# were not taken, so the battery stops without naming a limiter. That is
# honestly different from "you passed" and must never collapse into it — a
# missing measurement is not evidence of health.

#: How much deeper the turned-out attempt must be for orientation to be the
#: limiter. PROVISIONAL: from the source, not from this athlete's own spread.
GATE0_ORIENTATION_GAIN_CM: float = 10.0
GATE0_SAME_CM: float = 5.0

#: A leverage reading at or past its target counts as a pass. PROVISIONAL for
#: the same reason — every threshold here moves once three baseline mornings
#: exist and the noise floor is known.
LEVERAGE_TARGETS: dict[str, float] = {
    "leverage_bent": 10.0,        # cm floor-to-calf, smaller is better
    "leverage_straight": 90.0,    # cm ankle-to-ankle, bigger is better
}

#: Forehead height, cm. Smaller is better.
TILT_TARGET_CM: float = 25.0

#: Centimetres between the passive and isometric split depths before end-range
#: strength rather than puller strength is called the limiter.
SPECTRUM_GAP_CM: float = 12.0


def _worse(readings) -> float | None:
    """The worse side. Sides are never averaged — the worse one is what limits.

    Every test using this has smaller-is-better or is compared against a target
    that accounts for direction, so the caller decides what "worse" means; here
    it is the larger value, which is correct for the cm-gap tests.
    """
    values = [r.value for r in readings if r.usable]
    return max(values) if values else None


def _better(readings) -> float | None:
    """The worse side on a bigger-is-better scale — i.e. the smaller value."""
    values = [r.value for r in readings if r.usable]
    return min(values) if values else None


def evaluate_structure(assessment):
    from services import battery as b
    neutral = assessment.reading("gate0_neutral")
    turned = assessment.reading("gate0_turned_out")

    if neutral is None or turned is None:
        return b.SlotResult(slot=b.SLOT_STRUCTURE, passed=False, indeterminate=True,
                            reason="Gate 0 was not completed, so nothing below it can be "
                                   "read. A missing measurement is not a pass.")

    # Smaller is deeper. A turned-out attempt that goes MUCH deeper means the
    # joint was misaligned rather than the tissue short.
    # RELATIVE: this compares two of his own readings taken minutes apart, so it
    # carries its own reference and no invented norm is involved. The only slot
    # in the battery that is sound on a first morning.
    gain = neutral.value - turned.value
    if gain >= GATE0_ORIENTATION_GAIN_CM:
        return b.SlotResult(slot=b.SLOT_STRUCTURE, passed=False, pattern="B",
                            basis=b.BASIS_RELATIVE,
                            reason=f"Turning the legs out gained {gain:.1f} cm. Orientation "
                                   f"is the limiter, not tissue length.",
                            readings=(neutral, turned))
    return b.SlotResult(slot=b.SLOT_STRUCTURE, passed=True, basis=b.BASIS_RELATIVE,
                        reason=f"Turning out changed the depth by {gain:.1f} cm — below the "
                               f"threshold for calling alignment the limiter, so this is a "
                               f"genuine tissue restriction.",
                        readings=(neutral, turned))


def evaluate_regressed(assessment):
    from services import battery as b
    bent = _worse(assessment.readings_for("leverage_bent"))
    straight = _better(assessment.readings_for("leverage_straight"))

    if bent is None or straight is None:
        return b.SlotResult(slot=b.SLOT_REGRESSED, passed=False, indeterminate=True,
                            reason="Both available leverages are needed — bent against "
                                   "straight is what names the muscle.")

    # PROVISIONAL, and this is the slot where that matters most. The source
    # document describes Test 1 entirely qualitatively — "fails both", "fails
    # bent, straight relatively better", "passes bent, fails straight badly" —
    # and gives NO numbers. The two below were invented so the code could run.
    # The first real run of this battery returned Pattern E off them.
    bent_fails = bent > LEVERAGE_TARGETS["leverage_bent"]
    straight_fails = straight < LEVERAGE_TARGETS["leverage_straight"]

    if bent_fails and straight_fails:
        return b.SlotResult(slot=b.SLOT_REGRESSED, passed=False, pattern="C",
                            basis=b.BASIS_PROVISIONAL,
                            reason="Both leverages short — the whole group.")
    if bent_fails:
        return b.SlotResult(slot=b.SLOT_REGRESSED, passed=False, pattern="D",
                            basis=b.BASIS_PROVISIONAL,
                            reason="Short with the knee bent, relatively better straight — "
                                   "the adductors and rotators rather than gracilis.")
    if straight_fails:
        return b.SlotResult(slot=b.SLOT_REGRESSED, passed=False, pattern="E",
                            basis=b.BASIS_PROVISIONAL,
                            reason="Fine bent, poor straight. Gracilis is the only one of "
                                   "the group crossing the knee, so that difference names it.")
    return b.SlotResult(slot=b.SLOT_REGRESSED, passed=True, basis=b.BASIS_PROVISIONAL,
                        reason="Length is adequate at both available leverages.")


def evaluate_prerequisite(assessment):
    from services import battery as b
    rng = assessment.reading("tilt_range")
    prod = assessment.reading("tilt_production")

    if rng is None or prod is None:
        return b.SlotResult(slot=b.SLOT_PREREQUISITE, passed=False, indeterminate=True,
                            reason="Both halves are needed. Reach-with-help and "
                                   "produce-alone are what separate F from G, and one "
                                   "without the other names neither.")

    # PROVISIONAL for the same reason — TILT_TARGET_CM is ours, not the source's.
    if rng.value > TILT_TARGET_CM:
        return b.SlotResult(slot=b.SLOT_PREREQUISITE, passed=False, pattern="F",
                            basis=b.BASIS_PROVISIONAL,
                            reason="The position is not available even with help. Tilt work "
                                   "goes FIRST in the session and starts assisted — you "
                                   "cannot train actively into a position you cannot reach.",
                            readings=(rng, prod))
    if prod.value > TILT_TARGET_CM:
        return b.SlotResult(slot=b.SLOT_PREREQUISITE, passed=False, pattern="G",
                            basis=b.BASIS_PROVISIONAL,
                            reason="You can reach it, you cannot produce it. Tilt work moves "
                                   "to the END of the session and becomes strength work.",
                            readings=(rng, prod))
    return b.SlotResult(slot=b.SLOT_PREREQUISITE, passed=True,
                        reason="The tilt is available and producible — not your limiter.",
                        readings=(rng, prod))


def evaluate_spectrum(assessment):
    from services import battery as b
    active = assessment.readings_for("spectrum_active")
    iso = assessment.reading("spectrum_isometric")
    passive = assessment.reading("spectrum_passive")

    if not active or iso is None or passive is None:
        return b.SlotResult(slot=b.SLOT_SPECTRUM, passed=False, indeterminate=True,
                            reason="All three measures are needed; the spectrum is a "
                                   "comparison, not three separate numbers.")

    # Split depths: smaller is deeper. The isometric must come out SHALLOWER
    # than passive, or the load was too light and passive tissue absorbed it.
    if not b.isometric_is_shallower(passive.value, iso.value, smaller_is_better=True):
        return b.SlotResult(slot=b.SLOT_SPECTRUM, passed=False, indeterminate=True,
                            basis=b.BASIS_RELATIVE,
                            reason="The isometric reading is as deep as the passive one, so "
                                   "the load was too light — you measured passive twice. "
                                   "Take weight off and repeat before reading this slot.",
                            readings=(iso, passive))

    gap = iso.value - passive.value
    if gap >= SPECTRUM_GAP_CM:
        return b.SlotResult(slot=b.SLOT_SPECTRUM, passed=False, pattern="H",
                            reason=f"Passive goes {gap:.1f} cm deeper than you can hold. The "
                                   f"range exists and is not defended — end-range strength.",
                            readings=(iso, passive))
    return b.SlotResult(slot=b.SLOT_SPECTRUM, passed=False, pattern="I",
                        reason="You hold what you can reach, but cannot open the legs under "
                               "your own power. The pullers are the limiter.",
                        readings=tuple(active))


#: Passed to services.battery.run, in order. The list IS the method.
SLOT_EVALUATORS = [
    evaluate_structure,
    evaluate_regressed,
    evaluate_prerequisite,
    evaluate_spectrum,
]
