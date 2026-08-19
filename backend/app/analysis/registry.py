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
    correlation, outlier_detection, duplicate_rows, compare_groups, pivot,
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
    needs_causal_disclaimer: bool = False  # from plan.needs_causal_disclaimer -- see planner/schemas.py


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
    Operation.CORRELATION: correlation,
    Operation.OUTLIER_DETECTION: outlier_detection,
    Operation.DUPLICATE_ROWS: duplicate_rows,
    Operation.COMPARISON: compare_groups,
    Operation.PIVOT: pivot,
}

# Fail loudly at import time, not at runtime, if a future Operation enum
# member gets added here without also being registered in
# planner.schemas.OPERATION_PARAM_MODELS (or vice versa). Without this,
# an orphaned enum member is silently selectable by Gemini (it's a real
# schema member) but has nowhere to actually run -- exactly what
# happened with the old unused FILTER_AGG value, which produced a
# confusing generic error for the user instead of failing at dev time.
from app.planner.schemas import OPERATION_PARAM_MODELS as _OPERATION_PARAM_MODELS

_all_ops = set(Operation)
_registered_here = set(OPERATION_REGISTRY.keys())
_registered_in_planner = set(_OPERATION_PARAM_MODELS.keys())

if _all_ops != _registered_here or _all_ops != _registered_in_planner:
    _missing_from_registry = _all_ops - _registered_here
    _missing_from_planner = _all_ops - _registered_in_planner
    raise RuntimeError(
        "Operation enum is out of sync with its registries. "
        f"Missing from analysis.registry.OPERATION_REGISTRY: {_missing_from_registry or 'none'}. "
        f"Missing from planner.schemas.OPERATION_PARAM_MODELS: {_missing_from_planner or 'none'}. "
        "Every Operation enum member needs both a param model and a registry entry."
    )


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
        needs_causal_disclaimer=plan.needs_causal_disclaimer,
    )