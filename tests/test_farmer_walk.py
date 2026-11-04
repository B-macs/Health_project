"""WP-47, the farmer walk (the athlete, 2026-11-03): "I want to add farmer
walks into my program"; the goal "General Carrying strength."; "Id rather it in
C - and by time more than distance."; the dose "5. Yes" (three walks of 30-45 s,
the weight up when every walk reaches 45 s, then the aim 34 s); and, to keep C
under 70 minutes, "Move crossover to D"."""
from __future__ import annotations

import goal_block as gb
import goal_week as gw
from services import engine, guided_flow, placement as pl, rules, session_save
from services import sessions as s
from services import training_session as ts

WALK = gb.FARMER_WALK
NAME = "Farmer Walk (DB)"


def _walks(seconds, weight=30.0):
    return [{"reps": 1, "tut": t, "weight": weight} for t in seconds]


def _plan(history, plan_seconds=34, **kw):
    return engine.range_progression(30, 45, history, 30.0, plan_seconds, increment=5.0,
                                    prescribed_sets=3, reading="tut",
                                    aim_step=engine.HOLD_AIM_STEP_SECONDS, **kw)


def test_the_walk_ends_session_c_and_the_crossover_runs_monday_and_friday():
    assert NAME in [e["name"] for e in gb.SESSIONS["C"]]
    assert all(NAME not in [e["name"] for e in gb.SESSIONS[k]] for k in "ABD")
    week = gw.week()
    names = {d: [c.name for c in week[d]] for d in gw.DAYS}
    assert [d for d in gw.DAYS if "Reverse Cable Crossover" in names[d]] == ["Mon", "Fri"]
    for d in ("Thu", "Fri"):
        assert pl.minutes(week[d]) <= pl.SESSION_MINUTES_LIMIT + 0.5, d


def test_the_walk_is_a_dumbbell_in_each_hand_three_walks_of_30_to_45_seconds():
    assert (WALK["type"], WALK["sets"], WALK["equipment_type"]) == ("hold", 3, "dumbbell")
    assert WALK["increment_size"] == gb.DUMBBELL_PAIR_KG == 5.0
    assert (WALK["hold_min"], WALK["hold_max"]) == (30, 45)
    assert WALK["hold_seconds"] == engine.range_middle_bottom(30, 45) == 34


def test_its_record_names_goal_d_in_his_words():
    pick = gw.PICKS[NAME]
    assert pick.goal == "D" and pick.area == "carrying"
    assert "General Carrying strength" in pick.source and "2026-11-03" in pick.source
    assert pick.better


def test_it_lands_on_a_shoulder_rule_never_on_unknown():
    verdict = rules.check_movement(NAME, 2)
    assert verdict["severity"] == "caution"


def test_it_is_timed_on_a_stopwatch_that_counts_up_and_never_starts_by_itself():
    assert s.counts_up(WALK) and not s.is_timed_test(WALK)
    assert ts.timer_kind(WALK) == "stopwatch"
    first = guided_flow.Position(0, 1, 1, guided_flow.INTRO, "right")
    assert not guided_flow.hold_starts_next(WALK, first, "right")


def test_every_walk_at_45_seconds_steps_the_weight_and_the_aim_resets_to_34():
    up = _plan([("2026-11-05", _walks([45, 45, 45]))])
    assert (up["action"], up["weight"], up["aim"]) == ("step_up", 35.0, 34)
    past = _plan([("2026-11-05", _walks([47, 40, 38]))])
    assert past["action"] == "step_up"


def test_between_steps_the_aim_climbs_five_seconds_and_never_past_45():
    held = _plan([("2026-11-05", _walks([40, 36, 33]))])
    assert (held["action"], held["weight"], held["aim"]) == ("hold", 30.0, 38)
    near = _plan([("2026-11-05", _walks([44, 44, 43]))])
    assert near["aim"] == 45


def test_two_sessions_under_30_seconds_take_the_weight_back():
    back = _plan([("2026-11-12", _walks([28, 26, 25])), ("2026-11-05", _walks([30, 28, 27]))])
    assert (back["action"], back["weight"], back["aim"]) == ("step_back", 25.0, 34)


def test_the_session_shows_the_aim_the_range_and_when_the_weight_goes_up():
    history = [("2026-11-05", _walks([40, 36, 33]))]
    lp = {"session_date": "2026-11-05", "weight_kg": 30.0}
    entry = s.resolve_prescription(WALK, lp, "normal", {"reduced": False},
                                   weight_increment=WALK["increment_size"], history=history)
    assert entry["hold_seconds"] == 38 and entry["weight_kg"] == 30.0
    label = s.prescription_label(s.displayed_prescription(WALK, entry))
    assert "38s hold" in label and "(range 30-45s)" in label
    assert entry["next_step"] == ("The weight goes up when every set reaches 45 seconds or one "
                                  "set goes past 45 seconds, in each session of this lift in 7 days.")


def test_the_seconds_typed_are_the_seconds_stored():
    raw = [{"set_num": 1, "completed_at": "2026-11-05T18:00:00+01:00",
            "right": {"reps": None, "weight_kg": 30.0, "seconds": 41}}]
    [record] = session_save.records_from_raw(WALK, raw)
    assert (record["tut"], record["weight"]) == (41, 30.0)
