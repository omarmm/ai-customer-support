"""Offline tests for T275 Qdrant generation creation and point upsert."""

from types import SimpleNamespace

import httpx
import pytest
from qdrant_client.http import models

from app.rag.vector_storage.contracts import (
    VECTOR_DIMENSION,
    CreateGenerationRequest,
    UpsertPointInput,
    UpsertPointsRequest,
)
from app.rag.vector_storage.exceptions import (
    VectorGenerationBuildFailed,
    VectorStoreUnavailable,
)
from app.rag.vector_storage.qdrant_adapter import QdrantClientAdapter
from app.rag.vector_storage.retry import QdrantRetryPolicy

GENERATION_ID = "a" * 64
EMBEDDING_CONFIG_ID = "b" * 64


def make_payload(chunk_id: str, *, chunk_index: int = 0) -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
        "document_id": "document-001",
        "source_path": "knowledge/policy.md",
        "title": "Policy",
        "format": "md",
        "content": f"Chunk content for {chunk_id}",
        "start_offset": chunk_index * 20,
        "end_offset": chunk_index * 20 + 10,
        "chunk_index": chunk_index,
        "chunking_config_id": "c" * 64,
        "embedding_config_id": EMBEDDING_CONFIG_ID,
    }


def make_point(chunk_id: str, *, chunk_index: int = 0, value: float = 0.25):
    return UpsertPointInput(
        chunk_id=chunk_id,
        vector=[value] * VECTOR_DIMENSION,
        payload=make_payload(chunk_id, chunk_index=chunk_index),
    )


class FakeQdrantClient:
    def __init__(
        self,
        *,
        create_collection_result=True,
        index_status=models.UpdateStatus.COMPLETED,
        upsert_status=models.UpdateStatus.COMPLETED,
    ):
        self.create_collection_result = create_collection_result
        self.index_status = index_status
        self.upsert_status = upsert_status
        self.collection_calls = []
        self.index_calls = []
        self.upsert_calls = []

    def create_collection(self, **kwargs):
        self.collection_calls.append(kwargs)
        return self.create_collection_result

    def create_payload_index(self, **kwargs):
        self.index_calls.append(kwargs)
        return SimpleNamespace(status=self.index_status)

    def upsert(self, **kwargs):
        self.upsert_calls.append(kwargs)
        return SimpleNamespace(status=self.upsert_status)

    def close(self):
        pass


def make_adapter(client):
    return QdrantClientAdapter(
        client,
        retry_policy=QdrantRetryPolicy(max_attempts=1),
        sleep=lambda _: None,
    )


def test_create_generation_uses_fixed_collection_vector_schema_and_exact_indexes():
    client = FakeQdrantClient()
    adapter = make_adapter(client)

    result = adapter.create_generation(
        CreateGenerationRequest(GENERATION_ID, EMBEDDING_CONFIG_ID, VECTOR_DIMENSION)
    )

    assert result.generation_id == GENERATION_ID
    assert result.collection_name == f"knowledge_vectors_g_{GENERATION_ID}"
    assert result.vector_size == VECTOR_DIMENSION
    assert result.distance == "Cosine"

    assert len(client.collection_calls) == 1
    collection_call = client.collection_calls[0]
    assert collection_call["collection_name"] == result.collection_name
    assert collection_call["vectors_config"].size == VECTOR_DIMENSION
    assert collection_call["vectors_config"].distance is models.Distance.COSINE

    expected_indexes = [
        ("generation_id", models.PayloadSchemaType.KEYWORD),
        ("document_id", models.PayloadSchemaType.KEYWORD),
        ("source_path", models.PayloadSchemaType.KEYWORD),
        ("format", models.PayloadSchemaType.KEYWORD),
        ("chunking_config_id", models.PayloadSchemaType.KEYWORD),
        ("embedding_config_id", models.PayloadSchemaType.KEYWORD),
        ("chunk_index", models.PayloadSchemaType.INTEGER),
    ]
    assert [
        (call["field_name"], call["field_schema"]) for call in client.index_calls
    ] == expected_indexes
    assert all(call["wait"] is True for call in client.index_calls)


def test_create_generation_fails_when_collection_creation_is_not_confirmed():
    client = FakeQdrantClient(create_collection_result=False)

    with pytest.raises(VectorGenerationBuildFailed) as caught:
        make_adapter(client).create_generation(
            CreateGenerationRequest(GENERATION_ID, EMBEDDING_CONFIG_ID, VECTOR_DIMENSION)
        )

    assert caught.value.code == "VECTOR_GENERATION_BUILD_FAILED"
    assert client.index_calls == []


def test_create_generation_fails_when_any_payload_index_is_not_confirmed():
    client = FakeQdrantClient(index_status=models.UpdateStatus.ACKNOWLEDGED)

    with pytest.raises(VectorGenerationBuildFailed) as caught:
        make_adapter(client).create_generation(
            CreateGenerationRequest(GENERATION_ID, EMBEDDING_CONFIG_ID, VECTOR_DIMENSION)
        )

    assert caught.value.code == "VECTOR_GENERATION_BUILD_FAILED"
    assert len(client.index_calls) == 1


def test_create_generation_wraps_normalized_qdrant_failures():
    class BrokenClient(FakeQdrantClient):
        def create_collection(self, **kwargs):
            raise httpx.ConnectError("unavailable")

    with pytest.raises(VectorGenerationBuildFailed) as caught:
        make_adapter(BrokenClient()).create_generation(
            CreateGenerationRequest(GENERATION_ID, EMBEDDING_CONFIG_ID, VECTOR_DIMENSION)
        )

    assert caught.value.code == "VECTOR_GENERATION_BUILD_FAILED"
    assert isinstance(caught.value.underlying_error, VectorStoreUnavailable)
    assert isinstance(caught.value.__cause__, httpx.ConnectError)


def test_upsert_points_preserves_batch_order_and_adds_generation_to_payload():
    client = FakeQdrantClient()
    adapter = make_adapter(client)
    first = make_point("chunk-001", chunk_index=0, value=0.1)
    second = make_point("chunk-002", chunk_index=1, value=0.2)
    request = UpsertPointsRequest(GENERATION_ID, [first, second])

    result = adapter.upsert_points(request)

    assert result.generation_id == GENERATION_ID
    assert result.submitted_count == 2
    assert result.completed_count == 2
    assert result.succeeded is True

    assert len(client.upsert_calls) == 1
    call = client.upsert_calls[0]
    assert call["collection_name"] == f"knowledge_vectors_g_{GENERATION_ID}"
    assert call["wait"] is True
    assert [point.payload["chunk_id"] for point in call["points"]] == [
        "chunk-001",
        "chunk-002",
    ]
    assert [point.vector[0] for point in call["points"]] == [0.1, 0.2]
    assert [point.payload["generation_id"] for point in call["points"]] == [
        GENERATION_ID,
        GENERATION_ID,
    ]
    assert [point.id for point in call["points"]] == [
        str(first.point_id),
        str(second.point_id),
    ]
    assert all("generation_id" not in point.payload for point in request.points)


@pytest.mark.parametrize(
    "status",
    [models.UpdateStatus.ACKNOWLEDGED, models.UpdateStatus.COMPLETED],
)
def test_upsert_points_requires_completed_batch(status):
    client = FakeQdrantClient(upsert_status=status)

    if status is models.UpdateStatus.COMPLETED:
        result = make_adapter(client).upsert_points(
            UpsertPointsRequest(GENERATION_ID, [make_point("chunk-001")])
        )
        assert result.succeeded is True
        return

    with pytest.raises(VectorGenerationBuildFailed) as caught:
        make_adapter(client).upsert_points(
            UpsertPointsRequest(GENERATION_ID, [make_point("chunk-001")])
        )

    assert caught.value.code == "VECTOR_GENERATION_BUILD_FAILED"


def test_upsert_points_wraps_transport_failure_without_false_success():
    class BrokenClient(FakeQdrantClient):
        def upsert(self, **kwargs):
            raise httpx.ConnectError("connection lost after request")

    with pytest.raises(VectorGenerationBuildFailed) as caught:
        make_adapter(BrokenClient()).upsert_points(
            UpsertPointsRequest(GENERATION_ID, [make_point("chunk-001")])
        )

    assert caught.value.code == "VECTOR_GENERATION_BUILD_FAILED"
    assert isinstance(caught.value.underlying_error, VectorStoreUnavailable)
    assert isinstance(caught.value.__cause__, VectorStoreUnavailable)


def test_upsert_points_rejects_non_application_request_before_qdrant_io():
    client = FakeQdrantClient()

    with pytest.raises(TypeError):
        make_adapter(client).upsert_points(object())

    assert client.upsert_calls == []
