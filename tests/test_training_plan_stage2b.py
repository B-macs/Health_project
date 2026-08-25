"""Tests for training_plan.PLAN_STAGE2B — the Stage 2B block, Phase 3.

Mirrors tests/test_training_plan_stage2.py's invariants for the new block, and
adds the ones this block is the first to need: a twelve-day stretch with no
external load, running, ramp sets, and a flexibility session that has to sit
somewhere the retest rules allow.

The properties here are the ones that fail SILENTLY if they break. An exercise
missing from a map counts toward nothing (or, worse, toward everything at the
1.0 default); a day missing a day_type disables the readiness auto-shift for
the whole block; a gym day whose neighbour is not strictly lower priority makes
every shift proposal refuse without saying why.
"""

from __future__ import annotations

import pytest

import cluster_a_mechanics as cm
import training_constants as tc
import training_plan as tp
from services import flexibility as fx, rules, scheduling as sch, sessions as sess

PLAN = tp.PLAN_STAGE2B
DAYS = sorted(PLAN)
ALL_EXERCISES = [(d, ex) for d in DAYS for ex in PLAN[d]["exercises"]]
NAMES = sorted({ex["name"] for _d, ex in ALL_EXERCISES})


# ── shape ───────────────────────────────────────────────────────────────────

def test_the_block_is_twenty_eight_days():
    assert DAYS == list(range(1, 29))


def test_every_day_has_exercises_and_an_rpe_target():
    for d in DAYS:
        assert PLAN[d]["exercises"], f"day {d} is empty"
        # Accessed with [] rather than .get() by three call sites in
        # views/training.py — a missing key is a KeyError on the live screen.
        assert isinstance(PLAN[d]["session_rpe_target"], int), d


def test_every_exercise_carries_a_weight_key():
    for d, ex in ALL_EXERCISES:
        assert "weight_kg" in ex, f"day {d}: {ex['name']}"


def test_the_block_is_registered_and_startable():
    """Without both of these there is no route into Phase 3 at all: the plan
    lookup returns None and every day renders as rest."""
    assert sess.plan_dict_for_phase(3) is PLAN
    assert sess.PHASE_META[3]["stage"] == 2, (
        "Stage 2B is a new BLOCK at the same clinical stage — reading '2B' as "
        "stage 3 would hand over ACWR 1.5 and RPE 10 on the strength of a name"
    )


# ── the scheduling contract ─────────────────────────────────────────────────

def test_every_day_carries_a_valid_day_type():
    for d in DAYS:
        assert PLAN[d].get("day_type") in sch.SESSION_PRIORITY, d


def test_day_type_main_matches_is_gym_session():
    for d in DAYS:
        assert (PLAN[d]["day_type"] == "main") == bool(PLAN[d].get("is_gym_session")), d


def test_every_gym_day_is_followed_by_a_strictly_lower_priority_day():
    """swap_pairs_for_shift's partner check depends on this; without it the
    readiness auto-shift refuses every proposal."""
    for d in DAYS:
        if PLAN[d]["day_type"] != "main" or d + 1 not in PLAN:
            continue
        assert sch.SESSION_PRIORITY[PLAN[d + 1]["day_type"]] < sch.SESSION_PRIORITY["main"], d


def test_no_two_main_days_are_adjacent():
    mains = [d for d in DAYS if PLAN[d]["day_type"] == "main"]
    assert not [d for d in mains if d + 1 in mains], mains


def test_the_reassessment_is_not_the_day_after_a_main_session():
    """A test session run on fatigue measures the session before it."""
    for d in DAYS:
        if PLAN[d]["day_type"] == "test" and d - 1 in PLAN:
            assert PLAN[d - 1]["day_type"] != "main", d


def test_five_sessions_a_week_at_most():
    """STAGE_CONSTRAINTS[2]['session_freq_max']. The cluster counts against it —
    authoring five gym days and bolting flexibility on top is the thing the
    integration protocol names as not allowed."""
    cap = rules.STAGE_CONSTRAINTS[2]["session_freq_max"]
    for week in range(4):
        days = range(week * 7 + 1, week * 7 + 8)
        sessions = [d for d in days if PLAN[d]["day_type"] != "rest"]
        assert len(sessions) <= cap, f"week {week + 1} has {len(sessions)} sessions"


# ── safety ──────────────────────────────────────────────────────────────────

def test_no_contraindicated_exercise_anywhere_in_the_block():
    banned = rules.get_contraindicated_always()
    for name in NAMES:
        low = name.lower()
        for b in banned:
            assert not (b in low or low in b), f"{name} collides with {b!r}"


def test_no_exercise_is_contraindicated_at_the_block_stage():
    for name in NAMES:
        assert rules.check_movement(name, 2)["severity"] != "contraindicated", name


def test_running_actually_reaches_the_movement_rules():
    """The names contain "running" on purpose. "Easy Run" would return
    `unknown` — not a block, but not the caution verdict either, and naming a
    session so it misses a safety keyword is the vocabulary failure this repo
    has already been burned by."""
    runs = [n for n in NAMES if "running" in n.lower()]
    assert len(runs) == 3, runs
    for name in runs:
        assert rules.check_movement(name, 2)["severity"] == "caution", name


#: The two items the 2026-08-17 withdrawal trial actually withdrew. The trial
#: measures ONE thing — whether the upper glute's resting grip holds without
#: daily release — and its instrument is the weekly Upper Glute Grip Grade,
#: which reads the upper glute. These are the names that must stay off a rest
#: day; an item the grip grade does not measure cannot corrupt the reading.
_WITHDRAWN_PAIR = {
    "Upper Glute / TFL Self-Release",
    "Piriformis Contract-Relax (PNF)",
}


def test_the_release_block_precedes_every_training_session_and_is_absent_from_rest_days():
    """This test used to assert the release opened all 28 days, rest days
    included. Since 2026-08-17 it pins the WITHDRAWAL TRIAL instead, in both
    directions:

    * every TRAINING day (main, stretch, and the day-28 test screen) still
      opens with a release exercise — Key Rule 6, physio-confirmed;
    * every REST day carries none of the WITHDRAWN PAIR. Finding #1's exit
      criterion was met on 2026-07-19 and the pair ran 28/28 anyway; whether
      the reduction holds without daily release is unanswerable while it runs
      daily. The weekly Upper Glute Grip Grade on the mobility days is the
      trial's instrument, and it must not be quietly re-treated between
      readings — the pair creeping back onto a rest day would corrupt the
      trial while looking like diligence.

    ⚠ NARROWED 2026-08-24, deliberately, and it is a narrowing rather than a
    weakening. The assertion used to be "no RELEASE_EXERCISE_NAMES item at all
    on a rest day", which is wider than the trial it protects. The front-of-hip
    release is neither withdrawn structure, is not what the grip grade reads,
    and is not adaptation-seeking — a pressure release leaves the tissue
    quieter than it found it, which is why it sits in
    flexibility.RELEASE_EXERCISES and why the accessory session already offered
    it on exactly these days. What put it there: patient_profile's own
    pre_session_release note says the daily front-of-hip protocol "continues
    alongside and is the larger dose — it runs on desk days, which is the
    exposure being treated", and it had never run anywhere. Both directions are
    pinned below, so the pair cannot come back and the front of the hip cannot
    quietly go away.

    MEASUREMENTS AND TRIALS MAY LEAD, on any day — day 1's finding tests and
    P2's fold exposure carry a "(Test)"/"(Timed Test)"/"(Trial)" suffix, and
    they run BEFORE the release for one reason: the release changes the tissue
    being counted (the ischial release presses on the exact attachment the
    fold loads), so a count taken after it measures the release rather than
    the athlete. After the measurement prefix, a training day's first item
    must still be the release; nothing but suffixed measurements may sit
    ahead of it."""

    def _is_measurement(n):
        return "(Test)" in n or "(Timed Test)" in n or "(Trial)" in n

    for d in DAYS:
        names = [e["name"] for e in PLAN[d]["exercises"]]
        body = [n for n in names if not _is_measurement(n)]
        prefix_len = names.index(body[0]) if body else len(names)
        assert all(_is_measurement(n) for n in names[:prefix_len]), (
            f"day {d}: a non-measurement item sits inside the measurement prefix")
        if d == 1 or PLAN[d]["day_type"] != "rest":
            assert body and body[0] in sess.RELEASE_EXERCISE_NAMES, (
                f"day {d}'s first non-measurement item is "
                f"{body[0] if body else 'nothing'}")
        else:
            leaked = sorted(set(body) & _WITHDRAWN_PAIR)
            assert not leaked, (
                f"day {d} is a rest day inside the withdrawal trial and "
                f"carries the withdrawn pair: {leaked}")
            assert ANTERIOR in body, (
                f"day {d} carries no front-of-hip release. The desk day is the "
                f"exposure the protocol treats, and these are the days with "
                f"nothing else on them")


def test_the_long_stretch_runs_first_on_hip_loaded_days():
    """The warm-up review's free win: the block's only >=60s stretch leads, so
    the pressure releases sit between it and the first loaded rep."""
    for d in DAYS:
        names = [ex["name"] for ex in PLAN[d]["exercises"]]
        if "Right Posterior Hip Capsule Stretch (Revised Cue)" not in names:
            continue
        assert names[0] == "Right Posterior Hip Capsule Stretch (Revised Cue)", d


def test_the_upper_glute_release_runs_both_sides():
    """It was coded bilateral while its own text and the profile both say EACH
    SIDE — a 2x difference on the largest item in the release block."""
    assert tp.UPPER_GLUTE_RELEASE_5MIN["laterality"] == "unilateral"


# ── phase 2, the deliverable ────────────────────────────────────────────────

def test_every_session_has_a_wake_things_back_up_phase():
    """Mandatory in every session, athlete's direction.

    Two exemptions, both for a stated reason. Rest and travel days load nothing,
    so there is nothing to prepare for. The day-28 assessment is exempt because
    its whole value is comparability: the Stage 1 Day 21 and Stage 2A Day 28
    screens were run without a raise, and adding one here would move the numbers
    for a reason that has nothing to do with the athlete."""
    for d in DAYS:
        if PLAN[d]["day_type"] in ("rest", "test"):
            continue
        names = [ex["name"] for ex in PLAN[d]["exercises"]]
        assert "Walking Raise (Incline)" in names, f"day {d} has no raise"


def test_the_raise_is_never_cycling():
    """The literature's best general raise is low-intensity cycling, and the
    athlete's own 2025 log names cycling as what inhibits his glutes — the one
    muscle this phase exists to switch on."""
    for name in NAMES:
        assert "cycl" not in name.lower() and "bike" not in name.lower(), name


#: Coded laterality="unilateral" but having only ONE side. The rest-interval
#: review made a point of this: counting them twice is what inflated an earlier
#: estimate of the split's cost, and it would inflate the preparation budget
#: here in exactly the same way.
_RIGHT_ONLY = {
    "Right Posterior Hip Capsule Stretch (Revised Cue)",
    "Right Posterior Hip Capsule Stretch (Quadruped)",
    "Right Hip Tendon Path Drill (Coxa Saltans)",
}


def test_preparation_stays_inside_the_fifteen_minute_ceiling():
    """Locked by the athlete: total preparation, first movement to first
    working rep, is 10-15 min with 15 a ceiling not a target.

    Counts BOTH SIDES of every two-sided item, which services.sessions'
    estimate_duration itself does not do — that omission is a recorded open
    issue, and a budget test that inherited it would pass by under-counting the
    exact thing it exists to measure."""
    prep_names = sess.RELEASE_EXERCISE_NAMES | {
        "Walking Raise (Incline)", "Single-Leg Glute Bridge", "Dead Bug",
        "Scapular Wall Slide", "Prone Y-Raise (Scapular)",
    }
    for d in DAYS:
        # Skip the measurement prefix (finding tests, P2's fold trial) rather
        # than letting it end the walk at item zero — a leading test name used
        # to make this whole day's count vacuous, which quietly disarmed the
        # ceiling on exactly the days that gained items.
        exercises = [ex for ex in PLAN[d]["exercises"]
                     if "(Test)" not in ex["name"]
                     and "(Timed Test)" not in ex["name"]
                     and "(Trial)" not in ex["name"]]
        seconds = 0
        for ex in exercises:
            if ex["name"] not in prep_names:
                break
            sides = 2 if (ex.get("laterality") == "unilateral"
                          and ex["name"] not in _RIGHT_ONLY) else 1
            seconds += sess.exercise_duration_seconds(ex) * sides
        assert seconds <= 15 * 60, (
            f"day {d} spends {seconds / 60:.1f} min preparing, over the 15-minute ceiling"
        )


# ── ramp sets ───────────────────────────────────────────────────────────────

def test_ramp_sets_are_flagged_and_nothing_else_is():
    ramps = {ex["name"] for _d, ex in ALL_EXERCISES if ex.get("warmup")}
    assert ramps == {"Goblet Squat (Ramp Set)", "Romanian Deadlift (Ramp Set)"}


def test_ramp_sets_only_appear_once_the_loads_are_near_maximal():
    """A ramp buys +3-8% near 1RM and about nothing at ten reps, so it is
    scaled per exercise and per week — not switched on for the whole block."""
    ramp_days = {d for d, ex in ALL_EXERCISES if ex.get("warmup")}
    assert ramp_days == {22}, ramp_days


def test_a_ramp_is_lighter_than_the_lift_it_prepares():
    by_day = {d: {ex["name"]: ex for ex in PLAN[d]["exercises"]} for d in DAYS}
    day = by_day[22]
    assert day["Goblet Squat (Ramp Set)"]["weight_kg"] < day["Goblet Squat"]["weight_kg"]
    assert day["Romanian Deadlift (Ramp Set)"]["weight_kg"] < day["Romanian Deadlift (DB)"]["weight_kg"]


# ── the travel fortnight ────────────────────────────────────────────────────

TRAVEL_DAYS = range(3, 15)


def test_no_external_load_is_prescribed_while_away():
    """Days 3-14 are Ireland: long bands and mini-bands, nothing else. A
    dumbbell authored into these days is a session that cannot be done."""
    for d in TRAVEL_DAYS:
        for ex in PLAN[d]["exercises"]:
            assert ex.get("equipment_type") in (None, "band"), (
                f"day {d}: {ex['name']} needs {ex.get('equipment_type')}"
            )


def test_band_exercises_never_carry_a_weight():
    """A band is not a kilogram. weight_kg stays None so the set records
    weight=0 and the fortnight reads as unloaded reps, which is the truth."""
    for _d, ex in ALL_EXERCISES:
        if ex.get("equipment_type") == "band":
            assert ex["weight_kg"] is None, ex["name"]
            assert ex.get("band_tier"), f"{ex['name']} has no tier to progress on"


def test_the_gym_lifts_resume_one_step_down_after_the_travel_weeks():
    """Twelve days without load costs almost no strength — but "weight
    increased too quickly" is a named cause of the squat breakdown in the
    athlete's own log."""
    def load(day, name):
        return next(e["weight_kg"] for e in PLAN[day]["exercises"] if e["name"] == name)

    # Day 2, not day 1: the week-1 loaded session moved there on 2026-08-17
    # when day 1 became the measurement day.
    for name in ("Goblet Squat", "Romanian Deadlift (DB)", "Hip Thrust (Loaded)"):
        assert load(15, name) < load(2, name), f"{name} did not step down on re-entry"
        assert load(22, name) == load(2, name), f"{name} did not return to full load"


# ── rest intervals ──────────────────────────────────────────────────────────

def test_only_the_two_heavy_compounds_change_rest_and_only_in_week_four():
    """The one supported change out of the whole rest-interval review, and it
    is conditional on the loads actually being near-maximal."""
    long_rests = {(d, ex["name"]) for d, ex in ALL_EXERCISES
                  if (ex.get("rest_seconds") or 0) > 90}
    # The two heavy TOP SETS (added 2026-08-17) rest 150 s — near-maximal
    # 5-rep work is exactly the condition Grgic 2018's ">2 min" applies to,
    # so they belong in this set rather than being an exception to it.
    assert long_rests == {
        (22, "Goblet Squat"), (22, "Romanian Deadlift (DB)"),
        (22, "Goblet Squat (Heavy Top Set)"),
        (22, "Romanian Deadlift (Heavy Top Set)"),
    }, long_rests


def test_core_and_scapular_rest_is_left_alone():
    """No evidence bears on it in either direction, so changing it would be as
    unevidenced as leaving it."""
    for _d, ex in ALL_EXERCISES:
        if ex["name"] in ("Full Side Bridge", "McGill Curl-Up (Progressed)",
                          "Scapular Retraction Isometric"):
            assert ex["rest_seconds"] == 45, ex["name"]


def test_the_scapular_isometric_is_short_efforts_not_a_long_hold():
    """At matched loading time four 3-second contractions beat one 12-second
    hold, and the target tissue is perfusion-limited trapezius where a
    sustained contraction is the PROVOCATIVE mechanism."""
    iso = tp.SCAPULAR_ISOMETRIC
    assert iso["hold_seconds"] == 3
    assert iso["reps_in_set"] == 4


# ── the maps, all three ─────────────────────────────────────────────────────

@pytest.mark.parametrize("name", NAMES)
def test_every_name_is_in_every_map(name):
    assert name in tc.EXERCISE_BODY_REGION, "counts toward no sector"
    assert name in tc.EXERCISE_MOVEMENT_WEIGHT, "falls to the 1.0 default and inflates strain"
    assert name in tc.EXERCISE_REGION_SHARES, "has no regional split"


def test_running_counts_as_leg_loading():
    """A run the day before a flexibility retest is exactly the tightness the
    retest rule guards against."""
    for name in NAMES:
        if "running" in name.lower():
            assert tc.EXERCISE_BODY_REGION[name] == "lower_body", name
            assert name not in fx.RELEASE_EXERCISES, name


def test_the_cluster_session_never_lands_on_a_rest_day_or_after_leg_work():
    """flexibility_window ranks a rest day POOR — a cluster session is
    adaptation-seeking by definition — and the day after leg work worst of all."""
    # Identified by the day's OBJECTIVE since 2026-08-18: the session is no
    # longer one exercise called "Cluster A Flexibility Session" but the five
    # items pattern D prescribes, so a name check would find nothing and this
    # test would pass vacuously on a block with no flexibility slot at all.
    cluster_days = [d for d in DAYS if "Cluster A" in (PLAN[d].get("objective") or "")]
    assert cluster_days, "the block reserves no flexibility slot at all"
    leg_days = {
        d for d in DAYS
        for e in PLAN[d]["exercises"]
        if tc.EXERCISE_BODY_REGION.get(e["name"]) == "lower_body"
        and e["name"] not in fx.RELEASE_EXERCISES
    }
    for d in cluster_days:
        assert PLAN[d]["day_type"] != "rest", d
        assert d - 1 not in leg_days, f"day {d} follows leg work on day {d - 1}"


def test_the_cluster_starts_in_week_two_not_week_one():
    """One new stressor per week. Running is week 1's, so the cluster waits."""
    cluster_days = [d for d in DAYS if "Cluster A" in (PLAN[d].get("objective") or "")]
    assert cluster_days, "no cluster day found — see the note on identification above"
    assert min(cluster_days) > 7, cluster_days
    assert len([d for d in cluster_days if d <= 14]) == 1, "week 2 gets exactly one"


# ── the anterior-hip release ────────────────────────────────────────────────

ANTERIOR = "Anterior Hip Pressure Release"
_ANTERIOR_DAYS = [d for d in DAYS
                  if any(e["name"] == ANTERIOR for e in PLAN[d]["exercises"])]


def test_the_block_releases_the_front_of_the_hip_at_all():
    """The gap this closes. The MRI names psoas/hip-flexor hypertonicity as what
    amplifies the L5/S1 compression and "deep right hip flexors / TFL" sits on
    the overactive list — yet the release block inhibited the glute medius, the
    piriformis and the posterior capsule and left the front of the hip alone.
    Stage 1 had three hip-flexor items; all three vanished at the 2A transition
    and nothing replaced them until now."""
    assert _ANTERIOR_DAYS, "no anterior-hip release anywhere in the block"


def test_it_no_longer_waits_for_week_three():
    """This test used to assert `min(_ANTERIOR_DAYS) >= 15`, and the constraint
    it encoded was real: the seated tilt is the flexibility battery's central
    measurement, and starting a new anterior-hip intervention before the
    baseline was captured would contaminate it. Two weeks of the daily protocol
    landed in week 3.

    THE CONDITION IS NOW MET, so the gate is lifted rather than weakened. The
    athlete ran the battery cold on four separate mornings; the app lost every
    recording but the last, which is the same persistence failure that lost the
    per-exercise notes. His direction (2026-08-17): the surviving reading is the
    record and the baseline is complete. Requiring four more cold mornings
    because this system dropped the first four is a bug charging interest, not a
    clinical requirement.

    ⚠ What no instruction repairs, and what this test does NOT claim: three
    mornings established the NOISE FLOOR as well as the baseline. With one
    stored reading the spread is unknown, so BatteryResult.trusted stays False
    and a future change cannot be judged against ~2x the observed spread.

    REVERT: if the battery baseline is ever re-run from scratch, this gate comes
    back — restore `anterior=week >= 3` at the four call sites in
    training_plan._s2b_gym_a, _s2b_gym_a_bands, _s2b_run_day and _s2b_cluster.
    """
    assert min(_ANTERIOR_DAYS) == 1, _ANTERIOR_DAYS
    # The reason it moved is hip-flexor coverage, so it must be on every
    # hip-loaded day rather than merely present somewhere.
    hip_days = [d for d in DAYS
                if any(e["name"] == "Ischial Tuberosity Hamstring Release"
                       for e in PLAN[d]["exercises"])]
    missing = [d for d in hip_days if d not in _ANTERIOR_DAYS and d != 28]
    assert not missing, f"hip-loaded days with no front-of-hip release: {missing}"


def test_it_is_off_on_the_assessment_day():
    """Day 28's whole value is comparability with the Stage 1 and Stage 2A
    versions of the same screen. A new hip-flexor release immediately before a
    hinge assessment moves the number for a reason that is not the athlete."""
    assert 28 not in _ANTERIOR_DAYS


def test_no_pause_between_right_and_left():
    """Athlete's instruction, 2026-08-14. One set per side and zero rest, so
    there is no pause anywhere in it — which also matches how the guided flow
    already behaves, since the right-to-left transition has no rest timer."""
    ex = tp.ANTERIOR_HIP_RELEASE
    assert ex["sets"] == 1
    assert ex["rest_seconds"] == 0
    assert ex["laterality"] == "unilateral"


def test_it_carries_the_neurovascular_warning():
    """The sharp edge of this protocol: the inner front of the hip carries the
    leg's main artery and nerve. The warning is not optional decoration."""
    warning = (tp.ANTERIOR_HIP_RELEASE["warning"] or "").lower()
    assert "pulse" in warning
    assert "artery" in warning or "nerve" in warning


def test_it_counts_as_a_release_not_as_leg_loading():
    """It leaves the tissue quieter than it found it, which is the opposite of
    what the retest-spacing rule guards against."""
    assert ANTERIOR in fx.RELEASE_EXERCISES
    assert ANTERIOR in sess.RELEASE_EXERCISE_NAMES


# ── front-of-hip STRENGTH (2026-08-24) ──────────────────────────────────────
# The athlete's correction to the first draft of this work: "release is only
# going to help the next 2-3 hours of training, without isometric holds or
# strengthing the muscle will just return to its original position. We need to
# only a few minutes of release to allow for successful training but more time
# on holds and strengthing to get the real benefits."
#
# Before this the block had ONE front-of-hip item, a release, on 15 of 28 days,
# and no hip-flexor strength work anywhere — Stage 1's two hip-flexor items
# vanished at the Stage 2A transition with no reason recorded. These tests pin
# the shape of the answer, because the shape is the argument: three times a
# week, appended to the session rather than to the preparation block, dosed as
# efforts with an end rather than as positions to hold.

HOVER = "Half-Kneeling Knee-Hover Isometric"
PSOAS = "End-Range Psoas Isometric"
LIFT_OFFS = "Straddle lift-offs from a flat back"
_STRENGTH = (HOVER, PSOAS, LIFT_OFFS)
_STRENGTH_DAYS = [d for d in DAYS
                  if any(e["name"] in _STRENGTH for e in PLAN[d]["exercises"])]


def test_the_front_of_the_hip_is_actually_trained_and_not_only_released():
    """The whole claim of the 2026-08-24 change in one assertion. A release
    quiets tone for a few hours; nothing in the block loaded the tissue."""
    assert _STRENGTH_DAYS, "the block trains the front of the hip nowhere"


def test_hip_flexor_strength_runs_three_times_in_every_week():
    """Frequency is the claim, so frequency is what a later edit would break
    first — dropping one day looks like tidying and halves a strength stimulus
    that is already only four weeks long."""
    for start in range(1, 29, 7):
        window = [d for d in _STRENGTH_DAYS if start <= d < start + 7]
        assert len(window) >= 3, (
            f"days {start}-{start + 6} carry hip-flexor strength on {window}")


def test_the_strength_work_is_not_preparation():
    """It is appended AFTER the workout, which is what makes it affordable: the
    10-15 min preparation ceiling walks the day's list and stops at the first
    item that is not a release or the raise. Putting these in the preparation
    run would blow that ceiling on every hip-loaded day."""
    prep = sess.RELEASE_EXERCISE_NAMES | {
        "Walking Raise (Incline)", "Single-Leg Glute Bridge", "Dead Bug",
        "Scapular Wall Slide", "Prone Y-Raise (Scapular)",
    }
    for name in _STRENGTH:
        assert name not in prep, name
    for d in _STRENGTH_DAYS:
        names = [e["name"] for e in PLAN[d]["exercises"]]
        first_strength = min(names.index(n) for n in _STRENGTH if n in names)
        assert any(n not in prep and "(Trial)" not in n and "(Test)" not in n
                   for n in names[:first_strength]), (
            f"day {d} opens its strength work before any real session content")


def test_the_psoas_isometric_is_short_efforts_not_a_long_hold():
    """Same rule and same reason as the scapular isometric beside it: at
    matched loading time four 3-s contractions beat one 12-s hold, +57% against
    +25%, and intensity rather than duration is the variable
    (docs/training/rest_interval_evidence_review_2026-08-13.md 2.4)."""
    ex = tp.END_RANGE_PSOAS_ISOMETRIC
    assert ex["type"] == "hold_reps"
    assert ex["hold_seconds"] <= 5, ex["hold_seconds"]
    assert ex["reps_in_set"] >= 4, ex["reps_in_set"]
    assert ex["laterality"] == "unilateral"


def test_the_knee_hover_dose_steps_up_across_the_block_and_never_down():
    """The progression lives in the PLAN, the way the block's loaded lifts do,
    rather than in a `progression` field no view renders. A hover's intensity
    is fixed by bodyweight and leverage, so duration is the only thing there is
    to step — which is also why this one is a timed hold and the psoas
    isometric beside it is not."""
    by_week: dict[int, set[int]] = {}
    for d in DAYS:
        for e in PLAN[d]["exercises"]:
            if e["name"] != HOVER:
                continue
            assert e["type"] == "hold" and e["laterality"] == "unilateral"
            work = e["sets"] * e["hold_seconds"]
            by_week.setdefault((d - 1) // 7 + 1, set()).add(work)
    assert by_week, "the knee-hover is not in the block"
    for week, doses in by_week.items():
        assert len(doses) == 1, f"week {week} runs two different doses: {doses}"
    weeks = sorted(by_week)
    seconds = [next(iter(by_week[w])) for w in weeks]
    assert seconds == sorted(seconds), f"the dose steps DOWN across {weeks}: {seconds}"
    assert seconds[-1] > seconds[0], "the dose never actually progresses"


def test_the_knee_hover_says_the_knee_hovers_and_the_ribs_stay_down():
    """The athlete's own specification, and the two cues that make it the
    exercise rather than a stretch he holds: knee over the ankle, back knee off
    the ground. The lumbar arch is the named failure — the 2026-07-06 entry is
    a genuine strain produced by holding a corrected posture — so the set ends
    on the ribs flaring, not on the clock."""
    ex = next(e for d in DAYS for e in PLAN[d]["exercises"] if e["name"] == HOVER)
    mech = ex["mechanics"].lower()
    assert "over the ankle" in mech
    assert "off the floor" in mech and "never touches down" in mech
    assert "ribs" in mech and "arch" in mech


def test_the_right_hip_keeps_its_rotation_cue_in_the_new_work():
    """Key rule 7: right hip flexion past 60 degrees is cued neutral or
    slightly internal, because external rotation is what snaps the iliopsoas
    tendon. Both end-range items take the right hip there."""
    for name in (PSOAS, LIFT_OFFS):
        ex = next(e for d in DAYS for e in PLAN[d]["exercises"] if e["name"] == name)
        text = ex["mechanics"].lower()
        assert "right" in text, name
        assert "inward" in text or "internal" in text, name


def test_the_new_work_reaches_the_safety_rules():
    """`unknown` is not a block and reads exactly like `cleared` on the
    training screen. There was NO psoas rule in services/rules.py at all before
    this change — on the one muscle the imaging, the imbalance list and the
    symptom log all name."""
    for name in _STRENGTH:
        severity = rules.check_movement(name, 2)["severity"]
        assert severity in ("caution", "cleared"), f"{name} -> {severity}"


def test_the_lift_offs_are_the_clusters_own_exercise_by_name():
    """One name per movement across the layers. cluster_a_mechanics owns this
    exercise and its how-to text; a second name for it would let the two drift
    the way the plan and the prescription were about to before
    tests/test_cluster_session_is_real_exercises.py bound them."""
    assert LIFT_OFFS in {e.name for e in cm.LIBRARY}


def test_the_lift_offs_run_at_the_end_of_the_flexibility_session():
    """Pattern G's own sequencing: 'You can reach it, you cannot produce it.
    Tilt work moves to the END of the session and becomes strength work.' The
    2026-08-12 reading is tilt_range 89 deg clearing the 90 deg line while
    tilt_production 93 deg does not, which is that pattern exactly."""
    cluster_days = [d for d in DAYS if "Cluster A" in (PLAN[d].get("objective") or "")]
    lift_days = [d for d in DAYS
                 if any(e["name"] == LIFT_OFFS for e in PLAN[d]["exercises"])]
    assert lift_days == cluster_days, (lift_days, cluster_days)
    for d in lift_days:
        names = [e["name"] for e in PLAN[d]["exercises"]]
        assert names[-1] == LIFT_OFFS, f"day {d} ends on {names[-1]}"


def test_the_front_of_the_hip_is_released_every_day_but_the_assessment():
    """15 of 28 before 2026-08-24. The eight days carrying nothing at all were
    the rest, travel and mobility days — i.e. the DESK days, which are the
    exposure the protocol treats and the reason patient_profile says the daily
    front-of-hip protocol 'continues alongside and is the larger dose'. It had
    never run anywhere. Day 28 stays off: that screen's whole value is
    comparability with the Stage 1 and Stage 2A versions of itself."""
    assert _ANTERIOR_DAYS == [d for d in DAYS if d != 28], _ANTERIOR_DAYS


def test_the_release_dose_did_not_grow_to_pay_for_the_strength_work():
    """The athlete's reasoning, 2026-08-24: release buys the next two or three
    hours, so more of it is not the answer and a longer hold would be the trade
    he rejected. One zone, 60 s a side, everywhere it runs."""
    assert tp.ANTERIOR_HIP_RELEASE["hold_seconds"] == 60
    assert tp.ANTERIOR_HIP_RELEASE["sets"] == 1


def test_preparation_still_clears_the_ten_minute_floor_on_training_days():
    """The ceiling test's other half. The band is 10-15 min, and the upper-body
    days cross 10 for the first time here — they were at 9.55 with no
    front-of-hip work on them at all. Rest days and the day-28 screen are
    exempt for the same reason they are exempt from the raise: nothing is being
    prepared for, and day 28's value is comparability."""
    prep = sess.RELEASE_EXERCISE_NAMES | {
        "Walking Raise (Incline)", "Single-Leg Glute Bridge", "Dead Bug",
        "Scapular Wall Slide", "Prone Y-Raise (Scapular)",
    }
    for d in DAYS:
        if PLAN[d]["day_type"] in ("rest", "test"):
            continue
        exercises = [ex for ex in PLAN[d]["exercises"]
                     if "(Test)" not in ex["name"]
                     and "(Timed Test)" not in ex["name"]
                     and "(Trial)" not in ex["name"]]
        seconds = 0
        for ex in exercises:
            if ex["name"] not in prep:
                break
            sides = 2 if (ex.get("laterality") == "unilateral"
                          and ex["name"] not in _RIGHT_ONLY) else 1
            seconds += sess.exercise_duration_seconds(ex) * sides
        assert seconds >= 10 * 60, (
            f"day {d} spends only {seconds / 60:.1f} min preparing, under the "
            f"10-minute floor")


def test_the_release_names_the_spot_that_actually_releases():
    """The block named the WRONG SPOT from day 1 and ran that way for a week.

    docs/training/release_protocols_2026-08-10.md gives the ball two target
    zones. The exercise took zone 1 -- the pocket-corner just below and OUTSIDE
    the point of the hip bone. Athlete, 2026-08-24: "the second zone is where I
    get the pressure release during anterior hip flexor release, there is no
    release in the outside point of the hip bone that I do for that exercise."

    His FIRST session note said so, on 2026-08-18 -- "inside of my right" --
    and it was filed as a protocol deviation instead of read as the finding.
    The instruction now names zone 2, and the warning no longer sends him back
    out to the crest: it used to say "stay on the OUTER half of the front of
    the hip", which pointed away from the only spot that responds.

    Anatomy backs the correction rather than merely accommodating it: iliacus
    and psoas sit in that hollow and attach along L1-L4, which is where he
    reports the referred sensation into the mid-back. TFL sits on the crest,
    where he gets nothing.
    """
    ex = tp.ANTERIOR_HIP_RELEASE
    mech = ex["mechanics"].lower()
    warning = (ex["warning"] or "").lower()

    assert "inward" in mech and "just inside" in mech, (
        "the instruction no longer names the inward, higher spot -- the only "
        "one that releases for him")
    assert "outside the point of the hip bone" not in mech, (
        "the instruction is pointing at the bony corner again, where he gets "
        "nothing")
    assert "outer half" not in warning, (
        "the warning is sending him back out to the crest and away from the "
        "spot the exercise exists to press")
