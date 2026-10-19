"""Insights › Strength's data and rules, moved to services/strength_screen.py
on 2026-10-19 (move INS-1): the readout, the two charts' axes, the work done
without load, and the region cards and bar. Made-up figures only.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from services import strength
from services import strength_screen as ss
from services import tonnage


def _week(day: str, **sectors):
    return tonnage.TonnageWeek(
        week_start=date.fromisoformat(day), training_days=2,
        sectors={r: tonnage.SectorWeek(**sectors.get(r, {})) for r in tonnage.REGIONS})


def _region(region, points, pct, conf, index):
    return SimpleNamespace(region=region, contribution_points=points, contribution_pct=pct,
                           confidence=conf, displayed_index=index)


def test_the_week_label_has_no_leading_zero():
    assert ss.week_label(date(2026, 10, 5)) == "5 Oct"
    assert ss.week_label(date(2026, 10, 19)) == "19 Oct"


def test_the_readout_compares_this_week_with_last():
    data = {"score_series": [{"level": 52.0}, {"level": 54.5}],
            "tonnage": [_week("2026-10-05", upper_body={"kg": 0.0}),
                        _week("2026-10-12", upper_body={"kg": 1200.0})],
            "week_labels": ["5 Oct", "12 Oct"]}
    score = ss.readout(data, "Overall Strength Score")
    assert (score["current"], score["previous"], score["tone"]) == (54.5, 52.0, "up")
    assert score["points"] and score["labels"] == ("12 Oct", "5 Oct")
    upper = ss.readout(data, "Upper Body Tonnage")
    assert upper["delta"] == 1200.0 and upper["pct"] is None, "last week was zero"
    alone = ss.readout({"score_series": [{"level": 50.0}], "tonnage": [],
                        "week_labels": ["12 Oct"]}, "Overall Strength Score")
    assert alone["delta"] is None and alone["tone"] is None


def test_the_score_axis_falls_on_whole_gridlines():
    lo, hi = ss.score_axis([{"measured": 61.2, "level": 54.5}, {"measured": None, "level": 55.0}])
    assert lo == 40.0 and (hi - lo) % 20 == 0 and hi >= 80.0
    assert ss.score_axis([]) == (0.0, 100.0)


def test_the_tonnage_axis_and_the_work_without_load():
    series = [_week("2026-09-28", core={"unloaded_seconds": 120.0}),
              _week("2026-10-05", core={"unloaded_seconds": 245.0, "unloaded_reps": 36.0},
                    upper_body={"kg": 950.0})]
    values, top = ss.tonnage_axis(series, "upper_body")
    assert values == [0.0, 950.0] and top >= 950.0
    assert ss.unloaded_lines(series, "core") == [
        ("This week", "4 min 5 s held, 36 reps"), ("Last week", "2 min held")]
    assert ss.unloaded_lines(series, "upper_body") == []


def test_a_region_card_prints_a_dash_without_a_measurement():
    exit_ = strength.CALIBRATION_EXIT
    regions = [_region("lower_body", 30.0, 40.0, exit_, 81.2),
               _region("core", 15.0, 20.0, 0.0, None),
               _region("upper_body", 30.0, 40.0, exit_ / 2, 72.1)]
    cards = {c["region"]: c for c in ss.region_cards(regions)}
    assert [c["region"] for c in ss.region_cards(regions)] == list(ss.REGION_ORDER)
    assert cards["core"]["index_text"] == "—" and cards["core"]["off"] and cards["core"]["tone"] == "bad"
    assert cards["upper_body"]["band"] == "provisional" and cards["upper_body"]["tone"] == "warn"
    assert cards["lower_body"]["band"] == "established" and cards["lower_body"]["tone"] == "good"
    held = {c["region"]: c for c in ss.region_cards(regions, {"index": 63.4,
                                                              "date": date(2026, 10, 19)})}
    assert held["core"]["index_label"] == "Hold time" and held["core"]["index_text"] == "63.4"
    assert held["core"]["band"] == "provisional · hold time · 19 Oct" and not held["core"]["off"]
    assert [p["region"] for p in ss.split(regions)] == list(ss.REGION_ORDER)


def test_a_failed_read_is_said_out_loud():
    class _Broken:
        def get_all_training_exercises_raw(self):
            raise RuntimeError("store unreachable")

    import patient_profile
    import strength_baselines as sb
    reference = {"peaks": sb.PEAKS_2025, "region_prior": sb.REGION_PRIOR, "pr_rir": sb.PR_RIR,
                 "anchor_date": sb.ANCHOR_DATE, "anchor_value": sb.ANCHOR_VALUE,
                 "hold_baselines": sb.HOLD_BASELINES_2025,
                 "imbalances": patient_profile.PROFILE.get("imbalances", {})}
    assert set(reference) == set(ss.REFERENCE_KEYS)
    data = ss.read_data(_Broken(), date(2026, 10, 19), reference)
    assert "store unreachable" in data["load_error"]
    assert len(data["tonnage"]) == ss.WEEKS and data["imbalance_count"] is not None
