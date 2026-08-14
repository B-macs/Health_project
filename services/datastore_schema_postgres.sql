-- GENERATED FILE — do not edit.
-- Produced by services/datastore_postgres.py::to_postgres() from
-- services/datastore_schema.sql, which is the ONE schema. Change that
-- file and regenerate; editing this one puts the two dialects out of
-- step, which is the whole thing the translator exists to prevent.
--
-- Apply with: python scripts/build_supabase_schema.py

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

DROP TABLE IF EXISTS training_sets CASCADE;
CREATE TABLE training_sets (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exercise_id  TEXT,
    set_num      BIGINT,
    reps         DOUBLE PRECISION,
    weight       DOUBLE PRECISION,
    rest         DOUBLE PRECISION,
    tut          DOUBLE PRECISION,
    velocity     TEXT,
    band_tier    TEXT,   -- NULL when the exercise has no band tier
    ts           TEXT,   -- NULL for synthesized (make_sets_data) sets; ISO
                         -- datetime string for real captured sets (build_set_record)
    is_warmup    BIGINT DEFAULT 0,  -- 1 = ramp set. Excluded from weekly tonnage
                         -- and from every 1RM estimate. 0/NULL = a working set,
                         -- which is what all history before 2026-08 is.
    rest_taken_seconds DOUBLE PRECISION,  -- wall-clock rest that FOLLOWED this set. NULL means
                         -- not measured (last set of an exercise, pre-2026-08
                         -- history, or an interrupted rest) — never "no rest"
    reps_left    DOUBLE PRECISION,   -- the weaker side's own numbers, present ONLY when the
    weight_left  DOUBLE PRECISION    -- athlete edited the left side away from the right
);
CREATE INDEX idx_training_sets_exercise ON training_sets(exercise_id);

DROP TABLE IF EXISTS training_exercises CASCADE;
CREATE TABLE training_exercises (
    exercise_id         TEXT PRIMARY KEY,   -- Notion page id
    session_id          TEXT,
    session_date        TEXT,               -- ISO date, denormalized for query convenience
    movement_name       TEXT,
    movement_type       TEXT,
    planned_sets        DOUBLE PRECISION,
    planned_reps        DOUBLE PRECISION,
    exercise_rpe        DOUBLE PRECISION,
    actual_sets         BIGINT,
    total_volume_kg     DOUBLE PRECISION,
    notes               TEXT,
    note_summary        TEXT,
    sentiment_score     DOUBLE PRECISION,
    flagged_body_parts  TEXT,               -- JSON array string, as stored
    warning_level       TEXT,
    garmin_avg_hr       DOUBLE PRECISION,
    garmin_max_hr       DOUBLE PRECISION,
    garmin_distance_km  DOUBLE PRECISION,
    garmin_calories     DOUBLE PRECISION
);
CREATE INDEX idx_training_exercises_session ON training_exercises(session_id);
CREATE INDEX idx_training_exercises_date ON training_exercises(session_date);

DROP TABLE IF EXISTS training_sessions CASCADE;
CREATE TABLE training_sessions (
    session_id                TEXT PRIMARY KEY,  -- "Session ID", e.g. 2026-07-29-a1b2c3d4
    session_date              TEXT,               -- ISO date
    session_duration_minutes  DOUBLE PRECISION,
    session_rpe               DOUBLE PRECISION,
    session_au                DOUBLE PRECISION
);

DROP TABLE IF EXISTS readiness_checkins CASCADE;
CREATE TABLE readiness_checkins (
    date                  TEXT PRIMARY KEY,   -- ISO date
    current_condition     TEXT,
    tightness_score       DOUBLE PRECISION,
    pain_score            DOUBLE PRECISION,
    anatomical_locations  TEXT,               -- JSON array string
    sensation_tags        TEXT,               -- JSON array string
    subjective_tightness  TEXT,
    alcohol_units         DOUBLE PRECISION,
    travel_flag           BIGINT,            -- 0/1
    psych_stress_score    DOUBLE PRECISION,
    instability_events    DOUBLE PRECISION,
    bristol_type          DOUBLE PRECISION,
    unusual_stool_colour  BIGINT,            -- 0/1
    hunger_deviation      DOUBLE PRECISION,
    thirst_intensity      DOUBLE PRECISION,
    electrolytes_taken    BIGINT,            -- 0/1
    meditation_done       BIGINT,            -- 0/1
    meditation_minutes    DOUBLE PRECISION,
    relaxation_depth      DOUBLE PRECISION,
    -- AI note-parsing pipeline output (services.repository.update_readiness_ai) --
    -- absent/0 on every page until that pipeline actually runs against it.
    parsed                BIGINT,            -- 0/1
    parsed_severity       DOUBLE PRECISION,
    parsed_areas          TEXT,               -- JSON array string, as stored
    parsed_sensations     TEXT,               -- JSON array string, as stored
    warning_level         TEXT
);

DROP TABLE IF EXISTS garmin_daily CASCADE;
CREATE TABLE garmin_daily (
    date            TEXT PRIMARY KEY,
    steps           BIGINT,
    resting_hr      DOUBLE PRECISION,
    avg_stress      DOUBLE PRECISION,
    sleep_score     DOUBLE PRECISION,
    sleep_hours     DOUBLE PRECISION,
    calories_total  DOUBLE PRECISION,
    min_hr          DOUBLE PRECISION,
    max_hr          DOUBLE PRECISION,
    hrv_ms          DOUBLE PRECISION
);

DROP TABLE IF EXISTS garmin_activities CASCADE;
CREATE TABLE garmin_activities (
    activity_id       TEXT PRIMARY KEY,
    date              TEXT,
    name              TEXT,
    type              TEXT,
    start_time_local  TEXT,
    duration_minutes  DOUBLE PRECISION,
    distance_km       DOUBLE PRECISION,
    avg_hr            DOUBLE PRECISION,
    max_hr            DOUBLE PRECISION,
    calories          DOUBLE PRECISION
);
CREATE INDEX idx_garmin_activities_date ON garmin_activities(date);

DROP TABLE IF EXISTS session_hr CASCADE;
CREATE TABLE session_hr (
    date               TEXT PRIMARY KEY,
    activity_id        TEXT,
    activity_name      TEXT,
    activity_type      TEXT,
    start_time_local   TEXT,
    duration_minutes   DOUBLE PRECISION,
    overlap_minutes    DOUBLE PRECISION,
    avg_hr             DOUBLE PRECISION,
    max_hr             DOUBLE PRECISION,
    hr_max_used        DOUBLE PRECISION,
    edwards_load       DOUBLE PRECISION,
    hr_strain          DOUBLE PRECISION,
    banister_trimp     DOUBLE PRECISION,
    total_minutes      DOUBLE PRECISION,
    zone_source        TEXT,
    zone_minutes_json  TEXT,
    per_exercise_json  TEXT
);

DROP TABLE IF EXISTS oura_daily CASCADE;
CREATE TABLE oura_daily (
    date                                    TEXT PRIMARY KEY,
    sleep_score                             DOUBLE PRECISION,
    sleep_total_sleep                       DOUBLE PRECISION,
    sleep_efficiency                        DOUBLE PRECISION,
    sleep_restfulness                       DOUBLE PRECISION,
    sleep_rem_sleep                         DOUBLE PRECISION,
    sleep_deep_sleep                        DOUBLE PRECISION,
    sleep_latency                           DOUBLE PRECISION,
    sleep_timing                            DOUBLE PRECISION,
    readiness_score                         DOUBLE PRECISION,
    readiness_resting_heart_rate            DOUBLE PRECISION,
    readiness_hrv_balance                   DOUBLE PRECISION,
    readiness_body_temperature              DOUBLE PRECISION,
    readiness_recovery_index                DOUBLE PRECISION,
    readiness_sleep_balance                 DOUBLE PRECISION,
    readiness_activity_balance              DOUBLE PRECISION,
    readiness_previous_day_activity         DOUBLE PRECISION,
    readiness_previous_night                DOUBLE PRECISION,
    readiness_sleep_regularity              DOUBLE PRECISION,
    readiness_temperature_deviation         DOUBLE PRECISION,
    readiness_temperature_trend_deviation   DOUBLE PRECISION,
    activity_score                          DOUBLE PRECISION,
    steps                                   BIGINT,
    activity_high_time                      DOUBLE PRECISION,
    activity_medium_time                    DOUBLE PRECISION,
    activity_low_time                       DOUBLE PRECISION,
    activity_sedentary_time                 DOUBLE PRECISION,
    activity_met_minutes                    DOUBLE PRECISION,
    activity_high_met_minutes               DOUBLE PRECISION,
    activity_medium_met_minutes             DOUBLE PRECISION,
    activity_low_met_minutes                DOUBLE PRECISION,
    activity_sedentary_met_minutes          DOUBLE PRECISION,
    activity_non_wear_time                  DOUBLE PRECISION,
    activity_inactivity_alerts              DOUBLE PRECISION,
    activity_equivalent_walking_distance    DOUBLE PRECISION,
    activity_meters_to_target               DOUBLE PRECISION,
    activity_target_meters                  DOUBLE PRECISION,
    activity_meet_daily_targets             DOUBLE PRECISION,
    activity_move_every_hour                DOUBLE PRECISION,
    activity_recovery_time                  DOUBLE PRECISION,
    activity_stay_active                    DOUBLE PRECISION,
    activity_training_frequency             DOUBLE PRECISION,
    activity_training_volume                DOUBLE PRECISION,
    total_calories                          DOUBLE PRECISION,
    active_calories                         DOUBLE PRECISION,
    target_calories                         DOUBLE PRECISION,
    resting_time                            DOUBLE PRECISION,
    stress_high_duration                    DOUBLE PRECISION,
    stress_recovery_duration                DOUBLE PRECISION,
    stress_day_summary                      TEXT,
    resilience_level                        TEXT,
    resilience_sleep_recovery                DOUBLE PRECISION,
    resilience_daytime_recovery              DOUBLE PRECISION,
    resilience_stress                        DOUBLE PRECISION,
    spo2_average                             DOUBLE PRECISION,
    spo2_breathing_disturbance_index         DOUBLE PRECISION,
    vascular_age                             DOUBLE PRECISION,
    pulse_wave_velocity                      DOUBLE PRECISION,
    sleep_time_status                        TEXT,
    sleep_time_recommendation                TEXT,
    sleep_time_optimal_bedtime               TEXT,
    vo2_max                                  DOUBLE PRECISION
);

DROP TABLE IF EXISTS oura_workouts CASCADE;
CREATE TABLE oura_workouts (
    workout_id      TEXT PRIMARY KEY,
    day             TEXT,
    activity        TEXT,
    intensity       TEXT,
    calories        DOUBLE PRECISION,
    distance_km     DOUBLE PRECISION,
    start_datetime  TEXT,
    end_datetime    TEXT,
    source          TEXT
);
CREATE INDEX idx_oura_workouts_day ON oura_workouts(day);

DROP TABLE IF EXISTS oura_sleep_periods CASCADE;
CREATE TABLE oura_sleep_periods (
    sleep_id                         TEXT PRIMARY KEY,
    day                              TEXT,
    type                             TEXT,
    period                           DOUBLE PRECISION,
    bedtime_start                    TEXT,
    bedtime_end                      TEXT,
    total_sleep_duration             DOUBLE PRECISION,
    time_in_bed                      DOUBLE PRECISION,
    awake_time                       DOUBLE PRECISION,
    deep_sleep_duration              DOUBLE PRECISION,
    light_sleep_duration             DOUBLE PRECISION,
    rem_sleep_duration               DOUBLE PRECISION,
    efficiency                       DOUBLE PRECISION,
    latency                          DOUBLE PRECISION,
    average_heart_rate               DOUBLE PRECISION,
    lowest_heart_rate                 DOUBLE PRECISION,
    average_hrv                      DOUBLE PRECISION,
    average_breath                   DOUBLE PRECISION,
    restless_periods                 DOUBLE PRECISION,
    readiness_score                  DOUBLE PRECISION,
    readiness_temperature_deviation  DOUBLE PRECISION,
    sleep_score_delta                DOUBLE PRECISION,
    readiness_score_delta            DOUBLE PRECISION,
    sleep_algorithm_version          TEXT,
    sleep_analysis_reason            TEXT,
    low_battery_alert                TEXT,   -- gspread's verbatim 'TRUE'/'FALSE', NOT numeric
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

DROP TABLE IF EXISTS garmin_sleep_stages CASCADE;
CREATE TABLE garmin_sleep_stages (
    date                       TEXT PRIMARY KEY,
    sleep_start_gmt            TEXT,
    sleep_end_gmt              TEXT,
    utc_offset_minutes         DOUBLE PRECISION,
    segment_count              BIGINT,
    deep_seconds               DOUBLE PRECISION,
    light_seconds              DOUBLE PRECISION,
    rem_seconds                DOUBLE PRECISION,
    awake_seconds              DOUBLE PRECISION,
    -- Garmin's OWN per-stage totals, kept so totals_match can verify our
    -- activityLevel->stage mapping on every night, not just the one it was
    -- originally checked against.
    dto_deep_seconds           DOUBLE PRECISION,
    dto_light_seconds          DOUBLE PRECISION,
    dto_rem_seconds            DOUBLE PRECISION,
    dto_awake_seconds          DOUBLE PRECISION,
    -- TEXT, not INTEGER, and the three columns like it in this file are the
    -- same story. The value here is a Google Sheets cell as gspread returns
    -- it, which is the STRING 'TRUE'/'FALSE' -- clients/datastore_reader.py
    -- pins preserving that verbatim as a fidelity rule. SQLite's loose typing
    -- stored the string in an INTEGER column without complaint, so the
    -- mis-declaration was invisible until the Postgres copy: there the
    -- declared type is enforced, the value had to be coerced to 1/0, and a
    -- pull back returned 1 where 'TRUE' went in. That is not merely untidy --
    -- _garmin_sleep_stages_row reads movement_contiguous as
    -- `str(v).upper() != "FALSE"`, so a coerced 0 reads as "0" and inverts to
    -- CONTIGUOUS, silently reporting a night that needed gap-filling as
    -- clean. Found by round-tripping the real datastore through Supabase
    -- (scripts/pull_datastore_from_supabase.py --round-trip), not by reading.
    totals_match               TEXT,
    sleep_levels_json          TEXT,    -- lossless segment list, JSON, NOT numeric
    movement_start_gmt         TEXT,
    movement_interval_seconds  DOUBLE PRECISION,
    movement_slot_count        BIGINT,
    movement_contiguous        TEXT,    -- 'FALSE' = the series needed gap-filling;
                                        -- see totals_match above for why TEXT
    movement_gap_slots         BIGINT,
    movement_levels            TEXT,    -- comma-joined floats, NOT numeric
    sleep_hr_json              TEXT,    -- JSON, NOT numeric
    sleep_stress_json          TEXT     -- JSON, NOT numeric
);

DROP TABLE IF EXISTS sleep_fusion CASCADE;
CREATE TABLE sleep_fusion (
    date                            TEXT PRIMARY KEY,
    source                          TEXT,  -- fused / oura_only / garmin_only / none
    rules_version                   BIGINT,
    computed_at                     TEXT,
    window_start_utc                TEXT,
    utc_offset_minutes              DOUBLE PRECISION,
    minutes                         BIGINT,
    master_hypnogram                TEXT,  -- digit-coded string, NOT numeric
    oura_hypnogram                  TEXT,  -- digit-coded string, NOT numeric
    garmin_hypnogram                TEXT,  -- digit-coded string, NOT numeric
    reason_codes                    TEXT,  -- one char per minute, NOT numeric
    master_deep_minutes             DOUBLE PRECISION,
    master_light_minutes            DOUBLE PRECISION,
    master_rem_minutes              DOUBLE PRECISION,
    master_awake_minutes            DOUBLE PRECISION,
    master_sleep_hours              DOUBLE PRECISION,
    oura_sleep_hours                DOUBLE PRECISION,
    garmin_sleep_hours              DOUBLE PRECISION,
    phantom_wake_minutes            DOUBLE PRECISION,
    window_overlap_pct              DOUBLE PRECISION,
    agreement_pct                   DOUBLE PRECISION,
    cohen_kappa                     DOUBLE PRECISION,
    garmin_covered_minutes          DOUBLE PRECISION,
    garmin_gap_minutes              DOUBLE PRECISION,
    garmin_outside_window_minutes   DOUBLE PRECISION,
    oura_periods_on_day             BIGINT,
    -- Movement, on the 30-SECOND grid (twice the hypnogram's resolution),
    -- anchored at the same window_start_utc so the two share one time axis.
    movement_source                 TEXT,
    movement_slots                  BIGINT,
    movement_covered_slots          BIGINT,
    movement_still_slots            BIGINT,
    movement_restless_slots         BIGINT,
    movement_tossing_slots          BIGINT,
    movement_active_slots           BIGINT,
    movement_position_shifts        BIGINT,
    movement_mean_class             DOUBLE PRECISION,
    master_movement                 TEXT,  -- digit-coded string, NOT numeric
    oura_movement                   TEXT,  -- digit-coded string, NOT numeric
    garmin_movement                 TEXT,  -- digit-coded string, NOT numeric
    -- The calibration each movement series was produced under -- the
    -- movement counterpart of rules_version. Without it a re-fit would
    -- silently change what a stored "restless" meant.
    movement_cutpoints              TEXT   -- comma-joined floats, NOT numeric
);
CREATE INDEX idx_sleep_fusion_source ON sleep_fusion(source);

DROP TABLE IF EXISTS oura_sessions CASCADE;
CREATE TABLE oura_sessions (
    session_id      TEXT PRIMARY KEY,
    day             TEXT,
    type            TEXT,
    start_datetime  TEXT,
    end_datetime    TEXT,
    mood            TEXT,
    motion_count    DOUBLE PRECISION
);
CREATE INDEX idx_oura_sessions_day ON oura_sessions(day);

DROP TABLE IF EXISTS oura_rest_mode CASCADE;
CREATE TABLE oura_rest_mode (
    rest_mode_id  TEXT PRIMARY KEY,
    start_day     TEXT,
    end_day       TEXT,
    end_time      TEXT
);

DROP TABLE IF EXISTS biometric_blend CASCADE;
CREATE TABLE biometric_blend (
    date                  TEXT PRIMARY KEY,
    hrv_ms                DOUBLE PRECISION,
    resting_heart_rate    DOUBLE PRECISION,
    sleep_duration_hours  DOUBLE PRECISION,
    steps                 BIGINT,
    sources_missing       TEXT   -- JSON array string
);

DROP TABLE IF EXISTS metrics_history CASCADE;
CREATE TABLE metrics_history (
    date             TEXT PRIMARY KEY,
    readiness_score  DOUBLE PRECISION,
    sleep_pct        DOUBLE PRECISION,
    sleep_score      DOUBLE PRECISION,
    strain           DOUBLE PRECISION
);

DROP TABLE IF EXISTS wake_time_adjustments CASCADE;
CREATE TABLE wake_time_adjustments (
    date                TEXT PRIMARY KEY,
    adjustment_minutes  DOUBLE PRECISION
);

DROP TABLE IF EXISTS weekly_rollup CASCADE;
CREATE TABLE weekly_rollup (
    week_start   TEXT PRIMARY KEY,
    week_end     TEXT,
    phase        BIGINT,
    scheduled    BIGINT,
    completed    BIGINT,
    status       TEXT,
    computed_at  TEXT
    -- No "ratio" column: models.WeekScore doesn't carry one -- it's a
    -- display-only string the Sheets writer computes at write time.
    -- Trivially recomputable (completed/scheduled) by any datastore
    -- consumer; omitted here rather than re-deriving it in datastore.py.
);

DROP TABLE IF EXISTS sheet1_legacy_biometrics CASCADE;
CREATE TABLE sheet1_legacy_biometrics (
    date                  TEXT PRIMARY KEY,
    hrv_ms                DOUBLE PRECISION,
    resting_heart_rate    DOUBLE PRECISION,
    sleep_duration_hours  DOUBLE PRECISION,
    sleep_deep_hours      DOUBLE PRECISION,
    active_kcal           DOUBLE PRECISION,
    weight_kg             DOUBLE PRECISION,
    steps                 BIGINT
);

DROP TABLE IF EXISTS config CASCADE;
CREATE TABLE config (
    key      TEXT PRIMARY KEY,   -- e.g. "phases", "diagnostic_profile", "current_stage"
    value    TEXT,               -- raw string as stored -- JSON blob for some keys, plain for others
    updated  TEXT                -- ISO date the key was last written
);

DROP TABLE IF EXISTS datastore_meta CASCADE;
CREATE TABLE datastore_meta (
    key    TEXT PRIMARY KEY,
    value  TEXT
);

-- ── Foreign keys ─────────────────────────────────────────────────────
-- Lifted out of the CREATEs above: the SQLite file declares
-- training_sets before the table it references, which is only legal
-- with enforcement off. Applied here once every table exists, and
-- ENFORCED — services/datastore.py already loads parents first
-- (sessions, then exercises, then sets).
ALTER TABLE training_sets ADD CONSTRAINT training_sets_exercise_id_fkey
    FOREIGN KEY (exercise_id) REFERENCES training_exercises(exercise_id);
ALTER TABLE training_exercises ADD CONSTRAINT training_exercises_session_id_fkey
    FOREIGN KEY (session_id) REFERENCES training_sessions(session_id);

