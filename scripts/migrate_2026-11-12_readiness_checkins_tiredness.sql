-- Tiredness in the morning check-in (the owner, 2026-11-12: "can we add another
-- metric of subjective tiredness to the check in"; a 0-10 slider, recorded and
-- shown only).
--
-- PASTE THIS INTO THE SUPABASE SQL EDITOR BEFORE THE ENGINE DEPLOY. PostgREST has
-- no route that runs DDL, and every check-in the engine writes names this column,
-- so a project without it rejects every check-in save.
--
-- Safe to run twice. Do NOT paste services/datastore_schema_postgres.sql
-- instead: it opens with DROP TABLE ... CASCADE and would empty the project.

ALTER TABLE readiness_checkins ADD COLUMN IF NOT EXISTS tiredness_score DOUBLE PRECISION;

-- Check: one row, tiredness_score.
SELECT column_name FROM information_schema.columns
WHERE  table_name = 'readiness_checkins' AND column_name = 'tiredness_score';
