"""The watch's clock and the app's clock must be compared as INSTANTS.

The app does not run where the athlete trains. Per-set timestamps carry an
offset, but on a UTC host with HEALTH_TIMEZONE unset that offset is +00:00
while the watch stamps local time. Reduced to wall clock the two differ by the
athlete's whole UTC offset, and MATCH_TOLERANCE_SECONDS is wide enough that the
shifted window still scores a match -- so the failure mode is a CONFIDENT WRONG
MATCH, not a missing one.

Measured on the real data: per-set `ts` carried +02:00 on 2026-08-10 (which
matched cleanly, every exercise covered) and +00:00 from 2026-08-16 onward.
"""

from datetime import datetime, timedelta, timezone

from services import hr_matching as hm


# ─── device_start_iso ───────────────────────────────────────────────────────

def test_offset_is_inferred_from_the_pair_of_clocks():
    # Ireland in August: the watch is one hour ahead of UTC.
    got = hm.device_start_iso("2026-08-21 08:49:48", "2026-08-21 07:49:48")
    assert got == "2026-08-21T08:49:48+01:00"


def test_a_base_two_hours_ahead_reads_two_hours():
    got = hm.device_start_iso("2026-08-10 17:50:31", "2026-08-10 15:50:31")
    assert got == "2026-08-10T17:50:31+02:00"


def test_offsets_west_of_utc_are_negative():
    got = hm.device_start_iso("2026-08-21 03:49:48", "2026-08-21 08:49:48")
    assert got == "2026-08-21T03:49:48-05:00"


def test_half_hour_zones_survive():
    got = hm.device_start_iso("2026-08-21 13:19:48", "2026-08-21 07:49:48")
    assert got == "2026-08-21T13:19:48+05:30"


def test_a_gmt_string_carrying_its_own_offset_is_handled():
    got = hm.device_start_iso("2026-08-21 08:49:48", "2026-08-21T07:49:48+00:00")
    assert got == "2026-08-21T08:49:48+01:00"


def test_a_zulu_gmt_string_is_handled():
    got = hm.device_start_iso("2026-08-21 08:49:48", "2026-08-21T07:49:48Z")
    assert got == "2026-08-21T08:49:48+01:00"


# ─── it must never make things worse than it found them ─────────────────────

def test_missing_gmt_returns_the_local_string_unchanged():
    """Every row stored before this existed has no GMT side. It must degrade to
    exactly the old behaviour rather than guessing an offset."""
    assert hm.device_start_iso("2026-08-21 08:49:48", "") == "2026-08-21 08:49:48"
    assert hm.device_start_iso("2026-08-21 08:49:48", None) == "2026-08-21 08:49:48"


def test_unparseable_gmt_returns_the_local_string_unchanged():
    assert hm.device_start_iso("2026-08-21 08:49:48", "not a time") == "2026-08-21 08:49:48"


def test_an_impossible_offset_is_refused_rather_than_stamped():
    """A difference no real zone has means one of the two fields is not what it
    claims to be. Falling back is safe; stamping a 30-hour offset is not."""
    assert hm.device_start_iso("2026-08-21 08:49:48", "2026-08-20 02:00:00") == "2026-08-21 08:49:48"


def test_missing_local_yields_empty_not_a_crash():
    assert hm.device_start_iso("", "2026-08-21 07:49:48") == ""
    assert hm.device_start_iso(None, None) == ""


def test_a_local_string_that_already_carries_an_offset_passes_through():
    got = hm.device_start_iso("2026-08-21T08:49:48+01:00", "2026-08-21 07:49:48")
    assert got == "2026-08-21T08:49:48+01:00"


# ─── the behaviour that actually matters ──────────────────────────

def _utc(h, m, s=0):
    return datetime(2026, 8, 21, h, m, s, tzinfo=timezone.utc)


# The real 2026-08-21 session, from datastore.db. Per-set `ts` ran
# 07:50:53+00:00 -> 08:49:08+00:00, and the watch reported the activity at
# 08:49:48 local for 15.5 minutes. The athlete was in Ireland (UTC+1), so the
# activity truly ran 07:49:48 -> 08:05:18 UTC, i.e. INSIDE the session.
_WINDOW = (_utc(7, 50, 53), _utc(8, 49, 8))
_DURATION_MIN = 15.5


def test_an_offset_aware_activity_matches_the_window_it_really_overlaps():
    aware = [{"start_time_local": "2026-08-21T08:49:48+01:00",
              "duration_minutes": _DURATION_MIN, "type": "indoor_cardio"}]

    act, overlap = hm.match_activity(aware, _WINDOW)

    assert act is not None
    # The activity sits wholly inside the padded session window, so every
    # second of it is attributable: quality is 1.00.
    assert overlap == _DURATION_MIN * 60


def test_without_the_offset_the_same_data_matches_an_hour_late():
    """Guards the reason this fix exists. With a naive activity string the
    comparison falls back to wall clock. The window is then an hour out -- but
    MATCH_TOLERANCE_SECONDS is 15 minutes, wide enough that the tail still
    overlaps and still clears MIN_OVERLAP_SECONDS. So it returns a match, from
    the wrong fourteen minutes, with nothing anywhere reporting a problem."""
    naive = [{"start_time_local": "2026-08-21 08:49:48",
              "duration_minutes": _DURATION_MIN, "type": "indoor_cardio"}]

    act, overlap = hm.match_activity(naive, _WINDOW)

    assert act is not None                       # it does NOT fail loudly
    assert overlap < _DURATION_MIN * 60          # and it is the wrong window
    assert overlap == 860.0                      # the 14.3 min actually recorded


def test_naive_rows_still_match_the_way_they_always_did():
    """Rows stored before this change have no GMT side and stay naive.
    Nothing about their behaviour may move."""
    window = (datetime(2026, 8, 6, 12, 55), datetime(2026, 8, 6, 13, 40))
    rows = [{"start_time_local": "2026-08-06 12:50:35",
             "duration_minutes": 61.2, "type": "strength_training"}]

    act, overlap = hm.match_activity(rows, window)

    assert act is not None
    # activity 12:50:35 -> 13:51:47 against a window padded to 12:40 -> 13:55
    assert overlap == 3672.0
