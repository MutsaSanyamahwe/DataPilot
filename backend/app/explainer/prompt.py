# app/explainer/prompt.py
#
# Builds the text prompt sent to Gemini for the explanation step. Takes
# the AnalysisResult produced by analysis.registry.run_plan() -- the
# already-computed data, not raw user data -- and turns it into a
# compact, JSON-safe table the LLM can read and explain.
#
# Important: this file does NOT recompute anything. The numbers in the
# prompt are exactly what analysis/operations.py already calculated.
# The LLM's only job here is narration, matching the "LLM never does
# the math" architecture.

import math
import pandas as pd

from app.analysis.registry import AnalysisResult

MAX_ROWS_IN_PROMPT = 30  # keep the prompt small; explanation doesn't need every row


def build_explainer_prompt(user_question: str, result: AnalysisResult) -> str:
    table_json = _dataframe_to_safe_records(result.data.head(MAX_ROWS_IN_PROMPT))
    truncated_note = (
        f"\n(Showing the first {MAX_ROWS_IN_PROMPT} of {len(result.data)} rows.)"
        if len(result.data) > MAX_ROWS_IN_PROMPT
        else ""
    )

    return f"""You are explaining the result of a data analysis to a user in a chat
interface. The computation has already been done by deterministic Python
code -- your only job is to explain what the numbers mean in plain English.
Do not perform any calculations yourself, do not question or recompute the
numbers, and do not mention SQL, code, or "the operation" -- just explain
the result as if you're a helpful analyst summarizing findings.

User's original question: "{user_question}"

What this analysis was meant to focus on: {result.explanation_intent}

Computed result ({result.operation.value}):
{table_json}{truncated_note}

Rules:
- Write 2-4 sentences. Be direct and specific -- name the actual highest/lowest
  values, actual numbers, actual category names from the table above.
- Do not restate the question back to the user.
- Do not say things like "based on the data" or "according to the analysis" --
  just state the finding directly.
- Suggest 1-3 natural follow-up questions the user might genuinely want to ask
  next, based specifically on what this result shows (e.g. if one category
  stands out, a follow-up might drill into why, or compare it over time).
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