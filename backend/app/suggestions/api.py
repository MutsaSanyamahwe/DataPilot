# app/suggestions/api.py
#
# One read-only endpoint the chat screen calls right after a dataset is
# confirmed (or whenever it (re)mounts for an existing session), to
# populate the "questions you might ask" starter chips.
#
# Two-stage pipeline:
#   generate_suggested_questions()  (generator.py)  no LLM -- picks WHICH
#       operations and columns are safe to suggest for this exact
#       dataset. This is the guarantee: every question returned here is
#       one the backend has already confirmed (in real pandas) it can run.
#   polish_questions()              (service.py)     LLM call -- rewrites
#       the WORDING only, so the chips read like something a person would
#       actually type instead of a template. Never allowed to change
#       which operation/columns/values a question targets.
#
# The LLM call is a nicety, not a dependency -- any failure (rate limit,
# service error, wrong item count, a rewrite that slips into "why"
# territory) falls back to the plain template text for that question
# rather than blocking or degrading the guarantee generator.py provides.

import logging

from fastapi import APIRouter, HTTPException

from app.sessions.store import load_session_df
from app.suggestions.generator import generate_suggested_questions, _CAUSAL_WORDS
from app.suggestions.service import polish_questions
from app.llm_errors import LLMRateLimitError, LLMOverloadedError, LLMServiceError

logger = logging.getLogger(__name__)
router = APIRouter()

# A polished rewrite longer than this is more likely a malformed/rambling
# LLM response than an actual improvement -- fall back to the template
# for that one question rather than show it.
MAX_QUESTION_DISPLAY_LENGTH = 150


@router.get("/suggested_questions/{session_id}")
def get_suggested_questions(session_id: str):
    try:
        df = load_session_df(session_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please upload your data again.",
        )

    try:
        candidates = generate_suggested_questions(df)
    except Exception:
        # Same reasoning as the polish-pass fallback below: these are a
        # low-stakes nicety, never a hard dependency for the chat screen
        # to load. Log it and hand back an empty list rather than a 500.
        logger.exception("Failed to generate suggested questions for session %s", session_id)
        return {"questions": []}

    if not candidates:
        return {"questions": []}

    polished_texts = _polish_with_fallback(candidates, df, session_id)

    return {
        "questions": [
            {"question": text, "operation": c.operation}
            for c, text in zip(candidates, polished_texts)
        ]
    }


def _polish_with_fallback(candidates, df, session_id: str) -> list[str]:
    """
    Runs the candidates through the LLM polish pass and returns the final
    question text to show, one per candidate, same order. Falls back to
    the original template text -- per-question, not all-or-nothing --
    whenever the polish pass fails outright, comes back with the wrong
    number of items, or a specific rewrite fails the same causal/"why"
    and length checks the templates themselves are held to
    (see generator.py's own defensive _CAUSAL_WORDS filter).
    """
    originals = [c.question for c in candidates]

    try:
        result = polish_questions(
            candidates=[{"question": c.question, "operation": c.operation} for c in candidates],
            row_count=len(df),
            column_names=list(df.columns),
        )
    except (LLMRateLimitError, LLMOverloadedError, LLMServiceError) as e:
        logger.warning("Suggestions polish pass failed for session %s, using templates: %s", session_id, e)
        return originals

    polished = result.questions
    if len(polished) != len(originals):
        logger.warning(
            "Suggestions polish pass returned %d questions for %d candidates "
            "(session %s) -- falling back to templates.",
            len(polished), len(originals), session_id,
        )
        return originals

    final = []
    for original, rewritten in zip(originals, polished):
        rewritten = (rewritten or "").strip()
        if not rewritten or len(rewritten) > MAX_QUESTION_DISPLAY_LENGTH or _CAUSAL_WORDS.search(rewritten):
            final.append(original)
        else:
            final.append(rewritten)
    return final