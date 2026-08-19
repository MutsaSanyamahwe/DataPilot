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
    DISTRIBUTION = "distribution"
    COMPARISON = "comparison"
    OUTLIER_DETECTION = "outlier_detection"
    TOP_N = "top_n"
    FILTER = "filter"
    DISTINCT = "distinct"
    SAMPLE = "sample"
    DATE_RANGE_FILTER = "date_range_filter"
    DUPLICATE_ROWS = "duplicate_rows"
    PIVOT = "pivot"


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


class TopNRowsParams(BaseModel):
    """Raw row preview -- no aggregation. 'Show me the top 10 rows'."""
    n: int = 10
    sort_column: Optional[str] = None  # None = original row order, no sorting
    sort_ascending: bool = False


class DescribeDatasetParams(BaseModel):
    """No inputs needed -- always describes the whole dataset (row count,
    column names, types, non-null counts). Empty on purpose."""
    pass


class DistributionParams(BaseModel):
    """Value counts for one column. 'What's the distribution of departments?'"""
    column: str
    limit: Optional[int] = None  # top N categories by count; None = all


class FilterParams(BaseModel):
    """Row-level filtering. 'Show me employees in Sales earning over 70000.'"""
    filter_column: str
    filter_operator: Literal[
        "equals", "not_equals", "greater_than", "less_than",
        "greater_or_equal", "less_or_equal", "contains",
    ]
    filter_value: str  # kept as string; coerced to numeric at runtime if the column is numeric
    limit: Optional[int] = None  # row cap on the (possibly large) filtered result


class DistinctParams(BaseModel):
    """Unique values in one column, no counts. 'What departments exist?'"""
    column: str
    limit: Optional[int] = None


class SampleParams(BaseModel):
    """A random sample of rows, as opposed to top_n's ordered preview."""
    n: int = 10


class TrendParams(BaseModel):
    """
    Groups a date column into periods (day/week/month/quarter/year) and
    aggregates a metric per period -- or just counts rows per period if
    no metric is given. Covers "trend over time", "monthly breakdown",
    "how has X changed over time" style questions in one operation.
    """
    date_column: str
    granularity: Literal["day", "week", "month", "quarter", "year"] = "month"
    metric: Optional[str] = None  # None = count rows per period
    aggregation: Literal["mean", "sum", "count", "median", "min", "max", "std"] = "count"


class DateRangeFilterParams(BaseModel):
    """
    Filters rows to a date range on a date column. start_date/end_date
    are expected as ISO 'YYYY-MM-DD' strings -- the planner is responsible
    for translating relative language ("last year", "since March") into
    absolute dates, since it's told today's date in the prompt.
    """
    date_column: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: Optional[int] = None


class CorrelationParams(BaseModel):
    """
    Two modes: give both column_a and column_b for a single pairwise
    correlation coefficient, or leave both unset for a full correlation
    matrix across every numeric column. Giving only one is invalid --
    the planner should ask for clarification instead.
    """
    column_a: Optional[str] = None
    column_b: Optional[str] = None


class OutlierDetectionParams(BaseModel):
    """Flags statistical outliers in one numeric column using the IQR method."""
    column: str
    limit: Optional[int] = None


class DuplicateRowsParams(BaseModel):
    """
    Shows the actual duplicate rows in the currently loaded data (not the
    upload-time cleaning report -- this checks whatever's loaded right now,
    which may already be cleaned).
    """
    limit: Optional[int] = None


class ComparisonParams(BaseModel):
    """
    Compares one metric between exactly two specific values of a
    categorical column, computing both the absolute and percentage
    difference deterministically (so the explainer reads the numbers
    rather than computing the difference itself).

    metric is optional -- leave it unset for "headcount"/"how many"
    style comparisons (row counts), same pattern as trend/pivot.
    """
    group_column: str
    group_a: str
    group_b: str
    metric: Optional[str] = None
    aggregation: Literal["mean", "sum", "count", "median", "min", "max"] = "mean"


class PivotParams(BaseModel):
    """
    Cross-tabulates two categorical columns. If metric is given, cells
    show the aggregated metric (a true pivot table); if metric is left
    unset, cells show row counts (a crosstab / frequency table).
    """
    row_column: str
    col_column: str
    metric: Optional[str] = None
    aggregation: Literal["mean", "sum", "count", "median", "min", "max"] = "count"


# Maps each Operation to the param model that validates it.
OPERATION_PARAM_MODELS: dict[Operation, type[BaseModel]] = {
    Operation.GROUPBY_AGG: GroupByAggParams,
    Operation.TOP_N: TopNRowsParams,
    Operation.DESCRIBE: DescribeDatasetParams,
    Operation.DISTRIBUTION: DistributionParams,
    Operation.FILTER: FilterParams,
    Operation.DISTINCT: DistinctParams,
    Operation.SAMPLE: SampleParams,
    Operation.TREND: TrendParams,
    Operation.DATE_RANGE_FILTER: DateRangeFilterParams,
    Operation.CORRELATION: CorrelationParams,
    Operation.OUTLIER_DETECTION: OutlierDetectionParams,
    Operation.DUPLICATE_ROWS: DuplicateRowsParams,
    Operation.COMPARISON: ComparisonParams,
    Operation.PIVOT: PivotParams,
}


class AnalysisPlan(BaseModel):
    operation: Operation

    # --- Flattened params, one field per possible parameter across ALL
    # operations (all Optional, since only the fields relevant to the
    # chosen operation will actually be filled in). This replaces what
    # would otherwise be a nested `params: dict` -- see module docstring
    # for why that's not possible with Gemini's Developer API.
    #
    # When a new operation is added: add its param fields here too
    # (Optional, matching its param model), and extend validate_params()
    # below to build the right model for that operation.

    # groupby_agg fields
    group_by: Optional[str] = Field(default=None, description="Column to group by")
    metric: Optional[str] = Field(default=None, description="Column to aggregate")
    aggregation: Optional[Literal["mean", "sum", "count", "median", "min", "max", "std"]] = Field(
        default=None, description="How to aggregate the metric column"
    )
    sort_by: Optional[Literal["value_asc", "value_desc", "label"]] = Field(
        default="value_desc", description="How to sort a groupby_agg result"
    )
    limit: Optional[int] = Field(
        default=None,
        description="Max rows to return -- used as row count for top_n, "
        "or max categories for distribution, or row limit for groupby_agg",
    )

    # top_n fields
    sort_column: Optional[str] = Field(
        default=None, description="Column to sort by for top_n (e.g. 'salary' for highest-paid). "
        "Leave unset to just show rows in their original order."
    )
    sort_ascending: Optional[bool] = Field(
        default=False, description="For top_n: True for lowest-first, False for highest-first"
    )

    # distribution fields
    column: Optional[str] = Field(
        default=None, description="Column to compute a value-count distribution for, "
        "or to get distinct values from"
    )

    # filter fields
    filter_column: Optional[str] = Field(default=None, description="Column to filter on")
    filter_operator: Optional[Literal[
        "equals", "not_equals", "greater_than", "less_than",
        "greater_or_equal", "less_or_equal", "contains",
    ]] = Field(default=None, description="Comparison to apply for filtering")
    filter_value: Optional[str] = Field(
        default=None, description="Value to compare against (as text -- numbers are "
        "coerced automatically if the column is numeric)"
    )

    # trend / date_range_filter fields
    date_column: Optional[str] = Field(
        default=None, description="Date/datetime column to use for trend or date filtering"
    )
    granularity: Optional[Literal["day", "week", "month", "quarter", "year"]] = Field(
        default=None, description="Time period to group by for trend, e.g. 'month'"
    )
    start_date: Optional[str] = Field(
        default=None, description="Start of a date range, as 'YYYY-MM-DD'. Translate relative "
        "phrases like 'last year' into an absolute date using today's date given below."
    )
    end_date: Optional[str] = Field(
        default=None, description="End of a date range, as 'YYYY-MM-DD'. Same rule as start_date."
    )

    # correlation fields
    column_a: Optional[str] = Field(default=None, description="First column for a pairwise correlation")
    column_b: Optional[str] = Field(default=None, description="Second column for a pairwise correlation")

    # comparison fields
    group_column: Optional[str] = Field(default=None, description="Categorical column whose two values are being compared")
    group_a: Optional[str] = Field(default=None, description="First group value to compare, e.g. 'Engineering'")
    group_b: Optional[str] = Field(default=None, description="Second group value to compare, e.g. 'Sales'")

    # pivot fields
    row_column: Optional[str] = Field(default=None, description="Categorical column to use as pivot rows")
    col_column: Optional[str] = Field(default=None, description="Categorical column to use as pivot columns")

    chart: ChartType
    explanation_intent: str = Field(
        description="What the LLM should focus on when explaining results, "
        "e.g. 'highlight the department with highest average'"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    clarification_needed: Optional[str] = None

    # Set this when the user's actual question asks WHY something happened,
    # or needs information this dataset fundamentally can't provide (external
    # causes, business context, opinions) -- even though you're still
    # choosing the closest reasonable data operation as a topically-related
    # answer. This is NOT the same as clarification_needed: clarification is
    # for "I don't know which columns you mean"; this is for "I know what
    # data to show, but it can't actually explain the reason being asked
    # about." Setting this tells the explainer to be upfront that it's
    # showing related data, not the actual cause -- rather than silently
    # answering a "what" when the user asked "why".
    needs_causal_disclaimer: bool = Field(
        default=False,
        description="True if the user asked WHY something happened or for "
        "information outside this dataset, and you're answering with the "
        "closest related data instead of the actual reason. False for "
        "direct, fully-answerable data questions.",
    )

    def validate_params(self) -> BaseModel:
        """
        Builds and validates the correct param model for self.operation,
        pulling from this plan's flattened fields. Call this right after
        the planner returns a plan, before running any analysis.

        Raises ValueError if the operation has no param model registered,
        or has no field-gathering branch below yet. Raises
        pydantic.ValidationError if the required fields for this operation
        weren't filled in by the LLM (e.g. group_by is None for groupby_agg).
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
        elif self.operation == Operation.TOP_N:
            raw = {
                "n": self.limit if self.limit is not None else 10,
                "sort_column": self.sort_column,
                "sort_ascending": bool(self.sort_ascending),
            }
        elif self.operation == Operation.DESCRIBE:
            raw = {}
        elif self.operation == Operation.DISTRIBUTION:
            raw = {
                "column": self.column,
                "limit": self.limit,
            }
        elif self.operation == Operation.FILTER:
            raw = {
                "filter_column": self.filter_column,
                "filter_operator": self.filter_operator,
                "filter_value": self.filter_value,
                "limit": self.limit,
            }
        elif self.operation == Operation.DISTINCT:
            raw = {
                "column": self.column,
                "limit": self.limit,
            }
        elif self.operation == Operation.SAMPLE:
            raw = {
                "n": self.limit if self.limit is not None else 10,
            }
        elif self.operation == Operation.TREND:
            raw = {
                "date_column": self.date_column,
                "granularity": self.granularity or "month",
                "metric": self.metric,
                "aggregation": self.aggregation or "count",
            }
        elif self.operation == Operation.DATE_RANGE_FILTER:
            raw = {
                "date_column": self.date_column,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "limit": self.limit,
            }
        elif self.operation == Operation.CORRELATION:
            raw = {
                "column_a": self.column_a,
                "column_b": self.column_b,
            }
        elif self.operation == Operation.OUTLIER_DETECTION:
            raw = {
                "column": self.column,
                "limit": self.limit,
            }
        elif self.operation == Operation.DUPLICATE_ROWS:
            raw = {
                "limit": self.limit,
            }
        elif self.operation == Operation.COMPARISON:
            raw = {
                "group_column": self.group_column,
                "group_a": self.group_a,
                "group_b": self.group_b,
                "metric": self.metric,
                "aggregation": self.aggregation if self.aggregation in ("mean", "sum", "count", "median", "min", "max") else "mean",
            }
        elif self.operation == Operation.PIVOT:
            raw = {
                "row_column": self.row_column,
                "col_column": self.col_column,
                "metric": self.metric,
                "aggregation": self.aggregation if self.aggregation in ("mean", "sum", "count", "median", "min", "max") else "count",
            }
        else:
            # New operations need their own field-gathering branch here,
            # matching their param model's fields (once added above).
            raise ValueError(
                f"validate_params() doesn't know how to gather fields for "
                f"operation '{self.operation.value}' yet"
            )

        return model.model_validate(raw)