"""Async integration boundary for Person 3 Stage 1 after sanitisation."""
from __future__ import annotations

import asyncio
import json
from typing import Mapping

from app.evaluation.semantic_ranker import RankedCandidate, rank_candidates
from app.evaluation.llm_evaluator import evaluate_candidate
from app.persistence import repository
from app.models import BatchStatus


def _rubric_text(rubric: object) -> str:
    """Convert the batch's stored JSON rubric into stable embedding input."""
    if isinstance(rubric, str):
        rubric = rubric.strip()
        if not rubric:
            raise ValueError("Batch job rubric must not be empty.")
        try:
            parsed_rubric = json.loads(rubric)
        except json.JSONDecodeError:
            return rubric
        if isinstance(parsed_rubric, dict) and parsed_rubric:
            return json.dumps(parsed_rubric, sort_keys=True, ensure_ascii=False)
        if isinstance(parsed_rubric, str) and parsed_rubric.strip():
            return parsed_rubric.strip()
        raise ValueError("Batch job rubric must be a non-empty object or text.")
    if isinstance(rubric, dict) and rubric:
        return json.dumps(rubric, sort_keys=True, ensure_ascii=False)
    raise ValueError("Batch has no valid job rubric.")


async def rank_and_persist_batch(
    batch_id: str,
    sanitized_candidate_texts: Mapping[str, str],
) -> list[RankedCandidate]:
    """Rank sanitized candidate texts against the stored batch rubric.

    Call this at the end of the upstream M.3–M.6 pipeline. Embedding inference
    runs in a worker thread; Stage 1 results and promoted sanitized text are
    committed together by the existing repository.
    """
    batch = await repository.get_batch_status(batch_id)
    if batch is None:
        raise LookupError(f"Batch {batch_id} does not exist.")

    expected_count = batch.get("total_files")
    if expected_count is not None and int(expected_count) != len(sanitized_candidate_texts):
        raise ValueError(
            "Sanitized candidate count does not match the batch total_files value."
        )
    rubric_text = _rubric_text(batch.get("rubric"))
    candidates = dict(sanitized_candidate_texts)
    ranked = await asyncio.to_thread(rank_candidates, rubric_text, candidates)
    await repository.persist_semantic_ranking(
        batch_id,
        ranked,
        sanitized_candidate_texts=candidates,
    )
    return ranked


async def process_batch(
    batch_id: str,
    sanitized_candidate_texts: Mapping[str, str],
) -> dict[str, object]:
    """Run M.7, evaluate promoted candidates with M.8, and persist M.9 results.

    ``sanitized_candidate_texts`` maps each upstream candidate ID to its
    already anonymized and adversarially scanned text. The rubric is loaded
    from ``batch_jobs.rubric`` using ``batch_id``. Inputs must already be
    sanitized by the upstream M.5/M.6 flow. Only promoted
    resume text is retained for the Stage 2 handoff. Candidate evaluation
    failures are isolated and persisted per candidate; database failures
    propagate to the caller.
    """
    await repository.update_batch_status(batch_id, BatchStatus.scoring)
    try:
        ranked = await rank_and_persist_batch(batch_id, sanitized_candidate_texts)
    except Exception:
        # Keep the batch from appearing queued/scoring after a pipeline error.
        await repository.fail_batch_job(batch_id, "Stage 1 ranking or persistence failed.")
        raise

    batch = await repository.get_batch_status(batch_id)
    if batch is None:
        raise LookupError(f"Batch {batch_id} does not exist.")
    rubric_text = _rubric_text(batch.get("rubric"))
    handoff = await repository.get_stage2_candidates(batch_id)
    succeeded: list[str] = []
    failed: list[str] = []

    for candidate in handoff:
        try:
            evaluation = await evaluate_candidate(
                candidate.candidate_id,
                candidate.sanitized_resume_text,
                rubric_text,
            )
        except Exception as exc:
            # Persist only the stable exception type. Provider SDK exception
            # text can contain request content, so it is intentionally omitted.
            await repository.upsert_candidate_evaluation(
                batch_id=batch_id,
                candidate_id=candidate.candidate_id,
                status=BatchStatus.failed,
                cosine_score=candidate.cosine_similarity_score,
                error_log=f"Stage 2 evaluation failed ({type(exc).__name__}).",
            )
            failed.append(candidate.candidate_id)
            continue

        await repository.upsert_candidate_evaluation(
            batch_id=batch_id,
            candidate_id=candidate.candidate_id,
            status=BatchStatus.completed,
            cosine_score=candidate.cosine_similarity_score,
            evaluation=evaluation,
        )
        succeeded.append(candidate.candidate_id)

    await repository.update_batch_status(batch_id, BatchStatus.completed)
    return {
        "batch_id": batch_id,
        "status": BatchStatus.completed,
        "ranked_candidates": ranked,
        "evaluated_candidate_ids": succeeded,
        "failed_candidate_ids": failed,
        "pre_filtered_count": sum(not candidate.promoted for candidate in ranked),
    }
