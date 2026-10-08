class LLMProviderError(Exception):
    """Base exception for LLM provider failures."""


class LLMProviderConnectionError(LLMProviderError):
    """Raised when the provider cannot be reached."""


class LLMProviderTimeoutError(LLMProviderError):
    """Raised when the provider request times out."""


class LLMProviderHTTPError(LLMProviderError):
    """Raised when the provider returns an HTTP error."""

    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"LLM provider returned HTTP {status_code}")


class LLMProviderResponseError(LLMProviderError):
    """Raised when the provider response is invalid."""