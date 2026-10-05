import asyncio
import math
import threading
import time
import types

import pytest

from app.evaluation import semantic_ranker
from app.evaluation import stage1_pipeline
from app.evaluation.llm_evaluator import Stage2ProviderError
from app.models import BatchStatus, UnifiedEvaluationSchema


class FakeEmbeddingModel:
    def __init__(self):
        self.embeddings = {
            '{"title": "rubric"}': [1.0, 0.0],
            "best sanitized resume": [1.0, 0.0],
            "near sanitized resume": [0.9, math.sqrt(0.19)],
            "below threshold": [0.0, 1.0],
            "outside top n": [-1.0, 0.0],
        }

    def encode(self, values, *, convert_to_numpy, show_progress_bar):
        assert convert_to_numpy is True
        assert show_progress_bar is False
        if isinstance(values, str):
            return self.embeddings[values]
        return [self.embeddings[value] for value in values]


@pytest.mark.asyncio
async def test_pipeline_ranks_against_batch_rubric_and_persists_filter_results(monkeypatch):
    batch_id = "00000000-0000-0000-0000-000000000001"
    candidates = {
        "00000000-0000-0000-0000-000000000005": "outside top n",
        "00000000-0000-0000-0000-000000000004": "below threshold",
        "00000000-0000-0000-0000-000000000003": "near sanitized resume",
        "00000000-0000-0000-0000-000000000002": "best sanitized resume",
    }
    captured = {}

    async def fetch_batch(_batch_id):
        assert _batch_id == batch_id
        return {"rubric": {"title": "rubric"}}

    async def persist(_batch_id, ranked, *, sanitized_candidate_texts):
        captured["batch_id"] = _batch_id
        captured["ranked"] = ranked
        captured["texts"] = sanitized_candidate_texts

    from app.config import settings

    monkeypatch.setattr(settings, "stage1_top_n", 2)
    monkeypatch.setattr(settings, "stage1_similarity_threshold", 0.95)
    monkeypatch.setattr(semantic_ranker, "_model", FakeEmbeddingModel())
    monkeypatch.setattr(stage1_pipeline.repository, "get_batch_status", fetch_batch)
    monkeypatch.setattr(stage1_pipeline.repository, "persist_semantic_ranking", persist)

    ranked = await stage1_pipeline.rank_and_persist_batch(batch_id, candidates)

    assert captured["batch_id"] == batch_id
    assert captured["texts"] == candidates
    assert [item.candidate_id for item in ranked] == [
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000003",
        "00000000-0000-0000-0000-000000000004",
        "00000000-0000-0000-0000-000000000005",
    ]
    assert [item.promoted for item in ranked] == [True, False, False, False]
    assert [item.cosine_similarity_score for item in ranked] == pytest.approx([1.0, 0.9, 0.0, -1.0])
    assert captured["ranked"] is ranked


@pytest.mark.asyncio
async def test_pipeline_handles_empty_input_and_missing_batch(monkeypatch):
    persisted = []

    async def fetch_batch(_batch_id):
        return {"rubric": "rubric"}

    async def persist(batch_id, ranked, *, sanitized_candidate_texts):
        persisted.append((batch_id, ranked, sanitized_candidate_texts))

    monkeypatch.setattr(stage1_pipeline.repository, "get_batch_status", fetch_batch)
    monkeypatch.setattr(stage1_pipeline.repository, "persist_semantic_ranking", persist)
    assert await stage1_pipeline.rank_and_persist_batch("batch", {}) == []
    assert persisted == [("batch", [], {})]

    async def missing_batch(_batch_id):
        return None

    monkeypatch.setattr(stage1_pipeline.repository, "get_batch_status", missing_batch)
    with pytest.raises(LookupError, match="does not exist"):
        await stage1_pipeline.rank_and_persist_batch("missing", {})


@pytest.mark.asyncio
async def test_ranking_runs_off_event_loop(monkeypatch):
    async def fetch_batch(_batch_id):
        return {"rubric": "rubric"}

    async def persist(*_args, **_kwargs):
        return None

    called_from_worker = []

    def blocking_ranker(*_args):
        called_from_worker.append(threading.current_thread() is not threading.main_thread())
        time.sleep(0.06)
        return []

    monkeypatch.setattr(stage1_pipeline.repository, "get_batch_status", fetch_batch)
    monkeypatch.setattr(stage1_pipeline.repository, "persist_semantic_ranking", persist)
    monkeypatch.setattr(stage1_pipeline, "rank_candidates", blocking_ranker)
    ticker_ran = False

    async def ticker():
        nonlocal ticker_ran
        await asyncio.sleep(0.01)
        ticker_ran = True

    await asyncio.gather(stage1_pipeline.rank_and_persist_batch("batch", {}), ticker())
    assert ticker_ran is True
    assert called_from_worker == [True]


def test_embedding_model_is_loaded_once(monkeypatch):
    loads = []

    class FakeSentenceTransformer:
        def __init__(self, model_name):
            loads.append(model_name)

    monkeypatch.setattr(semantic_ranker, "_model", None)
    monkeypatch.setitem(
        __import__("sys").modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )

    first = semantic_ranker._get_model()
    second = semantic_ranker._get_model()

    assert first is second
    assert loads == ["all-MiniLM-L6-v2"]


@pytest.mark.asyncio
async def test_full_person3_flow_sends_only_promoted_sanitized_text_and_persists_outcomes(monkeypatch):
    batch_id = "00000000-0000-0000-0000-000000000001"
    promoted_id = "00000000-0000-0000-0000-000000000002"
    rejected_id = "00000000-0000-0000-0000-000000000003"
    sanitized_texts = {promoted_id: "anonymized resume", rejected_id: "second resume"}
    evaluations = []
    statuses = []
    persisted_ranking = []
    expected_evaluation = UnifiedEvaluationSchema(
        overall_score=80,
        skill_match_score=85,
        matching_skills=["Python"],
        missing_skills=[],
        work_experience_score=75,
        verdict_summary="Relevant experience.",
    )

    async def update_status(_batch, status):
        statuses.append(status)

    async def fetch_batch(_batch):
        return {"rubric": {"title": "Engineer"}}

    async def persist_ranking(_batch, ranked, *, sanitized_candidate_texts):
        persisted_ranking.extend(ranked)
        assert sanitized_candidate_texts == sanitized_texts

    async def stage2_candidates(_batch):
        return [
            types.SimpleNamespace(
                candidate_id=promoted_id,
                sanitized_resume_text=sanitized_texts[promoted_id],
                cosine_similarity_score=0.91,
            )
        ]

    async def evaluate(candidate_id, resume_text, rubric_text):
        assert candidate_id == promoted_id
        assert resume_text == sanitized_texts[promoted_id]
        assert rubric_text == '{"title": "Engineer"}'
        return expected_evaluation

    async def persist_evaluation(**kwargs):
        evaluations.append(kwargs)

    monkeypatch.setattr(stage1_pipeline.repository, "update_batch_status", update_status)
    monkeypatch.setattr(stage1_pipeline.repository, "get_batch_status", fetch_batch)
    monkeypatch.setattr(stage1_pipeline.repository, "persist_semantic_ranking", persist_ranking)
    monkeypatch.setattr(stage1_pipeline.repository, "get_stage2_candidates", stage2_candidates)
    monkeypatch.setattr(stage1_pipeline.repository, "upsert_candidate_evaluation", persist_evaluation)
    monkeypatch.setattr(stage1_pipeline, "evaluate_candidate", evaluate)
    monkeypatch.setattr(
        stage1_pipeline,
        "rank_candidates",
        lambda *_args, **_kwargs: [
            semantic_ranker.RankedCandidate(promoted_id, 0.91, True, rank=1),
            semantic_ranker.RankedCandidate(rejected_id, 0.12, False, rank=2),
        ],
    )

    result = await stage1_pipeline.process_batch(batch_id, sanitized_texts)

    assert result["status"] is BatchStatus.completed
    assert result["evaluated_candidate_ids"] == [promoted_id]
    assert result["pre_filtered_count"] == 1
    assert len(persisted_ranking) == 2
    assert statuses == [BatchStatus.scoring, BatchStatus.completed]
    assert len(evaluations) == 1
    assert evaluations[0]["status"] is BatchStatus.completed
    assert evaluations[0]["evaluation"] is expected_evaluation


@pytest.mark.asyncio
async def test_evaluation_exhaustion_persists_failed_status_without_provider_details(monkeypatch):
    batch_id = "00000000-0000-0000-0000-000000000011"
    promoted_id = "00000000-0000-0000-0000-000000000012"
    filtered_id = "00000000-0000-0000-0000-000000000013"
    persisted = []
    statuses = []
    candidates = {promoted_id: "sanitized promoted resume", filtered_id: "sanitized filtered resume"}

    async def update_status(_batch_id, status):
        statuses.append(status)

    async def fetch_batch(_batch_id):
        return {"rubric": "engineer rubric"}

    async def persist_ranking(_batch_id, _ranked, *, sanitized_candidate_texts):
        assert sanitized_candidate_texts == candidates

    async def promoted_handoff(_batch_id):
        return [types.SimpleNamespace(
            candidate_id=promoted_id,
            sanitized_resume_text=candidates[promoted_id],
            cosine_similarity_score=0.88,
        )]

    async def failed_evaluation(*_args):
        raise Stage2ProviderError("sensitive provider payload")

    async def persist_evaluation(**kwargs):
        persisted.append(kwargs)

    monkeypatch.setattr(stage1_pipeline.repository, "update_batch_status", update_status)
    monkeypatch.setattr(stage1_pipeline.repository, "get_batch_status", fetch_batch)
    monkeypatch.setattr(stage1_pipeline.repository, "persist_semantic_ranking", persist_ranking)
    monkeypatch.setattr(stage1_pipeline.repository, "get_stage2_candidates", promoted_handoff)
    monkeypatch.setattr(stage1_pipeline.repository, "upsert_candidate_evaluation", persist_evaluation)
    monkeypatch.setattr(stage1_pipeline, "evaluate_candidate", failed_evaluation)
    monkeypatch.setattr(
        stage1_pipeline,
        "rank_candidates",
        lambda *_args, **_kwargs: [
            semantic_ranker.RankedCandidate(promoted_id, 0.88, True, rank=1),
            semantic_ranker.RankedCandidate(filtered_id, 0.2, False, rank=2),
        ],
    )

    result = await stage1_pipeline.process_batch(batch_id, candidates)

    assert result["failed_candidate_ids"] == [promoted_id]
    assert result["evaluated_candidate_ids"] == []
    assert len(persisted) == 1
    assert persisted[0]["status"] is BatchStatus.failed
    assert "Stage2ProviderError" in persisted[0]["error_log"]
    assert "sensitive provider payload" not in persisted[0]["error_log"]
    assert statuses == [BatchStatus.scoring, BatchStatus.completed]
