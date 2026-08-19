# app/explainer/schemas.py
#
# Defines what the explainer LLM is allowed to return. Same pattern as
# planner/schemas.py -- a strict Pydantic model passed to Gemini as
# response_schema, so the output shape is enforced at generation time
# rather than hoped for via prompt instructions.

from pydantic import BaseModel, Field


class Explanation(BaseModel):
    text: str = Field(
        description="A clear, plain-English explanation of the computed result. "
        "No SQL, no code, no column-name jargon -- written for someone reading "
        "a chat message, not a data report."
    )
    follow_up_questions: list[str] = Field(
        default_factory=list,
        description="1-3 follow-up questions the user might ask next, phrased "
        "the way a user would actually type them (e.g. 'What about last "
        "quarter?' not 'Analyze Q3 trends.'). Every suggestion MUST be "
        "answerable by further analysis of this same dataset -- never a "
        "'why'/cause question, never something needing outside knowledge, "
        "never a prediction. See the rules in the prompt for what counts "
        "as answerable.",
    )


class FailureExplanation(BaseModel):
    """
    Returned when the planner couldn't build a valid, runnable plan for
    the user's question (unsupported operation, invalid/missing params,
    or a runtime failure inside the chosen operation). Unlike Explanation,
    this call DOES see the dataset's real column names, because its whole
    job is helping the user rephrase using columns that actually exist --
    a fundamentally different task from narrating an already-computed
    result, where seeing extra columns would risk hallucinating about
    data that was never actually analyzed.
    """
    message: str = Field(
        description="A friendly, specific explanation of why this exact question "
        "couldn't be answered, in plain language (never repeat the raw internal "
        "error text). End with concrete guidance on how to ask it differently, "
        "referencing real column names from this dataset where relevant."
    )
    follow_up_questions: list[str] = Field(
        default_factory=list,
        description="1-3 alternative, rephrased questions the user could ask "
        "instead, using real column names from this dataset, that WOULD "
        "actually work. Phrased the way a user would type them.",
    )