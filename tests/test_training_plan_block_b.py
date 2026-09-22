"""Tests for training_plan.PLAN_BLOCK_B — Block B, Phase 4.

Carries Stage 2B's scheduling, safety and map invariants forward, and pins the
things this block is the first to do: the session shape (Key Rule 21) on every
gym day, ramp and top sets nested under their own lift, one hip-flexor item per
gym day, the running build that restarts from Block A's actual run history,
the moving warm-up and daily planks that replaced the release block on
2026-09-22, and the removals the block header records with their revert
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

def test_the_block_is_twenty_eight_days_and_ends_with_the_reassessment():
    """Day 28 was the 10 km race until the athlete cancelled it (2026-09-18:
    "The race is off I'm not doing it anymore"). What replaces it is the
    re-test of the Bunkie baseline timed on 2026-09-20 — a baseline is only a
    baseline if something re-times it."""
    assert DAYS == list(range(1, 29))
    assert PLAN[28]["day_type"] == "test"
    assert "Reassessment" in PLAN[28]["objective"]
    assert len([n for n in _names(28) if n.startswith("Bunkie")]) == 5


def test_nothing_in_the_block_mentions_the_race():
    fields = ("objective",)
    for d in DAYS:
        for f in fields:
            assert "race" not in PLAN[d][f].lower(), (d, f)
        for ex in PLAN[d]["exercises"]:
            for f in ("name", "mechanics", "biomechanical_focus", "progression",
                      "regression", "warning"):
                text = (ex.get(f) or "").lower()
                assert "race" not in text.replace("brace", ""), (d, ex["name"], f)


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


def test_the_working_part_of_every_gym_day():
    """Three main lifts and one hip-flexor item on both days; the squat day
    keeps the Pallof press as its core lift. The press day's core item is the
    side bridge, which moved to the start with the planks on 2026-09-22."""
    for d in SQUAT_DAYS:
        assert sess.working_families(PLAN[d]["exercises"]) == [
            "Goblet Squat", "Romanian Deadlift", "Hip Thrust", "Pallof Press",
            "End-Range Psoas Isometric"], d
    for d in PRESS_DAYS:
        assert sess.working_families(PLAN[d]["exercises"]) == [
            "Incline DB Press", "Lat Pulldown", "Single-Arm DB Row", "Face Pull",
            "Half-Kneeling Knee-Hover Isometric"], d


def test_every_gym_day_fits_the_hour_with_measured_changeovers():
    """Over 60 is fine, 84 is not — the athlete's words. Stage 2B day 22 read
    92 on this model against 54 on the old one."""
    for d in GYM_DAYS:
        minutes = sess.estimate_duration(PLAN[d]["exercises"])
        assert minutes <= sess.SESSION_SHAPE["max_gym_minutes"], f"day {d}: {minutes} min"
    for d in (1, 5, 8, 12, 15, 19):
        minutes = sess.estimate_duration(PLAN[d]["exercises"])
        assert minutes >= 40, f"day {d}: {minutes} min — a gym session, not a warm-up"


def test_the_lifts_not_the_warm_up_are_most_of_every_gym_day():
    """A gym session, not a warm-up. With the release block gone (2026-09-22)
    the easy week's press day models at 39 minutes, under the 40-minute floor
    the weeks above keep; what that floor was guarding is this — the working
    part must be the larger part of the session, easy week included."""
    for d in GYM_DAYS:
        exercises = PLAN[d]["exercises"]
        n_prep = len(sess.preparation_entries(exercises))
        prep = sess.session_seconds(exercises[:n_prep])
        assert sess.session_seconds(exercises) - prep > prep, d


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


def test_preparation_is_the_march_the_planks_and_one_activation_item():
    """No release block since 2026-09-22 (athlete: "I think the release is now
    outdated, there isn't that much gripping anymore, a dynamic stretching
    would be better"). The planks come BEFORE the lifts: "every training day
    but at the start not the end". No incline walk: he walks fifteen minutes to
    the gym."""
    head = ["Standing Psoas March", "Forearm Plank", "Full Side Bridge"]
    for d in SQUAT_DAYS:
        prep = [e["name"] for e in sess.preparation_entries(PLAN[d]["exercises"])]
        assert prep == head + ["Single-Leg Glute Bridge"], d
    for d in PRESS_DAYS:
        prep = [e["name"] for e in sess.preparation_entries(PLAN[d]["exercises"])]
        assert prep == head + ["Scapular Wall Slide"], d


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


def test_the_cluster_day_is_the_march_the_planks_the_stack_and_the_lift_offs():
    """Nine entries, under 50 modelled minutes — found at 13 / 61 on
    2026-09-11, and ten until the release block came out on 2026-09-22. No
    raise: the phase-2 lock's two conditions (stretching before load, loads
    near max) are both false on a flexibility session, and the blueprint asks
    only that the MEASUREMENT be cold."""
    for d in (4, 11, 18, 25):
        names = _names(d)
        assert PLAN[d].get("session_kind") == "flexibility", d
        assert len(names) == 9, (d, len(names))
        assert names[:3] == ["Standing Psoas March", "Forearm Plank", "Full Side Bridge"], d
        assert names[3:8] == list(tp._CLUSTER_STACK_NAMES), d
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
    between. Same 90 s a side, no pause. OUT of the block with the rest of the
    release block since 2026-09-22 and kept for the revert, so it is pinned as
    it would come back."""
    ex = tp.ISCHIAL_RELEASE_NO_PAUSE
    assert ex["name"] == "Ischial Tuberosity Hamstring Release"
    assert ex["laterality"] == "unilateral" and ex["sets"] == 1
    assert ex["hold_seconds"] == 90 and ex["rest_seconds"] == 0
    assert "no pause" in ex["mechanics"].lower()
    for d in DAYS:
        assert tp.ISCHIAL_RELEASE_NO_PAUSE not in PLAN[d]["exercises"], d


# ── the warm-up, the planks, phase 2 (the release block left 2026-09-22) ───

def test_no_release_item_on_any_day_but_the_reassessment():
    """All four releases out (athlete, 2026-09-22), rest days included — a rest
    day is the walk. Day 28 keeps its own: it re-runs the 2026-09-20 baseline's
    protocol, and a re-test with a different lead-in measures the lead-in.
    REVERT (block header): right grip grade 2+ on a Wednesday, or the hip
    symptoms back."""
    for d in DAYS:
        if d == 28:
            continue
        assert not set(_names(d)) & sess.RELEASE_EXERCISE_NAMES, (d, _names(d))
    for d in (7, 14, 21, 27):
        assert _names(d) == ["Controlled Walking"], d


def test_the_grip_grade_is_read_first_and_cold_every_wednesday():
    """It is the check on the release block's removal, so it reads the hip
    before anything is done to it."""
    for d in (3, 10, 17, 24):
        names = [n for n in _names(d) if n != "Wide-Stance Rotation Count (Test)"]
        assert names[0] == "Upper Glute Grip Grade (Test)", d


def test_the_psoas_march_warms_up_every_session_that_loads_or_stretches():
    """His pick for the moving warm-up: "I feel more of stretch from that than
    any other stretch." Not on Wednesday — it is leg work, and Thursday's
    flexibility morning must not follow leg work — and not on rest days or
    day 28."""
    for d in GYM_DAYS + RUN_DAYS + [4, 11, 18, 25]:
        assert "Standing Psoas March" in _names(d), d
    for d in (3, 7, 10, 14, 17, 21, 24, 27, 28):
        assert "Standing Psoas March" not in _names(d), d
    march = tp.STANDING_PSOAS_MARCH
    assert march["laterality"] == "alternating" and march["sets"] == 2 and march["reps"] == 10
    text = march["mechanics"].lower()
    assert "do not swing" in text and "right" in text, "active range, and key rule 7's cue"
    assert rules.check_movement(march["name"], 2)["severity"] == "caution"


TRAINING_DAYS = [d for d in DAYS if d not in (7, 14, 21, 27, 28)]


def test_planks_open_every_training_day_but_the_reassessment():
    """Athlete, 2026-09-22: "Every training day but at the start not the end."
    Both planks sit before the first thing that is not warm-up or a
    measurement. Not on rest days, and not on day 28: its five Bunkie lines are
    timed plank holds, and a trunk tired first reads as a weaker one."""
    for d in TRAINING_DAYS:
        names = _names(d)
        assert "Forearm Plank" in names and "Full Side Bridge" in names, d
        first_work = next(i for i, n in enumerate(names)
                          if n not in sess.PREPARATION_NAMES and not sess.is_measurement(n))
        assert names.index("Forearm Plank") < first_work, d
        assert names.index("Full Side Bridge") < first_work, d
        assert names.count("Full Side Bridge") == 1, d
    for d in (7, 14, 21, 27, 28):
        assert not {"Forearm Plank", "Full Side Bridge"} & set(_names(d)), d


def test_the_plank_dose_is_short_and_steps_by_week():
    """Switched on, not tired, before a loaded hinge: 20 s rising 5 s a week,
    and the easy week back at 20 with one set fewer on the front plank."""
    for d in TRAINING_DAYS:
        week = (d - 1) // 7 + 1
        front, side = _ex(d, "Forearm Plank"), _ex(d, "Full Side Bridge")
        hold = {1: 20, 2: 25, 3: 30, 4: 20}[week]
        assert front["hold_seconds"] == side["hold_seconds"] == hold, d
        assert front["sets"] == (2 if week == 4 else 3), d
        assert side["sets"] == 2 and side["laterality"] == "unilateral", d


def test_no_reverse_plank():
    """The physio's third plank, left out on the shoulder: it loads the arm in
    extension under body weight, which drives the top of the arm bone forward
    in the socket — the direction of three dislocations and the Latarjet."""
    assert not any("reverse plank" in n.lower() for n in NAMES)
    assert rules.check_movement("Reverse Plank", 2)["severity"] != "cleared"


def test_the_glute_bridge_is_three_sets_on_the_same_eleven_days():
    """Athlete, 2026-09-22: more sets, not more days. Stage 2B's one-set
    activation item is untouched."""
    days = [d for d in DAYS if "Single-Leg Glute Bridge" in _names(d)]
    assert days == sorted(SQUAT_DAYS + RUN_DAYS)
    for d in days:
        assert _ex(d, "Single-Leg Glute Bridge")["sets"] == 3, d
    assert tp.PREP_GLUTE_ACTIVATION["sets"] == 1


def test_the_incline_walk_leads_the_runs_and_the_walk_to_the_gym_is_the_gym_days_raise():
    """Athlete, 2026-09-22: "I always walk 15 mins to get to the gym, so a 3 min
    incline walk is not needed to start." Fifteen minutes of easy walking is
    five times the raise's dose, so the gym days start at the psoas march. The
    runs start from home and keep it. A flexibility session loads nothing
    after, so it never had one."""
    for d in RUN_DAYS:
        assert _names(d)[0] == "Walking Raise (Incline)", d
    for d in GYM_DAYS:
        assert "Walking Raise (Incline)" not in _names(d), d
        assert _names(d)[0] == "Standing Psoas March", d
    # 28 joins the list that loads nothing after the release: a measurement is
    # taken cold, and the race it replaced was the one test day that loaded.
    for d in (3, 4, 7, 10, 11, 14, 17, 18, 21, 24, 25, 27, 28):
        assert "Walking Raise (Incline)" not in _names(d), d


def test_the_raise_is_never_cycling():
    for name in NAMES:
        assert "cycl" not in name.lower() and "bike" not in name.lower(), name


# ── running ─────────────────────────────────────────────────────────────────

def test_seven_run_walks_and_the_long_run_grows_about_a_tenth_a_week():
    """The athlete's four choices, 2026-09-18: two runs a week, the long run
    growing about 10% a week, run/walk throughout, and an easier fourth week.
    The race build this replaces went 20 continuous, 40, then a 55-minute
    decision run."""
    minutes = []
    for d in RUN_DAYS:
        run = next(e for e in PLAN[d]["exercises"] if "Running" in e["name"])
        minutes.append(run["duration_minutes"])
    assert minutes == [20, 25, 20, 28, 22, 30, 20]

    long_runs = [minutes[RUN_DAYS.index(d)] for d in (6, 13, 20)]
    for before, after in zip(long_runs, long_runs[1:]):
        assert 1.0 < after / before <= 1.15, (before, after)

    # Week 4 is the easy week: its one run is no longer than any other, and it
    # has no long run at all.
    assert minutes[-1] <= min(minutes)
    assert 27 not in RUN_DAYS and PLAN[27]["day_type"] == "rest"
    assert not any("Running" in n for n in _names(28))


def test_no_run_is_a_test_and_every_run_is_a_run_walk():
    """The 55-minute decision run pre-registered a race format. With no race
    there is nothing to decide on a run, and every session keeps walk breaks —
    the lever this build pulls instead of raising the minutes faster."""
    for d in RUN_DAYS:
        assert "decision" not in PLAN[d]["objective"].lower(), d
        run = next(e for e in PLAN[d]["exercises"] if "Running" in e["name"])
        assert run["name"] == "Running Intervals (Run/Walk)", d
        assert "walking" in run["mechanics"].lower(), d


def test_every_run_carries_the_sartorius_stop_rule():
    for d in RUN_DAYS:
        run = next(e for e in PLAN[d]["exercises"] if "Running" in e["name"])
        w = (run["warning"] or "").lower()
        assert "left" in w and "sartorius" in w and "stop" in w, d


def test_running_reaches_the_movement_rules_and_counts_as_leg_loading():
    runs = [n for n in NAMES if "running" in n.lower()]
    assert runs == ["Running Intervals (Run/Walk)"], runs
    for name in runs:
        assert rules.check_movement(name, 2)["severity"] == "caution", name
        assert tc.EXERCISE_BODY_REGION[name] == "lower_body", name
        assert name not in fx.RELEASE_EXERCISES, name


def test_day_28_re_times_the_baseline_protocol_UNCHANGED():
    """The same objects, not a re-wording of them: a re-test that re-writes its
    own instructions measures the wording. This is why day 28 is exempt from
    three of the block's own rules below — it runs the baseline's protocol."""
    baseline = tp.PLAN_STAGE2B[28]["exercises"]
    assert PLAN[28]["exercises"] == list(baseline)
    for mine, theirs in zip(PLAN[28]["exercises"], baseline):
        assert mine is theirs


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
