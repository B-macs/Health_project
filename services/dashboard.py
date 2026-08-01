"""
services/dashboard.py — pure Home-page computation, extracted from app.py.

app.py mixed data windowing, rolling-strain/step-modifier math, and
readiness/strain/sleep status-tier classification directly into module-level
code with no `today` parameterization (several buried date.today() calls).
This was undocumented architecture debt relative to CLAUDE.md's stated
"pure logic lives in engine/readiness/stats/rules/ai" model — see
REFACTOR_NOTES.md. Pulled out here as real, testable, parameterized functions.

SVG rendering helpers (_arc_svg, _sparkline) and _card_html stayed in app.py —
those are presentation, not business logic, matching how styles.py's HTML
builders are treated.
"""

from __future__ import annotations

from datetime import date, timedelta

from services import engine as _engine
from services import hr_load as _hr_load
from services import readiness as _readiness
from services import sleep_score as _sleep_score
from services.readiness import NOT_COMPUTED as _NOT_COMPUTED

SLEEP_NEED_HOURS_DEFAULT = 8.0


def au_to_strain_or_none(au: float | None, stage: int) -> float | None:
    if au is None or au <= 0:
        return None
    return _engine.au_to_strain(au, stage)


def fill_7day(rows: list[dict], key: str, selected_date: date) -> list:
    """One value per day for the 7 days ending on selected_date, in order,
    None where no row exists for that date."""
    by_date = {r["date"]: r.get(key) for r in rows}
    return [by_date.get((selected_date - timedelta(days=6 - i)).isoformat()) for i in range(7)]


def rolling_prior_strain(au_rows: list[dict], stage: int, today: date | None = None) -> float | None:
    """Average AU over the 7 days before today (today excluded, rest days
    count as 0), converted to a strain value — the body load already
    accumulated going into today, independent of whether today's own
    session has happened yet."""
    today = today or date.today()
    au_by_date = {r["date"]: float(r["total_au"]) for r in au_rows}
    prior_7d_au = [
        au_by_date.get((today - timedelta(days=d)).isoformat(), 0.0)
        for d in range(1, 8)
    ]
    prior_avg_au = sum(prior_7d_au) / 7
    return _engine.au_to_strain(prior_avg_au, stage) if prior_avg_au > 0 else None


def display_strain(today_strain: float | None, rolling_strain: float | None) -> tuple[float | None, bool]:
    """(value, is_rolling) — show today's actual strain once a session is
    logged; otherwise fall back to the rolling prior-load figure."""
    if today_strain is not None:
        return today_strain, False
    return rolling_strain, rolling_strain is not None


def apply_step_modifier(strain: float | None, bio_rows: list[dict],
                         today: date | None = None) -> float | None:
    """Shift displayed strain by yesterday's non-training step load relative
    to a 7-day baseline (today-8 .. today-2), clamped to [0, 21]."""
    if strain is None:
        return None
    today = today or date.today()
    yesterday_str = (today - timedelta(days=1)).isoformat()
    baseline_strs = {(today - timedelta(days=d)).isoformat() for d in range(2, 9)}
    yesterday_steps = next(
        (r["steps"] for r in bio_rows
         if r.get("date") == yesterday_str and r.get("steps") is not None),
        None,
    )
    baseline_steps = [
        r["steps"] for r in bio_rows
        if r.get("date") in baseline_strs and r.get("steps") is not None
    ]
    step_mod = _engine.step_strain_modifier(yesterday_steps, baseline_steps)
    if step_mod == 0.0:
        return strain
    return round(max(0.0, min(21.0, strain + step_mod)), 1)


def sleep_percent(sleep_hours: float | None, sleep_need_hours: float) -> int | None:
    return round(sleep_hours / sleep_need_hours * 100) if sleep_hours else None


def step_wake_time_adjustment(current_minutes: float, direction: int,
                               step: float = 5.0, ceiling: float = 120.0) -> float:
    """+/-`step` minutes per tap for the Sleep card's wake-time-adjustment
    control (CLAUDE.md rule 4's narrow manual-entry exception), mirroring
    services.sessions' step_reps/step_weight_kg steppers. Floored at 0 — an
    adjustment can't go negative, since that would mean *adding* awake time
    rather than correcting Oura's overestimation of it — and capped at
    `ceiling` (two hours) so a mis-tap can't run away. `direction` is +1 or
    -1."""
    return round(max(0.0, min(ceiling, current_minutes + direction * step)), 1)


def compute_daily_metrics_snapshot(
    d: date,
    bio_rows: list[dict],
    au_rows: list[dict],
    stage: int,
    sleep_base_hours: float | None = None,
    rolling_reference_date: date | None = None,
    wake_time_adjustments: dict[str, float] | None = None,
    hr_rows: list[dict] | None = None,
) -> dict:
    """The exact three numbers the Home page's cards show for date `d`: the
    smoothed readiness trend, sleep hours as a percent of the personal
    rolling baseline, and step-modifier-adjusted strain (today's own value
    once a session is logged that day, else the rolling 7-day prior-load
    figure). Shared by app.py's live Home page and
    Repository.sync_metrics_history so the persisted trend history can
    never drift from what was actually displayed on a given day.

    sleep_base_hours: pass a pre-computed baseline (readiness.sleep_baseline's
    result) when calling this in a loop over multiple dates, so the
    baseline — which scans the whole bio_rows window — isn't recomputed
    once per date. Matches how the Home page already computes ONE baseline
    from its fetched window and applies it regardless of which date is
    selected, rather than a strictly date-scoped baseline per historical day.

    rolling_reference_date: the date used for the rolling-prior-strain
    fallback and the step-count modifier — both represent "body load
    already accumulated heading into training," a concept the Home page
    deliberately anchors to the real present (date.today()) even while
    browsing a past day's card for reference, rather than to `d`. Defaults
    to `d` itself, which is what a batch historical persistence job wants
    instead (Repository.sync_metrics_history) — each persisted day should
    reflect its OWN rolling context, not whatever day the sync happened to
    run on. A live page that lets the user browse past dates (app.py's
    Home) should pass date.today() explicitly here to preserve that framing.

    wake_time_adjustments: passed straight through to services.sleep_score.
    compute_sleep_score (see its own docstring) — keyed by ISO date string,
    minutes to subtract from that date's recorded awake time. None (the
    default) reproduces the exact prior sleep_score behavior.

    hr_rows: persisted per-session heart-rate load
    (Repository.get_session_hr_history). When this date has a row, its
    Edwards'-TRIMP-derived strain becomes the primary signal and the RPE
    figure is blended in at a lower weight; with no row the result is
    bit-identical to the RPE-only strain this returned before HR load
    existed. Passing None (the default) forces that pre-existing behaviour.

    Returns {"readiness_score", "sleep_pct", "sleep_score", "strain",
    "strain_is_rolling", "strain_source", "strain_source_label",
    "strain_rpe_only", "strain_hr_only", "hr_detail"} — any of the metrics is
    None if there wasn't enough data to compute it for this date.
    strain_source names which method produced the value (see
    services.hr_load.SOURCE_*), so a fallback to RPE is visible rather than
    silent. sleep_pct is the retired "% of baseline" figure, kept only
    because nothing has migrated off it yet; sleep_score
    (services.sleep_score.compute_sleep_score) is what the Home page's Sleep
    card actually shows now."""
    rolling_reference_date = rolling_reference_date or d
    readiness_score = _readiness.compute_readiness_trend(d, bio_rows)
    if readiness_score == _NOT_COMPUTED:
        readiness_score = None

    d_str = d.isoformat()
    bio_day = next((r for r in bio_rows if r.get("date") == d_str), None)
    sleep_hours = bio_day.get("sleep_duration_hours") if bio_day else None
    if sleep_base_hours is None:
        sleep_base_hours, _ = _readiness.sleep_baseline(bio_rows)
    sleep_need = sleep_base_hours if sleep_base_hours else SLEEP_NEED_HOURS_DEFAULT
    sleep_pct = sleep_percent(sleep_hours, sleep_need)

    sleep_score = _sleep_score.compute_sleep_score(d, bio_rows, wake_time_adjustments=wake_time_adjustments)
    if sleep_score == _sleep_score.NOT_COMPUTED:
        sleep_score = None

    au_day = next((r for r in au_rows if r.get("date") == d_str), None)
    rpe_strain = au_to_strain_or_none(au_day["total_au"] if au_day else None, stage)

    # Heart-rate-derived strain takes priority when this date's session
    # matched a Garmin activity; RPE is kept in the blend at a lower weight
    # (see services.hr_load.blend_strain). With no matched activity this
    # collapses to exactly the RPE value computed above, which is the
    # behaviour that existed before HR load was introduced.
    hr_row = next((r for r in (hr_rows or []) if r.get("date") == d_str), None)
    hr_strain_value = hr_row.get("hr_strain") if hr_row else None
    today_strain, strain_source = _hr_load.blend_strain(hr_strain_value, rpe_strain)

    rolling_strain = rolling_prior_strain(au_rows, stage, today=rolling_reference_date)
    strain, strain_is_rolling = display_strain(today_strain, rolling_strain)
    strain = apply_step_modifier(strain, bio_rows, today=rolling_reference_date)
    if strain_is_rolling:
        # A rolling stand-in isn't attributable to either source — it's the
        # trailing average shown on days with no session at all.
        strain_source = _hr_load.SOURCE_NONE

    return {
        "readiness_score": readiness_score,
        "sleep_pct": sleep_pct,
        "sleep_score": sleep_score,
        "strain": strain,
        "strain_is_rolling": strain_is_rolling,
        "strain_source": strain_source,
        "strain_source_label": _hr_load.SOURCE_LABELS.get(strain_source, ""),
        "strain_rpe_only": rpe_strain,
        "strain_hr_only": hr_strain_value,
        "hr_detail": hr_row,
    }


# ─── Status-tier classification ─────────────────────────────────────────────
# (score, label) -> (color, value_str, label, header, description[, extra])
# Thresholds and copy moved verbatim from app.py's _readiness_meta/_strain_meta/
# _sleep_meta — pure classification, no rendering.

def readiness_meta(score) -> tuple:
    if score is None or score == _NOT_COMPUTED:
        return "#555555", "--", "No Readings", "Awaiting Data", \
               "The readiness model hasn't computed a score yet.", ""
    s = float(score)
    if s >= 85:   c, lbl, hdr = "#6BAF8B", "Optimal",       "Bring it on"
    elif s >= 70: c, lbl, hdr = "#BFA06A", "Good",           "Ready to train"
    elif s >= 50: c, lbl, hdr = "#BFA06A", "Pay Attention",  "Take it measured"
    else:         c, lbl, hdr = "#C47878", "Rest",           "Recover today"
    descs = {
        "Optimal":       "Your recovery metrics indicate full training capacity today.",
        "Good":          "Your body is recovered. A solid session is on the cards.",
        "Pay Attention": "Some recovery markers are below baseline. Train within yourself.",
        "Rest":          "Significant fatigue signals present. Prioritise rest and mobility.",
    }
    return c, str(int(s)), lbl, hdr, descs[lbl], ""


def strain_meta(score, is_rolling: bool = False) -> tuple:
    if score is None:
        return "#555555", "--", "No Readings", "No workload logged", \
               "No training data recorded for this day."
    s = float(score)
    if s < 6:    c, lbl = "#6BAF8B", "Light"
    elif s < 10: c, lbl = "#BFA06A", "Moderate"
    elif s < 14: c, lbl = "#C47878", "Hard"
    else:        c, lbl = "#C47878", "Strenuous"
    if is_rolling:
        heads = {
            "Light": "Low body load", "Moderate": "Moderate body load",
            "Hard": "High body load", "Strenuous": "Very high body load",
        }
        descs = {
            "Light":     "Low average training load over the past 7 days. Body has capacity to build.",
            "Moderate":  "Steady training stimulus from recent sessions. On track for adaptation.",
            "Hard":      "Significant accumulated load going into today. Prioritise recovery.",
            "Strenuous": "High load from recent sessions. Assess recovery before adding more volume.",
        }
    else:
        heads = {"Light": "Light day", "Moderate": "Building momentum",
                 "Hard": "High output", "Strenuous": "Peak effort"}
        descs = {
            "Light":     "Minimal cardiovascular stress. Ideal for active recovery.",
            "Moderate":  "Solid aerobic work accumulating. Body is adapting.",
            "Hard":      "Significant load logged. Adequate recovery needed before next session.",
            "Strenuous": "Max exertion. Full recovery required before your next training block.",
        }
    return c, f"{s:.1f}", lbl, heads[lbl], descs[lbl]


def sleep_meta(score, sleep_need_hours: float, sleep_base_window: int | None) -> tuple:
    """score: services.sleep_score.compute_sleep_score's 0-100 composite
    (or None). sleep_need_hours/sleep_base_window are still shown in the
    description text — they're the Total Sleep contributor's own baseline,
    not the score's full scale — even though the score itself no longer is
    a plain percent of that baseline."""
    if score is None:
        return "#555555", "--", "No Readings", "Sleep data missing", \
               "No sleep data available for this day."
    s = float(score)
    if s >= 85:   c, lbl = "#6BAF8B", "Optimal"
    elif s >= 70: c, lbl = "#BFA06A", "Good"
    elif s >= 50: c, lbl = "#BFA06A", "Pay Attention"
    else:         c, lbl = "#C47878", "Insufficient"
    heads = {"Optimal": "Well rested", "Good": "Adequate rest",
             "Pay Attention": "Sleep deficit", "Insufficient": "Significant deficit"}
    base_label = (
        f"{sleep_base_window}d avg ({sleep_need_hours:.1f} h)"
        if sleep_base_window else f"target ({sleep_need_hours:.0f} h)"
    )
    descs = {
        "Optimal":       f"Sleep score {s:.0f}/100 — total sleep, efficiency, REM/deep, "
                          f"restfulness, latency and timing all scored well against your baseline ({base_label}).",
        "Good":          f"Sleep score {s:.0f}/100. Recovery is solid; check the breakdown for what's holding it back.",
        "Pay Attention": f"Sleep score {s:.0f}/100. One or more contributors (total sleep vs {base_label}, "
                          f"efficiency, sleep stages, latency, timing) is below par.",
        "Insufficient":  f"Sleep score {s:.0f}/100 — critically low. Recovery is impaired.",
    }
    return c, f"{s:.0f}", lbl, heads[lbl], descs[lbl]


# ─── Sleep-fusion shadow report ─────────────────────────────────────────────
#  The fused hypnogram is deliberately NOT wired into the engine (see
#  services/sleep_fusion.py's module docstring). This answers the question
#  that decision defers: what WOULD change if it were?
#
#  Every fusion rule only removes phantom wake, so fused sleep is always >=
#  Oura's — and each of the three safety paths below loosens as sleep rises.
#  Quantifying that before wiring is the whole point.


def sleep_fusion_shadow_report(bio_rows: list[dict], fused_by_date: dict[str, float],
                                today: date | None = None) -> dict:
    """Re-runs traffic_light and readiness over a copy of `bio_rows` whose
    sleep_duration_hours has been replaced by the fused value, and reports
    what differs.

    `fused_by_date` is {date: master_sleep_hours}. Rows without a fused value
    are left exactly as they are, so an un-backfilled night contributes
    nothing rather than a false "no change".

    Returns counts and deltas only — it changes nothing and is read by
    views/insights.py for display.
    """
    fused_rows = []
    for r in bio_rows:
        fused_hours = fused_by_date.get(str(r.get("date")))
        fused_rows.append({**r, "sleep_duration_hours": fused_hours}
                          if fused_hours is not None else dict(r))

    covered = [r for r in bio_rows if str(r.get("date")) in fused_by_date]
    out = {
        "nights_compared": len(covered),
        "traffic_light_now": None, "traffic_light_fused": None,
        "traffic_light_would_flip": False,
        "readiness_deltas": [], "readiness_median_delta": None,
        "readiness_max_delta": None,
        "sleep_debt_now": None, "sleep_debt_fused": None,
        "rest_trigger_now": False, "rest_trigger_fused": False,
    }
    if not covered:
        return out

    now_light = _engine.traffic_light(bio_rows)
    fused_light = _engine.traffic_light(fused_rows)
    out["traffic_light_now"] = now_light.get("overall")
    out["traffic_light_fused"] = fused_light.get("overall")
    out["traffic_light_would_flip"] = out["traffic_light_now"] != out["traffic_light_fused"]

    today = today or date.today()
    deltas = []
    for r in covered:
        try:
            d = date.fromisoformat(str(r["date"]))
        except (ValueError, TypeError, KeyError):
            continue
        before = _readiness.compute_readiness(for_date=d, bio_rows=bio_rows)
        after = _readiness.compute_readiness(for_date=d, bio_rows=fused_rows)
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            deltas.append(round(float(after) - float(before), 1))
    if deltas:
        ordered = sorted(deltas)
        out["readiness_deltas"] = deltas
        out["readiness_median_delta"] = ordered[len(ordered) // 2]
        out["readiness_max_delta"] = max(deltas, key=abs)

    debt_now = _readiness.sleep_debt_hours(bio_rows, today, window_days=7)
    debt_fused = _readiness.sleep_debt_hours(fused_rows, today, window_days=7)
    out["sleep_debt_now"] = debt_now
    out["sleep_debt_fused"] = debt_fused
    if debt_now is not None:
        out["rest_trigger_now"] = debt_now >= 9.5
    if debt_fused is not None:
        out["rest_trigger_fused"] = debt_fused >= 9.5
    return out


# ─── Sleep drill-down formatting (2026-07-31) ───────────────────────────────
#  Copy, units and colour for the Home page's Sleep detail. Pure: the score
#  math lives in services/sleep_score.py, the HTML in app.py. This is the
#  layer that decides "5h 59m" over "5.98" and which of those numbers is
#  worth showing at all.
#
#  One colour scale governs the whole screen — the same thresholds sleep_meta
#  uses for the card and the tier label, reused here for every contributor
#  bar, so a coral bar and a coral tier always mean the same thing.

SLEEP_TIERS = ((85.0, "#6BAF8B", "Optimal"),
               (70.0, "#BFA06A", "Good"),
               (50.0, "#BFA06A", "Pay attention"))
_SLEEP_TIER_FLOOR = ("#C47878", "Poor")


def sleep_tier(score: float | None) -> tuple[str, str]:
    """(colour, qualitative label) for a 0-100 sub-score."""
    if score is None:
        return "#4A5568", "not scored"
    for threshold, colour, label in SLEEP_TIERS:
        if score >= threshold:
            return colour, label
    return _SLEEP_TIER_FLOOR


def format_duration(seconds: float | None) -> str | None:
    """`5h 59m` — Oura's own shape. Hours are never dropped, so the values
    stay column-comparable down a list."""
    if seconds is None:
        return None
    total = int(round(seconds / 60.0))
    return f"{total // 60}h {total % 60:02d}m"


def format_hours(hours: float | None) -> str | None:
    return None if hours is None else format_duration(hours * 3600.0)


def _contributor_value(key: str, raw, score, total_seconds) -> str:
    """The right-hand value on a contributor row.

    Absolute where a number means something to a person (durations, percent,
    minutes-to-sleep); qualitative where it doesn't. Restfulness is
    deliberately qualitative: services/sleep_score.py's docstring flags
    restless_periods' UNIT as an unverified guess, so printing "3.2 / h"
    would state a fact we can't stand behind.
    """
    if raw is None:
        return "not scored"
    if key == "total_sleep":
        return format_hours(raw) or "—"
    if key == "efficiency":
        return f"{raw:.0f} %"
    if key in ("rem", "deep"):
        if total_seconds:
            return f"{format_duration(total_seconds * raw / 100.0)}, {raw:.0f} %"
        return f"{raw:.0f} %"
    if key == "latency":
        return f"{raw:.0f}m"
    if key == "restfulness":
        return sleep_tier(score)[1]
    if key == "timing":
        return "Optimal" if raw <= 30 else f"{raw:.0f}m off usual"
    return f"{raw:.0f}"


def sleep_breakdown_rows(breakdown: dict) -> list[dict]:
    """One display row per contributor, always all seven, in the breakdown's
    own order. `bar_pct` is the sub-score; the right-hand value is the RAW
    reading — Oura's pattern, and it avoids putting two numbers on one row
    that a reader then has to reconcile."""
    rows = []
    total_seconds = breakdown.get("total_seconds")
    for c in breakdown.get("contributors", []):
        colour, _ = sleep_tier(c["score"])
        rows.append({
            "key": c["key"],
            "label": c["label"],
            "scored": c["score"] is not None,
            "value_display": _contributor_value(c["key"], c["raw"], c["score"], total_seconds),
            "bar_pct": c["score"] if c["score"] is not None else 0.0,
            "colour": colour,
        })
    return rows


def sleep_coverage_caption(breakdown: dict) -> str:
    """Renormalisation, said out loud. Empty when every contributor scored —
    a caption that always shows is a caption nobody reads.

    This is the first time the app admits that a night scored on one
    contributor and a night scored on seven both render as a confident
    number.
    """
    missing = breakdown.get("missing") or []
    if not missing:
        return ""
    scored = 7 - len(missing)
    return (f"Scored on {scored} of 7 contributors; "
            f"remaining weights renormalised to 100%.")


def sleep_unscored_reason(read_failed: bool) -> str:
    """What to say when the Sleep Score could not be computed at all.

    Two causes produce an identical empty result and must not produce an
    identical message. "Oura recorded no sleep period for this night" is a
    claim about the ring; asserting it after a failed Google Sheets read is
    simply false, and it sends the reader to check their ring instead of
    reloading. Observed in the wild on a night whose data was complete —
    every contributor present, score 76.8 — which is the whole reason this
    distinction is now a function rather than a hardcoded string.

    The same asymmetry the fusion work kept running into: a read that fails
    looks exactly like data that is absent, and only the caller knows which
    happened.
    """
    if read_failed:
        return ("Could not load your biometric readings — this is a "
                "loading problem, not missing sleep data. Try again shortly.")
    return "Oura recorded no sleep period for this night."


# ─── Readiness drill-down ────────────────────────────────────────────────────
#  Counterparts of the sleep helpers above, reusing sleep_tier's colour bands
#  deliberately: the two drill-downs sit one tap apart and a 51 that is amber
#  on one screen must not be green on the other. The bands are about a 0-100
#  sub-score, not about sleep.

def _readiness_component_value(key: str, raw, score, baseline_window: int = 0) -> str:
    """The right-hand value on a readiness component row.

    Absolute where a number means something to a person (ms, bpm, hours);
    Oura's own 0-100 for the three contributors Oura pre-scores, because
    there is no underlying raw unit we hold — printing a bare number is
    honest, inventing a unit is not.
    """
    if raw is None:
        return "not scored"
    if key == "hrv":
        return f"{raw:.0f} ms"
    if key == "rhr":
        return f"{raw:.0f} bpm"
    if key in ("sleep", "sleep_debt"):
        return format_hours(raw) or "—"
    if key == "body_temp":
        return f"{raw:.0f}"
    return f"{raw:.0f}"


def readiness_breakdown_rows(breakdown: dict) -> list[dict]:
    """One display row per component, always all seven, in the breakdown's own
    order. `bar_pct` is the sub-score; the right-hand value is the RAW reading,
    matching sleep_breakdown_rows so the two panels read identically.

    `weight_display` is carried here rather than composed in the view: the
    weight is the single most useful thing for judging whether a low component
    actually matters, and it is the one number the Sleep panel does not have
    to show (its weights are fixed and equal-ish; readiness' span 4.5%-22.5%).
    """
    rows = []
    window = breakdown.get("sleep_baseline_window") or 0
    for c in breakdown.get("components", []):
        colour, _ = sleep_tier(c["score"])
        rows.append({
            "key": c["key"],
            "label": c["label"],
            "scored": c["score"] is not None,
            "value_display": _readiness_component_value(c["key"], c["raw"], c["score"], window),
            "weight_display": f"{c['weight'] * 100:.1f}%",
            "bar_pct": c["score"] if c["score"] is not None else 0.0,
            "colour": colour,
        })
    return rows


def readiness_coverage_caption(breakdown: dict) -> str:
    """Renormalisation, said out loud — the readiness twin of
    sleep_coverage_caption. Empty when all seven scored.

    Readiness needs this more than sleep does, not less: its weights are
    uneven, so losing HRV (22.5%) and losing Previous Day Activity (4.5%)
    leave very differently-supported numbers behind, and both currently
    render as an equally confident score."""
    missing = breakdown.get("missing") or []
    if not missing:
        return ""
    scored = 7 - len(missing)
    pct = (breakdown.get("available_weight") or 0.0) * 100
    return (f"Scored on {scored} of 7 components ({pct:.0f}% of the weight); "
            f"the rest is renormalised away.")


def readiness_alcohol_caption(breakdown: dict) -> str:
    """The alcohol deduction, stated. Empty on a day with no units logged.

    Load-bearing, not a nicety: the penalty is a flat post-hoc subtraction,
    not a weighted component, so on a drinking day the seven contributions
    above CANNOT be reconciled with the score without this line. Same class
    of problem as the Sleep drill-down's wake-time note."""
    units = breakdown.get("alcohol_units")
    points = breakdown.get("alcohol_penalty_points") or 0.0
    if not units or not points:
        return ""
    unit_word = "unit" if abs(units - 1.0) < 1e-9 else "units"
    return (f"{points:.0f} points deducted for {units:g} {unit_word} of alcohol, "
            f"applied after the weighted average — so the components above "
            f"sum to {points:.0f} more than the score.")


def readiness_unscored_reason(read_failed: bool) -> str:
    """What to say when readiness could not be computed at all — the readiness
    twin of sleep_unscored_reason, and here from the first commit rather than
    added after the fact.

    Two causes produce an identical empty result and must not produce an
    identical message: a genuine absence of biometric readings, versus a
    failed Google Sheets read. Asserting the first when the second happened
    sends the reader to check their ring instead of reloading."""
    if read_failed:
        return ("Could not load your biometric readings — this is a loading "
                "problem, not missing data. Try again shortly.")
    return "No biometric readings for this day, so readiness could not be scored."


def oura_readiness_rows(detail: dict | None) -> list[dict]:
    """Oura's own nine contributors as display rows, in Oura's screen order.

    Values are Oura's raw 0-100 scores, NOT its tier words — see
    Repository.get_oura_readiness_detail for why reproducing the words would
    mean inventing thresholds Oura has never published. The colour still
    comes from sleep_tier, so the row reads at a glance without claiming to
    be Oura's own label."""
    if not detail:
        return []
    contributors = detail.get("contributors") or {}
    labels = detail.get("labels") or {}
    rows = []
    for key, value in contributors.items():
        colour, _ = sleep_tier(value)
        rows.append({
            "key": key,
            "label": labels.get(key, key),
            "scored": value is not None,
            "value_display": "—" if value is None else f"{value:.0f}",
            "weight_display": "",
            "bar_pct": value if value is not None else 0.0,
            "colour": colour,
        })
    return rows


def readiness_divergence_caption(ours: float | str | None,
                                 oura: float | None) -> str:
    """States the gap between the two models, and that neither settles it.

    Deliberately reports the difference without adjudicating: Oura's model is
    proprietary and has never been validated against any external standard,
    and we have no labelled outcome to score either against. Same stance as
    sleep_fusion's agreement_pct/cohen_kappa — measured, shown, never
    decisive."""
    if ours is None or ours == _NOT_COMPUTED or oura is None:
        return ("Oura's own nine contributors, for comparison. Neither model is "
                "ground truth.")
    gap = float(ours) - float(oura)
    if abs(gap) < 0.5:
        return ("Oura's own nine contributors. Both models agree on this day — "
                "neither is ground truth, so agreement is reassurance, not proof.")
    direction = "higher" if gap > 0 else "lower"
    return (f"Oura scores this day {oura:.0f}; we score it {float(ours):.0f} — "
            f"{abs(gap):.0f} points {direction}. Neither model is ground truth: "
            f"Oura's is proprietary and unvalidated, and ours weights different "
            f"inputs.")


SLEEP_DEBT_BANDS = ("None", "Low", "Moderate", "High")


def sleep_debt_display(debt_hours: float | None,
                       threshold: float = _readiness.SLEEP_DEBT_THRESHOLD_HOURS) -> dict:
    """The debt figure plus which of four bands it falls in.

    Banded against readiness.SLEEP_DEBT_THRESHOLD_HOURS — the same 9.5 h that
    makes scheduling.should_shift_session move a gym day — so the gauge on
    screen and the rule that actually reschedules training agree. `filled` is
    how many of the four segments to light.
    """
    if debt_hours is None:
        return {"value_display": None, "band": None, "filled": 0, "colour": "#4A5568"}
    frac = max(0.0, min(1.0, debt_hours / threshold)) if threshold else 0.0
    filled = min(4, int(frac * 4) + (1 if frac > 0 else 0))
    band = SLEEP_DEBT_BANDS[max(0, filled - 1)]
    colour = "#C47878" if frac >= 0.75 else ("#BFA06A" if frac >= 0.4 else "#6BAF8B")
    return {
        "value_display": format_hours(debt_hours),
        "band": band, "filled": filled, "colour": colour,
        "hours": debt_hours, "threshold": threshold,
    }


def sleep_key_metrics(detail: dict | None) -> list[dict]:
    """The 2x2 grid — a fixed set, so a missing reading shows a dash rather
    than collapsing the grid and moving everything else around."""
    d = detail or {}
    return [
        {"label": "Total sleep", "value": format_duration(d.get("total_seconds")) or "—"},
        {"label": "Time in bed", "value": format_duration(d.get("time_in_bed_seconds")) or "—"},
        {"label": "Efficiency",
         "value": f"{d['efficiency']:.0f} %" if d.get("efficiency") is not None else "—"},
        {"label": "Resting HR",
         "value": f"{d['lowest_heart_rate']:.0f} bpm" if d.get("lowest_heart_rate") is not None else "—"},
    ]


def sleep_stage_legend(detail: dict | None, stage_minutes: dict | None = None) -> list[dict]:
    """Awake / REM / Light / Deep with duration and share of total sleep.

    `stage_minutes` (from the fused hypnogram) wins when supplied, so the
    legend always describes the SAME sequence the strip above it draws —
    otherwise a fused night would show a strip and a set of numbers that
    disagree. Falls back to Oura's stored scalars.

    Percentages are of total SLEEP, not time in bed, so the three sleep
    stages sum to 100 and Awake is deliberately excluded from that sum.
    """
    d = detail or {}
    if stage_minutes:
        secs = {k: v * 60.0 for k, v in stage_minutes.items()}
    else:
        secs = {"awake": d.get("awake_seconds"), "rem": d.get("rem_seconds"),
                "light": d.get("light_seconds"), "deep": d.get("deep_seconds")}
    asleep = sum(v for k, v in secs.items() if k != "awake" and v) or None
    rows = []
    for key, label in (("awake", "Awake"), ("rem", "REM"), ("light", "Light"), ("deep", "Deep")):
        v = secs.get(key)
        pct = (f"{v / asleep * 100:.0f} %"
               if v is not None and asleep and key != "awake" else "—")
        rows.append({"key": key, "label": label,
                     "duration": format_duration(v) or "—", "pct": pct})
    return rows


def sleep_vitals_rows(detail: dict | None, context: dict | None = None) -> list[dict]:
    """An OPEN list — rows with no reading are omitted rather than rendered
    as dashes. average_breath is absent on older nights, and a wall of
    em-dashes is noise where a fixed set would have been signal."""
    d, c = detail or {}, context or {}
    candidates = [
        ("Average HR", d.get("average_heart_rate"), "{:.0f} bpm"),
        ("Lowest HR", d.get("lowest_heart_rate"), "{:.0f} bpm"),
        ("Average HRV", d.get("average_hrv"), "{:.0f} ms"),
        ("Respiratory rate", d.get("average_breath"), "{:.1f} /min"),
        ("Blood oxygen", c.get("spo2_average"), "{:.0f} %"),
        ("Breathing disturbance", c.get("breathing_disturbance_index"), "{:.0f}"),
        ("Temperature deviation", d.get("temperature_deviation"), "{:+.2f} °C"),
    ]
    return [{"label": lbl, "value": fmt.format(v)}
            for lbl, v, fmt in candidates if v is not None]


def format_clock(iso_datetime: str | None) -> str:
    """`22:42` from an ISO timestamp — the hypnogram's time axis. Returns ""
    rather than raising on a blank or malformed value, since older nights
    carry both."""
    if not iso_datetime:
        return ""
    try:
        from datetime import datetime as _dt
        return _dt.fromisoformat(str(iso_datetime)).strftime("%H:%M")
    except (ValueError, TypeError):
        return ""


def overnight_series(payload, max_points: int = 180) -> dict:
    """An Oura TimeSeries ({"interval", "items", "timestamp"}) → the shape the
    overnight HR/HRV charts need: {values, low, high, average, count}.

    Nulls are PRESERVED in `values` (the chart breaks its line across them)
    but excluded from the statistics — Oura pads the start of a night with
    them, and averaging a gap as zero would drag the reported mean down by an
    amount that varies with how long the pad happened to be.

    Returns count 0 rather than raising on anything unexpected, so a malformed
    cell costs one panel instead of the page.
    """
    items = (payload or {}).get("items") if isinstance(payload, dict) else None
    if not items:
        return {"values": [], "low": None, "high": None, "average": None, "count": 0}

    values = [v if isinstance(v, (int, float)) else None for v in items]
    # Downsample by striding, never by averaging: a mean would smooth away the
    # dips and excursions that are the entire reason to plot the night.
    if len(values) > max_points:
        step = len(values) / max_points
        values = [values[int(i * step)] for i in range(max_points)]

    real = [v for v in values if v is not None]
    if not real:
        return {"values": values, "low": None, "high": None, "average": None, "count": 0}
    return {
        "values": values,
        "low": min(real),
        "high": max(real),
        "average": round(sum(real) / len(real), 1),
        "count": len(real),
    }


def format_clock_offset(iso_datetime: str | None, minutes) -> str:
    """`06:21` from a start timestamp plus a duration in minutes.

    The hypnogram axis normally ends at Oura's bedtime_end, but a garmin_only
    night has no Oura sleep period at all — only the fusion row's own
    window_start_utc and minute count. Same blank-on-bad-input contract as
    format_clock, so an unparseable window costs the axis label and not the
    strip."""
    if not iso_datetime:
        return ""
    try:
        from datetime import datetime as _dt, timedelta as _td
        start = _dt.fromisoformat(str(iso_datetime))
        return (start + _td(minutes=float(minutes))).strftime("%H:%M")
    except (ValueError, TypeError):
        return ""
