"""Persistent background pipeline implementing M.3 through M.9."""
from __future__ import annotations

import asyncio
import io
import json
import traceback
import uuid
import zipfile

from app.config import settings
from app.evaluation.llm_evaluator import evaluate_candidate
from app.evaluation.semantic_ranker import rank_candidates
from app.ingestion.extractor import extract_text
from app.ingestion.validator import check_pdf, check_zip
from app.models import BatchStatus
from app.persistence import repository
from app.sanitisation.adversarial import scan_safe
from app.sanitisation.anonymiser import anonymise


def rubric_to_text(rubric: object) -> str:
    return json.dumps(rubric, indent=2) if isinstance(rubric, (dict, list)) else str(rubric)


def _files(payload: bytes, filename: str) -> list[tuple[str, bytes]]:
    if filename.lower().endswith(".zip"):
        names = check_zip(payload)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            return [(name, archive.read(name)) for name in names]
    check_pdf(payload)
    return [(filename, payload)]


def _process_file(name: str, payload: bytes) -> tuple[str | None, str | None]:
    try:
        check_pdf(payload)
        text = extract_text(payload)
        sanitised = anonymise(text)
        safe, reason = scan_safe(sanitised)
        return (sanitised, None if safe else reason)
    except Exception as exc:
        return (None, str(exc))


async def run_batch(batch_id: str, payload: bytes, filename: str, rubric: object) -> None:
    try:
        await repository.update_batch_status(batch_id, BatchStatus.extracting)
        files = await asyncio.to_thread(_files, payload, filename)
        clean: dict[str, str] = {}
        for name, item in files:
            candidate_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{batch_id}:{name}"))
            text, error = await asyncio.to_thread(_process_file, name, item)
            if error or not text:
                await repository.upsert_candidate_evaluation(batch_id, candidate_id, BatchStatus.failed, error_log=error or "No usable text.", filename=name)
            else:
                clean[candidate_id] = text
                await repository.upsert_candidate_evaluation(batch_id, candidate_id, BatchStatus.extracting, filename=name)
        if not clean:
            await repository.update_batch_status(batch_id, BatchStatus.failed, "No resume passed ingestion and safety checks.")
            return
        await repository.update_batch_status(batch_id, BatchStatus.scoring)
        rubric_text = rubric_to_text(rubric)
        ranked = await asyncio.to_thread(rank_candidates, rubric_text, clean, settings.stage1_top_n)
        shortlisted: dict[str, str] = {}
        for candidate in ranked:
            if candidate.promoted and candidate.cosine_similarity_score >= settings.min_similarity_score:
                shortlisted[candidate.candidate_id] = clean[candidate.candidate_id]
                await repository.upsert_candidate_evaluation(batch_id, candidate.candidate_id, BatchStatus.scoring, candidate.cosine_similarity_score)
            else:
                await repository.upsert_candidate_evaluation(batch_id, candidate.candidate_id, BatchStatus.pre_filtered, candidate.cosine_similarity_score)
        for candidate_id, text in shortlisted.items():
            try:
                evaluation = await evaluate_candidate(candidate_id, text, rubric_text)
                score = next(item.cosine_similarity_score for item in ranked if item.candidate_id == candidate_id)
                await repository.upsert_candidate_evaluation(batch_id, candidate_id, BatchStatus.completed, score, evaluation)
            except Exception as exc:
                await repository.upsert_candidate_evaluation(batch_id, candidate_id, BatchStatus.failed, error_log=str(exc))
        await repository.update_batch_status(batch_id, BatchStatus.completed)
    except Exception:
        await repository.update_batch_status(batch_id, BatchStatus.failed, traceback.format_exc())
