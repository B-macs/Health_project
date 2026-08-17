-- ============================================================================
-- Supabase migration — 2026-08-14
-- Adds the four per-set fields that shipped with the Stage 2B block build.
--
-- PASTE THIS FILE into the Supabase SQL editor. Run it once.
--
-- ⚠ DO NOT PASTE services/datastore_schema_postgres.sql INSTEAD.
--   That file is the FULL schema and opens with 21 `DROP TABLE ... CASCADE`
--   statements. It is written for building an empty project from nothing, and
--   running it against a populated one deletes every row in all 21 tables.
--   It is a generated file (scripts/build_supabase_schema.py) and is the
--   authority on what the columns should BE — it is not a migration.
--
-- WHY BY HAND AT ALL: PostgREST has no DDL route, so nothing in this repo can
-- apply a schema change to Supabase. Every other write goes through the API.
--
-- WHAT BREAKS IF THIS IS NOT RUN: the Supabase mirror sends these four keys on
-- every training_sets row from now on, and PostgREST rejects the WHOLE batch on
-- one unknown column. So the mirror stops mirroring sets. Nothing else is
-- affected — Notion and Sheets are the system of record, the local SQLite
-- datastore already has the columns, and a failed flush is caught and recorded
-- on Repository.mirror_last_error rather than raising. It fails quiet, which is
-- exactly why it is worth doing now rather than noticing in a month.
--
-- SAFE TO RE-RUN: every statement is IF NOT EXISTS.
-- ============================================================================

ALTER TABLE training_sets
    -- 1 = a ramp set. Excluded from weekly tonnage and from every 1RM estimate.
    -- DEFAULT 0 is load-bearing: every set logged before 2026-08-14 was a
    -- working set, and they must read as work rather than as warm-ups.
    ADD COLUMN IF NOT EXISTS is_warmup           BIGINT DEFAULT 0,

    -- Wall-clock rest that FOLLOWED this set. NULL means NOT MEASURED — the
    -- last set of an exercise, pre-2026-08-14 history, or a rest longer than
    -- 20 minutes, which is an interruption rather than a rest. NULL never
    -- means "no rest was taken".
    ADD COLUMN IF NOT EXISTS rest_taken_seconds  DOUBLE PRECISION,

    -- The weaker side's own numbers, written ONLY when the athlete edited the
    -- left side away from the right. Absent means the two sides were equal.
    ADD COLUMN IF NOT EXISTS reps_left           DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS weight_left         DOUBLE PRECISION;


-- ── Verify ──────────────────────────────────────────────────────────────────
-- Should return exactly four rows.
SELECT column_name, data_type, column_default
FROM   information_schema.columns
WHERE  table_name = 'training_sets'
  AND  column_name IN ('is_warmup', 'rest_taken_seconds', 'reps_left', 'weight_left')
ORDER  BY column_name;
