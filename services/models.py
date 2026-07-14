"""
services/models.py — typed shapes for the core training/phase/session domain.

Dataclasses only, no logic, no I/O. These are the boundary types repository.py
maps raw Notion pages / Sheets rows into, and the types plan.py/sessions.py
operate on. The long tail of read-only dashboard data (trend correlations,
flagged entries, movement risk, macro trends) stays plain dict-shaped in
repository.py — see REFACTOR_NOTES.md for the scoping rationale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class Phase:
    phase_number: int
    name: str
    start_date: str  # ISO date string, e.g. "2026-06-29"
    length_days: int
    status: str  # "active" | "completed" | "upcoming"


@dataclass(frozen=True)
class ExerciseEntry:
    """One exercise as logged in a training session (services.repository) or
    as prescribed in a plan day (training_plan.PLAN) — same shape either way."""
    name: str
    movement_type: str
    planned_sets: int | None = None
    planned_reps: int | None = None
    exercise_rpe: float | None = None
    actual_sets: int | None = None
    total_volume_kg: float | None = None


@dataclass(frozen=True)
class SessionRecord:
    session_date: str  # ISO date string
    session_duration_minutes: float | None
    session_rpe: float | None
    session_au: float | None
    exercises: list[ExerciseEntry] = field(default_factory=list)


@dataclass(frozen=True)
class DayCell:
    date: date
    weekday_label: str
    state: str  # "completed" | "missed" | "planned" | "rest"
    day_number_in_phase: int | None
    # Whatever the caller's session lookup provided for this date — the day
    # strip's own lookup is a cheap {"date": ...} existence check, not a full
    # SessionRecord, so this stays a loose dict rather than forcing one.
    session_ref: dict | None = None


@dataclass(frozen=True)
class CheckInRecord:
    date: str  # ISO date string
    current_condition: str | None
    tightness_score: float | None
    pain_score: float | None
    anatomical_locations: list[str] = field(default_factory=list)
    sensation_tags: list[str] = field(default_factory=list)
    subjective_tightness: str = ""
    alcohol_units: float | None = None
    travel_flag: bool = False
    psych_stress_score: float | None = None  # UI label covers both stress and mental clarity
    # Joint/HSD
    instability_events: int | None = None
    # Gut
    bristol_type: int | None = None
    unusual_stool_colour: bool = False
    # Body
    hunger_deviation: int | None = None
    craving_type: str | None = None
    # Hydration
    thirst_intensity: int | None = None
    electrolytes_taken: bool = False
    sodium_mg: float | None = None
    # Meditation
    meditation_done: bool = False
    meditation_minutes: float | None = None
    relaxation_depth: int | None = None


@dataclass(frozen=True)
class BiometricRecord:
    date: str  # ISO date string
    hrv_ms: float | None = None
    resting_heart_rate: float | None = None
    sleep_duration_hours: float | None = None
    sleep_deep_hours: float | None = None
    active_kcal: float | None = None
    weight_kg: float | None = None
    steps: int | None = None
    # Which "engine_field:source" pairs had only one of Oura/Garmin reporting
    # data for this date — e.g. ("hrv_ms:garmin",) means Oura had no HRV
    # reading, so Garmin's value was used at 100% weight. Empty when both
    # sources agreed or the record predates the Oura/Garmin blend (Sheet1).
    sources_missing: tuple[str, ...] = ()


WeekStatus = Literal["ultimate", "perfect", "normal", "failed", "in_progress", "no_plan"]


@dataclass(frozen=True)
class WeekScore:
    """One Mon-Sun week's training-plan adherence verdict. `status` is only
    meaningful once the week has ended ("in_progress" is a live/display-only
    placeholder for the current week; "no_plan" means zero scheduled
    sessions, e.g. a reassessment gap). `computed_at` is a persistence
    timestamp — None until services.metrics writes the row to Sheets."""
    week_start: str  # ISO date, a Monday
    week_end: str  # ISO date, the following Sunday
    phase_number: int | None
    scheduled: int
    completed: int
    status: WeekStatus
    computed_at: str | None = None


@dataclass(frozen=True)
class StreakInfo:
    current_streak: int
    best_streak: int
    perfect_count: int
    ultimate_count: int
    normal_count: int
    failed_count: int
