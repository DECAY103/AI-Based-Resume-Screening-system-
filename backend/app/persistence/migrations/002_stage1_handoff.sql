-- Backward-compatible M.7 → M.8 handoff: keep sanitized text only for
-- candidates promoted to Stage 2. Existing records remain unchanged.
ALTER TABLE candidate_evaluations
    ADD COLUMN IF NOT EXISTS sanitized_resume_text TEXT;
