"""
persistence/recovery.py — Orphan-job recovery on server startup.
Owner: Person 3 (M.9)

FastAPI lifespan calls recover_orphaned_jobs() once on startup.
It finds any batch_job records stuck in queued / extracting / scoring states
(i.e. interrupted by a previous server crash) and resolves them safely.
"""
from __future__ import annotations

import logging

from app.database import get_pool
from app.models import BatchStatus

_STUCK_STATUSES = (
    BatchStatus.queued,
    BatchStatus.extracting,
    BatchStatus.scoring,
)
_logger = logging.getLogger(__name__)
_RECOVERY_MESSAGE = (
    "Job interrupted before completion and cannot be safely re-enqueued: "
    "the current schema does not retain the uploaded files or extracted text."
)


async def recover_orphaned_jobs() -> None:
    """
    Resolve orphaned batch jobs without fabricating unrecoverable pipeline input.

    Called once during FastAPI lifespan startup (see main.py).

    The schema stores a rubric but neither uploaded-file locations nor extracted
    resume text. Re-enqueuing would therefore create a new pipeline run with
    invented input. Until durable source storage is added, the safe recovery
    action is to mark interrupted jobs failed and preserve an explanatory error.
    """
    pool = get_pool()
    async with pool.acquire() as connection:
        rows = await connection.fetch(
            """
            UPDATE batch_jobs
            SET
                status = $1,
                error_log = CASE
                    WHEN error_log IS NULL OR error_log = '' THEN $2
                    ELSE error_log || E'\\n' || $2
                END
            WHERE status = ANY($3::text[])
            RETURNING batch_id
            """,
            BatchStatus.failed.value,
            _RECOVERY_MESSAGE,
            [status.value for status in _STUCK_STATUSES],
        )

    if rows:
        _logger.warning("Marked %d unrecoverable orphaned batch job(s) as failed.", len(rows))
    else:
        _logger.info("No orphaned batch jobs found during startup recovery.")
