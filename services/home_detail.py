"""Home's three drill-downs for one day (Readiness, Sleep, Strain), composed
for the phone's API (rebuild Phase 2, milestone 5).

app.py draws the same panels from the same services/ functions
(services/home.py, sleep_screen.py, strain_screen.py, dashboard.py). This
module makes the reads for one day, every window ending on it (inventory
fault F8), and returns what each panel shows as data: the numbers, the
states, the sentences services/ already writes, and each chart's axes and
tap details, so the phone draws without computing anything. A sentence
app.py holds as fixed text (a panel heading, a static note) stays in the
phone's strings file, keyed by the state returned here: strain_screen.py's
rule.

A failed read never takes a panel's neighbours down: each read is tried on
its own, and the panel it feeds states its own absence, as on the Streamlit
page.
"""

from __future__ import annotations

from datetime import date, timedelta

import training_constants as _tc
from services import dashboard as dash
from services import home, readiness, sleep_score, sleep_screen, strain_screen
from services import plan as plan_svc

#: Nights of night detail read: the day shown and the week before it, as
#: app.py reads them.
NIGHT_DAYS = 7
#: The hypnogram codes in the order the stage rows list them.
STAGE_ROW_CODES = ("4", "3", "2", "1")
#: The trend chart each drill-down closes with: (Metrics History key, the
#: point's label, the chart's title, decimals, the scale's floor and cap).
TRENDS = {
    "readiness": ("readiness_score", "Readiness", "Readiness Trend", 0, 0.0, 100.0),
    "sleep": ("sleep_score", "Sleep Score", "Sleep Score Trend", 0, 0.0, 100.0),
    "strain": ("strain", "Strain", "Strain Trend", 1, 0.0, home.SCALES["strain"]),
}
#: Each detail screen's header title.
TITLES = {"readiness": "Readiness History", "sleep": "Sleep History", "strain": "Strain History"}


def _try(read, default):
    """(the read's result, True), or (`default`, False) when it raised."""
    try:
        return read(), True
    except Exception:
        return default, False


def _num(value) -> float | None:
    """A stored value as a number; None for a blank or unreadable one."""
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ticks(pairs) -> list[dict]:
    return [{"at": float(at), "text": str(text)} for at, text in pairs]


def value_axis(values, *, floor: float | None = None, cap: float | None = None) -> tuple:
    """(the rounded value axis or None, its tick labels from the top), as the
    Streamlit charts draw them (dashboard.value_axis, 4 ticks)."""
    axis = dash.value_axis(values, ticks=4, floor=floor, cap=cap)
    return axis, _ticks(dash.value_axis_labels(axis))


def _drawable(values) -> bool:
    """A line needs two readings; with fewer the chart shows its empty state."""
    return sum(1 for v in values if v is not None) >= 2


# ─── Charts ──────────────────────────────────────────────────────────────────

def trend_chart(dates: list[date], values: list, *, title: str, label: str, unit: str = "",
                decimals: int = 0, floor: float | None = None, cap: float | None = None,
                date_fmt: str = "%d %b", max_x_ticks: int = 5, subtitle: bool = True,
                history: list[dict] | None = None, exclude: str = "") -> dict:
    """A dated trend: the values, the latest as the headline, both axes, and
    each point's tap detail (dashboard.trend_point_detail). With `history`
    (Metrics History rows), each point also lists that day's OTHER stored
    metrics (dashboard.metrics_history_rows), as the 30-day trend does."""
    values = [_num(v) for v in values]
    axis, y_labels = value_axis(values, floor=floor, cap=cap)
    current = next((v for v in reversed(values) if v is not None), None)
    by_date = {r.get("date"): r for r in (history or [])}
    points = []
    for i in range(len(dates)):
        detail = dash.trend_point_detail(dates, values, i, unit=unit, decimals=decimals,
                                         label=label)
        if detail is not None:
            detail["extra"] = (dash.metrics_history_rows(by_date.get(detail["open_date"]),
                                                         exclude=exclude)
                               if history is not None else [])
        points.append(detail)
    return {
        "title": title,
        "dates": [d.isoformat() for d in dates],
        "values": values,
        "unit": unit,
        "decimals": decimals,
        "headline": ("—" if current is None
                     else f"{current:.{decimals}f}" + (f" {unit}" if unit else "")),
        "subtitle": (f"{dash.format_axis_date(dates[0])} – {dash.format_axis_date(dates[-1])}"
                     if subtitle and dates else ""),
        "axis": axis,
        "y_labels": y_labels,
        "x_labels": _ticks(dash.x_axis_labels(
            [dash.format_axis_date(d, date_fmt) for d in dates], max_ticks=max_x_ticks)),
        "points": points,
        "empty": axis is None or not _drawable(values),
    }


def history_trend(view: str, metrics_history: list[dict], day: date) -> dict:
    """The 30-day trend a drill-down closes with, from Metrics History, the
    stored record (home.trend_series), ending on the day shown."""
    key, label, title, decimals, floor, cap = TRENDS[view]
    dates, values, _latest = home.trend_series(metrics_history, day, key)
    return trend_chart(dates, values, title=title, label=label, decimals=decimals,
                       floor=floor, cap=cap, history=metrics_history, exclude=key)


def seven_day_chart(bio_rows: list[dict], day: date, key: str, title: str, unit: str) -> dict:
    """A 7-day biometric block (heart rate variability, resting heart rate):
    the live blend, weekday labels, no date range under the title."""
    dates = [day - timedelta(days=6 - i) for i in range(7)]
    return trend_chart(dates, dash.fill_7day(bio_rows, key, day), title=title, label=title,
                       unit=unit, floor=0.0, date_fmt="%a", max_x_ticks=7, subtitle=False)


def overnight_panels(detail: dict | None) -> list[dict]:
    """The overnight heart-rate and HRV panels (sleep_screen.OVERNIGHT_PANELS):
    the headline and secondary figures, the series against the night's own
    average, both axes, and a tap band per reading (merged above 48, each
    with the reading at its centre). A series with fewer than two readings
    has no panel: an empty chart would read as a flat night."""
    detail = detail or {}
    panels = []
    for heading, key, unit, big, small in sleep_screen.OVERNIGHT_PANELS:
        series = dash.overnight_series(detail.get(key))
        values = series["values"]
        if not series["count"] or not _drawable(values):
            continue
        axis, y_labels = value_axis(values, floor=0.0)
        if axis is None:
            continue
        x_labels = sleep_screen.overnight_axis(
            dash.overnight_axis_labels(series, max_ticks=4), detail, dash.format_clock)
        panels.append({
            "key": key, "title": heading, "unit": unit,
            "headline": series[big],
            "secondary_label": sleep_screen.OVERNIGHT_LABELS[small],
            "secondary": series[small],
            "average": series["average"],
            "values": values,
            "axis": axis, "y_labels": y_labels, "x_labels": _ticks(x_labels),
            "bands": [{"left": left, "width": width, "index": i,
                       "detail": dash.overnight_point_detail(series, i, unit=unit)}
                      for left, width, i in dash.hit_bands(len(values))],
        })
    return panels


def strip(codes: str, start_iso: str | None, total_minutes: float | None,
          names: dict[str, str], kind: str) -> dict:
    """A digit-coded strip (stages or movement): its codes, its runs named,
    and a tap band per slot (merged above 48) with the RUN that slot belongs
    to as its detail (dashboard.segment_point_detail)."""
    return {
        "codes": codes,
        "runs": [{"start": s, "end": e, "code": c, "name": names.get(c, "")}
                 for s, e, c in dash.merge_runs(codes)],
        "bands": [{"left": left, "width": width, "index": i,
                   "detail": dash.segment_point_detail(
                       codes, i, start_iso=start_iso, total_minutes=total_minutes,
                       labels=names, kind=kind)}
                  for left, width, i in dash.hit_bands(len(codes))],
    }


def hypnogram(detail: dict | None, fused: dict | None, fusion_loaded: bool) -> dict:
    """The night's stage strip and, under it on the same clock, its movement
    strip: the fused master when there is one, else Oura's own sequence
    (sleep_screen.strip_source), both stretched over one window
    (sleep_screen.strip_window). `note` says what the source line under the
    strip states: "phantom" (Oura wake counted as sleep), "watch" (the ring
    recorded nothing) or "plain". `empty` when the night has no stage
    timeline."""
    src = sleep_screen.strip_source(fused, detail, fusion_loaded)
    start_iso, total = sleep_screen.strip_window(detail, fused, dash.minutes_between)
    if not src["codes"]:
        return {"empty": True, "source": src["source"], "title": src["title"],
                "note": src["note"], "phantom_minutes": _num(src["phantom"]),
                "start": start_iso, "minutes": total, "x_labels": [],
                "stages": None, "movement": None}
    caption = sleep_screen.movement_caption(fused)
    movement = None
    if caption is not None:
        movement = {**strip(caption["codes"], start_iso, total, sleep_screen.MOVEMENT_NAMES,
                            "Movement"),
                    "title": caption["title"], "details": caption["details"]}
    return {
        "empty": False, "source": src["source"], "title": src["title"], "note": src["note"],
        "phantom_minutes": _num(src["phantom"]), "start": start_iso, "minutes": total,
        "x_labels": _ticks(dash.clock_axis_labels(start_iso, total, max_ticks=5)),
        "stages": strip(src["codes"], start_iso, total, sleep_screen.STAGE_NAMES, "Stage"),
        "movement": movement,
    }


# ─── The three drill-downs ───────────────────────────────────────────────────

def _frame(view: str, day: date, before: date, after: date | None, caller_today: date) -> dict:
    return {"date": day, "previous": before, "next": after, "is_today": day == caller_today,
            "date_label": home.date_label(day, caller_today), "screen_title": TITLES[view]}


def _night_reads(repo, day: date) -> dict:
    """The night detail, the Oura daily context and the fusion rows for the
    week ending on `day`, each tried on its own."""
    start, end = (day - timedelta(days=NIGHT_DAYS)).isoformat(), day.isoformat()
    details, details_loaded = _try(lambda: repo.get_sleep_night_details(start, end), {})
    context, _ok = _try(lambda: repo.get_oura_daily_sleep_context(start, end), {})
    fusion, fusion_loaded = _try(
        lambda: {r["date"]: r for r in repo.get_sleep_fusion_history(start, end)}, {})
    return {"details": details or {}, "details_loaded": details_loaded,
            "context": context or {}, "fusion": fusion or {}, "fusion_loaded": fusion_loaded}


def _contributors(scored: bool, rows: list[dict], caption: str, reason: str) -> dict:
    return {"scored": scored, "rows": rows if scored else [],
            "caption": caption if scored else "", "unscored_reason": "" if scored else reason}


def readiness_detail(repo, requested: date | None, caller_today: date) -> dict:
    """The Readiness drill-down for one day: the masthead (the card's
    headline, DAILY else TREND), the contributors of that same DAILY (one
    set of rows, the engine's on the caller's today: F6) with their caption
    or the reason there is no score, the 2x2 key metrics, the overnight
    heart-rate and HRV panels, and the 30-day stored trend."""
    from services import decision        # here: the heavier module, read on demand

    day, before, after = home.day_bounds(requested, caller_today)
    reads = home.read_home(repo, day)
    snap = home.snapshot(reads)
    nights = _night_reads(repo, day)
    stale = dash.has_night_without_biometric_row(reads.bio_rows, nights["details"], day)
    trend = snap["readiness_score"]
    daily, breakdown = None, None
    try:
        engine_rows = decision.readiness_rows(repo, day) if day == caller_today else None
        daily, breakdown = home.readiness_daily(
            day, home.readiness_rows_for(day, caller_today, engine_rows, reads.bio_rows))
    except Exception:
        pass
    breakdown = breakdown or readiness.readiness_breakdown(day, reads.bio_rows)
    colour, display, label, *_rest = dash.readiness_meta(home.readiness_card(daily, trend))
    key = day.isoformat()
    detail = nights["details"].get(key) or {}
    row = next((r for r in reads.bio_rows if r.get("date") == key), {})
    scored = breakdown["score"] != readiness.NOT_COMPUTED
    return {
        **_frame("readiness", day, before, after, caller_today),
        "title": f"READINESS · {home.date_label(day, caller_today)}",
        "masthead": {"colour": colour, "display": display, "label": label},
        "bio_failed": reads.bio_failed,
        "contributors": _contributors(
            scored, dash.readiness_breakdown_rows(breakdown) if scored else [],
            home.readiness_contributors_caption(trend, breakdown) if scored else "",
            dash.readiness_unscored_reason(reads.bio_failed, stale)),
        "key_metrics": home.readiness_key_metrics(row, detail),
        "overnight": overnight_panels(detail),
        "trend": history_trend("readiness", reads.metrics_history, day),
    }


def wake_control(day: date, adjustments: dict, sources: dict) -> dict:
    """The wake-time correction for a scored night (sleep_screen.wake_control,
    fault F5): the minutes, the stepper's words, whether it may be changed,
    its caption, and the two values the − and + buttons set
    (dashboard.step_wake_time_adjustment: 5-minute steps, 0 to 120), so the
    phone sends a value and never computes one."""
    control = sleep_screen.wake_control(day, adjustments, sources)
    minutes = control["minutes"]
    return {
        "minutes": minutes,
        "source": control["source"],
        "editable": control["editable"],
        "label": f"−{minutes:.0f} min" if minutes else "No adjustment",
        "caption": control["caption"],
        "decrease_to": dash.step_wake_time_adjustment(minutes, -1),
        "increase_to": dash.step_wake_time_adjustment(minutes, +1),
    }


def sleep_detail(repo, requested: date | None, caller_today: date) -> dict:
    """The Sleep drill-down for one night.

    ⚠ ALL OR NOTHING, AND THE GATE IS THE SCORE (athlete, 2026-08-25):
    `mode` is sleep_screen.screen_mode, and only "scored" carries `night`
    (the key metrics, the debt, the stage strip and rows, the naps, the
    overnight panels and the vitals) and `wake` (the correction stepper). A
    night only the watch recorded carries `watch_only` instead, which says
    in its own words that there is no Sleep Score. Every other mode carries
    neither: the reason line and the day arrows are the whole screen."""
    day, before, after = home.day_bounds(requested, caller_today)
    reads = home.read_home(repo, day)
    snap = home.snapshot(reads)
    nights = _night_reads(repo, day)
    stale = dash.has_night_without_biometric_row(reads.bio_rows, nights["details"], day)
    key = day.isoformat()
    detail = nights["details"].get(key)
    context = nights["context"].get(key) or {}
    fused = nights["fusion"].get(key) or {}
    breakdown = sleep_score.sleep_score_breakdown(day, reads.bio_rows)
    scored = breakdown["score"] != sleep_score.NOT_COMPUTED
    mode = sleep_screen.screen_mode(scored, fused, detail, nights["details_loaded"])
    colour, display, label, _header, _desc = dash.sleep_meta(
        snap["sleep_score"], snap["sleep_need_hours"], snap["sleep_base_window"])
    trend = history_trend("sleep", reads.metrics_history, day)
    trend_dates = [date.fromisoformat(d) for d in trend["dates"]]
    wake_view = sleep_screen.wake_display(day, reads.wake_adjustments, trend_dates)
    # The correction belongs to the night figures, never to the score (Sleep
    # Score MODEL_VERSION 3, 2026-10-27): the fusion's on a fused night, the
    # stepper's on any other.
    manual = (float(reads.wake_adjustments.get(key) or 0.0)
              if reads.wake_sources.get(key) == sleep_screen.MANUAL else 0.0)
    figures = dash.sleep_night_figures(detail, fused, manual)
    correction = (figures.get("phantom_wake_minutes") or 0.0) + (figures.get("manual_minutes") or 0.0)

    watch_only = None
    if mode == sleep_screen.WATCH_ONLY:
        watch_only = {
            "stages": [{**s, "name": sleep_screen.STAGE_NAMES[s["code"]],
                        "duration": dash.format_duration(s["minutes"] * 60) or "—"}
                       for s in sleep_screen.watch_only_stages(fused)],
            "hypnogram": hypnogram(None, fused, nights["fusion_loaded"]),
        }

    night = None
    if mode == sleep_screen.SCORED:
        debt = dash.sleep_debt_display(readiness.sleep_debt_hours(reads.bio_rows, day))
        legend = dash.sleep_stage_legend(detail, dash.sleep_stage_minutes(detail, fused))
        night = {
            "key_metrics": dash.sleep_key_metrics(detail, fused, manual),
            "fusion_caption": dash.sleep_fusion_caption(figures),
            "debt": debt if debt["value_display"] is not None else None,
            "asleep": dash.format_duration(figures.get("total_seconds")) or "—",
            "in_bed": dash.format_duration(figures.get("time_in_bed_seconds")) or "—",
            "stages": [{**r, "code": code} for r, code in zip(legend, STAGE_ROW_CODES)],
            "hypnogram": hypnogram(detail, fused, nights["fusion_loaded"]),
            "naps": dash.sleep_naps_display(detail),
            "overnight": overnight_panels(detail),
            "vitals": dash.sleep_vitals_rows(detail, context),
        }

    return {
        **_frame("sleep", day, before, after, caller_today),
        "title": (f"SLEEP · {home.date_label(day, caller_today)}"
                  + (" · ADJUSTED" if wake_view["adjusted"] else "")),
        "masthead": {"colour": colour, "display": display, "label": label},
        "adjusted": wake_view["adjusted"],
        "bio_failed": reads.bio_failed,
        "mode": mode,
        "contributors": _contributors(
            scored, dash.sleep_breakdown_rows(breakdown) if scored else [],
            sleep_screen.contributors_caption(dash.sleep_coverage_caption(breakdown), correction)
            if scored else "",
            dash.sleep_unscored_reason(reads.bio_failed, stale)),
        "watch_only": watch_only,
        "night": night,
        # Nothing to correct on a night with no reading (the all-or-nothing rule).
        "wake": wake_control(day, reads.wake_adjustments, reads.wake_sources) if scored else None,
        "nights_adjusted": wake_view["nights_adjusted"],
        "trend": trend,
    }


def _region_out(panel: dict, data: dict, show_week: bool) -> dict:
    """The region panel (strain_screen.region_panel) with each region's name,
    short name and colour (training_constants.REGION_DISPLAY), the strains'
    non-additive note, and whether the rest-day week can be shown."""
    shared = {"can_show_window": bool(data.get("can_show_window")), "showing_week": show_week}
    if panel["state"] == "empty":
        return {"state": "empty", "reason": panel["reason"],
                "unmapped_names": panel["unmapped_names"], **shared}
    regions = [{**r, "name": _tc.REGION_DISPLAY[r["id"]]["name"],
                "short": _tc.REGION_DISPLAY[r["id"]]["short"],
                "colour": _tc.REGION_DISPLAY[r["id"]]["colour"]}
               for r in panel["regions"]]
    return {**{k: v for k, v in panel.items() if k != "regions"}, "regions": regions,
            "non_additive_note": data.get("non_additive_note") or "", **shared}


def strain_detail(repo, requested: date | None, caller_today: date, show_week: bool = False) -> dict:
    """The Strain drill-down for one day: the masthead ("7D AVG" on a rest
    day), where the load landed by body region (the 7 days before on a rest
    day when `show_week`; nothing, and why, when the stage cannot be read,
    F7), the strain's source, the 7-day HRV and resting heart rate, and the
    30-day stored trend. The region ACWR's chronic baseline starts at the
    stage start as of the day shown."""
    day, before, after = home.day_bounds(requested, caller_today)
    reads = home.read_home(repo, day)
    snap = home.snapshot(reads)
    label = home.date_label(day, caller_today)
    is_rolling = bool(snap["strain_is_rolling"])
    rest_day = bool(snap.get("rest_day"))
    colour, display, band, _header, _desc = dash.strain_meta(snap["strain"], rest_day=rest_day)
    _card, title = strain_screen.strain_labels(is_rolling, label)
    region = None
    if reads.stage is not None:
        data = strain_screen.empty_region_data(rest_day)
        try:
            stage_start = plan_svc.current_stage_start(repo.get_phases(), day)
            data = strain_screen.region_data(
                repo.get_daily_region_au(strain_screen.REGION_DAYS, today=day),
                reads.stage, day, stage_start, snap, show_week)
        except Exception:
            pass                      # the panel states its own absence
        region = _region_out(strain_screen.region_panel(data, snap["strain"], reads.stage),
                             data, show_week)
    source = strain_screen.strain_source(snap)
    if source is not None:
        hr_strain, rpe_strain, hr_weight = source["blend"] or (None, None, None)
        source = {"kind": source["kind"], "label": source["label"],
                  "hr_rows": [{"label": n, "value": v} for n, v in source["hr_rows"]],
                  "blend": (None if source["blend"] is None else
                            {"hr_strain": hr_strain, "rpe_strain": rpe_strain,
                             "hr_weight_pct": hr_weight})}
    return {
        **_frame("strain", day, before, after, caller_today),
        "title": title,
        "masthead": {"colour": colour, "display": display, "label": band},
        "is_rolling": is_rolling,
        "bio_failed": reads.bio_failed,
        "stage_unread": home.STAGE_UNREAD if reads.stage is None else "",
        "region": region,
        "source": source,
        "hrv_7d": seven_day_chart(reads.bio_rows, day, "hrv_ms", "Heart Rate Variability", "ms"),
        "rhr_7d": seven_day_chart(reads.bio_rows, day, "resting_heart_rate",
                                  "Resting Heart Rate", "bpm"),
        "trend": history_trend("strain", reads.metrics_history, day),
    }


# ─── The wake-time correction, set (Key Rule 4's one manual correction) ──────

#: The values the wake stepper reaches: 0 to 120 minutes in 5-minute steps
#: (dashboard.step_wake_time_adjustment's defaults).
WAKE_VALUES = frozenset(float(m) for m in range(0, 121, 5))


class WakeAdjustmentError(ValueError):
    """A correction that may not be stored, with the reason's code:
    "future_day", "minutes_invalid", "night_not_scored" or "fusion_applies"."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def set_wake_adjustment(repo, day: date, caller_today: date, minutes: float) -> dict:
    """Store one night's wake-time correction and return the stepper as it
    now reads (wake_control).

    The same rules the Streamlit stepper keeps, checked here because the
    phone only sends a value: no night after the caller's today; one of the
    stepper's values; a scored night only (the all-or-nothing rule: nothing
    to correct on a night with no reading); and never on a fused night,
    where the fusion figure wins and a manual value would change nothing
    (fault F5). The value is absolute, so the same request sent twice stores
    one correction. Never touches the raw Oura reading."""
    if day > caller_today:
        raise WakeAdjustmentError("future_day")
    if float(minutes) not in WAKE_VALUES:
        raise WakeAdjustmentError("minutes_invalid")
    reads = home.read_home(repo, day)
    breakdown = sleep_score.sleep_score_breakdown(day, reads.bio_rows)
    if breakdown["score"] == sleep_score.NOT_COMPUTED:
        raise WakeAdjustmentError("night_not_scored")
    if not sleep_screen.wake_control(day, reads.wake_adjustments, reads.wake_sources)["editable"]:
        raise WakeAdjustmentError("fusion_applies")
    repo.set_wake_time_adjustment(day, float(minutes))
    adjustments, sources = repo.get_effective_wake_adjustments(
        start=day.isoformat(), end=day.isoformat())
    return wake_control(day, adjustments, sources)
