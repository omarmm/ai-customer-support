from abc import ABC, abstractmethod

from app.llm.contracts import LLMRequest, LLMResponse


class LLMProvider(ABC):

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError