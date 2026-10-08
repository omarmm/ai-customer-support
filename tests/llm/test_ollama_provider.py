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