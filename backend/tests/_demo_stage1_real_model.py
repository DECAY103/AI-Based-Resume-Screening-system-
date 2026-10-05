"""Manual M.7 demonstration using the production ranker and real model.

Run from backend with the project environment, e.g.
    python tests/_demo_stage1_real_model.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings
from app.evaluation.semantic_ranker import rank_candidates


RUBRIC = """
Senior Machine Learning Engineer. Build and evaluate production machine-learning
systems, with strong Python and PyTorch or TensorFlow experience, NLP or language
model work, data preparation and feature pipelines, model validation, and
deployment behind reliable APIs on AWS or similar cloud infrastructure. SQL,
monitoring, reproducibility, and collaboration with product and engineering teams
are valuable.
""".strip()

CANDIDATES = {
    "candidate-ml-01": """
    Anonymized resume. Machine Learning Engineer with six years building NLP and
    recommendation systems in Python and PyTorch. Fine-tuned transformer models,
    designed training and feature pipelines, evaluated models with offline and
    online metrics, and deployed inference APIs to AWS using Docker. Built data
    workflows with SQL and Airflow; added model monitoring and reproducible
    training. Led delivery with product and backend engineering teams.
    """,
    "candidate-data-02": """
    Anonymized resume. Data Scientist with four years using Python, pandas,
    scikit-learn, SQL, and statistics for forecasting and customer analytics.
    Prepared datasets, selected features, validated classifiers, and presented
    results to stakeholders. Some experience packaging a model as a REST service;
    limited PyTorch, NLP, and production cloud ownership.
    """,
    "candidate-software-03": """
    Anonymized resume. Backend Software Engineer with seven years building Java
    and Kotlin services, REST APIs, PostgreSQL schemas, and AWS infrastructure.
    Experienced with reliability, automated testing, CI/CD, and service
    monitoring. Has integrated third-party prediction APIs but has not trained,
    evaluated, or deployed machine-learning models.
    """,
    "candidate-people-04": """
    Anonymized resume. Talent Acquisition Specialist with five years coordinating
    hiring, interviewing applicants, maintaining applicant tracking systems,
    arranging onboarding, preparing recruiting reports, and partnering with
    department managers. Experienced with Excel, communications, and scheduling.
    """,
}


def print_run(label: str, top_n: int, threshold: float) -> list:
    ranked = rank_candidates(
        RUBRIC,
        CANDIDATES,
        top_n=top_n,
        similarity_threshold=threshold,
    )
    print(f"\n{label}")
    print(f"Top-N: {top_n}; similarity threshold: {threshold:.6f}")
    print("Ranking order (best first):")
    for position, result in enumerate(ranked, start=1):
        decision = "PROMOTED" if result.promoted else "pre_filtered"
        print(
            f"  {position}. {result.candidate_id}: "
            f"cosine={result.cosine_similarity_score:.6f}; {decision}"
        )
    return ranked


def main() -> None:
    print("M.7 Stage 1 semantic ranking — real sentence-transformers model")
    print("Model: all-MiniLM-L6-v2 (loaded by production rank_candidates())")
    print(f"Job rubric:\n{RUBRIC}")
    print("Candidate IDs:")
    for candidate_id in CANDIDATES:
        print(f"  {candidate_id}")
    print(
        "Configured settings: "
        f"TOP_N={settings.stage1_top_n}; "
        f"SIMILARITY_THRESHOLD={settings.stage1_similarity_threshold}"
    )

    baseline_top_n = len(CANDIDATES)
    baseline_threshold = -1.0
    baseline = print_run(
        "Baseline (all candidates fit within Top-N; threshold allows full score range)",
        baseline_top_n,
        baseline_threshold,
    )

    top_n_override = min(2, len(CANDIDATES))
    top_n_run = print_run(
        "Top-N override (threshold held constant)",
        top_n_override,
        baseline_threshold,
    )

    scores = [result.cosine_similarity_score for result in baseline]
    minimum, maximum = min(scores), max(scores)
    if minimum == maximum:
        raise RuntimeError("Synthetic demo resumes produced tied scores; threshold demonstration is inconclusive.")
    threshold_override = (minimum + maximum) / 2.0
    threshold_run = print_run(
        "Similarity-threshold override (all candidates within Top-N)",
        len(CANDIDATES),
        threshold_override,
    )

    baseline_promoted = {result.candidate_id for result in baseline if result.promoted}
    top_n_promoted = {result.candidate_id for result in top_n_run if result.promoted}
    threshold_promoted = {result.candidate_id for result in threshold_run if result.promoted}
    print("\nPromotion changes:")
    print(f"  Baseline -> Top-N override: {len(baseline_promoted)} -> {len(top_n_promoted)} promoted")
    print(
        "  All candidates in Top-N -> threshold override: "
        f"{len(CANDIDATES)} -> {len(threshold_promoted)} promoted"
    )
    if (
        len(baseline_promoted) != len(CANDIDATES)
        or len(top_n_promoted) != top_n_override
        or threshold_promoted in (set(), set(CANDIDATES))
    ):
        raise RuntimeError("A configuration override did not change promotion decisions.")


if __name__ == "__main__":
    main()
