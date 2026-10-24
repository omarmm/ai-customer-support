import pytest

from app.rag.embeddings.exceptions import (
    EmbeddingAuthenticationError,
    EmbeddingConfigurationError,
    EmbeddingConnectionError,
    EmbeddingError,
    EmbeddingInvalidRequestError,
    EmbeddingModelMismatchError,
    EmbeddingModelNotFoundError,
    EmbeddingRateLimitError,
    EmbeddingResponseError,
    EmbeddingTimeoutError,
    EmbeddingUnexpectedError,
    EmbeddingUnavailableError,
    normalize_provider_error,
)
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

APPLICATION_TAXONOMY = [
    (EmbeddingError, "unclassified", False),
    (EmbeddingConnectionError, "connection", True),
    (EmbeddingTimeoutError, "timeout", True),
    (EmbeddingRateLimitError, "rate_limit", True),
    (EmbeddingUnavailableError, "unavailable", True),
    (EmbeddingAuthenticationError, "authentication", False),
    (EmbeddingInvalidRequestError, "invalid_request", False),
    (EmbeddingModelNotFoundError, "model_not_found", False),
    (EmbeddingModelMismatchError, "model_mismatch", False),
    (EmbeddingResponseError, "response", False),
    (EmbeddingConfigurationError, "configuration", False),
    (EmbeddingUnexpectedError, "unexpected", False),
]

PROVIDER_TO_APPLICATION_MAPPINGS = [
    (
        EmbeddingProviderConnectionError("down"),
        EmbeddingConnectionError,
        "connection",
        True,
    ),
    (
        EmbeddingProviderTimeoutError("slow"),
        EmbeddingTimeoutError,
        "timeout",
        True,
    ),
    (
        EmbeddingProviderRateLimitError(429),
        EmbeddingRateLimitError,
        "rate_limit",
        True,
    ),
    (
        EmbeddingProviderAuthenticationError(401),
        EmbeddingAuthenticationError,
        "authentication",
        False,
    ),
    (
        EmbeddingProviderInvalidRequestError(400),
        EmbeddingInvalidRequestError,
        "invalid_request",
        False,
    ),
    (
        EmbeddingProviderModelNotFoundError(404),
        EmbeddingModelNotFoundError,
        "model_not_found",
        False,
    ),
    (
        EmbeddingProviderUnavailableError(503),
        EmbeddingUnavailableError,
        "unavailable",
        True,
    ),
    (
        EmbeddingProviderResponseError("malformed_response"),
        EmbeddingResponseError,
        "response",
        False,
    ),
    (
        EmbeddingProviderModelMismatchError("reported model differs"),
        EmbeddingModelMismatchError,
        "model_mismatch",
        False,
    ),
    (EmbeddingProviderError("unclassified"), EmbeddingError, "unclassified", False),
    (EmbeddingProviderHTTPError(418), EmbeddingError, "unclassified", False),
]


def make_application_error(error_type):
    if error_type is EmbeddingResponseError:
        return error_type("invalid_json")
    return error_type()


# --- Application taxonomy --------------------------------------------------


@pytest.mark.parametrize(
    "error_type, category, retryable",
    APPLICATION_TAXONOMY,
)
def test_every_application_error_exposes_category_and_retryability(
    error_type,
    category,
    retryable,
):
    error = make_application_error(error_type)

    assert isinstance(error, EmbeddingError)
    assert error.category == category
    assert error.retryable is retryable
    assert error.retry_count == 0


@pytest.mark.parametrize(
    "error_type",
    [error_type for error_type, _, _ in APPLICATION_TAXONOMY],
)
def test_every_application_error_is_an_embedding_error(error_type):
    error = make_application_error(error_type)

    assert isinstance(error, EmbeddingError)


def test_retry_count_is_mutable_on_an_instance():
    error = EmbeddingTimeoutError("timed out")

    error.retry_count = 2

    assert error.retry_count == 2


def test_response_error_preserves_its_reason_code():
    error = EmbeddingResponseError("dimension_mismatch")

    assert error.reason == "dimension_mismatch"
    assert "dimension_mismatch" in str(error)


@pytest.mark.parametrize("reason", ["", "   ", None])
def test_response_error_rejects_an_invalid_reason_code(reason):
    with pytest.raises(ValueError):
        EmbeddingResponseError(reason)


def test_unexpected_error_preserves_the_original_cause():
    original = RuntimeError("programming bug")

    with pytest.raises(EmbeddingUnexpectedError) as exc_info:
        try:
            raise original
        except RuntimeError as error:
            raise EmbeddingUnexpectedError("unexpected internal failure") from error

    assert exc_info.value.__cause__ is original


# --- Provider taxonomy -----------------------------------------------------


def test_provider_http_errors_carry_the_status_code():
    for error_type in (
        EmbeddingProviderRateLimitError,
        EmbeddingProviderAuthenticationError,
        EmbeddingProviderInvalidRequestError,
        EmbeddingProviderModelNotFoundError,
        EmbeddingProviderUnavailableError,
    ):
        error = error_type(503)

        assert isinstance(error, EmbeddingProviderHTTPError)
        assert isinstance(error, EmbeddingProviderError)
        assert error.status_code == 503


def test_generic_provider_http_error_carries_the_status_code():
    error = EmbeddingProviderHTTPError(418)

    assert error.status_code == 418
    assert "418" in str(error)


def test_provider_connection_and_timeout_are_not_http_errors():
    for error_type in (
        EmbeddingProviderConnectionError,
        EmbeddingProviderTimeoutError,
    ):
        error = error_type("provider failure")

        assert isinstance(error, EmbeddingProviderError)
        assert not isinstance(error, EmbeddingProviderHTTPError)


def test_provider_response_error_preserves_its_reason_code():
    error = EmbeddingProviderResponseError("missing_embeddings")

    assert error.reason == "missing_embeddings"
    assert "missing_embeddings" in str(error)


@pytest.mark.parametrize("reason", ["", "   ", None])
def test_provider_response_error_rejects_an_invalid_reason_code(reason):
    with pytest.raises(ValueError):
        EmbeddingProviderResponseError(reason)


def test_provider_model_mismatch_is_a_provider_error():
    error = EmbeddingProviderModelMismatchError("reported model differs")

    assert isinstance(error, EmbeddingProviderError)
    assert "reported model differs" in str(error)


# --- Provider-to-application mapping --------------------------------------


@pytest.mark.parametrize(
    "provider_error, application_error_type, category, retryable",
    PROVIDER_TO_APPLICATION_MAPPINGS,
)
def test_known_provider_errors_normalize(
    provider_error,
    application_error_type,
    category,
    retryable,
):
    mapped = normalize_provider_error(provider_error)

    assert type(mapped) is application_error_type
    assert isinstance(mapped, EmbeddingError)
    assert mapped.category == category
    assert mapped.retryable is retryable
    assert mapped.retry_count == 0
    assert mapped.__cause__ is provider_error


def test_provider_response_reason_is_preserved_when_normalized():
    provider_error = EmbeddingProviderResponseError("dimension_mismatch")

    mapped = normalize_provider_error(provider_error)

    assert isinstance(mapped, EmbeddingResponseError)
    assert mapped.reason == provider_error.reason


def test_unclassified_provider_failure_maps_to_the_base_error():
    provider_error = EmbeddingProviderError("unclassified failure")

    mapped = normalize_provider_error(provider_error)

    assert type(mapped) is EmbeddingError
    assert mapped.category == "unclassified"
    assert mapped.retryable is False


def test_generic_provider_http_failure_maps_to_the_base_error():
    provider_error = EmbeddingProviderHTTPError(408)

    mapped = normalize_provider_error(provider_error)

    assert type(mapped) is EmbeddingError
    assert mapped.category == "unclassified"
    assert mapped.retryable is False


def test_normalization_rejects_a_non_provider_error():
    with pytest.raises(TypeError):
        normalize_provider_error(RuntimeError("not a provider error"))


@pytest.mark.parametrize(
    "provider_error",
    [
        EmbeddingProviderError("SECRET CHUNK TEXT"),
        EmbeddingProviderConnectionError("SECRET CHUNK TEXT"),
        EmbeddingProviderTimeoutError("SECRET CHUNK TEXT"),
        EmbeddingProviderRateLimitError(429),
        EmbeddingProviderAuthenticationError(401),
        EmbeddingProviderInvalidRequestError(400),
        EmbeddingProviderModelNotFoundError(404),
        EmbeddingProviderUnavailableError(503),
        EmbeddingProviderResponseError("malformed_response"),
        EmbeddingProviderModelMismatchError("SECRET CHUNK TEXT"),
        EmbeddingProviderHTTPError(418),
    ],
)
def test_normalized_messages_do_not_leak_provider_details(provider_error):
    mapped = normalize_provider_error(provider_error)

    assert "SECRET CHUNK TEXT" not in str(mapped)
