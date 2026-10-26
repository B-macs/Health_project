"""The 12-week block (goal_block.py, phase 5): what it must stay.

docs/training/goal_system.md holds the decisions, steps 1-8, approved by the
athlete from 2026-10-14 to 2026-10-16. The sessions are written out in
goal_block.py, but they are not authored there: they are what
services/placement.py makes of the cards in goal_week.py. The first tests here
fail the moment the two differ, so a session can only change by changing its
card and placing the week again — never by an edit to one day.
"""
from __future__ import annotations

import re

import pytest

import cluster_a_prescription as rx
import goal_block as gb
import goal_week as gw
import training_constants as tc
import training_plan as tp
from services import placement as pl
from services import rules
from services import sessions as s

WEEK = gw.week()
DAY_OF = {"A": "Mon", "B": "Tue", "C": "Thu", "D": "Fri"}
FIELDS = ("name", "type", "sets", "reps", "hold_seconds", "reps_in_set", "rest_seconds",
          "equipment_type", "laterality")
PLAN = gb.PLAN_GOAL_BLOCK


def _names(exercises) -> list[str]:
    return [e["name"] for e in exercises]


def _every_entry():
    for d, day in PLAN.items():
        for e in day["exercises"] + day.get("home", []):
            yield d, day, e


# ─── The sessions are the placed sessions ───────────────────────────────────

@pytest.mark.parametrize("letter", "ABCD")
def test_each_session_is_the_placed_session_field_for_field(letter):
    placed = [pl.exercise_dict(c) for c in pl.order(WEEK[DAY_OF[letter]])]
    written = gb.SESSIONS[letter]
    assert _names(written) == [c["name"] for c in placed]
    for e, c in zip(written, placed):
        for f in FIELDS:
            assert e.get(f) == c.get(f), (letter, e["name"], f, e.get(f), c.get(f))


@pytest.mark.parametrize("letter", "ABCD")
def test_each_session_models_the_placed_minutes(letter):
    written = s.session_seconds(gb.SESSIONS[letter]) / 60
    assert abs(written - pl.minutes(WEEK[DAY_OF[letter]])) < 0.01


def test_the_core_sessions_meet_the_required_dose_and_no_limit_is_broken():
    core = {d: WEEK[d] for d in gw.CORE_DAYS}
    assert pl.violations(core, gw.SPEC, gw.EXTRA_SETS, gw.EXTRA_DAYS) == []
    assert pl.violations(WEEK, gw.SPEC, gw.EXTRA_SETS, gw.EXTRA_DAYS) == []


def test_the_home_item_is_the_week_s_home_item_on_the_core_days():
    for d, day in PLAN.items():
        home = _names(day.get("home", []))
        if day.get("session_letter") in gb.CORE_LETTERS:
            assert home == list(gw.HOME), d
        else:
            assert home == [], d
    assert set(gw.HOME["Neck Working Stretch (Right)"]["days"]) == {
        DAY_OF[letter] for letter in gb.CORE_LETTERS}


# ─── The week ───────────────────────────────────────────────────────────────

def test_twelve_weeks_in_the_approved_shape():
    """Strength Monday, Tuesday, Thursday and Friday (A to D); rest Wednesday
    and Saturday; flexibility Sunday (athlete, 2026-10-16: "yes agreed")."""
    assert len(PLAN) == gb.WEEKS * 7 == 84
    assert sorted(PLAN) == list(range(1, 85))
    for d, day in PLAN.items():
        weekday = (d - 1) % 7
        if weekday in gb.LETTER_BY_WEEKDAY:
            assert day["day_type"] == "main" and day["shape"] == "full_body", d
            assert day["session_letter"] == gb.LETTER_BY_WEEKDAY[weekday], d
        elif weekday == gb.FLEXIBILITY_WEEKDAY:
            assert day["session_kind"] == "flexibility" and day["day_type"] == "stretch", d
        else:
            assert day["day_type"] == "rest" and day["exercises"] == [], d
    assert dict(zip("ABCD", ("Mon", "Tue", "Thu", "Fri"))) == DAY_OF


def test_the_day_before_the_flexibility_session_is_rest():
    """Every strength day loads the legs; a flexibility session the day after
    one would train tired tissue (step 6)."""
    for d, day in PLAN.items():
        if day.get("session_kind") == "flexibility" and d > 1:
            assert PLAN[d - 1]["day_type"] == "rest", d


def test_no_three_strength_days_in_a_row():
    run = 0
    for d in sorted(PLAN):
        run = run + 1 if PLAN[d]["day_type"] == "main" else 0
        assert run <= 2, d


def test_no_running_in_stage_1():
    """Goal A, stage 1: 4 strength + 1 flexibility, no running until gate 1."""
    for d, _, e in _every_entry():
        assert not re.search(r"\brun", e["name"], re.I), (d, e["name"])
        # The training page reads a timed run or walk as a Garmin activity.
        assert not (e["type"] == "duration" and s.is_run_or_walk(e)), (d, e["name"])


def test_every_day_fits_the_session_shape():
    bad = {d: s.session_shape_violations(day) for d, day in PLAN.items()}
    assert not {d: v for d, v in bad.items() if v}, {d: v for d, v in bad.items() if v}


def test_the_six_exercise_cap_is_replaced_only_on_a_full_body_day():
    """Athlete, 2026-10-16: "yes replace it". The same session read as an
    ordinary gym day breaks the old cap, so the replacement is doing work."""
    day = dict(PLAN[8], shape=None)
    assert any("working exercises" in r for r in s.session_shape_violations(day))
    assert not s.session_shape_violations(PLAN[8])


def test_the_weekly_count_is_five_sessions():
    """Four strength sessions and one flexibility session: the stage-2 limit
    of five (rules.STAGE_CONSTRAINTS)."""
    limit = rules.STAGE_CONSTRAINTS[2]["session_freq_max"]
    for week in range(gb.WEEKS):
        days = [PLAN[week * 7 + i + 1] for i in range(7)]
        assert sum(1 for day in days if day["exercises"]) == limit == 5, week + 1


# ─── What is not in the block ───────────────────────────────────────────────

def test_no_release_block_no_planks_at_the_start_no_hip_lift():
    """Key Rule 6 (the release suspended since 2026-09-22); the planks-at-the-
    start rule retired for this block (2026-10-16); the 90/90 hip lift out
    (2026-10-16: "It doesnt warm up anything and the evidence it fixes the
    issue is weak")."""
    gone = set(s.RELEASE_EXERCISE_NAMES) | {"Forearm Plank", "Full Side Bridge", "90/90 Hip Lift"}
    for d, _, e in _every_entry():
        assert e["name"] not in gone, (d, e["name"])


def test_nothing_is_taken_from_an_old_block():
    """Key Rule 25: every exercise is written in goal_block.py. An object
    shared with training_plan.py would mean an old block's exercise reached
    this one by copying."""
    old = set()
    for name in dir(tp):
        value = getattr(tp, name)
        if isinstance(value, dict) and "mechanics" in value:
            old.add(id(value))
        elif isinstance(value, dict) and name.startswith("PLAN"):
            for day in value.values():
                old |= {id(e) for e in day.get("exercises", [])}
    for d, _, e in _every_entry():
        assert id(e) not in old, (d, e["name"])


def test_no_exercise_carries_a_warning():
    """Key Rule 24: no back warning in any message; the block's stop rules
    are in each exercise's own instructions."""
    for d, _, e in _every_entry():
        assert not e.get("warning"), (d, e["name"])


# ─── Every exercise is recorded, mapped and ruled ───────────────────────────

def test_every_entry_has_a_workflow_record():
    missing = sorted({e["name"] for _, _, e in _every_entry() if gw.pick_for(e["name"]) is None})
    assert not missing, missing


def test_every_entry_is_in_the_three_body_area_maps():
    names = {e["name"] for _, _, e in _every_entry()}
    for table in (tc.EXERCISE_BODY_REGION, tc.EXERCISE_REGION_SHARES, tc.EXERCISE_MOVEMENT_WEIGHT):
        assert not sorted(names - set(table)), sorted(names - set(table))


def test_every_exercise_lands_on_a_safety_rule():
    """'unknown' is not a block and reads like 'cleared'. A measurement is
    exempt: it trains nothing and runs its own protocol."""
    for d, _, e in _every_entry():
        if s.is_measurement(e["name"]):
            continue
        assert rules.check_movement(e["name"], 2)["severity"] != "unknown", (d, e["name"])


# ─── Load ───────────────────────────────────────────────────────────────────

_CARDS = {c.name: c for c in gw.CARDS + gw.BONUS_ORDER}
_STEPS = {"dumbbell": {gb.DUMBBELL_KG, gb.DUMBBELL_PAIR_KG},
          "machine": {gb.MACHINE_KG, gb.PLATE_KG}, "cable": {gb.CABLE_UNIT}}


def _training(day):
    return [e for e in day["exercises"]
            if not (s.is_measurement(e["name"]) or e["name"] in s.PREPARATION_NAMES
                    or e.get("warmup"))]


def test_every_training_exercise_has_three_working_sets():
    """L4 (2026-10-16): fewer exercises with 3 sets each."""
    for d, day in PLAN.items():
        if day["day_type"] == "main":
            for e in _training(day):
                assert e["sets"] == 3, (d, e["name"])


def test_every_loaded_lift_has_the_range_its_kind_takes():
    """8-12 for a compound lift, 10-15 for an isolation or core item
    (approved 2026-10-16). The hip airplane takes the compound range by his
    choice; a body-weight item has no range and its reps are logged as done."""
    for name, c in _CARDS.items():
        e = next(x for day in PLAN.values() for x in day["exercises"] if x["name"] == name)
        if not e.get("equipment_type"):
            assert e["rep_min"] is None and e["rep_max"] is None, name
            continue
        want = gb.COMPOUND_RANGE if (c.kind == "compound" or name == "Hip Airplane (Weighted)") \
            else gb.ISOLATION_RANGE
        assert {"rep_min": e["rep_min"], "rep_max": e["rep_max"]} == want, name


def test_every_step_is_one_he_confirmed():
    """Dumbbells 2.5 kg, a pair 5 kg (2026-10-22); machines 2.5 kg (2026-10-26,
    WP-36); the back extension a 2.5 kg plate (2026-10-16); cables half a unit
    (2026-10-22)."""
    for _, _, e in _every_entry():
        if e.get("equipment_type") in _STEPS and not e.get("warmup"):
            assert e["increment_size"] in _STEPS[e["equipment_type"]], e["name"]
            unit = "unit" if e["equipment_type"] == "cable" else "kg"
            assert e["increment_unit"] == unit, e["name"]
    assert next(e for e in gb.SESSIONS["B"] if e["name"] == "45° Back Extension")[
        "increment_size"] == gb.PLATE_KG


def test_every_machine_steps_two_and_a_half_kg():
    """WP-36 (2026-10-26): the shoulder press machine and every other machine."""
    assert gb.MACHINE_KG == 2.5
    machines = {e["name"]: e["increment_size"] for _, _, e in _every_entry()
                if e.get("equipment_type") == "machine" and not e.get("warmup")
                and e["name"] != "45° Back Extension"}
    assert {"Machine Shoulder Press", "Machine Chest Press", "Hack Squat", "Seated Leg Curl",
            "Adductor Machine (Seated)"} <= set(machines)
    assert set(machines.values()) == {2.5}


def test_every_cable_steps_half_a_unit():
    """His answer, 2026-10-22 ("No on all cables"): half-unit steps on every
    cable, not only the crossover's (his note of 2026-10-19: "1.5 Units for the
    last 2 sets", which the one-unit step could not show)."""
    assert gb.CABLE_UNIT == 0.5
    cables = [e for _, _, e in _every_entry() if e.get("equipment_type") == "cable"]
    assert cables and all(e["increment_size"] == 0.5 for e in cables)


def test_the_crossover_is_one_arm_at_a_time_with_a_short_rest():
    """His note, 2026-10-22: "Reverse cross over cable can only be done single
    hand". One arm at a time adds 3 modelled minutes; 15 s after both arms (his
    answer 5: each arm rests while the other works) keeps session C at or under
    70, and the right arm still stops at the line of the body."""
    for letter in ("A", "C"):
        e = next(x for x in gb.SESSIONS[letter] if x["name"] == "Reverse Cable Crossover")
        assert e["laterality"] == "unilateral" and e["rest_seconds"] == 15
        assert "one arm, then the other" in e["mechanics"] and "RIGHT, not behind it" in e["mechanics"]
    assert s.session_seconds(gb.SESSIONS["C"]) / 60 <= pl.SESSION_MINUTES_LIMIT


def test_the_walking_lunge_is_one_set_for_both_legs():
    """His note, 2026-10-22: "walking lunge you walk so you do both right and
    left at the same time". It is alternating: one tap ends a set, and the
    reps shown are each leg's."""
    from services import guided_flow
    for letter in ("A", "D"):
        lunge = next(x for x in gb.SESSIONS[letter] if x["name"] == "Walking Lunge (DB)")
        assert lunge["laterality"] == "alternating"
        working = [st for st in guided_flow.walk([lunge], "right") if st["phase"] != "resting"]
        assert len(working) == lunge["sets"], "one entry per set, no side steps"
        assert "each side" in s.prescription_label(lunge)


def test_an_alternating_set_counts_both_legs_in_the_tonnage():
    """The same three sets of 10 at 15 kg count 900 kg whether the lunge is
    read as one side at a time (its record before 2026-10-22) or alternating:
    both legs did 10 reps in every set (sessions.logged_sides)."""
    from datetime import date

    from services import tonnage
    rows = [{"movement_name": "Walking Lunge (DB)", "session_date": "2026-10-19",
             "sets": [{"set_num": n, "reps": 10, "weight": 15.0} for n in (1, 2, 3)]}]
    regions = {"Walking Lunge (DB)": "lower_body"}
    for sides_trait in (2, s.logged_sides({"laterality": "alternating"})):
        series, _ = tonnage.weekly_tonnage(rows, regions, today=date(2026, 10, 22), weeks=1,
                                           traits={"Walking Lunge (DB)": {"sides": sides_trait,
                                                                          "unit": "kg"}})
        assert series[-1].sectors["lower_body"].kg == 900.0
    assert s.exercise_traits()["Walking Lunge (DB)"]["sides"] == 2
    assert s.sides({"laterality": "alternating"}) == 1, "the time model counts the set once"


def test_the_posterior_stabilizing_line_has_the_knee_bent():
    """His note, 2026-10-22: "Stabilising line should mention that you need to
    Bend your knee", and his answer: the knee was bent on 2026-10-19, so the
    text catches up with the position and week 12 repeats it."""
    line = next(e for e in gb.PLANK_TEST if e["name"] == "Bunkie — Posterior Stabilizing Line (Timed)")
    assert "knee bent to about 90 degrees" in line["mechanics"]
    assert "straight" not in line["mechanics"]


def test_his_dumbbells_go_up_in_2_5_kg():
    """His answer, 2026-10-22: every dumbbell goes 2.5 to 40 kg in 2.5 kg steps
    (his notes of 2026-10-19/20: a 15 kg lunge, a 40 kg RDL, a 25 kg ramp set).
    A pair is logged as the total, so it steps both dumbbells: 5 kg."""
    assert gb.DUMBBELL_KG == 2.5
    assert gb.DUMBBELL_PAIR_KG == 2 * gb.DUMBBELL_KG
    for name in ("Walking Lunge (DB)", "Romanian Deadlift (DB)"):
        e = next(x for day in PLAN.values() for x in day["exercises"] if x["name"] == name)
        assert e["increment_size"] == gb.DUMBBELL_PAIR_KG, name


def test_a_starting_weight_is_a_real_dumbbell():
    for _, _, e in _every_entry():
        if e.get("equipment_type") == "dumbbell" and e.get("weight_kg") is not None:
            steps = e["weight_kg"] / e["increment_size"]
            assert abs(steps - round(steps)) < 1e-9 and steps >= 1, e["name"]


def test_a_ramp_has_no_weight_of_its_own_and_sits_before_its_lift():
    for d, day in PLAN.items():
        names = _names(day["exercises"])
        for i, e in enumerate(day["exercises"]):
            if e["name"].endswith(s.RAMP_SUFFIX):
                assert e["warmup"] and e["weight_kg"] is None and e["sets"] == 1, (d, e["name"])
                assert s.base_name(names[i + 1]) == s.base_name(e["name"]), (d, e["name"])
                assert e["increment_size"] == day["exercises"][i + 1]["increment_size"]


# ─── The test days ──────────────────────────────────────────────────────────

def test_the_plank_test_runs_in_weeks_1_and_12_in_place_of_session_a_s_abs():
    for week in range(1, gb.WEEKS + 1):
        day = PLAN[(week - 1) * 7 + 1]
        names = _names(day["exercises"])
        bunkie = [n for n in names if n.startswith("Bunkie")]
        if week in gb.TEST_WEEKS:
            assert bunkie == _names(gb.PLANK_TEST), week
            usual = _names(gb.SESSIONS["A"])
            crunch = usual.index("Lat-Pulldown Cable Crunch (Facing Away)")
            assert names[names.index(bunkie[0]) - 1] == usual[crunch - 1], week
            assert "Lat-Pulldown Cable Crunch (Facing Away)" not in names
            # Everything else in session A stays, the walking lunge included.
            assert names == usual[:crunch] + bunkie + usual[crunch + 1:], week
        else:
            assert not bunkie and day["exercises"] == gb.SESSIONS["A"], week
    for d, day in PLAN.items():
        if (d - 1) % 7:
            assert not [n for n in _names(day["exercises"]) if n.startswith("Bunkie")], d


def test_the_test_mondays_run_over_70_minutes_by_his_choice():
    """With the five timed lines in place of the abs, session A models 73
    minutes (2026-10-22: the one-arm crossover added 2, and the walking lunge,
    now one set for both legs, took 2 away).
    Asked whether the walking lunge should give way, he kept it (2026-10-16:
    "Leave it in for those days"), so the limit reads the training and not the
    test inside it: the day passes the shape check while its full time stays
    visible here."""
    full = s.session_seconds(PLAN[1]["exercises"]) / 60
    training = s.session_seconds(
        [e for e in PLAN[1]["exercises"] if not s.is_measurement(e["name"])]) / 60
    assert full > pl.SESSION_MINUTES_LIMIT and round(full) == 73
    assert training <= pl.SESSION_MINUTES_LIMIT
    assert "Walking Lunge (DB)" in _names(PLAN[1]["exercises"])
    assert not s.session_shape_violations(PLAN[1])
    assert not s.session_shape_violations(PLAN[78])


def test_only_a_test_is_left_out_of_the_minutes():
    """The same Monday with its timed lines read as training breaks the
    limit: the check leaves out measurements and nothing else."""
    as_training = [dict(e, name=e["name"].replace(" (Timed)", "")) for e in PLAN[1]["exercises"]]
    day = dict(PLAN[1], exercises=as_training)
    assert any("min with measured changeovers" in r for r in s.session_shape_violations(day))


def test_the_sunday_tests_run_first_and_in_a_fixed_order():
    for week in range(1, gb.WEEKS + 1):
        names = _names(PLAN[week * 7]["exercises"])
        want = []
        if week in gb.FLEX_RETEST_WEEKS:
            want.extend(gb.FLEXIBILITY_TEST_NAMES)
        assert names[:len(want)] == want, week
        assert names[len(want):] == _names(gb.FLEX_STACK), week


def test_the_rib_and_pelvis_test_is_not_in_the_block():
    """Removed on his note of 2026-10-26 (WP-34): "it was not requested and its
    explanation is unclear"."""
    for d, _, e in _every_entry():
        assert "Rib and Pelvis" not in e["name"], d
    assert "Rib and Pelvis Test (Test)" not in gw.PICKS
    assert not hasattr(gb, "RIB_AND_PELVIS_TEST")


def test_the_grip_grade_is_not_in_the_block():
    """Moving Block B's Wednesday grip grade to Sunday was put to him and he
    declined (2026-10-16: "b drop it"): Key Rule 6's release now comes back
    only if the hip symptoms return."""
    for d, _, e in _every_entry():
        assert "Grip Grade" not in e["name"], d
    assert "Upper Glute Grip Grade (Test)" not in gw.PICKS


def test_no_test_morning_follows_a_leg_day():
    """The flexibility retest is never the morning after leg work (his rule,
    2026-08-07): Saturday is rest."""
    for week in gb.FLEX_RETEST_WEEKS:
        assert PLAN[week * 7 - 1]["day_type"] == "rest"


# ─── The Sunday session is the prescription ─────────────────────────────────

def test_the_sunday_session_is_the_prescription_for_the_last_reading():
    stack = rx.prescribe(gb.FLEX_PATTERN).live_items
    assert _names(gb.FLEX_STACK) == [i.exercise for i in stack]
    for e, item in zip(gb.FLEX_STACK, stack):
        n = re.findall(r"\d+", item.dose)
        if e["type"] == "hold":
            assert [str(e["sets"]), str(e["hold_seconds"])] == n[:2], e["name"]
        elif e["type"] == "hold_reps":
            assert [str(e["reps_in_set"]), str(e["hold_seconds"])] == n[:2], e["name"]
        else:
            assert [str(e["sets"]), str(e["reps"])] == n[:2], e["name"]
        if item.note:
            assert item.note in e["mechanics"], e["name"]


def test_the_right_hip_cue_is_on_the_lift_offs():
    """'Neutral or slight internal rotation on the right' (the prescription's
    pattern D, mechanics Part 5) — the lift-offs flex the right hip under its
    own effort."""
    e = next(x for x in gb.FLEX_STACK if x["name"] == "90/90 hip rotations with lift-offs")
    assert "internal rotation on the right" in e["mechanics"]


def test_the_flexibility_pattern_is_the_stored_reading():
    assert gb.FLEX_PATTERN == "D"


# ─── The right side ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", [
    "Standing Psoas March", "Walking Lunge (DB)", "Hack Squat", "Standing Cable Hip Flexion",
    "Hip Airplane (Weighted)"])
def test_a_right_hip_flexion_item_carries_the_kneecap_cue(name):
    """Key Rule 7: right hip flexion past 60 degrees takes a neutral or
    inward-rotation cue (finding #4)."""
    e = next(x for day in PLAN.values() for x in day["exercises"] if x["name"] == name)
    assert re.search(r"RIGHT.*kneecap points straight ahead|kneecap points straight ahead",
                     e["mechanics"]), name


# ─── The load helpers the block needs (services/sessions.py) ────────────────

@pytest.mark.parametrize("logged,step,down,want", [
    (40.5, 5.0, False, 40.0),    # a 2.25 kg-step total reads as the nearest real pair
    (40.5, 5.0, True, 40.0),
    (13.5, 5.0, False, 15.0),    # the walking lunge of 2026-10-19: 15 kg, his note
    (13.5, 5.0, True, 10.0),     # a day that may not go up never rounds up
    (45.5, 5.0, False, 45.0),    # a step up from 40.5 lands on a real pair
    (22.5, 2.5, False, 22.5),    # his row is a real dumbbell
    (4.5, 2.5, False, 5.0),      # the hip airplane's 2.25 kg-step weight
    (None, 2.5, False, None),
    (1.0, 2.5, False, 1.0),      # under one step: left as it is
])
def test_a_dumbbell_weight_is_whole_dumbbells(logged, step, down, want):
    assert s.whole_dumbbells(logged, step, down=down) == want


def test_the_resolved_dumbbell_weight_is_whole_dumbbells():
    """His RDL was logged at 40.5 kg under the 2.25 kg steps on 2026-10-20 (his
    note: "40kg x 10"); the block reads it as 40 (two 20 kg dumbbells) and
    steps from there, both dumbbells one size up."""
    rdl = next(e for e in gb.SESSIONS["B"] if e["name"] == "Romanian Deadlift (DB)")
    sets = [{"reps": 10, "weight": 40.5}] * 3
    entry = s.resolve_prescription(
        rdl, {"session_date": "2026-10-20", "reps": 10, "weight_kg": 40.5}, "normal",
        {"reduced": False, "volume_factor": 1.0},
        weight_increment=rdl["increment_size"], last_session_sets=sets,
        history=[("2026-10-20", sets)])
    assert entry["weight_kg"] == 40.0 and entry["action"] == "hold"
    up = [{"reps": 12, "weight": 40.0}] * 3
    entry = s.resolve_prescription(
        rdl, {"session_date": "2026-10-20", "reps": 12, "weight_kg": 40.0}, "normal",
        {"reduced": False, "volume_factor": 1.0},
        weight_increment=rdl["increment_size"], last_session_sets=up,
        history=[("2026-10-20", up)])
    assert entry["weight_kg"] == 45.0 and entry["action"] == "step_up"


def test_a_ramp_follows_its_lift_at_about_60_percent():
    b = gb.SESSIONS["B"]
    i = _names(b).index("Romanian Deadlift (Ramp Set)")
    assert s.ramp_lift_index(b, i) == i + 1
    assert s.ramp_lift_index(b, i + 1) is None
    entry = s.ramp_entry(b[i], {"weight_kg": 45.0})
    # 60% of 45 is 27, rounded down to a real pair of dumbbells (5 kg steps).
    assert entry["weight_kg"] == 25.0 and entry["reps"] == 6 and entry["source"] == s.RAMP_SOURCE
    assert s.ramp_weight_kg(60.0, gb.MACHINE_KG) == 35.0      # 36 rounded down to the step
    assert s.ramp_weight_kg(0.0, gb.PLATE_KG) == 0.0
    assert "60%" in s.actual_caption(entry)


def test_a_ramp_with_its_own_weight_does_not_follow():
    """Block B authored its ramp weights; they stay its own."""
    day = tp.PLAN_BLOCK_B[1]["exercises"]
    for i, e in enumerate(day):
        if e["name"].endswith(s.RAMP_SUFFIX):
            assert s.ramp_lift_index(day, i) is None


def test_a_first_session_says_the_start_is_light():
    lift = next(e for e in gb.SESSIONS["A"] if e["name"] == "Machine Chest Press")
    entry = s.resolve_prescription(lift, None, "normal", {"reduced": False, "volume_factor": 1.0},
                                   weight_increment=lift["increment_size"], history=[])
    assert entry["source"] == "plan_default"
    assert "light start" in s.actual_caption(entry)


def test_a_planned_rest_day_is_recognised():
    assert s.is_planned_rest(PLAN[3]) and s.is_planned_rest(PLAN[6])
    assert not s.is_planned_rest(PLAN[1]) and not s.is_planned_rest(PLAN[7])
    assert not s.is_planned_rest(None)
