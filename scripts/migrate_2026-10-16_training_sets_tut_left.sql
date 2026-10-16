-- The core hold score's left side (docs/core_hold_index_design_2026-10-13.md,
-- decided 2026-10-13; built 2026-10-16). A timed test hold stores the right
-- side in `tut` and the left in `tut_left`.
--
-- PASTE THIS INTO THE SUPABASE SQL EDITOR BEFORE THE PUSH. PostgREST has no
-- route that runs DDL, and every training_sets row the app writes names this
-- column, so a project without it rejects every training save.
--
-- Safe to run twice. Do NOT paste services/datastore_schema_postgres.sql
-- instead: it opens with DROP TABLE ... CASCADE and would empty the project.

ALTER TABLE training_sets ADD COLUMN IF NOT EXISTS tut_left DOUBLE PRECISION;

-- Check: one row, tut_left.
SELECT column_name FROM information_schema.columns
WHERE  table_name = 'training_sets' AND column_name = 'tut_left';
