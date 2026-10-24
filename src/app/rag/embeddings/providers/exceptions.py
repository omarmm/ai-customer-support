"""Provider-level error taxonomy for knowledge document embeddings.

The Ollama adapter raises only these exceptions. Raw ``httpx`` exceptions and
provider response bodies never escape the adapter. Messages carry status codes
and stable reason codes only; request bodies and credentials are never
included.
"""

from __future__ import annotations


class EmbeddingProviderError(Exception):
    """Base class for embedding provider failures."""


class EmbeddingProviderConnectionError(EmbeddingProviderError):
    """Raised when the provider cannot be reached."""


class EmbeddingProviderTimeoutError(EmbeddingProviderError):
    """Raised when a provider attempt exceeds its timeout."""


class EmbeddingProviderHTTPError(EmbeddingProviderError):
    """Raised when the provider returns an HTTP error."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"embedding provider returned HTTP {status_code}")


class EmbeddingProviderRateLimitError(EmbeddingProviderHTTPError):
    """Raised when the provider throttles the request."""


class EmbeddingProviderAuthenticationError(EmbeddingProviderHTTPError):
    """Raised when the provider rejects credentials."""


class EmbeddingProviderInvalidRequestError(EmbeddingProviderHTTPError):
    """Raised when the provider rejects the request as invalid."""


class EmbeddingProviderModelNotFoundError(EmbeddingProviderHTTPError):
    """Raised when the provider reports the requested model as unknown."""


class EmbeddingProviderUnavailableError(EmbeddingProviderHTTPError):
    """Raised when the provider reports a transient server-side fault."""


class EmbeddingProviderResponseError(EmbeddingProviderError):
    """Raised when the provider response is invalid.

    ``reason`` is a stable provider-side reason code such as ``invalid_json``,
    ``malformed_response``, or ``missing_embeddings``.
    """

    def __init__(self, reason: str) -> None:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        self.reason = reason
        super().__init__(f"embedding provider response error: {reason}")


class EmbeddingProviderModelMismatchError(EmbeddingProviderError):
    """Raised when the response model is missing, invalid, or mismatched."""

    def __init__(
        self,
        message: str = "embedding provider model identity mismatch",
    ) -> None:
        super().__init__(message)
