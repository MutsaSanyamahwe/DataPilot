# planner/schemas.py
#
# Defines what a valid plan looks like: the Operation enum, ChartType enum,
# per-operation parameter models, and the top-level AnalysisPlan model.
# This is the single source of truth for what the planner LLM is allowed
# to return. See planner/README.md for full context.
#
# IMPORTANT CONSTRAINT: Gemini's Developer API (free tier) structured
# output CANNOT handle an open-ended dict field in the response schema --
# a dict with arbitrary keys requires "additionalProperties: true" in the
# generated JSON Schema, which the Developer API explicitly rejects
# (raises ValueError: "additionalProperties is only supported in Gemini
# Enterprise Agent Platform mode"). Because of this, AnalysisPlan CANNOT
# have a generic `params: dict` field -- every param has to be an
# explicit, fully-typed field on AnalysisPlan itself.
#
# This works cleanly right now because there's only one operation
# (groupby_agg). As more operations are added, their params also need to
# become explicit optional fields here (see the comment above AnalysisPlan
# below) -- there's no way around this while targeting the Developer API's
# structured output mode.

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Operation(str, Enum):
    GROUPBY_AGG = "groupby_agg"
    DESCRIBE = "describe"
    CORRELATION = "correlation"
    TREND = "trend"
    FILTER_AGG = "filter_agg"
    DISTRIBUTION = "distribution"
    COMPARISON = "comparison"
    OUTLIER_DETECTION = "outlier_detection"
    TOP_N = "top_n"


class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    STAT = "stat"
    TABLE = "table"
    NONE = "none"


# --- Per-operation param schemas ---
# Only groupby_agg exists so far, since it's the only operation built in
# analysis/. Add one of these per operation as each one gets built --
# and remember to also add its fields to AnalysisPlan below (see note there).

class GroupByAggParams(BaseModel):
    group_by: str
    metric: str
    aggregation: Literal["mean", "sum", "count", "median", "min", "max", "std"]
    sort_by: Optional[Literal["value_asc", "value_desc", "label"]] = "value_desc"
    limit: Optional[int] = None


# Maps each Operation to the param model that validates it.
OPERATION_PARAM_MODELS: dict[Operation, type[BaseModel]] = {
    Operation.GROUPBY_AGG: GroupByAggParams,
}


class AnalysisPlan(BaseModel):
    operation: Operation

    # --- Flattened params, one field per possible parameter across ALL
    # operations (all Optional, since only the fields relevant to the
    # chosen operation will actually be filled in). This replaces what
    # would otherwise be a nested `params: dict` -- see module docstring
    # for why that's not possible with Gemini's Developer API.
    #
    # Currently only groupby_agg's fields exist here, since it's the only
    # operation built. When a new operation is added, add its param
    # fields here too (Optional, matching its param model), and extend
    # validate_params() below to build the right model for that operation.
    group_by: Optional[str] = Field(default=None, description="Column to group by")
    metric: Optional[str] = Field(default=None, description="Column to aggregate")
    aggregation: Optional[Literal["mean", "sum", "count", "median", "min", "max", "std"]] = Field(
        default=None, description="How to aggregate the metric column"
    )
    sort_by: Optional[Literal["value_asc", "value_desc", "label"]] = Field(
        default="value_desc", description="How to sort the result"
    )
    limit: Optional[int] = Field(default=None, description="Max rows to return, if the user asked for a top-N style limit")

    chart: ChartType
    explanation_intent: str = Field(
        description="What the LLM should focus on when explaining results, "
        "e.g. 'highlight the department with highest average'"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    clarification_needed: Optional[str] = None

    def validate_params(self) -> BaseModel:
        """
        Builds and validates the correct param model for self.operation,
        pulling from this plan's flattened fields. Call this right after
        the planner returns a plan, before running any analysis.

        Raises ValueError if the operation has no param model registered.
        Raises pydantic.ValidationError if the required fields for this
        operation weren't filled in by the LLM (e.g. group_by is None) --
        this is exactly the "planner picked an operation but didn't fill
        in the params it needs" failure case, caught the same way it was
        before this field-flattening change.
        """
        model = OPERATION_PARAM_MODELS.get(self.operation)
        if model is None:
            raise ValueError(
                f"No param schema registered yet for operation '{self.operation.value}'"
            )

        if self.operation == Operation.GROUPBY_AGG:
            raw = {
                "group_by": self.group_by,
                "metric": self.metric,
                "aggregation": self.aggregation,
                "sort_by": self.sort_by,
                "limit": self.limit,
            }
        else:
            # New operations need their own field-gathering branch here,
            # matching their param model's fields (once added above).
            raise ValueError(
                f"validate_params() doesn't know how to gather fields for "
                f"operation '{self.operation.value}' yet"
            )

        return model.model_validate(raw)