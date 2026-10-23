"""Aggregate knowledge document chunking through an injected tokenizer.

The service composes the pure per-document chunker into one deterministic run.
It never reads settings on its own: the composition root supplies configuration
directly or through ``from_settings``. Input order does not affect the result,
and every valid input document remains represented, including documents that
produce zero chunks.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.rag.chunking.chunker import chunk_document
from app.rag.chunking.contracts import ChunkingConfig, ChunkingResult
from app.rag.chunking.tokenizer import Tokenizer, validate_identity
from app.rag.ingestion.contracts import KnowledgeDocument

__all__ = ["ChunkingService"]

DEFAULT_MAX_TOKENS = 500
DEFAULT_OVERLAP_TOKENS = 75


class ChunkingService:
    """Chunk documents with one effective configuration per service."""

    def __init__(
        self,
        tokenizer: Tokenizer,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    ):
        self._tokenizer = tokenizer
        self._config = ChunkingConfig(
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            tokenizer_id=validate_identity(tokenizer.identity),
        )

    @classmethod
    def from_settings(cls, settings, tokenizer: Tokenizer) -> "ChunkingService":
        """Build a service from a settings object without reading globals."""
        return cls(
            tokenizer=tokenizer,
            max_tokens=settings.knowledge_chunk_max_tokens,
            overlap_tokens=settings.knowledge_chunk_overlap_tokens,
        )

    @property
    def config(self) -> ChunkingConfig:
        """The effective configuration used for every chunk in this service."""
        return self._config

    def chunk(self, documents: Iterable[KnowledgeDocument]) -> ChunkingResult:
        """Chunk every input document, preserving deterministic ordering."""
        inputs = tuple(documents)

        seen: set[tuple[str, str]] = set()
        for document in inputs:
            key = (document.source_path, document.document_id)
            if key in seen:
                raise ValueError("duplicate (source_path, document_id) pair")
            seen.add(key)

        results = tuple(
            chunk_document(document, self._tokenizer, self._config)
            for document in inputs
        )
        return ChunkingResult(config=self._config, documents=results)
