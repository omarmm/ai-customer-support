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


class LLMProviderRateLimitError(LLMProviderHTTPError):
    """Raised when the provider throttles the request."""


class LLMProviderAuthenticationError(LLMProviderHTTPError):
    """Raised when the provider rejects credentials."""


class LLMProviderInvalidRequestError(LLMProviderHTTPError):
    """Raised when the provider rejects the request as invalid."""


class LLMProviderModelNotFoundError(LLMProviderHTTPError):
    """Raised when the provider reports the requested model as unknown."""


class LLMProviderUnavailableError(LLMProviderHTTPError):
    """Raised when the provider reports a transient server-side fault."""


class LLMProviderResponseError(LLMProviderError):
    """Raised when the provider response is invalid."""