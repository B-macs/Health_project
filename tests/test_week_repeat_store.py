"""week_repeat.store_failed_week_rule and store_redo: the rule's writes.

The Training page called the rule and wrote its result itself until
2026-10-19; the writes moved into services/week_repeat.py so the page and the
phone's engine run the same one. What this pins, with a store that records
every call:

  * nothing due, nothing read live and nothing written;
  * a verdict is rebuilt from LIVE reads of the stored phases AND the log
    before it is written: on 2026-09-22 a local copy missing two logged days
    failed a four-day week;
  * a stored verdict the local copy lacks is written back, which repairs the
    copy;
  * the redo is rebuilt from live reads too, and a week already set to run
    again is not set twice.
"""

from __future__ import annotations

from datetime import date

from services import week_repeat as wr
from services.models import Phase

BLOCK = Phase(5, "12-week block", "2026-10-19", 84, "active")
WEEK_1 = "2026-10-19"
MON_1026 = date(2026, 10, 26)                    # week 1 has ended
FOUR_DAYS = {"2026-10-19", "2026-10-20", "2026-10-22", "2026-10-23"}
TWO_OF_THEM = {"2026-10-19", "2026-10-20"}       # the copy that lost two days


class RecordingStore:
    """The reads and the one write the rule makes, over plain values."""

    def __init__(self, stored, live_logged, local_logged=None):
        self.stored = list(stored)
        self.live_logged = set(live_logged)
        self.local_logged = set(live_logged if local_logged is None else local_logged)
        self.calls: list[str] = []
        self.written = None

    def get_phases_live(self):
        self.calls.append("get_phases_live")
        return list(self.stored)

    def get_logged_session_dates_live(self, start, end):
        self.calls.append("get_logged_session_dates_live")
        return set(self.live_logged)

    def get_logged_session_dates(self, start, end, include_supplementary=True):
        self.calls.append("get_logged_session_dates")
        return set(self.local_logged)

    def set_phases(self, phases):
        self.calls.append("set_phases")
        self.written = self.stored = list(phases)


def test_nothing_due_reads_nothing_live_and_writes_nothing():
    judged = Phase(5, "12-week block", "2026-10-19", 84, "active",
                   week_results={WEEK_1: "Passed — 4 of 7 days logged"})
    store = RecordingStore([judged], FOUR_DAYS)
    assert wr.store_failed_week_rule(store, [judged], MON_1026, FOUR_DAYS) is False
    assert store.calls == []


def test_the_verdict_is_rebuilt_from_live_reads_before_it_is_written():
    """The 2026-09-22 case: the local copy holds two of the four logged days,
    so it says week 1 failed; the live log says it passed, and that is stored."""
    store = RecordingStore([BLOCK], FOUR_DAYS, local_logged=TWO_OF_THEM)
    assert wr.store_failed_week_rule(store, [BLOCK], MON_1026) is True
    assert store.calls == ["get_logged_session_dates", "get_phases_live",
                           "get_logged_session_dates_live", "set_phases"]
    [stored] = store.written
    assert stored.week_results[WEEK_1].startswith(wr.PASSED_PREFIX)
    assert "4 of 7 days" in stored.week_results[WEEK_1]
    assert stored.week_plan in (None, list(range(1, 13)))          # nothing repeated


def test_a_failed_week_is_repeated_from_the_live_count():
    store = RecordingStore([BLOCK], {"2026-10-19"})
    assert wr.store_failed_week_rule(store, [BLOCK], MON_1026, {"2026-10-19"}) is True
    [stored] = store.written
    assert stored.week_results[WEEK_1].startswith(wr.FAILED_PREFIX)
    assert stored.length_days == 91 and stored.week_plan[:2] == [1, 1]


def test_a_stored_verdict_the_copy_lacks_is_written_back():
    judged = Phase(5, "12-week block", "2026-10-19", 84, "active",
                   week_results={WEEK_1: "Passed — 4 of 7 days logged"})
    store = RecordingStore([judged], FOUR_DAYS)
    assert wr.store_failed_week_rule(store, [BLOCK], MON_1026, FOUR_DAYS) is True
    assert store.written == [judged]


def test_the_redo_is_rebuilt_from_live_reads_and_stored():
    store = RecordingStore([BLOCK], {"2026-10-26"})
    phases, why = wr.store_redo(store, MON_1026)
    assert why is None and phases == store.written
    assert store.calls == ["get_phases_live", "get_logged_session_dates_live", "set_phases"]
    assert store.written[0].week_results["2026-10-26"].startswith(wr.REDONE_PREFIX)


def test_a_week_already_set_to_run_again_is_not_set_twice():
    store = RecordingStore([BLOCK], {"2026-10-26"})
    wr.store_redo(store, MON_1026)
    store.calls.clear()
    phases, why = wr.store_redo(store, MON_1026)
    assert phases is None and why == "this week is already set to run again"
    assert "set_phases" not in store.calls


def test_no_block_no_redo():
    store = RecordingStore([], set())
    assert wr.store_redo(store, MON_1026) == (None, "there is no training block")
    assert store.calls == ["get_phases_live"]
