"""A read for a day ends on that day (rebuild rule 3), never on the newest row stored.

Found 2026-10-21, while the warnings calendar was rebuilt to show the days the app lowered
the load: worked out again for a past day, every decision read "no reading yet", because
four reads behind it had no end date. The check-ins' alcohol rows put a later day last in
the biometric rows, so the day's own row was never the newest and its light was never
judged; and a later check-in's pain reset an earlier day's pain-free streak. For today
they gave the same answers as now; for any past day they did not.

A real local copy (the offline reader applies the date filters, which the faked Notion
client of tests/test_repository.py does not). Made-up rows only; no network.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from services import record_cache
from tests._record_store import FakeStore, new_local_copy, record_repo

DAY = date(2026, 10, 16)


@pytest.fixture
def repo(tmp_path):
    path = new_local_copy(tmp_path)
    con = sqlite3.connect(path)
    # Check-ins before the day asked for, and one after it with pain and drink.
    for day, tightness, pain, alcohol in (("2026-10-10", 2, 3, 1), ("2026-10-14", 4, 0, 0),
                                          ("2026-10-20", 8, 5, 2)):
        con.execute("INSERT INTO readiness_checkins (date, tightness_score, pain_score, alcohol_units) "
                    "VALUES (?, ?, ?, ?)", (day, tightness, pain, alcohol))
    # A session before the day asked for and one after it.
    for sid, day, au in (("2026-10-12-aaaa0001", "2026-10-12", 300.0), ("2026-10-19-aaaa0002", "2026-10-19", 500.0)):
        con.execute("INSERT INTO training_sessions (session_id, session_date, session_duration_minutes, "
                    "session_rpe, session_au) VALUES (?, ?, 50, 6, ?)", (sid, day, au))
        con.execute("INSERT INTO training_exercises (exercise_id, session_id, session_date, movement_name) "
                    "VALUES (?, ?, ?, 'Made-up lift')", (f"ex-{sid}", sid, day))
    con.commit()
    con.close()
    yield record_repo(path, FakeStore())
    record_cache.forget(path)


def test_the_recent_check_ins_end_on_the_day(repo):
    assert sorted(r["date"] for r in repo.get_recent_readiness(days=10, today=DAY)) == ["2026-10-10", "2026-10-14"]


def test_the_average_tightness_counts_only_days_up_to_the_day(repo):
    assert repo.get_avg_tightness(14, today=DAY) == 3.0


def test_a_later_pain_does_not_reset_an_earlier_days_streak(repo):
    # Pain last reported on 10 Oct, so six days without pain on 16 Oct; the pain of
    # 20 Oct read as the anchor made it 0.
    assert repo.get_pain_free_streak(today=DAY) == 6
    assert repo.get_pain_free_streak(today=date(2026, 10, 21)) == 1


def test_the_training_load_counts_only_sessions_up_to_the_day(repo):
    rows = repo.get_daily_session_au_weighted(28, today=DAY)
    assert [r["date"] for r in rows] == ["2026-10-12"]


def test_the_biometric_rows_end_on_the_day(repo):
    rows = repo.get_biometric_rolling(days=28, today=DAY)
    assert rows and max(r.date for r in rows) <= DAY.isoformat()
