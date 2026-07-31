"""
services/datastore.py -- builds the project's own consolidated database
(services/datastore_schema.sql) as a full copy of the app's live Notion +
Google Sheets data. This is the target of the move away from Sheets/Notion:
today it's rebuilt by reading Repository (a one-way copy, nothing writes
back yet); the next step is repointing the app itself at this datastore
(Postgres/Supabase) instead of Notion/Sheets, at which point this module's
read-and-populate logic becomes the seed/backfill path for that cutover
rather than the whole story. Framework-agnostic (zero Streamlit imports)
and, for now, read-only with respect to Notion/Sheets: every value here
comes from Repository's existing public getters -- this module has zero
knowledge of Notion property names or Sheets column names (see
services/repository.py's module docstring; that rule applies here too).

rebuild() DROPs and recreates every table (services/datastore_schema.sql
itself contains the DROP statements) then repopulates all of them inside
ONE explicit transaction, so a failure partway through (a Repository call
raising, a malformed row) rolls every table back to empty rather than
leaving some populated and others not -- see this module's own tests for
the verified behavior. That said, `executescript`'s schema reset itself
(Python's sqlite3 module implicitly commits before running a script, and
each DDL statement inside it runs in SQLite's own autocommit mode) is NOT
covered by that rollback -- calling rebuild() a second time against a
connection that already holds real data will leave that connection's
tables empty if population then fails, not restored to what they held
before this call. The "a failed rebuild never touches the last known-good
datastore file" guarantee instead comes from scripts/build_datastore.py
building into a temp file and only replacing the real path (os.replace,
atomic on the same filesystem) once rebuild() returns successfully --
deliberately layered at the script level rather than here, so this
module's tests can exercise rebuild() directly against a plain
connection (including ":memory:") without any file/temp-path machinery.

DROP-and-recreate (not DELETE-then-reinsert) is deliberate: the schema will
keep evolving as sources gain columns, and DROP+CREATE picks that up for
free every run, whereas DELETE+reinsert would need separate ALTER/migration
logic to keep pace. Every populate step reads its source UNWINDOWED (full
history, no date cutoff) -- this is meant to be a complete copy, not a
rolling recent-data cache.

PRAGMA foreign_keys is deliberately left at SQLite's OFF default -- see
datastore_schema.sql's header comment.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from services.repository import Repository

SCHEMA_PATH = Path(__file__).resolve().parent / "datastore_schema.sql"


def rebuild(repo: Repository, conn: sqlite3.Connection, now: datetime | None = None) -> dict[str, int]:
    """Rebuilds every datastore table from `repo`'s live sources, full
    history. Returns {table_name: row_count} for every populated table
    (scripts/build_datastore.py prints this). Raises -- having rolled every
    table in this call back to empty, per the module docstring -- if any
    Repository call or insert fails.

    `now`: written into datastore_meta's built_at row -- explicit, never a
    hidden datetime.now() read, per this codebase's no-buried-clock-reads
    rule."""
    now = now or datetime.now()

    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    conn.execute("BEGIN")
    try:
        counts: dict[str, int] = {}
        counts["readiness_checkins"] = _populate_readiness(repo, conn)
        (counts["training_sessions"], counts["training_exercises"],
         counts["training_sets"]) = _populate_training(repo, conn)
        counts["garmin_daily"] = _insert_rows(conn, "garmin_daily", repo.get_all_garmin_daily_rows())
        counts["garmin_activities"] = _insert_rows(conn, "garmin_activities", repo.get_all_garmin_activities_rows())
        counts["session_hr"] = _insert_rows(conn, "session_hr", repo.get_all_session_hr_rows())
        counts["oura_daily"] = _insert_rows(conn, "oura_daily", repo.get_all_oura_daily_rows())
        counts["oura_workouts"] = _insert_rows(conn, "oura_workouts", repo.get_all_oura_workouts_rows())
        counts["oura_sleep_periods"] = _insert_rows(conn, "oura_sleep_periods", repo.get_all_oura_sleep_periods_rows())
        counts["oura_sessions"] = _insert_rows(conn, "oura_sessions", repo.get_all_oura_sessions_rows())
        counts["oura_rest_mode"] = _insert_rows(conn, "oura_rest_mode", repo.get_all_oura_rest_mode_rows())
        counts["biometric_blend"] = _populate_biometric_blend(repo, conn)
        counts["metrics_history"] = _insert_rows(conn, "metrics_history", repo.get_metrics_history())
        counts["wake_time_adjustments"] = _populate_wake_time_adjustments(repo, conn)
        counts["weekly_rollup"] = _populate_weekly_rollup(repo, conn)
        counts["sheet1_legacy_biometrics"] = _populate_sheet1_legacy(repo, conn)
        counts["config"] = _insert_rows(conn, "config", repo.get_all_config_rows())

        conn.execute("INSERT INTO datastore_meta (key, value) VALUES (?, ?)", ("built_at", now.isoformat()))
        conn.execute("INSERT INTO datastore_meta (key, value) VALUES (?, ?)", ("row_counts_json", json.dumps(counts)))
        conn.commit()
        return counts
    except Exception:
        conn.rollback()
        raise


# ─── Generic insert helper ──────────────────────────────────────────────

def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """A table's own column list, read back from the schema
    rebuild()/executescript just created -- so no table's field list is
    separately hand-maintained in this module (that would just be the
    Notion-name/Sheets-name duplication mistake one level removed: DDL and
    a Python list drifting apart instead). Excludes `id`, the one
    AUTOINCREMENT surrogate key (training_sets) -- never supplied by a
    caller, always sqlite-assigned."""
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})") if row[1] != "id"]


def _insert_rows(conn: sqlite3.Connection, table: str, rows: list[dict], replace: bool = False) -> int:
    """executemany insert for the sheet-shaped tables. `rows`' dict keys
    are assumed to already match the table's own column list -- every
    Repository getter this module calls documents that contract. Blank
    Sheets cells ("") are normalized to NULL; everything else passes
    through as-is (gspread has already done int/float coercion).

    `replace`: INSERT OR REPLACE instead of plain INSERT, for the one
    table (readiness_checkins) where a pre-existing, not-yet-merged
    duplicate Notion page for the same date is a known possible
    data-quality issue (see scripts/merge_duplicate_checkins.py) rather
    than a bug in this module -- last-one-wins there rather than raising
    and rolling back the whole datastore build over it. Every other table
    here is upserted-by-key at write time by Repository already, so a
    PRIMARY KEY collision on plain INSERT is a genuine, worth-surfacing
    bug rather than something to paper over."""
    if not rows:
        return 0
    columns = _table_columns(conn, table)
    cleaned = [{c: (row.get(c) if row.get(c) != "" else None) for c in columns} for row in rows]
    verb = "INSERT OR REPLACE" if replace else "INSERT"
    placeholders = ", ".join(f":{c}" for c in columns)
    conn.executemany(f"{verb} INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", cleaned)
    return len(cleaned)


def _populate_readiness(repo: Repository, conn: sqlite3.Connection) -> int:
    rows = repo.get_all_readiness_checkins_raw()
    return _insert_rows(conn, "readiness_checkins", rows, replace=True)


def _populate_training(repo: Repository, conn: sqlite3.Connection) -> tuple[int, int, int]:
    """Normalizes Repository.get_all_training_exercises_raw()'s flat
    one-dict-per-exercise-page shape into training_sessions ->
    training_exercises -> training_sets.

    Grouped by Session ID (the true session key generated once per session
    by create_training_session and denormalised onto every exercise row
    logged under it), NOT by date: two same-day sessions get two distinct
    training_sessions rows. A row with a blank/missing Session ID (older
    data predating that field) is grouped under a synthesized
    f"{session_date}:no-session-id" key rather than dropped, so no logged
    exercise is silently excluded from the datastore."""
    exercises = repo.get_all_training_exercises_raw()
    sessions: dict[str, dict] = {}
    exercise_rows: list[dict] = []
    set_rows: list[dict] = []

    for ex in exercises:
        sid = ex["session_id"] or f"{ex['session_date']}:no-session-id"
        sessions.setdefault(sid, {
            "session_id": sid,
            "session_date": ex["session_date"],
            "session_duration_minutes": ex["session_duration_minutes"],
            "session_rpe": ex["session_rpe"],
            "session_au": ex["session_au"],
        })
        exercise_rows.append({
            "exercise_id": ex["exercise_id"],
            "session_id": sid,
            "session_date": ex["session_date"],
            "movement_name": ex["movement_name"],
            "movement_type": ex["movement_type"],
            "planned_sets": ex["planned_sets"],
            "planned_reps": ex["planned_reps"],
            "exercise_rpe": ex["exercise_rpe"],
            "actual_sets": ex["actual_sets"],
            "total_volume_kg": ex["total_volume_kg"],
            "notes": ex["notes"],
            "note_summary": ex["note_summary"],
            "sentiment_score": ex["sentiment_score"],
            "flagged_body_parts": ex["flagged_body_parts"],
            "warning_level": ex["warning_level"],
            "garmin_avg_hr": ex["garmin_avg_hr"],
            "garmin_max_hr": ex["garmin_max_hr"],
            "garmin_distance_km": ex["garmin_distance_km"],
            "garmin_calories": ex["garmin_calories"],
        })
        for s in ex["sets"]:
            set_rows.append({
                "exercise_id": ex["exercise_id"], "set_num": s.get("set_num"),
                "reps": s.get("reps"), "weight": s.get("weight"), "rest": s.get("rest"),
                "tut": s.get("tut"), "velocity": s.get("velocity"),
                "band_tier": s.get("band_tier"), "ts": s.get("ts"),
            })

    n_sessions = _insert_rows(conn, "training_sessions", list(sessions.values()))
    n_exercises = _insert_rows(conn, "training_exercises", exercise_rows)
    n_sets = _insert_rows(conn, "training_sets", set_rows)
    return n_sessions, n_exercises, n_sets


def _populate_biometric_blend(repo: Repository, conn: sqlite3.Connection) -> int:
    rows = [{
        "date": r.date, "hrv_ms": r.hrv_ms, "resting_heart_rate": r.resting_heart_rate,
        "sleep_duration_hours": r.sleep_duration_hours, "steps": r.steps,
        "sources_missing": json.dumps(list(r.sources_missing)) if r.sources_missing else None,
    } for r in repo.get_biometric_blend_history()]
    return _insert_rows(conn, "biometric_blend", rows)


def _populate_wake_time_adjustments(repo: Repository, conn: sqlite3.Connection) -> int:
    rows = [{"date": d, "adjustment_minutes": m} for d, m in repo.get_wake_time_adjustments().items()]
    return _insert_rows(conn, "wake_time_adjustments", rows)


def _populate_weekly_rollup(repo: Repository, conn: sqlite3.Connection) -> int:
    rows = [{
        "week_start": s.week_start, "week_end": s.week_end, "phase": s.phase_number,
        "scheduled": s.scheduled, "completed": s.completed, "status": s.status,
        "computed_at": s.computed_at,
    } for s in repo.get_weekly_rollup_history()]
    return _insert_rows(conn, "weekly_rollup", rows)


def _populate_sheet1_legacy(repo: Repository, conn: sqlite3.Connection) -> int:
    rows = [{
        "date": r.date, "hrv_ms": r.hrv_ms, "resting_heart_rate": r.resting_heart_rate,
        "sleep_duration_hours": r.sleep_duration_hours, "sleep_deep_hours": r.sleep_deep_hours,
        "active_kcal": r.active_kcal, "weight_kg": r.weight_kg, "steps": r.steps,
    } for r in repo.get_all_sheet1_biometric_records()]
    return _insert_rows(conn, "sheet1_legacy_biometrics", rows)
