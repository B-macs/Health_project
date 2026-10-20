"""Tests for services/strength.py — the Overall Strength Score and its split.

The properties pinned here are the ones the design actually depends on:
the contributions summing to the overall, the headline being the middle of
the last three lifting weeks (the owner, 2026-10-20), and confidence being a
product so any one failure mode zeroes it.
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


def test_two_rows_for_one_exercise_on_one_day_keep_the_heavier():
    """An exercise can occupy two rows in a single session — a top set logged
    apart from the back-offs, or a re-log. Ordering by date alone lets
    whichever came last in query order win, which silently understates the
    index whenever the lighter row is written second."""
    rows = [
        _row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 60}]),
        _row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 20}]),
    ]
    obs = strength.best_observations(rows, today=date(2026, 8, 4))["Lat Pulldown"]
    assert obs.weight_kg == 60


def test_a_later_day_still_wins_even_if_it_is_lighter():
    """The counterpart: within a day take the best, but across days take the
    most RECENT — the score tracks where you are now, not your best ever."""
    rows = [
        _row("Lat Pulldown", "2026-07-20", [{"reps": 10, "weight": 60}]),
        _row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 20}]),
    ]
    obs = strength.best_observations(rows, today=date(2026, 8, 4))["Lat Pulldown"]
    assert obs.session_date == date(2026, 7, 27)
    assert obs.weight_kg == 20


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


def test_split_parts_always_sum_exactly_and_never_go_negative():
    """Brute force, because the exact-sum rule is the one thing the display
    cannot be allowed to violate."""
    import random

    random.seed(7)
    for _ in range(2000):
        raw = [random.random() for _ in range(3)]
        total_raw = sum(raw)
        shares = dict(zip(strength.REGIONS, (v / total_raw for v in raw)))
        for total in (50.0, 100.0, 1.0, 0.0):
            parts = strength.split_parts(shares, total)
            assert sum(parts.values()) == pytest.approx(total, abs=1e-9)
            assert min(parts.values()) >= 0.0


def test_the_remainder_absorbed_by_the_last_part_is_bounded():
    """The cost of making the column total exactly: the last region carries
    everyone else's rounding error. With three regions at one decimal that is
    at most two half-ticks, 0.1 of a point — small enough not to misrepresent
    the share, and it is why the column that has to add up gets the exact
    treatment rather than the one that does not."""
    import random

    random.seed(11)
    bound = (len(strength.REGIONS) - 1) * 0.05
    worst = 0.0
    for _ in range(2000):
        raw = [random.random() for _ in range(3)]
        total_raw = sum(raw)
        shares = dict(zip(strength.REGIONS, (v / total_raw for v in raw)))
        parts = strength.split_parts(shares, 50.0)
        worst = max(worst, max(abs(parts[r] - shares[r] * 50.0) for r in strength.REGIONS))
    assert worst <= bound + 1e-9


# ── the headline: the measured index (the owner, 2026-10-20) ────────────────
# It replaced a capped weekly model (+1.5 a lifting week at most, from an
# assumed 50) whose tests went with it: the model counted lifting weeks rather
# than measuring the lifts.

def _weekly(weights, today=date(2026, 10, 19)):
    """One Lat Pulldown session a week, oldest first, the last in today's week;
    None is a week without it."""
    monday = today - timedelta(days=today.weekday())
    rows = []
    for back, weight in enumerate(reversed(weights)):
        if weight is not None:
            day = (monday - timedelta(weeks=back)).isoformat()
            rows.append(_row("Lat Pulldown", day, [{"reps": 10, "weight": weight}], rpe=8))
    return rows


def _levels(weights, weeks=8, today=date(2026, 10, 19)):
    return strength.score_series(_weekly(weights, today), sb.PEAKS_2025, MW, sb.PR_RIR,
                                 today=today, weeks=weeks)


def test_the_headline_is_the_middle_of_the_last_three_lifting_weeks():
    points = _levels([50, 60, 70, 80])
    assert points[-1]["level"] == pytest.approx(points[-2]["measured"], abs=0.05)
    assert points[-1]["why"] == "middle of 3 lifting weeks"
    assert strength.headline(points) == points[-1]["level"]


def test_a_week_without_a_lift_is_skipped_not_counted_as_zero():
    points = _levels([60, None, 70, 80])
    assert points[-3]["measured"] is None
    assert points[-1]["level"] == pytest.approx(points[-2]["measured"], abs=0.05)


def test_one_light_week_does_not_move_it_and_two_do():
    steady = _levels([80, 80, 60])
    assert steady[-1]["level"] == pytest.approx(steady[-2]["measured"], abs=0.05)
    lighter = _levels([80, 60, 60])
    assert lighter[-1]["level"] == pytest.approx(lighter[-1]["measured"], abs=0.05)
    assert lighter[-1]["level"] < steady[-1]["level"], "it falls when the lifts fall"


def test_no_lift_in_the_look_back_is_no_headline():
    weights = [80] + [None] * strength.HEADLINE_LOOKBACK_WEEKS
    points = _levels(weights)
    assert points[-1]["level"] is None and strength.headline(points) is None
    assert points[-1]["why"] == f"no lift in {strength.HEADLINE_LOOKBACK_WEEKS} weeks"


def test_the_level_does_not_depend_on_how_many_weeks_are_drawn():
    weights = [50, 60, None, 70, 80, 75, 72]
    narrow, wide = _levels(weights, weeks=3), _levels(weights, weeks=12)
    assert len(narrow) == 3 and len(wide) == 12
    assert [p["level"] for p in narrow] == [p["level"] for p in wide[-3:]]


def test_headline_is_the_last_point():
    assert strength.headline([{"level": None}, {"level": 51.5}]) == 51.5
    assert strength.headline([{"level": 51.5}, {"level": None}]) is None
    assert strength.headline([]) is None


# ── the whole snapshot ──────────────────────────────────────────────────────

def _snapshot(rows, today=date(2026, 8, 4), overall=sb.ANCHOR_VALUE):
    return strength.snapshot(
        rows, sb.PEAKS_2025, tc.EXERCISE_BODY_REGION, MW, sb.REGION_PRIOR,
        sb.PR_RIR, overall, today=today,
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


def test_a_measured_region_below_the_exit_shows_the_placeholder():
    """Changed on purpose 2026-10-13 (WP-15). It was "every regional index
    displays at fifty while calibrating" — one flag, which the view always set,
    so all three regions read 50 for ever. Calibration is now per region: a
    MEASURED region below the exit still shows the placeholder, and a region
    with no measurement shows nothing (next test)."""
    rows = [_row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 45}])]
    upper = next(r for r in _snapshot(rows)["regions"] if r.region == "upper_body")
    assert upper.index is not None and upper.confidence < strength.CALIBRATION_EXIT
    assert upper.displayed_index == strength.CALIBRATION_INDEX


def test_a_region_with_no_measurement_shows_nothing_never_zero_or_fifty():
    """Zero would claim a measurement of nothing; fifty would claim a
    calibration that cannot happen. Core has no 2025 kilogram baseline, so it
    reads None whatever is logged, and the screen prints "—"."""
    rows = [_row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 45}]),
            _row("Pallof Press (Cable)", "2026-07-27", [{"reps": 10, "weight": 12.5}])]
    by_region = {r.region: r for r in _snapshot(rows)["regions"]}
    assert by_region["core"].displayed_index is None
    assert by_region["lower_body"].displayed_index is None


def test_the_regions_divide_whatever_headline_they_are_given():
    """Replaces "the overall holds at fifty for any share split" (2026-10-13):
    the headline is now the modelled level, not the anchor, and the identity
    the screen keeps is that the three contributions total it exactly."""
    rows = [_row("Lat Pulldown", "2026-07-27", [{"reps": 10, "weight": 45}])]
    snap = _snapshot(rows, overall=57.3)
    assert sum(r.contribution_points for r in snap["regions"]) == pytest.approx(57.3)


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


# ── the gate that counts and the gate that measures must be the same gate ────

def test_future_dated_rows_cannot_inflate_confidence():
    """The observation COUNT feeds `quantity`, which multiplies into
    confidence, which is the shrinkage weight that sets the displayed split.
    It once filtered on neither the date nor `today`, so twelve rows dated next
    month took upper body from provisional to established and moved real points
    off the other two regions."""
    base = [_row("Lat Pulldown", "2026-07-06", [{"reps": 10, "weight": 40}]),
            _row("Incline DB Press", "2026-07-06", [{"reps": 10, "weight": 14}])]
    future = base + [_row("Lat Pulldown", f"2026-09-{d:02d}", [{"reps": 10, "weight": 40}])
                     for d in range(1, 13)]
    before = _snapshot(base)["regions"]
    after = _snapshot(future)["regions"]
    for a, b in zip(before, after):
        assert a.observations == b.observations
        assert a.confidence == pytest.approx(b.confidence)
        assert a.contribution_points == pytest.approx(b.contribution_points)


def test_malformed_dates_cannot_inflate_confidence():
    base = [_row("Lat Pulldown", "2026-07-06", [{"reps": 10, "weight": 40}]),
            _row("Incline DB Press", "2026-07-06", [{"reps": 10, "weight": 14}])]
    junk = base + [_row("Lat Pulldown", "not-a-date", [{"reps": 10, "weight": 40}])] * 5
    upper_before = next(r for r in _snapshot(base)["regions"] if r.region == "upper_body")
    upper_after = next(r for r in _snapshot(junk)["regions"] if r.region == "upper_body")
    assert upper_before.observations == upper_after.observations


def test_an_observation_is_a_day_not_a_row():
    """Two rows for one lift in one session are one observation of it."""
    rows = [_row("Lat Pulldown", "2026-07-06", [{"reps": 10, "weight": 40}]),
            _row("Lat Pulldown", "2026-07-06", [{"reps": 10, "weight": 35}])]
    days = strength.observation_days(rows, today=date(2026, 8, 4))
    assert days["Lat Pulldown"] == {date(2026, 7, 6)}


def test_every_2025_baseline_resolves_in_both_lookup_maps():
    """A baseline whose exercise name is missing from either map is silently
    excluded from its region — no error, just a lift that quietly stops
    counting. The names are hand-transcribed, so nothing but a test catches a
    typo or a rename."""
    for name in sb.PEAKS_2025:
        assert name in tc.EXERCISE_BODY_REGION, f"{name} has no body region"
        assert name in tc.EXERCISE_MOVEMENT_WEIGHT, f"{name} has no movement weight"
        assert tc.EXERCISE_BODY_REGION[name] in strength.REGIONS


def test_the_calibration_index_is_not_duplicated_in_the_baselines_module():
    """It is the model's constant, not a measured baseline. A second copy in
    strength_baselines.py read like the source of truth and was read by
    nothing."""
    assert not hasattr(sb, "CALIBRATION_INDEX")


# ── WP-15 (2026-10-13): per-region calibration, the headline, the RPE read ──

_DAYS = ["2026-09-08", "2026-09-15", "2026-09-22", "2026-09-29"]


def _confident_upper_rows():
    """Three comparable upper-body lifts, each at 70% of its own 2025 e1RM on
    four days: quantity 12/12, comparability 1.0, consistency 1.0, so upper's
    confidence is 1.0. Weight = 0.5 x base: 10 reps at RPE 8 is 12 effective
    reps, a factor of 1.4, and 0.5 x 1.4 = 0.7."""
    rows = []
    for name in ("Lat Pulldown", "Single-Arm DB Row", "Incline DB Press"):
        peak_kg, peak_reps, _c, _w = sb.PEAKS_2025[name]
        base = strength.baseline_e1rm(peak_kg, peak_reps, sb.PR_RIR)
        rows += [_row(name, d, [{"reps": 10, "weight": round(0.5 * base, 4)}], rpe=8)
                 for d in _DAYS]
    return rows


def test_a_confident_region_shows_its_measured_index():
    upper = next(r for r in _snapshot(_confident_upper_rows(), today=date(2026, 10, 1))["regions"]
                 if r.region == "upper_body")
    assert upper.confidence >= strength.CALIBRATION_EXIT
    assert upper.calibrating is False
    assert upper.displayed_index == pytest.approx(70.0, abs=0.01)


def test_an_unmeasurable_region_does_not_hold_the_others_in_calibration():
    """Core can never leave calibration (no 2025 kilogram baseline), so a
    flag that waited for every region would never clear."""
    snap = _snapshot(_confident_upper_rows(), today=date(2026, 10, 1))
    assert snap["calibrating"] is False


def test_the_snapshot_calibrates_while_a_measured_region_is_below_the_exit():
    rows = _confident_upper_rows() + [
        _row("Hip Thrust (Loaded)", "2026-09-29", [{"reps": 10, "weight": 40}])]
    assert _snapshot(rows, today=date(2026, 10, 1))["calibrating"] is True


def test_nothing_measured_is_still_calibrating():
    assert _snapshot([])["calibrating"] is True


def test_the_screen_headline_is_the_charts_level_and_the_regions_total_it():
    rows = _weekly([60, 62, 64, 66])
    out = strength.screen(rows, sb.PEAKS_2025, tc.EXERCISE_BODY_REGION, MW, sb.REGION_PRIOR,
                          sb.PR_RIR, today=date(2026, 10, 19), weeks=6)
    assert out["overall"] == out["score_series"][-1]["level"]
    assert sum(r.contribution_points for r in out["regions"]) == pytest.approx(out["overall"])


def test_with_no_lift_the_screen_has_no_headline_and_no_points():
    out = strength.screen([], sb.PEAKS_2025, tc.EXERCISE_BODY_REGION, MW, sb.REGION_PRIOR,
                          sb.PR_RIR, today=date(2026, 10, 19))
    assert out["overall"] is None
    assert all(r.contribution_points == 0.0 for r in out["regions"])


def test_the_estimate_reads_the_session_rpe_not_the_heart_rate_one():
    """exercise_rpe has been filled from heart rate since 2026-08-14, and heart
    rate is not reps in reserve (Key Rule 23). 10 reps at the session's RPE 8
    is 12 effective reps; at the heart rate's 3 it would be 17."""
    row = {"movement_name": "Lat Pulldown", "session_date": "2026-09-08",
           "sets": [{"reps": 10, "weight": 50}], "exercise_rpe": 3.0, "session_rpe": 8.0}
    obs = strength.best_observations([row], today=date(2026, 9, 9))["Lat Pulldown"]
    assert obs.rpe == 8.0 and obs.effective_reps == 12.0
    week = strength.weekly_measured_index([row], sb.PEAKS_2025, MW, sb.PR_RIR,
                                          today=date(2026, 9, 9), weeks=1)
    base = strength.baseline_e1rm(*sb.PEAKS_2025["Lat Pulldown"][:2], sb.PR_RIR)
    assert week[-1][1] == pytest.approx(50 * (1 + 12 / 30) / base * 100)


def test_a_missing_session_rpe_reads_as_all_out_never_as_the_heart_rate():
    row = {"movement_name": "Lat Pulldown", "session_date": "2026-09-08",
           "sets": [{"reps": 10, "weight": 50}], "exercise_rpe": 3.0, "session_rpe": None}
    assert strength.best_observations([row], today=date(2026, 9, 9))["Lat Pulldown"].rpe == 10.0
