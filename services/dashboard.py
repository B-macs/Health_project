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

import math
from datetime import date, timedelta

import training_constants as _tc
from services import engine as _engine
from services import hr_load as _hr_load
from services import readiness as _readiness
from services import sleep_score as _sleep_score
from services import strain_regions as _strain_regions
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


def snapshot_is_complete(row: dict | None) -> bool:
    """True when a persisted Metrics History row already carries the day's
    morning numbers — readiness AND sleep both present.

    Home uses this to decide whether the device sync has to run in the
    FOREGROUND (the numbers aren't on screen yet, so you are waiting for
    them) or can be pushed to a background thread (they are, so you are
    not). Both derive from last night and are fixed by the time you wake up.

    Strain is deliberately excluded. It legitimately changes later in the
    day when a session is logged — but that arrives through the app's own
    write path, which clears the caches, not through a wearable sync.
    Requiring it here would force a foreground sync on every visit of every
    rest day.

    Tests for None-vs-zero: 0 is a real score (a heavy-alcohol night floors
    readiness at 0), so this checks for None rather than falsiness.
    """
    if not row:
        return False
    return row.get("readiness_score") is not None and row.get("sleep_score") is not None


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


# ─── Localised strain: a SIBLING of the snapshot above, never a widening ────
#
# compute_daily_metrics_snapshot's key set is read positionally or by literal
# set in three places — Repository._metrics_history_row (bracket access, so a
# rename raises), home_snapshot.build, and the Home page — and
# tests/test_dashboard.py already asserts it exactly. Localised strain is
# additive information beside the headline, so it gets its own function and
# leaves that contract alone.

_REGION_TONES: dict[str, str] = {
    "green":  "#6BAF8B",
    "yellow": "#BFA06A",
    "red":    "#C47878",
    "grey":   "#4A5568",
}

_ACWR_REASONS: dict[str, str] = {
    "optimal":        "optimal",
    "undertraining":  "below the optimal band",
    "overreach_risk": "above the ceiling",
}


def strain_region_acwr_display(acwr_result: dict | None) -> dict:
    """How one region's ACWR reads on screen: {"value", "reason", "colour",
    "diagnostic"}.

    TWO RULES, both already this codebase's habit.

    A status with no verdict in it — baseline_establishing,
    insufficient_regional_load, insufficient_chronic_data — takes the GREY
    tone and its reason is PRINTED, never left to the colour alone. An
    establishing baseline must not be distinguishable from a good score only
    by a shade of grey on a phone in daylight.

    A region with no ratio returns an em-dash and says why. Never a zero: a
    region that was not trained is not a region whose ACWR is 0.0, the same
    distinction services/battery.py draws between a failed reading and an
    unmeasured one.
    """
    if not acwr_result:
        return {"value": "ACWR —", "reason": "no load in window",
                "colour": _REGION_TONES["grey"], "diagnostic": False}

    status = acwr_result.get("status") or "insufficient_data"
    ratio = acwr_result.get("acwr")
    ceiling = acwr_result.get("ceiling", 1.3)

    if ratio is None:
        if status == "insufficient_regional_load":
            loaded = acwr_result.get("loaded_days", 0)
            floor = acwr_result.get("min_loaded_days", 0)
            reason = f"loaded {loaded}/{floor} days — too thin to rate"
        else:
            reason = "not enough history"
        return {"value": "ACWR —", "reason": reason,
                "colour": _REGION_TONES["grey"], "diagnostic": False}

    if status == "baseline_establishing":
        have = acwr_result.get("in_stage_days", 0)
        return {
            "value": f"ACWR {ratio:.2f}",
            "reason": (f"baseline {have}/{_engine.ACWR_MIN_IN_STAGE_DAYS} d "
                       f"— not diagnostic"),
            "colour": _REGION_TONES["grey"], "diagnostic": False,
        }

    reason = _ACWR_REASONS.get(status, status.replace("_", " "))
    if status == "overreach_risk":
        reason = f"above ceiling {ceiling:.2f}"
    return {
        "value": f"ACWR {ratio:.2f}", "reason": reason,
        "colour": _REGION_TONES[_engine.ACWR_STATUS_COLORS.get(status, "grey")],
        "diagnostic": True,
    }


def compute_region_strain_snapshot(
    d: date,
    region_rows: list[dict],
    stage: int,
    overall_snapshot: dict | None = None,
    provenance: dict | None = None,
    acwr_results: dict | None = None,
) -> dict:
    """The regional companion to compute_daily_metrics_snapshot.

    `region_rows` is Repository.get_daily_region_au()["rows"].
    `overall_snapshot` is passed IN rather than recomputed, so the stated
    additivity gap is measured against the very number the card shows and the
    two can never disagree by a rounding step.

    Returns {"regions": [...ordered upper/core/lower...], "has_split",
             "unattributed_au", "unattributed_pct", "total_au",
             "additivity_gap", "non_additive_note", "attributed_fraction",
             "attributed_is_low", "unmapped_names", "shares_basis",
             "shares_version"}.

    `has_split` is False on a day with no session, on a day whose strain is
    the rolling 7-day stand-in (there is no single day to divide), and on a
    day where nothing mapped — a pure yoga session. Callers must render "—"
    in that case, never 0.0.
    """
    provenance = provenance or {}
    overall_snapshot = overall_snapshot or {}
    row = _strain_regions.region_au_for_date(region_rows, d)

    rolling = bool(overall_snapshot.get("strain_is_rolling"))
    strains = _strain_regions.region_strain(row, stage)
    has_split = bool(row) and not rolling and any(v is not None for v in strains.values())

    total_au = float((row or {}).get("total_au") or 0.0)
    unattributed_au = float((row or {}).get(_strain_regions.UNATTRIBUTED) or 0.0)

    regions = []
    for name in _strain_regions.REGIONS:
        au = float((row or {}).get(name) or 0.0) if row else 0.0
        regions.append({
            "id": name,
            "au": au if has_split else None,
            "au_pct": (au / total_au * 100.0) if (has_split and total_au > 0) else None,
            "strain": strains[name] if has_split else None,
            "acwr": strain_region_acwr_display((acwr_results or {}).get(name)),
        })

    frac = provenance.get("attributed_fraction")
    return {
        "regions": regions,
        "has_split": has_split,
        "total_au": total_au if has_split else None,
        "unattributed_au": unattributed_au if has_split else None,
        "unattributed_pct": ((unattributed_au / total_au * 100.0)
                             if (has_split and total_au > 0) else None),
        "additivity_gap": _strain_regions.additivity_gap(
            strains, overall_snapshot.get("strain"),
        ) if has_split else None,
        "non_additive_note": _strain_regions.NON_ADDITIVE_NOTE,
        "attributed_fraction": frac,
        "attributed_is_low": (frac is not None
                              and frac < _strain_regions.ATTRIBUTED_FRACTION_LOW),
        "unmapped_names": provenance.get("unmapped_names") or [],
        "shares_basis": _tc.REGION_SHARES_BASIS,
        "shares_version": _tc.REGION_SHARES_VERSION,
    }


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

    Sleep Debt is shown in hours because that is what it physically is, and
    because its threshold (9.5 h) is the same one that reschedules training —
    a number the reader can act on. Every other component under readiness
    MODEL_VERSION 2 is one of Oura's pre-scored 0-100 contributors, where we
    hold no underlying raw unit at all: printing the bare score is honest,
    inventing a unit for it would not be.
    """
    if raw is None:
        return "not scored"
    if key == "sleep_debt":
        return format_hours(raw) or "—"
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
    # Total comes from the breakdown, never a literal: the component count
    # changed from 7 to 9 with readiness MODEL_VERSION 2, and a hardcoded
    # denominator would have gone quietly wrong rather than failing.
    total = len(breakdown.get("components") or []) or len(missing)
    scored = total - len(missing)
    pct = (breakdown.get("available_weight") or 0.0) * 100
    return (f"Scored on {scored} of {total} components ({pct:.0f}% of the weight); "
            f"the rest is renormalised away.")


def readiness_alcohol_caption(breakdown: dict) -> str:
    """Alcohol as CONTEXT, not as a deduction. Empty on a dry day.

    readiness MODEL_VERSION 2 stopped deducting points for alcohol: it is
    self-reported and the one input Oura cannot see, so scoring it made our
    number and Oura's incomparable on exactly the days most worth comparing.
    The units are still worth showing — they explain a low HRV balance or a
    poor previous night far better than the components alone do — so this
    reports them while being explicit that the score does not include them.

    services.scheduling still acts on alcohol independently (consecutive-day
    trigger, straight from the check-in), so nothing safety-relevant rests on
    this caption."""
    units = breakdown.get("alcohol_units")
    if not units:
        return ""
    unit_word = "unit" if abs(units - 1.0) < 1e-9 else "units"
    return (f"{units:g} {unit_word} of alcohol logged. Not deducted from the "
            f"score — it is self-reported and Oura cannot see it, so leaving "
            f"it out keeps this number comparable with Oura's.")


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


_NAP_TYPE_LABELS = {"late_nap": "Late nap", "sleep": "Nap", "long_sleep": "Second sleep"}


def sleep_naps_display(detail: dict | None) -> dict | None:
    """The nap panel: one row per nap, plus the day total the engine actually
    scored. None when the day has no qualifying nap, which is the overwhelming
    majority of days — the panel should not appear at all rather than appear
    empty.

    This exists because the Sleep drill-down otherwise contradicts itself the
    moment a nap is involved: every other number on that screen describes the
    main night (it has to — the hypnogram, the stage shares and the vitals all
    come from one continuous period), while readiness and Sleep Score were
    computed from the day total. Stating both, and labelling which is which,
    is the only version that isn't quietly wrong."""
    d = detail or {}
    naps = d.get("naps") or []
    if not naps:
        return None
    rows = []
    for n in naps:
        label = _NAP_TYPE_LABELS.get(str(n.get("type") or ""), "Nap")
        start = format_clock(n.get("bedtime_start"))
        rows.append({
            "label": label if not start else f"{label} · {start}",
            "duration": format_duration(n.get("total_seconds")) or "—",
            "efficiency": (f"{n['efficiency']:.0f} %"
                           if n.get("efficiency") is not None else ""),
        })
    return {
        "rows": rows,
        "nap_total": format_duration(d.get("nap_seconds")) or "—",
        "day_total": format_duration(d.get("day_total_seconds")) or "—",
        "night_total": format_duration(d.get("total_seconds")) or "—",
        "count": len(rows),
    }


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
        return {"values": [], "low": None, "high": None, "average": None, "count": 0,
                "indices": [], "interval": None, "timestamp": None}

    values = [v if isinstance(v, (int, float)) else None for v in items]
    indices = list(range(len(values)))
    # Downsample by striding, never by averaging: a mean would smooth away the
    # dips and excursions that are the entire reason to plot the night.
    if len(values) > max_points:
        step = len(values) / max_points
        indices = [int(i * step) for i in range(max_points)]
        values = [values[i] for i in indices]

    # `indices` maps each PLOTTED point back to its position in the raw series,
    # which is the only way a clicked point can be given a real clock time
    # after striding. Carried as indices rather than as pre-formatted times so
    # a 180-point night costs one timestamp parse per label actually drawn
    # (see overnight_axis_labels / overnight_point_detail), not 180.
    base = {
        "values": values,
        "indices": indices,
        "interval": (payload or {}).get("interval"),
        "timestamp": (payload or {}).get("timestamp"),
    }
    real = [v for v in values if v is not None]
    if not real:
        return {**base, "low": None, "high": None, "average": None, "count": 0}
    return {
        **base,
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


# ─── Chart axes and point selection (2026-08-03) ────────────────────────────
#  Every chart on the three Home drill-downs was drawn without a labelled axis
#  of either kind: the trend sparklines carried a single number floating beside
#  the last point, the overnight HR/HRV charts were explicitly relativised to
#  the night's own min/max with nothing on screen saying what the min and max
#  were, and the hypnogram had only its two end times. A shape with no scale
#  cannot be read — a 4 ms HRV wobble and a 40 ms collapse drew identically.
#
#  This section is the pure half of the fix: tick VALUES and tick POSITIONS,
#  which slot a click resolves to, and what a selected point should say. The
#  SVG/HTML that draws it lives in styles.py, and the query-param plumbing in
#  app.py, keeping this file renderer-agnostic like the rest of it.

def _tick_step(span: float, intervals: int) -> float:
    """A "nice" (1/2/5 × a power of ten) step of roughly span/intervals.

    Rounds to the NEAREST rung of the ladder rather than up to it, which is
    the difference between an axis that fits its data and one that wastes
    half its height: 34 points of readiness spread over 3 intervals wants a
    step of 11.3, and rounding that up to 20 produces a 40-100 axis for data
    that lives in 57-91. The sqrt thresholds are the standard geometric
    midpoints between rungs (d3's tickIncrement uses the same ones), so each
    rough step goes to whichever rung it is genuinely closer to on a log
    scale.
    """
    if not span or span <= 0 or not math.isfinite(span):
        return 1.0
    step0 = span / max(1, int(intervals))
    power = math.floor(math.log10(step0))
    err = step0 / (10.0 ** power)
    if err >= math.sqrt(50):
        mult = 10.0
    elif err >= math.sqrt(10):
        mult = 5.0
    elif err >= math.sqrt(2):
        mult = 2.0
    else:
        mult = 1.0
    return mult * (10.0 ** power)


def value_axis(values, ticks: int = 4, floor: float | None = None,
               cap: float | None = None, max_ticks: int = 6) -> dict | None:
    """Rounded bounds and tick values for a value (Y) axis.

    Returns {"lo", "hi", "step", "ticks"} or None when there is nothing
    numeric to scale. `lo`/`hi` are the ROUNDED bounds and are what the plot
    must be drawn against — scaling the line to the raw min/max while
    labelling the axis with rounded ticks would put every gridline in the
    wrong place, which is worse than no axis at all.

    `floor`/`cap` clamp the rounded bounds to a scale's real limits (0 for a
    duration, 0-100 for a score) so an axis never claims a negative resting
    heart rate or a readiness of 110. They clamp the BOUNDS, never the data:
    a value outside them still plots, it just stops the axis from being
    extended past the point where it means anything.

    `ticks` is a target, `max_ticks` a hard limit — nearest-rung rounding can
    land on a step that fits the data well but produces more gridlines than a
    92px plot can carry, so the step is widened until the count fits.

    A flat series gets a symmetric band around its single level rather than a
    zero-height axis, so the line lands mid-chart instead of on an edge.
    """
    nums = [float(v) for v in values
            if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not nums:
        return None
    lo_raw, hi_raw = min(nums), max(nums)
    if hi_raw == lo_raw:
        pad = abs(hi_raw) * 0.05 or 1.0
        lo_raw, hi_raw = lo_raw - pad, hi_raw + pad

    ticks = max(2, int(ticks))
    step = _tick_step(hi_raw - lo_raw, ticks - 1)
    for _ in range(8):
        lo = math.floor(lo_raw / step) * step
        hi = math.ceil(hi_raw / step) * step
        if (hi - lo) / step + 1 <= max_ticks + 1e-9:
            break
        step = _tick_step(step * 1.5, 1)

    # Clamp ONLY where doing so does not exclude a real reading. `floor`/`cap`
    # describe the scale, and the data is the more authoritative of the two: if
    # a value ever lands outside the nominal limits, the axis must widen to
    # show it rather than quietly plotting it off the edge of the chart.
    if floor is not None and lo < floor <= lo_raw:
        lo = floor
    if cap is not None and hi > cap >= hi_raw:
        hi = cap
    if hi <= lo:
        hi = lo + step

    # Ticks are multiples of `step`, anchored to the grid rather than to `lo`.
    # A clamped bound need not be on the grid (strain's cap of 21 is not a
    # multiple of 5), and starting the sequence at `lo` would drag every tick
    # off round numbers to preserve one that was never round to begin with.
    out, v, guard = [], math.ceil(lo / step - 1e-9) * step, 0
    while v <= hi + step * 1e-9 and guard < 64:
        out.append(round(v, 6))
        v += step
        guard += 1
    return {"lo": round(lo, 6), "hi": round(hi, 6), "step": step, "ticks": out}


def format_axis_value(value: float, step: float) -> str:
    """Tick text at exactly the precision the step justifies — a step of 10
    labelled "60.0" is three characters of noise in a 34px gutter."""
    if step >= 1:
        decimals = 0
    elif step >= 0.1:
        decimals = 1
    else:
        decimals = 2
    return f"{value:.{decimals}f}"


def value_axis_labels(axis: dict | None) -> list[tuple[float, str]]:
    """(fraction from the TOP, text) per tick — the form a positioned gutter
    needs. Top-anchored rather than bottom because that is how an absolutely
    positioned element is placed in CSS, and converting at the call site
    invites getting the flip wrong in one renderer and not the other."""
    if not axis:
        return []
    span = (axis["hi"] - axis["lo"]) or 1.0
    return [((axis["hi"] - t) / span, format_axis_value(t, axis["step"]))
            for t in axis["ticks"]]


def x_axis_labels(labels, max_ticks: int = 5) -> list[tuple[float, str]]:
    """(fraction across, text) for an evenly-spread subset of `labels`.

    Labelling all 30 days of a trend on a phone renders an unreadable smear,
    so a subset is chosen by even spacing with the first and last always
    included — those two anchor the axis and their absence is what made the
    old day-of-week strip ambiguous about which end was today. Blank labels
    are dropped after selection, never before: dropping first would shift
    every remaining tick off the position it labels.
    """
    labels = list(labels)
    n = len(labels)
    if n == 0:
        return []
    if n == 1:
        return [(0.0, str(labels[0]))] if str(labels[0]).strip() else []
    k = max(2, min(int(max_ticks), n))
    picks = sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})
    return [(i / (n - 1), str(labels[i])) for i in picks if str(labels[i]).strip()]


def hit_bands(n: int, max_bands: int = 48) -> list[tuple[float, float, int]]:
    """(left fraction, width fraction, slot index) for the tappable bands laid
    over a chart of `n` slots.

    One band per slot while that stays tappable, and evenly merged above
    `max_bands` — a 180-sample overnight series split 180 ways gives 2px
    targets on a phone, which is not a control. A merged band carries the
    index of the slot at its CENTRE, so the detail it opens is the reading
    under the middle of what was tapped rather than the edge.
    """
    n = int(n)
    if n <= 0:
        return []
    k = max(1, min(int(max_bands), n))
    return [(b / k, 1.0 / k, min(n - 1, int((b + 0.5) * n / k))) for b in range(k)]


def merge_runs(codes: str) -> list[tuple[int, int, str]]:
    """(start, end-exclusive, code) per run of identical characters.

    Shared by the strip renderers (which draw one rect per run instead of one
    per 30-second slot) and by the click path (which reports the whole run a
    tapped slot belongs to, since "Light, 23:41-00:14" is the fact a user
    wants and "slot 412" is not)."""
    out, i, n = [], 0, len(codes or "")
    while i < n:
        j = i
        while j < n and codes[j] == codes[i]:
            j += 1
        out.append((i, j, codes[i]))
        i = j
    return out


def run_at(codes: str, index: int) -> tuple[int, int, str] | None:
    """The run containing `index`, or None when out of range."""
    if not codes or not (0 <= index < len(codes)):
        return None
    start = end = index
    while start > 0 and codes[start - 1] == codes[index]:
        start -= 1
    while end + 1 < len(codes) and codes[end + 1] == codes[index]:
        end += 1
    return (start, end + 1, codes[index])


# ─── Selected point ─────────────────────────────────────────────────────────

def parse_point_selection(raw) -> tuple[str | None, int | None]:
    """`"hist:12"` → ("hist", 12); anything malformed → (None, None).

    The selection arrives as a URL query parameter, so it is user-editable by
    construction and must never be trusted to be in range — every consumer
    below re-checks the index against its own series rather than assuming a
    valid pair means a valid point."""
    if not raw or not isinstance(raw, str) or ":" not in raw:
        return None, None
    chart, _, idx = raw.partition(":")
    chart = chart.strip()
    if not chart:
        return None, None
    try:
        return chart, int(idx)
    except (TypeError, ValueError):
        return None, None


def point_selection_key(chart: str, index: int) -> str:
    """The inverse of parse_point_selection — the one place the wire format is
    written, so the two cannot drift."""
    return f"{chart}:{int(index)}"


def _as_iso_date(d) -> str:
    return d.isoformat() if isinstance(d, date) else str(d or "")


def format_axis_date(value, fmt: str = "%d %b") -> str:
    """A tick label for a dated axis, from either a `date` or an ISO string.

    Both shapes reach here — the trend windows are built as `date` objects
    while the persisted history is keyed by ISO string — and an axis that
    silently renders one of them as `2026-08-03` while the other reads
    `03 Aug` would look like two different charts."""
    if isinstance(value, date):
        return value.strftime(fmt)
    try:
        return date.fromisoformat(str(value)).strftime(fmt)
    except (ValueError, TypeError):
        return str(value or "")


def minutes_between(start_iso: str | None, end_iso: str | None) -> float | None:
    """Span of two ISO timestamps in minutes, or None if either is unusable.

    Compares absolute instants, so a night whose two ends carry different UTC
    offsets (which happens across a DST change, and which Oura has been seen
    to do within a single night — see the duplicate-period note in CLAUDE.md)
    measures the real elapsed time rather than the wall-clock difference."""
    if not start_iso or not end_iso:
        return None
    try:
        from datetime import datetime as _dt
        a = _dt.fromisoformat(str(start_iso))
        b = _dt.fromisoformat(str(end_iso))
    except (ValueError, TypeError):
        return None
    if (a.tzinfo is None) != (b.tzinfo is None):
        return None
    span = (b - a).total_seconds() / 60.0
    return span if span > 0 else None


def clock_axis_labels(start_iso: str | None, total_minutes: float | None,
                      max_ticks: int = 5) -> list[tuple[float, str]]:
    """(fraction across, HH:MM) evenly spaced over a night's window — the time
    axis under the hypnogram and movement strips.

    The strips previously carried only their two end times, which said when
    the night started and ended but nothing about where anything in between
    fell; reading "the long deep block was around 01:30" off it meant
    measuring with a finger."""
    if not start_iso or not total_minutes or float(total_minutes) <= 0:
        return []
    k = max(2, int(max_ticks))
    out = []
    for i in range(k):
        frac = i / (k - 1)
        clock = format_clock_offset(start_iso, frac * float(total_minutes))
        if clock:
            out.append((frac, clock))
    return out


def _fmt_number(value, decimals: int = 0, unit: str = "") -> str:
    if value is None:
        return "—"
    suffix = f" {unit}" if unit else ""
    return f"{float(value):.{decimals}f}{suffix}"


def trend_point_detail(dates, values, index: int, *, unit: str = "",
                       decimals: int = 0, label: str = "Value") -> dict | None:
    """What one point on a dated trend chart says about itself.

    Rows are deliberately comparative rather than a restatement of the number
    already under the cursor: the reading, what it moved FROM (and when — a
    +3 against yesterday and a +3 against nine days ago are different facts),
    and where it sits in the window being drawn. `open_date` is the day the
    point belongs to, so the caller can offer to navigate the whole page there.
    """
    dates = list(dates)
    values = list(values)
    if not (0 <= index < len(dates)) or index >= len(values):
        return None

    iso = _as_iso_date(dates[index])
    value = values[index]
    rows = [{"label": label,
             "value": _fmt_number(value, decimals, unit) if value is not None
                      else "No reading"}]

    if value is not None:
        prev_i = next((i for i in range(index - 1, -1, -1)
                       if values[i] is not None), None)
        if prev_i is not None:
            delta = float(value) - float(values[prev_i])
            gap = index - prev_i
            when = ("previous day" if gap == 1
                    else f"{gap} days earlier ({_as_iso_date(dates[prev_i])})")
            rows.append({"label": f"Change vs {when}",
                         "value": f"{delta:+.{decimals}f}{f' {unit}' if unit else ''}"})

    real = [float(v) for v in values if v is not None]
    if real:
        rows.append({"label": f"Window average ({len(real)} readings)",
                     "value": _fmt_number(sum(real) / len(real), decimals, unit)})
        rows.append({"label": "Window range",
                     "value": f"{_fmt_number(min(real), decimals)} – "
                              f"{_fmt_number(max(real), decimals, unit)}"})

    return {"title": iso, "rows": rows, "open_date": iso}


_METRICS_HISTORY_FIELDS = (
    ("readiness_score", "Readiness", "", 0),
    ("sleep_score", "Sleep Score", "", 0),
    ("sleep_pct", "Sleep vs need", "%", 0),
    ("strain", "Strain", "", 1),
)


def metrics_history_rows(row: dict | None, exclude: str = "") -> list[dict]:
    """The OTHER persisted metrics for a day, for the selected point on the
    30-day trend.

    The point being inspected is already the headline, so it is excluded —
    repeating it directly under itself is the kind of duplication that made
    the adjusted-total note necessary on the Sleep panel. Absent metrics are
    dropped rather than dashed: this block is supplementary, and a stack of
    em-dashes under a real reading reads as a fault in the reading."""
    if not row:
        return []
    out = []
    for key, lbl, unit, decimals in _METRICS_HISTORY_FIELDS:
        if key == exclude:
            continue
        v = row.get(key)
        if v is None:
            continue
        out.append({"label": lbl, "value": _fmt_number(v, decimals, unit)})
    return out


def overnight_axis_labels(series: dict | None, max_ticks: int = 4) -> list[tuple[float, str]]:
    """Clock ticks across an overnight HR/HRV chart.

    Derived from the series' own timestamp and sample interval rather than
    from the night's bedtime window: the two are not the same span (Oura's HR
    series starts when the sensor did, not when bedtime_start says the night
    began), and labelling a chart with a window it was not drawn against is
    how an axis becomes actively misleading. Returns [] when the payload
    lacks either field, which is what an older night looks like."""
    if not series:
        return []
    indices = series.get("indices") or []
    interval = series.get("interval")
    timestamp = series.get("timestamp")
    if len(indices) < 2 or not interval or not timestamp:
        return []
    out = []
    for frac, raw_i in x_axis_labels(indices, max_ticks=max_ticks):
        clock = format_clock_offset(timestamp, float(raw_i) * float(interval) / 60.0)
        if clock:
            out.append((frac, clock))
    return out


def overnight_point_detail(series: dict | None, index: int, *, unit: str,
                           decimals: int = 0) -> dict | None:
    """One sample of an overnight series: when it was taken, what it read, and
    how it sat against the night's own low/high/average — which is the only
    frame that makes an individual sample meaningful, since these charts are
    deliberately scaled to the night rather than to an absolute axis."""
    if not series:
        return None
    values = series.get("values") or []
    if not (0 <= index < len(values)):
        return None
    value = values[index]

    # The sample's clock time is the panel's TITLE, not a row — it is what
    # identifies the point, exactly as the date identifies a point on a trend.
    clock = ""
    indices = series.get("indices") or []
    interval, timestamp = series.get("interval"), series.get("timestamp")
    if index < len(indices) and interval and timestamp:
        clock = format_clock_offset(
            timestamp, float(indices[index]) * float(interval) / 60.0)
    title = clock or "Sample"

    rows = []
    if value is None:
        rows.append({"label": "Reading", "value": "Not measured"})
        return {"title": title, "rows": rows, "open_date": None}

    rows.append({"label": "Reading", "value": _fmt_number(value, decimals, unit)})
    avg = series.get("average")
    if avg is not None:
        rows.append({"label": "vs night average",
                     "value": f"{float(value) - float(avg):+.{max(decimals, 1)}f} {unit}".strip()})
    lo, hi = series.get("low"), series.get("high")
    if lo is not None and hi is not None:
        rows.append({"label": "Night low / high",
                     "value": f"{_fmt_number(lo, decimals)} – {_fmt_number(hi, decimals, unit)}"})
    return {"title": title, "rows": rows, "open_date": None}


def segment_point_detail(codes: str, index: int, *, start_iso: str | None,
                         total_minutes: float | None, labels: dict[str, str],
                         kind: str = "Stage") -> dict | None:
    """The run of a digit-coded strip (hypnogram or movement) containing the
    tapped slot — its class, its clock span and how long it lasted.

    The slot width is derived as total_minutes / len(codes) rather than
    assumed, because the two strips on the Sleep screen are drawn on
    different grids (Oura's hypnogram is 30-second, the fused master is
    per-minute, movement is 30-second) and are only guaranteed to share an
    axis because both are stretched across the same window. Deriving keeps
    the reported times consistent with what is actually on screen instead of
    with whichever grid the code was written against.
    """
    run = run_at(codes or "", index)
    if run is None:
        return None
    start, end, code = run
    n = len(codes)
    rows = [{"label": kind, "value": labels.get(code, "Unknown")}]

    per_slot = (float(total_minutes) / n) if total_minutes and n else None
    if per_slot:
        duration = (end - start) * per_slot
        if start_iso:
            a = format_clock_offset(start_iso, start * per_slot)
            b = format_clock_offset(start_iso, end * per_slot)
            if a and b:
                rows.append({"label": "From", "value": f"{a} – {b}"})
        rows.append({"label": "Duration",
                     "value": format_duration(duration * 60) or "—"})
        same = sum(e - s for s, e, c in merge_runs(codes) if c == code)
        # Label keeps the class name's own casing — lower-casing it read as
        # "Total rem tonight", and REM is an acronym.
        rows.append({"label": f"Total {labels.get(code, 'this class')} tonight",
                     "value": format_duration(same * per_slot * 60) or "—"})
    rows.append({"label": "Share of night",
                 "value": f"{(end - start) / n * 100:.1f} %"})
    return {"title": labels.get(code, "Segment"), "rows": rows, "open_date": None}
