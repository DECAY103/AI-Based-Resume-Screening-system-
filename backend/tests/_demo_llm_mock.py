"""M.8 demonstration with a mocked provider; no Gemini key or network needed."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "postgresql://demo-db.invalid/demo")
os.environ.setdefault("JWT_SECRET", "demo-only-secret")
os.environ.setdefault("GEMINI_API_KEY", "mock-provider-not-used")

from app.evaluation import llm_evaluator


async def main() -> None:
    async def mocked_provider(prompt: str) -> str:
        print("Prompt includes sanitized resume and rubric:",
              "Sanitized candidate resume" in prompt and "Job rubric" in prompt)
        return json.dumps({
            "overall_score": 84,
            "skill_match_score": 90,
            "matching_skills": ["Python", "SQL"],
            "missing_skills": ["Kubernetes"],
            "work_experience_score": 78,
            "verdict_summary": "Strong data engineering match; Kubernetes is not shown.",
        })

    llm_evaluator._generate_json = mocked_provider
    result = await llm_evaluator.evaluate_candidate(
        "candidate-demo",
        "Anonymized resume: Python, SQL, and data pipelines.",
        "Data engineer: Python, SQL, pipelines, Kubernetes.",
    )
    print("Validated UnifiedEvaluationSchema:")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
