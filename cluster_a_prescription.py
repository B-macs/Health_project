"""
cluster_a_prescription.py — Cluster A: WHAT TO DO. Pattern label in, stack out.

The machine-readable form of `Input_files/cluster_a_prescription.md`, adapted
for this athlete on 2026-08-06.

CONTAINS NO TESTS, AND DEFINES NO EXERCISES. It references exercises BY NAME
from cluster_a_mechanics.LIBRARY, and a test asserts every name resolves there —
which is what makes the layer boundary checkable rather than merely stated. If
an exercise needs explaining, that belongs in Mechanics. If a test is missing,
that belongs in the Battery.

A PRESCRIPTION WITHOUT A PATTERN IS A GUESS
--------------------------------------------
`prescribe(None)` does not return a sensible default, a starter stack, or the
most likely pattern. It refuses, and says why. That is the source document's own
instruction and it is pinned by a test — the failure mode it exists to prevent
is handing someone a plausible-looking programme built on no measurement, which
is exactly what the whole four-slot method was designed to replace.

THE STACK IS NOT MEANT TO ACCUMULATE
------------------------------------
When a failed test passes, the exercise that fixed it LEAVES and the next-lowest
rung moves to the front. Five exercises is a hard ceiling. The pre-session
release block does not count toward it — it is a precondition, not part of the
stack.
"""

from __future__ import annotations

from dataclasses import dataclass

import cluster_a_mechanics as _mech

CLUSTER_KEY = "a"


# ── the mandatory release block ──────────────────────────────────────────────
#
# From patient_profile.py, NOT from any flexibility source — which is exactly
# why it was missing from all nine stacks in the original. It precedes every
# session of any kind, and the ordering rule is INHIBIT, THEN ACTIVATE:
# overactive structures are released before underactive ones are asked to work.
# Run the other way round, a session trains the compensation.

@dataclass(frozen=True)
class ReleaseItem:
    name: str
    dose: str
    laterality: str = "bilateral"
    when: str = "always"


PRE_SESSION_RELEASE: tuple[ReleaseItem, ...] = (
    ReleaseItem("Upper glute / TFL self-release", "2 × 90 s per side"),
    ReleaseItem("Piriformis contract-relax (PNF)", "3 × 5 per side"),
    ReleaseItem("Right posterior hip capsule stretch", "3 × 60 s", "right", "hip_focused"),
    ReleaseItem("Ischial tuberosity hamstring release", "2 × 90 s per side", "bilateral",
                "hip_focused"),
    ReleaseItem("Coxa Saltans tendon-path drill", "2 × 10", "right", "right_hip_loaded"),
)


# ── stacks ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StackItem:
    """One line of a stack. `exercise` is a NAME resolved against Mechanics."""
    exercise: str
    dose: str
    note: str = ""
    deferred: bool = False


@dataclass(frozen=True)
class Stack:
    pattern: str
    limiter: str
    items: tuple[StackItem, ...]
    intro: str = ""
    outro: str = ""

    @property
    def live_items(self) -> tuple[StackItem, ...]:
        """What is actually performed today — deferrals removed."""
        return tuple(i for i in self.items if not i.deferred)


_T = _mech.LIBRARY_BY_KEY

STACKS: dict[str, Stack] = {

    "A": Stack(
        pattern="A", limiter="Bone",
        intro="No stretching stack. The only thing available is finding an orientation "
              "that clears the collision.",
        # ER hold FIRST, triangle second — the source document's own order,
        # which a transcription error had inverted (found in the 2026-08-07
        # stacking audit). Isolated before integrated: groom the turn-out on a
        # seat before spending it in the position.
        items=(
            StackItem(_T["er_holds"].name, "5 × 20 s",
                      "The turn-out in isolation, seat-supported — build the rotation "
                      "before the next drill spends it."),
            StackItem(_T["triangle_split"].name, "5 × 20 s, partial depth",
                      "Turn the legs out; do not arch the back to find the room."),
        ),
        outro="**Re-test gate 0 in two weeks, and stop sooner if it pinches.** A sharp "
              "anterior-hip pinch with a hard, unspringy stop is the one finding in this "
              "cluster that training cannot answer — bone does not lengthen, and repeated "
              "collision with it causes joint irritation rather than progress. If every "
              "orientation still pinches after two weeks of the drills above, the honest "
              "conclusion is that this is the shape of your hip rather than a restriction "
              "in it, and the goal moves to what the joint allows rather than what the "
              "skill asks for. That is a real outcome, not a failure.",
    ),

    "B": Stack(
        pattern="B", limiter="Orientation",
        intro="The cheapest situation on the list. Expect movement within a couple of "
              "sessions with no length change at all.",
        items=(
            StackItem(_T["pelvic_rock"].name, "3 × 12"),
            StackItem(_T["triangle_split"].name, "5 × 20 s", "No depth chasing."),
            StackItem(_T["elevated_hinge"].name, "3 × 60 s"),
            StackItem(_T["triangle_split"].name, "3 × 30 s"),
        ),
        outro="Retest gate 0 before adding anything.",
    ),

    "C": Stack(
        pattern="C", limiter="Whole adductor group",
        intro="Everything is short. Work up the leverage ladder — bent-knee work opens the "
              "rest of the group so the straight-knee work can reach gracilis instead of "
              "being capped before it gets there.",
        items=(
            StackItem(_T["tailors_pose"].name, "3 × 90 s", "Bent leverage."),
            StackItem(_T["horse_stance"].name, "3 × 8", "90° leverage.", deferred=True),
            StackItem(_T["elevated_hinge"].name, "3 × 90 s", "Tilt."),
            StackItem(_T["triangle_split"].name, "5 × 20 s", "Straight leverage."),
            StackItem(_T["isometric_split"].name, "3 × 15 s"),
        ),
        outro="Five is the ceiling and the release block does not count toward it. Under "
              "time pressure drop the straddle hinge — it is the least specific to what "
              "failed.",
    ),

    "D": Stack(
        pattern="D", limiter="Short adductors and rotators",
        items=(
            StackItem(_T["tailors_pose"].name, "4 × 90 s"),
            StackItem(_T["frog_rocks"].name, "3 × 10"),
            StackItem(_T["butterfly_pir"].name, "5 rounds of 5 s contract, 15 s relax"),
            StackItem(_T["rotations_90_90"].name, "3 × 8 per side",
                      "Neutral or slight internal rotation on the right."),
            StackItem(_T["triangle_split"].name, "3 × 30 s"),
        ),
    ),

    "E": Stack(
        pattern="E", limiter="Gracilis",
        intro="Bent-leg work slackens the exact muscle limiting you, so a STRAIGHT knee is "
              "the point of this stack — any bend and you have trained something else.",
        items=(
            StackItem(_T["horse_stance"].name, "3 × 8",
                      "Brief, to open the rest of the group.", deferred=True),
            StackItem(_T["wall_straddle"].name, "3 × 90 s", "Knees straight."),
            StackItem(_T["triangle_split"].name, "4 × 30 s", "Knees straight."),
            StackItem(_T["cossack_straight"].name, "3 × 6 per side", deferred=True),
            StackItem(_T["isometric_split"].name, "3 × 15 s", "Knees straight."),
        ),
        outro="**Medial knee discomfort is a finding, not a training sensation.** The "
              "original text here told you to expect it and continue; that contradicted both "
              "other documents and has been removed. Gracilis crosses the knee so some "
              "sensation is mechanically expected — but a weak VMO produces pain in the same "
              "place for a different reason, and at Beighton 6/9 the passive restraints are "
              "not doing the work they would in another body. If it appears, stop and check "
              "against §I before continuing. Note also that 'knees locked hard' is now "
              "'knees straight': forcing a locked joint is what the hypermobility profile "
              "rules out.",
    ),

    "F": Stack(
        pattern="F", limiter="Tilt range",
        intro="**The tilt-specific method, rebuilt rather than filtered.** The source's §F "
              "was four pancake variations, three of them using a plate or a strap to reach "
              "depth — which for a body that folds by rounding produces the depth through "
              "the spine. That is both the contraindicated route and the wrong measurement, "
              "and removing those would have left a stack of leftovers.\n\n"
              "The organising idea instead: **the lumbar rounding is the compensation, not "
              "the problem.** You round because the pelvis will not rotate forward. So the "
              "work is not to fold more carefully — it is to build the tilt until there is "
              "no reason to compensate.",
        items=(
            StackItem(_T["pelvic_rock"].name, "3 × 12",
                      "The tilt as an isolated MOVEMENT, no depth. You cannot train a "
                      "position through a joint action you cannot perform on its own."),
            StackItem(_T["elevated_hinge"].name, "3 × 60 s",
                      "The elevation supplies the tilt. **Lowering the block over months is "
                      "the progression** — not reaching further at a fixed height."),
            StackItem(_T["straddle_lift_offs"].name, "3 × 8",
                      "Hip flexor strength to PRODUCE the tilt rather than be placed into "
                      "it. Neutral or slight internal rotation on the right."),
            StackItem(_T["flat_back_hinge"].name, "3 × 8",
                      "Raises the hamstring ceiling that currently caps the tilt at about "
                      "90°, without a fold. Hinge, never round."),
        ),
        outro="**What success looks like, and it is not depth.** The number that should move "
              "is the tilt angle — the degrees your pelvis tips, phone on your lower back, "
              "measured the way the battery measures it. How far forward you fold may not "
              "change for weeks and that is not failure: if the angle grows, or the block "
              "under your hips comes down, while the fold stays put, the stack is working "
              "exactly as intended. Retest the tilt after four weeks, cold, before adding "
              "anything.",
    ),

    "G": Stack(
        pattern="G", limiter="Tilt production — hip flexor strength",
        intro="You can reach the position, you cannot produce it. The tilt work moves to the "
              "END of the session and becomes strength work.",
        items=(
            StackItem(_T["triangle_split"].name, "3 × 45 s"),
            StackItem(_T["isometric_split"].name, "3 × 15 s"),
            StackItem(_T["straddle_lift_offs"].name, "3 × 8"),
            StackItem(_T["loaded_flat_back_hinge"].name, "3 × 8",
                      "At the chest, never behind the neck."),
            StackItem(_T["pancake_own_power"].name, "3 × 30 s",
                      "Stop at the first loss of a flat back."),
        ),
    ),

    "H": Stack(
        pattern="H", limiter="Adductor end-range strength",
        intro="The body will not concede range it cannot support. The strength work here is "
              "what PERMITS the range rather than something added alongside it.",
        items=(
            StackItem(_T["triangle_split"].name, "1 × 60 s",
                      "Purely to open the door, to firm resistance only."),
            StackItem(_T["isometric_split"].name, "6 × 10 s",
                      "Hands off, full rest between."),
            StackItem(_T["horse_stance_weighted"].name, "3 × 8", deferred=True),
            StackItem(_T["adductor_squeeze"].name, "5 × 5 s"),
            StackItem(_T["copenhagen"].name, "3 × 20 s per side",
                      "Start here and hold it. Last performed May/June 2025 at 30 s × 3, "
                      "with a back injury and a full rehab block since — the old number is "
                      "history, not a starting point."),
        ),
    ),

    "I": Stack(
        pattern="I", limiter="Puller strength — hip abductors",
        intro="If the abductors cannot open the legs, the adductors do not release. The "
              "repeated split between abductor sets is deliberate, not filler — contracting "
              "the antagonist relaxes what you were stretching, so the second round goes "
              "deeper than the first.\n\n"
              "**The release block is load-bearing here, not routine.** This whole stack "
              "loads glute medius, minimus and TFL, and glute medius upper fibres are listed "
              "as overactive and right-dominant — named as the primary anchor driving joint "
              "compression through the chain, with release required BEFORE activation. "
              "Running this stack without it trains the compensation.",
        items=(
            StackItem(_T["side_leg_raise"].name, "4 × 8 per side", "Slow, no swing."),
            StackItem(_T["triangle_split"].name, "60 s"),
            StackItem(_T["banded_abduction"].name, "3 × 10"),
            StackItem(_T["triangle_split"].name, "60 s"),
            StackItem(_T["side_leg_raise_eccentric"].name, "3 × 6",
                      "Lift bent, straighten, lower slow."),
        ),
        outro="**If medial knee discomfort has appeared**, add terminal knee extensions or a "
              "Spanish squat, 3 × 10. VMO resists the knee collapsing inward, which is the "
              "direction gravity pulls it in a split. If you are running §E instead, "
              "gracilis load is the more likely cause and the fix is managing volume.",
    ),
}


# ── dosage ───────────────────────────────────────────────────────────────────

FREQUENCY: str = (
    "One to two sessions per week for the cluster. Not more — flexibility training "
    "fatigues you by the same route as strength training, and more sessions eat the "
    "adaptation."
)

#: Set against the REAL training week rather than generic guidance. Stage 2A
#: runs a 7-day cycle with legs loaded on days 1, 3 and 5.
PLACEMENT: str = (
    "Two or more days after leg training, or the same day in the evening after a morning "
    "session. **Not the day after leg training, and not on a rest day as recovery.**\n\n"
    "Against the real week: Stage 2A loads legs on **days 1 (goblet squat), 3 (RDL, hip "
    "thrust) and 5 (Bulgarian split squat)**. That leaves **day 7** as the clean slot, with "
    "day 2 as the same-day-evening fallback. Days 2, 4 and 6 are each the day after legs — "
    "the worst slot in the ranking.\n\n"
    "The cluster costs a session against the stage's five-per-week ceiling, so it is not "
    "free. And it does not belong on a rest day: the app offers yoga there, and this is not "
    "that. A restorative flow on a rest day is fine; an adaptation-seeking session is the "
    "thing the placement rule calls worst."
)

LENGTH: str = (
    "Three to five exercises. Five is a hard ceiling. The pre-session release block does "
    "not count toward it — it is a precondition, not part of the stack."
)

RETEST: str = "Every four weeks, cold, in order. Only re-run the slots below the one you have been fixing."

CHANGE_NOTHING: str = (
    "A number moving less than about double your baseline noise is not a result and is not "
    "a reason to change the programme. Give it another four weeks. **Until three baseline "
    "mornings exist there is no noise figure at all**, so until then, change nothing on the "
    "strength of a single reading in either direction."
)


# ── the one public function ──────────────────────────────────────────────────

class NoPatternError(ValueError):
    """Raised when a stack is asked for without a pattern to look up.

    A distinct type rather than a bare ValueError so a caller can catch exactly
    this and render the refusal, instead of swallowing every ValueError the
    module might ever raise.
    """


def prescribe(pattern: str | None) -> Stack:
    """Look up the stack for a pattern label. REFUSES rather than guessing.

    There is no default stack, no "most likely" fallback and no starter
    programme. The source document is explicit — *"a prescription without a
    pattern is a guess. Say so rather than guessing"* — and the failure this
    prevents is handing over a plausible-looking programme built on no
    measurement, which is the exact thing the four-slot method replaced.
    """
    if not pattern:
        raise NoPatternError(
            "No pattern label, so there is nothing to look up. Run the battery first — "
            "a prescription without a pattern is a guess, and guessing here means "
            "training whatever seemed likely rather than what was measured."
        )
    key = pattern.strip().upper()
    if key not in STACKS:
        raise NoPatternError(
            f"{pattern!r} is not a Cluster A pattern. Valid labels are "
            f"{', '.join(sorted(STACKS))}."
        )
    return STACKS[key]


def release_block(*, hip_focused: bool = True, right_hip_loaded: bool = False
                  ) -> tuple[ReleaseItem, ...]:
    """The pre-session protocol for a given session shape.

    Every Cluster A stack is hip-focused, so the default is the fuller version;
    `right_hip_loaded` adds the tendon-path drill and is true for any stack
    containing lift-offs or a squat pattern.
    """
    out = []
    for item in PRE_SESSION_RELEASE:
        if item.when == "always":
            out.append(item)
        elif item.when == "hip_focused" and hip_focused:
            out.append(item)
        elif item.when == "right_hip_loaded" and right_hip_loaded:
            out.append(item)
    return tuple(out)
