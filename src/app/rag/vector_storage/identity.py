"""Deterministic identity primitives for knowledge vector storage."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID, uuid5

PROJECT_VECTOR_NAMESPACE = UUID("452d7fec-5a06-47c6-801d-eb0363eec5c4")


def canonical_sha256(payload: dict[str, object]) -> str:
    """Return the lowercase SHA-256 digest of canonical UTF-8 JSON."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def point_id_for_chunk(chunk_id: str) -> UUID:
    """Derive a stable Qdrant point ID from the original chunk identity."""
    if not isinstance(chunk_id, str) or not chunk_id.strip():
        raise ValueError("chunk_id must be a non-empty string")
    return uuid5(PROJECT_VECTOR_NAMESPACE, chunk_id)
