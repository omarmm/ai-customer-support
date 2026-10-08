import pytest

from app.llm.contracts import LLMRequest
from app.llm.providers.ollama import OllamaProvider


@pytest.mark.asyncio
async def test_ollama_real_integration():
    provider = OllamaProvider(
        base_url="http://host.docker.internal:11434"
    )

    request = LLMRequest(
        system_prompt="You are a customer support assistant.",
        user_prompt="Reply with exactly: integration test passed",
        model="qwen3:8b",
        temperature=0.0,
        timeout=60.0,
    )

    response = await provider.generate(request)

    assert response.provider == "ollama"
    assert response.model == "qwen3:8b"
    assert response.content

    print(f"\nLLM response: {response.content}")
    print(f"Usage: {response.usage}")