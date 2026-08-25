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
import re
import pandas as pd

# Values that mean "missing" but don't get read as NaN by pandas by default
NULL_LIKE_VALUES = {"n/a", "na", "n.a.", "null", "none", "-", "--", "?", ""}

# Matches a number written as formatted text: optional leading minus,
# optional currency symbol, either comma-grouped thousands or a plain
# digit run, an optional decimal part, and an optional trailing percent
# sign. Covers "96.30%", "$1,234.56", "1,234", "-42.5", "42%".
# Deliberately does NOT cover accounting-style parentheses-negative
# ("(1,234.56)") -- a known gap, not attempted here to keep the pattern
# (and the decision of what counts as "numeric text") unambiguous.
NUMERIC_TEXT_PATTERN = re.compile(
    r"^\s*-?[$£€]?\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?\s*$"
)

# How much of a column has to match NUMERIC_TEXT_PATTERN before it's
# treated as "numbers stored as text" rather than a genuine mixed/text
# column. Deliberately stricter than the date-detection ratio elsewhere
# in this codebase (suggestions/generator.py uses 0.8) -- wrongly
# coercing a real categorical/ID column to numeric is a worse mistake
# than missing a genuine numeric-as-text column, so this requires
# near-unanimous agreement across the column's values.
NUMERIC_FORMAT_MATCH_RATIO = 0.9


def _parse_numeric_text(value) -> float | None:
    """Strips common numeric formatting (currency symbol, thousands
    commas, trailing %) and parses what's left as a float. Returns None
    if it can't be parsed -- callers are expected to have already
    confirmed the column matches NUMERIC_TEXT_PATTERN at a high enough
    ratio before calling this, so a None here should be rare."""
    if pd.isna(value):
        return None
    s = str(value).strip()
    negative = s.startswith("-")
    s = s.lstrip("-").strip()
    for symbol in ("$", "£", "€", ","):
        s = s.replace(symbol, "")
    s = s.strip()
    if s.endswith("%"):
        s = s[:-1].strip()
    try:
        num = float(s)
    except ValueError:
        return None
    return -num if negative else num


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
    issues += _detect_numeric_formatted_as_text(df)
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
    Numeric-text coercion runs for the same reason, right after case
    fixing: converting "96.30%" and "96.30 %" to the same float can also
    turn two previously-distinct rows into duplicates.
    """
    cleaned = df.copy()
    change_log: list[str] = []

    cleaned, log_entries = _fix_inconsistent_nulls(cleaned)
    change_log += log_entries

    cleaned, log_entries = _fix_whitespace(cleaned)
    change_log += log_entries

    cleaned, log_entries = _fix_case_inconsistency(cleaned)
    change_log += log_entries

    cleaned, log_entries = _fix_numeric_formatted_as_text(cleaned)
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


def _detect_numeric_formatted_as_text(df: pd.DataFrame) -> list[Issue]:
    issues = []
    for col in df.select_dtypes(include="object").columns:
        non_null = df[col].dropna()
        if non_null.empty:
            continue
        stripped = non_null.astype(str).str.strip()
        matches = stripped.str.match(NUMERIC_TEXT_PATTERN)
        if matches.mean() < NUMERIC_FORMAT_MATCH_RATIO:
            continue
        sample_value = stripped[matches].iloc[0]
        issues.append(Issue(
            kind="numeric_formatted_as_text",
            column=col,
            count=int(matches.sum()),
            description=f'"{col}" looks numeric but is stored as text (e.g. "{sample_value}") '
                        f'-- a %, $, or thousands-comma will be stripped and it will be '
                        f'converted to a real number',
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


def _looks_code_like(value: str) -> bool:
    """
    True for values shaped like a code/identifier rather than free-text
    prose: no whitespace, and contains both a letter and a digit (e.g.
    "N408CA", "SKU-1042"). Used by _case_variant_map to decide HOW to
    canonicalize a case-inconsistent group.

    Deliberately narrow: pure-alphabetic multi-word values ("Concord,
    NC", "west", "Sales") never match this, so free-text categorical
    columns keep the existing "most common casing wins" behavior --
    that's still the right default there, since there's no external
    convention dictating how someone should have typed "Concord, NC".
    Only code-shaped values get the override below.
    """
    has_space = any(ch.isspace() for ch in value)
    has_letter = any(ch.isalpha() for ch in value)
    has_digit = any(ch.isdigit() for ch in value)
    return not has_space and has_letter and has_digit


def _case_variant_map(df: pd.DataFrame, col: str):
    """
    Shared helper for both detection and fixing. Finds values that are
    the same once lowercased/stripped (e.g. "West" and "west") but differ
    in actual casing in the data.

    Returns (mask, canonical_map) where:
    - mask: boolean Series, True for rows whose value should be replaced
      to match the canonical casing for its group.
    - canonical_map: dict of {normalized_key: canonical_actual_value}.
      For ordinary free-text values, "canonical" is whichever casing
      appears most often in that group (ties broken by whichever appears
      first). For code-shaped values (see _looks_code_like) this vote is
      OVERRIDDEN with the uppercase form instead -- popularity within a
      single dataset is the wrong tie-break for something like an
      aircraft tail number or a SKU, which follows an external
      uppercase convention regardless of how it happens to be typed in
      this particular file. It also tends to be a near-coin-flip with
      the kind of small counts these groups usually have (2-3
      occurrences), where "most common" isn't a meaningful signal at all.

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

    # Override the vote for code-shaped groups -- see the docstring above
    # and _looks_code_like's docstring for why popularity is the wrong
    # rule here. norm is already the lowercased form, so norm.upper()
    # reconstructs the conventional casing directly without needing to
    # look at any specific row's value.
    for norm_key in canonical_map:
        if _looks_code_like(norm_key):
            canonical_map[norm_key] = norm_key.upper()

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


def _fix_numeric_formatted_as_text(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    log = []
    for col in df.select_dtypes(include="object").columns:
        non_null = df[col].dropna()
        if non_null.empty:
            continue
        stripped = non_null.astype(str).str.strip()
        matches = stripped.str.match(NUMERIC_TEXT_PATTERN)
        if matches.mean() < NUMERIC_FORMAT_MATCH_RATIO:
            continue

        parsed = df[col].apply(_parse_numeric_text)
        # Only commit the conversion if it didn't introduce any NEW
        # missing values -- if a value that matched the regex somehow
        # still failed to parse (shouldn't happen, but belt-and-suspenders),
        # leave the column as text rather than silently turning a real
        # value into NaN.
        if parsed.isna().sum() > df[col].isna().sum():
            continue

        count = int(non_null.shape[0])
        df[col] = parsed
        log.append(f'Converted "{col}" from formatted text to numbers ({count} values)')
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