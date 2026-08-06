import os

base = r"f:\IBM Data Science\DS_Projects\DataPilot\backend\app"

files = {}

# cleaning/__init__.py
files["cleaning/__init__.py"] = '''"""Data cleaning layer - validation, type inference, normalization."""
from app.cleaning.validator import validate_file, ValidationResult
from app.cleaning.cleaner import clean_dataframe, CleaningReport
from app.cleaning.type_inference import infer_types

__all__ = [
    "validate_file",
    "ValidationResult",
    "clean_dataframe",
    "CleaningReport",
    "infer_types",
]
'''

# cleaning/validator.py
files["cleaning/validator.py"] = '''"""File-level validation: encoding, headers, duplicates, structure."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import chardet
import pandas as pd


ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MAX_FILE_SIZE_MB = 100


@dataclass
class ValidationResult:
    valid: bool
    filename: str
    file_type: str
    encoding: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sheets: Optional[List[str]] = None


def _detect_encoding(path: Path) -> str:
    with open(path, "rb") as f:
        raw = f.read(100_000)
    result = chardet.detect(raw)
    return result.get("encoding") or "utf-8"


def validate_file(path: Path) -> ValidationResult:
    """Validate a single uploaded file before loading."""
    if not path.exists():
        return ValidationResult(False, path.name, "", errors=["File not found."])

    ext = path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return ValidationResult(
            False, path.name, ext,
            errors=[f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}"],
        )

    size_mb = path.stat().st_size / (1024 * 1024)
    result = ValidationResult(True, path.name, ext.lstrip("."))

    if size_mb > MAX_FILE_SIZE_MB:
        result.warnings.append(f"File is large ({size_mb:.1f} MB); processing may be slow.")

    if ext == ".csv":
        encoding = _detect_encoding(path)
        result.encoding = encoding
        try:
            # Try reading just the header
            df_head = pd.read_csv(path, nrows=0, encoding=encoding)
            cols = list(df_head.columns)
            if any(not str(c).strip() for c in cols):
                result.warnings.append("One or more columns have empty/blank headers.")
            if len(cols) != len(set(cols)):
                result.errors.append("Duplicate column names detected in CSV header.")
                result.valid = False
            if len(cols) == 0:
                result.errors.append("No columns found in CSV.")
                result.valid = False
        except UnicodeDecodeError:
            # Retry with utf-8-sig / latin-1 fallback
            for fallback in ("utf-8-sig", "latin-1"):
                try:
                    pd.read_csv(path, nrows=0, encoding=fallback)
                    result.encoding = fallback
                    break
                except Exception:
                    continue
            else:
                result.errors.append("Could not decode CSV with any known encoding.")
                result.valid = False
        except pd.errors.EmptyDataError:
            result.errors.append("CSV file is empty.")
            result.valid = False
        except Exception as e:
            result.errors.append(f"CSV parse error: {str(e)}")
            result.valid = False
    else:
        try:
            xls = pd.ExcelFile(path)
            result.sheets = xls.sheet_names
            if not result.sheets:
                result.errors.append("Excel file has no sheets.")
                result.valid = False
        except Exception as e:
            result.errors.append(f"Excel parse error: {str(e)}")
            result.valid = False

    return result
'''

# cleaning/type_inference.py
files["cleaning/type_inference.py"] = '''"""Infer semantic column types from pandas dtypes and content."""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def infer_types(df: pd.DataFrame) -> Dict[str, str]:
    """Return a mapping of column name -> inferred semantic type.

    Categories: numeric | categorical | datetime | boolean | text | unknown
    """
    inferred: Dict[str, str] = {}
    for col in df.columns:
        s = df[col]
        dtype = s.dtype

        # Boolean
        if dtype == bool:
            inferred[col] = "boolean"
            continue
        if dtype == object:
            non_null = s.dropna()
            if len(non_null) > 0:
                uniq = set(non_null.unique())
                if uniq <= {True, False, "True", "False", "true", "false", "yes", "no", "Yes", "No", 1, 0}:
                    inferred[col] = "boolean"
                    continue

        # Numeric
        if pd.api.types.is_numeric_dtype(dtype):
            # Low-cardinality numeric could be categorical code, but keep numeric
            inferred[col] = "numeric"
            continue

        # Datetime
        if pd.api.types.is_datetime64_any_dtype(dtype):
            inferred[col] = "datetime"
            continue

        # Try parsing object columns
        if dtype == object:
            non_null = s.dropna()
            if len(non_null) == 0:
                inferred[col] = "unknown"
                continue

            # Try datetime parse
            try:
                parsed = pd.to_datetime(non_null.head(50), errors="raise")
                inferred[col] = "datetime"
                continue
            except Exception:
                pass

            # Try numeric parse
            try:
                pd.to_numeric(non_null.head(50), errors="raise")
                inferred[col] = "numeric"
                continue
            except Exception:
                pass

            # Categorical vs text: cardinality ratio
            n_unique = non_null.nunique()
            n_total = len(non_null)
            if n_total > 0 and n_unique / n_total < 0.5 and n_unique < 100:
                inferred[col] = "categorical"
            else:
                inferred[col] = "text"
            continue

        inferred[col] = "unknown"
    return inferred
'''

# cleaning/cleaner.py
files["cleaning/cleaner.py"] = '''"""Deterministic data cleaning: missing values, duplicates, types, dates, strings."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np
import pandas as pd

from app.cleaning.type_inference import infer_types


@dataclass
class CleaningReport:
    actions: List[str] = field(default_factory=list)
    rows_before: int = 0
    rows_after: int = 0
    duplicates_removed: int = 0
    columns_cleaned: List[str] = field(default_factory=list)
    type_conversions: Dict[str, str] = field(default_factory=dict)


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport, Dict[str, str]]:
    """Clean a DataFrame deterministically and return (cleaned_df, report, inferred_types).

    Steps:
      1. Strip whitespace from column names and string cells.
      2. Drop fully-empty rows.
      3. Remove duplicate rows.
      4. Infer and convert types (numeric, datetime, boolean).
      5. Normalize string columns (strip, collapse internal whitespace).
    """
    report = CleaningReport(rows_before=len(df))
    df = df.copy()

    # 1. Clean column names
    original_cols = list(df.columns)
    df.columns = [str(c).strip() for c in df.columns]
    if list(df.columns) != original_cols:
        report.actions.append("Stripped whitespace from column names.")

    # 2. Drop fully-empty rows
    empty_rows = df.isna().all(axis=1)
    n_empty = int(empty_rows.sum())
    if n_empty > 0:
        df = df[~empty_rows]
        report.actions.append(f"Removed {n_empty} fully-empty rows.")

    # 3. Remove duplicate rows
    n_before = len(df)
    df = df.drop_duplicates()
    n_dups = n_before - len(df)
    report.duplicates_removed = n_dups
    if n_dups > 0:
        report.actions.append(f"Removed {n_dups} duplicate rows.")

    # 4. Type inference and conversion
    inferred = infer_types(df)
    report.type_conversions = {}

    for col, sem_type in inferred.items():
        if sem_type == "numeric" and df[col].dtype == object:
            try:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                report.type_conversions[col] = "numeric"
                report.columns_cleaned.append(col)
            except Exception:
                pass
        elif sem_type == "datetime":
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce")
                report.type_conversions[col] = "datetime"
                report.columns_cleaned.append(col)
            except Exception:
                pass
        elif sem_type == "boolean" and df[col].dtype == object:
            mapping = {
                "true": True, "false": False, "yes": True, "no": False,
                "1": True, "0": False, 1: True, 0: False,
            }
            lower = df[col].astype(str).str.lower().str.strip()
            df[col] = lower.map(mapping).where(lower.isin(mapping.keys()), df[col])
            report.type_conversions[col] = "boolean"
            report.columns_cleaned.append(col)

    # 5. Normalize string columns
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip().replace({"nan": np.nan, "None": np.nan, "": np.nan})
            report.columns_cleaned.append(col)

    report.actions.append("Normalized string columns (stripped whitespace, null markers).")
    report.rows_after = len(df)
    return df, report, inferred
'''

for rel, content in files.items():
    full = os.path.join(base, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {rel}")
