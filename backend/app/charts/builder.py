# charts/builder.py
#
# Takes the AnalysisResult produced by analysis.registry.run_plan() and
# turns it into a plain dict the frontend's Chart.jsx can render directly
# (bar/line/pie/stat/table -- same shapes it already knows how to draw
# from v1). No LLM involved here, no Pandas computation either -- this
# file only reshapes an already-computed dataframe into a chart spec.
#
# Important distinction from v1: in v1, chart type was *guessed* from the
# shape of arbitrary SQL results, because the LLM could return any shape.
# In v2, the planner LLM already chose a chart_type as part of the plan
# (see planner/schemas.py ChartType). This file mostly trusts that choice,
# but includes a couple of small sanity overrides -- e.g. a "pie" chart
# with 20 categories is unreadable, so we downgrade it to "bar" -- because
# the LLM chose the chart type without actually seeing the row count.

import math
from dataclasses import dataclass
from typing import Any

from app.analysis.registry import AnalysisResult

MAX_PIE_SLICES = 6
MAX_TABLE_ROWS = 50


def build_chart(result: AnalysisResult) -> dict[str, Any] | None:
    """
    Converts an AnalysisResult into a chart spec dict.
    Returns None if chart_type is "none" or there's no data to show.
    """
    df = result.data

    if result.chart_type == "none" or df.empty:
        return None

    # Single row, single column -> one big number ("stat" card),
    # regardless of what chart type the planner picked -- there's
    # nothing else meaningful to draw with one value.
    if df.shape == (1, 1):
        return _build_stat(df)

    # Anything with exactly 2 columns is the common "label, value" shape
    # that groupby_agg (and most other operations) will produce.
    if df.shape[1] == 2:
        return _build_label_value_chart(df, requested_type=result.chart_type)

    # More than 2 columns -- not a simple chartable shape, fall back to a table.
    return _build_table(df)


def _build_stat(df) -> dict[str, Any]:
    label = df.columns[0]
    value = _safe_value(df.iloc[0, 0])
    return {
        "kind": "stat",
        "title": label,
        "labels": [],
        "values": [],
        "value": value,
    }


def _build_label_value_chart(df, requested_type: str) -> dict[str, Any]:
    label_col, value_col = df.columns[0], df.columns[1]
    labels = [str(v) for v in df[label_col]]
    values = [_safe_value(v) for v in df[value_col]]

    chart_type = requested_type

    # Sanity override: too many slices makes a pie chart unreadable.
    if chart_type == "pie" and len(labels) > MAX_PIE_SLICES:
        chart_type = "bar"

    # Sanity override: "stat" or "none" requested but we actually have
    # multiple rows -- the planner likely misjudged this, bar is a safe default.
    if chart_type in ("stat", "none"):
        chart_type = "bar"

    return {
        "kind": chart_type,
        "title": f"{value_col} by {label_col}",
        "labels": labels,
        "values": values,
    }


def _build_table(df) -> dict[str, Any]:
    limited = df.head(MAX_TABLE_ROWS)
    return {
        "kind": "table",
        "title": "Results",
        "labels": [],
        "values": [],
        "tableColumns": list(limited.columns),
        "tableRows": [
            [_safe_value(v) for v in row]
            for row in limited.itertuples(index=False)
        ],
    }


def _safe_value(v):
    """Converts numpy/pandas scalar types into plain JSON-safe Python types."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "item"):  # numpy scalar (int64, float64, etc.)
        return v.item()
    return v