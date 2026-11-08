"""Offline tests for the Qdrant client adapter and exception normalization."""

import ast
import inspect
from dataclasses import FrozenInstanceError

import httpx
import pytest
from qdrant_client.common.client_exceptions import ResourceExhaustedResponse
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.rag.vector_storage import qdrant_adapter as adapter_module
from app.rag.vector_storage import retry as retry_module
from app.rag.vector_storage.exceptions import (
    VectorStoreConfigurationError,
    VectorStoreInvalidData,
    VectorStoreServiceError,
    VectorStoreTimeout,
    VectorStoreTransientServiceError,
    VectorStoreUnavailable,
)
from app.rag.vector_storage.qdrant_adapter import (
    DEFAULT_QDRANT_TIMEOUT_SECONDS,
    QdrantClientAdapter,
    QdrantClientConfig,
    build_qdrant_client,
    normalize_qdrant_error,
)
from app.rag.vector_storage.retry import QdrantRetryPolicy


class FakeClient:
    def __init__(self, value="client"):
        self.value = value
        self.closed = False

    def close(self):
        self.closed = True


def unexpected_response(status_code, *, body=b"raw response body", reason="reason"):
    return UnexpectedResponse(
        status_code=status_code,
        reason_phrase=reason,
        content=body,
        headers=httpx.Headers({"authorization": "secret-header"}),
    )


def test_client_config_defaults_match_the_approved_contract():
    config = QdrantClientConfig(url="http://qdrant:6333")

    assert config.url == "http://qdrant:6333"
    assert config.api_key is None
    assert config.timeout == DEFAULT_QDRANT_TIMEOUT_SECONDS == 10.0


def test_client_config_is_frozen():
    config = QdrantClientConfig(url="http://qdrant:6333")

    with pytest.raises(FrozenInstanceError):
        config.timeout = 5.0  # type: ignore[misc]


def test_client_config_hides_the_api_key_from_its_repr():
    config = QdrantClientConfig(url="http://qdrant:6333", api_key="super-secret-key")

    assert "super-secret-key" not in repr(config)
    assert "api_key" not in repr(config)


@pytest.mark.parametrize("url", [None, "", "   ", 123])
def test_client_config_rejects_invalid_urls(url):
    with pytest.raises(ValueError):
        QdrantClientConfig(url=url)


@pytest.mark.parametrize("api_key", ["", "   ", 123])
def test_client_config_rejects_invalid_api_keys(api_key):
    with pytest.raises(ValueError):
        QdrantClientConfig(url="http://qdrant:6333", api_key=api_key)


@pytest.mark.parametrize(
    "timeout", [True, False, 0, -1, "10", None, float("nan"), float("inf")]
)
def test_client_config_rejects_invalid_timeouts(timeout):
    with pytest.raises(ValueError):
        QdrantClientConfig(url="http://qdrant:6333", timeout=timeout)


def test_build_client_passes_explicit_config_without_compatibility_probe():
    recorded = {}
    client = FakeClient()

    def factory(**kwargs):
        recorded.update(kwargs)
        return client

    result = build_qdrant_client(
        QdrantClientConfig(url="http://qdrant:6333", api_key="secret-key", timeout=10),
        client_factory=factory,
    )

    assert result is client
    assert recorded == {
        "url": "http://qdrant:6333",
        "api_key": "secret-key",
        "timeout": 10.0,
        "check_compatibility": False,
    }


def test_build_client_supports_an_absent_api_key():
    recorded = {}

    def factory(**kwargs):
        recorded.update(kwargs)
        return FakeClient()

    build_qdrant_client(
        QdrantClientConfig(url="http://qdrant:6333"),
        client_factory=factory,
    )

    assert recorded["api_key"] is None


def test_build_client_requires_the_application_config_type():
    with pytest.raises(TypeError):
        build_qdrant_client({"url": "http://qdrant:6333"})


def test_client_construction_failure_is_normalized_without_leaking_details():
    failure = ValueError("bad secret-key value")

    def factory(**kwargs):
        raise failure

    with pytest.raises(VectorStoreConfigurationError) as caught:
        build_qdrant_client(
            QdrantClientConfig(url="http://qdrant:6333"),
            client_factory=factory,
        )

    assert caught.value.code == "VECTOR_STORE_CONFIGURATION_ERROR"
    assert caught.value.retryable is False
    assert caught.value.__cause__ is failure
    assert "secret-key" not in str(caught.value)


def test_adapter_from_config_constructs_and_executes_without_exposing_the_client():
    client = FakeClient("value")
    adapter = QdrantClientAdapter.from_config(
        QdrantClientConfig(url="http://qdrant:6333"),
        client_factory=lambda **kwargs: client,
        retry_policy=QdrantRetryPolicy(),
    )

    assert adapter._execute(lambda qdrant: qdrant.value) == "value"

    adapter.close()
    assert client.closed is True


def test_adapter_execute_retries_transient_failures_with_injected_sleep(monkeypatch):
    monkeypatch.setattr(retry_module.random, "uniform", lambda low, high: high)

    client = FakeClient()
    sleeps = []
    calls = []
    adapter = QdrantClientAdapter(
        client,
        retry_policy=QdrantRetryPolicy(base_delay=0.5),
        sleep=sleeps.append,
    )

    def operation(qdrant):
        calls.append(qdrant)
        if len(calls) < 2:
            raise httpx.ConnectError("not reachable")
        return "ok"

    assert adapter._execute(operation) == "ok"
    assert calls == [client, client]
    assert sleeps == [0.5]


def test_adapter_close_normalizes_transport_failures():
    class BrokenClient:
        def close(self):
            raise httpx.ConnectError("not reachable")

    adapter = QdrantClientAdapter(BrokenClient())

    with pytest.raises(VectorStoreUnavailable) as caught:
        adapter.close()

    assert isinstance(caught.value.__cause__, httpx.ConnectError)


def test_adapter_implements_only_the_authorized_generation_lifecycle_operations():
    for name in (
        "create_generation",
        "upsert_points",
        "verify_generation",
        "activate_generation",
        "get_generation_info",
        "delete_generation",
    ):
        assert hasattr(QdrantClientAdapter, name)

    for name in ("search",):
        assert not hasattr(QdrantClientAdapter, name)


@pytest.mark.parametrize("status_code", [500, 502, 503, 599])
def test_5xx_responses_map_to_retryable_service_errors(status_code):
    original = unexpected_response(status_code)

    error = normalize_qdrant_error(original)

    assert isinstance(error, VectorStoreTransientServiceError)
    assert error.code == "VECTOR_STORE_SERVICE_ERROR"
    assert error.retryable is True
    assert error.__cause__ is original


@pytest.mark.parametrize("status_code", [400, 422])
def test_invalid_request_responses_map_to_invalid_data(status_code):
    original = unexpected_response(status_code)

    error = normalize_qdrant_error(original)

    assert isinstance(error, VectorStoreInvalidData)
    assert error.code == "VECTOR_STORE_INVALID_DATA"
    assert error.retryable is False
    assert error.__cause__ is original


@pytest.mark.parametrize("status_code", [401, 403])
def test_authentication_responses_map_to_configuration_errors(status_code):
    original = unexpected_response(status_code)

    error = normalize_qdrant_error(original)

    assert isinstance(error, VectorStoreConfigurationError)
    assert error.code == "VECTOR_STORE_CONFIGURATION_ERROR"
    assert error.retryable is False
    assert error.__cause__ is original


@pytest.mark.parametrize("status_code", [404, 409, 418, 429])
def test_other_4xx_responses_are_permanent_service_errors(status_code):
    original = unexpected_response(status_code)

    error = normalize_qdrant_error(original)

    assert isinstance(error, VectorStoreServiceError)
    assert error.code == "VECTOR_STORE_SERVICE_ERROR"
    assert error.retryable is False
    assert error.__cause__ is original


def test_unknown_status_is_a_permanent_service_error():
    original = unexpected_response(None)

    error = normalize_qdrant_error(original)

    assert isinstance(error, VectorStoreServiceError)
    assert error.retryable is False


def test_resource_exhausted_response_is_a_permanent_service_error():
    original = ResourceExhaustedResponse("resource exhausted", retry_after_s=30)

    error = normalize_qdrant_error(original)

    assert isinstance(error, VectorStoreServiceError)
    assert error.code == "VECTOR_STORE_SERVICE_ERROR"
    assert error.retryable is False
    assert error.__cause__ is original
    assert "resource exhausted" not in str(error)


@pytest.mark.parametrize(
    "timeout",
    [
        httpx.ConnectTimeout("connect timed out"),
        httpx.ReadTimeout("read timed out"),
        httpx.WriteTimeout("write timed out"),
        httpx.PoolTimeout("pool timed out"),
    ],
)
def test_direct_timeouts_map_to_retryable_timeout_errors(timeout):
    error = normalize_qdrant_error(timeout)

    assert isinstance(error, VectorStoreTimeout)
    assert error.code == "VECTOR_STORE_TIMEOUT"
    assert error.retryable is True
    assert error.__cause__ is timeout


def test_direct_connection_failure_maps_to_retryable_unavailable_error():
    original = httpx.ConnectError("not reachable")

    error = normalize_qdrant_error(original)

    assert isinstance(error, VectorStoreUnavailable)
    assert error.code == "VECTOR_STORE_UNAVAILABLE"
    assert error.retryable is True
    assert error.__cause__ is original


@pytest.mark.parametrize(
    ("source", "expected_type", "retryable"),
    [
        (httpx.ReadTimeout("read timed out"), VectorStoreTimeout, True),
        (httpx.ConnectError("not reachable"), VectorStoreUnavailable, True),
        (ValueError("malformed response"), VectorStoreServiceError, False),
    ],
)
def test_wrapped_exceptions_are_classified_from_their_source(
    source, expected_type, retryable
):
    original = ResponseHandlingException(source)

    error = normalize_qdrant_error(original)

    assert isinstance(error, expected_type)
    assert error.retryable is retryable
    assert error.__cause__ is original
    assert original.source is source


def test_unknown_exception_maps_to_a_permanent_service_error():
    original = RuntimeError("unknown failure")

    error = normalize_qdrant_error(original)

    assert isinstance(error, VectorStoreServiceError)
    assert error.code == "VECTOR_STORE_SERVICE_ERROR"
    assert error.retryable is False
    assert error.__cause__ is original


def test_already_normalized_error_is_returned_unchanged():
    original = VectorStoreTimeout("timed out")

    assert normalize_qdrant_error(original) is original


def test_application_facing_errors_do_not_leak_bodies_headers_or_secrets():
    original = UnexpectedResponse(
        status_code=500,
        reason_phrase="secret-reason",
        content=b"secret-body",
        headers=httpx.Headers({"authorization": "secret-token"}),
    )

    error = normalize_qdrant_error(original)
    rendered = f"{error} {error!r}"

    assert "secret-body" not in rendered
    assert "secret-reason" not in rendered
    assert "secret-token" not in rendered


def _imported_modules(module) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_adapter_does_not_import_settings_startup_or_persistence_layers():
    modules = _imported_modules(adapter_module)
    forbidden_roots = (
        "app.core",
        "app.main",
        "app.llm",
        "app.infrastructure",
        "fastapi",
        "sqlalchemy",
        "psycopg",
    )

    for module in modules:
        assert not any(
            module == root or module.startswith(f"{root}.")
            for root in forbidden_roots
        ), module
