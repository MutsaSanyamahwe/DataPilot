# planner/prompt.py
#
# Builds the text prompt sent to Gemini in planner/service.py. Does NOT
# call the API itself. Only describes operations that have a param model
# in schemas.py's OPERATION_PARAM_MODELS -- those two lists must be kept
# in sync as new operations get built.

from datetime import date

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

- trend: Groups a date column into periods (day/week/month/quarter/year)
  and counts rows or aggregates a metric per period, in chronological
  order. Use this for questions like "how has X changed over time",
  "monthly hiring trend", "sales by quarter", "yearly breakdown".
  Fill in: date_column (the date/datetime column), granularity (day,
  week, month, quarter, or year -- pick whichever matches the question's
  timeframe; default to "month" if unspecified).
  Optional: metric (column to aggregate per period -- leave unset to just
  count rows per period), aggregation (mean, sum, count, median, min,
  max, std -- defaults to count).

- date_range_filter: Shows rows within a date range on a date column.
  Use this for questions like "employees hired before 2020", "records
  from last year", "what happened between March and June".
  Fill in: date_column.
  Optional: start_date, end_date (see date rules below), limit.

- correlation: Measures how strongly two numeric columns move together
  (Pearson correlation, from -1 to 1), or shows a full correlation
  matrix across all numeric columns at once.
  Use for questions like "is there a correlation between salary and
  tenure", "how are these numbers related", "correlation matrix".
  For a specific pair: fill in column_a AND column_b (both required together).
  For a full matrix ("how do all the numbers relate"): leave both unset.
  Never set only one of column_a/column_b.
  IMPORTANT: column_a and column_b MUST both be numeric columns (check the
  dtype shown in the dataset listing below). If the user's intended
  concept doesn't map to an actual numeric column in this dataset (e.g.
  they say "tenure" but there's only a date column, not a computed
  tenure/years-of-service number), do NOT pick a non-numeric column --
  set clarification_needed instead, explaining that concept isn't
  available as a numeric column, and suggest what numeric columns exist.

- outlier_detection: Finds rows with unusually high or low values in one
  numeric column (using the IQR statistical method).
  Use for questions like "are there any salary outliers", "find unusual
  values in X", "who has an abnormally high Y".
  Fill in: column (must be numeric -- check the dtype below; if the
  user's intended column isn't numeric, use clarification_needed instead
  of picking it anyway).
  Optional: limit.

- duplicate_rows: Shows exact duplicate rows in the currently loaded data.
  Use for questions like "are there duplicate rows", "do I have repeated
  entries". Note: this checks the data as currently loaded, which may
  already be cleaned.
  Optional: limit.

Note: there's no separate "sort" operation. For "sort by X" or "rank by
X" questions without a specific top-N in mind, use top_n with a
reasonable limit (e.g. 20) and set sort_column accordingly.
"""

CHART_GUIDE = """
Chart types: bar, line, pie, scatter, histogram, stat, table, none.
For groupby_agg and distribution results, "bar" is usually the right choice
unless the grouped column is a date/time (use "line") or there are very few
categories being compared as parts of a whole (use "pie").
For top_n, filter, distinct, sample, date_range_filter, outlier_detection,
and duplicate_rows results, use "table" -- individual rows with multiple
columns don't fit a bar/line/pie shape.
For describe, use "table" as well.
For trend results, always use "line" -- it's a chronological series, and
a line is the only chart type that shows change over time clearly.
For correlation: use "stat" for a pairwise correlation (a single number),
or "table" for a full matrix.
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
    today = date.today().isoformat()

    return f"""You are a data analysis planner. Your job is to read the user's
question and the dataset's columns, then decide exactly ONE operation to run
against the data. You do NOT perform any analysis yourself — you only choose
the operation and its parameters. Deterministic Python code will do the
actual computation.

Today's date is {today}.

{OPERATIONS_GUIDE}

{CHART_GUIDE}

Dataset ({row_count} rows):
{columns_description}

User question: "{user_question}"

Rules:
- group_by, metric, sort_column, column, filter_column, and date_column
  MUST be exact column names from the dataset above — never invent a
  column name that isn't listed.
- For date_range_filter and trend, translate relative time language into
  absolute dates using today's date above -- e.g. "last year" means
  start_date one year before today; "since March" means start_date of
  March 1st of the current year (or last year if that's already passed).
  start_date/end_date must be in "YYYY-MM-DD" format.
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