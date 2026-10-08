import json
import os

import httpx

from app.llm.contracts import LLMRequest, LLMResponse, LLMUsage
from app.llm.providers.base import LLMProvider
from app.llm.providers.exceptions import (
    LLMProviderConnectionError,
    LLMProviderHTTPError,
    LLMProviderResponseError,
    LLMProviderTimeoutError,
)


class OllamaProvider(LLMProvider):

    def __init__(
        self,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = (
            base_url
            or os.getenv(
                "OLLAMA_BASE_URL",
                "http://host.docker.internal:11434",
            )
        ).rstrip("/")

        self.transport = transport

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": request.model,
            "messages": [
                {
                    "role": "system",
                    "content": request.system_prompt,
                },
                {
                    "role": "user",
                    "content": request.user_prompt,
                },
            ],
            "stream": False,
            "options": {
                "temperature": request.temperature,
            },
        }

        try:
            async with httpx.AsyncClient(
                timeout=request.timeout,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )

        except httpx.ConnectError as exc:
            raise LLMProviderConnectionError(
                "Unable to connect to Ollama"
            ) from exc

        except httpx.TimeoutException as exc:
            raise LLMProviderTimeoutError(
                "Ollama request timed out"
            ) from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderHTTPError(
                response.status_code
            ) from exc

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise LLMProviderResponseError(
                "Ollama returned invalid JSON"
            ) from exc

        try:
            content = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMProviderResponseError(
                "Ollama response is missing message.content"
            ) from exc

        input_tokens = data.get("prompt_eval_count")
        output_tokens = data.get("eval_count")

        total_tokens = None

        if input_tokens is not None or output_tokens is not None:
            total_tokens = (input_tokens or 0) + (output_tokens or 0)

        usage = LLMUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

        return LLMResponse(
            content=content,
            model=data.get("model", request.model),
            provider="ollama",
            usage=usage,
        )