-- services/datastore_schema.sql
-- The project's own consolidated database -- full copy of the app's live
-- Notion + Google Sheets data. Rebuilt wholesale by
-- services/datastore.py::rebuild() every time scripts/build_datastore.py
-- runs -- never hand-edit this file to add data, only to change table
-- shape (rebuild() DROPs and recreates everything below on every run). See
-- services/datastore.py's module docstring for the all-or-nothing
-- single-transaction rebuild guarantee.
--
-- PRAGMA foreign_keys is deliberately left at SQLite's OFF default: this
-- datastore is wholesale-regenerated from Notion/Sheets every run for now,
-- so there's no write path for a constraint to protect, and enforcing it
-- would force strict parent-before-child insert ordering across every
-- DROP+recreate table for no real safety benefit. REFERENCES clauses below
-- are kept anyway, for documentation and any tooling (e.g. DB Browser for
-- SQLite) that draws relationship diagrams from them.

DROP TABLE IF EXISTS training_sets;
CREATE TABLE training_sets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id  TEXT REFERENCES training_exercises(exercise_id),
    set_num      INTEGER,
    reps         REAL,
    weight       REAL,
    rest         REAL,
    tut          REAL,
    velocity     TEXT,
    band_tier    TEXT,   -- NULL when the exercise has no band tier
    ts           TEXT    -- NULL for synthesized (make_sets_data) sets; ISO
                         -- datetime string for real captured sets (build_set_record)
);
CREATE INDEX idx_training_sets_exercise ON training_sets(exercise_id);

DROP TABLE IF EXISTS training_exercises;
CREATE TABLE training_exercises (
    exercise_id         TEXT PRIMARY KEY,   -- Notion page id
    session_id          TEXT REFERENCES training_sessions(session_id),
    session_date        TEXT,               -- ISO date, denormalized for query convenience
    movement_name       TEXT,
    movement_type       TEXT,
    planned_sets        REAL,
    planned_reps        REAL,
    exercise_rpe        REAL,
    actual_sets         INTEGER,
    total_volume_kg     REAL,
    notes               TEXT,
    note_summary        TEXT,
    sentiment_score     REAL,
    flagged_body_parts  TEXT,               -- JSON array string, as stored
    warning_level       TEXT,
    garmin_avg_hr       REAL,
    garmin_max_hr       REAL,
    garmin_distance_km  REAL,
    garmin_calories     REAL
);
CREATE INDEX idx_training_exercises_session ON training_exercises(session_id);
CREATE INDEX idx_training_exercises_date ON training_exercises(session_date);

DROP TABLE IF EXISTS training_sessions;
CREATE TABLE training_sessions (
    session_id                TEXT PRIMARY KEY,  -- "Session ID", e.g. 2026-07-29-a1b2c3d4
    session_date              TEXT,               -- ISO date
    session_duration_minutes  REAL,
    session_rpe               REAL,
    session_au                REAL
);

DROP TABLE IF EXISTS readiness_checkins;
CREATE TABLE readiness_checkins (
    date                  TEXT PRIMARY KEY,   -- ISO date
    current_condition     TEXT,
    tightness_score       REAL,
    pain_score            REAL,
    anatomical_locations  TEXT,               -- JSON array string
    sensation_tags        TEXT,               -- JSON array string
    subjective_tightness  TEXT,
    alcohol_units         REAL,
    travel_flag           INTEGER,            -- 0/1
    psych_stress_score    REAL,
    instability_events    REAL,
    bristol_type          REAL,
    unusual_stool_colour  INTEGER,            -- 0/1
    hunger_deviation      REAL,
    thirst_intensity      REAL,
    electrolytes_taken    INTEGER,            -- 0/1
    meditation_done       INTEGER,            -- 0/1
    meditation_minutes    REAL,
    relaxation_depth      REAL,
    -- AI note-parsing pipeline output (services.repository.update_readiness_ai) --
    -- absent/0 on every page until that pipeline actually runs against it.
    parsed                INTEGER,            -- 0/1
    parsed_severity       REAL,
    parsed_areas          TEXT,               -- JSON array string, as stored
    parsed_sensations     TEXT,               -- JSON array string, as stored
    warning_level         TEXT
);

DROP TABLE IF EXISTS garmin_daily;
CREATE TABLE garmin_daily (
    date            TEXT PRIMARY KEY,
    steps           INTEGER,
    resting_hr      REAL,
    avg_stress      REAL,
    sleep_score     REAL,
    sleep_hours     REAL,
    calories_total  REAL,
    min_hr          REAL,
    max_hr          REAL,
    hrv_ms          REAL
);

DROP TABLE IF EXISTS garmin_activities;
CREATE TABLE garmin_activities (
    activity_id       TEXT PRIMARY KEY,
    date              TEXT,
    name              TEXT,
    type              TEXT,
    start_time_local  TEXT,
    duration_minutes  REAL,
    distance_km       REAL,
    avg_hr            REAL,
    max_hr            REAL,
    calories          REAL
);
CREATE INDEX idx_garmin_activities_date ON garmin_activities(date);

DROP TABLE IF EXISTS session_hr;
CREATE TABLE session_hr (
    date               TEXT PRIMARY KEY,
    activity_id        TEXT,
    activity_name      TEXT,
    activity_type      TEXT,
    start_time_local   TEXT,
    duration_minutes   REAL,
    overlap_minutes    REAL,
    avg_hr             REAL,
    max_hr             REAL,
    hr_max_used        REAL,
    edwards_load       REAL,
    hr_strain          REAL,
    banister_trimp     REAL,
    total_minutes      REAL,
    zone_source        TEXT,
    zone_minutes_json  TEXT,
    per_exercise_json  TEXT
);

DROP TABLE IF EXISTS oura_daily;
CREATE TABLE oura_daily (
    date                                    TEXT PRIMARY KEY,
    sleep_score                             REAL,
    sleep_total_sleep                       REAL,
    sleep_efficiency                        REAL,
    sleep_restfulness                       REAL,
    sleep_rem_sleep                         REAL,
    sleep_deep_sleep                        REAL,
    sleep_latency                           REAL,
    sleep_timing                            REAL,
    readiness_score                         REAL,
    readiness_resting_heart_rate            REAL,
    readiness_hrv_balance                   REAL,
    readiness_body_temperature              REAL,
    readiness_recovery_index                REAL,
    readiness_sleep_balance                 REAL,
    readiness_activity_balance              REAL,
    readiness_previous_day_activity         REAL,
    readiness_previous_night                REAL,
    readiness_sleep_regularity              REAL,
    readiness_temperature_deviation         REAL,
    readiness_temperature_trend_deviation   REAL,
    activity_score                          REAL,
    steps                                   INTEGER,
    activity_high_time                      REAL,
    activity_medium_time                    REAL,
    activity_low_time                       REAL,
    activity_sedentary_time                 REAL,
    activity_met_minutes                    REAL,
    activity_high_met_minutes               REAL,
    activity_medium_met_minutes             REAL,
    activity_low_met_minutes                REAL,
    activity_sedentary_met_minutes          REAL,
    activity_non_wear_time                  REAL,
    activity_inactivity_alerts              REAL,
    activity_equivalent_walking_distance    REAL,
    activity_meters_to_target               REAL,
    activity_target_meters                  REAL,
    activity_meet_daily_targets             REAL,
    activity_move_every_hour                REAL,
    activity_recovery_time                  REAL,
    activity_stay_active                    REAL,
    activity_training_frequency             REAL,
    activity_training_volume                REAL,
    total_calories                          REAL,
    active_calories                         REAL,
    target_calories                         REAL,
    resting_time                            REAL,
    stress_high_duration                    REAL,
    stress_recovery_duration                REAL,
    stress_day_summary                      TEXT,
    resilience_level                        TEXT,
    resilience_sleep_recovery                REAL,
    resilience_daytime_recovery              REAL,
    resilience_stress                        REAL,
    spo2_average                             REAL,
    spo2_breathing_disturbance_index         REAL,
    vascular_age                             REAL,
    pulse_wave_velocity                      REAL,
    sleep_time_status                        TEXT,
    sleep_time_recommendation                TEXT,
    sleep_time_optimal_bedtime               TEXT,
    vo2_max                                  REAL
);

DROP TABLE IF EXISTS oura_workouts;
CREATE TABLE oura_workouts (
    workout_id      TEXT PRIMARY KEY,
    day             TEXT,
    activity        TEXT,
    intensity       TEXT,
    calories        REAL,
    distance_km     REAL,
    start_datetime  TEXT,
    end_datetime    TEXT,
    source          TEXT
);
CREATE INDEX idx_oura_workouts_day ON oura_workouts(day);

DROP TABLE IF EXISTS oura_sleep_periods;
CREATE TABLE oura_sleep_periods (
    sleep_id                         TEXT PRIMARY KEY,
    day                              TEXT,
    type                             TEXT,
    period                           REAL,
    bedtime_start                    TEXT,
    bedtime_end                      TEXT,
    total_sleep_duration             REAL,
    time_in_bed                      REAL,
    awake_time                       REAL,
    deep_sleep_duration              REAL,
    light_sleep_duration             REAL,
    rem_sleep_duration               REAL,
    efficiency                       REAL,
    latency                          REAL,
    average_heart_rate               REAL,
    lowest_heart_rate                 REAL,
    average_hrv                      REAL,
    average_breath                   REAL,
    restless_periods                 REAL,
    readiness_score                  REAL,
    readiness_temperature_deviation  REAL,
    sleep_score_delta                REAL,
    readiness_score_delta            REAL,
    sleep_algorithm_version          TEXT,
    sleep_analysis_reason            TEXT,
    low_battery_alert                INTEGER,
    sleep_phase_5_min                TEXT,   -- digit-coded hypnogram string, NOT numeric
    sleep_phase_30_sec               TEXT,   -- digit-coded hypnogram string, NOT numeric
    movement_30_sec                  TEXT,   -- digit-coded string, NOT numeric
    sleep_hr_series                  TEXT,   -- JSON object, NOT numeric
    sleep_hrv_series                 TEXT    -- JSON object, NOT numeric
);
CREATE INDEX idx_oura_sleep_periods_day ON oura_sleep_periods(day);

-- ── Garmin sleep stages + the derived fusion. Both arrived after the first
--    datastore build and were the two tabs the Sleep drill-down reads most,
--    which is exactly why offline reads (services/repository.py's
--    _OfflineWorksheet) needed them here. Every digit-coded/JSON column is
--    TEXT and flagged below for the same reason it is exempted from gspread's
--    numericising upstream: read back as a number it is unrecoverable.

DROP TABLE IF EXISTS garmin_sleep_stages;
CREATE TABLE garmin_sleep_stages (
    date                       TEXT PRIMARY KEY,
    sleep_start_gmt            TEXT,
    sleep_end_gmt              TEXT,
    utc_offset_minutes         REAL,
    segment_count              INTEGER,
    deep_seconds               REAL,
    light_seconds              REAL,
    rem_seconds                REAL,
    awake_seconds              REAL,
    -- Garmin's OWN per-stage totals, kept so totals_match can verify our
    -- activityLevel->stage mapping on every night, not just the one it was
    -- originally checked against.
    dto_deep_seconds           REAL,
    dto_light_seconds          REAL,
    dto_rem_seconds            REAL,
    dto_awake_seconds          REAL,
    totals_match               INTEGER,
    sleep_levels_json          TEXT,    -- lossless segment list, JSON, NOT numeric
    movement_start_gmt         TEXT,
    movement_interval_seconds  REAL,
    movement_slot_count        INTEGER,
    movement_contiguous        INTEGER, -- False = the series needed gap-filling
    movement_gap_slots         INTEGER,
    movement_levels            TEXT,    -- comma-joined floats, NOT numeric
    sleep_hr_json              TEXT,    -- JSON, NOT numeric
    sleep_stress_json          TEXT     -- JSON, NOT numeric
);

DROP TABLE IF EXISTS sleep_fusion;
CREATE TABLE sleep_fusion (
    date                            TEXT PRIMARY KEY,
    source                          TEXT,  -- fused / oura_only / garmin_only / none
    rules_version                   INTEGER,
    computed_at                     TEXT,
    window_start_utc                TEXT,
    utc_offset_minutes              REAL,
    minutes                         INTEGER,
    master_hypnogram                TEXT,  -- digit-coded string, NOT numeric
    oura_hypnogram                  TEXT,  -- digit-coded string, NOT numeric
    garmin_hypnogram                TEXT,  -- digit-coded string, NOT numeric
    reason_codes                    TEXT,  -- one char per minute, NOT numeric
    master_deep_minutes             REAL,
    master_light_minutes            REAL,
    master_rem_minutes              REAL,
    master_awake_minutes            REAL,
    master_sleep_hours              REAL,
    oura_sleep_hours                REAL,
    garmin_sleep_hours              REAL,
    phantom_wake_minutes            REAL,
    window_overlap_pct              REAL,
    agreement_pct                   REAL,
    cohen_kappa                     REAL,
    garmin_covered_minutes          REAL,
    garmin_gap_minutes              REAL,
    garmin_outside_window_minutes   REAL,
    oura_periods_on_day             INTEGER,
    -- Movement, on the 30-SECOND grid (twice the hypnogram's resolution),
    -- anchored at the same window_start_utc so the two share one time axis.
    movement_source                 TEXT,
    movement_slots                  INTEGER,
    movement_covered_slots          INTEGER,
    movement_still_slots            INTEGER,
    movement_restless_slots         INTEGER,
    movement_tossing_slots          INTEGER,
    movement_active_slots           INTEGER,
    movement_position_shifts        INTEGER,
    movement_mean_class             REAL,
    master_movement                 TEXT,  -- digit-coded string, NOT numeric
    oura_movement                   TEXT,  -- digit-coded string, NOT numeric
    garmin_movement                 TEXT,  -- digit-coded string, NOT numeric
    -- The calibration each movement series was produced under -- the
    -- movement counterpart of rules_version. Without it a re-fit would
    -- silently change what a stored "restless" meant.
    movement_cutpoints              TEXT   -- comma-joined floats, NOT numeric
);
CREATE INDEX idx_sleep_fusion_source ON sleep_fusion(source);

DROP TABLE IF EXISTS oura_sessions;
CREATE TABLE oura_sessions (
    session_id      TEXT PRIMARY KEY,
    day             TEXT,
    type            TEXT,
    start_datetime  TEXT,
    end_datetime    TEXT,
    mood            TEXT,
    motion_count    REAL
);
CREATE INDEX idx_oura_sessions_day ON oura_sessions(day);

DROP TABLE IF EXISTS oura_rest_mode;
CREATE TABLE oura_rest_mode (
    rest_mode_id  TEXT PRIMARY KEY,
    start_day     TEXT,
    end_day       TEXT,
    end_time      TEXT
);

DROP TABLE IF EXISTS biometric_blend;
CREATE TABLE biometric_blend (
    date                  TEXT PRIMARY KEY,
    hrv_ms                REAL,
    resting_heart_rate    REAL,
    sleep_duration_hours  REAL,
    steps                 INTEGER,
    sources_missing       TEXT   -- JSON array string
);

DROP TABLE IF EXISTS metrics_history;
CREATE TABLE metrics_history (
    date             TEXT PRIMARY KEY,
    readiness_score  REAL,
    sleep_pct        REAL,
    sleep_score      REAL,
    strain           REAL
);

DROP TABLE IF EXISTS wake_time_adjustments;
CREATE TABLE wake_time_adjustments (
    date                TEXT PRIMARY KEY,
    adjustment_minutes  REAL
);

DROP TABLE IF EXISTS weekly_rollup;
CREATE TABLE weekly_rollup (
    week_start   TEXT PRIMARY KEY,
    week_end     TEXT,
    phase        INTEGER,
    scheduled    INTEGER,
    completed    INTEGER,
    status       TEXT,
    computed_at  TEXT
    -- No "ratio" column: models.WeekScore doesn't carry one -- it's a
    -- display-only string the Sheets writer computes at write time.
    -- Trivially recomputable (completed/scheduled) by any datastore
    -- consumer; omitted here rather than re-deriving it in datastore.py.
);

DROP TABLE IF EXISTS sheet1_legacy_biometrics;
CREATE TABLE sheet1_legacy_biometrics (
    date                  TEXT PRIMARY KEY,
    hrv_ms                REAL,
    resting_heart_rate    REAL,
    sleep_duration_hours  REAL,
    sleep_deep_hours      REAL,
    active_kcal           REAL,
    weight_kg             REAL,
    steps                 INTEGER
);

DROP TABLE IF EXISTS config;
CREATE TABLE config (
    key      TEXT PRIMARY KEY,   -- e.g. "phases", "diagnostic_profile", "current_stage"
    value    TEXT,               -- raw string as stored -- JSON blob for some keys, plain for others
    updated  TEXT                -- ISO date the key was last written
);

DROP TABLE IF EXISTS datastore_meta;
CREATE TABLE datastore_meta (
    key    TEXT PRIMARY KEY,
    value  TEXT
);
