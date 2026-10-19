"""The accessory session's inputs, read by services/accessory.read_choice
(move TRN-14, 2026-10-19), so the training page and the engine API choose
from the same reads: the caller's day, every read degrading to the
conservative side, and a retest tomorrow keeping the legs clean. A fake
repository; no network.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import cluster_a_prescription as cap
import training_constants as tc
from services import accessory as acc
from services import strain_regions as sr

TODAY = date(2026, 10, 21)


def _rows(**au):
    row = {"date": (TODAY - timedelta(days=1)).isoformat(), "upper_body": 0.0, "core": 0.0,
           "lower_body": 0.0, "unattributed": 0.0, "regions_known": True}
    row.update(au)
    row["total_au"] = sum(row[r] for r in sr.REGIONS) + row["unattributed"]
    return [row]


class _Repo:
    def __init__(self, rows=None, assessments=(), fail=False):
        self.rows, self.assessments, self.fail = rows or [], list(assessments), fail
        self.days_asked = []

    def _check(self):
        if self.fail:
            raise RuntimeError("store unreachable")

    def get_daily_region_au(self, days=28, today=None):
        self._check()
        self.days_asked.append(("region", today))
        return {"rows": self.rows}

    def get_current_stage(self):
        self._check()
        return 2

    def get_phases(self):
        self._check()
        return []

    def get_flexibility_assessments(self):
        self._check()
        return self.assessments

    def get_recent_sessions(self, days=60, today=None):
        self._check()
        self.days_asked.append(("sessions", today))
        return []


def test_the_reads_use_the_callers_day():
    repo = _Repo(rows=_rows(upper_body=250.0, core=200.0, lower_body=1.0),
                 assessments=[SimpleNamespace(taken_on=TODAY - timedelta(days=10))])
    acc.read_choice(repo, None, None, None, TODAY)
    assert repo.days_asked == [("region", TODAY), ("sessions", TODAY)]


def test_unreadable_inputs_still_give_a_session():
    choice = acc.read_choice(_Repo(fail=True), None, None, None, TODAY)
    assert choice.exercises and choice.on_date == TODAY.isoformat()


def test_a_retest_tomorrow_keeps_the_legs_clean():
    rows = _rows(upper_body=250.0, core=200.0, lower_body=1.0)
    free = acc.read_choice(_Repo(rows=rows), None, None, None, TODAY)
    assert free.region == "lower_body"
    due_tomorrow = TODAY + timedelta(days=1) - timedelta(days=cap.RETEST_INTERVAL_DAYS)
    repo = _Repo(rows=rows, assessments=[SimpleNamespace(taken_on=due_tomorrow)])
    held = acc.read_choice(repo, None, None, None, TODAY)
    assert held.region != "lower_body"
    assert any("retest" in r for r in held.reasons)
    assert not [n for n in held.names if tc.EXERCISE_BODY_REGION.get(n) == "lower_body"]


def test_cached_region_rows_are_used_without_a_read():
    repo = _Repo(rows=_rows(lower_body=500.0))
    choice = acc.read_choice(repo, None, None, None, TODAY,
                             region_rows=_rows(upper_body=250.0, core=200.0, lower_body=1.0))
    assert ("region", TODAY) not in repo.days_asked
    assert choice.region == "lower_body", "the passed rows decided, not the store's"
