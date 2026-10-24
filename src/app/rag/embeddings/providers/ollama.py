"""Ollama adapter for the embedding endpoint.

The adapter owns Ollama-specific interpretation of HTTP failures. It sends
already-prefixed texts to ``POST {base_url}/api/embed``, validates the response
envelope, and raises only the provider-layer exceptions defined in
``providers.exceptions``. Raw ``httpx`` exceptions and response bodies never
escape this module.

The adapter does not call Ollama model metadata endpoints, does not verify the
served model digest, and does not validate vector count, dimension, or
finiteness. Those are service invariants (specification §6.1 and §7.3).
"""

from __future__ import annotations

import json
from typing import Sequence

import httpx

from app.rag.embeddings.contracts import EMBEDDING_IDENTITY, EMBEDDING_MODEL
from app.rag.embeddings.providers.exceptions import (
    EmbeddingProviderAuthenticationError,
    EmbeddingProviderConnectionError,
    EmbeddingProviderHTTPError,
    EmbeddingProviderInvalidRequestError,
    EmbeddingProviderModelMismatchError,
    EmbeddingProviderModelNotFoundError,
    EmbeddingProviderRateLimitError,
    EmbeddingProviderResponseError,
    EmbeddingProviderTimeoutError,
    EmbeddingProviderUnavailableError,
)

EMBED_PATH = "/api/embed"

__all__ = ["OllamaEmbeddingProvider"]


def _classify_http_error(status_code: int) -> EmbeddingProviderHTTPError:
    """Classify an Ollama HTTP error using Ollama-specific semantics.

    Mirrors the existing Ollama LLM adapter. This mapping is intentionally local
    to the Ollama adapter and must not be generalized to other providers.
    """

    if status_code == 429:
        return EmbeddingProviderRateLimitError(status_code)

    if status_code in (401, 403):
        return EmbeddingProviderAuthenticationError(status_code)

    if status_code in (400, 422):
        return EmbeddingProviderInvalidRequestError(status_code)

    if status_code == 404:
        return EmbeddingProviderModelNotFoundError(status_code)

    if 500 <= status_code <= 599:
        return EmbeddingProviderUnavailableError(status_code)

    return EmbeddingProviderHTTPError(status_code)


class OllamaEmbeddingProvider:
    """Generate chunk embeddings through Ollama's ``POST /api/embed``."""

    def __init__(
        self,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url must be a non-empty string")

        # The base URL is supplied explicitly by the composition root from the
        # approved ``settings.ollama_url`` setting (D-6). No environment
        # variable is read here.
        self.base_url = base_url.rstrip("/")
        self.transport = transport

    @property
    def identity(self) -> str:
        return EMBEDDING_IDENTITY

    async def embed(
        self,
        texts: Sequence[str],
        *,
        timeout: float,
    ) -> tuple[tuple[float, ...], ...]:
        payload = {
            "model": EMBEDDING_MODEL,
            "input": list(texts),
        }

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    f"{self.base_url}{EMBED_PATH}",
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise EmbeddingProviderTimeoutError(
                "embedding request timed out"
            ) from exc
        except httpx.HTTPError as exc:
            raise EmbeddingProviderConnectionError(
                "unable to reach the embedding provider"
            ) from exc

        if response.status_code >= 400:
            # The response body is never included in the error.
            raise _classify_http_error(response.status_code)

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise EmbeddingProviderResponseError("invalid_json") from exc

        if not isinstance(data, dict):
            raise EmbeddingProviderResponseError("malformed_response")

        model = data.get("model")
        if not isinstance(model, str) or model != EMBEDDING_MODEL:
            raise EmbeddingProviderModelMismatchError()

        if "embeddings" not in data:
            raise EmbeddingProviderResponseError("missing_embeddings")

        embeddings = data["embeddings"]
        if not isinstance(embeddings, list):
            raise EmbeddingProviderResponseError("malformed_response")

        vectors: list[tuple[float, ...]] = []
        for vector in embeddings:
            if not isinstance(vector, list):
                raise EmbeddingProviderResponseError("malformed_response")

            values: list[float] = []
            for value in vector:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise EmbeddingProviderResponseError("malformed_response")
                values.append(float(value))
            vectors.append(tuple(values))

        return tuple(vectors)
