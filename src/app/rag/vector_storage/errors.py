"""Stable application-owned error taxonomy for vector storage.

SDK and transport exceptions are intentionally not imported here. The Qdrant
adapter (a later task) will normalize those exceptions into these errors.
"""

from __future__ import annotations


class VectorStoreError(Exception):
    """Base error with a stable application code and retryability flag."""

    code = "VECTOR_STORE_SERVICE_ERROR"
    category = "service"
    retryable = False

    def __init__(
        self,
        message: str | None = None,
        *,
        cause: Exception | None = None,
    ) -> None:
        self.cause = cause
        if cause is not None:
            self.__cause__ = cause
        super().__init__(message or self.code)


class VectorStoreUnavailable(VectorStoreError):
    code = "VECTOR_STORE_UNAVAILABLE"
    category = "connection"
    retryable = True


class VectorStoreTimeout(VectorStoreError):
    code = "VECTOR_STORE_TIMEOUT"
    category = "timeout"
    retryable = True


class VectorStoreServiceError(VectorStoreError):
    code = "VECTOR_STORE_SERVICE_ERROR"
    category = "service"
    retryable = False


class VectorStoreTransientServiceError(VectorStoreServiceError):
    """HTTP 5xx/service failure; eligible for bounded retry."""

    retryable = True


class VectorStoreInvalidData(VectorStoreError):
    code = "VECTOR_STORE_INVALID_DATA"
    category = "invalid_data"


class VectorStoreConfigurationError(VectorStoreError):
    code = "VECTOR_STORE_CONFIGURATION_ERROR"
    category = "configuration"


class VectorGenerationBuildFailed(VectorStoreError):
    code = "VECTOR_GENERATION_BUILD_FAILED"
    category = "generation_build"

    def __init__(
        self,
        message: str | None = None,
        *,
        cause: VectorStoreError | None = None,
    ) -> None:
        self.underlying_error = cause
        self.retryable = bool(cause and cause.retryable)
        super().__init__(message, cause=cause)


class VectorGenerationActivationFailed(VectorStoreError):
    code = "VECTOR_GENERATION_ACTIVATION_FAILED"
    category = "generation_activation"

    def __init__(
        self,
        message: str | None = None,
        *,
        cause: VectorStoreError | None = None,
    ) -> None:
        self.underlying_error = cause
        self.retryable = bool(cause and cause.retryable)
        super().__init__(message, cause=cause)


class VectorGenerationActiveDeleteRejected(VectorStoreError):
    code = "VECTOR_GENERATION_ACTIVE_DELETE_REJECTED"
    category = "active_generation_delete"


class VectorGenerationNotFound(VectorStoreError):
    code = "VECTOR_GENERATION_NOT_FOUND"
    category = "generation_not_found"
