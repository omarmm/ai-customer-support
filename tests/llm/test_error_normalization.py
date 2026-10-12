import asyncio

import pytest

from app.llm.contracts import LLMRequest, LLMResponse
from app.llm.exceptions import (
    LLMAuthenticationError,
    LLMConnectionError,
    LLMError,
    LLMInvalidRequestError,
    LLMModelNotFoundError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnexpectedError,
    LLMUnavailableError,
)
from app.llm.providers.base import LLMProvider
from app.llm.providers.exceptions import (
    LLMProviderAuthenticationError,
    LLMProviderConnectionError,
    LLMProviderError,
    LLMProviderHTTPError,
    LLMProviderInvalidRequestError,
    LLMProviderModelNotFoundError,
    LLMProviderRateLimitError,
    LLMProviderResponseError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
)
from app.llm.services.llm_service import LLMService


class RaisingProvider(LLMProvider):

    def __init__(self, error: BaseException) -> None:
        self._error = error

    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise self._error


class EchoProvider(LLMProvider):

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content="ok",
            model=request.model,
            provider="echo",
        )


def make_request() -> LLMRequest:
    return LLMRequest(
        system_prompt="You are a support assistant.",
        user_prompt="Hello",
        model="test-model",
    )


KNOWN_MAPPINGS = [
    (LLMProviderConnectionError("down"), LLMConnectionError, "connection", True),
    (LLMProviderTimeoutError("slow"), LLMTimeoutError, "timeout", True),
    (LLMProviderRateLimitError(429), LLMRateLimitError, "rate_limit", True),
    (
        LLMProviderAuthenticationError(401),
        LLMAuthenticationError,
        "authentication",
        False,
    ),
    (
        LLMProviderInvalidRequestError(400),
        LLMInvalidRequestError,
        "invalid_request",
        False,
    ),
    (
        LLMProviderModelNotFoundError(404),
        LLMModelNotFoundError,
        "model_not_found",
        False,
    ),
    (LLMProviderUnavailableError(503), LLMUnavailableError, "unavailable", True),
    (LLMProviderResponseError("bad"), LLMResponseError, "response", False),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_error, application_error_type, category, retryable",
    KNOWN_MAPPINGS,
)
async def test_known_provider_errors_normalize(
    provider_error,
    application_error_type,
    category,
    retryable,
):
    service = LLMService(RaisingProvider(provider_error))

    with pytest.raises(application_error_type) as exc_info:
        await service.generate(make_request())

    error = exc_info.value

    assert type(error) is application_error_type
    assert isinstance(error, LLMError)
    assert error.category == category
    assert error.retryable is retryable
    assert error.__cause__ is provider_error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_error",
    [
        LLMProviderError("unclassified failure"),
        LLMProviderHTTPError(408),
        LLMProviderHTTPError(418),
    ],
)
async def test_unclassified_provider_errors_map_to_base_llm_error(
    provider_error,
):
    service = LLMService(RaisingProvider(provider_error))

    with pytest.raises(LLMError) as exc_info:
        await service.generate(make_request())

    error = exc_info.value

    assert type(error) is LLMError
    assert error.category == "unclassified"
    assert error.retryable is False
    assert error.__cause__ is provider_error


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unexpected_error",
    [
        ValueError("programming bug"),
        RuntimeError("boom"),
        TypeError("oops"),
    ],
)
async def test_unexpected_exceptions_wrap_and_preserve_cause(unexpected_error):
    service = LLMService(RaisingProvider(unexpected_error))

    with pytest.raises(LLMUnexpectedError) as exc_info:
        await service.generate(make_request())

    error = exc_info.value

    assert type(error) is LLMUnexpectedError
    assert isinstance(error, LLMError)
    assert error.category == "unexpected"
    assert error.retryable is False
    assert error.__cause__ is unexpected_error


@pytest.mark.asyncio
async def test_provider_errors_never_escape_as_provider_types():
    for provider_error in (
        LLMProviderConnectionError("down"),
        LLMProviderTimeoutError("slow"),
        LLMProviderRateLimitError(429),
        LLMProviderAuthenticationError(401),
        LLMProviderInvalidRequestError(400),
        LLMProviderModelNotFoundError(404),
        LLMProviderUnavailableError(503),
        LLMProviderResponseError("bad"),
        LLMProviderHTTPError(408),
        LLMProviderError("unclassified"),
    ):
        service = LLMService(RaisingProvider(provider_error))

        try:
            await service.generate(make_request())
        except LLMError:
            continue
        except Exception as exc:  # pragma: no cover - failure path
            pytest.fail(f"Provider error leaked as provider type: {type(exc)!r}")
        else:  # pragma: no cover - failure path
            pytest.fail("Provider error was not raised")


@pytest.mark.asyncio
async def test_llm_error_from_provider_passes_through_unchanged():
    original = LLMTimeoutError("already normalized")
    service = LLMService(RaisingProvider(original))

    with pytest.raises(LLMTimeoutError) as exc_info:
        await service.generate(make_request())

    assert exc_info.value is original


@pytest.mark.asyncio
async def test_normalization_is_deterministic():
    provider_error = LLMProviderHTTPError(408)
    service = LLMService(RaisingProvider(provider_error))

    observed_types = []
    for _ in range(3):
        with pytest.raises(LLMError) as exc_info:
            await service.generate(make_request())
        observed_types.append(type(exc_info.value))

    assert observed_types == [LLMError, LLMError, LLMError]


@pytest.mark.asyncio
async def test_cancellation_is_not_swallowed():
    service = LLMService(RaisingProvider(asyncio.CancelledError()))

    with pytest.raises(asyncio.CancelledError):
        await service.generate(make_request())


@pytest.mark.asyncio
async def test_success_path_returns_response():
    service = LLMService(EchoProvider())

    response = await service.generate(make_request())

    assert response.content == "ok"
    assert response.provider == "echo"
    assert response.model == "test-model"
