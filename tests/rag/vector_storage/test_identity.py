from uuid import UUID

import pytest

from app.rag.vector_storage.identity import (
    PROJECT_VECTOR_NAMESPACE,
    canonical_sha256,
    point_id_for_chunk,
)


def test_project_namespace_is_fixed():
    assert PROJECT_VECTOR_NAMESPACE == UUID("452d7fec-5a06-47c6-801d-eb0363eec5c4")


def test_point_id_is_deterministic_for_the_same_chunk():
    assert point_id_for_chunk("chunk-123") == point_id_for_chunk("chunk-123")


def test_point_id_uses_original_chunk_id_as_uuid5_name():
    expected = UUID("452d7fec-5a06-47c6-801d-eb0363eec5c4")
    from uuid import uuid5

    assert point_id_for_chunk("chunk-123") == uuid5(expected, "chunk-123")


def test_different_chunk_ids_produce_different_point_ids():
    assert point_id_for_chunk("chunk-a") != point_id_for_chunk("chunk-b")


@pytest.mark.parametrize("chunk_id", ["", " ", None, 123])
def test_point_id_rejects_invalid_chunk_id(chunk_id):
    with pytest.raises(ValueError, match="chunk_id"):
        point_id_for_chunk(chunk_id)


def test_canonical_sha256_uses_sorted_compact_utf8_json():
    assert canonical_sha256({"b": 2, "a": "é"}) == canonical_sha256({"a": "é", "b": 2})
