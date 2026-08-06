# planner/service.py
#
# This file is the ONLY place in the app that talks to Gemini for planning.
# Its job: take a user's question + a summary of their dataset, ask Gemini
# to fill out an AnalysisPlan, and validate that plan before handing it
# to anything else. Nothing downstream (analysis engine, API route) should
# ever construct a plan itself — they all go through get_validated_plan().

from google import genai
from google.genai import types
from pydantic import ValidationError

from config import settings
from planner.schemas import AnalysisPlan, OPERATION_PARAM_MODELS
from planner.prompt import build_planner_prompt


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


# One client, created once at import time and reused for every request.
# Reading the key from settings (which reads it from .env) rather than
# hardcoding it anywhere.
_client = genai.Client(api_key=settings.google_api_key)


def get_validated_plan(user_question: str, dataset_profile: dict) -> tuple[AnalysisPlan, object]:
    """
    Calls Gemini to produce an AnalysisPlan, then validates it.
    Returns (plan, validated_params) on success.
    Raises UnsupportedOperationError or InvalidPlanError on failure.
    """
    plan = _call_planner_llm(user_question, dataset_profile)

    if plan.operation not in OPERATION_PARAM_MODELS:
        raise UnsupportedOperationError(plan.operation.value)

    try:
        validated_params = plan.validate_params()
    except ValidationError as e:
        raise InvalidPlanError(plan.operation.value, str(e))

    return plan, validated_params


def _call_planner_llm(user_question: str, dataset_profile: dict) -> AnalysisPlan:
    """
    Sends the question + dataset profile to Gemini and asks it to return
    JSON matching the AnalysisPlan schema exactly. Gemini's structured
    output mode enforces the shape at generation time — passing our
    Pydantic model directly as response_schema means we don't have to
    manually parse or repair JSON.
    """
    prompt = build_planner_prompt(user_question, dataset_profile)

    response = _client.models.generate_content(
        model=settings.planner_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AnalysisPlan,
            temperature=settings.planner_temperature,
        ),
    )

    # response.parsed is already an AnalysisPlan instance when response_schema
    # is a Pydantic model — the SDK validates and instantiates it for us.
    return response.parsed