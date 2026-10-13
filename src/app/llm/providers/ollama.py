import json
import os

import httpx

from app.llm.contracts import LLMRequest, LLMResponse, LLMUsage
from app.llm.providers.base import LLMProvider
from app.llm.providers.exceptions import (
    LLMProviderAuthenticationError,
    LLMProviderConnectionError,
    LLMProviderHTTPError,
    LLMProviderInvalidRequestError,
    LLMProviderModelNotFoundError,
    LLMProviderRateLimitError,
    LLMProviderResponseError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
)


def _classify_http_error(status_code: int) -> LLMProviderHTTPError:
    """Classify an Ollama HTTP error using Ollama-specific semantics.

    This mapping is intentionally local to the Ollama adapter and must not be
    generalized to other providers.
    """

    if status_code == 429:
        return LLMProviderRateLimitError(status_code)

    if status_code in (401, 403):
        return LLMProviderAuthenticationError(status_code)

    if status_code in (400, 422):
        return LLMProviderInvalidRequestError(status_code)

    if status_code == 404:
        return LLMProviderModelNotFoundError(status_code)

    if 500 <= status_code <= 599:
        return LLMProviderUnavailableError(status_code)

    return LLMProviderHTTPError(status_code)


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
            raise _classify_http_error(
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

        # Preserve a provider-reported total when present. Otherwise derive it
        # only when both components are known; unknown stays None.
        total_tokens = data.get("total_tokens")

        if (
            total_tokens is None
            and input_tokens is not None
            and output_tokens is not None
        ):
            total_tokens = input_tokens + output_tokens

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