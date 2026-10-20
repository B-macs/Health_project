"""The Strain drill-down's rules: the region panel, the strain source and
the labels.

app.py decided these inline while drawing; the phone's API must return the
same (moves HOME-20 to HOME-24, rebuild Phase 2). The numbers come from
services/strain_regions.py and services/dashboard.py, unchanged; this module
says which numbers and which states apply. app.py keeps the sentences and the
drawing, and the phone keeps its own words in its strings file.
"""

from __future__ import annotations

from datetime import date

from services import dashboard as dash
from services import hr_load
from services import rules
from services import strain_regions as sr
from services.home import SCALES

#: The 0-21 strain scale's top, which the arcs and the region tracks are
#: drawn against (home.SCALES, the one place it is written).
STRAIN_TOP = SCALES["strain"]
#: Region AU days read: the 30-day trend window, plus the day before.
REGION_DAYS = 31


def acwr_ceiling(stage: int | None) -> float | None:
    """The stage's ACWR ceiling, from rules.STAGE_CONSTRAINTS and nowhere else
    (Key Rule 3). None for an unknown stage: the panel then names no
    ceiling, where app.py used to fall back to a copied 1.3."""
    if stage is None:
        return None
    return (rules.STAGE_CONSTRAINTS.get(stage) or {}).get("acwr_ceiling")


def empty_region_data(is_rolling: bool) -> dict:
    """The region panel's data when its reads failed: the panel then states
    its own absence, and the strain number above it is untouched."""
    return {"has_split": False, "unmapped_names": [], "is_rolling": bool(is_rolling)}


def region_data(region_au: dict, stage: int, day: date, stage_start: date | None,
                snapshot: dict, show_week: bool) -> dict:
    """The region panel's data for the day shown (move HOME-20).

    `region_au` is Repository.get_daily_region_au's result. The per-region
    ACWR is computed as of the day shown, with its chronic baseline from the
    stage start (strain_regions.region_acwr, advisory only). On a rest day
    the day has no session to divide; `show_week` then shows the 7 days
    before it instead, and `can_show_window` says whether that week holds
    anything to show, which decides between offering the control and a dead
    one."""
    rows = region_au["rows"]
    acwr = sr.region_acwr(rows, stage, today=day, stage_start=stage_start)
    is_rolling = bool(snapshot.get("strain_is_rolling"))
    week_row = sr.rolling_prior_region_row(rows, day) if is_rolling else None
    data = dash.compute_region_strain_snapshot(
        day, rows, stage, overall_snapshot=snapshot, provenance=region_au,
        acwr_results=acwr, window_row=week_row if show_week else None)
    data["can_show_window"] = bool(is_rolling and week_row)
    return data


def region_panel(data: dict, overall: float | None, stage: int | None) -> dict:
    """What the region panel shows, as fields (move HOME-21).

    state "empty": no split for the day, `reason` "rolling" (a rest day: the
    figure above is the 7-day average) or "no_split" (nothing logged, or
    nothing that maps to a region), with the unmapped names. An unmapped
    region has no number, never a 0.0.

    state "split": each region's strain, AU, share and track fill, the
    overall's tick on every track (a region can never read above it, and the
    three together overrun the axis: the strains do not add), the regions'
    total against the overall, the share's heading (of all load, or of the
    MAPPED load when part of it is unattributed), a thin-sample caveat, the
    unmapped names, the week's fields, and the ceiling (None for an unknown
    stage)."""
    unmapped = list(data.get("unmapped_names") or [])
    if not data.get("has_split"):
        return {"state": "empty", "reason": "rolling" if data.get("is_rolling") else "no_split",
                "unmapped_names": unmapped}
    regions = []
    for region in data["regions"]:
        strain = region["strain"]
        regions.append({
            "id": region["id"], "strain": strain, "au": region.get("au"),
            "au_pct": region.get("au_pct") or 0.0, "acwr": region.get("acwr"),
            "fill_pct": None if strain is None else min(100.0, strain / STRAIN_TOP * 100.0),
        })
    gap, frac = data.get("additivity_gap"), data.get("attributed_fraction")
    unattributed = data.get("unattributed_pct") or 0.0
    return {
        "state": "split",
        "week": data.get("window") == "week",
        "window_days": data.get("window_days") or 0,
        "regions": regions,
        "unattributed_pct": unattributed,
        "mapped_only": unattributed > 0,
        "overall": overall,
        "tick_pct": None if overall is None else max(0.0, min(100.0, overall / STRAIN_TOP * 100.0)),
        "regions_total": None if gap is None or overall is None else gap + overall,
        "thin_sample_pct": (frac * 100.0) if data.get("attributed_is_low") and frac is not None else None,
        "unmapped_names": unmapped,
        "stage": stage,
        "ceiling": acwr_ceiling(stage),
        "shares_basis": data.get("shares_basis"),
        "shares_version": data.get("shares_version"),
    }


#: The method, in the words the Strain screen uses (the owner, 2026-10-20: "more user
#: friendly"). hr_load.SOURCE_LABELS stay the short names stored and listed elsewhere.
SOURCE_WORDS = {
    hr_load.SOURCE_HR: "Your watch's heart rate",
    hr_load.SOURCE_BLENDED: "Your watch's heart rate and your session rating",
    hr_load.SOURCE_RPE: "Your session rating only: the watch had no heart rate for this session",
}

#: Each heart-rate zone in plain words; hr_load.ZONE_LOWER_PCT sets its limits.
ZONE_WORDS = {1: "very easy", 2: "easy", 3: "moderate", 4: "hard", 5: "very hard"}


def _bpm(value) -> str:
    return "—" if value in (None, "") else f"{float(value):.0f} bpm"


def _zone_minutes(minutes) -> str:
    m = float(minutes or 0)
    return "under 1 min" if 0 < m < 1 else f"{m:.0f} min"


def _zone_name(zone: int, hr_max) -> str:
    """"Zone 3, moderate (125-142 bpm)": the limits from the top heart rate the zones
    were set from, or the words alone when it is not known."""
    words = f"Zone {zone}, {ZONE_WORDS.get(zone, '')}".rstrip(", ")
    if not hr_max:
        return words
    low = hr_load.ZONE_LOWER_PCT[zone] * float(hr_max)
    high = hr_load.ZONE_LOWER_PCT.get(zone + 1, 1.0) * float(hr_max)
    return f"{words} ({low:.0f}-{high:.0f} bpm)"


def strain_source(snapshot: dict) -> dict | None:
    """Which method produced the strain, and the heart-rate detail behind it
    when there was one, so a fall back to RPE alone is visible rather than
    silent (move HOME-23). None when there is nothing to say: no strain, or
    the rolling stand-in, which no single method produced.

    {kind: "rpe" or "hr", label, hr_rows: [(name, value)], blend: (HR strain,
    RPE strain, HR weight %) or None}.

    In plain words (the owner, 2026-10-20): the method (SOURCE_WORDS), the average
    and highest heart rate, the minutes in each zone with its heart rates, the
    heart-rate load and the top heart rate the zones come from. The Banister
    figure, a cross-check the strain never used, is not shown."""
    source = snapshot.get("strain_source")
    if not source or source in (hr_load.SOURCE_NONE, "NOT_COMPUTED"):
        return None
    hr = snapshot.get("hr_detail") or {}
    hr_rows = []
    if hr:
        minutes = {int(z): m for z, m in (hr.get("zone_minutes") or {}).items()}
        hr_max = hr.get("hr_max_used")
        load = hr.get("edwards_load")
        hr_rows = [
            ("Average heart rate", _bpm(hr.get("avg_hr"))),
            ("Highest heart rate", _bpm(hr.get("max_hr"))),
            *[(_zone_name(z, hr_max), _zone_minutes(minutes.get(z)))
              for z in sorted(hr_load.ZONE_LOWER_PCT)],
            ("Heart-rate load (minutes × zone number)",
             "—" if load in (None, "") else f"{float(load):.0f}"),
        ]
        if hr_max:
            hr_rows.append(("Zones use your top heart rate", _bpm(hr_max)))
    both = (snapshot.get("strain_hr_only"), snapshot.get("strain_rpe_only"))
    blend = ((both[0], both[1], int(hr_load.HR_BLEND_WEIGHT * 100))
             if hr and all(v is not None for v in both) else None)
    return {"kind": "rpe" if source == hr_load.SOURCE_RPE else "hr",
            "label": SOURCE_WORDS.get(source) or snapshot.get("strain_source_label") or "",
            "hr_rows": hr_rows, "blend": blend}


def strain_labels(is_rolling: bool, date_label: str) -> tuple[str, str]:
    """(the card's label, the drill-down's) (move HOME-24). On a rest day the
    figure is the 7-day average, and "7D AVG" replaces the date."""
    if is_rolling:
        return "STRAIN  ·  7D AVG", "STRAIN · 7D AVG"
    return "STRAIN", f"STRAIN · {date_label}"
