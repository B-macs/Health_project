"""Tests for services/sleep_movement.py — Oura+Garmin movement fusion.

Reference figures quoted here were measured against the archived real payloads
(Input_files/oura_export/raw/, Input_files/garmin_export/) on 2026-07-31:
414 Oura nights carrying movement_30_sec, 53 Garmin nights carrying
sleepMovement, 26 of them paired.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services import sleep_fusion, sleep_movement as sm


def _utc(hh, mm=0, day=27):
    return datetime(2026, 7, day, hh, mm, tzinfo=timezone.utc)


def _segments(start: datetime, levels: list[float], minutes: int = 1):
    """Contiguous Garmin sleepMovement segments, the shape real payloads use."""
    out = []
    for i, level in enumerate(levels):
        s = start + timedelta(minutes=i * minutes)
        out.append({
            "startGMT": s.strftime("%Y-%m-%dT%H:%M:%S.0"),
            "endGMT": (s + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S.0"),
            "activityLevel": level,
        })
    return out


# ─── Oura decode ────────────────────────────────────────────────────────────

def test_oura_movement_decodes_the_published_1_to_4_alphabet():
    assert sm.oura_movement("1234") == [sm.STILL, sm.RESTLESS, sm.TOSSING, sm.ACTIVE]


def test_oura_movement_maps_out_of_alphabet_digits_to_uncovered_not_a_class():
    # A stray digit must never masquerade as a real motion reading.
    assert sm.oura_movement("1509") == [sm.STILL, sm.UNCOVERED, sm.UNCOVERED, sm.UNCOVERED]


def test_oura_movement_of_empty_or_none_is_empty():
    assert sm.oura_movement(None) == []
    assert sm.oura_movement("   ") == []


# ─── Garmin parse / gap-fill ────────────────────────────────────────────────

def test_parse_garmin_movement_builds_a_regular_grid_from_contiguous_segments():
    parsed = sm.parse_garmin_movement(_segments(_utc(22), [1.0, 2.0, 3.0]))
    assert parsed["levels"] == [1.0, 2.0, 3.0]
    assert parsed["contiguous"] is True
    assert parsed["gap_slots"] == 0
    assert parsed["start_utc"] == _utc(22)


def test_parse_garmin_movement_gap_fills_so_later_values_keep_their_true_position():
    """The 2026-05-27 failure mode: a real 4-minute hole in sleepMovement.

    Packing the surviving segments end-to-end would shift everything after the
    gap earlier by the gap's width and produce a plausible, silently wrong
    series. The hole must be preserved as None.
    """
    segs = _segments(_utc(22), [1.0, 2.0]) + _segments(_utc(22, 6), [9.0])
    parsed = sm.parse_garmin_movement(segs)
    assert parsed["levels"] == [1.0, 2.0, None, None, None, None, 9.0]
    assert parsed["contiguous"] is False
    assert parsed["gap_slots"] == 4
    # The value after the gap sits at its true minute offset, not at index 2.
    assert parsed["levels"].index(9.0) == 6


def test_parse_garmin_movement_of_nothing_is_empty_and_contiguous():
    for empty in (None, [], [{"startGMT": None, "endGMT": None, "activityLevel": None}]):
        parsed = sm.parse_garmin_movement(empty)
        assert parsed["levels"] == []
        assert parsed["start_utc"] is None


def test_parse_garmin_movement_ignores_unparseable_segments_without_losing_the_night():
    segs = _segments(_utc(22), [1.0, 2.0])
    segs.append({"startGMT": "not-a-time", "endGMT": "also-not", "activityLevel": "x"})
    assert sm.parse_garmin_movement(segs)["levels"] == [1.0, 2.0]


# ─── Encoding ───────────────────────────────────────────────────────────────

def test_encode_levels_roundtrips_to_two_decimal_places_preserving_gaps():
    levels = [5.67199759213915, None, 0.0, 8.131]
    decoded = sm.decode_levels(sm.encode_levels(levels))
    assert decoded == [5.67, None, 0.0, 8.13]


def test_encode_levels_stays_far_inside_the_sheets_cell_limit():
    """Raw sleepMovement is ~84k chars a night, over Sheets' 50k cell limit.
    The compact form must have real headroom, not just barely fit."""
    encoded = sm.encode_levels([1.23] * 720)   # a 12-hour night, per minute
    assert len(encoded) < 5000


def test_decode_levels_of_empty_is_empty():
    assert sm.decode_levels("") == []
    assert sm.decode_levels(None) == []


# ─── Calibration ────────────────────────────────────────────────────────────

def test_quantile_cutpoints_reproduce_the_oura_class_distribution():
    """The whole point of quantile mapping: after it, Garmin's four-class
    marginal matches Oura's. Verified on real data to within 0.01pp."""
    garmin = [float(i) for i in range(1000)]
    oura = [sm.STILL] * 700 + [sm.RESTLESS] * 200 + [sm.TOSSING] * 90 + [sm.ACTIVE] * 10
    cuts = sm.quantile_cutpoints(garmin, oura, nights=26)

    mapped = [sm.garmin_class(v, cuts) for v in garmin]
    for cls, expected in ((sm.STILL, 700), (sm.RESTLESS, 200),
                          (sm.TOSSING, 90), (sm.ACTIVE, 10)):
        assert abs(mapped.count(cls) - expected) <= 5


def test_quantile_cutpoints_returns_none_below_the_calibration_floor():
    """Missing calibration must read as missing, never as a fabricated
    default — same discipline as readiness.sleep_baseline under 7 nights."""
    garmin = [float(i) for i in range(1000)]
    # All four classes present, so ONLY the night count can cause a refusal —
    # otherwise the distinctness guard fires and the test proves nothing.
    oura = [sm.STILL] * 700 + [sm.RESTLESS] * 200 + [sm.TOSSING] * 90 + [sm.ACTIVE] * 10
    assert sm.quantile_cutpoints(garmin, oura, nights=sm.MIN_CALIBRATION_NIGHTS - 1) is None
    assert sm.quantile_cutpoints(garmin, oura, nights=sm.MIN_CALIBRATION_NIGHTS) is not None


def test_quantile_cutpoints_returns_none_when_boundaries_would_not_be_distinct():
    """A degenerate Oura sample makes a class unreachable; refuse rather than
    silently collapse the alphabet."""
    assert sm.quantile_cutpoints([1.0] * 100, [sm.STILL] * 100, nights=26) is None


def test_quantile_cutpoints_returns_none_with_no_usable_sample():
    assert sm.quantile_cutpoints([], [sm.STILL], nights=26) is None
    assert sm.quantile_cutpoints([1.0, 2.0], [], nights=26) is None


def test_garmin_class_is_uncovered_without_calibration_or_value():
    assert sm.garmin_class(3.0, None) == sm.UNCOVERED
    assert sm.garmin_class(None, (1.0, 2.0, 3.0)) == sm.UNCOVERED


def test_garmin_class_bands_are_half_open_upward():
    cuts = (2.0, 5.0, 8.0)
    assert sm.garmin_class(1.99, cuts) == sm.STILL
    assert sm.garmin_class(2.0, cuts) == sm.RESTLESS
    assert sm.garmin_class(4.99, cuts) == sm.RESTLESS
    assert sm.garmin_class(5.0, cuts) == sm.TOSSING
    assert sm.garmin_class(8.0, cuts) == sm.ACTIVE


# ─── Grid alignment ─────────────────────────────────────────────────────────

def test_garmin_slots_holds_each_minute_across_both_thirty_second_slots():
    parsed = sm.parse_garmin_movement(_segments(_utc(22), [1.0, 6.0]))
    slots, _ = sm.garmin_slots(parsed, (2.0, 5.0, 8.0), _utc(22), 4)
    assert slots == [sm.STILL, sm.STILL, sm.TOSSING, sm.TOSSING]


def test_garmin_slots_leaves_uncovered_minutes_uncovered_never_still():
    """Garmin's movement window is WIDER than the sleep window on real nights,
    and can also fall short. Reporting absence of data as absence of motion
    would feed the staging rules a confident "the body was still"."""
    parsed = sm.parse_garmin_movement(_segments(_utc(22), [1.0]))
    slots, diag = sm.garmin_slots(parsed, (2.0, 5.0, 8.0), _utc(22), 6)
    assert slots == [sm.STILL, sm.STILL, sm.UNCOVERED, sm.UNCOVERED,
                     sm.UNCOVERED, sm.UNCOVERED]
    assert diag["gap_slots"] == 4


def test_garmin_slots_trims_data_falling_outside_the_window():
    parsed = sm.parse_garmin_movement(_segments(_utc(21), [1.0, 1.0, 1.0]))
    slots, diag = sm.garmin_slots(parsed, (2.0, 5.0, 8.0), _utc(21, 2), 2)
    assert len(slots) == 2
    assert diag["outside_window_slots"] == 4


def test_garmin_slots_reports_uncalibrated_and_yields_no_classes():
    parsed = sm.parse_garmin_movement(_segments(_utc(22), [1.0, 2.0]))
    slots, diag = sm.garmin_slots(parsed, None, _utc(22), 4)
    assert diag["calibrated"] is False
    assert set(slots) == {sm.UNCOVERED}


# ─── Weighting ──────────────────────────────────────────────────────────────

def test_weights_switch_on_the_louder_device_not_on_oura_alone():
    assert sm.weights_for(sm.STILL, sm.STILL) is sm.LOW_AMPLITUDE_WEIGHTS
    assert sm.weights_for(sm.RESTLESS, sm.RESTLESS) is sm.LOW_AMPLITUDE_WEIGHTS
    # Either device seeing a whole-body event puts the slot in Garmin's regime.
    assert sm.weights_for(sm.STILL, sm.TOSSING) is sm.HIGH_AMPLITUDE_WEIGHTS
    assert sm.weights_for(sm.TOSSING, sm.STILL) is sm.HIGH_AMPLITUDE_WEIGHTS


def test_both_weight_pairs_sum_to_one_so_fusion_stays_within_bounds():
    for weights in (sm.LOW_AMPLITUDE_WEIGHTS, sm.HIGH_AMPLITUDE_WEIGHTS):
        assert sum(weights.values()) == pytest.approx(1.0)


def test_a_finger_only_spike_is_damped_by_the_watch():
    """The ring can reach the top class from a hand twitch that moved no part
    of the body; at high amplitude the watch is the better witness."""
    assert sm.fuse_slot(sm.ACTIVE, sm.STILL) < sm.ACTIVE


def test_a_watch_confirmed_postural_shift_survives_a_quiet_ring():
    assert sm.fuse_slot(sm.STILL, sm.ACTIVE) >= sm.TOSSING


def test_ring_micro_motion_is_preserved_at_low_amplitude():
    """Below the postural threshold the finger resolves motion under the
    wrist's noise floor, so the ring must not be averaged away."""
    assert sm.fuse_slot(sm.RESTLESS, sm.STILL) == sm.RESTLESS


# ─── Fusion contracts ───────────────────────────────────────────────────────

def test_fusion_never_invents_motion_neither_device_saw():
    """The movement analogue of sleep_fusion's "never manufacture sleep": a
    weighted mean of two integers can only land between them."""
    for o in sm.CLASSES:
        for g in sm.CLASSES:
            assert min(o, g) <= sm.fuse_slot(o, g) <= max(o, g)


def test_fusion_is_bit_identical_to_oura_when_garmin_is_absent():
    """Mirrors sleep_fusion.fuse's contract: a night without the other device
    behaves exactly as it did before this module existed."""
    oura = [sm.STILL, sm.RESTLESS, sm.ACTIVE, sm.TOSSING]
    for absent in (None, [], [sm.UNCOVERED] * 4):
        fused, source = sm.fuse_movement(oura, absent)
        assert fused == oura
        assert source == sleep_fusion.SOURCE_OURA_ONLY


def test_fusion_falls_back_to_garmin_when_oura_is_absent():
    garmin = [sm.STILL, sm.TOSSING]
    fused, source = sm.fuse_movement([], garmin)
    assert fused == garmin
    assert source == sleep_fusion.SOURCE_GARMIN_ONLY


def test_fusion_of_nothing_reports_no_data():
    assert sm.fuse_movement([], None) == ([], sleep_fusion.SOURCE_NONE)


def test_fusion_uses_sleep_fusions_own_source_vocabulary():
    """So one provenance-naming rule covers both the hypnogram and the
    movement strip in the UI."""
    _, source = sm.fuse_movement([sm.STILL], [sm.STILL])
    assert source == sleep_fusion.SOURCE_FUSED


def test_fusion_pads_a_short_garmin_series_rather_than_truncating_the_night():
    fused, _ = sm.fuse_movement([sm.RESTLESS] * 4, [sm.RESTLESS] * 2)
    assert len(fused) == 4


def test_fusion_of_uncovered_slot_on_both_devices_stays_uncovered():
    fused, _ = sm.fuse_movement([sm.UNCOVERED, sm.STILL], [sm.UNCOVERED, sm.STILL])
    assert fused[0] == sm.UNCOVERED


# ─── 30s -> 60s reduction ───────────────────────────────────────────────────

def test_to_minutes_reduces_by_max_never_mean():
    """A minute holding one 30-second burst of thrashing IS a minute in which
    the body moved; averaging would dilute exactly the events the staging
    rules look for."""
    assert sm.to_minutes([sm.STILL, sm.ACTIVE]) == [sm.ACTIVE]
    assert sm.to_minutes([sm.STILL, sm.STILL, sm.RESTLESS, sm.STILL]) == [sm.STILL, sm.RESTLESS]


def test_to_minutes_keeps_a_trailing_odd_slot():
    assert sm.to_minutes([sm.STILL, sm.STILL, sm.TOSSING]) == [sm.STILL, sm.TOSSING]


def test_to_minutes_of_empty_is_empty():
    assert sm.to_minutes([]) == []


# ─── Derived measures ───────────────────────────────────────────────────────

def test_class_totals_includes_every_class_even_at_zero():
    totals = sm.class_totals([sm.STILL, sm.STILL])
    assert totals[sm.STILL] == 2
    assert totals[sm.ACTIVE] == 0
    assert set(totals) == {*sm.CLASSES, sm.UNCOVERED}


def test_position_shifts_finds_runs_at_or_above_the_postural_threshold():
    slots = [sm.STILL, sm.TOSSING, sm.ACTIVE, sm.STILL, sm.STILL, sm.ACTIVE]
    assert sm.position_shifts(slots) == [(1, 2), (5, 1)]


def test_still_runs_respects_a_minimum_length():
    slots = [sm.STILL, sm.RESTLESS, sm.STILL, sm.STILL, sm.STILL]
    assert sm.still_runs(slots, min_slots=3) == [(2, 3)]
    assert sm.still_runs(slots, min_slots=1) == [(0, 1), (2, 3)]


def test_movement_summary_reports_none_mean_rather_than_zero_when_uncovered():
    """Zero motion and no measurement are different claims."""
    summary = sm.movement_summary([sm.UNCOVERED] * 4, sleep_fusion.SOURCE_NONE)
    assert summary["movement_mean_class"] is None
    assert summary["movement_covered_slots"] == 0


def test_movement_summary_counts_each_class_and_the_shifts():
    slots = [sm.STILL, sm.STILL, sm.RESTLESS, sm.TOSSING, sm.ACTIVE]
    summary = sm.movement_summary(slots, sleep_fusion.SOURCE_FUSED)
    assert summary["movement_still_slots"] == 2
    assert summary["movement_position_shifts"] == 1      # TOSSING+ACTIVE is one run
    assert summary["movement_source"] == sleep_fusion.SOURCE_FUSED


# ─── The window-alignment trap ──────────────────────────────────────────────

def test_garmin_values_on_grid_keeps_raw_floats_and_marks_gaps_none():
    """Calibration needs the RAW values on the fusion grid — mapping to
    classes first would need the cut points this is used to derive."""
    parsed = sm.parse_garmin_movement(_segments(_utc(22), [1.5, 7.25]))
    values, diag = sm.garmin_values_on_grid(parsed, _utc(22), 6)
    assert values == [1.5, 1.5, 7.25, 7.25, None, None]
    assert diag["covered_slots"] == 4
    assert diag["gap_slots"] == 2


def test_calibration_must_use_the_aligned_window_not_the_raw_series():
    """Regression: Garmin's movement series is ~2.7x wider than Oura's sleep
    period, covering settling-down time that is far more active than sleep.

    Fitting cut points on the RAW series while matching them to Oura's
    sleep-period-only classes compares two different spans of the night. On
    real data that pushed every boundary too high and mapped one night to
    94.7% STILL with zero postural shifts — physiologically implausible.
    """
    # 30 minutes of high pre-sleep movement, then 60 minutes of sleep whose
    # motion ramps across the whole in-sleep range.
    pre_sleep = [10.0 + i * 0.1 for i in range(30)]
    asleep = [i * 0.05 for i in range(60)]
    parsed = sm.parse_garmin_movement(_segments(_utc(21, 30), pre_sleep + asleep))
    sleep_window_start = _utc(22)                       # sleep starts 30 min in
    # Oura's own sleep-period distribution, roughly the real 77/18/4/0.2 shape.
    oura = [sm.STILL] * 60 + [sm.RESTLESS] * 40 + [sm.TOSSING] * 16 + [sm.ACTIVE] * 4

    aligned, _ = sm.garmin_values_on_grid(parsed, sleep_window_start, len(oura))
    in_window = [v for v in aligned if v is not None]
    assert max(in_window) < 10.0, "pre-sleep activity must be excluded"

    naive = [v for v in parsed["levels"] if v is not None]
    naive_cuts = sm.quantile_cutpoints(naive, oura, nights=26)
    aligned_cuts = sm.quantile_cutpoints(in_window, oura, nights=26)

    # Every boundary is dragged upward by movement that is not sleep at all.
    assert all(n > a for n, a in zip(naive_cuts, aligned_cuts))

    # The consequence, and the reason this is a bug rather than a nuance:
    # genuine in-sleep motion collapses into STILL. On real data the naive fit
    # produced a night that was 94.7% STILL with zero postural shifts.
    def moving_fraction(cuts):
        return sum(1 for v in in_window if sm.garmin_class(v, cuts) > sm.STILL) / len(in_window)

    # A ratio, not an absolute: how badly the naive fit understates depends on
    # how much pre-sleep time the series happens to carry. The direction and
    # the scale of the error are what must hold. On the real 2026-07-01 night
    # the naive fit gave 5.3% moving where the aligned fit gives ~24%.
    assert moving_fraction(naive_cuts) < moving_fraction(aligned_cuts) * 0.75


def test_garmin_slots_shares_one_alignment_path_with_the_calibration():
    """garmin_slots must be garmin_values_on_grid + the mapping, or the
    boundaries get fitted on different slots than they are applied to."""
    parsed = sm.parse_garmin_movement(_segments(_utc(22), [1.0, 6.0, 3.0]))
    values, _ = sm.garmin_values_on_grid(parsed, _utc(22), 6)
    slots, _ = sm.garmin_slots(parsed, (2.0, 5.0, 8.0), _utc(22), 6)
    assert slots == [sm.garmin_class(v, (2.0, 5.0, 8.0)) for v in values]
