"""Home's three cards for one day: the reads behind them and their numbers.

app.py computed these inline, against reads that counted back from the
server's own today, and the phone's API must return the same numbers for the
phone's date (rebuild rule 3). So the reads and the card numbers live here
with the day as a parameter; app.py keeps the caching and the drawing.

THE DAY SHOWN IS THE DAY EVERY WINDOW ENDS ON (inventory fault F8). The reads
used to count back from the server's today, so a day more than 60 days back
read "not scored" and blamed the ring, and a past day's rest-day strain was
the load heading into TODAY rather than into that day, so the card could
differ from its own point on the 30-day trend. A cache keyed by the day (as
app.py's now are) also stops the windows ending yesterday for half an hour
after midnight (F9).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from services import dashboard as dash
from services import readiness
from services import verdict

#: Biometric days read: 60 supports the 56-night progressive sleep baseline.
BIO_DAYS = 60
#: Session AU days read: the rolling 7-day prior load plus the strain trend.
AU_DAYS = 28
#: Metrics History, wake-time corrections and session heart rate: the 30-day
#: trend in each drill-down, with room for the point detail.
HISTORY_DAYS = 60
#: The drill-downs' persisted trend.
TREND_DAYS = 30
#: Each card's arc is drawn against its scale's top.
SCALES = {"readiness": 100.0, "sleep": 100.0, "strain": 21.0}
#: Why the strain card has no number when the stage could not be read (F7).
STAGE_UNREAD = "The training stage could not be read, so strain is not scored. Reload to try again."


@dataclass
class HomeReads:
    """What the three cards are computed from, for one day. A failed read
    leaves its field empty; `bio_failed` says the biometric read failed,
    because blank cards must not read as a night the ring was not worn, and
    `stage` is None when the stage could not be read (F7)."""
    day: date
    bio_rows: list = field(default_factory=list)
    bio_failed: bool = False
    au_rows: list = field(default_factory=list)
    metrics_history: list = field(default_factory=list)
    wake_adjustments: dict = field(default_factory=dict)
    #: Where each night's correction comes from (fusion or manual): the wake
    #: stepper offers a change only where the manual value would count (F5).
    wake_sources: dict = field(default_factory=dict)
    hr_rows: list = field(default_factory=list)
    stage: int | None = None
    #: The watch's walks and runs no session holds, by date
    #: (Repository.get_watch_cardio): they count on the day walked (2026-10-20).
    walks: dict = field(default_factory=dict)


def window_start(day: date, days: int) -> str:
    return (day - timedelta(days=days)).isoformat()


def read_home(repo, day: date) -> HomeReads:
    """Every read the three cards make, each window ending on `day`."""
    reads = HomeReads(day=day)
    try:
        reads.bio_rows = [asdict(r) for r in repo.get_biometric_rolling(days=BIO_DAYS, today=day)]
    except Exception:
        reads.bio_failed = True
    try:
        reads.au_rows = repo.get_daily_session_au_weighted(AU_DAYS, today=day)
    except Exception:
        pass
    start = window_start(day, HISTORY_DAYS)
    try:
        reads.metrics_history = repo.get_metrics_history(start=start, end=day.isoformat())
    except Exception:
        pass
    try:
        reads.wake_adjustments, reads.wake_sources = repo.get_effective_wake_adjustments(
            start=start, end=day.isoformat())
    except Exception:
        pass
    try:
        reads.hr_rows = [r for r in repo.get_session_hr_history(start=start)
                         if str(r.get("date", "")) <= day.isoformat()]
    except Exception:
        pass
    try:
        reads.walks = repo.get_watch_cardio(start=start, end=day.isoformat())
    except Exception:
        pass
    try:
        reads.stage = repo.get_current_stage()
    except Exception:
        reads.stage = None
    return reads


def sleep_need(bio_rows: list[dict]) -> tuple[float, float | None, int | None]:
    """(need in hours, the progressive baseline, its window in nights): the
    personal baseline (7 -> 14 -> 28 -> 56 nights, outliers under 4 h or over
    11 h removed), else dashboard.SLEEP_NEED_HOURS_DEFAULT."""
    base_hours, base_window = readiness.sleep_baseline(bio_rows)
    return (base_hours or dash.SLEEP_NEED_HOURS_DEFAULT), base_hours, base_window


def snapshot(reads: HomeReads) -> dict:
    """The three numbers for `reads.day`: dashboard.compute_daily_metrics_snapshot
    with the rest-day load counted back from the day shown (F8), and no strain
    when the stage is unknown (F7). Adds the sleep need and the stage's reason."""
    _need, base_hours, base_window = sleep_need(reads.bio_rows)
    snap = dash.compute_daily_metrics_snapshot(
        reads.day, reads.bio_rows, reads.au_rows, reads.stage,
        sleep_base_hours=base_hours, rolling_reference_date=reads.day,
        wake_time_adjustments=reads.wake_adjustments, hr_rows=reads.hr_rows,
        walks=reads.walks)
    snap["sleep_need_hours"] = _need
    snap["sleep_base_window"] = base_window
    snap["strain_unscored_reason"] = STAGE_UNREAD if reads.stage is None else ""
    return snap


def readiness_rows_for(day: date, caller_today: date, engine_rows: list[dict] | None,
                       home_rows: list[dict]) -> list[dict]:
    """The rows the DAILY readiness and its breakdown are computed from. On the
    caller's today, the engine's own (decision.readiness_rows), so the card
    shows the number the session was decided on; on a past day, which has no
    live decision to agree with, Home's rows ending on that day."""
    if day == caller_today and engine_rows is not None:
        return engine_rows
    return home_rows


def readiness_daily(day: date, rows: list[dict]) -> tuple[float | None, dict]:
    """The DAILY readiness and the breakdown that produced it, from ONE set of
    rows (inventory fault F6: the drill-down's contributors were computed
    from 60 rows while today's card showed the 14-row score, so on today the
    card and its breakdown could disagree)."""
    breakdown = readiness.readiness_breakdown(day, rows)
    score = breakdown["score"]
    return (None if score == readiness.NOT_COMPUTED else float(score)), breakdown


def readiness_card(daily: float | None, trend: float | None) -> float | None:
    """The card's headline: today's own score, and the trend on a day with no
    reading of its own."""
    return daily if daily is not None else trend


def verdict_is_due(day: date, caller_today: date) -> bool:
    """The verdict describes today's session, so it shows under today's card
    only: under a past day it would attach a live decision to a day that is
    over."""
    return day == caller_today


def day_bounds(requested: date | None, caller_today: date) -> tuple[date, date, date | None]:
    """(the day shown, the day before, the day after or None): never a day
    after the caller's today."""
    day = min(requested or caller_today, caller_today)
    after = day + timedelta(days=1)
    return day, day - timedelta(days=1), (after if after <= caller_today else None)


def trend_window(day: date) -> list[date]:
    """The TREND_DAYS dates of the drill-downs' persisted trend, ending on the
    day shown."""
    return [day - timedelta(days=TREND_DAYS - 1 - i) for i in range(TREND_DAYS)]


def trend_series(metrics_history: list[dict], day: date,
                 key: str) -> tuple[list[date], list, float | None]:
    """One metric's persisted 30-day trend for a drill-down: the dates ending
    on the day shown, each date's stored value (None where nothing is stored),
    and the latest stored value. From Metrics History, the fixed record, not
    a recomputation."""
    dates = trend_window(day)
    by_date = {r.get("date"): r.get(key) for r in metrics_history}
    values = [by_date.get(d.isoformat()) for d in dates]
    return dates, values, next((v for v in reversed(values) if v is not None), None)


# ─── The Readiness drill-down (moves HOME-14, HOME-15) ──────────────────────

def readiness_key_metrics(row: dict | None, detail: dict | None) -> list[dict]:
    """The 2x2 Oura puts on its own Readiness screen, each {label, value}:
    resting heart rate and HRV from the blend, body temperature and
    respiratory rate from Oura alone. "—" where a night has no reading. The
    temperature is signed on purpose: +0.4 and -0.4 °C are physiologically
    opposite, and an unsigned figure would read as the same reading."""
    row, detail = row or {}, detail or {}

    def num(value, fmt: str, suffix: str = "") -> str:
        return "—" if value is None else f"{fmt.format(value)}{suffix}"

    dev = row.get("oura_temperature_deviation")
    return [
        {"label": "Resting Heart Rate", "value": num(row.get("resting_heart_rate"), "{:.0f}", " bpm")},
        {"label": "Heart Rate Variability", "value": num(row.get("hrv_ms"), "{:.0f}", " ms")},
        {"label": "Body Temperature", "value": "—" if dev is None else f"{dev:+.2f} °C"},
        {"label": "Respiratory Rate", "value": num(detail.get("average_breath"), "{:.1f}", " /min")},
    ]


def readiness_contributors_caption(trend: float | None, breakdown: dict) -> str:
    """The caption under the readiness contributors: why the card's trend and
    this breakdown's daily differ, how much of the model was measured, and
    the alcohol shown but not scored. Each part only when it has something
    to say."""
    return " ".join(c for c in (
        verdict.readiness_scale_caption(trend, breakdown.get("score")),
        dash.readiness_coverage_caption(breakdown),
        dash.readiness_alcohol_caption(breakdown),
    ) if c)


# ─── The three cards, composed (rebuild Phase 2, milestone 5) ────────────────

def date_label(day: date, caller_today: date) -> str:
    """The date bar's words: "TODAY", or the day's ISO date."""
    return "TODAY" if day == caller_today else day.isoformat()


def score_pair(daily: float | None, trend: float | None) -> tuple[tuple[str, str], tuple[str, str]]:
    """The readiness card's two figures, EACH TITLED, ALWAYS: "--" where one
    does not exist yet (athlete, 2026-08-25: "Rather always see both labeled
    even when blank"). Rounded, where the band's own figure truncates
    (dashboard.readiness_meta); the pair is what the card shows."""
    def fmt(value: float | None) -> str:
        return "--" if value is None else f"{float(value):.0f}"
    return ("DAILY", fmt(daily)), ("TREND", fmt(trend))


def _verdict_out(v) -> dict | None:
    if v is None:
        return None
    return {"badge": v.badge, "tone": v.tone, "banner_kind": v.banner_kind,
            "banner_text": v.banner_text, "cause": v.cause, "hrv_note": v.hrv_note,
            "reduced": v.reduced, "has_something_to_say": v.has_something_to_say}


def cards(repo, requested: date | None, caller_today: date) -> dict:
    """Home's three cards for the day asked for (never after the caller's
    today), composed as the Streamlit Home page composes them: the reads
    ending on that day, the snapshot, the DAILY readiness from one set of
    rows (the engine's own on today, F6), each card's band words, and the
    verdict on today only. What the phone's Today screen shows."""
    from services import decision        # here: the heavier module, read on demand
    from services import strain_screen

    day, before, after = day_bounds(requested, caller_today)
    reads = read_home(repo, day)
    snap = snapshot(reads)
    is_today = day == caller_today
    trend = snap["readiness_score"]
    try:
        engine_rows = decision.readiness_rows(repo, day) if is_today else None
        daily, _breakdown = readiness_daily(
            day, readiness_rows_for(day, caller_today, engine_rows, reads.bio_rows))
    except Exception:
        daily = None
    headline = readiness_card(daily, trend)
    r_col, _r_disp, r_lbl, r_hdr, r_desc, r_tert = dash.readiness_meta(headline)
    verdict_out = None
    if verdict_is_due(day, caller_today):
        try:
            verdict_out = _verdict_out(decision.day_verdict(
                repo, day, readiness_display=trend, readiness_band=r_lbl))
        except Exception:
            verdict_out = None
    s_col, s_disp, s_lbl, s_hdr, s_desc = dash.strain_meta(
        snap["strain"], rest_day=bool(snap.get("rest_day")))
    if snap["strain_unscored_reason"]:
        # Not "no workload logged": the load may well be there, the stage is not.
        s_hdr, s_desc = "Not scored", snap["strain_unscored_reason"]
    label = date_label(day, caller_today)
    strain_card_label, _detail = strain_screen.strain_labels(bool(snap["strain_is_rolling"]), label)
    sl_col, sl_disp, sl_lbl, sl_hdr, sl_desc = dash.sleep_meta(
        snap["sleep_score"], snap["sleep_need_hours"], snap["sleep_base_window"])
    return {
        "date": day, "previous": before, "next": after, "is_today": is_today,
        "date_label": label, "bio_failed": reads.bio_failed,
        # No single "display" figure for readiness: the card shows the pair.
        "readiness": {"daily": daily, "trend": trend, "headline": headline,
                      "pair": [{"title": t_, "value": v_} for t_, v_ in score_pair(daily, trend)],
                      "colour": r_col, "label": r_lbl, "header": r_hdr,
                      "description": r_desc, "tertiary": r_tert,
                      "scale": SCALES["readiness"]},
        "strain": {"value": snap["strain"], "display": s_disp,
                   "is_rolling": bool(snap["strain_is_rolling"]),
                   # A rest day says so and shows the 7 days before as its own line.
                   "rest_day": bool(snap.get("rest_day")),
                   "seven_day": snap.get("strain_7d") if snap.get("rest_day") else None,
                   "card_label": strain_card_label, "colour": s_col, "label": s_lbl,
                   "header": s_hdr, "description": s_desc,
                   "unscored_reason": snap["strain_unscored_reason"],
                   "scale": SCALES["strain"]},
        "sleep": {"score": snap["sleep_score"], "display": sl_disp,
                  "need_hours": snap["sleep_need_hours"],
                  "base_window": snap["sleep_base_window"], "colour": sl_col,
                  "label": sl_lbl, "header": sl_hdr, "description": sl_desc,
                  "scale": SCALES["sleep"]},
        "verdict": verdict_out,
        "hrv_7d": dash.fill_7day(reads.bio_rows, "hrv_ms", day),
        "rhr_7d": dash.fill_7day(reads.bio_rows, "resting_heart_rate", day),
    }


def readiness_figures(repo, day: date, caller_today: date) -> dict:
    """The readiness card's figures alone, for GET /api/readiness: DAILY from
    one set of rows (the engine's 14 on the caller's today, else the 60
    ending on `day`), TREND over the 60 ending on `day`, and the headline.
    Not clamped to the caller's today: a later day has no reading, and says
    so. Each window ends on `day` (F8), where Phase 0's route counted a past
    day's 60 rows back from the caller's today."""
    from services import decision

    rows_60 = [asdict(r) for r in repo.get_biometric_rolling(days=BIO_DAYS, today=day)]
    engine_rows = decision.readiness_rows(repo, day) if day == caller_today else None
    daily, _breakdown = readiness_daily(
        day, readiness_rows_for(day, caller_today, engine_rows, rows_60))
    trend = readiness.compute_readiness_trend(day, rows_60)
    trend = None if trend == readiness.NOT_COMPUTED else float(trend)
    return {"daily": daily, "trend": trend, "headline": readiness_card(daily, trend),
            "window_days": (decision.READINESS_WINDOW_DAYS if engine_rows is not None
                            else BIO_DAYS)}


# ── The phone's Today screen (rebuild Phase 5) ───────────────────────────────

#: The week strip on the phone's Today screen: seven days, one readiness ring each.
WEEK_DAYS = 7


def opening_day(requested: date | None, picked_on: date | None, caller_today: date) -> date | None:
    """The day Today opens on when the phone sends the day it shows and the
    day it was picked on (H7, dashboard.home_date_on_open): a past day picked
    today, else today (None). Without `picked_on` the request is taken as it is."""
    if picked_on is None:
        return requested
    chosen = dash.home_date_on_open(requested.isoformat() if requested else None,
                                    picked_on.isoformat(), caller_today)
    return None if chosen == caller_today else chosen


def week_days(day: date, caller_today: date) -> list[date]:
    """The strip's seven days: the seven ending on the caller's today, or,
    when the day shown is older than those, the seven ending on it, so the
    day shown is always on the strip."""
    end = caller_today if (caller_today - day).days < WEEK_DAYS else day
    return [end - timedelta(days=WEEK_DAYS - 1 - i) for i in range(WEEK_DAYS)]


def week_strip(repo, requested: date | None, caller_today: date) -> dict:
    """GET /api/today/week: one readiness figure per day of the strip, each the
    headline that day's own card shows (readiness_figures, the figure
    cards() computes), so a ring and the card it opens never disagree. A day
    whose read fails has no figure, and says "No Readings"."""
    day, _before, _after = day_bounds(requested, caller_today)
    days = []
    for d in week_days(day, caller_today):
        try:
            figure = readiness_figures(repo, d, caller_today)["headline"]
        except Exception:
            figure = None
        days.append({"date": d, "readiness": figure, "label": dash.readiness_meta(figure)[2],
                     "is_today": d == caller_today, "selected": d == day})
    return {"date": day, "days": days}
