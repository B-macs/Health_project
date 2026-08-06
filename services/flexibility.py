"""
services/flexibility.py — skill scores, ladder rungs, and the passive-active gap.

Pure functions only. No I/O, no Streamlit, no hidden clock reads — every
date-dependent function takes an explicit `today`, same convention as
services/engine.py, services/strength.py and services/body_composition.py.

Read flexibility_baselines.py's module docstring first; it carries the model.

THE ONE RULE: MINIMUM, NOT MEAN
-------------------------------
A skill's score is the LOWEST rung on its ladder, and the name of that rung is
returned beside it. Averaging is what v1 did and it is exactly how a broken
capacity hides behind healthy ones — the `hip` score averaged fourteen
contributions across five unrelated capacities while Deep Lunge, the only thing
testing hip extension, scored 100.

If the ankle stops you at 38 it does not matter that the quads are at 84: you
still cannot squat. `limiting_rung` is therefore a first-class output, not a
diagnostic afterthought — it is the only part of the result that says what to
train.

THREE MEASURES, AND THE GAP
---------------------------
    PASSIVE    the ceiling
    ISOMETRIC  is the range defended
    ACTIVE     the usable range

`gap = passive - active`. For a Beighton 6/9 athlete this is the number that
decides the prescription: a WIDE gap means the range is already there and
cannot be held, so more stretching is the wrong lever and resisted/isometric
work is the right one. A NARROW gap means chase range.

The rung's own score is taken from ACTIVE where it exists, because usable range
is what limits a skill — a passive ceiling you cannot enter under your own
power does not help you squat. Passive is descriptive; it is half of the gap
and it is never the score on its own when an active reading exists.

WHAT WAS DELETED, AND MUST NOT COME BACK
----------------------------------------
v1 scored a self-rated "depth" on a TWO-SIDED band: full marks in 50-70,
penalised below AND above, so a rating of 88 scored 46. The athlete refuted it
correctly — his rating measured HOW FAR HE GOT, and penalising high values
treated it as if it measured ABSENCE OF MUSCULAR CONTROL. Those are different
things and v1 inferred one from the other with no evidence.

Achievement is now monotonic: more is always better, and the hypermobility
concern lives in the gap, where it can be measured instead of assumed. The
names `band_score`, `control_score`, `CONTROL_BAND`, `OVERSHOOT_SLOPE` and
`UNDERSHOOT_EXPONENT` are gone and a test fails loudly if any returns — the
defect survived review once, so it gets a guard rather than a comment.

WHAT THIS MODULE REFUSES TO DO
------------------------------
No flexibility age in years (the gym ships one and it compares a Jan-2025
measurement against a live chronological age). No averaging of rungs into a
skill. No scoring a rung from the 22 legacy pose ratings, which answer neither
question. No filling an unmeasured rung from a neighbour or a training note.
Nothing here reaches the engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import flexibility_baselines as _fb

# ── tunables ─────────────────────────────────────────────────────────────────

#: An assessment's confidence halves every this many days. ROM is slow-changing,
#: so a year is generous rather than punitive.
CONFIDENCE_HALFLIFE_DAYS: float = 365.0

#: A passive-minus-active gap at or above this is called wide, i.e. the rung
#: needs STRENGTH rather than RANGE. Provisional: it is set from the general
#: hypermobility literature rather than from this athlete's own data, because
#: he has no paired readings yet. Revisit once ASSESSMENTS has entries.
WIDE_GAP_POINTS: float = 25.0

PRESCRIPTION_RANGE = "range"
PRESCRIPTION_STRENGTH = "strength"
PRESCRIPTION_UNKNOWN = "unknown"


# ── results ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MeasureScore:
    measure: str
    raw: float
    score: float
    unit: str


@dataclass(frozen=True)
class RungScore:
    key: str
    label: str
    side: str
    passive: MeasureScore | None
    isometric: MeasureScore | None
    active: MeasureScore | None

    @property
    def score(self) -> float | None:
        """Usable range. ACTIVE where it exists, else isometric, else passive.

        Deliberately prefers the most self-generated reading available: a
        passive ceiling nobody can enter under their own power does not limit a
        skill any less for being high.
        """
        for m in (self.active, self.isometric, self.passive):
            if m is not None:
                return m.score
        return None

    @property
    def gap(self) -> float | None:
        if self.passive is None or self.active is None:
            return None
        return self.passive.score - self.active.score

    @property
    def prescription(self) -> str:
        g = self.gap
        if g is None:
            return PRESCRIPTION_UNKNOWN
        return PRESCRIPTION_STRENGTH if g >= WIDE_GAP_POINTS else PRESCRIPTION_RANGE

    @property
    def measured(self) -> bool:
        return self.score is not None


@dataclass(frozen=True)
class SkillScore:
    key: str
    label: str
    score: float | None
    limiting_rung: str | None
    limiting_label: str | None
    goal_level: float
    rungs: tuple[RungScore, ...]
    unmeasured_rungs: tuple[str, ...]
    #: Set when the skill is in the catalogue but cannot be chosen as a target
    #: until a clinician clears it. It still SCORES — hiding the number would
    #: lose the regression signal, which is the only reason to track a skill
    #: nobody is training toward.
    blocked_reason: str = ""

    @property
    def needs_signoff(self) -> bool:
        return bool(self.blocked_reason)

    @property
    def clears_goal(self) -> bool:
        return self.score is not None and self.score >= self.goal_level

    @property
    def complete(self) -> bool:
        """True when every rung on the ladder has a reading. A skill scored on a
        partial ladder can only ever be an UPPER BOUND — an unmeasured rung
        might be lower than anything seen so far."""
        return not self.unmeasured_rungs


@dataclass(frozen=True)
class Prescription:
    """What to actually do, for ONE target skill.

    This is the output the whole sector exists to produce, and the reason it is
    keyed on a target: a limiting rung is only actionable against a goal. The
    athlete's objection to the previous design was exactly this — "when you say
    chest/pecs is the limiting factor, what skill am I working towards? chest
    and pecs are only the limiting factor if I want a handstand or a bridge; if
    my first goal is a pancake then hamstrings matter more."
    """
    skill_key: str
    skill_label: str
    limiting_rung: str | None
    limiting_label: str
    limiting_score: float | None
    #: The steps of the skill's stack that move the limiting rung. May be empty
    #: when the skill has no stack built yet — an honest "nothing to do here
    #: yet" beats inventing a stretch.
    stretches: tuple[_fb.Stretch, ...]
    #: RANGE or STRENGTH, off the passive-active gap on the limiting rung.
    prescription: str
    complete: bool
    unmeasured_rungs: tuple[str, ...]


@dataclass(frozen=True)
class RungDelta:
    """One rung's movement between two assessments."""
    key: str
    label: str
    before: float | None
    after: float | None

    @property
    def delta(self) -> float | None:
        if self.before is None or self.after is None:
            return None
        return self.after - self.before

    @property
    def improved(self) -> bool:
        d = self.delta
        return d is not None and d > 0


@dataclass(frozen=True)
class FlexibilityReport:
    skills: tuple[SkillScore, ...]
    rungs: tuple[RungScore, ...]
    assessed_on: date | None
    confidence: float
    cold: bool
    target_skill: str = ""

    @property
    def measured_rung_count(self) -> int:
        """DISTINCT rungs, not readings. A bilateral test produces two readings
        for one rung, so counting readings displayed "19 of 14"."""
        return len({r.key for r in self.rungs if r.measured})

    @property
    def gap_count(self) -> int:
        return len({r.key for r in self.rungs if r.gap is not None})


# ── scoring ──────────────────────────────────────────────────────────────────

def rung_score(value: float, test: _fb.RungTest) -> float:
    """Linear interpolation between the test's own 0 and 100 anchors, clamped.

    MONOTONIC BY CONSTRUCTION — there is no upper penalty and there must never
    be one. Handles both scale directions without a special case, because
    several tests measure a gap that shrinks as capacity improves (elbows to
    floor: 0 cm is perfect) while others measure a distance that grows
    (knee-to-wall: 12 cm is perfect).
    """
    lo, hi = test.value_at_0, test.value_at_100
    if lo == hi:
        raise ValueError(f"{test.key}: value_at_0 and value_at_100 are identical")
    return max(0.0, min(100.0, (value - lo) / (hi - lo) * 100.0))


def staleness_confidence(measured_on: date, today: date) -> float:
    """Halves every CONFIDENCE_HALFLIFE_DAYS. A future date yields 1.0 rather
    than >1.0 — a clock skew must not manufacture confidence."""
    days = max(0, (today - measured_on).days)
    return 0.5 ** (days / CONFIDENCE_HALFLIFE_DAYS)


def score_reading(reading: _fb.RungReading) -> RungScore:
    test = _fb.RUNGS[reading.rung]

    def one(measure: str, raw: float | None) -> MeasureScore | None:
        if raw is None:
            return None
        return MeasureScore(measure=measure, raw=raw,
                            score=rung_score(raw, test), unit=test.unit)

    return RungScore(
        key=reading.rung, label=test.label, side=reading.side,
        passive=one(_fb.PASSIVE, reading.passive),
        isometric=one(_fb.ISOMETRIC, reading.isometric),
        active=one(_fb.ACTIVE, reading.active),
    )


def score_skill(skill: _fb.Skill, rungs: dict[str, RungScore]) -> SkillScore:
    """min(rungs), and the name of the rung that produced it.

    A bilateral rung appears once per side; the WORSE side is the one that
    limits, because a skill is performed by the whole body and the weak side
    stops it. Sides are never averaged.
    """
    on_ladder = [rungs[k] for k in skill.ladder if k in rungs and rungs[k].measured]
    unmeasured = tuple(k for k in skill.ladder
                       if k not in rungs or not rungs[k].measured)

    if not on_ladder:
        return SkillScore(
            key=skill.key, label=skill.label, score=None,
            limiting_rung=None, limiting_label=None, goal_level=skill.goal_level,
            rungs=(), unmeasured_rungs=unmeasured,
            blocked_reason=skill.blocked_reason,
        )

    worst = min(on_ladder, key=lambda r: r.score)
    return SkillScore(
        key=skill.key, label=skill.label, score=worst.score,
        limiting_rung=worst.key, limiting_label=worst.label,
        goal_level=skill.goal_level, rungs=tuple(on_ladder),
        unmeasured_rungs=unmeasured, blocked_reason=skill.blocked_reason,
    )


def report(
    assessment: _fb.Assessment | None = None,
    today: date | None = None,
) -> FlexibilityReport:
    """The whole sector, from one assessment.

    Defaults to the most recent recorded assessment, which is currently NONE —
    every skill then scores None with its whole ladder unmeasured, and that is
    the correct and honest empty state rather than a zero.
    """
    if today is None:
        today = date.today()
    if assessment is None:
        assessment = _fb.ASSESSMENTS[-1] if _fb.ASSESSMENTS else None

    scored: list[RungScore] = []
    if assessment is not None:
        scored = [score_reading(r) for r in assessment.readings]

    # Worst side wins per rung key — see score_skill's docstring.
    by_key: dict[str, RungScore] = {}
    for r in scored:
        if not r.measured:
            continue
        prev = by_key.get(r.key)
        if prev is None or r.score < prev.score:
            by_key[r.key] = r

    skills = tuple(
        score_skill(skill, by_key) for skill in _fb.SKILLS.values()
    )

    confidence = (staleness_confidence(assessment.taken_on, today)
                  if assessment is not None else 0.0)

    return FlexibilityReport(
        skills=skills,
        rungs=tuple(scored),
        assessed_on=assessment.taken_on if assessment else None,
        confidence=confidence,
        cold=assessment.cold if assessment else True,
        target_skill=assessment.target_skill if assessment else "",
    )


# ── one target at a time ─────────────────────────────────────────────────────

def prescribe(rep: FlexibilityReport, skill_key: str = "") -> Prescription | None:
    """The limiting rung of ONE skill, and the steps that move it.

    Defaults to the report's own target — the skill chosen before the tests
    were taken. None if the skill is unknown.

    Deliberately NOT filtered by whether the skill is selectable: a blocked
    skill still scores and still shows a limiting rung, it simply has no stack,
    so `stretches` comes back empty. Hiding the score would lose the regression
    signal, which is the reason a blocked skill is tracked at all.
    """
    key = skill_key or rep.target_skill or _fb.DEFAULT_TARGET_SKILL
    skill = _fb.SKILLS.get(key)
    if skill is None:
        return None

    score = next((s for s in rep.skills if s.key == key), None)
    limiting = score.limiting_rung if score else None

    # Only the steps that move the rung actually limiting the skill. The rest
    # of the stack is not wrong, it is just not the next thing — and handing
    # over five stretches when one rung is the blocker is how "come to
    # conclusions on where to focus" turns back into a list.
    stretches = tuple(s for s in skill.stack if limiting and limiting in s.targets)

    # Fall back to the whole stack only when nothing is measured yet, so a
    # freshly-chosen target still shows its route rather than an empty panel.
    if limiting is None:
        stretches = skill.stack

    rung = next((r for r in rep.rungs if r.key == limiting), None) if limiting else None
    return Prescription(
        skill_key=key,
        skill_label=skill.label,
        limiting_rung=limiting,
        limiting_label=score.limiting_label if score else "",
        limiting_score=score.score if score else None,
        stretches=stretches,
        prescription=rung.prescription if rung else PRESCRIPTION_UNKNOWN,
        complete=bool(score.complete) if score else False,
        unmeasured_rungs=tuple(score.unmeasured_rungs) if score else (),
    )


def compare(before: FlexibilityReport, after: FlexibilityReport) -> tuple[RungDelta, ...]:
    """Per-rung movement between two assessments, worst side each time.

    Shown after a re-test and before the athlete decides whether to stay on the
    current skill or switch. That decision is the one place the whole model
    pays off, and it cannot be made against a single column of numbers.

    Rungs measured in only one of the two assessments are INCLUDED with a None
    on the missing side rather than dropped: "we did not measure this last
    time" is information, and silently omitting it makes a partial re-test look
    like a complete one.
    """
    def worst(rep: FlexibilityReport) -> dict[str, RungScore]:
        out: dict[str, RungScore] = {}
        for r in rep.rungs:
            if not r.measured:
                continue
            if r.key not in out or r.score < out[r.key].score:
                out[r.key] = r
        return out

    b, a = worst(before), worst(after)
    return tuple(
        RungDelta(
            key=key,
            label=_fb.RUNGS[key].label,
            before=b[key].score if key in b else None,
            after=a[key].score if key in a else None,
        )
        for key in _fb.RUNGS if key in b or key in a
    )


# ── serialisation ────────────────────────────────────────────────────────────
#
# Pure dict <-> dataclass, so the store underneath can be a JSON file, a Sheets
# tab or anything else without this module knowing. services/repository.py owns
# where it actually lands, the same way it owns every other storage decision.

SCHEMA_VERSION: int = 1


def assessment_to_dict(a: _fb.Assessment) -> dict:
    return {
        "schema": SCHEMA_VERSION,
        "taken_on": a.taken_on.isoformat(),
        "cold": a.cold,
        "note": a.note,
        "target_skill": a.target_skill,
        "readings": [
            {"rung": r.rung, "side": r.side, "note": r.note,
             "passive": r.passive, "isometric": r.isometric, "active": r.active}
            for r in a.readings
        ],
    }


def assessment_from_dict(d: dict) -> _fb.Assessment | None:
    """None for anything unreadable — an unknown schema, a missing date, or a
    reading naming a rung that no longer exists.

    Returning None rather than raising is deliberate: a stored assessment that
    cannot be understood must degrade to "no assessment", which the screen
    already renders honestly. A half-parsed one would silently score a ladder
    against rungs it does not have.
    """
    if not isinstance(d, dict) or d.get("schema") != SCHEMA_VERSION:
        return None
    try:
        taken_on = date.fromisoformat(d["taken_on"])
    except (KeyError, TypeError, ValueError):
        return None

    readings = []
    for raw in d.get("readings") or []:
        rung = raw.get("rung")
        if rung not in _fb.RUNGS:
            continue
        readings.append(_fb.RungReading(
            rung=rung, side=raw.get("side") or "", note=raw.get("note") or "",
            passive=raw.get("passive"), isometric=raw.get("isometric"),
            active=raw.get("active"),
        ))
    # An unknown target degrades to "" rather than rejecting the assessment:
    # the readings are still good data, and a renamed skill must not delete a
    # session's worth of measurements taken on the floor.
    target = d.get("target_skill") or ""
    if target not in _fb.SKILLS:
        target = ""

    return _fb.Assessment(taken_on=taken_on, readings=tuple(readings),
                          cold=bool(d.get("cold", True)), note=d.get("note") or "",
                          target_skill=target)


def merge_reading(assessment: _fb.Assessment,
                  reading: _fb.RungReading) -> _fb.Assessment:
    """Replace any existing reading for the same (rung, side), else append.

    Re-entering a test overwrites rather than accumulating, so a corrected
    trial does not leave the bad one in the record to be picked up by the
    worse-side rule.
    """
    kept = tuple(r for r in assessment.readings
                 if not (r.rung == reading.rung and r.side == reading.side))
    return _fb.Assessment(taken_on=assessment.taken_on, cold=assessment.cold,
                          note=assessment.note, readings=kept + (reading,))


def assessment_progress(assessment: _fb.Assessment | None) -> tuple[int, int]:
    """(rungs with at least one reading, total rungs)."""
    if assessment is None:
        return 0, len(_fb.RUNGS)
    done = {r.rung for r in assessment.readings
            if r.passive is not None or r.isometric is not None or r.active is not None}
    return len(done), len(_fb.RUNGS)


# ── the scheduling window ────────────────────────────────────────────────────

def flexibility_window(
    today: date,
    hard_session_days: set[date] | frozenset[date],
    *,
    is_rest_day: bool = False,
    same_day_pm: bool = False,
) -> tuple[str, str]:
    """(window, reason) for a given day. ADVISORY ONLY — nothing reads this into
    the engine.

    The heuristic comes from the athlete's source brief. Its physiological
    mechanism is NOT encoded and NOT relied on: the calpain-mediated central
    fatigue story is stated well past what the evidence carries, and is treated
    as motivation the way services/sleep_fusion.py treats the abandoned
    quiet-wake rule.

    `is_rest_day` is accepted but deliberately does NOT downgrade the window on
    its own — see flexibility_baselines.REST_DAY_CONFLICT_UNRESOLVED. A
    restorative flow on a rest day is fine; an adaptation-seeking session is the
    thing the rule calls worst, and nothing in this codebase yet distinguishes
    them. Downgrading here would penalise the harmless case.
    """
    if today in hard_session_days:
        if same_day_pm:
            return _fb.WINDOW_GOOD, ("same day, PM, after an AM session — the fatigue signal "
                                     "has not landed yet")
        return _fb.WINDOW_OK, "immediately after training — reduce the volume of both"

    days_since = [(today - d).days for d in hard_session_days if (today - d).days > 0]
    if not days_since:
        return _fb.WINDOW_GOOD, "no recent hard session on record"

    since = min(days_since)
    if since == 1:
        return _fb.WINDOW_POOR, ("the day after a hard session — the worst slot for the "
                                 "adaptation this is trying to produce")
    return _fb.WINDOW_GOOD, f"{since} days since the last hard session"
