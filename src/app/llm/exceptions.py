class LLMError(Exception):
    """Base class for all known LLM Service errors.

    Raised directly for provider failures that cannot be classified more
    specifically.
    """

    category = "unclassified"
    retryable = False
    retry_count = 0


class LLMConnectionError(LLMError):
    """Raised when the provider cannot be reached."""

    category = "connection"
    retryable = True


class LLMTimeoutError(LLMError):
    """Raised when a provider attempt exceeds the configured timeout."""

    category = "timeout"
    retryable = True


class LLMRateLimitError(LLMError):
    """Raised when the provider throttles the request."""

    category = "rate_limit"
    retryable = True


class LLMUnavailableError(LLMError):
    """Raised when the provider reports a transient server-side fault."""

    category = "unavailable"
    retryable = True


class LLMAuthenticationError(LLMError):
    """Raised when credentials are missing or rejected."""

    category = "authentication"
    retryable = False


class LLMInvalidRequestError(LLMError):
    """Raised when a request is malformed or rejected by the provider."""

    category = "invalid_request"
    retryable = False


class LLMModelNotFoundError(LLMError):
    """Raised when the provider explicitly reports an unknown model."""

    category = "model_not_found"
    retryable = False


class LLMResponseError(LLMError):
    """Raised when a provider response cannot be parsed or is malformed."""

    category = "response"
    retryable = False


class LLMConfigurationError(LLMError):
    """Raised when provider/model configuration is missing or invalid."""

    category = "configuration"
    retryable = False


class LLMUnexpectedError(LLMError):
    """Raised when an unexpected internal exception occurs.

    Not a known provider failure. The original exception is preserved as the
    cause when the boundary wraps it.
    """

    category = "unexpected"
    retryable = False
