"""
db.py -- Notion Database Backend.

All health and training data is stored in Notion databases via the Notion API.
Function signatures and return structures are identical to the previous SQLite
version so no engine, stats, rules, or AI code requires changes.

Required environment variables (set in .streamlit/secrets.toml or OS env):
    NOTION_API_KEY       -- Internal integration secret token
    NOTION_DB_READINESS  -- Daily Readiness database ID
    NOTION_DB_TRAINING   -- Training Log database ID
    NOTION_DB_BIOMETRICS -- Daily Biometrics database ID
    NOTION_DB_CONFIG     -- App Config database ID

Rate limit: Notion API allows ~3 requests/second. Pagination is handled
automatically by _query_all().
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from notion_client import Client
from notion_client.errors import APIResponseError


# ─────────────────────────────────────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────────────────────────────────────

def _secret(key: str) -> str:
    """Read a secret from OS environment, then fall back to Streamlit secrets."""
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val:
            return val
    except Exception:
        pass
    raise EnvironmentError(
        f"'{key}' not found. Set it in your OS environment or .streamlit/secrets.toml."
    )


def _client() -> Client:
    return Client(auth=_secret("NOTION_API_KEY"))


def _dbs() -> dict[str, str]:
    return {
        "readiness":  _secret("NOTION_DB_READINESS"),
        "training":   _secret("NOTION_DB_TRAINING"),
        "biometrics": _secret("NOTION_DB_BIOMETRICS"),
        "config":     _secret("NOTION_DB_CONFIG"),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Notion Property Builders
# ─────────────────────────────────────────────────────────────────────────────

def _title(text: str) -> dict:
    return {"title": [{"text": {"content": str(text or "")[:2000]}}]}


def _text(text: str) -> dict:
    return {"rich_text": [{"text": {"content": str(text or "")[:2000]}}]}


def _num(val) -> dict:
    return {"number": float(val) if val is not None else None}


def _sel(name: str) -> dict:
    return {"select": {"name": str(name)}} if name else {"select": None}


def _msel(names: list) -> dict:
    return {"multi_select": [{"name": str(n)[:100]} for n in (names or [])]}


def _date(d) -> dict:
    return {"date": {"start": str(d)}} if d else {"date": None}


def _check(val: bool) -> dict:
    return {"checkbox": bool(val)}


# ─────────────────────────────────────────────────────────────────────────────
#  Notion Property Extractors
# ─────────────────────────────────────────────────────────────────────────────

def _get(page: dict, name: str, kind: str) -> Any:
    """Extract a typed value from a Notion page property."""
    prop = page.get("properties", {}).get(name)
    if not prop:
        return None
    if kind == "title":
        return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    if kind == "rich_text":
        return "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
    if kind == "number":
        return prop.get("number")
    if kind == "select":
        s = prop.get("select")
        return s.get("name") if s else None
    if kind == "multi_select":
        return [o.get("name") for o in prop.get("multi_select", [])]
    if kind == "date":
        d = prop.get("date")
        return d.get("start") if d else None
    if kind == "checkbox":
        return prop.get("checkbox", False)
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Pagination Helper
# ─────────────────────────────────────────────────────────────────────────────

def _query_all(
    db_id: str,
    filter_: dict = None,
    sorts: list = None,
    page_size: int = 100,
) -> list[dict]:
    """Fetch ALL pages from a Notion database, following pagination cursors."""
    notion = _client()
    results: list[dict] = []
    kwargs: dict = {"database_id": db_id, "page_size": page_size}
    if filter_:
        kwargs["filter"] = filter_
    if sorts:
        kwargs["sorts"] = sorts

    while True:
        try:
            resp = notion.databases.query(**kwargs)
        except APIResponseError as exc:
            if exc.status == 429:          # rate-limited
                time.sleep(1)
                resp = notion.databases.query(**kwargs)
            else:
                raise
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        kwargs["start_cursor"] = resp["next_cursor"]

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  Daily Readiness
# ─────────────────────────────────────────────────────────────────────────────

def save_daily_readiness(
    current_condition: str,
    tightness_score: int,
    pain_score: int,
    anatomical_locations: list,
    sensation_tags: list,
    subjective_tightness: str,
    alcohol_units: float,
    travel_flag: bool,
    psych_stress_score: int,
) -> None:
    today = str(date.today())
    _client().pages.create(
        parent={"database_id": _dbs()["readiness"]},
        properties={
            "Entry":         _title(f"{today} Morning Check-In"),
            "Date":          _date(today),
            "Condition":     _sel(current_condition),
            "Tightness":     _num(tightness_score),
            "Pain":          _num(pain_score),
            "Body Areas":    _msel(anatomical_locations or []),
            "Sensations":    _msel(sensation_tags or []),
            "Note":          _text(subjective_tightness or ""),
            "Alcohol Units": _num(alcohol_units or 0),
            "Travel":        _check(bool(travel_flag)),
            "Stress Level":  _num(psych_stress_score),
        },
    )


def get_recent_readiness(days: int = 60) -> list[dict]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    pages = _query_all(
        _dbs()["readiness"],
        filter_={"property": "Date", "date": {"on_or_after": cutoff}},
        sorts=[{"property": "Date", "direction": "descending"}],
    )
    out = []
    for p in pages:
        out.append({
            "date":                  _get(p, "Date",         "date"),
            "current_condition":     _get(p, "Condition",    "select"),
            "tightness_score":       _get(p, "Tightness",    "number"),
            "pain_score":            _get(p, "Pain",         "number"),
            "anatomical_locations":  json.dumps(_get(p, "Body Areas",  "multi_select") or []),
            "sensation_tags":        json.dumps(_get(p, "Sensations",   "multi_select") or []),
            "subjective_tightness":  _get(p, "Note",         "rich_text"),
            "alcohol_units":         _get(p, "Alcohol Units","number"),
            "travel_flag":           1 if _get(p, "Travel",  "checkbox") else 0,
            "psych_stress_score":    _get(p, "Stress Level", "number"),
        })
    return out


def get_unparsed_readiness() -> list[dict]:
    pages = _query_all(
        _dbs()["readiness"],
        filter_={
            "and": [
                {"property": "Parsed", "checkbox":  {"equals": False}},
                {"property": "Note",   "rich_text": {"is_not_empty": True}},
            ]
        },
        sorts=[{"property": "Date", "direction": "ascending"}],
    )
    out = []
    for p in pages:
        note = _get(p, "Note", "rich_text") or ""
        if note.strip():
            out.append({
                "id":                   p["id"],
                "timestamp":            _get(p, "Date",      "date"),
                "subjective_tightness": note,
                "tightness_score":      _get(p, "Tightness", "number"),
                "pain_score":           _get(p, "Pain",      "number"),
            })
    return out


def update_readiness_ai(
    row_id: str,
    severity: float,
    body_parts: list,
    sensation_type: list,
    warning_level: str,
) -> None:
    _client().pages.update(
        page_id=row_id,
        properties={
            "Parsed Severity":   _num(severity),
            "Parsed Areas":      _text(json.dumps(body_parts or [])),
            "Parsed Sensations": _text(json.dumps(sensation_type or [])),
            "Warning":           _sel(warning_level),
            "Parsed":            _check(True),
        },
    )


def get_parsed_readiness(limit: int = 90) -> list[dict]:
    """Parsed readiness rows for the Insights tightness map tab."""
    pages = _query_all(
        _dbs()["readiness"],
        filter_={"property": "Parsed", "checkbox": {"equals": True}},
        sorts=[{"property": "Date", "direction": "descending"}],
    )
    out = []
    for p in pages[:limit]:
        out.append({
            "date":                  _get(p, "Date",              "date"),
            "tightness_score":       _get(p, "Tightness",         "number"),
            "pain_score":            _get(p, "Pain",              "number"),
            "ai_body_parts":         _get(p, "Parsed Areas",      "rich_text"),
            "ai_sensation_type":     _get(p, "Parsed Sensations", "rich_text"),
            "ai_tightness_severity": _get(p, "Parsed Severity",   "number"),
            "ai_warning_level":      _get(p, "Warning",           "select"),
        })
    return out


def get_pain_free_streak() -> int:
    pages = _query_all(
        _dbs()["readiness"],
        sorts=[{"property": "Date", "direction": "descending"}],
    )
    streak = 0
    for p in pages:
        pain = _get(p, "Pain", "number") or 0
        if pain == 0:
            streak += 1
        else:
            break
    return streak


def get_avg_tightness(days: int = 14) -> float:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    pages = _query_all(
        _dbs()["readiness"],
        filter_={"property": "Date", "date": {"on_or_after": cutoff}},
    )
    vals = [
        _get(p, "Tightness", "number")
        for p in pages
        if _get(p, "Tightness", "number") is not None
    ]
    return round(sum(vals) / len(vals), 1) if vals else 0.0


# ─────────────────────────────────────────────────────────────────────────────
#  Training Log
# ─────────────────────────────────────────────────────────────────────────────

def create_training_session(
    session_date,
    duration_minutes: int,
    session_rpe: int,
) -> dict:
    """
    Generate a unique session identifier bundle.
    Returns a dict — callers pass session_info["session_id"] where an int ID was used before.
    No API call: sessions are denormalised into each training log entry.
    """
    return {
        "session_id":       f"{session_date}-{uuid.uuid4().hex[:8]}",
        "session_date":     str(session_date),
        "duration_minutes": int(duration_minutes),
        "session_rpe":      int(session_rpe),
        "session_au":       float(session_rpe * duration_minutes),
    }


def save_training_exercise(
    session_id,               # str (from create_training_session) or dict (ignored — backwards compat)
    movement_name: str,
    movement_type: str,
    planned_sets: int,
    planned_reps: int,
    rpe: int,
    sets: list = None,
    note: str = "",
    session_date=None,
    session_duration_minutes: int = 0,
    session_rpe: int = 0,
    session_au: float = 0.0,
) -> str:
    """
    Create a training log page in Notion.
    Sets data is serialised as JSON into the Sets property.
    Returns the Notion page ID (used for subsequent updates).
    """
    # If session_id is the old-style int (backwards compat during transition), stringify it
    sid = str(session_id) if not isinstance(session_id, dict) else session_id.get("session_id", "")

    # Infer session_date from session_id string if not supplied explicitly
    if session_date is None and sid and "-" in sid:
        parts = sid.split("-")
        if len(parts) >= 3:
            try:
                session_date = "-".join(parts[:3])
            except Exception:
                session_date = str(date.today())

    sets_json = json.dumps(sets or [])
    page = _client().pages.create(
        parent={"database_id": _dbs()["training"]},
        properties={
            "Movement":          _title(movement_name),
            "Session Date":      _date(session_date or str(date.today())),
            "Session ID":        _text(sid),
            "Type":              _sel(movement_type),
            "Planned Sets":      _num(planned_sets),
            "Planned Reps":      _num(planned_reps),
            "Exercise RPE":      _num(rpe),
            "Sets":              _text(sets_json),
            "Notes":             _text(note or ""),
            "Session Duration":  _num(session_duration_minutes),
            "Session RPE":       _num(session_rpe),
            "Session AU":        _num(session_au),
        },
    )
    return page["id"]


def save_training_set(
    training_log_id: str,
    set_number: int,
    reps_completed: int,
    weight_kg: float,
    rest_time_seconds: int,
    time_under_tension_seconds: int,
    movement_velocity: str,
) -> None:
    """
    Append one set to the Sets JSON on an existing training log page.
    Called when sets are logged one-at-a-time (legacy flow).
    """
    if not training_log_id:
        return
    notion = _client()
    page = notion.pages.retrieve(training_log_id)
    existing_json = _get(page, "Sets", "rich_text") or "[]"
    try:
        existing_sets = json.loads(existing_json)
    except Exception:
        existing_sets = []

    existing_sets.append({
        "set_num":  set_number,
        "reps":     reps_completed,
        "weight":   weight_kg,
        "rest":     rest_time_seconds,
        "tut":      time_under_tension_seconds,
        "velocity": movement_velocity,
    })
    notion.pages.update(
        page_id=training_log_id,
        properties={"Sets": _text(json.dumps(existing_sets))},
    )


def save_session_notes(training_log_id: str, raw_text: str) -> None:
    """Append raw_text to the Notes field of an existing training log page."""
    if not training_log_id or not (raw_text or "").strip():
        return
    notion = _client()
    page  = notion.pages.retrieve(training_log_id)
    existing = _get(page, "Notes", "rich_text") or ""
    combined = (existing.strip() + "\n\n" + raw_text.strip()).strip() if existing.strip() else raw_text.strip()
    notion.pages.update(
        page_id=training_log_id,
        properties={"Notes": _text(combined[:2000])},
    )


def get_recent_sessions(days: int = 60) -> list[dict]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    pages = _query_all(
        _dbs()["training"],
        filter_={"property": "Session Date", "date": {"on_or_after": cutoff}},
        sorts=[{"property": "Session Date", "direction": "descending"}],
    )
    out = []
    for p in pages:
        sets_raw = _get(p, "Sets", "rich_text") or "[]"
        try:
            sets = json.loads(sets_raw)
        except Exception:
            sets = []
        actual_sets  = len(sets)
        total_volume = round(
            sum((s.get("reps") or 0) * (s.get("weight") or 0.0) for s in sets), 1
        )
        out.append({
            "session_date":             _get(p, "Session Date",    "date"),
            "session_duration_minutes": _get(p, "Session Duration","number"),
            "session_rpe":              _get(p, "Session RPE",     "number"),
            "session_au":               _get(p, "Session AU",      "number"),
            "movement_name":            _get(p, "Movement",        "title"),
            "movement_type":            _get(p, "Type",            "select"),
            "planned_sets":             _get(p, "Planned Sets",    "number"),
            "planned_reps":             _get(p, "Planned Reps",    "number"),
            "exercise_rpe":             _get(p, "Exercise RPE",    "number"),
            "actual_sets":              actual_sets,
            "total_volume_kg":          total_volume,
        })
    return out


def get_daily_session_au(days: int = 28) -> list[dict]:
    """Return [{date, total_au}] for ACWR — one entry per calendar day."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    pages = _query_all(
        _dbs()["training"],
        filter_={"property": "Session Date", "date": {"on_or_after": cutoff}},
    )
    # Deduplicate by session_id so each session's AU is counted once
    seen_sessions: set[str] = set()
    au_by_date: dict[str, float] = {}
    for p in pages:
        sid = _get(p, "Session ID",   "rich_text") or ""
        d   = _get(p, "Session Date", "date") or ""
        au  = _get(p, "Session AU",   "number") or 0.0
        if sid and sid not in seen_sessions:
            seen_sessions.add(sid)
            au_by_date[d] = au_by_date.get(d, 0.0) + au

    return [{"date": d, "total_au": round(v, 1)} for d, v in sorted(au_by_date.items())]


def get_unparsed_session_notes() -> list[dict]:
    """Training log pages that have Notes text but no parsed summary yet."""
    pages = _query_all(
        _dbs()["training"],
        filter_={
            "and": [
                {"property": "Notes",        "rich_text": {"is_not_empty": True}},
                {"property": "Note Summary", "rich_text": {"is_empty": True}},
            ]
        },
        sorts=[{"property": "Session Date", "direction": "ascending"}],
    )
    out = []
    for p in pages:
        note = _get(p, "Notes", "rich_text") or ""
        if note.strip():
            out.append({
                "id":            p["id"],
                "raw_text":      note,
                "timestamp":     _get(p, "Session Date", "date"),
                "movement_name": _get(p, "Movement",     "title"),
                "session_date":  _get(p, "Session Date", "date"),
            })
    return out


def update_session_note_ai(
    note_id: str,
    summary: str,
    sentiment_score: float,
    flagged_body_parts: list,
    warning_level: str,
) -> None:
    _client().pages.update(
        page_id=note_id,
        properties={
            "Note Summary":  _text(summary or ""),
            "Sentiment":     _num(sentiment_score),
            "Flagged Areas": _text(json.dumps(flagged_body_parts or [])),
            "Warning":       _sel(warning_level),
        },
    )


def get_recent_raw_notes(limit: int = 20) -> list[dict]:
    """Recent training log notes — for MRI Intelligence keyword analysis."""
    pages = _query_all(
        _dbs()["training"],
        filter_={"property": "Notes", "rich_text": {"is_not_empty": True}},
        sorts=[{"property": "Session Date", "direction": "descending"}],
    )
    out = []
    for p in pages[:limit]:
        out.append({
            "raw_text":           _get(p, "Notes",        "rich_text"),
            "ai_summary":         _get(p, "Note Summary", "rich_text"),
            "flagged_body_parts": _get(p, "Flagged Areas","rich_text"),
            "warning_level":      _get(p, "Warning",      "select"),
            "session_date":       _get(p, "Session Date", "date"),
        })
    return out


def get_flagged_entries() -> list[dict]:
    """All entries with warning level 'flag' or 'monitor' across training and readiness."""
    results: list[dict] = []

    # Training log warnings
    for p in _query_all(
        _dbs()["training"],
        filter_={"or": [
            {"property": "Warning", "select": {"equals": "flag"}},
            {"property": "Warning", "select": {"equals": "monitor"}},
        ]},
        sorts=[{"property": "Session Date", "direction": "descending"}],
    )[:50]:
        results.append({
            "source":        "session_note",
            "timestamp":     _get(p, "Session Date", "date"),
            "summary":       _get(p, "Note Summary", "rich_text"),
            "warning_level": _get(p, "Warning",      "select"),
            "body_parts":    _get(p, "Flagged Areas","rich_text") or "[]",
            "movement_name": _get(p, "Movement",     "title"),
            "session_date":  _get(p, "Session Date", "date"),
        })

    # Readiness warnings
    for p in _query_all(
        _dbs()["readiness"],
        filter_={"or": [
            {"property": "Warning", "select": {"equals": "flag"}},
            {"property": "Warning", "select": {"equals": "monitor"}},
        ]},
        sorts=[{"property": "Date", "direction": "descending"}],
    )[:50]:
        results.append({
            "source":        "readiness",
            "timestamp":     _get(p, "Date",         "date"),
            "summary":       str(_get(p, "Parsed Severity", "number") or ""),
            "warning_level": _get(p, "Warning",      "select"),
            "body_parts":    _get(p, "Parsed Areas", "rich_text") or "[]",
            "movement_name": None,
            "session_date":  None,
        })

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  Daily Biometrics
# ─────────────────────────────────────────────────────────────────────────────

def get_biometrics(days: int = 60) -> list[dict]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    pages = _query_all(
        _dbs()["biometrics"],
        filter_={"property": "Log Date", "date": {"on_or_after": cutoff}},
        sorts=[{"property": "Log Date", "direction": "descending"}],
    )
    out = []
    for p in pages:
        out.append({
            "date":                 _get(p, "Log Date",          "date"),
            "resting_heart_rate":   _get(p, "RHR",              "number"),
            "heart_rate_avg":       _get(p, "HR Average",        "number"),
            "hrv_ms":               _get(p, "HRV",              "number"),
            "sleep_duration_hours": _get(p, "Sleep Hours",       "number"),
            "sleep_deep_hours":     _get(p, "Deep Sleep Hours",  "number"),
            "active_energy_kcal":   _get(p, "Active kcal",      "number"),
            "weight_kg":            _get(p, "Weight kg",         "number"),
            "steps":                _get(p, "Steps",             "number"),
        })
    return out


def get_biometric_rolling(days: int = 28) -> list[dict]:
    """Biometric rows sorted ascending — required by traffic_light() engine."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    pages = _query_all(
        _dbs()["biometrics"],
        filter_={"property": "Log Date", "date": {"on_or_after": cutoff}},
        sorts=[{"property": "Log Date", "direction": "ascending"}],
    )
    out = []
    for p in pages:
        out.append({
            "date":                 _get(p, "Log Date",    "date"),
            "hrv_ms":               _get(p, "HRV",        "number"),
            "resting_heart_rate":   _get(p, "RHR",        "number"),
            "sleep_duration_hours": _get(p, "Sleep Hours","number"),
        })
    return out


def save_biometrics_today(
    date_str: str,
    rhr: int = None,
    hrv: float = None,
    sleep_hours: float = None,
    sleep_deep: float = None,
    active_kcal: int = None,
    weight_kg: float = None,
    steps: int = None,
) -> None:
    """Insert or update the biometric row for date_str."""
    notion  = _client()
    db_id   = _dbs()["biometrics"]
    existing = _query_all(
        db_id,
        filter_={"property": "Log Date", "date": {"equals": date_str}},
    )
    props = {
        "Entry":            _title(date_str),
        "Log Date":         _date(date_str),
        "RHR":              _num(rhr),
        "HR Average":       _num(None),
        "HRV":              _num(hrv),
        "Sleep Hours":      _num(sleep_hours),
        "Deep Sleep Hours": _num(sleep_deep),
        "Active kcal":      _num(active_kcal),
        "Weight kg":        _num(weight_kg),
        "Steps":            _num(steps),
    }
    if existing:
        notion.pages.update(page_id=existing[0]["id"], properties=props)
    else:
        notion.pages.create(parent={"database_id": db_id}, properties=props)


# ─────────────────────────────────────────────────────────────────────────────
#  App Config  (user_config + diagnostic_profile + movement risk)
# ─────────────────────────────────────────────────────────────────────────────

def _config_page(key: str) -> dict | None:
    """Return the Notion page for a config key, or None."""
    pages = _query_all(
        _dbs()["config"],
        filter_={"property": "Key", "title": {"equals": key}},
    )
    return pages[0] if pages else None


def get_current_stage() -> int:
    page = _config_page("current_stage")
    if page:
        try:
            return int(_get(page, "Value", "rich_text") or "1")
        except (TypeError, ValueError):
            pass
    return 1


def set_config(key: str, value: str) -> None:
    notion = _client()
    page  = _config_page(key)
    props = {
        "Key":     _title(key),
        "Value":   _text(str(value)),
        "Updated": _date(str(date.today())),
    }
    if page:
        notion.pages.update(page_id=page["id"], properties=props)
    else:
        notion.pages.create(parent={"database_id": _dbs()["config"]}, properties=props)


def get_config_value(key: str) -> str | None:
    """Read a single config value by key. Returns None if key not found."""
    page = _config_page(key)
    return _get(page, "Value", "rich_text") if page else None


def get_diagnostic_profile() -> dict:
    page = _config_page("diagnostic_profile")
    if page:
        raw = _get(page, "Value", "rich_text") or "{}"
        try:
            return json.loads(raw)
        except Exception:
            pass
    return {}


def save_movement_risk(
    risk_summary: str,
    flagged_movements: list,
    safe_movements: list,
    correlation_notes: str,
    model_used: str,
) -> None:
    data = {
        "timestamp":         str(datetime.now())[:19],
        "risk_summary":      risk_summary,
        "flagged_movements": json.dumps(flagged_movements or []),
        "safe_movements":    json.dumps(safe_movements or []),
        "correlation_notes": correlation_notes,
        "model_used":        model_used,
    }
    set_config("latest_movement_risk", json.dumps(data))


def get_latest_movement_risk() -> dict:
    page = _config_page("latest_movement_risk")
    if page:
        raw = _get(page, "Value", "rich_text") or "{}"
        try:
            return json.loads(raw)
        except Exception:
            pass
    return {}


# ─────────────────────────────────────────────────────────────────────────────
#  Macro Trend Data
# ─────────────────────────────────────────────────────────────────────────────

def get_macro_trend_data(days: int = 90) -> dict:
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    # ── Biometrics ────────────────────────────────────────────────────────────
    bio_pages = _query_all(
        _dbs()["biometrics"],
        filter_={"property": "Log Date", "date": {"on_or_after": cutoff}},
        sorts=[{"property": "Log Date", "direction": "ascending"}],
    )
    biometrics = [
        {
            "date":                  _get(p, "Log Date",         "date"),
            "hrv_ms":                _get(p, "HRV",             "number"),
            "resting_heart_rate":    _get(p, "RHR",             "number"),
            "sleep_duration_hours":  _get(p, "Sleep Hours",     "number"),
            "sleep_deep_hours":      _get(p, "Deep Sleep Hours","number"),
            "active_energy_kcal":    _get(p, "Active kcal",    "number"),
            "weight_kg":             _get(p, "Weight kg",       "number"),
            "steps":                 _get(p, "Steps",           "number"),
        }
        for p in bio_pages
    ]

    # ── Readiness — aggregate per day ─────────────────────────────────────────
    read_pages = _query_all(
        _dbs()["readiness"],
        filter_={"property": "Date", "date": {"on_or_after": cutoff}},
        sorts=[{"property": "Date", "direction": "ascending"}],
    )
    by_day: dict[str, dict] = {}
    for p in read_pages:
        d = _get(p, "Date", "date") or ""
        if d not in by_day:
            by_day[d] = {"t": [], "pain": [], "stress": [], "travel": 0, "alc": []}
        t = _get(p, "Tightness",   "number")
        n = _get(p, "Pain",        "number")
        s = _get(p, "Stress Level","number")
        a = _get(p, "Alcohol Units","number") or 0
        v = 1 if _get(p, "Travel", "checkbox") else 0
        if t is not None:  by_day[d]["t"].append(t)
        if n is not None:  by_day[d]["pain"].append(n)
        if s is not None:  by_day[d]["stress"].append(s)
        by_day[d]["alc"].append(a)
        by_day[d]["travel"] = max(by_day[d]["travel"], v)

    readiness = [
        {
            "date":          d,
            "avg_tightness": round(sum(v["t"])    / len(v["t"]),     1) if v["t"]     else None,
            "max_pain":      max(v["pain"])                              if v["pain"]  else None,
            "avg_stress":    round(sum(v["stress"])/ len(v["stress"]),1) if v["stress"]else None,
            "travel":        v["travel"],
            "avg_alcohol":   round(sum(v["alc"])   / len(v["alc"]),  1) if v["alc"]  else None,
        }
        for d, v in sorted(by_day.items())
    ]

    # ── Sessions — deduplicate by session_id ──────────────────────────────────
    train_pages = _query_all(
        _dbs()["training"],
        filter_={"property": "Session Date", "date": {"on_or_after": cutoff}},
        sorts=[{"property": "Session Date", "direction": "ascending"}],
    )
    seen: set[str] = set()
    sess_by_day: dict[str, dict] = {}
    for p in train_pages:
        sid  = _get(p, "Session ID",   "rich_text") or ""
        d    = _get(p, "Session Date", "date") or ""
        au   = _get(p, "Session AU",   "number") or 0.0
        rpe  = _get(p, "Session RPE",  "number") or 0
        if sid and sid not in seen:
            seen.add(sid)
            if d not in sess_by_day:
                sess_by_day[d] = {"au": 0.0, "rpe": []}
            sess_by_day[d]["au"] += au
            sess_by_day[d]["rpe"].append(rpe)

    sessions = [
        {
            "date":     d,
            "total_au": round(v["au"], 1),
            "avg_rpe":  round(sum(v["rpe"]) / len(v["rpe"]), 1) if v["rpe"] else None,
        }
        for d, v in sorted(sess_by_day.items())
    ]

    return {
        "biometrics":    biometrics,
        "readiness":     readiness,
        "sessions":      sessions,
        "flagged_notes": [],
        "days_requested": days,
    }
