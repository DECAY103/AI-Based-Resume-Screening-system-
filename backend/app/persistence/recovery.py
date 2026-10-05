"""
persistence/recovery.py — Orphan-job recovery on server startup.
Owner: Person 3 (M.9)

FastAPI lifespan calls recover_orphaned_jobs() once on startup.
It finds any batch_job records stuck in queued / extracting / scoring states
(i.e. interrupted by a previous server crash) and re-enqueues them.
"""
from __future__ import annotations

import asyncio
from app.pipeline import run_batch
from app.persistence.repository import list_recoverable_batches

_STUCK_STATUSES = (
    BatchStatus.queued,
    BatchStatus.extracting,
    BatchStatus.scoring,
)


async def recover_orphaned_jobs() -> None:
    """
    Scan for orphaned batch_job records and re-enqueue them.

    Called once during FastAPI lifespan startup (see main.py).

    TODO (Person 3 — M.9):
      1. Query batch_jobs WHERE status IN ('queued', 'extracting', 'scoring').
      2. For each row, re-submit the processing pipeline as a background task.
         (May require storing enough context in batch_jobs to reconstruct the task,
          e.g. original file path or Supabase storage URL.)
      3. Log how many jobs were recovered.
    """
    for batch in await list_recoverable_batches():
        if batch["upload_bytes"]:
            asyncio.create_task(run_batch(str(batch["batch_id"]), batch["upload_bytes"], batch["upload_filename"], batch["rubric"]))
