"""The carried strain (the owner, 2026-11-12: *"I want to see accumulate strain each
day not the strain of just that day"*; his choices: carried over and fading, half per
day, the same arc and words).

The Strain card and screen lead with the strain carried into the day: today's own
strain plus each earlier day's, halved for each day back. The day's own strain is the
second line. Display only: Metrics History stores the day's own strain, and the load
ratio reads the day's own load (Key Rule 2b)."""

from __future__ import annotations

from datetime import date, timedelta

from services import dashboard as dash
from services import home

THU = date(2026, 11, 12)


def _days_back(k: int) -> str:
    return (THU - timedelta(days=k)).isoformat()


def test_the_rate_is_half_per_day_over_fourteen_days():
    assert dash.STRAIN_CARRY_PER_DAY == 0.5
    assert dash.STRAIN_CARRY_DAYS == 14


def test_his_week_carries_into_a_rest_day():
    # Mon 9: 15.0, Tue 10: 6.4, Wed 11: 15.6 (his stored strains), Thu 12: rest.
    daily = {_days_back(3): 15.0, _days_back(2): 6.4, _days_back(1): 15.6}
    # 15.6 / 2 + 6.4 / 4 + 15.0 / 8 = 7.8 + 1.6 + 1.875
    assert dash.carried_from_daily(daily, THU) == 11.3
    assert dash.carried_from_daily({**daily, THU.isoformat(): 14.0}, THU) == 25.3, \
        "today's own strain counts in full"


def test_the_carry_stops_after_fourteen_days():
    assert dash.carried_from_daily({_days_back(13): 16.0}, THU) == 0.0   # 16 / 8192
    assert dash.carried_from_daily({_days_back(14): 16_000.0}, THU) == 0.0


def test_carried_strain_adds_each_days_own_strain_at_its_share():
    au = [{"date": _days_back(1), "total_au": 400.0}, {"date": _days_back(3), "total_au": 300.0}]
    out = dash.carried_strain(au, 2, THU)
    yesterday = dash.day_strain(_days_back(1), au, 2)["strain"]
    three_back = dash.day_strain(_days_back(3), au, 2)["strain"]
    assert out["value"] == round(yesterday / 2 + three_back / 8, 1)
    assert [(d["date"], d["share"]) for d in out["days"]] == [
        (THU - timedelta(days=1), 0.5), (THU - timedelta(days=3), 0.125)], "newest first"
    assert out["days"][0]["carried"] == round(yesterday / 2, 1)


def test_nothing_in_fourteen_days_carries_nothing():
    assert dash.carried_strain([], 2, THU) == {"value": 0.0, "days": []}


def test_the_carried_words_use_the_strain_bands():
    assert dash.carried_strain_meta(11.7)[2] == "Moderate"
    assert dash.carried_strain_meta(23.3)[1:3] == ("23.3", "Strenuous"), "above 21 reads as it is"
    assert dash.carried_strain_meta(0.0)[2] == "Light"
    assert dash.carried_strain_meta(None)[1] == "--"


def test_the_stored_snapshot_keeps_the_days_own_strain():
    au = [{"date": _days_back(1), "total_au": 400.0}]
    snap = dash.compute_daily_metrics_snapshot(THU, [], au, 2)
    assert snap["strain"] == 0.0 and snap["rest_day"], "the day's own: a rest day"
    assert "strain_carried" not in snap, "Metrics History stores the day's own strain"


def _reads(au, stage=2) -> home.HomeReads:
    return home.HomeReads(day=THU, au_rows=au, stage=stage)


def test_the_home_snapshot_carries_and_says_what_it_carries():
    au = [{"date": _days_back(1), "total_au": 400.0}]
    snap = home.snapshot(_reads(au))
    assert snap["strain"] == 0.0
    assert snap["strain_carried"] == round(dash.day_strain(_days_back(1), au, 2)["strain"] / 2, 1)
    assert [d["date"] for d in snap["strain_carried_days"]] == [THU - timedelta(days=1)]


def test_no_stage_carries_nothing():
    snap = home.snapshot(_reads([{"date": _days_back(1), "total_au": 400.0}], stage=None))
    assert snap["strain_carried"] is None and snap["strain_carried_days"] == []
