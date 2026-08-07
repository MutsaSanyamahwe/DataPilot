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