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

router = APIRouter()

MAX_QUESTION_LENGTH = 1000


class AskRequest(BaseModel):
    session_id: str
    question: str


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

    try:
        plan, validated_params = get_validated_plan(question, dataset_profile)
    except UnsupportedOperationError:
        return {
            "text": "I can currently only do group-by style analysis "
                    "(e.g. \"average X by Y\"). That kind of question isn't supported yet.",
            "chart": None,
            "follow_up_questions": [],
        }
    except InvalidPlanError:
        return {
            "text": "I understood you wanted a group-by analysis, but couldn't "
                    "figure out exactly which columns to use. Could you rephrase?",
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
        # e.g. groupby_agg's own column-existence check failing --
        # shouldn't normally happen since the planner is told the real
        # column names, but guard against it rather than 500 blindly.
        raise HTTPException(status_code=400, detail=str(e))

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