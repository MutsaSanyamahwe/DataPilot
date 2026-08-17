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

from typing import List, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.sessions.store import load_session_df
from app.profiling.profiler import profile_dataset
from app.planner.service import (
    get_validated_plan,
    UnsupportedOperationError,
    InvalidPlanError,
)
from app.analysis.registry import run_plan
from app.charts.builder import build_chart
from app.explainer.service import get_explanation
from app.llm_errors import LLMRateLimitError, LLMServiceError

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_QUESTION_LENGTH = 1000


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
        return {
            "text": "I wasn't able to find a way to analyze that with this dataset. "
                    "Could you rephrase your question?",
            "chart": None,
            "follow_up_questions": [],
        }
    except InvalidPlanError as e:
        # This fires for ANY operation whose params failed validation --
        # not just groupby_agg, even though the message used to hardcode
        # "group-by analysis" from back when that was the only operation
        # that existed. Log the real validation detail server-side (which
        # operation, which fields failed) so this is actually diagnosable,
        # but keep the user-facing text operation-agnostic.
        logger.warning(
            "Plan validation failed for question %r (operation=%s): %s",
            question, e.operation, e.errors,
        )
        return {
            "text": "I understood what you wanted to analyze, but couldn't figure "
                    "out exactly which columns or values to use. Could you rephrase, "
                    "or be more specific about the columns involved?",
            "chart": None,
            "follow_up_questions": [],
        }
    except LLMRateLimitError:
        raise HTTPException(status_code=429, detail="You've hit the free-tier rate limit. Wait a moment and try again.")
    except LLMServiceError as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {e.detail}")

    # The planner can choose to ask a clarifying question instead of guessing.
    # No point running analysis or spending a second LLM call on an
    # explanation for a plan that was never actually executed.
    if plan.clarification_needed:
        return {
            "text": plan.clarification_needed,
            "chart": None,
            "follow_up_questions": [],
        }

    try:
        result = run_plan(plan, validated_params, df)
    except KeyError:
        # OPERATION_PARAM_MODELS and OPERATION_REGISTRY disagreed -- an
        # internal bug, not something the user did wrong.
        raise HTTPException(
            status_code=500,
            detail="Something went wrong running that analysis. Please try a different question.",
        )
    except ValueError as e:
        # An operation function rejected the plan's params at runtime --
        # e.g. the planner picked a non-numeric column for a correlation.
        # This should be rare now that the prompt explicitly warns about
        # column types, but it can still happen. NEVER show the raw
        # internal message to the user (it's meant for developers, not
        # a chat reply) -- log it for debugging, and respond the same
        # friendly way as the other "couldn't run this" cases above
        # (UnsupportedOperationError / InvalidPlanError / clarification_needed),
        # so the user sees a normal conversational reply, not an error bubble.
        logger.warning("Analysis operation failed for question %r: %s", question, e)
        return {
            "text": "I wasn't able to run that analysis with the columns I picked. "
                    "Could you rephrase, or specify which column you mean?",
            "chart": None,
            "follow_up_questions": [],
        }

    chart = build_chart(result)

    try:
        explanation = get_explanation(question, result)
    except LLMRateLimitError:
        raise HTTPException(status_code=429, detail="You've hit the free-tier rate limit. Wait a moment and try again.")
    except LLMServiceError as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {e.detail}")

    return {
        "text": explanation.text,
        "chart": chart,
        "follow_up_questions": explanation.follow_up_questions,
    }