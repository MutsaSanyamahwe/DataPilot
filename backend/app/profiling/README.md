# profiling/

## What this module does

Takes a raw pandas dataframe (the user's uploaded CSV/Excel data) and turns
it into a compact, JSON-safe summary: column names, data types, a handful
of example values per column, and basic stats (min/max/mean) for numeric
columns.

This summary is called the **dataset profile**. It's the only thing the
planner LLM ever sees about the user's actual data — never the raw rows.

## Why this exists (the problem it solves)

The planner (see `planner/README.md`) needs to know what columns exist and
roughly what kind of data lives in them, in order to pick a sensible
operation and fill in correct column names. But sending it the full dataset
would be:

- **Expensive** — Hundreds of rows per question adds up fast for no real benefit.
- **Unnecessary** — the LLM doesn't need to *see* the data to decide
  "group by department, average salary." It needs to know the columns
  exist, what type they are, and roughly what's in them.
- **Slower** — bigger prompts take longer to generate a response for.

So this module exists as a deliberate compression step between "raw
dataframe" and "what the LLM is allowed to see."

## Files

| File | Responsibility |
|---|---|
| `profiler.py` | Contains `profile_dataset(df)` — the one public function. Everything else in the file is a private helper. |

## Public function

### `profile_dataset(df: pd.DataFrame, max_sample_values: int = 5) -> dict`

Input: a pandas dataframe.

Output: a dict shaped like this —

```python
{
    "row_count": 1200,
    "columns": [
        {
            "name": "department",
            "dtype": "string",
            "sample_values": ["Sales", "Engineering", "Marketing"]
        },
        {
            "name": "salary",
            "dtype": "float",
            "sample_values": [65000.0, 82000.0, 71000.0],
            "min": 42000.0,
            "max": 145000.0,
            "mean": 78500.0
        }
    ]
}
```

Notes on behavior:

- `dtype` is simplified to one of: `integer`, `float`, `datetime`,
  `boolean`, `string` — not pandas' internal dtype names. Keeps the
  planner prompt simple and consistent.
- `min` / `max` / `mean` are only included for `integer` and `float`
  columns. They give the LLM a sanity check — e.g. a column with
  `min=10001, max=99999, mean=54321` and `dtype=integer` looks like a zip
  code, not something worth averaging, even though technically it's
  numeric.
- Values are cleaned before being returned: numpy scalar types (like
  `numpy.int64`) are converted to plain Python types, and `NaN` becomes
  `None`, because both would break JSON serialization otherwise.
- `sample_values` are a few distinct, non-null example values — enough
  for the LLM to see "this column contains department names" rather than
  just "this column is a string."

## Where this fits in the pipeline

```
Upload → Validation → Cleaning → Type Inference → [ profile_dataset() ] → Planner
```

This module runs once per question, right before the planner prompt is
built. It does not modify the dataframe — it only reads and summarizes it.

## What this module does NOT do

- Does not validate or clean the data (see `cleaning/`, once built).
- Does not decide what analysis to run — that's the planner's job.
- Does not talk to any LLM.
- Does not persist anything to disk or a database.

