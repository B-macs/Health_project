"""Tests for services/strength.py — the Overall Strength Score and its split.

The properties pinned here are the ones the design actually depends on:
the contributions summing to the overall, measured performance never being
able to push the level down, and confidence being a product so any one
failure mode zeroes it.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

import strength_baselines as sb
import training_constants as tc
from services import strength


MW = {name: weight for name, (_cat, weight) in tc.EXERCISE_MOVEMENT_WEIGHT.items()}


def _row(name, day, sets, rpe=6):
    return {"movement_name": name, "session_date": day, "sets": sets,
            "exercise_rpe": rpe, "session_rpe": rpe}


# ── estimation ──────────────────────────────────────────────────────────────

def test_estimated_1rm_converts_rpe_to_reps_in_reserve():
    # 10 reps at RPE 6 has 4 in reserve, so it behaves like a 14-rep max.
    e1rm, effective, _ = strength.estimated_1rm(100.0, 10, 6)
    assert effective == 14.0
    assert e1rm == pytest.approx(100.0 * (1 + 14 / 30))


def test_estimated_1rm_treats_missing_rpe_as_all_out():
    """No RPE must be the CONSERVATIVE reading. Assuming a set was easy would
    inflate the estimate, i.e. invent strength that was never demonstrated."""
    _, effective, _ = strength.estimated_1rm(100.0, 5, None)
    assert effective == 5.0


def test_estimated_1rm_rpe_above_ten_does_not_produce_negative_reserve():
    _, effective, _ = strength.estimated_1rm(100.0, 5, 11)
    assert effective == 5.0


def test_estimated_1rm_flags_estimates_outside_epleys_validated_range():
    _, _, ok_short = strength.estimated_1rm(100.0, 5, 9)      # 6 effective
    _, _, ok_long = strength.estimated_1rm(100.0, 12, 5)      # 17 effective
    assert ok_short is True
    assert ok_long is False


def test_exercise_index_is_none_without_a_baseline():
    assert strength.exercise_index(50.0, 0.0) is None


def test_exercise_index_is_a_percentage_of_the_2025_self():
    assert strength.exercise_index(50.0, 100.0) == pytest.approx(50.0)


# ── observation extraction ──────────────────────────────────────────────────

def test_unloaded_sets_never_produce_an_observation():
    """A rehab drill has no external load and therefore no 1RM to estimate.
    Inventing one is the failure this guards."""
    rows = [_row("Dead Bug", "2026-07-20", [{"reps": 10, "weight": None}])]
    assert strength.best_observations(rows, today=date(2026, 8, 4)) == {}


def test_best_observation_is_the_heaviest_set_of_the_latest_day():
    rows = [
        _row("Lat Pulldown", "2026-07-20", [{"reps": 10, "weight": 40}]),
        _row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 45},
                                            {"reps": 10, "weight": 50}]),
    ]
    obs = strength.best_observations(rows, today=date(2026, 8, 4))["Lat Pulldown"]
    assert obs.session_date == date(2026, 7, 27)
    assert obs.weight_kg == 50


def test_rows_after_today_are_ignored_so_history_can_be_replayed():
    rows = [_row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 50}])]
    assert strength.best_observations(rows, today=date(2026, 7, 20)) == {}


def test_unparseable_session_date_is_skipped_not_raised():
    rows = [_row("Lat Pulldown", "not-a-date", [{"reps": 10, "weight": 50}])]
    assert strength.best_observations(rows, today=date(2026, 8, 4)) == {}


# ── region index and confidence ─────────────────────────────────────────────

def test_region_index_weights_by_movement_not_evenly():
    idx = {"Hip Thrust (Loaded)": 100.0, "Goblet Squat": 0.0}
    weights = {"Hip Thrust (Loaded)": 1.0, "Goblet Squat": 3.0}
    assert strength.region_index(idx, weights) == pytest.approx(25.0)


def test_region_index_is_none_when_nothing_is_comparable():
    assert strength.region_index({}, MW) is None


def test_confidence_is_zero_when_no_baseline_is_comparable():
    """Core's real situation: its only loaded movement's 2025 peak is a band,
    so comparability is 0 and no amount of logging can raise the confidence."""
    conf, parts = strength.region_confidence(
        {"Pallof Press (Cable)": 80.0}, MW, {"Pallof Press (Cable)": 0.0}, 50,
    )
    assert conf == 0.0
    assert parts["comparability"] == 0.0


def test_confidence_is_a_product_so_one_weak_factor_dominates():
    strong = {"A": 70.0, "B": 72.0}
    conf, parts = strength.region_confidence(strong, {"A": 1.0, "B": 1.0},
                                             {"A": 1.0, "B": 1.0}, 12)
    assert parts["quantity"] == 1.0
    assert parts["comparability"] == 1.0
    assert conf == pytest.approx(parts["consistency"])


def test_a_single_exercise_cannot_corroborate_itself():
    """Zero spread across one value is not agreement, it is absence of
    evidence. Scoring it as perfect consistency would let one lift carry a
    whole region."""
    conf, parts = strength.region_confidence({"A": 70.0}, {"A": 1.0}, {"A": 1.0}, 12)
    assert parts["consistency"] == 0.0
    assert conf == 0.0


def test_confidence_falls_as_exercises_inside_a_region_disagree():
    tight, _ = strength.region_confidence({"A": 70.0, "B": 72.0},
                                          {"A": 1.0, "B": 1.0}, {"A": 1.0, "B": 1.0}, 12)
    wide, _ = strength.region_confidence({"A": 30.0, "B": 90.0},
                                         {"A": 1.0, "B": 1.0}, {"A": 1.0, "B": 1.0}, 12)
    assert wide < tight


# ── shares ──────────────────────────────────────────────────────────────────

def test_shares_are_the_prior_when_there_is_no_confidence():
    shares = strength.region_shares(
        {r: 0.0 for r in strength.REGIONS},
        {"upper_body": 1.0, "core": 0.0, "lower_body": 0.0},
        sb.REGION_PRIOR,
    )
    for region in strength.REGIONS:
        assert shares[region] == pytest.approx(sb.REGION_PRIOR[region])


def test_shares_are_the_evidence_at_full_confidence():
    evidence = {"upper_body": 0.5, "core": 0.2, "lower_body": 0.3}
    shares = strength.region_shares({r: 1.0 for r in strength.REGIONS},
                                    evidence, sb.REGION_PRIOR)
    for region in strength.REGIONS:
        assert shares[region] == pytest.approx(evidence[region])


def test_shares_always_sum_to_one():
    shares = strength.region_shares(
        {"upper_body": 0.46, "core": 0.0, "lower_body": 0.37},
        {"upper_body": 0.42, "core": 0.04, "lower_body": 0.54},
        sb.REGION_PRIOR,
    )
    assert sum(shares.values()) == pytest.approx(1.0)


def test_one_session_cannot_swing_the_split():
    """The shrinkage blend is what makes the allocation refine gradually. A
    small move in the evidence and in confidence must produce a small move in
    the share, not a step change."""
    before = strength.region_shares({"upper_body": 0.46, "core": 0.0, "lower_body": 0.37},
                                    {"upper_body": 0.42, "core": 0.04, "lower_body": 0.54},
                                    sb.REGION_PRIOR)
    after = strength.region_shares({"upper_body": 0.50, "core": 0.0, "lower_body": 0.37},
                                   {"upper_body": 0.45, "core": 0.04, "lower_body": 0.51},
                                   sb.REGION_PRIOR)
    assert max(abs(after[r] - before[r]) for r in strength.REGIONS) < 0.03


# ── the rounding invariant ──────────────────────────────────────────────────

def test_split_parts_sum_exactly_to_the_total():
    """The real shares round to 16.2 + 9.3 + 24.6 = 50.1 if each part is
    rounded independently. The last part absorbs the remainder instead."""
    shares = {"upper_body": 0.323, "core": 0.186, "lower_body": 0.491}
    parts = strength.split_parts(shares, 50.0)
    assert sum(parts.values()) == pytest.approx(50.0)


def test_split_parts_sum_exactly_at_the_2025_reference_too():
    shares = {"upper_body": 0.323, "core": 0.186, "lower_body": 0.491}
    assert sum(strength.split_parts(shares, 100.0).values()) == pytest.approx(100.0)


@pytest.mark.parametrize("u,c,l", [(0.3333, 0.3333, 0.3334), (0.111, 0.222, 0.667),
                                   (0.9, 0.05, 0.05), (0.0, 0.0, 1.0)])
def test_split_parts_sum_exactly_for_awkward_splits(u, c, l):
    parts = strength.split_parts({"upper_body": u, "core": c, "lower_body": l}, 50.0)
    assert sum(parts.values()) == pytest.approx(50.0)


# ── the weekly model ────────────────────────────────────────────────────────

def test_measured_performance_can_never_push_the_level_down():
    """The safety property. Pain, a substitution, a rehab restriction or a
    deliberately light week all show up as a low measured value — and none of
    them may read as strength loss."""
    level, why = strength.model_step(60.0, trend=30.0, has_stimulus=True, inactive_weeks=0)
    assert level == 60.0
    assert why == "flat"


def test_a_trend_inside_the_deadband_does_not_move_the_level():
    level, _ = strength.model_step(60.0, trend=60.5, has_stimulus=True, inactive_weeks=0)
    assert level == 60.0


def test_a_confirmed_gain_is_taken_only_partially_and_is_capped():
    level, _ = strength.model_step(60.0, trend=100.0, has_stimulus=True, inactive_weeks=0)
    assert level == pytest.approx(60.0 + strength.GAIN_CAP_POINTS)


def test_one_freak_workout_cannot_move_the_level_far():
    weeks = [(date(2026, 1, 5), 50.0), (date(2026, 1, 12), 51.0), (date(2026, 1, 19), 95.0)]
    out = strength.run_model(weeks, seed=50.0)
    assert out[-1][2] <= 50.0 + strength.GAIN_CAP_POINTS


def test_the_first_inactive_week_is_free():
    level, why = strength.model_step(60.0, None, has_stimulus=False, inactive_weeks=1)
    assert level == 60.0
    assert why == "grace"


def test_prolonged_inactivity_decays_and_accelerates():
    early, _ = strength.model_step(60.0, None, False, 2)
    late, _ = strength.model_step(60.0, None, False, 6)
    assert late < early < 60.0


def test_decay_is_suspended_while_calibrating():
    level, why = strength.model_step(60.0, None, False, 8, decay_suspended=True)
    assert level == 60.0
    assert "calibrating" in why


def test_returning_after_a_layoff_does_not_inherit_the_old_trend():
    """The bug this pins: a positional "last 3 entries with data" window let a
    six-week layoff sit invisibly between two entries, so the first week back
    was compared against a median built from before the break and awarded a
    gain the session did not support. A calendar window empties across a gap,
    so the week back has no trend and the level cannot move."""
    weeks = [(date(2026, 1, 5), 62.0), (date(2026, 1, 12), 62.0)]
    weeks += [(date(2026, 1, 19) + timedelta(weeks=n), None) for n in range(6)]
    weeks += [(date(2026, 3, 2), 54.0)]
    out = strength.run_model(weeks, seed=57.72, decay_suspended=True)
    before_return, week_back = out[-2], out[-1]
    assert week_back[1] == 54.0
    assert week_back[2] == pytest.approx(before_return[2])   # unchanged
    assert week_back[3] == "no trend yet"


def test_a_second_week_back_still_cannot_gain_from_a_lower_result():
    """Even once the calendar window refills, two weeks measured BELOW the
    level produce a median below it — so the gain has to be re-earned rather
    than resumed."""
    weeks = [(date(2026, 1, 5), 62.0), (date(2026, 1, 12), 62.0)]
    weeks += [(date(2026, 1, 19) + timedelta(weeks=n), None) for n in range(6)]
    weeks += [(date(2026, 3, 2), 54.0), (date(2026, 3, 9), 57.0)]
    out = strength.run_model(weeks, seed=57.72, decay_suspended=True)
    assert out[-1][2] == pytest.approx(out[-3][2])


# ── the whole snapshot ──────────────────────────────────────────────────────

def _snapshot(rows, today=date(2026, 8, 4), calibrating=True):
    return strength.snapshot(
        rows, sb.PEAKS_2025, tc.EXERCISE_BODY_REGION, MW, sb.REGION_PRIOR,
        sb.PR_RIR, sb.ANCHOR_VALUE, today=today, calibrating=calibrating,
    )


def test_contributions_always_total_the_overall():
    rows = [
        _row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 45}]),
        _row("Hip Thrust (Loaded)", "2026-07-27", [{"reps": 10, "weight": 40}]),
    ]
    snap = _snapshot(rows)
    assert sum(r.contribution_points for r in snap["regions"]) == pytest.approx(sb.ANCHOR_VALUE)
    assert sum(r.contribution_pct for r in snap["regions"]) == pytest.approx(100.0)


def test_contributions_total_the_overall_with_no_training_at_all():
    snap = _snapshot([])
    assert sum(r.contribution_points for r in snap["regions"]) == pytest.approx(sb.ANCHOR_VALUE)


def test_every_regional_index_displays_at_fifty_while_calibrating():
    rows = [_row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 45}])]
    snap = _snapshot(rows)
    assert all(r.displayed_index == strength.CALIBRATION_INDEX for r in snap["regions"])


def test_the_overall_holds_at_fifty_for_any_share_split():
    """The identity the whole calibration period rests on: with every index at
    50, the overall is 50 whatever the shares turn out to be."""
    rows = [_row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 45}])]
    snap = _snapshot(rows)
    computed = sum(r.share * r.displayed_index for r in snap["regions"])
    assert computed == pytest.approx(sb.ANCHOR_VALUE)


def test_core_stays_uncalibrated_because_its_2025_peak_is_a_band():
    rows = [_row("Pallof Press (Cable)", "2026-07-27", [{"reps": 10, "weight": 12.5}])]
    core = next(r for r in _snapshot(rows)["regions"] if r.region == "core")
    assert core.index is None
    assert core.confidence == 0.0
    assert core.calibrating is True


def test_a_region_below_the_exit_threshold_is_marked_provisional():
    rows = [_row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 45}])]
    upper = next(r for r in _snapshot(rows)["regions"] if r.region == "upper_body")
    assert upper.confidence < strength.CALIBRATION_EXIT
    assert upper.calibrating is True


def test_an_exercise_without_a_2025_baseline_is_excluded_not_guessed():
    rows = [_row("Wall Sit", "2026-07-27", [{"reps": 1, "weight": 0}])]
    snap = _snapshot(rows)
    assert snap["exercises"] == {}
