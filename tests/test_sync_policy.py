"""services/sync_policy.py: when the engine syncs, and which notice shows.

The owner's rule (2026-10-19): one sync at the first open of the day; while
last night's numbers are missing after it, a later open retries, at most once
an hour; nothing more once they are in. The day is the caller's (rebuild rule
3). And the sync notices app.py showed inline (move HOME-27): a dead Oura
credential is an error checked on its own, a failed step a caption.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from services import sync_policy as sp

TODAY = date(2026, 10, 20)
MORNING = datetime(2026, 10, 20, 7, 40)


def test_the_first_open_of_the_day_syncs():
    assert sp.sync_due(TODAY, MORNING, None, None, night_in=False) == sp.FIRST_OPEN
    yesterday_evening = datetime(2026, 10, 19, 22, 0)
    assert sp.sync_due(TODAY, MORNING, date(2026, 10, 19), yesterday_evening,
                       night_in=True) == sp.FIRST_OPEN


def test_once_last_night_is_in_nothing_more_that_day():
    assert sp.sync_due(TODAY, MORNING + timedelta(hours=5), TODAY, MORNING,
                       night_in=True) is None


def test_while_last_night_is_missing_a_later_open_retries_at_most_hourly():
    assert sp.sync_due(TODAY, MORNING + timedelta(minutes=59), TODAY, MORNING,
                       night_in=False) is None
    assert sp.sync_due(TODAY, MORNING + timedelta(minutes=60), TODAY, MORNING,
                       night_in=False) == sp.LAST_NIGHT_MISSING


def test_the_day_is_the_callers_not_the_clocks():
    """00:30 on the caller's new day, against a server clock still on the day
    before: the caller's day decides, so this is the first open of the day."""
    late = datetime(2026, 10, 19, 22, 30)                # the server's UTC clock
    assert sp.sync_due(TODAY, late, date(2026, 10, 19), datetime(2026, 10, 19, 8, 0),
                       night_in=True) == sp.FIRST_OPEN


def test_last_night_is_in_when_today_carries_readiness_and_sleep():
    assert sp.last_night_in({"readiness_score": 61.0, "sleep_score": 78.0})
    assert not sp.last_night_in({"readiness_score": 61.0, "sleep_score": None})
    assert sp.last_night_in({"readiness_score": 0.0, "sleep_score": 70.0})    # 0 is a real score
    assert not sp.last_night_in(None)


OK, FAILED = (True, None), (False, "timeout")


def test_a_dead_oura_credential_is_an_error_whatever_the_run_said():
    assert sp.sync_notices({"needs_authorisation": True}, OK, OK, None) == [
        ("error", sp.OURA_UNAUTHORISED)]
    assert sp.sync_notices({"needs_authorisation": True}, FAILED, OK, None) == [
        ("error", sp.OURA_UNAUTHORISED)]


def test_failed_steps_and_a_failed_chain_are_captions_in_order():
    assert sp.sync_notices({}, FAILED, FAILED, "chain crashed") == [
        ("caption", sp.OURA_UNAVAILABLE), ("caption", sp.GARMIN_UNAVAILABLE),
        ("caption", sp.SYNC_FAILED_TO_RUN)]
    assert sp.sync_notices(None, OK, OK, None) == []
    assert sp.sync_notices({}, (False, None), OK, None) == []   # no error text, nothing to say
