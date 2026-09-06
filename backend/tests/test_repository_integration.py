import os
import uuid

import pytest

from app.models import BatchStatus
from app.persistence import repository


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL repository integration tests.",
)


@pytest.mark.asyncio
async def test_repository_round_trip_against_configured_postgres_test_database(monkeypatch):
    import asyncpg

    pool = await asyncpg.create_pool(TEST_DATABASE_URL)
    batch_id = str(uuid.uuid4())
    candidate_id = str(uuid.uuid4())
    monkeypatch.setattr(repository, "get_pool", lambda: pool)

    try:
        await repository.create_batch_job(batch_id, total_files=1)
        batch = await repository.get_batch_status(batch_id)
        assert batch is not None
        assert batch["status"] == BatchStatus.queued.value

        await repository.upsert_candidate_evaluation(
            batch_id,
            candidate_id,
            BatchStatus.pre_filtered,
            cosine_score=-0.5,
        )
        batch = await repository.get_batch_status(batch_id)
        assert batch["processed_files"] == 1
        assert batch["pre_filtered_count"] == 1

        await repository.update_batch_status(batch_id, BatchStatus.completed)
        results = await repository.get_batch_results(batch_id)
        assert len(results) == 1
        assert results[0].cosine_similarity_score == -0.5
        assert results[0].status is BatchStatus.pre_filtered
    finally:
        async with pool.acquire() as connection:
            await connection.execute("DELETE FROM batch_jobs WHERE batch_id = $1::uuid", batch_id)
        await pool.close()
