# cleaning/

## What this module does

Detects common data-quality issues in a dataframe that already passed
validation — inconsistent null-like values (`"N/A"`, `"n/a"`, `"-"`,
etc.), stray leading/trailing whitespace, and fully duplicate rows — and
reports them. It can also apply fixes for everything it detects, but
only when explicitly asked to.

This module never decides on its own whether to modify the user's data.
Detection and fixing are two separate functions, and the decision to
apply fixes belongs to the user, not this module.

## Why this exists (the problem it solves)

Real uploaded spreadsheets are messy in predictable ways: someone typed
`"N/A"` in one row and left another blank, values have accidental
trailing spaces from copy-pasting, rows get duplicated during exports.
None of that is bad enough to reject the file (that's `validation/`'s
job), but left as-is it silently produces wrong-looking analysis — e.g.
`groupby_agg` treating `"Engineering"` and `" Engineering"` as two
different departments.

Rather than silently "fixing" this (which erodes trust — the user should
know their data was touched) or always blocking on a decision (which
adds friction for what are usually boring, obvious fixes), this module
splits the two concerns:

- **Inspect** — always safe to run, always read-only, tells you what's
  wrong.
- **Apply** — only runs if the user opts in, and always returns a
  human-readable log of exactly what changed.

## Files

| File | Responsibility |
|---|---|
| `cleaner.py` | Contains `inspect_cleaning()`, `apply_cleaning()`, and the `Issue` / `CleaningReport` data shapes they use. |

## Public functions

### `inspect_cleaning(df: pd.DataFrame) -> CleaningReport`

Read-only. Detects issues without modifying `df`. Safe to call on every
upload, before the user has made any choice.

`CleaningReport` looks like:

```python
CleaningReport(
    issues=[
        Issue(kind="inconsistent_nulls", column="department", count=1,
              description='1 inconsistent blank/null-like values in "department" ...'),
        Issue(kind="whitespace", column="department", count=2,
              description='2 values in "department" have extra leading/trailing whitespace'),
        Issue(kind="duplicate_rows", column=None, count=1,
              description="1 fully duplicate rows found"),
    ]
)
```

`report.has_issues` — quick boolean check. `report.summary()` — a
one-line, semicolon-joined summary string, handy for a quick UI message.

### `apply_cleaning(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]`

Only call this if the user opted in to cleaning. Applies fixes for every
issue category `inspect_cleaning()` would report:

- Standardizes null-like strings to real missing values.
- Trims whitespace.
- Drops fully duplicate rows.

Returns `(cleaned_df, change_log)` — `change_log` is a list of
human-readable strings describing exactly what changed, e.g.
`'Trimmed whitespace on 2 values in "department"'`. Meant to be shown to
the user after the fact or logged, so nothing about the fix is a black
box.

## A real gotcha this module already caught

Early testing surfaced a genuine pandas bug in the first version of the
whitespace check: `Series.astype(str)` does **not** convert actual `NaN`
values to the string `"nan"` — it leaves them as float `NaN`. Since
`NaN != NaN` is always `True` in pandas, every genuinely-missing cell was
being falsely flagged as "has whitespace." Fixed by explicitly excluding
null values (`.notna()`) before comparing. Worth knowing about if this
file's detection logic is extended later — any string-comparison-based
check needs to account for this.

## Where this fits in the pipeline

```
validation.validate_dataset(df)     ← hard gate, already passed
   → [ cleaning.inspect_cleaning(df) ]   ← this module — report only
   → user chooses: clean, or leave as-is
        → if clean: [ cleaning.apply_cleaning(df) ]   ← this module — actually fixes
   → profiling.profile_dataset(cleaned_or_original_df)
```

This naturally fits into the existing Inspect → Confirm screens in the
frontend — the cleaning report can be shown alongside the sheet picker,
with the "clean automatically" choice defaulted on but not forced.

## What this module deliberately does NOT do

- Does not reject files — that's `validation/`.
- Does not infer or fix column *types* (e.g. a numeric column read as
  text) — that's type inference, a separate stage.
- Does not decide whether to apply its own fixes — that decision is made
  by the API/frontend layer based on user input.
- Does not talk to any LLM.

## Status

Built and tested against deliberately messy data, including edge cases
around null handling. Three issue categories currently detected/fixed:
inconsistent nulls, whitespace, duplicate rows. More can be added later
(e.g. inconsistent casing, mixed date formats) following the same
inspect/apply split.
