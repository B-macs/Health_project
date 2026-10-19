"""Insights › Flexibility's rules (move INS-3, rebuild Phase 2, 2026-10-19), so
the phone's assessment screens follow the Streamlit page step for step: the
screen's read, the capture flow (its order, its progress ticks, the battery's
early answer, the leg-day check, the setup number offered back, the readings
merged in), filling in a missing reading, and the slot counts.

The METHOD stays where it is: services/battery.py runs the slots and stops at
the first failure, the cluster module (cluster_a_battery.py) owns its tests
and their order, and services/flexibility.py joins the layers. This module
only asks them, so a screen can never disagree with the evaluator.

Fault F10: the populated screen printed "of 4 slots run" and counted "4 minus
the slots run" as not measured, with the 4 typed in; the battery has three
slots since gate 0 was removed, so a full run read "3 of 4" and claimed a slot
was skipped. The count is the battery's own (slots_total).
"""

from __future__ import annotations

from datetime import date, timedelta

from services import battery as btry
from services import flexibility as fx


def _battery(cluster: str | None = None):
    return fx.CLUSTERS.get(cluster or fx.DEFAULT_CLUSTER, fx.CLUSTERS[fx.DEFAULT_CLUSTER])["battery"]


def read_data(repo, today: date) -> dict:
    """{"report", "count"}: the latest assessment run through the battery,
    with every stored assessment counted toward the baseline mornings."""
    stored = repo.get_flexibility_assessments()
    latest = stored[-1] if stored else None
    return {"report": fx.assess(latest, today, baseline_sessions=len(stored)),
            "count": len(stored)}


def slots_total(report) -> int:
    """How many slots the report's battery has (fault F10)."""
    return len(_battery(report.cluster).SLOT_EVALUATORS)


def slots_not_run(report) -> int:
    """Slots below the one that stopped: not measured, by the method."""
    run = len(report.result.slots) if report.result else 0
    return max(0, slots_total(report) - run)


# ─── The capture flow ────────────────────────────────────────────────────────

def begin(today: date, cold: bool, cluster: str | None = None) -> btry.Assessment:
    """A new, empty assessment of today, cold or warm."""
    return btry.Assessment(cluster=cluster or fx.DEFAULT_CLUSTER, taken_on=today,
                           readings=(), cold=cold)


def capture_order(draft: btry.Assessment) -> list[str]:
    """The tests to take, in order, asked of the battery module (a neutral
    reading well off the floor puts a comparison out of scope)."""
    battery = _battery(draft.cluster)
    applicable = getattr(battery, "applicable_tests", None)
    return list(applicable(draft) if applicable else battery.AVAILABLE_TESTS)


def skip_notes(draft: btry.Assessment) -> list[str]:
    """Why each test not in today's order is skipped, as the module words it."""
    battery = _battery(draft.cluster)
    order = set(capture_order(draft))
    notes = getattr(battery, "SKIP_NOTES", {})
    return [notes[key] for key in battery.AVAILABLE_TESTS
            if key not in order and notes.get(key)]


def clamp_step(step: int, order: list[str]) -> int:
    return max(0, min(int(step), len(order) - 1))


def step_ticks(order: list[str], step: int, draft: btry.Assessment | None) -> list[str]:
    """One tick per test: "now", "done" (a usable reading is in) or ""."""
    done = {r.test_key for r in draft.readings if r.usable} if draft else set()
    return ["now" if i == step else ("done" if key in done else "")
            for i, key in enumerate(order)]


def live_result(draft: btry.Assessment):
    """The battery run over what is in so far. A pattern means the slot that
    stopped has answered: a reading below a failure cannot be interpreted,
    so collecting more wastes the session."""
    return btry.run(draft.cluster, _battery(draft.cluster).SLOT_EVALUATORS, draft)


def legs_loaded_yesterday(repo, today: date) -> bool:
    """Yesterday's session loaded the legs: a cold reading today measures
    the leg day, not the baseline. A warning, never a block; a failed read is
    no warning."""
    try:
        return (today - timedelta(days=1)) in fx.leg_loading_days(
            repo.get_recent_sessions(days=3, today=today))
    except Exception:
        return False


def prior_setup(draft: btry.Assessment, earlier: tuple, test_key: str) -> tuple[float | None, bool]:
    """The setup number to offer back for a test, and whether it came from
    an earlier assessment. The setup number is the SAME every session by
    design: re-measuring it fresh by eye makes two sessions incomparable."""
    own = next((r.setup_value for r in draft.readings
                if r.test_key == test_key and r.setup_value is not None), None)
    if own is not None:
        return own, False
    for past in reversed(earlier or ()):
        value = next((r.setup_value for r in past.readings
                      if r.test_key == test_key and r.setup_value is not None), None)
        if value is not None:
            return value, True
    return None, False


def apply_entries(draft: btry.Assessment, test_key: str, entered: dict[str, float | None], *,
                  load: float | None = None, setup_value: float | None = None,
                  void: bool = False) -> btry.Assessment:
    """The step's readings merged into the draft, one per side typed (a side
    left blank is not a reading). Load and setup number travel with each
    reading: they are one datum."""
    test = _battery(draft.cluster).TESTS[test_key]
    updated = draft
    for side, value in entered.items():
        if value is None:
            continue
        updated = fx.merge_reading(updated, btry.Reading(
            test_key=test_key, value=float(value), unit=test.unit, side=side,
            load_kg=load, setup_value=setup_value, voided=bool(void)))
    return updated


def missing_inputs(assessment: btry.Assessment, report) -> list:
    """The one or two readings the battery is waiting on (the cluster module
    decides which)."""
    return list(_battery(assessment.cluster).missing_inputs(assessment, report.result))


def fill_missing(assessment: btry.Assessment, entered: dict) -> btry.Assessment:
    """The missing readings merged into the stored assessment, so the battery
    re-runs over them by the path a live reading takes. A setup number joins
    the reading it belongs to, every other field carried through."""
    battery = _battery(assessment.cluster)
    updated = assessment
    for item, value in entered.items():
        if value is None:
            continue
        if item.setup:
            existing = updated.reading(item.test_key)
            if existing is None:
                continue
            updated = fx.merge_reading(updated, btry.Reading(
                test_key=existing.test_key, value=existing.value, unit=existing.unit,
                side=existing.side, load_kg=existing.load_kg, setup_value=float(value),
                note=existing.note, voided=existing.voided))
        else:
            updated = fx.merge_reading(updated, btry.Reading(
                test_key=item.test_key, value=float(value),
                unit=battery.TESTS[item.test_key].unit, side=item.side))
    return updated


def finish(repo, draft: btry.Assessment) -> None:
    """Store the assessment, then drop the draft."""
    repo.save_flexibility_assessment(draft)
    repo.clear_flexibility_draft()
