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

import dataclasses
import json
import time
import uuid
from datetime import date, datetime, timedelta

from services import biometrics
from services import content_weighting
from services import dashboard
from services import hr_load
from services import hr_matching
from services import models
from services import readiness
from services import sessions as training_sessions
from services import sleep_fusion
from services import sleep_movement
from services.clients import datastore_reader
from services.clients import garmin
from services.clients import local_cache
from services.clients import notion
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

    @property
    def _nc(self):
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
        return bool(self.config.datastore_path)

    @property
    def _ds(self):
        """Lazy read-only connection to the datastore. Opened once per
        Repository lifetime, like every other client here."""
        if self._datastore_conn is None:
            self._datastore_conn = datastore_reader.connect(self.config.datastore_path)
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
        datastore's schema is fixed by datastore_schema.sql."""
        if self.offline:
            return datastore_reader.OfflineWorksheet(
                self._ds, title, _DATASTORE_TABLE_BY_TAB[title])
        return sheets.get_or_create_worksheet(
            self._sc, self.config.google_sheets_id, title, header)

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

    @property
    def _oc(self) -> str | None:
        """The bearer token itself — no session/login step for a personal
        access token, unlike Garmin. None if unconfigured."""
        if self._oura_token_obj is None:
            self._oura_token_obj = oura.make_client(self.config)
        return self._oura_token_obj

    def _query(self, db_id: str, filter_: dict | None = None, sorts: list | None = None) -> list[dict]:
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
            notion.create_page(
                self._nc, self.config.notion_db_readiness,
                properties=self._check_in_properties(record),
            )
            return

        merged, note_changed = self._merge_check_in(record, existing_page)
        properties = self._check_in_properties(merged)
        if note_changed:
            properties["Parsed"] = notion.checkbox(False)
        notion.update_page(self._nc, existing_page["id"], properties=properties)

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
        if properties["Note"]["rich_text"][0]["text"]["content"] != old_note:
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
                             sensation_type: list, warning_level: str) -> None:
        notion.update_page(self._nc, row_id, properties={
            "Parsed Severity":   notion.number(severity),
            "Parsed Areas":      notion.rich_text(json.dumps(body_parts or [])),
            "Parsed Sensations": notion.rich_text(json.dumps(sensation_type or [])),
            "Warning":           notion.select(warning_level),
            "Parsed":            notion.checkbox(True),
        })

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
        notion.update_page(self._nc, training_log_id, properties={
            "Notes": notion.rich_text(combined[:2000]),
        })

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
            total_volume = round(sum((s.get("reps") or 0) * (s.get("weight") or 0.0) for s in sets), 1)

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
                "total_volume_kg": round(sum((s.get("reps") or 0) * (s.get("weight") or 0.0) for s in sets), 1),
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

    def has_logged_session(self, d: date) -> bool:
        """True only for a logged rehab-plan session — a logged Yoga (or other
        supplementary) session must never mark the plan day itself as done.

        Filters "Type" != "Yoga" in Python rather than in the Notion query:
        a `select.does_not_equal` filter is validated against the property's
        currently-configured options at query time, and 400s outright if
        "Yoga" isn't one of them yet — which is exactly the state before the
        very first Yoga session is ever logged (save_training_exercise's
        Type="Yoga" write is what lazily creates that option in the first
        place). Querying by date alone and excluding Yoga client-side works
        regardless of whether that option exists yet."""
        pages = self._query(
            self.config.notion_db_training,
            filter_={"property": "Session Date", "date": {"equals": str(d)}},
        )
        return any(notion.get_property(p, "Type", "select") != "Yoga" for p in pages)

    def get_logged_session_dates(self, start: date, end: date) -> set[str]:
        pages = self._query(
            self.config.notion_db_training,
            filter_={"and": [
                {"property": "Session Date", "date": {"on_or_after": str(start)}},
                {"property": "Session Date", "date": {"on_or_before": str(end)}},
            ]},
        )
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
                "date": notion.get_property(p, "Session Date", "date") or "",
                "au": notion.get_property(p, "Session AU", "number") or 0.0,
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

        au_by_date: dict[str, float] = {}
        for bucket in sessions_by_id.values():
            mult = content_weighting.day_content_multiplier(bucket["exercise_seconds"])["multiplier"]
            au_by_date[bucket["date"]] = au_by_date.get(bucket["date"], 0.0) + bucket["au"] * mult

        return [{"date": d, "total_au": round(v, 1)} for d, v in sorted(au_by_date.items())]

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
        notion.update_page(self._nc, note_id, properties={
            "Note Summary":  notion.rich_text(summary or ""),
            "Sentiment":     notion.number(sentiment_score),
            "Flagged Areas": notion.rich_text(json.dumps(flagged_body_parts or [])),
            "Warning":       notion.select(warning_level),
        })

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

    def get_biometrics(self, days: int = 60, today: date | None = None) -> list[models.BiometricRecord]:
        today = today or date.today()
        cutoff = (today - timedelta(days=days)).isoformat()
        pages = self._query(
            self.config.notion_db_biometrics,
            filter_={"property": "Log Date", "date": {"on_or_after": cutoff}},
            sorts=[{"property": "Log Date", "direction": "descending"}],
        )
        out = []
        for p in pages:
            g = lambda name, kind: notion.get_property(p, name, kind)
            out.append(models.BiometricRecord(
                date=g("Log Date", "date"), hrv_ms=g("HRV", "number"),
                resting_heart_rate=g("RHR", "number"), sleep_duration_hours=g("Sleep Hours", "number"),
                sleep_deep_hours=g("Deep Sleep Hours", "number"), active_kcal=g("Active kcal", "number"),
                weight_kg=g("Weight kg", "number"), steps=g("Steps", "number"),
            ))
        return out

    def save_biometrics_today(self, date_str: str, rhr=None, hrv=None, sleep_hours=None,
                               sleep_deep=None, active_kcal=None, weight_kg=None, steps=None) -> None:
        db_id = self.config.notion_db_biometrics
        existing = self._query(db_id, filter_={"property": "Log Date", "date": {"equals": date_str}})
        props = {
            "Entry": notion.title(date_str), "Log Date": notion.date_prop(date_str),
            "RHR": notion.number(rhr), "HR Average": notion.number(None), "HRV": notion.number(hrv),
            "Sleep Hours": notion.number(sleep_hours), "Deep Sleep Hours": notion.number(sleep_deep),
            "Active kcal": notion.number(active_kcal), "Weight kg": notion.number(weight_kg),
            "Steps": notion.number(steps),
        }
        if existing:
            notion.update_page(self._nc, existing[0]["id"], props)
        else:
            notion.create_page(self._nc, db_id, props)

    # ─────────────────────────────────────────────────────────────────────
    #  App Config (flat key/value store — plan_start_date, current_stage,
    #  phases, training_progress, diagnostic_profile, movement risk)
    # ─────────────────────────────────────────────────────────────────────

    def _config_page(self, key: str) -> dict | None:
        pages = self._query(
            self.config.notion_db_config,
            filter_={"property": "Key", "title": {"equals": key}},
        )
        return pages[0] if pages else None

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
        if page:
            notion.update_page(self._nc, page["id"], props)
        else:
            notion.create_page(self._nc, self.config.notion_db_config, props)

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

        bio_pages = self._query(
            self.config.notion_db_biometrics,
            filter_={"property": "Log Date", "date": {"on_or_after": cutoff}},
            sorts=[{"property": "Log Date", "direction": "ascending"}],
        )
        biometrics = [
            {
                "date": notion.get_property(p, "Log Date", "date"),
                "hrv_ms": notion.get_property(p, "HRV", "number"),
                "resting_heart_rate": notion.get_property(p, "RHR", "number"),
                "sleep_duration_hours": notion.get_property(p, "Sleep Hours", "number"),
                "sleep_deep_hours": notion.get_property(p, "Deep Sleep Hours", "number"),
                "active_energy_kcal": notion.get_property(p, "Active kcal", "number"),
                "weight_kg": notion.get_property(p, "Weight kg", "number"),
                "steps": notion.get_property(p, "Steps", "number"),
            }
            for p in bio_pages
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
        if self.offline:
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
        if self.offline:
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
        sheets.upsert_row_by_key(self._garmin_daily_ws(), key_col=1, key_value=row["date"], row_values=values)

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
            main = biometrics.pick_main_sleep_period(entries)
            if main is None:
                continue
            duration_s = main.get("total_sleep_duration")
            out[day] = {
                "hrv_ms": main.get("average_hrv") or None,
                "resting_heart_rate": main.get("lowest_heart_rate") or None,
                "sleep_duration_hours": round(duration_s / 3600, 2) if duration_s else None,
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
        by ISO date — for the Readiness drill-down's comparison panel and the
        model audit behind it.

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

    def upsert_biometric_blend_row(self, record: models.BiometricRecord) -> None:
        """Writes one blended day into the Biometric Blend tab, keyed by
        date — re-running this for the same date overwrites it (idempotent),
        which is how a rolling few-day sync keeps very recent days current
        while older days (outside that rolling window) stop being touched
        and become a fixed historical record."""
        row = self._biometric_blend_row(record)
        values = [row.get(k, "") for k in _BIOMETRIC_BLEND_HEADER]
        sheets.upsert_row_by_key(self._biometric_blend_ws(), key_col=1, key_value=record.date, row_values=values)

    def sync_biometric_blend(self, days: int = 7, today: date | None = None) -> int:
        """Computes get_biometric_rolling(days, today) and persists every
        resulting day to the Biometric Blend tab. Returns the number of days
        written. `days` controls how far back to (re)persist — small (e.g. 7)
        for the routine once/day sync so only recent days get overwritten;
        large (e.g. 400) for the one-time/on-demand full-history backfill."""
        records = self.get_biometric_rolling(days=days, today=today)
        for r in records:
            self.upsert_biometric_blend_row(r)
        return len(records)

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

    def upsert_metrics_history_row(self, snapshot: dict) -> None:
        """snapshot: {"date": ISO str, "readiness_score", "sleep_pct",
        "sleep_score", "strain"} (services.dashboard.
        compute_daily_metrics_snapshot's shape, plus a "date" key) — writes
        one day into the Metrics History tab, keyed by date (idempotent,
        same upsert-by-date pattern as Biometric Blend)."""
        row = self._metrics_history_row(snapshot)
        values = [row.get(k, "") for k in _METRICS_HISTORY_HEADER]
        sheets.upsert_row_by_key(
            self._metrics_history_ws(), key_col=1, key_value=snapshot["date"], row_values=values,
        )

    def rebuild_metrics_history(self, fresh: dict[str, dict] | None = None) -> int:
        """Re-head the Metrics History tab so readiness_model_version stops
        being written into a column no read can see, carrying every existing
        row through. Call once after adding the column; see rebuild_tab for
        why any tab created before a column joined its header needs this."""
        return self.rebuild_tab(self._metrics_history_ws(), _METRICS_HISTORY_HEADER, fresh)

    def sync_metrics_history(self, days: int = 7, today: date | None = None) -> int:
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
        persisted Sleep Score reflects any per-night wake-time correction."""
        today = today or date.today()
        bio_rows = [dataclasses.asdict(r) for r in self.get_biometric_rolling(days=days + 60, today=today)]
        au_rows = self.get_daily_session_au_weighted(days=days + 28, today=today)
        stage = self.get_current_stage()
        wake_adjustments, _sources = self.get_effective_wake_adjustments(
            start=(today - timedelta(days=days - 1)).isoformat(), end=today.isoformat(),
        )

        written = 0
        for i in range(days):
            d = today - timedelta(days=i)
            snapshot = dashboard.compute_daily_metrics_snapshot(
                d, bio_rows, au_rows, stage, wake_time_adjustments=wake_adjustments,
            )
            snapshot["date"] = d.isoformat()
            self.upsert_metrics_history_row(snapshot)
            written += 1
        return written

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
                "readiness_score": r.get("readiness_score") or None,
                "sleep_pct": r.get("sleep_pct") or None,
                "sleep_score": r.get("sleep_score") or None,
                "strain": r.get("strain") or None,
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
        sheets.upsert_row_by_key(
            self._wake_time_adjustments_ws(), key_col=1, key_value=d.isoformat(), row_values=values,
        )

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

    def compute_session_hr(
        self, session_date: date | str, set_records_by_exercise: dict,
        duration_minutes: float = 0.0, hr_max: float | None = None,
        hr_rest: float | None = None, activity_limit: int = 20,
    ) -> dict | None:
        """Match a logged session to a Garmin activity and derive its
        heart-rate load. None when nothing matched — the caller then falls
        back to RPE-only strain, exactly as before this existed.

        `set_records_by_exercise`: {exercise_idx: [set records]} straight from
        the Sets JSON — the per-set "ts" timestamps are what make time-window
        matching (and per-exercise attribution) possible at all, so sessions
        logged before per-set capture existed correctly return None here.
        """
        if self._gc is None:
            return None
        all_sets = [r for rows in (set_records_by_exercise or {}).values() for r in rows]
        window = hr_matching.session_window(
            all_sets, duration_minutes=duration_minutes)
        if window is None:
            return None

        day = str(session_date)[:10]
        candidates = [
            self._garmin_activity_row(a)
            for a in garmin.get_recent_activities(self._gc, limit=activity_limit)
        ]
        candidates = [c for c in candidates if c.get("date") == day]
        activity, overlap = hr_matching.match_activity(candidates, window)
        if activity is None:
            return None

        if hr_max is None:
            hr_max = self.get_observed_hr_max()
        if hr_max is None:
            return None

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
        per_exercise: dict[str, dict] = {}
        if samples:
            for block in hr_matching.exercise_blocks(set_records_by_exercise):
                blk = hr_matching.samples_for_block(samples, block["start"], block["end"])
                if not blk:
                    continue
                blk_zones = hr_load.seconds_in_zone_from_samples(blk, hr_max)
                hrs = [hr for _, hr in blk]
                per_exercise[str(block["exercise_idx"])] = {
                    "edwards_load": hr_load.edwards_load(blk_zones),
                    "avg_hr": round(sum(hrs) / len(hrs), 1),
                    "max_hr": max(hrs),
                    "minutes": round(sum(blk_zones.values()) / 60.0, 1),
                }

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
        sheets.upsert_row_by_key(
            self._session_hr_ws(), key_col=1, key_value=row["date"], row_values=values)

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

    def sync_session_hr_for_date(self, d: date, hr_rest: float | None = None) -> bool:
        """Compute + persist HR load for the session logged on `d`. False when
        there's no session, no timestamps, or no matching Garmin activity —
        all ordinary "fall back to RPE" outcomes, not errors."""
        # Narrow window deliberately: this runs on page open, and
        # get_recent_sessions is a full Notion query per call.
        lookback = max(2, (date.today() - d).days + 2)
        sessions_on_day = [
            s for s in self.get_recent_sessions(days=lookback) if s.session_date == str(d)
        ]
        if not sessions_on_day:
            return False
        session = sessions_on_day[0]
        by_exercise = {
            i: (ex.sets or []) for i, ex in enumerate(session.exercises)
        }
        summary = self.compute_session_hr(
            d, by_exercise,
            duration_minutes=float(session.duration_minutes or 0),
            hr_rest=hr_rest,
        )
        if not summary:
            return False
        self.save_session_hr(summary)
        return True

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
        sheets.upsert_row_by_key(
            self._garmin_sleep_stages_ws(), key_col=1, key_value=str(row["date"]), row_values=values)

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
        sheets.rewrite_worksheet(worksheet, header, rows)
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
                "contiguous": str(r.get("movement_contiguous", "")).upper() != "FALSE",
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
            main = biometrics.pick_main_sleep_period(entries)
            if main is None or not str(main.get("sleep_phase_30_sec") or "").strip():
                continue
            out[day] = {**main, "periods_on_day": len(entries)}
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
            main = biometrics.pick_main_sleep_period(entries)
            if main is None:
                continue
            out[day] = {
                "period_type": main.get("type") or "",
                "period_index": _float_or_none(main.get("period")),
                "periods_on_day": len(entries),
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
        sheets.upsert_row_by_key(
            self._sleep_fusion_ws(), key_col=1, key_value=str(row["date"]), row_values=values)

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
        sheets.rewrite_worksheet(ws, _SLEEP_FUSION_HEADER, rows)
        return counts

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
            sheets.upsert_row_by_key(ws, key_col=1, key_value=str(d), row_values=values)
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
            sheets.upsert_row_by_key(ws, key_col=1, key_value=row["activity_id"], row_values=values)
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
        return bool(self.config.oura_token)

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
        that id column, by construction of every _OURA_*_HEADER above)."""
        entries = oura.get_collection(token, endpoint, start, end)
        for entry in entries:
            row = row_mapper(entry)
            values = [row.get(k, "") for k in header]
            sheets.upsert_row_by_key(worksheet, key_col=1, key_value=str(row[header[0]]), row_values=values)
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
        has never run). app.py's cached wrapper checks this before paying
        for a full Oura pull + the per-row Sheets upserts underneath it."""
        last = self.oura_last_synced()
        if last is None:
            return True
        return (now or datetime.now()) - last >= timedelta(hours=hours)

    def mark_oura_synced(self, when: datetime | None = None) -> None:
        data = local_cache.read()
        data["oura_last_synced"] = (when or datetime.now()).isoformat()
        local_cache.write(data)

    def sync_oura_all(self, days: int = 7, today: date | None = None) -> dict:
        """Pulls every configured Oura data type for the last `days` days
        (inclusive of today) and upserts each into its own Sheet tab — Oura
        Daily keyed by date, the 4 event tabs keyed by their own id, so
        re-running this (whether the 2-hour automatic trigger or the manual
        weekly button) never duplicates a row, only refreshes existing ones.
        Raises RuntimeError if Oura isn't configured, or whatever `requests`
        raises on a real API failure — callers (views/sync.py, app.py's
        cached wrapper) decide how to surface that. Returns
        {tab_name: rows_written}."""
        token = self._oc
        if token is None:
            raise RuntimeError("Oura is not configured — add OURA_TOKEN to .streamlit/secrets.toml.")
        today = today or date.today()
        start = (today - timedelta(days=days - 1)).isoformat()
        end = today.isoformat()

        by_date: dict[str, dict] = {}
        for endpoint in _OURA_DAILY_ENDPOINTS:
            for entry in oura.get_collection(token, endpoint, start, end):
                d = entry.get("day")
                if d:
                    by_date.setdefault(d, {})[endpoint] = entry
        daily_ws = self._oura_daily_ws()
        for d, group in by_date.items():
            row = self._oura_daily_row(d, group)
            values = [row.get(k, "") for k in _OURA_DAILY_HEADER]
            sheets.upsert_row_by_key(daily_ws, key_col=1, key_value=d, row_values=values)

        result = {"daily": len(by_date)}
        for key, endpoint, ws_getter, header, mapper in self._oura_event_specs():
            result[key] = self._sync_oura_events(
                token, endpoint, start, end, ws_getter(), header, mapper,
            )
        return result

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
            raise RuntimeError("Oura is not configured — add OURA_TOKEN to .streamlit/secrets.toml.")

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
            sheets.append_rows(ws, values)
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
            sheets.rewrite_worksheet(ws, header, values)
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
