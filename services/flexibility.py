"""
services/flexibility.py — the one place the three layers are joined.

Pure functions. No I/O, no Streamlit, no hidden clock reads — every
date-dependent function takes an explicit `today`, the same convention as
services/engine.py and services/strength.py.

    Mechanics tells you what is worth testing.
    Battery produces a pattern.
    Prescription looks the pattern up.

This module walks that chain and nothing else. It holds no tests, no exercises
and no doses of its own; when it needs one it asks the layer that owns it.

WHAT THIS REPLACED, so nobody rebuilds it
------------------------------------------
v2 scored fourteen rungs, took min() per skill, and reported a number out of
100. That was deleted on 2026-08-06 along with the rung tests, the skill
ladders and the stretch stacks. The names `rung_score`, `score_skill`,
`SkillScore`, `WIDE_GAP_POINTS`, `RUNGS` and `SKILLS` are gone and a test fails
loudly if any returns. Before that, v1 scored a self-rated depth on a two-sided
band where a rating of 88 scored 46; that guard is still here too, because a
defect that survived one review earns a permanent one.

The reason is not that min() was badly implemented. It is that the battery is a
DECISION TREE WITH EARLY EXIT and min() is a scoring function over everything.
A failing slot 0 does not make slots 1-3 lower priority, it makes them
meaningless — there is no value in a spectrum profile for a skill a bony block
had already made unavailable.

WHAT THIS MODULE REFUSES TO DO
------------------------------
No score out of 100 — the battery's output is a pattern label and, in the
source's words, "nothing else". No flexibility age in years. No prescription
without a pattern; `prescribe` raises rather than guessing. No averaging of
anything with anything. No reading carried over from the legacy gym goniometry
or the 22 pose ratings, which answer none of the battery's questions. Nothing
here reaches the engine — flexibility is not a safety input, and services/rules
remains the only thing that constrains movement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import cluster_a_battery as _a_battery
import cluster_a_mechanics as _a_mech
import cluster_a_prescription as _a_rx
import flexibility_baselines as _fb
from services import battery as _b

# ── clusters ─────────────────────────────────────────────────────────────────

#: Every cluster the app knows about. One entry today; the shape is what makes
#: adding a second one a data change rather than a code change.
CLUSTERS: dict[str, dict] = {
    "a": {
        "key": "a",
        "label": _a_mech.CLUSTER_LABEL,
        "skills": _a_mech.SKILLS,
        "mechanics": _a_mech,
        "battery": _a_battery,
        "prescription": _a_rx,
    },
}

DEFAULT_CLUSTER: str = "a"

#: An assessment's confidence halves every this many days. Range of motion is
#: slow-changing, so a year is generous rather than punitive. Staleness decays
#: WEIGHT, never VALUE — decaying a stale reading would invent a decline nobody
#: measured.
CONFIDENCE_HALFLIFE_DAYS: float = 365.0


# ── results ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Report:
    """Everything the screen needs, from one assessment."""
    cluster: str
    cluster_label: str
    result: _b.BatteryResult | None
    confidence: float
    assessed_on: date | None

    @property
    def measured(self) -> bool:
        return self.result is not None

    @property
    def pattern(self) -> str | None:
        return self.result.pattern if self.result else None

    @property
    def pattern_label(self) -> str:
        if not self.pattern:
            return ""
        return _a_battery.PATTERNS.get(self.pattern, "")

    @property
    def trusted(self) -> bool:
        """False until three baseline mornings exist. A pattern off one session
        is a HYPOTHESIS about where the failure is, not a verdict."""
        return bool(self.result and self.result.trusted)

    @property
    def stopped_at_label(self) -> str:
        return self.result.limiting_slot_label if self.result else ""


def cluster(key: str = DEFAULT_CLUSTER) -> dict:
    return CLUSTERS[key]


# ── the chain ────────────────────────────────────────────────────────────────

def assess(assessment: _b.Assessment | None,
           today: date,
           *,
           baseline_sessions: int = 0) -> Report:
    """Run the battery for an assessment's cluster and wrap the result.

    `None` in gives an honest empty report rather than a zero — no assessment
    has been run, and a zero would read as "measured, and bad".
    """
    if assessment is None:
        return Report(cluster=DEFAULT_CLUSTER,
                      cluster_label=CLUSTERS[DEFAULT_CLUSTER]["label"],
                      result=None, confidence=0.0, assessed_on=None)

    spec = CLUSTERS.get(assessment.cluster, CLUSTERS[DEFAULT_CLUSTER])
    result = _b.run(spec["key"], spec["battery"].SLOT_EVALUATORS, assessment,
                    baseline_sessions=baseline_sessions)
    return Report(
        cluster=spec["key"],
        cluster_label=spec["label"],
        result=result,
        confidence=staleness_confidence(assessment.taken_on, today),
        assessed_on=assessment.taken_on,
    )


def prescribe(report: Report):
    """The stack for a report's pattern. RAISES when there is no pattern.

    Deliberately not `-> Stack | None`. A None return invites a caller to render
    an empty panel and move on, which is how "we do not know what to train" gets
    quietly displayed as "nothing to train". The refusal carries the reason and
    the caller has to handle it.
    """
    spec = CLUSTERS.get(report.cluster, CLUSTERS[DEFAULT_CLUSTER])
    return spec["prescription"].prescribe(report.pattern)


def release_block_for(stack) -> tuple:
    """The pre-session protocol appropriate to a stack.

    A stack loads the right hip actively if it contains lift-offs or a squat
    pattern, which is what adds the Coxa Saltans tendon-path drill. Derived from
    the stack rather than hard-coded per pattern, so a stack edit cannot leave
    the protocol behind.
    """
    loaded = any(
        any(k in item.exercise.lower() for k in ("lift-off", "squat", "rotation"))
        for item in stack.live_items
    )
    return _a_rx.release_block(hip_focused=True, right_hip_loaded=loaded)


# ── staleness ────────────────────────────────────────────────────────────────

def staleness_confidence(measured_on: date, today: date) -> float:
    """Halves every CONFIDENCE_HALFLIFE_DAYS. Clamped to 1.0 for future dates.

    Decays WEIGHT, never VALUE.
    """
    days = (today - measured_on).days
    if days <= 0:
        return 1.0
    return float(0.5 ** (days / CONFIDENCE_HALFLIFE_DAYS))


# ── progress through a capture session ───────────────────────────────────────

def capture_progress(assessment: _b.Assessment | None,
                     cluster_key: str = DEFAULT_CLUSTER) -> tuple[int, int]:
    """(tests with any usable reading, tests available). Distinct TESTS, not
    readings — a bilateral test produces two readings for one test, and counting
    readings once displayed "19 of 14" in the model this replaced."""
    spec = CLUSTERS[cluster_key]
    available = spec["battery"].AVAILABLE_TESTS
    if assessment is None:
        return 0, len(available)
    done = {r.test_key for r in assessment.readings if r.usable and r.test_key in available}
    return len(done), len(available)


def merge_reading(assessment: _b.Assessment, reading: _b.Reading) -> _b.Assessment:
    """Replace any existing reading for the same (test, side), then append.

    (test_key, side) is the identity. Re-entering a test overwrites rather than
    accumulating, and the other side survives untouched.

    EVERY FIELD of the assessment is carried through explicitly. The version of
    this in the model it replaced silently dropped one, which was masked in
    practice because the dropped field had only one possible value at the time.
    """
    kept = tuple(r for r in assessment.readings
                 if not (r.test_key == reading.test_key and r.side == reading.side))
    return _b.Assessment(
        cluster=assessment.cluster,
        taken_on=assessment.taken_on,
        readings=kept + (reading,),
        cold=assessment.cold,
        note=assessment.note,
    )


# ── serialisation ────────────────────────────────────────────────────────────
#
# Pure dict <-> dataclass, so the store underneath can be a JSON file, a Sheets
# tab or anything else without this module knowing. services/repository.py owns
# where it actually lands.

SCHEMA_VERSION: int = 2


def assessment_to_dict(a: _b.Assessment) -> dict:
    return {
        "schema": SCHEMA_VERSION,
        "cluster": a.cluster,
        "taken_on": a.taken_on.isoformat(),
        "cold": a.cold,
        "note": a.note,
        "readings": [
            {"test_key": r.test_key, "value": r.value, "unit": r.unit, "side": r.side,
             "load_kg": r.load_kg, "setup_value": r.setup_value,
             "note": r.note, "voided": r.voided}
            for r in a.readings
        ],
    }


def assessment_from_dict(d: dict) -> _b.Assessment | None:
    """None for anything unreadable — an unknown schema, a missing date, or a
    reading naming a test that no longer exists.

    Returning None rather than raising is deliberate: a stored assessment that
    cannot be understood must degrade to "no assessment", which the screen
    renders honestly. A half-parsed one would run a battery against readings it
    does not have.

    `setup_value` was ADDED without a schema bump, on purpose: it is optional and
    absent payloads parse to None, so an assessment recorded before it existed
    still loads. Bumping would have silently dropped the athlete's first real
    session, which is a far worse outcome than a missing setup number.

    NOTE the schema bump to 2. Version 1 held the retired rung model, and a v1
    payload is not convertible — its readings measured different positions with
    different landmarks. It is dropped rather than migrated, which is safe
    because no v1 assessment was ever recorded.
    """
    if not isinstance(d, dict) or d.get("schema") != SCHEMA_VERSION:
        return None
    try:
        taken_on = date.fromisoformat(d["taken_on"])
    except (KeyError, TypeError, ValueError):
        return None

    cluster_key = d.get("cluster") or DEFAULT_CLUSTER
    if cluster_key not in CLUSTERS:
        return None
    known = CLUSTERS[cluster_key]["battery"].TESTS

    readings = []
    for raw in d.get("readings") or []:
        key = raw.get("test_key")
        if key not in known:
            continue
        try:
            value = float(raw["value"])
        except (KeyError, TypeError, ValueError):
            continue
        readings.append(_b.Reading(
            test_key=key, value=value, unit=raw.get("unit") or "",
            side=raw.get("side") or "", load_kg=raw.get("load_kg"),
            setup_value=raw.get("setup_value"),
            note=raw.get("note") or "", voided=bool(raw.get("voided")),
        ))

    return _b.Assessment(cluster=cluster_key, taken_on=taken_on, readings=tuple(readings),
                         cold=bool(d.get("cold", True)), note=d.get("note") or "")


# ── the scheduling window ────────────────────────────────────────────────────

def flexibility_window(today: date,
                       hard_session_days: set[date] | frozenset[date],
                       *,
                       is_rest_day: bool = False,
                       same_day_pm: bool = False) -> tuple[str, str]:
    """(window, reason) for a given day. ADVISORY — nothing reads this into the
    engine.

    The physiological mechanism behind the ranking is NOT encoded and NOT relied
    on: the calpain-mediated central-fatigue story in the source is stated well
    past what the evidence carries, and the source's own "what to hold loosely"
    section says so. It is treated as motivation, the way
    services/sleep_fusion.py treats the abandoned quiet-wake rule. The practical
    ordering survives whether or not the mechanism does.

    REST DAYS, resolved 2026-08-06. This used to accept `is_rest_day` and
    deliberately ignore it, because nothing distinguished a restorative flow
    from an adaptation-seeking session. The Prescription's dosage section
    settles it: a cluster session is adaptation-seeking by definition and is
    never a rest-day activity. A restorative yoga flow on a rest day remains
    fine — that is services/yoga.py's business, not this function's.
    """
    if is_rest_day:
        return _fb.WINDOW_POOR, ("a rest day — flexibility training is training, not "
                                 "recovery, and this is the slot the rule calls worst")
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
        return _fb.WINDOW_POOR, ("the day after a hard session — peak fatigue, minimum "
                                 "adaptation")
    return _fb.WINDOW_GOOD, f"{since} days since the last hard session"
