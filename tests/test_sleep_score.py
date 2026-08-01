"""Tests for services/sleep_score.py — the deterministic Sleep Score that
replaced the Home page's uncapped "% of baseline" figure
(services/dashboard.py::sleep_percent). Mirrors tests/test_readiness.py's
style: baseline helpers, then the composite's per-contributor behavior and
missing-data re-normalization.
"""

from datetime import date

from services import sleep_score


def _row(d: str, **fields) -> dict:
    return {"date": d, **fields}


# ─── _bedtime_minutes_since_noon ────────────────────────────────────────────

def test_bedtime_before_midnight_measured_from_same_day_noon():
    # 11:15 PM -> 11h15m after noon = 675 minutes
    m = sleep_score._bedtime_minutes_since_noon("2026-07-20T23:15:00+00:00")
    assert m == 675.0


def test_bedtime_after_midnight_continues_past_the_previous_evening():
    # 1:00 AM "belongs" to the night before -> anchored to noon the day
    # before, landing later than an 11:15 PM bedtime (780 > 675), not a
    # jump backwards the way naive clock-time comparison would produce.
    m = sleep_score._bedtime_minutes_since_noon("2026-07-21T01:00:00+00:00")
    assert m == 780.0


def test_bedtime_none_or_unparseable_returns_none():
    assert sleep_score._bedtime_minutes_since_noon(None) is None
    assert sleep_score._bedtime_minutes_since_noon("") is None
    assert sleep_score._bedtime_minutes_since_noon("not-a-datetime") is None


# ─── bedtime_baseline ────────────────────────────────────────────────────────

def test_bedtime_baseline_insufficient_nights_is_none():
    rows = [_row(f"2026-06-{i+1:02d}", oura_sleep_bedtime_start=f"2026-06-{i+1:02d}T23:00:00+00:00")
            for i in range(6)]  # minimum window is 7
    assert sleep_score.bedtime_baseline(rows) == (None, 0)


def test_bedtime_baseline_averages_exactly_seven_nights():
    rows = [_row(f"2026-06-{i+1:02d}", oura_sleep_bedtime_start=f"2026-06-{i+1:02d}T23:00:00+00:00")
            for i in range(7)]
    baseline, window = sleep_score.bedtime_baseline(rows)
    assert window == 7
    assert baseline == 660.0  # 11:00 PM every night -> 660 minutes since noon


# ─── compute_sleep_score ─────────────────────────────────────────────────────

def _baseline_rows(n: int = 10, hours: float = 8.0) -> list[dict]:
    return [_row(f"2026-06-{i+1:02d}", sleep_duration_hours=hours) for i in range(n)]


# ─── Bit-identity regression (2026-07-31, before the breakdown refactor) ─────
#  compute_sleep_score was split into _contributor_scores + _composite so
#  sleep_score_breakdown could expose the seven sub-scores without changing
#  the public float. These three values were captured from the PRE-refactor
#  implementation and must never move. Float summation order is load-bearing:
#  _composite keeps the literal `sum(s * (w / total_w) ...)` rather than the
#  algebraically-equal `sum(s * w ...) / total_w`, which rounds differently.


def _full_night_rows() -> list[dict]:
    """28 nights of history plus one fully-populated night — enough for both
    the sleep and bedtime baselines, so all seven contributors score."""
    rows = [
        _row(f"2026-06-{i+1:02d}", sleep_duration_hours=7.5,
             oura_sleep_bedtime_start=f"2026-06-{i+1:02d}T23:00:00+00:00")
        for i in range(28)
    ]
    rows.append(_row(
        "2026-07-01",
        sleep_duration_hours=5.98, oura_sleep_efficiency=74.0,
        oura_sleep_total_seconds=21540, oura_sleep_rem_seconds=5040,
        oura_sleep_deep_seconds=2940, oura_sleep_restless_periods=18,
        oura_sleep_latency_seconds=720, oura_sleep_awake_seconds=7440,
        oura_sleep_bedtime_start="2026-06-30T22:42:00+00:00",
    ))
    return rows


def test_compute_sleep_score_is_unchanged_for_a_fixed_fully_scored_night():
    assert sleep_score.compute_sleep_score(date(2026, 7, 1), _full_night_rows()) == 86.8


def test_compute_sleep_score_is_unchanged_for_a_night_with_a_wake_time_adjustment():
    assert sleep_score.compute_sleep_score(
        date(2026, 7, 1), _full_night_rows(), {"2026-07-01": 30.0}) == 89.7


def test_compute_sleep_score_is_unchanged_when_renormalising_a_single_contributor():
    """The path where `total_w` renormalisation actually bites — one
    contributor carrying the whole score."""
    rows = _full_night_rows()[:28] + [_row("2026-07-01", sleep_duration_hours=6.2)]
    assert sleep_score.compute_sleep_score(date(2026, 7, 1), rows) == 83.2


def test_no_bio_rows_is_not_computed():
    assert sleep_score.compute_sleep_score(date(2026, 7, 20), []) == sleep_score.NOT_COMPUTED


def test_no_row_for_the_date_is_not_computed():
    rows = _baseline_rows()
    assert sleep_score.compute_sleep_score(date(2026, 7, 25), rows) == sleep_score.NOT_COMPUTED


def test_row_present_but_no_sleep_fields_is_not_computed():
    rows = _baseline_rows() + [_row("2026-07-20")]
    assert sleep_score.compute_sleep_score(date(2026, 7, 20), rows) == sleep_score.NOT_COMPUTED


def test_total_sleep_alone_is_capped_at_100_when_sleeping_more_than_baseline():
    # Regression case for the bug this module replaced: sleeping longer than
    # your recent average must never push the score over 100.
    rows = _baseline_rows(hours=8.0) + [_row("2026-07-20", sleep_duration_hours=12.0)]
    score = sleep_score.compute_sleep_score(date(2026, 7, 20), rows)
    assert score == 100.0  # only contributor available (Total Sleep), capped


def test_total_sleep_scales_linearly_below_baseline():
    rows = _baseline_rows(hours=8.0) + [_row("2026-07-20", sleep_duration_hours=6.0)]
    score = sleep_score.compute_sleep_score(date(2026, 7, 20), rows)
    # Today's own 6h reading also feeds its own baseline average (last 7 of
    # [8.0]*10 + [6.0] = six 8.0s + one 6.0 -> baseline 7.714...), same
    # behavior as readiness.sleep_baseline -- not a flat 6/8.
    assert score == 77.8


def test_full_good_night_scores_near_100():
    rows = _baseline_rows(hours=8.0) + [_row(
        "2026-07-20",
        sleep_duration_hours=8.0,
        oura_sleep_efficiency=95.0,
        oura_sleep_total_seconds=28800.0,   # 8h
        oura_sleep_rem_seconds=6336.0,      # 22% of total -> top of REM band
        oura_sleep_deep_seconds=4320.0,     # 15% of total -> top of Deep band
        oura_sleep_restless_periods=1.0,    # 0.125/hr -> well under the 2/hr floor
        oura_sleep_latency_seconds=900.0,   # 15 min -> dead centre of ideal band
        oura_sleep_bedtime_start="2026-07-20T23:00:00+00:00",
    )]
    score = sleep_score.compute_sleep_score(date(2026, 7, 20), rows)
    assert score == 98.9  # timing excluded (no 7-night bedtime baseline yet); efficiency (95) the rest


def test_full_bad_night_scores_low():
    rows = _baseline_rows(hours=8.0) + [_row(
        "2026-07-20",
        sleep_duration_hours=4.0,           # 50% of an 8h baseline
        oura_sleep_efficiency=60.0,
        oura_sleep_total_seconds=14400.0,   # 4h
        oura_sleep_rem_seconds=0.0,         # 0% -> below REM floor
        oura_sleep_deep_seconds=0.0,        # 0% -> below Deep floor
        oura_sleep_restless_periods=48.0,   # 12/hr -> at/over the restless ceiling
        oura_sleep_latency_seconds=0.0,     # fell asleep instantly -> latency floor
        oura_sleep_bedtime_start="2026-07-21T03:00:00+00:00",  # far off an 11 PM baseline
    )]
    score = sleep_score.compute_sleep_score(date(2026, 7, 20), rows)
    # Today's own 4h reading also feeds its own baseline average (same
    # behavior as readiness.sleep_baseline), pulling it below a flat 8.0 --
    # total_sleep and efficiency are the only nonzero contributors, timing
    # excluded (no 7-night bedtime baseline yet), re-normalized over the 6
    # available weights.
    assert score == 26.8


def test_missing_contributor_renormalizes_rather_than_dragging_score_down():
    # Same "perfect" inputs as the good-night test but efficiency is simply
    # absent (e.g. a payload gap) -- the remaining 6 contributors should
    # re-normalise the weights among themselves rather than being averaged
    # against a phantom zero.
    rows = _baseline_rows(hours=8.0) + [_row(
        "2026-07-20",
        sleep_duration_hours=8.0,
        oura_sleep_total_seconds=28800.0,
        oura_sleep_rem_seconds=6336.0,
        oura_sleep_deep_seconds=4320.0,
        oura_sleep_restless_periods=1.0,
        oura_sleep_latency_seconds=900.0,
        oura_sleep_bedtime_start="2026-07-20T23:00:00+00:00",
    )]
    score = sleep_score.compute_sleep_score(date(2026, 7, 20), rows)
    assert score == 100.0  # every available contributor is maxed


def test_latency_too_fast_is_penalised_same_as_too_slow():
    base = _baseline_rows(hours=8.0)
    fast = base + [_row("2026-07-20", oura_sleep_latency_seconds=0.0)]
    slow = base + [_row("2026-07-20", oura_sleep_latency_seconds=60 * 60.0)]  # 60 min
    ideal = base + [_row("2026-07-20", oura_sleep_latency_seconds=15 * 60.0)]  # 15 min
    assert sleep_score.compute_sleep_score(date(2026, 7, 20), fast) == 0.0
    assert sleep_score.compute_sleep_score(date(2026, 7, 20), slow) == 0.0
    assert sleep_score.compute_sleep_score(date(2026, 7, 20), ideal) == 100.0


# ─── compute_sleep_score — wake_time_adjustments ────────────────────────────
# CLAUDE.md rule 4's narrow manual-entry exception: a per-night correction
# for Oura's known wake-time-overestimation pattern. The single most
# important guarantee here is that every test ABOVE this section keeps
# passing completely unchanged -- wake_time_adjustments defaults to None and
# must be a no-op whenever it's None or has no entry for the scored date.

def test_wake_time_adjustments_none_is_identical_to_omitting_the_argument():
    rows = _baseline_rows(hours=8.0) + [_row("2026-07-20", sleep_duration_hours=6.0)]
    without_arg = sleep_score.compute_sleep_score(date(2026, 7, 20), rows)
    with_none = sleep_score.compute_sleep_score(date(2026, 7, 20), rows, wake_time_adjustments=None)
    assert without_arg == with_none == 77.8


def test_wake_time_adjustments_empty_dict_is_a_no_op():
    rows = _baseline_rows(hours=8.0) + [_row("2026-07-20", sleep_duration_hours=6.0)]
    score = sleep_score.compute_sleep_score(date(2026, 7, 20), rows, wake_time_adjustments={})
    assert score == 77.8


def test_wake_time_adjustments_entry_for_a_different_date_has_no_effect():
    # Regression guard: the adjustment must only ever touch for_date's own
    # row, never a historical row that happens to have an entry too.
    rows = _baseline_rows(hours=8.0) + [_row("2026-07-20", sleep_duration_hours=6.0)]
    score = sleep_score.compute_sleep_score(
        date(2026, 7, 20), rows, wake_time_adjustments={"2026-07-19": 30},
    )
    assert score == 77.8


def test_wake_time_adjustment_increases_total_sleep_and_therefore_the_score():
    rows = _baseline_rows(hours=8.0) + [_row(
        "2026-07-20", sleep_duration_hours=6.0,
        oura_sleep_total_seconds=21600.0,   # 6h
        oura_sleep_awake_seconds=1800.0,    # 30 min recorded awake
    )]
    unadjusted = sleep_score.compute_sleep_score(date(2026, 7, 20), rows)
    adjusted = sleep_score.compute_sleep_score(
        date(2026, 7, 20), rows, wake_time_adjustments={"2026-07-20": 30},
    )
    assert unadjusted == 77.8
    assert adjusted == 84.3
    assert adjusted > unadjusted


def test_wake_time_adjustment_is_floored_at_the_recorded_awake_seconds():
    # Requesting a 60-minute correction when only 15 minutes (900s) of
    # awake time was actually recorded must cap the adjustment at 15
    # minutes -- never subtract more awake-time than was really logged.
    rows = _baseline_rows(hours=8.0) + [_row(
        "2026-07-20", sleep_duration_hours=6.0,
        oura_sleep_total_seconds=21600.0,
        oura_sleep_awake_seconds=900.0,     # only 15 min actually recorded
    )]
    floored = sleep_score.compute_sleep_score(
        date(2026, 7, 20), rows, wake_time_adjustments={"2026-07-20": 60},
    )
    full_15_min = sleep_score.compute_sleep_score(
        date(2026, 7, 20), rows, wake_time_adjustments={"2026-07-20": 15},
    )
    # A 60-minute request and a 15-minute request land on the same floored
    # result, since only 15 minutes of awake time exists to reclaim.
    assert floored == full_15_min == 81.1


def test_wake_time_adjustment_scales_the_efficiency_contributor_too():
    # Efficiency = sleep-time / time-in-bed; a proportional increase in
    # effective sleep seconds (time-in-bed held fixed) scales efficiency by
    # that same ratio, not just Total Sleep.
    rows = [_row(
        "2026-07-20",
        oura_sleep_efficiency=90.0,
        oura_sleep_total_seconds=28800.0,   # 8h
        oura_sleep_awake_seconds=1000.0,
    )]
    unadjusted = sleep_score.compute_sleep_score(date(2026, 7, 20), rows)
    adjusted = sleep_score.compute_sleep_score(
        date(2026, 7, 20), rows, wake_time_adjustments={"2026-07-20": 10},
    )
    assert unadjusted == 90.0
    assert adjusted == 91.9
    assert adjusted > unadjusted


def test_wake_time_adjustment_does_not_affect_rem_deep_or_restfulness_contributors():
    # By design, the adjustment only reclassifies time from "awake" to
    # "asleep" -- it can't say WHICH stage that reclaimed time belongs to,
    # so REM/Deep/Restfulness (all computed against the RAW, unadjusted
    # oura_sleep_total_seconds) must be completely unaffected. Locks in the
    # asymmetry so a future refactor can't silently start (or stop)
    # adjusting total_s for these three without a test noticing.
    rows = _baseline_rows(hours=8.0) + [_row(
        "2026-07-20",
        sleep_duration_hours=6.0,
        oura_sleep_total_seconds=21600.0,   # 6h
        oura_sleep_awake_seconds=1800.0,    # 30 min recorded awake
        oura_sleep_rem_seconds=4320.0,      # 20% of raw total -> mid REM band
        oura_sleep_deep_seconds=2160.0,     # 10% of raw total -> mid Deep band
        oura_sleep_restless_periods=1.0,
    )]
    unadjusted = sleep_score.compute_sleep_score(date(2026, 7, 20), rows)
    adjusted = sleep_score.compute_sleep_score(
        date(2026, 7, 20), rows, wake_time_adjustments={"2026-07-20": 30},
    )
    # Total Sleep changes (proving the adjustment really applied here), but
    # the overall score shift must come ONLY from Total Sleep + Efficiency
    # -- if REM/Deep/Restfulness were also scaled by the adjustment, the
    # score delta would be larger than what those two contributors alone
    # (40% combined weight) can produce.
    assert adjusted != unadjusted
    assert round(adjusted - unadjusted, 1) <= 100 * (0.25 + 0.20)  # total_sleep + efficiency weights


def test_wake_time_adjustment_is_a_no_op_when_awake_seconds_field_is_absent():
    # An older/partial Oura row might simply lack oura_sleep_awake_seconds.
    # A nonzero requested adjustment must degrade to a no-op (floored at 0
    # available awake-seconds), not error.
    rows = _baseline_rows(hours=8.0) + [_row(
        "2026-07-20", sleep_duration_hours=6.0,
        oura_sleep_total_seconds=21600.0,
        # oura_sleep_awake_seconds deliberately omitted entirely.
    )]
    unadjusted = sleep_score.compute_sleep_score(date(2026, 7, 20), rows)
    adjusted = sleep_score.compute_sleep_score(
        date(2026, 7, 20), rows, wake_time_adjustments={"2026-07-20": 30},
    )
    assert adjusted == unadjusted == 77.8


# ─── sleep_score_breakdown (2026-07-31) ─────────────────────────────────────
#  Exposes the seven sub-scores the composite has always computed and thrown
#  away. dashboard.sleep_meta's copy has told users to "check the breakdown"
#  since it was written; this is that breakdown.


def test_breakdown_score_equals_compute_sleep_score_because_both_share_one_composite():
    """The load-bearing equality. If these ever diverge, the screen is
    explaining a number the engine did not produce."""
    rows = _full_night_rows()
    for adj in (None, {"2026-07-01": 30.0}):
        assert (sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows, adj)["score"]
                == sleep_score.compute_sleep_score(date(2026, 7, 1), rows, adj))


def test_breakdown_lists_all_seven_contributors_in_ouras_reading_order():
    """Not weight order — the screen should read the way the user's other
    sleep app reads."""
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), _full_night_rows())
    assert [c["key"] for c in b["contributors"]] == [
        "total_sleep", "efficiency", "restfulness", "rem", "deep", "latency", "timing",
    ]


def test_all_seven_rows_are_present_even_when_only_one_contributor_has_data():
    """Absence is the most informative thing on this panel, so the UI needs a
    row for every contributor, not just the ones that scored."""
    rows = _full_night_rows()[:28] + [_row("2026-07-01", sleep_duration_hours=6.2)]
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows)
    assert len(b["contributors"]) == 7
    assert sum(1 for c in b["contributors"] if c["score"] is not None) == 1
    assert set(b["missing"]) == {"efficiency", "restfulness", "rem", "deep", "latency", "timing"}


def test_a_missing_contributor_has_no_score_and_zero_effective_weight():
    """Zero effective weight is what makes it impossible for a missing
    contributor to contribute silently."""
    rows = _full_night_rows()[:28] + [_row("2026-07-01", sleep_duration_hours=6.2)]
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows)
    missing = [c for c in b["contributors"] if c["key"] == "efficiency"][0]
    assert missing["score"] is None
    assert missing["effective_weight"] == 0.0
    assert missing["contribution"] is None


def test_effective_weights_sum_to_one_because_missing_weights_are_renormalised():
    rows = _full_night_rows()[:28] + [_row("2026-07-01", sleep_duration_hours=6.2,
                                           oura_sleep_efficiency=80.0)]
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows)
    total = sum(c["effective_weight"] for c in b["contributors"])
    assert abs(total - 1.0) < 1e-6


def test_contributions_sum_to_the_composite_within_rounding_tolerance():
    """Tolerance, not equality: the composite rounds once, the parts don't.
    The UI must present these as contributions, never as exact arithmetic."""
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), _full_night_rows())
    total = sum(c["contribution"] for c in b["contributors"] if c["contribution"] is not None)
    assert abs(total - b["score"]) < 0.5


def test_available_weight_reports_how_much_of_the_score_was_actually_measured():
    rows = _full_night_rows()[:28] + [_row("2026-07-01", sleep_duration_hours=6.2)]
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows)
    assert b["available_weight"] == 0.25          # total_sleep alone


def test_breakdown_reports_the_raw_value_each_sub_score_came_from():
    """So the UI shows Oura's own number rather than re-deriving it and
    risking a different rounding."""
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), _full_night_rows())
    by = {c["key"]: c for c in b["contributors"]}
    assert by["total_sleep"]["raw"] == 5.98             # hours
    assert by["efficiency"]["raw"] == 74.0              # percent
    assert abs(by["rem"]["raw"] - 5040 / 21540 * 100) < 1e-9   # percent of total
    assert abs(by["latency"]["raw"] - 12.0) < 1e-9      # minutes


def test_breakdown_reports_the_baseline_a_relative_contributor_was_scored_against():
    """Total sleep and Timing are relative; the caption needs to say what to.

    7.45, not 7.5: tonight's own 5.98 h is inside its own 28-night baseline
    window, matching readiness.sleep_baseline's documented behaviour. The
    breakdown must report the baseline the score ACTUALLY used, not a tidier
    one, or the caption would explain a comparison that never happened."""
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), _full_night_rows())
    by = {c["key"]: c for c in b["contributors"]}
    assert by["total_sleep"]["reference"] == 7.45
    assert by["total_sleep"]["reference_window"] == 28
    assert by["timing"]["reference"] is not None
    assert by["timing"]["reference_window"] == 28


def test_the_wake_adjustment_moves_total_sleep_and_efficiency_and_nothing_else():
    """Exactly the two contributors compute_sleep_score adjusts — see its
    wake-time block. A third moving would mean the breakdown and the score
    disagree about what the correction did."""
    rows = _full_night_rows()
    plain = {c["key"]: c["score"] for c in
             sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows)["contributors"]}
    adj = {c["key"]: c["score"] for c in
           sleep_score.sleep_score_breakdown(
               date(2026, 7, 1), rows, {"2026-07-01": 30.0})["contributors"]}
    assert adj["total_sleep"] > plain["total_sleep"]
    assert adj["efficiency"] > plain["efficiency"]
    for key in ("restfulness", "rem", "deep", "latency", "timing"):
        assert adj[key] == plain[key], key


def test_breakdown_reports_the_adjustment_it_applied_so_the_ui_can_disclose_it():
    b = sleep_score.sleep_score_breakdown(
        date(2026, 7, 1), _full_night_rows(), {"2026-07-01": 30.0})
    assert b["wake_adjustment_minutes"] == 30.0


def test_breakdown_with_no_rows_is_not_computed_but_still_lists_seven_rows():
    """The empty state still needs a row per contributor to render dashes
    against."""
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), [])
    assert b["score"] == sleep_score.NOT_COMPUTED
    assert len(b["contributors"]) == 7
    assert b["available_weight"] == 0.0
    assert len(b["missing"]) == 7


def test_breakdown_is_deterministic_for_the_same_inputs():
    rows = _full_night_rows()
    assert (sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows)
            == sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows))
