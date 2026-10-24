"""Immutable contracts and deterministic identity for document embeddings.

Construction validates the invariants of §5.2, §6.2, and §6.3 on every path,
including direct construction. Collections are normalized to immutable tuples
so ordering, derived counts, and identity cannot drift from the stored data.

The expected embedding dimension is provisional until T270 measures the live
model. No value in this module asserts that the live model returns 768.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

EMBEDDING_PROVIDER = "ollama"
EMBEDDING_MODEL = "nomic-embed-text:v1.5"
EMBEDDING_IDENTITY = f"{EMBEDDING_PROVIDER}:{EMBEDDING_MODEL}"

# Provisional and unverified until T270 measures the live model output.
PROVISIONAL_EMBEDDING_DIMENSION = 768

DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "
EMBEDDING_NORMALIZATION = "none"
EMBEDDINGS_ALGORITHM_VERSION = "embeddings-v1"

__all__ = [
    "DOCUMENT_PREFIX",
    "EMBEDDINGS_ALGORITHM_VERSION",
    "EMBEDDING_IDENTITY",
    "EMBEDDING_MODEL",
    "EMBEDDING_NORMALIZATION",
    "EMBEDDING_PROVIDER",
    "PROVISIONAL_EMBEDDING_DIMENSION",
    "QUERY_PREFIX",
    "ChunkEmbedding",
    "EmbeddingConfig",
    "EmbeddingResult",
]


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    return value


def _require_non_negative_int(value: Any, field: str) -> int:
    _require_int(value, field)
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


@dataclass(frozen=True)
class EmbeddingConfig:
    """Effective configuration identity for an embedding run."""

    provider: str = EMBEDDING_PROVIDER
    model: str = EMBEDDING_MODEL
    dimension: int = PROVISIONAL_EMBEDDING_DIMENSION
    document_prefix: str = DOCUMENT_PREFIX
    query_prefix: str = QUERY_PREFIX
    normalization: str = EMBEDDING_NORMALIZATION
    algorithm_version: str = EMBEDDINGS_ALGORITHM_VERSION

    def __post_init__(self) -> None:
        _require_non_empty_string(self.provider, "provider")
        _require_non_empty_string(self.model, "model")
        _require_non_empty_string(self.document_prefix, "document_prefix")
        _require_non_empty_string(self.query_prefix, "query_prefix")
        _require_non_empty_string(self.normalization, "normalization")
        _require_non_empty_string(self.algorithm_version, "algorithm_version")

        _require_int(self.dimension, "dimension")
        if self.dimension <= 0:
            raise ValueError("dimension must be greater than zero")

        if self.normalization != EMBEDDING_NORMALIZATION:
            raise ValueError("normalization must be 'none' in V1")

    @property
    def config_id(self) -> str:
        """Deterministic lowercase SHA-256 of the canonical configuration."""
        return _canonical_sha256(
            {
                "algorithm_version": self.algorithm_version,
                "dimension": self.dimension,
                "document_prefix": self.document_prefix,
                "model": self.model,
                "normalization": self.normalization,
                "provider": self.provider,
                "query_prefix": self.query_prefix,
            }
        )


@dataclass(frozen=True)
class ChunkEmbedding:
    """The embedding vector for one chunk, without retaining chunk text."""

    chunk_id: str
    document_id: str
    source_path: str
    chunk_index: int
    start_offset: int
    end_offset: int
    chunking_config_id: str
    embedding_config_id: str
    vector: tuple[float, ...]

    def __post_init__(self) -> None:
        _require_non_empty_string(self.chunk_id, "chunk_id")
        _require_non_empty_string(self.document_id, "document_id")
        _require_non_empty_string(self.source_path, "source_path")
        _require_non_empty_string(self.chunking_config_id, "chunking_config_id")
        _require_non_empty_string(self.embedding_config_id, "embedding_config_id")

        _require_non_negative_int(self.chunk_index, "chunk_index")
        _require_non_negative_int(self.start_offset, "start_offset")
        _require_non_negative_int(self.end_offset, "end_offset")

        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must be greater than start_offset")

        try:
            vector = tuple(self.vector)
        except TypeError:
            raise ValueError("vector must be a sequence of finite numbers") from None
        if not vector:
            raise ValueError("vector must be non-empty")

        normalized: list[float] = []
        for index, value in enumerate(vector):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"vector[{index}] must be a finite number")
            if not math.isfinite(value):
                raise ValueError(f"vector[{index}] must be finite")
            normalized.append(float(value))

        object.__setattr__(self, "vector", tuple(normalized))


@dataclass(frozen=True)
class EmbeddingResult:
    """The aggregate embedding result for one successful service run."""

    config: EmbeddingConfig
    embeddings: tuple[ChunkEmbedding, ...] = ()
    retry_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.config, EmbeddingConfig):
            raise ValueError("config must be an EmbeddingConfig")

        try:
            embeddings = tuple(self.embeddings)
        except TypeError:
            raise ValueError("embeddings must be an iterable") from None
        object.__setattr__(self, "embeddings", embeddings)

        _require_non_negative_int(self.retry_count, "retry_count")

        seen: set[str] = set()
        for embedding in embeddings:
            if not isinstance(embedding, ChunkEmbedding):
                raise ValueError("embeddings must contain ChunkEmbedding values")

            if embedding.chunk_id in seen:
                raise ValueError(f"duplicate chunk_id: {embedding.chunk_id}")
            seen.add(embedding.chunk_id)

            if embedding.embedding_config_id != self.config.config_id:
                raise ValueError(
                    "embedding embedding_config_id must match result config"
                )
            if len(embedding.vector) != self.config.dimension:
                raise ValueError("embedding vector length must match dimension")

            for value in embedding.vector:
                if not math.isfinite(value):
                    raise ValueError("embedding vector values must be finite")

    @property
    def count(self) -> int:
        return len(self.embeddings)

    @property
    def by_chunk_id(self) -> Mapping[str, ChunkEmbedding]:
        """Read-only mapping from chunk ID to its embedding."""
        return MappingProxyType(
            {embedding.chunk_id: embedding for embedding in self.embeddings}
        )
