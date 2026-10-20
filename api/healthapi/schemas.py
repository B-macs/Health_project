"""Request and response models: the contract with the phone app.

shared/openapi.json is exported from these (python -m healthapi.export_openapi),
and the TypeScript types in app/src/generated come from that file. Never
hand-edit either; change a model here and export again.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class BuildInfo(BaseModel):
    version: str
    commit: str | None
    built: str | None


class CacheInfo(BaseModel):
    mode: str
    exists: bool
    age_s: float | None


class HealthOut(BaseModel):
    """Diagnostics only: no personal reading, ever."""
    status: str
    build: BuildInfo
    python: str
    server_tz: str | None
    server_local_date: date
    started_at: str | None
    cache_rebuilt: bool | None
    cache: CacheInfo
    timings: dict[str, float]


class ReadinessBand(BaseModel):
    """The words services/dashboard.readiness_meta gives a score. The phone
    shows them; it never maps a number to a band itself."""
    label: str
    header: str
    description: str


class ReadinessOut(BaseModel):
    date: date
    daily: float | None
    trend: float | None
    headline: float | None
    band: ReadinessBand
    model_version: int
    window_days: int


class ErrorOut(BaseModel):
    error: str


# ── Today (Home) ─────────────────────────────────────────────────────────────

class Band(BaseModel):
    """A card's band: its colour and words, from services/dashboard.py. The
    phone never maps a number to a band itself."""
    colour: str
    label: str
    header: str
    description: str


class TitledValue(BaseModel):
    title: str
    value: str


class ReadinessCardOut(Band):
    daily: float | None
    trend: float | None
    headline: float | None
    pair: list[TitledValue]
    tertiary: str
    scale: float


class StrainCardOut(Band):
    value: float | None
    display: str
    is_rolling: bool
    card_label: str
    unscored_reason: str
    scale: float


class SleepCardOut(Band):
    score: float | None
    display: str
    need_hours: float
    base_window: int | None
    scale: float


class VerdictOut(BaseModel):
    """Today's training decision, as Home and Training both show it."""
    badge: str
    tone: str
    banner_kind: str
    banner_text: str
    cause: str
    hrv_note: str
    reduced: bool
    has_something_to_say: bool


class TodayOut(BaseModel):
    date: date
    previous: date
    next: date | None
    is_today: bool
    date_label: str
    bio_failed: bool
    readiness: ReadinessCardOut
    strain: StrainCardOut
    sleep: SleepCardOut
    verdict: VerdictOut | None
    hrv_7d: list[float | None]
    rhr_7d: list[float | None]


class WeekDayOut(BaseModel):
    date: date
    #: The headline that day's own card shows; None when there is no reading.
    readiness: float | None
    label: str
    is_today: bool
    selected: bool


class TodayWeekOut(BaseModel):
    """The Today screen's week strip (services/home.py:week_strip)."""
    date: date
    days: list[WeekDayOut]


# ── Today's drill-downs (services/home_detail.py) ────────────────────────────

class LabelValue(BaseModel):
    label: str
    value: str


class PointDetail(BaseModel):
    """What one tapped point of a chart says about itself."""
    title: str
    rows: list[LabelValue]
    open_date: str | None = None
    #: The day's other stored metrics (the 30-day trends only).
    extra: list[LabelValue] = []


class AxisTick(BaseModel):
    """`at` is the fraction across (an X tick) or down from the top (a Y tick)."""
    at: float
    text: str


class ValueAxis(BaseModel):
    lo: float
    hi: float
    step: float
    ticks: list[float]


class TrendChart(BaseModel):
    title: str
    dates: list[date]
    values: list[float | None]
    unit: str
    decimals: int
    headline: str
    subtitle: str
    axis: ValueAxis | None
    y_labels: list[AxisTick]
    x_labels: list[AxisTick]
    #: One per date: the point's tap detail (None past the series' end).
    points: list[PointDetail | None]
    #: Fewer than two readings: the chart shows its empty message.
    empty: bool


class TapBand(BaseModel):
    """A tappable band over a chart or strip, with the detail of the reading
    (or the run) at its centre."""
    left: float
    width: float
    index: int
    detail: PointDetail | None


class OvernightPanel(BaseModel):
    key: str
    title: str
    unit: str
    headline: float
    secondary_label: str
    secondary: float
    average: float | None
    values: list[float | None]
    axis: ValueAxis
    y_labels: list[AxisTick]
    x_labels: list[AxisTick]
    bands: list[TapBand]


class Masthead(BaseModel):
    colour: str
    display: str
    label: str


class ContributorRow(BaseModel):
    key: str | None = None
    label: str
    value_display: str
    weight_display: str | None = None
    scored: bool
    bar_pct: float
    colour: str


class Contributors(BaseModel):
    scored: bool
    rows: list[ContributorRow]
    caption: str
    #: Why there is no score (scored is False): read failed, night not
    #: through yet, or no reading.
    unscored_reason: str


class DetailFrame(BaseModel):
    date: date
    previous: date
    next: date | None
    is_today: bool
    date_label: str
    screen_title: str
    title: str
    masthead: Masthead
    bio_failed: bool
    trend: TrendChart


class ReadinessDetailOut(DetailFrame):
    contributors: Contributors
    key_metrics: list[LabelValue]
    overnight: list[OvernightPanel]


class StripRun(BaseModel):
    start: int
    end: int
    code: str
    name: str


class Strip(BaseModel):
    codes: str
    runs: list[StripRun]
    bands: list[TapBand]


class MovementStrip(Strip):
    title: str
    details: list[str]


class Hypnogram(BaseModel):
    """The stage strip and the movement strip on one clock. `note` is what the
    source line says: "phantom", "watch" or "plain"."""
    empty: bool
    source: str
    title: str
    note: str
    phantom_minutes: float | None
    start: str | None
    minutes: float | None
    x_labels: list[AxisTick]
    stages: Strip | None
    movement: MovementStrip | None


class StageRow(BaseModel):
    key: str
    code: str
    label: str
    duration: str
    pct: str


class WatchStage(BaseModel):
    stage: str
    code: str
    name: str
    minutes: float
    duration: str
    pct: float | None


class WatchOnlyNight(BaseModel):
    stages: list[WatchStage]
    hypnogram: Hypnogram


class SleepDebt(BaseModel):
    value_display: str
    band: str
    filled: int
    colour: str
    hours: float
    threshold: float


class NapRow(BaseModel):
    label: str
    duration: str
    efficiency: str


class Naps(BaseModel):
    rows: list[NapRow]
    nap_total: str
    day_total: str
    night_total: str
    count: int


class SleepNight(BaseModel):
    key_metrics: list[LabelValue]
    fusion_caption: str
    debt: SleepDebt | None
    asleep: str
    in_bed: str
    stages: list[StageRow]
    hypnogram: Hypnogram
    naps: Naps | None
    overnight: list[OvernightPanel]
    vitals: list[LabelValue]


class WakeControl(BaseModel):
    """The wake-time correction (Key Rule 4's one manual correction). The −
    and + buttons send `decrease_to` and `increase_to`."""
    minutes: float
    source: str
    editable: bool
    label: str
    caption: str
    decrease_to: float
    increase_to: float


class SleepDetailOut(DetailFrame):
    adjusted: bool
    #: sleep_screen.screen_mode: scored, watch_only, blank, detail_failed, no_detail.
    mode: str
    contributors: Contributors
    watch_only: WatchOnlyNight | None
    night: SleepNight | None
    wake: WakeControl | None
    nights_adjusted: int


class RegionAcwr(BaseModel):
    value: str
    reason: str
    colour: str
    diagnostic: bool


class RegionRow(BaseModel):
    id: str
    name: str
    short: str
    colour: str
    strain: float | None
    au: float | None
    au_pct: float
    acwr: RegionAcwr | None
    fill_pct: float | None


class RegionPanel(BaseModel):
    """Where the load landed. state "empty" carries `reason` ("rolling" or
    "no_split") and the unmapped names; state "split" carries the rest."""
    state: str
    reason: str | None = None
    unmapped_names: list[str]
    can_show_window: bool
    showing_week: bool
    week: bool | None = None
    window_days: int | None = None
    regions: list[RegionRow] = []
    unattributed_pct: float | None = None
    mapped_only: bool | None = None
    overall: float | None = None
    tick_pct: float | None = None
    regions_total: float | None = None
    thin_sample_pct: float | None = None
    stage: int | None = None
    ceiling: float | None = None
    shares_basis: str | None = None
    shares_version: int | None = None
    non_additive_note: str | None = None


class StrainBlend(BaseModel):
    hr_strain: float
    rpe_strain: float
    hr_weight_pct: int


class StrainSource(BaseModel):
    kind: str
    label: str
    hr_rows: list[LabelValue]
    blend: StrainBlend | None


class StrainDetailOut(DetailFrame):
    is_rolling: bool
    #: Why there is no region panel: the stage could not be read (F7).
    stage_unread: str
    region: RegionPanel | None
    source: StrainSource | None
    hrv_7d: TrendChart
    rhr_7d: TrendChart


class WakeAdjustmentIn(BaseModel):
    date: date
    minutes: float


# ── Status and sync (services/engine_sync.py) ────────────────────────────────

class SyncRun(BaseModel):
    """The engine's last sync run: each step's (ok, error)."""
    day: date | None
    at: str | None
    results: dict[str, tuple[bool, str | None]]
    error: str | None


class Notice(BaseModel):
    """A sync notice: level "error" or "caption"; the phone holds each code's words."""
    level: str
    code: str


class OuraStatus(BaseModel):
    """The Oura login's state. Never a token."""
    kind: str | None
    state: str | None
    needs_authorisation: bool | None
    expires_at: str | None
    seconds_remaining: float | None
    oauth_configured: bool | None


class StatusOut(BaseModel):
    writer: str | None
    offline: bool
    datastore_built_at: str | None
    oura: OuraStatus | None
    last_sync: SyncRun | None
    notices: list[Notice]
    #: Why a sync is due now, or None; only while the engine is the writer.
    sync_due: str | None


class SyncIn(BaseModel):
    #: Sync now even when the daily rule says it is not due.
    force: bool = False


class SyncOut(BaseModel):
    ran: bool
    reason: str | None
    status: SyncRun


# ── Check-in (services/checkin_form.py) ──────────────────────────────────────

class CheckInValues(BaseModel):
    """Every field of the morning check-in; all are required on a save."""
    current_condition: str
    tightness_score: int
    pain_score: int
    anatomical_locations: list[str]
    sensation_tags: list[str]
    subjective_tightness: str
    alcohol_units: float
    travel_flag: bool
    psych_stress_score: int
    instability_events: int
    bristol_type: int
    unusual_stool_colour: bool
    hunger_deviation: int
    thirst_intensity: int
    electrolytes_taken: bool
    meditation_minutes: float
    relaxation_depth: int


class WholeRange(BaseModel):
    field: str
    min: int
    max: int


class DecimalRange(BaseModel):
    field: str
    min: float
    max: float
    step: float


class CheckInFormOut(BaseModel):
    date: date
    #: The days a check-in can be saved for: the caller's today first, then back.
    options: list[date]
    is_today: bool
    #: The day already has an entry: the form opens with it, and the save replaces it.
    existing: bool
    #: The entry could not be read: the form opens at the defaults, and the save merges.
    read_failed: bool
    values: CheckInValues
    conditions: list[str]
    whole: list[WholeRange]
    decimal: list[DecimalRange]
    switches: list[str]
    locations: list[str]
    tags: list[str]


class CheckInIn(BaseModel):
    date: date
    #: The form opened the day's stored entry (GET said existing).
    opened_entry: bool
    #: Strictness lives in the service, which names every problem at once.
    values: dict
