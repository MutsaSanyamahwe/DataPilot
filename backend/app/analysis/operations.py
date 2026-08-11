# analysis/operations.py
#
# This file contains the actual computation functions — plain Pandas,
# no LLM involved anywhere in here. Each function corresponds 1:1 to one
# value in the Operation enum (planner/schemas.py) and one param model
# (e.g. GroupByAggParams). This is the "deterministic Python does the
# math" half of the architecture — the planner LLM only ever picks which
# of these functions to call and what arguments to pass it.

import pandas as pd
from typing import Literal

# Hard ceiling on rows returned by operations whose result size depends
# entirely on the data (filter, distinct, sample) rather than being
# naturally bounded (groupby_agg/distribution collapse to a handful of
# categories on their own). Without this, a filter on a low-selectivity
# column could return thousands of rows straight into the explainer
# prompt and the chart.
MAX_SAFETY_ROWS = 200


def groupby_agg(
    df: pd.DataFrame,
    group_by: str,
    metric: str,
    aggregation: Literal["mean", "sum", "count", "median", "min", "max", "std"],
    sort_by: Literal["value_asc", "value_desc", "label"] = "value_desc",
    limit: int | None = None,
) -> pd.DataFrame:
    """
    Groups the dataframe by one column and aggregates another.
    Example: groupby_agg(df, group_by="department", metric="salary", aggregation="mean")
    -> average salary per department

    Parameter names match GroupByAggParams (planner/schemas.py) exactly,
    so this can be called as groupby_agg(df, **validated_params.model_dump()).
    """
    if group_by not in df.columns:
        raise ValueError(f"Column '{group_by}' not found in dataset")
    if metric not in df.columns:
        raise ValueError(f"Column '{metric}' not found in dataset")

    result = df.groupby(group_by)[metric].agg(aggregation).reset_index()
    value_col = f"{metric}_{aggregation}"
    result.columns = [group_by, value_col]

    if sort_by == "value_desc":
        result = result.sort_values(by=value_col, ascending=False)
    elif sort_by == "value_asc":
        result = result.sort_values(by=value_col, ascending=True)
    else:  # "label"
        result = result.sort_values(by=group_by, ascending=True)

    if limit is not None:
        result = result.head(limit)

    return result.reset_index(drop=True)


def top_n_rows(
    df: pd.DataFrame,
    n: int = 10,
    sort_column: str | None = None,
    sort_ascending: bool = False,
) -> pd.DataFrame:
    """
    Returns a raw preview of the dataset -- no aggregation, no grouping.
    Example: top_n_rows(df, n=10) -> first 10 rows as-is
    Example: top_n_rows(df, n=5, sort_column="salary", sort_ascending=False)
    -> 5 highest-paid rows

    If sort_column is None, rows are returned in their original order
    (a plain "preview" rather than a "top by X" ranking).
    """
    if sort_column is not None:
        if sort_column not in df.columns:
            raise ValueError(f"Column '{sort_column}' not found in dataset")
        result = df.sort_values(by=sort_column, ascending=sort_ascending)
    else:
        result = df

    return result.head(n).reset_index(drop=True)


def describe_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a per-column summary of the whole dataset: name, dtype,
    non-null count, and total row count (repeated on every row so it's
    visible regardless of which row the explainer or chart looks at).
    Answers questions like "how many rows are there" and "what columns
    are in the data" in one shot.
    """
    total_rows = len(df)
    records = []
    for col in df.columns:
        records.append({
            "column": col,
            "dtype": str(df[col].dtype),
            "non_null_count": int(df[col].notna().sum()),
            "total_rows": total_rows,
        })
    return pd.DataFrame(records)


def distribution(
    df: pd.DataFrame,
    column: str,
    limit: int | None = None,
) -> pd.DataFrame:
    """
    Returns value counts for one column -- how many rows fall into each
    distinct category. Example: distribution(df, column="department")
    -> count of employees per department.
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in dataset")

    counts = df[column].value_counts(dropna=True).reset_index()
    counts.columns = [column, "count"]

    if limit is not None:
        counts = counts.head(limit)

    return counts.reset_index(drop=True)


def filter_rows(
    df: pd.DataFrame,
    filter_column: str,
    filter_operator: Literal[
        "equals", "not_equals", "greater_than", "less_than",
        "greater_or_equal", "less_or_equal", "contains",
    ],
    filter_value: str,
    limit: int | None = None,
) -> pd.DataFrame:
    """
    Filters rows where filter_column meets filter_operator against
    filter_value. Example: filter_rows(df, "department", "equals", "Sales")
    -> only rows where department is Sales.

    filter_value arrives as a string (Gemini's structured output can't mix
    types on one field); if the target column is numeric, it's coerced to
    a number before comparing.
    """
    if filter_column not in df.columns:
        raise ValueError(f"Column '{filter_column}' not found in dataset")

    series = df[filter_column]
    value = filter_value
    if pd.api.types.is_numeric_dtype(series):
        try:
            value = float(filter_value)
            if value.is_integer():
                value = int(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"Column '{filter_column}' is numeric, but '{filter_value}' isn't a valid number"
            )

    try:
        if filter_operator == "equals":
            mask = series == value
        elif filter_operator == "not_equals":
            mask = series != value
        elif filter_operator == "greater_than":
            mask = series > value
        elif filter_operator == "less_than":
            mask = series < value
        elif filter_operator == "greater_or_equal":
            mask = series >= value
        elif filter_operator == "less_or_equal":
            mask = series <= value
        elif filter_operator == "contains":
            mask = series.astype(str).str.contains(str(value), case=False, na=False)
        else:
            raise ValueError(f"Unsupported filter operator '{filter_operator}'")
    except TypeError as e:
        raise ValueError(f"Can't compare column '{filter_column}' this way: {e}")

    result = df[mask]
    row_cap = min(limit, MAX_SAFETY_ROWS) if limit is not None else MAX_SAFETY_ROWS
    return result.head(row_cap).reset_index(drop=True)


def distinct_values(
    df: pd.DataFrame,
    column: str,
    limit: int | None = None,
) -> pd.DataFrame:
    """
    Returns the unique values in one column, sorted, no counts.
    Example: distinct_values(df, "department") -> one row per unique
    department name. Use distribution() instead if counts are wanted too.
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in dataset")

    values = df[column].dropna().unique()
    result = pd.DataFrame({column: values}).sort_values(by=column).reset_index(drop=True)

    row_cap = min(limit, MAX_SAFETY_ROWS) if limit is not None else MAX_SAFETY_ROWS
    return result.head(row_cap)


def sample_rows(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """
    Returns a random sample of rows -- as opposed to top_n_rows, which is
    either the original order or explicitly sorted. Useful for "give me a
    feel for the data" style questions rather than a ranked view.
    """
    n = min(n, len(df), MAX_SAFETY_ROWS)
    if n <= 0:
        return df.head(0)
    return df.sample(n=n).reset_index(drop=True)