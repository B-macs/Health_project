"""Request and response models of the Insights screens, the Sync tab's data
and actions, the Oura login and Settings (services/insights_screens.py,
services/flexibility_screen.py, services/engine_actions.py). Part of the
contract exported to shared/openapi.json (healthapi.export_openapi). Never
hand-edit the exported files; change a model here and export again.

A deep structure a service already defines (the stage status, a slope row,
the shadow report) is carried as an object of its own keys rather than
re-declared field by field here: the service is the specification.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


# ── Strength ─────────────────────────────────────────────────────────────────

class MetricOption(BaseModel):
    label: str
    key: str
    unit: str
    short: str | None = None


class StrengthReadout(BaseModel):
    current: float | None
    previous: float | None
    unit: str
    points: bool
    delta: float | None
    pct: float | None
    #: up, down, flat, or None without both weeks.
    tone: str | None
    labels: list[str]


class Sector(BaseModel):
    kg: float
    sets: int
    unloaded_reps: float
    unloaded_seconds: float


class TonnageWeekOut(BaseModel):
    week_start: date
    training_days: int
    overall: Sector
    upper_body: Sector
    core: Sector
    lower_body: Sector


class TextLine(BaseModel):
    label: str
    text: str


class SplitPart(BaseModel):
    region: str
    points: float
    pct: float


class RegionCard(BaseModel):
    region: str
    points: float
    pct: float
    confidence: float
    index_label: str
    index_text: str
    band: str
    tone: str
    off: bool


class StrengthOut(BaseModel):
    today: date
    load_error: str | None
    overall: float | None
    calibrating: bool
    metrics: list[MetricOption]
    metric: str
    readout: StrengthReadout
    axis: dict[str, float]
    score_series: list[dict[str, Any]]
    tonnage: list[TonnageWeekOut]
    week_labels: list[str]
    unloaded: list[TextLine]
    split: list[SplitPart]
    regions: list[RegionCard]
    unmapped: list[str]
    imbalances: dict[str, Any]
    imbalance_count: int | None


# ── Metabolism ───────────────────────────────────────────────────────────────

class MetabolismMetric(BaseModel):
    label: str
    key: str
    unit: str
    dp: int
    span: float
    src: str
    better: str | None


class PeriodOption(BaseModel):
    label: str
    kind: str


class DatedValue(BaseModel):
    date: date
    value: float


class PeriodWindow(BaseModel):
    kind: str
    offset: int
    start: date
    end: date
    label: str
    sub: str


class ChartAxis(BaseModel):
    """The progress chart's scale (metabolism_screen.chart_axis): the value range and
    the labels, five from the top and five dates across."""
    lo: float
    hi: float
    y_labels: list[str]
    x_labels: list[str]


class MetabolismSeries(BaseModel):
    window: PeriodWindow
    can_back: bool
    can_forward: bool
    points: list[DatedValue]
    runs: list[list[DatedValue]]
    first: DatedValue | None
    last: DatedValue | None
    change: float | None
    #: good, bad, neutral, flat, or None (fault F11).
    tone: str | None
    #: None without a reading in the period.
    axis: ChartAxis | None = None


class LatestWeighIn(BaseModel):
    date: date
    weight_kg: float
    fat_mass_kg: float | None
    fat_free_mass_kg: float | None
    body_fat_pct: float | None


class Cellular(BaseModel):
    device: str
    days_old: int
    date: date
    phase_angle_deg: float | None
    ecw_tbw: float | None


class MetabolismOut(BaseModel):
    today: date
    load_error: str | None
    latest: LatestWeighIn | None
    split: dict[str, float] | None
    metrics: list[MetabolismMetric]
    ranges: list[PeriodOption]
    metric: str
    kind: str
    offset: int
    series: MetabolismSeries
    cellular: Cellular | None
    #: The body-analysis cards in groups: {group, blurb, cards: [{name, value, dp, unit, source}]}.
    analysis: list[dict[str, Any]]


# ── Flexibility ──────────────────────────────────────────────────────────────

class FlexReading(BaseModel):
    test_key: str
    #: The test's name as the screen writes it (the key is the store's).
    label: str = ""
    side: str
    value: float
    unit: str
    load_kg: float | None
    setup_value: float | None
    voided: bool


class FlexTest(BaseModel):
    key: str
    label: str
    unit: str
    slot: int
    slot_label: str
    bilateral: bool
    setup: str
    lock: str
    measurement: str
    what_youre_testing: str
    adapted_from: str
    safety: str
    input_hint: str
    setup_input: str
    takes_load: bool
    prior_setup: float | None
    prior_setup_from_earlier: bool


class FlexCapture(BaseModel):
    cluster: str
    taken_on: date
    cold: bool
    order: list[FlexTest]
    done: list[str]
    readings: list[FlexReading]
    #: The battery's early answer: a pattern means stop here.
    early_pattern: str | None
    early_pattern_label: str
    #: Why the slot that stopped answered as it did (empty with no early answer).
    early_reason: str = ""
    skip_notes: list[str]
    progress: dict[str, int]


class FlexReport(BaseModel):
    cluster_label: str = ""
    assessed_on: date | None
    pattern: str | None
    pattern_label: str
    #: The slot the battery stopped at.
    stopped_at: str = ""
    trusted: bool
    cold: bool
    baseline_sessions: int
    baseline_required: int
    reason: str
    ladder: list[dict[str, Any]]
    slots: list[dict[str, Any]]
    slots_total: int
    slots_not_run: int
    readings: list[FlexReading]
    #: What the battery is waiting on when there is no pattern.
    missing: list[dict[str, Any]]
    stack: dict[str, Any] | None
    stack_refused: str
    retest: dict[str, Any] | None
    retest_text: str


class FlexibilityOut(BaseModel):
    #: empty, populated, or unreadable (with load_error).
    state: str
    load_error: str | None = None
    count: int
    report: FlexReport | None
    capture: FlexCapture | None
    legs_loaded_yesterday: bool
    guide: dict[str, Any]


class CaptureStartIn(BaseModel):
    cold: bool


class CaptureStepIn(BaseModel):
    test_key: str
    #: {side: value}: "left" and "right" for a two-sided test, "" otherwise.
    entered: dict[str, float | None]
    load: float | None = None
    setup_value: float | None = None
    void: bool = False


class MissingEntry(BaseModel):
    test_key: str
    side: str = ""
    setup: bool = False
    value: float | None


class MissingIn(BaseModel):
    entries: list[MissingEntry]


class ClearedOut(BaseModel):
    cleared: bool


# ── Engine Data ──────────────────────────────────────────────────────────────

class EngineDataOut(BaseModel):
    today: date
    load_error: str | None
    directive: dict[str, Any] | None = None
    stage: dict[str, Any] | None = None
    traffic_light: dict[str, Any] | None = None
    acwr: dict[str, Any] | None = None
    volume: list[dict[str, Any]] = []
    #: The volume chart's rounded top (the AU chart's is acwr.chart.hi).
    volume_hi: float | None = None


# ── The Processing Queue, Macro Trends and Sleep Architecture ────────────────

class QueueEntry(BaseModel):
    level: str
    source: str
    parts: str
    summary: str
    movement: str | None = None


class QueueDay(BaseModel):
    date: date
    in_month: bool
    is_today: bool
    #: flag or monitor on a day with warnings.
    level: str | None
    entries: list[QueueEntry]


class YearMonth(BaseModel):
    year: int
    month: int


class QueueOut(BaseModel):
    pending_notes: int
    pending_readiness: int
    year: int
    month: int
    previous: YearMonth
    next: YearMonth
    weeks: list[list[QueueDay]]


class ProcessOut(BaseModel):
    total: int
    errors: list[str]


class TrendsOut(BaseModel):
    regions: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    #: The timeline's 0-10 scale and its dates (insights.score_timeline_axis).
    timeline_axis: dict[str, Any] | None = None
    levels: dict[str, list[dict[str, Any]]]
    gate: dict[str, Any]
    #: Once the data gate opens: the direction, slopes, correlations and interpretation.
    analysis: dict[str, Any] | None


class SleepArchitectureOut(BaseModel):
    load_error: str | None
    counts: dict[str, int] | None = None
    median_phantom_wake: float | None = None
    nights: list[str] = []
    night: dict[str, Any] | None = None
    shadow: dict[str, Any] | None = None


# ── The Sync tab's data and actions ──────────────────────────────────────────

class DataTableOut(BaseModel):
    table: str
    earliest: date | None
    latest: date | None
    rows: list[dict[str, Any]]


class SessionChecksOut(BaseModel):
    warnings: list[str]


class DataCheckTable(BaseModel):
    table: str
    backup_rows: int
    store_rows: int
    #: The backup's rows whose key the store no longer holds.
    missing: int
    #: Up to five of their keys (ids and dates, never a reading).
    examples: list[str]


class DataCheckOut(BaseModel):
    """The daily data check (services/data_check.py): the rows of the newest
    backup that the store no longer holds. Reads only."""
    checked_at: datetime
    backup_name: str | None
    backup_day: date | None
    #: The newest backup is older than two days, so the check misses what came after it.
    backup_stale: bool
    missing_rows: int
    tables: list[DataCheckTable]


class ManualSyncOut(BaseModel):
    kind: str
    result: dict[str, Any]


# ── The Oura login and Settings ──────────────────────────────────────────────

class OuraLoginIn(BaseModel):
    #: Registered on the Oura application; Oura refuses any other.
    redirect_uri: str


class OuraLoginOut(BaseModel):
    authorize_url: str


class OuraCallbackIn(BaseModel):
    code: str
    state: str


class OuraLoginStatus(BaseModel):
    kind: str | None
    state: str | None
    needs_authorisation: bool | None
    expires_at: str | None
    seconds_remaining: float | None
    oauth_configured: bool | None


class SettingsOut(BaseModel):
    plan_start_date: str | None
    #: A plan (any block) is stored: the start date is asked for only on a first run.
    plan_running: bool = True
    writer: str | None
    garmin_configured: bool
    oura_configured: bool
    seeded: bool | None = None
    active_phase: str | None = None
    #: The manual syncs Settings > Data offers (engine_actions.MANUAL_SYNCS).
    manual_syncs: list[str] = []


class PlanStartIn(BaseModel):
    start_date: date
