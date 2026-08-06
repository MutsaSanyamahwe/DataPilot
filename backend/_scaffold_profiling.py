import os

base = r"f:\IBM Data Science\DS_Projects\DataPilot\backend\app"

files = {}

# profiling/__init__.py
files["profiling/__init__.py"] = '''"""Dataset profiling layer - structural and quality profiling."""
from app.profiling.profiler import profile_dataset, profile_column
from app.profiling.relationships import detect_relationships

__all__ = ["profile_dataset", "profile_column", "detect_relationships"]
'''

# profiling/profiler.py
files["profiling/profiler.py"] = '''"""Deterministic dataset and column profiling."""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from app.models import ColumnProfile, DatasetProfile
from app.utils import safe_json_value


def profile_column(series: pd.Series, inferred_type: str) -> ColumnProfile:
    """Build a ColumnProfile for a single pandas Series."""
    n = len(series)
    missing = int(series.isna().sum())
    missing_pct = round((missing / n * 100), 2) if n else 0.0
    unique = int(series.nunique(dropna=True))
    unique_pct = round((unique / n * 100), 2) if n else 0.0

    profile = ColumnProfile(
        name=str(series.name),
        inferred_type=inferred_type,
        pandas_dtype=str(series.dtype),
        missing_count=missing,
        missing_pct=missing_pct,
        unique_count=unique,
        unique_pct=unique_pct,
    )

    non_null = series.dropna()

    if inferred_type == "numeric" and len(non_null) > 0:
        num = pd.to_numeric(non_null, errors="coerce").dropna()
        if len(num) > 0:
            profile.min = float(num.min())
            profile.max = float(num.max())
            profile.mean = float(num.mean())
            profile.median = float(num.median())
            profile.std = float(num.std()) if len(num) > 1 else 0.0
            profile.q1 = float(num.quantile(0.25))
            profile.q3 = float(num.quantile(0.75))

    elif inferred_type == "datetime" and len(non_null) > 0:
        dt = pd.to_datetime(non_null, errors="coerce").dropna()
        if len(dt) > 0:
            profile.min_date = str(dt.min().isoformat())
            profile.max_date = str(dt.max().isoformat())

    elif inferred_type in ("categorical", "boolean", "text") and len(non_null) > 0:
        vc = non_null.value_counts().head(10)
        profile.top_values = [
            {"value": safe_json_value(v), "count": int(c)}
            for v, c in vc.items()
        ]

    return profile


def profile_dataset(df: pd.DataFrame, table_name: str, source_file: str, inferred_types: Dict[str, str]) -> DatasetProfile:
    """Build a full DatasetProfile for a cleaned DataFrame."""
    n_rows = len(df)
    n_cols = len(df.columns)
    mem = int(df.memory_usage(deep=True).sum())
    dup_count = int(df.duplicated().sum())
    dup_pct = round((dup_count / n_rows * 100), 2) if n_rows else 0.0

    columns = [profile_column(df[c], inferred_types.get(c, "unknown")) for c in df.columns]

    return DatasetProfile(
        table_name=table_name,
        source_file=source_file,
        row_count=n_rows,
        column_count=n_cols,
        memory_usage_bytes=mem,
        duplicate_row_count=dup_count,
        duplicate_row_pct=dup_pct,
        columns=columns,
    )
'''

# profiling/relationships.py
files["profiling/relationships.py"] = '''"""Detect lightweight relationships between loaded datasets (shared columns)."""
from __future__ import annotations

from typing import Dict, List

from app.models import DatasetProfile


def detect_relationships(profiles: List[DatasetProfile]) -> List[Dict[str, str]]:
    """Find columns with identical names across tables (candidate join keys)."""
    relationships: List[Dict[str, str]] = []
    for i, a in enumerate(profiles):
        for b in profiles[i + 1:]:
            a_cols = {c.name for c in a.columns}
            b_cols = {c.name for c in b.columns}
            shared = a_cols & b_cols
            for col in shared:
                relationships.append({
                    "left_table": a.table_name,
                    "right_table": b.table_name,
                    "column": col,
                })
    return relationships
'''

for rel, content in files.items():
    full = os.path.join(base, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {rel}")
