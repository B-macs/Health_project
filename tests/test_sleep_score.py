"""Tests for services/sleep_score.py — the deterministic Sleep Score.

MODEL_VERSION 4 (2026-10-27, the athlete's choices that day): the weighted mean
of Oura's own seven sleep parts with this project's weights, with a wake-time
correction moving Total Sleep and Efficiency along Oura's own curve. Version 2
scored the parts itself and read 2026-10-27 at 91 against Oura's 63; its tests
pinned that arithmetic and went with it, replaced by the ones below. The
bedtime helpers are unchanged: they still give the Timing row its "minutes off
usual".
"""

from datetime import date

import pytest

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


# ─── The night of 2026-10-27 ────────────────────────────────────────────────
#  Oura's own seven parts that night, the raw night it scored them on, and 28
#  earlier nights so the Timing row has a usual bedtime to show against.

_PARTS_27_OCT = {
    "oura_sleep_total_sleep_score": 56.0, "oura_sleep_efficiency_score": 55.0,
    "oura_sleep_restfulness": 58.0, "oura_sleep_rem_score": 62.0,
    "oura_sleep_deep_score": 61.0, "oura_sleep_latency_score": 89.0,
    "oura_sleep_timing_score": 85.0,
}


def _history(n: int = 28) -> list[dict]:
    return [_row(f"2026-06-{i+1:02d}", sleep_duration_hours=6.9,
                 oura_sleep_bedtime_start=f"2026-06-{i+1:02d}T23:00:00+00:00")
            for i in range(n)]


def _night(**fields) -> list[dict]:
    return _history() + [_row(
        "2026-07-01",
        sleep_duration_hours=5.85, oura_sleep_total_seconds=20640.0,
        oura_sleep_efficiency=73.0, oura_sleep_rem_seconds=4380.0,
        oura_sleep_deep_seconds=3420.0, oura_sleep_restless_periods=750.0,
        oura_sleep_latency_seconds=660.0, oura_sleep_awake_seconds=4260.0,
        oura_sleep_bedtime_start="2026-07-01T23:54:00+00:00",
        **fields,
    )]


def test_the_score_is_the_weighted_mean_of_oura_s_seven_parts():
    """56×.25 + 55×.20 + 58×.10 + 62×.15 + 61×.15 + 89×.10 + 85×.05 = 62.4.
    Oura's own Sleep Score that night was 63; version 2 read 91."""
    assert sleep_score.compute_sleep_score(date(2026, 7, 1), _night(**_PARTS_27_OCT)) == 62.4


def test_the_weights_are_this_project_s():
    assert sleep_score._WEIGHTS == {
        "total_sleep": 0.25, "efficiency": 0.20, "rem": 0.15, "deep": 0.15,
        "restfulness": 0.10, "latency": 0.10, "timing": 0.05,
    }
    assert set(sleep_score.OURA_PARTS) == set(sleep_score._WEIGHTS)


# ─── The wake-time correction moves two parts along Oura's curve (version 4) ─
#  The athlete, 2026-10-27 afternoon: "I want it to still change the number of
#  hours Ive slept and such the overall sleep score".

def _by_key(rows, adjustments=None):
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows, adjustments)
    return b, {c["key"]: c for c in b["contributors"]}


def test_without_a_correction_every_part_is_oura_s_own():
    rows = _night(**_PARTS_27_OCT)
    for adjustments in (None, {}, {"2026-06-30": 30.0}):
        assert sleep_score.compute_sleep_score(date(2026, 7, 1), rows, adjustments) == 62.4


def test_the_watch_s_58_minutes_move_total_sleep_and_efficiency_along_oura_s_curve():
    """27 Oct: Oura 5h 44m at 73 %; the watch's 58 min make it 6h 42m at 85 %.
    Each part moves by the step Oura's own curve gives for that change."""
    curve_t, curve_e = sleep_score.OURA_TOTAL_SLEEP_CURVE, sleep_score.OURA_EFFICIENCY_CURVE
    raw_h, cor_h = 20640.0 / 3600, (20640.0 + 58 * 60) / 3600
    raw_e, cor_e = 73.0, 73.0 * (20640.0 + 58 * 60) / 20640.0
    plain_b, plain = _by_key(_night(**_PARTS_27_OCT))
    fixed_b, fixed = _by_key(_night(**_PARTS_27_OCT), {"2026-07-01": 58.0})
    assert fixed["total_sleep"]["score"] == pytest.approx(
        56.0 + sleep_score._interp(cor_h, curve_t) - sleep_score._interp(raw_h, curve_t))
    assert fixed["efficiency"]["score"] == pytest.approx(
        55.0 + sleep_score._interp(cor_e, curve_e) - sleep_score._interp(raw_e, curve_e))
    assert round(fixed["total_sleep"]["score"]) == 69 and round(fixed["efficiency"]["score"]) == 81
    assert fixed["total_sleep"]["raw"] == pytest.approx(cor_h), "the row shows the hours the score used"
    assert fixed["efficiency"]["raw"] == pytest.approx(cor_e)
    for key in ("restfulness", "rem", "deep", "latency", "timing"):
        assert fixed[key]["score"] == plain[key]["score"], key
    assert fixed_b["score"] == 70.8
    assert fixed_b["wake_adjustment_minutes"] == 58.0
    assert plain_b["wake_adjustment_minutes"] == 0.0


def test_the_correction_never_takes_more_awake_time_than_oura_recorded():
    rows = _history() + [{**_night(**_PARTS_27_OCT)[-1], "oura_sleep_awake_seconds": 600.0}]
    sixty = sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows, {"2026-07-01": 60.0})
    ten = sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows, {"2026-07-01": 10.0})
    assert sixty["score"] == ten["score"]
    assert sixty["wake_adjustment_minutes"] == 10.0


def test_a_corrected_part_stays_inside_zero_to_one_hundred():
    rows = _night(**{**_PARTS_27_OCT, "oura_sleep_total_sleep_score": 98.0,
                     "oura_sleep_efficiency_score": 99.0})
    _b, fixed = _by_key(rows, {"2026-07-01": 70.0})
    assert fixed["total_sleep"]["score"] <= 100.0
    assert fixed["efficiency"]["score"] <= 100.0


@pytest.mark.parametrize("curve", [sleep_score.OURA_TOTAL_SLEEP_CURVE,
                                   sleep_score.OURA_EFFICIENCY_CURVE])
def test_oura_s_curves_never_fall_as_the_reading_rises(curve):
    """A longer night can never score lower; the curves are measured by
    scripts/measure_oura_sleep_curves.py, never tuned by hand."""
    xs = [x for x, _ in curve]
    ys = [y for _, y in curve]
    assert xs == sorted(xs) and len(set(xs)) == len(xs)
    assert ys == sorted(ys)
    assert all(0.0 <= y <= 100.0 for y in ys)


def test_the_breakdown_and_the_score_agree_with_a_correction():
    rows = _night(**_PARTS_27_OCT)
    adj = {"2026-07-01": 58.0}
    assert (sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows, adj)["score"]
            == sleep_score.compute_sleep_score(date(2026, 7, 1), rows, adj))


def test_the_raw_night_does_not_move_the_score():
    """Oura scored the parts; the raw readings are only shown beside them."""
    longer = _history() + [_row("2026-07-01", oura_sleep_total_seconds=30000.0,
                                oura_sleep_efficiency=95.0, **_PARTS_27_OCT)]
    assert sleep_score.compute_sleep_score(date(2026, 7, 1), longer) == 62.4


def test_a_night_with_the_ring_s_raw_readings_but_none_of_oura_s_parts_has_no_score():
    rows = _night()
    assert sleep_score.compute_sleep_score(date(2026, 7, 1), rows) == sleep_score.NOT_COMPUTED


def test_a_part_oura_did_not_report_renormalises_rather_than_dragging_the_score_down():
    parts = {k: v for k, v in _PARTS_27_OCT.items() if k != "oura_sleep_efficiency_score"}
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), _night(**parts))
    assert "efficiency" in b["missing"]
    # (56×.25 + 58×.10 + 62×.15 + 61×.15 + 89×.10 + 85×.05) / 0.80 = 64.25
    assert b["score"] == 64.2


def test_one_part_alone_carries_the_score():
    rows = _night(oura_sleep_total_sleep_score=70.0)
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows)
    assert b["score"] == 70.0
    assert b["available_weight"] == 0.25


@pytest.mark.parametrize("field", list(sleep_score.OURA_PARTS.values()))
def test_every_part_is_kept_inside_zero_to_one_hundred(field):
    assert sleep_score.compute_sleep_score(date(2026, 7, 1), _night(**{field: 104.0})) == 100.0
    assert sleep_score.compute_sleep_score(date(2026, 7, 1), _night(**{field: -3.0})) == 0.0


# ─── No ring, no score ───────────────────────────────────────────────────────

def test_no_bio_rows_is_not_computed():
    assert sleep_score.compute_sleep_score(date(2026, 7, 20), []) == sleep_score.NOT_COMPUTED


def test_no_row_for_the_date_is_not_computed():
    assert sleep_score.compute_sleep_score(date(2026, 7, 25), _history()) == sleep_score.NOT_COMPUTED


def test_row_present_but_no_sleep_fields_is_not_computed():
    rows = _history() + [_row("2026-07-20")]
    assert sleep_score.compute_sleep_score(date(2026, 7, 20), rows) == sleep_score.NOT_COMPUTED


def test_a_watch_only_night_has_no_sleep_score():
    """2026-08-16, the Oura outage: a watch-only night read 100 under version 1.
    No ring reading, no Sleep Score (WP-11, approved 2026-10-13); the screen
    keeps the night's timeline and says there is no score."""
    rows = _history() + [_row("2026-07-20", sleep_duration_hours=9.5)]
    assert sleep_score.compute_sleep_score(date(2026, 7, 20), rows) == sleep_score.NOT_COMPUTED
    breakdown = sleep_score.sleep_score_breakdown(date(2026, 7, 20), rows)
    assert breakdown["score"] == sleep_score.NOT_COMPUTED
    assert breakdown["available_weight"] == 0.0
    ring = rows[:-1] + [_row("2026-07-20", sleep_duration_hours=9.5,
                             oura_sleep_total_sleep_score=97.0)]
    assert sleep_score.compute_sleep_score(date(2026, 7, 20), ring) == 97.0, (
        "with the ring's own part, the night scores")


# ─── sleep_score_breakdown (2026-07-31) ─────────────────────────────────────

def test_breakdown_score_equals_compute_sleep_score_because_both_share_one_composite():
    """The load-bearing equality. If these ever diverge, the screen is
    explaining a number the engine did not produce."""
    rows = _night(**_PARTS_27_OCT)
    assert (sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows)["score"]
            == sleep_score.compute_sleep_score(date(2026, 7, 1), rows))


def test_breakdown_lists_all_seven_contributors_in_ouras_reading_order():
    """Not weight order — the screen should read the way the user's other
    sleep app reads."""
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), _night(**_PARTS_27_OCT))
    assert [c["key"] for c in b["contributors"]] == [
        "total_sleep", "efficiency", "restfulness", "rem", "deep", "latency", "timing",
    ]


def test_all_seven_rows_are_present_even_when_only_one_contributor_has_data():
    """Absence is the most informative thing on this panel, so the UI needs a
    row for every contributor, not just the ones that scored."""
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), _night(oura_sleep_total_sleep_score=70.0))
    assert len(b["contributors"]) == 7
    assert sum(1 for c in b["contributors"] if c["score"] is not None) == 1
    assert set(b["missing"]) == {"efficiency", "restfulness", "rem", "deep", "latency", "timing"}


def test_a_missing_contributor_has_no_score_and_zero_effective_weight():
    """Zero effective weight is what makes it impossible for a missing
    contributor to contribute silently."""
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), _night(oura_sleep_total_sleep_score=70.0))
    missing = [c for c in b["contributors"] if c["key"] == "efficiency"][0]
    assert missing["score"] is None
    assert missing["effective_weight"] == 0.0
    assert missing["contribution"] is None


def test_effective_weights_sum_to_one_because_missing_weights_are_renormalised():
    b = sleep_score.sleep_score_breakdown(
        date(2026, 7, 1), _night(oura_sleep_total_sleep_score=70.0, oura_sleep_efficiency_score=80.0))
    total = sum(c["effective_weight"] for c in b["contributors"])
    assert abs(total - 1.0) < 1e-6


def test_contributions_sum_to_the_composite_within_rounding_tolerance():
    """Tolerance, not equality: the composite rounds once, the parts don't.
    The UI must present these as contributions, never as exact arithmetic."""
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), _night(**_PARTS_27_OCT))
    total = sum(c["contribution"] for c in b["contributors"] if c["contribution"] is not None)
    assert abs(total - b["score"]) < 0.5


def test_breakdown_reports_oura_s_own_night_as_the_raw_value_beside_each_part():
    """The right-hand value of each row is Oura's own, uncorrected night: hours
    from Oura's sleep period (not the blended duration), efficiency %, REM
    share, minutes to sleep."""
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), _night(**_PARTS_27_OCT))
    by = {c["key"]: c for c in b["contributors"]}
    assert by["total_sleep"]["raw"] == pytest.approx(20640.0 / 3600)
    assert by["total_sleep"]["score"] == 56.0
    assert by["efficiency"]["raw"] == 73.0
    assert by["efficiency"]["score"] == 55.0
    assert by["rem"]["raw"] == pytest.approx(4380.0 / 20640.0 * 100)
    assert by["latency"]["raw"] == pytest.approx(11.0)
    assert by["restfulness"]["raw"] == pytest.approx(750.0 / (20640.0 / 3600))
    assert b["total_seconds"] == 20640.0


def test_the_timing_row_names_the_usual_bedtime_it_is_shown_against():
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), _night(**_PARTS_27_OCT))
    by = {c["key"]: c for c in b["contributors"]}
    # Tonight's own 23:54 is inside its 28-night window (27 nights at 23:00 and
    # tonight), as readiness.sleep_baseline does: (27×660 + 714) / 28 = 661.9.
    assert by["timing"]["reference"] == 661.9
    assert by["timing"]["raw"] == pytest.approx(714.0 - 661.9)
    assert by["timing"]["reference_window"] == 28
    assert by["total_sleep"]["reference"] is None, "Oura scores Total Sleep against its own target"


def test_breakdown_with_no_rows_is_not_computed_but_still_lists_seven_rows():
    """The empty state still needs a row per contributor to render dashes
    against."""
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), [])
    assert b["score"] == sleep_score.NOT_COMPUTED
    assert len(b["contributors"]) == 7
    assert b["available_weight"] == 0.0
    assert len(b["missing"]) == 7


def test_breakdown_is_deterministic_for_the_same_inputs():
    rows = _night(**_PARTS_27_OCT)
    assert (sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows)
            == sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows))


# ─── Restfulness is Oura's own contributor (since MODEL_VERSION 2) ──────────

def _restfulness(rows):
    b = sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows)
    return next(c for c in b["contributors"] if c["key"] == "restfulness")


def test_restfulness_scores_oura_s_own_reading():
    part = _restfulness(_night(oura_sleep_restfulness=64.0))
    assert part["score"] == 64.0
    assert part["raw"] == pytest.approx(750.0 / (20640.0 / 3600)), "the count stays as the raw value"


def test_without_oura_s_reading_the_part_is_missing_not_zero():
    rows = _night(oura_sleep_total_sleep_score=70.0)
    assert _restfulness(rows)["score"] is None
    assert "restfulness" in sleep_score.sleep_score_breakdown(date(2026, 7, 1), rows)["missing"]


# ─── The model ───────────────────────────────────────────────────────────────

def test_the_model_version_says_four():
    assert sleep_score.MODEL_VERSION == 4
    for retired in ("_RESTLESS_BAND", "_REM_PCT_BAND", "_DEEP_PCT_BAND",
                    "_LATENCY_BAND", "_TIMING_BAND"):
        assert not hasattr(sleep_score, retired), f"{retired}: version 1 and 2 bands are retired"
