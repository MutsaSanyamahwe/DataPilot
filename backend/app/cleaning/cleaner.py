# cleaning/cleaner.py
#
# Runs after validation, before profiling: upload -> validation -> [THIS
# FILE] -> profiling -> planner. Unlike validation, this file never
# rejects a file -- it only detects issues and reports them. Whether the
# fixes get applied is a decision made by the user (via the API/frontend
# Inspect step), not by this module. That split is deliberate:
#
#   inspect_cleaning(df)  -> CleaningReport   (read-only, always safe to call)
#   apply_cleaning(df)    -> (cleaned_df, log) (only called if user opts in)
#
# The API route calls inspect_cleaning() right after validation and shows
# the report to the user. If they choose "clean automatically," the route
# then calls apply_cleaning() before handing the dataframe to profiling.
# If they choose "leave as-is," profiling runs on the original df.

from dataclasses import dataclass, field
import pandas as pd

# Values that mean "missing" but don't get read as NaN by pandas by default
NULL_LIKE_VALUES = {"n/a", "na", "n.a.", "null", "none", "-", "--", "?", ""}


@dataclass
class Issue:
    kind: str          # e.g. "inconsistent_nulls", "duplicate_rows", "whitespace"
    column: str | None  # None for dataset-wide issues like duplicate rows
    count: int
    description: str


@dataclass
class CleaningReport:
    issues: list[Issue] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0

    def summary(self) -> str:
        if not self.has_issues:
            return "No cleaning issues found."
        return "; ".join(f"{i.description}" for i in self.issues)


def inspect_cleaning(df: pd.DataFrame) -> CleaningReport:
    """
    Detects cleaning issues without modifying the dataframe. Safe to call
    on every upload -- read-only.
    """
    issues: list[Issue] = []
    issues += _detect_inconsistent_nulls(df)
    issues += _detect_whitespace(df)
    issues += _detect_duplicate_rows(df)
    return CleaningReport(issues=issues)


def apply_cleaning(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Applies fixes for everything inspect_cleaning() would report.
    Only call this if the user opted in. Returns (cleaned_df, change_log)
    where change_log is a list of human-readable strings describing what
    was changed -- useful to show the user after the fact, or to log.
    """
    cleaned = df.copy()
    change_log: list[str] = []

    cleaned, log_entries = _fix_inconsistent_nulls(cleaned)
    change_log += log_entries

    cleaned, log_entries = _fix_whitespace(cleaned)
    change_log += log_entries

    cleaned, log_entries = _fix_duplicate_rows(cleaned)
    change_log += log_entries

    return cleaned, change_log


# --- Detection ---

def _detect_inconsistent_nulls(df: pd.DataFrame) -> list[Issue]:
    issues = []
    for col in df.select_dtypes(include="object").columns:
        mask = df[col].astype(str).str.strip().str.lower().isin(NULL_LIKE_VALUES)
        count = mask.sum()
        if count > 0:
            issues.append(Issue(
                kind="inconsistent_nulls",
                column=col,
                count=int(count),
                description=f'{count} inconsistent blank/null-like values in "{col}" '
                            f'(e.g. "N/A", "n/a", "-") will be treated as missing',
            ))
    return issues


def _detect_whitespace(df: pd.DataFrame) -> list[Issue]:
    issues = []
    for col in df.select_dtypes(include="object").columns:
        non_null = df[col].notna()
        stripped = df[col].astype(str).str.strip()
        # Only compare where the original value isn't null -- NaN != NaN
        # is always True in pandas, which would otherwise falsely flag
        # every missing value as "has whitespace".
        mask = non_null & (stripped != df[col].astype(str))
        count = mask.sum()
        if count > 0:
            issues.append(Issue(
                kind="whitespace",
                column=col,
                count=int(count),
                description=f'{count} values in "{col}" have extra leading/trailing whitespace',
            ))
    return issues


def _detect_duplicate_rows(df: pd.DataFrame) -> list[Issue]:
    count = int(df.duplicated().sum())
    if count > 0:
        return [Issue(
            kind="duplicate_rows",
            column=None,
            count=count,
            description=f"{count} fully duplicate rows found",
        )]
    return []


# --- Fixing ---

def _fix_inconsistent_nulls(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    log = []
    for col in df.select_dtypes(include="object").columns:
        mask = df[col].astype(str).str.strip().str.lower().isin(NULL_LIKE_VALUES)
        count = mask.sum()
        if count > 0:
            df.loc[mask, col] = None
            log.append(f'Standardized {count} null-like values in "{col}" to empty')
    return df, log


def _fix_whitespace(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    log = []
    for col in df.select_dtypes(include="object").columns:
        non_null = df[col].notna()
        original = df[col].astype(str)
        stripped = original.str.strip()
        mask = non_null & (stripped != original)
        count = mask.sum()
        if count > 0:
            df.loc[mask, col] = stripped[mask]
            log.append(f'Trimmed whitespace on {count} values in "{col}"')
    return df, log


def _fix_duplicate_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    count = int(df.duplicated().sum())
    if count > 0:
        df = df.drop_duplicates().reset_index(drop=True)
        return df, [f"Removed {count} fully duplicate rows"]
    return df, []