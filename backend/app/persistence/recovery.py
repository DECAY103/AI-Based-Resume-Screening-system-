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

async def recover_orphaned_jobs() -> None:
    """
    Scan for orphaned batch_job records and re-enqueue them.

    Called once during FastAPI lifespan startup (see main.py).

    The original upload bytes and rubric are stored with the job, so each
    interrupted batch can be submitted again without requiring object storage.
    """
    for batch in await list_recoverable_batches():
        if batch["upload_bytes"]:
            asyncio.create_task(run_batch(str(batch["batch_id"]), batch["upload_bytes"], batch["upload_filename"], batch["rubric"]))
