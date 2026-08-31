-- migrations/001_initial.sql
-- Owner: Person 3 (M.9)
-- Run this script against your Supabase / PostgreSQL database to create the schema.
--
-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- for gen_random_uuid()

-- ─── batch_jobs ──────────────────────────────────────────────────────────────
-- Tracks each upload batch (single résumé or ZIP archive).

CREATE TABLE IF NOT EXISTS batch_jobs (
    batch_id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Status lifecycle: queued → extracting → scoring → completed | failed
    status              TEXT        NOT NULL DEFAULT 'queued'
                            CHECK (status IN ('queued','extracting','scoring',
                                              'pre_filtered','completed','failed')),

    total_files         INT         NOT NULL DEFAULT 1,
    processed_files     INT         NOT NULL DEFAULT 0,
    failed_files        INT         NOT NULL DEFAULT 0,
    pre_filtered_count  INT         NOT NULL DEFAULT 0,

    -- Stored for fault-recovery: enough context to re-run the pipeline on restart
    -- TODO (Person 3 — M.9): Add storage_url or file_path column if needed.
    rubric              JSONB,
    error_log           TEXT
);

-- Auto-update updated_at on every write
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER batch_jobs_updated_at
    BEFORE UPDATE ON batch_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ─── candidate_evaluations ───────────────────────────────────────────────────
-- One row per candidate per batch. Stores Stage 1 score and Stage 2 evaluation.

CREATE TABLE IF NOT EXISTS candidate_evaluations (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id                UUID        NOT NULL REFERENCES batch_jobs(batch_id) ON DELETE CASCADE,
    candidate_id            UUID        NOT NULL DEFAULT gen_random_uuid(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    status                  TEXT        NOT NULL DEFAULT 'queued'
                                CHECK (status IN ('queued','extracting','scoring',
                                                  'pre_filtered','completed','failed')),

    -- Stage 1 output (M.7)
    cosine_similarity_score FLOAT,

    -- Stage 2 output (M.8) — stored as JSONB (UnifiedEvaluationSchema)
    evaluation              JSONB,

    -- Error details for failed candidates
    error_log               TEXT,

    UNIQUE (batch_id, candidate_id)
);

CREATE TRIGGER candidate_evaluations_updated_at
    BEFORE UPDATE ON candidate_evaluations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Index to speed up leaderboard queries (ORDER BY overall_score DESC)
CREATE INDEX IF NOT EXISTS idx_candidate_eval_score
    ON candidate_evaluations ((evaluation->>'overall_score') DESC NULLS LAST);

-- Index for batch status polling aggregate queries
CREATE INDEX IF NOT EXISTS idx_candidate_eval_batch
    ON candidate_evaluations (batch_id, status);
