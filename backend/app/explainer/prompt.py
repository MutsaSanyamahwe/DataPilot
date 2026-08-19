# app/explainer/prompt.py
#
# Builds prompts for both explainer LLM calls:
#   - build_explainer_prompt: narrates an already-computed AnalysisResult
#     (does NOT see the dataset's other columns -- narration only).
#   - build_failure_prompt: explains why a question couldn't be turned
#     into a valid plan, and suggests real rephrasings (DOES see the
#     dataset's columns -- that's the whole point of this one).
#
# Important: build_explainer_prompt does NOT recompute anything. The
# numbers in its prompt are exactly what analysis/operations.py already
# calculated. The LLM's only job there is narration, matching the
# "LLM never does the math" architecture. build_failure_prompt has a
# different job entirely -- helping the user reformulate a question that
# never got as far as producing a result.

import math
import pandas as pd

from app.analysis.registry import AnalysisResult
from app.planner.prompt import _format_conversation_history

MAX_ROWS_IN_PROMPT = 30  # keep the prompt small; explanation doesn't need every row


def build_explainer_prompt(user_question: str, result: AnalysisResult) -> str:
    table_json = _dataframe_to_safe_records(result.data.head(MAX_ROWS_IN_PROMPT))
    truncated_note = (
        f"\n(Showing the first {MAX_ROWS_IN_PROMPT} of {len(result.data)} rows.)"
        if len(result.data) > MAX_ROWS_IN_PROMPT
        else ""
    )

    causal_disclaimer_section = ""
    if result.needs_causal_disclaimer:
        causal_disclaimer_section = """
IMPORTANT: The user actually asked a "why" question, or something this
dataset can't directly answer (an external cause, business reasoning, an
opinion). The data below is only the CLOSEST RELATED information
available -- it does not explain the actual reason they asked about.
Start your explanation with a brief, honest, natural sentence
acknowledging this (e.g. "I can't tell you exactly why, but here's what
the data shows:" or "This dataset doesn't capture the reason for that,
but here's the related breakdown:") -- then present the data as useful
context, not as if it fully answers their question. Do not fabricate a
cause. Do not imply the numbers below explain the "why".
"""

    return f"""You are explaining the result of a data analysis to a user in a chat
interface. The computation has already been done by deterministic Python
code -- your only job is to explain what the numbers mean in plain English.
Do not perform any calculations yourself, do not question or recompute the
numbers, and do not mention SQL, code, or "the operation" -- just explain
the result as if you're a helpful analyst summarizing findings.

User's original question: "{user_question}"

What this analysis was meant to focus on: {result.explanation_intent}
{causal_disclaimer_section}
Computed result ({result.operation.value}):
{table_json}{truncated_note}

Rules:
- Write 2-4 sentences. Be direct and specific -- name the actual highest/lowest
  values, actual numbers, actual category names from the table above.
- Do not restate the question back to the user.
- Do not say things like "based on the data" or "according to the analysis" --
  just state the finding directly.
- Suggest 1-3 follow-up questions -- but ONLY questions this system can
  actually answer. A safe follow-up either (a) narrows or re-sorts THIS
  SAME result using only the columns visible in the table above (e.g.
  "just show me the top one", "what about the lowest instead of the
  highest"), or (b) is a plain, self-contained new question using column
  names you can see in the table above.
- Do NOT suggest breaking the data down by, filtering on, comparing
  against, or trending over any column that is NOT shown in the result
  table above. You cannot see the full dataset's other columns from
  here -- guessing at a column name that might not exist would send the
  user's next question straight to a dead end.
- NEVER suggest a "why" question, or anything else asking for a REASON or
  CAUSE (e.g. "why did X happen", "what caused the drop", "why is Sales
  smaller than other departments"). This system can only report computed
  facts from the data -- it has no way to explain causation, and
  suggesting a question it can't answer just wastes the user's next turn.
- NEVER suggest questions needing information that isn't in this dataset
  (e.g. "who is the department head", "are there plans to hire more",
  "how does this compare to industry average").
- NEVER suggest predictions or hypotheticals ("will this trend continue",
  "what if we hired more people").
"""


def build_failure_prompt(
    user_question: str,
    reason: str,
    dataset_profile: dict,
    conversation_history: list[dict] | None = None,
) -> str:
    """
    Builds the prompt for explaining a FAILED plan -- the planner
    either picked an operation that doesn't exist, left required params
    unfilled, or the operation itself rejected the params at runtime
    (e.g. picked a non-numeric column for an average).

    Unlike build_explainer_prompt, this DOES receive the dataset's real
    column list -- its whole job is helping the user reformulate using
    columns that actually exist, which build_explainer_prompt deliberately
    never needs to do.
    """
    columns_description = "\n".join(
        f"- {col['name']} ({col['dtype']}), example values: {col['sample_values']}"
        for col in dataset_profile.get("columns", [])
    )
    row_count = dataset_profile.get("row_count", "unknown")

    history_block = _format_conversation_history(conversation_history)
    history_section = f"\nRecent conversation (most recent last):\n{history_block}\n" if history_block else ""

    return f"""A user asked a data question, but the system could NOT turn it
into a valid analysis. Your job is to explain this to the user in a
friendly, helpful way, and suggest 1-3 real alternative questions that
WOULD work with this dataset.

Internal technical reason (for YOUR understanding only -- do not repeat
this raw text to the user, it's meant for developers, not a chat reply):
{reason}

Dataset ({row_count} rows), actual columns available:
{columns_description}
{history_section}
User's question that failed: "{user_question}"

Rules:
- In `message`, briefly and kindly explain why this specific question
  couldn't be answered, in plain language -- never repeat the internal
  technical reason above verbatim (no Python types, no field names like
  "metric" or "group_by", no pydantic/validation language).
- Then give concrete guidance: point to real column names from the list
  above that are close to what the user was probably asking about, if
  any exist.
- If the recent conversation shows this question was a short follow-up
  reply (e.g. answering a clarifying question the assistant just asked),
  factor that context into your explanation and suggestions.
- In `follow_up_questions`, suggest 1-3 alternative questions the user
  could ask instead that WOULD actually work -- phrased the way a user
  would type them, using ONLY real column names from the list above.
- Every suggestion must be something this system can actually compute:
  filtering, grouping/aggregating, comparing two specific groups, a
  trend over time (only if a real date-like column exists above), a
  distribution, a correlation between two numeric columns, outliers, or
  a plain preview of rows. Never suggest a "why"/cause question, a
  prediction, or anything needing information not in this dataset.
"""


def _dataframe_to_safe_records(df: pd.DataFrame) -> list[dict]:
    """Converts a dataframe into a list of plain-Python-typed dicts, safe to
    embed in a prompt string. Same numpy/NaN-safety concern as profiling's
    _safe_value -- numpy scalars and NaN aren't directly usable here."""
    records = []
    for row in df.itertuples(index=False):
        record = {}
        for col, value in zip(df.columns, row):
            record[col] = _safe_value(value)
        records.append(record)
    return records


def _safe_value(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "item"):  # numpy scalar (int64, float64, etc.)
        return v.item()
    return v