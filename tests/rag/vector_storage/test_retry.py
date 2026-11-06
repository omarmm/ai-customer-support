"""Offline tests for the Qdrant storage retry policy and executor."""

import ast
import inspect
from dataclasses import FrozenInstanceError

import httpx
import pytest
from qdrant_client.common.client_exceptions import ResourceExhaustedResponse
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.rag.vector_storage import retry as retry_module
from app.rag.vector_storage.exceptions import (
    VectorStoreInvalidData,
    VectorStoreServiceError,
    VectorStoreTimeout,
    VectorStoreTransientServiceError,
    VectorStoreUnavailable,
)
from app.rag.vector_storage.qdrant_adapter import execute_with_retry
from app.rag.vector_storage.retry import QdrantRetryPolicy


def unexpected_response(status_code):
    return UnexpectedResponse(
        status_code=status_code,
        reason_phrase="reason",
        content=b"raw response body",
        headers=httpx.Headers(),
    )


def test_defaults_match_the_approved_retry_policy():
    policy = QdrantRetryPolicy()

    assert policy.max_attempts == 3
    assert policy.base_delay == 0.5
    assert policy.max_delay == 8.0


def test_jitter_ratio_parameter_has_been_removed():
    with pytest.raises(TypeError):
        QdrantRetryPolicy(jitter=0.2)


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_attempts": 0},
        {"max_attempts": 4},
        {"max_attempts": True},
        {"max_attempts": "3"},
        {"base_delay": -0.1},
        {"max_delay": -0.1},
        {"max_delay": 0.25, "base_delay": 0.5},
        {"base_delay": float("nan")},
        {"max_delay": float("inf")},
        {"base_delay": "0.5"},
    ],
)
def test_invalid_policies_are_rejected(overrides):
    with pytest.raises(ValueError):
        QdrantRetryPolicy(**overrides)


def test_policy_is_frozen():
    policy = QdrantRetryPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.max_attempts = 1  # type: ignore[misc]


@pytest.fixture
def full_jitter_high(monkeypatch):
    """Make Full Jitter deterministic by always sampling the upper bound."""

    monkeypatch.setattr(retry_module.random, "uniform", lambda low, high: high)


def test_full_jitter_upper_bound_grows_exponentially_and_is_capped(monkeypatch):
    calls = []

    def uniform(low, high):
        calls.append((low, high))
        return high

    monkeypatch.setattr(retry_module.random, "uniform", uniform)

    policy = QdrantRetryPolicy(base_delay=0.5, max_delay=2.0)

    assert policy.delay_for_attempt(0) == 0.5
    assert policy.delay_for_attempt(1) == 1.0
    assert policy.delay_for_attempt(2) == 2.0
    assert policy.delay_for_attempt(3) == 2.0
    assert policy.delay_for_attempt(10) == 2.0
    assert calls == [
        (0.0, 0.5),
        (0.0, 1.0),
        (0.0, 2.0),
        (0.0, 2.0),
        (0.0, 2.0),
    ]


def test_full_jitter_samples_between_zero_and_the_cap(monkeypatch):
    calls = []

    def uniform(low, high):
        calls.append((low, high))
        return high * 0.25

    monkeypatch.setattr(retry_module.random, "uniform", uniform)

    policy = QdrantRetryPolicy(base_delay=1.0, max_delay=4.0)

    assert policy.delay_for_attempt(1) == 0.5
    assert policy.delay_for_attempt(10) == 1.0
    assert calls == [(0.0, 2.0), (0.0, 4.0)]


def test_full_jitter_can_produce_a_zero_delay(monkeypatch):
    monkeypatch.setattr(retry_module.random, "uniform", lambda low, high: low)

    policy = QdrantRetryPolicy(base_delay=1.0, max_delay=8.0)

    assert policy.delay_for_attempt(3) == 0.0


def test_zero_base_delay_produces_zero_backoff(monkeypatch):
    calls = []

    def uniform(low, high):
        calls.append((low, high))
        return high

    monkeypatch.setattr(retry_module.random, "uniform", uniform)

    policy = QdrantRetryPolicy(base_delay=0.0, max_delay=0.0)

    assert policy.delay_for_attempt(0) == 0.0
    assert policy.delay_for_attempt(5) == 0.0
    assert calls == [(0.0, 0.0), (0.0, 0.0)]


def test_negative_attempt_is_rejected():
    with pytest.raises(ValueError):
        QdrantRetryPolicy().delay_for_attempt(-1)


def test_successful_operation_is_attempted_once_without_sleep():
    sleeps = []
    calls = []

    result = execute_with_retry(
        lambda: calls.append(1) or "ok",
        policy=QdrantRetryPolicy(base_delay=0.5),
        sleep=sleeps.append,
    )

    assert result == "ok"
    assert len(calls) == 1
    assert sleeps == []


def test_transient_failure_is_retried_until_success(full_jitter_high):
    sleeps = []
    calls = []

    def operation():
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("not reachable")
        return "ok"

    result = execute_with_retry(
        operation,
        policy=QdrantRetryPolicy(base_delay=0.5, max_delay=8.0),
        sleep=sleeps.append,
    )

    assert result == "ok"
    assert len(calls) == 2
    assert sleeps == [0.5]


def test_transient_failure_is_limited_to_three_total_attempts(full_jitter_high):
    sleeps = []
    calls = []

    def operation():
        calls.append(1)
        raise httpx.ConnectError("not reachable")

    with pytest.raises(VectorStoreUnavailable) as caught:
        execute_with_retry(
            operation,
            policy=QdrantRetryPolicy(base_delay=0.5, max_delay=8.0),
            sleep=sleeps.append,
        )

    assert len(calls) == 3
    assert sleeps == [0.5, 1.0]
    assert isinstance(caught.value.__cause__, httpx.ConnectError)


def test_permanent_http_failure_is_not_retried():
    calls = []
    sleeps = []

    def operation():
        calls.append(1)
        raise unexpected_response(404)

    with pytest.raises(VectorStoreServiceError) as caught:
        execute_with_retry(operation, sleep=sleeps.append)

    assert caught.value.retryable is False
    assert len(calls) == 1
    assert sleeps == []


def test_429_without_retry_after_is_not_retried():
    calls = []
    sleeps = []

    def operation():
        calls.append(1)
        raise unexpected_response(429)

    with pytest.raises(VectorStoreServiceError) as caught:
        execute_with_retry(operation, sleep=sleeps.append)

    assert caught.value.code == "VECTOR_STORE_SERVICE_ERROR"
    assert caught.value.retryable is False
    assert len(calls) == 1
    assert sleeps == []


def test_429_with_retry_after_is_not_retried():
    calls = []
    sleeps = []

    def operation():
        calls.append(1)
        raise ResourceExhaustedResponse("resource exhausted", retry_after_s=30)

    with pytest.raises(VectorStoreServiceError) as caught:
        execute_with_retry(operation, sleep=sleeps.append)

    assert caught.value.retryable is False
    assert len(calls) == 1
    assert sleeps == []


def test_wrapped_parsing_failure_is_not_retried():
    calls = []
    sleeps = []

    def operation():
        calls.append(1)
        raise ResponseHandlingException(ValueError("malformed response"))

    with pytest.raises(VectorStoreServiceError) as caught:
        execute_with_retry(operation, sleep=sleeps.append)

    assert caught.value.retryable is False
    assert len(calls) == 1
    assert sleeps == []


def test_unknown_failure_is_not_retried():
    calls = []
    sleeps = []

    def operation():
        calls.append(1)
        raise RuntimeError("unexpected")

    with pytest.raises(VectorStoreServiceError) as caught:
        execute_with_retry(operation, sleep=sleeps.append)

    assert caught.value.retryable is False
    assert len(calls) == 1
    assert sleeps == []


def test_wrapped_timeout_is_retried(full_jitter_high):
    calls = []
    sleeps = []

    def operation():
        calls.append(1)
        raise ResponseHandlingException(httpx.ReadTimeout("timed out"))

    with pytest.raises(VectorStoreTimeout) as caught:
        execute_with_retry(
            operation,
            policy=QdrantRetryPolicy(base_delay=0.25, max_delay=1.0),
            sleep=sleeps.append,
        )

    assert caught.value.retryable is True
    assert len(calls) == 3
    assert sleeps == [0.25, 0.5]


def test_wrapped_connection_failure_is_retried(full_jitter_high):
    calls = []
    sleeps = []

    def operation():
        calls.append(1)
        if len(calls) == 1:
            raise ResponseHandlingException(httpx.ConnectError("not reachable"))
        return "ok"

    result = execute_with_retry(
        operation,
        policy=QdrantRetryPolicy(base_delay=0.5),
        sleep=sleeps.append,
    )

    assert result == "ok"
    assert len(calls) == 2
    assert sleeps == [0.5]


def test_five_hundred_failure_is_retried(full_jitter_high):
    calls = []
    sleeps = []

    def operation():
        calls.append(1)
        if len(calls) < 3:
            raise unexpected_response(503)
        return "ok"

    result = execute_with_retry(
        operation,
        policy=QdrantRetryPolicy(base_delay=0.5),
        sleep=sleeps.append,
    )

    assert result == "ok"
    assert len(calls) == 3
    assert sleeps == [0.5, 1.0]


def test_already_normalized_application_error_is_passed_through():
    error = VectorStoreInvalidData("invalid payload")
    calls = []

    def operation():
        calls.append(1)
        raise error

    with pytest.raises(VectorStoreInvalidData) as caught:
        execute_with_retry(operation, sleep=lambda _: None)

    assert caught.value is error
    assert len(calls) == 1


def test_transient_application_error_is_retried(full_jitter_high):
    calls = []
    sleeps = []

    def operation():
        calls.append(1)
        if len(calls) == 1:
            raise VectorStoreTransientServiceError("service unavailable")
        return "ok"

    result = execute_with_retry(
        operation,
        policy=QdrantRetryPolicy(base_delay=0.5),
        sleep=sleeps.append,
    )

    assert result == "ok"
    assert len(calls) == 2
    assert sleeps == [0.5]


def test_executor_uses_full_jitter_with_deterministic_randomness(monkeypatch):
    random_calls = []
    sleeps = []
    operation_calls = []

    def uniform(low, high):
        random_calls.append((low, high))
        return high * 0.25

    monkeypatch.setattr(retry_module.random, "uniform", uniform)

    def operation():
        operation_calls.append(1)
        if len(operation_calls) < 3:
            raise httpx.ConnectError("not reachable")
        return "ok"

    result = execute_with_retry(
        operation,
        policy=QdrantRetryPolicy(base_delay=0.5, max_delay=8.0),
        sleep=sleeps.append,
    )

    assert result == "ok"
    assert len(operation_calls) == 3
    assert random_calls == [(0.0, 0.5), (0.0, 1.0)]
    assert sleeps == [0.125, 0.25]


def test_max_attempts_one_disables_retries():
    calls = []
    sleeps = []

    def operation():
        calls.append(1)
        raise httpx.ConnectError("not reachable")

    with pytest.raises(VectorStoreUnavailable):
        execute_with_retry(
            operation,
            policy=QdrantRetryPolicy(max_attempts=1),
            sleep=sleeps.append,
        )

    assert len(calls) == 1
    assert sleeps == []


def _imported_modules(module) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_retry_module_does_not_import_qdrant_or_http_client_libraries():
    modules = _imported_modules(retry_module)

    assert not any(
        module == root or module.startswith(f"{root}.")
        for module in modules
        for root in ("qdrant_client", "httpx", "app.core", "fastapi")
    )
