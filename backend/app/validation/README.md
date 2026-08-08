# validation/

## What this module does

Runs a set of hard pass/fail checks against a freshly-parsed dataframe,
right after a file is uploaded and parsed. If the file is fundamentally
unusable (empty, no columns, no real headers, entirely blank, duplicate
column names), it rejects the file immediately with a clear, user-facing
reason. If the file passes, it's structurally sound enough to move on to
cleaning.

## Why this exists (the problem it solves)

Every later stage in the pipeline (cleaning, profiling, the planner LLM,
the analysis engine) assumes it's working with a dataframe that has at
least some real structure — real column names, at least one row, no
duplicate columns to confuse a `groupby`. Without a hard gate up front,
a broken file wouldn't fail loudly and early — it would fail confusingly
later, deep inside profiling or analysis, with an error that doesn't
point back to "the actual problem is your file was empty."

This module exists to fail fast, fail clearly, and fail at the earliest
possible point — before any other module has to defensively guard
against garbage input.

## What this module deliberately does NOT do

- It does not judge data **quality** — messy-but-structurally-valid data
  (inconsistent nulls, stray whitespace, duplicate rows) is not this
  module's concern. That's `cleaning/`.
- It does not fix anything. Every check here either passes silently or
  raises. There is no auto-correction in this file.
- It does not talk to any LLM.

## Files

| File | Responsibility |
|---|---|
| `validator.py` | Contains `validate_dataset(df)` — the one public function — plus `ValidationError`, the exception it raises. |

## Public function

### `validate_dataset(df: pd.DataFrame) -> None`

Raises `ValidationError` on the first failing check. Returns `None`
(no return value, no exception) if the dataset passes all checks.

Current checks, run in this order:

1. **Not empty** — at least one data row.
2. **Has columns** — at least one column.
3. **No duplicate column names** — a `groupby` or column lookup on a
   dataset with two columns named the same thing is ambiguous and unsafe.
4. **Not entirely null** — every cell being blank means there's nothing
   to analyze.
5. **Has real headers** — if more than half the columns are unnamed
   (pandas' `"Unnamed: 0"` style auto-names), the file likely doesn't
   have a proper header row.

### `ValidationError`

```python
class ValidationError(Exception):
    def __init__(self, reason: str): ...
```

`reason` is safe to show directly to the user in an API error response —
it's already written as a plain-English, actionable message (e.g. "This
file has no data rows. Please upload a file with at least one row of
data.").

## Where this fits in the pipeline

```
Upload (parses file into df)
   → [ validate_dataset(df) ]   ← this module — hard reject or proceed
   → cleaning.inspect_cleaning(df)
   → profiling.profile_dataset(df)
   → planner.get_validated_plan(...)
```

The API route should call `validate_dataset(df)` immediately after
parsing an uploaded file, and catch `ValidationError` to return a 400
response with `reason` as the error message — before the file ever
reaches cleaning or profiling.

## Status

Built and tested against deliberately broken inputs. Five checks
currently implemented. More can be added later (e.g. file size limits,
column count ceilings) as real-world uploads surface new failure modes.
