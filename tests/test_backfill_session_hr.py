"""scripts/backfill_session_hr.py (2026-11-11): the plan sessions it looks at and
the day shift it takes. The athlete: "Find those connections in the Garmin server
and download them"."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "scripts" / "backfill_session_hr.py"
_spec = importlib.util.spec_from_file_location("backfill_session_hr", _PATH)
bf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bf)


class _Repo:
    def __init__(self, logged, have):
        self.logged, self.have, self.asked = logged, have, []

    def get_logged_session_dates(self, start, end, include_supplementary=True):
        self.asked.append((start, end, include_supplementary))
        return set(self.logged)

    def get_session_hr_history(self, start=None):
        return [{"date": d} for d in self.have]


def test_it_looks_at_plan_sessions_with_no_heart_rate_row_oldest_first():
    repo = _Repo(logged={"2026-11-11", "2026-08-06", "2026-10-29"}, have={"2026-10-29"})
    days = bf.missing_dates(repo, date(2026, 8, 1), date(2026, 11, 11))
    assert days == [date(2026, 8, 6), date(2026, 11, 11)]
    assert repo.asked == [(date(2026, 8, 1), date(2026, 11, 11), False)], "plan sessions only"


def test_a_shift_names_a_day_and_its_hours():
    assert bf.parse_shift("2026-08-06=2") == (date(2026, 8, 6), 2.0)
    assert bf.parse_shift("2026-08-06=-1.5") == (date(2026, 8, 6), -1.5)


def test_a_day_with_no_activity_says_so():
    assert bf.describe_activities([]) == "Garmin has no activity on this day"
    line = bf.describe_activities([{"start_time_local": "2026-08-05T17:55:15+02:00",
                                    "name": "Made-up walk", "duration_minutes": 22.9}])
    assert line == "Garmin's activities that day: 17:55 Made-up walk (23 min)"
