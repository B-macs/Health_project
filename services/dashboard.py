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
from services import readiness as _readiness
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


def compute_daily_metrics_snapshot(
    d: date,
    bio_rows: list[dict],
    au_rows: list[dict],
    stage: int,
    sleep_base_hours: float | None = None,
    rolling_reference_date: date | None = None,
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

    Returns {"readiness_score", "sleep_pct", "strain", "strain_is_rolling"} —
    any of the three metrics is None if there wasn't enough data to compute
    it for this date."""
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

    au_day = next((r for r in au_rows if r.get("date") == d_str), None)
    today_strain = au_to_strain_or_none(au_day["total_au"] if au_day else None, stage)
    rolling_strain = rolling_prior_strain(au_rows, stage, today=rolling_reference_date)
    strain, strain_is_rolling = display_strain(today_strain, rolling_strain)
    strain = apply_step_modifier(strain, bio_rows, today=rolling_reference_date)

    return {
        "readiness_score": readiness_score,
        "sleep_pct": sleep_pct,
        "strain": strain,
        "strain_is_rolling": strain_is_rolling,
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


def sleep_meta(pct, sleep_need_hours: float, sleep_base_window: int | None) -> tuple:
    if pct is None:
        return "#555555", "--%", "No Readings", "Sleep data missing", \
               "No sleep data available for this day."
    p = float(pct)
    if p >= 85:   c, lbl = "#6BAF8B", "Optimal"
    elif p >= 70: c, lbl = "#BFA06A", "Good"
    elif p >= 50: c, lbl = "#BFA06A", "Pay Attention"
    else:         c, lbl = "#C47878", "Insufficient"
    heads = {"Optimal": "Well rested", "Good": "Adequate rest",
             "Pay Attention": "Sleep deficit", "Insufficient": "Significant deficit"}
    base_label = (
        f"{sleep_base_window}d avg ({sleep_need_hours:.1f} h)"
        if sleep_base_window else f"target ({sleep_need_hours:.0f} h)"
    )
    descs = {
        "Optimal":       f"Sleep met or exceeded your personal baseline — {base_label}.",
        "Good":          f"You reached {p:.0f}% of your baseline {base_label}. Recovery is solid.",
        "Pay Attention": f"Only {p:.0f}% of baseline {base_label} met. Fatigue may accumulate.",
        "Insufficient":  f"Sleep critically short ({p:.0f}% of baseline {base_label}). Recovery impaired.",
    }
    return c, f"{p:.0f}%", lbl, heads[lbl], descs[lbl]
