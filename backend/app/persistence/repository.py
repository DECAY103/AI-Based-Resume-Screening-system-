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
        row = await conn.fetchrow("SELECT id,email,password_hash,role,totp_secret,last_login_at FROM users WHERE email=$1", email.lower())
    return dict(row) if row else None


async def get_user(user_id: str) -> Optional[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id,email,password_hash,role,totp_secret,last_login_at FROM users WHERE id=$1::uuid", user_id)
    return dict(row) if row else None


async def update_last_login(user_id: str) -> Optional[str]:
    """Set last_login_at to NOW() and return the *previous* value (for display)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            previous = await conn.fetchval(
                "SELECT last_login_at FROM users WHERE id=$1::uuid", user_id,
            )
            await conn.execute(
                "UPDATE users SET last_login_at=NOW() WHERE id=$1::uuid", user_id,
            )
    if previous:
        return previous.isoformat()
    return None


async def update_password(user_id: str, new_password_hash: str) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET password_hash=$1 WHERE id=$2::uuid", new_password_hash, user_id)


# ─── Activity Logs ────────────────────────────────────────────────────────────

async def log_activity(
    action: str,
    *,
    user_id: str | None = None,
    email: str | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO activity_logs (user_id,email,action,detail,ip_address,user_agent) VALUES ($1::uuid,$2,$3,$4,$5,$6)",
            user_id, email, action, detail, ip_address, user_agent,
        )


async def get_activity_logs(user_id: str | None = None, limit: int = 50) -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        if user_id:
            rows = await conn.fetch(
                "SELECT id,user_id,email,action,detail,ip_address,user_agent,created_at FROM activity_logs WHERE user_id=$1::uuid ORDER BY created_at DESC LIMIT $2",
                user_id, limit,
            )
        else:
            rows = await conn.fetch(
                "SELECT id,user_id,email,action,detail,ip_address,user_agent,created_at FROM activity_logs ORDER BY created_at DESC LIMIT $1",
                limit,
            )
    return [dict(r) for r in rows]


# ─── Password Reset Tokens ────────────────────────────────────────────────────

async def create_password_reset_token(user_id: str, token: str, expires_at) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO password_reset_tokens (user_id,token,expires_at) VALUES ($1::uuid,$2,$3)",
            user_id, token, expires_at,
        )


async def get_valid_reset_token(token: str) -> Optional[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id,user_id,token,expires_at FROM password_reset_tokens WHERE token=$1 AND used=FALSE AND expires_at > NOW()",
            token,
        )
    return dict(row) if row else None


async def mark_reset_token_used(token: str) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE password_reset_tokens SET used=TRUE WHERE token=$1", token)


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


async def get_candidate_filename(batch_id: str, candidate_id: str) -> str | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        value = await conn.fetchval("SELECT filename FROM candidate_evaluations WHERE batch_id=$1::uuid AND candidate_id=$2::uuid", batch_id, candidate_id)
    return str(value) if value else None
