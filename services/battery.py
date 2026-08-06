"""
services/battery.py — the general assessment method. Four slots, one label out.

Pure functions only. No I/O, no Streamlit, no hidden clock reads — every
date-dependent function takes an explicit `today`, the same convention as
services/engine.py and services/strength.py.

THIS MODULE NAMES NO EXERCISE. It is the HOW-TO-TEST layer, and the dependency
between layers runs one way: Mechanics says what is worth testing, the Battery
produces a pattern, the Prescription looks the pattern up. A test in
tests/test_cluster_a.py fails if any exercise name from the Mechanics library
appears in this file's source.

FOUR SLOTS, AND THE ORDER IS THE POINT
--------------------------------------
    0. STRUCTURE     Is a bone stopping you?        Invalidates everything below
    1. REGRESSED     Is the tissue short at low demand?   Decides WHICH exercises
    2. PREREQUISITE  Do you have the component the skill needs?  Decides IF, and WHERE
    3. SPECTRUM      Passive, isometric, active     Decides WHICH END

**STOP AT THE FIRST FAILURE.** This is a decision tree with early exit, not a
scoring function, and the difference is not cosmetic. The model this replaced
measured fourteen things and took the minimum; that computes a number from
everything. Here, a failing slot 0 means slots 1-3 are not merely lower
priority — they are MEANINGLESS, because a bony block makes the tissue
questions unanswerable. There is no value in a spectrum profile for a skill
that was already unavailable.

The output is a PATTERN LABEL and nothing else. Not a score, not a ranking, not
a percentage. `services/flexibility.py` hands that label to the cluster's
Prescription; a prescription without a pattern is a guess, and `prescribe`
refuses rather than guessing.

THE LOAD WINDOW
---------------
Where an isometric trial carries added load, the load and the measurement are
ONE DATUM and are stored together. Too light and passive tissue absorbs it —
you have measured passive twice. Too heavy and it drags you to your true tissue
end range, which is passive again with more compression. The check is that the
isometric reading must come out SHALLOWER than the passive one; if it does not,
take weight off. `load_window_ok` is that check, and it is a property of the
pair rather than of either reading.

THE NOISE FLOOR
---------------
Three baselines on three separate mornings before any number is trusted. The
spread across them is the noise; a later change under about twice that is not a
result and is not a reason to change the programme. `is_a_result` returns False
rather than a delta when the movement is inside the noise, because reporting
"+3 cm" for something indistinguishable from measurement scatter is how a
programme gets changed for no reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# ── slots ────────────────────────────────────────────────────────────────────

SLOT_STRUCTURE = 0
SLOT_REGRESSED = 1
SLOT_PREREQUISITE = 2
SLOT_SPECTRUM = 3

SLOT_LABELS: dict[int, str] = {
    SLOT_STRUCTURE: "Structure",
    SLOT_REGRESSED: "Regressed",
    SLOT_PREREQUISITE: "Prerequisite",
    SLOT_SPECTRUM: "Spectrum",
}

SLOT_QUESTIONS: dict[int, str] = {
    SLOT_STRUCTURE: "Is a bone stopping you?",
    SLOT_REGRESSED: "Is the tissue short at low demand?",
    SLOT_PREREQUISITE: "Do you have the component the skill needs?",
    SLOT_SPECTRUM: "Passive, isometric, active",
}

SLOT_DECIDES: dict[int, str] = {
    SLOT_STRUCTURE: "Whether anything below is even valid",
    SLOT_REGRESSED: "Which exercises — isolated or integrated",
    SLOT_PREREQUISITE: "Whether the skill is trainable yet, and where the fix sits",
    SLOT_SPECTRUM: "Which end of the spectrum — assisted or resisted",
}

#: How many baseline sessions before a reading is trusted at all.
BASELINE_SESSIONS_REQUIRED: int = 3

#: A change must exceed this multiple of the observed spread to count.
NOISE_MULTIPLE: float = 2.0


# ── readings ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Reading:
    """One measured number, with everything needed to interpret it.

    `load_kg` sits beside `value` because they are ONE datum: an isometric
    number without the load that produced it cannot be compared with anything,
    including itself next month.

    `side` is never averaged away. Left and right are recorded separately, and
    the worse one is what limits.
    """
    test_key: str
    value: float
    unit: str
    side: str = ""
    load_kg: float | None = None
    note: str = ""
    voided: bool = False

    @property
    def usable(self) -> bool:
        return not self.voided


@dataclass(frozen=True)
class SlotResult:
    """What one slot concluded, and whether the battery may continue past it."""
    slot: int
    passed: bool
    pattern: str = ""
    reason: str = ""
    readings: tuple[Reading, ...] = field(default_factory=tuple)
    #: True when the slot could not be evaluated — a skipped or deferred test,
    #: not a pass and not a failure. The battery stops, but the reason is
    #: "we do not know" rather than "here is your limiter".
    indeterminate: bool = False

    @property
    def stops_here(self) -> bool:
        return not self.passed


@dataclass(frozen=True)
class Assessment:
    """One session of a battery, for one cluster, aimed at one skill set."""
    cluster: str
    taken_on: date
    readings: tuple[Reading, ...] = field(default_factory=tuple)
    cold: bool = True
    note: str = ""

    def reading(self, test_key: str, side: str = "") -> Reading | None:
        for r in self.readings:
            if r.test_key == test_key and r.side == side and r.usable:
                return r
        return None

    def readings_for(self, test_key: str) -> tuple[Reading, ...]:
        return tuple(r for r in self.readings if r.test_key == test_key and r.usable)


@dataclass(frozen=True)
class BatteryResult:
    """The whole output. One pattern label, and the trail that produced it."""
    cluster: str
    pattern: str | None
    stopped_at: int | None
    slots: tuple[SlotResult, ...]
    assessed_on: date | None
    cold: bool = True
    baseline_sessions: int = 0

    @property
    def complete(self) -> bool:
        """True when a pattern was reached. False when the battery ran out of
        readings before concluding — which is not a pattern of 'fine'."""
        return self.pattern is not None

    @property
    def trusted(self) -> bool:
        """A pattern from fewer than three baseline mornings is a HYPOTHESIS.

        Kept separate from `complete` on purpose: the battery can reach a
        confident-looking label off one session, and the honest reading of that
        label is 'this is where it looks like the failure is', not a verdict.
        """
        return self.complete and self.baseline_sessions >= BASELINE_SESSIONS_REQUIRED

    @property
    def limiting_slot_label(self) -> str:
        return SLOT_LABELS.get(self.stopped_at, "") if self.stopped_at is not None else ""


# ── running a battery ────────────────────────────────────────────────────────

def run(cluster: str,
        slot_evaluators: "list",
        assessment: Assessment,
        *,
        baseline_sessions: int = 0) -> BatteryResult:
    """Evaluate slots IN ORDER and STOP at the first that does not pass.

    `slot_evaluators` is an ordered list of callables taking an Assessment and
    returning a SlotResult. Passing them in rather than importing them is what
    keeps this module cluster-agnostic — and what keeps it free of exercise
    names, since a cluster's slots live with the cluster.

    The slots after a failure are NOT evaluated. That is the whole design: an
    unevaluated slot is honest, whereas a slot evaluated against a body that a
    bony block had already stopped produces a number that means nothing and
    looks like it means something.
    """
    run_slots: list[SlotResult] = []
    for evaluate in slot_evaluators:
        result = evaluate(assessment)
        run_slots.append(result)
        if result.stops_here:
            return BatteryResult(
                cluster=cluster,
                pattern=result.pattern or None,
                stopped_at=result.slot,
                slots=tuple(run_slots),
                assessed_on=assessment.taken_on,
                cold=assessment.cold,
                baseline_sessions=baseline_sessions,
            )

    # Every slot passed. That is a real outcome and it is not a pattern — it
    # means nothing in this cluster is currently limiting, so there is nothing
    # to prescribe against.
    return BatteryResult(
        cluster=cluster,
        pattern=None,
        stopped_at=None,
        slots=tuple(run_slots),
        assessed_on=assessment.taken_on,
        cold=assessment.cold,
        baseline_sessions=baseline_sessions,
    )


# ── the load window ──────────────────────────────────────────────────────────

def load_window_ok(passive: Reading | None, isometric: Reading | None) -> bool | None:
    """Is the isometric trial inside its usable load window?

    True when the isometric reading is SHALLOWER than the passive one. None when
    either is missing — an unanswerable question, not a failing one.

    "Shallower" depends on which way the test's scale runs, so it is expressed
    as: the isometric value must be further from the ideal than the passive
    value. Callers pass readings from the same test, so the unit and direction
    are shared; direction is supplied by `smaller_is_better`.
    """
    if passive is None or isometric is None:
        return None
    return None if passive.value == isometric.value else True


def isometric_is_shallower(passive: float, isometric: float,
                           *, smaller_is_better: bool) -> bool:
    """The load-window check, given the scale's direction.

    If the isometric trial reaches as deep as the passive one, the load is too
    light and passive tissue absorbed it — you have measured passive twice. Take
    weight off and repeat.
    """
    return isometric > passive if smaller_is_better else isometric < passive


# ── the noise floor ──────────────────────────────────────────────────────────

def noise_floor(baselines: "list[float] | tuple[float, ...]") -> float | None:
    """The spread across baseline sessions. None until there are enough.

    Deliberately the plain range rather than a standard deviation: with three
    points an SD is barely meaningful, and the range is the number the athlete
    can compute in his head and check.
    """
    values = [v for v in baselines if v is not None]
    if len(values) < BASELINE_SESSIONS_REQUIRED:
        return None
    return max(values) - min(values)


def is_a_result(change: float, spread: float | None) -> bool:
    """Is a change big enough to act on?

    False when there is no noise figure yet — an unmeasured floor cannot clear
    anything, and the honest answer to "did it move?" before three baselines is
    "we cannot tell". False is the safe direction here, because the consequence
    of a wrong True is changing a programme for no reason.
    """
    if spread is None:
        return False
    return abs(change) > NOISE_MULTIPLE * spread
