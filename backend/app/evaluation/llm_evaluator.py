"""Stage 2 scoring with optional Gemini and a no-cost deterministic fallback."""
from __future__ import annotations

import asyncio
import json
import re

from app.config import settings
from app.models import UnifiedEvaluationSchema

_MAX_RETRIES = 2
_SYSTEM_PROMPT = """Evaluate the anonymised resume against the rubric. Return only JSON with overall_score, skill_match_score, matching_skills, missing_skills, work_experience_score, verdict_summary. All score values must be floats from 0 to 100."""


def _keywords(text: str) -> set[str]:
    stop = {"the", "and", "with", "for", "from", "that", "this", "have", "years", "experience", "candidate", "resume", "role", "job", "skills"}
    return {word.lower() for word in re.findall(r"[A-Za-z][A-Za-z+#.]{1,}", text) if word.lower() not in stop}


def _heuristic_evaluate(resume_text: str, rubric_text: str) -> UnifiedEvaluationSchema:
    required = _keywords(rubric_text)
    present = _keywords(resume_text)
    matching = sorted(required & present)[:20]
    missing = sorted(required - present)[:20]
    skill = round(100 * len(matching) / max(1, len(required)), 1)
    years = [int(value) for value in re.findall(r"(\d{1,2})\+?\s+years?", resume_text.lower())]
    experience = min(100.0, float((max(years) if years else 0) * 20))
    overall = round(skill * 0.75 + experience * 0.25, 1)
    summary = f"Keyword-based fallback score: {len(matching)} rubric terms matched and {len(missing)} gaps identified. Recruiter review is required."
    return UnifiedEvaluationSchema(overall_score=overall, skill_match_score=skill, matching_skills=matching, missing_skills=missing, work_experience_score=experience, verdict_summary=summary)


async def _gemini_evaluate(resume_text: str, rubric_text: str) -> UnifiedEvaluationSchema:
    import google.generativeai as genai
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.gemini_model)
    prompt = f"{_SYSTEM_PROMPT}\n\nJOB RUBRIC:\n{rubric_text}\n\nANONYMISED RESUME:\n{resume_text}"
    response = await model.generate_content_async(prompt)
    raw = response.text.strip().removeprefix("```json").removesuffix("```").strip()
    return UnifiedEvaluationSchema.model_validate(json.loads(raw))


async def evaluate_candidate(candidate_id: str, resume_text: str, rubric_text: str) -> UnifiedEvaluationSchema:
    if settings.llm_provider.lower() in {"heuristic", "free", "local"}:
        return _heuristic_evaluate(resume_text, rubric_text)
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            if settings.llm_provider.lower() == "gemini":
                return await _gemini_evaluate(resume_text, rubric_text)
            raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
        except Exception as exc:
            last_error = exc
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(2 ** attempt)
    raise ValueError(f"Evaluation failed for {candidate_id}: {last_error}")


async def evaluate_batch(candidates: dict[str, str], rubric_text: str) -> dict[str, UnifiedEvaluationSchema]:
    values = await asyncio.gather(*(evaluate_candidate(candidate_id, text, rubric_text) for candidate_id, text in candidates.items()), return_exceptions=True)
    return {candidate_id: value for candidate_id, value in zip(candidates, values) if isinstance(value, UnifiedEvaluationSchema)}
