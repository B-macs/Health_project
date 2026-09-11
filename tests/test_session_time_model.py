"""The session time model — services.sessions.session_seconds and the
measured changeover constants it is built on.

Until 2026-09-11 a session estimate charged 30 s per exercise change and read
no laterality. Measured from the per-set timestamps of 13 logged sessions
(109 exercise changes), an exercise change costs a median 74 s to a floor item
and 117 s to a rack, plates or a cable. Stage 2B day 22 was estimated at 54
min and took 81; the athlete's own words for the same session were "nearly 40
mins in when I finished just the first two real training exercises", which the
timestamps put at 39.

Two things are pinned here. The constants, with their provenance, so a hand
edit has to argue with a measurement; and the shape of the model — laterality
doubles work, consecutive entries of one lift share a station, the gap after an
entry is the longer of its rest and the changeover — because those are the
parts that made the old estimate wrong, not the arithmetic.
"""

from __future__ import annotations

import training_plan as tp
from services import sessions as s


# ── the measured constants ──────────────────────────────────────────────────

def test_changeover_constants_are_the_measured_medians():
    """Re-measure with scripts/measure_changeovers.py before changing these.
    They are medians of the athlete's own changeovers, not preferences."""
    assert s.CHANGEOVER_SECONDS == {"floor": 74, "gym": 117, "band": 158}
    assert s.CHANGEOVER_SAME_STATION_SECONDS < s.CHANGEOVER_SECONDS["floor"]


def test_the_old_thirty_second_changeover_is_gone():
    """The single number the old estimate got wrong."""
    assert 30 not in s.CHANGEOVER_SECONDS.values()


# ── station kinds ───────────────────────────────────────────────────────────

def test_station_kind_reads_equipment_then_name():
    assert s.station_kind({"name": "Goblet Squat", "equipment_type": "dumbbell"}) == "gym"
    assert s.station_kind({"name": "Pallof Press (Cable)", "equipment_type": "cable"}) == "gym"
    assert s.station_kind({"name": "Band Front Squat", "equipment_type": "band"}) == "band"
    assert s.station_kind({"name": "Dead Bug"}) == "floor"
    # A treadmill is a station even though the exercise carries no equipment.
    assert s.station_kind(tp.PREP_RAISE) == "gym"


# ── laterality ──────────────────────────────────────────────────────────────

def test_a_two_sided_item_counts_both_sides_and_a_right_only_item_does_not():
    two = {"name": "Full Side Bridge", "type": "hold", "laterality": "unilateral",
           "sets": 3, "hold_seconds": 45, "rest_seconds": 45}
    one = dict(two, laterality="bilateral")
    assert s.exercise_work_seconds(two) == 2 * s.exercise_work_seconds(one) - 2 * 45
    right_only = dict(two, name="Right Posterior Hip Capsule Stretch (Revised Cue)")
    assert s.sides(right_only) == 1


def test_the_rest_between_sets_is_not_doubled_for_a_two_sided_item():
    """The guided flow runs no timer on the right-to-left switch (the
    rest-interval review's own finding), so the other side's work IS the
    rest. Doubling it would repeat the error that inflated the split's cost."""
    ex = {"name": "Pallof Press (Cable)", "type": "reps", "laterality": "unilateral",
          "sets": 3, "reps": 10, "rest_seconds": 45, "equipment_type": "cable"}
    assert s.exercise_work_seconds(ex) == 3 * 10 * s.REPS_SECONDS_DEFAULT * 2 + 2 * 45


# ── per-rep time ────────────────────────────────────────────────────────────

def test_tempo_sets_the_seconds_per_rep():
    assert s.tempo_seconds("3-1-1") == 5
    assert s.tempo_seconds("3-1-3") == 7
    assert s.tempo_seconds(None) == s.REPS_SECONDS_DEFAULT
    assert s.tempo_seconds("fast") == s.REPS_SECONDS_DEFAULT


def test_a_set_of_ten_at_tempo_three_one_one_is_fifty_seconds():
    """Measured 2026-09-10: RDL, ten reps at 3-1-1, ~44 s per set."""
    ex = {"name": "Romanian Deadlift (DB)", "type": "reps", "sets": 1, "reps": 10,
          "tempo": "3-1-1", "rest_seconds": 120}
    assert s.set_work_seconds(ex) == 50


# ── one lift is one station ─────────────────────────────────────────────────

def test_base_name_strips_the_role_suffix():
    assert s.base_name("Goblet Squat (Ramp Set)") == "Goblet Squat"
    assert s.base_name("Romanian Deadlift (Heavy Top Set)") == "Romanian Deadlift"
    assert s.base_name("Romanian Deadlift (DB)") == "Romanian Deadlift"
    assert s.base_name("Full Side Bridge") == "Full Side Bridge"


def test_a_ramp_followed_by_its_lift_costs_a_weight_change_not_a_changeover():
    ramp = dict(tp.GOBLET_RAMP)
    lift = next(e for e in tp._s2b_gym_a(4)["exercises"] if e["name"] == "Goblet Squat")
    assert s.changeover_seconds(ramp, lift) == s.CHANGEOVER_SAME_STATION_SECONDS
    assert s.changeover_seconds(lift, tp.END_RANGE_PSOAS_ISOMETRIC) == s.CHANGEOVER_SECONDS["floor"]


def test_nesting_the_singles_under_their_lift_is_cheaper_than_interleaving_them():
    """The 2026-09-10 order (both ramps, both tops, both lifts) against the
    nested order (ramp, top, lift, ramp, top, lift) — same work, fewer
    stations. This is the arithmetic behind Key Rule 21's nesting rule."""
    a4 = _by_name(tp._s2b_gym_a(4)["exercises"])
    interleaved = [a4["Goblet Squat (Ramp Set)"], a4["Romanian Deadlift (Ramp Set)"],
                   a4["Goblet Squat (Heavy Top Set)"], a4["Romanian Deadlift (Heavy Top Set)"],
                   a4["Goblet Squat"], a4["Romanian Deadlift (DB)"]]
    nested = [a4["Goblet Squat (Ramp Set)"], a4["Goblet Squat (Heavy Top Set)"], a4["Goblet Squat"],
              a4["Romanian Deadlift (Ramp Set)"], a4["Romanian Deadlift (Heavy Top Set)"],
              a4["Romanian Deadlift (DB)"]]
    assert s.session_seconds(nested) < s.session_seconds(interleaved)


def test_the_gap_after_an_entry_is_the_longer_of_its_rest_and_the_changeover():
    """After a heavy top set the athlete rests 150 s whether the next entry is
    the same lift or a walk to another station; a release item with 15 s of
    rest is bounded by the 74 s it takes to get onto the next mat."""
    top = dict(tp.GOBLET_TOP_SET)                    # rest 150
    lift = next(e for e in tp._s2b_gym_a(4)["exercises"] if e["name"] == "Goblet Squat")
    assert s.gap_seconds(top, lift) == 150           # same lift: the rest bounds it
    assert s.gap_seconds(top, tp.END_RANGE_PSOAS_ISOMETRIC) == 150   # different: still the rest
    release = tp.UPPER_GLUTE_RELEASE_5MIN            # rest 15
    assert s.gap_seconds(release, tp.PIRIFORMIS_PNF_5MIN) == s.CHANGEOVER_SECONDS["floor"]
    ramp = dict(tp.GOBLET_RAMP, rest_seconds=60)
    assert s.gap_seconds(ramp, lift) == 60           # same rack: the rest, not a changeover
    assert s.gap_seconds(None, lift) == 0


# ── against the measurement ─────────────────────────────────────────────────

def test_the_model_reads_stage_2b_day_22_near_its_measured_81_minutes():
    """The session that produced all of this. Logged at 81 min (session
    2026-09-10-156321a3). The old estimate said 54. The model charges the
    prescribed 150 s rests after the top sets, which the athlete cut short,
    so it reads a little over — the tolerance is for that, not for drift."""
    minutes = s.estimate_duration(tp.PLAN_STAGE2B[22]["exercises"])
    assert 75 <= minutes <= 95, minutes


def test_the_model_reads_the_stage_2a_gym_days_near_their_logged_hour():
    """2026-08-04 (day 15) logged 66 min, 2026-08-06 (day 17) 64, 2026-08-16
    (day 26) 52. The old estimate was ~35-40 against ~41-47 real working time
    plus preparation; this one should land within about ten minutes."""
    for day, logged in ((15, 66), (17, 64), (26, 52)):
        minutes = s.estimate_duration(tp.PLAN_STAGE2[day]["exercises"])
        assert abs(minutes - logged) <= 10, f"day {day}: model {minutes}, logged {logged}"


def test_the_estimate_floor_is_unchanged():
    assert s.estimate_duration([]) == 10


def _by_name(exercises):
    return {e["name"]: e for e in exercises}
