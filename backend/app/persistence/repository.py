"""Database CRUD for authentication, jobs, and evaluation records."""
from __future__ import annotations

import json
from typing import Any, Optional

from app.database import get_pool
from app.models import BatchStatus, CandidateResult, UnifiedEvaluationSchema, UserRole


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {})


async def create_user(email: str, password_hash: str, role: UserRole, totp_secret: str) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "INSERT INTO users (email, password_hash, role, totp_secret) VALUES ($1,$2,$3,$4) RETURNING id,email,role,totp_secret",
                email.lower(), password_hash, role.value, totp_secret,
            )
        except Exception as exc:
            if getattr(exc, "sqlstate", None) == "23505":
                raise ValueError("An account with that email already exists.") from exc
            raise
    return dict(row)


async def get_user_by_email(email: str) -> Optional[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id,email,password_hash,role,totp_secret FROM users WHERE email=$1", email.lower())
    return dict(row) if row else None


async def get_user(user_id: str) -> Optional[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id,email,password_hash,role,totp_secret FROM users WHERE id=$1::uuid", user_id)
    return dict(row) if row else None


async def create_batch_job(batch_id: str, total_files: int, rubric: Any, upload_bytes: bytes, upload_filename: str) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO batch_jobs (batch_id,total_files,rubric,upload_bytes,upload_filename) VALUES ($1::uuid,$2,$3::jsonb,$4,$5)",
            batch_id, total_files, _json(rubric), upload_bytes, upload_filename,
        )


async def update_batch_status(batch_id: str, status: BatchStatus, error_log: str | None = None) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE batch_jobs SET status=$1,error_log=COALESCE($2,error_log) WHERE batch_id=$3::uuid", status.value, error_log, batch_id)


async def get_batch_status(batch_id: str) -> Optional[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT b.batch_id,b.status,b.total_files,
                      COUNT(c.id) FILTER (WHERE c.status IN ('completed','pre_filtered','failed')) processed_files,
                      COUNT(c.id) FILTER (WHERE c.status='failed') failed_files,
                      COUNT(c.id) FILTER (WHERE c.status='pre_filtered') pre_filtered_count
               FROM batch_jobs b LEFT JOIN candidate_evaluations c ON c.batch_id=b.batch_id
               WHERE b.batch_id=$1::uuid GROUP BY b.batch_id""", batch_id)
    return dict(row) if row else None


async def get_batch_context(batch_id: str) -> Optional[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT batch_id,rubric,upload_bytes,upload_filename,status FROM batch_jobs WHERE batch_id=$1::uuid", batch_id)
    return dict(row) if row else None


async def list_recoverable_batches() -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT batch_id,rubric,upload_bytes,upload_filename FROM batch_jobs WHERE status=ANY($1::text[])", ["queued", "extracting", "scoring"])
    return [dict(row) for row in rows]


async def upsert_candidate_evaluation(batch_id: str, candidate_id: str, status: BatchStatus, cosine_score: float = 0.0, evaluation: Optional[UnifiedEvaluationSchema] = None, error_log: Optional[str] = None, filename: str | None = None) -> None:
    pool = get_pool()
    payload = json.dumps(evaluation.model_dump()) if evaluation else None
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO candidate_evaluations (batch_id,candidate_id,status,cosine_similarity_score,evaluation,error_log,filename)
               VALUES ($1::uuid,$2::uuid,$3,$4,$5::jsonb,$6,$7)
               ON CONFLICT (batch_id,candidate_id) DO UPDATE SET status=EXCLUDED.status,
               cosine_similarity_score=EXCLUDED.cosine_similarity_score,evaluation=COALESCE(EXCLUDED.evaluation,candidate_evaluations.evaluation),
               error_log=EXCLUDED.error_log,filename=COALESCE(EXCLUDED.filename,candidate_evaluations.filename)""",
            batch_id, candidate_id, status.value, cosine_score, payload, error_log, filename)


async def get_batch_results(batch_id: str) -> list[CandidateResult]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT candidate_id,status,cosine_similarity_score,evaluation,error_log FROM candidate_evaluations WHERE batch_id=$1::uuid ORDER BY (evaluation->>'overall_score')::float DESC NULLS LAST,cosine_similarity_score DESC", batch_id)
    results: list[CandidateResult] = []
    for row in rows:
        value = row["evaluation"] or {}
        evaluation = json.loads(value) if isinstance(value, str) else value
        prefiltered = row["status"] == "pre_filtered"
        results.append(CandidateResult(
            candidate_id=str(row["candidate_id"]), status=BatchStatus(row["status"]), cosine_similarity_score=float(row["cosine_similarity_score"] or 0),
            overall_score=float(evaluation.get("overall_score", 0)), skill_match_score=float(evaluation.get("skill_match_score", 0)), work_experience_score=float(evaluation.get("work_experience_score", 0)),
            matching_skills=evaluation.get("matching_skills", []), missing_skills=evaluation.get("missing_skills", []),
            verdict_summary=evaluation.get("verdict_summary", "Not selected for detailed evaluation." if prefiltered else row["error_log"] or "Evaluation unavailable."),
        ))
    return results
