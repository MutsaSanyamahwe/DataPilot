# profiling/profiler.py
#
# This file looks at an actual pandas dataframe (the user's uploaded data)
# and produces a JSON-safe summary of it — column names, types, and a few
# example/statistical values per column. This summary is what gets handed
# to the planner prompt, NOT the raw data itself.
#
# Why not send raw rows to the LLM? Two reasons:
# 1. Cost/quota —  sending hundreds of rows per question burns tokens fast for no real benefit.
# 2. The planner doesn't need to see every row to pick "group by department,
#    average salary" — it just needs to know the column names, their types,
#    and a rough sense of what values live in them.

import pandas as pd


def profile_dataset(df: pd.DataFrame, max_sample_values: int = 5) -> dict:
    """
    Builds a compact summary of a dataframe for the planner LLM.

    Returns:
    {
        "row_count": 1200,
        "columns": [
            {
                "name": "department",
                "dtype": "string",
                "sample_values": ["Sales", "Engineering", "Marketing"],
            },
            {
                "name": "salary",
                "dtype": "float",
                "sample_values": [65000.0, 82000.0, 71000.0],
                "min": 42000.0,
                "max": 145000.0,
                "mean": 78500.0,
            },
        ],
    }
    """
    columns = []

    for col_name in df.columns:
        series = df[col_name]
        dtype = _simplify_dtype(series)

        column_info = {
            "name": col_name,
            "dtype": dtype,
            "sample_values": _get_sample_values(series, max_sample_values),
        }

        # Numeric columns get basic stats too — this helps the LLM judge
        # things like "is this a metric worth averaging" vs "is this
        # actually a categorical code stored as a number".
        if dtype in ("integer", "float"):
            column_info["min"] = _safe_float(series.min())
            column_info["max"] = _safe_float(series.max())
            column_info["mean"] = _safe_float(series.mean())

        columns.append(column_info)

    return {
        "row_count": len(df),
        "columns": columns,
    }


def _simplify_dtype(series: pd.Series) -> str:
    """Maps pandas dtypes to simple labels the LLM prompt already expects."""
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    return "string"


def _get_sample_values(series: pd.Series, max_values: int) -> list:
    """
    Pulls a few distinct, non-null example values from the column so the
    LLM can see what's actually in it (e.g. "Sales", "Engineering" —
    not just the type "string").
    """
    unique_values = series.dropna().unique()[:max_values]
    return [_safe_value(v) for v in unique_values]


def _safe_value(v):
    """Converts numpy/pandas scalar types into plain JSON-safe Python types."""
    if hasattr(v, "item"):  # numpy scalar (int64, float64, etc.)
        return v.item()
    return str(v) if not isinstance(v, (int, float, bool)) else v


def _safe_float(v) -> float | None:
    """Handles NaN safely — NaN isn't valid JSON and will break the API call."""
    if pd.isna(v):
        return None
    return float(v)