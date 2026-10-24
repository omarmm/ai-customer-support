"""Application-level error taxonomy for knowledge document embeddings.

Provider exceptions, raw HTTP exceptions, and HTTP-library exceptions are
normalized here by explicit provider exception type at the service boundary.
Messages carry stable identifiers, model names, status codes, reason codes, and
chunk IDs only. Chunk text, document text, full vectors, and secrets are never
included.
"""

from __future__ import annotations

from app.rag.embeddings.providers.exceptions import (
    EmbeddingProviderAuthenticationError,
    EmbeddingProviderConnectionError,
    EmbeddingProviderError,
    EmbeddingProviderHTTPError,
    EmbeddingProviderInvalidRequestError,
    EmbeddingProviderModelMismatchError,
    EmbeddingProviderModelNotFoundError,
    EmbeddingProviderRateLimitError,
    EmbeddingProviderResponseError,
    EmbeddingProviderTimeoutError,
    EmbeddingProviderUnavailableError,
)


class EmbeddingError(Exception):
    """Base class for embedding failures.

    Used directly for provider failures that cannot be classified more
    specifically.
    """

    category = "unclassified"
    retryable = False
    retry_count = 0


class EmbeddingConnectionError(EmbeddingError):
    """Raised when the provider cannot be reached."""

    category = "connection"
    retryable = True


class EmbeddingTimeoutError(EmbeddingError):
    """Raised when a provider attempt exceeds the configured timeout."""

    category = "timeout"
    retryable = True


class EmbeddingRateLimitError(EmbeddingError):
    """Raised when the provider throttles the request."""

    category = "rate_limit"
    retryable = True


class EmbeddingUnavailableError(EmbeddingError):
    """Raised when the provider reports a transient server-side fault."""

    category = "unavailable"
    retryable = True


class EmbeddingAuthenticationError(EmbeddingError):
    """Raised when credentials are missing or rejected."""

    category = "authentication"
    retryable = False


class EmbeddingInvalidRequestError(EmbeddingError):
    """Raised when a request is malformed or rejected by the provider."""

    category = "invalid_request"
    retryable = False


class EmbeddingModelNotFoundError(EmbeddingError):
    """Raised when the provider explicitly reports an unknown model."""

    category = "model_not_found"
    retryable = False


class EmbeddingModelMismatchError(EmbeddingError):
    """Raised when the served model identity differs from the approved one."""

    category = "model_mismatch"
    retryable = False

    def __init__(
        self,
        message: str = "embedding model identity mismatch",
    ) -> None:
        super().__init__(message)


class EmbeddingResponseError(EmbeddingError):
    """Raised when a provider response cannot be accepted.

    ``reason`` is one of the stable reason codes in §7.3 and is preserved when a
    provider response error is normalized.
    """

    category = "response"
    retryable = False

    def __init__(self, reason: str) -> None:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        self.reason = reason
        super().__init__(f"embedding response error: {reason}")


class EmbeddingConfigurationError(EmbeddingError):
    """Raised when provider/model wiring or configuration is invalid."""

    category = "configuration"
    retryable = False

    def __init__(
        self,
        message: str = "embedding configuration is invalid",
    ) -> None:
        super().__init__(message)


class EmbeddingUnexpectedError(EmbeddingError):
    """Raised when an unexpected internal exception occurs.

    Not a known provider failure. The original exception is preserved as the
    cause when the boundary wraps it.
    """

    category = "unexpected"
    retryable = False

    def __init__(
        self,
        message: str = "unexpected embedding failure",
    ) -> None:
        super().__init__(message)


def normalize_provider_error(error: EmbeddingProviderError) -> EmbeddingError:
    """Map a provider-layer exception to its application-layer counterpart.

    Mapping is by explicit provider exception type, ordered from most specific
    to most general. Raw HTTP status codes are never interpreted here; the
    Ollama adapter owns provider-specific status interpretation. The provider
    error is preserved as ``__cause__``.

    Unexpected non-provider exceptions are the service boundary's
    responsibility and map to ``EmbeddingUnexpectedError`` there.
    """
    if not isinstance(error, EmbeddingProviderError):
        raise TypeError("error must be an EmbeddingProviderError")

    if isinstance(error, EmbeddingProviderResponseError):
        mapped: EmbeddingError = EmbeddingResponseError(error.reason)
    elif isinstance(error, EmbeddingProviderModelMismatchError):
        mapped = EmbeddingModelMismatchError()
    elif isinstance(error, EmbeddingProviderRateLimitError):
        mapped = EmbeddingRateLimitError()
    elif isinstance(error, EmbeddingProviderAuthenticationError):
        mapped = EmbeddingAuthenticationError()
    elif isinstance(error, EmbeddingProviderInvalidRequestError):
        mapped = EmbeddingInvalidRequestError()
    elif isinstance(error, EmbeddingProviderModelNotFoundError):
        mapped = EmbeddingModelNotFoundError()
    elif isinstance(error, EmbeddingProviderUnavailableError):
        mapped = EmbeddingUnavailableError()
    elif isinstance(error, EmbeddingProviderHTTPError):
        mapped = EmbeddingError()
    elif isinstance(error, EmbeddingProviderConnectionError):
        mapped = EmbeddingConnectionError()
    elif isinstance(error, EmbeddingProviderTimeoutError):
        mapped = EmbeddingTimeoutError()
    else:
        mapped = EmbeddingError()

    mapped.__cause__ = error
    return mapped
