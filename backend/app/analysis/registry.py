# analysis/registry.py
#
# This is the connective tissue between the planner and operations.py.
# It maps each Operation (planner/schemas.py) to the actual function in
# operations.py that implements it, runs that function against a real
# dataframe using the plan's validated params, and wraps the output in
# a consistent AnalysisResult object.
#
# Nothing outside this file should call operations.py functions directly
# for plan execution -- run_plan() is the one entry point, the same way
# planner.service.get_validated_plan() is the one entry point for planning.

import pandas as pd
from dataclasses import dataclass
from typing import Any

from app.planner.schemas import Operation, AnalysisPlan
from app.analysis.operations import (
    groupby_agg, top_n_rows, describe_dataset, distribution,
    filter_rows, distinct_values, sample_rows, trend, date_range_filter,
)


@dataclass
class AnalysisResult:
    """
    The standard output shape for any analysis operation. This is what
    charts/ and the explainer service will consume next -- regardless of
    which operation produced it, they always get this same shape.
    """
    operation: Operation
    data: pd.DataFrame        # the computed result table
    chart_type: str           # from plan.chart, passed through unchanged
    explanation_intent: str   # from plan.explanation_intent, for the explainer


# Maps each Operation to the function in operations.py that implements it.
# Every entry here MUST also have a matching param model in
# planner.schemas.OPERATION_PARAM_MODELS -- the two registries are kept
# in sync deliberately, one operation added to both at a time.
OPERATION_REGISTRY = {
    Operation.GROUPBY_AGG: groupby_agg,
    Operation.TOP_N: top_n_rows,
    Operation.DESCRIBE: describe_dataset,
    Operation.DISTRIBUTION: distribution,
    Operation.FILTER: filter_rows,
    Operation.DISTINCT: distinct_values,
    Operation.SAMPLE: sample_rows,
    Operation.TREND: trend,
    Operation.DATE_RANGE_FILTER: date_range_filter,
}


def run_plan(plan: AnalysisPlan, validated_params: Any, df: pd.DataFrame) -> AnalysisResult:
    """
    Executes a validated plan against a real dataframe.

    plan: the AnalysisPlan returned by planner.service.get_validated_plan()
    validated_params: the matching param model instance (e.g. GroupByAggParams),
        also returned by get_validated_plan()
    df: the user's actual data

    Returns an AnalysisResult. Raises KeyError if plan.operation somehow
    isn't in the registry (shouldn't happen if get_validated_plan() already
    checked it, but this file doesn't trust that blindly).
    """
    handler = OPERATION_REGISTRY.get(plan.operation)
    if handler is None:
        raise KeyError(
            f"Operation '{plan.operation.value}' has no registered handler "
            f"in analysis/registry.py, even though it passed planner validation. "
            f"This means OPERATION_PARAM_MODELS and OPERATION_REGISTRY are out of sync."
        )

    params_dict = validated_params.model_dump()
    result_df = handler(df, **params_dict)

    return AnalysisResult(
        operation=plan.operation,
        data=result_df,
        chart_type=plan.chart.value,
        explanation_intent=plan.explanation_intent,
    )