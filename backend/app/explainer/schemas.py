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
        description="1-3 natural follow-up questions the user might ask next, "
        "based on this result. Phrased the way a user would actually type them, "
        "e.g. 'What about last quarter?' not 'Analyze Q3 trends.'",
    )
 