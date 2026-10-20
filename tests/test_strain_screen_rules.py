"""services/strain_screen.py: the Strain drill-down's rules, moved out of
app.py on 2026-10-19 (moves HOME-20 to HOME-24) so the phone's API returns the
same. tests/test_strain_screen.py renders app.py's own region block over them.

What this pins: the region panel is computed as of the day shown; its fields
(fills, the overall's tick, the regions' total, the share's heading, the
thin-sample caveat, the ceiling) come from one function; the ACWR ceiling is
read from rules.STAGE_CONSTRAINTS with no copied default (Key Rule 3); the
strain source is named, or nothing is said; a rest day's label says 7D AVG.
"""

from __future__ import annotations

from datetime import date, timedelta

from services import dashboard, hr_load, rules
from services import strain_regions as sr
from services import strain_screen as ss

D = date(2026, 10, 15)


def _row(day: date, **kw) -> dict:
    row = {"date": day.isoformat(), "upper_body": 50.1, "core": 47.2,
           "lower_body": 107.3, "unattributed": 0.0, "total_au": 204.6,
           "regions_known": True}
    row.update(kw)
    return row


def test_the_ceiling_comes_from_the_rules_and_an_unknown_stage_names_none():
    assert ss.acwr_ceiling(2) == rules.STAGE_CONSTRAINTS[2]["acwr_ceiling"]
    assert ss.acwr_ceiling(None) is None
    assert ss.acwr_ceiling(99) is None          # never a copied 1.3


def test_the_region_data_is_computed_as_of_the_day_shown(monkeypatch):
    asked = {}
    real = sr.region_acwr

    def recording(rows, stage=1, today=None, stage_start=None):
        asked["today"], asked["stage_start"] = today, stage_start
        return real(rows, stage, today=today, stage_start=stage_start)

    monkeypatch.setattr(sr, "region_acwr", recording)
    start = date(2026, 10, 1)
    data = ss.region_data({"rows": [_row(D)]}, 2, D, start,
                          {"strain": 14.5, "strain_is_rolling": False}, show_week=False)
    assert asked == {"today": D, "stage_start": start}
    assert data["has_split"] and data["can_show_window"] is False


def test_a_rest_day_offers_its_week_only_when_the_week_had_load():
    rows = [_row(D - timedelta(days=2))]
    rolling = {"strain": 8.0, "strain_is_rolling": True}
    shown = ss.region_data({"rows": rows}, 2, D, None, rolling, show_week=True)
    assert shown["can_show_window"] and shown["window"] == "week"
    hidden = ss.region_data({"rows": rows}, 2, D, None, rolling, show_week=False)
    assert hidden["can_show_window"] and not hidden["has_split"]
    empty = ss.region_data({"rows": []}, 2, D, None, rolling, show_week=True)
    assert empty["can_show_window"] is False


def test_an_empty_panel_says_which_kind_of_empty():
    assert ss.region_panel(ss.empty_region_data(True), 8.0, 2) == {
        "state": "empty", "reason": "rolling", "unmapped_names": []}
    no_split = ss.region_panel({"has_split": False, "is_rolling": False,
                                "unmapped_names": ["Sun Salutation"]}, None, 2)
    assert (no_split["reason"], no_split["unmapped_names"]) == ("no_split", ["Sun Salutation"])


def test_a_split_panel_carries_its_fills_tick_total_and_ceiling():
    snapshot = {"strain": 14.5, "strain_is_rolling": False}
    data = dashboard.compute_region_strain_snapshot(D, [_row(D)], 2, overall_snapshot=snapshot)
    panel = ss.region_panel(data, 14.5, 2)
    assert panel["state"] == "split" and not panel["week"]
    assert [r["id"] for r in panel["regions"]] == list(sr.REGIONS)
    for region in panel["regions"]:
        assert region["fill_pct"] == min(100.0, region["strain"] / 21.0 * 100.0)
        assert region["strain"] <= 14.5                     # never above the overall
    assert panel["tick_pct"] == 14.5 / 21.0 * 100.0
    assert panel["regions_total"] > 14.5                     # the strains do not add
    assert panel["mapped_only"] is False and panel["ceiling"] == ss.acwr_ceiling(2)
    assert round(sum(r["au_pct"] for r in panel["regions"]), 6) == 100.0


def test_a_partly_unmapped_day_says_its_share_is_of_the_mapped_load():
    row = _row(D, unattributed=40.0, total_au=244.6)
    data = dashboard.compute_region_strain_snapshot(
        D, [row], 2, overall_snapshot={"strain": 14.5, "strain_is_rolling": False})
    panel = ss.region_panel(data, 14.5, None)
    assert panel["mapped_only"] and panel["unattributed_pct"] > 0
    assert panel["ceiling"] is None


def test_the_strain_source_is_named_or_nothing_is_said():
    assert ss.strain_source({}) is None
    assert ss.strain_source({"strain_source": hr_load.SOURCE_NONE}) is None
    rpe = ss.strain_source({"strain_source": hr_load.SOURCE_RPE, "strain_source_label": "RPE"})
    assert rpe == {"kind": "rpe", "label": ss.SOURCE_WORDS[hr_load.SOURCE_RPE],
                   "hr_rows": [], "blend": None}
    hr = ss.strain_source({
        "strain_source": hr_load.SOURCE_BLENDED, "strain_source_label": "Heart rate + RPE",
        "hr_detail": {"edwards_load": 96, "avg_hr": 121, "max_hr": 158, "hr_max_used": 186,
                      "banister_trimp": 74.2, "zone_minutes": {2: 14, 1: 20}},
        "strain_hr_only": 11.8, "strain_rpe_only": 10.9})
    assert hr["kind"] == "hr"
    # In plain words (the owner, 2026-10-20): every zone with its heart rates, no cross-check.
    rows = dict(hr["hr_rows"])
    assert hr["label"] == "Your watch's heart rate and your session rating"
    assert rows["Average heart rate"] == "121 bpm" and rows["Highest heart rate"] == "158 bpm"
    assert rows["Zone 1, very easy (93-112 bpm)"] == "20 min"
    assert rows["Zone 2, easy (112-130 bpm)"] == "14 min"
    assert rows["Zone 5, very hard (167-186 bpm)"] == "0 min"
    assert rows["Heart-rate load (minutes × zone number)"] == "96"
    assert rows["Zones use your top heart rate"] == "186 bpm"
    assert not any("TRIMP" in name or "Edwards" in name for name in rows)
    assert hr["blend"] == (11.8, 10.9, int(hr_load.HR_BLEND_WEIGHT * 100))


def test_a_zone_under_a_minute_says_so_and_unknown_limits_leave_the_words():
    hr = ss.strain_source({
        "strain_source": hr_load.SOURCE_HR,
        "hr_detail": {"edwards_load": 12.4, "avg_hr": None, "max_hr": 150.0,
                      "zone_minutes": {"5": 0.2}}})
    rows = dict(hr["hr_rows"])
    assert rows["Zone 5, very hard"] == "under 1 min"
    assert rows["Average heart rate"] == "—"
    assert "Zones use your top heart rate" not in rows


def test_a_rest_days_label_says_7d_avg():
    assert ss.strain_labels(True, "2026-10-15") == ("STRAIN  ·  7D AVG", "STRAIN · 7D AVG")
    assert ss.strain_labels(False, "TODAY") == ("STRAIN", "STRAIN · TODAY")
    assert ss.STRAIN_TOP == 21.0
