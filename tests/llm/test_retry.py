import asyncio
from types import SimpleNamespace

import pytest

from app.llm.contracts import LLMRequest, LLMResponse
from app.llm.exceptions import (
    LLMAuthenticationError,
    LLMError,
    LLMTimeoutError,
    LLMUnexpectedError,
    LLMUnavailableError,
)
from app.llm.providers.base import LLMProvider
from app.llm.providers.exceptions import (
    LLMProviderAuthenticationError,
    LLMProviderHTTPError,
    LLMProviderUnavailableError,
)
from app.llm.retry import RetryPolicy
from app.llm.services.llm_service import LLMService


class RecordingSleep:

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


class AlwaysRaisingProvider(LLMProvider):

    def __init__(
        self,
        error: BaseException,
        timeout_log: list[float] | None = None,
    ) -> None:
        self._error = error
        self._timeout_log = timeout_log
        self.calls = 0

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self._timeout_log is not None:
            self._timeout_log.append(request.timeout)
        raise self._error


class ScriptedProvider(LLMProvider):
    """Raise the scripted errors, then return a response."""

    def __init__(self, errors: list[BaseException]) -> None:
        self._errors = list(errors)
        self.calls = 0

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self._errors:
            raise self._errors.pop(0)
        return LLMResponse(
            content="recovered",
            model=request.model,
            provider="scripted",
        )


class PerRequestFlakyProvider(LLMProvider):
    """Fail a configurable number of times per user prompt, independently."""

    def __init__(self, failures_by_prompt: dict[str, int]) -> None:
        self._remaining = dict(failures_by_prompt)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        key = request.user_prompt
        if self._remaining.get(key, 0) > 0:
            self._remaining[key] -= 1
            raise LLMProviderUnavailableError(503)

        return LLMResponse(
            content=key,
            model=request.model,
            provider="flaky",
        )


def make_request(user_prompt: str = "Hello") -> LLMRequest:
    return LLMRequest(
        system_prompt="You are a support assistant.",
        user_prompt=user_prompt,
        model="test-model",
        timeout=12.5,
    )


@pytest.mark.asyncio
async def test_retryable_error_is_retried_up_to_limit():
    provider = AlwaysRaisingProvider(LLMProviderUnavailableError(503))
    sleep = RecordingSleep()
    service = LLMService(
        provider,
        retry_policy=RetryPolicy(max_retries=3, base_delay=0.0),
        sleep=sleep,
    )

    with pytest.raises(LLMUnavailableError) as exc_info:
        await service.generate(make_request())

    error = exc_info.value

    assert provider.calls == 4  # 1 + max_retries
    assert error.retryable is True
    assert error.retry_count == 3
    assert error.__cause__ is provider._error
    assert len(sleep.delays) == 3


@pytest.mark.asyncio
async def test_default_policy_bounds_total_attempts():
    provider = AlwaysRaisingProvider(LLMProviderUnavailableError(503))
    service = LLMService(provider, sleep=RecordingSleep())

    with pytest.raises(LLMUnavailableError) as exc_info:
        await service.generate(make_request())

    assert RetryPolicy().max_retries == 2
    assert provider.calls == 3
    assert exc_info.value.retry_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_error, application_error_type",
    [
        (LLMProviderAuthenticationError(401), LLMAuthenticationError),
        (LLMProviderHTTPError(418), LLMError),
    ],
)
async def test_non_retryable_errors_fail_immediately(
    provider_error,
    application_error_type,
):
    provider = AlwaysRaisingProvider(provider_error)
    sleep = RecordingSleep()
    service = LLMService(provider, sleep=sleep)

    with pytest.raises(application_error_type) as exc_info:
        await service.generate(make_request())

    assert provider.calls == 1
    assert sleep.delays == []
    assert exc_info.value.retryable is False
    assert exc_info.value.retry_count == 0


@pytest.mark.asyncio
async def test_unexpected_error_is_not_retried():
    original = ValueError("programming bug")
    provider = AlwaysRaisingProvider(original)
    sleep = RecordingSleep()
    service = LLMService(provider, sleep=sleep)

    with pytest.raises(LLMUnexpectedError) as exc_info:
        await service.generate(make_request())

    assert provider.calls == 1
    assert sleep.delays == []
    assert exc_info.value.__cause__ is original
    assert exc_info.value.retry_count == 0


@pytest.mark.asyncio
async def test_success_after_retries_reports_retry_count():
    provider = ScriptedProvider(
        [
            LLMProviderUnavailableError(503),
            LLMProviderUnavailableError(503),
        ]
    )
    sleep = RecordingSleep()
    service = LLMService(
        provider,
        retry_policy=RetryPolicy(max_retries=3, base_delay=0.0),
        sleep=sleep,
    )

    response = await service.generate(make_request())

    assert response.content == "recovered"
    assert response.metadata["retry_count"] == 2
    assert provider.calls == 3
    assert len(sleep.delays) == 2


@pytest.mark.asyncio
async def test_success_without_retries_reports_zero():
    provider = ScriptedProvider([])
    service = LLMService(provider, sleep=RecordingSleep())

    response = await service.generate(make_request())

    assert response.metadata["retry_count"] == 0
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_backoff_is_bounded_exponential():
    provider = AlwaysRaisingProvider(LLMProviderUnavailableError(503))
    sleep = RecordingSleep()
    policy = RetryPolicy(max_retries=5, base_delay=0.1, max_delay=0.4)
    service = LLMService(provider, retry_policy=policy, sleep=sleep)

    with pytest.raises(LLMUnavailableError):
        await service.generate(make_request())

    assert sleep.delays == [0.1, 0.2, 0.4, 0.4, 0.4]
    assert all(0 < delay <= policy.max_delay for delay in sleep.delays)


@pytest.mark.asyncio
async def test_backoff_does_not_consume_per_attempt_timeout():
    timeouts: list[float] = []
    provider = AlwaysRaisingProvider(
        LLMProviderUnavailableError(503),
        timeout_log=timeouts,
    )
    sleep = RecordingSleep()
    service = LLMService(
        provider,
        retry_policy=RetryPolicy(max_retries=2, base_delay=0.25),
        sleep=sleep,
    )

    request = make_request()

    with pytest.raises(LLMUnavailableError):
        await service.generate(request)

    # Each attempt sees the original, unchanged per-attempt timeout.
    assert timeouts == [request.timeout, request.timeout, request.timeout]
    # Backoff is a separate wait and never counted against the timeout.
    assert sleep.delays == [0.25, 0.5]


@pytest.mark.asyncio
async def test_cancellation_is_not_retried_or_swallowed():
    provider = AlwaysRaisingProvider(asyncio.CancelledError())
    sleep = RecordingSleep()
    service = LLMService(provider, sleep=sleep)

    with pytest.raises(asyncio.CancelledError):
        await service.generate(make_request())

    assert provider.calls == 1
    assert sleep.delays == []


@pytest.mark.asyncio
async def test_provider_application_error_passes_through_without_retry():
    original = LLMTimeoutError("already normalized")
    provider = AlwaysRaisingProvider(original)
    sleep = RecordingSleep()
    service = LLMService(provider, sleep=sleep)

    with pytest.raises(LLMTimeoutError) as exc_info:
        await service.generate(make_request())

    assert exc_info.value is original
    assert provider.calls == 1
    assert sleep.delays == []


@pytest.mark.asyncio
async def test_retry_state_is_not_shared_between_concurrent_requests():
    provider = PerRequestFlakyProvider({"a": 2, "b": 0})
    sleep = RecordingSleep()
    service = LLMService(
        provider,
        retry_policy=RetryPolicy(max_retries=3, base_delay=0.0),
        sleep=sleep,
    )

    first, second = await asyncio.gather(
        service.generate(make_request("a")),
        service.generate(make_request("b")),
    )

    assert first.metadata["retry_count"] == 2
    assert second.metadata["retry_count"] == 0


def test_retry_policy_rejects_invalid_values():
    with pytest.raises(ValueError):
        RetryPolicy(max_retries=-1)

    with pytest.raises(ValueError):
        RetryPolicy(base_delay=-0.1)

    with pytest.raises(ValueError):
        RetryPolicy(max_delay=-1.0)

    with pytest.raises(ValueError):
        RetryPolicy(base_delay=1.0, max_delay=0.5)

    with pytest.raises(ValueError):
        RetryPolicy(jitter=-0.1)


def test_delay_for_attempt_rejects_negative_attempt():
    with pytest.raises(ValueError):
        RetryPolicy().delay_for_attempt(-1)


def test_retry_policy_from_settings():
    settings = SimpleNamespace(
        llm_max_retries=5,
        llm_retry_base_delay=0.2,
        llm_retry_max_delay=1.6,
        llm_retry_jitter=0.1,
    )

    policy = RetryPolicy.from_settings(settings)

    assert policy == RetryPolicy(
        max_retries=5,
        base_delay=0.2,
        max_delay=1.6,
        jitter=0.1,
    )
