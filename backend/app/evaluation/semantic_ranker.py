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

# TODO (Person 3 — M.7): Load model once at module level.
# from sentence_transformers import SentenceTransformer
# _model = SentenceTransformer("all-MiniLM-L6-v2")


@dataclass
class RankedCandidate:
    candidate_id: str
    cosine_similarity_score: float
    promoted: bool  # True → goes to Stage 2; False → pre_filtered


def rank_candidates(
    rubric_text: str,
    candidates: dict[str, str],
    top_n: int,
) -> list[RankedCandidate]:
    """
    Rank candidates by semantic similarity to the job rubric.

    Args:
        rubric_text: Plain-text representation of the job rubric.
        candidates: Mapping of candidate_id → anonymised résumé text.
        top_n: Number of top candidates to promote to Stage 2.

    Returns:
        List of RankedCandidate, sorted by cosine_similarity_score descending.
        Top-N have promoted=True; the rest have promoted=False.

    IMPORTANT: Run inside asyncio.to_thread().

    TODO (Person 3 — M.7):
      1. Encode rubric_text with _model.encode([rubric_text]).
      2. Encode all résumé texts in a single batch for efficiency.
      3. Compute cosine similarity between rubric embedding and each résumé.
         (scipy.spatial.distance.cosine or util.cos_sim from sentence_transformers).
      4. Sort by score descending; set promoted=True for indices < top_n.
      5. Return the sorted RankedCandidate list.
    """
    raise NotImplementedError("[M.7] rank_candidates not yet implemented.")
