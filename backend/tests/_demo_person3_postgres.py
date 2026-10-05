"""End-to-end Person 3 demo using PostgreSQL and a mocked Gemini response.

Requires TEST_DATABASE_URL, schema migrations, and the all-MiniLM-L6-v2 model.
The Gemini provider is mocked so this demo never requires a real API key.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import unquote, urlsplit

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("JWT_SECRET", "demo-only-secret")
os.environ.setdefault("GEMINI_API_KEY", "mock-provider-not-used")
if not os.environ.get("TEST_DATABASE_URL"):
    raise SystemExit("Set TEST_DATABASE_URL to a disposable PostgreSQL database before running this demo.")
if "test" not in unquote(urlsplit(os.environ["TEST_DATABASE_URL"]).path).lower():
    raise SystemExit("TEST_DATABASE_URL must target a disposable database whose name contains 'test'.")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

from app.database import close_db, get_pool, init_db
from app.evaluation import llm_evaluator
from app.evaluation.stage1_pipeline import process_batch
from app.config import settings
from app.models import BatchStatus
from app.persistence import repository


async def main() -> None:
    async def mocked_provider(prompt: str) -> str:
        assert "Sanitized candidate resume" in prompt
        assert "Job rubric" in prompt
        return json.dumps({
            "overall_score": 82,
            "skill_match_score": 86,
            "matching_skills": ["Python", "SQL"],
            "missing_skills": ["Kubernetes"],
            "work_experience_score": 78,
            "verdict_summary": "Relevant data engineering experience.",
        })

    llm_evaluator._generate_json = mocked_provider
    # Deliberate demonstration overrides: exercise both paths deterministically.
    settings.stage1_top_n = 2
    settings.stage1_similarity_threshold = -1.0
    batch_id = str(uuid.uuid4())
    rubric = {"title": "Data Engineer", "skills": ["Python", "SQL", "pipelines"]}
    candidates = {
        str(uuid.uuid4()): "Anonymized: Python, SQL, ETL pipelines, and production data systems.",
        str(uuid.uuid4()): "Anonymized: SQL reports, data cleaning, and dashboard maintenance.",
        str(uuid.uuid4()): "Anonymized: Java APIs, frontend components, and CSS layouts.",
        str(uuid.uuid4()): "Anonymized: warehouse modeling, Python ETL, SQL optimization, and data quality checks.",
    }
    print("=== PERSON 3 PIPELINE ===")
    print("Batch ID:", batch_id)
    print("Candidates received:", len(candidates))
    database_initialized = False
    try:
        await init_db()
        database_initialized = True
        await repository.create_batch_job(batch_id, len(candidates), rubric)
        run = await process_batch(batch_id, candidates)
        batch = await repository.get_batch_status(batch_id)
        results = await repository.get_batch_results(batch_id)
        assert batch["status"] == BatchStatus.completed.value
        async with get_pool().acquire() as connection:
            database_candidates = await connection.fetch(
                """
                SELECT candidate_id, status, cosine_similarity_score, evaluation
                FROM candidate_evaluations
                WHERE batch_id = $1::uuid
                ORDER BY cosine_similarity_score DESC, candidate_id ASC
                """,
                batch_id,
            )
        assert len(database_candidates) == len(candidates)
        print("\nM.7 RANKING")
        for candidate in run["ranked_candidates"]:
            decision = "PROMOTED" if candidate.promoted else "PRE_FILTERED"
            print(
                f"{candidate.rank}. {candidate.candidate_id} | "
                f"cosine={candidate.cosine_similarity_score:.4f} | {decision}"
            )
        print("\nM.7 PROMOTED")
        for candidate in run["ranked_candidates"]:
            if candidate.promoted:
                print(candidate.candidate_id)
        print("\nM.7 PRE-FILTERED")
        for candidate in run["ranked_candidates"]:
            if not candidate.promoted:
                print(candidate.candidate_id)
        print("\nM.8 EVALUATION (mocked provider; schema validated)")
        for result in results:
            if result.status is BatchStatus.completed:
                print(f"candidate_id: {result.candidate_id}")
                print(f"overall_score: {result.overall_score}")
                print(f"skill_match_score: {result.skill_match_score}")
                print(f"work_experience_score: {result.work_experience_score}")
                print(f"matching_skills: {result.matching_skills}")
                print(f"missing_skills: {result.missing_skills}")
                print(f"verdict_summary: {result.verdict_summary}")
        print("\nM.9 DATABASE")
        print("Batch persisted:", batch["status"] == BatchStatus.completed.value)
        print("Candidate results persisted:", len(results))
        print("Direct SQL candidate rows:")
        for candidate in database_candidates:
            evaluation_data = candidate["evaluation"]
            if isinstance(evaluation_data, str):
                evaluation_data = json.loads(evaluation_data)
            print({
                "candidate_id": str(candidate["candidate_id"]),
                "status": candidate["status"],
                "cosine_similarity_score": candidate["cosine_similarity_score"],
                "evaluation_result": evaluation_data,
            })
        print("Counters:", {
            key: batch[key] for key in
            ("total_files", "processed_files", "failed_files", "pre_filtered_count")
        })
        print("\nFINAL STATUS")
        print(batch["status"])
        print("\nDirect PostgreSQL verification SQL (using canonical application columns):")
        print(
            "SELECT batch_id, total_files, processed_files, failed_files, "
            "pre_filtered_count, status FROM batch_jobs WHERE batch_id = '",
            batch_id,
            "';",
            sep="",
        )
        print(
            "SELECT candidate_id, status, cosine_similarity_score, evaluation "
            "FROM candidate_evaluations WHERE batch_id = '",
            batch_id,
            "' ORDER BY cosine_similarity_score DESC;",
            sep="",
        )
    finally:
        if database_initialized:
            async with get_pool().acquire() as connection:
                await connection.execute(
                    "DELETE FROM batch_jobs WHERE batch_id = $1::uuid", batch_id
                )
            await close_db()


if __name__ == "__main__":
    asyncio.run(main())
