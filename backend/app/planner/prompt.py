# planner/prompt.py
#
# Builds the text prompt sent to Gemini in planner/service.py. Does NOT
# call the API itself. Only describes operations that have a param model
# in schemas.py's OPERATION_PARAM_MODELS -- those two lists must be kept
# in sync as new operations get built.

OPERATIONS_GUIDE = """
Available operations:

- groupby_agg: Groups rows by one column and aggregates a metric column.
  Use this for questions like "average salary by department",
  "total sales per region", "count of orders by status".
  Fill in: group_by (column to group by), metric (column to aggregate),
  aggregation (one of: mean, sum, count, median, min, max, std).
  Optional: sort_by (value_asc, value_desc, label), limit (max rows to return).

- top_n: Shows a raw preview of individual rows -- no grouping or math.
  Use this for questions like "show me the top 10 rows", "show me the
  5 highest-paid employees", "give me a sample of the data".
  Fill in: limit (how many rows -- defaults to 10 if the user didn't say).
  Optional: sort_column (column to rank by, e.g. "salary" for "highest-paid"
  -- leave unset for a plain, unranked preview), sort_ascending (True for
  lowest-first, False for highest-first).

- describe: Gives an overview of the whole dataset -- row count, column
  names, data types, and how many non-empty values each column has.
  Use this for questions like "how many rows are there", "what columns
  are in the data", "give me an overview of this dataset".
  No fields to fill in -- always describes the whole dataset.

- distribution: Counts how many rows fall into each distinct value of one
  column. Use this for questions like "what's the distribution of
  departments", "how many of each category are there", "breakdown by region".
  Fill in: column (the column to count categories in).
  Optional: limit (only show the top N categories, if there are many).

- filter: Shows rows matching a condition -- no aggregation. Use this for
  questions like "show me employees in Sales", "which rows have salary
  over 100000", "find rows where department is Marketing".
  Fill in: filter_column, filter_operator (one of: equals, not_equals,
  greater_than, less_than, greater_or_equal, less_or_equal, contains),
  filter_value (as text, even for numbers).
  Optional: limit (cap on rows returned, useful if the match is broad).

- distinct: Lists the unique values in one column, with no counts. Use
  this for questions like "what departments exist", "what are the
  possible values in region". If the user also wants counts (e.g. "how
  many of each"), use distribution instead.
  Fill in: column.
  Optional: limit.

- sample: A random sample of rows -- for "give me a feel for the data"
  style questions where the user doesn't want any particular ranking.
  Fill in: limit (how many rows -- defaults to 10 if unspecified).

Note: there's no separate "sort" operation. For "sort by X" or "rank by
X" questions without a specific top-N in mind, use top_n with a
reasonable limit (e.g. 20) and set sort_column accordingly.
"""

CHART_GUIDE = """
Chart types: bar, line, pie, scatter, histogram, stat, table, none.
For groupby_agg and distribution results, "bar" is usually the right choice
unless the grouped column is a date/time (use "line") or there are very few
categories being compared as parts of a whole (use "pie").
For top_n, filter, distinct, and sample results, use "table" -- individual
rows with multiple columns don't fit a bar/line/pie shape.
For describe, use "table" as well.
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
- group_by, metric, sort_column, and column MUST be exact column names
  from the dataset above — never invent a column name that isn't listed.
- If the question is ambiguous (e.g. it's unclear which column is the
  metric, or the question doesn't match any available operation at all),
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