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
    hr_rows: list = field(default_factory=list)
    stage: int | None = None


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
        reads.wake_adjustments, _sources = repo.get_effective_wake_adjustments(
            start=start, end=day.isoformat())
    except Exception:
        pass
    try:
        reads.hr_rows = [r for r in repo.get_session_hr_history(start=start)
                         if str(r.get("date", "")) <= day.isoformat()]
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
        wake_time_adjustments=reads.wake_adjustments, hr_rows=reads.hr_rows)
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
