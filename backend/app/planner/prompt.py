# planner/prompt.py
#
# Builds the text prompt sent to Gemini in planner/service.py. Does NOT
# call the API itself. Only describes operations that have a param model
# in schemas.py's OPERATION_PARAM_MODELS -- those two lists must be kept
# in sync as new operations get built.

OPERATIONS_GUIDE = """
Available operation:

- groupby_agg: Groups rows by one column and aggregates a metric column.
  Use this for questions like "average salary by department",
  "total sales per region", "count of orders by status".
  Fill in: group_by (column to group by), metric (column to aggregate),
  aggregation (one of: mean, sum, count, median, min, max, std).
  Optional: sort_by (value_asc, value_desc, label), limit (max rows to return).
"""

CHART_GUIDE = """
Chart types: bar, line, pie, scatter, histogram, stat, table, none.
For groupby_agg results, "bar" is usually the right choice unless the
group_by column is a date/time (use "line") or there are very few
categories being compared as parts of a whole (use "pie").
"""


def build_planner_prompt(user_question: str, dataset_profile: dict) -> str:
    """
    Builds the full prompt string sent to Gemini.

    dataset_profile comes from profiling.profile_dataset(df) and looks like:
    {
        "row_count": 1200,
        "columns": [
            {"name": "department", "dtype": "string", "sample_values": [...]},
            {"name": "salary", "dtype": "float", "sample_values": [...], "min": ..., "max": ..., "mean": ...},
        ]
    }
    """
    columns_description = "\n".join(
        f"- {col['name']} ({col['dtype']}), example values: {col['sample_values']}"
        for col in dataset_profile.get("columns", [])
    )
    row_count = dataset_profile.get("row_count", "unknown")

    return f"""You are a data analysis planner. Your job is to read the user's
question and the dataset's columns, then decide exactly ONE operation to run
against the data. You do NOT perform any analysis yourself — you only choose
the operation and its parameters. Deterministic Python code will do the
actual computation.

{OPERATIONS_GUIDE}

{CHART_GUIDE}

Dataset ({row_count} rows):
{columns_description}

User question: "{user_question}"

Rules:
- group_by and metric MUST be exact column names from the dataset above —
  never invent a column name that isn't listed.
- If the question is ambiguous (e.g. it's unclear which column is the
  metric, or the question doesn't match the available operation at all),
  set clarification_needed to a short question you'd ask the user instead
  of guessing.
- confidence should reflect how sure you are that this operation and these
  params correctly answer the question — 1.0 for a clear match, lower if
  you had to guess at column names or interpretation.
- explanation_intent should be a short instruction for a second AI step
  that will explain the computed result in plain English — tell it what
  to focus on, e.g. "highlight which department has the highest average
  and by how much".
"""