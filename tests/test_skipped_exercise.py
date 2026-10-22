"""A skipped exercise is stored as skipped (WP-22, 2026-10-22).

The phone walks every exercise of the session and records each set it
completes, so an exercise it sends with no raw set was skipped. The save used
to fill such an exercise with its prescription (sessions.make_sets_data), as if
it was done: on 2026-10-19 the hip airplane, which the athlete did not do
(his answer, 2026-10-22), was stored as 3 x 10 at 4.5 kg with no set time, and
it fed the tonnage, the weekly dose and the next session's weight. Now it is
stored with its planned sets and none done. A save without the guided flow
(`logged_sets` None) still repeats the prescription, as before.
"""

from __future__ import annotations

from services import session_save
from services import training_session as tsession

LIFT = {"name": "Hip Airplane (Weighted)", "type": "reps", "laterality": "unilateral", "sets": 3,
        "reps": 10, "weight_kg": 5.0, "equipment_type": "dumbbell", "rest_seconds": 60}
DONE = {"name": "Machine Chest Press", "type": "reps", "sets": 3, "reps": 10, "weight_kg": 30.0,
        "equipment_type": "machine", "rest_seconds": 90}
RAW = [{"set_num": n, "completed_at": f"2026-10-22T07:1{n}:00+01:00",
        "right": {"reps": 10, "weight_kg": 30.0}} for n in (1, 2, 3)]


def test_an_exercise_the_flow_recorded_no_set_for_is_stored_with_none_done():
    saved = session_save.exercise_from_flow(LIFT, "ex-skipped", logged_sets=[])
    assert saved.sets == ()
    assert saved.planned_sets == 3


def test_a_save_without_the_flow_still_repeats_the_prescription():
    saved = session_save.exercise_from_flow(LIFT, "ex-no-flow", logged_sets=None)
    assert [(s["reps"], s["weight"]) for s in saved.sets] == [(10, 5.0)] * 3


def test_the_phone_save_reads_an_exercise_without_raw_sets_as_skipped():
    body = {"session_id": "2026-10-22-5c1pped0", "date": "2026-10-22", "kind": "plan",
            "duration_minutes": 50, "session_rpe": 7, "notes": "",
            "exercises": [
                {"exercise_id": "ex-done", "exercise": DONE, "raw_sets": RAW},
                {"exercise_id": "ex-skipped", "exercise": LIFT, "raw_sets": [], "sets": []},
            ]}
    saved = tsession.build_save(body)
    done, skipped = saved.exercises
    assert [s["reps"] for s in done.sets] == [10, 10, 10]
    assert skipped.sets == () and skipped.planned_sets == 3
    # The heart-rate match reads the same records: the skipped exercise has none.
    assert set(tsession.sets_by_name(body)) == {"Machine Chest Press"}
