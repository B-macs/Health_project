"""
cluster_a_battery.py — Cluster A's three slots. Side split and pancake.

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
  B1  SUPERSEDED by REMOVED_GATE_0 — it adapted a test that no longer exists.
      Kept as a numbered line rather than deleted so B2-B8 keep their names.
      It read: gate 0 turns the legs out instead of arching the back, because
      the Mechanics document calls the two routes equivalent and only one
      collides with an L5/S1 retrolisthesis. Still true, and it comes back with
      gate 0 if gate 0 ever does.
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
  B6  SUPERSEDED by REMOVED_GATE_0, same as B1. It scoped gate 0's
      two-orientation comparison to the last 15 cm of the floor, on the
      athlete's 2026-08-07 call that bone meets socket only in the last few
      centimetres of a FULL side split. That claim is still the reason gate 0
      was removable rather than merely unwanted, so it is restated in
      REMOVED_GATE_0 and comes back with the slot.
  B8  Every side split records the WIDTH between the heels, not the gap from
      the floor to the crotch (athlete's call, 2026-08-12: "it is hard to gauge
      each time where exactly the crotch reads"). The heels are unambiguous and
      the width is what he can repeat. SPECTRUM_GAP_CM stayed a HEIGHT off the
      floor, because the same depth difference is a different width at every
      depth, so floor_gap_from_span converts using a leg length measured ONCE
      standing and carried on the isometric reading as its setup_value. Read
      that function before touching any of it: the conversion is sharp where he
      is (0.5 cm of height per cm of width at 60 cm off the floor) and blunt
      where he is not (8.8 cm at 5 cm), which is the opposite of the obvious
      worry. Reverts: when a reading lands inside ~25 cm the spectrum
      comparison needs a directly measured gap again. Gated on the READING.
  B9  THE TILT IS THE ATHLETE'S OWN ANGLE, and it amends B7 rather than
      replacing it (athlete, 2026-08-12). He measures the angle between his
      straight legs and his torso: 0 is the stomach on the floor, 90 is bolt
      upright, 180 is flat on the back. SMALLER IS BETTER. He read 93 under his
      own power — "I cant even get over my hips to start the pancake stretch, I
      am slightly behind" — and 89 with help.
      The field had been asking for something else entirely: degrees the PELVIS
      moved between sitting tall and the deepest tip, bigger better, target 20.
      So a 93 was read as 93 degrees of pelvic rotation and scored 100%, on a
      screen that then said "no pattern reached" for an unrelated reason. A
      number in the right unit, in the wrong direction, against the wrong
      denominator, is the exact failure the plain-English rule at the top of
      this file exists to prevent, and it survived because nothing cross-checks
      a reading against the range a human could plausibly produce.
      ⚠ IT RE-ADMITS THE CONFOUND B7 REMOVED, and that is the cost. A torso
      angle can be bought by rounding the spine, which is his documented
      compensation; the pelvic reading could not be. It is handled in the LOCK
      instead of by choosing a different measurement — both tilt trials now void
      on a rounded back and say why. Watch it: if his readings improve while the
      rounding is unchanged, the lock is not holding and B7's measurement comes
      back as the arbiter.
      Reverts: on that evidence, not on a date.
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

#: What was taken out entirely, and what would put it back — the convention
#: cluster_a_mechanics.REMOVED establishes, because an unexplained absence is
#: indistinguishable from an oversight.
REMOVED_GATE_0: str = """
Slot 0 (Structure) and both of its side splits were REMOVED on 2026-08-12, on
the athlete's instruction, stated twice: "Remove Gate 0, its not required" and
"I dont want it".

HIS REASON, which is a measurement argument and is the part worth keeping:
gate 0 was a passive end-range side split under another name, and it ran FIRST.
The battery already encodes the opposite rule everywhere else — MEASURE_ORDER is
active -> isometric -> passive, and spectrum_passive's own safety text says
passive work "leaves tissue looser for an hour or more, so doing it first would
flatter every reading after it". Gate 0 did exactly that to the two leverages,
both tilt trials and all three spectrum measures, and the bias is optimistic:
everything below it read looser than it is.

It was also, for this athlete, nearly inert. B6's relevance line meant the
turned-out comparison only ran inside 15 cm of the floor; he is over 60 cm up
and calls a full split "2 years or more" away (2026-08-12), so the comparison
was skipped every session and slot 0 could only ever return pass. One passive
split, taken at the worst possible moment, for a verdict that could not vary.

WHAT WENT WITH IT: tests gate0_neutral and gate0_turned_out, evaluate_structure,
GATE0_ORIENTATION_GAIN_CM, GATE0_BONE_RELEVANT_CM, the SKIP_NOTES entry,
applicable_tests' only rule, and the ladder's "bone" rung.

WHAT DID NOT: patterns A (Bone) and B (Orientation) keep their entries here and
their stacks in cluster_a_prescription — they are the source's material and the
battery simply cannot emit them now. A test pins that they are unreachable so
nobody reads their presence as a live outcome. floor_gap_from_span stayed too;
the spectrum splits still need it.

WHAT WOULD PUT IT BACK: a bony end-feel finding — the sharp anterior pinch with
a hard stop that patient_profile logs for 2026-08-05 and has never explained —
or any reading landing inside ~15 cm of the floor, where the question stops
being hypothetical. Restoring means the two tests, evaluate_structure at the
head of SLOT_EVALUATORS, and the bone rung; B1 and B6 come back with them. If it
returns it should be measured LAST and read first, which is the ordering
objection answered rather than reintroduced.
"""

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
        lock="Arms stay crossed, knees stay straight, kneecaps stay pointing up, **and "
             "your back stays flat**. The tell for the hands: if one comes down to the "
             "floor, even briefly, the trial is void. **The tell for the back: if it "
             "rounds, the trial is void** — the angle is read to your torso, so a folded "
             "spine buys degrees your hips never gave, and rounding is your documented "
             "compensation for exactly this.",
        measurement="The angle between your legs and your torso at your deepest tip. "
                    "**Smaller is better, and the scale runs 0 to 180: 0 is your stomach "
                    "on the floor with your legs straight, 90 is sitting bolt upright, "
                    "180 is lying flat on your back.** Above 90 you are leaning backwards "
                    "and have not started the fold at all. Take it from the side — a "
                    "phone photo against a wall, or a level app laid along your "
                    "breastbone.",
        input_hint="The angle between your legs and your torso at your deepest tip, in "
                   "degrees — 90 is upright, less is further over",
        setup_input="Straddle width — inside of one heel to the inside of the other (cm)",
        what_youre_testing="Whether you can PRODUCE the position, not just be placed in "
                           "it. This is the half that matters most for you: your file "
                           "records that you cannot roll the pelvis forward in sitting, "
                           "and that the rounding everyone notices is the compensation "
                           "for it rather than the problem itself. **The lock is what "
                           "stops a rounding spine faking this** — the angle is read to "
                           "your torso, so a folded back would buy degrees your hips "
                           "never gave. Taken before "
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
        lock="Your knees stay straight, your kneecaps stay pointing up **and your back "
             "stays flat**. **The tell: if your knees bend or roll inward, or your back "
             "rounds, the trial is void** — with help the spine is what gives first, and "
             "it would buy degrees the hips never gave.",
        measurement="The same angle, read the same way: legs to torso at your deepest "
                    "helped tip. **Smaller is better — 90 is upright, 0 is flat on your "
                    "stomach.**",
        input_hint="The angle between your legs and your torso at your deepest helped "
                   "tip, in degrees",
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
        label="Isometric — split, hands off", unit="cm",
        setup="Slide into a side split at depth and **take your hands off everything**, "
              "holding your own weight. Five seconds, then measure. **This is the one "
              "split where nothing supports you** — not the blocks you used at the start, "
              "not the bench you use next.",
        lock="Hands off. **The tell is obvious and that is the point** — if a hand goes back "
             "down, the trial is void.",
        measurement="Measure along the floor from the inside of one heel to the inside of "
                    "the other. Bigger is deeper. **If you are using any added load, write "
                    "the load down beside the number** — they are one measurement and "
                    "neither means anything alone.",
        input_hint="The distance between the inside of one heel and the inside of the "
                   "other, in cm — plus the load beside it if you used one",
        setup_input="Leg length — standing, floor to crotch (cm)",
        what_youre_testing="Whether the range is defended by muscle or only propped up from "
                           "outside. Your body will not let a muscle relax into a position it "
                           "cannot support, so end-range strength is not something running "
                           "alongside flexibility — it is what permits it.",
        safety="**If your isometric number comes out as wide as your passive one, the load "
               "is too light** and passive tissue absorbed it — you have measured passive "
               "twice. Take weight off and repeat.",
    ),
    "spectrum_passive": BatteryTest(
        key="spectrum_passive", slot=_b.SLOT_SPECTRUM,
        label="Passive — split, supported", unit="cm",
        setup="Side split with a bench or blocks taking your upper body weight, legs "
              "relaxed. **Go to firm resistance, not to the floor.** Unlike the hands-off "
              "hold you just did, here the support carries you and the legs do nothing.",
        lock="Legs stay relaxed — this is the one trial where you are not holding yourself "
             "up. **The tell: if you are working to stay there, you are measuring the "
             "isometric again and the trial is void.** Let the support take the weight.",
        measurement="Measure along the floor from the inside of one heel to the inside of "
                    "the other, to the nearest half centimetre. Bigger is deeper.",
        input_hint="The distance between the inside of one heel and the inside of the "
                   "other, in cm",
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
    "leverage_bent", "leverage_straight",          # leverage_90 deferred
    "tilt_production", "tilt_range",
    "spectrum_active", "spectrum_isometric", "spectrum_passive",
)

AVAILABLE_TESTS: tuple[str, ...] = tuple(k for k in TEST_ORDER if TESTS[k].available)
DEFERRED_TESTS: tuple[str, ...] = tuple(k for k, t in TESTS.items() if not t.available)


def applicable_tests(assessment=None) -> tuple[str, ...]:
    """The tests a SESSION actually asks for, given what it has measured so far.

    NO RULES TODAY. The only one there has ever been belonged to gate 0, which
    was removed on 2026-08-12 (see REMOVED_GATE_0) — every remaining test is
    asked every session. Kept as the seam rather than inlined at the call sites:
    when a rule comes back it belongs here, so the capture flow and the
    evaluators cannot disagree about which tests a session owes.
    """
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

#: Why a test that applicable_tests dropped was dropped, in the athlete's
#: language — the capture flow shows this instead of the step.
SKIP_NOTES: dict[str, str] = {}

#: A leverage reading at or past its target counts as a pass. PROVISIONAL for
#: the same reason — every threshold here moves once three baseline mornings
#: exist and the noise floor is known.
LEVERAGE_TARGETS: dict[str, float] = {
    "leverage_bent": 10.0,        # cm floor-to-calf, smaller is better
    "leverage_straight": 90.0,    # cm ankle-to-ankle, bigger is better
}

#: The torso-to-leg angle, sitting with the legs straight. SMALLER IS BETTER,
#: and the scale is the athlete's own (2026-08-12): 0° is the stomach on the
#: floor with the legs straight, 90° is sitting bolt upright, 180° is lying flat
#: on the back. He measured 93° under his own power — "I cant even get over my
#: hips to start the pancake stretch, I am slightly behind".
#:
#: 90° IS NOT INVENTED, which makes it the least arbitrary threshold in this
#: file. It is the geometric point where the movement begins: past it the torso
#: is forward of vertical and the fold has started; short of it you are leaning
#: backwards and have not begun. His own framing, used as the line.
#: PROVISIONAL still, in the B5 sense — it moves once three baseline mornings
#: show his spread, and note his helped reading of 89° clears it by 1°, which is
#: inside any plausible noise floor. That is what BatteryResult.trusted is for.
TILT_TARGET_DEG: float = 90.0


def floor_gap_from_span(span_cm, leg_length_cm):
    """How high off the floor a side split of `span_cm` puts you, given the
    athlete's standing leg length. Returns None when it cannot be computed.

    WHY THE READINGS ARE WIDTHS AND THE THRESHOLDS ARE STILL HEIGHTS (athlete,
    2026-08-12): finding the crotch by eye mid-split is not repeatable, and it
    was the number he was asked for every session. The heels are unambiguous. So
    he measures the width, and the one crotch measurement that survives is taken
    ONCE, standing, where a tailor takes it.

    Each leg is the hypotenuse from crotch to floor contact, so with half the
    span as one side, `gap = sqrt(L^2 - (span/2)^2)`.

    THE CONVERSION IS SHARP WHERE HE IS AND BLUNT WHERE HE IS NOT, which is the
    opposite of the worry and worth writing down. Per 1 cm of error in the width,
    at leg length 84-88 cm:

        60 cm off the floor   0.5 cm of height     <- him today
        30 cm                 1.3 cm
        15 cm                 2.9 cm
         5 cm                 8.8 cm

    REVERT CONDITION, in the HRV_GARMIN_HOLD idiom: when a reading lands inside
    ~25 cm this stops being good enough and the spectrum comparison needs a
    directly measured floor-to-crotch gap rather than one derived from a width.
    Gated on the READING, not on a date.
    """
    if not span_cm or not leg_length_cm or leg_length_cm <= 0:
        return None
    half = float(span_cm) / 2.0
    if half >= float(leg_length_cm):
        return None            # wider than two legs — a mismeasure, not a split
    return math.sqrt(float(leg_length_cm) ** 2 - half ** 2)


def leg_length(assessment):
    """The athlete's recorded leg length for this session.

    ASKED ONCE PER SESSION, NOT ONCE PER SPLIT. It lived on gate 0 until gate 0
    was removed (REMOVED_GATE_0, 2026-08-12); the spectrum is now the only thing
    that needs it, and spectrum_isometric is the first split that runs, so it
    owns the number and the passive trial reads it back. Re-asking at the
    passive would invite a second, differently-eyeballed value for one quantity,
    which is the failure the recorded-setup convention exists to prevent.
    """
    r = assessment.reading("spectrum_isometric") if assessment is not None else None
    return r.setup_value if r is not None else None


def _spectrum_gap(reading, leg_length_cm):
    """A spectrum split width as a floor-to-crotch gap — the athlete measures
    heels, the thresholds are depths."""
    if reading is None:
        return None
    return floor_gap_from_span(reading.value, leg_length_cm)

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

    # SMALLER IS BETTER: the reading is the angle between the legs and the
    # torso, so 0° is folded flat and 90° is upright. A reading ABOVE the target
    # means he has not got over his hips at all. Flipped 2026-08-12 with the
    # measurement itself — see B9.
    if rng.value > TILT_TARGET_DEG:
        return b.SlotResult(slot=b.SLOT_PREREQUISITE, passed=False, pattern="F",
                            basis=b.BASIS_PROVISIONAL,
                            reason="The position is not available even with help. Tilt work "
                                   "goes FIRST in the session and starts assisted — you "
                                   "cannot train actively into a position you cannot reach.",
                            readings=(rng, prod))
    if prod.value > TILT_TARGET_DEG:
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

    # Both splits are recorded as WIDTHS and compared as DEPTHS, for the reason
    # gate 0 is: SPECTRUM_GAP_CM is a distance off the floor, and the same depth
    # difference is a different width at every depth. See floor_gap_from_span.
    length = leg_length(assessment)
    iso_gap = _spectrum_gap(iso, length)
    passive_gap = _spectrum_gap(passive, length)
    if iso_gap is None or passive_gap is None:
        return b.SlotResult(slot=b.SLOT_SPECTRUM, passed=False, indeterminate=True,
                            reason="The split widths cannot be turned into depths without "
                                   "the leg length recorded at gate 0, and the comparison "
                                   "below is a distance off the floor. A missing "
                                   "measurement is not a pass.",
                            readings=(iso, passive))

    # Split depths: smaller is deeper. The isometric must come out SHALLOWER
    # than passive, or the load was too light and passive tissue absorbed it.
    if not b.isometric_is_shallower(passive_gap, iso_gap, smaller_is_better=True):
        return b.SlotResult(slot=b.SLOT_SPECTRUM, passed=False, indeterminate=True,
                            basis=b.BASIS_RELATIVE,
                            reason="The isometric reading is as deep as the passive one, so "
                                   "the load was too light — you measured passive twice. "
                                   "Take weight off and repeat before reading this slot.",
                            readings=(iso, passive))

    gap = iso_gap - passive_gap
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
    rng_frac = b.fraction_of_target(rng.value if rng else None, TILT_TARGET_DEG,
                                    smaller_is_better=True)
    prod_frac = b.fraction_of_target(prod.value if prod else None, TILT_TARGET_DEG,
                                     smaller_is_better=True)

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

    # Shown as DEPTHS, like gate 0's rung: the widths are what he measured, the
    # depths are what the rung is read against.
    length = leg_length(assessment)
    iso_gap = _spectrum_gap(iso, length)
    passive_gap = _spectrum_gap(passive, length)

    # RELATIVE, and the one rung that needs no invented number: the fraction is
    # the athlete's own held depth over his own passive depth.
    depth_frac = None
    if iso_gap is not None and passive_gap is not None and iso_gap > 0:
        depth_frac = max(0.0, min(1.0, passive_gap / iso_gap))
    open_frac = b.fraction_of_target(active_sum, 180.0)

    unreadable = (slot3 is not None and slot3.indeterminate
                  and "too light" in slot3.reason)
    if unreadable:
        add("end_range", b.RUNG_UNREADABLE, measured=iso_gap, target=passive_gap,
            detail="The load was too light — passive measured twice. Repeat "
                   "before reading this rung.")
    elif slot3 is not None and not slot3.indeterminate and iso_gap is not None:
        add("end_range",
            b.RUNG_LIMITING if slot3.pattern == "H" else b.RUNG_PASSED,
            pattern="H" if slot3.pattern == "H" else "",
            measured=iso_gap, target=passive_gap, fraction=depth_frac,
            detail=f"Holds {iso_gap:.0f} cm off the floor against a passive "
                   f"{passive_gap:.0f} cm — your own reading is the yardstick.")
    elif iso_gap is not None and passive_gap is not None:
        add("end_range", b.RUNG_CONTEXT, measured=iso_gap, target=passive_gap,
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
