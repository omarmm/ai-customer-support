from app.llm.contracts import LLMRequest, LLMResponse
from app.llm.providers.base import LLMProvider


class LLMService:

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return await self.provider.generate(request)