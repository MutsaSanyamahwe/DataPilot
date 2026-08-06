# analysis/operations.py
import pandas as pd
from typing import Literal

def groupby_agg(
    df: pd.DataFrame,
    group_by: str,
    metric: str,
    aggregation: Literal["mean", "sum", "count", "median", "min", "max"],
) -> pd.DataFrame:
    """
    Groups the dataframe by one column and aggregates another.
    Example: groupby_agg(df, group_by="department", metric="salary", aggregation="mean")
    -> average salary per department
    """
    if group_by not in df.columns:
        raise ValueError(f"Column '{group_by}' not found in dataset")
    if metric not in df.columns:
        raise ValueError(f"Column '{metric}' not found in dataset")

    result = df.groupby(group_by)[metric].agg(aggregation).reset_index()
    result.columns = [group_by, f"{metric}_{aggregation}"]
    result = result.sort_values(by=f"{metric}_{aggregation}", ascending=False)
    return result