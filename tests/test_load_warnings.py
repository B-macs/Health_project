"""Insights › Warnings since 2026-10-21 (services/load_warnings.py): the days the
app told him to lower the load. The owner: "I thought the warning was the days that it
says reduce load because of tiredness or other reason strain? Can we change it to this?"
Each day is its own decision, worked out again from the readings stored for it; a fake
decision here. No network.
"""

from __future__ import annotations

import types
from datetime import date, timedelta

from services import load_warnings as lw

TODAY = date(2026, 10, 21)


def _decisions(monkeypatch, kinds):
    asked = []

    def verdict(repo, day):
        asked.append(day)
        kind, cause = kinds.get(day, ("", ""))
        return types.SimpleNamespace(banner_kind=kind, cause=cause)
    monkeypatch.setattr(lw.decision, "day_verdict", verdict)
    return asked


def test_rest_reduced_and_held_days_are_warnings_and_nothing_else_is(monkeypatch):
    _decisions(monkeypatch, {date(2026, 10, 1): ("error", "Made-up reading."),
                             date(2026, 10, 6): ("warning", "Made-up reading."),
                             date(2026, 10, 9): ("info", ""),
                             date(2026, 10, 12): ("neutral", "No reading yet.")})
    assert lw.day_warning(None, date(2026, 10, 1)) == ("rest", "Made-up reading.")
    assert lw.day_warning(None, date(2026, 10, 6)) == ("reduced", "Made-up reading.")
    assert lw.day_warning(None, date(2026, 10, 9)) == ("held", "")
    assert lw.day_warning(None, date(2026, 10, 12)) == (None, ""), "no reading is not a warning"
    assert lw.day_warning(None, date(2026, 10, 13)) == (None, ""), "a clear day"


def test_the_month_opens_on_today_counts_its_own_days_and_stops_at_today(monkeypatch):
    asked = _decisions(monkeypatch, {date(2026, 9, 30): ("error", "x"),     # the grid's first row
                                     date(2026, 10, 6): ("warning", "y"),
                                     date(2026, 10, 7): ("warning", "z")})
    month = lw.calendar(None, TODAY)
    assert (month["year"], month["month"]) == (2026, 10)
    assert month["previous"] == {"year": 2026, "month": 9} and month["next"] == {"year": 2026, "month": 11}
    assert month["counts"] == {"rest": 0, "reduced": 2, "held": 0}, "only October's own days count"
    days = {d["date"]: d for week in month["weeks"] for d in week}
    assert days[date(2026, 9, 30)]["level"] == "rest" and not days[date(2026, 9, 30)]["in_month"]
    assert max(asked) == TODAY and days[TODAY]["is_today"]
    assert all(days[d]["level"] is None for d in days if d > TODAY)


def test_a_month_after_today_works_out_nothing(monkeypatch):
    asked = _decisions(monkeypatch, {})
    month = lw.calendar(None, TODAY, 2026, 12)
    assert month["month"] == 12 and asked == [], "a month after today asks for no day"
    assert all(d["level"] is None for week in month["weeks"] for d in week)
