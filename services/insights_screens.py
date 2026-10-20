"""The Insights screens, composed for the phone's API (rebuild Phase 2,
milestone 5): Strength, Metabolism, Engine Data, the Processing Queue,
Macro Trends, Sleep Architecture, and the data tables of the Sync tab.

views/insights.py draws the same screens from the same services/ functions
(strength_screen, metabolism_screen, decision, insights, processing_queue,
sleep_architecture, stats, ai). This module makes the reads for the
caller's day (rule 3) and returns what each screen shows as data; fixed
text (a tab's caption, a section's heading) stays in the phone's strings
file. A failed read is carried as `load_error` and never shown as an empty
history: the two look the same once a list is empty, and only one of them
is a real reading.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date

from services import ai
from services import dashboard as dash
from services import decision, engine, insights, metabolism_screen, processing_queue
from services import sessions as sess
from services import home_detail, sleep_architecture, sleep_screen, stats, strength_screen
from services import tonnage, volume


def _error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


# ─── Strength ────────────────────────────────────────────────────────────────

#: The store's config row that holds the Strength screen's personal reference
#: (the 2025 peaks, the region prior, the anchor, the hold baselines and the
#: profile's imbalances). They are personal records, kept out of the engine's
#: image (rebuild rule 7); scripts/upload_strength_reference.py writes the row
#: from the local files.
REFERENCE_KEY = "strength_reference"


def reference_json(reference: dict) -> str:
    """The reference as the config row stores it: JSON, the anchor date as
    an ISO date, every tuple as a list."""
    return json.dumps({**reference, "anchor_date": reference["anchor_date"].isoformat()},
                      sort_keys=True)


def _tuples(value):
    if isinstance(value, list):
        return tuple(_tuples(v) for v in value)
    return value


def reference_from_store(repo) -> dict | None:
    """The reference read back from the store, or None when the row is
    absent or unreadable: the anchor date as a date, every list as the tuple
    strength_baselines writes."""
    try:
        raw = repo.get_config_value(REFERENCE_KEY)
        stored = json.loads(raw) if raw else None
    except Exception:
        return None
    if not stored:
        return None
    try:
        return {
            "peaks": {k: _tuples(v) for k, v in stored["peaks"].items()},
            "region_prior": dict(stored["region_prior"]),
            "pr_rir": float(stored["pr_rir"]),
            "anchor_date": date.fromisoformat(stored["anchor_date"]),
            "anchor_value": float(stored["anchor_value"]),
            "hold_baselines": {k: _tuples(v) for k, v in stored["hold_baselines"].items()},
            "imbalances": stored.get("imbalances") or {},
        }
    except (KeyError, TypeError, ValueError):
        return None


class ReferenceMissing(LookupError):
    """The Strength screen's reference is not in the store yet."""


#: The tonnage series' keys: the whole body, then each sector.
TONNAGE_KEYS = ("overall", "upper_body", "core", "lower_body")
#: The picker's first entry, the strength score.
DEFAULT_STRENGTH_METRIC = next(iter(strength_screen.METRICS))


def _week_out(week) -> dict:
    out = {"week_start": week.week_start, "training_days": week.training_days}
    for key in TONNAGE_KEYS:
        sector = week.value(key)
        out[key] = {"kg": sector.kg, "sets": sector.sets,
                    "unloaded_reps": sector.unloaded_reps,
                    "unloaded_seconds": sector.unloaded_seconds,
                    "unit_reps": sector.unit_reps}
    return out


def strength(repo, today: date, metric: str = DEFAULT_STRENGTH_METRIC) -> dict:
    """The Strength screen (strength_screen.read_data): the headline and
    whether it is calibrating, the chosen series' readout and chart (the
    score's weekly levels, or a sector's tonnage), the work without load,
    the body-part split and the region cards, and the muscle-balance
    findings. ReferenceMissing when the store holds no reference;
    ValueError for an unknown metric."""
    if metric not in strength_screen.METRICS:
        raise ValueError(f"unknown metric {metric!r}")
    reference = reference_from_store(repo)
    if reference is None:
        raise ReferenceMissing(REFERENCE_KEY)
    data = strength_screen.read_data(repo, today, reference)
    key = strength_screen.METRICS[metric]["key"]
    if key == "score":
        lo, hi = strength_screen.score_axis(data["score_series"])
    else:
        lo, (_values, hi) = 0.0, strength_screen.tonnage_axis(data["tonnage"], key)
    return {
        "today": today, "load_error": data["load_error"],
        "overall": data["overall"], "calibrating": data["calibrating"],
        "metrics": [{"label": label, **m} for label, m in strength_screen.METRICS.items()],
        "metric": metric,
        "readout": strength_screen.readout(data, metric),
        "axis": {"lo": lo, "hi": hi},
        "score_series": data["score_series"],
        "tonnage": [_week_out(w) for w in data["tonnage"]],
        "week_labels": data["week_labels"],
        "unloaded": ([{"label": label, "text": text} for label, text
                      in strength_screen.unloaded_lines(data["tonnage"], key)]
                     if key != "score" else []),
        "split": strength_screen.split(data["regions"]),
        "regions": strength_screen.region_cards(data["regions"], data.get("core_hold")),
        "unmapped": data["unmapped"],
        "imbalances": data["imbalances"],
        "imbalance_count": data["imbalance_count"],
        # The phone's page since 2026-10-20 (strength_screen, the redo): the whole page in
        # one answer, whatever `metric` asked for.
        "trend": strength_screen.trend(data),
        "trend_axis": dict(zip(("lo", "hi"), strength_screen.score_axis(data["score_series"]))),
        "areas": strength_screen.area_rows(data["regions"], data.get("core_hold")),
        "volume": strength_screen.volume(data["tonnage"]),
    }


# ─── Metabolism ──────────────────────────────────────────────────────────────

def _point(day_value) -> dict:
    day, value = day_value
    return {"date": day, "value": value}


def metabolism(repo, today: date, metric: str = "Weight", kind: str = "all",
               offset: int = 0) -> dict:
    """The Metabolism screen (metabolism_screen): the latest weigh-in and its
    fat/fat-free split, the chosen measure over one calendar period (its
    window, whether it steps back or on, the points, the runs the chart
    draws, the change and its tone, F11), the latest scan's height-immune
    pair, and the body-analysis cards. ValueError for an unknown measure or
    period."""
    if metric not in metabolism_screen.METRICS:
        raise ValueError(f"unknown metric {metric!r}")
    if kind not in {k for _label, k in metabolism_screen.RANGES}:
        raise ValueError(f"unknown period {kind!r}")
    data = metabolism_screen.read_data(repo, today)
    readings, scans = data["readings"], data["scans"]
    latest = readings[-1] if readings else None
    shown = metabolism_screen.series(data, metric, kind, offset)
    window = shown["window"]
    cell = metabolism_screen.cellular(scans, today)
    return {
        "today": today, "load_error": data["load_error"],
        "latest": None if latest is None else {
            "date": latest.day, "weight_kg": latest.weight_kg,
            "fat_mass_kg": latest.fat_mass_kg, "fat_free_mass_kg": latest.fat_free_mass_kg,
            "body_fat_pct": latest.body_fat_pct},
        "split": metabolism_screen.split(latest),
        "metrics": [{"label": label, **m} for label, m in metabolism_screen.METRICS.items()],
        "ranges": [{"label": label, "kind": k} for label, k in metabolism_screen.RANGES],
        "metric": metric, "kind": kind, "offset": offset,
        "series": {
            "window": {"kind": window.kind, "offset": window.offset, "start": window.start,
                       "end": window.end, "label": window.label, "sub": window.sub},
            "can_back": shown["can_back"], "can_forward": shown["can_forward"],
            "points": [_point(p) for p in shown["points"]],
            "runs": [[_point(p) for p in run] for run in shown["runs"]],
            "first": _point(shown["first"]) if shown["first"] else None,
            "last": _point(shown["last"]) if shown["last"] else None,
            "change": shown["change"], "tone": shown["tone"],
            "axis": metabolism_screen.chart_axis(shown["points"], shown["metric"]["span"],
                                                 shown["metric"]["dp"], window),
        },
        "cellular": None if cell is None else {
            "device": cell["device"], "days_old": cell["days_old"], "date": cell["scan"].day,
            "phase_angle_deg": cell["scan"].phase_angle_deg, "ecw_tbw": cell["scan"].ecw_tbw},
        "analysis": metabolism_screen.analysis(latest),
    }


# ─── Engine Data ─────────────────────────────────────────────────────────────

#: The traffic light's four metric cards: (key, label).
METRIC_CARDS = (("hrv_ms", "HRV"), ("resting_heart_rate", "RHR"),
                ("sleep_duration_hours", "SLEEP"), ("oura_temperature_deviation", "BODY TEMP"))


def engine_data(repo, today: date) -> dict:
    """Insights › Engine Data for the caller's day: the directive as Home and
    Training show it (the shared verdict, fault F4), the stage progression,
    the traffic light with its four metric cards and the baseline drift, the
    workload (ACWR, its windows, its advisory status and the 28-day chart),
    and the weekly volume load. A failed read answers load_error and nothing
    else, never a half screen."""
    try:
        state = decision.engine_state(repo, today, with_stage_status=True)
    except Exception as exc:
        return {"today": today, "load_error": _error(exc)}
    verdict = decision.day_verdict(repo, today)
    directive = decision.directive(repo, today)
    tl, acwr_result = state["traffic_light"], state["acwr"]
    today_row = next((r for r in state["bio_rows"] if r.get("date") == today.isoformat()), None)
    missing = set((today_row or {}).get("sources_missing") or ())
    metrics = tl.get("metrics", {})
    drift = tl.get("drift", {}) or {}
    chronic_label, chronic_help = insights.acwr_chronic_label(acwr_result)
    status = insights.acwr_status(acwr_result)
    sessions_ = repo.get_recent_sessions(days=60, today=today)
    chart = insights.acwr_chart_data(acwr_result.get("daily_au_28", [0.0] * 28), today=today)
    # Each chart's rounded top (tonnage.nice_axis_max), so the phone draws no scale of its own.
    chart["hi"] = tonnage.nice_axis_max(max(chart["au"], default=0.0))
    weeks = volume.weekly_volume_series(sessions_, today)
    return {
        "today": today, "load_error": None,
        "directive": {"tone": verdict.tone, "words": insights.directive_words(verdict),
                      "banner_kind": verdict.banner_kind, "banner_text": verdict.banner_text,
                      "engine_label": directive.get("label") or "",
                      "acwr_advisory": directive.get("acwr_advisory") or ""},
        "stage": state["stage_status"],
        "traffic_light": {
            "status": tl["status"], "overall": tl.get("overall"), "message": tl["message"],
            "no_reading": tl["status"] in engine.NO_READING_STATUSES,
            "cards": [{"key": key, "label": label,
                       **insights.metric_card(metrics.get(key, {})),
                       "missing_source": insights.missing_source(missing, key)}
                      for key, label in METRIC_CARDS],
            "drift": {"drifted": bool(drift.get("drifted")),
                      "severity": drift.get("severity") or "",
                      "message": drift.get("message") or "",
                      "applied": bool(tl.get("drift_applied")),
                      "lines": insights.drift_lines(drift, metrics) if drift.get("drifted") else []},
        },
        "acwr": {"value": acwr_result.get("acwr"), "acute_avg": acwr_result.get("acute_avg"),
                 "chronic_avg": acwr_result.get("chronic_avg"),
                 "chronic_label": chronic_label, "chronic_help": chronic_help,
                 "ceiling": acwr_result.get("ceiling"),
                 "status": None if status is None else {"kind": status[0], "text": status[1]},
                 "chart": chart},
        "volume": [{"week_start": week, "kg": kg} for week, kg in weeks],
        "volume_hi": tonnage.nice_axis_max(max((kg for _week, kg in weeks), default=0.0)),
    }


# ─── The Processing Queue ────────────────────────────────────────────────────

def queue(repo, today: date, year: int | None = None, month: int | None = None) -> dict:
    """The Processing Queue: what still waits for the keyword parse, and
    the warnings calendar of one month (the latest warning's month without
    one), each day with its marker and its entries."""
    pending = processing_queue.pending(repo)
    flagged = repo.get_flagged_entries()
    by_date = processing_queue.warnings_by_date(flagged)
    if year is None or month is None:
        year, month = processing_queue.calendar_anchor(by_date, today)
    weeks = processing_queue.month_weeks(year, month)
    prev_y, prev_m = processing_queue.step_month(year, month, -1)
    next_y, next_m = processing_queue.step_month(year, month, 1)
    return {
        "pending_notes": len(pending["notes"]), "pending_readiness": len(pending["readiness"]),
        "year": year, "month": month,
        "previous": {"year": prev_y, "month": prev_m}, "next": {"year": next_y, "month": next_m},
        "weeks": [[{"date": d, "in_month": d.month == month, "is_today": d == today,
                    "level": (processing_queue.day_level(by_date[d.isoformat()])
                              if d.isoformat() in by_date else None),
                    "entries": [processing_queue.entry_view(e)
                                for e in by_date.get(d.isoformat(), [])]}
                   for d in week] for week in weeks],
    }


def process_queue(repo) -> dict:
    """Run the keyword parse over everything pending (processing_queue.
    process_all): one failure never stops the rest, and each error names
    its item."""
    out = processing_queue.process_all(repo, repo.get_diagnostic_profile())
    return {"total": out.get("total", 0), "errors": list(out.get("errors") or [])}


# ─── Macro Trends ────────────────────────────────────────────────────────────

def checkin_trend(repo, today: date) -> dict:
    """The check-in half of Macro Trends, for the phone and the Streamlit app alike: the
    body areas he selected (insights.selected_area_frequency, the owner 2026-10-20) and the
    tightness timeline (insights.tightness_timeline), over the check-ins of the last
    insights.CHECKIN_TREND_DAYS days.

    The window's parsed check-ins are the newest parsed check-ins, and there are no more of
    them than check-ins in the window (both are rows of the one check-in table, newest
    first), so reading that many parsed rows finds every severity the timeline can show."""
    checkins = repo.get_recent_readiness(days=insights.CHECKIN_TREND_DAYS, today=today)
    regions = sorted(insights.selected_area_frequency(checkins).items(), key=lambda kv: (-kv[1], kv[0]))
    top = max((n for _r, n in regions), default=0)
    timeline = insights.tightness_timeline(
        checkins, repo.get_parsed_readiness(limit=len(checkins)) if checkins else [])
    return {
        # Each area's check-ins, and its share of the most selected one (the bar's length).
        "regions": [{"region": r, "mentions": n, "share": n / top if top else 0.0}
                    for r, n in regions],
        # Every check-in of the window, oldest first, as a timeline reads.
        "timeline": timeline,
        "timeline_axis": insights.score_timeline_axis([t["date"] for t in timeline]),
    }


def trends(repo, today: date) -> dict:
    """Macro Trends: the body areas he selected and the tightness timeline of every
    check-in (checkin_trend), the parsed check-ins by warning level, and the multi-week
    analysis once the data gate opens (the recovery direction, the slopes, the notable
    correlations, and the interpretation computed on load, I72)."""
    parsed = repo.get_parsed_readiness(limit=90)
    by_level = processing_queue.rows_by_warning_level(parsed)
    trend_data = repo.get_macro_trend_data(90, today=today)
    gate = insights.trend_gate(trend_data)
    analysis = None
    if gate["enough"]:
        computed = stats.compute_all_correlations(trend_data)
        result = ai.analyze_macro_trends(trend_data, repo.get_diagnostic_profile())
        analysis = {
            "recovery_direction": computed["recovery_direction"],
            "recovery_label": insights.recovery_label(computed["recovery_direction"]),
            "slopes": insights.slope_direction_rows(computed.get("slopes", {})),
            "notable": computed.get("notable_correlations", []),
            "interpretation": {
                "headline": result.get("headline") or "",
                "recovery_label": insights.recovery_label(
                    result.get("recovery_direction", "insufficient_data")),
                "load_management_note": result.get("load_management_note") or "",
                "correlations": result.get("correlation_interpretations", []),
                "recommendations": result.get("recommendations", []),
            },
        }
    return {
        **checkin_trend(repo, today),
        "levels": {level: [{"date": r.get("date"), "tightness": r.get("tightness_score"),
                            "pain": r.get("pain_score"),
                            "severity": r.get("ai_tightness_severity"),
                            "parts": processing_queue.names(r.get("ai_body_parts") or ""),
                            "sensation": processing_queue.names(r.get("ai_sensation_type") or "")}
                           for r in rows] for level, rows in by_level.items()},
        "gate": gate,
        "analysis": analysis,
    }


# ─── Sleep Architecture ──────────────────────────────────────────────────────

#: The three hypnograms a fused night shows, in order: (label, row key).
NIGHT_STRIPS = (("Oura (as recorded)", "oura_hypnogram"),
                ("Master (fused)", "master_hypnogram"),
                ("Garmin (as recorded)", "garmin_hypnogram"))


def sleep_architecture_view(repo, today: date, night: str | None = None) -> dict:
    """Sleep Architecture: the fused, ring-only and watch-only counts (F12),
    one fused night's three hypnograms with its figures (the latest without
    `night`), and the shadow report: what wiring fusion into the engine
    would change. A failed read is named as such."""
    try:
        rows = repo.get_sleep_fusion_history()
    except Exception as exc:
        return {"load_error": _error(exc)}
    summary = sleep_architecture.summary(rows)
    fused = summary["fused_rows"]
    chosen = next((r for r in fused if r["date"] == night), fused[-1] if fused else None)
    bio = [asdict(r) for r in repo.get_biometric_rolling(days=28, today=today)]
    shadow = dash.sleep_fusion_shadow_report(bio, sleep_architecture.fused_hours(rows), today=today)
    # The three strips on the night's own window (the fusion row's), each as the Sleep
    # screen's strip: its runs named and a tap band per slot (home_detail.strip).
    start_iso, total = sleep_screen.strip_window(None, chosen, dash.minutes_between)
    return {
        "load_error": None,
        "counts": {k: summary[k] for k in ("fused", "oura_only", "watch_only")},
        "median_phantom_wake": summary["median_phantom_wake"],
        "nights": [r["date"] for r in reversed(fused)],
        "night": None if chosen is None else {
            "date": chosen["date"],
            "strips": [{"label": label,
                        **home_detail.strip(str(chosen.get(key) or ""), start_iso, total,
                                            sleep_screen.STAGE_NAMES, "Stage")}
                       for label, key in NIGHT_STRIPS],
            "x_labels": [{"at": float(at), "text": str(text)}
                         for at, text in dash.clock_axis_labels(start_iso, total, max_ticks=5)],
            **{k: chosen.get(k) for k in ("oura_sleep_hours", "master_sleep_hours",
                                          "phantom_wake_minutes", "window_overlap_pct",
                                          "agreement_pct", "cohen_kappa",
                                          "garmin_covered_minutes", "minutes")}},
        "shadow": shadow,
    }


# ─── The Sync tab's data tables ──────────────────────────────────────────────

def _row(record) -> dict:
    return asdict(record) if is_dataclass(record) else dict(record)


def _between(rows: list[dict], start: date | None, end: date | None) -> list[dict]:
    if start is None and end is None:
        return rows
    span = insights.date_span(rows)
    if span is None:
        return []
    return insights.rows_between(rows, start or span[0], end or span[1])


def data_table(repo, today: date, table: str, start: date | None = None,
               end: date | None = None) -> dict:
    """One of the Sync tab's tables: "engine_view" (the live blend the engine
    reads, last 28 days), "blend_history" (the persisted blend) or
    "metrics_history" (the persisted Readiness, Sleep Score and Strain),
    between `start` and `end` when given. ValueError for another table."""
    if table == "engine_view":
        rows = [_row(r) for r in repo.get_biometric_rolling(days=28, today=today)]
    elif table == "blend_history":
        rows = [_row(r) for r in repo.get_biometric_blend_history()]
    elif table == "metrics_history":
        rows = [_row(r) for r in repo.get_metrics_history()]
    else:
        raise ValueError(f"unknown table {table!r}")
    span = insights.date_span(rows)
    return {"table": table, "earliest": span[0] if span else None,
            "latest": span[1] if span else None, "rows": _between(rows, start, end)}


def session_checks(repo, today: date) -> dict:
    """The session log's checks over the last 35 days
    (sessions.session_log_warnings): a repeat save, and a day far above the
    rest."""
    return {"warnings": sess.session_log_warnings(
        repo.get_session_summaries(days=35, today=today))}
