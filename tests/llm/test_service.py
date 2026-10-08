import pytest

from app.llm.contracts import LLMRequest, LLMResponse
from app.llm.providers.base import LLMProvider
from app.llm.services.llm_service import LLMService


class FakeLLMProvider(LLMProvider):

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content="Service test response",
            model=request.model,
            provider="fake",
        )


@pytest.mark.asyncio
async def test_llm_service_delegates_to_provider():
    provider = FakeLLMProvider()
    service = LLMService(provider)

    request = LLMRequest(
        system_prompt="You are a support assistant.",
        user_prompt="I need help.",
        model="test-model",
    )

    response = await service.generate(request)

    assert response.content == "Service test response"
    assert response.provider == "fake"
    assert response.model == "test-model"