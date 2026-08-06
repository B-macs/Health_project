"""
flexibility_baselines.py — skills, their ladders, and the 14 rung tests.

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
failure that broke this model twice. Six tests REPLACE a standard test that is
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

    #: PLAIN ENGLISH IS A REQUIREMENT OF THE FOUR FIELDS ABOVE, not a nicety.
    #: `setup`, `lock`, `measurement` and `safety` are read by the athlete while
    #: he is lying on the floor holding a tape measure, and a test he
    #: misunderstands produces a number that looks valid and is not. The first
    #: draft of this file failed that: "the greatest toe-to-wall distance at
    #: which the knee still touches" never said WHAT the knee touches, and
    #: "binary and externally detectable" was not English. Anatomical names
    #: (supine, gluteal fold, lateral aspect, ulnar styloid, acromion) belong in
    #: `what_youre_testing`, never in the instructions. Nothing about this
    #: codebase — module names, what a test replaces, finding numbers, symptom
    #: log dates — belongs in ANY of them.
    what_youre_testing: str = ""

    #: True when this test's 0/100 anchors are OUR estimate rather than a
    #: published norm, so the score is comparable with the athlete's own history
    #: and NOT with anybody else's. A flag, not a phrase in `safety`: the first
    #: version asserted the word "PROVISIONAL" appeared in the prose, which made
    #: a plain-English rewrite of that prose look like a regression. The fact is
    #: data about the scale and belongs on the scale.
    anchor_provisional: bool = False

    #: Clinical provenance. NOT DISPLAYED to the athlete: which test this
    #: substitutes for is a decision that was already made for him, and reading
    #: it mid-assessment invites a "well, why not just do the normal one" that
    #: the contraindication answers and the sentence does not.
    replaces: str = ""

    @property
    def inverted(self) -> bool:
        """True when a SMALLER reading is better."""
        return self.value_at_100 < self.value_at_0


#: Shown once, before the first test, and available from every step. The three
#: measures are the whole model and they were previously explained NOWHERE the
#: athlete could see — the screen asked for three numbers per position and named
#: them with words that mean something specific in physiology and something else
#: in ordinary speech ("active" does not obviously mean "under your own power").
MEASURES_EXPLAINED: tuple[tuple[str, str, str], ...] = (
    (PASSIVE, "How far it goes when something else does the work",
     "Gravity, your hands, or a wall put you into the position. You are not "
     "pulling — you are letting it happen and stopping at firm resistance. This "
     "is your ceiling: the furthest the joint goes at all."),
    (ISOMETRIC, "Can you hold it once you are there",
     "Get to that same end position, then take away whatever put you there and "
     "hold still for a moment. Either you hold the position or you drop out of "
     "it. This says whether the range is defended by muscle or only propped up "
     "from outside."),
    (ACTIVE, "How far you can get under your own power",
     "Same position, no help at all — no hands, no wall, no swinging. Only your "
     "own muscles pulling you in. This is the range you can actually use in a "
     "lift or a sport, which is why it is the one that scores."),
)

#: The gap, in one sentence each, for the two directions it can point.
GAP_EXPLAINED: str = (
    "Passive minus active is the number that matters most for you. A BIG gap "
    "means the range is already there and you cannot hold it — stretching more "
    "will not help, and strength work in the position will. A SMALL gap means "
    "you are using nearly everything you have, and the range itself is what to "
    "chase. You are hypermobile, so the big-gap case is the one to expect."
)

#: Why the lock matters, and the answer to the obvious question about it.
#: The athlete asked directly: if the lock is lost, why not just redo the test?
#: The answer is that you can and you should — the difficulty is NOTICING, and
#: that is a design requirement on every lock rather than a note about one.
LOCK_EXPLAINED: str = (
    "Every test names a LOCK: one thing that must not move. It is there because "
    "your body will always find another joint to do the job — arch the back "
    "instead of opening the hip, collapse the arch instead of bending the "
    "ankle. That substitution does not feel like cheating; it feels like "
    "success, because you got further. **And that is the trap: a lost lock "
    "makes the number BETTER, not worse, so nothing warns you.** "
    "Yes — if you lose the lock, just reset and take the reading again. There "
    "is no limit and no penalty; a repeated trial is not a worse trial. That is "
    "why each lock has a TELL you can see or feel from outside — a towel that "
    "stops being squashed, a sheet of paper that drops, a heel that leaves the "
    "floor. Trust the tell, not the feeling. If you finish a trial and only "
    "then realise the lock went, tick 'void this trial' and do it again."
)

#: Measurements that must be identical between sessions or the comparison is
#: meaningless. Each is taken ONCE, written down, and re-used forever — the
#: number is the record, never a chalk mark or a piece of tape, because a mark
#: on a floor is gone by the next session and a mark that has moved silently
#: invalidates every reading taken against it. The athlete found the fourth one
#: below by reading the adductor protocol: it set the heels to "a marked
#: position" with nothing recording where that position was.
FROZEN_CONSTANTS: tuple[tuple[str, str], ...] = (
    ("arm_length_cm",
     "Shoulder-tip to wrist bone, arm straight. Converts the overhead and lat "
     "measurements from a floor gap into an angle."),
    ("shin_length_cm",
     "Knee joint line to the floor, sitting with the knee bent square. Used by "
     "the hip-rotation reading."),
    ("foot_outline",
     "Both feet traced on a sheet of card, photographed. Reproduces squat "
     "stance width and toe-out, which is the single biggest source of "
     "session-to-session drift in the squat test."),
    ("butterfly_heel_distance_cm",
     "Tailbone to the back of the heels in the butterfly position. THE NUMBER "
     "is the setup, not a mark on the floor: heels further away drop the knees "
     "without your groin being one millimetre longer, so a session that "
     "re-marks the floor by eye is not comparable with the last one."),
)

#: The 14 rungs. Keys are stable and are referenced by SKILLS below.
RUNGS: dict[str, RungTest] = {
    "hip_flexors": RungTest(
        key="hip_flexors", label="Hip flexors",
        test_name="Lying back off the edge of a bench, one knee hugged in",
        unit="°", value_at_100=15.0, value_at_0=-20.0, bilateral=True,
        setup="Sit right on the edge of a bench or a firm bed — the edge should be under the "
              "crease where your buttock meets your thigh. Roll back, pull both knees to your "
              "chest, then let the leg you are testing down toward the floor. Keep hugging the "
              "other knee. **Keep the lowered leg straight.** If you let that knee bend you "
              "start stretching the front of the thigh instead, and that is the next test, "
              "not this one.",
        lock="The knee you are hugging. It holds your pelvis still so your lower back stays "
             "pressed flat on the bench. **The tell: if your lower back lifts off the bench, "
             "the trial is void** — reset and take it again. Pull the knee in with your arms "
             "only, never by lifting with the hip itself, because working that hip actively is "
             "what sets your right hip clicking.",
        measurement="Strap your phone flat along the front of the lowered thigh and use it as "
                    "an angle meter, zeroed against the top of the bench. Read how far the "
                    "thigh sits above or below level. **Below level is a positive number and "
                    "is the good direction**; above level means the hip will not straighten "
                    "all the way. Left and right separately, to the nearest degree.",
        what_youre_testing="Whether your hip can straighten past neutral, or whether it is "
                           "held in a bent position even at rest. Anatomically this is the "
                           "modified Thomas test read off the thigh angle, done off a bench "
                           "edge so the thigh is free to drop below horizontal. It is the "
                           "capacity behind standing tall without arching, driving the hips "
                           "through at the top of a lift, and the back leg of a lunge.",
        safety="This is your stated number one problem — 'my hips are stuck in flexion with my "
               "back arched'. A test that lets your back arch measures nothing at all here, "
               "which is why the hugged knee is the whole protocol rather than a detail.",
        replaces="the FLOOR version of the modified Thomas test, where the floor blocks the "
                 "thigh at 0° and every result below neutral is censored to the same value",
    ),
    "quads": RungTest(
        key="quads", label="Quads / rectus femoris",
        test_name="Lying on your side, heel pulled toward your backside",
        unit="cm", value_at_100=0.0, value_at_0=25.0, bilateral=True,
        setup="Lie on your side on the floor. Pull your bottom knee up toward your chest and "
              "hold it there with your bottom hand. Now bend your top knee and pull that heel "
              "toward your backside, using your top hand on the ankle.",
        lock="The bottom knee you are hugging. Holding it in tips your pelvis and rounds your "
             "lower back, and that is what stops your spine arching to buy fake range. **The "
             "tell: if your lower back arches out of that rounded shape, or your top hip "
             "swings forward, the trial is void** — reset and take it again.",
        measurement="Photo from behind, phone on a marked spot, a ruler standing upright in "
                    "the shot. Measure the gap between the back of your heel and the crease "
                    "under your buttock. **Smaller is better — 0 cm means the heel touches.** "
                    "Left and right separately, to the nearest half centimetre.",
        what_youre_testing="The rectus femoris, the one thigh muscle that crosses both the hip "
                           "and the knee. Because it spans two joints it can limit two "
                           "different things — how deep you can squat, and how far your hip "
                           "can extend behind you — which is why it appears on more than one "
                           "list.",
        safety="Nothing here is loaded and nobody pushes on you. Stop at firm resistance; this "
               "is not a test of how much stretch you can tolerate.",
        replaces="the prone Ely / prone quad stretch — a restricted rectus femoris in prone "
                 "tilts the pelvis anteriorly and drives lumbar extension, which is "
                 "contraindicated here",
    ),
    "calves_ankle": RungTest(
        key="calves_ankle", label="Calves / ankle",
        test_name="Driving your knee forward to a wall, heel down",
        unit="cm", value_at_100=12.0, value_at_0=0.0, bilateral=True,
        setup="Bare feet. Run a strip of tape along the floor straight out from a wall, and "
              "lay a tape measure along it with **zero at the wall**. Put the foot you are "
              "testing on the line, second toe pointing straight at the wall. Bend that knee "
              "forward until it touches the wall, keeping your heel flat on the floor.",
        lock="Your arch. A flat foot can fake ankle range by rolling inward and collapsing "
             "instead of the ankle actually bending. **The tell: watch the inside of your "
             "foot — if the arch sinks toward the floor or your ankle rolls in, the trial is "
             "void** — reset and take it again.",
        measurement="Start with your toe close to the wall, where the knee reaches easily. "
                    "Move the foot back a little at a time and try again. **The reading is "
                    "the furthest your toe can be from the wall while your knee can still "
                    "touch the wall and your heel stays flat on the floor.** Bigger is "
                    "better. Left and right separately, to the nearest half centimetre.",
        what_youre_testing="How far your shin can travel forward over your foot — ankle "
                           "dorsiflexion. It is usually the first thing that stops a deep "
                           "squat: when the ankle runs out of room, either your heels lift or "
                           "your back rounds to keep your balance, and both of those look "
                           "like a hip problem when they are not.",
        safety="You have flat feet on record, which is exactly why the arch is the point of "
               "this test and not a footnote — without holding it you would be measuring your "
               "foot collapsing rather than your ankle bending.",
    ),
    "hamstrings": RungTest(
        key="hamstrings", label="Hamstrings",
        test_name="Lying on your back, raising one straight leg",
        unit="°", value_at_100=90.0, value_at_0=0.0, bilateral=True,
        setup="Lie on your back on the floor, both legs straight, lower back flat, arms by "
              "your sides. Strap your phone to your shin to use as an angle meter. Raise one "
              "leg, **keeping that knee locked straight**, until you feel firm resistance — "
              "not the furthest it will go if you push.",
        lock="The leg still on the floor. Its heel and the back of its thigh must stay in "
             "contact with the floor for the whole trial. **The tell: if that leg lifts off "
             "the floor or its knee starts to bend, your pelvis has rolled and you are no "
             "longer measuring the hamstring — the trial is void.**",
        measurement="Read the angle off the phone at firm resistance. Bigger is better. Left "
                    "and right separately, to the nearest degree.",
        what_youre_testing="Hamstring length, on its own, with the pelvis held still. Worth "
                           "knowing what 'normal' means here: sitting upright with your legs "
                           "straight out in front of you is already about 90 degrees. You "
                           "measured 86-89 at the gym, which is normal length with **no "
                           "reserve** — so every extra degree of a forward fold has to come "
                           "from your spine instead, which is exactly what you described.",
        safety="Raise the leg yourself and stop at firm resistance. Nobody pushes it further, "
               "and there is nothing to gain here from finding the furthest it will go.",
        replaces="the seated forward fold, sit-and-reach and standing toe-touch, all "
                 "contraindicated in rules.py (end-range lumbar flexion loads the covered "
                 "annulus tears at L3/4 and L4/5)",
    ),
    "adductors": RungTest(
        key="adductors", label="Adductors",
        test_name="Butterfly on your back — how far the knees drop",
        unit="cm", value_at_100=0.0, value_at_0=25.0, bilateral=True,
        setup="Lie on your back with your lower back pressed flat to the floor. Put the soles "
              "of your feet together and let your knees fall out to the sides. Pull your heels "
              "in toward you until you reach **your recorded heel distance** (tailbone to the "
              "back of the heels — see the frozen measurements), then leave them there and let "
              "the knees settle.",
        lock="Two things: where your heels are, and your lower back staying flat. Sliding the "
             "heels further away drops the knees without your groin being one millimetre "
             "longer. **The tell for the back is easy — if you can slide a hand under your "
             "waist, the trial is void. The tell for the heels is a number you measure, not a "
             "mark on the floor:** measure tailbone to the back of your heels each time and "
             "match the recorded figure. A chalk mark is gone by the next session, and a mark "
             "you have re-placed by eye makes the new reading impossible to compare with the "
             "old one — so if you did not check the number, treat the trial as void.",
        measurement="Hold a tape measure standing up beside each knee in turn. Measure the "
                    "gap from the floor up to **the outside of the knee**. Smaller is better "
                    "— 0 cm means the knee is resting on the floor. Left and right separately, "
                    "to the nearest half centimetre.",
        what_youre_testing="Your groin muscles, and how far the thigh bone can travel out to "
                           "the side while turned outward at the hip. This is what lets your "
                           "knees track out over your feet in a squat instead of caving in.",
        safety="You are fully supported on the floor and nothing is loaded. You confirmed on "
               "2026-08-05 that this position does not set your right hip clicking — that "
               "needs the hip working actively, not just being in the position.",
    ),
    "hip_rotation": RungTest(
        key="hip_rotation", label="Hip rotation",
        test_name="Sitting on a bench edge, swinging one foot outward",
        unit="°", value_at_100=40.0, value_at_0=0.0, bilateral=True,
        setup="Sit on the edge of a bench with both knees bent square and your shins hanging "
              "free — feet off the floor. Sit up tall with even weight on both sit bones and "
              "grip the bench with both hands. Now **keep your thigh completely still and "
              "swing that foot outward, away from your other leg.** Only the shin moves.",
        lock="Even weight on both sit bones, and your grip on the bench. **The tell: if one "
             "side of your backside lifts, or your body starts turning to follow the foot, "
             "you have stopped testing the hip and started turning your whole trunk — the "
             "trial is void.** Sit back down square and take it again.",
        measurement="Strap your phone to your shin, zeroed with the shin hanging straight "
                    "down. Read the tilt in degrees where the movement stops. Bigger is "
                    "better. Left and right separately, to the nearest degree.",
        what_youre_testing="How far the ball of your hip can turn inward inside its socket. "
                           "Swinging the foot **outward** is what turns the hip **inward** — "
                           "that feels backwards but it is correct, because the shin acts as "
                           "a lever below the knee. This is the range that lets you sit into "
                           "a deep squat without your knees collapsing inward.",
        safety="Turning the hip inward is the safe direction for your right hip. What sets it "
               "clicking is turning outward while the hip is working actively, and this is "
               "neither — confirmed on 2026-08-05, when no passive position produced a snap "
               "at all.",
    ),
    "shoulders_overhead": RungTest(
        key="shoulders_overhead", label="Shoulders overhead",
        test_name="Supine shoulder flexion — straight arms, thumbs up, towel-gauged lumbar lock",
        unit="°", value_at_100=170.0, value_at_0=0.0, bilateral=True,
        setup="Lie on your back on a bare hard floor, or **the same thin mat every time**. "
              "Knees bent, feet flat. Fold a hand towel to a set thickness — write that "
              "thickness down — and slide it under your lower back. Start with your arms by "
              "your sides, **elbows locked straight and thumbs pointing at the ceiling**. "
              "Reach both arms overhead, toward the floor behind your head.",
        lock="The towel. Squash it flat against the floor before you start. **The tell does "
             "not depend on how the position feels: if anyone can slide a finger under that "
             "towel at any point, your back has arched and the trial is void.** That matters "
             "more here than anywhere else, because your sense of what 'flat' feels like is "
             "set by your normal arched posture — so 'it feels flat to me' is exactly the "
             "judgement that will mislead you. Reset and take it again.",
        measurement="One photo from each side: phone on a marked spot at floor level, at "
                    "least 1.5 m away, with a ruler standing upright beside that wrist. "
                    "Measure the gap from the floor up to **the wrist bone on the "
                    "little-finger side**. Smaller is better — 0 cm means the arm is resting "
                    "on the floor. The app converts that gap into an angle using your "
                    "recorded arm length, so the centimetres are what you write down and the "
                    "angle is what scores.",
        what_youre_testing="How far your arms travel overhead with your back honestly flat. "
                           "This is the position you already know you fail — you cannot rest "
                           "both elbows on the floor. Three separate tissues can be the "
                           "reason: your chest muscles, the muscles deep in the armpit, and "
                           "your lats. This test says how far you get; the lat test that "
                           "follows is what tells them apart.",
        safety="You raise your own arms and stop where they stop. **Never let anyone press "
               "your arms down toward the floor.** Your right shoulder is held by muscle "
               "rather than ligament after the surgery, and pressure into the end of this "
               "range is the one thing it is least able to resist.",
    ),
    "lats": RungTest(
        key="lats", label="Lats",
        test_name="One arm overhead, with your lower back fully rounded into the floor",
        unit="°", value_at_100=160.0, value_at_0=0.0, bilateral=True,
        setup="Lie on your back with your hips and knees bent square and **your feet flat "
              "against a wall or a chair seat**. That holds your lower back rounded into the "
              "floor without you having to hold it there, and it is a stronger position than "
              "simply 'flat'. **One arm at a time**, elbow locked straight, thumb at the "
              "ceiling, reaching overhead toward the floor behind your head.",
        lock="Your feet against the wall, and your lower back pressed hard into the floor. "
             "Here the rounded back is not just a safety rule — **it is the entire point of "
             "the test**, because it is what puts the lats on stretch and leaves the other "
             "two tissues alone. **The tell: if your lower back lifts away from the floor at "
             "all, or your feet push off the wall, the trial is void.** One arm at a time, so "
             "the other side cannot help.",
        measurement="Same as the previous test: photo from that side, gap from the floor up "
                    "to **the wrist bone on the little-finger side**. Smaller is better. Left "
                    "and right separately, to the nearest half centimetre.",
        what_youre_testing="Your lats specifically, separated from everything else. Three "
                           "tissues can stop an arm going overhead, and **only the lat is "
                           "attached to your lower back** — so changing your back position "
                           "changes the lat's tension and nothing else's. Round the back and "
                           "the lat pulls tight; arch it and the lat goes slack. That is why "
                           "the same arm movement, done in two back positions, tells you "
                           "whether the lat is the thing stopping you. Read together with the "
                           "previous test: both poor means the lat is your limit; this one "
                           "fine but the last one poor means it is your chest or the shoulder "
                           "joint itself.",
        anchor_provisional=True,
        safety="**The 100 mark on this one is our own estimate, and it is deliberately "
               "harsh.** The standard version of this test is done with the back merely flat; "
               "we round it further, which makes it harder, so a score here is comparable "
               "with your own future scores but should not be compared against any published "
               "figure. Worth asking the physio to set it properly. As with the last test: "
               "you move your own arm, and nobody presses it down.",
    ),
    "chest_horizontal": RungTest(
        key="chest_horizontal", label="Chest / pecs",
        test_name="Standing against a wall, arms up in a goalpost",
        unit="cm", value_at_100=0.0, value_at_0=15.0, bilateral=True,
        setup="Stand with your back to a wall, heels about 10-15 cm out from it, knees soft. "
              "Press your lower back flat to the wall and **trap a sheet of A4 paper between "
              "your lower back and the wall**. Bring your arms up into a goalpost shape — "
              "upper arms out level with your shoulders, elbows bent square, forearms "
              "pointing up. Take the backs of your hands back toward the wall.",
        lock="The trapped sheet of paper. **The tell checks itself: the moment your lower back "
             "arches, the paper goes loose and falls — and that trial is void.** Arching is "
             "how the shoulders reach the wall without your chest being any longer at all. "
             "Reset and take it again.",
        measurement="Measure the horizontal gap from the wall to **the back of your wrist**, "
                    "at the crease. Smaller is better — 0 cm means the wrist touches the "
                    "wall. Left and right separately, to the nearest half centimetre.",
        what_youre_testing="The length of your chest muscles, and how freely the shoulder "
                           "turns outward. This is the wall-slide start position you already "
                           "find hard, measured rather than guessed at. It is also the live "
                           "replacement for the gym's 'Chest — Low' reading from January "
                           "2025, which never recorded how it was taken.",
        safety="Stop where the movement stops. This is a measurement of where your arms sit, "
               "not a stretch to push into, and pressing into the end of it is the direction "
               "your right shoulder likes least.",
        replaces="the doorway pec stretch and the supine 90/90 pec stretch — both hang the "
                 "anterior capsule on an external frame, which is the apprehension position "
                 "for this shoulder",
    ),
    "thoracic_rotation": RungTest(
        key="thoracic_rotation", label="Thoracic rotation",
        test_name="Lying on your side, turning the top shoulder back",
        unit="°", value_at_100=45.0, value_at_0=0.0, bilateral=True,
        setup="Lie on your side with your hips and knees stacked one on top of the other and "
              "bent square, knees resting on a folded towel of **the same thickness every "
              "time**. **Fold your arms across your chest.** Now turn your top shoulder "
              "backwards, toward the floor behind you.",
        lock="Your pelvis. Reach across with your bottom hand and press your top knee down, "
             "and keep the hips stacked. **The tell: if your top knee lifts or your hips roll "
             "back with your shoulder, you are rolling your whole body instead of turning "
             "your upper back — the trial is void.**",
        measurement="Measure the height from the floor up to **the bony point on top of your "
                    "top shoulder**, first at the start and then at the end of the turn. "
                    "Record the drop between the two. Bigger is better. The app converts it "
                    "to degrees.",
        what_youre_testing="Rotation through your upper back — the part of your spine that is "
                           "actually built to twist. Your lower back is not, which is why "
                           "pinning the pelvis matters. Stiffness here shows up as your ribs "
                           "and shoulder blade fighting each other when you reach overhead.",
        safety="**Arms stay folded across your chest** — do not sweep the top arm out to the "
               "floor behind you, which is the usual way this stretch is taught. That end "
               "position puts your right shoulder in the exact position it was operated on "
               "for.",
        replaces="the classic open book with the top arm sweeping to the floor",
    ),
    "lumbar": RungTest(
        key="lumbar", label="Lumbar control",
        test_name="Flattening your lower back to the floor",
        unit="cm", value_at_100=0.0, value_at_0=5.0, bilateral=False,
        setup="Lie on your back with both legs straight and together, arms by your sides, "
              "next to a wall with a 30 cm ruler taped upright at hip height. **Actively "
              "flatten your lower back down to the floor** — draw it down using your stomach, "
              "and hold it there.",
        lock="Your feet and your backside. **The tell: if you press through your heels or "
             "clench your buttocks, you are pushing the floor away rather than controlling "
             "your back — the gap closes without you having done the thing being measured, "
             "and the trial is void.** Keep the legs relaxed and heavy.",
        measurement="Photo from the side, from at least 1.5 m, phone on a marked spot at "
                    "floor level with the ruler in shot. Measure the biggest gap left between "
                    "the floor and your lower back. Smaller is better — 0 cm means flat to "
                    "the floor.",
        what_youre_testing="Whether you can flatten your lower back on purpose and hold it "
                           "there. This is the only test here that is control rather than "
                           "length, and it sits underneath almost everything else — nearly "
                           "every other test can be faked by arching, so if you cannot "
                           "flatten your back on demand, several other readings cannot be "
                           "trusted either.",
        safety="Safe, and actively good for you: flattening the lower back is the same "
               "movement already recommended to take pressure off the two lowest joints in "
               "your spine.",
    ),
    "lateral_trunk": RungTest(
        key="lateral_trunk", label="Lateral trunk",
        test_name="Standing against a wall, sliding one hand down your leg",
        unit="cm", value_at_100=20.0, value_at_0=0.0, bilateral=True,
        setup="Stand with your heels, buttocks, upper back and head **all touching a wall**, "
              "feet hip-width apart on your traced floor mark. Let your arms hang with your "
              "palms flat against the outside of your thighs. Slide one hand straight down "
              "the side of that leg, bending sideways.",
        lock="The wall — all four points of contact. **The tell: if your buttocks, upper back "
             "or head come away from the wall, you have started leaning forward or twisting "
             "instead of bending sideways, and the trial is void.**",
        measurement="Mark your trouser seam with a pen where your fingertips reach at rest, "
                    "and again at the furthest point. Measure the distance between the two "
                    "marks. Bigger is better. Left and right separately, to the nearest half "
                    "centimetre.",
        what_youre_testing="Sideways bend through your trunk. It is measured as how far the "
                           "hand travels rather than as an angle, because a tape between two "
                           "pen marks is something you can reproduce alone in three months' "
                           "time and an eyeballed angle is not.",
        safety="**Keep it light and stop early.** Bending sideways is a caution movement for "
               "you in *both* directions, for two different reasons — to the right it narrows "
               "an already-narrowed nerve opening at the base of your spine, and to the left "
               "it loads the two disc bulges higher up. Move yourself, do not reach overhead, "
               "and do not chase the number.",
    ),
    "neck": RungTest(
        key="neck", label="Neck (rotation)",
        test_name="Lying on your back, turning your head to one side",
        unit="°", value_at_100=80.0, value_at_0=0.0, bilateral=True,
        setup="Lie on your back on a bare hard floor, or **the same thin mat every time**. "
              "Knees bent, feet flat, arms by your sides. Strap your phone flat across your "
              "forehead with a headband, and zero it looking straight up with your chin "
              "level. Turn your head slowly to one side and **stop at the first firm "
              "resistance — not as far as it will go.**",
        lock="Your own bodyweight and your shoulder blades: both stay on the floor for the "
             "whole trial, which is what stops your body turning with your head. Your chin "
             "also stays level. **The tell: tipping the chin up or down buys fake rotation, "
             "so if the phone shows the chin has moved more than about 5 degrees, the trial "
             "is void.**",
        measurement="Read the turn angle off the phone where you meet firm resistance. Bigger "
                    "is better. Left and right separately, to the nearest degree. **Do it "
                    "twice per side and record the second** — the first is always a "
                    "familiarisation attempt.",
        what_youre_testing="How far your neck turns. Note what this test does **not** cover: "
                           "your actual neck complaint is tightness bending forward, "
                           "noticeably worse on the left, and that direction is deliberately "
                           "not measured because it is not safe to push. So expect this "
                           "number to sit still even in a week when your neck feels worse.",
        safety="**You turn your own head, and nobody ever pushes it further — not a partner, "
               "not your own hand.** Given how mobile your joints are generally, the neck is "
               "the last place to go hunting for extra range. Stopping at first firm "
               "resistance rather than the true end is deliberate and stays that way until "
               "the hypermobility assessment has been done properly; that question is on the "
               "list for the physio on 2026-08-16.",
        replaces="a seated chin-to-acromion tape reading, whose own lock required both hands "
                 "on the seat while its measurement required holding a tape",
    ),
    "squat_depth": RungTest(
        key="squat_depth", label="Squat depth",
        test_name="Squatting down until your back stops being flat",
        unit="cm", value_at_100=5.0, value_at_0=-20.0, bilateral=False,
        setup="Bare feet, standing on your traced foot outline. Squat down and **stop at the "
              "first moment your lower back stops being flat and starts to round or arch** — "
              "not the lowest you can get.",
        lock="The traced outline. How wide your feet are and how far your toes point out "
             "change this reading more than anything else does, so the stance has to be "
             "identical every time. **The tell: if your feet are not sitting inside the "
             "traced lines, the trial is void** — reset them before you squat, not after.",
        measurement="Photo from the side at your lowest good position, phone at about knee "
                    "height and at least 1.5 m away, with a tape stuck vertically to the wall "
                    "behind you. Measure the height of your hip crease against the top of "
                    "your kneecap. **Below the kneecap is a positive number and is the good "
                    "direction.**",
        what_youre_testing="How deep you can squat while your back is still doing what it "
                           "should. Read this one differently from the rest: **it is a "
                           "result, not a cause.** If it is low, the reason is your ankles, "
                           "your groin or your hip rotation — so this number tells you "
                           "something is wrong and the other three tell you what.",
        safety="Bodyweight only, never with a bar or a weight. You stop at the first loss of a "
               "flat back rather than at the bottom, so nothing here loads your spine in a "
               "rounded position.",
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
#: achievement or a control reading would be inventing data. 0 of 14 rungs
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
#: has not been run yet, which is the honest state: 0 of 14 rungs have a passive
#: reading, and 0 of 14 have an isometric or active one, so the gap metric that
#: is the entire point of v2 has no data at all. Until this list is non-empty,
#: the assessment is not an enhancement to the model — it IS the model.
ASSESSMENTS: tuple[Assessment, ...] = ()
