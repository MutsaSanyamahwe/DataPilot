# app/suggestions/schemas.py
#
# Defines what the "polish pass" LLM (suggestions/service.py) is allowed
# to return. Deliberately minimal compared to planner/explainer schemas --
# this call only ever rewrites wording, so there's nothing to validate
# except "did we get the right shape back."

from pydantic import BaseModel, Field


class PolishedQuestions(BaseModel):
    questions: list[str] = Field(
        description="Rewritten versions of the input questions, in the exact "
        "same order, one rewritten question per input question -- never add, "
        "remove, merge, split, or reorder. Each rewritten question must ask "
        "for the exact same thing as its corresponding input question (same "
        "operation, same column(s), same specific value(s) if any are "
        "named) -- only the wording changes, never the meaning."
    )