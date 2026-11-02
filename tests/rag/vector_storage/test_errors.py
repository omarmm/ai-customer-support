import pytest

from app.rag.vector_storage.errors import (
    VectorGenerationActiveDeleteRejected,
    VectorGenerationActivationFailed,
    VectorGenerationBuildFailed,
    VectorGenerationNotFound,
    VectorStoreConfigurationError,
    VectorStoreError,
    VectorStoreInvalidData,
    VectorStoreServiceError,
    VectorStoreTimeout,
    VectorStoreTransientServiceError,
    VectorStoreUnavailable,
)


@pytest.mark.parametrize(
    ("error_type", "code", "retryable"),
    [
        (VectorStoreUnavailable, "VECTOR_STORE_UNAVAILABLE", True),
        (VectorStoreTimeout, "VECTOR_STORE_TIMEOUT", True),
        (VectorStoreServiceError, "VECTOR_STORE_SERVICE_ERROR", False),
        (VectorStoreTransientServiceError, "VECTOR_STORE_SERVICE_ERROR", True),
        (VectorStoreInvalidData, "VECTOR_STORE_INVALID_DATA", False),
        (VectorStoreConfigurationError, "VECTOR_STORE_CONFIGURATION_ERROR", False),
        (VectorGenerationBuildFailed, "VECTOR_GENERATION_BUILD_FAILED", False),
        (VectorGenerationActivationFailed, "VECTOR_GENERATION_ACTIVATION_FAILED", False),
        (VectorGenerationActiveDeleteRejected, "VECTOR_GENERATION_ACTIVE_DELETE_REJECTED", False),
        (VectorGenerationNotFound, "VECTOR_GENERATION_NOT_FOUND", False),
    ],
)
def test_error_taxonomy_exposes_stable_code_and_retryability(error_type, code, retryable):
    error = error_type()
    assert isinstance(error, VectorStoreError)
    assert error.code == code
    assert error.retryable is retryable


def test_generation_build_failure_preserves_underlying_retryability_and_cause():
    cause = VectorStoreTimeout("request timed out")
    error = VectorGenerationBuildFailed(cause=cause)

    assert error.code == "VECTOR_GENERATION_BUILD_FAILED"
    assert error.retryable is True
    assert error.underlying_error is cause
    assert error.__cause__ is cause


def test_generation_build_failure_is_not_retryable_for_permanent_cause():
    cause = VectorStoreInvalidData("invalid payload")
    error = VectorGenerationBuildFailed(cause=cause)

    assert error.retryable is False


def test_generation_activation_failure_preserves_underlying_retryability_and_cause():
    cause = VectorStoreUnavailable("connection failed")
    error = VectorGenerationActivationFailed(cause=cause)

    assert error.retryable is True
    assert error.underlying_error is cause
    assert error.__cause__ is cause


def test_error_does_not_require_or_expose_raw_response_content():
    secret = "do-not-log-this"
    error = VectorStoreConfigurationError("invalid Qdrant configuration")

    assert secret not in str(error)
    assert error.code == "VECTOR_STORE_CONFIGURATION_ERROR"
