# app/llm_errors.py
#
# Shared exception types for any Gemini API call failure, used by both
# planner/service.py and explainer/service.py (the two places that
# actually call Gemini). Kept in a neutral, shared module rather than
# defined in either service and imported by the other -- that would
# create a confusing dependency between two modules that otherwise
# don't need to know about each other.

class LLMRateLimitError(Exception):
    """Raised when Gemini returns a 429 -- free-tier quota hit."""
    pass


class LLMServiceError(Exception):
    """Raised for any other Gemini API failure (non-429 ClientError)."""
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)