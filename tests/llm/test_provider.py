import pytest

from app.llm.contracts import LLMRequest, LLMResponse
from app.llm.providers.base import LLMProvider


class FakeLLMProvider(LLMProvider):

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content=f"Fake response for: {request.user_prompt}",
            model=request.model,
            provider="fake",
        )


@pytest.mark.asyncio
async def test_provider_returns_normalized_response():
    provider = FakeLLMProvider()

    request = LLMRequest(
        system_prompt="You are a support assistant.",
        user_prompt="I want a refund.",
        model="test-model",
    )

    response = await provider.generate(request)

    assert isinstance(response, LLMResponse)
    assert response.content == "Fake response for: I want a refund."
    assert response.model == "test-model"
    assert response.provider == "fake"