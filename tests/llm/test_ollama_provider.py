import httpx
import pytest

from app.llm.contracts import LLMRequest, LLMResponse
from app.llm.providers.ollama import OllamaProvider


@pytest.mark.asyncio
async def test_ollama_provider_generates_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "http://ollama.test/api/chat"

        payload = request.read().decode()

        assert '"model":"qwen3:8b"' in payload
        assert '"stream":false' in payload

        return httpx.Response(
            200,
            json={
                "model": "qwen3:8b",
                "message": {
                    "role": "assistant",
                    "content": "Your refund request is being reviewed.",
                },
                "prompt_eval_count": 20,
                "eval_count": 10,
            },
        )

    transport = httpx.MockTransport(handler)

    provider = OllamaProvider(
        base_url="http://ollama.test",
        transport=transport,
    )

    request = LLMRequest(
        system_prompt="You are a customer support assistant.",
        user_prompt="I want a refund.",
        model="qwen3:8b",
    )

    response = await provider.generate(request)

    assert isinstance(response, LLMResponse)
    assert response.content == "Your refund request is being reviewed."
    assert response.model == "qwen3:8b"
    assert response.provider == "ollama"

    assert response.usage is not None
    assert response.usage.input_tokens == 20
    assert response.usage.output_tokens == 10
    assert response.usage.total_tokens == 30


def make_partial_provider(extra: dict) -> OllamaProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "qwen3:8b",
                "message": {
                    "role": "assistant",
                    "content": "Partial usage.",
                },
                **extra,
            },
        )

    return OllamaProvider(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    )


def make_partial_request() -> LLMRequest:
    return LLMRequest(
        system_prompt="You are a customer support assistant.",
        user_prompt="I want a refund.",
        model="qwen3:8b",
    )


@pytest.mark.asyncio
async def test_ollama_provider_does_not_invent_total_with_partial_counts():
    provider = make_partial_provider({"prompt_eval_count": 20})

    response = await provider.generate(make_partial_request())

    assert response.usage is not None
    assert response.usage.input_tokens == 20
    assert response.usage.output_tokens is None
    assert response.usage.total_tokens is None


@pytest.mark.asyncio
async def test_ollama_provider_preserves_total_when_counts_missing():
    provider = make_partial_provider({})

    response = await provider.generate(make_partial_request())

    assert response.usage is not None
    assert response.usage.input_tokens is None
    assert response.usage.output_tokens is None
    assert response.usage.total_tokens is None


@pytest.mark.asyncio
async def test_ollama_provider_preserves_provider_reported_total():
    provider = make_partial_provider(
        {
            "prompt_eval_count": 20,
            "eval_count": 10,
            "total_tokens": 99,
        }
    )

    response = await provider.generate(make_partial_request())

    assert response.usage is not None
    assert response.usage.input_tokens == 20
    assert response.usage.output_tokens == 10
    assert response.usage.total_tokens == 99