"""Embedding service: batching, ordering, validation, and bounded retries.

The service owns every invariant the provider adapter deliberately leaves to a
higher layer: vector count, non-empty batch output, dimension, and finiteness
(specification §7.3). It preserves input order across batches, rejects duplicate
chunk IDs before any provider call, and aborts the whole run on the first failed
batch. It performs no persistence and imports no LLM, Qdrant, database, or HTTP
framework module.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable, Iterable, Sequence

from app.rag.chunking.contracts import Chunk
from app.rag.embeddings.contracts import (
    DOCUMENT_PREFIX,
    ChunkEmbedding,
    EmbeddingConfig,
    EmbeddingResult,
)
from app.rag.embeddings.exceptions import (
    EmbeddingConfigurationError,
    EmbeddingError,
    EmbeddingResponseError,
    EmbeddingUnexpectedError,
    normalize_provider_error,
)
from app.rag.embeddings.providers.base import EmbeddingProvider
from app.rag.embeddings.providers.exceptions import EmbeddingProviderError
from app.rag.embeddings.retry import EmbeddingRetryPolicy

DEFAULT_BATCH_SIZE = 16
DEFAULT_TIMEOUT = 30.0

__all__ = ["DEFAULT_BATCH_SIZE", "DEFAULT_TIMEOUT", "EmbeddingService"]


def _require_positive_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _require_positive_number(value: object, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{field} must be a positive finite number")
    return float(value)


class EmbeddingService:
    """Embed chunks with one effective configuration per service."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        config: EmbeddingConfig | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: EmbeddingRetryPolicy | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        if config is not None and not isinstance(config, EmbeddingConfig):
            raise ValueError("config must be an EmbeddingConfig")

        self._provider = provider
        self._config = config if config is not None else EmbeddingConfig()
        self._batch_size = _require_positive_int(batch_size, "batch_size")
        self._timeout = _require_positive_number(timeout, "timeout")

        if retry_policy is not None and not isinstance(
            retry_policy, EmbeddingRetryPolicy
        ):
            raise ValueError("retry_policy must be an EmbeddingRetryPolicy")
        self._retry_policy = (
            retry_policy if retry_policy is not None else EmbeddingRetryPolicy()
        )
        self._sleep = sleep if sleep is not None else asyncio.sleep

        identity = getattr(provider, "identity", None)
        expected_identity = f"{self._config.provider}:{self._config.model}"
        if not isinstance(identity, str) or identity != expected_identity:
            raise EmbeddingConfigurationError(
                "embedding provider identity does not match the configured "
                "provider and model"
            )

    @classmethod
    def from_settings(
        cls,
        settings,
        provider: EmbeddingProvider,
    ) -> "EmbeddingService":
        """Build a service from a settings object without reading globals."""
        return cls(
            provider=provider,
            batch_size=settings.embedding_batch_size,
            timeout=settings.embedding_timeout_seconds,
            retry_policy=EmbeddingRetryPolicy.from_settings(settings),
        )

    @property
    def config(self) -> EmbeddingConfig:
        """The effective configuration used for every embedding in this service."""
        return self._config

    async def embed_chunks(self, chunks: Iterable[Chunk]) -> EmbeddingResult:
        """Embed every input chunk, preserving input order across batches."""
        inputs = tuple(chunks)

        if not inputs:
            return EmbeddingResult(
                config=self._config,
                embeddings=(),
                retry_count=0,
            )

        seen: set[str] = set()
        for chunk in inputs:
            if chunk.chunk_id in seen:
                raise ValueError("duplicate chunk_id")
            seen.add(chunk.chunk_id)

        embeddings: list[ChunkEmbedding] = []
        retry_count = 0

        for start in range(0, len(inputs), self._batch_size):
            batch = inputs[start : start + self._batch_size]
            vectors, retry_count = await self._embed_batch(batch, retry_count)
            self._validate_batch(batch, vectors, retry_count)
            embeddings.extend(
                self._to_chunk_embedding(chunk, vector)
                for chunk, vector in zip(batch, vectors)
            )

        return EmbeddingResult(
            config=self._config,
            embeddings=tuple(embeddings),
            retry_count=retry_count,
        )

    async def _embed_batch(
        self,
        batch: Sequence[Chunk],
        retry_count: int,
    ) -> tuple[tuple[tuple[float, ...], ...], int]:
        """Embed one batch, retrying retryable failures up to the limit.

        ``retry_count`` is the number of additional attempts already performed
        in this service call. The returned count includes retries spent in this
        batch.
        """
        texts = tuple(DOCUMENT_PREFIX + chunk.content for chunk in batch)
        attempt = 0

        while True:
            try:
                vectors = await self._provider.embed(texts, timeout=self._timeout)
            except EmbeddingError:
                # Already an application-level error; do not re-normalize and do
                # not retry it here.
                raise
            except EmbeddingProviderError as exc:
                error = normalize_provider_error(exc)
                cause = exc
            except Exception as exc:
                unexpected = EmbeddingUnexpectedError(
                    "unexpected error during embedding"
                )
                unexpected.retry_count = retry_count
                raise unexpected from exc
            else:
                return tuple(vectors), retry_count

            if not error.retryable or attempt >= self._retry_policy.max_retries:
                error.retry_count = retry_count
                raise error from cause

            await self._sleep(self._retry_policy.delay_for_attempt(attempt))
            attempt += 1
            retry_count += 1

    def _validate_batch(
        self,
        batch: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
        retry_count: int,
    ) -> None:
        """Enforce the service-layer response invariants of §7.3."""
        if not vectors:
            self._raise_response_error("empty_embeddings", retry_count)

        if len(vectors) != len(batch):
            self._raise_response_error("count_mismatch", retry_count)

        for vector in vectors:
            if len(vector) != self._config.dimension:
                self._raise_response_error("dimension_mismatch", retry_count)

            for value in vector:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    # The provider contract rejects these; a provider that
                    # violates it must not leak a raw TypeError.
                    self._raise_response_error("malformed_response", retry_count)
                if not math.isfinite(value):
                    self._raise_response_error("non_finite_value", retry_count)

    @staticmethod
    def _raise_response_error(reason: str, retry_count: int) -> None:
        error = EmbeddingResponseError(reason)
        error.retry_count = retry_count
        raise error

    def _to_chunk_embedding(
        self,
        chunk: Chunk,
        vector: Sequence[float],
    ) -> ChunkEmbedding:
        return ChunkEmbedding(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            source_path=chunk.source_path,
            chunk_index=chunk.chunk_index,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            chunking_config_id=chunk.chunking_config_id,
            embedding_config_id=self._config.config_id,
            vector=tuple(float(value) for value in vector),
        )
