"""
flexibility_baselines.py — skills, their ladders, and the 13 rung tests.

REWRITTEN 2026-08-05 (v2). The v1 model in this file scored eight body regions
and averaged them. That is the wrong shape and it failed in a specific, provable
way: the `hip` score averaged fourteen contributions across five unrelated
capacities, and Deep Lunge — the ONLY thing testing hip extension, the athlete's
single worst documented capacity — scored 100 and was carried by healthy rungs.
The athlete's own objection killed it:

    "we know my hips are stuck in flexion with my back arched and this is a huge
     issue for me, and yet my flexibility score is nearly 80 for hips"

THE MODEL NOW
-------------
A SKILL is a position you can either achieve or not ("hip mobility" is as
meaningless as "hip strength" — the joint does too many things). Under each
skill is a LADDER of candidate limiters. Only the LOWEST rung limits the skill,
so the skill's score is min(rungs), and the name of that rung is published
beside it. Fix it, re-test, and the limiter moves to the next one — that
re-pointing IS the training programme.

Regions are therefore DIAGNOSTICS, never a score. Nothing here is averaged.

THREE MEASURES PER RUNG, AND THE GAP IS THE POINT
-------------------------------------------------
Each rung is measured three ways in the same position:

    PASSIVE    gravity or hands put you there      -> the ceiling
    ISOMETRIC  can you hold it once you are there  -> is the range defended
    ACTIVE     can you pull yourself in unassisted -> the usable range

PASSIVE - ACTIVE is the number that matters for THIS athlete. The source method
this is built on is written for people who LACK range; at Beighton 6/9 the
assisted half of it solves a problem he does not have. A wide gap means the
range exists and cannot be held, so more stretching is the wrong lever and
resisted/isometric work is the right one. That single number decides whether a
rung needs RANGE or STRENGTH — the question v1 could not answer at all.

This replaces v1's `CONTROL` axis, which asked the athlete to self-rate whether
he "owned" a position. Two objective readings beat one subjective rating.

EVERY TEST NAMES A LOCK
-----------------------
The `lock` field is the thing that must not move. An unlocked joint lets a
neighbour substitute and the test measures nothing — which is precisely the
failure that broke this model twice. Four tests REPLACE a standard test that is
contraindicated for this athlete, with something measuring the same capacity
safely; they are marked `replaces`.

Measurements are taped DISTANCES wherever possible rather than eyeballed
angles, because a distance is what one person alone reproduces in three months.

MEASURE COLD
------------
No warm-up, ever. A warm reading measures the viscoelastic effect, which is
gone within hours; a cold reading isolates the durable change. This is the
difference between tracking progress and tracking whether he happened to
stretch that morning.

Source: 13 test protocols from a 3-designer / 3-reviewer design pass,
2026-08-05, reconciled against patient_profile.py and services/rules.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# ── measures ─────────────────────────────────────────────────────────────────

PASSIVE = "passive"
ISOMETRIC = "isometric"
ACTIVE = "active"
MEASURES: tuple[str, ...] = (PASSIVE, ISOMETRIC, ACTIVE)


@dataclass(frozen=True)
class RungTest:
    """One ladder rung and how it is measured.

    `value_at_100` and `value_at_0` bracket the scale and MAY RUN IN EITHER
    DIRECTION — several tests measure a gap that shrinks as capacity improves
    (elbows to floor: 0 cm is perfect, 30 cm is the floor), while others measure
    a distance that grows (knee-to-wall: 12 cm is perfect, 0 cm is the floor).
    `services.flexibility.rung_score` interpolates between them and therefore
    handles both without a special case.
    """
    key: str
    label: str
    test_name: str
    unit: str
    value_at_100: float
    value_at_0: float
    setup: str
    lock: str
    measurement: str
    bilateral: bool
    safety: str
    replaces: str = ""

    @property
    def inverted(self) -> bool:
        """True when a SMALLER reading is better."""
        return self.value_at_100 < self.value_at_0


#: The 13 rungs. Keys are stable and are referenced by SKILLS below.
RUNGS: dict[str, RungTest] = {
    "hip_flexors": RungTest(
        key="hip_flexors", label="Hip flexors",
        test_name="Bench-edge modified Thomas, tested knee STRAIGHT — thigh angle by inclinometer",
        unit="°", value_at_100=15.0, value_at_0=-20.0, bilateral=True,
        setup="Sit on the very edge of a bench or firm bed, roll back and draw BOTH knees to "
              "the chest, then lower the tested leg. Hug the other knee to the chest. The "
              "tested KNEE STAYS STRAIGHT — a bent knee puts rectus femoris on stretch and "
              "turns a hip-extension test into a quad test, which is the quads rung's job.",
        lock="The hugged knee holds the pelvis in posterior tilt, and the bench edge must sit "
             "at the gluteal fold so the thigh is free to drop BELOW horizontal. If the low "
             "back lifts off the bench the reading is void. Hug with the ARMS, never lift with "
             "the hip — that is the contractile Coxa Saltans trigger (finding #4).",
        measurement="Phone strapped flat along the front of the tested thigh as an "
                    "inclinometer, zeroed against the bench surface. Read the thigh angle "
                    "relative to horizontal — below horizontal is positive hip extension, "
                    "above it is a flexion contracture. L and R separately, to 1°.",
        safety="The athlete's stated #1 problem: 'my hips are stuck in flexion with my back "
               "arched'. A test that lets the low back arch measures nothing here, so the "
               "posterior-tilt lock is the entire protocol rather than a detail.",
        replaces="the FLOOR version of the modified Thomas test, where the floor blocks the "
                 "thigh at 0° and every result below neutral is censored to the same value",
    ),
    "quads": RungTest(
        key="quads", label="Quads / rectus femoris",
        test_name="Side-lying rectus femoris — heel to buttock, pelvis hugged shut",
        unit="cm", value_at_100=0.0, value_at_0=25.0, bilateral=True,
        setup="Side-lying on the floor. Draw the BOTTOM hip and knee up and hold that knee "
              "with the bottom hand. Bend the top knee and draw the heel toward the buttock.",
        lock="The hugged bottom knee — it posteriorly tilts the pelvis and rounds the low "
             "back, which is what stops the lumbar spine substituting for quad length.",
        measurement="Photo from behind, phone on a marked spot, ruler upright in frame. Gap "
                    "from the back of the heel to the gluteal fold, to 0.5 cm.",
        safety="Rectus femoris crosses both hip and knee, so it appears on two ladders.",
        replaces="the prone Ely / prone quad stretch — a restricted rectus femoris in prone "
                 "tilts the pelvis anteriorly and drives lumbar extension, which is "
                 "contraindicated here",
    ),
    "calves_ankle": RungTest(
        key="calves_ankle", label="Calves / ankle",
        test_name="Knee-to-wall lunge, arch-controlled",
        unit="cm", value_at_100=12.0, value_at_0=0.0, bilateral=True,
        setup="Barefoot. Tape a strip perpendicular to a wall with a tape measure along it, "
              "zeroed AT the wall. Tested foot on the line, second toe pointing at the wall. "
              "Drive the knee forward to touch the wall with the heel flat.",
        lock="The ARCH. Pes planus buys apparent dorsiflexion by collapsing the midfoot and "
             "subtalar joint instead of moving the ankle — the arch must be held, or the "
             "test reads foot collapse as ankle range.",
        measurement="Greatest toe-to-wall distance at which the knee still touches with the "
                    "heel flat, to 0.5 cm.",
        safety="Documented pes planus makes the arch the whole protocol here, not a footnote.",
    ),
    "hamstrings": RungTest(
        key="hamstrings", label="Hamstrings",
        test_name="Passive supine straight-leg raise — phone inclinometer on the shin",
        unit="°", value_at_100=90.0, value_at_0=0.0, bilateral=True,
        setup="Supine on the floor, both legs straight, low back flat, arms at the sides. "
              "Phone strapped to the shin as an inclinometer. Raise one straight leg to firm "
              "resistance.",
        lock="The opposite leg — its heel and the back of its thigh stay in floor contact for "
             "the whole trial, or the pelvis has rotated and the number is not hamstring length.",
        measurement="Maximum angle in degrees at firm resistance, to 1°.",
        safety="Long-sitting upright is already ~90° of hip flexion with the knee straight, so "
               "the 2026-08-05 finding — normal length with NO RESERVE — predicts a reading "
               "near 90 rather than a low one.",
        replaces="the seated forward fold, sit-and-reach and standing toe-touch, all "
                 "contraindicated in rules.py (end-range lumbar flexion loads the covered "
                 "annulus tears at L3/4 and L4/5)",
    ),
    "adductors": RungTest(
        key="adductors", label="Adductors",
        test_name="Supine butterfly — knee-to-floor height at a fixed heel position",
        unit="cm", value_at_100=0.0, value_at_0=25.0, bilateral=True,
        setup="Supine, low back pressed flat, soles together, knees falling out to the sides. "
              "Draw the heels in to a marked position and leave them there.",
        lock="Heel position marked on the floor PLUS the flat low back — sliding the heels out "
             "makes the knees drop without any change in adductor length.",
        measurement="Tape held vertically beside each knee in turn; vertical gap from the floor "
                    "to the lateral aspect of the knee, L and R separately.",
        safety="Passive floor-supported hip flexion + external rotation, which the 2026-08-05 "
               "finding established is NOT a Coxa Saltans risk position — the trigger is "
               "contractile, not positional.",
    ),
    "hip_rotation": RungTest(
        key="hip_rotation", label="Hip rotation",
        test_name="Seated bench-edge hip INTERNAL rotation — shank tilt by inclinometer",
        unit="°", value_at_100=40.0, value_at_0=0.0, bilateral=True,
        setup="Sit on the EDGE of a bench with both knees at 90° and the shins hanging free, "
              "sitting tall with even weight on both sit bones and both hands gripping the "
              "bench. Swing the foot outward, keeping the thigh still.",
        lock="Even weight on both sit bones plus the grip — letting the pelvis rotate turns "
             "hip internal rotation into trunk rotation. The free-hanging shin is what lets "
             "an inclinometer read the tilt directly instead of inferring it from a "
             "floor-blocked distance and a frozen shin length.",
        measurement="Phone strapped to the shin, zeroed with the shank vertical. Read the tilt "
                    "in degrees at end range, L and R separately, to 1°.",
        safety="Internal rotation is the SAFE direction for finding #4 — the trigger is "
               "external rotation under ACTIVE hip flexion, and this is neither. Confirmed by "
               "the 2026-08-05 negative finding that passive flexion + external rotation "
               "produced no snap at all.",
    ),
    "shoulders_overhead": RungTest(
        key="shoulders_overhead", label="Shoulders overhead",
        test_name="Supine shoulder flexion — straight arms, thumbs up, towel-gauged lumbar lock",
        unit="°", value_at_100=170.0, value_at_0=0.0, bilateral=True,
        setup="Supine on a bare hard floor or the SAME thin mat every session, knees bent, "
              "feet flat. A folded hand towel of FIXED, RECORDED thickness under the lumbar "
              "spine. Arms start at the sides, ELBOWS LOCKED STRAIGHT and THUMBS POINTING AT "
              "THE CEILING. Raise both arms overhead toward the floor behind the head.",
        lock="The towel, and it is binary and externally detectable: it is compressed at the "
             "start and the trial is VOID the moment a finger slides under it. That matters "
             "specifically here — symptom_log 2026-07-06 records that this athlete's internal "
             "sense of neutral is calibrated to his habitual anterior tilt, so 'low back flat' "
             "is precisely the judgement he gets wrong. It is also the L5/S1 safety gate.",
        measurement="One photo per side from that side, phone on a marked spot at floor level "
                    "≥1.5 m away, a ruler upright beside that wrist. Read the floor-to-ulnar-"
                    "styloid gap, then derive flexion = 180 − arcsin(gap / L), where L is the "
                    "acromion-to-styloid length frozen at session 1. The cm is the record; the "
                    "angle is what scores.",
        safety="Unloaded and self-limited. NEVER a partner pressing the arms down — passive "
               "end-range pressure into a post-Latarjet shoulder whose stability is muscular "
               "rather than ligamentous (finding #6). This is the athlete's own failed test: "
               "he cannot rest both elbows on the floor with the arms overhead.",
    ),
    "lats": RungTest(
        key="lats", label="Lats",
        test_name="Supine unilateral overhead reach at FULL posterior pelvic tilt",
        unit="°", value_at_100=160.0, value_at_0=0.0, bilateral=True,
        setup="Supine with the hips and knees at 90° and the feet flat on a wall or a chair "
              "seat — that holds the pelvis in FULL posterior tilt hands-free, which is more "
              "than the 'flat' the shoulders_overhead test gauges with a towel. One arm at a "
              "time, elbow locked straight, thumb at the ceiling, reaching overhead toward "
              "the floor behind the head.",
        lock="The feet on the wall, plus the low back pressed hard into the floor. Rounding "
             "the lumbar spine IS the isolation mechanism here, not just a safety gate: of "
             "the three tissues that limit an overhead reach — pec major, subscapularis with "
             "teres major, and lats — the lats are the ONLY ones crossing the lower back, so "
             "taking the lumbar spine into full flexion puts them on stretch relative to the "
             "other two. Unilateral, so the other side cannot compensate.",
        measurement="Same read as shoulders_overhead: photo from that side, floor-to-ulnar-"
                    "styloid gap in cm, converted with the same frozen acromion-to-styloid "
                    "length L. L and R separately, to 0.5 cm.",
        safety="ANCHOR IS PROVISIONAL AND STRICTER THAN THE PUBLISHED NORM. The supine "
               "lat-length test is normally defined against a FLAT lumbar spine, where full "
               "shoulder flexion is the pass; this uses full posterior tilt, which is harder. "
               "160° is set as the ceiling on that reasoning rather than from a source, so "
               "the number is comparable with itself over time but NOT with a published norm "
               "— revisit once there are two or three sessions to look at. Unloaded and "
               "self-limited, no partner pressing the arm down (finding #6).",
    ),
    "chest_horizontal": RungTest(
        key="chest_horizontal", label="Chest / pecs",
        test_name="Wall slide — goalpost start-position contact (the athlete's own drill)",
        unit="cm", value_at_100=0.0, value_at_0=15.0, bilateral=True,
        setup="Back to a wall, heels 10-15 cm out, knees soft. Press the low back flat and pin "
              "a sheet of A4 paper between the low back and the wall. Bring the arms to a "
              "goalpost position and take them back toward the wall.",
        lock="The pinned A4 sheet — self-verifying, because it drops the moment the low back "
             "arches. Arching is how the shoulders reach the wall without any pec length.",
        measurement="Horizontal gap from the wall to the back of the WRIST CREASE, L and R "
                    "separately, to 0.5 cm.",
        safety="The athlete already reports this drill as difficult, and it is the one place "
               "the gym's 'Chest 106° Low' reading has a live successor.",
        replaces="the doorway pec stretch and the supine 90/90 pec stretch — both hang the "
                 "anterior capsule on an external frame, which is the apprehension position "
                 "for this shoulder",
    ),
    "thoracic_rotation": RungTest(
        key="thoracic_rotation", label="Thoracic rotation",
        test_name="Side-lying modified open book — arms folded, top-shoulder descent",
        unit="°", value_at_100=45.0, value_at_0=0.0, bilateral=True,
        setup="Side-lying, hips and knees stacked and bent to 90°, knees resting on a folded "
              "towel of the SAME thickness every time. Arms folded across the chest. Rotate "
              "the top shoulder back toward the floor.",
        lock="The pelvis — the bottom hand presses the top knee down and it must stay stacked. "
             "An unlocked pelvis turns thoracic rotation into a lumbar roll.",
        measurement="Vertical height from the floor to the top acromion at start (frozen at "
                    "session 1) and at end range; the drop converts to degrees.",
        safety="Arms FOLDED, not swept out to the floor behind — the classic open book ends in "
               "90° abduction plus horizontal extension, the apprehension position.",
        replaces="the classic open book with the top arm sweeping to the floor",
    ),
    "lumbar": RungTest(
        key="lumbar", label="Lumbar control",
        test_name="Supine lumbar flattening — residual floor-to-lumbar gap",
        unit="cm", value_at_100=0.0, value_at_0=5.0, bilateral=False,
        setup="Supine, both legs straight and together, arms at the sides, alongside a wall "
              "with a 30 cm ruler taped upright at hip level. Actively flatten the low back "
              "to the floor.",
        lock="The feet and glutes — pushing through the heels turns the test into a leg press "
             "and flattens the back without any lumbar control.",
        measurement="Side-on photo from ≥1.5 m, phone on a marked spot at floor level, ruler in "
                    "frame. Maximum vertical gap between the floor and the low back.",
        safety="A posterior pelvic tilt is exactly what finding #3's training implication "
               "prescribes to decompress the L5/S1 horizontal facet slides. Safe, and useful.",
    ),
    "lateral_trunk": RungTest(
        key="lateral_trunk", label="Lateral trunk",
        test_name="Wall-backed standing lateral flexion — fingertip travel",
        unit="cm", value_at_100=20.0, value_at_0=0.0, bilateral=True,
        setup="Heels, buttocks, upper back and head all touching a wall, feet on a traced floor "
              "mark at hip width, arms hanging with palms flat against the outside of the "
              "thighs. Slide one hand down the leg.",
        lock="The wall — four points of contact. Coming off the wall converts side-bend into "
             "flexion or rotation.",
        measurement="Pen-mark the trouser seam at rest and at end range; measure the travel, "
                    "L and R separately, to 0.5 cm.",
        safety="rules.py rates side bending CAUTION in BOTH directions for DIFFERENT reasons — "
               "right narrows the stenotic right L5/S1 foramen, left loads the dorsolateral "
               "protrusions at L3/4 and L4/5. Light, self-generated, no reaching overhead.",
    ),
    "neck": RungTest(
        key="neck", label="Neck (rotation)",
        test_name="Supine cervical rotation to first firm resistance — inclinometer on the forehead",
        unit="°", value_at_100=80.0, value_at_0=0.0, bilateral=True,
        setup="Supine on a bare hard floor or the SAME thin mat every session, knees bent, "
              "feet flat, arms at the sides. Phone strapped flat across the forehead with a "
              "headband, levelled and zeroed face-up with the chin level. Turn the head slowly "
              "to one side and stop at FIRST FIRM RESISTANCE — not as far as it will go.",
        lock="Bodyweight plus the shoulder blades: both stay in floor contact for the whole "
             "trial, which mechanically removes the trunk rotation a seated version has to "
             "police. The chin stays level — tipping it buys apparent rotation, so record "
             "pitch as well and void the trial if it moved more than 5°.",
        measurement="Roll angle in degrees off the phone at first firm resistance, to 1°, L "
                    "and R separately. Two attempts per side: the first is familiarisation, "
                    "RECORD THE SECOND.",
        safety="ACTIVE and self-generated only — NO hand overpressure on the head, ever. At "
               "Beighton 6/9 the cervical spine is the last place to hang on ligament. Stopped "
               "at first firm resistance rather than end range until the hEDS/HSD assessment "
               "is done (patient_profile joint_notes: 'Possible HSD/hEDS-spectrum — not yet "
               "assessed against 2017 criteria'), because craniocervical laxity is the one "
               "thing that would matter here — put that question on the 2026-08-16 agenda. "
               "NOTE THE GAP: cervical FLEXION is this athlete's documented dominant "
               "restriction (symptom_log 2026-07-31, markedly left-dominant) and is "
               "deliberately NOT measured on safety grounds, so this rung will not move when "
               "his actual neck problem moves.",
        replaces="a seated chin-to-acromion tape reading, whose own lock required both hands "
                 "on the seat while its measurement required holding a tape",
    ),
    "squat_depth": RungTest(
        key="squat_depth", label="Squat depth",
        test_name="Bodyweight squat to first loss of neutral spine — hip crease vs knee height",
        unit="cm", value_at_100=5.0, value_at_0=-20.0, bilateral=False,
        setup="Barefoot, feet on a traced floor outline. Trace the feet ONCE, photograph the "
              "outline, and reproduce the stance width and toe-out angle exactly every session. "
              "Descend to the first loss of a neutral spine and stop there.",
        lock="The traced outline — stance width and toe-out are the single largest source of "
             "session-to-session drift in this test.",
        measurement="Side-on photo at the deepest neutral-spine position, phone at ~knee height "
                    "≥1.5 m away, tape taped vertically to the wall behind. Height of the hip "
                    "crease relative to the top of the kneecap; below = positive.",
        safety="Bodyweight only, never loaded. This is a COMPOSITE and is interpreted, not "
               "independent — it is downstream of calves_ankle, adductors and hip_rotation, so "
               "a low reading here is a symptom whose cause is one of those rungs.",
    ),
}


@dataclass(frozen=True)
class Skill:
    """A goal position, and the ladder of rungs that could be limiting it.

    `goal_level` is the rung level every rung must reach for the skill to be
    considered achieved. `excluded_reason`, when set, means the skill is
    tracked but must never be trained toward.
    """
    key: str
    label: str
    ladder: tuple[str, ...]
    goal_level: float
    gates: str
    note: str = ""
    excluded_reason: str = ""

    @property
    def excluded(self) -> bool:
        return bool(self.excluded_reason)


#: The four in-scope skills, chosen for transfer to the lifts already in the
#: block rather than for gymnastics. The athlete's stated aim is to get "the
#: muscle pulling in the right direction with nothing restricted" so his lifts
#: work — not the splits.
SKILLS: dict[str, Skill] = {
    "deep_squat": Skill(
        key="deep_squat", label="Deep squat",
        ladder=("calves_ankle", "adductors", "hip_rotation", "lumbar", "quads"),
        goal_level=70.0,
        gates="Goblet squat, Bulgarian split squat",
        note="squat_depth is the OUTCOME of this ladder, not a rung in it — including it "
             "would let the symptom vote on its own diagnosis.",
    ),
    "hip_extension": Skill(
        key="hip_extension", label="Hip extension",
        ladder=("hip_flexors", "quads", "lumbar"),
        goal_level=70.0,
        gates="Hip thrust, RDL lockout, lunge",
        note="The athlete's stated #1 problem: 'my hips are stuck in flexion with my back "
             "arched'. lumbar is on this ladder because arching is how hip extension gets "
             "faked, so a good lumbar score is a precondition for trusting hip_flexors.",
    ),
    "shoulder_flexion": Skill(
        key="shoulder_flexion", label="Shoulder flexion",
        ladder=("shoulders_overhead", "lats", "chest_horizontal", "thoracic_rotation",
                "lumbar"),
        goal_level=70.0,
        gates="Overhead work (currently prohibited), lat pulldown path",
        note="The three tissues that limit an overhead reach now have a rung each: "
             "chest_horizontal for pec major, lats for latissimus, and thoracic_rotation for "
             "the segment they both act across, with shoulders_overhead as the composite the "
             "athlete actually fails. READ THEM TOGETHER: if shoulders_overhead is low AND "
             "lats is low, the lat is the limiter; if shoulders_overhead is low while lats is "
             "fine, it is pec or capsule. That comparison is the reason the lat rung exists — "
             "the composite alone cannot say which tissue stopped it.",
    ),
    "active_pike": Skill(
        key="active_pike", label="Active pike",
        ladder=("hamstrings", "lumbar"),
        goal_level=70.0,
        gates="RDL, hinge pattern",
        note="The PASSIVE version is already achieved — palms flat to floor is a Beighton "
             "positive — and is also contraindicated as a test (seated forward fold). The "
             "active version is unmeasured, and that gap is the whole thesis of this model.",
    ),
    # ── tracked, never trained toward ────────────────────────────────────────
    "bridge": Skill(
        key="bridge", label="Bridge",
        ladder=("hip_flexors", "shoulders_overhead", "thoracic_rotation"),
        goal_level=70.0,
        gates="—",
        excluded_reason="End-range lumbar extension against L5/S1 retrolisthesis and activated "
                        "osteochondrosis; services.rules already contraindicates "
                        "'hyperextension' and 'back extension'. Its COMPONENTS are exactly what "
                        "this athlete needs and remain rungs elsewhere — only the composite "
                        "goal is refused.",
    ),
    "shoulder_extension": Skill(
        key="shoulder_extension", label="Shoulder extension",
        ladder=("chest_horizontal", "shoulders_overhead"),
        goal_level=70.0,
        gates="—",
        excluded_reason="The apprehension direction for an anterior-instability shoulder "
                        "post-Latarjet (finding #6). Tracked so regression is visible; never a "
                        "target to maximise.",
    ),
}

#: Skills that may be trained toward.
ACTIVE_SKILLS: tuple[str, ...] = tuple(k for k, s in SKILLS.items() if not s.excluded)


# ── the flexibility window ───────────────────────────────────────────────────
#
# From the athlete's source brief. The MECHANISM it offers (calcium accumulation
# -> calpain -> fibre damage -> inflammation -> central fatigue) is stated well
# past what the evidence carries and is recorded as MOTIVATION, NOT FACT — the
# same treatment services/sleep_fusion.py gives the abandoned quiet-wake rule.
# The scheduling heuristic is worth encoding regardless and is computable from
# the training log the app already holds.
#
# ADVISORY ONLY. Nothing here reaches the engine — not the traffic light, not
# ACWR, not readiness, not the volume recommendation.

WINDOW_GOOD = "good"
WINDOW_OK = "ok"
WINDOW_POOR = "poor"

WINDOW_RULES: dict[str, str] = {
    WINDOW_GOOD: "2+ days after hard sport or strength, or the same day PM after an AM session "
                 "(the fatigue signal has not landed yet)",
    WINDOW_OK:   "immediately after sport or strength, with the volume of both reduced",
    WINDOW_POOR: "the day after strength, or slotted into a rest day as 'active recovery' — "
                 "which the source argues it is not",
}

#: A rest day is the WORST slot for adaptation-seeking flexibility work and a
#: perfectly good slot for a restorative flow. Nothing in the codebase currently
#: distinguishes the two — views/training.py's suggest_for_day("rest_day") offers
#: a session on exactly the day this rule calls worst. Resolving that needs an
#: intent flag on the session, which is why this constant exists rather than a
#: silent assumption.
REST_DAY_CONFLICT_UNRESOLVED: bool = True


# ── provenance: what existed before v2 ───────────────────────────────────────

SCAN_DATE: date = date(2025, 1, 17)
AGE_AT_SCAN_YEARS: int = 30
VENDOR_BIOAGE_YEARS: int = 28
VENDOR_BIOAGE_COMPARED_AGAINST_AGE: int = 31


@dataclass(frozen=True)
class LegacyGymReading:
    """A 2025-01-17 gym goniometry row, kept as PROVENANCE ONLY.

    None of these enter a score. Their protocol is unrecorded — the screen
    printed degrees per region and never said which movement produced them — so
    'Hip 33°' corroborates a different clinical finding depending on whether it
    is internal rotation, abduction or a Thomas test. v1 assumed protocols and
    scored them anyway; v2 does not, and the v2 tests above supersede all five.
    """
    label: str
    left: float
    right: float
    vendor_verdict: str
    superseded_by: str
    note: str = ""


LEGACY_GYM_READINGS: tuple[LegacyGymReading, ...] = (
    LegacyGymReading("Neck", 30.0, 30.0, "Low", "neck",
                     "Exactly equal L/R while three other rows differ by 1-3°."),
    LegacyGymReading("Chest", 106.0, 106.0, "Low", "chest_horizontal",
                     "Exactly equal L/R is the least plausible reading on the sheet given "
                     "three right anterior dislocations and a Latarjet."),
    LegacyGymReading("Lat Flex", 20.0, 21.0, "Normal", "lateral_trunk",
                     "'Normal' at 20-21° contradicts the obvious reading of the label."),
    LegacyGymReading("Hip", 33.0, 32.0, "Low", "hip_rotation"),
    LegacyGymReading("Hamstrings", 89.0, 86.0, "Normal", "hamstrings",
                     "The one reading whose successor test measures the same thing the same "
                     "way; it predicts a v2 passive SLR near 90°."),
)


#: The 22 yoga depth-ratings from 2026-08-05. RETAINED IN FULL as a dated
#: historical instrument with the athlete's verbatim notes in
#: docs/training/Yoga_Library.md — and used by NOTHING.
#:
#: They answer a question that is neither passive range nor active range ("how
#: far did I get AND how much did I feel"), so reinterpreting any of them as an
#: achievement or a control reading would be inventing data. 0 of 13 rungs
#: inherit a value from them. A test pins that.
LEGACY_POSE_DEPTH_RATINGS_2026_08_05: dict[str, int] = {
    "Seated Cross-Legged Side Bend (Shoulder Drop)": 40,
    "Seated Side Stretch (Right)": 60, "Seated Side Stretch (Left)": 65,
    "90/90 Hip Rotation": 85, "Butterfly Forward Fold": 82,
    "Walk the Dog (Down Dog pedaling)": 76, "Deep Lunge (Right)": 57,
    "Deep Lunge Hip Opener (Right)": 46, "Half Pigeon Pose (Right)": 40,
    "Seated Twist (Left)": 66, "Down Dog": 64, "Deep Lunge (Left)": 57,
    "Deep Lunge Hip Opener (Left)": 46, "Half Pigeon Pose (Left)": 40,
    "Seated Twist (Right)": 68, "Straddle Forward Fold": 25,
    "Knee to Chest (Right)": 85, "Lying Twist (Right)": 85,
    "Knee to Chest (Left)": 88, "Lying Twist (Left)": 88,
    "Happy Baby": 80, "Deep Relaxation (Savasana)": 100,
}
LEGACY_DEPTH_RATING_DATE: date = date(2026, 8, 5)


# ── recorded assessments ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class RungReading:
    """One rung, one session. Any measure may be absent."""
    rung: str
    passive: float | None = None
    isometric: float | None = None
    active: float | None = None
    side: str = ""          # "left" | "right" | "" for midline
    note: str = ""


@dataclass(frozen=True)
class Assessment:
    taken_on: date
    readings: tuple[RungReading, ...] = field(default_factory=tuple)
    cold: bool = True
    note: str = ""


#: Every assessment ever run, oldest first. EMPTY — the standalone assessment
#: has not been run yet, which is the honest state: 0 of 13 rungs have a passive
#: reading, and 0 of 13 have an isometric or active one, so the gap metric that
#: is the entire point of v2 has no data at all. Until this list is non-empty,
#: the assessment is not an enhancement to the model — it IS the model.
ASSESSMENTS: tuple[Assessment, ...] = ()
