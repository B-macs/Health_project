"""Insights › Sleep Architecture's counts and the Sync tab's history filters,
moved to services on 2026-10-19 (move INS-6), and fault F12: the "Oura only"
count took every night that was not fused, the watch-only nights included.
"""

from __future__ import annotations

from datetime import date

from services import insights as insights_svc
from services import sleep_architecture as sa
from services import sleep_fusion

ROWS = [
    {"date": "2026-10-10", "source": sleep_fusion.SOURCE_FUSED, "phantom_wake_minutes": 12,
     "master_sleep_hours": 7.1},
    {"date": "2026-10-11", "source": sleep_fusion.SOURCE_FUSED, "phantom_wake_minutes": 30,
     "master_sleep_hours": ""},
    {"date": "2026-10-12", "source": sleep_fusion.SOURCE_OURA_ONLY},
    {"date": "2026-10-13", "source": sleep_fusion.SOURCE_GARMIN_ONLY},
    {"date": "2026-10-14", "source": sleep_fusion.SOURCE_GARMIN_ONLY},
]


def test_each_source_has_its_own_count():
    s = sa.summary(ROWS)
    assert (s["fused"], s["oura_only"], s["watch_only"]) == (2, 1, 2), "F12"
    assert [r["date"] for r in s["fused_rows"]] == ["2026-10-10", "2026-10-11"]
    assert s["median_phantom_wake"] == 30.0, "the upper middle, as the tab always showed"
    assert sa.summary([])["median_phantom_wake"] is None


def test_only_fused_nights_with_hours_reach_the_shadow_report():
    assert sa.fused_hours(ROWS) == {"2026-10-10": 7.1}


def test_the_history_filters_include_both_ends():
    rows = [{"date": f"2026-10-{d:02d}"} for d in (1, 5, 9, 12)]
    assert insights_svc.date_span(rows) == (date(2026, 10, 1), date(2026, 10, 12))
    assert insights_svc.date_span([]) is None
    assert [r["date"] for r in insights_svc.rows_between(rows, date(2026, 10, 5),
                                                         date(2026, 10, 9))] == [
        "2026-10-05", "2026-10-09"]
