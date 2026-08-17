"""
services/repository.py — the ONLY place that knows Notion property names or
Google Sheets column names.

Wraps services/clients/notion.py + services/clients/sheets.py (the raw I/O)
and maps to/from services/models.py for the 6 core entities used by plan.py/
sessions.py (Phase, SessionRecord, ExerciseEntry, DayCell, CheckInRecord,
BiometricRecord). The remaining read-only dashboard functions (trends,
correlations, movement risk, flagged entries) are ported here too — same
queries, same shapes — but keep returning plain dicts; converting their long
tail to dataclasses was scoped out (see REFACTOR_NOTES.md).

Every function that used to compute a `date.today()`-based cutoff internally
now takes an optional `today: date | None = None` parameter (defaulting to
date.today()) so repository behavior is testable/deterministic — no hidden
clock reads.

One Repository instance holds one Notion client + one (lazily-built) Sheets
client for its lifetime — a deliberate, behavior-invisible change from the
prior per-call `Client()` construction in db.py/sync_sheets.py.
"""

from __future__ import annotations

import atexit

import dataclasses
import json
import threading
import time
import uuid
from datetime import date, datetime, timedelta

from services import biometrics
from services import content_weighting
from services import dashboard
from services import flexibility
from services import home_snapshot
from services import hr_load
from services import hr_matching
from services import models
from services import oura_auth
from services import readiness
from services import sessions as training_sessions
from services import sleep_fusion
from services import sleep_movement
from services import strain_regions
from services import supabase_store
from services.clients import datastore_reader
from services.clients import datastore_writer
from services.clients import garmin
from services.clients import local_cache
from services.clients import notion
from services.clients import notion_reader
from services.clients import oura
from services.clients import sheets
from services.config import Config


class PhasesCorruptError(Exception):
    """Raised by Repository.get_phases() when the stored 'phases' config
    value exists but fails to parse — deliberately distinct from returning
    [], which means "nothing has ever been configured" and is safe for a
    caller to auto-seed from. See get_phases's docstring."""


# ─── Check-In merge-upsert — CheckInRecord field -> (Notion property name,
#     get_property kind, that field's untouched-widget default in
#     views/checkin.py). save_check_in() uses this to decide, field by
#     field, whether a second same-day submission is "new information" (not
#     equal to its default — the value wins) or "still at the default"
#     (nothing entered — the prior page's value is kept, so a forgotten
#     field on a follow-up check-in doesn't blank out an earlier real
#     entry). Keep in sync with the widget defaults in views/checkin.py. ───
_CHECKIN_FIELD_MAP: dict[str, tuple[str, str, object]] = {
    "current_condition":    ("Condition", "select", "Excellent"),
    "tightness_score":      ("Tightness", "number", 0),
    "pain_score":            ("Pain", "number", 0),
    "anatomical_locations":  ("Body Areas", "multi_select", []),
    "sensation_tags":        ("Sensations", "multi_select", []),
    "subjective_tightness":  ("Note", "rich_text", ""),
    "alcohol_units":         ("Alcohol Units", "number", 0.0),
    "travel_flag":           ("Travel", "checkbox", False),
    "psych_stress_score":    ("Stress Level", "number", 1),
    "instability_events":    ("Instability Events", "number", 0),
    "bristol_type":          ("Bristol Type", "number", 4),
    "unusual_stool_colour":  ("Unusual Stool Colour", "checkbox", False),
    "hunger_deviation":      ("Hunger Deviation", "number", 0),
    "thirst_intensity":      ("Thirst Intensity", "number", 1),
    "electrolytes_taken":    ("Electrolytes Taken", "checkbox", False),
    "meditation_minutes":    ("Meditation Minutes", "number", 0.0),
    "relaxation_depth":      ("Relaxation Depth", "number", 1),
}


_GARMIN_DAILY_HEADER = [
    "date", "steps", "resting_hr", "avg_stress", "sleep_score",
    "sleep_hours", "calories_total", "min_hr", "max_hr", "hrv_ms",
]
_GARMIN_ACTIVITY_HEADER = [
    "activity_id", "date", "name", "type", "start_time_local",
    "duration_minutes", "distance_km", "avg_hr", "max_hr", "calories",
]

# ─── Garmin sleep stages — the sleepLevels segment list that _garmin_daily_row
#     has always fetched and always thrown away. Stored LOSSLESSLY as JSON
#     (variable-length {startGMT,endGMT,activityLevel} segments, 19-38 a
#     night) rather than as a derived minute-string: baking the resampling
#     choice into storage would mean a services/sleep_fusion.py RULES_VERSION
#     bump could never be recomputed without re-calling Garmin.
#     The dto_* columns are Garmin's OWN per-stage totals, kept so
#     totals_match can verify our activityLevel->stage mapping on every single
#     night instead of on the one night it was originally verified against. ──
_GARMIN_SLEEP_STAGES_HEADER = [
    "date", "sleep_start_gmt", "sleep_end_gmt", "utc_offset_minutes",
    "segment_count", "deep_seconds", "light_seconds", "rem_seconds",
    "awake_seconds", "dto_deep_seconds", "dto_light_seconds",
    "dto_rem_seconds", "dto_awake_seconds", "totals_match",
    "sleep_levels_json",
    # ── Movement (sleepMovement), stored as a REDUCED regular grid rather
    #    than losslessly like sleep_levels_json above. Not a preference: raw
    #    sleepMovement is ~78-84k chars a night (707 per-minute segments,
    #    measured across 53 archived nights) against Sheets' 50,000-char cell
    #    limit, so the lossless form simply does not fit. start + interval +
    #    levels[] is equivalent AT 2DP, and ~3.5k chars.
    #
    #    movement_levels is gap-FILLED, with an empty slot for any minute no
    #    segment covered, so every later value keeps its true position. That
    #    matters: 2 of those 53 nights carry real time gaps (4 minutes on
    #    2026-05-27, 1 minute on 2026-06-02), and packing the survivors
    #    end-to-end would shift the rest of the night and produce a plausible,
    #    silently wrong series.
    #
    #    movement_contiguous therefore records whether filling was NEEDED —
    #    a diagnostic, the same way totals_match turns the activityLevel ->
    #    stage mapping from an assumption into a stored, checkable fact.
    "movement_start_gmt", "movement_interval_seconds", "movement_slot_count",
    "movement_contiguous", "movement_gap_slots", "movement_levels",
    # Overnight HR and stress, from the same payload. ~12k and ~8k chars —
    # both comfortably inside one cell, so these stay lossless JSON.
    "sleep_hr_json", "sleep_stress_json",
]
# movement_levels is a comma-joined numeric string; gspread would happily read
# "1.13,0.75,..." as text but a SINGLE-minute night ("1.13") as a float, so the
# column's type would depend on the length of the night. Same hazard class as
# the hypnogram columns, same fix.
_GARMIN_SLEEP_STAGES_NUMERICISE_IGNORE = [
    _GARMIN_SLEEP_STAGES_HEADER.index(c) + 1
    for c in ("movement_levels", "sleep_levels_json", "sleep_hr_json", "sleep_stress_json")
]

# ─── Sleep Fusion — one row per night, the merged Oura+Garmin hypnogram
#     (services/sleep_fusion.py). A DERIVED artefact, deliberately in its own
#     tab rather than as columns on Oura Sleep Periods: rebuild_oura_tabs()
#     refreshes that tab from the Oura API and would clobber anything derived
#     stored there. Deliberately NOT read by the engine — see the module
#     docstring in services/sleep_fusion.py for why. ─────────────────────────
_SLEEP_FUSION_HEADER = [
    "date", "source", "rules_version", "computed_at",
    "window_start_utc", "utc_offset_minutes", "minutes",
    "master_hypnogram", "oura_hypnogram", "garmin_hypnogram", "reason_codes",
    "master_deep_minutes", "master_light_minutes", "master_rem_minutes",
    "master_awake_minutes",
    "master_sleep_hours", "oura_sleep_hours", "garmin_sleep_hours",
    "phantom_wake_minutes", "window_overlap_pct", "agreement_pct",
    "cohen_kappa", "garmin_covered_minutes", "garmin_gap_minutes",
    "garmin_outside_window_minutes", "oura_periods_on_day",
    # ── Movement (services/sleep_movement.py). On the 30-SECOND grid, twice
    #    the resolution of the hypnogram columns above and anchored at the
    #    same window_start, so the two strips share one time axis.
    #    movement_cutpoints records the calibration each series was produced
    #    under — the movement counterpart of rules_version, without which a
    #    re-fit would silently change what a stored "restless" meant.
    "movement_source", "movement_slots", "movement_covered_slots",
    "movement_still_slots", "movement_restless_slots",
    "movement_tossing_slots", "movement_active_slots",
    "movement_position_shifts", "movement_mean_class",
    "master_movement", "oura_movement", "garmin_movement", "movement_cutpoints",
]
# Same hazard as _OURA_NUMERICISE_IGNORE: these are digit-coded strings, and
# gspread would read a 450-digit hypnogram back as an int, then write it out
# as a JSON number no float64 cell can represent.
_SLEEP_FUSION_NUMERICISE_IGNORE = [
    _SLEEP_FUSION_HEADER.index(c) + 1
    for c in ("master_hypnogram", "oura_hypnogram", "garmin_hypnogram", "reason_codes",
              "master_movement", "oura_movement", "garmin_movement",
              # Comma-joined floats: a full night reads as text but a
              # single-cutpoint value would read as a float, making the
              # column's type depend on its content.
              "movement_cutpoints")
]

# ─── Session HR — one row per training session that matched a Garmin
#     activity, holding its Edwards'-TRIMP load and the strain derived from
#     it (services/hr_load.py). Persisted rather than recomputed live because
#     deriving it costs several calls to Garmin's unofficial API; a date with
#     no row here simply falls back to RPE-only strain. ────────────────────
_SESSION_HR_HEADER = [
    "date", "activity_id", "activity_name", "activity_type", "start_time_local",
    "duration_minutes", "overlap_minutes", "avg_hr", "max_hr", "hr_max_used",
    "edwards_load", "hr_strain", "banister_trimp", "total_minutes",
    "zone_source", "zone_minutes_json", "per_exercise_json",
]

# ─── Oura — the 7 "daily summary score" endpoints merged into one row per
#     date, plus vo2_max (also a daily-shaped scalar, though sparse) ────────
_OURA_DAILY_ENDPOINTS = (
    "daily_sleep", "daily_readiness", "daily_activity", "daily_stress",
    "daily_resilience", "daily_spo2", "daily_cardiovascular_age", "sleep_time", "vo2_max",
)

# The order sync_oura_all writes tabs in, most load-bearing first. Oura Daily
# carries the readiness contributors and Oura Sleep Periods carries duration,
# efficiency, the hypnogram, HRV and RHR — between them every number on the
# Home page. The remaining three are archival: nothing on any screen reads
# them, so they are the right thing to still be mid-write when a run is cut
# short. Deliberately NOT the order of _oura_event_specs(), which is shared
# with the historical backfill and pinned by its own test.
_OURA_SYNC_ORDER = ("daily", "sleep_periods", "workouts", "sessions", "rest_mode_periods")


def _working_volume_kg(sets: list[dict]) -> float:
    """Sum of reps x weight across WORKING sets only — the value written to
    every `total_volume_kg`, and the one services/volume.py adds up.

    Warm-up sets are excluded because this is a claim about work done, matching
    services/tonnage.py's own eligibility rule; without that the two weekly
    kilogram figures in the app would disagree the first time a ramp set is
    logged. `actual_sets` deliberately does NOT get the same treatment: it
    counts sets performed, and a ramp set really was performed.

    An absent `is_warmup` reads as a working set, which is what every set logged
    before 2026-08 is."""
    return round(sum((s.get("reps") or 0) * (s.get("weight") or 0.0)
                     for s in sets if not s.get("is_warmup")), 1)

# .sync_state.json key holding an unfinished run's per-tab counts, and how
# long that marker stays resumable. See Repository.oura_sync_progress.
_OURA_SYNC_PROGRESS_KEY = "oura_sync_progress"
_OURA_SYNC_RESUME_MINUTES = 30

# Where the OAuth credential lives, under the SAME key in two stores.
#
# Notion's Config DB is the durable copy: the hosted filesystem is wiped on
# redeploy (key rule 18), and a refresh token lost that way costs a manual
# browser re-authorisation, not just a slow first read. .sync_state.json is
# the fast local copy that every request actually reads — exactly the
# training-checkpoint arrangement two constants above, and for the same
# reason: the durable store is ~136 ms away and this value is read on every
# sync.
_OURA_TOKEN_KEY = "oura_oauth_token"

# Set when persisting a refreshed credential to Notion fails. Surfaced by
# oura_auth_status: the local copy still works, so the sync keeps running,
# but the credential is now one redeploy away from being lost and that must
# not be silent.
_OURA_TOKEN_PERSIST_ERROR_KEY = "oura_token_persist_error"

# Set when Oura answers 401 during a sync, cleared when one succeeds.
#
# The only way to learn that a STATIC token has been revoked. A PAT carries no
# expiry, so nothing about the stored value distinguishes a working one from
# the dead one this project ran on from 2026-08-12 — without this marker,
# oura_auth_status would keep calling that credential healthy and the Home
# banner would never fire on the exact state it was written for.
_OURA_AUTH_FAILURE_KEY = "oura_auth_failure"

# Daily endpoints the current grant does not cover, recorded by
# _sync_oura_daily. Their Oura Daily columns stay permanently blank, which is
# a fact worth being able to answer without re-probing the API — and worth
# distinguishing from "Oura had no data", which looks identical in the sheet.
_OURA_SCOPE_GAPS_KEY = "oura_scope_gaps"

# ⚠ PROCESS-WIDE, not per-Repository, and that is the entire point.
#
# Oura's refresh tokens are SINGLE USE (services/oura_auth.py). The
# background sync thread builds its OWN Repository (key rule 12) while the
# script thread holds another, so an instance lock would serialise nothing —
# both would refresh, one would win, and the loser would persist a token
# Oura had already invalidated. That failure is unrecoverable without a human
# in a browser, which is why this is a module global rather than an attribute.
#
# It does NOT cover two PROCESSES. That is accepted rather than solved: the
# hosted app runs one, and the repair for the cross-process race (a lease in
# the durable store) costs a Notion round trip on every sync to prevent
# something no current deployment can do.
_OURA_REFRESH_LOCK = threading.Lock()

# .sync_state.json key holding the durable Home-card snapshot, keyed by ISO
# date. See services/home_snapshot.py.
_HOME_SNAPSHOT_KEY = "home_snapshots"

#: Completed flexibility assessments, and the one in-progress draft.
#: Kept on local disk rather than in Sheets deliberately: the capture flow runs
#: ~40 minutes across 13 steps, and a network write failing at step 9 would lose
#: the session. Syncing completed assessments onward is a separate, later job —
#: losing the draft is the failure that actually matters.
_FLEXIBILITY_KEY = "flexibility_assessments"
_FLEXIBILITY_DRAFT_KEY = "flexibility_draft"

#: Local MIRROR of the in-progress training checkpoint that set_config stores
#: under "training_progress" in Notion. Same payload, written to local disk on
#: EVERY checkpoint; Notion is written only at session transitions.
#:
#: Why a mirror rather than just writing Notion less often: the stepper value
#: is not cosmetic. views/training.py's _record_completed_set reads
#: st.session_state.tp_actuals LIVE at the moment a set is completed, and
#: _auto_log_session writes exactly that blob — so a reconnect that restored a
#: STALE load would log every subsequent set at the wrong weight, understating
#: weekly tonnage and lowering the next session's clamp ceiling (which
#: _seed_actuals_if_needed derives from get_last_session_all_sets). Dropping
#: the tap-path write entirely was rejected for that reason.
_TRAINING_CHECKPOINT_KEY = "training_checkpoint"
_OURA_DAILY_HEADER = [
    "date",
    "sleep_score", "sleep_total_sleep", "sleep_efficiency", "sleep_restfulness",
    "sleep_rem_sleep", "sleep_deep_sleep", "sleep_latency", "sleep_timing",
    "readiness_score", "readiness_resting_heart_rate", "readiness_hrv_balance",
    "readiness_body_temperature", "readiness_recovery_index", "readiness_sleep_balance",
    "readiness_activity_balance", "readiness_previous_day_activity",
    "readiness_previous_night", "readiness_sleep_regularity",
    # Temperature in DEGREES, against the wearer's own baseline — distinct
    # from readiness_body_temperature above, which is the 0-100 contributor
    # score derived from it. Oura's only published temperature signal: it is
    # nightly, and has no per-session equivalent.
    "readiness_temperature_deviation", "readiness_temperature_trend_deviation",
    "activity_score", "steps", "activity_high_time", "activity_medium_time",
    "activity_low_time", "activity_sedentary_time", "activity_met_minutes",
    "activity_high_met_minutes", "activity_medium_met_minutes",
    "activity_low_met_minutes", "activity_sedentary_met_minutes",
    "activity_non_wear_time", "activity_inactivity_alerts",
    "activity_equivalent_walking_distance", "activity_meters_to_target",
    "activity_target_meters",
    "activity_meet_daily_targets", "activity_move_every_hour",
    "activity_recovery_time", "activity_stay_active",
    "activity_training_frequency", "activity_training_volume",
    "total_calories", "active_calories", "target_calories", "resting_time",
    "stress_high_duration", "stress_recovery_duration", "stress_day_summary",
    "resilience_level", "resilience_sleep_recovery", "resilience_daytime_recovery", "resilience_stress",
    "spo2_average", "spo2_breathing_disturbance_index",
    "vascular_age", "pulse_wave_velocity",
    "sleep_time_status", "sleep_time_recommendation", "sleep_time_optimal_bedtime",
    "vo2_max",
]
# Event-based Oura data — 0-N per day, so each gets its own tab keyed by the
# event's own id (first column below) rather than by date.
_OURA_WORKOUT_HEADER = [
    "workout_id", "day", "activity", "intensity", "calories", "distance_km",
    "start_datetime", "end_datetime", "source",
]
_OURA_SLEEP_PERIOD_HEADER = [
    "sleep_id", "day", "type", "period", "bedtime_start", "bedtime_end",
    "total_sleep_duration", "time_in_bed", "awake_time", "deep_sleep_duration",
    "light_sleep_duration", "rem_sleep_duration", "efficiency", "latency",
    "average_heart_rate", "lowest_heart_rate", "average_hrv", "average_breath",
    "restless_periods",
    # Per-period readiness — for a nap or a split night this genuinely differs
    # from the day-level daily_readiness row, so it isn't a duplicate of it.
    "readiness_score", "readiness_temperature_deviation",
    "sleep_score_delta", "readiness_score_delta",
    "sleep_algorithm_version", "sleep_analysis_reason", "low_battery_alert",
    # Hypnograms — the per-night stage sequence, one digit per block
    # (1=deep, 2=light, 3=REM, 4=awake). The scalar *_duration columns above
    # are these summed; what only these preserve is the ORDER, i.e. sleep
    # architecture (when deep sleep landed, how fragmented the night was).
    # One cell per night, ~180 and ~1,800 chars — nothing like the row
    # explosion that keeps heart_rate.items/met.items excluded.
    # RING-derived only: Oura also returns app_sleep_phase_5_min, which
    # differs on 769 of 781 nights because it reflects user bedtime edits.
    # These columns are digit-coded TEXT — see _OURA_NUMERICISE_IGNORE.
    "sleep_phase_5_min", "sleep_phase_30_sec",
    # Movement — Oura's published 1-4 alphabet (1 no motion, 2 restless,
    # 3 tossing and turning, 4 active), one digit per 30 seconds. Present on
    # 414/414 archived nights, at most 1,800 chars, so it costs a column on
    # the same terms as the hypnograms above.
    #
    # NOT always the same length as sleep_phase_30_sec: both are anchored at
    # bedtime_start, but on 216 of 414 nights the HYPNOGRAM is one 30-second
    # block shorter (movement matches time_in_bed exactly). Consumers align at
    # index 0 and truncate to the shorter — see sleep_movement.oura_movement.
    "movement_30_sec",
    # Overnight HR and HRV — {"interval": 300.0, "items": [...]} as JSON,
    # ~109 samples and ~730 chars each. Small enough to store per night,
    # unlike the top-level heartrate endpoint's full series.
    "sleep_hr_series", "sleep_hrv_series",
]
# Columns whose values are digit strings, not numbers. gspread numericises by
# default, which would turn a hypnogram into a 1,800-digit int and, on the
# next write, a JSON number that no float64 spreadsheet cell can represent.
_OURA_NUMERICISE_IGNORE = {
    "sleep_periods": [
        _OURA_SLEEP_PERIOD_HEADER.index(c) + 1
        for c in ("sleep_phase_5_min", "sleep_phase_30_sec", "movement_30_sec",
                  # The two series are JSON objects and so are not numeric
                  # today, but they are exempted anyway: if Oura ever returned
                  # a bare array of digits, silent numericising would be the
                  # same unrecoverable corruption, and the cost of exempting
                  # a non-numeric column is nil.
                  "sleep_hr_series", "sleep_hrv_series")
    ],
}
_OURA_SESSION_HEADER = [
    "session_id", "day", "type", "start_datetime", "end_datetime", "mood", "motion_count",
]
_OURA_REST_MODE_HEADER = [
    "rest_mode_id", "start_day", "end_day", "end_time",
]
_BIOMETRIC_BLEND_HEADER = [
    "date", "hrv_ms", "resting_heart_rate", "sleep_duration_hours", "steps", "sources_missing",
]
_METRICS_HISTORY_HEADER = [
    "date", "readiness_score", "sleep_pct", "sleep_score", "strain",
    # Which readiness model produced this row's readiness_score. Added with
    # MODEL_VERSION 2 (which rescored from Oura's contributors and dropped the
    # alcohol deduction), so a stored figure is always traceable to the maths
    # behind it -- the same reason sleep_fusion rows carry rules_version and
    # movement_cutpoints. A blank value means version 1.
    "readiness_model_version",
]
_WAKE_TIME_ADJUSTMENTS_HEADER = ["date", "adjustment_minutes"]


# ─── Offline mode — Sheets tab title -> datastore table name.
#
#     The tab titles live in services/clients/sheets.py and the table names
#     in services/datastore_schema.sql; this is the one place the two are
#     tied together, for the same reason every other Sheets column name is
#     confined to this module. Adding a tab means adding a row here AND a
#     table to the schema, or offline reads of it silently return [] (see
#     OfflineWorksheet.get_all_records on why empty rather than raising).
#
#     Sheet1 is absent on purpose: the datastore holds it MAPPED
#     (sheet1_legacy_biometrics, models.BiometricRecord's field names), not
#     under its raw Apple Health export headers, so it cannot be served
#     through this generic path. _sheets_biometric_records handles it
#     directly instead. ────────────────────────────────────────────────────
# How long a FAILED sync waits before being retried — see the durable sync
# throttle section in Repository. Deliberately far shorter than any success
# interval: a transient error should recover within minutes, while a
# persistent one (Sheets quota, expired credentials) must not be retried on
# every single page load.
_SYNC_FAILURE_COOLDOWN_MINUTES = 15

# Distinguishes "the caller supplied None because there is no such row"
# from "the caller supplied nothing, look it up yourself". A plain None
# default would conflate the two and silently re-read the tab per row.
_UNSET = object()


def _cell_eq(a, b) -> bool:
    """Would writing `a` over `b` actually change the cell?

    Compares the way a spreadsheet does, not the way Python does. gspread
    numericises on read, so a value this code wrote as the float 71.0 comes
    back as the int 71, and a blank comes back as "" rather than None. A
    naive != therefore reports "changed" for every row on every sync, which
    is precisely the churn the no-op skip exists to avoid.
    """
    if a is None:
        a = ""
    if b is None:
        b = ""
    if a == b:
        return True
    a_blank = isinstance(a, str) and not a.strip()
    b_blank = isinstance(b, str) and not b.strip()
    if a_blank or b_blank:
        return a_blank and b_blank
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()


def _blank_or_number(val) -> float | None:
    """None for a blank cell, the number otherwise — keeping a genuine 0.

    Distinct from _sheet_float, which maps 0.0 to None as well. That is right
    for the Apple Health rows it was written for, where 0 means "no reading",
    and wrong for a score, where 0 is a reading.
    """
    if val is None:
        return None
    if isinstance(val, str) and not val.strip():
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _row_unchanged(new_values: list, existing: dict | None, header: list[str]) -> bool:
    """True when every cell of `new_values` already holds that value in the
    existing row, so the write can be skipped entirely."""
    if not existing:
        return False
    return all(
        _cell_eq(new, existing.get(col))
        for new, col in zip(new_values, header)
    )

_DATASTORE_TABLE_BY_TAB = {
    sheets.GARMIN_DAILY_WORKSHEET: "garmin_daily",
    sheets.GARMIN_ACTIVITIES_WORKSHEET: "garmin_activities",
    sheets.GARMIN_SLEEP_STAGES_WORKSHEET: "garmin_sleep_stages",
    sheets.SLEEP_FUSION_WORKSHEET: "sleep_fusion",
    sheets.SESSION_HR_WORKSHEET: "session_hr",
    sheets.OURA_DAILY_WORKSHEET: "oura_daily",
    sheets.OURA_WORKOUTS_WORKSHEET: "oura_workouts",
    sheets.OURA_SLEEP_PERIODS_WORKSHEET: "oura_sleep_periods",
    sheets.OURA_SESSIONS_WORKSHEET: "oura_sessions",
    sheets.OURA_REST_MODE_WORKSHEET: "oura_rest_mode",
    sheets.BIOMETRIC_BLEND_WORKSHEET: "biometric_blend",
    sheets.METRICS_HISTORY_WORKSHEET: "metrics_history",
    sheets.WAKE_TIME_ADJUSTMENTS_WORKSHEET: "wake_time_adjustments",
    sheets.WEEKLY_ROLLUP_WORKSHEET: "weekly_rollup",
}


#: Set once per process by Repository._register_mirror_flush_at_exit.
_MIRROR_ATEXIT_REGISTERED = False


class Repository:
    def __init__(self, config: Config):
        self.config = config
        self._notion_client = None
        self._sheets_client = None
        self._garmin_client_obj = None
        self._garmin_login_attempted = False
        self._oura_token_obj = None
        self._datastore_conn = None
        # {(tab_title, ignore_cols): (write_generation, monotonic_ts, rows)}
        self._read_cache: dict = {}
        # {tab_title: worksheet handle} — see _ws.
        self._ws_cache: dict = {}
        # Cache mode only: the LIVE tab handles, kept apart from the
        # offline read handles above. See _write_target.
        self._live_ws_cache: dict = {}
        # (monotonic_ts, {Key: page}) for the whole Config DB — see
        # _config_pages. None means "not fetched, or invalidated by a write".
        self._config_cache: tuple | None = None
        # {tab_title: header} recorded by _ws — the mirror needs COLUMN NAMES
        # for values that reach it as a bare positional list.
        self._ws_headers: dict[str, list[str]] = {}
        self._supabase_store_obj = None
        # Rows written but not yet sent live in supabase_store.OUTBOX, which
        # is PROCESS-WIDE rather than per-Repository. It has to be: the
        # background sync builds its own Repository (key rule 12), so a
        # per-instance buffer never sent anything written on the UI thread —
        # every Notion write and every manual sync button. See MirrorOutbox.
        #: (table, message) of the last mirror failure, or None. Read by the
        #: Sync page — a mirror that quietly stopped working looks exactly
        #: like one that is up to date.
        self.mirror_last_error: tuple[str, str] | None = None

    @property
    def _nc(self):
        """The live Notion client — WRITES ONLY, once offline mode covers
        Notion reads.

        Raises offline for the reason datastore_reader.py's docstring names
        as the worst of the three options: reading a local snapshot while
        writing to the live backend. Every read now goes through _query, so
        everything still reaching this property is a create/update/archive
        (plus save_session_notes' read-modify-write, which is a write path
        whichever half you look at). Letting those through would push a
        value derived from a stale snapshot into the real database."""
        if self.offline:
            raise datastore_reader.DatastoreReadOnlyError(
                "a Notion write was attempted while offline (datastore_path "
                f"= {self.config.datastore_path!r}). Offline mode is "
                "read-only: unset datastore_path / HEALTH_DATASTORE_PATH to "
                "run against live Notion."
            )
        if self._notion_client is None:
            self._notion_client = notion.make_client(self.config)
        return self._notion_client

    @property
    def _sc(self):
        if self._sheets_client is None:
            self._sheets_client = sheets.make_client(self.config)
        return self._sheets_client

    @property
    def offline(self) -> bool:
        """True when this Repository serves Sheets reads from a local
        datastore instead of the Google Sheets API. Public because the Sync
        page has to be able to say so on screen — a page that looks live but
        is reading a snapshot is the failure mode this whole thing has to
        avoid."""
        return bool(self.config.datastore_path
                    and self.config.datastore_mode != "cache")

    @property
    def cached(self) -> bool:
        """True in the HOSTED mode: reads served locally, writes going through
        to the backend AND to the local copy in the same call.

        The distinction from `offline` is the whole point. Offline refuses
        writes because reading a snapshot while writing live is the worst of
        the three options — a session logged into Notion that the cache has
        never heard of makes the next strain and ACWR quietly wrong. Cache
        mode gets the 32 ms reads without that hazard by WRITING THROUGH, so
        the cache cannot be behind the backend for a value this app wrote.
        """
        return bool(self.config.datastore_path
                    and self.config.datastore_mode == "cache")

    @property
    def local_datastore(self) -> bool:
        """Reads come from the local datastore, in either mode."""
        return bool(self.config.datastore_path)

    @property
    def _ds(self):
        """Lazy connection to the datastore. Opened once per Repository
        lifetime, like every other client here — read-only in offline mode so
        a bug that reaches a write path fails at SQLite too, read-WRITE in
        cache mode because that is where write-through lands."""
        if self._datastore_conn is None:
            self._datastore_conn = (
                datastore_writer.connect_rw(self.config.datastore_path)
                if self.cached
                else datastore_reader.connect(self.config.datastore_path))
        return self._datastore_conn

    def datastore_built_at(self) -> str | None:
        """When the offline snapshot was built (datastore_meta.built_at), or
        None if not offline / the marker is absent. The age of the snapshot
        is the single most important thing to show alongside any offline
        reading — "yesterday's data" and "a month-old copy" look identical
        on screen otherwise."""
        if not self.offline:
            return None
        try:
            row = self._ds.execute(
                "SELECT value FROM datastore_meta WHERE key='built_at'").fetchone()
        except Exception:
            return None
        return row[0] if row else None

    def _ws(self, title: str, header: list[str]):
        """A worksheet for `title` — the real Google Sheets tab, or an
        OfflineWorksheet over the datastore when offline. Every _*_ws()
        getter below goes through here, which is what makes offline mode one
        seam rather than fourteen.

        Deliberately an EITHER/OR on config, never a fallback: offline mode
        is not "use the datastore when Sheets fails". Silently serving a
        snapshot to someone who believes they are looking at last night's
        sleep is a worse outcome than an error, so a live read that fails
        keeps failing.

        `header` is unused offline — creating a tab is a write, and the
        datastore's schema is fixed by datastore_schema.sql.

        Memoized per Repository instance (a whole Streamlit process, via
        repo.py's st.cache_resource). The short-lived read cache further down
        saves the get_all_records() call but NOT this, because the handle is
        resolved before _read_records is even entered:
        `self._read_records(self._garmin_daily_ws())` evaluates the getter
        first, so every cache HIT still paid an open_by_key() plus a
        fetch_sheet_metadata() round-trip. Caching here is safe in a way
        caching rows is not — a handle carries no data, so every read through
        it still goes to the API and no invalidation is needed."""
        self._ws_headers[title] = header
        ws = self._ws_cache.get(title)
        if ws is not None:
            return ws
        if self.local_datastore:
            ws = datastore_reader.OfflineWorksheet(
                self._ds, title, _DATASTORE_TABLE_BY_TAB[title])
        else:
            ws = sheets.get_or_create_worksheet(
                self._sc, self.config.google_sheets_id, title, header)
        self._ws_cache[title] = ws
        return ws

    @property
    def _gc(self):
        """Lazy — and logs in at most once per Repository lifetime (a
        Streamlit session, via repo.py's st.cache_resource), since each
        login is a real Garmin SSO round-trip. None if unconfigured; a
        failed login raises once and is not silently retried every call."""
        if not self._garmin_login_attempted:
            self._garmin_login_attempted = True
            self._garmin_client_obj = garmin.make_client(self.config)
        return self._garmin_client_obj

    # ─── Oura credential ─────────────────────────────────────────────────
    #  Was one line: return the static PAT. It is now a lifecycle, because
    #  Oura retired PATs and OAuth access tokens expire. Everything below
    #  exists to keep `_oc` returning a plain string, so the ~10 call sites
    #  that pass it to oura.get_collection stay untouched.

    def _load_oura_token(self) -> oura_auth.OAuthToken | None:
        """The stored OAuth credential: fast local copy first, durable Notion
        copy as the fallback that survives a redeploy.

        A hit in Notion is written back to local disk, so the ~136 ms round
        trip is paid once per process rather than once per sync — the same
        hydrate-on-miss shape as repo.get_repository filling an empty
        datastore from Supabase.

        Never raises. A Config read can fail (offline mode, a Notion blip)
        and the honest answer then is "no credential I can see", which the
        caller already has to handle.
        """
        local = oura_auth.from_json(local_cache.read().get(_OURA_TOKEN_KEY))
        if local:
            return local
        try:
            stored = self.get_config_value(_OURA_TOKEN_KEY)
        except Exception:
            return None
        token = oura_auth.from_json(stored)
        if token:
            local_cache.update({_OURA_TOKEN_KEY: oura_auth.to_json(token)})
        return token

    def _store_oura_token(self, token: oura_auth.OAuthToken,
                          today: date | None = None) -> None:
        """Persist a credential to BOTH stores, local first.

        Local first because it cannot meaningfully fail and because it is
        what the next read in this process uses — getting it written closes
        the window in which a second thread refreshes again. Notion second
        because it is the copy that survives a redeploy, and because it is
        the one that can fail.

        ⚠ A failed durable write is recorded, NOT raised. By the time this is
        called the refresh has already happened and the old refresh token is
        already dead, so raising would abort a sync while leaving the app
        holding the only copy of a credential it just declined to use. The
        marker is what stops that being invisible.
        """
        blob = oura_auth.to_json(token)
        local_cache.update({_OURA_TOKEN_KEY: blob})
        if self.offline:
            # Notion writes raise offline by contract (_nc). Refusing to
            # record the failure here would be noise, not information: the
            # caller deliberately chose a read-only backend.
            return
        try:
            self.set_config(_OURA_TOKEN_KEY, blob, today=today)
            local_cache.update({_OURA_TOKEN_PERSIST_ERROR_KEY: None})
        except Exception as exc:
            local_cache.update({
                _OURA_TOKEN_PERSIST_ERROR_KEY:
                    f"{datetime.now().isoformat(timespec='seconds')}: {exc}"
            })

    def _refresh_oura_token(self, token: oura_auth.OAuthToken
                            ) -> oura_auth.OAuthToken:
        """Redeem the refresh token and persist the replacement.

        PERSIST BEFORE RETURN, unconditionally. The refresh token is spent
        the instant Oura answers, so the response is the only copy of the
        next one in existence — returning it to a caller that might not store
        it is how a credential gets destroyed by a successful call.
        """
        payload = oura.refresh_access_token(
            self.config.oura_client_id, self.config.oura_client_secret,
            token.refresh_token,
        )
        fresh = oura_auth.from_response(payload, previous=token)
        self._store_oura_token(fresh)
        return fresh

    @property
    def _oc(self) -> str | None:
        """A currently-valid Oura bearer token, or None when unconfigured.

        Still returns a plain string — every caller passes it straight to
        oura.get_collection and none of them needs to know which credential
        kind it came from, or that a network round trip may have happened
        here.

        Order is OAuth first, PAT second. A PAT is only reached when no OAuth
        credential is stored, so a working legacy token keeps working and a
        dead one (this project's, since 2026-08-12) is superseded the moment
        the browser flow is run.

        Refresh is guarded by _OURA_REFRESH_LOCK with a re-read inside it —
        classic double-checked locking, and load-bearing here rather than an
        optimisation. Two threads reaching this together must produce ONE
        refresh: the second has to see the first's result instead of spending
        a refresh token that Oura has already invalidated.

        A failed refresh does NOT raise while the current access token is
        still valid. REFRESH_SKEW_SECONDS is a day wide precisely so that a
        transient failure has many retries before anything breaks; turning
        the first one into an exception would throw that away and take the
        sync down for a credential that still works.
        """
        token = self._load_oura_token()
        if token and not oura_auth.needs_refresh(token):
            return token.access_token
        if token and oura_auth.can_refresh(token):
            with _OURA_REFRESH_LOCK:
                # Re-read: another thread may have refreshed while this one
                # waited, in which case its result is the live credential and
                # ours would be a second, fatal redemption.
                token = self._load_oura_token() or token
                if oura_auth.needs_refresh(token):
                    try:
                        token = self._refresh_oura_token(token)
                    except Exception:
                        if not oura_auth.is_expired(token):
                            return token.access_token
                        raise
                return token.access_token
        if token and token.access_token and not oura_auth.is_expired(token):
            # Stored, unexpired, but with nothing to refresh with. Usable
            # now; oura_auth_status is what says it is a dead end.
            return token.access_token
        if self._oura_token_obj is None:
            self._oura_token_obj = oura.make_client(self.config)
        return self._oura_token_obj

    def _record_oura_scope_gap(self, endpoint: str) -> None:
        """Add `endpoint` to the recorded scope gaps, keeping the rest."""
        local_cache.mutate(
            _OURA_SCOPE_GAPS_KEY,
            lambda old: sorted(set(old or []) | {endpoint}),
        )

    def oura_scope_gaps(self) -> list[str]:
        """Endpoints the current grant does not cover. Empty is the normal
        case; a non-empty list means those columns are blank by permission
        rather than because Oura had no data — indistinguishable in the sheet
        and worth being able to answer without re-probing."""
        return list(local_cache.read().get(_OURA_SCOPE_GAPS_KEY) or [])

    def _record_oura_auth_failure(self, exc: Exception) -> None:
        """Remember that Oura rejected the credential, with when and why.

        Local-only, and that is enough: the marker is re-created by the very
        next sync attempt, so losing it to a redeploy costs one page load of
        accuracy rather than the credential itself.
        """
        local_cache.update({
            _OURA_AUTH_FAILURE_KEY:
                f"{datetime.now().isoformat(timespec='seconds')}: {exc}"
        })

    def _clear_oura_auth_failure(self) -> None:
        local_cache.update({_OURA_AUTH_FAILURE_KEY: None})

    def oura_auth_status(self, now: datetime | None = None) -> dict:
        """What credential Oura sync is running on, and whether it is healthy.

        For display — it never includes a token value, so it is safe to
        render and safe to screenshot. `kind` is "oauth", "pat" or "none";
        `state` is oura_auth.status's, plus "pat" for the legacy path.

        This exists because the failure it describes was invisible. A dead
        credential and a flaky network produced the same grey caption for
        five days, over a stretch where the missing data did not read as
        missing — readiness renormalised onto its one surviving component and
        went UP. `needs_authorisation` is the single flag a caller should
        branch on to say so out loud.
        """
        cache = local_cache.read()
        rejected = cache.get(_OURA_AUTH_FAILURE_KEY)
        common = {
            "oauth_configured": bool(self.config.oura_client_id
                                     and self.config.oura_client_secret),
            "persist_error": cache.get(_OURA_TOKEN_PERSIST_ERROR_KEY),
            "rejected": rejected,
        }
        token = self._load_oura_token()
        if token:
            st = dict(oura_auth.status(token, now=now), kind="oauth", **common)
            # An observed 401 outranks anything the stored token claims about
            # itself: a refresh token can be revoked while still looking
            # perfectly refreshable.
            st["needs_authorisation"] = bool(rejected) or st["state"] in (
                "unauthenticated", "expired")
            if rejected:
                st["state"] = "rejected"
            return st
        if self.config.oura_token:
            return {"kind": "pat", "state": "rejected" if rejected else "pat",
                    "expires_at": None, "can_refresh": False, "scope": "",
                    "seconds_remaining": None,
                    "needs_authorisation": bool(rejected), **common}
        return {"kind": "none", "state": "unauthenticated", "expires_at": None,
                "can_refresh": False, "scope": "", "seconds_remaining": None,
                "needs_authorisation": True, **common}

    def save_oura_oauth_token(self, payload: dict,
                              today: date | None = None) -> oura_auth.OAuthToken:
        """Store the token pair a fresh authorisation produced. The entry
        point scripts/authorize_oura.py uses, kept here so the storage rules
        (both stores, local first) have exactly one implementation."""
        token = oura_auth.from_response(payload, previous=self._load_oura_token())
        self._store_oura_token(token, today=today)
        return token

    # ─── Supabase mirror ─────────────────────────────────────────────────
    #  Every Sheets row this class writes is ALSO sent to Supabase, so the
    #  Postgres copy stays current instead of being whatever the last manual
    #  push left. Notion and Sheets remain the system of record; nothing
    #  reads from Postgres. This is the same shape as every other staged
    #  change here (HRV_GARMIN_HOLD, ACWR advisory mode, measured RPE beside
    #  self-reported): run the new path beside the old one, and switch on
    #  evidence rather than on a date.
    #
    #  BUFFERED, NOT PER-ROW. A round trip costs ~136 ms (measured
    #  2026-08-11), so mirroring each row as it is written would add minutes
    #  to a sync that writes a week of nights. Rows accumulate per table and
    #  flush in ONE request each.

    def _mirror_sinks_active(self) -> bool:
        """True when a written row has anywhere to go.

        TWO independent sinks, and gating on Supabase alone was a real bug:
        in cache mode without Supabase configured, nothing was written through
        to the local datastore, so every read after a write served stale rows
        — silently, which is the exact hazard cache mode exists to remove."""
        return self.supabase_configured() or self.cached

    def supabase_configured(self) -> bool:
        return bool(self.config.supabase_url and self.config.supabase_secret_key)

    def _register_mirror_flush_at_exit(self) -> None:
        """Flush whatever is still queued when the PROCESS ends.

        The Streamlit app flushes at the end of every sync chain, but a CLI
        script never calls one — scripts/merge_duplicate_checkins.py and the
        four backfills all write mirrored tables and then simply exit, which
        would drop every row they queued. Five scripts today, and the sixth
        would have to remember; a hook is one place instead of an obligation.

        Registered lazily on first queue and once per process, holding the
        Config rather than the Repository: a Repository owns clients that are
        not thread-safe and the background sync builds its own, so capturing
        one here would keep an arbitrary instance alive for the whole run.
        Failures are swallowed — the system of record already has the data,
        and raising during interpreter shutdown helps nobody.
        """
        global _MIRROR_ATEXIT_REGISTERED
        if _MIRROR_ATEXIT_REGISTERED:
            return
        _MIRROR_ATEXIT_REGISTERED = True
        config = self.config

        def _flush_on_exit():
            if supabase_store.OUTBOX.size() == 0:
                return
            try:
                Repository(config).flush_supabase_mirror()
            except Exception:
                pass

        atexit.register(_flush_on_exit)

    @property
    def _sb(self):
        """The Supabase client, or None when unconfigured — which is not an
        error, exactly as an absent Garmin login is not."""
        if not self.supabase_configured():
            return None
        if self._supabase_store_obj is None:
            self._supabase_store_obj = supabase_store.SupabaseStore(
                self.config.supabase_url, self.config.supabase_secret_key)
        return self._supabase_store_obj

    def _write_target(self, ws):
        """The worksheet a WRITE should go to.

        In cache mode `_ws()` hands back an OfflineWorksheet — correct for
        reads, and its writes raise. So the write seam resolves the LIVE tab
        by title instead. Two handles for one tab is the honest shape of
        "read local, write live": one object that silently did both would hide
        which side of the split any given call was on.
        """
        if not self.cached:
            return ws
        title = getattr(ws, "title", "")
        live = self._live_ws_cache.get(title)
        if live is None:
            live = sheets.get_or_create_worksheet(
                self._sc, self.config.google_sheets_id, title,
                self._ws_headers.get(title, []))
            self._live_ws_cache[title] = live
        return live

    def _upsert_sheet_row(self, ws, key_value, values: list) -> None:
        """THE Sheets row-write path: write the tab, then queue the same row
        for Supabase. All eleven upsert-by-date/id call sites go through here,
        so the mirror is one seam rather than eleven remembered obligations —
        the same reasoning as _ws for reads.

        Note what this does NOT cover: rebuild_tab/rewrite_worksheet and the
        append_rows batch path, which rewrite a tab wholesale. Those are rare
        maintenance operations, and a wholesale rewrite is what the full push
        is for."""
        sheets.upsert_row_by_key(self._write_target(ws), key_col=1,
                                 key_value=key_value, row_values=values)
        self._queue_mirror_row(getattr(ws, "title", ""), key_value, values)

    def _rewrite_sheet(self, ws, header: list[str], rows: list[list]) -> None:
        """A whole-tab rewrite, mirrored.

        Safe to mirror as plain upserts because every caller here MERGES:
        rebuild_tab carries each existing row through and applies `fresh` over
        it, sync_sleep_fusion and rebuild_oura_tabs do the same. The rewrite
        is always a superset of what the tab held, so no row disappears and
        there is nothing to delete. A rewrite that could SHRINK a tab would
        need delete-then-insert, the way training_sets does.
        """
        sheets.rewrite_worksheet(self._write_target(ws), header, rows)
        self._queue_mirror_rows(ws, header, rows)

    def _append_sheet_rows(self, ws, header: list[str], values: list[list]) -> None:
        sheets.append_rows(self._write_target(ws), values)
        self._queue_mirror_rows(ws, header, values)

    def _queue_mirror_rows(self, ws, header: list[str], rows: list[list]) -> None:
        """Queue a batch of positional rows against an EXPLICIT header.

        The header is passed rather than read from _ws_headers because these
        paths deliberately use the tab's own header, which can differ from the
        current constant — that is the whole point of rebuild_tab. Every one
        of these tabs is keyed on its first column."""
        title = getattr(ws, "title", "")
        if not self._mirror_sinks_active() or not _DATASTORE_TABLE_BY_TAB.get(title):
            return
        for values in rows:
            if values:
                self._queue_mirror_row(title, values[0], values, header=header)

    def _queue_mirror_row(self, title: str, key_value, values: list,
                          header: list[str] | None = None) -> None:
        """Buffer one written row against its datastore table.

        The sheet's HEADER NAMES ARE the datastore's column names — already
        load-bearing (services/datastore.py inserts _read_records output
        straight into these tables) and pinned by
        tests/test_repository_offline_datastore.py — so the row is the header
        zipped onto the values it was just written from.
        """
        if not self._mirror_sinks_active():
            return
        table = _DATASTORE_TABLE_BY_TAB.get(title)
        header = header or self._ws_headers.get(title)
        if not table or not header:
            return
        # Filtered to the table's real columns, which is _insert_rows' own
        # behaviour rather than caution — a sheet that has gained a column the
        # datastore has not would otherwise send an unknown key, and PostgREST
        # rejects the whole batch on one.
        known = supabase_store.table_columns(table)
        row = {c: v for c, v in zip(header, values) if c in known}
        self.queue_mirror(table, key_value, row)

    def queue_mirror(self, table: str, key_value, row: dict,
                     mode: str = supabase_store.UPSERT) -> None:
        """Queue one written row for Supabase.

        `mode` is the important argument. A COMPLETE row upserts. A PARTIAL
        one — a Notion update_page that touched four columns — must PATCH,
        because upsert INSERTS when the key is absent and would create a row
        holding those four columns and NULL for everything else. That orphan
        looks like a real logged exercise to anything counting rows.
        """
        # Blank -> NULL on the way in, so a mirrored row is the row the next
        # full rebuild would write. See blank_to_null.
        if mode == supabase_store.REPLACE:
            # A child SET, and an EMPTY one is meaningful: it means this
            # exercise now has no sets, which must still delete the old ones.
            payload = [supabase_store.blank_to_null(r) for r in (row or [])]
        elif not row:
            return
        else:
            payload = supabase_store.blank_to_null(row)
        # TWO SINKS, and the split is deliberate. The local cache is written
        # SYNCHRONOUSLY because the very next read must see it — that is the
        # whole reason cache mode is safe where offline mode was not. Supabase
        # is BUFFERED because it is a network round trip (~136 ms) and being a
        # few seconds behind costs nothing: nothing reads from it.
        self._write_through(table, key_value, payload, mode)
        if self.supabase_configured():
            self._register_mirror_flush_at_exit()
            supabase_store.OUTBOX.queue(table, key_value, payload, mode=mode)

    def _write_through(self, table: str, key_value, payload, mode: str) -> None:
        """Apply one written row to the LOCAL datastore.

        Only in cache mode: offline refuses writes outright, and with no
        datastore there is nothing to keep current.

        Applies the SAME row the mirror sends, through the same three modes,
        because the two copies disagreeing is exactly the failure this whole
        arc has been chasing. SQLite's ON CONFLICT DO UPDATE has PostgREST's
        merge-duplicates semantics, verified: a partial upsert leaves the
        columns it did not name alone.

        UNLIKE the Supabase flush, a failure here RAISES. A mirror falling
        behind leaves a replica stale; a cache falling behind leaves the thing
        the app READS FROM disagreeing with the system of record, and the next
        page renders a number that is quietly wrong.
        """
        if not self.cached:
            return
        try:
            conn = self._ds
            with conn:
                if mode == supabase_store.REPLACE:
                    datastore_writer.replace_children(
                        conn, table,
                        supabase_store.REPLACE_PARENT_COLUMN[table],
                        key_value, payload)
                elif mode == supabase_store.PATCH:
                    datastore_writer.patch(
                        conn, table, supabase_store.primary_key(table),
                        key_value, payload)
                else:
                    datastore_writer.upsert(
                        conn, table, supabase_store.primary_key(table), payload)
            # Every cached read is now stale, PROCESS-WIDE. Per-instance
            # invalidation would not do: the background sync writes through
            # on its own Repository (key rule 12) while the script thread
            # holds its own read cache, and that thread is the one about to
            # render the number.
            sheets.bump_write_generation()
        except Exception as exc:
            raise datastore_writer.DatastoreWriteError(
                f"could not write {table} row {key_value!r} through to the "
                f"local datastore ({self.config.datastore_path}): {exc}. The "
                f"backend write already succeeded, so the cache is now BEHIND "
                f"— rebuild it with scripts/pull_datastore_from_supabase.py."
            ) from exc

    #: Which datastore table each Notion database writes to. Training is
    #: absent because ONE training page spans three tables — see
    #: _mirror_training_write.
    _NOTION_TABLE = {
        notion_reader.READINESS: "readiness_checkins",
        notion_reader.CONFIG: "config",
    }

    #: training_sessions' own columns, which arrive denormalised on every
    #: training page and must NOT be posted to training_exercises.
    _SESSION_COLUMNS = ("session_duration_minutes", "session_rpe", "session_au")

    def mirror_notion_write(self, kind: str, pk_value, properties: dict,
                            mode: str = supabase_store.UPSERT,
                            sets: list | None = None) -> None:
        """Queue one Notion page write for Supabase.

        CALL THIS AFTER THE NOTION CALL RETURNS, never before and never in a
        `finally`. A create_page that raised must not leave a row queued for
        Postgres that Notion does not hold — the mirror's job is to say what
        the system of record says.

        `mode` is supabase_store.PATCH for an update_page that touched only
        some properties, which is most of them: a partial UPSERT would insert
        an orphan row for a page logged before the mirror existed.
        """
        if not self._mirror_sinks_active():
            return
        row = notion_reader.row_from_properties(kind, properties)
        if kind == notion_reader.TRAINING:
            self._mirror_training_write(pk_value, row, mode=mode, sets=sets)
            return
        self.queue_mirror(self._NOTION_TABLE[kind], pk_value, row, mode=mode)

    def _mirror_training_write(self, exercise_id, row: dict,
                               mode: str = supabase_store.UPSERT,
                               sets: list | None = None) -> None:
        """One Notion training page fans out to THREE datastore tables.

        Notion stores a session flat — every exercise row carries the session's
        duration/RPE/AU — and services/datastore.py::_populate_training
        normalises that into training_sessions -> training_exercises ->
        training_sets. The mirror has to do the same split, because posting the
        decoded row whole would send session columns and a `_sets_json` key
        that is not a column at all to training_exercises, which is a 400.

        actual_sets and total_volume_kg have NO Notion property — they are
        derived on read (get_all_training_exercises_raw). They are recomputed
        here from the same sets list, using that function's own expression, or
        Postgres would hold NULL where a rebuild holds real numbers.
        """
        session_id = row.get("session_id")
        if mode == supabase_store.UPSERT and session_id:
            session_row = {"session_id": session_id,
                           "session_date": row.get("session_date")}
            session_row.update({c: row[c] for c in self._SESSION_COLUMNS if c in row})
            self.queue_mirror("training_sessions", session_id, session_row)

        exercise_row = {k: v for k, v in row.items()
                        if k not in self._SESSION_COLUMNS and k != "_sets_json"}
        if sets is None and "_sets_json" in row:
            try:
                sets = json.loads(row["_sets_json"] or "[]")
            except (ValueError, TypeError):
                sets = []
        if sets is not None:
            exercise_row["actual_sets"] = len(sets)
            exercise_row["total_volume_kg"] = _working_volume_kg(sets)
        if mode == supabase_store.UPSERT:
            exercise_row["exercise_id"] = exercise_id
        if exercise_row:
            self.queue_mirror("training_exercises", exercise_id, exercise_row,
                              mode=mode)

        if sets is not None:
            # REPLACE, not upsert: training_sets' key is a surrogate the writer
            # never supplies, so an insert-only mirror would duplicate every
            # set on every re-log. A Notion write always carries the COMPLETE
            # set list for that exercise, so replacing them is faithful.
            self.queue_mirror("training_sets", exercise_id, [
                {"exercise_id": exercise_id, "set_num": s.get("set_num"),
                 "reps": s.get("reps"), "weight": s.get("weight"),
                 "rest": s.get("rest"), "tut": s.get("tut"),
                 "velocity": s.get("velocity"), "band_tier": s.get("band_tier"),
                 "ts": s.get("ts"),
                 # A key absent from this projection is dropped without raising —
                 # so every field added to services.sessions.build_set_record has
                 # to be added here too, and to services/datastore.py's own
                 # projection, and to the two schema files.
                 "is_warmup": 1 if s.get("is_warmup") else 0,
                 "rest_taken_seconds": s.get("rest_taken_seconds"),
                 "reps_left": s.get("reps_left"),
                 "weight_left": s.get("weight_left")}
                for s in sets
            ], mode=supabase_store.REPLACE)

    def flush_supabase_mirror(self) -> dict[str, int]:
        """Send everything in the outbox. Returns {table: rows sent}.

        NEVER RAISES. The Notion or Sheets write it mirrors has already
        succeeded and is the system of record; taking a sync down because a
        replica was unreachable would trade a working app for a consistent
        copy nothing reads yet. Failures are recorded on mirror_last_error and
        the rows are DROPPED rather than retried forever — the full push is
        the repair path, and an unbounded outbox is a leak in a process that
        stays up for days.
        """
        if self._sb is None:
            return {}
        drained = supabase_store.OUTBOX.drain()
        if not drained:
            return {}
        sent: dict[str, int] = {}
        # PARENTS BEFORE CHILDREN, explicitly. The foreign keys are ENFORCED
        # in Postgres (unlike SQLite, where they are documentation), so a
        # training_sets insert before its exercise exists is a hard error.
        # Insertion order happens to be right today because the fan-out queues
        # in that order — but that is an accident of one function, and this is
        # the guarantee.
        def _rank(entry):
            table = entry[0][0]
            order = supabase_store.LOAD_ORDER
            return order.index(table) if table in order else len(order)

        for (table, mode), rows in sorted(drained.items(), key=_rank):
            try:
                numeric = supabase_store.numeric_columns(table)
                if mode == supabase_store.REPLACE:
                    parent = supabase_store.REPLACE_PARENT_COLUMN[table]
                    n = 0
                    for parent_key, children in rows.items():
                        # Delete first, ALWAYS — including when the new list
                        # is empty, which is how "this exercise now has no
                        # sets" reaches Postgres.
                        self._sb.delete_where(table, parent, parent_key)
                        payload = [supabase_store.coerce_row(c, numeric)
                                   for c in children]
                        if payload:
                            n += self._sb.insert(table, payload)
                    sent[table] = sent.get(table, 0) + n
                    continue
                if mode == supabase_store.PATCH:
                    pk = supabase_store.primary_key(table)
                    n = 0
                    for key, row in rows.items():
                        n += self._sb.patch(
                            table, pk, key,
                            supabase_store.coerce_row(row, numeric))
                    sent[table] = sent.get(table, 0) + n
                    continue
                payload = [supabase_store.coerce_row(r, numeric)
                           for r in rows.values()]
                # One request per DISTINCT COLUMN SET: PostgREST requires
                # uniform keys across a bulk body, and Notion writes to one
                # table do not all carry the same columns.
                n = 0
                for batch in supabase_store.group_by_columns(payload):
                    n += self._sb.upsert(table, batch)
                sent[table] = sent.get(table, 0) + n
            except Exception as exc:
                self.mirror_last_error = (table, str(exc)[:300])
        return sent

    def _db_kind(self, db_id: str) -> str:
        """Which of the four Notion databases an id refers to.

        Offline needs a NAME, since a Notion database id means nothing to a
        SQLite table. An unrecognised id raises rather than defaulting: a
        wrong guess here would serve one database's rows in answer to
        another's query, and every property lookup would return None — which
        renders as an empty screen, not as an error."""
        for kind, configured in (
            (notion_reader.READINESS, self.config.notion_db_readiness),
            (notion_reader.TRAINING, self.config.notion_db_training),
            (notion_reader.CONFIG, self.config.notion_db_config),
        ):
            if db_id == configured:
                return kind
        raise KeyError(
            f"Notion database id {db_id!r} is not one of the four configured "
            f"databases, so offline mode has no table for it"
        )

    def _query(self, db_id: str, filter_: dict | None = None, sorts: list | None = None) -> list[dict]:
        """Every Notion read in this class goes through here — which is what
        made offline mode for Notion one branch rather than forty rewrites,
        exactly as _ws did for the fourteen Sheets tabs.

        Either/or on config, never a fallback, for the same reason as _ws: a
        failed live read keeps failing rather than quietly serving a
        snapshot."""
        if self.local_datastore:
            return notion_reader.query(
                self._ds, self._db_kind(db_id), filter_=filter_, sorts=sorts)
        return notion.query_database(self._nc, db_id, filter_=filter_, sorts=sorts)

    # ─────────────────────────────────────────────────────────────────────
    #  Daily Readiness / Check-In
    # ─────────────────────────────────────────────────────────────────────

    def ensure_checkin_extension_columns(self) -> list[str]:
        """One-time schema migration: adds the Joint/HSD, Gut, Body,
        Hydration, and Meditation properties to the Readiness database if
        they don't already exist. Safe to call repeatedly. See
        services.clients.notion.ensure_properties. Craving Type and Sodium
        (mg) were removed from the check-in (2026-07-14) — no longer
        created here, though the columns may still exist in Notion from
        before if they were never manually deleted."""
        return notion.ensure_properties(self._nc, self.config.notion_db_readiness, {
            "Instability Events":   {"number": {}},
            "Bristol Type":         {"number": {}},
            "Unusual Stool Colour": {"checkbox": {}},
            "Hunger Deviation":     {"number": {}},
            "Thirst Intensity":     {"number": {}},
            "Electrolytes Taken":   {"checkbox": {}},
            "Meditation Done":      {"checkbox": {}},
            "Meditation Minutes":   {"number": {}},
            "Relaxation Depth":     {"number": {}},
        })

    def _check_in_properties(self, record: models.CheckInRecord) -> dict:
        return {
            "Entry":         notion.title(f"{record.date} Morning Check-In"),
            "Date":          notion.date_prop(record.date),
            "Condition":     notion.select(record.current_condition),
            "Tightness":     notion.number(record.tightness_score),
            "Pain":          notion.number(record.pain_score),
            "Body Areas":    notion.multi_select(record.anatomical_locations),
            "Sensations":    notion.multi_select(record.sensation_tags),
            "Note":          notion.rich_text(record.subjective_tightness or ""),
            "Alcohol Units": notion.number(record.alcohol_units or 0),
            "Travel":        notion.checkbox(record.travel_flag),
            "Stress Level":  notion.number(record.psych_stress_score),
            "Instability Events":   notion.number(record.instability_events),
            "Bristol Type":         notion.number(record.bristol_type),
            "Unusual Stool Colour": notion.checkbox(record.unusual_stool_colour),
            "Hunger Deviation":     notion.number(record.hunger_deviation),
            "Thirst Intensity":     notion.number(record.thirst_intensity),
            "Electrolytes Taken":   notion.checkbox(record.electrolytes_taken),
            "Meditation Done":      notion.checkbox(record.meditation_done),
            "Meditation Minutes":   notion.number(record.meditation_minutes),
            "Relaxation Depth":     notion.number(record.relaxation_depth),
        }

    def _find_check_in_page(self, iso_date: str) -> dict | None:
        """The existing Readiness-DB page for this date, if any. Notion's
        "equals" date filter matches on the day only, so this is exact —
        not a range. Assumes at most one page per date; if duplicates exist
        from before this upsert behavior existed, returns whichever one
        Notion's default (unsorted) query order returns first, and leaves
        the other(s) alone."""
        pages = self._query(
            self.config.notion_db_readiness,
            filter_={"property": "Date", "date": {"equals": iso_date}},
        )
        return pages[0] if pages else None

    def _merge_check_in(self, new: models.CheckInRecord, existing_page: dict) -> tuple[models.CheckInRecord, bool]:
        """Field-by-field upsert: a field on `new` only overwrites the
        existing page's value if it was actually filled in (i.e. it's not
        still sitting at that field's untouched-widget default). A
        follow-up check-in that only sets, say, meditation minutes leaves
        every other already-recorded field on that day's entry untouched
        rather than blanking it back to defaults. Returns (merged record,
        whether the note text changed — a previously-parsed note that just
        changed needs the AI parser to see it again, see
        get_unparsed_readiness's Parsed filter)."""
        changes: dict[str, object] = {}
        note_changed = False
        for field, (prop_name, kind, default) in _CHECKIN_FIELD_MAP.items():
            new_val = getattr(new, field)
            if new_val != default:
                changes[field] = new_val
                if field == "subjective_tightness":
                    old_val = notion.get_property(existing_page, prop_name, kind)
                    note_changed = new_val != (old_val or "")
            else:
                old_val = notion.get_property(existing_page, prop_name, kind)
                changes[field] = old_val if old_val is not None else default
        changes["meditation_done"] = bool(changes["meditation_minutes"])
        return dataclasses.replace(new, **changes), note_changed

    def save_check_in(self, record: models.CheckInRecord) -> None:
        existing_page = self._find_check_in_page(record.date)
        if existing_page is None:
            properties = self._check_in_properties(record)
            notion.create_page(
                self._nc, self.config.notion_db_readiness, properties=properties,
            )
            # A brand-new page carries no "Parsed" property at all, and
            # get_property reads an absent checkbox as None, which the
            # datastore stores as 0 (`1 if g("Parsed","checkbox") else 0`).
            # Without this the INSERT would leave NULL where a rebuild holds
            # 0. The other four AI columns are genuinely absent-not-zero, so
            # they stay NULL, which is what a rebuild writes for them too.
            self.mirror_notion_write(
                notion_reader.READINESS, record.date,
                {**properties, "Parsed": notion.checkbox(False)})
            return

        merged, note_changed = self._merge_check_in(record, existing_page)
        properties = self._check_in_properties(merged)
        if note_changed:
            properties["Parsed"] = notion.checkbox(False)
        notion.update_page(self._nc, existing_page["id"], properties=properties)
        # PATCH, not upsert: this writes 19 of 24 columns and must not touch
        # the AI-parser ones (update_readiness_ai owns those), nor reset
        # `parsed` on an update that did not change the note.
        self.mirror_notion_write(notion_reader.READINESS, record.date,
                                 properties, mode=supabase_store.PATCH)

    # ─── One-off cleanup: pre-upsert same-day duplicate check-ins ─────────
    # (scripts/merge_duplicate_checkins.py) — save_check_in() above is now
    # an upsert going forward, but it can't retroactively fix duplicate
    # pages created before that behavior existed. These three methods fold
    # a date's duplicate pages into one, generalizing _merge_check_in's
    # "an untouched widget default loses to a real value" rule to N pages,
    # plus: list fields and the Note are combined across all of that date's
    # pages rather than one replacing another, since two separate check-ins
    # can each carry real, non-overlapping information there.

    def find_duplicate_check_in_dates(self) -> dict[str, list[dict]]:
        """Every date in the Readiness DB with more than one page, raw
        pages keyed by ISO date — input for merge_check_in_group()."""
        pages = self._query(self.config.notion_db_readiness)
        by_date: dict[str, list[dict]] = {}
        for p in pages:
            d = notion.get_property(p, "Date", "date")
            if d:
                by_date.setdefault(d, []).append(p)
        return {d: ps for d, ps in by_date.items() if len(ps) > 1}

    def merge_check_in_group(self, pages: list[dict]) -> tuple[str, dict, list[str]] | None:
        """Folds >= 2 same-day check-in pages into one.

        Scalar fields (Tightness, Pain, Condition, ...): if only one page
        has a value that differs from that field's untouched-widget
        default, it wins; if every page is still at the default, the
        default is kept; if two pages disagree with two DIFFERENT real
        values, this is a genuine conflict that can't be resolved by a
        rule — returns None so the caller can flag that date for manual
        cleanup in Notion instead of silently guessing.

        List fields (Body Areas, Sensations) are unioned rather than one
        page's selection replacing another's, and the Note field is
        concatenated across every page that has one — both cover the case
        where two check-ins each recorded real, distinct information
        rather than one being a strict superset of the other.

        Returns (primary_page_id, merged_properties, [page ids to
        archive]) — the oldest page (by created_time) is kept as the
        surviving primary; apply_check_in_merge() writes this out."""
        pages_sorted = sorted(pages, key=lambda p: p.get("created_time", ""))
        primary = pages_sorted[0]
        properties: dict = {}

        # The Date, written back unchanged. _CHECKIN_FIELD_MAP has no entry
        # for it, so without this the merged properties carry no date at all —
        # and readiness_checkins is keyed BY date, so the Supabase mirror
        # could not name the row it had just rewritten. A no-op in Notion
        # (find_duplicate_check_in_dates groups on this exact value, so every
        # page in the group already holds it), and it makes the merged
        # property set self-identifying the same way save_check_in's is.
        merged_date = notion.get_property(primary, "Date", "date")
        if merged_date:
            properties["Date"] = notion.date_prop(merged_date)

        for field, (prop_name, kind, default) in _CHECKIN_FIELD_MAP.items():
            values = [notion.get_property(p, prop_name, kind) for p in pages_sorted]

            if kind == "multi_select":
                union: list[str] = []
                for v in values:
                    for name in (v or []):
                        if name not in union:
                            union.append(name)
                properties[prop_name] = notion.multi_select(union)
                continue

            if prop_name == "Note":
                parts = [v for v in values if v]
                properties[prop_name] = notion.rich_text(" / ".join(dict.fromkeys(parts)))
                continue

            non_default = {v for v in values if v is not None and v != default}
            if not non_default:
                merged_val = default
            elif len(non_default) == 1:
                merged_val = next(iter(non_default))
            else:
                return None  # two different real values — needs a human
            if kind == "number":
                properties[prop_name] = notion.number(merged_val)
            elif kind == "select":
                properties[prop_name] = notion.select(merged_val)
            else:
                properties[prop_name] = notion.checkbox(merged_val)

        properties["Meditation Done"] = notion.checkbox(bool(properties["Meditation Minutes"]["number"]))
        old_note = notion.get_property(primary, "Note", "rich_text") or ""
        # Join ALL blocks: notion.rich_text chunks values over 2000 chars, so
        # comparing block 0 alone against the joined read-back would flag a
        # long unchanged note as changed on every merge.
        new_note = "".join(b["text"]["content"] for b in properties["Note"]["rich_text"])
        if new_note != old_note:
            properties["Parsed"] = notion.checkbox(False)

        return primary["id"], properties, [p["id"] for p in pages_sorted[1:]]

    def apply_check_in_merge(self, primary_page_id: str, properties: dict, archive_ids: list[str]) -> None:
        """Writes merge_check_in_group()'s result: updates the surviving
        page with the merged fields, then archives the now-redundant
        duplicate(s). Notion's archive is a soft-delete (restorable from
        its own trash), never a hard delete."""
        notion.update_page(self._nc, primary_page_id, properties=properties)
        for page_id in archive_ids:
            notion.archive_page(self._nc, page_id)

        # The archived duplicates need NO delete. readiness_checkins is keyed
        # by date and every page in the group carries the SAME date
        # (find_duplicate_check_in_dates groups on it), so the duplicates
        # never had rows of their own — datastore.py already collapses them
        # last-one-wins. Only the surviving merged row has to be mirrored, or
        # Postgres keeps whichever duplicate the last rebuild happened to pick.
        merged_date = notion_reader.row_from_properties(
            notion_reader.READINESS, properties).get("date")
        if merged_date:
            self.mirror_notion_write(notion_reader.READINESS, merged_date,
                                     properties, mode=supabase_store.PATCH)

    def get_recent_readiness(self, days: int = 60, today: date | None = None) -> list[dict]:
        today = today or date.today()
        cutoff = (today - timedelta(days=days)).isoformat()
        pages = self._query(
            self.config.notion_db_readiness,
            filter_={"property": "Date", "date": {"on_or_after": cutoff}},
            sorts=[{"property": "Date", "direction": "descending"}],
        )
        out = []
        for p in pages:
            g = lambda name, kind: notion.get_property(p, name, kind)
            out.append({
                "date":                  g("Date", "date"),
                "current_condition":     g("Condition", "select"),
                "tightness_score":       g("Tightness", "number"),
                "pain_score":            g("Pain", "number"),
                "anatomical_locations":  json.dumps(g("Body Areas", "multi_select") or []),
                "sensation_tags":        json.dumps(g("Sensations", "multi_select") or []),
                "subjective_tightness":  g("Note", "rich_text"),
                "alcohol_units":         g("Alcohol Units", "number"),
                "travel_flag":           1 if g("Travel", "checkbox") else 0,
                "psych_stress_score":    g("Stress Level", "number"),
                "instability_events":    g("Instability Events", "number"),
                "bristol_type":          g("Bristol Type", "number"),
                "unusual_stool_colour":  1 if g("Unusual Stool Colour", "checkbox") else 0,
                "hunger_deviation":      g("Hunger Deviation", "number"),
                "thirst_intensity":      g("Thirst Intensity", "number"),
                "electrolytes_taken":    1 if g("Electrolytes Taken", "checkbox") else 0,
                "meditation_done":       1 if g("Meditation Done", "checkbox") else 0,
                "meditation_minutes":    g("Meditation Minutes", "number"),
                "relaxation_depth":      g("Relaxation Depth", "number"),
            })
        return out

    def get_all_readiness_checkins_raw(self) -> list[dict]:
        """Every check-in page ever logged, unwindowed (no Date filter) —
        get_recent_readiness's fields PLUS the AI note-parsing pipeline's
        output (parsed/parsed_severity/parsed_areas/parsed_sensations/
        warning_level — see update_readiness_ai), which get_recent_readiness
        doesn't expose. For services.datastore's readiness_checkins table."""
        pages = self._query(self.config.notion_db_readiness)
        out = []
        for p in pages:
            g = lambda name, kind: notion.get_property(p, name, kind)
            out.append({
                "date":                  g("Date", "date"),
                "current_condition":     g("Condition", "select"),
                "tightness_score":       g("Tightness", "number"),
                "pain_score":            g("Pain", "number"),
                "anatomical_locations":  json.dumps(g("Body Areas", "multi_select") or []),
                "sensation_tags":        json.dumps(g("Sensations", "multi_select") or []),
                "subjective_tightness":  g("Note", "rich_text"),
                "alcohol_units":         g("Alcohol Units", "number"),
                "travel_flag":           1 if g("Travel", "checkbox") else 0,
                "psych_stress_score":    g("Stress Level", "number"),
                "instability_events":    g("Instability Events", "number"),
                "bristol_type":          g("Bristol Type", "number"),
                "unusual_stool_colour":  1 if g("Unusual Stool Colour", "checkbox") else 0,
                "hunger_deviation":      g("Hunger Deviation", "number"),
                "thirst_intensity":      g("Thirst Intensity", "number"),
                "electrolytes_taken":    1 if g("Electrolytes Taken", "checkbox") else 0,
                "meditation_done":       1 if g("Meditation Done", "checkbox") else 0,
                "meditation_minutes":    g("Meditation Minutes", "number"),
                "relaxation_depth":      g("Relaxation Depth", "number"),
                "parsed":                1 if g("Parsed", "checkbox") else 0,
                "parsed_severity":       g("Parsed Severity", "number"),
                "parsed_areas":          g("Parsed Areas", "rich_text"),
                "parsed_sensations":     g("Parsed Sensations", "rich_text"),
                "warning_level":         g("Warning", "select"),
            })
        return out

    def get_unparsed_readiness(self) -> list[dict]:
        pages = self._query(
            self.config.notion_db_readiness,
            filter_={"and": [
                {"property": "Parsed", "checkbox": {"equals": False}},
                {"property": "Note", "rich_text": {"is_not_empty": True}},
            ]},
            sorts=[{"property": "Date", "direction": "ascending"}],
        )
        out = []
        for p in pages:
            note = notion.get_property(p, "Note", "rich_text") or ""
            if note.strip():
                out.append({
                    "id":                   p["id"],
                    "timestamp":            notion.get_property(p, "Date", "date"),
                    "subjective_tightness": note,
                    "tightness_score":      notion.get_property(p, "Tightness", "number"),
                    "pain_score":           notion.get_property(p, "Pain", "number"),
                })
        return out

    def update_readiness_ai(self, row_id: str, severity: float, body_parts: list,
                             sensation_type: list, warning_level: str,
                             entry_date: str | None = None) -> None:
        """`entry_date` exists ONLY for the Supabase mirror, and is optional so
        no existing caller breaks.

        readiness_checkins is keyed by DATE while this method is handed a
        Notion PAGE ID, and there is no page-id-to-date index anywhere — so
        without it the mirror cannot name the row it just changed. The caller
        has the date for free: get_unparsed_readiness returns it as
        `timestamp`, read with the same get_property call that populates the
        `date` column, so the keys match by construction. Omit it and the
        Notion write still happens; only the mirror is skipped."""
        properties = {
            "Parsed Severity":   notion.number(severity),
            "Parsed Areas":      notion.rich_text(json.dumps(body_parts or [])),
            "Parsed Sensations": notion.rich_text(json.dumps(sensation_type or [])),
            "Warning":           notion.select(warning_level),
            "Parsed":            notion.checkbox(True),
        }
        notion.update_page(self._nc, row_id, properties=properties)
        if entry_date:
            self.mirror_notion_write(notion_reader.READINESS, entry_date,
                                     properties, mode=supabase_store.PATCH)

    def get_parsed_readiness(self, limit: int = 90) -> list[dict]:
        pages = self._query(
            self.config.notion_db_readiness,
            filter_={"property": "Parsed", "checkbox": {"equals": True}},
            sorts=[{"property": "Date", "direction": "descending"}],
        )
        out = []
        for p in pages[:limit]:
            g = lambda name, kind: notion.get_property(p, name, kind)
            out.append({
                "date":                  g("Date", "date"),
                "tightness_score":       g("Tightness", "number"),
                "pain_score":            g("Pain", "number"),
                "ai_body_parts":         g("Parsed Areas", "rich_text"),
                "ai_sensation_type":     g("Parsed Sensations", "rich_text"),
                "ai_tightness_severity": g("Parsed Severity", "number"),
                "ai_warning_level":      g("Warning", "select"),
            })
        return out

    def get_pain_free_streak(self) -> int:
        pages = self._query(
            self.config.notion_db_readiness,
            sorts=[{"property": "Date", "direction": "descending"}],
        )
        streak = 0
        for p in pages:
            pain = notion.get_property(p, "Pain", "number") or 0
            if pain == 0:
                streak += 1
            else:
                break
        return streak

    def get_avg_tightness(self, days: int = 14, today: date | None = None) -> float:
        today = today or date.today()
        cutoff = (today - timedelta(days=days)).isoformat()
        pages = self._query(
            self.config.notion_db_readiness,
            filter_={"property": "Date", "date": {"on_or_after": cutoff}},
        )
        vals = [
            v for p in pages
            if (v := notion.get_property(p, "Tightness", "number")) is not None
        ]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    # ─────────────────────────────────────────────────────────────────────
    #  Training Log / Sessions
    # ─────────────────────────────────────────────────────────────────────

    def create_training_session(self, session_date, duration_minutes: int, session_rpe: int) -> dict:
        """No API call: sessions are denormalised into each training log entry."""
        return {
            "session_id":       f"{session_date}-{uuid.uuid4().hex[:8]}",
            "session_date":     str(session_date),
            "duration_minutes": int(duration_minutes),
            "session_rpe":      int(session_rpe),
            "session_au":       float(session_rpe * duration_minutes),
        }

    def save_training_exercise(self, session_id, movement_name: str, movement_type: str,
                                planned_sets: int, planned_reps: int, rpe: int,
                                sets: list | None = None, note: str = "", session_date=None,
                                session_duration_minutes: int = 0, session_rpe: int = 0,
                                session_au: float = 0.0, today: date | None = None,
                                garmin_avg_hr: float | None = None, garmin_max_hr: float | None = None,
                                garmin_distance_km: float | None = None, garmin_calories: float | None = None) -> str:
        today = today or date.today()
        sid = str(session_id) if not isinstance(session_id, dict) else session_id.get("session_id", "")

        if session_date is None and sid and "-" in sid:
            parts = sid.split("-")
            if len(parts) >= 3:
                try:
                    session_date = "-".join(parts[:3])
                except Exception:
                    session_date = str(today)

        sets_json = json.dumps(sets or [])
        properties = {
            "Movement":          notion.title(movement_name),
            "Session Date":      notion.date_prop(session_date or str(today)),
            "Session ID":        notion.rich_text(sid),
            "Type":              notion.select(movement_type),
            "Planned Sets":      notion.number(planned_sets),
            "Planned Reps":      notion.number(planned_reps),
            "Exercise RPE":      notion.number(rpe),
            "Sets":              notion.rich_text(sets_json),
            "Notes":             notion.rich_text(note or ""),
            "Session Duration":  notion.number(session_duration_minutes),
            "Session RPE":       notion.number(session_rpe),
            "Session AU":        notion.number(session_au),
        }
        # Only set on the one exercise row a Garmin activity was actually
        # matched to — every other row (and every non-Garmin session) simply
        # omits these properties, leaving that Notion cell blank.
        if garmin_avg_hr is not None:
            properties["Activity Avg HR"] = notion.number(garmin_avg_hr)
        if garmin_max_hr is not None:
            properties["Activity Max HR"] = notion.number(garmin_max_hr)
        if garmin_distance_km is not None:
            properties["Activity Distance (km)"] = notion.number(garmin_distance_km)
        if garmin_calories is not None:
            properties["Activity Calories"] = notion.number(garmin_calories)

        page = notion.create_page(self._nc, self.config.notion_db_training, properties=properties)
        # AFTER the create, because the page id IS training_exercises' primary
        # key and because a create that raised must not leave a row queued for
        # Postgres that Notion does not hold. `sets` is passed explicitly so
        # the fan-out does not have to re-parse the JSON it was just given.
        self.mirror_notion_write(notion_reader.TRAINING, page["id"], properties,
                                 sets=sets or [])
        return page["id"]

    def ensure_garmin_activity_columns(self) -> list[str]:
        """One-time schema migration: adds the 4 Garmin-activity Number
        properties to the Training Log database if they don't already exist.
        Safe to call repeatedly (a no-op once they're present). Returns the
        property names actually created."""
        return notion.ensure_number_properties(
            self._nc, self.config.notion_db_training,
            ["Activity Avg HR", "Activity Max HR", "Activity Distance (km)", "Activity Calories"],
        )

    # save_training_set() lived here: an incremental "append one set to an
    # existing page's Sets JSON" writer that was never called from anywhere.
    # Per-set records are now captured in-session (services.sessions.
    # build_set_record) and written in one shot by save_training_exercise
    # above, so a per-set round-trip to Notion mid-session is redundant.

    def save_session_notes(self, training_log_id: str, raw_text: str) -> None:
        if not training_log_id or not (raw_text or "").strip():
            return
        page = self._nc.pages.retrieve(training_log_id)
        existing = notion.get_property(page, "Notes", "rich_text") or ""
        combined = (
            (existing.strip() + "\n\n" + raw_text.strip()).strip()
            if existing.strip() else raw_text.strip()
        )
        properties = {"Notes": notion.rich_text(combined[:2000])}
        notion.update_page(self._nc, training_log_id, properties=properties)
        # ONE property, so PATCH — an upsert would insert a training_exercises
        # row holding nothing but a note for any page logged before the mirror
        # existed. training_log_id IS exercise_id (the Notion page id).
        self.mirror_notion_write(notion_reader.TRAINING, training_log_id,
                                 properties, mode=supabase_store.PATCH)

    def get_recent_sessions(self, days: int = 60, today: date | None = None) -> list[models.SessionRecord]:
        """One SessionRecord per calendar date, exercises grouped under it —
        the underlying Notion rows are flat (one row per exercise, session
        fields denormalised onto every row); this groups them at the boundary."""
        today = today or date.today()
        cutoff = (today - timedelta(days=days)).isoformat()
        pages = self._query(
            self.config.notion_db_training,
            filter_={"property": "Session Date", "date": {"on_or_after": cutoff}},
            sorts=[{"property": "Session Date", "direction": "descending"}],
        )
        by_date: dict[str, dict] = {}
        for p in pages:
            g = lambda name, kind: notion.get_property(p, name, kind)
            sets_raw = g("Sets", "rich_text") or "[]"
            try:
                sets = json.loads(sets_raw)
            except Exception:
                sets = []
            actual_sets = len(sets)
            total_volume = _working_volume_kg(sets)

            d = g("Session Date", "date") or ""
            bucket = by_date.setdefault(d, {
                "session_duration_minutes": g("Session Duration", "number"),
                "session_rpe": g("Session RPE", "number"),
                "session_au": g("Session AU", "number"),
                "exercises": [],
            })
            bucket["exercises"].append(models.ExerciseEntry(
                name=g("Movement", "title"),
                movement_type=g("Type", "select"),
                planned_sets=g("Planned Sets", "number"),
                planned_reps=g("Planned Reps", "number"),
                exercise_rpe=g("Exercise RPE", "number"),
                actual_sets=actual_sets,
                total_volume_kg=total_volume,
            ))

        return [
            models.SessionRecord(
                session_date=d,
                session_duration_minutes=v["session_duration_minutes"],
                session_rpe=v["session_rpe"],
                session_au=v["session_au"],
                exercises=v["exercises"],
            )
            for d, v in sorted(by_date.items(), reverse=True)
        ]

    def get_last_performance(self, movement_name: str) -> dict | None:
        """Most recent logged performance of this exact movement name, read
        back from the same per-set `Sets` JSON every training exercise
        already stores (services.sessions.make_sets_data's output) — the
        durable "last time" source for stepper seeding in the live guided
        flow. Deliberately does NOT touch the Notes field (that feeds the
        unrelated AI sentiment pipeline — see get_unparsed_session_notes).

        Returns None if the movement has never been logged, or its most
        recent logged page has an empty/unparseable Sets JSON."""
        pages = self._query(
            self.config.notion_db_training,
            filter_={"property": "Movement", "title": {"equals": movement_name}},
            sorts=[{"property": "Session Date", "direction": "descending"}],
        )
        if not pages:
            return None
        latest = max(pages, key=lambda p: notion.get_property(p, "Session Date", "date") or "")
        sets_raw = notion.get_property(latest, "Sets", "rich_text") or "[]"
        try:
            sets = json.loads(sets_raw)
        except Exception:
            sets = []
        if not sets:
            return None
        last_set = sets[-1]
        return {
            "session_date": notion.get_property(latest, "Session Date", "date"),
            "reps":         last_set.get("reps"),
            "weight_kg":    last_set.get("weight"),
            "band_tier":    last_set.get("band_tier"),
            "sets_count":   len(sets),
        }

    def get_last_session_all_sets(self, movement_name: str) -> list[dict] | None:
        """Most recent logged session's FULL per-set array for this exact
        movement name — same Notion query as get_last_performance (filter
        Movement==movement_name, most recent by Session Date), but returns
        every set instead of just the last one. Needed by double progression
        (services.engine.double_progression), which requires checking that
        ALL prescribed sets hit the top of the rep range, not just the last
        set logged.

        Warm-up sets are deliberately NOT filtered here. A ramp is authored as
        its own exercise (training_plan._ex(warmup=True)) sitting beside the lift
        it prepares, so a movement's sets are either all ramp or none — and
        filtering would empty the ramp's own history, losing the last weight its
        stepper should seed from. Double progression is unaffected either way:
        ramp exercises carry no rep_min/rep_max, so it never runs on them.

        Returns None if the movement has never been logged, or its most
        recent logged page has an empty/unparseable Sets JSON."""
        pages = self._query(
            self.config.notion_db_training,
            filter_={"property": "Movement", "title": {"equals": movement_name}},
            sorts=[{"property": "Session Date", "direction": "descending"}],
        )
        if not pages:
            return None
        latest = max(pages, key=lambda p: notion.get_property(p, "Session Date", "date") or "")
        sets_raw = notion.get_property(latest, "Sets", "rich_text") or "[]"
        try:
            sets = json.loads(sets_raw)
        except Exception:
            sets = []
        if not sets:
            return None
        return sets

    def get_all_training_exercises_raw(self) -> list[dict]:
        """Every exercise row ever logged in the Training DB, unwindowed (no
        Session Date filter) — the full historical per-set detail that
        get_recent_sessions/get_last_session_all_sets deliberately don't
        expose (windowed by days, and/or collapsed to session-date-keyed
        aggregates). Built for services.datastore's normalized
        training_sessions/training_exercises/training_sets tables.

        One dict per Notion page (= one logged exercise):
          exercise_id, session_id, session_date, movement_name,
          movement_type, planned_sets, planned_reps, exercise_rpe,
          actual_sets, total_volume_kg (same len(sets)/sum(reps*weight)
          math get_recent_sessions already uses), session_duration_minutes,
          session_rpe, session_au, notes, note_summary, sentiment_score,
          flagged_body_parts (raw JSON string, as stored), warning_level,
          garmin_avg_hr, garmin_max_hr, garmin_distance_km, garmin_calories,
          and sets — json.loads("Sets" rich_text), a list of
          {set_num, reps, weight, rest, tut, velocity, band_tier?, ts?} dicts
          (band_tier/ts are only present on rows that have them — optional
          per services.sessions.build_set_record/make_sets_data).

        A page whose Sets JSON fails to parse gets sets=[] (and therefore
        actual_sets=0, total_volume_kg=0.0) rather than raising — the same
        defensive fallback get_recent_sessions/get_last_session_all_sets
        already use."""
        pages = self._query(self.config.notion_db_training)
        out = []
        for p in pages:
            g = lambda name, kind: notion.get_property(p, name, kind)
            sets_raw = g("Sets", "rich_text") or "[]"
            try:
                sets = json.loads(sets_raw)
            except Exception:
                sets = []
            out.append({
                "exercise_id": p["id"],
                "session_id": g("Session ID", "rich_text") or "",
                "session_date": g("Session Date", "date"),
                "movement_name": g("Movement", "title"),
                "movement_type": g("Type", "select"),
                "planned_sets": g("Planned Sets", "number"),
                "planned_reps": g("Planned Reps", "number"),
                "exercise_rpe": g("Exercise RPE", "number"),
                "actual_sets": len(sets),
                "total_volume_kg": _working_volume_kg(sets),
                "session_duration_minutes": g("Session Duration", "number"),
                "session_rpe": g("Session RPE", "number"),
                "session_au": g("Session AU", "number"),
                "notes": g("Notes", "rich_text"),
                "note_summary": g("Note Summary", "rich_text"),
                "sentiment_score": g("Sentiment", "number"),
                "flagged_body_parts": g("Flagged Areas", "rich_text"),
                "warning_level": g("Warning", "select"),
                "garmin_avg_hr": g("Activity Avg HR", "number"),
                "garmin_max_hr": g("Activity Max HR", "number"),
                "garmin_distance_km": g("Activity Distance (km)", "number"),
                "garmin_calories": g("Activity Calories", "number"),
                "sets": sets,
            })
        return out

    def has_checked_in(self, d: date) -> bool:
        """True if a Morning Check-In has already been submitted for this
        date — used to gate the Garmin sync cadence (see
        sync_garmin_daily_if_due): once today's check-in is in, that day's
        readiness is already anchored, so further 2-hourly polling is
        unnecessary until tomorrow."""
        pages = self._query(
            self.config.notion_db_readiness,
            filter_={"property": "Date", "date": {"equals": str(d)}},
        )
        return len(pages) > 0

    #: Session Type values that are SUPPLEMENTARY training: real load, real
    #: strain, but never a substitute for the plan day — a logged Yoga flow,
    #: an imported outdoor activity (hike/walk/trail run from Garmin), or an
    #: accessory session (services/accessory.py) must not mark the rehab plan
    #: day as done, must not block the manual day swap, and must not close the
    #: missed-session carry.
    #:
    #: This frozenset IS the mechanism, for all three. Everything else follows
    #: from membership here, which is why the accessory session needs no
    #: special case anywhere in `has_logged_session`, the swap gates or the
    #: reschedule logic — only its own literal on the write.
    SUPPLEMENTARY_SESSION_TYPES: frozenset[str] = frozenset({"Yoga", "Outdoor", "Accessory"})

    def has_logged_session(self, d: date) -> bool:
        """True only for a logged rehab-plan session — a logged Yoga,
        imported outdoor activity, or other supplementary session must never
        mark the plan day itself as done.

        Filters the Type client-side in Python rather than in the Notion
        query: a `select.does_not_equal` filter is validated against the
        property's currently-configured options at query time, and 400s
        outright if the option doesn't exist yet — which is exactly the
        state before the very first session of that type is ever logged
        (save_training_exercise's Type write is what lazily creates the
        option in the first place). Querying by date alone and excluding
        client-side works regardless of whether the option exists yet."""
        pages = self._query(
            self.config.notion_db_training,
            filter_={"property": "Session Date", "date": {"equals": str(d)}},
        )
        return any(
            notion.get_property(p, "Type", "select") not in self.SUPPLEMENTARY_SESSION_TYPES
            for p in pages
        )

    def get_logged_session_dates(self, start: date, end: date,
                                 include_supplementary: bool = True) -> set[str]:
        """Dates with any logged session in [start, end]. The default includes
        Yoga/supplementary rows (the day strip's and Weekly Rollup's historic
        definition of a trained day). Pass include_supplementary=False for
        has_logged_session's stricter PLAN-day meaning — the manual swap uses
        it so a yoga session (including the rest-day screen's own suggestion)
        never reads as "today already trained" and blocks the athlete's swap,
        and a yoga'd past day still counts as missed, matching the day-detail
        router that offers the swap in the first place. Same client-side Type
        filter as has_logged_session, for the same lazily-created-option
        reason documented there."""
        pages = self._query(
            self.config.notion_db_training,
            filter_={"and": [
                {"property": "Session Date", "date": {"on_or_after": str(start)}},
                {"property": "Session Date", "date": {"on_or_before": str(end)}},
            ]},
        )
        if not include_supplementary:
            pages = [p for p in pages
                     if notion.get_property(p, "Type", "select")
                     not in self.SUPPLEMENTARY_SESSION_TYPES]
        return {d for p in pages if (d := notion.get_property(p, "Session Date", "date"))}

    def get_daily_session_au(self, days: int = 28, today: date | None = None) -> list[dict]:
        today = today or date.today()
        cutoff = (today - timedelta(days=days)).isoformat()
        pages = self._query(
            self.config.notion_db_training,
            filter_={"property": "Session Date", "date": {"on_or_after": cutoff}},
        )
        seen: set[str] = set()
        au_by_date: dict[str, float] = {}
        for p in pages:
            sid = notion.get_property(p, "Session ID", "rich_text") or ""
            d   = notion.get_property(p, "Session Date", "date") or ""
            au  = notion.get_property(p, "Session AU", "number") or 0.0
            if sid and sid not in seen:
                seen.add(sid)
                au_by_date[d] = au_by_date.get(d, 0.0) + au
        return [{"date": d, "total_au": round(v, 1)} for d, v in sorted(au_by_date.items())]

    def get_daily_session_au_weighted(self, days: int = 28, today: date | None = None) -> list[dict]:
        """
        Content-aware counterpart to get_daily_session_au — same
        {"date", "total_au"} shape (a drop-in replacement for every existing
        consumer: engine.acwr(), dashboard.rolling_prior_strain(),
        dashboard.au_to_strain_or_none() via compute_daily_metrics_snapshot —
        none of those need any signature change), but "total_au" here is the
        raw Foster Session AU already scaled by that day's own content
        multiplier (services.content_weighting.day_content_multiplier),
        computed live from each day's actually-logged exercises' Sets JSON —
        never from a static per-session-type lookup.

        The raw "Session AU" Notion property itself is untouched by this
        (create_training_session/save_training_exercise still write raw
        Foster AU) — this re-derives the weighted figure at read time only,
        mirroring how au_to_strain's CLF scaling is already applied at
        read/display time, never at write time (see engine.au_to_strain's
        own docstring: "The database always stores raw Foster AU ... CLF is
        applied at display/computation time only").

        Self-healing over historical data: recomputes every day's multiplier
        fresh from that day's own persisted Sets JSON on every call, so a
        day logged before this feature existed is weighted correctly the
        very next time this is called — no backfill needed for this or any
        other live read path. (The one exception is the already-persisted
        Metrics History sheet snapshot — see sync_metrics_history's
        docstring.)

        Multiple sessions on the same date (e.g. a rehab session + a
        same-day Yoga session) are content-weighted independently per
        Session ID (mirroring get_daily_session_au's own dedup-by-Session-ID
        loop) and then summed — so one session's exercise mix never dilutes
        another's. An exercise name with no services.content_weighting entry
        (e.g. any Yoga pose — this feature currently only has weight-table
        coverage for training_plan.PLAN_STAGE2's exercise universe)
        contributes at UNMAPPED_EXERCISE_WEIGHT (1.0, i.e. unchanged from
        raw AU) — a known, visible scope boundary, not a silent bug; see
        content_weighting.day_content_multiplier's own docstring.
        """
        return [
            {"date": d, "total_au": round(v, 1)}
            for d, v in sorted(self._weighted_au_by_date(days=days, today=today).items())
        ]

    def _weighted_sessions(self, days: int = 28, today: date | None = None) -> list[dict]:
        """One entry per Session ID over the window — the ONE bucketing loop.

        [{"session_id", "date", "au" (raw Foster), "multiplier",
          "weighted_au", "elapsed_seconds", "exercise_seconds"}]
        where exercise_seconds is content_weighting.day_content_multiplier's
        own input shape, [{"name", "seconds"}, ...].

        Extracted so get_daily_session_au_weighted and get_daily_region_au are
        both consumers of it: the day's AU and the day's regional split can
        then never be computed from two different readings of the same Notion
        pages, and the regional split costs no extra API call.
        """
        today = today or date.today()
        cutoff = (today - timedelta(days=days)).isoformat()
        pages = self._query(
            self.config.notion_db_training,
            filter_={"property": "Session Date", "date": {"on_or_after": cutoff}},
        )
        sessions_by_id: dict[str, dict] = {}
        for p in pages:
            sid = notion.get_property(p, "Session ID", "rich_text") or ""
            if not sid:
                continue
            bucket = sessions_by_id.setdefault(sid, {
                "session_id": sid,
                "date": notion.get_property(p, "Session Date", "date") or "",
                "au": notion.get_property(p, "Session AU", "number") or 0.0,
                # Wall-clock length of the session, for the attributed-fraction
                # figure services.strain_regions reports. Reconstructed
                # exercise time covers only about half of it (measured: 50%
                # over 23 sessions, ranging 6%-565%), and a split computed off
                # a 6% sample should say so.
                "elapsed_seconds": float(
                    notion.get_property(p, "Session Duration", "number") or 0.0
                ) * 60.0,
                "exercise_seconds": [],
            })
            name = notion.get_property(p, "Movement", "title") or ""
            sets_raw = notion.get_property(p, "Sets", "rich_text") or "[]"
            try:
                sets = json.loads(sets_raw)
            except Exception:
                sets = []
            seconds = training_sessions.exercise_seconds_from_sets(sets)
            bucket["exercise_seconds"].append({"name": name, "seconds": seconds})

        out = []
        for bucket in sessions_by_id.values():
            mult = content_weighting.day_content_multiplier(
                bucket["exercise_seconds"],
            )["multiplier"]
            out.append({**bucket, "multiplier": mult,
                        "weighted_au": bucket["au"] * mult})
        return out

    def _weighted_au_by_date(self, days: int = 28,
                             today: date | None = None) -> dict[str, float]:
        au_by_date: dict[str, float] = {}
        for s in self._weighted_sessions(days=days, today=today):
            au_by_date[s["date"]] = au_by_date.get(s["date"], 0.0) + s["weighted_au"]
        return au_by_date

    def get_daily_region_au(self, days: int = 28, today: date | None = None) -> dict:
        """Regional counterpart to get_daily_session_au_weighted — the same
        weighted AU, divided across upper_body / core / lower_body plus an
        `unattributed` bucket.

        {"rows": [{"date", "upper_body", "core", "lower_body", "unattributed",
                   "total_au", "regions_known"}],
         "unmapped_names", "renormalised_names", "attributed_fraction"}

        Per date the four parts sum to that date's total_au EXACTLY, and
        total_au matches get_daily_session_au_weighted's figure for the same
        window because both read the same _weighted_sessions pass.

        Self-healing over history for exactly the reason that method's
        docstring gives: recomputed live from each day's own Sets JSON on every
        call, so a day logged before this existed splits correctly the very
        next time it is read. NOTHING here is persisted, deliberately — the
        region weights are invented and expected to be revised, and a stored
        column derived from constants you expect to change is the
        does-not-self-heal failure that bit the Stage 1 strain over-count.
        """
        return strain_regions.daily_region_au(
            self._weighted_sessions(days=days, today=today),
        )

    def get_unparsed_session_notes(self) -> list[dict]:
        pages = self._query(
            self.config.notion_db_training,
            filter_={"and": [
                {"property": "Notes", "rich_text": {"is_not_empty": True}},
                {"property": "Note Summary", "rich_text": {"is_empty": True}},
            ]},
            sorts=[{"property": "Session Date", "direction": "ascending"}],
        )
        out = []
        for p in pages:
            note = notion.get_property(p, "Notes", "rich_text") or ""
            if note.strip():
                out.append({
                    "id":            p["id"],
                    "raw_text":      note,
                    "timestamp":     notion.get_property(p, "Session Date", "date"),
                    "movement_name": notion.get_property(p, "Movement", "title"),
                    "session_date":  notion.get_property(p, "Session Date", "date"),
                })
        return out

    def update_session_note_ai(self, note_id: str, summary: str, sentiment_score: float,
                                flagged_body_parts: list, warning_level: str) -> None:
        properties = {
            "Note Summary":  notion.rich_text(summary or ""),
            "Sentiment":     notion.number(sentiment_score),
            "Flagged Areas": notion.rich_text(json.dumps(flagged_body_parts or [])),
            "Warning":       notion.select(warning_level),
        }
        notion.update_page(self._nc, note_id, properties=properties)
        self.mirror_notion_write(notion_reader.TRAINING, note_id, properties,
                                 mode=supabase_store.PATCH)

    def get_recent_raw_notes(self, limit: int = 20) -> list[dict]:
        pages = self._query(
            self.config.notion_db_training,
            filter_={"property": "Notes", "rich_text": {"is_not_empty": True}},
            sorts=[{"property": "Session Date", "direction": "descending"}],
        )
        out = []
        for p in pages[:limit]:
            g = lambda name, kind: notion.get_property(p, name, kind)
            out.append({
                "raw_text":           g("Notes", "rich_text"),
                "ai_summary":         g("Note Summary", "rich_text"),
                "flagged_body_parts": g("Flagged Areas", "rich_text"),
                "warning_level":      g("Warning", "select"),
                "session_date":       g("Session Date", "date"),
            })
        return out

    def get_flagged_entries(self) -> list[dict]:
        results: list[dict] = []
        for p in self._query(
            self.config.notion_db_training,
            filter_={"or": [
                {"property": "Warning", "select": {"equals": "flag"}},
                {"property": "Warning", "select": {"equals": "monitor"}},
            ]},
            sorts=[{"property": "Session Date", "direction": "descending"}],
        )[:50]:
            g = lambda name, kind: notion.get_property(p, name, kind)
            results.append({
                "source": "session_note", "timestamp": g("Session Date", "date"),
                "summary": g("Note Summary", "rich_text"), "warning_level": g("Warning", "select"),
                "body_parts": g("Flagged Areas", "rich_text") or "[]",
                "movement_name": g("Movement", "title"), "session_date": g("Session Date", "date"),
            })
        for p in self._query(
            self.config.notion_db_readiness,
            filter_={"or": [
                {"property": "Warning", "select": {"equals": "flag"}},
                {"property": "Warning", "select": {"equals": "monitor"}},
            ]},
            sorts=[{"property": "Date", "direction": "descending"}],
        )[:50]:
            g = lambda name, kind: notion.get_property(p, name, kind)
            results.append({
                "source": "readiness", "timestamp": g("Date", "date"),
                "summary": str(g("Parsed Severity", "number") or ""),
                "warning_level": g("Warning", "select"), "body_parts": g("Parsed Areas", "rich_text") or "[]",
                "movement_name": None, "session_date": None,
            })
        return results

    # ─────────────────────────────────────────────────────────────────────
    #  Daily Biometrics (Notion — legacy; live biometrics are Sheets-sourced,
    #  see get_biometric_rolling below. Kept for parity; see REFACTOR_NOTES.md.)
    # ─────────────────────────────────────────────────────────────────────




    # ─────────────────────────────────────────────────────────────────────
    #  App Config (flat key/value store — plan_start_date, current_stage,
    #  phases, training_progress, diagnostic_profile, movement risk)
    # ─────────────────────────────────────────────────────────────────────

    _CONFIG_CACHE_TTL_SECONDS = 30.0

    def _config_pages(self) -> dict[str, dict]:
        """Every Config row, keyed by its Key, in ONE query.

        This was an N+1 and it sat on every page's critical path. Each key was
        its own filtered database query — plan_start_date, current_stage,
        phases, diagnostic_profile, latest_movement_risk, training_progress —
        so six methods meant six HTTP round trips against one tiny table.
        Measured 2026-08-10: three of them (get_phases, get_current_stage,
        get_config_value) cost 1.33s of a 4.62s page open, and Notion was 92%
        of that wall time. An unfiltered fetch of the same table costs the same
        as one filtered fetch — the table holds a handful of rows — so this is
        6 round trips traded for 1.

        Cached for _CONFIG_CACHE_TTL_SECONDS, the same shape and TTL as the
        Sheets _read_cache, and INVALIDATED by set_config so a write is always
        visible to the next read. The TTL is what bounds staleness against the
        other writer this cache cannot see: the Notion UI. A Repository is
        process-wide (repo.get_repository is @st.cache_resource), so an
        unbounded memo would hide an edit made in Notion until the process
        restarted.

        Duplicate rows for one Key resolve first-wins, which is what the
        per-key filtered query already did (`pages[0]`); Notion returns no
        guaranteed order either way, so a duplicated key was already
        nondeterministic and this does not make it worse.
        """
        now = time.monotonic()
        entry = self._config_cache
        if entry is not None and now - entry[0] < self._CONFIG_CACHE_TTL_SECONDS:
            return entry[1]
        by_key: dict[str, dict] = {}
        for page in self._query(self.config.notion_db_config):
            key = notion.get_property(page, "Key", "title") or ""
            if key and key not in by_key:
                by_key[key] = page
        self._config_cache = (now, by_key)
        return by_key

    def _invalidate_config_cache(self) -> None:
        self._config_cache = None

    def _config_page(self, key: str) -> dict | None:
        return self._config_pages().get(key)

    def get_current_stage(self) -> int:
        page = self._config_page("current_stage")
        if page:
            try:
                return int(notion.get_property(page, "Value", "rich_text") or "1")
            except (TypeError, ValueError):
                pass
        return 1

    def set_config(self, key: str, value: str, today: date | None = None) -> None:
        today = today or date.today()
        page = self._config_page(key)
        props = {
            "Key": notion.title(key), "Value": notion.rich_text(str(value)),
            "Updated": notion.date_prop(str(today)),
        }
        try:
            if page:
                notion.update_page(self._nc, page["id"], props)
            else:
                notion.create_page(self._nc, self.config.notion_db_config, props)
            # Inside the try and AFTER the write, never in the finally: a
            # Notion failure propagates here, and queueing in the finally
            # would ship a row to Postgres that Notion does not hold. `props`
            # also reuses the `today` resolved above rather than reading the
            # clock again, so a write near midnight cannot stamp two
            # different `updated` dates in the two backends.
            self.mirror_notion_write(notion_reader.CONFIG, key, props)
        finally:
            # Always, even on a failed write: the cached page may be exactly
            # what is wrong (deleted upstream, or a duplicate we picked the
            # wrong side of), and serving it again would repeat the failure.
            self._invalidate_config_cache()

    def get_config_value(self, key: str) -> str | None:
        page = self._config_page(key)
        return notion.get_property(page, "Value", "rich_text") if page else None

    def get_phases(self) -> list[models.Phase]:
        """[] means "nothing has ever been configured" — genuinely safe for
        a caller to treat as a first-run state. A stored value that exists
        but fails to parse raises PhasesCorruptError instead of also
        returning [] (as this used to): views/training.py used to treat an
        empty list as licence to auto-create-and-persist a fresh Phase 1
        (that seed-on-read side effect has since been removed entirely —
        see views/training.py's _get_phases_and_active_phase — Phase 1
        creation is now an explicit button click, same as Phase 2's), which
        would silently overwrite real phase data (including any
        date_overrides reschedule) on a transient read/parse glitch,
        permanently turning a recoverable blip into real data loss. See
        CLAUDE.md's known-issues entry on the
        2026-07-28/29 incident this was written in response to."""
        raw = self.get_config_value("phases")
        if not raw:
            return []
        try:
            return [models.Phase(**p) for p in json.loads(raw)]
        except Exception as exc:
            raise PhasesCorruptError(
                f"stored 'phases' config exists but failed to parse: {exc!r}"
            ) from exc

    def set_phases(self, phases: list[models.Phase], today: date | None = None) -> None:
        payload = [
            {"phase_number": p.phase_number, "name": p.name, "start_date": p.start_date,
             "length_days": p.length_days, "status": p.status,
             "date_overrides": p.date_overrides, "shift_reasons": p.shift_reasons}
            for p in phases
        ]
        self.set_config("phases", json.dumps(payload), today=today)

    def get_diagnostic_profile(self) -> dict:
        page = self._config_page("diagnostic_profile")
        if page:
            raw = notion.get_property(page, "Value", "rich_text") or "{}"
            try:
                return json.loads(raw)
            except Exception:
                pass
        return {}

    def save_movement_risk(self, risk_summary: str, flagged_movements: list, safe_movements: list,
                            correlation_notes: str, model_used: str, now: datetime | None = None) -> None:
        now = now or datetime.now()
        data = {
            "timestamp": str(now)[:19], "risk_summary": risk_summary,
            "flagged_movements": json.dumps(flagged_movements or []),
            "safe_movements": json.dumps(safe_movements or []),
            "correlation_notes": correlation_notes, "model_used": model_used,
        }
        self.set_config("latest_movement_risk", json.dumps(data))

    def get_latest_movement_risk(self) -> dict:
        page = self._config_page("latest_movement_risk")
        if page:
            raw = notion.get_property(page, "Value", "rich_text") or "{}"
            try:
                return json.loads(raw)
            except Exception:
                pass
        return {}

    def get_all_config_rows(self) -> list[dict]:
        """Every key/value row in the Config DB, unwindowed — for
        services.datastore's config table. A faithful copy rather than a
        per-key parse: `value` is whatever raw string is stored (JSON blob
        for phases/diagnostic_profile/latest_movement_risk, a plain string
        for current_stage/garmin_daily_last_synced_at) — interpreting each
        key's own shape is a job for whatever reads the datastore later,
        not for this passthrough."""
        pages = self._query(self.config.notion_db_config)
        return [{
            "key": notion.get_property(p, "Key", "title"),
            "value": notion.get_property(p, "Value", "rich_text"),
            "updated": notion.get_property(p, "Updated", "date"),
        } for p in pages]

    # ─────────────────────────────────────────────────────────────────────
    #  Macro Trend Data
    # ─────────────────────────────────────────────────────────────────────

    def get_macro_trend_data(self, days: int = 90, today: date | None = None) -> dict:
        today = today or date.today()
        cutoff = (today - timedelta(days=days)).isoformat()

        # The Oura+Garmin blend — the engine's actual biometric source (key
        # rule 4). This used to read the Notion Biometrics database, which was
        # RETIRED on 2026-08-12: it held ten pages with every column NULL, had
        # no live writer, and so this panel reported "Biometric days available:
        # 0" and refused to compute for as long as it has existed. Same eight
        # fields, from data that is actually there.
        biometrics = [
            {
                "date": r.date,
                "hrv_ms": r.hrv_ms,
                "resting_heart_rate": r.resting_heart_rate,
                "sleep_duration_hours": r.sleep_duration_hours,
                "sleep_deep_hours": r.sleep_deep_hours,
                "active_energy_kcal": r.active_kcal,
                "weight_kg": r.weight_kg,
                "steps": r.steps,
            }
            for r in self.get_biometric_rolling(days=days, today=today)
            if r.date and r.date >= cutoff
        ]

        read_pages = self._query(
            self.config.notion_db_readiness,
            filter_={"property": "Date", "date": {"on_or_after": cutoff}},
            sorts=[{"property": "Date", "direction": "ascending"}],
        )
        by_day: dict[str, dict] = {}
        for p in read_pages:
            d = notion.get_property(p, "Date", "date") or ""
            if d not in by_day:
                by_day[d] = {"t": [], "pain": [], "stress": [], "travel": 0, "alc": []}
            t = notion.get_property(p, "Tightness", "number")
            n = notion.get_property(p, "Pain", "number")
            s = notion.get_property(p, "Stress Level", "number")
            a = notion.get_property(p, "Alcohol Units", "number") or 0
            v = 1 if notion.get_property(p, "Travel", "checkbox") else 0
            if t is not None: by_day[d]["t"].append(t)
            if n is not None: by_day[d]["pain"].append(n)
            if s is not None: by_day[d]["stress"].append(s)
            by_day[d]["alc"].append(a)
            by_day[d]["travel"] = max(by_day[d]["travel"], v)

        readiness = [
            {
                "date": d,
                "avg_tightness": round(sum(v["t"]) / len(v["t"]), 1) if v["t"] else None,
                "max_pain": max(v["pain"]) if v["pain"] else None,
                "avg_stress": round(sum(v["stress"]) / len(v["stress"]), 1) if v["stress"] else None,
                "travel": v["travel"],
                "avg_alcohol": round(sum(v["alc"]) / len(v["alc"]), 1) if v["alc"] else None,
            }
            for d, v in sorted(by_day.items())
        ]

        train_pages = self._query(
            self.config.notion_db_training,
            filter_={"property": "Session Date", "date": {"on_or_after": cutoff}},
            sorts=[{"property": "Session Date", "direction": "ascending"}],
        )
        seen: set[str] = set()
        sess_by_day: dict[str, dict] = {}
        for p in train_pages:
            sid = notion.get_property(p, "Session ID", "rich_text") or ""
            d   = notion.get_property(p, "Session Date", "date") or ""
            au  = notion.get_property(p, "Session AU", "number") or 0.0
            rpe = notion.get_property(p, "Session RPE", "number") or 0
            if sid and sid not in seen:
                seen.add(sid)
                if d not in sess_by_day:
                    sess_by_day[d] = {"au": 0.0, "rpe": []}
                sess_by_day[d]["au"] += au
                sess_by_day[d]["rpe"].append(rpe)
        sessions = [
            {"date": d, "total_au": round(v["au"], 1),
             "avg_rpe": round(sum(v["rpe"]) / len(v["rpe"]), 1) if v["rpe"] else None}
            for d, v in sorted(sess_by_day.items())
        ]

        return {
            "biometrics": biometrics, "readiness": readiness, "sessions": sessions,
            "flagged_notes": [], "days_requested": days,
        }

    # ─────────────────────────────────────────────────────────────────────
    #  Google Sheets — biometrics
    # ─────────────────────────────────────────────────────────────────────

    def get_raw_sheet_rows(self) -> list[dict]:
        """Every row in Sheet1, completely unmapped (gspread's own header-row
        dict keys) — the Sync page's raw-passthrough preview table.

        Raises offline: the datastore stores Sheet1 already MAPPED (see
        _sheets_biometric_records), so there is nothing here to pass through
        raw. Returning the mapped columns under this method's name would be
        a lie about what "raw passthrough" means, and returning [] would
        read as "the legacy export is empty"."""
        if self.local_datastore:
            raise datastore_reader.DatastoreReadOnlyError(
                "get_raw_sheet_rows() has no offline equivalent — the "
                "datastore holds Sheet1 mapped (sheet1_legacy_biometrics), "
                "not under its raw Apple Health export headers. Use "
                "get_all_sheet1_biometric_records() instead."
            )
        return sheets.get_all_records(self._sc, self.config.google_sheets_id)

    def _sheets_biometric_records(self) -> list[models.BiometricRecord]:
        """Every row in Sheet1, mapped once — the single place that knows the
        Sheets column names. Previously duplicated independently in
        sync_sheets.py (field name `sleep_duration_hours`) and views/sync.py's
        own preview-table loop (field name `sleep_hours` for the same data —
        the two had already drifted; see REFACTOR_NOTES.md). Consolidated here
        and standardized on `sleep_duration_hours`, matching what the engine
        actually consumes.

        Offline this reads sheet1_legacy_biometrics directly rather than
        going through _ws(): the datastore already holds this table in
        BiometricRecord's own field names (services/datastore.py's
        _populate_sheet1_legacy wrote it from this very method), so the
        mapping below has already been applied and re-applying it to the
        mapped names would map everything to None."""
        if self.local_datastore:
            rows = datastore_reader.OfflineWorksheet(
                self._ds, sheets.WORKSHEET, "sheet1_legacy_biometrics").get_all_records()
            return [models.BiometricRecord(
                date=str(r.get("date") or ""),
                hrv_ms=_sheet_float(r.get("hrv_ms")),
                resting_heart_rate=_sheet_int(r.get("resting_heart_rate")),
                sleep_duration_hours=_sheet_float(r.get("sleep_duration_hours")),
                sleep_deep_hours=_sheet_float(r.get("sleep_deep_hours")),
                active_kcal=_sheet_float(r.get("active_kcal")),
                weight_kg=_sheet_float(r.get("weight_kg")),
                steps=_sheet_int(r.get("steps")),
            ) for r in rows if r.get("date")]
        raw_rows = self.get_raw_sheet_rows()
        out = []
        for row in raw_rows:
            d = _sheet_date(row.get("Date/Time", ""))
            if not d:
                continue
            out.append(models.BiometricRecord(
                date=d,
                hrv_ms=_sheet_float(row.get("Heart Rate Variability (ms)")),
                resting_heart_rate=_sheet_int(row.get("Resting Heart Rate (count/min)")),
                sleep_duration_hours=_sheet_float(row.get("Sleep Analysis [Total] (hr)")),
                sleep_deep_hours=_sheet_float(row.get("Sleep Analysis [Deep] (hr)")),
                active_kcal=_sheet_kj_to_kcal(row.get("Active Energy (kJ)")),
                weight_kg=_sheet_float(row.get("Weight (kg)")),
                steps=_sheet_int(row.get("Step Count (count)")),
            ))
        return out

    def get_sheet1_biometric_rolling(self, days: int = 28, today: date | None = None) -> list[models.BiometricRecord]:
        """Last `days` days from the legacy Apple Health/Sheet1 export, sorted
        ascending by date. No longer read by the engine (see
        get_biometric_rolling below) — kept only for
        scripts/backfill_garmin_from_sheet1.py and historical reference."""
        today = today or date.today()
        cutoff = (today - timedelta(days=days)).isoformat()
        today_str = str(today)
        records = [r for r in self._sheets_biometric_records() if cutoff <= r.date <= today_str]
        return sorted(records, key=lambda r: r.date)

    def get_all_sheet1_biometric_records(self) -> list[models.BiometricRecord]:
        """Every Sheet1 row, unwindowed — the full legacy history, for the
        one-time backfill script (which needs pre-wearable dates that a
        rolling window would exclude)."""
        return self._sheets_biometric_records()

    def get_garmin_daily_dates(self) -> set[str]:
        """Every date already present in the Garmin Daily sheet tab — used by
        scripts/backfill_garmin_from_sheet1.py so it only fills dates Garmin
        doesn't already have, never overwriting a real Garmin-synced day."""
        rows = self._read_records(self._garmin_daily_ws())
        return {str(r["date"]) for r in rows if r.get("date")}

    def upsert_garmin_daily_row(self, row: dict) -> None:
        """Writes one already-mapped row (see biometrics.sheet1_row_to_
        garmin_daily_row) into the Garmin Daily tab, keyed by date — same
        upsert primitive sync_garmin_daily uses per-day."""
        values = [row.get(k, "") for k in _GARMIN_DAILY_HEADER]
        self._upsert_sheet_row(self._garmin_daily_ws(), row["date"], values)

    # ─────────────────────────────────────────────────────────────────────
    #  Blended Oura+Garmin — the engine's live biometric source
    # ─────────────────────────────────────────────────────────────────────
    # HRV/RHR/sleep duration: Oura 70% / Garmin 30%. Steps: Garmin 80% /
    # Oura 20%. Weighting math lives in services/biometrics.py (pure,
    # tested independently); this method's job is only fetching each
    # source's already-synced Sheet tab rows and grouping them by date.
    # Replaces Sheet1 as of this change — see get_sheet1_biometric_rolling
    # above for the retired pipeline.

    def _oura_daily_steps_by_date(self, start: str, end: str) -> dict[str, int | None]:
        rows = self._read_records(self._oura_daily_ws())
        return {
            str(r["date"]): (r.get("steps") or None)
            for r in rows if r.get("date") and start <= str(r["date"]) <= end
        }

    def _oura_sleep_metrics_by_date(self, start: str, end: str) -> dict[str, dict]:
        rows = self._oura_tab_records("sleep_periods", self._oura_sleep_periods_ws())
        by_day: dict[str, list[dict]] = {}
        for r in rows:
            day = str(r.get("day") or "")
            if day and start <= day <= end:
                by_day.setdefault(day, []).append(r)

        out: dict[str, dict] = {}
        for day, entries in by_day.items():
            main, naps = biometrics.split_sleep_periods(entries)
            if main is None:
                continue
            duration_s = main.get("total_sleep_duration")
            # DURATION counts the naps; ARCHITECTURE does not. See the sleep-
            # period section of services/biometrics.py for why the two part
            # company here. The practical consequence is that
            # sleep_duration_hours and oura_sleep_total_seconds below are
            # deliberately NOT the same quantity on a day with a nap, and
            # services/sleep_score.py relies on that: the former is its Total
            # Sleep contributor, the latter its REM/deep denominator.
            day_total_s = biometrics.day_total_sleep_seconds(main, naps)
            out[day] = {
                # HRV and resting HR stay main-period-only. A nap's average_hrv
                # is measured over a few minutes of a body that has been awake
                # and upright all day, which is not the same measurement as an
                # overnight average and must not be averaged into one.
                "hrv_ms": main.get("average_hrv") or None,
                "resting_heart_rate": main.get("lowest_heart_rate") or None,
                "sleep_duration_hours": round(day_total_s / 3600, 2) if day_total_s else None,
                # Raw sleep-architecture fields — feeds
                # services.sleep_score.compute_sleep_score. Kept raw (seconds/
                # counts), not pre-scored; that module does its own 0-100 math.
                "oura_sleep_efficiency": main.get("efficiency"),
                "oura_sleep_total_seconds": duration_s,
                "oura_sleep_deep_seconds": main.get("deep_sleep_duration"),
                "oura_sleep_rem_seconds": main.get("rem_sleep_duration"),
                "oura_sleep_latency_seconds": main.get("latency"),
                "oura_sleep_restless_periods": main.get("restless_periods"),
                "oura_sleep_bedtime_start": main.get("bedtime_start") or None,
                "oura_sleep_awake_seconds": main.get("awake_time"),
            }
        return out

    def _garmin_metrics_by_date(self, start: str, end: str) -> dict[str, dict]:
        rows = self._read_records(self._garmin_daily_ws())
        return {
            str(r["date"]): {
                "hrv_ms": r.get("hrv_ms") or None,
                "resting_heart_rate": r.get("resting_hr") or None,
                "sleep_duration_hours": r.get("sleep_hours") or None,
                "steps": r.get("steps") or None,
            }
            for r in rows if r.get("date") and start <= str(r["date"]) <= end
        }

    def _oura_readiness_contributors_by_date(self, start: str, end: str) -> dict[str, dict]:
        """Oura's own daily_readiness contributor sub-scores (0-100), from
        the Oura Daily tab — Oura-exclusive, no Garmin equivalent, so this
        is a straight passthrough rather than a blend. Feeds
        services.readiness.compute_readiness alongside HRV/RHR/Sleep.

        temperature_deviation is the odd one out: the RAW °C figure, not a
        0-100 sub-score, carried alongside body_temperature (Oura's scored
        version of the same reading) because engine.traffic_light applies
        absolute thresholds to it. `or None` is wrong for it — a genuine
        0.0 deviation is a real reading and must not collapse to None the
        way an empty cell does, so it goes through _float_or_none."""
        rows = self._read_records(self._oura_daily_ws())
        return {
            str(r["date"]): {
                "body_temperature":      r.get("readiness_body_temperature") or None,
                "recovery_index":        r.get("readiness_recovery_index") or None,
                "previous_day_activity": r.get("readiness_previous_day_activity") or None,
                "temperature_deviation": _float_or_none(r.get("readiness_temperature_deviation")),
                # Promoted from display-only to engine inputs by readiness
                # MODEL_VERSION 2. `resting_heart_rate` here is Oura's 0-100
                # CONTRIBUTOR, not the bpm — see BiometricRecord's warning on
                # oura_resting_heart_rate_score.
                "hrv_balance":            r.get("readiness_hrv_balance") or None,
                "previous_night":         r.get("readiness_previous_night") or None,
                "sleep_regularity":       r.get("readiness_sleep_regularity") or None,
                "activity_balance":       r.get("readiness_activity_balance") or None,
                "resting_heart_rate":     r.get("readiness_resting_heart_rate") or None,
            }
            for r in rows if r.get("date") and start <= str(r["date"]) <= end
        }

    # ── Oura's own readiness contributors — DISPLAY/AUDIT ONLY ───────────────
    #  Oura publishes nine readiness contributors and all nine are already in
    #  the Oura Daily tab; _oura_readiness_contributors_by_date above lifts
    #  only the three services.readiness actually scores with (plus the raw
    #  temperature deviation engine.traffic_light needs). The other six are
    #  synced and unused.
    #
    #  This is deliberately a SEPARATE read rather than more fields on
    #  BiometricRecord: they are display and model-audit material, not engine
    #  inputs, and threading them through the biometric rows would carry them
    #  into readiness, the traffic light and the metrics-history backfill for
    #  no engine benefit. Same reasoning as get_sleep_night_details, whose
    #  docstring makes the argument at length.
    # ────────────────────────────────────────────────────────────────────────

    _OURA_READINESS_CONTRIBUTORS = (
        ("resting_heart_rate",    "Resting heart rate"),
        ("hrv_balance",           "HRV balance"),
        ("body_temperature",      "Body temperature"),
        ("recovery_index",        "Recovery index"),
        ("previous_night",        "Previous night"),
        ("sleep_balance",         "Sleep balance"),
        ("sleep_regularity",      "Sleep regularity"),
        ("previous_day_activity", "Previous day activity"),
        ("activity_balance",      "Activity balance"),
    )

    def get_oura_readiness_detail(self, start: str, end: str) -> dict[str, dict]:
        """Oura's own readiness score and all nine of its contributors, keyed
        by ISO date.

        ⚠ NO UI CONSUMER. The "Oura says" comparison panel this was written
        for was removed once readiness MODEL_VERSION 2 landed: the drill-down
        shows ONE row per metric, not one per source, and that stays true when
        Garmin joins. Kept because it is the only way to read Oura's own
        composite `readiness_score` — the nine contributors reach the engine
        via BiometricRecord, but the composite does not — and that composite
        is the anchor for checking whether our model has drifted (it is what
        produced the r=0.992 agreement figure, and it is what the Garmin 265
        re-test will need). Same reasoning that keeps readiness.hrv_baseline
        alive with no scoring consumer.

        Contributors come back as {key: 0-100 or None} under `contributors`,
        in _OURA_READINESS_CONTRIBUTORS order (Oura's own screen order), with
        `labels` alongside so the caller needs no column-name knowledge —
        this module stays the only place Sheets column names live.

        Scores are Oura's raw 0-100 numbers, NOT its tier words. Oura's app
        shows "Optimal"/"Good"/"Fair"/"Pay attention", but those thresholds
        are unpublished and demonstrably differ per contributor (45 renders
        as "Fair" while 42 renders as "Pay attention"), so reproducing them
        would mean inventing a mapping and presenting it as Oura's.

        A date with no Oura Daily row is simply absent from the result."""
        rows = self._read_records(self._oura_daily_ws())
        out: dict[str, dict] = {}
        for r in rows:
            d = _sheet_key(r.get("date"))
            if not d or d < start or d > end:
                continue
            out[d] = {
                "readiness_score": _float_or_none(r.get("readiness_score")),
                "temperature_deviation": _float_or_none(
                    r.get("readiness_temperature_deviation")),
                "temperature_trend_deviation": _float_or_none(
                    r.get("readiness_temperature_trend_deviation")),
                "contributors": {
                    key: _float_or_none(r.get(f"readiness_{key}"))
                    for key, _label in self._OURA_READINESS_CONTRIBUTORS
                },
                "labels": {key: label for key, label in self._OURA_READINESS_CONTRIBUTORS},
            }
        return out

    def hrv_blend_status(self, days: int = 60, today: date | None = None) -> dict:
        """Where the Oura/Garmin HRV comparison stands, and therefore whether
        services.biometrics.HRV_GARMIN_HOLD can be lifted.

        Reads both platforms' already-synced tabs (no device calls) and pairs
        the nights where BOTH reported an HRV, then hands them to the pure
        biometrics.hrv_agreement. Returns its stats plus `held` (is the hold
        currently on) and `garmin_nights` (how many nights Garmin reported
        HRV at all — which is 0 for the whole Forerunner 645 era, and is the
        first number that will move when a watch supporting HRV Status
        arrives).

        Existence of this method is the point: the hold is meant to be lifted
        on a measurement, and a measurement nobody can run is a measurement
        nobody will make."""
        today = today or date.today()
        start = (today - timedelta(days=days)).isoformat()
        end = today.isoformat()

        oura_hrv = {
            d: m.get("hrv_ms")
            for d, m in self._oura_sleep_metrics_by_date(start, end).items()
            if m.get("hrv_ms") is not None
        }
        garmin_hrv = {
            d: m.get("hrv_ms")
            for d, m in self._garmin_metrics_by_date(start, end).items()
            if m.get("hrv_ms") is not None
        }
        paired = [(oura_hrv[d], garmin_hrv[d]) for d in sorted(oura_hrv) if d in garmin_hrv]

        status = biometrics.hrv_agreement(paired)
        status["held"] = biometrics.HRV_GARMIN_HOLD
        status["garmin_nights"] = len(garmin_hrv)
        status["oura_nights"] = len(oura_hrv)
        status["window_days"] = days
        return status

    def _alcohol_units_by_date(self, days: int, today: date) -> dict[str, float]:
        """Alcohol units logged via the morning check-in (Notion Readiness
        DB — not a wearable source), keyed by date. Feeds
        services.readiness.compute_readiness's flat point penalty."""
        rows = self.get_recent_readiness(days=days, today=today)
        return {
            r["date"]: float(r["alcohol_units"])
            for r in rows
            if r.get("date") and r.get("alcohol_units") is not None
        }

    def get_biometric_rolling(self, days: int = 28, today: date | None = None) -> list[models.BiometricRecord]:
        """Last `days` days, sorted ascending by date — the shape the
        engine's traffic_light()/readiness computations expect. Blends
        Oura + Garmin (services/biometrics.py) rather than reading Sheet1;
        both platforms' Sheet tabs are kept fresh by sync_oura_all (2h cache,
        app.py) and sync_garmin_daily_if_due (once/day, app.py + training.py)
        before this reads them. Also the Sync page's "Engine View" preview.

        Oura's readiness contributor sub-scores (body temperature, recovery
        index, previous day activity), Oura's raw sleep-architecture fields
        (efficiency, deep/rem seconds, latency, restless periods, bedtime —
        feeds services.sleep_score), and alcohol units from the morning
        check-in are attached as a passthrough after blending — none of
        these are part of the Oura/Garmin weighted-average fields above
        (alcohol isn't even a wearable reading, it's self-reported)."""
        today = today or date.today()
        start = (today - timedelta(days=days)).isoformat()
        end = today.isoformat()

        oura_steps = self._oura_daily_steps_by_date(start, end)
        oura_sleep = self._oura_sleep_metrics_by_date(start, end)
        garmin_metrics = self._garmin_metrics_by_date(start, end)
        oura_readiness = self._oura_readiness_contributors_by_date(start, end)
        alcohol = self._alcohol_units_by_date(days, today)

        all_dates = (
            set(oura_steps) | set(oura_sleep) | set(garmin_metrics)
            | set(oura_readiness) | set(alcohol)
        )
        records = []
        for d in all_dates:
            oura_day = dict(oura_sleep.get(d, {}))
            oura_day["steps"] = oura_steps.get(d)
            garmin_day = garmin_metrics.get(d, {})
            record = biometrics.blend_biometric_day(d, oura_day, garmin_day)
            contributors = oura_readiness.get(d)
            if contributors:
                record = dataclasses.replace(
                    record,
                    oura_body_temperature=contributors.get("body_temperature"),
                    oura_recovery_index=contributors.get("recovery_index"),
                    oura_previous_day_activity=contributors.get("previous_day_activity"),
                    oura_temperature_deviation=contributors.get("temperature_deviation"),
                    oura_hrv_balance=contributors.get("hrv_balance"),
                    oura_previous_night=contributors.get("previous_night"),
                    oura_sleep_regularity=contributors.get("sleep_regularity"),
                    oura_activity_balance=contributors.get("activity_balance"),
                    oura_resting_heart_rate_score=contributors.get("resting_heart_rate"),
                )
            sleep_raw = oura_sleep.get(d)
            if sleep_raw:
                record = dataclasses.replace(
                    record,
                    oura_sleep_efficiency=sleep_raw.get("oura_sleep_efficiency"),
                    oura_sleep_total_seconds=sleep_raw.get("oura_sleep_total_seconds"),
                    oura_sleep_deep_seconds=sleep_raw.get("oura_sleep_deep_seconds"),
                    oura_sleep_rem_seconds=sleep_raw.get("oura_sleep_rem_seconds"),
                    oura_sleep_latency_seconds=sleep_raw.get("oura_sleep_latency_seconds"),
                    oura_sleep_restless_periods=sleep_raw.get("oura_sleep_restless_periods"),
                    oura_sleep_bedtime_start=sleep_raw.get("oura_sleep_bedtime_start"),
                    oura_sleep_awake_seconds=sleep_raw.get("oura_sleep_awake_seconds"),
                )
            if d in alcohol:
                record = dataclasses.replace(record, alcohol_units=alcohol[d])
            records.append(record)
        return sorted(records, key=lambda r: r.date)

    # ─────────────────────────────────────────────────────────────────────
    #  Biometric Blend — persisted history
    #  get_biometric_rolling() above is a live recompute (cheap, but the
    #  *result* is never fixed — if a weight changes later, or Oura/Garmin
    #  retroactively revise a day's raw reading, a live recompute of a past
    #  date would silently change too). This persists each day's blended
    #  result once, so "look back at last month" reads a stable snapshot
    #  rather than a re-derived value. Written by sync_biometric_blend,
    #  called once/day from app.py (rolling few-day window) and on-demand
    #  from the Sync page's "Backfill full history" button (wide window).
    # ─────────────────────────────────────────────────────────────────────

    def _biometric_blend_ws(self):
        return self._ws(sheets.BIOMETRIC_BLEND_WORKSHEET, _BIOMETRIC_BLEND_HEADER)

    def _biometric_blend_row(self, record: models.BiometricRecord) -> dict:
        return {
            "date": record.date,
            "hrv_ms": record.hrv_ms if record.hrv_ms is not None else "",
            "resting_heart_rate": record.resting_heart_rate if record.resting_heart_rate is not None else "",
            "sleep_duration_hours": record.sleep_duration_hours if record.sleep_duration_hours is not None else "",
            "steps": record.steps if record.steps is not None else "",
            "sources_missing": json.dumps(list(record.sources_missing)) if record.sources_missing else "",
        }

    def upsert_biometric_blend_row(self, record: models.BiometricRecord,
                                    existing=_UNSET) -> None:
        """Writes one blended day into the Biometric Blend tab, keyed by
        date — re-running this for the same date overwrites it (idempotent),
        which is how a rolling few-day sync keeps very recent days current
        while older days (outside that rolling window) stop being touched
        and become a fixed historical record."""
        row = self._biometric_blend_row(record)
        values = [row.get(k, "") for k in _BIOMETRIC_BLEND_HEADER]
        ws = self._biometric_blend_ws()
        if self._skip_unchanged(ws, _BIOMETRIC_BLEND_HEADER, "date",
                                record.date, values, existing):
            return
        self._upsert_sheet_row(ws, record.date, values)

    def sync_biometric_blend(self, days: int = 7, today: date | None = None) -> int:
        """Computes get_biometric_rolling(days, today) and persists every
        resulting day to the Biometric Blend tab. Returns the number of days
        written. `days` controls how far back to (re)persist — small (e.g. 7)
        for the routine once/day sync so only recent days get overwritten;
        large (e.g. 400) for the one-time/on-demand full-history backfill."""
        records = self.get_biometric_rolling(days=days, today=today)
        # One read of the tab up front, not one per row — see _rows_by_key.
        existing = self._rows_by_key(self._biometric_blend_ws(), "date")
        for r in records:
            self.upsert_biometric_blend_row(r, existing=existing.get(_sheet_key(r.date)))
        return len(records)

    def sync_biometric_blend_if_due(self, days: int = 7, today: date | None = None,
                                     hours: float = 2, now: datetime | None = None
                                     ) -> tuple[bool, str | None]:
        """sync_biometric_blend() at most every `hours` hours, with a durable
        marker (see the sync throttle section).

        This had no durable throttle at all — app.py relied purely on
        st.cache_data's TTL, which is in-memory, dies with the process, and
        is wiped by the blanket st.cache_data.clear() views/checkin.py calls
        on every check-in save. The blend derives from the Oura/Garmin tabs,
        so re-persisting it more often than those themselves sync cannot
        produce a different answer — it just spends a Sheets write per day in
        the window, against the same quota the Oura sync is already
        straining."""
        return self.run_sync_if_due(
            "biometric_blend", lambda: self.sync_biometric_blend(days=days, today=today),
            hours=hours, now=now,
        )

    def get_biometric_blend_history(
        self, start: str | None = None, end: str | None = None,
    ) -> list[models.BiometricRecord]:
        """Every persisted day from the Biometric Blend tab, optionally
        restricted to [start, end] (inclusive, ISO date strings) — unbounded
        by default, unlike get_biometric_rolling's rolling window. Sorted
        ascending by date."""
        rows = self._read_records(self._biometric_blend_ws())
        out = []
        for r in rows:
            d = str(r.get("date") or "")
            if not d:
                continue
            if start and d < start:
                continue
            if end and d > end:
                continue
            sm_raw = r.get("sources_missing") or ""
            try:
                sources_missing = tuple(json.loads(sm_raw)) if sm_raw else ()
            except (json.JSONDecodeError, TypeError):
                sources_missing = ()
            out.append(models.BiometricRecord(
                date=d,
                hrv_ms=r.get("hrv_ms") or None,
                resting_heart_rate=r.get("resting_heart_rate") or None,
                sleep_duration_hours=r.get("sleep_duration_hours") or None,
                steps=r.get("steps") or None,
                sources_missing=sources_missing,
            ))
        return sorted(out, key=lambda r: r.date)

    # ─────────────────────────────────────────────────────────────────────
    #  Metrics History — persisted Readiness/Sleep/Strain trend
    #  Readiness, Sleep %, and Strain (services.dashboard.
    #  compute_daily_metrics_snapshot) are otherwise pure live recomputes,
    #  same as get_biometric_rolling above — this persists each day's
    #  result once so "look back at last month" reads a stable snapshot
    #  instead of a re-derived value that could drift if e.g. the rehab
    #  stage changes later (strain's CLF depends on the *current* stage;
    #  a live recompute of an old day would silently reflect today's
    #  stage, not the one active back then). Written by
    #  sync_metrics_history, called once/day from app.py (rolling few-day
    #  window) and on-demand with a wide `days` value for a one-time/
    #  full-history backfill — same pattern as Biometric Blend. sleep_pct is
    #  the retired "% of baseline" figure (services/dashboard.py's old
    #  sleep_percent), kept only as an untouched historical column; nothing
    #  reads it anymore. sleep_score (services/sleep_score.py) replaced it
    #  on the Home page and was backfilled across all of history the same
    #  way commit f37a537 backfilled Session AU weighting: a direct wide-
    #  `days` sync_metrics_history call, not a standing UI button.
    # ─────────────────────────────────────────────────────────────────────

    def _metrics_history_ws(self):
        return self._ws(sheets.METRICS_HISTORY_WORKSHEET, _METRICS_HISTORY_HEADER)

    def _metrics_history_row(self, snapshot: dict) -> dict:
        return {
            "date": snapshot["date"],
            "readiness_score": snapshot["readiness_score"] if snapshot["readiness_score"] is not None else "",
            "sleep_pct": snapshot["sleep_pct"] if snapshot["sleep_pct"] is not None else "",
            "sleep_score": snapshot["sleep_score"] if snapshot["sleep_score"] is not None else "",
            "strain": snapshot["strain"] if snapshot["strain"] is not None else "",
            "readiness_model_version": readiness.MODEL_VERSION,
        }

    def upsert_metrics_history_row(self, snapshot: dict, existing=_UNSET) -> None:
        """snapshot: {"date": ISO str, "readiness_score", "sleep_pct",
        "sleep_score", "strain"} (services.dashboard.
        compute_daily_metrics_snapshot's shape, plus a "date" key) — writes
        one day into the Metrics History tab, keyed by date (idempotent,
        same upsert-by-date pattern as Biometric Blend)."""
        row = self._metrics_history_row(snapshot)
        values = [row.get(k, "") for k in _METRICS_HISTORY_HEADER]
        ws = self._metrics_history_ws()
        if self._skip_unchanged(ws, _METRICS_HISTORY_HEADER, "date",
                                snapshot["date"], values, existing):
            return
        self._upsert_sheet_row(ws, snapshot["date"], values)

    def rebuild_metrics_history(self, fresh: dict[str, dict] | None = None) -> int:
        """Re-head the Metrics History tab so readiness_model_version stops
        being written into a column no read can see, carrying every existing
        row through. Call once after adding the column; see rebuild_tab for
        why any tab created before a column joined its header needs this."""
        return self.rebuild_tab(self._metrics_history_ws(), _METRICS_HISTORY_HEADER, fresh)

    def sync_metrics_history(self, days: int = 7, today: date | None = None,
                              only_dates: set[str] | None = None) -> int:
        """Computes services.dashboard.compute_daily_metrics_snapshot for
        each of the last `days` days and persists it to the Metrics History
        tab. Returns the number of days written. `days` controls how far
        back to (re)persist — small (e.g. 7) for the routine sync so only
        recent days get overwritten; large (e.g. 400) for the one-time/
        on-demand full-history backfill.

        Pulls a wider lookback window than `days` for its own inputs (60
        extra days of biometric rows, matching app.py's own _bio_rolling,
        to support the 56-night progressive sleep baseline and readiness
        trend's 14-day EMA lookback; 28 extra days of session AU to support
        the 7-day rolling-strain lookback with margin) so even the oldest
        day in the `days` window gets a correctly-computed value, not one
        truncated by an under-fetched window. Also fetches wake-time
        adjustments (get_wake_time_adjustments) for the same `days` window
        as a single bulk read, threaded into each day's snapshot so the
        persisted Sleep Score reflects any per-night wake-time correction.

        `only_dates` (ISO date strings) restricts which days inside the
        window are written, without narrowing the window itself — the
        lookbacks above still see every day, so a restricted run computes
        exactly what an unrestricted one would. It exists so a re-derive can
        reach a distant row without inventing rows for the untouched dates
        between; see rederive_metrics_history, which is what callers want."""
        today = today or date.today()
        bio_rows = [dataclasses.asdict(r) for r in self.get_biometric_rolling(days=days + 60, today=today)]
        au_rows = self.get_daily_session_au_weighted(days=days + 28, today=today)
        stage = self.get_current_stage()
        wake_adjustments, _sources = self.get_effective_wake_adjustments(
            start=(today - timedelta(days=days - 1)).isoformat(), end=today.isoformat(),
        )

        # One read of the tab up front, not one per row — see _rows_by_key.
        existing = self._rows_by_key(self._metrics_history_ws(), "date")
        written = 0
        for i in range(days):
            d = today - timedelta(days=i)
            iso = d.isoformat()
            if only_dates is not None and iso not in only_dates:
                continue
            snapshot = dashboard.compute_daily_metrics_snapshot(
                d, bio_rows, au_rows, stage, wake_time_adjustments=wake_adjustments,
            )
            snapshot["date"] = iso
            self.upsert_metrics_history_row(
                snapshot, existing=existing.get(_sheet_key(iso)),
            )
            written += 1
        return written

    def rederive_metrics_history(self, today: date | None = None) -> int:
        """Recompute every day the Metrics History tab ALREADY holds, and
        write back only those whose values actually moved. Returns the number
        of existing rows re-derived.

        Exists because `days` is the wrong handle for this job. The tab is
        SPARSE — it holds two clusters (2025-09-26→10-13 and 2026-06-29
        onward) separated by eight months with no rows at all — so the
        `sync_metrics_history(days=N)` needed to reach the oldest row also
        invents a row for all 258 dates in between, dates that were never
        measured and have nothing to persist. A backfill that grows a
        54-row tab to 312 is not a re-derive.

        Deliberately no `days` parameter: the window is derived from what is
        stored, which is the only definition of "the rows that exist" that
        cannot drift out of step with the tab."""
        today = today or date.today()
        stored = [r["date"] for r in self.get_metrics_history() if r.get("date")]
        if not stored:
            return 0
        oldest = date.fromisoformat(min(stored))
        span = (today - oldest).days + 1
        return self.sync_metrics_history(
            days=span, today=today, only_dates=set(stored),
        )

    def sync_metrics_history_if_due(self, days: int = 7, today: date | None = None,
                                     hours: float = 2, now: datetime | None = None
                                     ) -> tuple[bool, str | None]:
        """sync_metrics_history() at most every `hours` hours, with a durable
        marker — same rationale as sync_biometric_blend_if_due (it had no
        durable throttle either), and the same cadence, since this derives
        from the blend which derives from the Oura/Garmin tabs."""
        return self.run_sync_if_due(
            "metrics_history", lambda: self.sync_metrics_history(days=days, today=today),
            hours=hours, now=now,
        )

    def get_metrics_history(self, start: str | None = None, end: str | None = None) -> list[dict]:
        """Every persisted day from the Metrics History tab, optionally
        restricted to [start, end] (inclusive, ISO date strings) —
        unbounded by default, like get_biometric_blend_history. Sorted
        ascending by date. Plain dicts, not a dataclass — matches this
        file's existing convention for read-only dashboard-shaped history
        (see module docstring: the "long tail" of newer read-only data was
        deliberately left as dicts rather than typed)."""
        rows = self._read_records(self._metrics_history_ws())
        out = []
        for r in rows:
            d = str(r.get("date") or "")
            if not d:
                continue
            if start and d < start:
                continue
            if end and d > end:
                continue
            out.append({
                "date": d,
                # _blank_or_number, not `or None`: `or` maps a stored 0 to
                # None, and 0 is a real score here — a heavy-alcohol night
                # floors readiness at 0, and a logged session with no load
                # gives strain 0. That mattered little while these only fed
                # sparklines, but dashboard.snapshot_is_complete now reads
                # them to decide whether today is settled, and it tests for
                # None specifically. A genuine 0 read back as None would
                # report the day unsettled and pin Home to the blocking
                # foreground sync on every open for the rest of that day.
                "readiness_score": _blank_or_number(r.get("readiness_score")),
                "sleep_pct": _blank_or_number(r.get("sleep_pct")),
                "sleep_score": _blank_or_number(r.get("sleep_score")),
                "strain": _blank_or_number(r.get("strain")),
                # Which readiness model produced this row. Blank/absent means
                # version 1 — rows written before the column existed. Mapped
                # here as well as stored: this getter lists its keys
                # explicitly, so a column added to the header alone would sit
                # in the sheet and never reach a caller.
                "readiness_model_version": r.get("readiness_model_version") or None,
            })
        return sorted(out, key=lambda r: r["date"])

    # ─────────────────────────────────────────────────────────────────────
    #  Wake Time Adjustments — per-night manual correction for Sleep Score
    #  (CLAUDE.md rule 4's narrow, documented exception to "no manual
    #  biometric entry"). Corrects a known, specific Oura measurement
    #  pattern — wake-time overestimation — not general manual biometric
    #  entry: the raw Oura reading (oura_sleep_awake_seconds, above) is
    #  never touched or overwritten by this. Same tiny-tab upsert-by-date
    #  pattern as Metrics History; services.sleep_score.compute_sleep_score
    #  floors the adjustment at the raw recorded awake-time so it can never
    #  subtract more than was actually logged.
    # ─────────────────────────────────────────────────────────────────────

    def _wake_time_adjustments_ws(self):
        return self._ws(sheets.WAKE_TIME_ADJUSTMENTS_WORKSHEET, _WAKE_TIME_ADJUSTMENTS_HEADER)

    def get_wake_time_adjustment(self, d: date) -> float:
        """The stored adjustment_minutes for date `d`, or 0.0 if nothing has
        ever been set for that date (the "no adjustment" default)."""
        d_str = d.isoformat()
        rows = self._read_records(self._wake_time_adjustments_ws())
        for r in rows:
            if str(r.get("date") or "") == d_str:
                minutes = r.get("adjustment_minutes")
                return float(minutes) if minutes not in (None, "") else 0.0
        return 0.0

    def set_wake_time_adjustment(self, d: date, minutes: float) -> None:
        """Upsert-by-date, same call shape as upsert_metrics_history_row."""
        values = [d.isoformat(), minutes]
        self._upsert_sheet_row(self._wake_time_adjustments_ws(), d.isoformat(), values)

    def get_wake_time_adjustments(self, start: str | None = None, end: str | None = None) -> dict[str, float]:
        """Every persisted adjustment, keyed by ISO date string, optionally
        restricted to [start, end] (inclusive) — the bulk/ranged read a
        caller threading this into services.sleep_score.compute_sleep_score
        over multiple dates wants, instead of one get_wake_time_adjustment
        call per date. Dates with no stored adjustment are simply absent
        (not zero-valued entries)."""
        rows = self._read_records(self._wake_time_adjustments_ws())
        out: dict[str, float] = {}
        for r in rows:
            d = str(r.get("date") or "")
            if not d:
                continue
            if start and d < start:
                continue
            if end and d > end:
                continue
            minutes = r.get("adjustment_minutes")
            if minutes not in (None, ""):
                out[d] = float(minutes)
        return out

    def get_effective_wake_adjustments(self, start: str | None = None,
                                        end: str | None = None,
                                        ) -> tuple[dict[str, float], dict[str, str]]:
        """The manual per-night wake correction and the fusion-derived one,
        resolved to exactly one value per night.

        Both mechanisms subtract phantom Oura wake, so applying both would
        double-count. Precedence lives in the pure
        sleep_fusion.effective_wake_adjustments; this method only supplies the
        two inputs. services/sleep_score.py is deliberately untouched by any
        of this — it still receives a plain {date: minutes} dict and behaves
        exactly as before.

        Returns (adjustments, sources) so the UI can name which one won."""
        manual = self.get_wake_time_adjustments(start=start, end=end)
        try:
            fused = self.get_fused_wake_adjustments(start=start, end=end)
        except Exception:
            # The Sleep Fusion tab may not exist yet. Falling back to manual
            # alone keeps Sleep Score behaving exactly as it did before.
            fused = {}
        return sleep_fusion.effective_wake_adjustments(manual, fused)

    # ─────────────────────────────────────────────────────────────────────
    #  Google Sheets — Weekly Rollup
    # ─────────────────────────────────────────────────────────────────────

    def _weekly_rollup_ws(self):
        return self._ws(sheets.WEEKLY_ROLLUP_WORKSHEET, _WEEKLY_ROLLUP_HEADER)

    def get_weekly_rollup_history(self) -> list[models.WeekScore]:
        """Every row in the Weekly Rollup tab, mapped back to WeekScore.
        Rows that fail to parse (e.g. a hand-edited or malformed row) are
        skipped rather than raising, since this is historical/display data."""
        raw_rows = sheets.get_weekly_rollup_records(self._weekly_rollup_ws())
        out = []
        for row in raw_rows:
            try:
                phase_raw = row.get("phase")
                out.append(models.WeekScore(
                    week_start=str(row["week_start"]),
                    week_end=str(row["week_end"]),
                    phase_number=int(phase_raw) if phase_raw not in (None, "", "None") else None,
                    scheduled=int(row["scheduled"]),
                    completed=int(row["completed"]),
                    status=row["status"],
                    computed_at=str(row["computed_at"]) if row.get("computed_at") else None,
                ))
            except (KeyError, ValueError, TypeError):
                continue
        return out

    def upsert_weekly_rollup(self, scores: list[models.WeekScore]) -> list[str]:
        """Writes each WeekScore as a row in the Weekly Rollup tab, keyed on
        week_start (update-in-place if that week_start already has a row,
        append otherwise). Returns the week_start values written."""
        ws = self._weekly_rollup_ws()
        written = []
        for score in scores:
            row_values = [
                score.week_start,
                score.week_end,
                str(score.phase_number) if score.phase_number is not None else "",
                str(score.scheduled),
                str(score.completed),
                f"{score.completed}/{score.scheduled}",
                score.status,
                score.computed_at or "",
            ]
            sheets.upsert_weekly_rollup_row(ws, key_col=1, key_value=score.week_start, row_values=row_values)
            written.append(score.week_start)
        return written


    # ─────────────────────────────────────────────────────────────────────
    #  Garmin — daily wellness metrics + activities
    #  Daily wellness metrics feed services/engine.py's readiness/ACWR
    #  pipeline (30% weight, blended with Oura — see
    #  get_biometric_rolling/services/biometrics.py) via the Garmin Daily
    #  sheet tab written here. Also used for the run/walk training-log hook
    #  in views/training.py and its own Garmin Activities sheet tab.
    # ─────────────────────────────────────────────────────────────────────

    def garmin_configured(self) -> bool:
        return bool(self.config.garmin_email and self.config.garmin_password)

    def _garmin_daily_ws(self):
        return self._ws(sheets.GARMIN_DAILY_WORKSHEET, _GARMIN_DAILY_HEADER)

    def _garmin_activities_ws(self):
        return self._ws(sheets.GARMIN_ACTIVITIES_WORKSHEET, _GARMIN_ACTIVITY_HEADER)

    def _garmin_sleep_stages_ws(self):
        return self._ws(sheets.GARMIN_SLEEP_STAGES_WORKSHEET, _GARMIN_SLEEP_STAGES_HEADER)

    def _sleep_fusion_ws(self):
        return self._ws(sheets.SLEEP_FUSION_WORKSHEET, _SLEEP_FUSION_HEADER)

    def _session_hr_ws(self):
        return self._ws(sheets.SESSION_HR_WORKSHEET, _SESSION_HR_HEADER)

    # ── Heart-rate load (Edwards' TRIMP) ─────────────────────────────────

    def garmin_activity_hr_samples(self, activity_id) -> list[tuple[float, float]]:
        """(epoch_seconds, bpm) samples for one activity.

        Garmin returns detail metrics as parallel arrays plus a
        `metricDescriptors` list naming each column, so the HR and timestamp
        column INDEXES have to be looked up by key rather than assumed —
        they move between activity types and firmware versions. Anything
        unrecognised yields [] and the caller falls back to Garmin's own
        zone summary.
        """
        client = self._gc
        if client is None:
            return []
        detail = garmin.get_activity_details(client, activity_id)
        descriptors = detail.get("metricDescriptors") or []
        metrics = detail.get("activityDetailMetrics") or []
        if not descriptors or not metrics:
            return []

        idx_hr = idx_ts = None
        for d in descriptors:
            key = (d.get("key") or "").lower()
            if key == "directheartrate":
                idx_hr = d.get("metricsIndex")
            elif key in ("directtimestamp", "sumelapsedduration"):
                # directTimestamp is epoch milliseconds; sumElapsedDuration is
                # seconds from activity start — either anchors the series.
                if idx_ts is None or key == "directtimestamp":
                    idx_ts, ts_key = d.get("metricsIndex"), key
        if idx_hr is None or idx_ts is None:
            return []
        ts_is_epoch_ms = any(
            (d.get("key") or "").lower() == "directtimestamp"
            and d.get("metricsIndex") == idx_ts for d in descriptors
        )
        start_epoch = 0.0
        if not ts_is_epoch_ms:
            start_dt = hr_matching._to_dt(detail.get("summaryDTO", {}).get("startTimeLocal"))
            start_epoch = start_dt.timestamp() if start_dt else 0.0

        out: list[tuple[float, float]] = []
        for row in metrics:
            vals = row.get("metrics") or []
            if idx_hr >= len(vals) or idx_ts >= len(vals):
                continue
            hr, ts = vals[idx_hr], vals[idx_ts]
            if hr is None or ts is None:
                continue
            try:
                epoch = float(ts) / 1000.0 if ts_is_epoch_ms else start_epoch + float(ts)
                out.append((epoch, float(hr)))
            except (TypeError, ValueError):
                continue
        return out

    def get_observed_hr_max(self, days: int = 365, today: date | None = None) -> float | None:
        """Highest plausible heart rate seen across synced Garmin data —
        the HRmax that every Edwards' zone boundary is computed against.

        Reads the already-synced Sheet tabs rather than calling Garmin, so
        this is cheap enough to call on any render. Draws on both per-activity
        max HR (where a real maximal effort actually shows up) and the daily
        summary max. See services.hr_load.estimate_hr_max for why observed-max
        is used instead of an age formula.
        """
        today = today or date.today()
        cutoff = (today - timedelta(days=days)).isoformat()
        observed: list[float | None] = []
        for ws_getter, date_key in (
            (self._garmin_activities_ws, "date"),
            (self._garmin_daily_ws, "date"),
        ):
            try:
                for row in ws_getter().get_all_records():
                    if str(row.get(date_key, ""))[:10] >= cutoff:
                        observed.append(_sheet_float(row.get("max_hr")))
            except Exception:
                continue
        return hr_load.estimate_hr_max(observed)

    def get_garmin_activities_for_date(self, d: date | str) -> list[dict]:
        """Every Garmin activity recorded on calendar date `d`, as normalised
        rows (_garmin_activity_row's shape) — the hike/walk importer's fetch,
        date-scoped so a past day (the 2026-08-08 Mittenwald walk that
        motivated it) costs one API call instead of a guessed limit walk.
        Returns [] when Garmin is unconfigured; API errors (incl. RateLimited)
        propagate so the view can say what happened rather than silently
        showing an empty day."""
        if self._gc is None:
            return []
        return [self._garmin_activity_row(a)
                for a in garmin.get_activities_for_date(self._gc, d)]

    def find_open_garmin_activity(self, day: str) -> dict | None:
        """Today's longest Garmin activity, or None.

        Used by the completion screen to tell the athlete whether the watch
        workout has actually been saved yet. A Garmin activity IN PROGRESS
        does not appear in the API at all — it materialises only once the
        athlete stops and syncs it — so a None here is an actionable prompt
        ("go stop your watch"), not an error. Checking before the session is
        saved is the whole point: afterwards the athlete has walked away and
        the heart-rate record for that session cannot be recovered.
        """
        if self._gc is None:
            return None
        try:
            rows = [self._garmin_activity_row(a)
                    for a in garmin.get_recent_activities(self._gc, limit=15)]
        except Exception:
            return None
        today = [r for r in rows if r.get("date") == day]
        return max(today, key=lambda r: r.get("duration_minutes") or 0) if today else None

    def compute_session_hr(
        self, session_date: date | str, set_records_by_exercise: dict,
        duration_minutes: float = 0.0, hr_max: float | None = None,
        hr_rest: float | None = None, activity_limit: int = 20,
        force_activity_id: str | None = None, shift_hours: float = 0.0,
    ) -> dict | None:
        """Match a logged session to a Garmin activity and derive its
        heart-rate load. None when nothing matched — the caller then falls
        back to RPE-only strain, exactly as before this existed.

        `set_records_by_exercise`: {exercise_idx: [set records]} straight from
        the Sets JSON — the per-set "ts" timestamps are what make time-window
        matching (and per-exercise attribution) possible at all, so sessions
        logged before per-set capture existed correctly return None here.

        Returns a dict with "needs_choice": True instead of a load summary
        when the day HAS activities but none aligns convincingly — the travel
        case, where HEALTH_TIMEZONE names one zone and the watch recorded in
        another. The caller is expected to show `candidates` and ask. Guessing
        is specifically what this avoids: an hour-shifted session still
        overlaps a long activity enough to look like a match, and would
        attribute every exercise an hour of the wrong heart rate.

        `force_activity_id` / `shift_hours` are how that answer comes back.
        """
        if self._gc is None:
            return None
        all_sets = [r for rows in (set_records_by_exercise or {}).values() for r in rows]
        window = hr_matching.session_window(
            all_sets, duration_minutes=duration_minutes)
        if window is None:
            return None
        if shift_hours:
            window = (window[0] + timedelta(hours=shift_hours),
                      window[1] + timedelta(hours=shift_hours))
            all_sets = [dict(r, ts=hr_matching.shift_ts(r.get("ts"), shift_hours))
                        for r in all_sets]
            set_records_by_exercise = {
                i: [dict(r, ts=hr_matching.shift_ts(r.get("ts"), shift_hours)) for r in rows]
                for i, rows in (set_records_by_exercise or {}).items()
            }

        day = str(session_date)[:10]
        candidates = [
            self._garmin_activity_row(a)
            for a in garmin.get_recent_activities(self._gc, limit=activity_limit)
        ]
        # Same-day filter uses the SHIFTED window's date: training late in
        # Ireland can land the Berlin-rendered clock on the following day.
        candidates = [c for c in candidates
                      if c.get("date") in (day, str(window[0].date()))]

        if force_activity_id:
            activity = next((c for c in candidates
                             if str(c.get("activity_id")) == str(force_activity_id)), None)
            if activity is None:
                return None
            overlap = hr_matching.overlap_seconds(
                window[0], window[1], activity.get("start_time_local"),
                hr_matching._to_dt(activity.get("start_time_local"))
                + timedelta(minutes=float(activity.get("duration_minutes") or 0)))
        else:
            activity, overlap = hr_matching.match_activity(candidates, window)
            quality = hr_matching.match_quality(window, activity, overlap)
            if activity is None or quality < hr_matching.MIN_MATCH_QUALITY:
                alts = hr_matching.alignment_candidates(candidates, window)
                if alts:
                    return {
                        "needs_choice": True,
                        "session_au": None,
                        "reason": ("no activity lines up with this session's clock"
                                   if activity is None else
                                   f"best overlap covers only {quality:.0%} of the session"),
                        "window": window,
                        "candidates": alts,
                    }
                return None

        if hr_max is None:
            hr_max = self.get_observed_hr_max()
        if hr_max is None:
            return None
        if hr_rest is None:
            # Heart-rate RESERVE divides by (max - rest), so a wrong resting
            # value distorts every derived intensity. Use the measured
            # Oura/Garmin median rather than the activity's own minimum,
            # which on 2026-08-06 read 73 against a true 54 because the
            # athlete never stopped moving.
            try:
                rows = self.get_biometric_rolling(days=45) or []
                rests = sorted(float(r.resting_heart_rate) for r in rows
                               if getattr(r, "resting_heart_rate", None))
                hr_rest = rests[len(rests) // 2] if rests else None
            except Exception:
                hr_rest = None

        activity_id = activity.get("activity_id")
        samples = self.garmin_activity_hr_samples(activity_id)
        if samples:
            zones = hr_load.seconds_in_zone_from_samples(samples, hr_max)
            zone_source = "samples"
        else:
            zones = hr_load.seconds_in_zone_from_garmin_zones(
                garmin.get_activity_hr_zones(self._gc, activity_id))
            zone_source = "garmin_zones"
        if not zones:
            return None

        summary = hr_load.session_hr_summary(
            zones,
            avg_hr=_sheet_float(activity.get("avg_hr")),
            max_hr=_sheet_float(activity.get("max_hr")),
            hr_rest=hr_rest, hr_max=hr_max,
            duration_minutes=float(activity.get("duration_minutes") or 0),
        )

        # Per-exercise attribution — only possible from a real sample series.
        #
        # An exercise with NO samples is recorded as uncovered rather than
        # skipped. Skipping it made a paused watch invisible: the session
        # still produced a confident-looking figure, from only the exercises
        # that happened to be recorded. Keeping the row is what lets the
        # coverage fraction below be true.
        per_exercise: dict[str, dict] = {}
        rpe_blocks: list[dict] = []
        if samples:
            for block in hr_matching.exercise_blocks(set_records_by_exercise):
                key = str(block["exercise_idx"])
                blk = hr_matching.samples_for_block(samples, block["start"], block["end"])
                rpe_blocks.append({"name": key, "samples": blk})
                if not blk:
                    per_exercise[key] = {"edwards_load": 0.0, "avg_hr": None,
                                          "max_hr": None, "minutes": 0.0,
                                          "hr_rpe": None, "covered": False}
                    continue
                blk_zones = hr_load.seconds_in_zone_from_samples(blk, hr_max)
                hrs = [hr for _, hr in blk]
                rpe = hr_load.exercise_hr_rpe(hrs, hr_rest, hr_max)
                per_exercise[key] = {
                    "edwards_load": hr_load.edwards_load(blk_zones),
                    "avg_hr": round(sum(hrs) / len(hrs), 1),
                    "max_hr": max(hrs),
                    "minutes": round(sum(blk_zones.values()) / 60.0, 1),
                    "hr_rpe": rpe["rpe"],
                    "covered": True,
                }

        # HR-derived session RPE and AU, on ACTIVE minutes only.
        #
        # NOT a replacement for the self-reported Foster AU, and deliberately
        # stored beside it: CLAUDE.md rule 2b keeps ACWR on one unit, because
        # a load figure that changes depending on whether the watch happened
        # to be running would swing the ceiling on button behaviour rather
        # than physiology. This is the paired signal that rule says must
        # accumulate before the two can ever be unified.
        rpe_summary = hr_load.session_hr_rpe(
            rpe_blocks, hr_rest=hr_rest, hr_max=hr_max,
            session_minutes=float(duration_minutes or activity.get('duration_minutes') or 0),
        )

        summary.update({
            "date": day,
            "activity_id": activity_id,
            "activity_name": activity.get("name", ""),
            "activity_type": activity.get("type", ""),
            "start_time_local": activity.get("start_time_local", ""),
            "duration_minutes": activity.get("duration_minutes"),
            "overlap_minutes": round(overlap / 60.0, 1),
            "zone_source": zone_source,
            "per_exercise": per_exercise,
            "hr_rpe": rpe_summary["session_rpe"],
            "hr_au": rpe_summary["au_session"],
            "hr_au_active": rpe_summary["au_active"],
            "hr_active_minutes": rpe_summary["active_minutes"],
            "hr_coverage": rpe_summary["coverage"],
            "hr_covered_exercises": rpe_summary["covered_exercises"],
            "hr_total_exercises": rpe_summary["total_exercises"],
        })
        return summary

    def save_session_hr(self, summary: dict) -> None:
        """Persist one session's HR load to the Session HR tab, keyed by date
        (idempotent — re-running a day overwrites rather than duplicating)."""
        row = {
            **summary,
            "zone_minutes_json": json.dumps(summary.get("zone_minutes") or {}),
            "per_exercise_json": json.dumps(summary.get("per_exercise") or {}),
        }
        values = [row.get(k, "") if row.get(k) is not None else "" for k in _SESSION_HR_HEADER]
        self._upsert_sheet_row(self._session_hr_ws(), row["date"], values)

    def reassign_exercise_rpe_from_hr(self, d: date, per_exercise: dict) -> int:
        """Write each exercise's HR-DERIVED RPE onto its own Notion row.

        The session slider is one number for a whole hour. It is the athlete's
        honest answer to "how hard was that session" and it stays exactly where
        it is — it feeds session_au, and through it Strain and ACWR, and key
        rule 2b is emphatic that nothing heart-rate-derived may go near that.
        What it is NOT is a per-exercise rating, and it used to be copied onto
        every exercise as though it were: a 90-second pressure release and a set
        of RDLs both recorded RPE 8 on 2026-08-14 because the session did.

        This assigns the real per-exercise figure, from the heart rate actually
        recorded during that exercise's own working sets (%HRR, mean blended
        with peak — services/hr_load.exercise_hr_rpe). On the 2026-08-10 session
        it separates the pressure release (1.4) from the Pallof hold (5.2),
        which is the distinction the flat value erased.

        WHY THIS RUNS AFTER THE FACT rather than at save time: HR attribution
        needs the Garmin activity, and the activity is not on Garmin's servers
        when the last set is logged. So the exercise row is written with a null
        RPE and this fills it in on the next sync.

        MATCHED BY MOVEMENT NAME, which is the only key both callers of
        compute_session_hr agree on — get_session_sets_by_exercise's docstring
        has the reason: an integer key means the plan-day index on the live path
        and a renumbering-from-zero on the rebuilt path, so it would attribute
        heart rate to the wrong movement.

        Skips an exercise whose block has no samples (`covered` False) or no
        derivable rate: a null RPE is "not measured", and overwriting it with a
        guess is the failure this whole change exists to undo. Returns the
        number of rows actually updated.
        """
        usable = {name: v.get("hr_rpe") for name, v in (per_exercise or {}).items()
                  if v.get("covered") and v.get("hr_rpe") is not None}
        if not usable:
            return 0
        pages = self._query(
            self.config.notion_db_training,
            filter_={"property": "Session Date", "date": {"equals": str(d)}},
        )
        updated = 0
        for page in pages:
            name = notion.get_property(page, "Movement", "title") or ""
            rpe = usable.get(name)
            if rpe is None:
                continue
            properties = {"Exercise RPE": notion.number(round(float(rpe), 1))}
            notion.update_page(self._nc, page["id"], properties=properties)
            # PATCH, never UPSERT. This touches one property of an existing
            # page; a partial upsert would insert an orphan training_exercises
            # row carrying an RPE and nothing else — no session_id, no movement,
            # no sets — indistinguishable from a real logged exercise to
            # anything counting rows.
            self.mirror_notion_write(notion_reader.TRAINING, page["id"],
                                     properties, mode=supabase_store.PATCH)
            updated += 1
        return updated

    def get_session_hr_history(self, start: str | None = None) -> list[dict]:
        """Persisted per-session HR load, oldest first. `start` is an
        inclusive ISO date filter."""
        try:
            records = self._session_hr_ws().get_all_records()
        except Exception:
            return []
        out = []
        for r in records:
            d = str(r.get("date", ""))[:10]
            if not d or (start and d < start):
                continue
            out.append({
                "date": d,
                "edwards_load": _sheet_float(r.get("edwards_load")),
                "hr_strain": _sheet_float(r.get("hr_strain")),
                "banister_trimp": _sheet_float(r.get("banister_trimp")),
                "avg_hr": _sheet_float(r.get("avg_hr")),
                "max_hr": _sheet_float(r.get("max_hr")),
                "hr_max_used": _sheet_float(r.get("hr_max_used")),
                "activity_name": r.get("activity_name", ""),
                "activity_type": r.get("activity_type", ""),
                "zone_source": r.get("zone_source", ""),
                "overlap_minutes": _sheet_float(r.get("overlap_minutes")),
                "zone_minutes": _json_or(r.get("zone_minutes_json"), {}),
                "per_exercise": _json_or(r.get("per_exercise_json"), {}),
            })
        return sorted(out, key=lambda r: r["date"])

    def get_all_session_hr_rows(self) -> list[dict]:
        """Every column of every persisted Session HR row, unmapped (unlike
        get_session_hr_history, which narrows to the subset services/hr_load
        consumers need and drops activity_id/start_time_local/
        duration_minutes/total_minutes) — for services.datastore's session_hr
        table. zone_minutes_json/per_exercise_json stay undecoded (opaque
        TEXT), same as the live tab."""
        try:
            return self._read_records(self._session_hr_ws())
        except Exception:
            return []

    def get_session_sets_by_exercise(self, d: date) -> dict[str, list[dict]]:
        """{movement name: per-set records} for the session logged on `d`.

        The per-set "ts" timestamps in here are the only thing that makes
        heart-rate matching possible, and they live in the "Sets" rich_text
        JSON — NOT on models.ExerciseEntry, which carries the aggregates
        (actual_sets, total_volume_kg) and no per-set detail at all.

        Keyed by MOVEMENT NAME rather than by position. The two callers of
        compute_session_hr count exercises differently — views/training.py
        passes live plan-day indices, gaps preserved, while anything rebuilt
        from Notion can only see the exercises that were actually logged,
        renumbered from zero — so an integer key means two different things
        depending on which path produced it, and per-exercise heart rate would
        be attributed to the wrong movement. The name is the same in both.

        One filtered query, not the unwindowed get_all_training_exercises_raw:
        this runs on page open.
        """
        pages = self._query(
            self.config.notion_db_training,
            filter_={"property": "Session Date", "date": {"equals": str(d)}},
        )
        out: dict[str, list[dict]] = {}
        for p in pages:
            name = notion.get_property(p, "Movement", "title") or ""
            if not name:
                continue
            try:
                sets = json.loads(notion.get_property(p, "Sets", "rich_text") or "[]")
            except Exception:
                sets = []          # same defensive fallback as every other reader
            if sets:
                out.setdefault(name, []).extend(sets)
        return out

    def sync_session_hr_for_date(self, d: date, hr_rest: float | None = None) -> bool:
        """Compute + persist HR load for the session logged on `d`. False when
        there's no session, no timestamps, or no matching Garmin activity —
        all ordinary "fall back to RPE" outcomes, not errors.

        This raised AttributeError on EVERY call until 2026-08-10: it read
        `ex.sets` off models.ExerciseEntry, which has no such field. Nothing
        surfaced it — save_session_hr is its only caller's next statement, that
        caller runs inside run_sync_if_due which catches and returns
        (False, message), and the one test that touches it monkeypatches this
        method itself. The consequence was total and silent:
        get_session_hr_history() always returned [], blend_strain always fell
        to SOURCE_RPE, and the Edwards'-TRIMP half of strain reached the
        displayed number on zero days ever.
        """
        # Narrow window deliberately: this runs on page open, and
        # get_recent_sessions is a full Notion query per call.
        lookback = max(2, (date.today() - d).days + 2)
        sessions_on_day = [
            s for s in self.get_recent_sessions(days=lookback) if s.session_date == str(d)
        ]
        if not sessions_on_day:
            return False
        session = sessions_on_day[0]
        by_exercise = self.get_session_sets_by_exercise(d)
        if not by_exercise:
            return False           # logged before per-set capture existed
        summary = self.compute_session_hr(
            d, by_exercise,
            # session_duration_minutes, not duration_minutes — a SECOND
            # AttributeError sitting behind the first, on the same statement,
            # and equally unreachable while the first one fired.
            duration_minutes=float(session.session_duration_minutes or 0),
            hr_rest=hr_rest,
        )
        if not summary:
            return False
        if summary.get("needs_choice"):
            # The day HAS activities but none aligns convincingly — the travel
            # case compute_session_hr documents. That dict carries candidates,
            # not a load summary, and has no "date": save_session_hr would raise
            # KeyError building its row, which run_sync_if_due then swallows as
            # a failed sync. Refusing here makes it what it actually is — no
            # match, fall back to RPE — and leaves the choice to the screen that
            # can ask.
            return False
        self.save_session_hr(summary)
        # Assign each exercise its own RPE from its own heart rate. Deliberately
        # after save_session_hr: the HR record is the measurement and lands
        # first, this is a derived convenience written onto the training rows.
        try:
            self.reassign_exercise_rpe_from_hr(d, summary.get("per_exercise") or {})
        except Exception:
            # Never fail the HR sync over the write-back. The measurement is
            # saved either way, and per_exercise_json keeps the same numbers.
            pass
        return True

    def sync_session_hr_recent_if_due(self, days: int = 2, today: date | None = None,
                                       hours: float = 2, now: datetime | None = None
                                       ) -> tuple[bool, str | None]:
        """sync_session_hr_for_date() over the last `days` days, at most every
        `hours` hours, with a durable marker.

        (True, None) when Garmin isn't configured or the window is already
        fresh — both "nothing to do", not errors. A date that yields nothing
        (no session, no per-set timestamps, no matching activity) is likewise
        a normal fall-back-to-RPE outcome; only a raised exception is a
        failure. Only the last couple of days: a session's Garmin activity
        doesn't change retroactively, and each date costs several calls to
        Garmin's unofficial, rate-limit-sensitive API — the one most worth
        not repeating after a failure."""
        if not self.garmin_configured():
            return True, None
        today = today or date.today()

        def _work():
            for offset in range(days):
                self.sync_session_hr_for_date(today - timedelta(days=offset))

        return self.run_sync_if_due("session_hr", _work, hours=hours, now=now)

    def _garmin_raw_day(self, client, d: date) -> dict:
        """The four Garmin fetches for one day, done ONCE. Split out from
        _garmin_daily_row so the same payloads feed both the Garmin Daily row
        and the Garmin Sleep Stages row — capturing sleep stages therefore
        costs zero additional API calls, which matters on an unofficial API
        that rate-limits by IP."""
        return {
            "summary": garmin.get_daily_summary(client, d),
            "sleep": garmin.get_sleep_data(client, d),
            "stress": garmin.get_stress_data(client, d),
            "hrv": garmin.get_hrv_data(client, d),
        }

    def _garmin_daily_row(self, client, d: date) -> dict:
        """Unchanged public behaviour — fetches, then extracts. Kept as a thin
        wrapper so existing callers and tests are unaffected by the
        _garmin_raw_day split."""
        return self._garmin_daily_row_from_raw(self._garmin_raw_day(client, d), d)

    def _garmin_daily_row_from_raw(self, raw: dict, d: date) -> dict:
        """Field names here are Garmin's well-known (but unofficial, and
        occasionally-shifting) daily-summary/sleep/stress JSON shape. Every
        lookup is defensive — a missing/renamed key yields a blank cell
        rather than breaking the whole sync."""
        summary = raw.get("summary") or {}
        sleep = raw.get("sleep") or {}
        stress = raw.get("stress") or {}
        hrv = raw.get("hrv") or {}

        # Unverified against a live payload — hrvSummary.lastNightAvg matches
        # garminconnect's commonly-documented /hrv-service/hrv/{date} shape.
        # See services/clients/garmin.py::get_hrv_data and
        # scripts/garmin_login_test.py for the live-confirmation step.
        hrv_ms = (hrv.get("hrvSummary") or {}).get("lastNightAvg")

        sleep_dto = sleep.get("dailySleepDTO") or {}
        sleep_seconds = sleep_dto.get("sleepTimeSeconds")
        # Verified against a real payload (2026-07-08): no "sleepScores" key
        # anywhere in the response (top-level keys were just dailySleepDTO,
        # sleepMovement, remSleepData, sleepLevels, sleepHeartRate,
        # sleepStress, skinTempDataExists, restingHeartRate) — this account/
        # device just doesn't get a computed Sleep Score from this endpoint.
        # Kept as a 3-way fallback (not a single lookup) in case a different
        # account/day/device does return one under any of these shapes;
        # still None — a blank cell, not an error — if none match.
        sleep_score = (
            ((sleep_dto.get("sleepScores") or {}).get("overall") or {}).get("value")
            or ((sleep.get("sleepScores") or {}).get("overall") or {}).get("value")
            or sleep.get("overallSleepScore")
        )

        return {
            "date": str(d),
            "steps": summary.get("totalSteps"),
            "resting_hr": summary.get("restingHeartRate"),
            "avg_stress": summary.get("averageStressLevel", stress.get("avgStressLevel")),
            "sleep_score": sleep_score,
            "sleep_hours": round(sleep_seconds / 3600, 2) if sleep_seconds else None,
            "calories_total": summary.get("totalKilocalories"),
            "min_hr": summary.get("minHeartRate"),
            "max_hr": summary.get("maxHeartRate"),
            "hrv_ms": hrv_ms,
        }

    def _garmin_sleep_stages_row(self, raw: dict, d: date) -> dict:
        """One night's sleepLevels segments, from the SAME payload
        _garmin_daily_row_from_raw consumes — so capturing stage data costs no
        extra Garmin calls.

        Segments are stored losslessly as JSON. The derived per-stage seconds
        alongside them exist purely so totals_match can compare them against
        dailySleepDTO's own totals: the activityLevel->stage mapping was
        confirmed on a single night, and this turns a future Garmin schema
        drift into a visible flag rather than a quietly wrong hypnogram.
        services/sleep_fusion.py refuses any night where it is false.

        Movement (sleepMovement) rides in this same payload, so capturing it
        costs no extra calls either — which matters against an unofficial API
        that rate-limits by IP. Unlike the stage segments it CANNOT be stored
        losslessly (~78-84k chars against a 50,000-char cell limit), so it is
        reduced to a gap-filled regular grid by
        services/sleep_movement.py::parse_garmin_movement. See
        _GARMIN_SLEEP_STAGES_HEADER for why gap-FILLING rather than
        gap-flagging is the load-bearing part."""
        sleep = raw.get("sleep") or {}
        dto = sleep.get("dailySleepDTO") or {}
        segments = sleep.get("sleepLevels") or []
        movement = sleep_movement.parse_garmin_movement(sleep.get("sleepMovement"))

        derived = {sleep_fusion.DEEP: 0.0, sleep_fusion.LIGHT: 0.0,
                   sleep_fusion.REM: 0.0, sleep_fusion.AWAKE: 0.0}
        for seg in segments:
            stage = sleep_fusion.GARMIN_LEVEL_TO_STAGE.get(_float_or_none(seg.get("activityLevel")))
            start = sleep_fusion.utc_from_gmt_string(seg.get("startGMT"))
            end = sleep_fusion.utc_from_gmt_string(seg.get("endGMT"))
            if stage is None or start is None or end is None:
                continue
            derived[stage] += abs((end - start).total_seconds())

        dto_totals = {
            sleep_fusion.DEEP: dto.get("deepSleepSeconds"),
            sleep_fusion.LIGHT: dto.get("lightSleepSeconds"),
            sleep_fusion.REM: dto.get("remSleepSeconds"),
            sleep_fusion.AWAKE: dto.get("awakeSleepSeconds"),
        }
        # 180s tolerance. Segment bounds are minute-rounded, so exact equality
        # flags healthy nights — the real 2026-07-28 payload lands 60s out on
        # light sleep alone. A genuinely wrong mapping (two stages swapped)
        # would be out by hundreds of minutes, so this stays a real check.
        totals_match = bool(segments) and all(
            v is not None and abs(derived[k] - float(v)) <= 180.0
            for k, v in dto_totals.items()
        )

        return {
            "date": str(d),
            "sleep_start_gmt": dto.get("sleepStartTimestampGMT", ""),
            "sleep_end_gmt": dto.get("sleepEndTimestampGMT", ""),
            "utc_offset_minutes": sleep_fusion.utc_offset_minutes(
                dto.get("sleepStartTimestampGMT"), dto.get("sleepStartTimestampLocal")),
            "segment_count": len(segments),
            "deep_seconds": int(derived[sleep_fusion.DEEP]),
            "light_seconds": int(derived[sleep_fusion.LIGHT]),
            "rem_seconds": int(derived[sleep_fusion.REM]),
            "awake_seconds": int(derived[sleep_fusion.AWAKE]),
            "dto_deep_seconds": dto_totals[sleep_fusion.DEEP],
            "dto_light_seconds": dto_totals[sleep_fusion.LIGHT],
            "dto_rem_seconds": dto_totals[sleep_fusion.REM],
            "dto_awake_seconds": dto_totals[sleep_fusion.AWAKE],
            "totals_match": totals_match,
            "sleep_levels_json": json.dumps(segments),
            "movement_start_gmt": (
                movement["start_utc"].isoformat() if movement["start_utc"] else ""),
            "movement_interval_seconds": movement["interval_seconds"],
            "movement_slot_count": len(movement["levels"]),
            "movement_contiguous": movement["contiguous"],
            "movement_gap_slots": movement["gap_slots"],
            "movement_levels": sleep_movement.encode_levels(movement["levels"]),
            "sleep_hr_json": _json_or_blank(sleep.get("sleepHeartRate")),
            "sleep_stress_json": _json_or_blank(sleep.get("sleepStress")),
        }

    def upsert_garmin_sleep_stages_row(self, row: dict) -> None:
        values = [row.get(k, "") if row.get(k) is not None else "" for k in _GARMIN_SLEEP_STAGES_HEADER]
        self._upsert_sheet_row(self._garmin_sleep_stages_ws(), str(row["date"]), values)

    def rebuild_tab(self, worksheet, header: list[str], fresh: dict[str, dict] | None = None,
                    key: str = "date", numericise_ignore: list | None = None) -> int:
        """Rewrite a whole date-keyed tab against the CURRENT header, merging
        `fresh` over whatever is already stored.

        The only way to WIDEN a tab, and the fix for a specific recurring bug:
        get_or_create_worksheet writes the header ONLY when it creates the tab,
        and upsert_row_by_key overwrites just the first len(row_values) columns
        of one row and never touches row 1. So adding a column to a _HEADER
        constant writes values into an unheadered column from then on, and
        gspread's get_all_records — which maps by header — silently drops them.

        That is not hypothetical. It had already happened to hrv_ms on the
        Garmin Daily tab: the column was added to _GARMIN_DAILY_HEADER, every
        sync since has written a value into column J, and every read has
        discarded it, so services/biometrics.py's documented Oura-70/Garmin-30
        HRV blend has silently been 100% Oura.

        Rows present and not in `fresh` are carried through, so the output is
        always a superset. Batched for the same reason sync_sleep_fusion is:
        per-row upserts cost two API calls each and walk into Sheets'
        60-writes-per-minute quota.
        """
        merged = {
            _sheet_key(r.get(key)): r
            for r in self._read_records(worksheet, numericise_ignore=numericise_ignore)
            if _sheet_key(r.get(key))
        }
        merged.update(fresh or {})
        rows = [
            ["" if merged[d].get(c) is None else merged[d].get(c, "") for c in header]
            for d in sorted(merged)
        ]
        self._rewrite_sheet(worksheet, header, rows)
        return len(rows)

    def rebuild_garmin_sleep_stages(self, fresh: dict[str, dict] | None = None) -> int:
        return self.rebuild_tab(
            self._garmin_sleep_stages_ws(), _GARMIN_SLEEP_STAGES_HEADER, fresh,
            numericise_ignore=_GARMIN_SLEEP_STAGES_NUMERICISE_IGNORE)

    def rebuild_garmin_daily(self, fresh: dict[str, dict] | None = None) -> int:
        """Re-header the Garmin Daily tab so hrv_ms stops being written into a
        column no read can see. Existing rows keep their values; the recovered
        column simply becomes readable for future syncs."""
        return self.rebuild_tab(self._garmin_daily_ws(), _GARMIN_DAILY_HEADER, fresh)

    def get_all_garmin_sleep_stages_rows(self) -> list[dict]:
        """Every row in the Garmin Sleep Stages tab, unmapped and undecoded
        (sleep_levels_json/movement_levels stay opaque TEXT, exactly as the
        tab holds them) — for services.datastore's garmin_sleep_stages
        table. Unlike get_garmin_sleep_stages above, this must NOT decode:
        the datastore is a faithful copy, and decoding here would bake a
        parsing choice into storage — the same reason the tab stores
        sleep_levels_json losslessly instead of a derived minute-string."""
        return self._read_records(
            self._garmin_sleep_stages_ws(),
            numericise_ignore=_GARMIN_SLEEP_STAGES_NUMERICISE_IGNORE)

    def get_all_sleep_fusion_rows(self) -> list[dict]:
        """Every row in the Sleep Fusion tab, unmapped — for
        services.datastore's sleep_fusion table. Goes through the same
        numericise_ignore as every other read of this tab, so the hypnogram
        and movement strings arrive as strings."""
        return self._read_records(
            self._sleep_fusion_ws(), numericise_ignore=_SLEEP_FUSION_NUMERICISE_IGNORE)

    def get_garmin_sleep_stages_dates(self) -> set[str]:
        """Dates the Garmin Sleep Stages tab already holds — lets the backfill
        script resume, mirroring get_garmin_daily_dates."""
        try:
            rows = self._read_records(
                self._garmin_sleep_stages_ws(),
                numericise_ignore=_GARMIN_SLEEP_STAGES_NUMERICISE_IGNORE)
        except Exception:
            return set()
        return {_sheet_key(r.get("date")) for r in rows if _sheet_key(r.get("date"))}

    def get_garmin_sleep_stages(self, start: str | None = None,
                                 end: str | None = None) -> dict[str, dict]:
        """{date: row} from the Garmin Sleep Stages tab, with `segments`
        decoded back out of JSON and `movement` decoded back into a gap-filled
        level grid. Read-only, no Garmin API calls."""
        try:
            rows = self._read_records(
                self._garmin_sleep_stages_ws(),
                numericise_ignore=_GARMIN_SLEEP_STAGES_NUMERICISE_IGNORE)
        except Exception:
            return {}
        out: dict[str, dict] = {}
        for r in rows:
            d = _sheet_key(r.get("date"))
            if not d or (start and d < start) or (end and d > end):
                continue
            row = dict(r)
            try:
                row["segments"] = json.loads(r.get("sleep_levels_json") or "[]")
            except (ValueError, TypeError):
                row["segments"] = []
            # Rebuilt into the same shape parse_garmin_movement returns, so a
            # caller cannot tell whether the night came from a live payload or
            # from storage — the round trip is the point of encode_levels.
            row["movement"] = {
                "start_utc": sleep_fusion.utc_from_gmt_string(r.get("movement_start_gmt")),
                "interval_seconds": int(
                    _float_or_none(r.get("movement_interval_seconds"))
                    or sleep_movement.GARMIN_INTERVAL_SECONDS),
                "levels": sleep_movement.decode_levels(r.get("movement_levels")),
                # Falsey spellings listed EXPLICITLY rather than testing
                # `!= "FALSE"`. That test treats every unrecognised value as
                # contiguous, so a stored 0 reads as "0", misses the compare
                # and INVERTS to clean — silently claiming a night needed no
                # gap-filling when it did. The two totals_match reads below
                # already guard the same way by naming their true spellings.
                "contiguous": str(r.get("movement_contiguous", "")).strip().lower()
                              not in ("false", "0"),
                "gap_slots": int(_float_or_none(r.get("movement_gap_slots")) or 0),
            }
            out[d] = row
        return out

    # ─────────────────────────────────────────────────────────────────────
    #  Sleep Fusion — merged Oura+Garmin hypnogram (services/sleep_fusion.py)
    #
    #  Reads ONLY the two already-synced Sheet tabs. No Garmin or Oura API
    #  calls, which means fusion is immune to the Garmin 429 problem and can
    #  be recomputed freely whenever sleep_fusion.RULES_VERSION changes.
    #  Display-only by design: nothing here feeds services/engine.py.
    # ─────────────────────────────────────────────────────────────────────

    def _oura_hypnograms_by_date(self, start: str, end: str) -> dict[str, dict]:
        """{day: main sleep period} for nights carrying a 30-second hypnogram.
        Uses the same biometrics.pick_main_sleep_period gate as
        _oura_sleep_metrics_by_date, so fusion describes exactly the period
        the rest of the engine already treats as the night."""
        rows = self._oura_tab_records("sleep_periods", self._oura_sleep_periods_ws())
        by_day: dict[str, list[dict]] = {}
        for r in rows:
            day = str(r.get("day") or "")
            if day and start <= day <= end:
                by_day.setdefault(day, []).append(r)
        out: dict[str, dict] = {}
        for day, entries in by_day.items():
            unique = biometrics.dedupe_sleep_periods(entries)
            main = biometrics.pick_main_sleep_period(unique)
            if main is None or not str(main.get("sleep_phase_30_sec") or "").strip():
                continue
            out[day] = {**main, "periods_on_day": len(unique)}
        return out

    def get_sleep_night_details(self, start: str, end: str) -> dict[str, dict]:
        """{day: night detail} for the Home page's Sleep drill-down — every
        field it displays that the ENGINE does not read.

        Deliberately separate from _oura_sleep_metrics_by_date rather than
        widening it: BiometricRecord is asdict()-ed into 60+ rows held in
        st.cache_data and walked by compute_readiness / traffic_light /
        sync_metrics_history, so carrying a 1,800-char hypnogram through that
        hot path to render one strip would be pure dead weight. This is read
        only when the drill-down is actually open.

        Uses the same biometrics.pick_main_sleep_period gate, so it describes
        exactly the period the engine already treats as the night."""
        rows = self._oura_tab_records("sleep_periods", self._oura_sleep_periods_ws())
        by_day: dict[str, list[dict]] = {}
        for r in rows:
            day = str(r.get("day") or "")
            if day and start <= day <= end:
                by_day.setdefault(day, []).append(r)

        out: dict[str, dict] = {}
        for day, entries in by_day.items():
            unique = biometrics.dedupe_sleep_periods(entries)
            main, naps = biometrics.split_sleep_periods(unique)
            if main is None:
                continue
            out[day] = {
                "period_type": main.get("type") or "",
                "period_index": _float_or_none(main.get("period")),
                "periods_on_day": len(unique),
                # Naps, so the drill-down can account for the difference
                # between the night the architecture describes and the day
                # total the engine scored. Sub-threshold periods are absent
                # by construction (biometrics.NAP_MIN_SECONDS) — showing a
                # 2-minute 3%-efficiency period as a "nap" the score ignored
                # would raise a question about a non-event.
                "naps": [
                    {
                        "type": n.get("type") or "",
                        "bedtime_start": n.get("bedtime_start") or "",
                        "bedtime_end": n.get("bedtime_end") or "",
                        "total_seconds": _float_or_none(n.get("total_sleep_duration")),
                        "efficiency": _float_or_none(n.get("efficiency")),
                    }
                    for n in naps
                ],
                "nap_seconds": biometrics.day_total_sleep_seconds(None, naps) or None,
                "day_total_seconds": biometrics.day_total_sleep_seconds(main, naps) or None,
                "bedtime_start": main.get("bedtime_start") or "",
                "bedtime_end": main.get("bedtime_end") or "",
                "total_seconds": _float_or_none(main.get("total_sleep_duration")),
                "time_in_bed_seconds": _float_or_none(main.get("time_in_bed")),
                "awake_seconds": _float_or_none(main.get("awake_time")),
                "deep_seconds": _float_or_none(main.get("deep_sleep_duration")),
                "light_seconds": _float_or_none(main.get("light_sleep_duration")),
                "rem_seconds": _float_or_none(main.get("rem_sleep_duration")),
                "efficiency": _float_or_none(main.get("efficiency")),
                "latency_seconds": _float_or_none(main.get("latency")),
                "restless_periods": _float_or_none(main.get("restless_periods")),
                "average_heart_rate": _float_or_none(main.get("average_heart_rate")),
                "lowest_heart_rate": _float_or_none(main.get("lowest_heart_rate")),
                "average_hrv": _float_or_none(main.get("average_hrv")),
                "average_breath": _float_or_none(main.get("average_breath")),
                "oura_readiness_score": _float_or_none(main.get("readiness_score")),
                "temperature_deviation": _float_or_none(main.get("readiness_temperature_deviation")),
                "hypnogram_30sec": str(main.get("sleep_phase_30_sec") or ""),
                # Overnight series, captured with the movement columns. Oura
                # ships these as {"interval": 300.0, "items": [...],
                # "timestamp": ...} — ~109 samples and ~730 chars, so they
                # ride along in the same read rather than costing another.
                "hr_series": _json_or(main.get("sleep_hr_series"), {}),
                "hrv_series": _json_or(main.get("sleep_hrv_series"), {}),
                "movement_30sec": str(main.get("movement_30_sec") or ""),
            }
        return out

    def get_oura_daily_sleep_context(self, start: str, end: str) -> dict[str, dict]:
        """The sleep-adjacent Oura Daily columns the engine never reads —
        blood-oxygen and breathing. Stored since the schema widened; nothing
        has surfaced them until now."""
        try:
            rows = self._read_records(self._oura_daily_ws())
        except Exception:
            return {}
        out: dict[str, dict] = {}
        for r in rows:
            d = _sheet_key(r.get("date"))
            if not d or not (start <= d <= end):
                continue
            out[d] = {
                "spo2_average": _float_or_none(r.get("spo2_average")),
                "breathing_disturbance_index": _float_or_none(
                    r.get("spo2_breathing_disturbance_index")),
                "optimal_bedtime": r.get("sleep_time_optimal_bedtime") or "",
            }
        return out

    def _match_garmin_night(self, day: str, window_start, window_end,
                            garmin_by_date: dict[str, dict]) -> tuple[dict | None, float]:
        """Which Garmin night IS this Oura night, and how well do they overlap.

        Oura keys a night by its wake date, Garmin by its own — never assume
        they agree. Searches the neighbouring days and takes the best genuine
        overlap; a silent one-day mismatch would produce a completely wrong
        but entirely plausible-looking hypnogram, the worst failure available
        here.

        Extracted so the movement calibration pairs nights by exactly the same
        rule the hypnogram fusion does. Two copies of this logic that drifted
        apart would calibrate the movement mapping against different nights
        than it is then applied to, which is the one way quantile mapping
        silently produces a biased result.
        """
        best, best_overlap = None, 0.0
        if window_start is None:
            return best, best_overlap
        for offset in (-1, 0, 1):
            candidate = garmin_by_date.get(str(date.fromisoformat(day) + timedelta(days=offset)))
            if not candidate or not candidate.get("segments"):
                continue
            if str(candidate.get("totals_match")).strip().lower() not in ("true", "1"):
                # Our activityLevel->stage mapping didn't reproduce Garmin's
                # own totals for this night — refuse rather than fuse against
                # a mapping we can't verify.
                continue
            segs = candidate["segments"]
            starts = [s for s in (sleep_fusion.utc_from_gmt_string(x.get("startGMT")) for x in segs) if s]
            ends = [e for e in (sleep_fusion.utc_from_gmt_string(x.get("endGMT")) for x in segs) if e]
            if not starts or not ends:
                continue
            frac = sleep_fusion.window_overlap_fraction(
                window_start, window_end, min(starts), max(ends))
            if frac > best_overlap:
                best, best_overlap = candidate, frac
        return best, best_overlap

    def sleep_movement_cutpoints(self, oura_by_date: dict[str, dict],
                                 garmin_by_date: dict[str, dict]
                                 ) -> tuple[float, float, float] | None:
        """Fit Garmin's movement scale onto Oura's published 1-4 alphabet.

        Oura reports an ordinal class, Garmin an undocumented float — see
        services/sleep_movement.py's docstring for why quantile mapping onto
        Oura is the only defensible direction. Fitted ONCE over the whole
        paired history and passed down to every night, never per night: a
        per-night fit would make a calm night's "restless" mean something
        different from a rough night's, and the classes would stop being
        comparable across the very series the UI plots.

        Returns None when there is too little paired history
        (sleep_movement.MIN_CALIBRATION_NIGHTS), so callers fall back to
        Oura-only movement rather than to an invented scale.
        """
        garmin_values: list[float] = []
        oura_classes: list[int] = []
        nights = 0
        for day, main in oura_by_date.items():
            classes = sleep_movement.oura_movement(main.get("movement_30_sec"))
            if not classes:
                continue
            window_start = sleep_fusion.utc_from_iso_offset(main.get("bedtime_start"))
            if window_start is None:
                continue
            window_end = window_start + timedelta(seconds=len(classes) * sleep_movement.SLOT_SECONDS)
            best, overlap = self._match_garmin_night(
                day, window_start, window_end, garmin_by_date)
            if best is None or overlap < sleep_fusion.MIN_WINDOW_OVERLAP_FRACTION:
                continue
            parsed = best.get("movement") or {}
            if not parsed.get("levels"):
                continue
            # Aligned to the SAME window and grid fusion will use — not the
            # raw level array. Garmin's movement series is ~2.7x wider than
            # the Oura sleep period, so calibrating on the raw array matches
            # Oura's sleep-period classes against Garmin's whole evening and
            # pushes every boundary too high. See
            # sleep_movement.garmin_values_on_grid for the measured effect.
            aligned, _diag = sleep_movement.garmin_values_on_grid(
                parsed, window_start, len(classes))
            paired = [(v, c) for v, c in zip(aligned, classes) if v is not None]
            if not paired:
                continue
            nights += 1
            garmin_values.extend(v for v, _ in paired)
            oura_classes.extend(c for _, c in paired)
        return sleep_movement.quantile_cutpoints(garmin_values, oura_classes, nights=nights)

    def compute_sleep_fusion_for_date(self, day: str, oura_by_date: dict[str, dict],
                                       garmin_by_date: dict[str, dict],
                                       movement_cutpoints: tuple[float, float, float] | None = None,
                                       ) -> dict | None:
        """One night's fused hypnogram, or None when neither device has one.
        Pure lookup + services/sleep_fusion.py math — no I/O."""
        main = oura_by_date.get(day)
        oura_min = sleep_fusion.oura_minutes(main.get("sleep_phase_30_sec")) if main else []

        if not oura_min:
            # No ring reading. Fall back to the watch alone rather than
            # returning nothing: the two devices are not worn equally, and
            # over the Garmin era 27 of 71 nights had watch stage data and no
            # ring reading at all. Anchored on Garmin's OWN window, since
            # there is no bedtime_start to anchor on.
            return self._garmin_only_night(day, garmin_by_date, movement_cutpoints)

        window_start = sleep_fusion.utc_from_iso_offset(main.get("bedtime_start"))
        window_end = (window_start + timedelta(minutes=len(oura_min))) if window_start else None

        best, best_overlap = self._match_garmin_night(
            day, window_start, window_end, garmin_by_date)
        best_diag: dict = {}

        garmin_min = None
        if best is not None and best_overlap >= sleep_fusion.MIN_WINDOW_OVERLAP_FRACTION:
            garmin_min, best_diag = sleep_fusion.garmin_minutes(
                best["segments"], window_start, len(oura_min))

        # Movement is fused FIRST: RULES_VERSION 2's staging rules read it, so
        # the motion series has to exist before the hypnogram is decided.
        movement_cols, fused_slots = self._fuse_movement_for_night(
            main, best, best_overlap, window_start, len(oura_min), movement_cutpoints)

        summary = sleep_fusion.night_summary(
            day=day, window_start=window_start, oura=oura_min, garmin=garmin_min,
            offset_minutes=_float_or_none(best.get("utc_offset_minutes")) if best else None,
            oura_periods_on_day=main.get("periods_on_day", 1),
            garmin_diagnostics=best_diag,
            overlap_fraction=best_overlap if garmin_min else 0.0,
            # Reduced 30s -> 60s by max, onto the hypnogram's own grid.
            movement=sleep_movement.to_minutes(fused_slots) if fused_slots else None,
        )
        return {**summary, **movement_cols}

    def _matched_garmin_date(self, day: str, main: dict,
                             garmin_by_date: dict[str, dict]) -> str | None:
        """Which Garmin date a paired night consumed — Oura keys a night by
        its wake date and Garmin by its own, so the two are often a day apart.

        Recomputes the window rather than threading the answer back out of
        compute_sleep_fusion_for_date, whose return value maps 1:1 onto the
        Sheet header and must not grow a key that is not a column. Costs
        nothing: it is pure lookup over dicts already in memory, for the ~26
        fused nights only."""
        oura_min = sleep_fusion.oura_minutes(main.get("sleep_phase_30_sec"))
        window_start = sleep_fusion.utc_from_iso_offset(main.get("bedtime_start"))
        if not oura_min or window_start is None:
            return None
        best, _overlap = self._match_garmin_night(
            day, window_start, window_start + timedelta(minutes=len(oura_min)), garmin_by_date)
        return _sheet_key(best.get("date")) if best else None

    def _garmin_only_night(self, day: str, garmin_by_date: dict[str, dict],
                           movement_cutpoints: tuple[float, float, float] | None,
                           ) -> dict | None:
        """A night the watch recorded and the ring did not.

        Anchored on Garmin's own sleepStartTimestampGMT rather than a
        bedtime_start that does not exist. Keyed by Garmin's own date, which
        is safe from double-counting because sync_sleep_fusion only asks for
        this on days no Oura night claimed — see its `claimed` set.

        Deliberately still goes through sleep_fusion.night_summary with an
        empty Oura array rather than hand-building a row: the totals, the
        encoding and the persisted shape then come from exactly one place, and
        `source` comes out as SOURCE_GARMIN_ONLY by the same rule that decides
        it everywhere else.
        """
        night = garmin_by_date.get(day)
        if not night or not night.get("segments"):
            return None
        if str(night.get("totals_match")).strip().lower() not in ("true", "1"):
            # Same refusal as the paired path: an unverifiable activityLevel
            # -> stage mapping must not become a plausible-looking hypnogram.
            return None

        starts = [s for s in (sleep_fusion.utc_from_gmt_string(x.get("startGMT"))
                              for x in night["segments"]) if s]
        ends = [e for e in (sleep_fusion.utc_from_gmt_string(x.get("endGMT"))
                            for x in night["segments"]) if e]
        if not starts or not ends:
            return None
        window_start = min(starts)
        minutes = max(1, int(round((max(ends) - window_start).total_seconds() / 60)))
        garmin_min, diag = sleep_fusion.garmin_minutes(night["segments"], window_start, minutes)
        if not any(m != sleep_fusion.UNCOVERED for m in garmin_min):
            return None

        movement_cols, _slots = self._fuse_movement_for_night(
            {}, night, 1.0, window_start, minutes, movement_cutpoints)
        summary = sleep_fusion.night_summary(
            day=day, window_start=window_start, oura=[], garmin=garmin_min,
            offset_minutes=_float_or_none(night.get("utc_offset_minutes")),
            oura_periods_on_day=0, garmin_diagnostics=diag, overlap_fraction=0.0,
        )
        return {**summary, **movement_cols}

    def _fuse_movement_for_night(self, main: dict, garmin_night: dict | None,
                                 overlap: float, window_start, stage_minutes: int,
                                 cutpoints: tuple[float, float, float] | None,
                                 ) -> tuple[dict, list[int]]:
        """The movement half of one night, on the SAME window_start as the
        hypnogram so the two strips share a time axis and can never disagree
        on screen about when the night began.

        Runs on the 30-second grid — the finer of the two devices' — because
        downsampling Oura to Garmin's minute would discard real resolution to
        accommodate the coarser sensor. Oura's own movement string sets the
        slot count where it exists; only when it doesn't do we fall back to
        the stage grid's own span.

        Returns (columns, fused_slots). The slots come back separately because
        the staging rules consume them at minute resolution while the stored
        column keeps the full 30-second series — reducing once, at the point
        of use, rather than storing the reduced form and losing the detail the
        tick strip draws.
        """
        oura_slots = sleep_movement.oura_movement(main.get("movement_30_sec"))
        slot_count = len(oura_slots) or stage_minutes * 2

        garmin_slots: list[int] | None = None
        if (garmin_night is not None
                and overlap >= sleep_fusion.MIN_WINDOW_OVERLAP_FRACTION
                and cutpoints is not None):
            parsed = garmin_night.get("movement") or {}
            if parsed.get("levels"):
                garmin_slots, _diag = sleep_movement.garmin_slots(
                    parsed, cutpoints, window_start, slot_count)

        fused, source = sleep_movement.fuse_movement(oura_slots, garmin_slots)
        return {
            **sleep_movement.movement_summary(fused, source),
            "master_movement": sleep_fusion.encode(fused),
            "oura_movement": sleep_fusion.encode(oura_slots),
            "garmin_movement": sleep_fusion.encode(garmin_slots or []),
            # Persisted per night so a stored series always says which
            # calibration produced it — the movement counterpart of
            # rules_version, and the thing that makes a re-fit auditable
            # rather than a silent change of meaning.
            "movement_cutpoints": (
                ",".join(f"{c:.3f}" for c in cutpoints) if cutpoints else ""),
        }, fused

    def save_sleep_fusion(self, summary: dict) -> None:
        row = {**summary, "computed_at": datetime.now().isoformat(timespec="seconds")}
        values = [row.get(k, "") if row.get(k) is not None else "" for k in _SLEEP_FUSION_HEADER]
        self._upsert_sheet_row(self._sleep_fusion_ws(), str(row["date"]), values)

    def sync_sleep_fusion(self, days: int = 7, today: date | None = None) -> dict:
        """Recompute and persist fused hypnograms for the last `days` days.

        Writes as ONE batched rewrite rather than a row-per-night upsert: a
        full-history rebuild is ~400 nights, and upserting costs two API calls
        each, which would blow straight through Sheets' 60-writes-per-minute
        quota. Batched, sync_sleep_fusion(days=1000) is a handful of calls and
        is the intended way to re-derive everything after a
        sleep_fusion.RULES_VERSION bump.

        Nights outside the window keep their existing rows — the output is
        always a superset of what was there. Reads only Sheets, never a device
        API. Returns {source: count} for the nights recomputed."""
        today = today or date.today()
        start = (today - timedelta(days=days - 1)).isoformat()
        end = today.isoformat()
        oura_by_date = self._oura_hypnograms_by_date(start, end)
        garmin_by_date = self.get_garmin_sleep_stages()

        # Fitted over the WHOLE paired history, not just this sync's window,
        # and over the same nights the mapping is then applied to. A window
        # narrower than the history would refit the scale on every sync and
        # make yesterday's "restless" incomparable with last month's.
        cutpoints = self.sleep_movement_cutpoints(
            self._oura_hypnograms_by_date("0000-01-01", end), garmin_by_date)

        fresh: dict[str, dict] = {}
        counts: dict[str, int] = {}
        stamp = datetime.now().isoformat(timespec="seconds")

        # Ring nights first. Each one may consume a Garmin night keyed up to a
        # day either side, which is then off-limits to the watch-only pass —
        # otherwise a paired night would be emitted twice, once under Oura's
        # wake date and once under Garmin's own, and the same sleep would be
        # counted as two nights.
        claimed: set[str] = set()
        for day in sorted(oura_by_date):
            summary = self.compute_sleep_fusion_for_date(
                day, oura_by_date, garmin_by_date, movement_cutpoints=cutpoints)
            if summary is None:
                continue
            fresh[day] = {**summary, "computed_at": stamp}
            counts[summary["source"]] = counts.get(summary["source"], 0) + 1
            if summary["source"] == sleep_fusion.SOURCE_FUSED:
                matched = self._matched_garmin_date(day, oura_by_date[day], garmin_by_date)
                if matched:
                    claimed.add(matched)
            claimed.add(day)

        # Then nights only the watch recorded. Strictly additive: every day
        # here had no usable ring hypnogram, so nothing above is overwritten.
        for day in sorted(garmin_by_date):
            if day in claimed or day in fresh or not (start <= day <= end):
                continue
            summary = self._garmin_only_night(day, garmin_by_date, cutpoints)
            if summary is None:
                continue
            fresh[day] = {**summary, "computed_at": stamp}
            counts[summary["source"]] = counts.get(summary["source"], 0) + 1

        ws = self._sleep_fusion_ws()
        merged = {
            _sheet_key(r.get("date")): r
            for r in self.get_sleep_fusion_history()
            if _sheet_key(r.get("date"))
        }
        merged.update(fresh)
        rows = [
            ["" if merged[d].get(c) is None else merged[d].get(c, "") for c in _SLEEP_FUSION_HEADER]
            for d in sorted(merged)
        ]
        self._rewrite_sheet(ws, _SLEEP_FUSION_HEADER, rows)
        return counts

    def sync_sleep_fusion_if_due(self, days: int = 14, today: date | None = None,
                                  hours: float = 2, now: datetime | None = None
                                  ) -> tuple[bool, str | None]:
        """sync_sleep_fusion() at most every `hours` hours, with a durable
        marker.

        Cheaper than the others — it reads already-synced tabs and makes no
        Oura or Garmin API calls — but it is not free: it re-derives up to
        `days` nights and rewrites the whole Sleep Fusion tab every time. A
        fused night does not change once both devices' rows are in, so
        repeating that on every process start is pure cost against the same
        Sheets quota."""
        return self.run_sync_if_due(
            "sleep_fusion", lambda: self.sync_sleep_fusion(days=days, today=today),
            hours=hours, now=now,
        )

    def get_sleep_fusion_history(self, start: str | None = None,
                                  end: str | None = None) -> list[dict]:
        """Persisted fused nights, oldest first. Reads with the hypnogram
        columns exempted from numericising — mandatory, see
        _SLEEP_FUSION_NUMERICISE_IGNORE.

        RAISES on a read failure rather than returning []. It used to swallow
        the exception, and that produced two bad outcomes that were extremely
        hard to trace:

          - app.py wraps this in @st.cache_data(ttl=1800). A transient Sheets
            error returned [], which cached as "this night has no fusion" for
            THIRTY MINUTES — the drill-down then labelled a genuinely fused
            night "Stage timeline from Oura" long after the error had passed,
            with nothing anywhere reporting a failure. An exception is not
            cached, so the next render simply retries.
          - sync_sleep_fusion merges THIS result with freshly computed nights
            before a full-tab rewrite. An empty read there would have silently
            dropped every night outside the sync window from the tab.

        Callers that genuinely want "no data on failure" must say so
        themselves; the distinction between empty and broken is not this
        method's to erase.
        """
        rows = self._read_records(
            self._sleep_fusion_ws(), numericise_ignore=_SLEEP_FUSION_NUMERICISE_IGNORE)
        out = []
        for r in rows:
            d = _sheet_key(r.get("date"))
            if not d or (start and d < start) or (end and d > end):
                continue
            out.append({**r, "date": d})
        return sorted(out, key=lambda r: r["date"])

    def get_fused_wake_adjustments(self, start: str | None = None,
                                    end: str | None = None) -> dict[str, float]:
        """{date: minutes} of Oura wake the fusion reclassified as sleep —
        already in the manual wake_time_adjustments unit, which is what lets
        sleep_fusion.effective_wake_adjustments treat them as interchangeable.
        Only genuinely fused nights contribute; an oura_only night has nothing
        to say and must not override a manual correction."""
        out: dict[str, float] = {}
        for r in self.get_sleep_fusion_history(start, end):
            if str(r.get("source")) != sleep_fusion.SOURCE_FUSED:
                continue
            minutes = _float_or_none(r.get("phantom_wake_minutes"))
            if minutes:
                out[r["date"]] = minutes
        return out

    def _garmin_daily_complete_dates(self) -> set[str]:
        """Past dates already fully captured in BOTH Garmin tabs. A completed
        past day never changes, so re-fetching it is 4 wasted API calls
        against an endpoint that rate-limits by IP."""
        stages = self.get_garmin_sleep_stages_dates()
        try:
            rows = self._read_records(self._garmin_daily_ws())
        except Exception:
            return set()
        daily = {
            _sheet_key(r.get("date")) for r in rows
            if _sheet_key(r.get("date")) and str(r.get("sleep_hours", "")).strip() != ""
        }
        return daily & stages

    def sync_garmin_daily(self, days: int = 7, today: date | None = None,
                          force: bool = False) -> int:
        """Pull the last `days` days of Garmin daily wellness metrics and
        upsert each into the Garmin Daily sheet tab, keyed by date. Also
        captures that day's sleep-stage segments from the same payload, at no
        extra API cost. Returns the number of days actually fetched.

        Skips past days already complete in both tabs (`force` overrides).
        Before this, a days=7 sync spent 28 API calls every 2 hours almost
        entirely on re-fetching immutable history — the likeliest cause of the
        429 IP rate-limits this account has been hitting.

        Raises RuntimeError if Garmin isn't configured, or whatever
        garminconnect raises on a real login/API failure — the caller
        (views/sync.py) surfaces that as an error."""
        client = self._gc
        if client is None:
            raise RuntimeError(
                "Garmin is not configured — add GARMIN_EMAIL/GARMIN_PASSWORD "
                "to .streamlit/secrets.toml."
            )
        today = today or date.today()
        complete = set() if force else self._garmin_daily_complete_dates()
        ws = self._garmin_daily_ws()
        fetched = 0
        for delta in range(days):
            d = today - timedelta(days=delta)
            # Today and yesterday are still mutable — Garmin backfills sleep
            # and stress well after midnight — so they always re-sync.
            if delta > 1 and str(d) in complete:
                continue
            raw = self._garmin_raw_day(client, d)
            row = self._garmin_daily_row_from_raw(raw, d)
            values = [row.get(k, "") for k in _GARMIN_DAILY_HEADER]
            self._upsert_sheet_row(ws, str(d), values)
            self.upsert_garmin_sleep_stages_row(self._garmin_sleep_stages_row(raw, d))
            fetched += 1
        return fetched

    def sync_garmin_daily_if_due(self, days: int = 7, today: date | None = None,
                                  hours: int = 2, now: datetime | None = None) -> tuple[bool, str | None]:
        """Runs sync_garmin_daily() at most every `hours` hours (default 2,
        matching Oura's own oura_sync_due cadence) — but stops re-syncing for
        the rest of the day the moment a Morning Check-In has been submitted
        for `today` (has_checked_in), since that check-in already anchors
        the day's readiness and further polling until tomorrow is
        unnecessary. The 2-hour marker is persisted via the Config DB
        (garmin_daily_last_synced_at, a full timestamp — was date-only under
        the old once/day key garmin_daily_last_synced_date, now retired) so
        it survives across Streamlit reruns/sessions/restarts. Triggered on
        both Home (app.py) and Training page open, since Garmin feeds the
        engine's biometric blend (services/biometrics.py) and needs
        current-day data available on open. Still throttled at all (not
        every page load) because Garmin's API is unofficial and
        rate-limit-sensitive. (True, None) if not configured, a check-in is
        already in for today, or the last sync was under `hours` hours ago
        (all "nothing to do", not an error) or on sync success; (False, msg)
        only on an actual sync failure. Matches
        services.metrics.sync_weekly_rollup's (ok, error) contract so callers
        can treat both the same way."""
        if not self.garmin_configured():
            return True, None
        today = today or date.today()
        now = now or datetime.now()
        try:
            if self.has_checked_in(today):
                return True, None
            if self.garmin_rate_limited(now=now):
                # Circuit breaker open. Retrying a throttled endpoint on every
                # page load is exactly how a transient 429 becomes a
                # persistent one, so this is "nothing to do", not an error.
                return True, None
            raw = self.get_config_value("garmin_daily_last_synced_at")
            if raw:
                try:
                    last_synced = datetime.fromisoformat(raw)
                except ValueError:
                    last_synced = None
                if last_synced is not None and now - last_synced < timedelta(hours=hours):
                    return True, None
            self.sync_garmin_daily(days=days, today=today)
            self.set_config("garmin_daily_last_synced_at", now.isoformat(), today=today)
            return True, None
        except garmin.RateLimited as exc:
            self.open_garmin_rate_limit_breaker(now=now, today=today)
            return True, f"Garmin rate-limited — backing off until {self.get_config_value('garmin_rate_limited_until')}. ({exc})"
        except Exception as exc:
            return False, str(exc)

    # ─── Garmin 429 circuit breaker ──────────────────────────────────────
    #  Garmin's API is unofficial and throttles by IP. Without a breaker every
    #  page open retries a throttled endpoint, which sustains the limit
    #  indefinitely — the failure mode observed 2026-07-31.

    GARMIN_RATE_LIMIT_BACKOFF_HOURS = 6

    def garmin_rate_limited(self, now: datetime | None = None) -> bool:
        raw = self.get_config_value("garmin_rate_limited_until")
        if not raw:
            return False
        try:
            until = datetime.fromisoformat(raw)
        except ValueError:
            return False
        return (now or datetime.now()) < until

    def open_garmin_rate_limit_breaker(self, now: datetime | None = None,
                                        today: date | None = None) -> str:
        until = (now or datetime.now()) + timedelta(hours=self.GARMIN_RATE_LIMIT_BACKOFF_HOURS)
        self.set_config("garmin_rate_limited_until", until.isoformat(), today=today)
        return until.isoformat()

    def _garmin_activity_row(self, act: dict) -> dict:
        activity_type = (act.get("activityType") or {}).get("typeKey", "")
        start_local = act.get("startTimeLocal", "")
        duration_s = act.get("duration") or 0
        distance_m = act.get("distance") or 0
        return {
            "activity_id": str(act.get("activityId", "")),
            "date": start_local[:10] if start_local else "",
            "name": act.get("activityName", ""),
            "type": activity_type,
            "start_time_local": start_local,
            "duration_minutes": round(duration_s / 60, 1),
            "distance_km": round(distance_m / 1000, 2),
            "avg_hr": act.get("averageHR", ""),
            "max_hr": act.get("maxHR", ""),
            "calories": act.get("calories", ""),
        }

    def sync_garmin_activities(self, limit: int = 20) -> int:
        """Pull the most recent `limit` Garmin activities and upsert each
        into the Garmin Activities sheet tab, keyed by activity_id (so
        re-running the sync never duplicates a row)."""
        client = self._gc
        if client is None:
            raise RuntimeError(
                "Garmin is not configured — add GARMIN_EMAIL/GARMIN_PASSWORD "
                "to .streamlit/secrets.toml."
            )
        ws = self._garmin_activities_ws()
        activities = garmin.get_recent_activities(client, limit=limit)
        for act in activities:
            row = self._garmin_activity_row(act)
            values = [row.get(k, "") for k in _GARMIN_ACTIVITY_HEADER]
            self._upsert_sheet_row(ws, row["activity_id"], values)
        return len(activities)

    def get_recent_garmin_activity_minutes(
        self, target_minutes: float, buffer_minutes: float, now: datetime | None = None,
    ) -> tuple[float, list[dict]]:
        """Finds the most recent (of the last 10 logged) Garmin activity that
        started today AND whose OWN duration falls within [target_minutes -
        buffer_minutes, target_minutes + buffer_minutes] — e.g. a 15-min
        planned walk with a 5-min buffer matches any of today's activities
        lasting 10-20 minutes. This is the "just finished, pull it in" hook
        used by the training page's run/walk Complete button.

        Matching on the activity's OWN duration rather than on how recently
        it started relative to `now` is deliberate: the previous "started
        within the last N minutes" check was fragile against any delay
        between finishing the walk and actually opening the app to tap
        Complete — a late tap could miss a real match entirely.

        Returns (0.0, []) if Garmin isn't configured or nothing in the last
        10 activities matches, rather than raising — callers treat that the
        same as "no matching activity found"."""
        client = self._gc
        if client is None:
            return 0.0, []
        today = (now or datetime.now()).date()
        lo, hi = max(0.0, target_minutes - buffer_minutes), target_minutes + buffer_minutes
        for act in garmin.get_recent_activities(client, limit=10):
            start_local = act.get("startTimeLocal", "")
            try:
                start_dt = datetime.strptime(start_local, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                continue
            if start_dt.date() != today:
                continue
            duration_min = (act.get("duration") or 0) / 60
            if lo <= duration_min <= hi:
                return round(duration_min, 1), [act]
        return 0.0, []

    def get_all_garmin_daily_rows(self) -> list[dict]:
        """Every row in the Garmin Daily tab, unmapped (gspread's own
        dict-per-row parsing) — for services.datastore's garmin_daily table."""
        return self._read_records(self._garmin_daily_ws())

    def get_all_garmin_activities_rows(self) -> list[dict]:
        """Every row in the Garmin Activities tab, unmapped — for
        services.datastore's garmin_activities table."""
        return self._read_records(self._garmin_activities_ws())

    # ─────────────────────────────────────────────────────────────────────
    #  Oura — daily summary scores + workouts/sleep periods/sessions/rest
    #  mode. Daily steps + sleep-period HRV/RHR/sleep-duration feed
    #  services/engine.py's readiness/ACWR pipeline (70% weight for HRV/RHR/
    #  sleep, 20% for steps — blended with Garmin, see
    #  get_biometric_rolling/services/biometrics.py); workouts/sessions/rest
    #  mode remain archival only. Raw high-volume time-series (heartrate, and
    #  the per-day series embedded in daily_activity/sleep like met.items/
    #  class_5_min/heart_rate.items) are deliberately NOT pulled — by request,
    #  to avoid 100k+ row/year Sheet growth. Only the scalar/summary fields
    #  are captured.
    # ─────────────────────────────────────────────────────────────────────

    def oura_configured(self) -> bool:
        """True when Oura sync has SOMETHING to authenticate with — a stored
        OAuth credential, or the legacy PAT.

        Deliberately not "is the credential valid": a stale OAuth token is
        configured and refreshable, and reporting it as unconfigured would
        route the athlete to "add OURA_TOKEN to secrets.toml", which is now
        the wrong repair and no longer even possible. oura_auth_status is
        what answers health.
        """
        return bool(self.config.oura_token) or self._load_oura_token() is not None

    def _oura_daily_ws(self):
        return self._ws(sheets.OURA_DAILY_WORKSHEET, _OURA_DAILY_HEADER)

    def _oura_workouts_ws(self):
        return self._ws(sheets.OURA_WORKOUTS_WORKSHEET, _OURA_WORKOUT_HEADER)

    def _oura_sleep_periods_ws(self):
        return self._ws(sheets.OURA_SLEEP_PERIODS_WORKSHEET, _OURA_SLEEP_PERIOD_HEADER)

    def _oura_sessions_ws(self):
        return self._ws(sheets.OURA_SESSIONS_WORKSHEET, _OURA_SESSION_HEADER)

    def _oura_rest_mode_ws(self):
        return self._ws(sheets.OURA_REST_MODE_WORKSHEET, _OURA_REST_MODE_HEADER)

    def _oura_daily_row(self, date_str: str, group: dict) -> dict:
        """group: {endpoint_name: entry_dict} for ONE date — see
        _OURA_DAILY_ENDPOINTS for the 9 possible keys. Every lookup is
        defensive: a date missing one of the 9 endpoints (e.g. daily_
        resilience needs weeks of history before it starts returning data)
        just leaves those columns blank rather than breaking the row."""
        sleep = group.get("daily_sleep") or {}
        sleep_c = sleep.get("contributors") or {}
        readiness = group.get("daily_readiness") or {}
        readiness_c = readiness.get("contributors") or {}
        activity = group.get("daily_activity") or {}
        activity_c = activity.get("contributors") or {}
        stress = group.get("daily_stress") or {}
        resilience = group.get("daily_resilience") or {}
        resilience_c = resilience.get("contributors") or {}
        spo2 = group.get("daily_spo2") or {}
        cardio = group.get("daily_cardiovascular_age") or {}
        sleep_time = group.get("sleep_time") or {}
        vo2 = group.get("vo2_max") or {}

        return {
            "date": date_str,
            "sleep_score": sleep.get("score"),
            "sleep_total_sleep": sleep_c.get("total_sleep"),
            "sleep_efficiency": sleep_c.get("efficiency"),
            "sleep_restfulness": sleep_c.get("restfulness"),
            "sleep_rem_sleep": sleep_c.get("rem_sleep"),
            "sleep_deep_sleep": sleep_c.get("deep_sleep"),
            "sleep_latency": sleep_c.get("latency"),
            "sleep_timing": sleep_c.get("timing"),
            "readiness_score": readiness.get("score"),
            "readiness_resting_heart_rate": readiness_c.get("resting_heart_rate"),
            "readiness_hrv_balance": readiness_c.get("hrv_balance"),
            "readiness_body_temperature": readiness_c.get("body_temperature"),
            "readiness_recovery_index": readiness_c.get("recovery_index"),
            "readiness_sleep_balance": readiness_c.get("sleep_balance"),
            "readiness_activity_balance": readiness_c.get("activity_balance"),
            "readiness_previous_day_activity": readiness_c.get("previous_day_activity"),
            "readiness_previous_night": readiness_c.get("previous_night"),
            "readiness_sleep_regularity": readiness_c.get("sleep_regularity"),
            "readiness_temperature_deviation": readiness.get("temperature_deviation"),
            "readiness_temperature_trend_deviation": readiness.get("temperature_trend_deviation"),
            "activity_score": activity.get("score"),
            "steps": activity.get("steps"),
            "activity_high_time": activity.get("high_activity_time"),
            "activity_medium_time": activity.get("medium_activity_time"),
            "activity_low_time": activity.get("low_activity_time"),
            "activity_sedentary_time": activity.get("sedentary_time"),
            "activity_met_minutes": activity.get("average_met_minutes"),
            "activity_high_met_minutes": activity.get("high_activity_met_minutes"),
            "activity_medium_met_minutes": activity.get("medium_activity_met_minutes"),
            "activity_low_met_minutes": activity.get("low_activity_met_minutes"),
            "activity_sedentary_met_minutes": activity.get("sedentary_met_minutes"),
            "activity_non_wear_time": activity.get("non_wear_time"),
            "activity_inactivity_alerts": activity.get("inactivity_alerts"),
            "activity_equivalent_walking_distance": activity.get("equivalent_walking_distance"),
            "activity_meters_to_target": activity.get("meters_to_target"),
            "activity_target_meters": activity.get("target_meters"),
            "activity_meet_daily_targets": activity_c.get("meet_daily_targets"),
            "activity_move_every_hour": activity_c.get("move_every_hour"),
            "activity_recovery_time": activity_c.get("recovery_time"),
            "activity_stay_active": activity_c.get("stay_active"),
            "activity_training_frequency": activity_c.get("training_frequency"),
            "activity_training_volume": activity_c.get("training_volume"),
            "total_calories": activity.get("total_calories"),
            "active_calories": activity.get("active_calories"),
            "target_calories": activity.get("target_calories"),
            "resting_time": activity.get("resting_time"),
            "stress_high_duration": stress.get("stress_high"),
            "stress_recovery_duration": stress.get("recovery_high"),
            "stress_day_summary": stress.get("day_summary"),
            "resilience_level": resilience.get("level"),
            "resilience_sleep_recovery": resilience_c.get("sleep_recovery"),
            "resilience_daytime_recovery": resilience_c.get("daytime_recovery"),
            "resilience_stress": resilience_c.get("stress"),
            "spo2_average": (spo2.get("spo2_percentage") or {}).get("average"),
            "spo2_breathing_disturbance_index": spo2.get("breathing_disturbance_index"),
            "vascular_age": cardio.get("vascular_age"),
            "pulse_wave_velocity": cardio.get("pulse_wave_velocity"),
            "sleep_time_status": sleep_time.get("status"),
            "sleep_time_recommendation": sleep_time.get("recommendation"),
            "sleep_time_optimal_bedtime": sleep_time.get("optimal_bedtime"),
            "vo2_max": vo2.get("vo2_max"),
        }

    def _oura_workout_row(self, w: dict) -> dict:
        distance_m = w.get("distance")
        return {
            "workout_id": w.get("id", ""),
            "day": w.get("day", ""),
            "activity": w.get("activity", ""),
            "intensity": w.get("intensity", ""),
            "calories": w.get("calories"),
            "distance_km": round(distance_m / 1000, 2) if distance_m else "",
            "start_datetime": w.get("start_datetime", ""),
            "end_datetime": w.get("end_datetime", ""),
            "source": w.get("source", ""),
        }

    def _oura_sleep_period_row(self, s: dict) -> dict:
        """Scalars, the two ring hypnograms, the movement series, and the
        overnight HR/HRV series.

        The old blanket exclusion of every embedded time-series was too coarse.
        What actually justifies excluding the top-level heartrate endpoint is
        its ROW COUNT, not the fact that it is a series: these three are one
        cell per night each (movement ~1.8k chars, HR and HRV ~730 chars as
        JSON at a 300-second interval), so they cost a column on exactly the
        same terms as the hypnograms rather than the rows a per-sample table
        would add. Measured against 414 archived nights.

        Still excluded: the top-level heartrate and met endpoints, which are
        genuinely per-sample across the whole day."""
        readiness = s.get("readiness") or {}
        return {
            "sleep_id": s.get("id", ""),
            "day": s.get("day", ""),
            "type": s.get("type", ""),
            "period": s.get("period"),
            "bedtime_start": s.get("bedtime_start", ""),
            "bedtime_end": s.get("bedtime_end", ""),
            "total_sleep_duration": s.get("total_sleep_duration"),
            "time_in_bed": s.get("time_in_bed"),
            "awake_time": s.get("awake_time"),
            "deep_sleep_duration": s.get("deep_sleep_duration"),
            "light_sleep_duration": s.get("light_sleep_duration"),
            "rem_sleep_duration": s.get("rem_sleep_duration"),
            "efficiency": s.get("efficiency"),
            "latency": s.get("latency"),
            "average_heart_rate": s.get("average_heart_rate"),
            "lowest_heart_rate": s.get("lowest_heart_rate"),
            "average_hrv": s.get("average_hrv"),
            "average_breath": s.get("average_breath"),
            "restless_periods": s.get("restless_periods"),
            "readiness_score": readiness.get("score"),
            "readiness_temperature_deviation": readiness.get("temperature_deviation"),
            "sleep_score_delta": s.get("sleep_score_delta"),
            "readiness_score_delta": s.get("readiness_score_delta"),
            "sleep_algorithm_version": s.get("sleep_algorithm_version", ""),
            "sleep_analysis_reason": s.get("sleep_analysis_reason", ""),
            "low_battery_alert": s.get("low_battery_alert"),
            # Ring-derived hypnograms. app_sleep_phase_5_min is deliberately
            # NOT stored — it is the same night after the user's own bedtime
            # edits, so it describes the UI, not the measurement.
            "sleep_phase_5_min": s.get("sleep_phase_5_min", ""),
            "sleep_phase_30_sec": s.get("sleep_phase_30_sec", ""),
            "movement_30_sec": s.get("movement_30_sec", ""),
            "sleep_hr_series": _json_or_blank(s.get("heart_rate")),
            "sleep_hrv_series": _json_or_blank(s.get("hrv")),
        }

    def _oura_session_row(self, s: dict) -> dict:
        """Scalar fields only — excludes embedded heart_rate/heart_rate_
        variability time-series, same exclusion as everywhere else here.
        Defensive .get() throughout means a renamed/missing field blanks that
        cell only.

        motion_count is NOT a scalar in real payloads (verified 2026-07-30
        against 6 historical sessions): Oura returns the same TimeSeries shape
        as heart_rate — {"interval": 5.0, "items": [...], "timestamp": ...}.
        Writing that dict straight into a cell is a hard Sheets 400, which
        went unnoticed only because the sessions in the live 7-day sync window
        happened to have it null. Summed to a total-motion scalar here, per
        this module's summary-fields-only policy."""
        return {
            "session_id": s.get("id", ""),
            "day": s.get("day", ""),
            "type": s.get("type", ""),
            "start_datetime": s.get("start_datetime", ""),
            "end_datetime": s.get("end_datetime", ""),
            "mood": s.get("mood", ""),
            "motion_count": _timeseries_total(s.get("motion_count")),
        }

    def _oura_rest_mode_row(self, r: dict) -> dict:
        """Unverified against real data (no rest-mode periods logged yet)
        — same defensive .get() treatment as _oura_session_row above."""
        return {
            "rest_mode_id": r.get("id", ""),
            "start_day": r.get("start_day", ""),
            "end_day": r.get("end_day", ""),
            "end_time": r.get("end_time", ""),
        }

    def _sync_oura_events(self, token: str, endpoint: str, start: str, end: str,
                           worksheet, header: list[str], row_mapper) -> int:
        """Shared upsert loop for the 4 event-based Oura endpoints (0-N
        entries per day, keyed by the event's own id — header[0] is always
        that id column, by construction of every _OURA_*_HEADER above).

        An endpoint outside the grant is skipped, not fatal — same reasoning
        as _sync_oura_daily, and applied here too so a future scope change
        cannot take the sleep tabs down from the other side."""
        try:
            entries = oura.get_collection(token, endpoint, start, end)
        except oura.OuraScopeError:
            self._record_oura_scope_gap(endpoint)
            return 0
        for entry in entries:
            row = row_mapper(entry)
            values = [row.get(k, "") for k in header]
            self._upsert_sheet_row(worksheet, str(row[header[0]]), values)
        return len(entries)

    def _oura_event_specs(self) -> tuple:
        """The 4 event-based Oura endpoints, one spec per output tab:
        (result_key, api_endpoint, worksheet_getter, header, row_mapper).
        Shared by sync_oura_all (rolling window) and fetch_oura_history /
        backfill_oura_history (arbitrary historical range) so the
        endpoint→tab→header→mapper wiring lives in exactly one place."""
        return (
            ("workouts", "workout", self._oura_workouts_ws,
             _OURA_WORKOUT_HEADER, self._oura_workout_row),
            ("sleep_periods", "sleep", self._oura_sleep_periods_ws,
             _OURA_SLEEP_PERIOD_HEADER, self._oura_sleep_period_row),
            ("sessions", "session", self._oura_sessions_ws,
             _OURA_SESSION_HEADER, self._oura_session_row),
            ("rest_mode_periods", "rest_mode_period", self._oura_rest_mode_ws,
             _OURA_REST_MODE_HEADER, self._oura_rest_mode_row),
        )

    # ─────────────────────────────────────────────────────────────────────
    #  Short-lived worksheet read cache
    #
    #  One Sleep drill-down render was reading Oura Daily 3x, Oura Sleep
    #  Periods 2x and Sleep Fusion 2x — 10 tab reads where 6 would do,
    #  because get_biometric_rolling, get_effective_wake_adjustments and the
    #  drill-down's own fetches each open the same tabs independently.
    #
    #  Correctness rests on two things: the cache is keyed on
    #  sheets.write_generation(), so ANY write anywhere in the process
    #  invalidates every cached read (no call site has to remember to
    #  invalidate); and it expires after _READ_CACHE_TTL_SECONDS, which
    #  bounds staleness from writes made OUTSIDE this process. That TTL is
    #  far tighter than the 30-minute @st.cache_data the pages already wrap
    #  these reads in, so nothing gets staler than it was before.
    # ─────────────────────────────────────────────────────────────────────

    _READ_CACHE_TTL_SECONDS = 30.0

    def _rows_by_key(self, ws, key_col_name: str) -> dict[str, dict]:
        """The tab's current rows indexed by their key column, read ONCE.

        A sync loop must take this snapshot up front and pass each row into
        the upsert, rather than letting every upsert look itself up. The
        read cache is keyed on sheets.write_generation(), so the first real
        write in the loop invalidates it and every later lookup re-downloads
        the whole tab — turning a 7-row sync where everything changed into 7
        extra full-tab reads. Snapshotting first is also more correct for
        this purpose: "did the row differ from what was there when the sync
        started" is the question being asked.

        Returns {} on a read failure, which makes every row look new and so
        writes them all — the safe direction.
        """
        try:
            rows = self._read_records(ws)
        except Exception:
            return {}
        out: dict[str, dict] = {}
        for r in rows:
            key = _sheet_key(r.get(key_col_name))
            if key:
                out[key] = r
        return out

    def _skip_unchanged(self, ws, header: list[str], key_col_name: str,
                        key_value: str, values: list,
                        existing: dict | None) -> bool:
        """True when the tab already holds exactly `values` for `key_value`,
        so an upsert would rewrite the row with what is already in it.

        Every Home open re-persists a rolling 7-day window to both Biometric
        Blend and Metrics History. Six of those seven days are settled
        history that cannot have changed, so six of every seven writes were
        pure waste — two Sheets operations each (upsert_row_by_key does a
        find then an update), against the 60-per-minute quota that is the
        actual cause of the sync failures this code keeps working around.

        It is also what makes "only overwrite when new information arrives"
        literally true of the stored data, rather than merely true of what
        the numbers happen to be.

        `existing` is that date's row as of the START of the sync, taken
        once by _rows_by_key — see there for why per-row lookups are wrong.
        Pass None to mean "no such row" (always write); callers outside a
        sync loop pass _UNSET to have it looked up here.
        """
        if existing is _UNSET:
            existing = self._rows_by_key(ws, key_col_name).get(_sheet_key(key_value))
        return _row_unchanged(values, existing, header)

    def _read_records(self, ws, numericise_ignore: list | None = None) -> list[dict]:
        key = (getattr(ws, "title", id(ws)), tuple(numericise_ignore or ()))
        entry = self._read_cache.get(key)
        now = time.monotonic()
        if (entry is not None
                and entry[0] == sheets.write_generation()
                and now - entry[1] < self._READ_CACHE_TTL_SECONDS):
            return entry[2]
        rows = sheets.get_worksheet_records(ws, numericise_ignore=numericise_ignore)
        self._read_cache[key] = (sheets.write_generation(), now, rows)
        return rows

    def _oura_tab_records(self, key: str, ws) -> list[dict]:
        """Reads an Oura tab with that tab's digit-string columns exempted
        from gspread's numericising (see _OURA_NUMERICISE_IGNORE) — the only
        safe way to read a tab holding hypnograms."""
        return self._read_records(ws, numericise_ignore=_OURA_NUMERICISE_IGNORE.get(key))

    def get_all_oura_daily_rows(self) -> list[dict]:
        """Every row in the Oura Daily tab, unmapped — for services.datastore's
        oura_daily table."""
        return self._read_records(self._oura_daily_ws())

    def get_all_oura_workouts_rows(self) -> list[dict]:
        """Every row in the Oura Workouts tab — for services.datastore's
        oura_workouts table."""
        return self._oura_tab_records("workouts", self._oura_workouts_ws())

    def get_all_oura_sleep_periods_rows(self) -> list[dict]:
        """Every row in the Oura Sleep Periods tab, via _oura_tab_records so
        the hypnogram columns (sleep_phase_5_min/sleep_phase_30_sec) stay
        exempted from gspread's numericising — for services.datastore's
        oura_sleep_periods table."""
        return self._oura_tab_records("sleep_periods", self._oura_sleep_periods_ws())

    def get_all_oura_sessions_rows(self) -> list[dict]:
        """Every row in the Oura Sessions tab — for services.datastore's
        oura_sessions table."""
        return self._oura_tab_records("sessions", self._oura_sessions_ws())

    def get_all_oura_rest_mode_rows(self) -> list[dict]:
        """Every row in the Oura Rest Mode tab — for services.datastore's
        oura_rest_mode table."""
        return self._oura_tab_records("rest_mode_periods", self._oura_rest_mode_ws())

    def _oura_tab_specs(self) -> list[tuple]:
        """Every Oura output tab as (result_key, worksheet_getter, header) —
        the daily tab (keyed by date) plus the 4 event tabs (keyed by their
        own id). header[0] is always the key column, by construction of every
        _OURA_*_HEADER."""
        return [("daily", self._oura_daily_ws, _OURA_DAILY_HEADER)] + [
            (key, ws_getter, header)
            for key, _endpoint, ws_getter, header, _mapper in self._oura_event_specs()
        ]

    def oura_last_synced(self) -> datetime | None:
        """Last time sync_oura_all actually ran, per the local .sync_state.json
        (see services/clients/local_cache.py for why this isn't just
        st.cache_data — it needs to survive process restarts and unrelated
        st.cache_data.clear() calls elsewhere in the app)."""
        raw = local_cache.read().get("oura_last_synced")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    def oura_sync_due(self, hours: int = 2, now: datetime | None = None) -> bool:
        """True if sync_oura_all hasn't run in the last `hours` hours (or
        has never run). sync_oura_all_if_due checks this before paying for a
        full Oura pull + the per-row Sheets upserts underneath it."""
        return self.sync_due("oura", hours=hours, now=now)

    def mark_oura_synced(self, when: datetime | None = None) -> None:
        self.mark_synced("oura", when=when)

    # ─────────────────────────────────────────────────────────────────────
    #  Durable sync throttles — .sync_state.json, see clients/local_cache.py
    #
    #  Two markers per sync key, not one:
    #
    #    <key>_last_synced     — last SUCCESSFUL completion. Gates the normal
    #                            "already fresh, nothing to do" case.
    #    <key>_last_attempted  — last time the sync was STARTED, written
    #                            before the work begins and cleared on
    #                            success. A leftover one means "failed
    #                            recently".
    #
    #  The second exists because a success-only marker is never written when
    #  a sync raises partway, so every later page load retries the whole
    #  thing and fails the same way. That is not hypothetical here:
    #  sync_oura_all spends two Sheets writes per row across five tabs, which
    #  for a 7-day window walks into Sheets' 60-operations-per-minute quota —
    #  the same quota _run_startup_sync's own note describes hitting. Under a
    #  success-only marker the throttle then never engages at all, and every
    #  single app open pays a full failing Oura sync.
    #
    #  Recording the attempt gives a failed sync a short cooldown instead of
    #  an immediate retry, kept far below the success interval so a genuinely
    #  transient error still recovers within minutes.
    # ─────────────────────────────────────────────────────────────────────

    def _sync_marker(self, name: str) -> datetime | None:
        raw = local_cache.read().get(name)
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    def _write_sync_marker(self, name: str, when: datetime | None) -> None:
        # local_cache.update, not read()+write() — the sync now runs on a
        # background thread while the Streamlit script thread reads these,
        # so the read-modify-write has to be one atomic step or concurrent
        # marker updates lose each other. None deletes the key.
        local_cache.update({name: when.isoformat() if when else None})

    def last_synced(self, key: str) -> datetime | None:
        """Last successful completion of the sync named `key`, or None."""
        return self._sync_marker(f"{key}_last_synced")

    def last_sync_attempted(self, key: str) -> datetime | None:
        """Start time of the last run of `key` that did NOT go on to succeed
        — mark_synced clears this — or None."""
        return self._sync_marker(f"{key}_last_attempted")

    def mark_synced(self, key: str, when: datetime | None = None) -> None:
        """Record a successful completion, and clear the attempt marker so a
        success never leaves a failure cooldown behind it."""
        self._write_sync_marker(f"{key}_last_synced", when or datetime.now())
        self._write_sync_marker(f"{key}_last_attempted", None)

    def mark_sync_attempted(self, key: str, when: datetime | None = None) -> None:
        self._write_sync_marker(f"{key}_last_attempted", when or datetime.now())

    def in_sync_failure_cooldown(self, key: str,
                                 minutes: float = _SYNC_FAILURE_COOLDOWN_MINUTES,
                                 now: datetime | None = None) -> bool:
        """True if `key` started but never completed within the last
        `minutes` — it failed recently and should be left alone for a moment
        rather than retried on this page load.

        A marker dated in the FUTURE counts as not-in-cooldown rather than
        blocking until the clock catches up: that only happens on clock skew
        or a hand-edited state file, and silently disabling a sync for hours
        is much worse than one extra attempt."""
        last_attempt = self.last_sync_attempted(key)
        if last_attempt is None:
            return False
        elapsed = (now or datetime.now()) - last_attempt
        return timedelta(0) <= elapsed < timedelta(minutes=minutes)

    def sync_due(self, key: str, hours: float = 2,
                 cooldown_minutes: float = _SYNC_FAILURE_COOLDOWN_MINUTES,
                 now: datetime | None = None) -> bool:
        """True if the sync named `key` should run now: not in a post-failure
        cooldown, and its last SUCCESS at least `hours` old (or never). A
        success marker dated in the future is treated as stale, same reason
        as above."""
        now = now or datetime.now()
        if self.in_sync_failure_cooldown(key, minutes=cooldown_minutes, now=now):
            return False
        last_success = self.last_synced(key)
        if last_success is None:
            return True
        elapsed = now - last_success
        return elapsed >= timedelta(hours=hours) or elapsed < timedelta(0)

    def run_sync_if_due(self, key: str, work, hours: float = 2,
                        cooldown_minutes: float = _SYNC_FAILURE_COOLDOWN_MINUTES,
                        now: datetime | None = None) -> tuple[bool, str | None]:
        """Run `work()` at most every `hours` hours, recording the attempt
        before starting and the success after finishing.

        Returns the (ok, error) contract the rest of this class uses:
        (True, None) both when the work ran cleanly and when it was skipped
        as not-due (neither is an error); (False, message) only on a real
        failure. Never raises — a sync failing must not take the page down.
        """
        now = now or datetime.now()
        if not self.sync_due(key, hours=hours, cooldown_minutes=cooldown_minutes, now=now):
            return True, None
        # The marker writes are inside the try too. They touch the
        # filesystem, so they can fail (disk full, the file made read-only,
        # a locked directory) — and with them outside, this method could
        # raise despite documenting that it never does, taking the whole
        # sync chain and the page down with it.
        try:
            self.mark_sync_attempted(key, when=now)
            work()
            self.mark_synced(key, when=now)
        except Exception as exc:
            return False, str(exc)
        return True, None

    def run_home_syncs(self, today: date | None = None, now: datetime | None = None,
                       hours: float = 2) -> dict[str, tuple[bool, str | None]]:
        """The Home page's whole device-sync chain, each step individually
        throttled to `hours`. Returns {name: (ok, error)} and never raises.

        Ordering is load-bearing and unchanged from app.py's original inline
        sequence: Oura and Garmin write the raw tabs; the blend derives from
        those; session HR needs the day's Garmin activities present; metrics
        history derives from all of them; sleep fusion reads the already
        synced tabs. Grouped into one method so the background runner has a
        single thing to call and the ordering can't drift between the
        foreground and background paths.
        """
        today = today or date.today()
        now = now or datetime.now()
        kw = dict(today=today, now=now, hours=hours)
        results: dict[str, tuple[bool, str | None]] = {}
        results["oura"] = self.sync_oura_all_if_due(days=7, **kw)
        results["garmin"] = self._garmin_daily_if_due_safe(days=2, **kw)
        results["blend"] = self.sync_biometric_blend_if_due(days=7, **kw)
        results["session_hr"] = self.sync_session_hr_recent_if_due(days=2, **kw)
        results["metrics_history"] = self.sync_metrics_history_if_due(days=7, **kw)
        results["sleep_fusion"] = self.sync_sleep_fusion_if_due(days=14, **kw)
        # LAST, and unthrottled: it sends only what the steps above actually
        # wrote, so an empty buffer costs nothing and a throttle would just
        # delay rows that are already in hand. Never raises — see
        # flush_supabase_mirror.
        sent = self.flush_supabase_mirror()
        results["supabase_mirror"] = (
            self.mirror_last_error is None,
            None if self.mirror_last_error is None
            else f"{self.mirror_last_error[0]}: {self.mirror_last_error[1]}",
        ) if sent or self.mirror_last_error else (True, None)
        return results

    def _garmin_daily_if_due_safe(self, days: int = 2, today: date | None = None,
                                  now: datetime | None = None, hours: float = 2
                                  ) -> tuple[bool, str | None]:
        """sync_garmin_daily_if_due, but never raising and a no-op when
        Garmin isn't configured — matching the contract every other step of
        run_home_syncs already has."""
        if not self.garmin_configured():
            return True, None
        try:
            return self.sync_garmin_daily_if_due(
                days=days, today=today, hours=hours, now=now,
            )
        except Exception as exc:
            return False, str(exc)

    # ─── Durable Home-card snapshot ──────────────────────────────────────
    #  Lets a reopened app repaint Readiness/Strain/Sleep from local disk
    #  instead of ~6 Sheets reads. All the rules about when that is safe
    #  live in services/home_snapshot.py — read its docstring first.

    def get_home_snapshot(self, d: date, today: date | None = None) -> dict | None:
        """The stored card values for `d`, or None when there is nothing
        safe to serve (no entry, an older schema, or today's entry still
        incomplete — see home_snapshot.is_serveable)."""
        store = local_cache.read().get(_HOME_SNAPSHOT_KEY) or {}
        entry = home_snapshot.get(store, d)
        if home_snapshot.is_serveable(entry, d, today or date.today()):
            return entry
        return None

    def save_home_snapshot(self, d: date, snapshot: dict,
                           sleep_need_hours: float | None,
                           sleep_baseline_window: int | None,
                           computed_at: datetime | None = None,
                           today: date | None = None) -> dict:
        """Persists what the cards show for `d`. Incomplete entries are
        stored too, deliberately: get_home_snapshot refuses to serve them,
        but keeping them means a day whose sleep never arrives is a visible
        record rather than an absent one, and the next complete recompute
        simply overwrites in place."""
        entry = home_snapshot.build(
            snapshot, sleep_need_hours, sleep_baseline_window, computed_at=computed_at,
        )
        local_cache.mutate(
            _HOME_SNAPSHOT_KEY,
            lambda store: home_snapshot.prune(
                home_snapshot.put(store or {}, d, entry), today or date.today()),
        )
        return entry

    def invalidate_home_snapshot(self, d: date) -> None:
        """Drops `d`'s entry. Called wherever something happens that can move
        a card — a logged session (strain), a saved check-in, a wake-time
        correction (sleep score) — since this cache outlives the process and
        would otherwise survive the very events that invalidate it."""
        local_cache.mutate(
            _HOME_SNAPSHOT_KEY,
            lambda store: store if home_snapshot.get(store or {}, d) is None
            else home_snapshot.drop(store or {}, d),
        )

    # ─── In-progress training checkpoint (local mirror) ──────────────────
    #  The durable copy lives in Notion under set_config("training_progress").
    #  One set_config is a find-then-write PAIR — a Notion query plus a page
    #  update — so on the guided flow's hot path (a weight/reps stepper tap) it
    #  cost two network round trips per tap, on a screen the athlete taps five
    #  times to move 20 kg to 32.5 kg. These two methods are the fast tier:
    #  every tap mirrors locally, and only session transitions also pay Notion.

    def save_training_checkpoint_local(self, payload: str) -> bool:
        """Mirror the checkpoint JSON to local disk. True when stored.

        On failure the key is DELETED rather than left holding an older
        payload. A stale mirror is the one genuinely dangerous state: it would
        win over a newer Notion copy on restore and resurrect superseded state
        — including a session the athlete explicitly discarded. An ABSENT
        mirror is safe, because get_training_checkpoint_local returning None
        simply falls back to Notion.
        """
        try:
            local_cache.update({_TRAINING_CHECKPOINT_KEY: payload})
            return True
        except Exception:
            try:
                local_cache.update({_TRAINING_CHECKPOINT_KEY: None})
            except Exception:
                pass
            return False

    def get_training_checkpoint_local(self) -> str | None:
        """The mirrored checkpoint JSON, or None if there isn't one.

        None is not an error — it means "ask Notion", which is exactly what a
        fresh process (a Community Cloud restart, where the local file is gone)
        should do.
        """
        try:
            raw = local_cache.read().get(_TRAINING_CHECKPOINT_KEY)
        except Exception:
            return None
        return raw if isinstance(raw, str) else None

    def clear_training_checkpoint_local(self) -> None:
        """Drop the mirror. Used when the durable copy is authoritative."""
        try:
            local_cache.update({_TRAINING_CHECKPOINT_KEY: None})
        except Exception:
            pass

    # ─── Flexibility assessments ─────────────────────────────────────────
    #  One session of a cluster battery (see services/battery.py and
    #  cluster_a_battery.py). Read those docstrings before touching this:
    #  readings are the ONLY input the model has, so a lost or half-parsed one
    #  is not a degraded answer, it is a wrong one.
    #
    #  The payload schema went to 2 on 2026-08-06 when the rung model was
    #  deleted. A v1 payload is NOT migrated — its readings measured different
    #  positions with different landmarks, so there is nothing to convert — and
    #  assessment_from_dict returns None for one, which lands it in the
    #  dropped-entry path below. No v1 assessment was ever recorded, so this
    #  costs nothing and guessing a conversion would not have.

    def get_flexibility_assessments(self) -> tuple:
        """Every completed assessment, oldest first.

        Unreadable entries are DROPPED rather than raising or being partially
        recovered — flexibility.assessment_from_dict returns None for an
        unknown schema or a rung that no longer exists, and "no assessment" is
        a state the screen already renders honestly.
        """
        raw = local_cache.read().get(_FLEXIBILITY_KEY) or []
        parsed = [flexibility.assessment_from_dict(d) for d in raw]
        good = [a for a in parsed if a is not None]
        return tuple(sorted(good, key=lambda a: a.taken_on))

    def save_flexibility_assessment(self, assessment) -> None:
        """Store a completed assessment, replacing any same-dated one.

        Same date replaces rather than appending: re-running on the same day is
        a correction, and two entries for one date would let the model see a
        history that never happened.
        """
        stamp = assessment.taken_on.isoformat()

        def _replace_same_date(existing):
            kept = [d for d in (existing or [])
                    if not (isinstance(d, dict) and d.get("taken_on") == stamp)]
            kept.append(flexibility.assessment_to_dict(assessment))
            return kept

        local_cache.mutate(_FLEXIBILITY_KEY, _replace_same_date)

    def get_flexibility_draft(self):
        """The in-progress assessment, or None. This is what makes the flow
        resumable — 40 minutes is long enough to be interrupted, and a
        half-finished assessment that vanishes will not be attempted twice."""
        return flexibility.assessment_from_dict(
            local_cache.read().get(_FLEXIBILITY_DRAFT_KEY) or {})

    def save_flexibility_draft(self, assessment) -> None:
        """Called after EVERY step, not at the end. The whole point is that
        nothing is lost mid-flow."""
        local_cache.update(
            {_FLEXIBILITY_DRAFT_KEY: flexibility.assessment_to_dict(assessment)})

    def clear_flexibility_draft(self) -> None:
        local_cache.update({_FLEXIBILITY_DRAFT_KEY: None})

    def _sync_oura_daily(self, token: str, start: str, end: str) -> int:
        """The Oura Daily tab alone (readiness/sleep/activity/SpO2 etc.
        collapsed into one row per date). Split out of sync_oura_all so it is
        one resumable step alongside the four event tabs."""
        by_date: dict[str, dict] = {}
        for endpoint in _OURA_DAILY_ENDPOINTS:
            try:
                entries = oura.get_collection(token, endpoint, start, end)
            except oura.OuraScopeError:
                # ONE endpoint outside the grant must not cost the other
                # eight. Measured 2026-08-17: a grant covering all eight of
                # Oura's PUBLISHED scopes still 401s on daily_resilience
                # (wants an undocumented `stress` scope) and
                # daily_cardiovascular_age (`heart_health`) — and because
                # that 401 propagated, the whole sync died at the first of
                # them, taking sleep with it on a credential that reads
                # sleep perfectly well. Both are archival: nothing outside
                # the Oura Daily tab's own columns reads either.
                #
                # Recorded, not swallowed: a column that is permanently blank
                # because of a scope should be answerable without re-probing
                # the API, and is indistinguishable in the sheet from Oura
                # simply having no data.
                self._record_oura_scope_gap(endpoint)
                continue
            for entry in entries:
                d = entry.get("day")
                if d:
                    by_date.setdefault(d, {})[endpoint] = entry
        daily_ws = self._oura_daily_ws()
        for d, group in by_date.items():
            row = self._oura_daily_row(d, group)
            values = [row.get(k, "") for k in _OURA_DAILY_HEADER]
            self._upsert_sheet_row(daily_ws, d, values)
        return len(by_date)

    def oura_sync_progress(self, window: str, now: datetime | None = None) -> dict:
        """Per-tab row counts already written for `window` by a run that
        started but did not finish, or {} if there is nothing to resume.

        Discarded — i.e. the next run redoes everything — when the window
        differs (a new day moves the rolling window, so nothing carries
        over), when the marker is unparseable, or when it is older than
        _OURA_SYNC_RESUME_MINUTES. That last bound is what stops a resume
        from serving stale data: Oura revises a day's readiness and sleep
        scores for some hours after the upload, so skipping a tab written
        this morning because the marker says "done" would pin the
        provisional numbers for the rest of the day. Half an hour covers the
        case this exists for — the app closed mid-sync and reopened shortly
        after — and nothing longer.
        """
        raw = local_cache.read().get(_OURA_SYNC_PROGRESS_KEY) or {}
        if raw.get("window") != window:
            return {}
        try:
            started = datetime.fromisoformat(raw.get("at", ""))
        except (TypeError, ValueError):
            return {}
        if (now or datetime.now()) - started > timedelta(minutes=_OURA_SYNC_RESUME_MINUTES):
            return {}
        counts = raw.get("counts")
        return dict(counts) if isinstance(counts, dict) else {}

    def _mark_oura_tab_synced(self, window: str, tab: str, count: int,
                              now: datetime | None = None) -> None:
        """Records one finished tab. Written after EACH tab rather than once
        at the end — the whole point is to survive the process disappearing
        mid-run, which is precisely when an end-of-run write never happens.

        This is the one that most needed to become atomic: it runs on the
        BACKGROUND sync thread, once per tab, while the Streamlit script
        thread writes the in-progress training checkpoint into the same file
        on every stepper tap. As a read()/write() pair it rewrote the WHOLE
        file and reverted whatever the other thread had just stored."""
        def _advance(raw):
            raw = raw or {}
            counts = dict(raw.get("counts") or {}) if raw.get("window") == window else {}
            counts[tab] = count
            return {
                "window": window,
                "at": (now or datetime.now()).isoformat(timespec="seconds"),
                "counts": counts,
            }

        local_cache.mutate(_OURA_SYNC_PROGRESS_KEY, _advance)

    def _clear_oura_sync_progress(self) -> None:
        local_cache.update({_OURA_SYNC_PROGRESS_KEY: None})

    def sync_oura_all(self, days: int = 7, today: date | None = None,
                      now: datetime | None = None) -> dict:
        """Pulls every configured Oura data type for the last `days` days
        (inclusive of today) and upserts each into its own Sheet tab — Oura
        Daily keyed by date, the 4 event tabs keyed by their own id, so
        re-running this (whether the 2-hour automatic trigger or the manual
        weekly button) never duplicates a row, only refreshes existing ones.
        Raises RuntimeError if Oura isn't configured, or whatever `requests`
        raises on a real API failure — callers (views/sync.py, app.py's
        cached wrapper) decide how to surface that. Returns
        {tab_name: rows_written}.

        Interruption-tolerant in two independent ways, because a full run
        takes ~46 seconds and app.py deliberately starts it AFTER the page
        paints — so closing the app is a normal way for it to be cut off,
        not an edge case:

        * **Order.** Tabs are written in _OURA_SYNC_ORDER, which front-loads
          the only two the Home page reads. A run killed partway therefore
          leaves the app's own screen correct and only the archival tabs
          behind, instead of the observed failure where Oura Daily landed,
          Oura Sleep Periods did not, and the Sleep card read "No Readings"
          all morning against a night Oura had recorded perfectly well.
        * **Resume.** Each finished tab is recorded (see oura_sync_progress),
          so the next attempt within the resume window picks up where this
          one stopped rather than re-uploading the ~29 workout rows it had
          already written. Counts for skipped tabs are carried through from
          the marker, so the returned dict still describes the whole window
          and the manual button in Insights → Sync keeps reporting real
          numbers.

        The marker is cleared on completion, so the ordinary path leaves no
        state behind.
        """
        token = self._oc
        if token is None:
            raise RuntimeError(
                "Oura is not authorised — run `python scripts/authorize_oura.py`. "
                "(Oura retired Personal Access Tokens in December 2025, so adding "
                "OURA_TOKEN to secrets.toml is no longer a route in: new credentials "
                "come from the OAuth flow.)"
            )
        today = today or date.today()
        start = (today - timedelta(days=days - 1)).isoformat()
        end = today.isoformat()
        window = f"{start}..{end}"

        already = self.oura_sync_progress(window, now=now)
        events = {
            key: (endpoint, ws_getter, header, mapper)
            for key, endpoint, ws_getter, header, mapper in self._oura_event_specs()
        }

        # Cleared here rather than in the two recorders, because THIS is the
        # call that covers every endpoint — so it is the only scope at which
        # "no longer missing" can be observed. Accumulating per-endpoint
        # without a reset would keep reporting a gap that a wider
        # re-authorisation had already closed; resetting inside
        # _sync_oura_daily would wipe the event endpoints' gaps instead.
        if not already:
            local_cache.update({_OURA_SCOPE_GAPS_KEY: None})

        result: dict[str, int] = {}
        try:
            for tab in _OURA_SYNC_ORDER:
                if tab in already:
                    result[tab] = already[tab]
                    continue
                if tab == "daily":
                    count = self._sync_oura_daily(token, start, end)
                else:
                    endpoint, ws_getter, header, mapper = events[tab]
                    count = self._sync_oura_events(
                        token, endpoint, start, end, ws_getter(), header, mapper,
                    )
                result[tab] = count
                self._mark_oura_tab_synced(window, tab, count, now=now)
        except oura.OuraAuthError as exc:
            # RECORD, then re-raise unchanged. A 401 here is the only evidence
            # that a static PAT has been revoked — nothing about the stored
            # credential itself can reveal it, so without this the athlete's
            # actual 2026-08-12 state (a dead PAT) still reports healthy and
            # the Home banner still never fires.
            self._record_oura_auth_failure(exc)
            raise
        self._clear_oura_auth_failure()
        self._clear_oura_sync_progress()
        return result

    def sync_oura_all_if_due(self, days: int = 7, today: date | None = None,
                             hours: float = 2, now: datetime | None = None
                             ) -> tuple[bool, str | None]:
        """sync_oura_all() at most every `hours` hours, recording the attempt
        before the work starts.

        That last part matters more here than anywhere else. sync_oura_all
        spends two Sheets writes per row across five tabs, which for a 7-day
        window runs into the 60-operations-per-minute quota that
        _run_startup_sync's own note describes hitting. Under the previous
        success-only marker that meant mark_oura_synced() was never reached,
        so the next page load started the identical heavy sync again — the
        throttle could never engage, and every app open paid a full failing
        Oura sync. (True, None) when Oura isn't configured or the window is
        already fresh."""
        if not self.oura_configured():
            return True, None
        return self.run_sync_if_due(
            "oura", lambda: self.sync_oura_all(days=days, today=today),
            hours=hours, now=now,
        )

    # ─── Historical backfill (arbitrary date range) ──────────────────────
    #  sync_oura_all covers a rolling window ending today and upserts row by
    #  row — 2 API calls each, fine for 7 days, hopeless for a multi-year
    #  range (Sheets allows 60 writes/minute). These two split that into a
    #  read-only fetch and a batch-append write so a big range costs a
    #  handful of calls, and so the fetched data can also be exported
    #  locally without being fetched twice.

    def fetch_oura_history(self, start: str, end: str) -> dict:
        """Read-only pull of every Oura data type over an arbitrary inclusive
        [start, end] range (ISO YYYY-MM-DD), mapped into the same row shapes
        sync_oura_all writes — but writing nothing anywhere. Returns
        {"rows": {tab_key: [row_dict, ...]}, "raw": {endpoint: [entry, ...]}}:
        `rows` feeds backfill_oura_history and any CSV export, `raw` is the
        unmapped API payload so a caller can archive the fields the Sheet
        schema deliberately drops (embedded time-series, hypnograms) without
        paying for a second fetch.

        Dates missing an endpoint entirely — daily_resilience needs weeks of
        prior history, vo2_max/rest_mode_period are often empty outright —
        just leave those columns None, same defensive behaviour as
        _oura_daily_row."""
        token = self._oc
        if token is None:
            raise RuntimeError(
                "Oura is not authorised — run `python scripts/authorize_oura.py`. "
                "(Oura retired Personal Access Tokens in December 2025, so adding "
                "OURA_TOKEN to secrets.toml is no longer a route in: new credentials "
                "come from the OAuth flow.)"
            )

        raw: dict[str, list[dict]] = {}
        by_date: dict[str, dict] = {}
        for endpoint in _OURA_DAILY_ENDPOINTS:
            entries = oura.get_collection(token, endpoint, start, end)
            raw[endpoint] = entries
            for entry in entries:
                d = entry.get("day")
                if d:
                    by_date.setdefault(d, {})[endpoint] = entry

        rows: dict[str, list[dict]] = {
            "daily": [self._oura_daily_row(d, by_date[d]) for d in sorted(by_date)],
        }
        for key, endpoint, _ws_getter, _header, mapper in self._oura_event_specs():
            entries = oura.get_collection(token, endpoint, start, end)
            raw[endpoint] = entries
            rows[key] = [mapper(e) for e in entries]
        return {"rows": rows, "raw": raw}

    def backfill_oura_history(self, rows: dict[str, list[dict]]) -> dict[str, dict]:
        """Batch-appends pre-fetched rows (fetch_oura_history()["rows"]) into
        their Sheet tabs, skipping every key the tab already holds. Two
        consequences worth stating: a real synced day is never overwritten by
        a backfill, and re-running the same range is idempotent rather than
        duplicating rows.

        This appends where sync_oura_all upserts — deliberate, since the diff
        against existing keys costs one read per tab instead of one find per
        row. Returns {tab_key: {"written": n, "skipped": n}}."""
        out: dict[str, dict] = {}
        for key, ws_getter, header in self._oura_tab_specs():
            candidates = rows.get(key) or []
            if not candidates:
                out[key] = {"written": 0, "skipped": 0}
                continue
            ws = ws_getter()
            key_field = header[0]
            existing = {
                _sheet_key(r.get(key_field)) for r in self._oura_tab_records(key, ws)
            }
            new_rows = [r for r in candidates if _sheet_key(r.get(key_field)) not in existing]
            values = [
                ["" if r.get(k) is None else r.get(k) for k in header]
                for r in new_rows
            ]
            self._append_sheet_rows(ws, header, values)
            out[key] = {"written": len(new_rows), "skipped": len(candidates) - len(new_rows)}
        return out

    def export_oura_tabs(self) -> dict[str, list[dict]]:
        """Every Oura tab's current contents, {tab_key: [row_dict, ...]} —
        read-only, and read through the tab's OWN header rather than the
        current _OURA_*_HEADER, so it stays a faithful snapshot even when the
        two have diverged. Exists so a caller can back a tab up before
        rebuild_oura_tabs() rewrites it."""
        return {
            key: self._oura_tab_records(key, ws_getter())
            for key, ws_getter, _header in self._oura_tab_specs()
        }

    def rebuild_oura_tabs(self, start: str, end: str,
                          rows: dict[str, list[dict]] | None = None) -> dict[str, dict]:
        """Rewrites every Oura tab against the CURRENT header — the migration
        path for a schema that has gained columns, which neither sync_oura_all
        nor backfill_oura_history can perform (both only ever write the first
        len(header) columns of individual rows, so a widened header leaves
        every pre-existing row short).

        Re-fetches [start, end] unless `rows` is supplied, then merges: a row
        the fetch covers is replaced with the freshly-mapped version (this is
        what populates the new columns), and a row it does NOT cover is
        carried through untouched, with the new columns simply blank. Nothing
        is ever dropped — the output is always a superset of what was there.

        Returns {tab_key: {"total", "refreshed", "carried", "added"}}."""
        data = rows if rows is not None else self.fetch_oura_history(start, end)["rows"]
        out: dict[str, dict] = {}
        for key, ws_getter, header in self._oura_tab_specs():
            ws = ws_getter()
            key_field = header[0]
            fresh = {
                _sheet_key(r.get(key_field)): r for r in (data.get(key) or [])
                if _sheet_key(r.get(key_field))
            }
            merged, seen = [], set()
            for old in self._oura_tab_records(key, ws):
                k = _sheet_key(old.get(key_field))
                if not k or k in seen:
                    continue
                seen.add(k)
                merged.append(fresh.get(k, old))
            added = [r for k, r in fresh.items() if k not in seen]
            merged.extend(added)
            # Chronological, so a rebuilt tab reads the same way a freshly
            # synced one would; the id key is the tiebreak within a day.
            merged.sort(key=lambda r: (
                _sheet_key(r.get("date") or r.get("day") or r.get("start_day")),
                _sheet_key(r.get(key_field)),
            ))
            values = [
                ["" if r.get(c) is None else r.get(c) for c in header]
                for r in merged
            ]
            self._rewrite_sheet(ws, header, values)
            refreshed = sum(1 for k in seen if k in fresh)
            out[key] = {
                "total": len(merged), "refreshed": refreshed,
                "carried": len(seen) - refreshed, "added": len(added),
            }
        return out


_WEEKLY_ROLLUP_HEADER = [
    "week_start", "week_end", "phase", "scheduled", "completed", "ratio", "status", "computed_at",
]


def _timeseries_total(val) -> float | int | None:
    """Collapses an Oura TimeSeries ({"interval", "items", "timestamp"}) into
    the sum of its items, so a count-style series can occupy one cell instead
    of being written as a dict (a Sheets 400). Nulls inside items are skipped
    — Oura pads gaps with them. Passes an already-scalar value straight
    through, and returns None for anything else, so this stays safe if Oura
    changes the field's shape again."""
    if isinstance(val, dict):
        items = val.get("items") or []
        nums = [v for v in items if isinstance(v, (int, float))]
        return sum(nums) if nums else None
    if isinstance(val, (int, float)):
        return val
    return None


def _float_or_none(val) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _sheet_key(val) -> str:
    """Normalises a key-column value for comparison across a round trip
    through Sheets — a date written as "2023-07-04" can read back as
    "2023-07-04 00:00:00" depending on the tab's cell formatting, which would
    otherwise make Repository.backfill_oura_history think an existing date is
    new. A no-op for the event tabs' UUID keys."""
    return str(val or "").split(" ")[0].strip()


def _sheet_date(val) -> str | None:
    try:
        return str(val).split(" ")[0].strip() or None
    except Exception:
        return None


def _json_or(raw, default):
    """Parse a JSON cell, falling back to `default` on empty/corrupt values —
    a mangled zone breakdown must degrade to "no detail", never break a read."""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def _json_or_blank(value) -> str:
    """Serialise a nested structure for a single cell, blank when there is
    nothing to store. The write-direction counterpart to _json_or.

    Writing a dict or list straight into a cell is a hard Sheets 400 — the
    failure _oura_session_row's motion_count hit in production. Anything that
    will not serialise degrades to blank rather than raising, so one odd field
    costs a cell and not the whole night's row."""
    if value is None or value == "" or value == [] or value == {}:
        return ""
    try:
        return json.dumps(value, separators=(",", ":"))
    except (TypeError, ValueError):
        return ""


def _sheet_float(val) -> float | None:
    try:
        v = float(val)
        return v if v != 0.0 else None
    except (TypeError, ValueError):
        return None


def _sheet_int(val) -> int | None:
    try:
        v = int(float(val))
        return v if v != 0 else None
    except (TypeError, ValueError):
        return None


def _sheet_kj_to_kcal(val) -> int | None:
    v = _sheet_float(val)
    return round(v / 4.184) if v else None
