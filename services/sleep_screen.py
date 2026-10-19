"""The Sleep drill-down's rules: which panels a night shows, and where each
part of it comes from.

app.py decided these inline while drawing; the phone's API must return the
same decisions (moves HOME-8 to HOME-17, rebuild Phase 2). The numbers come
from services/dashboard.py, unchanged; this module says what to show.

⚠ ALL OR NOTHING, AND THE GATE IS THE SCORE (athlete, 2026-08-25: "I want the
sleep to be fully blank until the data is there, I should be able to review
yesterdays sleep by toggling to yesterday if I want that"). A night detail can
exist while the score does not; half a screen is worse than none of it,
because the reader cannot tell which half to believe. The one exception is a
night only the watch recorded, which says in its own words that there is no
Sleep Score and only the timeline is real.
"""

from __future__ import annotations

from datetime import date

from services.sleep_fusion import WAKE_SOURCE_FUSION, WAKE_SOURCE_MANUAL

#: What each fusion source is called on screen.
SOURCE_TITLES = {
    "fused": "Fused (Oura + Garmin)",
    "oura_only": "Oura",
    "garmin_only": "Garmin",
}

#: What the screen shows for a night (screen_mode).
SCORED = "scored"              # every panel
WATCH_ONLY = "watch_only"      # the watch's timeline and stage split, no score
BLANK = "blank"                # nothing: the reason line and the day arrows
DETAIL_FAILED = "detail_failed"  # scored, but the night's detail could not be read
NO_DETAIL = "no_detail"        # scored, no detail row: nothing below the score

#: The two overnight series panels: (heading, detail key, unit, the headline
#: figure, the secondary figure). Oura puts both on its Readiness screen too.
OVERNIGHT_PANELS = (
    ("Lowest heart rate", "hr_series", "bpm", "low", "average"),
    ("Average HRV", "hrv_series", "ms", "average", "high"),
)
OVERNIGHT_LABELS = {"low": "Lowest", "high": "Max", "average": "Average"}

#: The stage keys of a fusion row's master_*_minutes, in the order the
#: legend lists them, with the hypnogram code each is drawn in.
STAGES = (("awake", "4"), ("rem", "3"), ("light", "2"), ("deep", "1"))


def screen_mode(scored: bool, fused: dict | None, detail: dict | None,
                detail_loaded: bool) -> str:
    """What the night shows: SCORED, WATCH_ONLY, BLANK, DETAIL_FAILED or
    NO_DETAIL. The score decides for everything; a watch-only night (a fusion
    row of source garmin_only with a hypnogram) is the one unscored night
    that still draws."""
    fused = fused or {}
    if not scored:
        if str(fused.get("source")) == "garmin_only" and fused.get("master_hypnogram"):
            return WATCH_ONLY
        return BLANK
    if detail is None:
        return NO_DETAIL if detail_loaded else DETAIL_FAILED
    return SCORED


def _minutes(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def watch_only_stages(fused: dict) -> list[dict]:
    """A watch-only night's stage split, off the fusion row's own minute
    counts: {stage, code, minutes, pct} in legend order. The share is of
    deep + light + REM (time asleep), so Awake has none."""
    asleep = sum(_minutes(fused.get(f"master_{k}_minutes")) for k in ("deep", "light", "rem"))
    rows = []
    for stage, code in STAGES:
        minutes = _minutes(fused.get(f"master_{stage}_minutes"))
        pct = round(minutes / asleep * 100) if asleep and stage != "awake" else None
        rows.append({"stage": stage, "code": code, "minutes": minutes, "pct": pct})
    return rows


def strip_source(fused: dict | None, detail: dict | None, fusion_loaded: bool) -> dict:
    """The stage strip's codes and what produced them: the fused master when
    there is one, else Oura's own sequence. A failed fusion read is named as
    such, so Oura's sequence is never presented as the night's last word when
    the fused one could not be read. Returns {codes, source, title, phantom,
    note} where note is "phantom" (a fused night that counted Oura wake as
    sleep), "watch" (the ring recorded nothing) or "plain"."""
    fused, detail = fused or {}, detail or {}
    codes = str(fused.get("master_hypnogram") or "") or detail.get("hypnogram_30sec") or ""
    if fused.get("master_hypnogram"):
        source = str(fused.get("source") or "oura_only")
        title = SOURCE_TITLES.get(source, "Oura")
    else:
        source = "oura_only"
        title = "Oura" if fusion_loaded else "Oura (fusion unavailable)"
    phantom = fused.get("phantom_wake_minutes")
    note = ("phantom" if source == "fused" and phantom
            else "watch" if source == "garmin_only" else "plain")
    return {"codes": codes, "source": source, "title": title, "phantom": phantom, "note": note}


def strip_window(detail: dict | None, fused: dict | None,
                 minutes_between) -> tuple[str | None, float | None]:
    """(start, minutes) the strips are drawn across: the Oura sleep period's
    bedtime window, else (a watch-only night) the fusion row's own window.
    `minutes_between` is dashboard.minutes_between."""
    detail, fused = detail or {}, fused or {}
    start = detail.get("bedtime_start") or fused.get("window_start_utc")
    total = minutes_between(detail.get("bedtime_start"), detail.get("bedtime_end"))
    if total is None and fused.get("minutes"):
        try:
            total = float(fused["minutes"])
        except (TypeError, ValueError):
            total = None
    return start, total


def movement_caption(fused: dict | None) -> dict | None:
    """The movement strip's caption, or None when the night has no movement:
    {codes, title, details}, details naming what fusion adds and the
    position shifts."""
    fused = fused or {}
    codes = str(fused.get("master_movement") or "")
    if not codes:
        return None
    source = str(fused.get("movement_source") or "")
    details = []
    if source == "fused":
        details.append("ring resolves small motion, watch confirms whole-body")
    shifts = fused.get("movement_position_shifts")
    if shifts not in (None, ""):
        details.append(f"{shifts} position shift{'s' if shifts != 1 else ''}")
    return {"codes": codes, "title": SOURCE_TITLES.get(source, "Movement"), "details": details}


def overnight_axis(series_labels: list, detail: dict | None, format_clock) -> list:
    """The overnight chart's time axis: the series' own timestamps, else the
    night's bedtime window (all an older night has). `format_clock` is
    dashboard.format_clock."""
    if series_labels:
        return series_labels
    detail = detail or {}
    start, end = format_clock(detail.get("bedtime_start")), format_clock(detail.get("bedtime_end"))
    return [(0.0, start), (1.0, end)] if start and end else []


# ─── The wake-time correction (moves HOME-16, HOME-17; fault F5) ─────────────

#: Where a night's correction comes from (Repository.get_effective_wake_adjustments).
FUSION, MANUAL = WAKE_SOURCE_FUSION, WAKE_SOURCE_MANUAL


def wake_control(day: date, adjustments: dict, sources: dict) -> dict:
    """What the wake-time correction shows for one night, and whether the
    athlete's stepper can change it: {minutes, source, editable, caption}.

    ⚠ ON A FUSED NIGHT THE FUSION FIGURE WINS (sleep_fusion.
    effective_wake_adjustments resolves one value per night), so a manual
    value written there changes nothing. The stepper used to offer − and +
    on such a night anyway and credited Oura's pattern for a correction the
    fusion made (inventory fault F5). It now says the fusion applies and
    offers no stepper; a manual correction stays editable everywhere else."""
    key = day.isoformat()
    minutes = float(adjustments.get(key) or 0.0)
    source = sources.get(key, "") if minutes else ""
    if source == FUSION:
        return {"minutes": minutes, "source": FUSION, "editable": False,
                "caption": (f"The fused night already counts {minutes:.0f} min of Oura wake "
                            f"as sleep (Garmin saw no movement), so a manual correction "
                            f"would change nothing.")}
    return {"minutes": minutes, "source": MANUAL if minutes else "", "editable": True,
            "caption": (f"Wake time corrected −{minutes:.0f} min for {key} "
                        f"(known Oura wake-time-overestimation pattern).") if minutes else ""}


def wake_display(day: date, adjustments: dict, window: list[date]) -> dict:
    """The correction as the drill-down marks it: whether this night is
    ADJUSTED, and how many nights of the trend window are."""
    return {"adjusted": bool(adjustments.get(day.isoformat())),
            "nights_adjusted": sum(1 for d in window if adjustments.get(d.isoformat()))}


def contributors_caption(coverage_caption: str, breakdown: dict) -> str:
    """The caption under the sleep contributors: the coverage line, and when
    a wake-time correction applied, that Total sleep and Efficiency include
    it, and so do the figures below (since 2026-08-25 they are the same
    corrected ones, so the note names the correction and stops there)."""
    minutes = breakdown.get("wake_adjustment_minutes") or 0
    if not minutes:
        return coverage_caption
    note = (f"Total sleep and Efficiency include a {minutes:.0f} min wake-time "
            f"correction, and so do the figures below.")
    return f"{coverage_caption} {note}".strip()
