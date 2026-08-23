# app/suggestions/service.py
#
# The one file that talks to Gemini for the suggestions "polish" pass.
# Same structural pattern as explainer/service.py: one client, structured
# output via response_schema, same shared LLMRateLimitError/LLMServiceError
# types so callers (suggestions/api.py) can handle this failure the same
# way every other LLM call in the app is handled.
#
# What makes this call lower-stakes than the planner's: it can only ever
# reword an already-validated question, never choose what gets asked. A
# bad or failed response here just means the caller falls back to the
# plainer template text (see suggestions/api.py) -- it can't cause a chip
# to run the wrong operation or reference a column that doesn't exist.

from google import genai
from google.genai import types
from google.genai.errors import ClientError

from app.config import settings
from app.suggestions.schemas import PolishedQuestions
from app.suggestions.prompt import build_polish_prompt
from app.llm_errors import LLMRateLimitError, LLMServiceError

_client = genai.Client(api_key=settings.google_api_key)


def polish_questions(
    candidates: list[dict],
    row_count: int,
    column_names: list[str],
) -> PolishedQuestions:
    """
    candidates: [{"question": str, "operation": str}, ...] -- the
        deterministic template output from suggestions/generator.py.
    Returns a PolishedQuestions with one rewritten string per candidate,
    in the same order. Raises LLMRateLimitError / LLMServiceError on a
    Gemini API failure -- same types as planner/service.py and
    explainer/service.py, so this can share their except blocks.

    Does NOT validate that the count/order came back correctly -- that's
    the caller's job (suggestions/api.py), since what to do about a
    malformed response (fall back per-question vs. whole-list) is a
    caller-level policy decision, not something this thin API wrapper
    should decide on its own.
    """
    prompt = build_polish_prompt(candidates, row_count, column_names)

    try:
        response = _client.models.generate_content(
            model=settings.explainer_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PolishedQuestions,
                temperature=0.4,
            ),
        )
    except ClientError as e:
        if e.status_code == 429:
            raise LLMRateLimitError() from e
        raise LLMServiceError(str(e)) from e

    return response.parsed