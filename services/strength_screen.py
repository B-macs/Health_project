"""Insights › Strength's data and rules (move INS-1, rebuild Phase 2,
2026-10-19), so the phone's Strength screen reads one composition with the
Streamlit page: the one read of the training log, the weekly readout, the two
charts' axes, the work done without load, and the region cards.

What the numbers MEAN is services/strength.py's and services/tonnage.py's
subject (read their docstrings); this module only composes them for a screen.

The 2025 peaks (strength_baselines.py) and the clinical profile's imbalances
(patient_profile.py) are personal records, kept out of the engine's image by
rebuild rule 7, so the caller passes them in as `reference` (REFERENCE_KEYS).
"""

from __future__ import annotations

import math
from datetime import date

import training_constants
from services import bioage
from services import sessions
from services import strength
from services import tonnage

#: Weeks of history in the progress display, a rolling window: a week with no
#: eligible work is an explicit zero, never dropped.
WEEKS = 6

#: label -> series key and unit, in the picker's order. "score" is the
#: strength score; the other four are tonnage.
METRICS: dict[str, dict] = {
    "Overall Strength Score":   {"key": "score", "unit": "points", "short": "pts"},
    "Overall Strength Tonnage": {"key": "overall", "unit": "kg", "short": "kg"},
    "Upper Body Tonnage":       {"key": "upper_body", "unit": "kg", "short": "kg"},
    "Core Tonnage":             {"key": "core", "unit": "kg", "short": "kg"},
    "Lower Body Tonnage":       {"key": "lower_body", "unit": "kg", "short": "kg"},
}

#: The body-part cards' order.
REGION_ORDER: tuple[str, ...] = ("upper_body", "core", "lower_body")

#: What `reference` carries: the 2025 peaks that "100" means and the model's
#: other personal constants (strength_baselines.py), and the clinical
#: profile's imbalances (patient_profile.PROFILE["imbalances"]).
REFERENCE_KEYS = ("peaks", "region_prior", "pr_rir", "anchor_date", "anchor_value",
                  "hold_baselines", "imbalances")


def week_label(day: date) -> str:
    """"5 Oct": the day without a leading zero, the month's short name."""
    return f"{day.day} {day.strftime('%b')}"


def kilogram_rows(rows: list[dict], traits: dict[str, dict],
                  unit_kg: dict[str, float] | None = None) -> list[dict]:
    """The log as the strength estimate reads it (the owner, 2026-10-20): a lift
    on a machine that shows stack units (traits' "unit") is converted to
    kilograms where its kilograms per unit is known
    (training_constants.MACHINE_UNIT_KG) and left out where it is not — a stack
    number divided by a 2025 kilogram figure is not a measurement."""
    unit_kg = training_constants.MACHINE_UNIT_KG if unit_kg is None else unit_kg
    out = []
    for row in rows:
        name = row.get("movement_name")
        if (traits.get(name) or {}).get("unit", "kg") == "kg":
            out.append(row)
            continue
        factor = unit_kg.get(name)
        if not factor:
            continue
        sets = [{**s, **{k: float(s[k]) * factor for k in ("weight", "weight_left")
                         if s.get(k) not in (None, "")}} for s in row.get("sets") or []]
        out.append({**row, "sets": sets})
    return out


def read_data(repo, today: date, reference: dict) -> dict:
    """Everything the screen shows, from one unwindowed read of the training
    log (get_all_training_exercises_raw: the only source with per-set reps and
    weight, which the 1RM estimate and the loaded/unloaded split need).

    A failed read is carried as load_error and the screen shows its no-data
    state with a warning: an empty log reads as "you have never trained", and
    only one of the two is a real reading. The muscle-imbalance findings read
    the clinical profile, so they show either way."""
    load_error = None
    try:
        rows = repo.get_all_training_exercises_raw()
    except Exception as exc:
        rows, load_error = [], f"{type(exc).__name__}: {exc}"
    movement_weights = {name: weight for name, (_category, weight)
                        in training_constants.EXERCISE_MOVEMENT_WEIGHT.items()}
    # What a logged set cannot say by itself: its sides and its unit (2026-10-20).
    traits = sessions.exercise_traits()
    # One call, so the headline IS the chart's current level and each region
    # leaves calibration on its own confidence (WP-15, 2026-10-13).
    snapshot = strength.screen(
        kilogram_rows(rows, traits), reference["peaks"], training_constants.EXERCISE_BODY_REGION,
        movement_weights, reference["region_prior"], reference["pr_rir"],
        today=today, weeks=WEEKS, hold_baselines=reference["hold_baselines"])
    series, unmapped = tonnage.weekly_tonnage(
        rows, training_constants.EXERCISE_BODY_REGION, today=today, weeks=WEEKS, traits=traits)
    imbalances = reference["imbalances"] or {}
    return {
        "today": today, "load_error": load_error,
        "overall": snapshot["overall"], "calibrating": snapshot["calibrating"],
        "regions": snapshot["regions"], "core_hold": snapshot["core_hold"],
        "exercises": snapshot["exercises"], "tonnage": series,
        "unmapped": sorted(unmapped), "score_series": snapshot["score_series"],
        "week_labels": [week_label(w.week_start) for w in series],
        "imbalances": imbalances,
        "imbalance_count": bioage.muscle_imbalance_count(imbalances),
    }


def readout(data: dict, label: str) -> dict:
    """This week and last week of the chosen series, and the change:
    {"current", "previous", "labels", "unit", "points", "delta", "pct",
    "tone"}. `pct` is None when last week was zero; `tone` is "up", "down",
    "flat", or None without both weeks."""
    metric = METRICS[label]
    points = metric["key"] == "score"
    if points:
        series = data["score_series"]
        current = series[-1]["level"] if series else None
        previous = series[-2]["level"] if len(series) > 1 else None
    else:
        series = data["tonnage"]
        current = series[-1].value(metric["key"]).kg if series else None
        previous = series[-2].value(metric["key"]).kg if len(series) > 1 else None
    labels = data["week_labels"]
    out = {"current": current, "previous": previous, "unit": metric["unit"],
           "points": points, "delta": None, "pct": None, "tone": None,
           "labels": (labels[-1] if labels else "", labels[-2] if len(labels) > 1 else "")}
    if current is not None and previous is not None:
        delta, pct = tonnage.change(current, previous)
        out.update(delta=delta, pct=pct,
                   tone="flat" if abs(delta) < 5e-2 else ("up" if delta > 0 else "down"))
    return out


def score_axis(points: list[dict]) -> tuple[float, float]:
    """The score chart's y range: 10 below the lowest point and two tens above
    the highest, the span a multiple of 20 so its four gridlines fall on whole
    points (90/77.5/65 printing as 90/78/65 misreads the chart); 0-100 with
    nothing to draw."""
    seen = [v for p in points for v in (p["measured"], p["level"]) if v is not None]
    if not seen:
        return 0.0, 100.0
    lo = max(0.0, (min(seen) // 10) * 10 - 10)
    hi = ((max(seen) // 10) + 2) * 10
    return lo, lo + math.ceil((hi - lo) / 20.0) * 20.0


def tonnage_axis(series: list, key: str) -> tuple[list[float], float]:
    """The tonnage chart's kilograms per week and its rounded top."""
    values = [week.value(key).kg for week in series]
    return values, tonnage.nice_axis_max(max(values) if values else 0.0)


def unloaded_lines(series: list, key: str) -> list[tuple[str, str]]:
    """This week's and last week's work without load under a tonnage chart,
    as (label, text); empty when neither week did any. Held time and reps are
    never added together (tonnage.unloaded_text)."""
    lines = []
    for label, week in (("This week", series[-1] if series else None),
                        ("Last week", series[-2] if len(series) > 1 else None)):
        text = tonnage.unloaded_text(week.value(key)) if week is not None else None
        if text:
            lines.append((label, text))
    return lines


def region_cards(regions: list, core_hold: dict | None = None) -> list[dict]:
    """One card per body part, in REGION_ORDER: its points and share, its
    index ("—" when nothing is measured, never 0), its confidence and band.
    Core has no kilogram scale: from the first timed plank test its card
    shows the hold-time index, marked provisional, never in the headline
    (strength.core_hold_index, decided 2026-10-13). `tone` is "good" once a
    region left calibration, "warn" while it is provisional, "bad" at zero
    confidence, where the card is also marked off."""
    by_id = {r.region: r for r in regions}
    cards = []
    for region in REGION_ORDER:
        state = by_id.get(region)
        if state is None:
            continue
        conf = state.confidence
        established = conf >= strength.CALIBRATION_EXIT
        card = {
            "region": region, "points": state.contribution_points,
            "pct": state.contribution_pct, "confidence": conf,
            "index_label": "Index",
            "index_text": "—" if state.displayed_index is None else f"{state.displayed_index:.1f}",
            "band": "established" if established else "provisional",
            "tone": "good" if established else ("warn" if conf > 0 else "bad"),
            "off": conf <= 0,
        }
        if region == "core" and state.displayed_index is None and core_hold:
            card.update(index_label="Hold time", index_text=f"{core_hold['index']:.1f}",
                        band=f"provisional · hold time · {week_label(core_hold['date'])}",
                        tone="warn", off=False)
        cards.append(card)
    return cards


def split(regions: list) -> list[dict]:
    """The body-parts bar, by id in REGION_ORDER (never by position, which
    would recolour every segment if strength.REGIONS were reordered)."""
    by_id = {r.region: r for r in regions}
    return [{"region": rid, "points": by_id[rid].contribution_points,
             "pct": by_id[rid].contribution_pct}
            for rid in REGION_ORDER if rid in by_id]


# ─── The phone's Strength page, redone (the owner, 2026-10-20) ──────────────
# "Can you review that page and redo it": one answer carries the whole page, so
# no part of it waits on a request of its own (his buttons seemed dead while
# each tap waited for one), and nothing sets an unfinished week against a full
# one (a Tuesday read -54%). Words are the phone's; these give it states and
# numbers.

#: A body area's state on the page (area_rows).
AREA_MEASURED = "measured"   # its % of 2025 is shown
AREA_TOO_FEW = "too_few"     # lifts measured, but not yet enough to show a number
AREA_NONE = "none"           # nothing comparable measured (core: no kilogram scale)
AREA_HOLD = "hold_time"      # core's plank-test score, provisional, never in the headline


def trend(data: dict) -> list[dict]:
    """The strength chart's weeks, oldest first (strength.score_series): the
    week's label, its measured % of 2025 (None without a lift) and the
    headline as it read that week (the middle of its last lifting weeks)."""
    return [{"label": week_label(p["week"]), "measured": p["measured"], "level": p["level"]}
            for p in data["score_series"]]


def area_rows(regions: list, core_hold: dict | None = None) -> list[dict]:
    """Each body area, in REGION_ORDER: `state` (AREA_*), `pct_of_2025` when a
    number may be shown (calibration holds it until the area's confidence
    reaches strength.CALIBRATION_EXIT, never a placeholder 50), `progress`
    toward that point while it is too early (0-1), the lifts measured, and
    for core's plank test its date."""
    by_id = {r.region: r for r in regions}
    rows = []
    for region in REGION_ORDER:
        state = by_id.get(region)
        if state is None:
            continue
        row = {"region": region, "state": AREA_NONE, "pct_of_2025": None, "progress": None,
               "lifts": state.observations, "hold_date": None}
        if state.index is not None and state.confidence >= strength.CALIBRATION_EXIT:
            row.update(state=AREA_MEASURED, pct_of_2025=round(state.displayed_index, 1))
        elif state.index is not None:
            row.update(state=AREA_TOO_FEW,
                       progress=round(min(1.0, state.confidence / strength.CALIBRATION_EXIT), 2))
        elif region == "core" and core_hold:
            row.update(state=AREA_HOLD, pct_of_2025=core_hold["index"], hold_date=core_hold["date"])
        rows.append(row)
    return rows


def volume(series: list) -> dict:
    """The work in kilograms by week (tonnage.weekly_tonnage's window, oldest
    first; its last week is the caller's own and unfinished): each week's
    kilograms by body area; the last FULL week against the full week before
    it (`last_full`, None without two); this week so far (`this_week`); the
    work not counted in kilograms in those two weeks, by area (held time,
    unloaded reps, cable reps in stack units: tonnage.unloaded_text); and the
    chart's top."""
    weeks = [{"label": week_label(w.week_start),
              **{area: w.value(area).kg for area in REGION_ORDER},
              "total": w.value("overall").kg, "current": i == len(series) - 1}
             for i, w in enumerate(series)]
    last_full = None
    if len(series) >= 3:
        full, before = series[-2], series[-3]
        kg, previous = full.value("overall").kg, before.value("overall").kg
        delta, pct = tonnage.change(kg, previous)
        last_full = {"label": week_label(full.week_start), "kg": kg,
                     "previous_label": week_label(before.week_start), "previous_kg": previous,
                     "delta": delta, "pct": pct,
                     "tone": "flat" if abs(delta) < 5e-2 else ("up" if delta > 0 else "down")}
    this_week = None
    if series:
        now = series[-1]
        this_week = {"label": week_label(now.week_start), "kg": now.value("overall").kg,
                     "days": now.training_days}
    unloaded = []
    for which, week in (("last_full", series[-2] if len(series) > 1 else None),
                        ("this_week", series[-1] if series else None)):
        if week is None:
            continue
        for area in REGION_ORDER:
            text = tonnage.unloaded_text(week.value(area))
            if text:
                unloaded.append({"week": which, "area": area, "text": text})
    top = tonnage.nice_axis_max(max((w["total"] for w in weeks), default=0.0))
    return {"weeks": weeks, "hi": top, "last_full": last_full, "this_week": this_week,
            "unloaded": unloaded}
