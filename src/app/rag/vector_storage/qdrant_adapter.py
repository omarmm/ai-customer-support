"""Qdrant client boundary for knowledge vector storage.

Only this module imports the Qdrant SDK and HTTPX. Qdrant SDK exceptions, SDK
response models, raw response bodies, and API keys never escape the adapter:
every failure is translated into the application-owned taxonomy defined in
``app.rag.vector_storage.exceptions``.

This task adds client construction, exception normalization, and bounded retry
execution only. Collection, point, verification, activation, information, and
deletion behavior belong to later tasks.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

import httpx
from qdrant_client import QdrantClient
from qdrant_client.common.client_exceptions import ResourceExhaustedResponse
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.rag.vector_storage.exceptions import (
    VectorStoreConfigurationError,
    VectorStoreError,
    VectorStoreInvalidData,
    VectorStoreServiceError,
    VectorStoreTimeout,
    VectorStoreTransientServiceError,
    VectorStoreUnavailable,
)
from app.rag.vector_storage.retry import QdrantRetryPolicy

DEFAULT_QDRANT_TIMEOUT_SECONDS = 10.0

T = TypeVar("T")

__all__ = [
    "DEFAULT_QDRANT_TIMEOUT_SECONDS",
    "QdrantClientAdapter",
    "QdrantClientConfig",
    "build_qdrant_client",
    "execute_with_retry",
    "normalize_qdrant_error",
]


@dataclass(frozen=True)
class QdrantClientConfig:
    """Explicit Qdrant connection configuration.

    The URL, optional API key, and timeout are supplied by the caller. No
    environment variable or global settings object is read here; composition
    belongs to the application wiring task.
    """

    url: str
    api_key: str | None = field(default=None, repr=False)
    timeout: float = DEFAULT_QDRANT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if not isinstance(self.url, str) or not self.url.strip():
            raise ValueError("url must be a non-empty string")

        if self.api_key is not None:
            if not isinstance(self.api_key, str) or not self.api_key.strip():
                raise ValueError("api_key must be a non-empty string when provided")

        if isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float)):
            raise ValueError("timeout must be a positive number")
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("timeout must be positive and finite")

        object.__setattr__(self, "timeout", float(self.timeout))


def build_qdrant_client(
    config: QdrantClientConfig,
    *,
    client_factory: Callable[..., Any] = QdrantClient,
) -> Any:
    """Construct a Qdrant client without performing network I/O.

    ``check_compatibility=False`` is intentional: the SDK otherwise starts a
    background compatibility request during construction, which would violate
    the approved requirement that application startup performs no Qdrant
    network I/O.
    """

    if not isinstance(config, QdrantClientConfig):
        raise TypeError("config must be a QdrantClientConfig")

    try:
        return client_factory(
            url=config.url,
            api_key=config.api_key,
            timeout=config.timeout,
            check_compatibility=False,
        )
    except VectorStoreError:
        raise
    except Exception as exc:
        raise VectorStoreConfigurationError(
            "unable to construct Qdrant client", cause=exc
        ) from exc


def _is_timeout(exc: BaseException) -> bool:
    return isinstance(exc, httpx.TimeoutException)


def _is_connection_failure(exc: BaseException) -> bool:
    return isinstance(exc, httpx.ConnectError)


def _error_for_status(
    status_code: object, cause: Exception
) -> VectorStoreError:
    if isinstance(status_code, int) and not isinstance(status_code, bool):
        if 500 <= status_code <= 599:
            return VectorStoreTransientServiceError(
                "Qdrant service error", cause=cause
            )
        if status_code in (400, 422):
            return VectorStoreInvalidData(
                "invalid Qdrant vector or payload data", cause=cause
            )
        if status_code in (401, 403):
            return VectorStoreConfigurationError(
                "invalid Qdrant endpoint configuration or credentials", cause=cause
            )

    # Includes HTTP 429, other 4xx responses, and unknown status values. The
    # rate-limit path is explicitly not retried in V1.
    return VectorStoreServiceError("Qdrant request failed", cause=cause)


def normalize_qdrant_error(exc: Exception) -> VectorStoreError:
    """Translate a Qdrant/HTTPX/unknown exception into the application taxonomy.

    The original exception is retained as the internal ``__cause__`` for
    diagnostics. Error messages are fixed strings; raw response bodies, reason
    phrases, URLs, and credentials are never copied into them.
    """

    if isinstance(exc, VectorStoreError):
        return exc

    if isinstance(exc, UnexpectedResponse):
        return _error_for_status(exc.status_code, exc)

    if isinstance(exc, ResourceExhaustedResponse):
        # The SDK raises this for a 429 that carries ``Retry-After``. V1 does
        # not honor ``Retry-After`` and never retries a rate-limit response.
        return VectorStoreServiceError("Qdrant rate limit response", cause=exc)

    if isinstance(exc, ResponseHandlingException):
        source = exc.source
        if _is_timeout(source):
            return VectorStoreTimeout("Qdrant request timed out", cause=exc)
        if _is_connection_failure(source):
            return VectorStoreUnavailable("Qdrant connection failed", cause=exc)
        # A wrapper is not automatically a transport failure. Response
        # parsing/validation failures and unrecognized sources are permanent
        # application-level failures.
        return VectorStoreServiceError("Qdrant response handling failed", cause=exc)

    if _is_timeout(exc):
        return VectorStoreTimeout("Qdrant request timed out", cause=exc)
    if _is_connection_failure(exc):
        return VectorStoreUnavailable("Qdrant connection failed", cause=exc)
    return VectorStoreServiceError("Qdrant request failed", cause=exc)


def execute_with_retry(
    operation: Callable[[], T],
    *,
    policy: QdrantRetryPolicy | None = None,
    sleep: Callable[[float], None] | None = None,
) -> T:
    """Run one storage operation with bounded transient-only retries.

    The operation may raise an application-owned ``VectorStoreError`` or a raw
    exception from the Qdrant/HTTPX boundary. Non-retryable failures and HTTP
    429 fail immediately. Eligible failures receive at most
    ``policy.max_attempts`` total attempts.
    """

    effective_policy = policy or QdrantRetryPolicy()
    sleep_fn = time.sleep if sleep is None else sleep

    for attempt_index in range(effective_policy.max_attempts):
        try:
            return operation()
        except Exception as exc:
            error = normalize_qdrant_error(exc)
            if not error.retryable or attempt_index + 1 >= effective_policy.max_attempts:
                raise error
            sleep_fn(effective_policy.delay_for_attempt(attempt_index))

    # ``max_attempts`` is validated as at least one, so this is unreachable.
    raise AssertionError("retry loop exhausted without a result")


class QdrantClientAdapter:
    """Owns a Qdrant client and executes SDK calls at the application boundary.

    Later storage tasks add the operation methods. This class deliberately does
    not implement generation lifecycle orchestration, collection creation, or
    startup connectivity checks.
    """

    def __init__(
        self,
        client: Any,
        *,
        retry_policy: QdrantRetryPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._client = client
        self._retry_policy = retry_policy or QdrantRetryPolicy()
        self._sleep = sleep

    @classmethod
    def from_config(
        cls,
        config: QdrantClientConfig,
        *,
        client_factory: Callable[..., Any] = QdrantClient,
        retry_policy: QdrantRetryPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> "QdrantClientAdapter":
        client = build_qdrant_client(config, client_factory=client_factory)
        return cls(client, retry_policy=retry_policy, sleep=sleep)

    def _execute(self, operation: Callable[[Any], T]) -> T:
        """Execute an SDK operation through the normalized retry boundary."""

        return execute_with_retry(
            lambda: operation(self._client),
            policy=self._retry_policy,
            sleep=self._sleep,
        )

    def close(self) -> None:
        try:
            self._client.close()
        except Exception as exc:
            raise normalize_qdrant_error(exc) from exc
