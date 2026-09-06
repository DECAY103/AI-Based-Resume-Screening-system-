import pytest
from fastapi import HTTPException

from app.models import BatchStatus, CandidateResult
from app.routers import jobs


@pytest.mark.asyncio
async def test_status_endpoint_returns_persisted_progress(monkeypatch):
    async def fetch_status(batch_id):
        assert batch_id == "00000000-0000-0000-0000-000000000001"
        return {
            "status": BatchStatus.scoring.value,
            "total_files": 4,
            "processed_files": 2,
            "failed_files": 1,
            "pre_filtered_count": 1,
        }

    monkeypatch.setattr(jobs, "fetch_batch_status", fetch_status)

    response = await jobs.get_batch_status("00000000-0000-0000-0000-000000000001")

    assert response.status is BatchStatus.scoring
    assert response.progress_percentage == 50.0
    assert response.failed_files == 1


@pytest.mark.asyncio
async def test_status_endpoint_returns_not_found_for_unknown_batch(monkeypatch):
    async def fetch_status(batch_id):
        return None

    monkeypatch.setattr(jobs, "fetch_batch_status", fetch_status)

    with pytest.raises(HTTPException) as exception:
        await jobs.get_batch_status("00000000-0000-0000-0000-000000000001")

    assert exception.value.status_code == 404


@pytest.mark.asyncio
async def test_results_endpoint_requires_completion_then_returns_results(monkeypatch):
    async def in_progress_status(batch_id):
        return {"status": BatchStatus.scoring.value}

    monkeypatch.setattr(jobs, "fetch_batch_status", in_progress_status)
    with pytest.raises(HTTPException) as exception:
        await jobs.get_batch_results("00000000-0000-0000-0000-000000000001")
    assert exception.value.status_code == 409

    expected_results = [
        CandidateResult(
            candidate_id="00000000-0000-0000-0000-000000000002",
            overall_score=80.0,
            skill_match_score=75.0,
            work_experience_score=70.0,
            matching_skills=["Python"],
            missing_skills=[],
            verdict_summary="Good match",
            cosine_similarity_score=0.7,
            status=BatchStatus.completed,
        )
    ]

    async def completed_status(batch_id):
        return {"status": BatchStatus.completed.value}

    async def fetch_results(batch_id):
        return expected_results

    monkeypatch.setattr(jobs, "fetch_batch_status", completed_status)
    monkeypatch.setattr(jobs, "fetch_batch_results", fetch_results)

    response = await jobs.get_batch_results("00000000-0000-0000-0000-000000000001")

    assert response.results == expected_results
