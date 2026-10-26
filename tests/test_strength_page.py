"""The phone's Strength page, redone (the owner, 2026-10-20: "Can you review that
page and redo it"; services/strength_screen.trend, area_rows, volume).

One answer carries the whole page, so no part of it waits for a request of its
own. A body area shows a number only once calibration lets it, never the
placeholder 50. The volume never sets an unfinished week against a full one:
the last full week is set against the full week before it, and this week is
shown apart. Made-up numbers only.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from services import strength
from services import strength_screen as ss
from services import tonnage


def _region(region, index=None, displayed=None, confidence=0.0, observations=0):
    return strength.RegionState(
        region=region, index=index, displayed_index=displayed, confidence=confidence,
        share=1 / 3, contribution_points=0.0, contribution_pct=0.0,
        observations=observations, calibrating=confidence < strength.CALIBRATION_EXIT)


def test_an_area_shows_a_number_only_once_calibration_lets_it():
    exit_ = strength.CALIBRATION_EXIT
    rows = ss.area_rows([
        _region("lower_body", index=76.1, displayed=strength.CALIBRATION_INDEX,
                confidence=exit_ * 0.8, observations=33),
        _region("upper_body", index=84.8, displayed=84.8, confidence=0.96, observations=22),
        _region("core"),
    ])
    assert [r["region"] for r in rows] == list(ss.REGION_ORDER), "the page's own order"
    upper, core, lower = rows
    assert upper["state"] == ss.AREA_MEASURED and upper["pct_of_2025"] == 84.8 and upper["lifts"] == 22
    assert lower["state"] == ss.AREA_TOO_FEW and lower["pct_of_2025"] is None, \
        "no number, never the placeholder 50"
    assert lower["progress"] == pytest.approx(0.8)
    assert core["state"] == ss.AREA_NONE and core["pct_of_2025"] is None


def test_core_shows_its_plank_test_apart_from_the_headline():
    hold = {"index": 81.7, "date": date(2026, 10, 19)}
    [core] = ss.area_rows([_region("core")], core_hold=hold)
    assert core["state"] == ss.AREA_HOLD and core["pct_of_2025"] == 81.7
    assert core["hold_date"] == date(2026, 10, 19)


def _week(start, upper=0.0, lower=0.0, days=4, core_seconds=0.0):
    return tonnage.TonnageWeek(
        week_start=start, training_days=days,
        sectors={"upper_body": tonnage.SectorWeek(kg=upper),
                 "core": tonnage.SectorWeek(unloaded_seconds=core_seconds),
                 "lower_body": tonnage.SectorWeek(kg=lower)})


MONDAY = date(2026, 10, 19)


def test_the_last_full_week_is_set_against_the_full_week_before_it():
    series = [_week(MONDAY - timedelta(weeks=2), 3135, 3447.5),
              _week(MONDAY - timedelta(weeks=1), 3172.5, 3150),
              _week(MONDAY, 1000, 725, days=2, core_seconds=84)]
    v = ss.volume(series)
    full = v["last_full"]
    assert full["label"] == "12 Oct" and full["previous_label"] == "5 Oct"
    assert full["kg"] == 6322.5 and full["previous_kg"] == 6582.5
    assert full["delta"] == pytest.approx(-260.0) and full["tone"] == "down"
    assert v["this_week"] == {"label": "19 Oct", "kg": 1725.0, "days": 2}, \
        "this week stands apart: never set against a full week"
    assert [w["current"] for w in v["weeks"]] == [False, False, True]
    assert v["weeks"][0]["total"] == 6582.5 and v["weeks"][0]["upper_body"] == 3135
    assert v["hi"] == tonnage.nice_axis_max(6582.5)
    assert v["unloaded"] == [{"week": "this_week", "area": "core", "text": "1 min 24 s held"}]


def test_without_two_full_weeks_there_is_no_comparison():
    v = ss.volume([_week(MONDAY - timedelta(weeks=1), 100), _week(MONDAY, 50, days=1)])
    assert v["last_full"] is None and v["this_week"]["kg"] == 50.0
    assert ss.volume([])["this_week"] is None


def test_the_trend_carries_each_weeks_measure_and_the_headline_as_it_read():
    data = {"score_series": [
        {"week": MONDAY - timedelta(weeks=1), "measured": 82.0, "level": 85.4, "why": ""},
        {"week": MONDAY, "measured": None, "level": 82.0, "why": ""}]}
    assert ss.trend(data) == [{"label": "12 Oct", "measured": 82.0, "level": 85.4},
                              {"label": "19 Oct", "measured": None, "level": 82.0}]


def test_each_lift_shows_its_own_percent_of_2025():
    """WP-38 (2026-10-26): each lift against its own 2025 best, highest first in
    each body area, with how close the two lifts are."""
    def obs(name, w, r, day):
        return strength.Observation(exercise=name, session_date=date.fromisoformat(day),
                                    weight_kg=w, reps=r, rpe=9.0, effective_reps=r + 1,
                                    e1rm=w * (1 + (r + 1) / 30), within_epley_range=True)
    exercises = {
        "Made-up row": {"index": 72.0, "e1rm_now": 33.0, "e1rm_2025": 45.8, "comparability": 1.0,
                        "region": "upper_body", "observation": obs("Made-up row", 22.5, 12, "2026-10-22")},
        "Made-up hinge": {"index": 64.0, "e1rm_now": 57.3, "e1rm_2025": 89.6, "comparability": 0.7,
                          "region": "lower_body", "observation": obs("Made-up hinge", 40, 12, "2026-10-22")},
        "Made-up press": {"index": 81.0, "e1rm_now": 20.0, "e1rm_2025": 24.7, "comparability": 0.6,
                          "region": "upper_body", "observation": obs("Made-up press", 15, 10, "2026-10-12")},
    }
    rows = ss.lift_rows(exercises)
    assert [r["name"] for r in rows] == ["Made-up press", "Made-up row", "Made-up hinge"]
    press, row, hinge = rows
    assert (row["pct_of_2025"], row["weight_kg"], row["reps"], row["match"]) == (72.0, 22.5, 12, "same")
    assert hinge["match"] == "close" and press["match"] == "machine"
    assert ss.lift_match(0.4) == "rough"
