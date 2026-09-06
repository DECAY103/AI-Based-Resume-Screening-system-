"""
evaluation/semantic_ranker.py — Stage 1 semantic pre-filtering.
Owner: Person 3 (M.7)

Uses sentence-transformers (all-MiniLM-L6-v2) to encode résumé texts and the
job rubric into dense vectors, then ranks candidates by cosine similarity.

The top-N candidates (configured via settings.stage1_top_n) are promoted to
Stage 2 LLM evaluation. The rest receive status "pre_filtered".

IMPORTANT: sentence-transformers inference is CPU-bound and synchronous.
           Call rank_candidates() inside asyncio.to_thread().
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from threading import Lock
from typing import Any, Iterable


_MODEL_NAME = "all-MiniLM-L6-v2"
_model: Any | None = None
_model_lock = Lock()


@dataclass
class RankedCandidate:
    candidate_id: str
    cosine_similarity_score: float
    promoted: bool  # True → goes to Stage 2; False → pre_filtered


def _get_model() -> Any:
    """Load the embedding model at most once, on the worker thread that needs it."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    """Return mathematical cosine similarity, treating zero vectors as unrelated."""
    left_values = [float(value) for value in left]
    right_values = [float(value) for value in right]
    if len(left_values) != len(right_values):
        raise ValueError("Embedding vectors must have the same dimensionality.")

    dot_product = sum(left_value * right_value for left_value, right_value in zip(left_values, right_values))
    left_norm = sqrt(sum(value * value for value in left_values))
    right_norm = sqrt(sum(value * value for value in right_values))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def _resolve_similarity_threshold(similarity_threshold: float | None) -> float:
    if similarity_threshold is None:
        # Import lazily so callers that explicitly provide a threshold do not
        # require application settings simply to use the pure ranking routine.
        from app.config import settings

        similarity_threshold = settings.stage1_similarity_threshold

    if not -1.0 <= similarity_threshold <= 1.0:
        raise ValueError("similarity_threshold must be between -1.0 and 1.0.")
    return float(similarity_threshold)


def _resolve_top_n(top_n: int | None) -> int:
    if top_n is None:
        from app.config import settings

        top_n = settings.stage1_top_n

    if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n < 0:
        raise ValueError("top_n must be a non-negative integer.")
    return top_n


def rank_candidates(
    rubric_text: str,
    candidates: dict[str, str],
    top_n: int | None = None,
    *,
    similarity_threshold: float | None = None,
) -> list[RankedCandidate]:
    """
    Rank candidates by semantic similarity to the job rubric.

    Args:
        rubric_text: Plain-text representation of the job rubric.
        candidates: Mapping of candidate_id → anonymised résumé text.
        top_n: Number of top candidates to promote to Stage 2. When omitted,
            uses settings.stage1_top_n.
        similarity_threshold: Minimum cosine similarity required for promotion.
            When omitted, uses settings.stage1_similarity_threshold.

    Returns:
        List of RankedCandidate, sorted by cosine_similarity_score descending.
        Candidates are promoted only when they are within Top-N and meet the
        configured similarity threshold.

    IMPORTANT: Run inside asyncio.to_thread().

    """
    resolved_top_n = _resolve_top_n(top_n)
    threshold = _resolve_similarity_threshold(similarity_threshold)
    if not candidates:
        return []
    if not rubric_text or not rubric_text.strip():
        raise ValueError("rubric_text must not be empty.")

    candidate_items = sorted(candidates.items(), key=lambda item: item[0])
    model = _get_model()
    rubric_embedding = model.encode(
        rubric_text,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    candidate_embeddings = model.encode(
        [resume_text for _, resume_text in candidate_items],
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    if len(candidate_embeddings) != len(candidate_items):
        raise ValueError("Model returned an unexpected number of candidate embeddings.")

    scored_candidates = [
        (candidate_id, _cosine_similarity(rubric_embedding, resume_embedding))
        for (candidate_id, _), resume_embedding in zip(candidate_items, candidate_embeddings)
    ]
    scored_candidates.sort(key=lambda item: (-item[1], item[0]))

    return [
        RankedCandidate(
            candidate_id=candidate_id,
            cosine_similarity_score=score,
            promoted=rank < resolved_top_n and score >= threshold,
        )
        for rank, (candidate_id, score) in enumerate(scored_candidates)
    ]
