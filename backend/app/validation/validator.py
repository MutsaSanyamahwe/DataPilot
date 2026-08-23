# validation/validator.py
#
# Runs first in the pipeline, right after a file is parsed into a
# dataframe (upload -> [THIS FILE] -> cleaning -> profiling -> planner).
# Its only job is to catch files that are fundamentally unusable and
# reject them immediately with a clear reason. It does NOT fix anything
# and does NOT judge data quality (messy-but-usable data is cleaning's
# job, not validation's) -- this is strictly a pass/fail gate.

import pandas as pd

from app.config import settings


class ValidationError(Exception):
    """Raised when a dataset fails a hard validation check. Carries a
    user-facing reason -- safe to show directly in an API error response."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


MIN_ROWS = 1
MIN_COLUMNS = 1
# Upper bounds come from settings (app/config.py) rather than being
# hardcoded here, so ops can tune them via env vars without a code change.
# max_rows_dataset exists to keep the whole pipeline (parquet storage,
# profiling, the per-question analysis pass) fast and within the
# analysis_timeout_seconds budget -- pandas ops on a multi-million-row
# dataframe inside a single request can blow that budget easily.
# max_columns_dataset exists mainly for the planner LLM call: the dataset
# profile lists every column with dtype + sample values, and a very wide
# dataset would bloat that prompt past what's useful (and past what the
# free-tier model was validated against).
MAX_ROWS = settings.max_rows_dataset
MAX_COLUMNS = settings.max_columns_dataset


def validate_dataset(df: pd.DataFrame) -> None:
    """
    Runs all hard-reject checks against a freshly-parsed dataframe.
    Raises ValidationError on the first failure. Returns None (no error)
    if the dataset is usable enough to proceed to cleaning.
    """
    _check_not_empty(df)
    _check_has_columns(df)
    _check_no_duplicate_columns(df)
    _check_not_entirely_null(df)
    _check_has_named_columns(df)
    _check_not_too_many_rows(df)
    _check_not_too_many_columns(df)


def _check_not_empty(df: pd.DataFrame) -> None:
    if len(df) < MIN_ROWS:
        raise ValidationError(
            "This file has no data rows. Please upload a file with at least one row of data."
        )


def _check_has_columns(df: pd.DataFrame) -> None:
    if len(df.columns) < MIN_COLUMNS:
        raise ValidationError("This file has no columns. Please check the file and try again.")


def _check_no_duplicate_columns(df: pd.DataFrame) -> None:
    duplicates = df.columns[df.columns.duplicated()].tolist()
    if duplicates:
        raise ValidationError(
            f"This file has duplicate column names: {', '.join(set(duplicates))}. "
            "Please rename the duplicate columns and re-upload."
        )


def _check_not_entirely_null(df: pd.DataFrame) -> None:
    if df.isnull().all().all():
        raise ValidationError(
            "Every cell in this file is empty. Please check the file and try again."
        )


def _check_not_too_many_rows(df: pd.DataFrame) -> None:
    if len(df) > MAX_ROWS:
        raise ValidationError(
            f"This file has {len(df):,} rows, which is more than the "
            f"{MAX_ROWS:,}-row limit for this tool. Please upload a smaller "
            "file, or pre-filter/aggregate it before uploading."
        )


def _check_not_too_many_columns(df: pd.DataFrame) -> None:
    if len(df.columns) > MAX_COLUMNS:
        raise ValidationError(
            f"This file has {len(df.columns):,} columns, which is more than "
            f"the {MAX_COLUMNS:,}-column limit for this tool. Please remove "
            "unused columns and try again."
        )


def _check_has_named_columns(df: pd.DataFrame) -> None:
    # Pandas auto-names blank header cells "Unnamed: 0", "Unnamed: 1", etc.
    # If most columns are unnamed, the file likely has no real header row.
    unnamed_count = sum(1 for c in df.columns if str(c).startswith("Unnamed:"))
    if unnamed_count > len(df.columns) / 2:
        raise ValidationError(
            "This file doesn't appear to have proper column headers. "
            "Please make sure the first row contains column names."
        )
