import json
import sys
import types

import pytest
from pydantic import ValidationError

from app.evaluation import llm_evaluator
from app.models import UnifiedEvaluationSchema


RUBRIC = "Senior data engineer: Python, SQL, and production data pipelines."
RESUME = "Anonymized resume: five years building Python and SQL data pipelines."


def valid_response():
    return {
        "overall_score": 86.0,
        "skill_match_score": 90.0,
        "matching_skills": ["Python", "SQL", "data pipelines"],
        "missing_skills": ["cloud orchestration"],
        "work_experience_score": 80.0,
        "verdict_summary": "Strong pipeline experience; cloud orchestration is not shown.",
    }


@pytest.mark.asyncio
async def test_valid_provider_response_is_validated_and_preserved(monkeypatch):
    sent_prompts = []

    async def fake_provider(prompt):
        sent_prompts.append(prompt)
        return json.dumps(valid_response())

    monkeypatch.setattr(llm_evaluator, "_generate_json", fake_provider)

    result = await llm_evaluator.evaluate_candidate("candidate-1", RESUME, RUBRIC)

    assert isinstance(result, UnifiedEvaluationSchema)
    assert result.matching_skills == ["Python", "SQL", "data pipelines"]
    assert result.missing_skills == ["cloud orchestration"]
    assert result.verdict_summary == "Strong pipeline experience; cloud orchestration is not shown."
    assert len(sent_prompts) == 1
    assert RUBRIC in sent_prompts[0]
    assert RESUME in sent_prompts[0]


@pytest.mark.asyncio
async def test_provider_failure_is_raised_as_clear_stage2_exception(monkeypatch):
    async def failed_provider(_prompt):
        raise RuntimeError("service unavailable")

    monkeypatch.setattr(llm_evaluator, "_generate_json", failed_provider)

    with pytest.raises(llm_evaluator.Stage2ProviderError, match="Gemini evaluation request failed") as error:
        await llm_evaluator.evaluate_candidate("candidate-1", RESUME, RUBRIC)

    assert isinstance(error.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_gemini_request_timeout_is_wrapped_as_provider_error(monkeypatch):
    close_calls = []

    async def slow_response(_prompt):
        import asyncio

        await asyncio.sleep(1)
        return types.SimpleNamespace(text="{}")

    class FakeModels:
        async def generate_content(self, *, model, contents, config):
            assert model == llm_evaluator.settings.gemini_model
            assert contents == "synthetic prompt"
            assert config["response_mime_type"] == "application/json"
            return await slow_response(contents)

    class FakeClient:
        def __init__(self, *, api_key):
            assert api_key == llm_evaluator.settings.gemini_api_key
            self.aio = self
            self.models = FakeModels()

        async def aclose(self):
            close_calls.append("async")

        def close(self):
            close_calls.append("sync")

    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = FakeClient
    fake_types = types.ModuleType("google.genai.types")
    fake_types.GenerateContentConfig = lambda **kwargs: kwargs
    fake_google = types.ModuleType("google")
    fake_google.__path__ = []
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)
    monkeypatch.setattr(llm_evaluator.settings, "stage2_timeout_seconds", 0.001)

    with pytest.raises(llm_evaluator.Stage2ProviderError, match="Gemini evaluation request failed"):
        await llm_evaluator._generate_json("synthetic prompt")
    assert close_calls == ["async", "sync"]


@pytest.mark.asyncio
async def test_gemini_sdk_adapter_returns_json_text_and_closes_client(monkeypatch):
    close_calls = []

    class FakeModels:
        async def generate_content(self, *, model, contents, config):
            assert model == llm_evaluator.settings.gemini_model
            assert contents == "synthetic prompt"
            assert config["response_mime_type"] == "application/json"
            return types.SimpleNamespace(text='{"overall_score": 1}')

    class FakeClient:
        def __init__(self, *, api_key):
            assert api_key == llm_evaluator.settings.gemini_api_key
            self.aio = self
            self.models = FakeModels()

        async def aclose(self):
            close_calls.append("async")

        def close(self):
            close_calls.append("sync")

    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = FakeClient
    fake_types = types.ModuleType("google.genai.types")
    fake_types.GenerateContentConfig = lambda **kwargs: kwargs
    fake_google = types.ModuleType("google")
    fake_google.__path__ = []
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)

    response_text = await llm_evaluator._generate_json("synthetic prompt")

    assert response_text == '{"overall_score": 1}'
    assert close_calls == ["async", "sync"]


@pytest.mark.asyncio
async def test_malformed_json_is_reported_without_fabricated_result(monkeypatch):
    async def malformed_provider(_prompt):
        return "not valid JSON"

    monkeypatch.setattr(llm_evaluator, "_generate_json", malformed_provider)

    with pytest.raises(llm_evaluator.Stage2ResponseError, match="malformed JSON"):
        await llm_evaluator.evaluate_candidate("candidate-1", RESUME, RUBRIC)


@pytest.mark.asyncio
async def test_schema_validation_failure_is_reported(monkeypatch):
    response = valid_response()
    del response["missing_skills"]

    async def invalid_provider(_prompt):
        return json.dumps(response)

    monkeypatch.setattr(llm_evaluator, "_generate_json", invalid_provider)

    with pytest.raises(llm_evaluator.Stage2ResponseError, match="UnifiedEvaluationSchema") as error:
        await llm_evaluator.evaluate_candidate("candidate-1", RESUME, RUBRIC)

    assert isinstance(error.value.__cause__, ValidationError)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rubric", "resume", "expected_message"),
    [("  ", RESUME, "rubric_text"), (RUBRIC, "", "resume_text")],
)
async def test_empty_inputs_are_rejected_before_provider_call(
    monkeypatch, rubric, resume, expected_message
):
    async def unexpected_provider(_prompt):
        pytest.fail("Provider must not be called for empty input.")

    monkeypatch.setattr(llm_evaluator, "_generate_json", unexpected_provider)

    with pytest.raises(ValueError, match=expected_message):
        await llm_evaluator.evaluate_candidate("candidate-1", resume, rubric)


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["overall_score", "skill_match_score", "work_experience_score"])
async def test_out_of_range_scores_fail_shared_schema_validation(monkeypatch, field):
    response = valid_response()
    response[field] = 100.1

    async def invalid_score_provider(_prompt):
        return json.dumps(response)

    monkeypatch.setattr(llm_evaluator, "_generate_json", invalid_score_provider)

    with pytest.raises(llm_evaluator.Stage2ResponseError, match="UnifiedEvaluationSchema"):
        await llm_evaluator.evaluate_candidate("candidate-1", RESUME, RUBRIC)


@pytest.mark.asyncio
async def test_extra_fields_and_nonfinite_scores_fail_schema_validation(monkeypatch):
    response = valid_response()
    response["private_note"] = "unexpected"
    response["overall_score"] = float("nan")

    async def invalid_provider(_prompt):
        return json.dumps(response)

    async def no_wait(_delay):
        return None

    monkeypatch.setattr(llm_evaluator, "_generate_json", invalid_provider)
    monkeypatch.setattr(llm_evaluator, "_retry_limit", lambda: 0)
    monkeypatch.setattr(llm_evaluator.asyncio, "sleep", no_wait)
    with pytest.raises(llm_evaluator.Stage2ResponseError, match="UnifiedEvaluationSchema"):
        await llm_evaluator.evaluate_candidate("candidate-1", RESUME, RUBRIC)


@pytest.mark.asyncio
async def test_batch_helper_returns_results_keyed_by_stage1_candidate_id(monkeypatch):
    expected = UnifiedEvaluationSchema.model_validate(valid_response())
    calls = []

    async def fake_evaluate(candidate_id, resume_text, rubric_text):
        calls.append((candidate_id, rubric_text, resume_text))
        return expected

    monkeypatch.setattr(llm_evaluator, "evaluate_candidate", fake_evaluate)
    candidates = {"candidate-1": "sanitized resume 1", "candidate-2": "sanitized resume 2"}

    results = await llm_evaluator.evaluate_batch(candidates, RUBRIC)

    assert results == {"candidate-1": expected, "candidate-2": expected}
    assert set(calls) == {
        ("candidate-1", RUBRIC, "sanitized resume 1"),
        ("candidate-2", RUBRIC, "sanitized resume 2"),
    }


@pytest.mark.asyncio
async def test_provider_failure_retries_then_returns_validated_evaluation(monkeypatch):
    calls = []
    sleeps = []

    async def flaky_provider(_prompt):
        calls.append(1)
        if len(calls) == 1:
            raise llm_evaluator.Stage2ProviderError("private provider details")
        return json.dumps(valid_response())

    async def no_wait(delay):
        sleeps.append(delay)

    monkeypatch.setattr(llm_evaluator, "_generate_json", flaky_provider)
    monkeypatch.setattr(llm_evaluator, "_retry_limit", lambda: 2)
    monkeypatch.setattr(llm_evaluator, "_backoff_seconds", lambda retry: retry * 0.25)
    monkeypatch.setattr(llm_evaluator.asyncio, "sleep", no_wait)

    result = await llm_evaluator.evaluate_candidate("candidate-1", RESUME, RUBRIC)

    assert result.overall_score == 86.0
    assert len(calls) == 2
    assert sleeps == [0.25]


@pytest.mark.asyncio
async def test_provider_failure_then_invalid_json_then_valid_response_uses_exponential_backoff(monkeypatch):
    responses = iter([
        RuntimeError("private provider detail"),
        "{invalid json",
        json.dumps(valid_response()),
    ])
    prompts = []
    delays = []

    async def mixed_provider(prompt):
        prompts.append(prompt)
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    async def capture_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(llm_evaluator, "_generate_json", mixed_provider)
    monkeypatch.setattr(llm_evaluator, "_retry_limit", lambda: 2)
    monkeypatch.setattr(llm_evaluator, "_backoff_seconds", lambda retry: 0.5 * (2 ** (retry - 1)))
    monkeypatch.setattr(llm_evaluator.asyncio, "sleep", capture_sleep)

    result = await llm_evaluator.evaluate_candidate("candidate-1", RESUME, RUBRIC)

    assert result.overall_score == 86.0
    assert len(prompts) == 3
    assert delays == [0.5, 1.0]


@pytest.mark.asyncio
async def test_invalid_schema_retries_and_exhaustion_raises_clear_error(monkeypatch):
    response = valid_response()
    response.pop("missing_skills")
    calls = []

    async def invalid_provider(_prompt):
        calls.append(1)
        return json.dumps(response)

    async def no_wait(_delay):
        return None

    monkeypatch.setattr(llm_evaluator, "_generate_json", invalid_provider)
    monkeypatch.setattr(llm_evaluator, "_retry_limit", lambda: 2)
    monkeypatch.setattr(llm_evaluator.asyncio, "sleep", no_wait)

    with pytest.raises(llm_evaluator.Stage2ResponseError, match="UnifiedEvaluationSchema"):
        await llm_evaluator.evaluate_candidate("candidate-1", RESUME, RUBRIC)
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_prompt_marks_resume_as_sanitized_and_does_not_log_provider_secrets(monkeypatch, caplog):
    prompt_texts = []

    async def fake_provider(prompt):
        prompt_texts.append(prompt)
        return json.dumps(valid_response())

    monkeypatch.setattr(llm_evaluator, "_generate_json", fake_provider)
    await llm_evaluator.evaluate_candidate("candidate-1", RESUME, RUBRIC)
    assert "Sanitized candidate resume" in prompt_texts[0]
    assert RESUME in prompt_texts[0]
    assert RUBRIC in prompt_texts[0]
    assert "candidate-1" not in prompt_texts[0]
