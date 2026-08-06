# planner/schemas.py

## this file contains code that defines  what a valid plan looks like.
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError


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
# Only groupby_agg exists for now, since it's the only operation we've
# actually built in analysis/. Add one of these per operation as we build it.

class GroupByAggParams(BaseModel):
    group_by: str
    metric: str
    aggregation: Literal["mean", "sum", "count", "median", "min", "max", "std"]
    sort_by: Optional[Literal["value_asc", "value_desc", "label"]] = "value_desc"
    limit: Optional[int] = None


# Maps each Operation to the param model that validates it.
# This is the single source of truth — nothing here yet for the other
# 8 operations, so plans using them will correctly fail validation
# until we add their param models.
OPERATION_PARAM_MODELS: dict[Operation, type[BaseModel]] = {
    Operation.GROUPBY_AGG: GroupByAggParams,
}


class AnalysisPlan(BaseModel):
    operation: Operation
    params: dict  # raw params from the LLM, validated below via validate_params()
    chart: ChartType
    explanation_intent: str = Field(
        description="What the LLM should focus on when explaining results, "
        "e.g. 'highlight the department with highest average'"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    clarification_needed: Optional[str] = None  # planner can bail and ask the user something

    def validate_params(self) -> BaseModel:
        """
        Validates self.params against the correct param model for self.operation.
        Call this right after the planner returns a plan, before running any analysis.
        Raises ValueError if the operation has no param model yet, or ValidationError
        if the params themselves are invalid.
        """
        model = OPERATION_PARAM_MODELS.get(self.operation)
        if model is None:
            raise ValueError(
                f"No param schema registered yet for operation '{self.operation.value}'"
            )
        return model.model_validate(self.params)