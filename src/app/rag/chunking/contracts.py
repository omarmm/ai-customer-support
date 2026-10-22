"""Immutable contracts and deterministic identifiers for document chunking.

Construction validates the invariants of §7.4 on every path, including direct
construction. Collections are normalized to immutable tuples, so ordering,
derived counts, and identity cannot drift from the stored data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

ALGORITHM_VERSION = "chunking-v1"

__all__ = [
    "ALGORITHM_VERSION",
    "Chunk",
    "ChunkingConfig",
    "ChunkingResult",
    "DocumentChunking",
    "compute_chunk_id",
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


@dataclass(frozen=True)
class ChunkingConfig:
    """Effective configuration identity for a chunking run."""

    max_tokens: int
    overlap_tokens: int
    tokenizer_id: str
    algorithm_version: str = ALGORITHM_VERSION

    def __post_init__(self) -> None:
        _require_int(self.max_tokens, "max_tokens")
        _require_int(self.overlap_tokens, "overlap_tokens")

        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be greater than zero")
        if self.overlap_tokens < 0:
            raise ValueError("overlap_tokens must be non-negative")
        if self.overlap_tokens >= self.max_tokens:
            raise ValueError("overlap_tokens must be less than max_tokens")
        if not isinstance(self.tokenizer_id, str) or not self.tokenizer_id.strip():
            raise ValueError("tokenizer_id must be a non-empty string")
        if (
            not isinstance(self.algorithm_version, str)
            or not self.algorithm_version.strip()
        ):
            raise ValueError("algorithm_version must be a non-empty string")

    @property
    def config_id(self) -> str:
        """Deterministic lowercase SHA-256 of the canonical configuration."""
        return _canonical_sha256(
            {
                "algorithm_version": self.algorithm_version,
                "max_tokens": self.max_tokens,
                "overlap_tokens": self.overlap_tokens,
                "tokenizer_id": self.tokenizer_id,
            }
        )


def compute_chunk_id(
    *,
    chunking_config_id: str,
    document_id: str,
    source_path: str,
    start_offset: int,
    end_offset: int,
    content: str,
) -> str:
    """Return the deterministic chunk ID defined in §8.4.

    ``source_path`` is part of the payload so identical content at different
    paths produces distinct chunk IDs.
    """
    return _canonical_sha256(
        {
            "chunking_config_id": chunking_config_id,
            "document_id": document_id,
            "source_path": source_path,
            "start_offset": start_offset,
            "end_offset": end_offset,
            "content": content,
        }
    )


@dataclass(frozen=True)
class Chunk:
    """A retrieval-sized, exact source slice of one knowledge document."""

    chunk_id: str
    document_id: str
    source_path: str
    title: str
    format: str
    content: str
    start_offset: int
    end_offset: int
    token_start: int
    token_end: int
    token_count: int
    chunk_index: int
    chunking_config_id: str

    def __post_init__(self) -> None:
        _require_non_negative_int(self.start_offset, "start_offset")
        _require_non_negative_int(self.end_offset, "end_offset")
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must be greater than start_offset")

        _require_non_negative_int(self.token_start, "token_start")
        _require_non_negative_int(self.token_end, "token_end")
        if self.token_end <= self.token_start:
            raise ValueError("token_end must be greater than token_start")

        _require_int(self.token_count, "token_count")
        if self.token_count != self.token_end - self.token_start:
            raise ValueError("token_count must equal token_end - token_start")

        _require_non_negative_int(self.chunk_index, "chunk_index")

        if not isinstance(self.content, str):
            raise ValueError("content must be a string")
        if len(self.content) != self.end_offset - self.start_offset:
            raise ValueError("content length must equal end_offset - start_offset")

    @classmethod
    def build(
        cls,
        *,
        document_id: str,
        source_path: str,
        title: str,
        format: str,
        content: str,
        start_offset: int,
        end_offset: int,
        token_start: int,
        token_end: int,
        chunk_index: int,
        chunking_config_id: str,
    ) -> "Chunk":
        """Construct a chunk and derive its deterministic ID and token count."""
        return cls(
            chunk_id=compute_chunk_id(
                chunking_config_id=chunking_config_id,
                document_id=document_id,
                source_path=source_path,
                start_offset=start_offset,
                end_offset=end_offset,
                content=content,
            ),
            document_id=document_id,
            source_path=source_path,
            title=title,
            format=format,
            content=content,
            start_offset=start_offset,
            end_offset=end_offset,
            token_start=token_start,
            token_end=token_end,
            token_count=token_end - token_start,
            chunk_index=chunk_index,
            chunking_config_id=chunking_config_id,
        )

    @property
    def char_count(self) -> int:
        return self.end_offset - self.start_offset


@dataclass(frozen=True)
class DocumentChunking:
    """The chunking outcome for one knowledge document."""

    document_id: str
    source_path: str
    title: str
    format: str
    content_length: int
    token_count: int
    chunks: tuple[Chunk, ...] = ()

    def __post_init__(self) -> None:
        _require_non_negative_int(self.content_length, "content_length")
        _require_non_negative_int(self.token_count, "token_count")

        chunks = tuple(sorted(self.chunks, key=lambda chunk: chunk.chunk_index))
        object.__setattr__(self, "chunks", chunks)

        if self.content_length == 0:
            if self.token_count != 0:
                raise ValueError("content_length 0 requires token_count 0")
            if chunks:
                raise ValueError("content_length 0 requires no chunks")

        if self.token_count == 0:
            if chunks:
                raise ValueError("token_count 0 requires no chunks")
            return

        if not chunks:
            raise ValueError("token_count greater than 0 requires chunks")

        previous: Chunk | None = None
        for position, chunk in enumerate(chunks):
            if chunk.chunk_index != position:
                raise ValueError("chunk indexes must be contiguous from 0")
            if (
                chunk.document_id != self.document_id
                or chunk.source_path != self.source_path
                or chunk.title != self.title
                or chunk.format != self.format
            ):
                raise ValueError("chunk metadata must match the enclosing document")
            if chunk.token_end > self.token_count:
                raise ValueError("chunk token_end exceeds document token_count")
            if chunk.end_offset > self.content_length:
                raise ValueError("chunk end_offset exceeds document content_length")

            if previous is not None:
                if not (
                    chunk.token_start > previous.token_start
                    and chunk.token_start <= previous.token_end
                ):
                    raise ValueError(
                        "chunk token ranges must advance without gaps"
                    )
                if not (
                    chunk.start_offset > previous.start_offset
                    and chunk.start_offset <= previous.end_offset
                ):
                    raise ValueError(
                        "chunk source ranges must advance without gaps"
                    )

            previous = chunk

        if chunks[0].token_start != 0:
            raise ValueError("first chunk must start at token 0")
        if chunks[-1].token_end != self.token_count:
            raise ValueError("last chunk must end at document token_count")
        if chunks[0].start_offset != 0:
            raise ValueError("first chunk must start at offset 0")
        if chunks[-1].end_offset != self.content_length:
            raise ValueError("last chunk must end at content_length")

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)


@dataclass(frozen=True)
class ChunkingResult:
    """The aggregate chunking result for every input document."""

    config: ChunkingConfig
    documents: tuple[DocumentChunking, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.config, ChunkingConfig):
            raise ValueError("config must be a ChunkingConfig")

        documents = tuple(
            sorted(
                self.documents,
                key=lambda document: (document.source_path, document.document_id),
            )
        )
        object.__setattr__(self, "documents", documents)

        seen: set[tuple[str, str]] = set()
        for document in documents:
            key = (document.source_path, document.document_id)
            if key in seen:
                raise ValueError("duplicate (source_path, document_id) pair")
            seen.add(key)

            for chunk in document.chunks:
                if chunk.chunking_config_id != self.config.config_id:
                    raise ValueError(
                        "chunk chunking_config_id must match result config"
                    )
                if chunk.token_count > self.config.max_tokens:
                    raise ValueError("chunk token_count exceeds max_tokens")

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def chunk_count(self) -> int:
        return sum(document.chunk_count for document in self.documents)

    @property
    def total_token_count(self) -> int:
        return sum(document.token_count for document in self.documents)

    @property
    def chunks(self) -> tuple[Chunk, ...]:
        return tuple(
            chunk for document in self.documents for chunk in document.chunks
        )

    @property
    def has_chunks(self) -> bool:
        return self.chunk_count > 0
