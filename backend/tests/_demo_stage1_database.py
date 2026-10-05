import asyncio
import os
import uuid
from urllib.parse import unquote, urlsplit

if not os.environ.get("TEST_DATABASE_URL"):
    raise SystemExit("Set TEST_DATABASE_URL to a disposable PostgreSQL database before running this demo.")
if "test" not in unquote(urlsplit(os.environ["TEST_DATABASE_URL"]).path).lower():
    raise SystemExit("TEST_DATABASE_URL must target a disposable database whose name contains 'test'.")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

from app.database import init_db, close_db
from app.database import get_pool
from app.persistence import repository
from app.evaluation.stage1_pipeline import rank_and_persist_batch


async def main():
    batch_id = str(uuid.uuid4())

    rubric = {
        "title": "Senior Machine Learning Engineer",
        "skills": [
            "Python",
            "PyTorch or TensorFlow",
            "NLP",
            "machine learning",
            "data pipelines",
            "model validation",
            "API deployment",
            "AWS",
            "SQL",
            "monitoring",
        ],
    }

    candidates = {
        str(uuid.uuid4()): """
        Machine Learning Engineer with 5 years of experience.
        Strong Python and PyTorch experience. Built NLP and transformer
        models, data pipelines and ML APIs. Deployed production systems
        on AWS with monitoring, SQL and model validation.
        """,

        str(uuid.uuid4()): """
        Software Engineer with experience in Python, REST APIs, SQL,
        Docker and AWS. Built backend services and some machine learning
        applications. Limited NLP and deep learning experience.
        """,

        str(uuid.uuid4()): """
        Data Analyst with Python, SQL, pandas and data visualization.
        Experienced in reporting and data cleaning, but little experience
        with machine learning model development or deployment.
        """,

        str(uuid.uuid4()): """
        Frontend developer experienced with JavaScript, React, HTML and CSS.
        Built several web applications and worked with REST APIs.
        No significant machine learning experience.
        """,
    }

    print("\n=== M.7 + M.9 REAL DATABASE DEMO ===")
    print(f"Batch ID: {batch_id}")
    print(f"Candidates: {len(candidates)}")

    database_initialized = False
    try:
        await init_db()
        database_initialized = True
        await repository.create_batch_job(
            batch_id=batch_id,
            total_files=len(candidates),
            rubric=rubric,
        )

        print("\nBatch created in PostgreSQL.")

        ranked = await rank_and_persist_batch(
            batch_id=batch_id,
            sanitized_candidate_texts=candidates,
        )

        print("\n=== RANKING RESULT ===")

        for index, candidate in enumerate(ranked, start=1):
            decision = "PROMOTED" if candidate.promoted else "PRE_FILTERED"
            print(
                f"{index}. {candidate.candidate_id} | "
                f"cosine={candidate.cosine_similarity_score:.6f} | "
                f"{decision}"
            )

        status = await repository.get_batch_status(batch_id)

        print("\n=== BATCH STATUS FROM DATABASE ===")
        print(f"status:              {status['status']}")
        print(f"total_files:         {status['total_files']}")
        print(f"processed_files:     {status['processed_files']}")
        print(f"failed_files:        {status['failed_files']}")
        print(f"pre_filtered_count:  {status['pre_filtered_count']}")

        stage2 = await repository.get_stage2_candidates(batch_id)

        print("\n=== STAGE 2 HANDOFF ===")
        print(f"Candidates promoted to Stage 2: {len(stage2)}")

        for candidate in stage2:
            print(
                f"- {candidate.candidate_id} | "
                f"cosine={candidate.cosine_similarity_score:.6f}"
            )

        print("\nDemo completed successfully.")
        print(f"Temporary Batch ID (removed after demo): {batch_id}")
    finally:
        if database_initialized:
            async with get_pool().acquire() as connection:
                await connection.execute(
                    "DELETE FROM batch_jobs WHERE batch_id = $1::uuid", batch_id
                )
            await close_db()


if __name__ == "__main__":
    asyncio.run(main())
