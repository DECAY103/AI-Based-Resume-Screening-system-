import json
import os
import uuid
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

from app.models import BatchStatus, UnifiedEvaluationSchema
from app.persistence import recovery, repository
from app.evaluation.semantic_ranker import RankedCandidate


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL repository integration tests.",
)


async def _create_test_pool():
    """Apply ordered migrations only to the explicitly named test database."""
    parsed_url = urlsplit(TEST_DATABASE_URL)
    database_name = unquote(parsed_url.path.lstrip("/"))
    if "test" not in database_name.lower():
        raise RuntimeError(
            "TEST_DATABASE_URL must target a disposable PostgreSQL database whose name contains 'test'."
        )

    import asyncpg

    pool = await asyncpg.create_pool(TEST_DATABASE_URL)
    migration_dir = Path(__file__).resolve().parents[1] / "app" / "persistence" / "migrations"
    try:
        async with pool.acquire() as connection:
            for migration_path in sorted(migration_dir.glob("*.sql")):
                await connection.execute(migration_path.read_text(encoding="utf-8"))
    except Exception:
        await pool.close()
        raise
    return pool


@pytest.mark.asyncio
async def test_repository_round_trip_against_configured_postgres_test_database(monkeypatch):
    pool = await _create_test_pool()
    batch_id = str(uuid.uuid4())
    candidate_id = str(uuid.uuid4())
    monkeypatch.setattr(repository, "get_pool", lambda: pool)

    try:
        await repository.create_batch_job(batch_id, total_files=2, rubric={"title": "Engineer"})
        batch = await repository.get_batch_status(batch_id)
        assert batch is not None
        assert batch["status"] == BatchStatus.queued.value

        rejected_id = str(uuid.uuid4())
        await repository.persist_semantic_ranking(
            batch_id,
            [
                RankedCandidate(candidate_id, 0.8, True),
                RankedCandidate(rejected_id, -0.5, False),
            ],
            sanitized_candidate_texts={candidate_id: "sanitized engineer resume"},
        )
        batch = await repository.get_batch_status(batch_id)
        assert batch["processed_files"] == 1
        assert batch["failed_files"] == 0
        assert batch["pre_filtered_count"] == 1

        handoff = await repository.get_stage2_candidates(batch_id)
        assert len(handoff) == 1
        assert handoff[0].candidate_id == candidate_id
        assert handoff[0].sanitized_resume_text == "sanitized engineer resume"
        assert handoff[0].cosine_similarity_score == 0.8

        await repository.upsert_candidate_evaluation(
            batch_id,
            candidate_id,
            BatchStatus.completed,
            cosine_score=0.8,
            evaluation=UnifiedEvaluationSchema(
                overall_score=88,
                skill_match_score=90,
                matching_skills=["Python"],
                missing_skills=[],
                work_experience_score=85,
                verdict_summary="Strong relevant experience.",
            ),
        )
        await repository.update_batch_status(batch_id, BatchStatus.completed)
        results = await repository.get_batch_results(batch_id)
        assert len(results) == 2
        assert {result.status for result in results} == {BatchStatus.completed, BatchStatus.pre_filtered}
        batch = await repository.get_batch_status(batch_id)
        assert batch["status"] == BatchStatus.completed.value
        assert batch["processed_files"] == 2
        assert batch["failed_files"] == 0
        async with pool.acquire() as connection:
            persisted = await connection.fetchrow(
                """
                SELECT status, cosine_similarity_score, evaluation
                FROM candidate_evaluations
                WHERE batch_id = $1::uuid AND candidate_id = $2::uuid
                """,
                batch_id,
                candidate_id,
            )
            assert persisted["status"] == BatchStatus.completed.value
            assert persisted["cosine_similarity_score"] == 0.8
            evaluation_data = persisted["evaluation"]
            if isinstance(evaluation_data, str):
                evaluation_data = json.loads(evaluation_data)
            assert evaluation_data["overall_score"] == 88
    finally:
        async with pool.acquire() as connection:
            await connection.execute("DELETE FROM batch_jobs WHERE batch_id = $1::uuid", batch_id)
        await pool.close()


@pytest.mark.asyncio
async def test_postgres_recovery_resumes_persisted_stage2_handoff(monkeypatch):
    pool = await _create_test_pool()
    batch_id = str(uuid.uuid4())
    candidate_id = str(uuid.uuid4())
    monkeypatch.setattr(repository, "get_pool", lambda: pool)
    monkeypatch.setattr(recovery, "get_pool", lambda: pool)

    async def mocked_evaluation(_candidate_id, resume_text, rubric_text):
        assert resume_text == "sanitized recovery resume"
        assert rubric_text == '{"title": "Recovery engineer"}'
        return UnifiedEvaluationSchema(
            overall_score=80,
            skill_match_score=82,
            matching_skills=["Python"],
            missing_skills=[],
            work_experience_score=78,
            verdict_summary="Recovered evaluation.",
        )

    monkeypatch.setattr(recovery, "evaluate_candidate", mocked_evaluation)
    try:
        await repository.create_batch_job(
            batch_id, total_files=1, rubric={"title": "Recovery engineer"}
        )
        await repository.persist_semantic_ranking(
            batch_id,
            [RankedCandidate(candidate_id, 0.75, True, rank=1)],
            sanitized_candidate_texts={candidate_id: "sanitized recovery resume"},
        )
        await repository.update_batch_status(batch_id, BatchStatus.scoring)

        await recovery.recover_orphaned_jobs()

        batch = await repository.get_batch_status(batch_id)
        results = await repository.get_batch_results(batch_id)
        assert batch["status"] == BatchStatus.completed.value
        assert batch["processed_files"] == 1
        assert batch["failed_files"] == 0
        assert len(results) == 1
        assert results[0].status is BatchStatus.completed
        assert results[0].overall_score == 80
    finally:
        async with pool.acquire() as connection:
            await connection.execute("DELETE FROM batch_jobs WHERE batch_id = $1::uuid", batch_id)
        await pool.close()


@pytest.mark.asyncio
async def test_postgres_rejects_invalid_completed_evaluations_and_allows_failed_terminal_rows(
    monkeypatch,
):
    import asyncpg

    pool = await _create_test_pool()
    batch_id = str(uuid.uuid4())
    invalid_candidate_id = str(uuid.uuid4())
    failed_batch_id = str(uuid.uuid4())
    failed_candidate_id = str(uuid.uuid4())
    monkeypatch.setattr(repository, "get_pool", lambda: pool)

    try:
        await repository.create_batch_job(batch_id, total_files=1, rubric={"title": "Engineer"})
        await repository.persist_semantic_ranking(
            batch_id,
            [RankedCandidate(invalid_candidate_id, 0.8, True)],
            sanitized_candidate_texts={invalid_candidate_id: "sanitized engineer resume"},
        )
        with pytest.raises(asyncpg.CheckViolationError):
            async with pool.acquire() as connection:
                await connection.execute(
                    """
                    UPDATE candidate_evaluations
                    SET status = 'completed', evaluation = '{}'::jsonb
                    WHERE batch_id = $1::uuid AND candidate_id = $2::uuid
                    """,
                    batch_id,
                    invalid_candidate_id,
                )
        with pytest.raises(ValueError, match="incomplete evaluations"):
            await repository.update_batch_status(batch_id, BatchStatus.completed)

        await repository.create_batch_job(
            failed_batch_id, total_files=1, rubric={"title": "Engineer"}
        )
        await repository.persist_semantic_ranking(
            failed_batch_id,
            [RankedCandidate(failed_candidate_id, 0.4, True)],
            sanitized_candidate_texts={failed_candidate_id: "sanitized engineer resume"},
        )
        await repository.upsert_candidate_evaluation(
            failed_batch_id,
            failed_candidate_id,
            BatchStatus.failed,
            cosine_score=0.4,
            error_log="Stage 2 evaluation failed (Stage2ProviderError).",
        )
        await repository.update_batch_status(failed_batch_id, BatchStatus.completed)

        async with pool.acquire() as connection:
            failed_row = await connection.fetchrow(
                """
                SELECT status, evaluation, error_log
                FROM candidate_evaluations
                WHERE batch_id = $1::uuid AND candidate_id = $2::uuid
                """,
                failed_batch_id,
                failed_candidate_id,
            )
        assert failed_row["status"] == BatchStatus.failed.value
        assert failed_row["evaluation"] is None
        assert "Stage2ProviderError" in failed_row["error_log"]
    finally:
        async with pool.acquire() as connection:
            await connection.execute(
                "DELETE FROM batch_jobs WHERE batch_id = ANY($1::uuid[])",
                [batch_id, failed_batch_id],
            )
        await pool.close()
