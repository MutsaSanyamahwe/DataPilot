# app/suggestions/prompt.py
#
# Builds the prompt for the one-shot "polish" LLM call in
# suggestions/service.py. This call ONLY rewrites phrasing -- it never
# picks an operation or a column, those are already locked in by
# generator.py's deterministic templates before this prompt is ever built.
# Keeping the prompt narrow (just column names and row count, not full
# dtypes/sample values like planner/prompt.py sends) is deliberate: this
# call doesn't need to reason about the dataset, just have enough context
# to rephrase naturally without inventing an unrelated column name.

from app.suggestions.generator import _humanize

# Cap how many column names get listed in the prompt -- a 200-column
# dataset (the validator's own upper bound, see validation/validator.py)
# would bloat this prompt for no benefit; the LLM only needs a general
# sense of the dataset's vocabulary, not an exhaustive list.
MAX_COLUMNS_IN_PROMPT = 40


def build_polish_prompt(candidates: list[dict], row_count: int, column_names: list[str]) -> str:
    numbered = "\n".join(
        f"{i + 1}. {c['question']}  (operation: {c['operation']})"
        for i, c in enumerate(candidates)
    )

    # IMPORTANT: humanized here too, same as generator.py does for the
    # questions themselves ("hire_date" -> "hire date"). This list used to
    # be sent with raw column names -- the model would then "correct"
    # phrasing in the input questions back to the raw/technical name
    # (e.g. "network manager" -> "Network_Manager") because that's what it
    # saw listed as the "real" column here. Humanizing this list too closes
    # that loophole -- there's no raw name anywhere in the prompt for the
    # model to fall back to.
    shown_columns = [_humanize(c) for c in column_names[:MAX_COLUMNS_IN_PROMPT]]
    columns_line = ", ".join(shown_columns)
    if len(column_names) > MAX_COLUMNS_IN_PROMPT:
        columns_line += f", and {len(column_names) - MAX_COLUMNS_IN_PROMPT} more"

    return f"""
You are rewriting a list of pre-approved starter questions for a chat tool
that answers questions about an uploaded dataset. Someone is about to see
these as tappable suggestion chips before they've asked anything -- this
is their first impression of what the tool can do, so it needs to read
like something a real person would actually type, not a database query.

Dataset context:
- {row_count} rows
- Columns (already written the way they should appear in a question):
  {columns_line}

Questions to rewrite ({len(candidates)} total):
{numbered}

Rewrite each question so it sounds casual and direct -- the way someone
would type it into a chat box, not the way a report would describe it.

STRICT RULES:
- Return exactly {len(candidates)} rewritten questions, in the SAME ORDER
  as the list above -- one rewritten question per input question. Never
  add, remove, merge, split, or reorder questions.
- Each rewritten question must ask for the EXACT SAME thing as its
  corresponding input question -- same operation, same column(s), same
  specific value(s) if any are named. You are only changing the words,
  never the meaning or the target of the question.
- Column and value names in the input questions are ALREADY written the
  way they should read -- e.g. "hire date", not "hire_date". Keep them
  exactly as given. Never swap a name back to an underscored, all-caps,
  or otherwise "technical-looking" form, even if you think that's the
  literal column name -- it isn't, it's already been formatted for you.
- Never introduce a column name that isn't listed above.
- Never turn a question into a "why"/causal question, and never add any
  request for reasoning or explanation -- these must stay direct,
  answerable questions about the data itself, not about causes.
- Keep each question roughly the same length as the original -- short,
  one sentence, no preamble.
- Do not add commentary, numbering, or quotation marks around your answers.
"""