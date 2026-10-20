"""Request and response models of the Training screen (services/
training_screen.py and services/training_session.py): part of the contract
with the phone app, exported to shared/openapi.json with the rest
(healthapi.export_openapi). Never hand-edit the exported files; change a
model here and export again.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


# ── The week ─────────────────────────────────────────────────────────────────

class PhaseOut(BaseModel):
    number: int
    name: str
    start_date: str
    length_days: int
    plan_days: int
    day_num: int | None


class WeekBanner(BaseModel):
    """The rollup banner (training_week.banner); `progress` is
    metrics_logic.week_progress's kind: no_plan, ultimate, perfect, failing
    or normal, with `to_go` sessions to the next line."""
    scheduled: int
    completed: int
    progress: str
    to_go: int
    streak_weeks: int
    streak_all_ultimate: bool
    perfect_count: int
    ultimate_count: int
    #: Last week's verdict while its line shows (a failed week's on the Monday only).
    last_week: str | None


class ScheduleNote(BaseModel):
    """Why a day's session sits where it does; `moved` only when it really moved."""
    text: str
    moved: bool


class StripDay(BaseModel):
    date: date
    weekday_label: str
    #: done, today, missed, planned or rest (training_week.strip_marker).
    marker: str
    state: str
    day_num: int | None
    note: ScheduleNote | None


class RedoOffer(BaseModel):
    offered: bool
    consequences: list[str]


class Gate1Waiting(BaseModel):
    monday: date
    core_done: int
    core_required: int


class Gate1Reason(BaseModel):
    key: str
    label: str


class Gate1Lift(BaseModel):
    lift: str
    first: float | None
    latest: float | None
    target: float | None
    met: bool


class Gate1Card(BaseModel):
    count: dict[str, Any]
    lifts_met: int
    rows: list[Gate1Lift]
    waiting: Gate1Waiting | None
    reasons: list[Gate1Reason]
    flare_this_week: bool
    #: When running starts, in the screen's words (gate1.how_text).
    how: str = ""


class RetestNotice(BaseModel):
    """flexibility.retest_notice: kind warning or info; status tomorrow, ready or blocked."""
    kind: str
    status: str
    reason: str


class GapNext(BaseModel):
    name: str
    start_date: str
    days_away: int


class GapScreen(BaseModel):
    next: GapNext | None
    #: {name, last_date, days: [[day number, day type, date]]}: a block that ran
    #: out of calendar before its last days.
    stranded: dict[str, Any] | None


class CarryPrompt(BaseModel):
    """A missed session's proposed carry; nothing moves until the athlete answers."""
    in_order: bool
    lines: list[str]


class ShiftPrompt(BaseModel):
    """Readiness suggests moving today's session; nothing moves until the athlete answers."""
    reason: str


class TrainingWeekOut(BaseModel):
    phases_readable: bool
    phases_error: str
    today: date | None = None
    phase: PhaseOut | None = None
    banner: WeekBanner | None = None
    repeat_notice: str | None = None
    #: A failed week's repeat holds the load all week (Key Rule 22).
    load_held: bool = False
    redo: RedoOffer | None = None
    gate1: Gate1Card | None = None
    retest: RetestNotice | None = None
    week_start: date | None = None
    is_current_week: bool = False
    can_go_back: bool = False
    can_go_forward: bool = False
    strip: list[StripDay] = []
    viewed_week_status: str | None = None
    gap: GapScreen | None = None
    carry_prompt: CarryPrompt | None = None
    shift_prompt: ShiftPrompt | None = None


# ── One day ──────────────────────────────────────────────────────────────────

class ExerciseLine(BaseModel):
    name: str
    type: str | None
    icon: str
    prescription: str
    laterality: str | None
    mechanics: str


class PlannedDay(BaseModel):
    day_num: int
    plan_days: int
    objective: str | None
    rpe_target: int | None
    exercises: list[ExerciseLine]
    home: list[ExerciseLine]


class SwapOffer(BaseModel):
    available: bool
    #: The logged sessions could not be checked: no swap is offered.
    check_failed: bool
    blockers: list[str]
    warnings: list[str]
    today_objective: str


class LoggedExercise(BaseModel):
    name: str
    movement_type: str | None
    planned_sets: int | None


class LoggedSession(BaseModel):
    rpe: float | None
    minutes: float | None
    au: float | None
    exercises: list[LoggedExercise]


class YogaSuggestion(BaseModel):
    slug: str
    name: str
    minutes: int


class RestView(BaseModel):
    is_today: bool
    yoga_suggestion: YogaSuggestion | None


class VerdictBanner(BaseModel):
    """The session's load decision: kind error, warning, info, neutral or ""."""
    kind: str
    text: str
    cause: str
    acwr_advisory: str


class Adaptation(BaseModel):
    volume_factor: float
    reduced: bool
    banner_kind: str
    volume_note: str
    badge_shown: bool


class WorkoutCard(BaseModel):
    minutes: int
    rpe_target: int
    focus: list[str]
    loaded: bool
    exercise_count: int


class TodayOverview(BaseModel):
    """`screen`: overview, logged, not_started or complete."""
    screen: str
    day_num: int | None
    plan_days: int
    phase_name: str
    objective: str | None = None
    banner: VerdictBanner | None = None
    headline: str | None = None
    subtitle: str | None = None
    card: WorkoutCard | None = None
    release: list[ExerciseLine] = []
    main: list[ExerciseLine] = []
    home: list[ExerciseLine] = []
    first_side: str | None = None
    first_side_note: str | None = None
    adaptation: Adaptation | None = None


class TrainingDayOut(BaseModel):
    """`route`: rest, past_completed (with `logged`; None when its detail could
    not be read), past_missed and future (with `planned` and `swap`), today
    (with `overview`), no_phase (with `gap`) or phases_unreadable."""
    date: date
    route: str
    phases_error: str | None = None
    gap: GapScreen | None = None
    phase: PhaseOut | None = None
    note: ScheduleNote | None = None
    rest: RestView | None = None
    logged: LoggedSession | None = None
    planned: PlannedDay | None = None
    swap: SwapOffer | None = None
    overview: TodayOverview | None = None


# ── The actions ──────────────────────────────────────────────────────────────

#: An id the phone mints for one answer; the same answer sent again is applied once.
ActionId = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


class SwapIn(BaseModel):
    #: The other day: its session comes to today, and today's goes there.
    date: date
    action_id: ActionId | None = None


class AnswerIn(BaseModel):
    #: True: apply the proposal; False: keep as planned, and it is not asked again.
    accept: bool
    action_id: ActionId | None = None


class RedoIn(BaseModel):
    action_id: ActionId | None = None


class Gate1ReasonIn(BaseModel):
    monday: date
    reason: str


class StoredOut(BaseModel):
    stored: bool


# ── Today's session ──────────────────────────────────────────────────────────

class SessionExercise(BaseModel):
    index: int
    name: str
    type: str
    laterality: str | None
    sets: int | None
    reps: int | None
    reps_in_set: int | None
    hold_seconds: float | None
    duration_minutes: float | None
    rest_seconds: float | None
    tempo: str | None
    rep_min: int | None
    rep_max: int | None
    equipment_type: str | None
    increment_size: float | None
    increment_unit: str | None
    weight_kg: float | None
    band_tier: str | None
    icon: str
    warmup: bool
    timed_test: bool
    #: stopwatch, hold, duration, or None for reps.
    timer: str | None
    prescription: str
    mechanics: str
    #: The safety warning, only while its body area is over the strain threshold.
    warning: str
    #: The lift this ramp set prepares.
    ramp_for: int | None
    reps_editable: bool
    #: The stepper's starting values (services/prescription.py), or None.
    entry: dict[str, Any] | None
    previous: dict[str, Any] | None
    previous_caption: str
    delta: str
    delta_direction: str
    entry_caption: str
    contradiction: str | None
    garmin_pull: bool
    garmin_window: list[float] | None
    #: The save screen's review time when the watch verified none.
    estimated_minutes: int


class FlowStep(BaseModel):
    """One position of the guided flow (guided_flow.walk). `event` leads to
    the next entry; "skip" leads to `skip_to`."""
    index: int
    ex_idx: int
    set_num: int
    rep: int
    phase: str
    side: str
    event: str
    record_set: int | None
    rest_begins: bool
    rest_ends: bool
    ending: str | None
    #: When this entry's timer starts by itself (guided_flow.timer_starts):
    #: "on_arrival" (a rest), "after_timer" (a hold reached because the timer
    #: before it ran out), or None (the athlete starts it).
    timer_starts: Literal["on_arrival", "after_timer"] | None
    skip_to: int


class BandTier(BaseModel):
    tier: str
    label: str


class NextDay(BaseModel):
    day_num: int
    objective: str
    exercises: list[ExerciseLine]


class SessionPlanOut(BaseModel):
    """`kind`: plan or accessory."""
    kind: str
    date: date
    day_num: int | None
    #: The block's length in plan days ("Day n of N"); None for the accessory session.
    plan_days: int | None = None
    objective: str
    phase: str
    rpe_target: int | None
    first_side: str
    banner: VerdictBanner
    adaptation: Adaptation
    exercises: list[SessionExercise]
    steps: list[FlowStep]
    model_minutes: int
    min_minutes: int
    #: The save asks which length to keep when the clock passes this (T93); None
    #: when it never asks (the accessory session).
    ask_length_above_minutes: float | None = None
    rest_taken_max_seconds: int
    garmin_configured: bool
    band_tiers: list[BandTier]
    #: Why the accessory session was chosen.
    reasons: list[str]
    next_day: NextDay | None
    note: str = ""


class CompletionIn(BaseModel):
    model_minutes: int = Field(ge=0)
    #: The phone's own clock, in seconds: the first set, and now.
    start_ts: float
    end_ts: float
    rpe: int = Field(ge=1, le=10)
    kind: str = "plan"


class LengthChoice(BaseModel):
    minutes: int
    #: plan or clock.
    source: str
    au: float
    au_by_rpe: list[float]


class CompletionOut(BaseModel):
    clock_minutes: int
    model_minutes: int
    #: The clock ran so far past the plan that the athlete chooses the length.
    ask_length: bool
    choices: list[LengthChoice]


class SideIn(BaseModel):
    """One side's numbers in a set: reps and weight, or a timed hold's seconds."""
    reps: int | None = None
    weight_kg: float | None = None
    seconds: float | None = None


class RawSetIn(BaseModel):
    """One set as the phone saw it (rebuild Phase 6); the engine builds the
    record (session_save.records_from_raw)."""
    set_num: int = Field(ge=1)
    #: When the set was done: the phone's own clock, ISO with its UTC offset.
    completed_at: str
    right: SideIn | None = None
    left: SideIn | None = None
    band_tier: str | None = None
    #: The rest that followed the set: the phone's clock, epoch seconds.
    rest_started_at: float | None = None
    rest_ended_at: float | None = None


class SavedExerciseIn(BaseModel):
    #: Minted by the phone once, before the first send.
    exercise_id: str
    #: The exercise as the session plan gave it (name, type, sets, ...).
    exercise: dict[str, Any]
    #: The stepper's final values.
    actual: dict[str, Any] | None = None
    #: The sets as recorded, one dict per set.
    sets: list[dict[str, Any]] = []
    #: Or the sets' raw facts, from which the engine builds the records.
    raw_sets: list[RawSetIn] = []
    note: str = ""
    garmin_minutes: float | None = None
    garmin_detail: dict[str, Any] | None = None


class SessionSaveIn(BaseModel):
    #: Minted by the phone once: the same body sent again stores one session.
    session_id: str
    date: date
    kind: str = "plan"
    duration_minutes: int = Field(ge=1)
    session_rpe: int = Field(ge=1, le=10)
    notes: str = ""
    #: The session plan's own note (the accessory session's), stored before `notes`.
    plan_note: str = ""
    exercises: list[SavedExerciseIn]


class SessionSaveOut(BaseModel):
    stored: bool
    session_id: str
    exercise_ids: list[str]
    duration_minutes: int
    session_rpe: int
    au: float


class GarminActivity(BaseModel):
    activity_id: str
    name: str
    type: str
    duration_minutes: float | None


class OpenActivityOut(BaseModel):
    found: bool
    activity: GarminActivity | None


class ActivityMinutesOut(BaseModel):
    #: 0 when no activity of today lasts within `window`.
    minutes: float
    detail: dict[str, Any] | None
    window: list[float]


class HeartRateIn(BaseModel):
    date: date
    #: The session's recorded sets by exercise name (each with its time stamp).
    sets_by_exercise: dict[str, list[dict[str, Any]]] = {}
    #: Or the session as the phone saved it: the engine builds its sets the way
    #: the save does (training_session.sets_by_name).
    session: SessionSaveIn | None = None
    duration_minutes: float
    reported_rpe: int | None = None
    #: The athlete's pick when the session did not line up with the watch.
    activity_id: str | None = None
    shift_hours: float = 0.0


class HrCandidate(BaseModel):
    activity_id: str
    name: str
    type: str
    start_time_local: str
    duration_minutes: float | None
    shift_hours: float
    quality: float | None


class HrComparison(BaseModel):
    measured_rpe: float
    measured_au: float
    active_minutes: float | None
    rpe_delta: float | None
    au_delta: float | None
    verdict: str | None
    coverage: float
    low_coverage: bool
    activity: str | None
    covered_exercises: int | None
    total_exercises: int | None


class HeartRateOut(BaseModel):
    """`state`: matched (with `comparison`), choose (with `candidates`) or no_match."""
    state: str
    reason: str
    candidates: list[HrCandidate]
    comparison: HrComparison | None


# ── The "+" menu: yoga and outdoor ───────────────────────────────────────────

class YogaCaution(BaseModel):
    pose: str
    severity: str
    note: str


class YogaPoseOut(BaseModel):
    name: str
    hold_seconds: int | None = None


class YogaFlow(BaseModel):
    slug: str
    name: str
    minutes: int
    rpe: int
    video_url: str
    poses: list[YogaPoseOut]
    cautions: list[YogaCaution]


class YogaCatalogueOut(BaseModel):
    #: False: the stage could not be read, so the cautions are the strictest set.
    stage_read: bool
    flows: list[YogaFlow]


class YogaLogIn(BaseModel):
    slug: str
    session_id: str
    pose_ids: list[str]
    note: str = ""


class LoggedOut(BaseModel):
    #: False: another save already logged it, and nothing was written. The same save
    #: sent again (the outbox, after a lost answer) answers True, as it did the first time.
    logged: bool


class OutdoorActivity(BaseModel):
    activity_id: str
    name: str
    type: str
    duration_minutes: float | None
    distance_km: float | None
    avg_hr: float | None
    logs_as: str
    #: In the hike, walk and trail-run family.
    in_family: bool
    minutes: int
    au_by_rpe: list[float]


class OutdoorListOut(BaseModel):
    date: date
    activities: list[OutdoorActivity]


class OutdoorLogIn(BaseModel):
    date: date
    activity_id: str
    rpe: int = Field(ge=1, le=10)
    session_id: str
    exercise_id: str


class OutdoorLogOut(BaseModel):
    logged: bool
    au: float
    logs_as: str
