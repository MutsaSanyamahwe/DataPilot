# app/ask.py
#
# v2 /ask endpoint. Replaces the old SQL tool-calling loop entirely.
# Pipeline:
#
#   load session dataframe
#     -> profile_dataset()            (profiling/)      no LLM
#     -> get_validated_plan()         (planner/)         LLM call #1 -- picks ONE operation
#     -> run_plan()                   (analysis/)        no LLM -- actual computation
#     -> build_chart()                (charts/)          no LLM -- shapes result for the frontend
#     -> get_explanation()            (explainer/)        LLM call #2 -- plain-English narration
#
# Only two LLM calls happen per question, both structured-output, both with
# the shared rate-limit/service-error handling from app/llm_errors.py.

import logging
import concurrent.futures

from typing import List, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.sessions.store import load_session_df
from app.profiling.profiler import profile_dataset
from app.planner.service import (
    get_validated_plan,
    UnsupportedOperationError,
    InvalidPlanError,
)
from app.analysis.registry import run_plan
from app.charts.builder import build_chart
from app.explainer.service import get_explanation, explain_failure
from app.llm_errors import LLMRateLimitError, LLMOverloadedError, LLMServiceError
from app.suggestions.generator import generate_suggested_questions

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_QUESTION_LENGTH = 1000

# Bounds how long a single /ask request will wait for run_plan() before
# giving up and telling the user, instead of the request just hanging.
# NOTE (portfolio-scope, being upfront about the real limitation): this
# uses a thread pool with a result timeout, not a hard kill -- Python
# can't forcibly stop a running thread. If a pandas operation is truly
# stuck (e.g. a pathological groupby on high-cardinality columns), the
# computation keeps running in the background after the user gets their
# timeout response; it just no longer blocks THEIR request. A real
# production system would run analysis in a separate process (so it can
# be killed outright) or a task queue with its own worker timeout. For a
# single-user portfolio deployment this is enough to stop one slow
# question from hanging the request indefinitely.
_analysis_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class AskRequest(BaseModel):
    session_id: str
    question: str
    # Recent conversation, most recent last -- sent by the frontend from
    # its own message state (nothing is persisted server-side; this is
    # purely per-request context). Optional and defaults to empty so
    # older frontend calls without this field still work unchanged.
    history: List[ConversationTurn] = []


def _explain_failure_or_fallback(
    question: str,
    reason: str,
    dataset_profile: dict,
    conversation_history: list[dict],
    fallback_text: str,
) -> dict:
    """
    Shared by all three failure paths below (unsupported operation,
    invalid params, runtime operation error). Calls the failure-coaching
    explainer -- which sees the dataset's real columns and can suggest
    concrete rephrasings -- and falls back to a generic canned message
    only if that call itself fails. A failure explaining a failure
    should never crash or cascade into a worse experience than the old
    static message.
    """
    try:
        failure = explain_failure(question, reason, dataset_profile, conversation_history)
        return {
            "text": failure.message,
            "chart": None,
            "follow_up_questions": failure.follow_up_questions,
        }
    except (LLMRateLimitError, LLMOverloadedError, LLMServiceError) as e:
        logger.warning("explain_failure itself failed for question %r: %s", question, e)
        return {"text": fallback_text, "chart": None, "follow_up_questions": []}


def _llm_unavailable_response(question: str, error: Exception) -> dict:
    """
    Shared by both LLM call sites below (planner, explainer). Turns a
    Gemini-side failure into the same kind of soft, actionable response
    the rest of this file already uses for timeouts and clarifications --
    real text explaining what happened, plus a one-tap retry (the
    original question, resent as a follow-up chip) -- rather than a bare
    HTTPException that dead-ends the conversation. The user asked a
    reasonable question; the AI service being rate-limited or briefly
    overloaded isn't something rephrasing would fix, so "try again" is
    the only actionable next step, and this makes it one tap instead of
    retyping the whole question.
    """
    if isinstance(error, LLMRateLimitError):
        logger.warning("LLM rate limit hit for question %r", question)
        text = ("I've hit the AI service's usage limit right now -- this could be a short-term "
                "rate limit or today's free quota being used up. Please wait a bit and try again.")
    elif isinstance(error, LLMOverloadedError):
        logger.warning("LLM overloaded (5xx) for question %r", question)
        text = ("The AI service is temporarily overloaded due to high demand. This usually "
                "clears up within a minute or two -- please try again shortly.")
    else:
        logger.error("LLM service error for question %r: %s", question, getattr(error, "detail", error))
        text = "Something went wrong reaching the AI service, so I couldn't process that question. Please try again in a moment."

    return {"text": text, "chart": None, "follow_up_questions": [question]}


@router.post("/ask")
def ask(payload: AskRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if len(question) > MAX_QUESTION_LENGTH:
        raise HTTPException(status_code=400, detail="Question is too long.")

    try:
        df = load_session_df(payload.session_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found. Please upload your data again.")

    dataset_profile = profile_dataset(df)
    conversation_history = [{"role": t.role, "text": t.text} for t in payload.history]

    try:
        plan, validated_params = get_validated_plan(question, dataset_profile, conversation_history)
    except UnsupportedOperationError as e:
        # With the registry/schema sync guard in analysis/registry.py, this
        # should now be unreachable in practice (an orphaned enum member
        # can't exist without failing at import time) -- but keep this as
        # a safety net and log it clearly if it ever fires again.
        logger.warning("Planner selected an unsupported operation %r for question %r", e.operation, question)
        reason = f"The system tried to use an operation called '{e.operation}', which isn't actually implemented."
        return _explain_failure_or_fallback(
            question, reason, dataset_profile, conversation_history,
            fallback_text="I wasn't able to find a way to analyze that with this dataset. Could you rephrase your question?",
        )
    except InvalidPlanError as e:
        # This fires for ANY operation whose params failed validation --
        # not just groupby_agg, even though the message used to hardcode
        # "group-by analysis" from back when that was the only operation
        # that existed. Log the real validation detail server-side (which
        # operation, which fields failed) so this is actually diagnosable.
        logger.warning(
            "Plan validation failed for question %r (operation=%s): %s",
            question, e.operation, e.errors,
        )
        reason = f"The system tried to use the '{e.operation}' operation but some required information was missing or invalid: {e.errors}"
        return _explain_failure_or_fallback(
            question, reason, dataset_profile, conversation_history,
            fallback_text="I understood what you wanted to analyze, but couldn't figure out exactly "
                          "which columns or values to use. Could you rephrase, or be more specific?",
        )
    except (LLMRateLimitError, LLMOverloadedError, LLMServiceError) as e:
        return _llm_unavailable_response(question, e)
    # No point running analysis or spending an extra LLM call for a plan
    # that was never actually executed -- the clarification IS the answer.
    # This is also the path a genuinely out-of-scope question lands on --
    # e.g. something unrelated to the dataset entirely, or an operation
    # this dataset's columns can't support (see planner/prompt.py's rule:
    # "the question doesn't match any available operation at all" ->
    # clarification_needed). Rather than leave the user at a dead end with
    # nothing to do next, hand back a few guaranteed-answerable starter
    # questions for this exact dataset (same generator that powers the
    # chat screen's initial suggestions) so there's always a next tap.
    if plan.clarification_needed:
        try:
            fallback_suggestions = [
                s.question for s in generate_suggested_questions(df, max_questions=3)
            ]
        except Exception:
            logger.exception("Failed to generate fallback suggestions for question %r", question)
            fallback_suggestions = []
        return {
            "text": plan.clarification_needed,
            "chart": None,
            "follow_up_questions": fallback_suggestions,
        }

    try:
        future = _analysis_executor.submit(run_plan, plan, validated_params, df)
        result = future.result(timeout=settings.analysis_timeout_seconds)
    except concurrent.futures.TimeoutError:
        logger.warning(
            "Analysis timed out for question %r (operation=%s) after %ss",
            question, plan.operation, settings.analysis_timeout_seconds,
        )
        return _explain_failure_or_fallback(
            question,
            f"The analysis took longer than {settings.analysis_timeout_seconds} seconds to run and was stopped.",
            dataset_profile, conversation_history,
            fallback_text="That analysis took too long to run. Try a simpler question, "
                          "or one that touches fewer rows or columns.",
        )
    except KeyError:
        # OPERATION_PARAM_MODELS and OPERATION_REGISTRY disagreed -- an
        # internal bug, not something the user did wrong.
        raise HTTPException(
            status_code=500,
            detail="Something went wrong running that analysis. Please try a different question.",
        )
    except ValueError as e:
        # An operation function rejected the plan's params at runtime --
        # e.g. the planner picked a non-numeric column for a correlation,
        # or a pivot with too many distinct columns. This should be rarer
        # now that the prompt explicitly warns about column types, but it
        # can still happen. NEVER show the raw internal message to the
        # user -- log it for debugging, and let the failure-coaching
        # explainer turn it into something genuinely useful.
        logger.warning("Analysis operation failed for question %r: %s", question, e)
        return _explain_failure_or_fallback(
            question, str(e), dataset_profile, conversation_history,
            fallback_text="I wasn't able to run that analysis with the columns I picked. "
                          "Could you rephrase, or specify which column you mean?",
        )

    chart = build_chart(result)

    try:
        explanation = get_explanation(question, result)
    except (LLMRateLimitError, LLMOverloadedError, LLMServiceError) as e:
        # Unlike the planner-stage failure earlier in this function, the
        # actual analysis already ran successfully by this point --
        # `result`/`chart` are real, computed answers. Only the LLM
        # narration step failed. Falling back to a generic "couldn't
        # reach the AI service" message with no chart would throw away
        # perfectly good work over a wording problem -- show the chart
        # with a plain fallback caption instead, and be honest about why
        # there's no written explanation this time.
        if isinstance(e, LLMRateLimitError):
            logger.warning("LLM rate limit hit narrating result for question %r", question)
            note = "the AI service's usage limit being hit right now"
        elif isinstance(e, LLMOverloadedError):
            logger.warning("LLM overloaded (5xx) narrating result for question %r", question)
            note = "the AI service being temporarily overloaded"
        else:
            logger.error(
                "LLM service error narrating result for question %r: %s",
                question, getattr(e, "detail", e),
            )
            note = "an AI service error"
        return {
            "text": f"Here's the result -- I couldn't generate a written explanation because of "
                    f"{note}. Try asking again in a moment for the full explanation.",
            "chart": chart,
            "follow_up_questions": [question],
        }

    return {
        "text": explanation.text,
        "chart": chart,
        "follow_up_questions": explanation.follow_up_questions,
    }