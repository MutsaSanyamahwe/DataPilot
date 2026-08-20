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


def _require_numeric_for_aggregation(df: pd.DataFrame, column: str, aggregation: str) -> None:
    """
    Shared guard for every operation that aggregates a metric column
    (groupby_agg, compare_groups, pivot, trend). "count" works fine on
    any dtype (it just counts non-null values), but mean/sum/median/min/
    max/std all require real numeric data.

    Without this check, a column that LOOKS numeric by name (e.g.
    "AVERAGE_STUDENT_ATTENDANCE") but is actually stored as text (e.g.
    "96.30%" with a percent sign, so pandas reads it as a string) causes
    pandas to raise a raw TypeError deep inside its aggregation internals.
    That TypeError isn't a ValueError, so it bypasses app/ask.py's
    friendly-error handling entirely and becomes an unhandled 500. This
    guard converts that failure into a clean, catchable ValueError before
    pandas ever gets the chance to raise its own confusing error.
    """
    if aggregation == "count":
        return
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise ValueError(
            f"Column '{column}' isn't numeric, can't compute {aggregation}. "
            f"It may contain text formatting (like a '%' sign) even though it looks like a number."
        )


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
    _require_numeric_for_aggregation(df, metric, aggregation)

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


# Accepted spellings for a "true"/"false" filter value, case-insensitive.
# Covers the realistic range of how a user or the planner might phrase it.
_TRUE_STRINGS = {"true", "t", "yes", "y", "1"}
_FALSE_STRINGS = {"false", "f", "no", "n", "0"}


def _coerce_to_bool(filter_value: str, filter_column: str) -> bool:
    normalized = str(filter_value).strip().lower()
    if normalized in _TRUE_STRINGS:
        return True
    if normalized in _FALSE_STRINGS:
        return False
    raise ValueError(
        f"Column '{filter_column}' is a true/false column, but "
        f"'{filter_value}' isn't recognizable as true or false"
    )


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
    types on one field). It's coerced before comparing:
    - boolean columns: "true"/"false" (any case, plus t/f/yes/no/1/0) -> real bool
    - numeric columns: parsed as a number
    Boolean is checked BEFORE numeric, because pandas' is_numeric_dtype()
    considers boolean columns numeric too (bool is numeric-like at the
    numpy level) -- without this ordering, a value like "true" would fall
    into the numeric branch and fail to parse as a float, every time,
    regardless of casing or phrasing.
    """
    if filter_column not in df.columns:
        raise ValueError(f"Column '{filter_column}' not found in dataset")

    series = df[filter_column]
    value = filter_value
    if pd.api.types.is_bool_dtype(series):
        value = _coerce_to_bool(filter_value, filter_column)
    elif pd.api.types.is_numeric_dtype(series):
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


_TREND_FREQ_MAP = {"day": "D", "week": "W", "month": "M", "quarter": "Q", "year": "Y"}


def trend(
    df: pd.DataFrame,
    date_column: str,
    granularity: Literal["day", "week", "month", "quarter", "year"] = "month",
    metric: str | None = None,
    aggregation: Literal["mean", "sum", "count", "median", "min", "max", "std"] = "count",
) -> pd.DataFrame:
    """
    Groups rows into time periods (day/week/month/quarter/year) and
    aggregates a metric per period -- or counts rows per period if no
    metric is given. Result is always sorted chronologically, so it's
    ready to chart as a line without any extra sorting downstream.

    Example: trend(df, "hire_date", granularity="year") -> hires per year
    Example: trend(df, "sale_date", granularity="month", metric="revenue",
                    aggregation="sum") -> monthly revenue totals
    """
    if date_column not in df.columns:
        raise ValueError(f"Column '{date_column}' not found in dataset")
    if metric is not None and metric not in df.columns:
        raise ValueError(f"Column '{metric}' not found in dataset")
    if metric is not None:
        _require_numeric_for_aggregation(df, metric, aggregation)

    parsed_dates = pd.to_datetime(df[date_column], format="mixed", errors="coerce")
    if parsed_dates.notna().sum() == 0:
        raise ValueError(f"Column '{date_column}' doesn't contain any recognizable dates")

    freq = _TREND_FREQ_MAP.get(granularity)
    if freq is None:
        raise ValueError(f"Unsupported granularity '{granularity}'")

    working = df.copy()
    working["_period"] = parsed_dates.dt.to_period(freq)
    working = working.dropna(subset=["_period"])

    if metric is None:
        result = working.groupby("_period", observed=True).size().reset_index(name="count")
    else:
        result = working.groupby("_period", observed=True)[metric].agg(aggregation).reset_index()

    result = result.sort_values("_period")
    result["_period"] = result["_period"].astype(str)
    result = result.rename(columns={"_period": date_column})
    return result.reset_index(drop=True)


def date_range_filter(
    df: pd.DataFrame,
    date_column: str,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """
    Filters rows to those within [start_date, end_date] on date_column.
    Either bound can be omitted for an open-ended range. Dates are parsed
    properly (not compared as raw strings), so this works regardless of
    the column's original date format.
    """
    if date_column not in df.columns:
        raise ValueError(f"Column '{date_column}' not found in dataset")

    parsed_dates = pd.to_datetime(df[date_column], format="mixed", errors="coerce")
    if parsed_dates.notna().sum() == 0:
        raise ValueError(f"Column '{date_column}' doesn't contain any recognizable dates")

    mask = parsed_dates.notna()

    if start_date:
        start = pd.to_datetime(start_date, errors="coerce")
        if pd.isna(start):
            raise ValueError(f"'{start_date}' isn't a recognizable date")
        mask &= parsed_dates >= start

    if end_date:
        end = pd.to_datetime(end_date, errors="coerce")
        if pd.isna(end):
            raise ValueError(f"'{end_date}' isn't a recognizable date")
        mask &= parsed_dates <= end

    result = df[mask]
    row_cap = min(limit, MAX_SAFETY_ROWS) if limit is not None else MAX_SAFETY_ROWS
    return result.head(row_cap).reset_index(drop=True)


def correlation(
    df: pd.DataFrame,
    column_a: str | None = None,
    column_b: str | None = None,
) -> pd.DataFrame:
    """
    Two modes:
    - column_a AND column_b given -> single pairwise Pearson correlation,
      returned as a 1x1 dataframe (renders as a stat card).
    - neither given -> full correlation matrix across every numeric column.
    - only one given -> invalid, raises (the planner should ask for
      clarification rather than send a half-filled request).
    """
    numeric_df = df.select_dtypes(include="number")

    if column_a and column_b:
        for col in (column_a, column_b):
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found in dataset")
            if col not in numeric_df.columns:
                raise ValueError(f"Column '{col}' isn't numeric, can't compute correlation")
        corr_value = df[column_a].corr(df[column_b])
        label = f"{column_a} vs {column_b} correlation"
        return pd.DataFrame({label: [corr_value]})

    if column_a or column_b:
        raise ValueError(
            "Provide both column_a and column_b for a pairwise correlation, "
            "or neither for a full correlation matrix"
        )

    if numeric_df.shape[1] < 2:
        raise ValueError("Not enough numeric columns in this dataset to compute correlation")

    matrix = numeric_df.corr().reset_index().rename(columns={"index": "column"})
    return matrix


def outlier_detection(
    df: pd.DataFrame,
    column: str,
    limit: int | None = None,
) -> pd.DataFrame:
    """
    Flags statistical outliers in one numeric column using the IQR method
    (values more than 1.5x the interquartile range below Q1 or above Q3
    -- a standard, deterministic, no-training-required outlier rule).
    Returns the actual outlier rows, not just a count.
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in dataset")
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise ValueError(f"Column '{column}' isn't numeric, can't detect outliers")

    values = df[column].dropna()
    if len(values) < 4:
        raise ValueError(f"Not enough data in '{column}' to detect outliers")

    q1 = values.quantile(0.25)
    q3 = values.quantile(0.75)
    iqr = q3 - q1

    if iqr == 0:
        # No spread outside the middle 50% -- nothing is a meaningful
        # outlier by this method. Returning everything as "outlying"
        # would be misleading, so return an empty result instead.
        return df.head(0)

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    mask = (df[column] < lower_bound) | (df[column] > upper_bound)

    result = df[mask]
    row_cap = min(limit, MAX_SAFETY_ROWS) if limit is not None else MAX_SAFETY_ROWS
    return result.head(row_cap).reset_index(drop=True)


def duplicate_rows(df: pd.DataFrame, limit: int | None = None) -> pd.DataFrame:
    """
    Returns every row that's an exact duplicate of another row in the
    CURRENTLY LOADED data -- distinct from cleaning's upload-time report,
    since this checks whatever's loaded right now (possibly already
    cleaned, if the user chose to clean on confirm).
    """
    dupe_mask = df.duplicated(keep=False)  # flag every occurrence, not just the "extra" ones
    result = df[dupe_mask].sort_values(by=list(df.columns))

    row_cap = min(limit, MAX_SAFETY_ROWS) if limit is not None else MAX_SAFETY_ROWS
    return result.head(row_cap).reset_index(drop=True)


def compare_groups(
    df: pd.DataFrame,
    group_column: str,
    group_a: str,
    group_b: str,
    metric: str | None = None,
    aggregation: Literal["mean", "sum", "count", "median", "min", "max"] = "mean",
) -> pd.DataFrame:
    """
    Compares one metric between exactly two values of a categorical
    column. Computes both the absolute and percentage difference
    deterministically -- the explainer just reads these numbers rather
    than computing the difference itself.

    metric is optional: leave it unset for "headcount"/"how many" style
    comparisons, which just compare row counts between the two groups
    (same pattern as trend/pivot handling a missing metric).

    Example: compare_groups(df, "department", "Engineering", "Sales", "salary")
    -> average salary in Engineering vs Sales, plus the difference.
    Example: compare_groups(df, "department", "Marketing", "Finance")
    -> headcount in Marketing vs Finance, plus the difference.
    """
    if group_column not in df.columns:
        raise ValueError(f"Column '{group_column}' not found in dataset")
    if metric is not None and metric not in df.columns:
        raise ValueError(f"Column '{metric}' not found in dataset")
    if metric is not None:
        _require_numeric_for_aggregation(df, metric, aggregation)

    col_as_str = df[group_column].astype(str)
    subset_a = df[col_as_str == str(group_a)]
    subset_b = df[col_as_str == str(group_b)]

    if len(subset_a) == 0:
        raise ValueError(f"No rows found where '{group_column}' is '{group_a}'")
    if len(subset_b) == 0:
        raise ValueError(f"No rows found where '{group_column}' is '{group_b}'")

    if metric is None:
        value_a = float(len(subset_a))
        value_b = float(len(subset_b))
        value_col = "count"
    else:
        value_a = float(subset_a[metric].agg(aggregation))
        value_b = float(subset_b[metric].agg(aggregation))
        value_col = f"{metric}_{aggregation}"

    diff_a_vs_b = value_a - value_b
    pct_a_vs_b = (diff_a_vs_b / value_b * 100) if value_b != 0 else None

    return pd.DataFrame({
        group_column: [group_a, group_b],
        value_col: [value_a, value_b],
        "difference_vs_other": [diff_a_vs_b, -diff_a_vs_b],
        "pct_difference_vs_other": [
            pct_a_vs_b,
            (-pct_a_vs_b if pct_a_vs_b is not None else None),
        ],
    })


MAX_PIVOT_COLUMNS = 20  # too many distinct column-values makes a pivot unreadable


def pivot(
    df: pd.DataFrame,
    row_column: str,
    col_column: str,
    metric: str | None = None,
    aggregation: Literal["mean", "sum", "count", "median", "min", "max"] = "count",
) -> pd.DataFrame:
    """
    Cross-tabulates two categorical columns. If metric is given, cells
    hold the aggregated metric value (a true pivot table); if metric is
    left unset, cells hold row counts (a crosstab / frequency table --
    the same operation, just without a metric to aggregate).

    Example: pivot(df, "department", "region") -> headcount per
    department x region combination.
    Example: pivot(df, "department", "region", metric="salary", aggregation="mean")
    -> average salary per department x region combination.
    """
    if row_column not in df.columns:
        raise ValueError(f"Column '{row_column}' not found in dataset")
    if col_column not in df.columns:
        raise ValueError(f"Column '{col_column}' not found in dataset")
    if row_column == col_column:
        raise ValueError("row_column and col_column must be different columns")
    if metric is not None and metric not in df.columns:
        raise ValueError(f"Column '{metric}' not found in dataset")
    if metric is not None:
        _require_numeric_for_aggregation(df, metric, aggregation)

    if metric is None:
        # Count mode: 0 genuinely means "zero rows in this combination" --
        # a real, correct zero.
        result = pd.crosstab(df[row_column], df[col_column])
    else:
        # Metric mode: DO NOT fill missing combinations with 0. A pivot_table
        # fill_value=0 here would make "no employees in this combination"
        # indistinguishable from "the average salary here is genuinely $0" --
        # misleading for mean/median/min/max, and just as confusing for sum.
        # Leave it as NaN; NaN is already handled correctly downstream (charts
        # and the explainer both convert NaN to None / "no data" safely).
        result = df.pivot_table(
            index=row_column, columns=col_column, values=metric,
            aggfunc=aggregation,
        )

    if result.shape[1] > MAX_PIVOT_COLUMNS:
        raise ValueError(
            f"'{col_column}' has too many distinct values to pivot into columns "
            f"({result.shape[1]}). Try a column with fewer categories, or swap "
            f"row_column and col_column."
        )

    result = result.reset_index()
    result.columns = [str(c) for c in result.columns]  # flatten any tuple/non-string labels
    return result.head(MAX_SAFETY_ROWS)