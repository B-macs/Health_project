-- The Metabolism screen's readings move into Supabase (rebuild Phase 2,
-- inventory fault F15, approved by the owner 2026-10-19). Until now the scale
-- readings came from a git-ignored CSV (Input_files/Fitdays.csv), so the
-- hosted app showed no weight at all, and the gym scans lived only in a
-- Python file.
--
-- PASTE THIS INTO THE SUPABASE SQL EDITOR BEFORE THE PUSH THAT REGISTERS
-- THESE TABLES. The app rebuilds its local copy from every table it knows at
-- each start, so a registered table that Supabase lacks stops that rebuild.
--
-- Safe to run twice: it only creates, and it never drops or changes a table
-- that exists. Do NOT paste services/datastore_schema_postgres.sql instead:
-- it opens with DROP TABLE ... CASCADE and would empty the project.

-- One Foryond scale weigh-in. Only weight is a measurement; BMI and body fat
-- are kept as the device printed them. taken_at is the local wall time,
-- 'YYYY-MM-DDTHH:MM:SS', one row per minute (the export holds same-minute
-- duplicates; the last one is kept).
CREATE TABLE IF NOT EXISTS scale_readings (
    taken_at      TEXT PRIMARY KEY,
    weight_kg     DOUBLE PRECISION NOT NULL,
    bmi           DOUBLE PRECISION,
    body_fat_pct  DOUBLE PRECISION
);

-- One InBody scan, as printed, before the height correction
-- (services/body_composition.InBodyScan.at_height runs on read). `device`
-- keeps two machine models apart: readings are never pooled across models.
CREATE TABLE IF NOT EXISTS inbody_scans (
    taken_at            TEXT PRIMARY KEY,
    device              TEXT NOT NULL,
    weight_kg           DOUBLE PRECISION NOT NULL,
    bmi                 DOUBLE PRECISION NOT NULL,
    total_body_water_l  DOUBLE PRECISION NOT NULL,
    skeletal_muscle_kg  DOUBLE PRECISION NOT NULL,
    ecw_tbw             DOUBLE PRECISION NOT NULL,
    phase_angle_deg     DOUBLE PRECISION,
    note                TEXT
);

-- Check: two rows, inbody_scans and scale_readings.
SELECT table_name FROM information_schema.tables
WHERE  table_schema = 'public' AND table_name IN ('scale_readings', 'inbody_scans')
ORDER  BY table_name;
