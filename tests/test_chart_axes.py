"""Tests for the Home drill-down chart axes and clickable points.

Covers the pure half in services/dashboard.py (tick values, tick positions,
which slot a click resolves to, what a selected point says) and the invariants
of the renderers in styles.py that make those numbers land where the labels
claim they do.

The property that matters most and is pinned hardest: a gridline, its label
and the point it explains must all be computed from the SAME bounds. Every
earlier version of these charts scaled the line to the data's raw min/max, so
the moment the axis was rounded the two drifted apart — an axis whose labels
are a few pixels off its own gridlines is worse than no axis, because it is
confidently wrong rather than merely absent.
"""

from datetime import date, timedelta

import pytest

from services import dashboard

# styles.py imports streamlit; that is fine here (it is a UI module, not a
# services one) and tests/test_no_streamlit_in_services.py still guards the
# rule that matters.
import styles


# ─── value_axis: nice bounds and ticks ───────────────────────────────────────

def test_value_axis_returns_none_when_nothing_is_numeric():
    assert dashboard.value_axis([None, None, ""]) is None
    assert dashboard.value_axis([]) is None


def test_value_axis_bounds_always_contain_the_data():
    for values in ([57, 61, 72, 88, 91], [2.6, 14.1], [0, 21], [48, 49]):
        axis = dashboard.value_axis(values)
        assert axis["lo"] <= min(values)
        assert axis["hi"] >= max(values)


def test_value_axis_ticks_span_lo_to_hi_at_a_constant_step():
    axis = dashboard.value_axis([30, 44, 58, 70])
    assert axis["ticks"][0] == axis["lo"]
    assert axis["ticks"][-1] == pytest.approx(axis["hi"])
    gaps = [b - a for a, b in zip(axis["ticks"], axis["ticks"][1:])]
    assert all(g == pytest.approx(axis["step"]) for g in gaps)


def test_value_axis_ticks_stay_on_the_grid_when_a_bound_is_clamped():
    """Strain's cap of 21 is not a multiple of the step. The axis top is 21,
    but every tick must still be a round number — anchoring the sequence to
    `lo`/`hi` instead of the grid would give 1, 6, 11, 16, 21."""
    axis = dashboard.value_axis([0.0, 21.0], floor=0.0, cap=21.0)
    assert axis["hi"] == 21.0
    assert axis["ticks"] == [0.0, 5.0, 10.0, 15.0, 20.0]


def test_value_axis_every_tick_is_inside_the_bounds():
    for values in ([0, 21], [57, 91], [2.6, 14.1], [48, 49], [-3, 10]):
        axis = dashboard.value_axis(values, floor=0.0, cap=100.0)
        assert all(axis["lo"] <= t <= axis["hi"] for t in axis["ticks"])


def test_value_axis_step_is_a_nice_number():
    for values in ([57, 91], [2.6, 14.1], [48, 56], [0.4, 0.9]):
        step = dashboard.value_axis(values)["step"]
        mantissa = step / 10 ** round(__import__("math").log10(step) // 1)
        assert round(mantissa, 6) in (1.0, 2.0, 5.0, 10.0)


def test_value_axis_rounds_to_the_nearest_rung_not_up():
    """34 points over 3 intervals wants a step of ~11.3. Ceiling-rounding gives
    20 and a 40-100 axis for data living in 57-91; nearest gives 10 and 50-100.
    This is the difference the whole _tick_step docstring is about."""
    axis = dashboard.value_axis([57, 61, 72, 88, 91], floor=0.0, cap=100.0)
    assert axis["step"] == 10.0
    assert (axis["lo"], axis["hi"]) == (50.0, 100.0)


def test_value_axis_never_exceeds_max_ticks():
    for values in ([1, 2, 3, 97], [0, 0.5], [1000, 9999], [48, 49]):
        assert len(dashboard.value_axis(values, max_ticks=6)["ticks"]) <= 7


def test_value_axis_floor_and_cap_clamp_the_bounds():
    axis = dashboard.value_axis([2.6, 14.1], floor=0.0, cap=21.0)
    assert axis["lo"] >= 0.0
    assert axis["hi"] <= 21.0


def test_value_axis_floor_does_not_clip_the_data():
    """A floor bounds the AXIS, never the series — a value below it must still
    be inside [lo, hi] or the plot would draw it off the chart."""
    axis = dashboard.value_axis([-3.0, 10.0], floor=0.0)
    assert axis["lo"] <= -3.0


def test_value_axis_flat_series_gets_a_band_not_a_zero_height_axis():
    axis = dashboard.value_axis([12.0, 12.0, 12.0])
    assert axis["hi"] > axis["lo"]
    assert axis["lo"] < 12.0 < axis["hi"]


def test_value_axis_ignores_booleans():
    """bool is an int subclass; a True slipping into a score series would
    silently drag the axis down to 0-1."""
    assert dashboard.value_axis([True, False]) is None


# ─── Tick positions ──────────────────────────────────────────────────────────

def test_value_axis_labels_are_fractions_from_the_top():
    axis = dashboard.value_axis([0, 100], floor=0.0, cap=100.0)
    labels = dashboard.value_axis_labels(axis)
    assert labels[0][0] == pytest.approx(1.0)      # lowest tick, bottom
    assert labels[-1][0] == pytest.approx(0.0)     # highest tick, top
    assert all(0.0 <= f <= 1.0 for f, _ in labels)


def test_value_axis_labels_of_none_is_empty():
    assert dashboard.value_axis_labels(None) == []


def test_format_axis_value_uses_only_the_precision_the_step_justifies():
    assert dashboard.format_axis_value(60.0, 10.0) == "60"
    assert dashboard.format_axis_value(48.5, 0.5) == "48.5"
    assert dashboard.format_axis_value(0.25, 0.05) == "0.25"


def test_x_axis_labels_always_include_both_ends():
    labels = dashboard.x_axis_labels([str(i) for i in range(30)], max_ticks=5)
    assert labels[0][0] == 0.0
    assert labels[-1][0] == 1.0
    assert len(labels) <= 5


def test_x_axis_labels_positions_match_their_own_index():
    src = ["a", "b", "c", "d", "e"]
    for frac, text in dashboard.x_axis_labels(src, max_ticks=5):
        assert src[round(frac * (len(src) - 1))] == text


def test_x_axis_labels_drops_blanks_without_moving_the_rest():
    labels = dashboard.x_axis_labels(["a", "", "c"], max_ticks=3)
    assert labels == [(0.0, "a"), (1.0, "c")]


def test_x_axis_labels_handles_short_inputs():
    assert dashboard.x_axis_labels([]) == []
    assert dashboard.x_axis_labels(["only"]) == [(0.0, "only")]


# ─── Gridlines line up with their labels ─────────────────────────────────────

def test_gutter_labels_and_plot_share_one_mapping():
    """The invariant the whole feature rests on: the container-space fraction
    axis_gutter_labels puts a tick label at is exactly where plot_y_fraction
    puts that tick's VALUE. If these two ever disagree, every chart on the
    three drill-downs is mislabelled and nothing on screen says so."""
    axis = dashboard.value_axis([45, 52, 60, 72], floor=0.0)
    height = 92
    gutter = styles.axis_gutter_labels(axis, height)
    for (frac, _text), tick in zip(gutter, axis["ticks"]):
        assert frac == pytest.approx(
            styles.plot_y_fraction(tick, axis["lo"], axis["hi"], height))


def test_plot_y_fraction_is_inside_the_padded_plot():
    axis = dashboard.value_axis([10, 90])
    for v in (axis["lo"], axis["hi"], 50):
        f = styles.plot_y_fraction(v, axis["lo"], axis["hi"], 92)
        assert 0.0 <= f <= 1.0


def test_plot_y_fraction_is_monotonic_downwards():
    """Higher value, smaller fraction — y grows downward on screen."""
    a = styles.plot_y_fraction(80, 0, 100, 92)
    b = styles.plot_y_fraction(20, 0, 100, 92)
    assert a < b


# ─── hit_bands ───────────────────────────────────────────────────────────────

def test_hit_bands_cover_the_full_width_without_gaps_or_overlap():
    bands = dashboard.hit_bands(37, max_bands=12)
    assert bands[0][0] == 0.0
    assert bands[-1][0] + bands[-1][1] == pytest.approx(1.0)
    for (l1, w1, _), (l2, _, _) in zip(bands, bands[1:]):
        assert l1 + w1 == pytest.approx(l2)


def test_hit_bands_one_per_slot_when_under_the_cap():
    bands = dashboard.hit_bands(7, max_bands=48)
    assert [i for _, _, i in bands] == list(range(7))


def test_hit_bands_never_exceeds_max_bands():
    assert len(dashboard.hit_bands(1200, max_bands=48)) == 48


def test_hit_band_indices_are_in_range_and_ascending():
    bands = dashboard.hit_bands(1200, max_bands=48)
    idx = [i for _, _, i in bands]
    assert all(0 <= i < 1200 for i in idx)
    assert idx == sorted(idx)


def test_hit_bands_of_nothing_is_empty():
    assert dashboard.hit_bands(0) == []
    assert dashboard.hit_bands(-4) == []


def test_trend_point_lands_inside_its_own_band():
    """A trend point sits at i/(n-1) while its band spans [i/n, (i+1)/n). The
    two are not the same arithmetic, and the dot must still fall inside the
    band that selects it or clicking a point would open its neighbour."""
    for n in (2, 7, 30, 48):
        bands = dashboard.hit_bands(n, max_bands=n)
        for i in range(n):
            x = i / (n - 1)
            left, width, idx = bands[i]
            assert idx == i
            assert left - 1e-9 <= x <= left + width + 1e-9


# ─── Runs ────────────────────────────────────────────────────────────────────

def test_merge_runs_collapses_identical_neighbours():
    assert dashboard.merge_runs("11223") == [(0, 2, "1"), (2, 4, "2"), (4, 5, "3")]


def test_merge_runs_covers_every_slot_exactly_once():
    codes = "1112223344444111"
    runs = dashboard.merge_runs(codes)
    assert runs[0][0] == 0 and runs[-1][1] == len(codes)
    assert sum(e - s for s, e, _ in runs) == len(codes)


def test_merge_runs_of_empty_is_empty():
    assert dashboard.merge_runs("") == []
    assert dashboard.merge_runs(None) == []


def test_run_at_returns_the_whole_run_containing_the_index():
    codes = "1112223344444111"
    assert dashboard.run_at(codes, 4) == (3, 6, "2")
    assert dashboard.run_at(codes, 0) == (0, 3, "1")
    assert dashboard.run_at(codes, len(codes) - 1) == (13, 16, "1")


def test_run_at_agrees_with_merge_runs_for_every_slot():
    codes = "112223344444111223"
    for s, e, c in dashboard.merge_runs(codes):
        for i in range(s, e):
            assert dashboard.run_at(codes, i) == (s, e, c)


def test_run_at_out_of_range_is_none():
    assert dashboard.run_at("111", 3) is None
    assert dashboard.run_at("111", -1) is None
    assert dashboard.run_at("", 0) is None


# ─── Point selection round trip ──────────────────────────────────────────────

def test_point_selection_round_trips():
    for chart, index in (("hist", 0), ("ohrv", 179), ("hyp", 1042)):
        key = dashboard.point_selection_key(chart, index)
        assert dashboard.parse_point_selection(key) == (chart, index)


@pytest.mark.parametrize("raw", [
    None, "", "hist", "hist:", ":4", "hist:abc", "hist:1.5", 12, [], "  :3",
])
def test_parse_point_selection_rejects_anything_malformed(raw):
    """The selection is a URL query parameter, so it is user-editable by
    construction; nothing downstream may assume it is well formed."""
    assert dashboard.parse_point_selection(raw) == (None, None)


def test_parse_point_selection_accepts_a_negative_index():
    """Parsing and range-checking are separate jobs — -5 parses, and every
    consumer then rejects it against its own series length."""
    assert dashboard.parse_point_selection("hist:-5") == ("hist", -5)


# ─── trend_point_detail ──────────────────────────────────────────────────────

def _week():
    return [date(2026, 7, 20) + timedelta(days=i) for i in range(7)]


def test_trend_point_detail_out_of_range_is_none():
    dates, values = _week(), [1, 2, 3, 4, 5, 6, 7]
    assert dashboard.trend_point_detail(dates, values, 7) is None
    assert dashboard.trend_point_detail(dates, values, -1) is None
    assert dashboard.trend_point_detail([], [], 0) is None


def test_trend_point_detail_open_date_is_the_point_s_own_day():
    detail = dashboard.trend_point_detail(_week(), [1, 2, 3, 4, 5, 6, 7], 3)
    assert detail["open_date"] == "2026-07-23"
    assert detail["title"] == "2026-07-23"


def test_trend_point_detail_compares_against_the_last_REAL_reading():
    """Not against index-1: with a gap, "change vs previous day" would be a
    change against nothing. The row has to name how far back it reached."""
    values = [50, None, None, 62]
    rows = dashboard.trend_point_detail(_week()[:4], values, 3)["rows"]
    change = next(r for r in rows if r["label"].startswith("Change"))
    assert change["value"] == "+12"
    assert "3 days earlier" in change["label"]
    assert "2026-07-20" in change["label"]


def test_trend_point_detail_adjacent_reading_says_previous_day():
    rows = dashboard.trend_point_detail(_week()[:2], [50, 44], 1)["rows"]
    change = next(r for r in rows if r["label"].startswith("Change"))
    assert change["label"] == "Change vs previous day"
    assert change["value"] == "-6"


def test_trend_point_detail_on_a_missing_day_says_so_and_omits_the_change():
    rows = dashboard.trend_point_detail(_week()[:3], [50, None, 60], 1)["rows"]
    assert rows[0]["value"] == "No reading"
    assert not any(r["label"].startswith("Change") for r in rows)


def test_trend_point_detail_window_stats_ignore_missing_days():
    rows = dashboard.trend_point_detail(_week()[:4], [10, None, 20, 30], 3)["rows"]
    avg = next(r for r in rows if r["label"].startswith("Window average"))
    assert "3 readings" in avg["label"]
    assert avg["value"] == "20"


def test_trend_point_detail_honours_unit_and_decimals():
    rows = dashboard.trend_point_detail(
        _week()[:2], [7.75, 9.25], 1, unit="ms", decimals=1, label="HRV")["rows"]
    assert rows[0] == {"label": "HRV", "value": "9.2 ms"}


def test_trend_point_detail_accepts_iso_strings_as_dates():
    detail = dashboard.trend_point_detail(["2026-07-20", "2026-07-21"], [1, 2], 1)
    assert detail["open_date"] == "2026-07-21"


# ─── metrics_history_rows ────────────────────────────────────────────────────

def test_metrics_history_rows_excludes_the_metric_being_inspected():
    row = {"readiness_score": 61, "sleep_score": 74, "sleep_pct": 88, "strain": 9.2}
    labels = [r["label"] for r in dashboard.metrics_history_rows(row, exclude="readiness_score")]
    assert "Readiness" not in labels
    assert labels == ["Sleep Score", "Sleep vs need", "Strain"]


def test_metrics_history_rows_drops_absent_metrics_rather_than_dashing_them():
    row = {"readiness_score": 61, "sleep_score": None, "sleep_pct": None, "strain": 9.2}
    rows = dashboard.metrics_history_rows(row, exclude="readiness_score")
    assert [r["label"] for r in rows] == ["Strain"]


def test_metrics_history_rows_of_nothing_is_empty():
    assert dashboard.metrics_history_rows(None) == []
    assert dashboard.metrics_history_rows({}) == []


def test_metrics_history_rows_keeps_a_stored_zero():
    """0 is a real reading here — a logged session with no load gives strain 0
    — and the same `or None` slip this guards against has already been fixed
    once in Repository.get_metrics_history."""
    rows = dashboard.metrics_history_rows({"strain": 0}, exclude="readiness_score")
    assert rows == [{"label": "Strain", "value": "0.0"}]


# ─── Overnight series and its points ─────────────────────────────────────────

_PAYLOAD = {
    "interval": 300.0,
    "timestamp": "2026-07-28T23:00:00+01:00",
    "items": [None, None] + [50 + (i % 11) for i in range(100)],
}


def test_overnight_series_carries_the_raw_index_of_every_plotted_point():
    s = dashboard.overnight_series(_PAYLOAD, max_points=20)
    assert len(s["indices"]) == len(s["values"]) == 20
    assert s["indices"] == sorted(s["indices"])
    assert s["values"] == [_PAYLOAD["items"][i] for i in s["indices"]]


def test_overnight_series_without_downsampling_indexes_one_to_one():
    s = dashboard.overnight_series(_PAYLOAD)
    assert s["indices"] == list(range(len(_PAYLOAD["items"])))


def test_overnight_series_keeps_interval_and_timestamp():
    s = dashboard.overnight_series(_PAYLOAD)
    assert s["interval"] == 300.0
    assert s["timestamp"] == "2026-07-28T23:00:00+01:00"


def test_overnight_series_empty_payload_still_has_the_new_keys():
    for payload in (None, {}, {"items": []}, "nonsense"):
        s = dashboard.overnight_series(payload)
        assert s["count"] == 0
        assert s["indices"] == [] and s["interval"] is None


def test_overnight_series_stats_exclude_the_null_pad():
    s = dashboard.overnight_series(_PAYLOAD)
    assert s["low"] == 50 and s["high"] == 60
    assert s["count"] == 100


def test_overnight_axis_labels_are_clock_times_from_the_series_own_clock():
    s = dashboard.overnight_series(_PAYLOAD)
    labels = dashboard.overnight_axis_labels(s, max_ticks=4)
    assert labels[0] == (0.0, "23:00")
    # index 101 × 300 s = 8h25m after 23:00 → 07:25 the next morning.
    assert labels[-1][0] == 1.0 and labels[-1][1] == "07:25"


def test_overnight_axis_labels_absent_without_a_timestamp():
    s = dashboard.overnight_series({"items": [1, 2, 3]})
    assert dashboard.overnight_axis_labels(s) == []


def test_overnight_point_detail_titles_with_the_sample_s_clock_time():
    s = dashboard.overnight_series(_PAYLOAD)
    detail = dashboard.overnight_point_detail(s, 12, unit="bpm")
    assert detail["title"] == "00:00"          # 23:00 + 12 samples × 5 min
    assert detail["rows"][0]["label"] == "Reading"


def test_overnight_point_detail_reports_the_value_at_that_index():
    s = dashboard.overnight_series(_PAYLOAD)
    detail = dashboard.overnight_point_detail(s, 20, unit="bpm")
    assert detail["rows"][0]["value"] == f"{_PAYLOAD['items'][20]:.0f} bpm"


def test_overnight_point_detail_on_a_gap_says_not_measured():
    s = dashboard.overnight_series(_PAYLOAD)
    detail = dashboard.overnight_point_detail(s, 0, unit="bpm")
    assert detail["rows"] == [{"label": "Reading", "value": "Not measured"}]


def test_overnight_point_detail_out_of_range_is_none():
    s = dashboard.overnight_series(_PAYLOAD)
    assert dashboard.overnight_point_detail(s, 9999, unit="bpm") is None
    assert dashboard.overnight_point_detail(s, -1, unit="bpm") is None
    assert dashboard.overnight_point_detail(None, 0, unit="bpm") is None


# ─── Strip segments ──────────────────────────────────────────────────────────

_STAGES = {"1": "Deep", "2": "Light", "3": "REM", "4": "Awake"}
_CODES = "2" * 40 + "1" * 60 + "2" * 30 + "3" * 20 + "4" * 10 + "2" * 40


def test_segment_point_detail_describes_the_run_not_the_slot():
    detail = dashboard.segment_point_detail(
        _CODES, 70, start_iso="2026-07-28T23:00:00+01:00",
        total_minutes=len(_CODES), labels=_STAGES)
    assert detail["title"] == "Deep"
    values = {r["label"]: r["value"] for r in detail["rows"]}
    assert values["Stage"] == "Deep"
    assert values["From"] == "23:40 – 00:40"
    assert values["Duration"] == "1h 00m"


def test_segment_point_detail_totals_every_run_of_that_class():
    detail = dashboard.segment_point_detail(
        _CODES, 5, start_iso="2026-07-28T23:00:00+01:00",
        total_minutes=len(_CODES), labels=_STAGES)
    values = {r["label"]: r["value"] for r in detail["rows"]}
    # Light appears three times: 40 + 30 + 40 = 110 minutes.
    assert values["Total Light tonight"] == "1h 50m"


def test_segment_point_detail_share_of_night_matches_the_run_length():
    # index 140 is inside the 20-slot REM run (40 Light + 60 Deep + 30 Light).
    detail = dashboard.segment_point_detail(
        _CODES, 140, start_iso=None, total_minutes=None, labels=_STAGES)
    rows = {r["label"]: r["value"] for r in detail["rows"]}
    assert rows["Stage"] == "REM"
    assert rows["Share of night"] == f"{20 / len(_CODES) * 100:.1f} %"


def test_segment_point_detail_without_a_window_omits_the_clock_rows():
    detail = dashboard.segment_point_detail(
        _CODES, 10, start_iso=None, total_minutes=None, labels=_STAGES)
    labels = [r["label"] for r in detail["rows"]]
    assert "From" not in labels and "Duration" not in labels
    assert labels[0] == "Stage"


def test_segment_point_detail_derives_slot_width_from_the_window():
    """The two strips run on different grids (30-second hypnogram, per-minute
    fused master, 30-second movement) and are only aligned because both are
    stretched across the same window. Deriving the slot width keeps the
    reported times consistent with what is drawn."""
    thirty_sec = "1" * 120                      # 120 slots over a 60-minute window
    detail = dashboard.segment_point_detail(
        thirty_sec, 0, start_iso="2026-07-28T23:00:00+01:00",
        total_minutes=60, labels=_STAGES)
    values = {r["label"]: r["value"] for r in detail["rows"]}
    assert values["From"] == "23:00 – 00:00"
    assert values["Duration"] == "1h 00m"


def test_segment_point_detail_out_of_range_is_none():
    assert dashboard.segment_point_detail(
        _CODES, 99999, start_iso=None, total_minutes=None, labels=_STAGES) is None
    assert dashboard.segment_point_detail(
        "", 0, start_iso=None, total_minutes=None, labels=_STAGES) is None


def test_segment_point_detail_unknown_code_does_not_raise():
    detail = dashboard.segment_point_detail(
        "999", 1, start_iso=None, total_minutes=None, labels=_STAGES)
    assert detail["title"] == "Segment"


# ─── Window helpers ──────────────────────────────────────────────────────────

def test_minutes_between_measures_absolute_instants():
    """Not wall-clock strings: Oura has been seen storing one night's two ends
    under different UTC offsets, and string arithmetic reads that as an hour
    that never happened."""
    assert dashboard.minutes_between(
        "2026-07-28T23:00:00+01:00", "2026-07-29T07:00:00+02:00") == 420.0


def test_minutes_between_rejects_unusable_input():
    for a, b in (("", "2026-07-29T07:00:00+01:00"),
                 ("2026-07-28T23:00:00+01:00", None),
                 ("nonsense", "2026-07-29T07:00:00+01:00"),
                 ("2026-07-28T23:00:00+01:00", "2026-07-28T23:00:00"),   # mixed tz
                 ("2026-07-29T07:00:00+01:00", "2026-07-28T23:00:00+01:00")):  # backwards
        assert dashboard.minutes_between(a, b) is None


def test_clock_axis_labels_span_the_window_evenly():
    labels = dashboard.clock_axis_labels("2026-07-28T23:00:00+01:00", 480, max_ticks=5)
    assert [f for f, _ in labels] == [0.0, 0.25, 0.5, 0.75, 1.0]
    assert [t for _, t in labels] == ["23:00", "01:00", "03:00", "05:00", "07:00"]


def test_clock_axis_labels_absent_without_a_window():
    assert dashboard.clock_axis_labels(None, 480) == []
    assert dashboard.clock_axis_labels("2026-07-28T23:00:00+01:00", 0) == []
    assert dashboard.clock_axis_labels("2026-07-28T23:00:00+01:00", None) == []


def test_format_axis_date_handles_both_date_objects_and_iso_strings():
    assert dashboard.format_axis_date(date(2026, 8, 3)) == "03 Aug"
    assert dashboard.format_axis_date("2026-08-03") == "03 Aug"
    assert dashboard.format_axis_date("not a date") == "not a date"
    assert dashboard.format_axis_date(date(2026, 8, 3), "%a") == "Mon"


# ─── Renderers ───────────────────────────────────────────────────────────────

def test_trend_chart_svg_uses_the_bounds_it_is_given():
    """The whole reason lo/hi are parameters: the plot must be scaled to the
    ROUNDED axis, not to its own min/max, or the line and the gridlines
    describe different scales."""
    svg = styles.trend_chart_svg([50, 100], height=100, lo=0, hi=100)
    assert 'viewBox="0 0 100 100"' in svg
    # 100 sits at the top of the padded plot, 50 halfway down it.
    assert f"{styles.PLOT_PAD:.2f}" in svg


def test_trend_chart_svg_needs_two_points():
    assert styles.trend_chart_svg([]) == ""
    assert styles.trend_chart_svg([None, None]) == ""
    assert styles.trend_chart_svg([5]) == ""


def test_trend_chart_svg_draws_a_gridline_per_requested_fraction():
    svg = styles.trend_chart_svg([1, 2, 3], gridlines=[0.1, 0.5, 0.9])
    assert svg.count("<line") == 3


def test_overnight_chart_svg_default_bounds_are_unchanged():
    """Omitting lo/hi must render exactly as before this feature existed —
    views/insights.py and older call sites depend on it."""
    values = [50, 55, 60]
    assert styles.overnight_chart_svg(values, lo=50, hi=60) == \
           styles.overnight_chart_svg(values)


def test_hypnogram_svg_defaults_draw_no_rows_and_no_highlight():
    """views/insights.py calls this with one positional argument."""
    plain = styles.hypnogram_svg("1122")
    assert plain == styles.hypnogram_svg("1122", 52)
    assert "stroke" not in plain


def test_hypnogram_svg_rows_adds_three_separators():
    assert styles.hypnogram_svg("1122", rows=True).count("<line") == 3


def test_hypnogram_svg_highlight_outlines_the_given_span():
    svg = styles.hypnogram_svg("11112222", highlight=(4, 8))
    assert 'x="50.000%"' in svg and 'width="50.000%"' in svg


def test_hypnogram_row_labels_match_the_order_the_bands_are_drawn_in():
    labels = styles.hypnogram_row_labels()
    assert [t for _, t in labels] == ["Awake", "REM", "Light", "Deep"]
    assert [round(f, 3) for f, _ in labels] == [0.125, 0.375, 0.625, 0.875]


def test_movement_row_labels_are_inset_from_the_ends():
    labels = styles.movement_row_labels()
    assert [t for _, t in labels] == ["Active", "No motion"]
    assert all(0.0 < f < 1.0 for f, _ in labels)


def test_movement_svg_defaults_unchanged_and_highlight_is_optional():
    assert styles.movement_svg("1234") == styles.movement_svg("1234", 26)
    assert "stroke" in styles.movement_svg("1234", highlight=(1, 3))


def test_chart_hits_emits_one_anchor_per_item_with_its_href():
    html = styles.chart_hits([
        {"left": 0.0, "width": 0.5, "href": "?pt=hist:0", "title": "a"},
        {"left": 0.5, "width": 0.5, "href": "?pt=hist:1", "title": "b",
         "selected": True},
    ])
    assert html.count("<a ") == 2
    assert 'href="?pt=hist:0"' in html and 'href="?pt=hist:1"' in html
    assert html.count("hp-on") == 1
    assert 'title="b"' in html


def test_chart_hits_of_nothing_is_empty():
    assert styles.chart_hits([]) == ""


def test_chart_points_marks_only_the_selected_one():
    html = styles.chart_points([
        {"x": 0.0, "y": 0.5, "colour": "#fff"},
        {"x": 1.0, "y": 0.2, "colour": "#fff", "selected": True},
    ])
    assert html.count("hp-dot") == 2
    assert html.count("hp-dot hp-on") == 1
    assert "pointer-events:none" in html


def test_chart_frame_mirrors_its_spacers_in_both_columns():
    """The gutter and the plot column must stay in vertical step, or a Y label
    ends up beside the wrong plot."""
    frame = styles.chart_frame([
        {"svg": "<svg/>", "height": 56, "y_labels": [(0.5, "A")]},
        {"svg": "<svg/>", "height": 34, "y_labels": [(0.5, "B")], "gap": 4},
    ], x_labels=[(0.0, "23:00"), (1.0, "07:00")])
    assert frame.count("height:4px;") == 2          # one spacer per column
    assert frame.count("height:56px") >= 2          # gutter cell + plot cell
    assert ">A<" in frame and ">B<" in frame
    assert ">23:00<" in frame and ">07:00<" in frame


def test_chart_frame_bottom_rule_only_on_the_last_plot():
    one = styles.chart_frame([{"svg": "", "height": 40}])
    two = styles.chart_frame([{"svg": "", "height": 40}, {"svg": "", "height": 20}])
    assert one.count("bottom:0;height:1px") == 1
    assert two.count("bottom:0;height:1px") == 1


def test_chart_frame_axis_rules_do_not_participate_in_layout():
    """Absolutely-positioned 1px children, not CSS borders — a border would eat
    a pixel of the plot under box-sizing:border-box and walk the gridlines off
    their labels."""
    frame = styles.chart_frame([{"svg": "", "height": 40, "y_labels": [(0.0, "x")]}])
    assert "border-left" not in frame and "border-bottom" not in frame
    assert "position:absolute" in frame


def test_chart_link_script_targets_only_this_feature_s_classes():
    """It must not change how any other link in the app behaves."""
    assert "a.hp-hit[target], a.hp-link[target]" in styles._CHART_LINK_JS
    assert "__healthChartNav" in styles._CHART_LINK_JS       # rerun guard
