"""The Metabolism screen's rules, moved to services/metabolism_screen.py on
2026-10-19 (move INS-2), and fault F11: every rise was coloured amber and
every fall green, which is wrong for fat-free mass and phase angle, and every
derived card printed "Normal" with no check behind it. Made-up readings only.
"""

from __future__ import annotations

from datetime import date, datetime

from services import body_composition as bc
from services import metabolism_screen as ms

TODAY = date(2026, 10, 19)


def _r(day: date, weight: float, pct: float | None = 17.0) -> bc.ScaleReading:
    return bc.ScaleReading(taken_at=datetime(day.year, day.month, day.day, 7, 30),
                           weight_kg=weight, bmi=None, body_fat_pct=pct)


def _scan(day: date, phase: float | None, device: str = "Model A") -> bc.InBodyScan:
    return bc.InBodyScan(taken_at=datetime(day.year, day.month, day.day, 12, 0),
                         weight_kg=80.0, bmi=80.0 / 1.82 ** 2, total_body_water_l=48.0,
                         skeletal_muscle_kg=37.0, ecw_tbw=0.377, phase_angle_deg=phase,
                         device=device)


def test_each_measure_knows_which_way_is_better():
    better = {label: m["better"] for label, m in ms.METRICS.items()}
    assert better == {"Weight": None, "Fat mass": "down", "Fat-free mass": "up",
                      "Body fat percent": "down", "Phase angle": "up",
                      "ECW / TBW ratio": "down"}


def test_a_change_is_coloured_by_its_own_measure():
    assert ms.change_tone(0.6, "up", 1) == "good", "fat-free mass up is good (F11)"
    assert ms.change_tone(0.2, "up", 1) == "good", "phase angle up is good (F11)"
    assert ms.change_tone(0.6, "down", 1) == "bad", "fat up is bad"
    assert ms.change_tone(-0.6, "down", 1) == "good"
    assert ms.change_tone(-0.6, None, 1) == "neutral", "weight is not a goal"
    assert ms.change_tone(0.04, "up", 1) == "flat"
    assert ms.change_tone(None, "up", 1) is None


def test_no_card_carries_a_status():
    groups = ms.analysis(_r(TODAY, 80.0))
    cards = [c for g in groups for c in g["cards"]]
    assert [g["group"] for g in groups] == ["MASS", "ENERGY", "WATER", "RISK"]
    assert all(set(c) == {"name", "value", "dp", "unit", "source"} for c in cards)
    assert {c["source"] for c in cards} == {"measured", "derived", "absent"}
    assert next(c for c in cards if c["name"] == "Weight")["source"] == "measured"
    assert next(c for c in cards if c["name"] == "Basal metabolic rate")["value"] == round(
        370 + 21.6 * 80.0 * 0.83)
    assert [g["group"] for g in ms.analysis(_r(TODAY, 80.0, pct=None))] == ["MASS"]
    assert ms.analysis(None) == []


def test_the_change_is_the_one_the_chart_draws():
    data = {"readings": [_r(date(2026, 9, 20), 81.0), _r(date(2026, 10, 1), 80.0),
                         _r(date(2026, 10, 12), 79.0), _r(date(2026, 10, 15), 79.4)],
            "scans": [], "today": TODAY}
    shown = ms.series(data, "Weight", "month", 0)
    assert shown["points"] == [(date(2026, 10, 1), 80.0), (date(2026, 10, 12), 79.0),
                               (date(2026, 10, 15), 79.4)]
    assert round(shown["change"], 6) == -0.6 and shown["tone"] == "neutral"
    assert shown["can_back"] and not shown["can_forward"]
    september = ms.series(data, "Weight", "month", -1)
    assert september["points"] == [(date(2026, 9, 20), 81.0)]
    assert september["change"] is None, "one reading has no change"
    assert not september["can_back"], "nothing before September"


def test_a_long_gap_is_never_drawn_as_a_line():
    data = {"readings": [_r(date(2026, 1, 1), 80.0), _r(date(2026, 6, 1), 78.0)],
            "scans": [], "today": TODAY}
    assert len(ms.series(data, "Weight", "all", 0)["runs"]) == 2


def test_the_store_is_read_and_a_failed_read_is_said_out_loud():
    class _Repo:
        def get_scale_readings(self):
            return [_r(date(2026, 10, 1), 80.0)]

        def get_inbody_scans(self):
            return [_scan(date(2026, 3, 1), 6.0, "Model A"), _scan(date(2026, 9, 1), 6.1, "Model B")]

        def get_seca_scans(self):
            return []

    data = ms.read_data(_Repo(), TODAY)
    assert data["load_error"] is None and len(data["readings"]) == 1
    assert [s.device for s in data["scans"]] == ["Model B"], "the latest machine only"
    assert data["scans"][0].entered_height_m == bc.TRUE_HEIGHT_M, "corrected to the true height"

    class _Broken:
        def get_scale_readings(self):
            raise RuntimeError("store unreachable")

        def get_inbody_scans(self):
            return []

        def get_seca_scans(self):
            raise RuntimeError("config unreadable")

    broken = ms.read_data(_Broken(), TODAY)
    assert broken["readings"] == [] and "store unreachable" in broken["load_error"]
    assert broken["seca"] == [] and "SECA scans" in broken["load_error"], \
        "a SECA read that failed is said, never shown as no scan"


def test_the_split_and_the_scan_age():
    split = ms.split(_r(TODAY, 80.0, pct=20.0))
    assert (round(split["fat"], 6), round(split["lean"], 6), round(split["fat_pct"], 6)) == (
        16.0, 64.0, 20.0)
    assert ms.split(_r(TODAY, 80.0, pct=None)) is None
    cell = ms.cellular([_scan(date(2026, 10, 9), 6.0)], TODAY)
    assert cell["days_old"] == 10 and cell["device"] == "Model A"
    assert ms.cellular([], TODAY) is None


# ── the progress chart's scale (rebuild Phase 8: moved out of the Streamlit view) ──

def test_the_chart_scale_is_centred_and_never_magnifies_a_quiet_period():
    window = bc.period_window("month", 0, date(2026, 10, 20), date(2026, 7, 1))
    points = [(date(2026, 10, 4), 80.9), (date(2026, 10, 20), 80.6)]
    axis = ms.chart_axis(points, min_span=2.0, dp=1, window=window)
    # The readings span 0.3 kg: the scale is the minimum span, a quarter taller, centred.
    assert axis["hi"] - axis["lo"] == 2.0 * 1.25
    assert (axis["hi"] + axis["lo"]) / 2 == (80.9 + 80.6) / 2
    assert axis["y_labels"] == [f"{axis['hi'] - i / 4 * 2.5:.1f}" for i in range(5)]
    assert axis["x_labels"] == ["1 Oct", "9 Oct", "16 Oct", "23 Oct", "31 Oct"]


def test_a_wide_spread_sets_the_scale_and_a_long_period_names_months():
    window = bc.period_window("year", 0, date(2026, 10, 20), date(2025, 1, 1))
    points = [(date(2026, 2, 1), 85.0), (date(2026, 9, 1), 80.0)]
    axis = ms.chart_axis(points, min_span=2.0, dp=1, window=window)
    assert axis["hi"] - axis["lo"] == 5.0 * 1.25
    assert axis["x_labels"][0] == "Jan 26" and axis["x_labels"][-1] == "Dec 26"


def test_no_reading_has_no_scale():
    window = bc.period_window("week", 0, date(2026, 10, 20), date(2026, 7, 1))
    assert ms.chart_axis([], min_span=2.0, dp=1, window=window) is None


def test_the_streamlit_chart_draws_with_the_engines_scale():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "views" / "insights.py").read_text(encoding="utf-8")
    assert "ms.chart_axis(points, min_span, dp, window)" in source
