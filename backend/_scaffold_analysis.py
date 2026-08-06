import os

base = r"f:\IBM Data Science\DS_Projects\DataPilot\backend\app"

files = {}

# analysis/__init__.py
files["analysis/__init__.py"] = '''"""Statistical analysis engine - deterministic Pandas/NumPy computations."""
from app.analysis.engine import AnalysisEngine

__all__ = ["AnalysisEngine"]
'''

# analysis/engine.py
files["analysis/engine.py"] = '''"""Deterministic analysis engine.

Executes an AnalysisPlan using Pandas/NumPy and returns an AnalysisResult.
The LLM never computes statistics - it only produces the plan and explains
the result.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.config import settings
from app.models import AnalysisPlan, AnalysisResult, ChartSpec
from app.utils import safe_json_value


AGG_FUNCS = {
    "mean": "mean",
    "sum": "sum",
    "median": "median",
    "min": "min",
    "max": "max",
    "count": "count",
    "std": "std",
    "var": "var",
    "nunique": "nunique",
}


class AnalysisEngine:
    """Run deterministic analyses against a loaded DataFrame."""

    def __init__(self, df: pd.DataFrame, inferred_types: Optional[Dict[str, str]] = None):
        self.df = df
        self.inferred_types = inferred_types or {}
        self.max_rows = settings.max_rows_to_model

    # ------------------------------------------------------------------ public
    def execute(self, plan: AnalysisPlan) -> AnalysisResult:
        op = (plan.operation or "").lower().strip()
        handler = getattr(self, f"_op_{op}", None)
        if handler is None:
            raise ValueError(f"Unsupported analysis operation: {op}")

        df = self._apply_filters(plan)
        result = handler(df, plan)
        result.operation = op
        result.table = plan.table
        return result

    # ------------------------------------------------------------------ helpers
    def _apply_filters(self, plan: AnalysisPlan) -> pd.DataFrame:
        df = self.df
        filters = plan.filters or {}
        for col, cond in filters.items():
            if col not in df.columns:
                continue
            if isinstance(cond, dict):
                if "eq" in cond:
                    df = df[df[col] == cond["eq"]]
                if "ne" in cond:
                    df = df[df[col] != cond["ne"]]
                if "gt" in cond:
                    df = df[df[col] > cond["gt"]]
                if "gte" in cond:
                    df = df[df[col] >= cond["gte"]]
                if "lt" in cond:
                    df = df[df[col] < cond["lt"]]
                if "lte" in cond:
                    df = df[df[col] <= cond["lte"]]
                if "in" in cond:
                    df = df[df[col].isin(cond["in"])]
            else:
                df = df[df[col] == cond]
        return df

    def _rows_to_dicts(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        capped = df.head(self.max_rows)
        return [
            {k: safe_json_value(v) for k, v in row.items()}
            for _, row in capped.iterrows()
        ]

    def _make_chart(self, kind: str, title: str, **kwargs) -> ChartSpec:
        return ChartSpec(kind=kind, title=title, **kwargs)

    # ------------------------------------------------------------------ ops
    def _op_describe(self, df: pd.DataFrame, plan: AnalysisPlan) -> AnalysisResult:
        """Full summary statistics for the dataset or selected columns."""
        cols = (plan.metric or list(df.columns))
        numeric_cols = [c for c in cols if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        desc = df[numeric_cols].describe().reset_index() if numeric_cols else pd.DataFrame()
        summary = {
            "row_count": int(len(df)),
            "numeric_columns": numeric_cols,
            "statistics": {
                c: {
                    "mean": safe_json_value(df[c].mean()),
                    "median": safe_json_value(df[c].median()),
                    "std": safe_json_value(df[c].std()),
                    "min": safe_json_value(df[c].min()),
                    "max": safe_json_value(df[c].max()),
                    "q1": safe_json_value(df[c].quantile(0.25)),
                    "q3": safe_json_value(df[c].quantile(0.75)),
                    "missing_pct": round(float(df[c].isna().mean() * 100), 2),
                }
                for c in numeric_cols
            },
        }
        data = self._rows_to_dicts(desc) if not desc.empty else []
        chart = None
        if numeric_cols:
            chart = self._make_chart(
                "table", "Summary statistics",
                table_columns=list(desc.columns) if not desc.empty else numeric_cols,
                table_rows=[[safe_json_value(v) for v in r] for r in desc.head(20).values.tolist()] if not desc.empty else [],
            )
        return AnalysisResult(operation="describe", table=plan.table, summary=summary, data=data, chart=chart)

    def _op_summary(self, df: pd.DataFrame, plan: AnalysisPlan) -> AnalysisResult:
        """Alias for describe focused on a single metric column."""
        return self._op_describe(df, plan)

    def _op_groupby(self, df: pd.DataFrame, plan: AnalysisPlan) -> AnalysisResult:
        group_by = plan.group_by or []
        metrics = plan.metric or []
        agg = (plan.aggregation or "mean").lower()
        if agg not in AGG_FUNCS:
            raise ValueError(f"Unsupported aggregation: {agg}")
        if not group_by or not metrics:
            raise ValueError("groupby requires group_by and metric fields.")

        existing_metrics = [m for m in metrics if m in df.columns]
        if not existing_metrics:
            raise ValueError(f"None of the metric columns {metrics} exist in table.")

        grouped = df.groupby(group_by, dropna=False)[existing_metrics].agg(AGG_FUNCS[agg])
        grouped = grouped.reset_index().sort_values(by=existing_metrics[0], ascending=False)

        summary = {
            "group_by": group_by,
            "metric": existing_metrics,
            "aggregation": agg,
            "group_count": int(len(grouped)),
            "top_group": safe_json_value(grouped.iloc[0].to_dict()) if len(grouped) > 0 else None,
            "min_group": safe_json_value(grouped.iloc[-1].to_dict()) if len(grouped) > 0 else None,
        }

        data = self._rows_to_dicts(grouped)

        chart_kind = (plan.chart or "bar").lower()
        labels = [str(safe_json_value(v)) for v in grouped[group_by[0]].head(20).tolist()]
        values = [float(safe_json_value(v) or 0) for v in grouped[existing_metrics[0]].head(20).tolist()]
        chart = self._make_chart(
            chart_kind,
            f"{agg.title()} of {existing_metrics[0]} by {group_by[0]}",
            x_label=group_by[0],
            y_label=f"{agg}({existing_metrics[0]})",
            labels=labels,
            values=values,
        )
        return AnalysisResult(operation="groupby", table=plan.table, summary=summary, data=data, chart=chart)

    def _op_correlation(self, df: pd.DataFrame, plan: AnalysisPlan) -> AnalysisResult:
        numeric = df.select_dtypes(include=[np.number])
        if numeric.shape[1] < 2:
            raise ValueError("Correlation requires at least two numeric columns.")
        corr = numeric.corr()
        summary = {
            "columns": list(corr.columns),
            "strongest_positive": self._top_corr(corr, positive=True),
            "strongest_negative": self._top_corr(corr, positive=False),
        }
        data = self._rows_to_dicts(corr.reset_index())
        # Heatmap series
        series = []
        for i, row in enumerate(corr.index):
            for j, col in enumerate(corr.columns):
                series.append({"x": col, "y": row, "v": float(corr.iloc[i, j])})
        chart = self._make_chart("heatmap", "Correlation matrix", series=series)
        return AnalysisResult(operation="correlation", table=plan.table, summary=summary, data=data, chart=chart)

    def _top_corr(self, corr: pd.DataFrame, positive: bool) -> Optional[Dict[str, Any]]:
        if corr.empty:
            return None
        c = corr.copy()
        np.fill_diagonal(c.values, np.nan)
        if positive:
            val = c.max().max()
        else:
            val = c.min().min()
        if pd.isna(val):
            return None
        loc = c.stack().idxmax() if positive else c.stack().idxmin()
        return {"pair": list(loc), "value": float(val)}

    def _op_distribution(self, df: pd.DataFrame, plan: AnalysisPlan) -> AnalysisResult:
        cols = plan.metric or []
        if not cols:
            raise ValueError("distribution requires a metric column.")
        col = cols[0]
        if col not in df.columns:
            raise ValueError(f"Column {col} not found.")
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        bins = int((plan.params or {}).get("bins", 10))
        counts, edges = np.histogram(series, bins=bins)
        labels = [f"{edges[i]:.1f}-{edges[i+1]:.1f}" for i in range(len(counts))]
        summary = {
            "column": col,
            "bins": bins,
            "mean": float(series.mean()) if len(series) else None,
            "median": float(series.median()) if len(series) else None,
            "std": float(series.std()) if len(series) > 1 else 0.0,
            "skew": float(series.skew()) if len(series) > 2 else 0.0,
        }
        chart = self._make_chart("histogram", f"Distribution of {col}", x_label=col, y_label="Frequency", labels=labels, values=[int(c) for c in counts])
        return AnalysisResult(operation="distribution", table=plan.table, summary=summary, data=[], chart=chart)

    def _op_timeseries(self, df: pd.DataFrame, plan: AnalysisPlan) -> AnalysisResult:
        params = plan.params or {}
        date_col = (plan.group_by or [params.get("date_col")])[0]
        value_col = (plan.metric or [params.get("value_col")])[0]
        if not date_col or not value_col:
            raise ValueError("timeseries requires a date column and a value column.")
        if date_col not in df.columns or value_col not in df.columns:
            raise ValueError(f"Columns {date_col} or {value_col} not found.")
        ts = df[[date_col, value_col]].copy()
        ts[date_col] = pd.to_datetime(ts[date_col], errors="coerce")
        ts = ts.dropna(subset=[date_col])
        ts[value_col] = pd.to_numeric(ts[value_col], errors="coerce")
        freq = params.get("freq", "M")
        agg = (plan.aggregation or "sum").lower()
        ts = ts.set_index(date_col).resample(freq)[value_col].agg(AGG_FUNCS.get(agg, "sum")).reset_index()
        ts = ts.dropna(subset=[value_col])

        if len(ts) >= 2:
            first, last = float(ts[value_col].iloc[0]), float(ts[value_col].iloc[-1])
            pct_change = ((last - first) / first * 100) if first else 0.0
        else:
            pct_change = 0.0

        summary = {
            "date_col": date_col,
            "value_col": value_col,
            "freq": freq,
            "aggregation": agg,
            "periods": int(len(ts)),
            "first_value": float(ts[value_col].iloc[0]) if len(ts) else None,
            "last_value": float(ts[value_col].iloc[-1]) if len(ts) else None,
            "pct_change": round(pct_change, 2),
            "trend": "increasing" if pct_change > 0 else "decreasing" if pct_change < 0 else "flat",
        }
        data = self._rows_to_dicts(ts)
        labels = [d.strftime("%Y-%m-%d") for d in ts[date_col].tolist()]
        values = [float(v) for v in ts[value_col].tolist()]
        chart = self._make_chart("line", f"{agg.title()} {value_col} over time", x_label=date_col, y_label=value_col, labels=labels, values=values)
        return AnalysisResult(operation="timeseries", table=plan.table, summary=summary, data=data, chart=chart)

    def _op_topn(self, df: pd.DataFrame, plan: AnalysisPlan) -> AnalysisResult:
        params = plan.params or {}
        n = int(params.get("n", 10))
        cols = plan.metric or []
        group = (plan.group_by or [None])[0]
        if not group or not cols:
            raise ValueError("topn requires group_by and metric.")
        col = cols[0]
        agg = (plan.aggregation or "sum").lower()
        grouped = df.groupby(group, dropna=False)[col].agg(AGG_FUNCS.get(agg, "sum")).reset_index()
        grouped = grouped.sort_values(by=col, ascending=False).head(n)
        summary = {
            "group_by": group,
            "metric": col,
            "aggregation": agg,
            "n": n,
            "top": safe_json_value(grouped.iloc[0].to_dict()) if len(grouped) else None,
        }
        data = self._rows_to_dicts(grouped)
        chart = self._make_chart("bar", f"Top {n} {group} by {agg} {col}", x_label=group, y_label=col, labels=[str(v) for v in grouped[group].tolist()], values=[float(v) for v in grouped[col].tolist()])
        return AnalysisResult(operation="topn", table=plan.table, summary=summary, data=data, chart=chart)

    def _op_outlier(self, df: pd.DataFrame, plan: AnalysisPlan) -> AnalysisResult:
        cols = plan.metric or []
        if not cols:
            raise ValueError("outlier requires a metric column.")
        col = cols[0]
        series = pd.to_numeric(df[col], errors="coerce")
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        mask = (series < lower) | (series > upper)
        outliers = df[mask].copy()
        summary = {
            "column": col,
            "method": "IQR (1.5x)",
            "lower_bound": float(lower),
            "upper_bound": float(upper),
            "outlier_count": int(mask.sum()),
            "outlier_pct": round(float(mask.mean() * 100), 2),
        }
        data = self._rows_to_dicts(outliers)
        chart = self._make_chart("box", f"Outliers in {col}", x_label=col, values=[float(v) for v in series.dropna().tolist()])
        return AnalysisResult(operation="outlier", table=plan.table, summary=summary, data=data, chart=chart)

    def _op_frequency(self, df: pd.DataFrame, plan: AnalysisPlan) -> AnalysisResult:
        cols = plan.metric or plan.group_by or []
        if not cols:
            raise ValueError("frequency requires a column.")
        col = cols[0]
        vc = df[col].value_counts().reset_index()
        vc.columns = [col, "count"]
        vc["pct"] = (vc["count"] / vc["count"].sum() * 100).round(2)
        summary = {
            "column": col,
            "unique_values": int(df[col].nunique()),
            "most_frequent": safe_json_value(vc.iloc[0].to_dict()) if len(vc) else None,
        }
        data = self._rows_to_dicts(vc.head(20))
        chart = self._make_chart("bar", f"Frequency of {col}", x_label=col, y_label="count", labels=[str(v) for v in vc[col].head(20).tolist()], values=[int(v) for v in vc["count"].head(20).tolist()])
        return AnalysisResult(operation="frequency", table=plan.table, summary=summary, data=data, chart=chart)

    def _op_pivot(self, df: pd.DataFrame, plan: AnalysisPlan) -> AnalysisResult:
        params = plan.params or {}
        rows = plan.group_by or [params.get("rows")]
        cols = params.get("cols")
        vals = (plan.metric or [params.get("vals")])
        agg = (plan.aggregation or "mean").lower()
        if not rows or not cols or not vals:
            raise ValueError("pivot requires rows, cols, and vals.")
        rows = rows[0] if isinstance(rows, list) else rows
        vals = vals[0] if isinstance(vals, list) else vals
        pivot = pd.pivot_table(df, index=rows, columns=cols, values=vals, aggfunc=AGG_FUNCS.get(agg, "mean"))
        pivot = pivot.reset_index()
        summary = {
            "rows": rows,
            "cols": cols,
            "values": vals,
            "aggregation": agg,
            "shape": list(pivot.shape),
        }
        data = self._rows_to_dicts(pivot)
        chart = self._make_chart("table", f"Pivot: {vals} by {rows} and {cols}", table_columns=list(pivot.columns), table_rows=[[safe_json_value(v) for v in r] for r in pivot.head(20).values.tolist()])
        return AnalysisResult(operation="pivot", table=plan.table, summary=summary, data=data, chart=chart)
'''

for rel, content in files.items():
    full = os.path.join(base, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {rel}")
