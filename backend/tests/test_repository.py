import json
from contextlib import asynccontextmanager

import pytest

from app.models import BatchStatus, UnifiedEvaluationSchema
from app.evaluation.semantic_ranker import RankedCandidate
from app.persistence import recovery, repository


class FakeConnection:
    def __init__(self, *, fetchrow_result=None, fetch_result=None):
        self.fetchrow_result = fetchrow_result
        self.fetch_result = fetch_result if fetch_result is not None else []
        self.calls = []

    async def execute(self, query, *args):
        self.calls.append(("execute", query, args))
        return "UPDATE 1"

    async def fetchrow(self, query, *args):
        self.calls.append(("fetchrow", query, args))
        return self.fetchrow_result

    async def fetch(self, query, *args):
        self.calls.append(("fetch", query, args))
        return self.fetch_result

    @asynccontextmanager
    async def transaction(self):
        self.calls.append(("transaction", None, ()))
        yield


class FakePool:
    def __init__(self, connection):
        self.connection = connection

    @asynccontextmanager
    async def acquire(self):
        yield self.connection


def use_fake_pool(monkeypatch, connection):
    monkeypatch.setattr(repository, "get_pool", lambda: FakePool(connection))


@pytest.mark.asyncio
async def test_create_batch_and_update_status_use_parameterized_schema_queries(monkeypatch):
    connection = FakeConnection()
    use_fake_pool(monkeypatch, connection)

    await repository.create_batch_job("00000000-0000-0000-0000-000000000001", 3)
    await repository.update_batch_status(
        "00000000-0000-0000-0000-000000000001", BatchStatus.extracting
    )

    assert "INSERT INTO batch_jobs" in connection.calls[0][1]
    assert connection.calls[0][2][-1] == BatchStatus.queued.value
    assert "UPDATE batch_jobs SET status" in connection.calls[1][1]
    with pytest.raises(ValueError, match="total_files"):
        await repository.create_batch_job("00000000-0000-0000-0000-000000000001", -1)


@pytest.mark.asyncio
async def test_get_batch_status_returns_none_for_a_missing_batch(monkeypatch):
    connection = FakeConnection(fetchrow_result=None)
    use_fake_pool(monkeypatch, connection)

    assert await repository.get_batch_status("00000000-0000-0000-0000-000000000001") is None


@pytest.mark.asyncio
async def test_upsert_persists_cosine_evaluation_and_batch_counts(monkeypatch):
    connection = FakeConnection()
    use_fake_pool(monkeypatch, connection)
    evaluation = UnifiedEvaluationSchema(
        overall_score=95,
        skill_match_score=90,
        matching_skills=["Python"],
        missing_skills=[],
        work_experience_score=80,
        verdict_summary="Strong match",
    )

    await repository.upsert_candidate_evaluation(
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        BatchStatus.completed,
        -0.25,
        evaluation,
    )

    insert_call = connection.calls[1]
    assert "ON CONFLICT (batch_id, candidate_id)" in insert_call[1]
    assert insert_call[2][3] == -0.25
    assert json.loads(insert_call[2][4])["overall_score"] == 95.0
    assert "pre_filtered_count" in connection.calls[2][1]


@pytest.mark.asyncio
async def test_persist_semantic_ranking_sets_stage_one_candidate_statuses(monkeypatch):
    connection = FakeConnection()
    use_fake_pool(monkeypatch, connection)

    await repository.persist_semantic_ranking(
        "00000000-0000-0000-0000-000000000001",
        [
            RankedCandidate("00000000-0000-0000-0000-000000000002", 0.8, True),
            RankedCandidate("00000000-0000-0000-0000-000000000003", -0.2, False),
        ],
    )

    insert_calls = [
        call
        for call in connection.calls
        if call[0] == "execute" and "INSERT INTO candidate_evaluations" in call[1]
    ]
    assert [call[2][2] for call in insert_calls] == [
        BatchStatus.scoring.value,
        BatchStatus.pre_filtered.value,
    ]


@pytest.mark.asyncio
async def test_batch_results_include_pre_filtered_candidates_with_stage_one_score(monkeypatch):
    connection = FakeConnection(
        fetch_result=[
            {
                "candidate_id": "00000000-0000-0000-0000-000000000002",
                "status": "completed",
                "cosine_similarity_score": 0.8,
                "evaluation": json.dumps(
                    {
                        "overall_score": 80,
                        "skill_match_score": 70,
                        "matching_skills": ["Python"],
                        "missing_skills": [],
                        "work_experience_score": 75,
                        "verdict_summary": "Good match",
                    }
                ),
            },
            {
                "candidate_id": "00000000-0000-0000-0000-000000000003",
                "status": "pre_filtered",
                "cosine_similarity_score": -0.4,
                "evaluation": None,
            },
        ]
    )
    use_fake_pool(monkeypatch, connection)

    results = await repository.get_batch_results("00000000-0000-0000-0000-000000000001")

    assert [result.status for result in results] == [BatchStatus.completed, BatchStatus.pre_filtered]
    assert results[1].cosine_similarity_score == -0.4
    assert results[1].overall_score == 0.0
    assert "pre-filtered" in results[1].verdict_summary


@pytest.mark.asyncio
async def test_recovery_marks_jobs_failed_when_pipeline_input_cannot_be_reconstructed(monkeypatch):
    connection = FakeConnection(fetch_result=[{"batch_id": "00000000-0000-0000-0000-000000000001"}])
    monkeypatch.setattr(recovery, "get_pool", lambda: FakePool(connection))

    await recovery.recover_orphaned_jobs()

    call = connection.calls[0]
    assert "UPDATE batch_jobs" in call[1]
    assert call[2][0] == BatchStatus.failed.value
    assert call[2][2] == ["queued", "extracting", "scoring"]
