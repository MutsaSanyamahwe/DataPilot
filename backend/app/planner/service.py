# planner/service.py
#
# The only file that talks to Gemini for planning. get_validated_plan()
# is the single entry point everything else should use -- it calls the
# LLM, checks the operation is supported, validates params, and raises a
# clear error otherwise. Requires GOOGLE_API_KEY in .env (see config.py).

from google import genai
from google.genai import types
from google.genai.errors import APIError
import httpx
from pydantic import ValidationError

from app.config import settings
from app.planner.schemas import AnalysisPlan, OPERATION_PARAM_MODELS
from app.planner.prompt import build_planner_prompt
from app.llm_errors import LLMRateLimitError, LLMOverloadedError, LLMServiceError, classify_and_raise


class UnsupportedOperationError(Exception):
    """Raised when the planner picks an operation we haven't built yet."""
    def __init__(self, operation: str):
        self.operation = operation
        super().__init__(f"Operation '{operation}' is not supported yet")


class InvalidPlanError(Exception):
    """Raised when the LLM's params don't match the operation's schema."""
    def __init__(self, operation: str, errors: str):
        self.operation = operation
        self.errors = errors
        super().__init__(f"Invalid params for '{operation}': {errors}")


_client = genai.Client(api_key=settings.google_api_key)


def get_validated_plan(
    user_question: str,
    dataset_profile: dict,
    conversation_history: list[dict] | None = None,
) -> tuple[AnalysisPlan, object]:
    """
    Calls Gemini to produce an AnalysisPlan, then validates it.
    Returns (plan, validated_params) on success.
    Raises UnsupportedOperationError or InvalidPlanError on a bad plan,
    or LLMRateLimitError / LLMOverloadedError / LLMServiceError on a
    Gemini API failure -- shared exception types with explainer/service.py
    and suggestions/service.py so api/ask.py can handle all of them with
    one except block.

    conversation_history is optional recent-turn context (see
    planner/prompt.py) used to resolve follow-ups, pronouns, and answers
    to a clarifying question the assistant just asked.
    """
    plan = _call_planner_llm(user_question, dataset_profile, conversation_history)

    if plan.operation not in OPERATION_PARAM_MODELS:
        raise UnsupportedOperationError(plan.operation.value)

    try:
        validated_params = plan.validate_params()
    except ValidationError as e:
        raise InvalidPlanError(plan.operation.value, str(e))

    return plan, validated_params


def _call_planner_llm(
    user_question: str,
    dataset_profile: dict,
    conversation_history: list[dict] | None = None,
) -> AnalysisPlan:
    prompt = build_planner_prompt(user_question, dataset_profile, conversation_history)

    try:
        response = _client.models.generate_content(
            model=settings.planner_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AnalysisPlan,
                temperature=settings.planner_temperature,
            ),
        )
    except (APIError, httpx.RequestError) as e:
        classify_and_raise(e)

    return response.parsed