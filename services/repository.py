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

import json
import uuid
from datetime import date, datetime, timedelta

from services import models
from services.clients import garmin
from services.clients import notion
from services.clients import oura
from services.clients import sheets
from services.config import Config

_GARMIN_DAILY_HEADER = [
    "date", "steps", "resting_hr", "avg_stress", "sleep_score",
    "sleep_hours", "calories_total", "min_hr", "max_hr",
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
                                session_au: float = 0.0, today: date | None = None) -> str:
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
        page = notion.create_page(
            self._nc, self.config.notion_db_training,
            properties={
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
            },
        )
        return page["id"]

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

    def get_biometric_rolling(self, days: int = 28, today: date | None = None) -> list[models.BiometricRecord]:
        """Last `days` days, sorted ascending by date — the shape the engine's
        traffic_light()/readiness computations expect. Also the Sync page's
        "Engine View" preview (previously its own independent, slightly
        drifted copy of this exact mapping+window)."""
        today = today or date.today()
        cutoff = (today - timedelta(days=days)).isoformat()
        today_str = str(today)
        records = [r for r in self._sheets_biometric_records() if cutoff <= r.date <= today_str]
        return sorted(records, key=lambda r: r.date)


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
    #  Archival only: does not feed services/engine.py's readiness/ACWR
    #  pipeline (that stays on Sheet1, unchanged). Used for its own Garmin
    #  Daily/Activities sheet tabs and for the run/walk training-log hook
    #  in views/training.py.
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

    def sync_garmin_daily_if_due(self, days: int = 7, today: date | None = None) -> tuple[bool, str | None]:
        """Runs sync_garmin_daily() at most once per Mon-Sun week, persisted
        via the Config DB (garmin_daily_last_synced_week) so it survives
        across Streamlit reruns/sessions/restarts. Unlike Weekly Rollup
        (cheap Notion+Sheets only, safe to re-check every 30 min),
        Garmin's API is rate-limit-sensitive — this must not fire on every
        page load. (True, None) if not configured or already synced this
        week (both "nothing to do", not an error) or on success; (False, msg)
        only on an actual sync failure. Matches services.metrics.
        sync_weekly_rollup's (ok, error) contract so callers can treat both
        the same way."""
        if not self.garmin_configured():
            return True, None
        today = today or date.today()
        week_start = str(today - timedelta(days=today.weekday()))
        try:
            if self.get_config_value("garmin_daily_last_synced_week") == week_start:
                return True, None
            self.sync_garmin_daily(days=days, today=today)
            self.set_config("garmin_daily_last_synced_week", week_start, today=today)
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
        self, window_minutes: int, now: datetime | None = None,
    ) -> tuple[float, list[dict]]:
        """Total duration (minutes) of Garmin activities that STARTED within
        the last `window_minutes` from `now` — the "just finished, pull it
        in" hook used by the training page's run/walk Complete button.
        Returns (0.0, []) if Garmin isn't configured, rather than raising —
        callers treat that the same as "no matching activity found"."""
        client = self._gc
        if client is None:
            return 0.0, []
        now = now or datetime.now()
        cutoff = now - timedelta(minutes=window_minutes)
        matched, total = [], 0.0
        for act in garmin.get_recent_activities(client, limit=10):
            start_local = act.get("startTimeLocal", "")
            try:
                start_dt = datetime.strptime(start_local, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                continue
            if start_dt >= cutoff:
                matched.append(act)
                total += (act.get("duration") or 0) / 60
        return round(total, 1), matched


    # ─────────────────────────────────────────────────────────────────────
    #  Oura — daily summary scores + workouts/sleep periods/sessions/rest
    #  mode. Archival only, same as Garmin: does not feed the readiness/ACWR
    #  engine, which keeps reading Sheet1 exactly as it does today. Raw
    #  high-volume time-series (heartrate, and the per-day series embedded
    #  in daily_activity/sleep like met.items/class_5_min/heart_rate.items)
    #  are deliberately NOT pulled — by request, to avoid 100k+ row/year
    #  Sheet growth. Only the scalar/summary fields are captured.
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
