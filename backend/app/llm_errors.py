# app/llm_errors.py
#
# Shared exception types + classification logic for any Gemini API call
# failure, used by every service.py that talks to Gemini (planner,
# explainer, suggestions). Centralized here rather than duplicated in
# each service file -- that duplication is exactly how a real bug ended
# up in three places at once: each service.py independently caught only
# `ClientError` (missing `ServerError` -- 5xx responses like "503
# UNAVAILABLE, high demand" -- entirely, so those crashed as an unhandled
# 500), AND each one read `e.status_code`, which isn't a real attribute
# on these exceptions at all (the actual one is `.code`) -- so even a
# real 429 rate-limit hit crashed with an AttributeError inside the
# except block instead of ever raising LLMRateLimitError as intended.
# Centralizing the classification logic here means that class of bug can
# now only exist in one place, and any new service.py automatically gets
# it right by using classify_and_raise() instead of writing its own.

from google.genai.errors import APIError
import httpx


class LLMRateLimitError(Exception):
    """Raised when Gemini returns a 429 -- a usage/quota limit was hit.
    Gemini doesn't reliably distinguish "too many requests per minute"
    from "today's free-tier quota is used up" in the error body itself,
    so the user-facing message (see app/ask.py) stays honest about that
    rather than guessing which one it was."""
    pass


class LLMOverloadedError(Exception):
    """Raised when Gemini returns a 5xx (e.g. "503 UNAVAILABLE... high
    demand") -- a transient, Google-side capacity issue, not something
    wrong with the request or with this app. Usually clears up within
    seconds to minutes on retry."""
    pass


class LLMServiceError(Exception):
    """Raised for anything else: a malformed request, an auth problem
    (bad/missing API key), an unexpected non-429/5xx response, or a
    network-level failure reaching Gemini at all (no internet, DNS
    failure, connection refused, timeout before any HTTP response came
    back)."""
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


def classify_and_raise(e: Exception) -> None:
    """
    Turns any exception raised by a genai.Client.models.generate_content()
    call into exactly one of this module's three exception types above.
    Every service.py's Gemini call should be wrapped as:

        try:
            response = _client.models.generate_content(...)
        except (APIError, httpx.RequestError) as e:
            classify_and_raise(e)

    Always raises -- never returns normally.
    """
    if isinstance(e, APIError):
        # NOTE: the real attribute is `.code`, NOT `.status_code` --
        # APIError never defines `.status_code`, so referencing it
        # raises AttributeError instead of ever comparing correctly.
        # See this module's docstring for how that bug hid for a while.
        code = getattr(e, "code", None)
        if code == 429:
            raise LLMRateLimitError() from e
        if code is not None and 500 <= code < 600:
            raise LLMOverloadedError() from e
        raise LLMServiceError(f"{code}: {getattr(e, 'message', str(e))}") from e

    if isinstance(e, httpx.RequestError):
        # Never got an HTTP response at all -- DNS failure, connection
        # refused, timed out before Gemini replied, etc.
        raise LLMServiceError(f"Could not reach the AI service: {e}") from e

    raise LLMServiceError(str(e)) from e