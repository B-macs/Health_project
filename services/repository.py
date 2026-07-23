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
import uuid
from datetime import date, datetime, timedelta

from services import biometrics
from services import content_weighting
from services import dashboard
from services import models
from services import sessions as training_sessions
from services.clients import garmin
from services.clients import local_cache
from services.clients import notion
from services.clients import oura
from services.clients import sheets
from services.config import Config

_GARMIN_DAILY_HEADER = [
    "date", "steps", "resting_hr", "avg_stress", "sleep_score",
    "sleep_hours", "calories_total", "min_hr", "max_hr", "hrv_ms",
]
_GARMIN_ACTIVITY_HEADER = [
    "activity_id", "date", "name", "type", "start_time_local",
    "duration_minutes", "distance_km", "avg_hr", "max_hr", "calories",
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
    "activity_score", "steps", "activity_high_time", "activity_medium_time",
    "activity_low_time", "activity_sedentary_time", "activity_met_minutes",
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
    "sleep_id", "day", "type", "bedtime_start", "bedtime_end",
    "total_sleep_duration", "time_in_bed", "awake_time", "deep_sleep_duration",
    "light_sleep_duration", "rem_sleep_duration", "efficiency", "latency",
    "average_heart_rate", "lowest_heart_rate", "average_hrv", "average_breath",
    "restless_periods",
]
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
    "date", "readiness_score", "sleep_pct", "strain",
]


class Repository:
    def __init__(self, config: Config):
        self.config = config
        self._notion_client = None
        self._sheets_client = None
        self._garmin_client_obj = None
        self._garmin_login_attempted = False
        self._oura_token_obj = None

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

    def save_check_in(self, record: models.CheckInRecord) -> None:
        notion.create_page(
            self._nc, self.config.notion_db_readiness,
            properties={
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
            },
        )

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

    def save_training_set(self, training_log_id: str, set_number: int, reps_completed: int,
                           weight_kg: float, rest_time_seconds: int,
                           time_under_tension_seconds: int, movement_velocity: str) -> None:
        """Append one set to the Sets JSON on an existing training log page."""
        if not training_log_id:
            return
        page = self._nc.pages.retrieve(training_log_id)
        existing_json = notion.get_property(page, "Sets", "rich_text") or "[]"
        try:
            existing_sets = json.loads(existing_json)
        except Exception:
            existing_sets = []
        existing_sets.append({
            "set_num": set_number, "reps": reps_completed, "weight": weight_kg,
            "rest": rest_time_seconds, "tut": time_under_tension_seconds,
            "velocity": movement_velocity,
        })
        notion.update_page(self._nc, training_log_id, properties={
            "Sets": notion.rich_text(json.dumps(existing_sets)),
        })

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
        supplementary) session must never mark the plan day itself as done."""
        pages = self._query(
            self.config.notion_db_training,
            filter_={"and": [
                {"property": "Session Date", "date": {"equals": str(d)}},
                {"property": "Type", "select": {"does_not_equal": "Yoga"}},
            ]},
        )
        return len(pages) > 0

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
        raw = self.get_config_value("phases")
        if not raw:
            return []
        try:
            return [models.Phase(**p) for p in json.loads(raw)]
        except Exception:
            return []

    def set_phases(self, phases: list[models.Phase], today: date | None = None) -> None:
        payload = [
            {"phase_number": p.phase_number, "name": p.name, "start_date": p.start_date,
             "length_days": p.length_days, "status": p.status}
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
        dict keys) — the Sync page's raw-passthrough preview table."""
        return sheets.get_all_records(self._sc, self.config.google_sheets_id)

    def _sheets_biometric_records(self) -> list[models.BiometricRecord]:
        """Every row in Sheet1, mapped once — the single place that knows the
        Sheets column names. Previously duplicated independently in
        sync_sheets.py (field name `sleep_duration_hours`) and views/sync.py's
        own preview-table loop (field name `sleep_hours` for the same data —
        the two had already drifted; see REFACTOR_NOTES.md). Consolidated here
        and standardized on `sleep_duration_hours`, matching what the engine
        actually consumes."""
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
        rows = sheets.get_worksheet_records(self._garmin_daily_ws())
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
        rows = sheets.get_worksheet_records(self._oura_daily_ws())
        return {
            str(r["date"]): (r.get("steps") or None)
            for r in rows if r.get("date") and start <= str(r["date"]) <= end
        }

    def _oura_sleep_metrics_by_date(self, start: str, end: str) -> dict[str, dict]:
        rows = sheets.get_worksheet_records(self._oura_sleep_periods_ws())
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
            }
        return out

    def _garmin_metrics_by_date(self, start: str, end: str) -> dict[str, dict]:
        rows = sheets.get_worksheet_records(self._garmin_daily_ws())
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
        services.readiness.compute_readiness alongside HRV/RHR/Sleep."""
        rows = sheets.get_worksheet_records(self._oura_daily_ws())
        return {
            str(r["date"]): {
                "body_temperature":      r.get("readiness_body_temperature") or None,
                "recovery_index":        r.get("readiness_recovery_index") or None,
                "previous_day_activity": r.get("readiness_previous_day_activity") or None,
            }
            for r in rows if r.get("date") and start <= str(r["date"]) <= end
        }

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
        index, previous day activity) and alcohol units from the morning
        check-in are attached as a passthrough after blending — neither is
        part of the Oura/Garmin weighted-average fields above (alcohol isn't
        even a wearable reading, it's self-reported)."""
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
        return sheets.get_or_create_worksheet(
            self._sc, self.config.google_sheets_id,
            sheets.BIOMETRIC_BLEND_WORKSHEET, _BIOMETRIC_BLEND_HEADER,
        )

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
        rows = sheets.get_worksheet_records(self._biometric_blend_ws())
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
    #  window) and on-demand from the Sync page's "Backfill full history"
    #  button (wide window) — same pattern as Biometric Blend.
    # ─────────────────────────────────────────────────────────────────────

    def _metrics_history_ws(self):
        return sheets.get_or_create_worksheet(
            self._sc, self.config.google_sheets_id,
            sheets.METRICS_HISTORY_WORKSHEET, _METRICS_HISTORY_HEADER,
        )

    def _metrics_history_row(self, snapshot: dict) -> dict:
        return {
            "date": snapshot["date"],
            "readiness_score": snapshot["readiness_score"] if snapshot["readiness_score"] is not None else "",
            "sleep_pct": snapshot["sleep_pct"] if snapshot["sleep_pct"] is not None else "",
            "strain": snapshot["strain"] if snapshot["strain"] is not None else "",
        }

    def upsert_metrics_history_row(self, snapshot: dict) -> None:
        """snapshot: {"date": ISO str, "readiness_score", "sleep_pct", "strain"}
        (services.dashboard.compute_daily_metrics_snapshot's shape, plus a
        "date" key) — writes one day into the Metrics History tab, keyed by
        date (idempotent, same upsert-by-date pattern as Biometric Blend)."""
        row = self._metrics_history_row(snapshot)
        values = [row.get(k, "") for k in _METRICS_HISTORY_HEADER]
        sheets.upsert_row_by_key(
            self._metrics_history_ws(), key_col=1, key_value=snapshot["date"], row_values=values,
        )

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
        truncated by an under-fetched window."""
        today = today or date.today()
        bio_rows = [dataclasses.asdict(r) for r in self.get_biometric_rolling(days=days + 60, today=today)]
        au_rows = self.get_daily_session_au_weighted(days=days + 28, today=today)
        stage = self.get_current_stage()

        written = 0
        for i in range(days):
            d = today - timedelta(days=i)
            snapshot = dashboard.compute_daily_metrics_snapshot(d, bio_rows, au_rows, stage)
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
        rows = sheets.get_worksheet_records(self._metrics_history_ws())
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
                "strain": r.get("strain") or None,
            })
        return sorted(out, key=lambda r: r["date"])

    # ─────────────────────────────────────────────────────────────────────
    #  Google Sheets — Weekly Rollup
    # ─────────────────────────────────────────────────────────────────────

    def _weekly_rollup_ws(self):
        return sheets.get_or_create_weekly_rollup_worksheet(
            self._sc, self.config.google_sheets_id, _WEEKLY_ROLLUP_HEADER,
        )

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
        return sheets.get_or_create_worksheet(
            self._sc, self.config.google_sheets_id,
            sheets.GARMIN_DAILY_WORKSHEET, _GARMIN_DAILY_HEADER,
        )

    def _garmin_activities_ws(self):
        return sheets.get_or_create_worksheet(
            self._sc, self.config.google_sheets_id,
            sheets.GARMIN_ACTIVITIES_WORKSHEET, _GARMIN_ACTIVITY_HEADER,
        )

    def _garmin_daily_row(self, client, d: date) -> dict:
        """Field names here are Garmin's well-known (but unofficial, and
        occasionally-shifting) daily-summary/sleep/stress JSON shape. Every
        lookup is defensive — a missing/renamed key yields a blank cell
        rather than breaking the whole sync."""
        summary = garmin.get_daily_summary(client, d)
        sleep = garmin.get_sleep_data(client, d)
        stress = garmin.get_stress_data(client, d)
        hrv = garmin.get_hrv_data(client, d)

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

    def sync_garmin_daily(self, days: int = 7, today: date | None = None) -> int:
        """Pull the last `days` days of Garmin daily wellness metrics and
        upsert each into the Garmin Daily sheet tab, keyed by date. Returns
        the number of days synced. Raises RuntimeError if Garmin isn't
        configured, or whatever garminconnect raises on a real login/API
        failure — the caller (views/sync.py) surfaces that as an error."""
        client = self._gc
        if client is None:
            raise RuntimeError(
                "Garmin is not configured — add GARMIN_EMAIL/GARMIN_PASSWORD "
                "to .streamlit/secrets.toml."
            )
        today = today or date.today()
        ws = self._garmin_daily_ws()
        for delta in range(days):
            d = today - timedelta(days=delta)
            row = self._garmin_daily_row(client, d)
            values = [row.get(k, "") for k in _GARMIN_DAILY_HEADER]
            sheets.upsert_row_by_key(ws, key_col=1, key_value=str(d), row_values=values)
        return days

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
        except Exception as exc:
            return False, str(exc)

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
        return sheets.get_or_create_worksheet(
            self._sc, self.config.google_sheets_id, sheets.OURA_DAILY_WORKSHEET, _OURA_DAILY_HEADER,
        )

    def _oura_workouts_ws(self):
        return sheets.get_or_create_worksheet(
            self._sc, self.config.google_sheets_id, sheets.OURA_WORKOUTS_WORKSHEET, _OURA_WORKOUT_HEADER,
        )

    def _oura_sleep_periods_ws(self):
        return sheets.get_or_create_worksheet(
            self._sc, self.config.google_sheets_id, sheets.OURA_SLEEP_PERIODS_WORKSHEET, _OURA_SLEEP_PERIOD_HEADER,
        )

    def _oura_sessions_ws(self):
        return sheets.get_or_create_worksheet(
            self._sc, self.config.google_sheets_id, sheets.OURA_SESSIONS_WORKSHEET, _OURA_SESSION_HEADER,
        )

    def _oura_rest_mode_ws(self):
        return sheets.get_or_create_worksheet(
            self._sc, self.config.google_sheets_id, sheets.OURA_REST_MODE_WORKSHEET, _OURA_REST_MODE_HEADER,
        )

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
            "activity_score": activity.get("score"),
            "steps": activity.get("steps"),
            "activity_high_time": activity.get("high_activity_time"),
            "activity_medium_time": activity.get("medium_activity_time"),
            "activity_low_time": activity.get("low_activity_time"),
            "activity_sedentary_time": activity.get("sedentary_time"),
            "activity_met_minutes": activity.get("average_met_minutes"),
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
        """Scalar fields only — deliberately excludes the embedded heart_rate/
        hrv/movement_30_sec time-series and the sleep_phase_5_min hypnogram
        string (same high-volume exclusion as the top-level heartrate endpoint)."""
        return {
            "sleep_id": s.get("id", ""),
            "day": s.get("day", ""),
            "type": s.get("type", ""),
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
        }

    def _oura_session_row(self, s: dict) -> dict:
        """Scalar fields only — excludes embedded heart_rate/heart_rate_
        variability time-series, same exclusion as everywhere else here.
        Unverified against real data (this account has no sessions logged
        yet) — field names are Oura's documented schema; defensive .get()
        throughout means a renamed/missing field blanks that cell only."""
        return {
            "session_id": s.get("id", ""),
            "day": s.get("day", ""),
            "type": s.get("type", ""),
            "start_datetime": s.get("start_datetime", ""),
            "end_datetime": s.get("end_datetime", ""),
            "mood": s.get("mood", ""),
            "motion_count": s.get("motion_count"),
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

        return {
            "daily": len(by_date),
            "workouts": self._sync_oura_events(
                token, "workout", start, end, self._oura_workouts_ws(),
                _OURA_WORKOUT_HEADER, self._oura_workout_row,
            ),
            "sleep_periods": self._sync_oura_events(
                token, "sleep", start, end, self._oura_sleep_periods_ws(),
                _OURA_SLEEP_PERIOD_HEADER, self._oura_sleep_period_row,
            ),
            "sessions": self._sync_oura_events(
                token, "session", start, end, self._oura_sessions_ws(),
                _OURA_SESSION_HEADER, self._oura_session_row,
            ),
            "rest_mode_periods": self._sync_oura_events(
                token, "rest_mode_period", start, end, self._oura_rest_mode_ws(),
                _OURA_REST_MODE_HEADER, self._oura_rest_mode_row,
            ),
        }


_WEEKLY_ROLLUP_HEADER = [
    "week_start", "week_end", "phase", "scheduled", "completed", "ratio", "status", "computed_at",
]


def _sheet_date(val) -> str | None:
    try:
        return str(val).split(" ")[0].strip() or None
    except Exception:
        return None


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
