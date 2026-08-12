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
  B6  Gate 0's two-orientation comparison only runs within
      GATE0_BONE_RELEVANT_CM of the floor. The athlete's call (2026-08-07):
      bone meets socket in the last few centimetres of a FULL side split, so at
      his current height tissue stops him long before bone can, and the
      comparison answers nothing up there. Above the line, slot 0 passes on the
      neutral reading alone and the turned-out attempt is skipped.
      Reverts: if a reading taken inside the line ever contradicts the claim.
  B8  Gate 0 records the WIDTH of the split, not the gap from the floor to the
      crotch (athlete's call, 2026-08-12: "it is hard to gauge each time where
      exactly the crotch reads"). The heels are unambiguous and the width is
      what he can repeat. Every threshold stayed a HEIGHT off the floor — the
      claim they encode is about the last few centimetres of a full split — so
      floor_gap_from_span converts, using a leg length measured ONCE standing
      and carried on the reading as its setup_value. Read that function before
      touching any of it: the conversion is sharp where he is (0.5 cm of height
      per cm of width at 60 cm off the floor) and blunt where he is not (8.8 cm
      at 5 cm), which is the opposite of the obvious worry.
      Reverts: when a reading lands inside ~25 cm the two-orientation
      comparison needs a directly measured gap again. Gated on the READING.
  B7  The tilt is measured as an ANGLE at the pelvis, not as forehead height
      (athlete's call, 2026-08-07). Forehead height is exactly the number a
      rounding spine can fake, and his rounding is the documented compensation
      — so the old protocol needed a second guard measurement, and the angle
      needs none. One number replaces two. The two tilt trials also run OWN
      POWER FIRST, then helped — help flatters whatever follows it, the same
      principle as slot 3's order, and the athlete states it as a requirement.
"""

from __future__ import annotations

import math
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
    #: One line answering "where does the number I am about to type come
    #: from?", shown AT the input field itself. The measurement field explains
    #: the whole procedure; this one locates the tape. Patient-facing.
    input_hint: str = ""
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
        label="Side split, legs neutral", unit="cm", smaller_is_better=False,
        setup="Slide into a side split with your legs in a **neutral rotation** — kneecaps "
              "pointing forward, not turned up. Go to where it stops, not past it. Hands on "
              "blocks in front of you so your chest stays up.",
        lock="Your pelvis and lower back must be **identical between this attempt and the "
             "next one**. The whole reading is the difference the leg rotation makes, so "
             "anything else that moves contaminates it. **The tell: if your back position "
             "changes between the two attempts, the trial is void** — reset and take both "
             "again.",
        measurement="Measure along the floor from the inside of one heel to the inside "
                    "of the other. Bigger is deeper. To the nearest half centimetre. "
                    "**Record your leg length once, standing** — floor to crotch with "
                    "your heels down, the way a tailor measures an inseam. That number "
                    "is what turns the width into how high off the floor you are, and "
                    "it is the same number every session.",
        input_hint="The distance between the inside of one heel and the inside of the "
                   "other, in cm",
        setup_input="Leg length — standing, floor to crotch (cm)",
        what_youre_testing="Whether the thing stopping you is the shape of your hip joint "
                           "rather than tissue length. The neck of the thigh bone eventually "
                           "meets the rim of the socket, and where that happens varies a lot "
                           "between healthy people. Bone does not stretch, so if this is your "
                           "limit the answer is alignment rather than more stretching. That "
                           "collision only happens in the last few centimetres of a full "
                           "split, though — so this reading doubles as the check on whether "
                           "the question is even live yet. More than 15 cm off the floor, "
                           "tissue is stopping you long before any bone could, and the "
                           "turned-out comparison is skipped until you are closer.",
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
        label="Side split, legs turned out", unit="cm", smaller_is_better=False,
        setup="The same position, but now **turn both legs out from the hips** — let the "
              "kneecaps rotate toward the ceiling. Keep your back exactly as it was in the "
              "first attempt.",
        lock="As above: pelvis and lower back unchanged between the two. **The tell is the "
             "same** — if your back moves, the comparison is void.",
        measurement="Same measurement: inside heel to inside heel along the floor, to "
                    "the nearest half centimetre. **The reading is the difference "
                    "between the two attempts.**",
        input_hint="The distance between the inside of one heel and the inside of the "
                   "other, in cm — same tape as the first attempt",
        what_youre_testing="The same question, asked with the joint aligned differently. "
                           "There are two ways to give the hip more room — turn the leg out, "
                           "or tilt the pelvis — and they reach the same place. This uses the "
                           "turn-out because tilting means arching your lower back under your "
                           "full bodyweight, which your imaging rules out. A large jump "
                           "between the two attempts means alignment was the limit, not "
                           "tissue. This attempt only runs when your neutral reading lands "
                           "within 15 cm of the floor — higher than that, bone cannot be "
                           "what stops you and the comparison answers nothing.",
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
        input_hint="The gap between the floor and the outside of each calf, in cm — "
                   "left and right separately",
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
        input_hint="The gap between the floor and your hip crease, in cm",
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
                    "**Bigger is better here** — a larger number is the good direction.",
        input_hint="The distance between the inside of one ankle and the inside of the "
                   "other, in cm",
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
    #
    # OWN POWER FIRST, then helped — the athlete's requirement (2026-08-07),
    # and the same principle as slot 3's order: an assisted trial flatters
    # whatever follows it, so the unassisted one cannot come after.
    #
    # Measured as an ANGLE at the pelvis, not as forehead height. Forehead
    # height is exactly the number a rounding spine can fake, and his rounding
    # is the documented compensation — which is why the old protocol needed a
    # second guard measurement and this one needs none.
    "tilt_production": BatteryTest(
        key="tilt_production", slot=_b.SLOT_PREREQUISITE,
        label="Tilt — under your own power", unit="°",
        setup="Sit tall with your legs straight and open to **your recorded straddle "
              "width** — kneecaps and toes pointing up. **Arms crossed on your chest. No "
              "hands, no strap, nothing to pull on.** Now tip your hips forward — as if "
              "your waistband were a bowl of water you are pouring out the front — as far "
              "as you can under your own power, and hold it there.",
        lock="Arms stay crossed, knees stay straight, kneecaps stay pointing up. **The "
             "tell: if a hand comes down to the floor, even briefly, the trial is void.** "
             "Steadying the phone against your lower back with one hand is fine — it is "
             "the floor you must not touch.",
        measurement="Your phone, flat against your lower back just above the tailbone, "
                    "with a level app open. Sitting tall, note the angle. Tip as far as "
                    "you can, hold it, and read the angle again in the same spot. **The "
                    "reading is how many degrees it moved. Bigger is better.** One number "
                    "is enough — a rounding back cannot fake this one, which is why the "
                    "old two-number version is gone.",
        input_hint="How many degrees the phone reading moved between sitting tall and "
                   "your deepest tip",
        setup_input="Straddle width — inside of one heel to the inside of the other (cm)",
        what_youre_testing="Whether you can PRODUCE the position, not just be placed in "
                           "it. This is the half that matters most for you: your file "
                           "records that you cannot roll the pelvis forward in sitting, "
                           "and that the rounding everyone notices is the compensation "
                           "for it rather than the problem itself. Measured at the pelvis "
                           "because the pelvis is the thing being tested — a forehead "
                           "height is exactly what a rounding spine fakes. Taken before "
                           "the helped version, because help flatters whatever follows "
                           "it. If this fails and the helped test passes, the fix is "
                           "strength at the end of the range, done last in the session.",
    ),
    "tilt_range": BatteryTest(
        key="tilt_range", slot=_b.SLOT_PREREQUISITE,
        label="Tilt — with help", unit="°",
        setup="The same position and **the same straddle width you just recorded**. This "
              "time use help: walk your hands forward on the floor, or pull on a strap "
              "anchored in front of you, to tip your hips further forward than you could "
              "on your own.",
        lock="Your knees stay straight and your kneecaps stay pointing up. **The tell: if "
             "your knees bend or roll inward, the trial is void.**",
        measurement="The same phone reading: flat against your lower back, sitting tall "
                    "first, then at your deepest helped tip. **The reading is how many "
                    "degrees it moved. Bigger is better.**",
        input_hint="How many degrees the phone reading moved, sitting tall to your "
                   "deepest helped tip",
        what_youre_testing="Whether the position exists at all when something else helps. "
                           "Paired with the test before it, this separates 'cannot reach "
                           "it' from 'can reach it but cannot produce it' — and those two "
                           "answers send you to completely different training. It runs "
                           "second on purpose: help leaves everything looser, so the "
                           "own-power trial had to come first.",
        safety="**Help tips the hips; it must not fold the spine. Stop the moment your "
               "lower back rounds** — past that point the extra depth is coming from "
               "your spine, which is both the wrong variable and the one your discs "
               "cannot take. You predicted on 2026-08-06 that you would fail before "
               "reaching the deep position at all — this test is what checks that. If "
               "you get significantly past sitting tall, say so, because the decision "
               "to keep this test rests on that prediction being right.",
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
        input_hint="The angle of the raised leg, in degrees up from straight down — "
                   "left and right separately",
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
        input_hint="The gap between the floor and your crotch, in cm — plus the load "
                   "beside it if you used one",
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
        input_hint="The gap between the floor and your crotch, in cm",
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

#: The order they are performed in. Slot by slot; within slot 2 own-power comes
#: before helped, and within slot 3 the measure order is active → isometric →
#: passive. NEITHER is the order the source writes them in, and both exist for
#: the same reason: an assisted or passive trial flatters whatever follows it.
TEST_ORDER: tuple[str, ...] = (
    "gate0_neutral", "gate0_turned_out",
    "leverage_bent", "leverage_straight",          # leverage_90 deferred
    "tilt_production", "tilt_range",
    "spectrum_active", "spectrum_isometric", "spectrum_passive",
)

AVAILABLE_TESTS: tuple[str, ...] = tuple(k for k in TEST_ORDER if TESTS[k].available)
DEFERRED_TESTS: tuple[str, ...] = tuple(k for k, t in TESTS.items() if not t.available)


def applicable_tests(assessment=None) -> tuple[str, ...]:
    """The tests a SESSION actually asks for, given what it has measured so far.

    One rule today: the turned-out attempt only runs when the neutral
    side-split reading is within GATE0_BONE_RELEVANT_CM of the floor — above
    that, bone cannot be what stops him and the comparison answers nothing.
    Owned here rather than by the screen, so the capture flow and the evaluator
    cannot disagree about when the comparison matters.
    """
    neutral = assessment.reading("gate0_neutral") if assessment is not None else None
    gap = _gap(neutral)
    if gap is not None and gap > GATE0_BONE_RELEVANT_CM:
        return tuple(k for k in AVAILABLE_TESTS if k != "gate0_turned_out")
    return AVAILABLE_TESTS


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

#: The height off the floor below which the bony question becomes live. THE
#: ATHLETE'S CALL (2026-08-07): the neck of the thigh bone meets the socket only
#: in the last few centimetres of a FULL side split, so at his current height
#: tissue stops him long before bone can, and asking the two-orientation
#: comparison up there answers nothing. Above this line slot 0 passes on the
#: neutral reading alone and the turned-out attempt is skipped. A claim about
#: where in the range the mechanism operates, not a preference — re-open it only
#: if a reading taken inside the line contradicts it.
#:
#: STILL IN CENTIMETRES OFF THE FLOOR after the 2026-08-12 switch to measuring
#: the split's WIDTH — see floor_gap_from_span. It is also the athlete's own
#: stated success target ("15 cm or less and I'll consider it a success",
#: 2026-08-12), so it is now two claims in one number and both are his.
GATE0_BONE_RELEVANT_CM: float = 15.0


def floor_gap_from_span(span_cm, leg_length_cm):
    """How high off the floor a side split of `span_cm` puts you, given the
    athlete's standing leg length. Returns None when it cannot be computed.

    WHY THE READING IS A WIDTH AND THE THRESHOLDS ARE STILL HEIGHTS (athlete,
    2026-08-12): finding the crotch by eye mid-split is not repeatable, and it
    is the number he was asked for every session. The heels are unambiguous. So
    he measures the width, and the one crotch measurement that survives is taken
    ONCE, standing, where a tailor takes it.

    Each leg is the hypotenuse from crotch to floor contact, so with half the
    span as one side, `gap = sqrt(L^2 - (span/2)^2)`.

    THE CONVERSION IS SHARP WHERE HE IS AND BLUNT WHERE HE IS NOT, which is the
    opposite of the worry and worth writing down. Per 1 cm of error in the width,
    at leg length 84-88 cm:

        60 cm off the floor   0.5 cm of height     <- him today
        30 cm                 1.3 cm
        15 cm                 2.9 cm               <- the line above
         5 cm                 8.8 cm

    So the whole zone this threshold governs is about 2.6 cm of width, and down
    there a width reading cannot answer the question at all. That does not bite
    yet — he is over 60 cm off the floor and calls a full split "2 years or
    more" away (2026-08-12), and the turned-out attempt is skipped that whole
    time. REVERT CONDITION, in the HRV_GARMIN_HOLD idiom: when a reading lands
    inside ~25 cm, this stops being good enough and the two-orientation
    comparison needs a directly measured floor-to-crotch gap rather than one
    derived from a width. Gated on the READING, not on a date.
    """
    if not span_cm or not leg_length_cm or leg_length_cm <= 0:
        return None
    half = float(span_cm) / 2.0
    if half >= float(leg_length_cm):
        return None            # wider than two legs — a mismeasure, not a split
    return math.sqrt(float(leg_length_cm) ** 2 - half ** 2)


def _gap(reading):
    """The floor-to-crotch gap a gate 0 reading implies, or None. The leg length
    rides on the reading as its `setup_value` — load and measurement are ONE
    DATUM, the same rule as the heel distance and the straddle width."""
    if reading is None:
        return None
    return floor_gap_from_span(reading.value, reading.setup_value)

#: Why a test that applicable_tests dropped was dropped, in the athlete's
#: language — the capture flow shows this instead of the step.
SKIP_NOTES: dict[str, str] = {
    "gate0_turned_out": (
        f"Skipped: legs turned out. At your height off the floor, bone is not yet "
        f"a factor — the comparison starts mattering under "
        f"{GATE0_BONE_RELEVANT_CM:.0f} cm, and it will come back by itself once a "
        f"neutral reading lands inside that line."
    ),
}

#: A leverage reading at or past its target counts as a pass. PROVISIONAL for
#: the same reason — every threshold here moves once three baseline mornings
#: exist and the noise floor is known.
LEVERAGE_TARGETS: dict[str, float] = {
    "leverage_bent": 10.0,        # cm floor-to-calf, smaller is better
    "leverage_straight": 90.0,    # cm ankle-to-ankle, bigger is better
}

#: Degrees of pelvic tip produced, sitting tall to deepest. Bigger is better.
#: PROVISIONAL like the rest — invented so the code can run, and it moves once
#: three baseline mornings show what his own numbers look like.
TILT_TARGET_DEG: float = 20.0

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

    if neutral is None:
        return b.SlotResult(slot=b.SLOT_STRUCTURE, passed=False, indeterminate=True,
                            reason="Gate 0 was not completed, so nothing below it can be "
                                   "read. A missing measurement is not a pass.")

    # The reading is the WIDTH of the split; every threshold below is a height
    # off the floor. Without the leg length recorded beside it the width cannot
    # be turned into one, and a width alone is not evidence of anything — say so
    # rather than passing on a number nothing can interpret.
    neutral_gap = _gap(neutral)
    if neutral_gap is None:
        return b.SlotResult(slot=b.SLOT_STRUCTURE, passed=False, indeterminate=True,
                            reason="The split width was recorded without a leg length "
                                   "beside it, so how high off the floor you are cannot "
                                   "be worked out. Measure it once standing — floor to "
                                   "crotch, heels down — and it is the same number every "
                                   "session after that.")

    # THE RELEVANCE LINE (athlete's call, 2026-08-07). Bone meets socket only in
    # the last few centimetres of a full split; above the line, tissue stops him
    # long before bone can, so the two-orientation comparison answers nothing
    # and is skipped rather than asked. PROVISIONAL in the formal sense — no
    # measurement validates 15 over 12 — but the number is his, from the
    # mechanics of the test, not one invented to make the code run.
    if neutral_gap > GATE0_BONE_RELEVANT_CM:
        extra = ""
        turned_gap = _gap(turned)
        if turned_gap is not None:
            diff = neutral_gap - turned_gap
            extra = (f" Turning out changed it by {diff:.1f} cm — noted, but at this "
                     f"height that is tissue following the alignment, not bone.")
        return b.SlotResult(slot=b.SLOT_STRUCTURE, passed=True, basis=b.BASIS_PROVISIONAL,
                            reason=f"A {neutral.value:.1f} cm split puts you "
                                   f"{neutral_gap:.1f} cm off the floor, and bone cannot be "
                                   f"what stops you up there — that contact only happens in "
                                   f"the last few centimetres of a full split. The "
                                   f"two-orientation check starts mattering under "
                                   f"{GATE0_BONE_RELEVANT_CM:.0f} cm; it comes back by "
                                   f"itself once you are inside that line.{extra}",
                            readings=(neutral,) if turned is None else (neutral, turned))

    if turned is None:
        return b.SlotResult(slot=b.SLOT_STRUCTURE, passed=False, indeterminate=True,
                            reason=f"Within {GATE0_BONE_RELEVANT_CM:.0f} cm of the floor "
                                   f"the bony question is live, and it needs the turned-out "
                                   f"attempt. A missing measurement is not a pass.")

    turned_gap = _gap(turned)
    if turned_gap is None:
        return b.SlotResult(slot=b.SLOT_STRUCTURE, passed=False, indeterminate=True,
                            reason="The turned-out width has no leg length beside it, so "
                                   "the two attempts cannot be compared as depths. A "
                                   "missing measurement is not a pass.")

    # A turned-out attempt that goes MUCH deeper means the joint was misaligned
    # rather than the tissue short. Compared as HEIGHTS, not as widths: the same
    # gain is 5.9 cm of width at 30 cm off the floor and 2.3 cm at 15 cm, so a
    # width threshold would mean something different at every depth. See
    # floor_gap_from_span.
    # RELATIVE: this compares two of his own readings taken minutes apart, so it
    # carries its own reference and no invented norm is involved. The only slot
    # in the battery that is sound on a first morning.
    gain = neutral_gap - turned_gap
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
    prod = assessment.reading("tilt_production")
    rng = assessment.reading("tilt_range")

    # Degrees only. A tilt recorded in centimetres is from the retired
    # forehead-height protocol and cannot be read against an angle target —
    # treating it as unreadable is honest; treating 40 cm as 40° would not be.
    prod = prod if prod is not None and prod.unit == "°" else None
    rng = rng if rng is not None and rng.unit == "°" else None

    if rng is None or prod is None:
        return b.SlotResult(slot=b.SLOT_PREREQUISITE, passed=False, indeterminate=True,
                            reason="Both halves are needed. Produce-alone and "
                                   "reach-with-help are what separate F from G, and one "
                                   "without the other names neither. (Angle readings only "
                                   "— a tilt recorded in centimetres is from the old "
                                   "protocol and cannot be read.)")

    # PROVISIONAL for the same reason — TILT_TARGET_DEG is ours, not the
    # source's. Bigger is better: the reading is degrees of pelvic tip produced.
    if rng.value < TILT_TARGET_DEG:
        return b.SlotResult(slot=b.SLOT_PREREQUISITE, passed=False, pattern="F",
                            basis=b.BASIS_PROVISIONAL,
                            reason="The position is not available even with help. Tilt work "
                                   "goes FIRST in the session and starts assisted — you "
                                   "cannot train actively into a position you cannot reach.",
                            readings=(rng, prod))
    if prod.value < TILT_TARGET_DEG:
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


# ── the ladder ───────────────────────────────────────────────────────────────
#
# Cluster A's ladder, bottom-up: the tightest thing is at the bottom and it is
# what you work first. Seven rungs, each a capacity the battery measures,
# annotated with the muscle it names. States come from the battery result —
# the ladder never re-decides anything.
#
# Denominators, because every fraction must name one:
#   group/gracilis/tilt  the PROVISIONAL targets (invented, flagged as such)
#   strength at depth    the athlete's OWN passive reading — relative, sound
#   openers              180° — the geometry of a full side split, not a guess

#: Display metadata, bottom rung first. The prototype reads this too.
LADDER_INFO: tuple[dict, ...] = (
    {"key": "bone", "label": "Bone & orientation",
     "muscle": "the shape of the hip joint", "unit": "cm", "provisional": False},
    {"key": "group_length", "label": "Adductor group — bent knee",
     "muscle": "inner thigh group", "unit": "cm", "provisional": True},
    {"key": "gracilis", "label": "Gracilis — straight knee",
     "muscle": "the groin muscle that crosses the knee", "unit": "cm",
     "provisional": True},
    {"key": "tilt_range", "label": "Tilt, with help",
     "muscle": "hamstrings capping the pelvis", "unit": "°", "provisional": True},
    {"key": "tilt_production", "label": "Tilt, own power",
     "muscle": "hip flexors", "unit": "°", "provisional": True},
    {"key": "end_range", "label": "Strength at depth",
     "muscle": "adductors under load", "unit": "cm", "provisional": False},
    {"key": "pullers", "label": "Openers",
     "muscle": "hip abductors", "unit": "°", "provisional": False},
)


def _info(key: str) -> dict:
    return next(i for i in LADDER_INFO if i["key"] == key)


def ladder(assessment, result) -> tuple:
    """The battery's decision path as rungs, bottom-up.

    Readings below the first failure appear as CONTEXT when they exist (the
    athlete chose to keep going) — measured numbers, honestly shown, but the
    working rung stays the battery's first failure. Absent readings appear as
    UNMEASURED with no number at all.
    """
    from services import battery as b

    ran = {s.slot: s for s in result.slots}
    rungs: list = []

    def add(key, state, *, measured=None, target=None, fraction=None,
            detail="", pattern=""):
        info = _info(key)
        rungs.append(b.LadderRung(
            key=key, label=info["label"], muscle=info["muscle"], state=state,
            unit=info["unit"], measured=measured, target=target,
            fraction=fraction, detail=detail, pattern=pattern,
            provisional=info["provisional"]))

    # ── bone & orientation (slot 0) ─────────────────────────────────────────
    slot0 = ran.get(b.SLOT_STRUCTURE)
    neutral = assessment.reading("gate0_neutral")
    # The rung shows the DERIVED height, not the width, because the target it is
    # read against is a height and a bar mixing the two would be meaningless.
    neutral_gap = _gap(neutral)
    if slot0 is None or slot0.indeterminate:
        add("bone", b.RUNG_UNMEASURED, detail="Gate 0 incomplete.")
    elif not slot0.passed:
        add("bone", b.RUNG_LIMITING, pattern=slot0.pattern, measured=neutral_gap,
            detail="Turning the legs out changes the depth — alignment, not tissue.")
    elif neutral_gap is not None and neutral_gap > GATE0_BONE_RELEVANT_CM:
        add("bone", b.RUNG_PASSED, measured=neutral_gap,
            detail=f"Not a factor at {neutral_gap:.0f} cm off the floor, which is what "
                   f"a {neutral.value:g} cm split comes to — the question goes live "
                   f"under {GATE0_BONE_RELEVANT_CM:g} cm.")
    else:
        add("bone", b.RUNG_PASSED, measured=neutral_gap,
            detail="Turning out changed little — tissue, not bone.")

    # ── the two leverages (slot 1) ──────────────────────────────────────────
    slot1 = ran.get(b.SLOT_REGRESSED)
    bent = _worse(assessment.readings_for("leverage_bent"))
    straight = _better(assessment.readings_for("leverage_straight"))
    bent_frac = b.fraction_of_target(bent, LEVERAGE_TARGETS["leverage_bent"],
                                     smaller_is_better=True)
    straight_frac = b.fraction_of_target(straight,
                                         LEVERAGE_TARGETS["leverage_straight"])

    def leverage_state(has_reading, failed):
        if slot1 is None or slot1.indeterminate:
            if not has_reading:
                return b.RUNG_UNMEASURED
            return b.RUNG_CONTEXT if slot1 is None else b.RUNG_PASSED
        return b.RUNG_LIMITING if failed else b.RUNG_PASSED

    if slot1 is not None and not slot1.indeterminate:
        group_fails = slot1.pattern in ("C", "D")
        gracilis_fails = slot1.pattern in ("C", "E")
    else:
        group_fails = gracilis_fails = False

    add("group_length",
        leverage_state(bent is not None, group_fails),
        measured=bent, target=LEVERAGE_TARGETS["leverage_bent"],
        fraction=bent_frac if bent is not None else None,
        pattern="D" if slot1 and slot1.pattern == "D" else
                ("C" if slot1 and slot1.pattern == "C" else ""),
        detail="Worse side decides; heels at the recorded distance.")
    add("gracilis",
        leverage_state(straight is not None, gracilis_fails),
        measured=straight, target=LEVERAGE_TARGETS["leverage_straight"],
        fraction=straight_frac if straight is not None else None,
        pattern="E" if slot1 and slot1.pattern == "E" else
                ("C" if slot1 and slot1.pattern == "C" else ""),
        detail="Named by the straight-against-bent comparison.")

    # ── the tilt, two ways (slot 2) ─────────────────────────────────────────
    slot2 = ran.get(b.SLOT_PREREQUISITE)
    rng = assessment.reading("tilt_range")
    rng = rng if rng is not None and rng.unit == "°" else None
    prod = assessment.reading("tilt_production")
    prod = prod if prod is not None and prod.unit == "°" else None
    rng_frac = b.fraction_of_target(rng.value if rng else None, TILT_TARGET_DEG)
    prod_frac = b.fraction_of_target(prod.value if prod else None, TILT_TARGET_DEG)

    if slot2 is not None and not slot2.indeterminate:
        if slot2.pattern == "F":
            add("tilt_range", b.RUNG_LIMITING, pattern="F",
                measured=rng.value, target=TILT_TARGET_DEG, fraction=rng_frac,
                detail="Not available even with help — tilt work first, assisted.")
            add("tilt_production", b.RUNG_CONTEXT,
                measured=prod.value, target=TILT_TARGET_DEG, fraction=prod_frac,
                detail="Same slot, second question — read it again once the "
                       "helped tilt moves.")
        elif slot2.pattern == "G":
            add("tilt_range", b.RUNG_PASSED,
                measured=rng.value, target=TILT_TARGET_DEG, fraction=rng_frac,
                detail="The position exists when something helps.")
            add("tilt_production", b.RUNG_LIMITING, pattern="G",
                measured=prod.value, target=TILT_TARGET_DEG, fraction=prod_frac,
                detail="Reachable but not producible — strength work, last in "
                       "the session.")
        else:
            add("tilt_range", b.RUNG_PASSED, measured=rng.value,
                target=TILT_TARGET_DEG, fraction=rng_frac)
            add("tilt_production", b.RUNG_PASSED, measured=prod.value,
                target=TILT_TARGET_DEG, fraction=prod_frac)
    else:
        for key, reading, frac in (("tilt_range", rng, rng_frac),
                                   ("tilt_production", prod, prod_frac)):
            if reading is None:
                add(key, b.RUNG_UNMEASURED)
            else:
                add(key, b.RUNG_CONTEXT, measured=reading.value,
                    target=TILT_TARGET_DEG, fraction=frac,
                    detail="Measured below a failure — context, not diagnosis.")

    # ── the spectrum (slot 3) ───────────────────────────────────────────────
    slot3 = ran.get(b.SLOT_SPECTRUM)
    iso = assessment.reading("spectrum_isometric")
    passive = assessment.reading("spectrum_passive")
    actives = assessment.readings_for("spectrum_active")
    by_side = {r.side: r.value for r in actives}
    active_sum = sum(by_side.values()) if len(by_side) >= 2 else None

    # RELATIVE, and the one rung that needs no invented number: the fraction is
    # the athlete's own held depth over his own passive depth.
    depth_frac = None
    if iso is not None and passive is not None and iso.value > 0:
        depth_frac = max(0.0, min(1.0, passive.value / iso.value))
    open_frac = b.fraction_of_target(active_sum, 180.0)

    unreadable = (slot3 is not None and slot3.indeterminate
                  and "too light" in slot3.reason)
    if unreadable:
        add("end_range", b.RUNG_UNREADABLE, measured=iso.value, target=passive.value,
            detail="The load was too light — passive measured twice. Repeat "
                   "before reading this rung.")
    elif slot3 is not None and not slot3.indeterminate:
        add("end_range",
            b.RUNG_LIMITING if slot3.pattern == "H" else b.RUNG_PASSED,
            pattern="H" if slot3.pattern == "H" else "",
            measured=iso.value, target=passive.value, fraction=depth_frac,
            detail=f"Holds {iso.value:g} cm against a passive {passive.value:g} cm "
                   f"— your own reading is the yardstick.")
    elif iso is not None and passive is not None:
        add("end_range", b.RUNG_CONTEXT, measured=iso.value, target=passive.value,
            fraction=depth_frac,
            detail="Measured below a failure — context, not diagnosis.")
    else:
        add("end_range", b.RUNG_UNMEASURED)

    if slot3 is not None and not slot3.indeterminate:
        add("pullers",
            b.RUNG_LIMITING if slot3.pattern == "I" else b.RUNG_PASSED,
            pattern="I" if slot3.pattern == "I" else "",
            measured=active_sum, target=180.0, fraction=open_frac,
            detail="Left plus right, against the 180° of a full split.")
    elif active_sum is not None:
        add("pullers", b.RUNG_CONTEXT, measured=active_sum, target=180.0,
            fraction=open_frac,
            detail="Measured below a failure — context, not diagnosis.")
    else:
        add("pullers", b.RUNG_UNMEASURED)

    return tuple(rungs)
