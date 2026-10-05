"""
persistence/repository.py — Database CRUD operations.
Owner: Person 3 (M.9)

All functions use the shared asyncpg pool from app.database.get_pool().
Table schemas are defined in migrations/001_initial.sql.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from pydantic import ValidationError

from app.database import get_pool
from app.evaluation.semantic_ranker import RankedCandidate
from app.models import BatchStatus, CandidateResult, UnifiedEvaluationSchema


@dataclass(frozen=True)
class Stage2Candidate:
    """Sanitized Stage 1 output ready for a future M.8 evaluator."""

    batch_id: str
    candidate_id: str
    sanitized_resume_text: str
    cosine_similarity_score: float


# ─── batch_jobs ───────────────────────────────────────────────────────────────

async def create_batch_job(batch_id: str, total_files: int, rubric: object = None) -> None:
    """
    Insert a new batch_job record with status=queued.
    The optional rubric is serialized to JSONB for the Stage 1 pipeline boundary.
    """
    if total_files < 0:
        raise ValueError("total_files must not be negative.")

    rubric_json = json.dumps(rubric) if rubric is not None else None
    pool = get_pool()
    async with pool.acquire() as connection:
        await connection.execute(
            """
            INSERT INTO batch_jobs (batch_id, total_files, status, rubric)
            VALUES ($1::uuid, $2, $3, $4::jsonb)
            """,
            batch_id,
            total_files,
            BatchStatus.queued.value,
            rubric_json,
        )


async def update_batch_status(batch_id: str, status: BatchStatus) -> None:
    """
    Update the status column of a batch_job row.

    """
    pool = get_pool()
    async with pool.acquire() as connection:
        result = await connection.execute(
            """
            UPDATE batch_jobs SET status = $1
            WHERE batch_id = $2::uuid
              AND (
                  status = $1
                  OR (status = 'queued' AND $1 IN ('extracting', 'scoring', 'failed'))
                  OR (status = 'extracting' AND $1 IN ('scoring', 'failed'))
                  OR (status = 'scoring' AND $1 IN ('completed', 'failed'))
              )
              AND ($1 <> 'completed' OR NOT EXISTS (
                  SELECT 1 FROM candidate_evaluations
                  WHERE batch_id = $2::uuid
                    AND (status NOT IN ('completed', 'pre_filtered', 'failed')
                         OR (status = 'completed'
                             AND NOT is_valid_unified_evaluation(evaluation)))
              ))
              AND ($1 <> 'completed' OR (
                  SELECT COUNT(*) FROM candidate_evaluations
                  WHERE batch_id = $2::uuid
              ) = (
                  SELECT total_files FROM batch_jobs WHERE batch_id = $2::uuid
              ))
            """,
            status.value,
            batch_id,
        )
    if result == "UPDATE 0":
        raise ValueError(
            "Batch does not exist, has an invalid status transition, or still has incomplete evaluations."
        )


async def get_batch_status(batch_id: str) -> Optional[dict]:
    """
    Fetch a batch_job row by batch_id.

    Returns None if not found.

    """
    pool = get_pool()
    async with pool.acquire() as connection:
        row = await connection.fetchrow(
            "SELECT * FROM batch_jobs WHERE batch_id = $1::uuid",
            batch_id,
        )
    return dict(row) if row is not None else None


# ─── candidate_evaluations ────────────────────────────────────────────────────

async def upsert_candidate_evaluation(
    batch_id: str,
    candidate_id: str,
    status: BatchStatus,
    cosine_score: float,
    evaluation: Optional[UnifiedEvaluationSchema] = None,
    error_log: Optional[str] = None,
) -> None:
    """
    Insert or update a candidate_evaluation row.

    The evaluation field (UnifiedEvaluationSchema) is stored as JSONB.

    """
    if status is BatchStatus.completed:
        if evaluation is None:
            raise ValueError("A candidate cannot be completed without a validated evaluation.")
        evaluation_data = (
            evaluation.model_dump(mode="python")
            if isinstance(evaluation, UnifiedEvaluationSchema)
            else evaluation
        )
        try:
            evaluation = UnifiedEvaluationSchema.model_validate(evaluation_data)
        except ValidationError as exc:
            raise ValueError(
                "A candidate cannot be completed without a valid evaluation."
            ) from exc
    evaluation_json = (
        json.dumps(evaluation.model_dump(mode="json")) if evaluation is not None else None
    )
    pool = get_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                """
                INSERT INTO candidate_evaluations (
                    batch_id,
                    candidate_id,
                    status,
                    cosine_similarity_score,
                    evaluation,
                    error_log
                )
                VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, $6)
                ON CONFLICT (batch_id, candidate_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    cosine_similarity_score = EXCLUDED.cosine_similarity_score,
                    evaluation = EXCLUDED.evaluation,
                    error_log = EXCLUDED.error_log
                """,
                batch_id,
                candidate_id,
                status.value,
                cosine_score,
                evaluation_json,
                error_log,
            )
            await connection.execute(
                """
                UPDATE batch_jobs
                SET
                    processed_files = counts.processed_files,
                    failed_files = counts.failed_files,
                    pre_filtered_count = counts.pre_filtered_count
                FROM (
                    SELECT
                        COUNT(*) FILTER (
                            WHERE status IN ('pre_filtered', 'completed', 'failed')
                        )::int AS processed_files,
                        COUNT(*) FILTER (WHERE status = 'failed')::int AS failed_files,
                        COUNT(*) FILTER (WHERE status = 'pre_filtered')::int AS pre_filtered_count
                    FROM candidate_evaluations
                    WHERE batch_id = $1::uuid
                ) AS counts
                WHERE batch_jobs.batch_id = $1::uuid
                """,
                batch_id,
            )


async def persist_semantic_ranking(
    batch_id: str,
    ranked_candidates: list[RankedCandidate],
    sanitized_candidate_texts: Optional[dict[str, str]] = None,
) -> None:
    """Atomically persist every Stage 1 score and the resulting candidate state."""
    pool = get_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            batch = await connection.fetchrow(
                "SELECT batch_id FROM batch_jobs WHERE batch_id = $1::uuid FOR UPDATE",
                batch_id,
            )
            if batch is None:
                raise LookupError(f"Batch {batch_id} does not exist.")

            for candidate in ranked_candidates:
                resume_text = None
                if candidate.promoted and sanitized_candidate_texts is not None:
                    resume_text = sanitized_candidate_texts[candidate.candidate_id]
                await connection.execute(
                    """
                    INSERT INTO candidate_evaluations (
                        batch_id, candidate_id, status,
                        cosine_similarity_score, sanitized_resume_text
                    )
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5)
                    ON CONFLICT (batch_id, candidate_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        cosine_similarity_score = EXCLUDED.cosine_similarity_score,
                        sanitized_resume_text = EXCLUDED.sanitized_resume_text,
                        evaluation = NULL,
                        error_log = NULL
                    """,
                    batch_id,
                    candidate.candidate_id,
                    BatchStatus.scoring.value if candidate.promoted else BatchStatus.pre_filtered.value,
                    candidate.cosine_similarity_score,
                    resume_text,
                )

            result = await connection.execute(
                """
                UPDATE batch_jobs
                SET
                    status = 'scoring',
                    processed_files = counts.processed_files,
                    failed_files = counts.failed_files,
                    pre_filtered_count = counts.pre_filtered_count
                FROM (
                    SELECT
                        COUNT(*) FILTER (
                            WHERE status IN ('pre_filtered', 'completed', 'failed')
                        )::int AS processed_files,
                        COUNT(*) FILTER (WHERE status = 'failed')::int AS failed_files,
                        COUNT(*) FILTER (WHERE status = 'pre_filtered')::int AS pre_filtered_count
                    FROM candidate_evaluations
                    WHERE batch_id = $1::uuid
                ) AS counts
                WHERE batch_jobs.batch_id = $1::uuid
                  AND batch_jobs.status IN ('queued', 'extracting', 'scoring')
                """,
                batch_id,
            )
            if result == "UPDATE 0":
                raise ValueError(
                    "Batch is not in a state that permits Stage 1 results to be persisted."
                )


async def get_stage2_candidates(batch_id: str) -> list[Stage2Candidate]:
    """Return promoted candidates with their sanitized text and Stage 1 scores."""
    pool = get_pool()
    async with pool.acquire() as connection:
        batch = await connection.fetchrow(
            "SELECT batch_id FROM batch_jobs WHERE batch_id = $1::uuid",
            batch_id,
        )
        if batch is None:
            raise LookupError(f"Batch {batch_id} does not exist.")
        rows = await connection.fetch(
            """
            SELECT batch_id, candidate_id, sanitized_resume_text,
                   cosine_similarity_score
            FROM candidate_evaluations
            WHERE batch_id = $1::uuid
              AND status = 'scoring'
              AND sanitized_resume_text IS NOT NULL
              AND cosine_similarity_score IS NOT NULL
            ORDER BY cosine_similarity_score DESC, candidate_id ASC
            """,
            batch_id,
        )
    return [
        Stage2Candidate(
            batch_id=str(row["batch_id"]),
            candidate_id=str(row["candidate_id"]),
            sanitized_resume_text=row["sanitized_resume_text"],
            cosine_similarity_score=float(row["cosine_similarity_score"]),
        )
        for row in rows
    ]


async def get_batch_results(batch_id: str) -> list[CandidateResult]:
    """
    Fetch all candidate_evaluations for a batch, ordered by overall_score DESC.

    """
    pool = get_pool()
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            SELECT candidate_id, status, cosine_similarity_score, evaluation
            FROM candidate_evaluations
            WHERE batch_id = $1::uuid
              AND status IN ('completed', 'pre_filtered', 'failed')
            ORDER BY
                CASE WHEN status = 'completed' THEN 0 ELSE 1 END,
                (evaluation->>'overall_score')::double precision DESC NULLS LAST,
                cosine_similarity_score DESC NULLS LAST,
                candidate_id ASC
            """,
            batch_id,
        )

    results: list[CandidateResult] = []
    for row in rows:
        evaluation_data = row["evaluation"]
        if isinstance(evaluation_data, str):
            evaluation_data = json.loads(evaluation_data)
        if evaluation_data is None:
            # Non-evaluated terminal candidates do not receive Stage 2 scores.
            # Keep the existing numeric result contract and use status to
            # distinguish those placeholders from actual evaluation scores.
            evaluation_data = {
                "overall_score": 0.0,
                "skill_match_score": 0.0,
                "matching_skills": [],
                "missing_skills": [],
                "work_experience_score": 0.0,
                "verdict_summary": (
                    "Candidate was pre-filtered before Stage 2 evaluation."
                    if row["status"] == BatchStatus.pre_filtered.value
                    else "Candidate evaluation failed; no Stage 2 score is available."
                ),
            }
        evaluation = UnifiedEvaluationSchema.model_validate(evaluation_data)
        results.append(
            CandidateResult(
                candidate_id=str(row["candidate_id"]),
                cosine_similarity_score=float(row["cosine_similarity_score"]),
                status=BatchStatus(row["status"]),
                **evaluation.model_dump(),
            )
        )
    return results


async def fail_batch_job(batch_id: str, error_message: str) -> None:
    """Mark a batch-level failure and preserve a concise diagnostic."""
    if not error_message or not error_message.strip():
        raise ValueError("error_message must not be empty.")
    pool = get_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            await connection.execute(
                """
                UPDATE candidate_evaluations
                SET status = $1,
                    error_log = CASE WHEN error_log IS NULL OR error_log = ''
                                     THEN $2 ELSE error_log || E'\\n' || $2 END
                WHERE batch_id = $3::uuid
                  AND status NOT IN ('completed', 'pre_filtered', 'failed')
                """,
                BatchStatus.failed.value,
                error_message,
                batch_id,
            )
            result = await connection.execute(
                """
                UPDATE batch_jobs
                SET status = $1,
                    error_log = CASE WHEN error_log IS NULL OR error_log = ''
                                     THEN $2 ELSE error_log || E'\\n' || $2 END,
                    processed_files = batch_jobs.total_files,
                    failed_files = LEAST(
                        batch_jobs.total_files,
                        (SELECT COUNT(*) FROM candidate_evaluations
                         WHERE batch_id = $3::uuid AND status = 'failed')
                        + GREATEST(
                            batch_jobs.total_files - (SELECT COUNT(*) FROM candidate_evaluations
                                                      WHERE batch_id = $3::uuid),
                            0
                        )
                    ),
                    pre_filtered_count = (SELECT COUNT(*) FROM candidate_evaluations
                                          WHERE batch_id = $3::uuid AND status = 'pre_filtered')
                WHERE batch_jobs.batch_id = $3::uuid
                """,
                BatchStatus.failed.value,
                error_message,
                batch_id,
            )
    if result == "UPDATE 0":
        raise LookupError(f"Batch {batch_id} does not exist.")
