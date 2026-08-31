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
from app.models import BatchStatus, CandidateResult, UnifiedEvaluationSchema


# ─── batch_jobs ───────────────────────────────────────────────────────────────

async def create_batch_job(batch_id: str, total_files: int) -> None:
    """
    Insert a new batch_job record with status=queued.

    TODO (Person 3 — M.9): INSERT INTO batch_jobs (batch_id, total_files, status) VALUES (...)
    """
    raise NotImplementedError("[M.9] create_batch_job not yet implemented.")


async def update_batch_status(batch_id: str, status: BatchStatus) -> None:
    """
    Update the status column of a batch_job row.

    TODO (Person 3 — M.9): UPDATE batch_jobs SET status=$1 WHERE batch_id=$2
    """
    raise NotImplementedError("[M.9] update_batch_status not yet implemented.")


async def get_batch_status(batch_id: str) -> Optional[dict]:
    """
    Fetch a batch_job row by batch_id.

    Returns None if not found.

    TODO (Person 3 — M.9): SELECT * FROM batch_jobs WHERE batch_id=$1
    """
    raise NotImplementedError("[M.9] get_batch_status not yet implemented.")


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

    TODO (Person 3 — M.9):
      INSERT INTO candidate_evaluations
        (batch_id, candidate_id, status, cosine_similarity_score, evaluation, error_log)
      VALUES ($1, $2, $3, $4, $5::jsonb, $6)
      ON CONFLICT (candidate_id) DO UPDATE SET ...
    """
    raise NotImplementedError("[M.9] upsert_candidate_evaluation not yet implemented.")


async def get_batch_results(batch_id: str) -> list[CandidateResult]:
    """
    Fetch all candidate_evaluations for a batch, ordered by overall_score DESC.

    TODO (Person 3 — M.9):
      SELECT * FROM candidate_evaluations
      WHERE batch_id=$1
      ORDER BY (evaluation->>'overall_score')::float DESC
    """
    raise NotImplementedError("[M.9] get_batch_results not yet implemented.")
