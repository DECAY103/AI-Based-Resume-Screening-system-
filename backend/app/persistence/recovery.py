"""Resume safely recoverable Stage 2 work and fail unreconstructable jobs."""
from __future__ import annotations

import json
import logging

from app.database import get_pool
from app.evaluation.llm_evaluator import evaluate_candidate
from app.models import BatchStatus
from app.persistence import repository


_STUCK_STATUSES = (
    BatchStatus.queued.value,
    BatchStatus.extracting.value,
    BatchStatus.scoring.value,
)
_UNRECOVERABLE_MESSAGE = (
    "Job interrupted before Stage 1 handoff; uploaded files and sanitized source "
    "candidate text are not available for reconstruction."
)
_MISSING_HANDOFF_MESSAGE = (
    "Interrupted Stage 2 candidate has no persisted sanitized resume or job rubric."
)
_logger = logging.getLogger(__name__)


def _rubric_text(rubric: object) -> str:
    """Convert a stored JSON rubric to stable text for an interrupted M.8 call."""
    if isinstance(rubric, str):
        rubric = rubric.strip()
        if not rubric:
            raise ValueError("Job rubric is empty.")
        try:
            parsed_rubric = json.loads(rubric)
        except json.JSONDecodeError:
            return rubric
        if isinstance(parsed_rubric, dict) and parsed_rubric:
            return json.dumps(parsed_rubric, sort_keys=True, ensure_ascii=False)
        if isinstance(parsed_rubric, str) and parsed_rubric.strip():
            return parsed_rubric.strip()
        raise ValueError("Job rubric is not a non-empty object or text.")
    if isinstance(rubric, dict) and rubric:
        return json.dumps(rubric, sort_keys=True, ensure_ascii=False)
    raise ValueError("Job rubric is missing or invalid.")


async def _resume_stage2(batch: dict) -> None:
    """Retry persisted Stage 1 promotions using their stored sanitized text."""
    batch_id = str(batch["batch_id"])
    try:
        rubric_text = _rubric_text(batch.get("rubric"))
    except ValueError:
        await repository.fail_batch_job(batch_id, _MISSING_HANDOFF_MESSAGE)
        return

    pool = get_pool()
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            SELECT candidate_id, status, sanitized_resume_text,
                   cosine_similarity_score
            FROM candidate_evaluations
            WHERE batch_id = $1::uuid
            ORDER BY candidate_id ASC
            """,
            batch_id,
        )

    for row in rows:
        if row["status"] != BatchStatus.scoring.value:
            continue
        candidate_id = str(row["candidate_id"])
        resume_text = row["sanitized_resume_text"]
        cosine_score = row["cosine_similarity_score"]
        if not isinstance(resume_text, str) or not resume_text.strip() or cosine_score is None:
            await repository.upsert_candidate_evaluation(
                batch_id=batch_id,
                candidate_id=candidate_id,
                status=BatchStatus.failed,
                cosine_score=float(cosine_score or 0.0),
                error_log=_MISSING_HANDOFF_MESSAGE,
            )
            continue
        try:
            evaluation = await evaluate_candidate(candidate_id, resume_text, rubric_text)
        except Exception as exc:
            # Keep SDK/request details out of persistent diagnostics.
            await repository.upsert_candidate_evaluation(
                batch_id=batch_id,
                candidate_id=candidate_id,
                status=BatchStatus.failed,
                cosine_score=float(cosine_score),
                error_log=f"Recovered Stage 2 evaluation failed ({type(exc).__name__}).",
            )
            continue
        await repository.upsert_candidate_evaluation(
            batch_id=batch_id,
            candidate_id=candidate_id,
            status=BatchStatus.completed,
            cosine_score=float(cosine_score),
            evaluation=evaluation,
        )

    if len(rows) != int(batch["total_files"]):
        await repository.fail_batch_job(
            batch_id,
            "Interrupted batch has no persisted candidate record for every source file.",
        )
        return
    await repository.update_batch_status(batch_id, BatchStatus.completed)


async def recover_orphaned_jobs() -> None:
    """Resume stored Stage 2 handoffs; fail jobs whose inputs were not saved.

    Queued/extracting jobs cannot be reconstructed because uploads and sanitized
    source text are not stored. Scoring jobs have a narrower recovery path: M.7
    persisted its scores and promoted sanitized resumes, so those M.8 calls can
    safely be retried without re-running M.7 or using unsanitized inputs.
    """
    pool = get_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            rows = await connection.fetch(
                """
                SELECT batch_id, status, total_files, rubric
                FROM batch_jobs
                WHERE status = ANY($1::text[])
                FOR UPDATE
                """,
                list(_STUCK_STATUSES),
            )

    resumed_count = 0
    failed_count = 0
    for row in rows:
        batch = dict(row)
        if batch["status"] == BatchStatus.scoring.value:
            await _resume_stage2(batch)
            resumed_count += 1
        else:
            await repository.fail_batch_job(
                str(batch["batch_id"]),
                _UNRECOVERABLE_MESSAGE,
            )
            failed_count += 1

    if rows:
        _logger.info(
            "Startup recovery handled %d batch(es): %d Stage 2 handoff(s) retried, "
            "%d pre-handoff job(s) marked failed.",
            len(rows),
            resumed_count,
            failed_count,
        )
    else:
        _logger.info("No orphaned batch jobs found during startup recovery.")
