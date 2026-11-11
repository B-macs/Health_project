"""
front_split_prescription.py — the front split: WHAT TO DO. Pattern in, stack out.

Written 2026-11-11 on the athlete's answer "Yes, all four" (front_split_mechanics
records the four). CONTAINS NO TESTS AND DEFINES NO EXERCISE: every name is
looked up in front_split_mechanics.LIBRARY, and tests/test_front_split.py fails
on a name that does not resolve.

A PRESCRIPTION WITHOUT A PATTERN IS A GUESS. `prescribe(None)` refuses, as
Cluster A's does. Until the front split test has been taken, the evening
session keeps the last stack that was measured (goal_block.evening_mobility_day).

HOW EVERY STACK IS BUILT (the blueprint's Part 6, and its adaptation for him)
------------------------------------------------------------------------------
- Three to five exercises. The skill comes LAST: small isolated work opens the
  parts, then the split uses them.
- Weighted to the resisted end (Beighton 6/9): range he cannot control is the
  hypermobile failure mode, so the active lifts and holds lead, and the one
  pattern built on that gap (A) has no passive split hold at all ("More
  stretching makes this worse").
- An assisted item is paired with a resisted one where the blueprint's pairing
  applies: the hip lifts the leg, the hamstrings relax, the contract-relax goes
  deeper.
- No release block. Key Rule 6 is suspended (his decision of 2026-09-22, kept for
  the 12-week block on 2026-10-16): a release comes back only if the hip-crest or
  front-of-hip symptoms return.

DOSES. The blueprint gives none for this skill. They follow its methods: the
contract-relax at 5 s pressing and 15 s sinking (the shape Cluster A's butterfly
uses), holds of 30-45 s, isometric presses of about 3 s (method 3), slow
lowering for 5 s (method 5), and the back-knee hover at the 20 s his own
progression of 2026-08-24 reached. Every session models under the flexibility
day's ceilings (sessions.SESSION_SHAPE: 10 entries, 50 minutes).
"""

from __future__ import annotations

from cluster_a_prescription import Stack, StackItem
import front_split_mechanics as _mech

CLUSTER_KEY = "front_split"

_T = _mech.LIBRARY_BY_KEY

STACKS: dict[str, Stack] = {

    "B": Stack(
        pattern="B", limiter="Both legs short",
        intro="Both legs are short at low demand. The front leg is opened first, then the "
              "back leg, then each is made strong at its new length, and the split last "
              "uses both.",
        items=(
            StackItem(_T["half_split_pir"].name, "5 rounds of 5 s contract, 15 s relax per side"),
            StackItem(_T["hip_flexor_tucked"].name, "2 × 45 s per side"),
            StackItem(_T["slr_lifts"].name, "3 × 8 per side"),
            StackItem(_T["knee_hover"].name, "3 × 20 s per side"),
            StackItem(_T["split_on_blocks"].name, "3 × 30 s per side"),
        ),
    ),

    "H": Stack(
        pattern="H", limiter="Front leg — hamstrings",
        intro="The front leg is short with the knee straight. The hip muscles lift the leg "
              "first, which relaxes the hamstrings; the contract-relax then adds range, the "
              "slow lowers make the new range strong, and the split last uses all of it.",
        items=(
            StackItem(_T["slr_lifts"].name, "3 × 8 per side"),
            StackItem(_T["half_split_pir"].name, "5 rounds of 5 s contract, 15 s relax per side"),
            StackItem(_T["slr_lowers"].name, "3 × 5 per side"),
            StackItem(_T["split_on_blocks"].name, "3 × 30 s per side"),
        ),
    ),

    "P": Stack(
        pattern="P", limiter="Back leg — deep hip flexors",
        intro="The back leg's deep hip flexors are short. The tucked stretch opens them, the "
              "hover makes that length strong, the slides teach the square hips, and the "
              "split last.",
        items=(
            StackItem(_T["hip_flexor_tucked"].name, "3 × 45 s per side"),
            StackItem(_T["knee_hover"].name, "3 × 20 s per side"),
            StackItem(_T["split_slides"].name, "2 × 8 per side"),
            StackItem(_T["split_on_blocks"].name, "3 × 30 s per side"),
        ),
    ),

    "R": Stack(
        pattern="R", limiter="Back leg — front of the thigh",
        intro="The back leg's front-of-thigh muscle is short. The deep group is opened first "
              "so the knee-bent stretch reaches this muscle, the hover makes the length "
              "strong, and the split last.",
        items=(
            StackItem(_T["hip_flexor_tucked"].name, "2 × 45 s per side"),
            StackItem(_T["front_thigh_kneeling"].name, "3 × 45 s per side"),
            StackItem(_T["knee_hover"].name, "3 × 20 s per side"),
            StackItem(_T["split_on_blocks"].name, "3 × 30 s per side"),
        ),
    ),

    "A": Stack(
        pattern="A", limiter="Range you cannot control yet",
        intro="The range is there and you cannot reach it under your own power. Strength at "
              "length is the work, so there is no passive split hold in this stack: more "
              "stretching makes this pattern worse.",
        items=(
            StackItem(_T["slr_lifts"].name, "3 × 8 per side"),
            StackItem(_T["slr_lowers"].name, "3 × 5 per side"),
            StackItem(_T["knee_hover"].name, "3 × 20 s per side"),
            StackItem(_T["split_heel_press"].name, "3 × 6 per side"),
        ),
    ),

    "S": Stack(
        pattern="S", limiter="The split itself",
        intro="Both legs are long enough and you control the range, so the split itself is "
              "the work: the square-hip slides, presses at depth, and the hold.",
        items=(
            StackItem(_T["split_slides"].name, "3 × 8 per side"),
            StackItem(_T["split_heel_press"].name, "3 × 6 per side"),
            StackItem(_T["split_on_blocks"].name, "3 × 30 s per side"),
        ),
    ),
}


# ── dosage ───────────────────────────────────────────────────────────────────

FREQUENCY: str = (
    "Two evening sessions a week, the blueprint's limit of one or two, on the evening of "
    "a strength day with no strength the next day (services/mobility_session.py)."
)

LENGTH: str = "Three to five exercises. Five is a hard ceiling."

#: Twelve weeks, the flexibility retest's interval since 2026-10-13 (his
#: words: "Flexibility should be retested every 12 weeks not 4 weeks"). From a
#: first test in November it falls after the block's last day (2027-01-10),
#: which keeps his rule of 2026-11-08: no test inside the block after this one.
RETEST_INTERVAL_DAYS: int = 84

RETEST: str = (
    "Every twelve weeks, cold, in the morning, in order. **Never the morning after leg "
    "training**: a leg day reads as extra tightness in exactly the legs being tested."
)

CHANGE_NOTHING: str = (
    "A number moving less than about double your baseline noise is not a result. Until "
    "three test mornings exist there is no noise figure, so change nothing on one reading."
)


# ── the one public function ──────────────────────────────────────────────────

class NoPatternError(ValueError):
    """A stack asked for without a front split pattern to look up."""


def prescribe(pattern: str | None) -> Stack:
    """The stack for a front split pattern. REFUSES rather than guessing."""
    if not pattern or not pattern.strip():
        raise NoPatternError(
            "No front split pattern yet, so there is nothing to look up. Take the front "
            "split test first: a prescription without a pattern is a guess."
        )
    key = pattern.strip().upper()
    if key not in STACKS:
        raise NoPatternError(
            f"{pattern!r} is not a front split pattern. Valid labels are "
            f"{', '.join(sorted(STACKS))}."
        )
    return STACKS[key]
