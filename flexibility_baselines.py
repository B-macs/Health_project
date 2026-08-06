"""
flexibility_baselines.py — shared flexibility vocabulary, and what came before.

REWRITTEN 2026-08-06 (v3). This file used to hold the whole model: fourteen
rung tests, eight skills with ladders, and a stack of stretches. All of that is
DELETED. It has been replaced by a three-document cluster system whose layers
live in cluster_a_mechanics.py, services/battery.py + cluster_a_battery.py, and
cluster_a_prescription.py.

WHY THE MODEL CHANGED, so nobody rebuilds the old one
------------------------------------------------------
v2 measured fourteen rungs, scored each skill as min(rungs), and reported a
number out of 100. The replacement runs FOUR SLOTS IN ORDER AND STOPS AT THE
FIRST FAILURE, and its output is a single pattern label — not a score, not a
ranking, nothing else. Those are different programs. min() measures everything
and then picks; the battery stops as soon as it knows the answer and never
measures the rest. There is no value in a spectrum profile for a skill that a
bony block had already made unavailable.

Nothing was lost in the deletion: no assessment had ever been run, and none of
Cluster A's eight measurements were implemented by any of the fourteen rungs.
The closest, the old `adductors` rung, tested the same tissue at the same
leverage from a different position with a different landmark — so not even its
value would have transferred.

WHAT THIS FILE IS NOW
---------------------
The vocabulary shared across every cluster (the three measures, the
assisted-to-resisted spectrum, the scheduling window), the per-athlete
constants that make one session comparable with the next, and the provenance of
everything that was measured before the cluster model existed. It holds no
tests, no exercises and no prescriptions — those belong to the three layers,
and the dependency between them runs one way only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# ── the three measures ───────────────────────────────────────────────────────
#
# Used by slot 3 of any battery. Note they are reached ONLY if slots 0-2 pass —
# in the old model every rung was measured three ways regardless.

PASSIVE = "passive"
ISOMETRIC = "isometric"
ACTIVE = "active"
MEASURES: tuple[str, ...] = (PASSIVE, ISOMETRIC, ACTIVE)

#: Shown before the first measurement is taken. The three words mean something
#: specific in physiology and something else in ordinary speech — "active" does
#: not obviously mean "under your own power" to anyone who has not read a
#: module docstring — and they were previously explained nowhere on screen.
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

#: The gap, and what each direction means.
GAP_EXPLAINED: str = (
    "Passive minus active is the number that matters most for you. A BIG gap "
    "means the range is already there and you cannot hold it — stretching more "
    "will not help, and strength work in the position will. A SMALL gap means "
    "you are using nearly everything you have, and the range itself is what to "
    "chase. You are hypermobile, so the big-gap case is the one to expect — "
    "with one documented exception, the seated pelvic tilt, where the range "
    "genuinely is missing."
)

#: ORDER MATTERS AND IS NOT NEGOTIABLE. Passive work leaves tissue looser for an
#: hour or more, so a passive trial taken first flatters everything measured
#: after it. This is the one procedural rule most likely to be broken by
#: someone working through the tests in the order they are written down.
MEASURE_ORDER: tuple[str, ...] = (ACTIVE, ISOMETRIC, PASSIVE)

#: Why a lock matters, and the answer to the obvious question about it.
#: The athlete asked directly: if the lock is lost, why not just redo the test?
#: You can and you should — the difficulty is NOTICING, which is a design
#: requirement on every lock rather than a note about one.
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


# ── the assisted → resisted spectrum ─────────────────────────────────────────
#
# The source method's central programming dial, and the athlete asked for it by
# name. Every exercise sits somewhere on a line from HEAVILY ASSISTED (a
# partner, a wall or gravity puts you in the position) to HEAVILY RESISTED (you
# fight your way in, or hold it against load).
#
# FOR THIS ATHLETE THE ASSISTED HALF IS LARGELY WASTED, and that is measured
# rather than preferred: Beighton 6/9, and a profile rule that prescribes
# "controlled-range strength/stability work over passive end-range stretching".
# The documented exception is the seated pelvic tilt, where the range really is
# absent — see cluster_a_mechanics.LIMITERS, limiter 5.

ASSISTED = "assisted"
UNASSISTED = "unassisted"
RESISTED = "resisted"
SPECTRUM: tuple[str, ...] = (ASSISTED, UNASSISTED, RESISTED)

SPECTRUM_EXPLAINED: tuple[tuple[str, str], ...] = (
    (ASSISTED, "Something else puts you in the position — a wall, a block, "
               "gravity, a partner. Builds the ceiling. **Mostly not your "
               "problem**: your passive range is already good, and this is the "
               "half of the usual method aimed at people who lack it."),
    (UNASSISTED, "You get into the position under your own power, with nothing "
                 "helping. This is the range you can actually use, and it is "
                 "what the tests score."),
    (RESISTED, "You hold or fight the position against resistance — your own "
               "muscles, a band, a load. Builds the strength to keep the range "
               "you have. **This is where most of your work belongs**, and the "
               "wide passive-minus-active gap is what says so."),
)


# ── per-athlete constants ────────────────────────────────────────────────────

#: Measured ONCE, written down, and re-used forever. Each is a setup number
#: rather than a score: get it wrong and the comparison between two sessions is
#: meaningless, however carefully each was measured.
#:
#: THE NUMBER IS THE RECORD, never a chalk mark. The athlete found the need for
#: this by reading a protocol that set the heels to "a marked position" and
#: recorded nothing about where that position was — a mark on a floor is gone by
#: the next session, and a mark re-placed by eye silently invalidates every
#: reading taken against it.
FROZEN_CONSTANTS: tuple[tuple[str, str], ...] = (
    ("straddle_width_cm",
     "Inner ankle to inner ankle in the seated straddle, at the width you "
     "actually work at. The instruction is 'open to maximum, then come in "
     "slightly' — which is bone clearance, not comfort, and is not reproducible "
     "by feel."),
    ("tailors_heel_distance_cm",
     "Tailbone to the back of the heels in the seated butterfly. Heels further "
     "away drop the knees without the groin being one millimetre longer, so a "
     "session that re-places them by eye is not comparable with the last one."),
    ("side_split_stance",
     "Both feet traced on card, photographed, with the turn-out angle marked. "
     "Stance width and toe-out move this reading more than anything else does."),
    ("floor_reference",
     "Which floor and which surface. A carpet, a mat and bare boards give "
     "different crotch and forehead heights for the same body."),
)

#: NOT frozen — this one is meant to move, and its movement IS the progress.
#: Recorded beside every reading rather than fixed, because a depth reached from
#: a lower block is a different achievement from the same depth on a higher one.
PROGRESSION_VARIABLE: tuple[str, str] = (
    "block_height_cm",
    "The elevation under the hips. Sitting above foot level rotates the pelvis "
    "forward on its own, so the block is the assist device for the tilt "
    "specifically. Lowering it over months is the progression — reaching "
    "further at a fixed height is not.",
)


# ── the scheduling window ────────────────────────────────────────────────────
#
# RESOLVED 2026-08-06. This used to carry REST_DAY_CONFLICT_UNRESOLVED, a flag
# recording that the app offered yoga on rest days while the flexibility model
# called that the worst slot, and that nothing in the code distinguished a
# restorative flow from an adaptation-seeking session.
#
# The Prescription's dosage section answers it directly: one to two sessions a
# week, two or more days after leg training or the same day in the evening,
# "not the day after leg training, and not on a rest day as recovery". A
# cluster session is adaptation-seeking BY DEFINITION, so it is never a rest-day
# activity. A restorative yoga flow on a rest day remains fine — that is a
# different thing, and services/yoga.py owns it.

WINDOW_GOOD = "good"
WINDOW_OK = "ok"
WINDOW_POOR = "poor"

WINDOW_RULES: dict[str, str] = {
    WINDOW_GOOD: "2+ days after hard sport or strength, or the same day PM after an AM "
                 "session — the fatigue signal has not landed yet",
    WINDOW_OK:   "immediately after sport or strength, with the volume of both reduced",
    WINDOW_POOR: "the day after strength, or slotted into a rest day as 'active recovery' — "
                 "peak fatigue, minimum adaptation, and flexibility training is not recovery",
}


# ── provenance: what was measured before the cluster model ───────────────────
#
# Kept as a historical record and used by NOTHING. Every entry here predates the
# battery, none of it is a battery reading, and no value in it may be carried
# into one. Tests pin that.

SCAN_DATE: date = date(2025, 1, 17)
AGE_AT_SCAN_YEARS: int = 30
VENDOR_BIOAGE_YEARS: int = 28
VENDOR_BIOAGE_COMPARED_AGAINST_AGE: int = 31


@dataclass(frozen=True)
class LegacyGymReading:
    """One region off the January 2025 gym goniometry print-out.

    Its defect is unchanged and is worth remembering, because it is the same
    class of error as the InBody's typed height: the vendor printed degrees per
    region and never recorded WHICH MOVEMENT produced them. `Hip 33°` means one
    thing as internal rotation and another as a Thomas test, and corroborates a
    different finding in each case.
    """
    label: str
    left: float | None
    right: float | None
    vendor_verdict: str
    note: str = ""


LEGACY_GYM_READINGS: tuple[LegacyGymReading, ...] = (
    LegacyGymReading("Neck", 30.0, 30.0, "Normal",
                     "Perfect bilateral symmetry against 1-3° differences elsewhere — "
                     "flagged as suspect, never resolved."),
    LegacyGymReading("Chest", 106.0, 106.0, "Low",
                     "Exact equality post-Latarjet is the least likely reading on the sheet."),
    LegacyGymReading("Lat flexion", 20.0, 21.0, "Normal",
                     "The vendor's own verdict contradicts the obvious reading of the "
                     "label; a band guessed out of a contradiction is worse than no band."),
    LegacyGymReading("Hip", 33.0, 34.0, "Low", "Protocol unrecorded — see the class note above."),
    LegacyGymReading("Hamstrings", 89.0, 86.0, "Normal",
                     "The most load-bearing legacy number: normal length with NO RESERVE. "
                     "Long-sitting upright with a straight knee is already ~90° of hip "
                     "flexion, so he is at the limit before a fold begins."),
)

#: The 22 poses of the hip/spine yoga flow, self-rated 1-100 on 2026-08-05.
#: 1 = can barely enter the position, 100 = at the physical limit.
#:
#: THESE DO NOT FEED ANY SCORE AND MUST NOT BE MADE TO. A battery asks for
#: passive, isometric and active readings in a locked position, measured cold;
#: a self-rating of a yoga pose answers none of the three, and no pose here
#: isolates a locked joint. Their value is clinical and historical — this table
#: is what identified the seated tilt deficit that the whole of Cluster A is
#: now built around.
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

#: The single most informative entry above, restated because the whole cluster
#: rests on it: Straddle Forward Fold scored 25/100 — his worst of the 22 — with
#: the note "hips stuck in flexion with tail bone down, back fully rounds,
#: unable to get shoulders over the hips unless greatly bending the knees".
#: Three other seated positions produced the same report independently.
LEGACY_TILT_DEFICIT_EVIDENCE: str = (
    "Straddle Forward Fold 25/100 (2026-08-05), the athlete's worst of 22 poses: "
    "'hips stuck in flexion with tail bone down, back fully rounds, unable to get "
    "shoulders over the hips unless greatly bending the knees.' The rounding is the "
    "COMPENSATION for a pelvis that will not rotate forward, not the restriction "
    "itself — which is why the prescription trains the tilt rather than avoiding "
    "the fold."
)
