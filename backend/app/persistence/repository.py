"""
persistence/repository.py — Database CRUD operations.
Owner: Person 3 (M.9)

All functions use the shared asyncpg pool from app.database.get_pool().
Table schemas are defined in migrations/001_initial.sql.
"""
from __future__ import annotations

import json
from typing import Optional

from app.database import get_pool
from app.evaluation.semantic_ranker import RankedCandidate
from app.models import BatchStatus, CandidateResult, UnifiedEvaluationSchema


# ─── batch_jobs ───────────────────────────────────────────────────────────────

async def create_batch_job(batch_id: str, total_files: int) -> None:
    """
    Insert a new batch_job record with status=queued.

    """
    if total_files < 0:
        raise ValueError("total_files must not be negative.")

    pool = get_pool()
    async with pool.acquire() as connection:
        await connection.execute(
            """
            INSERT INTO batch_jobs (batch_id, total_files, status)
            VALUES ($1::uuid, $2, $3)
            """,
            batch_id,
            total_files,
            BatchStatus.queued.value,
        )


async def update_batch_status(batch_id: str, status: BatchStatus) -> None:
    """
    Update the status column of a batch_job row.

    """
    pool = get_pool()
    async with pool.acquire() as connection:
        await connection.execute(
            "UPDATE batch_jobs SET status = $1 WHERE batch_id = $2::uuid",
            status.value,
            batch_id,
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
                    evaluation = COALESCE(EXCLUDED.evaluation, candidate_evaluations.evaluation),
                    error_log = COALESCE(EXCLUDED.error_log, candidate_evaluations.error_log)
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
) -> None:
    """Persist Stage 1 scores and the candidate lifecycle they determine."""
    for candidate in ranked_candidates:
        await upsert_candidate_evaluation(
            batch_id=batch_id,
            candidate_id=candidate.candidate_id,
            status=(BatchStatus.scoring if candidate.promoted else BatchStatus.pre_filtered),
            cosine_score=candidate.cosine_similarity_score,
        )


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
              AND status IN ('completed', 'pre_filtered')
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
            # Pre-filtered candidates do not receive a Stage 2 evaluation. The
            # response retains the established numeric API fields while their
            # lifecycle state conveys that those values are not LLM scores.
            evaluation_data = {
                "overall_score": 0.0,
                "skill_match_score": 0.0,
                "matching_skills": [],
                "missing_skills": [],
                "work_experience_score": 0.0,
                "verdict_summary": "Candidate was pre-filtered before Stage 2 evaluation.",
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
