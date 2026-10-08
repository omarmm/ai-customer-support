import httpx
import pytest

from app.llm.contracts import LLMRequest
from app.llm.providers.exceptions import (
    LLMProviderConnectionError,
    LLMProviderHTTPError,
    LLMProviderResponseError,
    LLMProviderTimeoutError,
)
from app.llm.providers.ollama import OllamaProvider


def make_request() -> LLMRequest:
    return LLMRequest(
        system_prompt="You are a support assistant.",
        user_prompt="Hello",
        model="qwen3:8b",
        timeout=1.0,
    )


@pytest.mark.asyncio
async def test_connection_error():
    async def handler(request):
        raise httpx.ConnectError("connection failed")

    provider = OllamaProvider(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMProviderConnectionError):
        await provider.generate(make_request())


@pytest.mark.asyncio
async def test_timeout_error():
    async def handler(request):
        raise httpx.ReadTimeout("timeout")

    provider = OllamaProvider(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMProviderTimeoutError):
        await provider.generate(make_request())


@pytest.mark.asyncio
async def test_http_error():
    async def handler(request):
        return httpx.Response(
            500,
            json={"error": "internal error"},
        )

    provider = OllamaProvider(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMProviderHTTPError) as exc_info:
        await provider.generate(make_request())

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_invalid_json_response():
    async def handler(request):
        return httpx.Response(
            200,
            content=b"not-json",
        )

    provider = OllamaProvider(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMProviderResponseError):
        await provider.generate(make_request())


@pytest.mark.asyncio
async def test_malformed_response():
    async def handler(request):
        return httpx.Response(
            200,
            json={"model": "qwen3:8b"},
        )

    provider = OllamaProvider(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMProviderResponseError):
        await provider.generate(make_request())


@pytest.mark.asyncio
async def test_ollama_base_url_from_environment(monkeypatch):
    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        "http://custom-ollama:11434",
    )

    provider = OllamaProvider()

    assert provider.base_url == "http://custom-ollama:11434"