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


class CompletionGuardConnection(FakeConnection):
    def __init__(self, candidates, total_files):
        super().__init__()
        self.candidates = candidates
        self.total_files = total_files
        self.batch_status = BatchStatus.scoring.value

    async def execute(self, query, *args):
        self.calls.append(("execute", query, args))
        if "UPDATE batch_jobs SET status" not in query or args[0] != "completed":
            return "UPDATE 1"

        terminal_states = {
            BatchStatus.completed.value,
            BatchStatus.pre_filtered.value,
            BatchStatus.failed.value,
        }
        can_complete = (
            self.batch_status == BatchStatus.scoring.value
            and len(self.candidates) == self.total_files
            and all(candidate["status"] in terminal_states for candidate in self.candidates)
            and all(
                candidate["status"] != BatchStatus.completed.value
                or candidate["evaluation"] is not None
                for candidate in self.candidates
            )
        )
        if can_complete:
            self.batch_status = BatchStatus.completed.value
            return "UPDATE 1"
        return "UPDATE 0"


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

    await repository.create_batch_job(
        "00000000-0000-0000-0000-000000000001", 3, {"title": "Engineer"}
    )
    await repository.update_batch_status(
        "00000000-0000-0000-0000-000000000001", BatchStatus.extracting
    )

    assert "INSERT INTO batch_jobs" in connection.calls[0][1]
    assert connection.calls[0][2][-2] == BatchStatus.queued.value
    assert json.loads(connection.calls[0][2][-1]) == {"title": "Engineer"}
    assert "UPDATE batch_jobs SET status" in connection.calls[1][1]
    with pytest.raises(ValueError, match="total_files"):
        await repository.create_batch_job("00000000-0000-0000-0000-000000000001", -1)


@pytest.mark.asyncio
async def test_batch_completion_accepts_evaluated_and_pre_filtered_candidates(monkeypatch):
    connection = CompletionGuardConnection(
        [
            {"status": BatchStatus.completed.value, "evaluation": UnifiedEvaluationSchema(
                overall_score=88,
                skill_match_score=90,
                matching_skills=["Python"],
                missing_skills=[],
                work_experience_score=85,
                verdict_summary="Strong match.",
            )},
            {"status": BatchStatus.pre_filtered.value, "evaluation": None},
        ],
        total_files=2,
    )
    use_fake_pool(monkeypatch, connection)

    await repository.update_batch_status(
        "00000000-0000-0000-0000-000000000001", BatchStatus.completed
    )

    assert connection.batch_status == BatchStatus.completed.value
    query = connection.calls[0][1]
    assert "status NOT IN ('completed', 'pre_filtered', 'failed')" in query
    assert "status = 'completed'" in query
    assert "NOT is_valid_unified_evaluation(evaluation)" in query
    assert "SELECT COUNT(*) FROM candidate_evaluations" in query


@pytest.mark.parametrize("incomplete_status", [BatchStatus.queued, BatchStatus.scoring])
@pytest.mark.asyncio
async def test_batch_completion_rejects_candidates_still_in_progress(
    monkeypatch, incomplete_status
):
    connection = CompletionGuardConnection(
        [
            {"status": BatchStatus.completed.value, "evaluation": object()},
            {"status": incomplete_status.value, "evaluation": None},
        ],
        total_files=2,
    )
    use_fake_pool(monkeypatch, connection)

    with pytest.raises(ValueError, match="incomplete evaluations"):
        await repository.update_batch_status(
            "00000000-0000-0000-0000-000000000001", BatchStatus.completed
        )

    assert connection.batch_status == BatchStatus.scoring.value


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
async def test_candidate_cannot_be_completed_without_validated_evaluation(monkeypatch):
    connection = FakeConnection()
    use_fake_pool(monkeypatch, connection)

    with pytest.raises(ValueError, match="without a validated evaluation"):
        await repository.upsert_candidate_evaluation(
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
            BatchStatus.completed,
            0.8,
        )


@pytest.mark.asyncio
async def test_candidate_cannot_be_completed_with_an_invalid_constructed_evaluation(monkeypatch):
    connection = FakeConnection()
    use_fake_pool(monkeypatch, connection)
    invalid_evaluation = UnifiedEvaluationSchema.model_construct(
        overall_score=101,
        skill_match_score=90,
        matching_skills=["Python"],
        missing_skills=[],
        work_experience_score=85,
        verdict_summary="Invalid score.",
    )

    with pytest.raises(ValueError, match="valid evaluation"):
        await repository.upsert_candidate_evaluation(
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
            BatchStatus.completed,
            0.8,
            invalid_evaluation,
        )


@pytest.mark.asyncio
async def test_batch_level_failure_marks_running_candidates_failed_and_updates_counts(monkeypatch):
    connection = FakeConnection()
    use_fake_pool(monkeypatch, connection)

    await repository.fail_batch_job(
        "00000000-0000-0000-0000-000000000001",
        "Stage 1 ranking or persistence failed.",
    )

    writes = [call[1] for call in connection.calls if call[0] == "execute"]
    assert any("UPDATE candidate_evaluations" in query for query in writes)
    batch_update = next(query for query in writes if "UPDATE batch_jobs" in query)
    assert "processed_files" in batch_update
    assert "failed_files" in batch_update


@pytest.mark.asyncio
async def test_persist_semantic_ranking_sets_stage_one_candidate_statuses(monkeypatch):
    connection = FakeConnection(fetchrow_result={"batch_id": "00000000-0000-0000-0000-000000000001"})
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
    assert insert_calls[0][2][4] is None
    batch_update = connection.calls[-1][1]
    assert "status = 'scoring'" in batch_update
    assert "pre_filtered_count" in batch_update


@pytest.mark.asyncio
async def test_stage1_persistence_retains_only_promoted_text_and_rejects_missing_batch(monkeypatch):
    batch_id = "00000000-0000-0000-0000-000000000001"
    promoted_id = "00000000-0000-0000-0000-000000000002"
    rejected_id = "00000000-0000-0000-0000-000000000003"
    connection = FakeConnection(fetchrow_result={"batch_id": batch_id})
    use_fake_pool(monkeypatch, connection)

    await repository.persist_semantic_ranking(
        batch_id,
        [RankedCandidate(promoted_id, 0.8, True), RankedCandidate(rejected_id, -0.2, False)],
        sanitized_candidate_texts={promoted_id: "sanitized resume", rejected_id: "rejected resume"},
    )

    writes = [call for call in connection.calls if call[0] == "execute" and "INSERT INTO candidate_evaluations" in call[1]]
    assert writes[0][2][4] == "sanitized resume"
    assert writes[1][2][4] is None

    missing_connection = FakeConnection(fetchrow_result=None)
    use_fake_pool(monkeypatch, missing_connection)
    with pytest.raises(LookupError, match="does not exist"):
        await repository.persist_semantic_ranking(batch_id, [])


@pytest.mark.asyncio
async def test_stage2_handoff_returns_promoted_candidate_contract(monkeypatch):
    connection = FakeConnection(
        fetchrow_result={"batch_id": "00000000-0000-0000-0000-000000000001"},
        fetch_result=[
            {
                "batch_id": "00000000-0000-0000-0000-000000000001",
                "candidate_id": "00000000-0000-0000-0000-000000000002",
                "sanitized_resume_text": "sanitized resume",
                "cosine_similarity_score": 0.75,
            }
        ],
    )
    use_fake_pool(monkeypatch, connection)

    result = await repository.get_stage2_candidates("00000000-0000-0000-0000-000000000001")

    assert len(result) == 1
    assert result[0].batch_id == "00000000-0000-0000-0000-000000000001"
    assert result[0].candidate_id == "00000000-0000-0000-0000-000000000002"
    assert result[0].sanitized_resume_text == "sanitized resume"
    assert result[0].cosine_similarity_score == 0.75
    assert "status = 'scoring'" in connection.calls[1][1]


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
    connection = FakeConnection(fetch_result=[{
        "batch_id": "00000000-0000-0000-0000-000000000001",
        "status": BatchStatus.queued.value,
        "total_files": 1,
        "rubric": None,
    }])
    monkeypatch.setattr(recovery, "get_pool", lambda: FakePool(connection))
    monkeypatch.setattr(repository, "get_pool", lambda: FakePool(connection))

    await recovery.recover_orphaned_jobs()

    calls = [call for call in connection.calls if call[0] == "execute"]
    assert any("UPDATE candidate_evaluations" in call[1] for call in calls)
    assert any("UPDATE batch_jobs" in call[1] for call in calls)
    assert connection.calls[0][0] == "transaction"


@pytest.mark.asyncio
async def test_recovery_retries_scoring_handoff_using_only_persisted_sanitized_text(monkeypatch):
    batch_id = "00000000-0000-0000-0000-000000000021"
    promoted_id = "00000000-0000-0000-0000-000000000022"
    filtered_id = "00000000-0000-0000-0000-000000000023"
    batch_rows = [{
        "batch_id": batch_id,
        "status": BatchStatus.scoring.value,
        "total_files": 2,
        "rubric": {"title": "Engineer"},
    }]
    candidate_rows = [
        {
            "candidate_id": promoted_id,
            "status": BatchStatus.scoring.value,
            "sanitized_resume_text": "sanitized promoted resume",
            "cosine_similarity_score": 0.9,
        },
        {
            "candidate_id": filtered_id,
            "status": BatchStatus.pre_filtered.value,
            "sanitized_resume_text": None,
            "cosine_similarity_score": 0.2,
        },
    ]

    class RecoveryConnection(FakeConnection):
        async def fetch(self, query, *args):
            self.calls.append(("fetch", query, args))
            return batch_rows if "FROM batch_jobs" in query else candidate_rows

    connection = RecoveryConnection()
    monkeypatch.setattr(recovery, "get_pool", lambda: FakePool(connection))
    persisted = []
    statuses = []
    expected = UnifiedEvaluationSchema(
        overall_score=88,
        skill_match_score=90,
        matching_skills=["Python"],
        missing_skills=[],
        work_experience_score=85,
        verdict_summary="Strong match.",
    )
    evaluated = []

    async def evaluate(candidate_id, resume_text, rubric_text):
        evaluated.append((candidate_id, resume_text, rubric_text))
        return expected

    async def persist(**kwargs):
        persisted.append(kwargs)

    async def update_status(_batch_id, status):
        statuses.append(status)

    monkeypatch.setattr(recovery, "evaluate_candidate", evaluate)
    monkeypatch.setattr(repository, "upsert_candidate_evaluation", persist)
    monkeypatch.setattr(repository, "update_batch_status", update_status)

    await recovery.recover_orphaned_jobs()

    assert evaluated == [(promoted_id, "sanitized promoted resume", '{"title": "Engineer"}')]
    assert len(persisted) == 1
    assert persisted[0]["candidate_id"] == promoted_id
    assert persisted[0]["status"] is BatchStatus.completed
    assert persisted[0]["evaluation"] is expected
    assert statuses == [BatchStatus.completed]
