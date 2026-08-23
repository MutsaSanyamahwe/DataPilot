# app/suggestions/generator.py
#
# Builds the "questions you might ask" starter chips shown when the chat
# screen first loads for a dataset. Deliberately has NO LLM call in it --
# unlike the planner/explainer, these suggestions need to be instant (they
# render before the user has asked anything) and, more importantly, they
# need to be GUARANTEED answerable. A hallucinated suggestion that fails
# on the very first tap would be a worse first impression than no
# suggestions at all, so this only ever proposes a question if it has
# already confirmed (in plain pandas) that a column of the right shape
# exists for that operation.
#
# One candidate question is built per Operation (planner/schemas.py) that
# the dataset actually supports, then the best `max_questions` of those
# are returned. "Supports" is judged with the same simple heuristics the
# planner prompt already teaches the LLM (numeric dtype for aggregation,
# a date-looking column for trend/date_range_filter, etc.) so a chip
# clicked by the user should reliably hit the same operation, not bounce
# into a clarification_needed round-trip.
#
# PHRASING RULES (this is the part that's easy to get wrong):
#   - These should read like the LLM-written follow_up_questions chips
#     that appear under an answer (see explainer/schemas.py -- "phrased
#     the way a user would actually type them"), NOT like a description
#     of which operation/columns get used. A user who has never seen this
#     dataset's raw column names should still understand the question.
#   - Column names get humanized (_humanize() below) before going into a
#     question -- "hire_date" becomes "hire date", "TENURE_YEARS" becomes
#     "tenure years". The planner still gets the real column names via
#     the dataset profile and matches semantically, so this is purely a
#     display-time readability fix, not a behavior change.
#   - No internal/operation jargon in the question text itself -- e.g.
#     "pivot" and "distribution" are operation names, not words a person
#     asks with. Phrase those as plain breakdowns/comparisons instead.
#   - Never a "why"/causal question. Those need a *reason*, and this
#     dataset can only show what happened, not why -- the planner would
#     have to answer with needs_causal_disclaimer, which is confusing to
#     hit from a suggestion chip that's supposed to be a safe, direct
#     answer. _is_causal_phrasing() below is a defensive filter for this,
#     even though none of the templates below should ever produce one.

import re
import pandas as pd
from dataclasses import dataclass

from app.config import settings
from app.planner.schemas import Operation

# A categorical column needs at least this many distinct values to be
# worth grouping/distinguishing by, and no more than this many, or a
# breakdown-style question would return an unreadable wall of categories
# (same spirit as charts/builder.py's MAX_PIE_SLICES, just a looser bound
# since these are table/bar-friendly, not pie-only).
MIN_CATEGORY_VALUES = 2
MAX_CATEGORY_VALUES = 50

# If a column's cardinality equals (or nearly equals) the row count, it's
# almost certainly an identifier/primary-key-style column (e.g. "id",
# "order_number", a UUID) -- technically it fits the "categorical" or
# "numeric" bucket by dtype, but grouping or correlating by a unique-per-row
# ID is never a useful suggested question.
ID_LIKE_UNIQUE_RATIO = 0.98

# Some numeric-dtype columns are never meaningful QUANTITIES no matter
# their cardinality -- a zip code column commonly repeats a lot (many
# rows share a zip), so it fails the ID_LIKE_UNIQUE_RATIO check above and
# would otherwise land in `numeric`, producing nonsense like "what's the
# average zip code" or "top rows by zip code". These are caught by name
# instead of by value distribution, since there's no statistical
# signature that reliably distinguishes "5-digit code" from "5-digit
# quantity" -- the column's *name* is the only real signal available.
# Matched as whole tokens after splitting on underscore/space/hyphen, so
# "phone_number" matches on "phone" but "number_of_students" doesn't
# match at all (deliberately no bare "number"/"code" token that would
# also catch legitimate counts).
CODE_LIKE_NAME_TOKENS = {
    "id", "zip", "zipcode", "postal", "postcode", "ssn", "fips", "ein",
    "npi", "phone", "fax", "sku", "isbn", "upc", "barcode", "routing",
    "vin", "plate", "pin",
}


def _is_code_like_name(column_name: str) -> bool:
    tokens = re.split(r"[_\s\-]+", str(column_name).strip().lower())
    return any(tok in CODE_LIKE_NAME_TOKENS for tok in tokens)

# A string column counts as date-like if at least this fraction of its
# non-null sample values parse as real dates. Matches the same "look at
# the actual values, not just the dtype" approach the planner prompt uses,
# since pandas frequently loads date columns as plain strings.
DATE_PARSE_SUCCESS_RATIO = 0.8

_CAUSAL_WORDS = re.compile(r"\bwhy\b|\bcause[sd]?\b|\breason[s]?\b", re.IGNORECASE)


@dataclass
class SuggestedQuestion:
    question: str
    operation: str  # Operation enum value, so the frontend/analytics can group by it


def _humanize(column_name: str) -> str:
    """
    Turns a raw column name into something that reads naturally inside a
    sentence -- "hire_date" -> "hire date", "TENURE-YEARS" -> "tenure
    years". Purely cosmetic: the planner still receives (and matches
    against) the real column name via the dataset profile, so this can't
    cause a mismatch, only make the suggested question easier to read.
    """
    s = str(column_name).replace("_", " ").replace("-", " ")
    s = " ".join(s.split())  # collapse repeated whitespace
    return s.lower()


def _humanize_value(value) -> str:
    """Same idea as _humanize(), but for an actual data value rather than
    a column name -- mainly matters for booleans, so a filter suggestion
    reads 'is true' instead of the Python-esque 'is True'."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _is_id_like(series: pd.Series, n_rows: int) -> bool:
    if n_rows <= 1:
        return False
    n_unique = series.nunique(dropna=True)
    return n_unique >= n_rows * ID_LIKE_UNIQUE_RATIO


def _looks_like_dates(series: pd.Series) -> bool:
    sample = series.dropna()
    if len(sample) == 0:
        return False
    sample = sample.head(50)
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    success_ratio = parsed.notna().mean()
    return success_ratio >= DATE_PARSE_SUCCESS_RATIO


def _classify_columns(df: pd.DataFrame) -> dict:
    n_rows = len(df)
    categorical, numeric, date = [], [], []

    for col in df.columns:
        series = df[col]

        if pd.api.types.is_datetime64_any_dtype(series):
            date.append(col)
            continue

        if pd.api.types.is_bool_dtype(series):
            categorical.append(col)
            continue

        if pd.api.types.is_numeric_dtype(series):
            if _is_id_like(series, n_rows):
                continue  # near-unique-per-row -- a primary key, not useful at all here

            if _is_code_like_name(col):
                # Numeric dtype, but the name says this is an identifier/
                # code (zip, phone, SKU...) rather than a quantity -- never
                # suggest averaging/summing/correlating it, but it can
                # still be a reasonable thing to filter or group by if it
                # doesn't have too many distinct values.
                n_unique = series.nunique(dropna=True)
                if MIN_CATEGORY_VALUES <= n_unique <= MAX_CATEGORY_VALUES:
                    categorical.append(col)
                continue

            numeric.append(col)
            continue

        # Everything else is string/object -- could be categorical or a
        # date stored as text (very common straight out of CSV exports).
        if _looks_like_dates(series):
            date.append(col)
            continue

        n_unique = series.nunique(dropna=True)
        if MIN_CATEGORY_VALUES <= n_unique <= MAX_CATEGORY_VALUES and not _is_id_like(series, n_rows):
            categorical.append(col)

    return {"categorical": categorical, "numeric": numeric, "date": date}


def _sample_value(df: pd.DataFrame, column: str):
    non_null = df[column].dropna()
    if non_null.empty:
        return None
    return non_null.iloc[0]


def _two_sample_values(df: pd.DataFrame, column: str) -> tuple | None:
    values = df[column].dropna().unique()
    if len(values) < 2:
        return None
    return values[0], values[1]


def generate_suggested_questions(
    df: pd.DataFrame,
    max_questions: int | None = None,
) -> list[SuggestedQuestion]:
    """
    Returns up to `max_questions` starter questions for this dataset,
    covering as many distinct supported operations as the data's actual
    columns allow. Always includes describe/sample first (safe, always
    answerable orientation questions), then fills in with whichever
    operations this specific dataset's column types support.

    Never raises -- worst case (e.g. a one-column dataset) it just
    returns a shorter list; the chat screen should handle an empty or
    short list gracefully rather than assume a fixed count.
    """
    if max_questions is None:
        max_questions = settings.suggested_questions_count

    cols = _classify_columns(df)
    categorical, numeric, date = cols["categorical"], cols["numeric"], cols["date"]

    candidates: list[SuggestedQuestion] = []

    # --- Always-applicable orientation questions ---
    candidates.append(SuggestedQuestion(
        "Give me an overview of this dataset", Operation.DESCRIBE.value,
    ))
    candidates.append(SuggestedQuestion(
        "Are there any duplicate rows in this dataset?", Operation.DUPLICATE_ROWS.value,
    ))

    # --- top_n ---
    if numeric:
        candidates.append(SuggestedQuestion(
            f"Show me the rows with the highest {_humanize(numeric[0])}", Operation.TOP_N.value,
        ))
    else:
        candidates.append(SuggestedQuestion(
            "Show me the first 10 rows", Operation.TOP_N.value,
        ))

    # --- sample ---
    candidates.append(SuggestedQuestion(
        "Give me a random sample of the data", Operation.SAMPLE.value,
    ))

    # --- distinct ---
    if categorical:
        candidates.append(SuggestedQuestion(
            f"What are the different values for {_humanize(categorical[0])}?", Operation.DISTINCT.value,
        ))

    # --- distribution (prefer a different column than distinct used, if there is one) ---
    if categorical:
        dist_col = categorical[1] if len(categorical) > 1 else categorical[0]
        candidates.append(SuggestedQuestion(
            f"Give me a breakdown by {_humanize(dist_col)}", Operation.DISTRIBUTION.value,
        ))

    # --- filter ---
    if categorical:
        sample_val = _sample_value(df, categorical[0])
        if sample_val is not None:
            candidates.append(SuggestedQuestion(
                f"Show me rows where {_humanize(categorical[0])} is {_humanize_value(sample_val)}",
                Operation.FILTER.value,
            ))
    elif numeric:
        candidates.append(SuggestedQuestion(
            f"Show me rows where {_humanize(numeric[0])} is above average", Operation.FILTER.value,
        ))

    # --- groupby_agg ---
    if categorical and numeric:
        candidates.append(SuggestedQuestion(
            f"What's the average {_humanize(numeric[0])} by {_humanize(categorical[0])}?",
            Operation.GROUPBY_AGG.value,
        ))

    # --- trend ---
    if date:
        if numeric:
            candidates.append(SuggestedQuestion(
                f"How has {_humanize(numeric[0])} changed over time?", Operation.TREND.value,
            ))
        else:
            candidates.append(SuggestedQuestion(
                "How many records were there each month?", Operation.TREND.value,
            ))

    # --- date_range_filter ---
    # Deliberately doesn't name the date column -- "show me records from
    # the past year" reads naturally, and the planner already resolves
    # relative date phrases against whichever date column exists (see
    # planner/prompt.py) without needing it spelled out here.
    if date:
        candidates.append(SuggestedQuestion(
            "Show me records from the past year", Operation.DATE_RANGE_FILTER.value,
        ))

    # --- correlation ---
    if len(numeric) >= 2:
        candidates.append(SuggestedQuestion(
            f"Is there a correlation between {_humanize(numeric[0])} and {_humanize(numeric[1])}?",
            Operation.CORRELATION.value,
        ))

    # --- outlier_detection ---
    if numeric:
        candidates.append(SuggestedQuestion(
            f"Are there any unusually high or low values in {_humanize(numeric[0])}?",
            Operation.OUTLIER_DETECTION.value,
        ))

    # --- comparison ---
    if categorical:
        pair = None
        for c in categorical:
            pair = _two_sample_values(df, c)
            if pair is not None:
                break
        if pair is not None:
            group_a, group_b = _humanize_value(pair[0]), _humanize_value(pair[1])
            if numeric:
                candidates.append(SuggestedQuestion(
                    f"How does {_humanize(numeric[0])} compare between {group_a} and {group_b}?",
                    Operation.COMPARISON.value,
                ))
            else:
                candidates.append(SuggestedQuestion(
                    f"How does the number of records compare between {group_a} and {group_b}?",
                    Operation.COMPARISON.value,
                ))

    # --- pivot ---
    # "pivot" is an operation name, not something a person asks for --
    # phrase it as a plain side-by-side breakdown instead.
    if len(categorical) >= 2:
        if numeric:
            candidates.append(SuggestedQuestion(
                f"Show me {_humanize(numeric[0])} broken down by "
                f"{_humanize(categorical[0])} and {_humanize(categorical[1])} together",
                Operation.PIVOT.value,
            ))
        else:
            candidates.append(SuggestedQuestion(
                f"Show me how {_humanize(categorical[0])} and {_humanize(categorical[1])} relate to each other",
                Operation.PIVOT.value,
            ))

    # Defensive filter: none of the templates above should ever produce a
    # causal/"why" question (those need a *reason*, which this dataset
    # can't give -- see needs_causal_disclaimer in planner/schemas.py),
    # but if a future template slips one in, drop it here rather than
    # ship a suggestion that reads more like a request for an explanation
    # than a direct, answerable question.
    candidates = [c for c in candidates if not _CAUSAL_WORDS.search(c.question)]

    return candidates[:max_questions]