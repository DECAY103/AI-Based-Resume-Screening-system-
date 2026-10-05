-- A candidate may enter the completed state only with the exact validated
-- UnifiedEvaluationSchema payload expected by the application.
CREATE OR REPLACE FUNCTION is_valid_unified_evaluation(payload JSONB)
RETURNS BOOLEAN
LANGUAGE plpgsql
IMMUTABLE
PARALLEL SAFE
AS $$
BEGIN
    IF payload IS NULL OR jsonb_typeof(payload) IS DISTINCT FROM 'object' THEN
        RETURN FALSE;
    END IF;

    IF jsonb_object_length(payload) <> 6
       OR NOT (payload ?& ARRAY[
           'overall_score',
           'skill_match_score',
           'matching_skills',
           'missing_skills',
           'work_experience_score',
           'verdict_summary'
       ]) THEN
        RETURN FALSE;
    END IF;

    IF jsonb_typeof(payload->'overall_score') IS DISTINCT FROM 'number'
       OR jsonb_typeof(payload->'skill_match_score') IS DISTINCT FROM 'number'
       OR jsonb_typeof(payload->'work_experience_score') IS DISTINCT FROM 'number'
       OR jsonb_typeof(payload->'matching_skills') IS DISTINCT FROM 'array'
       OR jsonb_typeof(payload->'missing_skills') IS DISTINCT FROM 'array'
       OR jsonb_typeof(payload->'verdict_summary') IS DISTINCT FROM 'string' THEN
        RETURN FALSE;
    END IF;

    IF (payload->>'overall_score')::NUMERIC NOT BETWEEN 0 AND 100
       OR (payload->>'skill_match_score')::NUMERIC NOT BETWEEN 0 AND 100
       OR (payload->>'work_experience_score')::NUMERIC NOT BETWEEN 0 AND 100 THEN
        RETURN FALSE;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM jsonb_array_elements(payload->'matching_skills') AS entries(item)
        WHERE jsonb_typeof(item) IS DISTINCT FROM 'string'
    ) OR EXISTS (
        SELECT 1
        FROM jsonb_array_elements(payload->'missing_skills') AS entries(item)
        WHERE jsonb_typeof(item) IS DISTINCT FROM 'string'
    ) THEN
        RETURN FALSE;
    END IF;

    RETURN TRUE;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'candidate_evaluations'::regclass
          AND conname = 'candidate_completed_evaluation_valid'
    ) THEN
        ALTER TABLE candidate_evaluations
            ADD CONSTRAINT candidate_completed_evaluation_valid
            CHECK (
                status <> 'completed'
                OR is_valid_unified_evaluation(evaluation)
            ) NOT VALID;
    END IF;
END;
$$;

ALTER TABLE candidate_evaluations
    VALIDATE CONSTRAINT candidate_completed_evaluation_valid;
