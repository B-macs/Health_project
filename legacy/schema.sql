PRAGMA foreign_keys = ON;

-- Core baseline medical context and history.
-- injury_weight_decay_lambda: starting λ for e^(-λt) decay, reviewed every 14 days.
CREATE TABLE IF NOT EXISTS diagnostic_profile (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp                   DATETIME DEFAULT CURRENT_TIMESTAMP,
    injury_focus                TEXT,
    mri_raw_text                TEXT,
    historical_compensations    TEXT,
    injury_weight_decay_lambda  REAL DEFAULT 0.05
);

-- Daily readiness & subjective context.
-- anatomical_locations and sensation_tags stored as JSON arrays.
CREATE TABLE IF NOT EXISTS daily_readiness (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp            DATETIME DEFAULT CURRENT_TIMESTAMP,
    current_condition    TEXT,
    tightness_score      INTEGER,    -- 0-10 clinical scale; primary Stage 1→2 progression metric
    pain_score           INTEGER,    -- 0-10 overall pain
    anatomical_locations TEXT,       -- JSON array: selected body part tags
    sensation_tags       TEXT,       -- JSON array: e.g. ["Tight", "Stiff"]
    subjective_tightness TEXT,       -- free-text 1-sentence note for AI parsing
    alcohol_units        REAL DEFAULT 0,
    travel_flag          INTEGER DEFAULT 0,   -- boolean: 1 = travel day
    psych_stress_score   INTEGER              -- 1-5 psychological stress scale
);

-- One row per gym session (session-level aggregates).
-- session_au = session_rpe * session_duration_minutes (Foster Arbitrary Units).
CREATE TABLE IF NOT EXISTS training_sessions (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date             DATE DEFAULT (date('now')),
    timestamp                DATETIME DEFAULT CURRENT_TIMESTAMP,
    session_duration_minutes INTEGER,
    session_rpe              INTEGER,   -- 1-10 overall session feeling
    session_au               REAL       -- session_rpe * session_duration_minutes
);

-- One row per exercise within a session.
CREATE TABLE IF NOT EXISTS training_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER REFERENCES training_sessions(id),
    timestamp     DATETIME DEFAULT CURRENT_TIMESTAMP,
    movement_name TEXT,
    movement_type TEXT,     -- "Weight" | "Stretch" | "Conditioning" | "Rehab"
    planned_sets  INTEGER,
    planned_reps  INTEGER,
    rpe           INTEGER   -- per-exercise RPE 1-10
);

-- One row per set within an exercise.
-- movement_velocity: proxy for execution quality fed into trend analysis.
CREATE TABLE IF NOT EXISTS training_set_log (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    training_log_id            INTEGER NOT NULL REFERENCES training_log(id),
    set_number                 INTEGER,
    reps_completed             INTEGER,        -- from dial
    weight_kg                  REAL,           -- from dial
    rest_time_seconds          INTEGER,        -- from auto-timer
    time_under_tension_seconds INTEGER,        -- for isometric protocols
    movement_velocity          TEXT,           -- "Explosive"|"Smooth/Controlled"|"Sluggish"|"Compensated"
    timestamp                  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- AI-parseable free-text session notes (voice or typed).
-- ai_summary, sentiment_score, flagged_body_parts populated by Probabilistic Engine (Bucket 5).
CREATE TABLE IF NOT EXISTS session_notes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    training_log_id     INTEGER REFERENCES training_log(id),
    timestamp           DATETIME DEFAULT CURRENT_TIMESTAMP,
    raw_text            TEXT,
    ai_summary          TEXT,
    sentiment_score     REAL,           -- -1.0 (negative) to 1.0 (positive)
    flagged_body_parts  TEXT            -- comma-separated anatomical tags
);

-- Centralized Apple Health data — one row per calendar date, never overwritten.
CREATE TABLE IF NOT EXISTS daily_biometrics (
    date                 DATE PRIMARY KEY,
    resting_heart_rate   INTEGER,
    heart_rate_avg       INTEGER,
    hrv_ms               REAL,
    sleep_duration_hours REAL,
    sleep_deep_hours     REAL,
    active_energy_kcal   INTEGER,
    weight_kg            REAL,
    steps                INTEGER
);

-- Bucket 5: AI-generated movement risk assessments linked to diagnostic profile.
-- One row per analysis run — append-only; a new run creates a new row.
CREATE TABLE IF NOT EXISTS ai_movement_risk (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp          DATETIME DEFAULT CURRENT_TIMESTAMP,
    risk_summary       TEXT,    -- clinical summary from LLM
    flagged_movements  TEXT,    -- JSON array: movements to avoid/modify
    safe_movements     TEXT,    -- JSON array: cleared movements for current stage
    correlation_notes  TEXT,    -- LLM-identified pattern between MRI + recent session notes
    model_used         TEXT
);

-- Functional biomechanical assessment — separate from MRI structural data.
-- Reviewed every 2-4 weeks; a new row is inserted per assessment, is_current flips on the latest.
-- tight_areas, weak_areas, movement_patterns stored as JSON arrays for AI engine queries.
CREATE TABLE IF NOT EXISTS biomechanical_assessment (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_date      DATE DEFAULT (date('now')),
    timestamp            DATETIME DEFAULT CURRENT_TIMESTAMP,
    profile_summary      TEXT,       -- free-text full summary for LLM context
    tight_areas_json     TEXT,       -- JSON array: e.g. ["glute_medius","piriformis","right_iliopsoas"]
    weak_areas_json      TEXT,       -- JSON array: e.g. ["gluteus_maximus","deep_core"]
    movement_patterns_json TEXT,     -- JSON array of objects: {finding, location, side, mechanism}
    review_date          DATE,       -- date when reassessment is due (assessment_date + 14-28 days)
    is_current           INTEGER DEFAULT 1  -- boolean: 1 = active profile used by engine
);

-- Engine configuration — key/value store for persistent state (current_stage, etc.)
CREATE TABLE IF NOT EXISTS user_config (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for rolling 7/28-day window queries and FK joins.
CREATE INDEX IF NOT EXISTS idx_daily_readiness_ts          ON daily_readiness(timestamp);
CREATE INDEX IF NOT EXISTS idx_training_sessions_date      ON training_sessions(session_date);
CREATE INDEX IF NOT EXISTS idx_training_log_session        ON training_log(session_id);
CREATE INDEX IF NOT EXISTS idx_training_log_ts             ON training_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_training_set_log_exercise   ON training_set_log(training_log_id);
CREATE INDEX IF NOT EXISTS idx_session_notes_exercise      ON session_notes(training_log_id);
CREATE INDEX IF NOT EXISTS idx_biomechanical_current       ON biomechanical_assessment(is_current, assessment_date);
