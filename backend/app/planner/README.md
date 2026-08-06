# planner/

## What this module does

Takes the user's plain-English question plus a dataset profile (from
`profiling/`), sends both to Gemini, and gets back a structured
**AnalysisPlan** — a JSON object naming exactly one operation to run and
the parameters for it (e.g. "group by department, average salary, sort
descending").

The LLM's only job here is to *choose* an operation and fill in
parameters. It never computes anything itself. The actual math happens
later, in the analysis engine, using plain Python/Pandas.

## Why this exists (the problem it solves)

This replaces the old v1 approach where the LLM wrote raw SQL and the
backend just executed whatever it produced. That worked, but:

- Correctness depended entirely on the LLM writing valid, correct SQL
  every time.
- There was no way to guarantee the LLM's output was safe or well-formed
  before running it against data.
- It didn't really demonstrate backend/data engineering skill — it was
  mostly prompt engineering wrapped around SQL execution.

The planner constrains the LLM to a fixed, closed set of operations
(defined in `schemas.py`) with strict parameter schemas. If the LLM's
output doesn't match one of these shapes exactly, it's rejected before
it ever reaches real data. This is what makes the architecture
"deterministic" — the LLM chooses, Python computes.

## Files

| File | Responsibility |
|---|---|
| `schemas.py` | Defines what a *valid* plan looks like: the `Operation` enum, `ChartType` enum, per-operation parameter models (e.g. `GroupByAggParams`), and the top-level `AnalysisPlan` model. This is the single source of truth for "what the LLM is allowed to return." |
| `prompt.py` | Builds the actual text prompt sent to Gemini — explains the available operations, the chart types, and formats the dataset profile into something readable. Does not call any API itself. |
| `service.py` | The only file that actually talks to Gemini. Sends the prompt, gets back a plan, validates it against `schemas.py`, and raises a clear error if something's wrong. This is the function everything else (the API route) should call — nothing outside this file should construct a plan directly. |

## Flow through these three files

```
user_question + dataset_profile
        │
        ▼
prompt.py: build_planner_prompt()  →  prompt string
        │
        ▼
service.py: _call_planner_llm()    →  calls Gemini with schemas.AnalysisPlan
        │                              as response_schema (structured output)
        ▼
service.py: get_validated_plan()   →  checks operation is supported,
        │                              validates params against schemas.py
        ▼
   (plan, validated_params)        →  handed to the analysis engine
```

## Public function

### `get_validated_plan(user_question: str, dataset_profile: dict) -> tuple[AnalysisPlan, BaseModel]`

Defined in `service.py`. This is the only entry point other code should
use. It:

1. Builds the prompt (via `prompt.py`)
2. Calls Gemini with `schemas.AnalysisPlan` as the structured output schema
3. Checks the returned operation is one we actually support
4. Validates the returned params against that operation's specific param
   model
5. Returns `(plan, validated_params)` on success

Raises:

- `UnsupportedOperationError` — the LLM picked an operation that exists
  in the `Operation` enum but doesn't have a param model / backend
  implementation yet.
- `InvalidPlanError` — the LLM picked a supported operation, but the
  params it filled in don't pass validation (missing field, wrong type,
  invalid literal value, etc).

Both are meant to be caught by the API route and turned into a friendly
message — never shown raw to the user.

## Design decisions worth knowing

- **One operation per plan, no chaining (for now).** Multi-step plans
  (e.g. "top 5 departments, then their headcount trend") are intentionally
  out of scope until single-step is solid. `AnalysisPlan.operation` is
  singular, not a list.
- **The prompt only describes operations that have a param model.**
  `schemas.py`'s `Operation` enum currently lists 9 possible operations,
  but `prompt.py` only tells Gemini about the ones with a matching entry
  in `OPERATION_PARAM_MODELS` (currently just `groupby_agg`). This keeps
  the LLM from picking operations the backend can't actually run yet.
  When a new operation is built, both `schemas.py` (param model) and
  `prompt.py` (description) need updating together.
- **`clarification_needed` is a first-class way to bail.** If a question
  is ambiguous, the planner is instructed to ask a clarifying question
  rather than guess at column names. This avoids silently answering the
  wrong question.
- **Structured output, not manual JSON parsing.** `service.py` passes the
  `AnalysisPlan` Pydantic model directly to Gemini as `response_schema`.
  Gemini enforces that shape during generation, so there's no
  markdown-fence-stripping or "the model added a preamble" JSON parsing
  hacks.

## What this module does NOT do

- Does not execute any analysis (that's `analysis/`).
- Does not generate charts (that's `charts/`).
- Does not explain results in plain English (that's the separate
  explainer service, LLM call #2 in the pipeline).
- Does not read files or dataframes directly — it only receives an
  already-built `dataset_profile` dict from `profiling/`.

## Status

`schemas.py`, `prompt.py`, and `service.py` are all written and use a real
Gemini call (`google-genai` SDK). Only `groupby_agg` has a param model, so
it's currently the only operation the planner can successfully return.
Not yet tested end-to-end against a real dataset profile, and not yet
wired into the `/ask` API route.
