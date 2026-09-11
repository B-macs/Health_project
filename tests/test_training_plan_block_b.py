"""Tests for training_plan.PLAN_BLOCK_B — Block B, the race build, Phase 4.

Carries Stage 2B's scheduling, safety and map invariants forward, and pins the
things this block is the first to do: the session shape (Key Rule 21) on every
gym day, ramp and top sets nested under their own lift, one hip-flexor item per
gym day, the running build that restarts from Block A's actual run history and
ends on race day, and the removals the block header records with their revert
conditions.
"""

from __future__ import annotations

import pytest

import training_constants as tc
import training_plan as tp
from services import flexibility as fx, rules, scheduling as sch, sessions as sess

PLAN = tp.PLAN_BLOCK_B
DAYS = sorted(PLAN)
ALL_EXERCISES = [(d, ex) for d in DAYS for ex in PLAN[d]["exercises"]]
NAMES = sorted({ex["name"] for _d, ex in ALL_EXERCISES})
GYM_DAYS = [d for d in DAYS if PLAN[d]["day_type"] == "main"]
SQUAT_DAYS = [1, 8, 15, 22]
PRESS_DAYS = [5, 12, 19, 26]
RUN_DAYS = [2, 6, 9, 13, 16, 20, 23]


def _names(d):
    return [e["name"] for e in PLAN[d]["exercises"]]


def _ex(d, name):
    return next(e for e in PLAN[d]["exercises"] if e["name"] == name)


# ── shape ───────────────────────────────────────────────────────────────────

def test_the_block_is_twenty_eight_days_and_race_day_is_the_last():
    assert DAYS == list(range(1, 29))
    assert PLAN[28]["day_type"] == "test"
    assert "RACE DAY" in PLAN[28]["objective"]
    assert any("10 km Running" in n for n in _names(28))


def test_every_day_has_exercises_an_rpe_target_and_the_phase_name():
    for d in DAYS:
        assert PLAN[d]["exercises"], d
        assert isinstance(PLAN[d]["session_rpe_target"], int), d
        assert PLAN[d]["phase"] == tp._BB_PHASE, d


def test_every_exercise_carries_a_weight_key():
    for d, ex in ALL_EXERCISES:
        assert "weight_kg" in ex, f"day {d}: {ex['name']}"


def test_the_block_is_registered_at_the_same_clinical_stage():
    assert sess.plan_dict_for_phase(4) is PLAN
    assert sess.PHASE_META[4]["stage"] == 2, (
        "a block change is not a stage change; Block A's exit criteria gate the "
        "latter and are mostly untested")
    assert sess.PHASE_META[4]["name"] == tp._BB_PHASE


def test_the_block_is_next_in_line_after_stage_2b():
    from services.models import Phase
    phases = [Phase(phase_number=n, name=str(n), start_date=d, length_days=k, status=st)
              for n, d, k, st in ((1, "2026-06-29", 21, "completed"),
                                   (2, "2026-07-20", 28, "completed"),
                                   (3, "2026-08-17", 28, "active"))]
    assert sess.next_phase_offer(phases) == 4


# ── the scheduling contract ─────────────────────────────────────────────────

def test_every_day_carries_a_valid_day_type():
    for d in DAYS:
        assert PLAN[d].get("day_type") in sch.SESSION_PRIORITY, d


def test_day_type_main_matches_is_gym_session():
    for d in DAYS:
        assert (PLAN[d]["day_type"] == "main") == bool(PLAN[d].get("is_gym_session")), d


def test_the_week_is_the_same_shape_every_week():
    """Mon squat, Tue run, Wed mobility, Thu cluster, Fri press, Sat run, Sun
    rest — race week swaps Saturday's run for rest and Sunday's rest for the
    race. Key rule 18b: the week is the unit."""
    assert GYM_DAYS == SQUAT_DAYS + PRESS_DAYS or sorted(GYM_DAYS) == sorted(SQUAT_DAYS + PRESS_DAYS)
    for d in SQUAT_DAYS:
        assert "Squat" in PLAN[d]["objective"], d
    for d in PRESS_DAYS:
        assert "Press" in PLAN[d]["objective"], d
    for d in RUN_DAYS:
        assert PLAN[d]["day_type"] == "stretch" and "Run" in PLAN[d]["objective"], d
    for d in (3, 10, 17, 24):
        assert "Mobility" in PLAN[d]["objective"] and PLAN[d]["day_type"] == "rest", d
    for d in (4, 11, 18, 25):
        assert "Cluster A" in PLAN[d]["objective"] and PLAN[d]["day_type"] == "stretch", d
    for d in (7, 14, 21, 27):
        assert PLAN[d]["day_type"] == "rest" and "Rest" in PLAN[d]["objective"], d


def test_every_gym_day_is_followed_by_a_strictly_lower_priority_day():
    for d in GYM_DAYS:
        if d + 1 in PLAN:
            assert sch.SESSION_PRIORITY[PLAN[d + 1]["day_type"]] < sch.SESSION_PRIORITY["main"], d


def test_no_two_main_days_are_adjacent():
    assert not [d for d in GYM_DAYS if d + 1 in GYM_DAYS]


def test_race_day_is_not_the_day_after_a_main_session_or_a_run():
    assert PLAN[27]["day_type"] == "rest"


def test_five_sessions_a_week_at_most():
    cap = rules.STAGE_CONSTRAINTS[2]["session_freq_max"]
    for week in range(4):
        days = range(week * 7 + 1, week * 7 + 8)
        sessions = [d for d in days if PLAN[d]["day_type"] != "rest"]
        assert len(sessions) <= cap, f"week {week + 1} has {len(sessions)} sessions"


def test_the_cluster_session_never_lands_on_a_rest_day_or_after_leg_work():
    leg_days = {
        d for d in DAYS for e in PLAN[d]["exercises"]
        if tc.EXERCISE_BODY_REGION.get(e["name"]) == "lower_body"
        and e["name"] not in fx.RELEASE_EXERCISES
    }
    for d in (4, 11, 18, 25):
        assert PLAN[d]["day_type"] != "rest"
        assert d - 1 not in leg_days, f"cluster day {d} follows leg work on day {d - 1}"


# ── KEY RULE 21: the session shape ──────────────────────────────────────────

def test_no_day_breaks_the_session_shape_rules():
    bad = {d: sess.session_shape_violations(PLAN[d]) for d in DAYS}
    bad = {d: v for d, v in bad.items() if v}
    assert not bad, "\n".join(f"day {d}: {'; '.join(v)}" for d, v in bad.items())


def test_every_gym_day_is_three_main_lifts_one_core_item_one_hip_item():
    for d in SQUAT_DAYS:
        assert sess.working_families(PLAN[d]["exercises"]) == [
            "Goblet Squat", "Romanian Deadlift", "Hip Thrust", "Pallof Press",
            "End-Range Psoas Isometric"], d
    for d in PRESS_DAYS:
        assert sess.working_families(PLAN[d]["exercises"]) == [
            "Incline DB Press", "Lat Pulldown", "Single-Arm DB Row", "Face Pull",
            "Full Side Bridge", "Half-Kneeling Knee-Hover Isometric"], d


def test_every_gym_day_fits_the_hour_with_measured_changeovers():
    """Over 60 is fine, 84 is not — the athlete's words. Stage 2B day 22 read
    92 on this model against 54 on the old one."""
    for d in GYM_DAYS:
        minutes = sess.estimate_duration(PLAN[d]["exercises"])
        assert minutes <= sess.SESSION_SHAPE["max_gym_minutes"], f"day {d}: {minutes} min"
        assert minutes >= 40, f"day {d}: {minutes} min — a gym session, not a warm-up"


def test_ramp_and_top_set_sit_immediately_before_their_own_lift():
    for d in SQUAT_DAYS:
        names = _names(d)
        for lift, base in (("Goblet Squat", "Goblet Squat"),
                           ("Romanian Deadlift (DB)", "Romanian Deadlift")):
            i = names.index(lift)
            preceding = [n for n in names[:i] if sess.base_name(n) == base]
            assert preceding and preceding[0].endswith(sess.RAMP_SUFFIX), (d, lift)
            # Everything between the ramp and the lift is this lift's own sets.
            j = names.index(preceding[0])
            assert all(sess.base_name(n) == base for n in names[j:i]), (d, names[j:i])


def test_ramp_sets_are_flagged_and_nothing_else_is():
    ramps = {ex["name"] for _d, ex in ALL_EXERCISES if ex.get("warmup")}
    assert ramps == {"Goblet Squat (Ramp Set)", "Romanian Deadlift (Ramp Set)"}
    for d in SQUAT_DAYS:
        assert _ex(d, "Goblet Squat (Ramp Set)")["weight_kg"] < _ex(d, "Goblet Squat")["weight_kg"]
        assert _ex(d, "Romanian Deadlift (Ramp Set)")["weight_kg"] < _ex(d, "Romanian Deadlift (DB)")["weight_kg"]


def test_a_ramp_rests_sixty_seconds_not_ninety():
    """A rehearsal set at 62% needs the rest a rehearsal needs."""
    for d in SQUAT_DAYS:
        for name in ("Goblet Squat (Ramp Set)", "Romanian Deadlift (Ramp Set)"):
            assert _ex(d, name)["rest_seconds"] == 60, (d, name)


def test_top_sets_run_weeks_one_to_three_and_never_in_race_week():
    for d in (1, 8, 15):
        assert "Goblet Squat (Heavy Top Set)" in _names(d), d
        assert "Romanian Deadlift (Heavy Top Set)" in _names(d), d
        for name in ("Goblet Squat (Heavy Top Set)", "Romanian Deadlift (Heavy Top Set)"):
            top = _ex(d, name)
            assert top["sets"] == 1 and top["reps"] == 5 and top["rest_seconds"] == 150
            lift = "Goblet Squat" if "Goblet" in name else "Romanian Deadlift (DB)"
            assert top["weight_kg"] > _ex(d, lift)["weight_kg"], (d, name)
    assert not any("Heavy Top Set" in n for n in _names(22))


def test_race_week_runs_two_working_sets_at_week_one_loads_or_lighter():
    for name in ("Goblet Squat", "Romanian Deadlift (DB)", "Hip Thrust (Loaded)"):
        assert _ex(22, name)["sets"] == 2, name
        assert _ex(22, name)["weight_kg"] <= _ex(1, name)["weight_kg"], name
    for name in ("Incline DB Press", "Lat Pulldown", "Single-Arm DB Row"):
        assert _ex(26, name)["sets"] == 2, name
        assert _ex(26, name)["weight_kg"] <= _ex(5, name)["weight_kg"], name


def test_the_heavy_compounds_rest_two_minutes_and_ninety_in_race_week():
    for d in (1, 8, 15):
        assert _ex(d, "Goblet Squat")["rest_seconds"] == 120
        assert _ex(d, "Romanian Deadlift (DB)")["rest_seconds"] == 120
    assert _ex(22, "Goblet Squat")["rest_seconds"] == 90


def test_no_one_set_training_entry_anywhere_on_a_gym_day():
    for d in GYM_DAYS:
        singles = [n for e, n in ((e, e["name"]) for e in PLAN[d]["exercises"])
                   if (e.get("sets", 1) or 1) == 1
                   and n not in sess.PREPARATION_NAMES
                   and not sess.is_measurement(n) and not sess.is_ramp_or_top(n)]
        assert not singles, (d, singles)


def test_preparation_is_release_raise_and_one_activation_item():
    for d in SQUAT_DAYS:
        prep = [e["name"] for e in sess.preparation_entries(PLAN[d]["exercises"])]
        assert prep == ["Ischial Tuberosity Hamstring Release", "Upper Glute / TFL Self-Release",
                        "Piriformis Contract-Relax (PNF)", "Anterior Hip Pressure Release",
                        "Walking Raise (Incline)", "Single-Leg Glute Bridge"], d
    for d in PRESS_DAYS:
        prep = [e["name"] for e in sess.preparation_entries(PLAN[d]["exercises"])]
        assert prep == ["Upper Glute / TFL Self-Release", "Piriformis Contract-Relax (PNF)",
                        "Anterior Hip Pressure Release", "Walking Raise (Incline)",
                        "Scapular Wall Slide"], d


# ── the removals, each with its revert written at the block header ──────────

def test_dead_bug_and_the_fold_trial_are_out_of_the_whole_block():
    assert "Dead Bug" not in NAMES
    assert not any("Forward Fold" in n for n in NAMES)


def test_the_prone_y_raise_is_out_of_the_press_day():
    for d in PRESS_DAYS:
        assert "Prone Y-Raise (Scapular)" not in _names(d), d


def test_the_mat_items_moved_to_the_mobility_day():
    for d in (3, 10, 17, 24):
        names = _names(d)
        assert "McGill Curl-Up (Progressed)" in names, d
        assert "Scapular Retraction Isometric" in names, d
    for d in GYM_DAYS:
        assert "McGill Curl-Up (Progressed)" not in _names(d), d
        assert "Scapular Retraction Isometric" not in _names(d), d


def test_the_finding_five_movements_are_measured_not_maintained():
    """Zero cracks on 2026-08-17. A quiet finding gets its count re-run once a
    block (week-4 mobility day) rather than two maintenance exercises every
    week. REVERT: any crack on that count puts both back on the Saturday runs."""
    assert "Hip 90/90 Flow" not in NAMES and "Lateral Lunge" not in NAMES
    assert _names(24)[0] == "Wide-Stance Rotation Count (Test)"
    for d in (3, 10, 17):
        assert "Wide-Stance Rotation Count (Test)" not in _names(d), d


def test_one_hip_flexor_item_per_gym_day_and_both_after_the_tuesday_run():
    for d in SQUAT_DAYS:
        assert "End-Range Psoas Isometric" in _names(d) and "Half-Kneeling Knee-Hover Isometric" not in _names(d), d
    for d in PRESS_DAYS:
        assert "Half-Kneeling Knee-Hover Isometric" in _names(d) and "End-Range Psoas Isometric" not in _names(d), d
    for d in (2, 9, 16, 23):
        assert _names(d)[-2:] == ["Half-Kneeling Knee-Hover Isometric", "End-Range Psoas Isometric"], d
    # Never after the long Saturday run: it would muddy the run's own signal.
    for d in (6, 13, 20):
        assert not {"Half-Kneeling Knee-Hover Isometric", "End-Range Psoas Isometric"} & set(_names(d)), d


def test_the_cluster_day_is_the_release_the_stack_and_the_lift_offs():
    """Ten entries, under 50 modelled minutes — found at 13 / 61 on 2026-09-11.
    No raise: the phase-2 lock's two conditions (stretching before load, loads
    near max) are both false on a flexibility session, and the blueprint asks
    only that the MEASUREMENT be cold."""
    for d in (4, 11, 18, 25):
        names = _names(d)
        assert PLAN[d].get("session_kind") == "flexibility", d
        assert len(names) == 10, (d, len(names))
        assert names[:4] == ["Ischial Tuberosity Hamstring Release", "Upper Glute / TFL Self-Release",
                             "Piriformis Contract-Relax (PNF)", "Anterior Hip Pressure Release"], d
        assert names[4:9] == list(tp._CLUSTER_STACK_NAMES), d
        assert names[-1] == "Straddle lift-offs from a flat back", d
        assert "Walking Raise (Incline)" not in names, d
        assert sess.estimate_duration(PLAN[d]["exercises"]) <= sess.SESSION_SHAPE["max_flexibility_minutes"], d


def test_each_hip_flexor_item_lands_twice_a_week():
    for start in range(1, 29, 7):
        week = range(start, start + 7)
        for name in ("Half-Kneeling Knee-Hover Isometric", "End-Range Psoas Isometric"):
            assert sum(name in _names(d) for d in week) == 2, (start, name)


def test_the_knee_hover_never_steps_down_and_holds_from_week_two():
    doses = [(_ex(d, "Half-Kneeling Knee-Hover Isometric")["sets"],
              _ex(d, "Half-Kneeling Knee-Hover Isometric")["hold_seconds"]) for d in PRESS_DAYS]
    tuesday = [(_ex(d, "Half-Kneeling Knee-Hover Isometric")["sets"],
                _ex(d, "Half-Kneeling Knee-Hover Isometric")["hold_seconds"]) for d in (2, 9, 16, 23)]
    assert tuesday == doses, "the Tuesday exposure runs the same week's dose as the Friday one"
    work = [s * h for s, h in doses]
    assert work == sorted(work) and work[1] > work[0] and work[1] == work[2] == work[3]


def test_the_ischial_release_is_one_side_then_the_other_with_no_pause():
    """Athlete's 2026-09-10 note: 'Is one set one side and then the other? Why
    is there a pause between a stretch?' It was two bilateral sets with 45 s
    between. Same 90 s a side, no pause."""
    ex = tp.ISCHIAL_RELEASE_NO_PAUSE
    assert ex["name"] == "Ischial Tuberosity Hamstring Release"
    assert ex["laterality"] == "unilateral" and ex["sets"] == 1
    assert ex["hold_seconds"] == 90 and ex["rest_seconds"] == 0
    assert "no pause" in ex["mechanics"].lower()
    for d in SQUAT_DAYS + RUN_DAYS + [4, 11, 18, 25, 28]:
        assert _ex(d, ex["name"]) is not tp.ISCHIAL_RELEASE, d
        assert _ex(d, ex["name"])["rest_seconds"] == 0, d


# ── the release block, the withdrawal trial, phase 2 ────────────────────────

def test_every_training_day_opens_with_the_release_and_rest_days_carry_only_the_front_of_hip():
    withdrawn = {"Upper Glute / TFL Self-Release", "Piriformis Contract-Relax (PNF)"}
    for d in DAYS:
        names = [n for n in _names(d) if not sess.is_measurement(n)]
        if PLAN[d]["day_type"] != "rest":
            assert names[0] in sess.RELEASE_EXERCISE_NAMES, (d, names[0])
        else:
            assert not withdrawn & set(names), d
            assert "Anterior Hip Pressure Release" in names, d


def test_the_front_of_the_hip_is_released_every_day_of_the_block():
    for d in DAYS:
        assert "Anterior Hip Pressure Release" in _names(d), d


def test_every_loaded_session_and_every_run_has_a_raise_and_the_cluster_day_does_not():
    """Phase 2 is mandatory where stretching runs immediately before LOAD —
    the lock's own condition. A flexibility session loads nothing after."""
    for d in GYM_DAYS + RUN_DAYS + [28]:
        assert "Walking Raise (Incline)" in _names(d), d
    for d in (3, 4, 7, 10, 11, 14, 17, 18, 21, 24, 25, 27):
        assert "Walking Raise (Incline)" not in _names(d), d


def test_the_raise_is_never_cycling():
    for name in NAMES:
        assert "cycl" not in name.lower() and "bike" not in name.lower(), name


# ── running ─────────────────────────────────────────────────────────────────

def test_seven_runs_then_the_race_and_the_long_runs_only_grow():
    minutes = []
    for d in RUN_DAYS:
        run = next(e for e in PLAN[d]["exercises"] if "Running" in e["name"])
        minutes.append(run["duration_minutes"])
    assert minutes == [25, 30, 20, 40, 30, 55, 25]
    long_runs = [minutes[i] for i, d in enumerate(RUN_DAYS) if d in (6, 13, 20)]
    assert long_runs == sorted(long_runs)
    race = next(e for e in PLAN[28]["exercises"] if "10 km Running" in e["name"])
    assert race["duration_minutes"] > max(minutes)


def test_the_decision_run_is_day_20_and_says_so():
    run = next(e for e in PLAN[20]["exercises"] if "Running" in e["name"])
    assert "DECISION" in PLAN[20]["objective"]
    assert "decides the race" in run["mechanics"]
    assert "not clean" in run["regression"].lower()
    assert "left front-of-hip signal" in run["biomechanical_focus"].lower()


def test_every_run_and_the_race_carry_the_sartorius_stop_rule():
    for d in RUN_DAYS + [28]:
        run = next(e for e in PLAN[d]["exercises"] if "Running" in e["name"])
        w = (run["warning"] or "").lower()
        assert "left" in w and "sartorius" in w and "stop" in w, d


def test_running_reaches_the_movement_rules_and_counts_as_leg_loading():
    runs = [n for n in NAMES if "running" in n.lower()]
    assert len(runs) == 4, runs
    for name in runs:
        assert rules.check_movement(name, 2)["severity"] == "caution", name
        assert tc.EXERCISE_BODY_REGION[name] == "lower_body", name
        assert name not in fx.RELEASE_EXERCISES, name


def test_the_race_is_run_walk_and_the_format_is_decided_on_day_20():
    race = next(e for e in PLAN[28]["exercises"] if "10 km Running" in e["name"])
    assert "run/walk" in race["mechanics"].lower()
    assert "decision run" in race["mechanics"].lower()
    assert _names(28)[-1] == "Race Debrief (Notes)"


# ── safety and the maps ─────────────────────────────────────────────────────

def test_no_contraindicated_exercise_anywhere_in_the_block():
    banned = rules.get_contraindicated_always()
    for name in NAMES:
        low = name.lower()
        for b in banned:
            assert not (b in low or low in b), f"{name} collides with {b!r}"


def test_no_exercise_is_contraindicated_at_the_block_stage():
    for name in NAMES:
        assert rules.check_movement(name, 2)["severity"] != "contraindicated", name


@pytest.mark.parametrize("name", NAMES)
def test_every_name_is_in_every_map(name):
    assert name in tc.EXERCISE_BODY_REGION, "counts toward no sector"
    assert name in tc.EXERCISE_MOVEMENT_WEIGHT, "falls to the 1.0 default and inflates strain"
    assert name in tc.EXERCISE_REGION_SHARES, "has no regional split"


def test_block_b_dicts_are_copies_not_block_a_objects():
    """The steppers mutate the day dict they are handed. A Block B day that
    shared an exercise object with Block A would let one block's stepper move
    the other's authored number."""
    a = {id(e) for d in tp.PLAN_STAGE2B for e in tp.PLAN_STAGE2B[d]["exercises"]}
    shared = [(d, e["name"]) for d, e in ALL_EXERCISES if id(e) in a]
    # Shared CONSTANTS (the release block, the raise, the isometrics) are
    # fine — they are module-level singletons in both blocks already. What
    # must not be shared is a lift whose weight Block B changed.
    lifts = {"Goblet Squat", "Romanian Deadlift (DB)", "Hip Thrust (Loaded)", "Incline DB Press",
             "Lat Pulldown", "Single-Arm DB Row", "Face Pull (Cable)", "Pallof Press (Cable)"}
    assert not [x for x in shared if x[1] in lifts], shared


def test_loads_start_where_the_log_left_them():
    """2026-09-10: Goblet 3 x 8 at 22.5 (top 25 x 5); RDL 3 x 10 at 40 on the
    re-entry step, 45 before travel (top 52.5 x 5); Hip Thrust cut to 25."""
    assert _ex(1, "Goblet Squat")["weight_kg"] == 22.5
    assert _ex(1, "Goblet Squat (Heavy Top Set)")["weight_kg"] == 25.0
    assert _ex(1, "Romanian Deadlift (DB)")["weight_kg"] == 42.5
    assert _ex(1, "Romanian Deadlift (Heavy Top Set)")["weight_kg"] == 52.5
    assert _ex(1, "Hip Thrust (Loaded)")["weight_kg"] == 30.0
    assert _ex(5, "Incline DB Press")["weight_kg"] == 15.0
