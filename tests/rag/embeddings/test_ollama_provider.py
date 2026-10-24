"""Offline tests for the Ollama embedding adapter.

Every test uses ``httpx.MockTransport``; no socket, Ollama instance, or metadata
endpoint is used. Tests cover the request and response contracts in
specification §4 and the provider behavior required by §11.2.
"""

import inspect
import json

import httpx
import pytest

from app.rag.embeddings.contracts import (
    EMBEDDING_IDENTITY,
    EMBEDDING_MODEL,
)
from app.rag.embeddings.providers import ollama as ollama_module
from app.rag.embeddings.providers.exceptions import (
    EmbeddingProviderAuthenticationError,
    EmbeddingProviderConnectionError,
    EmbeddingProviderHTTPError,
    EmbeddingProviderInvalidRequestError,
    EmbeddingProviderModelMismatchError,
    EmbeddingProviderModelNotFoundError,
    EmbeddingProviderRateLimitError,
    EmbeddingProviderResponseError,
    EmbeddingProviderTimeoutError,
    EmbeddingProviderUnavailableError,
)
from app.rag.embeddings.providers.ollama import OllamaEmbeddingProvider

BASE_URL = "http://ollama.test"
TIMEOUT = 2.5
TEXTS = (
    "search_document: Refunds are processed within 5-7 business days.",
    "search_document: Returns are accepted within 30 days.",
)


def make_provider(handler) -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(
        base_url=BASE_URL,
        transport=httpx.MockTransport(handler),
    )


def success_response(embeddings, model=EMBEDDING_MODEL) -> httpx.Response:
    return httpx.Response(200, json={"model": model, "embeddings": embeddings})


@pytest.mark.asyncio
async def test_embed_posts_request_contract():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return success_response([[0.1, -0.2, 0.3], [0.4, 0.5, -0.6]])

    provider = make_provider(handler)

    await provider.embed(TEXTS, timeout=TIMEOUT)

    assert len(seen) == 1
    request = seen[0]

    assert request.method == "POST"
    assert str(request.url) == f"{BASE_URL}/api/embed"
    assert json.loads(request.content) == {
        "model": EMBEDDING_MODEL,
        "input": list(TEXTS),
    }

    # The per-attempt timeout is applied to every HTTP timeout component.
    assert request.extensions["timeout"] == {
        "connect": TIMEOUT,
        "read": TIMEOUT,
        "write": TIMEOUT,
        "pool": TIMEOUT,
    }


@pytest.mark.asyncio
async def test_embed_returns_single_vector():
    provider = make_provider(
        lambda request: success_response([[0.1, 0.2, 0.3]])
    )

    vectors = await provider.embed(TEXTS[:1], timeout=TIMEOUT)

    assert vectors == ((0.1, 0.2, 0.3),)
    assert isinstance(vectors, tuple)
    assert isinstance(vectors[0], tuple)


@pytest.mark.asyncio
async def test_embed_preserves_order_for_multiple_vectors():
    provider = make_provider(
        lambda request: success_response([[1.0], [2.0], [3.0]])
    )

    vectors = await provider.embed(TEXTS + ("third",), timeout=TIMEOUT)

    assert vectors == ((1.0,), (2.0,), (3.0,))


@pytest.mark.asyncio
async def test_adapter_does_not_validate_dimension():
    # Dimension validation is a service invariant (§6.1). The adapter returns
    # whatever vectors the provider reported.
    provider = make_provider(
        lambda request: success_response([[0.1, 0.2], [0.3, 0.4, 0.5]])
    )

    vectors = await provider.embed(TEXTS, timeout=TIMEOUT)

    assert vectors == ((0.1, 0.2), (0.3, 0.4, 0.5))


@pytest.mark.asyncio
async def test_empty_embeddings_list_is_structurally_valid():
    provider = make_provider(
        lambda request: success_response([])
    )

    vectors = await provider.embed(TEXTS, timeout=TIMEOUT)

    assert vectors == ()


@pytest.mark.asyncio
async def test_missing_embeddings_raises_missing_embeddings():
    provider = make_provider(
        lambda request: httpx.Response(200, json={"model": EMBEDDING_MODEL})
    )

    with pytest.raises(EmbeddingProviderResponseError) as exc_info:
        await provider.embed(TEXTS, timeout=TIMEOUT)

    assert exc_info.value.reason == "missing_embeddings"


@pytest.mark.asyncio
@pytest.mark.parametrize("embeddings", [None, "vectors", {"0": [0.1]}, 1])
async def test_non_array_embeddings_raises_malformed_response(embeddings):
    provider = make_provider(
        lambda request: httpx.Response(
            200,
            json={"model": EMBEDDING_MODEL, "embeddings": embeddings},
        )
    )

    with pytest.raises(EmbeddingProviderResponseError) as exc_info:
        await provider.embed(TEXTS, timeout=TIMEOUT)

    assert exc_info.value.reason == "malformed_response"


@pytest.mark.asyncio
@pytest.mark.parametrize("vector", ["0.1", 0.1, {"x": 0.1}, None])
async def test_non_array_vector_raises_malformed_response(vector):
    provider = make_provider(
        lambda request: success_response([vector])
    )

    with pytest.raises(EmbeddingProviderResponseError) as exc_info:
        await provider.embed(TEXTS[:1], timeout=TIMEOUT)

    assert exc_info.value.reason == "malformed_response"


@pytest.mark.asyncio
@pytest.mark.parametrize("element", [True, False, "0.1", None, [0.1]])
async def test_invalid_vector_element_raises_malformed_response(element):
    provider = make_provider(
        lambda request: success_response([[0.1, element, 0.3]])
    )

    with pytest.raises(EmbeddingProviderResponseError) as exc_info:
        await provider.embed(TEXTS[:1], timeout=TIMEOUT)

    assert exc_info.value.reason == "malformed_response"


@pytest.mark.asyncio
async def test_non_object_json_raises_malformed_response():
    provider = make_provider(
        lambda request: httpx.Response(200, json=[1, 2, 3])
    )

    with pytest.raises(EmbeddingProviderResponseError) as exc_info:
        await provider.embed(TEXTS, timeout=TIMEOUT)

    assert exc_info.value.reason == "malformed_response"


@pytest.mark.asyncio
async def test_invalid_json_raises_invalid_json():
    provider = make_provider(
        lambda request: httpx.Response(
            200,
            content=b"not-json",
            headers={"content-type": "application/json"},
        )
    )

    with pytest.raises(EmbeddingProviderResponseError) as exc_info:
        await provider.embed(TEXTS, timeout=TIMEOUT)

    assert exc_info.value.reason == "invalid_json"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"model": 123, "embeddings": [[0.1]]},
        {"model": None, "embeddings": [[0.1]]},
        {"model": "other-model:latest", "embeddings": [[0.1]]},
        {"model": "nomic-embed-text", "embeddings": [[0.1]]},
    ],
)
async def test_model_identity_mismatch_is_permanent(payload):
    provider = make_provider(
        lambda request: httpx.Response(200, json=payload)
    )

    with pytest.raises(EmbeddingProviderModelMismatchError):
        await provider.embed(TEXTS[:1], timeout=TIMEOUT)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code, expected_error_type",
    [
        (429, EmbeddingProviderRateLimitError),
        (401, EmbeddingProviderAuthenticationError),
        (403, EmbeddingProviderAuthenticationError),
        (400, EmbeddingProviderInvalidRequestError),
        (422, EmbeddingProviderInvalidRequestError),
        (404, EmbeddingProviderModelNotFoundError),
        (500, EmbeddingProviderUnavailableError),
        (502, EmbeddingProviderUnavailableError),
        (503, EmbeddingProviderUnavailableError),
        (408, EmbeddingProviderHTTPError),
        (418, EmbeddingProviderHTTPError),
    ],
)
async def test_http_status_classification(status_code, expected_error_type):
    provider = make_provider(
        lambda request: httpx.Response(
            status_code,
            json={"error": "provider error"},
        )
    )

    with pytest.raises(expected_error_type) as exc_info:
        await provider.embed(TEXTS, timeout=TIMEOUT)

    assert type(exc_info.value) is expected_error_type
    assert exc_info.value.status_code == status_code


@pytest.mark.asyncio
async def test_http_error_message_does_not_include_response_body():
    provider = make_provider(
        lambda request: httpx.Response(
            500,
            json={"error": "secret-provider-body"},
        )
    )

    with pytest.raises(EmbeddingProviderUnavailableError) as exc_info:
        await provider.embed(TEXTS, timeout=TIMEOUT)

    assert "secret-provider-body" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_connection_error_maps_to_provider_connection_error():
    async def handler(request):
        raise httpx.ConnectError("connection failed")

    provider = make_provider(handler)

    with pytest.raises(EmbeddingProviderConnectionError):
        await provider.embed(TEXTS, timeout=TIMEOUT)


@pytest.mark.asyncio
async def test_timeout_maps_to_provider_timeout_error():
    async def handler(request):
        raise httpx.ReadTimeout("timed out")

    provider = make_provider(handler)

    with pytest.raises(EmbeddingProviderTimeoutError):
        await provider.embed(TEXTS, timeout=TIMEOUT)


@pytest.mark.asyncio
async def test_other_transport_error_does_not_leak_httpx_exception():
    async def handler(request):
        raise httpx.ReadError("transport failed")

    provider = make_provider(handler)

    with pytest.raises(EmbeddingProviderConnectionError):
        await provider.embed(TEXTS, timeout=TIMEOUT)


@pytest.mark.asyncio
async def test_adapter_never_calls_metadata_endpoints():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if len(paths) == 1:
            return success_response([[0.1]])
        return httpx.Response(200, json={"model": "wrong", "embeddings": [[0.1]]})

    provider = make_provider(handler)

    await provider.embed(TEXTS[:1], timeout=TIMEOUT)
    with pytest.raises(EmbeddingProviderModelMismatchError):
        await provider.embed(TEXTS[:1], timeout=TIMEOUT)

    assert paths == ["/api/embed", "/api/embed"]
    assert "/api/tags" not in paths
    assert "/api/show" not in paths


def test_adapter_does_not_claim_digest_verification():
    source = inspect.getsource(ollama_module)
    provider = OllamaEmbeddingProvider(base_url=BASE_URL)

    assert "/api/tags" not in source
    assert "/api/show" not in source
    assert not hasattr(provider, "digest")
    assert not hasattr(provider, "model_digest")
    assert provider.identity == EMBEDDING_IDENTITY
    assert "verified" not in provider.identity


def test_identity_is_the_pinned_provider_model_identity():
    provider = OllamaEmbeddingProvider(base_url=BASE_URL)

    assert provider.identity == EMBEDDING_IDENTITY
    assert provider.identity == "ollama:nomic-embed-text:v1.5"


def test_base_url_is_required_and_normalized():
    provider = OllamaEmbeddingProvider(base_url="http://ollama.test/")

    assert provider.base_url == "http://ollama.test"

    with pytest.raises(ValueError):
        OllamaEmbeddingProvider(base_url="")


@pytest.mark.asyncio
async def test_adapter_does_not_read_environment_variables(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"{BASE_URL}/api/embed"
        return success_response([[0.1]])

    monkeypatch.setenv("OLLAMA_URL", "http://from-environment.test")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://also-from-environment.test")

    provider = make_provider(handler)

    assert provider.base_url == BASE_URL
    await provider.embed(TEXTS[:1], timeout=TIMEOUT)
