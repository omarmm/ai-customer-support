"""Immutable application contracts for knowledge vector storage."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol
from uuid import UUID

VECTOR_DIMENSION = 768
MAX_UPSERT_BATCH_SIZE = 64
ACTIVE_GENERATION_ALIAS = "knowledge_vectors_active"
GENERATION_ID_PATTERN = re.compile(r"[0-9a-f]{64}\Z")

PAYLOAD_FIELDS = frozenset(
    {
        "chunk_id",
        "document_id",
        "source_path",
        "title",
        "format",
        "content",
        "start_offset",
        "end_offset",
        "chunk_index",
        "chunking_config_id",
        "embedding_config_id",
    }
)
_PAYLOAD_STRING_FIELDS = (
    "document_id",
    "source_path",
    "title",
    "format",
    "content",
    "chunking_config_id",
    "embedding_config_id",
)
_PAYLOAD_INTEGER_FIELDS = ("start_offset", "end_offset", "chunk_index")


def _require_generation_id(value: object, field: str = "generation_id") -> str:
    if not isinstance(value, str) or GENERATION_ID_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field} must be exactly 64 lowercase hexadecimal characters")
    return value


def _require_non_empty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    return value


def _require_non_negative_int(value: object, field: str) -> int:
    _require_int(value, field)
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


def _validate_payload(payload: Mapping[str, object], chunk_id: str) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    keys = set(payload)
    if keys != PAYLOAD_FIELDS:
        missing = sorted(PAYLOAD_FIELDS - keys)
        unknown = sorted(keys - PAYLOAD_FIELDS)
        raise ValueError(f"payload fields mismatch (missing={missing}, unknown={unknown})")

    for field in _PAYLOAD_STRING_FIELDS:
        if not isinstance(payload[field], str):
            raise ValueError(f"payload.{field} must be a string")
    _require_non_empty_string(payload["chunk_id"], "payload.chunk_id")
    for field in _PAYLOAD_INTEGER_FIELDS:
        _require_non_negative_int(payload[field], f"payload.{field}")

    if payload["end_offset"] <= payload["start_offset"]:
        raise ValueError("payload.end_offset must be greater than payload.start_offset")
    if payload["chunk_id"] != chunk_id:
        raise ValueError("payload.chunk_id must match chunk_id")
    return MappingProxyType(dict(payload))


@dataclass(frozen=True)
class CreateGenerationRequest:
    generation_id: str
    embedding_config_id: str
    vector_size: int

    def __post_init__(self) -> None:
        _require_generation_id(self.generation_id)
        _require_generation_id(self.embedding_config_id, "embedding_config_id")
        _require_int(self.vector_size, "vector_size")
        if self.vector_size != VECTOR_DIMENSION:
            raise ValueError(f"vector_size must equal {VECTOR_DIMENSION} in V1")


@dataclass(frozen=True)
class CollectionInfo:
    generation_id: str
    collection_name: str
    vector_size: int
    distance: str

    def __post_init__(self) -> None:
        _require_generation_id(self.generation_id)
        if self.collection_name != f"knowledge_vectors_g_{self.generation_id}":
            raise ValueError("collection_name does not match generation_id")
        _require_int(self.vector_size, "vector_size")
        if self.vector_size <= 0:
            raise ValueError("vector_size must be positive")
        if self.distance != "Cosine":
            raise ValueError("distance must be 'Cosine'")


@dataclass(frozen=True)
class UpsertPointInput:
    chunk_id: str
    vector: tuple[float, ...]
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        _require_non_empty_string(self.chunk_id, "chunk_id")
        try:
            vector = tuple(self.vector)
        except TypeError:
            raise ValueError("vector must be a sequence of finite numbers") from None
        if len(vector) != VECTOR_DIMENSION:
            raise ValueError(f"vector must contain exactly {VECTOR_DIMENSION} values")
        normalized: list[float] = []
        for index, value in enumerate(vector):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"vector[{index}] must be a finite number")
            if not math.isfinite(value):
                raise ValueError(f"vector[{index}] must be finite")
            normalized.append(float(value))
        object.__setattr__(self, "vector", tuple(normalized))
        object.__setattr__(self, "payload", _validate_payload(self.payload, self.chunk_id))

    @property
    def point_id(self) -> UUID:
        from app.rag.vector_storage.identity import point_id_for_chunk

        return point_id_for_chunk(self.chunk_id)


@dataclass(frozen=True)
class UpsertPointsRequest:
    generation_id: str
    points: tuple[UpsertPointInput, ...]

    def __post_init__(self) -> None:
        _require_generation_id(self.generation_id)
        try:
            points = tuple(self.points)
        except TypeError:
            raise ValueError("points must be an iterable") from None
        if not 1 <= len(points) <= MAX_UPSERT_BATCH_SIZE:
            raise ValueError(f"points must contain between 1 and {MAX_UPSERT_BATCH_SIZE} items")
        if any(not isinstance(point, UpsertPointInput) for point in points):
            raise ValueError("points must contain UpsertPointInput values")
        chunk_ids = [point.chunk_id for point in points]
        if len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError("chunk_id values must be unique within a batch")
        point_ids = [point.point_id for point in points]
        if len(set(point_ids)) != len(point_ids):
            raise ValueError("derived point IDs must be unique within a batch")
        object.__setattr__(self, "points", points)


@dataclass(frozen=True)
class UpsertPointsResult:
    generation_id: str
    submitted_count: int
    completed_count: int
    succeeded: bool

    def __post_init__(self) -> None:
        _require_generation_id(self.generation_id)
        _require_non_negative_int(self.submitted_count, "submitted_count")
        _require_non_negative_int(self.completed_count, "completed_count")
        if not isinstance(self.succeeded, bool):
            raise ValueError("succeeded must be a boolean")
        if self.submitted_count < 1 or self.submitted_count > MAX_UPSERT_BATCH_SIZE:
            raise ValueError("submitted_count must be between 1 and 64")
        if self.completed_count > self.submitted_count:
            raise ValueError("completed_count cannot exceed submitted_count")
        if not self.succeeded or self.completed_count != self.submitted_count:
            raise ValueError("a result may represent only a fully completed batch")


@dataclass(frozen=True)
class VerifyGenerationRequest:
    generation_id: str
    expected_point_count: int

    def __post_init__(self) -> None:
        _require_generation_id(self.generation_id)
        _require_non_negative_int(self.expected_point_count, "expected_point_count")


@dataclass(frozen=True)
class GenerationVerificationResult:
    generation_id: str
    expected_point_count: int
    actual_point_count: int
    vector_size: int
    distance: str

    def __post_init__(self) -> None:
        _require_generation_id(self.generation_id)
        _require_non_negative_int(self.expected_point_count, "expected_point_count")
        _require_non_negative_int(self.actual_point_count, "actual_point_count")
        _require_int(self.vector_size, "vector_size")
        if self.expected_point_count != self.actual_point_count:
            raise ValueError("point counts must match for a verified generation")
        if self.vector_size != VECTOR_DIMENSION:
            raise ValueError(f"vector_size must equal {VECTOR_DIMENSION}")
        if self.distance != "Cosine":
            raise ValueError("distance must be 'Cosine'")


@dataclass(frozen=True)
class ActivateGenerationRequest:
    generation_id: str

    def __post_init__(self) -> None:
        _require_generation_id(self.generation_id)


@dataclass(frozen=True)
class GenerationActivationResult:
    generation_id: str
    alias_name: str
    previous_generation_id: str | None

    def __post_init__(self) -> None:
        _require_generation_id(self.generation_id)
        if self.alias_name != ACTIVE_GENERATION_ALIAS:
            raise ValueError(f"alias_name must be {ACTIVE_GENERATION_ALIAS!r}")
        if self.previous_generation_id is not None:
            _require_generation_id(self.previous_generation_id, "previous_generation_id")


@dataclass(frozen=True)
class GetGenerationInfoRequest:
    generation_id: str

    def __post_init__(self) -> None:
        _require_generation_id(self.generation_id)


@dataclass(frozen=True)
class GenerationInfo:
    generation_id: str
    collection_name: str
    point_count: int
    vector_size: int
    distance: str
    is_active: bool

    def __post_init__(self) -> None:
        _require_generation_id(self.generation_id)
        expected_name = f"knowledge_vectors_g_{self.generation_id}"
        if self.collection_name != expected_name:
            raise ValueError("collection_name does not match generation_id")
        _require_non_negative_int(self.point_count, "point_count")
        _require_int(self.vector_size, "vector_size")
        if self.vector_size <= 0:
            raise ValueError("vector_size must be positive")
        _require_non_empty_string(self.distance, "distance")
        if not isinstance(self.is_active, bool):
            raise ValueError("is_active must be a boolean")


@dataclass(frozen=True)
class DeleteGenerationRequest:
    generation_id: str

    def __post_init__(self) -> None:
        _require_generation_id(self.generation_id)


@dataclass(frozen=True)
class GenerationDeletionResult:
    generation_id: str
    collection_name: str
    deleted: bool

    def __post_init__(self) -> None:
        _require_generation_id(self.generation_id)
        if self.collection_name != f"knowledge_vectors_g_{self.generation_id}":
            raise ValueError("collection_name does not match generation_id")
        if self.deleted is not True:
            raise ValueError("deleted must be True for a successful result")


class VectorStore(Protocol):
    """Application-owned storage port; search semantics belong to Retrieval SDD."""

    def create_generation(self, request: CreateGenerationRequest) -> CollectionInfo: ...

    def upsert_points(self, request: UpsertPointsRequest) -> UpsertPointsResult: ...

    def verify_generation(
        self, request: VerifyGenerationRequest
    ) -> GenerationVerificationResult: ...

    def activate_generation(
        self, request: ActivateGenerationRequest
    ) -> GenerationActivationResult: ...

    def search(self, request: object) -> object:
        """Reserved interface only; do not implement retrieval behavior."""
        ...

    def get_generation_info(self, request: GetGenerationInfoRequest) -> GenerationInfo: ...

    def delete_generation(self, request: DeleteGenerationRequest) -> GenerationDeletionResult: ...
