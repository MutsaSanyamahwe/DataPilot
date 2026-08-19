# app/explainer/service.py
#
# The only file that talks to Gemini for explanation. Two entry points:
#   - get_explanation(): LLM call for narrating a successful AnalysisResult.
#   - explain_failure(): LLM call for explaining a FAILED plan and
#     suggesting real rephrasings, using the dataset's actual columns.
# Same structural pattern for both: one client, structured output via
# response_schema, no manual JSON parsing.

from google import genai
from google.genai import types
from google.genai.errors import ClientError

from app.config import settings
from app.analysis.registry import AnalysisResult
from app.explainer.schemas import Explanation, FailureExplanation
from app.explainer.prompt import build_explainer_prompt, build_failure_prompt
from app.llm_errors import LLMRateLimitError, LLMServiceError


_client = genai.Client(api_key=settings.google_api_key)


def get_explanation(user_question: str, result: AnalysisResult) -> Explanation:
    """
    Calls Gemini to turn a computed AnalysisResult into a plain-English
    explanation plus follow-up question suggestions.

    Unlike the planner, there's no validation-and-reject step here --
    the explainer's output is narration, not something that gets executed,
    so a slightly-off explanation isn't unsafe the way a bad plan would be.
    Pydantic's response_schema still guarantees the shape is well-formed.

    Raises LLMRateLimitError on a 429, LLMServiceError on any other API
    failure -- shared exception types with planner/service.py.
    """
    prompt = build_explainer_prompt(user_question, result)

    try:
        response = _client.models.generate_content(
            model=settings.explainer_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Explanation,
                temperature=0.4,  # a bit more room than the planner's 0.1 -- this is prose, not a strict choice
            ),
        )
    except ClientError as e:
        if e.status_code == 429:
            raise LLMRateLimitError() from e
        raise LLMServiceError(str(e)) from e

    return response.parsed


def explain_failure(
    user_question: str,
    reason: str,
    dataset_profile: dict,
    conversation_history: list[dict] | None = None,
) -> FailureExplanation:
    """
    Calls Gemini to turn a failed plan into a helpful, specific message
    plus real, rephrased follow-up suggestions -- using the dataset's
    actual columns, unlike get_explanation() above.

    Raises LLMRateLimitError / LLMServiceError same as get_explanation().
    Callers (app/ask.py) should catch these and fall back to a generic
    canned message -- a failure explaining a failure shouldn't cascade
    into a crash or a second layer of confusing errors.
    """
    prompt = build_failure_prompt(user_question, reason, dataset_profile, conversation_history)

    try:
        response = _client.models.generate_content(
            model=settings.explainer_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FailureExplanation,
                temperature=0.4,
            ),
        )
    except ClientError as e:
        if e.status_code == 429:
            raise LLMRateLimitError() from e
        raise LLMServiceError(str(e)) from e

    return response.parsed