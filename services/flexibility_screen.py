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


# ─── The screen, served (GET /api/insights/flexibility and the capture
#     actions; rebuild Phase 2, milestone 5) ──────────────────────────────────

class CaptureRefused(ValueError):
    """A capture action that cannot be taken: `code` names why."""

    def __init__(self, code: str, details: list[str] | None = None):
        super().__init__(code if not details else f"{code}: {'; '.join(details)}")
        self.code = code


def reading_out(r: btry.Reading) -> dict:
    return {"test_key": r.test_key, "side": r.side, "value": r.value, "unit": r.unit,
            "load_kg": r.load_kg, "setup_value": r.setup_value, "voided": r.voided}


def test_out(test, earlier: tuple = (), draft: btry.Assessment | None = None) -> dict:
    """One test's protocol as the capture screen shows it, with the setup
    number to offer back when it has one (prior_setup) and whether the step
    takes an added load (an isometric spectrum test: load and reading are
    one datum)."""
    prior, from_earlier = (prior_setup(draft, earlier, test.key)
                           if draft is not None and test.setup_input else (None, False))
    return {
        "key": test.key, "label": test.label, "unit": test.unit, "slot": test.slot,
        "slot_label": btry.SLOT_LABELS[test.slot], "bilateral": test.bilateral,
        "setup": test.setup, "lock": test.lock, "measurement": test.measurement,
        "what_youre_testing": test.what_youre_testing, "adapted_from": test.adapted_from,
        "safety": test.safety, "input_hint": test.input_hint,
        "setup_input": test.setup_input,
        "takes_load": test.slot == btry.SLOT_SPECTRUM and "isometric" in test.key,
        "prior_setup": prior, "prior_setup_from_earlier": from_earlier,
    }


def guide() -> dict:
    """The protocol's fixed explanations, as the cluster modules write them:
    the three measures, the gap, the lock, the setup numbers, the progression
    variable, the nerve check and the medial knee note, the slots and why
    they run in order, and the tests held back for now."""
    import cluster_a_battery as cba
    import flexibility_baselines as fb
    moving_name, moving_why = fb.PROGRESSION_VARIABLE
    return {
        "measures": [{"measure": m, "short": s, "long": lg}
                     for m, s, lg in fb.MEASURES_EXPLAINED],
        "gap": fb.GAP_EXPLAINED, "lock": fb.LOCK_EXPLAINED,
        "frozen": [{"name": n, "why": w} for n, w in fb.FROZEN_CONSTANTS],
        "progression_variable": {"name": moving_name, "why": moving_why},
        "nerve_check": cba.NERVE_CHECK, "medial_knee_note": cba.MEDIAL_KNEE_NOTE,
        "slots": [{"slot": s, "label": btry.SLOT_LABELS[s], "question": btry.SLOT_QUESTIONS[s],
                   "decides": btry.SLOT_DECIDES[s]}
                  for s in (btry.SLOT_REGRESSED, btry.SLOT_PREREQUISITE, btry.SLOT_SPECTRUM)],
        "held_back": [{"key": k, "label": cba.TESTS[k].label,
                       "until": cba.TESTS[k].deferred_until, "safety": cba.TESTS[k].safety}
                      for k in cba.DEFERRED_TESTS],
        "test_count": len(_battery().AVAILABLE_TESTS),
    }


#: The how-to fields of a stack exercise (cluster_a_mechanics.Exercise).
EXERCISE_DETAIL_FIELDS = ("spectrum", "position", "movement", "feel", "stop", "progress",
                          "note", "adapted_from", "reverts_when", "deferred_until")


def _exercise_detail(name: str) -> dict | None:
    import cluster_a_mechanics as cam
    ex = cam.exercise(name)
    if ex is None:
        return None
    return {k: getattr(ex, k, "") or "" for k in EXERCISE_DETAIL_FIELDS}


def report_out(repo, report, today: date) -> dict:
    """The populated screen: the pattern (or why there is none, with the one
    or two readings the battery is waiting on), whether it is trusted yet,
    the ladder (top rung first), the stack with each exercise's how-to, the
    slots run and the ones not run (F10), every reading, and the retest
    status."""
    import cluster_a_prescription as cap
    result = report.result
    slots = result.slots if result else ()
    out = {
        "assessed_on": report.assessed_on, "pattern": report.pattern,
        "pattern_label": report.pattern_label, "trusted": report.trusted,
        "cold": bool(result.cold) if result else True,
        "baseline_sessions": result.baseline_sessions if result else 0,
        "baseline_required": btry.BASELINE_SESSIONS_REQUIRED,
        "reason": slots[-1].reason if slots else "",
        "ladder": [{"key": r.key, "label": r.label, "muscle": r.muscle, "state": r.state,
                    "unit": r.unit, "measured": r.measured, "target": r.target,
                    "fraction": r.fraction, "detail": r.detail, "pattern": r.pattern,
                    "provisional": r.provisional} for r in reversed(report.ladder)],
        "slots": [{"slot": s.slot, "label": btry.SLOT_LABELS[s.slot],
                   "question": btry.SLOT_QUESTIONS[s.slot], "passed": s.passed,
                   "indeterminate": s.indeterminate, "basis": s.basis, "reason": s.reason}
                  for s in slots],
        "slots_total": slots_total(report),
        "slots_not_run": slots_not_run(report),
        "readings": [reading_out(r) for r in (slots[-1].readings or ())] if slots else [],
        "missing": [],
        "stack": None,
        "stack_refused": "",
        "retest": None,
        "retest_text": cap.RETEST,
    }
    if not report.pattern:
        stored = repo.get_flexibility_assessments()
        if stored:
            out["missing"] = [{"test_key": m.test_key, "side": m.side, "setup": m.setup,
                               "label": m.label, "hint": m.hint}
                              for m in missing_inputs(stored[-1], report)]
    else:
        try:
            stack = fx.prescribe(report)
        except cap.NoPatternError as exc:
            out["stack_refused"] = str(exc)
        else:
            out["stack"] = {
                "pattern": stack.pattern, "limiter": stack.limiter, "outro": stack.outro,
                "items": [{"exercise": i.exercise, "dose": i.dose, "note": i.note,
                           "detail": _exercise_detail(i.exercise)} for i in stack.live_items],
                "held_back": [{"exercise": i.exercise, "detail": _exercise_detail(i.exercise)}
                              for i in stack.items if i.deferred]}
    if report.assessed_on:
        try:
            status, reason = fx.retest_readiness(
                report.assessed_on, today,
                fx.leg_loading_days(repo.get_recent_sessions(days=60, today=today)))
            out["retest"] = {"status": status, "reason": reason}
        except Exception:
            out["retest"] = None
    return out


def capture_out(repo, today: date, draft: btry.Assessment) -> dict:
    """The capture screen for a draft: today's order with each test's
    protocol, the tests done, the readings in so far, the battery's early
    answer (a pattern: stop here, a reading below a failure cannot be
    interpreted), the skip notes and the progress."""
    import cluster_a_battery as cba
    try:
        earlier = repo.get_flexibility_assessments()
    except Exception:
        earlier = ()
    order = capture_order(draft)
    battery = _battery(draft.cluster)
    live = live_result(draft)
    done, total = fx.capture_progress(draft, draft.cluster)
    return {
        "cluster": draft.cluster, "taken_on": draft.taken_on, "cold": draft.cold,
        "order": [test_out(battery.TESTS[k], earlier, draft) for k in order],
        "done": [k for k in order if any(r.test_key == k and r.usable for r in draft.readings)],
        "readings": [reading_out(r) for r in draft.readings],
        "early_pattern": live.pattern,
        "early_pattern_label": cba.PATTERNS.get(live.pattern, "") if live.pattern else "",
        "skip_notes": skip_notes(draft),
        "progress": {"done": done, "total": total},
    }


def screen(repo, today: date) -> dict:
    """Insights › Flexibility: "empty" (no assessment yet) or "populated"
    with the report; a draft in progress rides along as `capture`, and the
    guide and the leg-day warning are always there."""
    try:
        data = read_data(repo, today)
    except Exception as exc:
        # "Could not read the flexibility record", never an empty one (I26).
        return {"state": "unreadable", "load_error": f"{type(exc).__name__}: {exc}",
                "count": 0, "report": None, "capture": None,
                "legs_loaded_yesterday": False, "guide": guide()}
    try:
        draft = repo.get_flexibility_draft()
    except Exception:
        draft = None
    return {
        "state": "populated" if data["count"] else "empty",
        "load_error": None,
        "count": data["count"],
        "report": report_out(repo, data["report"], today) if data["count"] else None,
        "capture": capture_out(repo, today, draft) if draft is not None else None,
        "legs_loaded_yesterday": legs_loaded_yesterday(repo, today),
        "guide": guide(),
    }


def start_capture(repo, today: date, cold: bool) -> dict:
    """Begin an assessment of the caller's day (cold or warm) and store it
    as the draft; the store keeps it, so a restart loses nothing (F13). An
    assessment already in progress is answered, never replaced."""
    draft = repo.get_flexibility_draft()
    if draft is None:
        draft = begin(today, cold)
        repo.save_flexibility_draft(draft)
    return capture_out(repo, today, draft)


def record_step(repo, today: date, test_key: str, entered: dict, *, load: float | None = None,
                setup_value: float | None = None, void: bool = False) -> dict:
    """One step's readings into the draft (apply_entries), stored, and the
    capture screen as it now stands, with the battery's early answer."""
    draft = repo.get_flexibility_draft()
    if draft is None:
        raise CaptureRefused("no_capture")
    if test_key not in capture_order(draft):
        raise CaptureRefused("unknown_test", [test_key])
    test = _battery(draft.cluster).TESTS[test_key]
    sides = {"left", "right"} if test.bilateral else {""}
    if set(entered) - sides:
        raise CaptureRefused("unknown_side", sorted(set(entered) - sides))
    updated = apply_entries(draft, test_key, entered, load=load, setup_value=setup_value,
                            void=void)
    repo.save_flexibility_draft(updated)
    return capture_out(repo, today, updated)


def cancel_capture(repo) -> None:
    """Drop the assessment in progress."""
    repo.clear_flexibility_draft()


def finish_capture(repo, today: date) -> dict:
    """Store the draft as an assessment and answer the screen."""
    draft = repo.get_flexibility_draft()
    if draft is None:
        raise CaptureRefused("no_capture")
    finish(repo, draft)
    return screen(repo, today)


def add_missing(repo, today: date, entries: list[dict]) -> dict:
    """The readings the battery is waiting on, merged into the latest
    assessment (fill_missing) and stored, so the battery re-runs over them
    by the path a live reading takes."""
    import cluster_a_battery as cba
    stored = repo.get_flexibility_assessments()
    if not stored:
        raise CaptureRefused("no_assessment")
    entered = {}
    for e in entries:
        if e.get("test_key") not in cba.TESTS:
            raise CaptureRefused("unknown_test", [str(e.get("test_key"))])
        entered[cba.MissingInput(e["test_key"], e.get("side") or "",
                                 bool(e.get("setup")))] = e.get("value")
    updated = fill_missing(stored[-1], entered)
    if updated is stored[-1]:
        raise CaptureRefused("nothing_entered")
    repo.save_flexibility_assessment(updated)
    return screen(repo, today)
