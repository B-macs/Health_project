"""
Tests for services/sleep_fusion.py — merging Oura and Garmin sleep stages
into one master hypnogram.

Pure module, no I/O, so everything here is direct. The real-payload fixtures
below are the night of 2026-07-28, captured from both devices: Garmin's 37
sleepLevels segments and Oura sleep period ac08e613's 30-second hypnogram.
They are pinned rather than synthesised because the activityLevel->stage
mapping is the one assumption in this module that no amount of internal
consistency can validate — only Garmin's own totals can.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services import sleep_fusion as sf

D, L, R, A, U = sf.DEEP, sf.LIGHT, sf.REM, sf.AWAKE, sf.UNCOVERED

_EPOCH = datetime(2026, 7, 27, 19, 38, tzinfo=timezone.utc)


# ─── helpers ────────────────────────────────────────────────────────────────

def _arr(*runs: tuple[int, int]) -> list[int]:
    """[(stage, minutes), ...] -> a flat minute array."""
    out: list[int] = []
    for stage, minutes in runs:
        out.extend([stage] * minutes)
    return out


def _oura(*runs: tuple[int, int]) -> str:
    """[(stage, minutes), ...] -> a 30-second digit string (2 chars/minute)."""
    return "".join(str(stage) * (minutes * 2) for stage, minutes in runs)


_LEVEL_FOR_STAGE = {D: 0.0, L: 1.0, R: 2.0, A: 3.0}


def _garmin(*runs: tuple[int, int], start: datetime | None = None) -> list[dict]:
    """[(stage, minutes), ...] -> sleepLevels segments anchored at `start`."""
    cursor = start or _EPOCH
    segments = []
    for stage, minutes in runs:
        end = cursor + timedelta(minutes=minutes)
        segments.append({
            "startGMT": cursor.strftime("%Y-%m-%dT%H:%M:%S.0"),
            "endGMT": end.strftime("%Y-%m-%dT%H:%M:%S.0"),
            "activityLevel": _LEVEL_FOR_STAGE[stage],
        })
        cursor = end
    return segments


# ─── real payloads — night of 2026-07-28 ────────────────────────────────────

_REAL_GARMIN_SLEEP_LEVELS = [
    {"startGMT": s, "endGMT": e, "activityLevel": lvl} for s, e, lvl in [
        ("2026-07-27T19:38:00.0", "2026-07-27T20:07:00.0", 1.0),
        ("2026-07-27T20:07:00.0", "2026-07-27T20:28:00.0", 0.0),
        ("2026-07-27T20:28:00.0", "2026-07-27T20:42:00.0", 1.0),
        ("2026-07-27T20:42:00.0", "2026-07-27T20:52:00.0", 2.0),
        ("2026-07-27T20:52:00.0", "2026-07-27T21:07:00.0", 1.0),
        ("2026-07-27T21:07:00.0", "2026-07-27T21:08:00.0", 0.0),
        ("2026-07-27T21:08:00.0", "2026-07-27T21:09:00.0", 3.0),
        ("2026-07-27T21:09:00.0", "2026-07-27T21:14:00.0", 0.0),
        ("2026-07-27T21:14:00.0", "2026-07-27T21:47:00.0", 1.0),
        ("2026-07-27T21:47:00.0", "2026-07-27T22:18:00.0", 2.0),
        ("2026-07-27T22:18:00.0", "2026-07-27T22:22:00.0", 1.0),
        ("2026-07-27T22:22:00.0", "2026-07-27T22:26:00.0", 2.0),
        ("2026-07-27T22:26:00.0", "2026-07-27T23:05:00.0", 1.0),
        ("2026-07-27T23:05:00.0", "2026-07-27T23:06:00.0", 3.0),
        ("2026-07-27T23:06:00.0", "2026-07-27T23:15:00.0", 1.0),
        ("2026-07-27T23:15:00.0", "2026-07-27T23:41:00.0", 2.0),
        ("2026-07-27T23:41:00.0", "2026-07-27T23:48:00.0", 1.0),
        ("2026-07-27T23:48:00.0", "2026-07-28T00:02:00.0", 2.0),
        ("2026-07-28T00:02:00.0", "2026-07-28T01:25:00.0", 1.0),
        ("2026-07-28T01:25:00.0", "2026-07-28T01:30:00.0", 2.0),
        ("2026-07-28T01:30:00.0", "2026-07-28T01:36:00.0", 1.0),
        ("2026-07-28T01:36:00.0", "2026-07-28T01:42:00.0", 2.0),
        ("2026-07-28T01:42:00.0", "2026-07-28T02:05:00.0", 1.0),
        ("2026-07-28T02:05:00.0", "2026-07-28T02:08:00.0", 3.0),
        ("2026-07-28T02:08:00.0", "2026-07-28T02:20:00.0", 1.0),
        ("2026-07-28T02:20:00.0", "2026-07-28T02:33:00.0", 2.0),
        ("2026-07-28T02:33:00.0", "2026-07-28T02:38:00.0", 1.0),
        ("2026-07-28T02:38:00.0", "2026-07-28T02:40:00.0", 2.0),
        ("2026-07-28T02:40:00.0", "2026-07-28T02:42:00.0", 1.0),
        ("2026-07-28T02:42:00.0", "2026-07-28T02:55:00.0", 2.0),
        ("2026-07-28T02:55:00.0", "2026-07-28T04:11:00.0", 1.0),
        ("2026-07-28T04:11:00.0", "2026-07-28T04:36:00.0", 2.0),
        ("2026-07-28T04:36:00.0", "2026-07-28T04:43:00.0", 3.0),
        ("2026-07-28T04:43:00.0", "2026-07-28T04:55:00.0", 1.0),
        ("2026-07-28T04:55:00.0", "2026-07-28T04:56:00.0", 2.0),
        ("2026-07-28T04:56:00.0", "2026-07-28T05:05:00.0", 3.0),
        ("2026-07-28T05:05:00.0", "2026-07-28T05:26:00.0", 1.0),
    ]
]
# Garmin's own dailySleepDTO totals for that same night.
_REAL_GARMIN_DTO_SECONDS = {D: 1620, L: 23340, R: 9000, A: 1260}
_REAL_OURA_BEDTIME_START = "2026-07-27T21:33:29.000+02:00"


# ─── the mapping — the only externally-verifiable assumption here ───────────

def test_the_activity_level_mapping_reproduces_garmins_own_per_stage_totals():
    """The single load-bearing test in this file. GARMIN_LEVEL_TO_STAGE was
    derived by inspection; nothing internal to this module can confirm it.
    Summing each level's segment durations and matching dailySleepDTO's own
    deep/light/rem/awake seconds is the only real evidence it is right."""
    derived: dict[int, float] = {D: 0.0, L: 0.0, R: 0.0, A: 0.0}
    for seg in _REAL_GARMIN_SLEEP_LEVELS:
        stage = sf.GARMIN_LEVEL_TO_STAGE[seg["activityLevel"]]
        start = sf.utc_from_gmt_string(seg["startGMT"])
        end = sf.utc_from_gmt_string(seg["endGMT"])
        derived[stage] += (end - start).total_seconds()

    for stage, expected in _REAL_GARMIN_DTO_SECONDS.items():
        # 180s tolerance: segment bounds are minute-rounded. A swapped mapping
        # would be out by hundreds of minutes, not three.
        assert abs(derived[stage] - expected) <= 180, sf.STAGE_LABELS[stage]


def test_deep_and_rem_map_exactly_which_is_what_rules_out_a_swapped_mapping():
    """Deep and REM reconcile to the second on the real night. If 0.0 and 2.0
    were transposed these would be out by 123 minutes."""
    derived: dict[int, float] = {D: 0.0, R: 0.0}
    for seg in _REAL_GARMIN_SLEEP_LEVELS:
        stage = sf.GARMIN_LEVEL_TO_STAGE[seg["activityLevel"]]
        if stage in derived:
            derived[stage] += (sf.utc_from_gmt_string(seg["endGMT"])
                               - sf.utc_from_gmt_string(seg["startGMT"])).total_seconds()
    assert derived[D] == _REAL_GARMIN_DTO_SECONDS[D]
    assert derived[R] == _REAL_GARMIN_DTO_SECONDS[R]


# ─── timezone normalisation ─────────────────────────────────────────────────

def test_garmin_gmt_strings_and_oura_offset_strings_resolve_to_the_same_instant():
    """Garmin's naive "GMT" string and Oura's +02:00 ISO describe the same
    wall-clock moment differently. Both must land on one UTC instant or the
    two series are silently offset by the local UTC offset."""
    garmin_utc = sf.utc_from_gmt_string("2026-07-27T19:33:29.0")
    oura_utc = sf.utc_from_iso_offset("2026-07-27T21:33:29.000+02:00")
    assert garmin_utc == oura_utc


def test_both_converters_return_aware_datetimes_because_overlap_math_mixes_them():
    """hr_matching.overlap_seconds compares the two directly; a naive value
    meeting an aware one raises TypeError rather than being wrong quietly."""
    assert sf.utc_from_gmt_string("2026-07-27T19:38:00.0").tzinfo is not None
    assert sf.utc_from_iso_offset(_REAL_OURA_BEDTIME_START).tzinfo is not None


def test_overlap_seconds_accepts_the_normalised_pair_without_raising():
    a = sf.utc_from_gmt_string("2026-07-27T19:38:00.0")
    b = sf.utc_from_iso_offset(_REAL_OURA_BEDTIME_START)
    from services import hr_matching
    assert hr_matching.overlap_seconds(a, a + timedelta(hours=1), b, b + timedelta(hours=1)) > 0


def test_utc_offset_is_derived_from_garmins_gmt_and_local_epoch_pair():
    """Real values for 2026-07-28: +120 minutes (CEST)."""
    assert sf.utc_offset_minutes(1785181140000, 1785188340000) == 120


def test_utc_offset_is_none_rather_than_zero_when_garmin_omits_the_pair():
    """Zero would be indistinguishable from a real UTC night."""
    assert sf.utc_offset_minutes(None, 1785188340000) is None


def test_a_whole_day_offset_window_scores_no_overlap_so_it_can_be_refused():
    """Oura keys a night by wake date and Garmin by its own. A silent
    one-day mismatch would produce a plausible but entirely wrong hypnogram,
    so the overlap gate has to see it as zero."""
    start = _EPOCH
    frac = sf.window_overlap_fraction(
        start, start + timedelta(hours=8),
        start + timedelta(days=1), start + timedelta(days=1, hours=8))
    assert frac == 0.0


def test_the_real_paired_night_overlaps_almost_entirely():
    start = sf.utc_from_iso_offset(_REAL_OURA_BEDTIME_START)
    frac = sf.window_overlap_fraction(
        start, start + timedelta(minutes=529),
        sf.utc_from_gmt_string(_REAL_GARMIN_SLEEP_LEVELS[0]["startGMT"]),
        sf.utc_from_gmt_string(_REAL_GARMIN_SLEEP_LEVELS[-1]["endGMT"]))
    assert frac > sf.MIN_WINDOW_OVERLAP_FRACTION
    assert frac > 0.98


# ─── oura_minutes — the 30-second downsample ────────────────────────────────

def test_oura_minutes_collapses_each_pair_of_thirty_second_codes_to_one_minute():
    assert sf.oura_minutes("11112222") == [D, D, L, L]


def test_a_split_minute_resolves_to_awake_because_resampling_must_not_invent_sleep():
    """The conservative tie-break is what makes the phantom-wake figure
    attributable: every awake minute removed is removed by a NAMED rule, not
    quietly lost in resampling."""
    assert sf.oura_minutes("42") == [A]
    assert sf.oura_minutes("24") == [A]


def test_a_split_minute_between_two_sleep_stages_prefers_the_deeper_one():
    assert sf.oura_minutes("12") == [D]
    assert sf.oura_minutes("23") == [R]


def test_an_odd_trailing_code_becomes_its_own_final_minute_rather_than_being_dropped():
    """The real 2026-07-28 hypnogram is 1057 chars — odd. Dropping the tail
    would silently shorten the night."""
    assert sf.oura_minutes("1111" + "2") == [D, D, L]


def test_oura_minutes_of_the_real_night_is_half_the_string_rounded_up():
    real_len = 1057
    assert len(sf.oura_minutes("1" * real_len)) == 529


def test_oura_minutes_is_empty_for_a_night_with_no_hypnogram():
    assert sf.oura_minutes("") == []
    assert sf.oura_minutes(None) == []


# ─── garmin_minutes — resampling variable segments onto the grid ────────────

def test_garmin_segments_resample_onto_the_fixed_minute_grid():
    segments = _garmin((L, 3), (D, 2))
    minutes, _ = sf.garmin_minutes(segments, _EPOCH, 5)
    assert minutes == [L, L, L, D, D]


def test_a_gap_between_segments_is_uncovered_not_awake():
    """Garmin sometimes carries wakefulness in sleepMovement rather than a
    sleepLevels segment. Calling a gap Awake would inject phantom wake from
    the very device being used to remove it."""
    segments = _garmin((L, 2)) + _garmin((L, 2), start=_EPOCH + timedelta(minutes=5))
    minutes, diag = sf.garmin_minutes(segments, _EPOCH, 7)
    assert minutes == [L, L, U, U, U, L, L]
    assert diag["gap_minutes"] == 3


def test_minutes_before_the_oura_window_are_counted_as_outside_not_folded_in():
    segments = _garmin((D, 10), start=_EPOCH - timedelta(minutes=5))
    minutes, diag = sf.garmin_minutes(segments, _EPOCH, 5)
    assert minutes == [D] * 5
    assert diag["outside_window_minutes"] == 5


def test_a_minute_split_across_two_segments_takes_the_dominant_one():
    segments = [
        {"startGMT": _EPOCH.strftime("%Y-%m-%dT%H:%M:%S.0"),
         "endGMT": (_EPOCH + timedelta(seconds=40)).strftime("%Y-%m-%dT%H:%M:%S.0"),
         "activityLevel": 1.0},
        {"startGMT": (_EPOCH + timedelta(seconds=40)).strftime("%Y-%m-%dT%H:%M:%S.0"),
         "endGMT": (_EPOCH + timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%S.0"),
         "activityLevel": 0.0},
    ]
    minutes, _ = sf.garmin_minutes(segments, _EPOCH, 1)
    assert minutes == [L]


def test_an_unknown_activity_level_is_skipped_rather_than_guessed():
    """Garmin's field names have shifted before. A new level code must leave
    the minute uncovered, not be coerced into a stage."""
    segments = [{"startGMT": _EPOCH.strftime("%Y-%m-%dT%H:%M:%S.0"),
                 "endGMT": (_EPOCH + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S.0"),
                 "activityLevel": 9.0}]
    minutes, _ = sf.garmin_minutes(segments, _EPOCH, 1)
    assert minutes == [U]


def test_the_real_night_resamples_to_near_complete_coverage():
    window_start = sf.utc_from_iso_offset(_REAL_OURA_BEDTIME_START)
    minutes, diag = sf.garmin_minutes(_REAL_GARMIN_SLEEP_LEVELS, window_start, 529)
    assert diag["segment_count"] == 37
    assert diag["covered_minutes"] == 525
    assert diag["gap_minutes"] == 4          # Oura in bed ~5 min before Garmin starts


# ─── rule 1 — agreement ─────────────────────────────────────────────────────

def test_when_both_devices_agree_that_stage_is_taken_unchanged():
    oura = _arr((D, 2), (L, 2), (R, 2), (A, 2))
    master, reasons, source = sf.fuse(oura, list(oura))
    assert master == oura
    assert set(reasons) == {sf.REASON_AGREE}
    assert source == sf.SOURCE_FUSED


# ─── rule 2 — over-reported wake ────────────────────────────────────────────

def test_oura_awake_with_garmin_asleep_and_no_nearby_garmin_wake_becomes_light():
    """The hypermobility filter: Garmin's wrist sensor needs larger rotational
    motion, so its silence here reads as joint repositioning, not waking."""
    oura = _arr((L, 3), (A, 1), (L, 3))
    garmin = _arr((L, 7))
    master, reasons, _ = sf.fuse(oura, garmin)
    assert master[3] == L
    assert reasons[3] == sf.REASON_REPOSITION


def test_oura_awake_stays_awake_when_garmin_flags_wake_within_the_radius():
    """Garmin's Awake is the strict filter — when it corroborates, this is a
    real awakening and must survive."""
    oura = _arr((L, 3), (A, 1), (L, 5))
    garmin = _arr((L, 6), (A, 1), (L, 2))     # Garmin awake at index 6, i.e. +3
    master, reasons, _ = sf.fuse(oura, garmin)
    assert master[3] == A
    assert reasons[3] == sf.REASON_WAKE_CONFIRMED


def test_a_garmin_wake_just_outside_the_radius_does_not_corroborate():
    oura = _arr((L, 3), (A, 1), (L, 6))
    garmin = _arr((L, 7), (A, 1), (L, 2))     # index 7, i.e. +4 — outside +/-3
    master, reasons, _ = sf.fuse(oura, garmin)
    assert master[3] == L
    assert reasons[3] == sf.REASON_REPOSITION


def test_garmin_awake_with_oura_asleep_becomes_light_as_isolated_limb_movement():
    oura = _arr((R, 5))
    garmin = _arr((L, 2), (A, 1), (L, 2))
    master, reasons, _ = sf.fuse(oura, garmin)
    assert master[2] == L
    assert reasons[2] == sf.REASON_GARMIN_WAKE


def test_both_awake_stays_awake():
    master, reasons, _ = sf.fuse(_arr((A, 3)), _arr((A, 3)))
    assert master == [A, A, A]
    assert reasons == [sf.REASON_AGREE] * 3


# ─── rule 3 — both asleep, stages disagree ──────────────────────────────────

def test_oura_rem_beats_garmin_light_because_garmin_mislabels_rem_as_light():
    master, reasons, _ = sf.fuse(_arr((R, 4)), _arr((L, 4)))
    assert master == [R] * 4
    assert set(reasons) == {sf.REASON_OURA_WINS}


def test_oura_deep_beats_garmin_light_in_the_first_half_of_the_night():
    oura = _arr((D, 10), (L, 40))
    master, _, _ = sf.fuse(oura, _arr((L, 50)))
    assert master[:10] == [D] * 10


def test_oura_light_beats_garmin_deep_because_oura_is_the_stage_authority():
    """Not covered by the stated rules; resolved by the same principle the
    stated half uses — Oura wins whenever both devices agree you are asleep."""
    master, reasons, _ = sf.fuse(_arr((L, 4)), _arr((D, 4)))
    assert master == [L] * 4
    assert set(reasons) == {sf.REASON_OURA_WINS}


def test_oura_rem_beats_garmin_deep():
    master, _, _ = sf.fuse(_arr((R, 4)), _arr((D, 4)))
    assert master == [R] * 4


def test_oura_deep_beats_garmin_rem_when_the_run_is_plausible():
    master, _, _ = sf.fuse(_arr((D, 4)), _arr((R, 4)))
    assert master == [D] * 4


def test_an_over_long_deep_run_in_the_second_half_keeps_its_first_forty_five_minutes():
    """Rule 3's override is excess-only: a 60-minute run defers 15 minutes,
    not all 60. Flipping the whole run would create a cliff where one extra
    minute costs an hour of deep sleep."""
    oura = _arr((L, 100), (D, 60))
    garmin = _arr((L, 160))
    master, reasons, _ = sf.fuse(oura, garmin)
    deep_run = master[100:160]
    assert deep_run[:sf.DEEP_RUN_PLAUSIBLE_MINUTES] == [D] * sf.DEEP_RUN_PLAUSIBLE_MINUTES
    assert deep_run[sf.DEEP_RUN_PLAUSIBLE_MINUTES:] == [L] * 15
    assert reasons[100 + sf.DEEP_RUN_PLAUSIBLE_MINUTES] == sf.REASON_DEEP_EXCESS


def test_the_same_over_long_run_in_the_first_half_stays_deep_throughout():
    """Slow-wave sleep is expected to be long early in the night, so length
    alone is not suspicious there."""
    oura = _arr((D, 60), (L, 100))
    master, _, _ = sf.fuse(oura, _arr((L, 160)))
    assert master[:60] == [D] * 60


def test_a_deep_run_at_exactly_the_threshold_is_left_alone():
    """Strictly longer than DEEP_RUN_PLAUSIBLE_MINUTES, not equal to it."""
    oura = _arr((L, 100), (D, sf.DEEP_RUN_PLAUSIBLE_MINUTES))
    master, _, _ = sf.fuse(oura, _arr((L, 145)))
    assert master[100:] == [D] * sf.DEEP_RUN_PLAUSIBLE_MINUTES


def test_the_deep_override_does_not_fire_when_garmin_also_says_deep():
    oura = _arr((L, 100), (D, 60))
    master, _, _ = sf.fuse(oura, _arr((L, 100), (D, 60)))
    assert master[100:] == [D] * 60


# ─── rule 4 — temporal smoothing ────────────────────────────────────────────

def test_an_isolated_one_minute_awake_surrounded_by_sleep_on_both_devices_is_smoothed():
    oura = _arr((L, 2), (A, 1), (L, 2))
    garmin = _arr((L, 2), (A, 1), (L, 2))     # both awake -> survives rules 1-3
    master, reasons, _ = sf.fuse(oura, garmin)
    assert master[2] == L
    assert reasons[2] == sf.REASON_SMOOTHED


def test_a_garmin_corroborated_wake_is_exempt_from_smoothing():
    """Rules 2 and 4 genuinely collide: rule 2 looks +/-3 minutes for
    corroboration, rule 4 looks only at immediate neighbours. Without the
    exemption a wake Garmin confirmed 3 minutes away would still be smoothed
    off, making rule 2's corroboration branch dead code for exactly the
    one-minute awakenings it exists to protect."""
    oura = _arr((L, 3), (A, 1), (L, 5))
    garmin = _arr((L, 6), (A, 1), (L, 2))
    master, reasons, _ = sf.fuse(oura, garmin)
    assert master[3] == A
    assert reasons[3] == sf.REASON_WAKE_CONFIRMED


def test_two_consecutive_awake_minutes_are_not_smoothed_because_they_are_not_isolated():
    oura = _arr((L, 2), (A, 2), (L, 2))
    master, _, _ = sf.fuse(oura, list(oura))
    assert master[2:4] == [A, A]


def test_an_awake_minute_at_the_very_start_is_not_smoothed_because_it_has_no_left_neighbour():
    oura = _arr((A, 1), (L, 3))
    master, _, _ = sf.fuse(oura, list(oura))
    assert master[0] == A


def test_smoothing_requires_sleep_on_both_devices_not_just_the_master():
    """The rule says "on both devices", so an uncovered Garmin neighbour is
    not evidence of continuous sleep."""
    oura = _arr((L, 2), (A, 1), (L, 2))
    garmin = [L, U, A, L, L]
    master, _, _ = sf.fuse(oura, garmin)
    assert master[2] == A


def test_smoothing_reads_a_frozen_snapshot_so_the_result_is_scan_direction_independent():
    """Alternating awake minutes must not cascade: if a smoothed minute could
    become a neighbour's evidence, the output would depend on iteration
    order."""
    oura = _arr((L, 1), (A, 1), (L, 1), (A, 1), (L, 1), (A, 1), (L, 1))
    master, _, _ = sf.fuse(oura, list(oura))
    assert master == [L, L, L, L, L, L, L]
    reversed_input = list(reversed(oura))
    reversed_master, _, _ = sf.fuse(reversed_input, list(reversed_input))
    assert reversed_master == list(reversed(master))


# ─── graceful degradation — the blend_strain contract ───────────────────────

def test_a_night_with_no_garmin_data_returns_ouras_hypnogram_unchanged():
    """Mirrors hr_load.blend_strain: with one source absent the output must
    collapse to the other bit-identically, so a Garmin-less night behaves
    exactly as it did before this module existed."""
    oura = _arr((A, 3), (L, 5), (D, 4), (R, 2))
    master, reasons, source = sf.fuse(oura, None)
    assert master == oura
    assert source == sf.SOURCE_OURA_ONLY
    assert set(reasons) == {sf.REASON_OURA_PASSTHROUGH}


def test_an_all_uncovered_garmin_array_is_treated_as_no_garmin_at_all():
    oura = _arr((A, 2), (L, 3))
    master, _, source = sf.fuse(oura, [U] * 5)
    assert master == oura
    assert source == sf.SOURCE_OURA_ONLY


def test_uncovered_garmin_minutes_pass_oura_through_untouched():
    oura = _arr((A, 2), (L, 2))
    master, reasons, _ = sf.fuse(oura, [U, U, L, L])
    assert master[:2] == [A, A]
    assert reasons[:2] == [sf.REASON_OURA_PASSTHROUGH] * 2


def test_a_short_garmin_array_is_padded_rather_than_truncating_the_night():
    oura = _arr((L, 10))
    master, _, _ = sf.fuse(oura, _arr((L, 4)))
    assert len(master) == 10


def test_neither_device_yields_no_master_at_all():
    assert sf.fuse([], None) == ([], [], sf.SOURCE_NONE)
    assert sf.fuse([], [sf.UNCOVERED] * 5) == ([], [], sf.SOURCE_NONE)


def test_no_oura_reading_falls_back_to_the_watch_alone():
    """Replaces an earlier test that asserted this produced nothing, which
    pinned a real bug: SOURCE_GARMIN_ONLY was unreachable, so nights the watch
    recorded and the ring did not produced no row at all.

    That is not an edge case here — over the 71 nights of the Garmin era the
    ring recorded 27 and the watch 53, so 27 nights (216 hours of sleep) were
    being discarded. Garmin's staging is the weaker of the two, so the label
    matters as much as the data.
    """
    master, reasons, source = sf.fuse([], _arr((L, 5)))
    assert master == _arr((L, 5))
    assert source == sf.SOURCE_GARMIN_ONLY
    assert set(reasons) == {sf.REASON_GARMIN_ONLY}


def test_a_garmin_only_night_contributes_no_phantom_wake():
    """phantom_wake_minutes feeds the Sleep Score through
    effective_wake_adjustments. A night with no Oura reading has no Oura wake
    to reclassify, so it must contribute exactly nothing — the watch must not
    become a backdoor into a score built entirely from ring measurements."""
    master, _, _ = sf.fuse([], _arr((L, 3), (A, 2)))
    assert sf.phantom_wake_minutes([], master) == 0


# ─── invariants ─────────────────────────────────────────────────────────────

def test_fusion_never_converts_a_sleep_minute_into_awake():
    """Every rule either removes phantom wake or swaps one sleep stage for
    another. This is the property the engine-wiring decision rests on."""
    oura = _arr((L, 20), (A, 5), (D, 30), (R, 10), (A, 2), (L, 15))
    garmin = _arr((D, 15), (A, 3), (L, 25), (L, 20), (R, 5), (A, 14))
    master, _, _ = sf.fuse(oura, garmin)
    for i, (o, m) in enumerate(zip(oura, master)):
        if o in sf.SLEEP_STAGES:
            assert m in sf.SLEEP_STAGES, f"minute {i} turned {o} into {m}"


def test_master_sleep_time_is_never_less_than_ouras():
    oura = _arr((L, 20), (A, 10), (D, 20), (A, 5), (R, 5))
    garmin = _arr((L, 30), (D, 20), (L, 10))
    master, _, _ = sf.fuse(oura, garmin)
    assert sf.sleep_minutes(master) >= sf.sleep_minutes(oura)


def test_the_master_is_always_exactly_as_long_as_the_oura_window():
    oura = _arr((L, 37))
    for garmin in (None, _arr((L, 5)), _arr((L, 100))):
        master, reasons, _ = sf.fuse(oura, garmin)
        assert len(master) == 37
        assert len(reasons) == 37


def test_every_minute_carries_a_reason_so_the_output_is_fully_attributable():
    oura = _arr((A, 4), (L, 4), (D, 4))
    master, reasons, _ = sf.fuse(oura, _arr((L, 8), (R, 4)))
    assert len(reasons) == len(master)
    assert all(r in sf.REASON_LABELS for r in reasons)


def test_fusion_is_deterministic_for_the_same_inputs():
    oura = _arr((L, 10), (A, 3), (D, 50), (R, 8))
    garmin = _arr((D, 12), (L, 40), (A, 2), (R, 17))
    assert sf.fuse(oura, garmin) == sf.fuse(oura, garmin)


# ─── derived measures ───────────────────────────────────────────────────────

def test_encode_and_decode_round_trip_a_hypnogram():
    minutes = _arr((D, 3), (L, 2), (R, 1), (A, 2))
    assert sf.decode(sf.encode(minutes)) == minutes


def test_encode_produces_the_same_digit_alphabet_oura_itself_uses():
    """Deliberate: a master hypnogram and an Oura hypnogram are then directly
    comparable strings with no translation step."""
    assert sf.encode(_arr((D, 1), (L, 1), (R, 1), (A, 1))) == "1234"


def test_stage_totals_reports_every_stage_including_zeros():
    totals = sf.stage_totals(_arr((L, 3)))
    assert totals[L] == 3
    assert totals[D] == 0 and totals[R] == 0 and totals[A] == 0


def test_phantom_wake_counts_only_oura_awake_minutes_the_master_calls_sleep():
    oura = _arr((A, 5), (L, 5))
    master = _arr((L, 3), (A, 2), (L, 5))
    assert sf.phantom_wake_minutes(oura, master) == 3


def test_phantom_wake_is_in_the_same_unit_as_the_manual_wake_correction():
    """Minutes of recorded awake time to subtract — which is exactly what
    services/sleep_score.py's wake_time_adjustments expects, and why
    effective_wake_adjustments can treat the two as interchangeable."""
    oura = _arr((A, 12), (L, 30))
    master = _arr((L, 42))
    assert sf.phantom_wake_minutes(oura, master) == 12


def test_agreement_ignores_minutes_either_device_did_not_cover():
    pct, _ = sf.agreement([L, L, U, A], [L, L, L, U])
    assert pct == 100.0


def test_agreement_is_none_when_the_devices_never_overlap():
    assert sf.agreement([U, U], [L, L]) == (None, None)


def test_cohens_kappa_is_zero_when_agreement_is_only_what_chance_predicts():
    """Both devices calling everything Light agree 100% of the time but carry
    no information — raw percent agreement flatters them, kappa does not."""
    pct, kappa = sf.agreement([L] * 10, [L] * 10)
    assert pct == 100.0
    assert kappa is None      # expected agreement is 1.0; kappa undefined


def test_the_real_paired_night_fuses_and_removes_phantom_wake():
    """End-to-end on the pinned payloads. Oura called 99 minutes awake that
    night; Garmin corroborated almost none of it."""
    window_start = sf.utc_from_iso_offset(_REAL_OURA_BEDTIME_START)
    oura = _arr((A, 20), (L, 200), (D, 75), (R, 81), (A, 79), (L, 74))
    garmin, _ = sf.garmin_minutes(_REAL_GARMIN_SLEEP_LEVELS, window_start, len(oura))
    master, _, source = sf.fuse(oura, garmin)
    assert source == sf.SOURCE_FUSED
    assert sf.phantom_wake_minutes(oura, master) > 0
    assert sf.sleep_minutes(master) >= sf.sleep_minutes(oura)


# ─── night_summary ──────────────────────────────────────────────────────────

def test_night_summary_keys_are_all_real_sleep_fusion_columns():
    """A key here that is not a column silently goes nowhere on write."""
    from services.repository import _SLEEP_FUSION_HEADER
    summary = sf.night_summary("2026-07-28", _EPOCH, _arr((L, 5)), _arr((L, 5)))
    assert set(summary) <= set(_SLEEP_FUSION_HEADER)


def test_the_sleep_fusion_header_is_fully_covered_by_its_two_producers():
    """A column no producer fills silently writes a blank forever.

    The row is now assembled from TWO halves — sf.night_summary for stages and
    sleep_movement.movement_summary (plus the repository's own series columns)
    for movement. Checking either alone would let a column added for the other
    go unnoticed, so this asserts the union covers the header exactly.
    """
    from services import sleep_movement as sm
    from services.repository import _SLEEP_FUSION_HEADER
    stages = sf.night_summary("2026-07-28", _EPOCH, _arr((L, 5)), _arr((L, 5)))
    movement = sm.movement_summary([sm.STILL], sf.SOURCE_FUSED)
    series = {"master_movement", "oura_movement", "garmin_movement", "movement_cutpoints"}
    # computed_at is stamped by the repository at save time, not by a producer.
    assert set(stages) | set(movement) | series == set(_SLEEP_FUSION_HEADER) - {"computed_at"}


def test_night_summary_records_which_ruleset_produced_the_row():
    summary = sf.night_summary("2026-07-28", _EPOCH, _arr((L, 5)), None)
    assert summary["rules_version"] == sf.RULES_VERSION
    assert summary["source"] == sf.SOURCE_OURA_ONLY


def test_night_summary_reports_master_sleep_at_least_oura_sleep():
    summary = sf.night_summary(
        "2026-07-28", _EPOCH, _arr((A, 5), (L, 5)), _arr((L, 10)))
    assert summary["master_sleep_hours"] >= summary["oura_sleep_hours"]
    assert summary["phantom_wake_minutes"] == 5


# ─── effective_wake_adjustments — the double-counting guard ─────────────────

def test_a_fused_night_uses_the_fusion_figure_instead_of_the_manual_one():
    adjustments, sources = sf.effective_wake_adjustments(
        manual={"2026-07-28": 30.0}, fused={"2026-07-28": 88.0})
    assert adjustments["2026-07-28"] == 88.0
    assert sources["2026-07-28"] == sf.WAKE_SOURCE_FUSION


def test_a_night_without_a_fused_figure_keeps_its_manual_correction():
    adjustments, sources = sf.effective_wake_adjustments(
        manual={"2026-07-27": 20.0}, fused={"2026-07-28": 88.0})
    assert adjustments["2026-07-27"] == 20.0
    assert sources["2026-07-27"] == sf.WAKE_SOURCE_MANUAL


def test_the_two_corrections_can_never_both_apply_to_one_night():
    """Double-counting is impossible by construction, not by arithmetic —
    a night resolves to exactly one source."""
    adjustments, sources = sf.effective_wake_adjustments(
        manual={"2026-07-28": 30.0}, fused={"2026-07-28": 88.0})
    assert len(adjustments) == 1
    assert adjustments["2026-07-28"] != 30.0 + 88.0
    assert len(set(sources.values())) == 1


def test_no_fusion_data_at_all_is_identical_to_the_manual_dict():
    manual = {"2026-07-26": 10.0, "2026-07-27": 20.0}
    adjustments, _ = sf.effective_wake_adjustments(manual=manual, fused=None)
    assert adjustments == manual


def test_both_absent_yields_an_empty_dict_rather_than_none():
    assert sf.effective_wake_adjustments(None, None) == ({}, {})


def test_a_zero_correction_is_dropped_so_it_cannot_mask_a_real_one():
    adjustments, sources = sf.effective_wake_adjustments(
        manual={"2026-07-28": 30.0}, fused={"2026-07-28": 0.0})
    assert adjustments["2026-07-28"] == 30.0
    assert sources["2026-07-28"] == sf.WAKE_SOURCE_MANUAL


# ─── RULES_VERSION 2 — movement-aware staging (rules 5-7) ───────────────────

def test_movement_class_constants_match_sleep_movement():
    """The 1-4 alphabet is declared in both modules to keep the import graph
    one-directional. Pin them together so the duplication cannot drift."""
    from services import sleep_movement as sm
    assert (sf.MOTION_STILL, sf.MOTION_RESTLESS, sf.MOTION_ACTIVE) == (
        sm.STILL, sm.RESTLESS, sm.ACTIVE)


def test_still_body_with_garmin_asleep_reads_as_asleep():
    """The case this ruleset was commissioned for: Oura awake, Garmin light,
    no movement on either device — therefore asleep. Version 1 reached the
    same verdict from the hypermobility premise alone; version 2 reaches it
    from measured stillness."""
    oura = [A] * 7
    garmin = [L] * 7
    movement = [sf.MOTION_STILL] * 7
    stage, reason = sf.merge_minute(oura, garmin, 3, sf._deep_runs(oura), movement)
    assert stage == L
    assert reason == sf.REASON_STILL_ASLEEP


def test_sustained_motion_preserves_an_awakening_version_one_would_have_erased():
    """Rule 6 — the first mechanism that stops a real awakening being
    converted to sleep. Without movement this exact minute becomes L."""
    oura = [A] * 7
    garmin = [L] * 7
    movement = [sf.MOTION_AWAKE_FROM] * 7
    stage, reason = sf.merge_minute(oura, garmin, 3, sf._deep_runs(oura), movement)
    assert stage == A
    assert reason == sf.REASON_MOTION_AWAKE
    # Same minute, no movement evidence -> version 1's verdict.
    assert sf.merge_minute(oura, garmin, 3, sf._deep_runs(oura))[0] == L


def test_merely_restless_movement_is_not_evidence_of_being_awake():
    """"Restless" is a normal state DURING sleep in Oura's own alphabet, not a
    marker of wakefulness — movement during sleep is normal and frequent
    (Wilde-Frenz & Schulz 1983). Only sustained GROSS motion counts.

    Measured: with the threshold at RESTLESS this rule fired on 1,451 of
    12,347 minutes and cut phantom-wake removal from 1,811 minutes to 360,
    moving 24 hours of sleep across 26 nights. At TOSSING it fires on 39.
    """
    assert sf.MOTION_AWAKE_FROM > sf.MOTION_RESTLESS
    oura = [A] * 7
    garmin = [L] * 7
    movement = [sf.MOTION_RESTLESS] * 7
    stage, reason = sf.merge_minute(oura, garmin, 3, sf._deep_runs(oura), movement)
    assert stage == L
    assert reason != sf.REASON_MOTION_AWAKE


def test_a_brief_burst_is_still_read_as_repositioning():
    """Between the two new rules sits the original verdict: motion too short
    to be an awakening, not still enough to be confidently asleep."""
    oura = [A] * 7
    garmin = [L] * 7
    movement = [sf.MOTION_STILL] * 3 + [sf.MOTION_ACTIVE] + [sf.MOTION_STILL] * 3
    stage, reason = sf.merge_minute(oura, garmin, 3, sf._deep_runs(oura), movement)
    assert stage == L
    assert reason == sf.REASON_REPOSITION


def test_uncovered_movement_never_counts_as_stillness():
    """An unmeasured minute is not evidence the body was still; treating it as
    such would let a gap manufacture the highest-confidence asleep verdict."""
    oura = [A] * 7
    garmin = [L] * 7
    movement = [sf.UNCOVERED] * 7
    _stage, reason = sf.merge_minute(oura, garmin, 3, sf._deep_runs(oura), movement)
    assert reason == sf.REASON_REPOSITION


def test_deep_sleep_with_whole_body_motion_defers_to_garmin():
    """Rule 7 — sustained slow-wave sleep essentially does not contain
    postural shifts, so Oura-Deep coinciding with ACTIVE motion is
    implausible. A physiological test where DEEP_RUN_PLAUSIBLE is a heuristic."""
    oura = [D] * 5
    garmin = [L] * 5
    movement = [sf.MOTION_ACTIVE] * 5
    stage, reason = sf.merge_minute(oura, garmin, 2, sf._deep_runs(oura), movement)
    assert stage == L
    assert reason == sf.REASON_DEEP_MOTION
    # Without the motion evidence Oura's Deep stands (the run is short).
    assert sf.merge_minute(oura, garmin, 2, sf._deep_runs(oura))[0] == D


def test_motion_confirmed_wake_survives_the_isolated_awake_smoothing():
    """Rule 4 must not undo rule 6, for the same reason it already exempts
    Garmin-corroborated wake."""
    master = [L, A, L]
    reasons = [sf.REASON_AGREE, sf.REASON_MOTION_AWAKE, sf.REASON_AGREE]
    out, out_reasons = sf.smooth_isolated_awake(
        master, reasons, [L, A, L], [L, L, L])
    assert out[1] == A
    assert out_reasons[1] == sf.REASON_MOTION_AWAKE


def test_rules_version_two_without_movement_is_identical_to_version_one():
    """The bump must be safe to apply to the whole history: every night that
    predates the watch has to re-derive bit-identically."""
    oura = _arr((A, 4), (L, 6), (D, 50), (R, 10), (A, 3))
    garmin = _arr((L, 20), (D, 30), (L, 20), (A, 3))
    assert sf.fuse(oura, garmin, None) == sf.fuse(oura, garmin)


def test_movement_alone_never_changes_a_verdict_without_garmin_stages():
    """Every movement rule sits inside a branch that already required
    Garmin's stage opinion, so a Garmin-less night still passes Oura
    through untouched however much it moved."""
    oura = _arr((A, 5), (L, 5))
    movement = [sf.MOTION_ACTIVE] * 10
    master, _reasons, source = sf.fuse(oura, None, movement)
    assert master == oura
    assert source == sf.SOURCE_OURA_ONLY


def test_every_reason_code_has_a_label():
    """A code with no label renders as a blank explanation in the UI."""
    codes = [v for k, v in vars(sf).items() if k.startswith("REASON_") and isinstance(v, str)]
    assert set(codes) == set(sf.REASON_LABELS)
