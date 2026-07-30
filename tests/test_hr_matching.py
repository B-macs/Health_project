"""Tests for services/hr_matching.py — Garmin activity ↔ logged session."""

from datetime import datetime

import pytest

from services import hr_matching as hm


def _sets(*iso_stamps):
    return [{"set_num": i + 1, "ts": s} for i, s in enumerate(iso_stamps)]


def _activity(start, minutes, type_="strength_training", **extra):
    return {"start_time_local": start, "duration_minutes": minutes,
            "type": type_, **extra}


# ─── overlap_seconds ────────────────────────────────────────────────────────

def test_overlap_of_partially_overlapping_spans():
    ov = hm.overlap_seconds("2026-07-30T18:00:00", "2026-07-30T19:00:00",
                             "2026-07-30T18:30:00", "2026-07-30T20:00:00")
    assert ov == 30 * 60


def test_overlap_of_disjoint_spans_is_zero():
    assert hm.overlap_seconds("2026-07-30T18:00:00", "2026-07-30T19:00:00",
                               "2026-07-30T19:30:00", "2026-07-30T20:00:00") == 0.0


def test_overlap_fully_contained():
    ov = hm.overlap_seconds("2026-07-30T18:00:00", "2026-07-30T20:00:00",
                             "2026-07-30T18:30:00", "2026-07-30T19:00:00")
    assert ov == 30 * 60


def test_overlap_handles_reversed_bounds():
    assert hm.overlap_seconds("2026-07-30T19:00:00", "2026-07-30T18:00:00",
                               "2026-07-30T18:30:00", "2026-07-30T20:00:00") == 30 * 60


def test_overlap_unparseable_bounds_are_zero():
    assert hm.overlap_seconds("nonsense", "2026-07-30T19:00:00",
                               "2026-07-30T18:30:00", "2026-07-30T20:00:00") == 0.0
    assert hm.overlap_seconds(None, None, None, None) == 0.0


def test_overlap_accepts_garmin_local_time_format():
    ov = hm.overlap_seconds("2026-07-30 18:00:00", "2026-07-30 19:00:00",
                             datetime(2026, 7, 30, 18, 30), datetime(2026, 7, 30, 20, 0))
    assert ov == 30 * 60


# ─── session_window ─────────────────────────────────────────────────────────

def test_session_window_spans_first_to_last_set():
    w = hm.session_window(_sets("2026-07-30T18:02:00", "2026-07-30T18:20:00",
                                 "2026-07-30T18:41:00"))
    assert w == (datetime(2026, 7, 30, 18, 2), datetime(2026, 7, 30, 18, 41))


def test_session_window_extends_to_full_duration_when_longer():
    # Sets all logged in a 5-minute burst, but the session ran 45 minutes.
    w = hm.session_window(_sets("2026-07-30T18:00:00", "2026-07-30T18:05:00"),
                           duration_minutes=45)
    assert w[1] == datetime(2026, 7, 30, 18, 45)


def test_session_window_does_not_shrink_below_logged_sets():
    w = hm.session_window(_sets("2026-07-30T18:00:00", "2026-07-30T19:00:00"),
                           duration_minutes=10)
    assert w[1] == datetime(2026, 7, 30, 19, 0)


def test_session_window_none_without_timestamps():
    """Every session logged before per-set capture existed has no "ts" at
    all — those cannot be time-matched and must fall through to RPE."""
    assert hm.session_window([{"set_num": 1, "reps": 10}]) is None
    assert hm.session_window([]) is None
    assert hm.session_window(None) is None


def test_session_window_ignores_unparseable_timestamps():
    w = hm.session_window(_sets("garbage", "2026-07-30T18:20:00"))
    assert w == (datetime(2026, 7, 30, 18, 20), datetime(2026, 7, 30, 18, 20))


# ─── match_activity ─────────────────────────────────────────────────────────

WINDOW = (datetime(2026, 7, 30, 18, 0), datetime(2026, 7, 30, 19, 0))


def test_matches_the_overlapping_activity():
    acts = [_activity("2026-07-30 18:05:00", 50)]
    act, ov = hm.match_activity(acts, WINDOW)
    assert act is acts[0]
    assert ov > 0


def test_prefers_the_largest_overlap():
    short = _activity("2026-07-30 18:50:00", 10, name="walk")
    long = _activity("2026-07-30 18:00:00", 60, name="gym")
    act, _ = hm.match_activity([short, long], WINDOW)
    assert act is long


def test_ignores_activity_on_a_different_day():
    acts = [_activity("2026-07-29 18:05:00", 50)]
    assert hm.match_activity(acts, WINDOW) == (None, 0.0)


def test_ignores_brief_incidental_overlap():
    # A 2-minute walk brushing the edge of the window is not the session.
    acts = [_activity("2026-07-30 18:58:00", 2)]
    assert hm.match_activity(acts, WINDOW) == (None, 0.0)


def test_tolerance_allows_activity_starting_just_before_the_session():
    """The stated real-world case: the watch was started before the first set
    was logged, or stopped after the last one."""
    acts = [_activity("2026-07-30 17:50:00", 40)]
    act, _ = hm.match_activity(acts, WINDOW)
    assert act is not None


def test_no_window_means_no_match():
    assert hm.match_activity([_activity("2026-07-30 18:00:00", 60)], None) == (None, 0.0)


def test_no_activities_means_no_match():
    assert hm.match_activity([], WINDOW) == (None, 0.0)


def test_skips_excluded_activity_types():
    acts = [_activity("2026-07-30 18:00:00", 60, type_="sleep")]
    assert hm.match_activity(acts, WINDOW) == (None, 0.0)


def test_skips_activities_with_junk_fields():
    acts = [
        _activity(None, 60),
        _activity("2026-07-30 18:00:00", "abc"),
        _activity("2026-07-30 18:00:00", 0),
    ]
    assert hm.match_activity(acts, WINDOW) == (None, 0.0)


def test_unknown_activity_type_still_matches():
    """Strength-work typeKey varies by device/firmware, so anything not
    explicitly excluded must remain eligible."""
    acts = [_activity("2026-07-30 18:00:00", 60, type_="some_new_garmin_type")]
    assert hm.match_activity(acts, WINDOW)[0] is not None


# ─── exercise_blocks / samples_for_block ────────────────────────────────────

def test_exercise_blocks_sorted_by_start():
    blocks = hm.exercise_blocks({
        1: _sets("2026-07-30T18:20:00", "2026-07-30T18:26:00"),
        0: _sets("2026-07-30T18:02:00", "2026-07-30T18:10:00"),
    })
    assert [b["exercise_idx"] for b in blocks] == [0, 1]
    assert blocks[0]["start"] == datetime(2026, 7, 30, 18, 2)
    assert blocks[0]["end"] == datetime(2026, 7, 30, 18, 10)


def test_exercise_blocks_skips_untimestamped_exercises():
    blocks = hm.exercise_blocks({0: [{"set_num": 1}], 1: _sets("2026-07-30T18:20:00")})
    assert [b["exercise_idx"] for b in blocks] == [1]


def test_exercise_blocks_empty_input():
    assert hm.exercise_blocks({}) == []
    assert hm.exercise_blocks(None) == []


def test_samples_for_block_selects_the_time_range():
    base = datetime(2026, 7, 30, 18, 0).timestamp()
    samples = [(base + i, 140 + i) for i in range(10)]
    got = hm.samples_for_block(samples, datetime(2026, 7, 30, 18, 0, 2),
                                datetime(2026, 7, 30, 18, 0, 5))
    assert [hr for _, hr in got] == [142, 143, 144, 145]


def test_samples_for_block_zero_length_block_takes_nearest_sample():
    base = datetime(2026, 7, 30, 18, 0).timestamp()
    samples = [(base + 30, 150)]
    instant = datetime(2026, 7, 30, 18, 0, 25)
    assert hm.samples_for_block(samples, instant, instant) == [(base + 30, 150)]


def test_samples_for_block_zero_length_block_ignores_distant_samples():
    base = datetime(2026, 7, 30, 18, 0).timestamp()
    samples = [(base + 600, 150)]
    instant = datetime(2026, 7, 30, 18, 0, 0)
    assert hm.samples_for_block(samples, instant, instant) == []


def test_samples_for_block_empty():
    assert hm.samples_for_block([], datetime(2026, 7, 30, 18, 0),
                                 datetime(2026, 7, 30, 18, 5)) == []


# ─── end-to-end: per-exercise HR attribution ────────────────────────────────

def test_per_exercise_hr_attribution_end_to_end():
    """The item-16 requirement: HR logged against exercise time. Two blocks,
    the second genuinely harder, must come out with different zone profiles."""
    from services import hr_load

    base = datetime(2026, 7, 30, 18, 0)
    # Exercise 0 easy (HR 120 ~ Z2), exercise 1 hard (HR 175 ~ Z5).
    samples = ([(base.timestamp() + i, 120) for i in range(0, 300)]
               + [(base.timestamp() + i, 175) for i in range(300, 600)])
    by_ex = {
        0: _sets("2026-07-30T18:00:00", "2026-07-30T18:04:00"),
        1: _sets("2026-07-30T18:05:00", "2026-07-30T18:09:00"),
    }
    blocks = hm.exercise_blocks(by_ex)
    loads = {}
    for b in blocks:
        blk = hm.samples_for_block(samples, b["start"], b["end"])
        zones = hr_load.seconds_in_zone_from_samples(blk, hr_max=190)
        loads[b["exercise_idx"]] = hr_load.edwards_load(zones)

    assert loads[1] > loads[0]          # the hard block carries more load
    assert set(loads) == {0, 1}
