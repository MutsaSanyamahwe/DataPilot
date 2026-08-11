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
    issues += _detect_case_inconsistency(df)
    issues += _detect_duplicate_rows(df)
    return CleaningReport(issues=issues)


def apply_cleaning(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Applies fixes for everything inspect_cleaning() would report.
    Only call this if the user opted in. Returns (cleaned_df, change_log)
    where change_log is a list of human-readable strings describing what
    was changed -- useful to show the user after the fact, or to log.

    Order matters here: case-fixing runs BEFORE duplicate-row removal,
    because normalizing "West" and "west" to the same casing can turn
    two previously-distinct rows into exact duplicates -- we want the
    duplicate check to catch those too, not just pre-existing duplicates.
    """
    cleaned = df.copy()
    change_log: list[str] = []

    cleaned, log_entries = _fix_inconsistent_nulls(cleaned)
    change_log += log_entries

    cleaned, log_entries = _fix_whitespace(cleaned)
    change_log += log_entries

    cleaned, log_entries = _fix_case_inconsistency(cleaned)
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


def _case_variant_map(df: pd.DataFrame, col: str):
    """
    Shared helper for both detection and fixing. Finds values that are
    the same once lowercased/stripped (e.g. "West" and "west") but differ
    in actual casing in the data.

    Returns (mask, canonical_map) where:
    - mask: boolean Series, True for rows whose value should be replaced
      to match the canonical casing for its group.
    - canonical_map: dict of {normalized_key: canonical_actual_value},
      where "canonical" is whichever casing appears most often in that
      group (ties broken by whichever appears first).

    Returns (None, {}) if no case-variant groups exist in this column.
    """
    non_null = df[col].notna()
    raw_vals = df[col].astype(str)
    # Compare STRIPPED values, not raw -- otherwise a pure whitespace
    # difference (e.g. "Marketing " vs "Marketing", same casing) gets
    # miscounted as a case issue. Whitespace is already the whitespace
    # check's job; this check should only fire on genuine case differences.
    stripped_vals = raw_vals.str.strip()
    normalized = stripped_vals.str.lower()

    tmp = pd.DataFrame({"val": stripped_vals[non_null], "norm": normalized[non_null]})
    tmp["orig_idx"] = tmp.index  # preserve row order for tie-breaking below

    counts = (
        tmp.groupby(["norm", "val"])
        .agg(n=("val", "size"), first_idx=("orig_idx", "min"))
        .reset_index()
    )

    variant_norms = counts.groupby("norm")["val"].nunique()
    variant_norms = set(variant_norms[variant_norms > 1].index)
    if not variant_norms:
        return None, {}

    variant_rows = counts[counts["norm"].isin(variant_norms)].copy()
    # Canonical casing = highest row count wins. On an exact tie, prefer
    # whichever casing appeared FIRST in the original data -- without
    # this, a 3-way tie (e.g. "Sales"/"sales"/"SALES" each appearing
    # once) can arbitrarily pick an odd casing like all-caps due to
    # pandas' internal sort order, which looks wrong to a user.
    variant_rows = variant_rows.sort_values(
        ["norm", "n", "first_idx"], ascending=[True, False, True]
    )
    canonical_map = variant_rows.groupby("norm").first()["val"].to_dict()

    canonical_for_row = normalized.map(canonical_map)
    # Compare against the stripped value here too, for the same reason --
    # a row that only has a whitespace difference shouldn't be marked as
    # needing a case fix.
    mask = non_null & normalized.isin(variant_norms) & (stripped_vals != canonical_for_row)
    return mask, canonical_map


def _detect_case_inconsistency(df: pd.DataFrame) -> list[Issue]:
    issues = []
    for col in df.select_dtypes(include="object").columns:
        mask, canonical_map = _case_variant_map(df, col)
        if mask is None:
            continue
        count = int(mask.sum())
        if count > 0:
            # Show a concrete example in the description rather than just
            # a count -- "West" vs "west" is much more legible than an
            # abstract "3 casing issues found".
            example_norm, example_canonical = next(iter(canonical_map.items()))
            group_stripped_vals = (
                df.loc[df[col].astype(str).str.strip().str.lower() == example_norm, col]
                .astype(str).str.strip().unique()
            )
            other_casings = sorted({v for v in group_stripped_vals if v != example_canonical})
            example = f'"{example_canonical}" vs "{other_casings[0]}"' if other_casings else f'"{example_canonical}"'
            issues.append(Issue(
                kind="case_inconsistency",
                column=col,
                count=count,
                description=f'{count} values in "{col}" differ only in capitalization '
                            f'(e.g. {example}) and will be treated as separate categories',
            ))
    return issues


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


def _fix_case_inconsistency(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    log = []
    for col in df.select_dtypes(include="object").columns:
        mask, canonical_map = _case_variant_map(df, col)
        if mask is None:
            continue
        count = int(mask.sum())
        if count > 0:
            normalized = df[col].astype(str).str.strip().str.lower()
            df.loc[mask, col] = normalized[mask].map(canonical_map)
            log.append(f'Standardized capitalization on {count} values in "{col}"')
    return df, log