"""Offline tests for T276 generation verification and activation."""

from types import SimpleNamespace

import httpx
import pytest
from qdrant_client.http import models

from app.rag.vector_storage.contracts import (
    ACTIVE_GENERATION_ALIAS,
    VECTOR_DIMENSION,
    ActivateGenerationRequest,
    UpsertPointInput,
    UpsertPointsRequest,
    VerifyGenerationRequest,
)
from app.rag.vector_storage.exceptions import (
    VectorGenerationActivationFailed,
    VectorGenerationBuildFailed,
)
from app.rag.vector_storage.qdrant_adapter import QdrantClientAdapter
from app.rag.vector_storage.retry import QdrantRetryPolicy

GENERATION_ID = "a" * 64
OTHER_GENERATION_ID = "b" * 64
COLLECTION = f"knowledge_vectors_g_{GENERATION_ID}"
OTHER_COLLECTION = f"knowledge_vectors_g_{OTHER_GENERATION_ID}"


def collection_info(*, size=VECTOR_DIMENSION, distance=models.Distance.COSINE, count=3):
    return SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors=models.VectorParams(size=size, distance=distance)
            )
        ),
        points_count=count,
    )


class FakeQdrantClient:
    def __init__(
        self, *, collection=None, aliases=None, alias_result=True,
        alias_error=None, upsert_error=None
    ):
        self.collection = collection or collection_info()
        self.aliases = dict(aliases or {})
        self.alias_result = alias_result
        self.alias_error = alias_error
        self.upsert_error = upsert_error
        self.get_collection_calls = []
        self.count_calls = []
        self.get_aliases_calls = 0
        self.alias_operations = []

    def get_collection(self, *, collection_name):
        self.get_collection_calls.append(collection_name)
        return self.collection

    def count(self, *, collection_name, exact):
        self.count_calls.append((collection_name, exact))
        return SimpleNamespace(count=self.collection.points_count)

    def upsert(self, **kwargs):
        if self.upsert_error is not None:
            raise self.upsert_error
        return SimpleNamespace(status=models.UpdateStatus.COMPLETED)

    def get_aliases(self):
        self.get_aliases_calls += 1
        return SimpleNamespace(
            aliases=[
                SimpleNamespace(alias_name=alias, collection_name=collection)
                for alias, collection in self.aliases.items()
            ]
        )

    def update_collection_aliases(self, *, change_aliases_operations):
        self.alias_operations.append(change_aliases_operations)
        if self.alias_error is not None:
            if self.alias_error == "commit_then_timeout":
                for operation in change_aliases_operations:
                    if getattr(operation, "delete_alias", None) is not None:
                        self.aliases.pop(operation.delete_alias.alias_name, None)
                    if getattr(operation, "create_alias", None) is not None:
                        self.aliases[operation.create_alias.alias_name] = (
                            operation.create_alias.collection_name
                        )
                raise httpx.ReadTimeout("response lost after server commit")
            raise self.alias_error
        if self.alias_result is not True:
            return self.alias_result
        # Apply all operations as one simulated atomic transaction.
        next_aliases = dict(self.aliases)
        for operation in change_aliases_operations:
            delete_alias = getattr(operation, "delete_alias", None)
            create_alias = getattr(operation, "create_alias", None)
            if delete_alias is not None:
                next_aliases.pop(delete_alias.alias_name, None)
            if create_alias is not None:
                next_aliases[create_alias.alias_name] = create_alias.collection_name
        self.aliases = next_aliases
        return True


def make_adapter(client):
    return QdrantClientAdapter(
        client,
        retry_policy=QdrantRetryPolicy(max_attempts=1),
        sleep=lambda _: None,
    )


def test_verify_generation_returns_result_only_for_matching_schema_and_count():
    client = FakeQdrantClient()
    adapter = make_adapter(client)

    result = adapter.verify_generation(VerifyGenerationRequest(GENERATION_ID, 3))

    assert result.generation_id == GENERATION_ID
    assert result.expected_point_count == 3
    assert result.actual_point_count == 3
    assert result.vector_size == VECTOR_DIMENSION
    assert result.distance == "Cosine"
    assert client.get_collection_calls == [COLLECTION]
    assert client.count_calls == [(COLLECTION, True)]


@pytest.mark.parametrize(
    ("collection", "expected_count"),
    [
        (None, 3),
        (collection_info(size=384), 3),
        (collection_info(distance=models.Distance.DOT), 3),
        (collection_info(count=2), 3),
    ],
)
def test_verify_generation_rejects_missing_or_incompatible_generation(
    collection, expected_count
):
    client = (
        FakeQdrantClient(collection=collection) if collection else FakeQdrantClient()
    )
    if collection is None:
        client.get_collection = lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("collection missing")
        )
    with pytest.raises(VectorGenerationBuildFailed) as caught:
        make_adapter(client).verify_generation(
            VerifyGenerationRequest(GENERATION_ID, expected_count)
        )
    assert caught.value.code == "VECTOR_GENERATION_BUILD_FAILED"


def test_activation_requires_successful_verification():
    client = FakeQdrantClient()
    with pytest.raises(VectorGenerationActivationFailed):
        make_adapter(client).activate_generation(
            ActivateGenerationRequest(GENERATION_ID)
        )
    assert client.alias_operations == []


def test_first_activation_creates_the_fixed_alias_atomically():
    client = FakeQdrantClient()
    adapter = make_adapter(client)
    adapter.verify_generation(VerifyGenerationRequest(GENERATION_ID, 3))

    result = adapter.activate_generation(ActivateGenerationRequest(GENERATION_ID))

    assert result.generation_id == GENERATION_ID
    assert result.alias_name == ACTIVE_GENERATION_ALIAS
    assert result.previous_generation_id is None
    assert client.aliases == {ACTIVE_GENERATION_ALIAS: COLLECTION}
    assert len(client.alias_operations) == 1
    operations = client.alias_operations[0]
    assert len(operations) == 1
    assert operations[0].create_alias.alias_name == ACTIVE_GENERATION_ALIAS
    assert operations[0].create_alias.collection_name == COLLECTION


def test_replacement_activation_atomically_retains_previous_generation():
    client = FakeQdrantClient(aliases={ACTIVE_GENERATION_ALIAS: OTHER_COLLECTION})
    adapter = make_adapter(client)
    adapter.verify_generation(VerifyGenerationRequest(GENERATION_ID, 3))

    result = adapter.activate_generation(ActivateGenerationRequest(GENERATION_ID))

    assert result.previous_generation_id == OTHER_GENERATION_ID
    assert client.aliases == {ACTIVE_GENERATION_ALIAS: COLLECTION}
    operations = client.alias_operations[0]
    assert len(operations) == 2
    assert operations[0].delete_alias.alias_name == ACTIVE_GENERATION_ALIAS
    assert operations[1].create_alias.collection_name == COLLECTION


def test_activation_reverifies_generation_before_alias_update():
    client = FakeQdrantClient()
    adapter = make_adapter(client)
    adapter.verify_generation(VerifyGenerationRequest(GENERATION_ID, 3))
    client.collection = collection_info(count=2)

    with pytest.raises(VectorGenerationActivationFailed):
        adapter.activate_generation(ActivateGenerationRequest(GENERATION_ID))

    assert client.alias_operations == []
    assert ACTIVE_GENERATION_ALIAS not in client.aliases


def test_failed_atomic_alias_operation_preserves_previous_active_generation():
    client = FakeQdrantClient(
        aliases={ACTIVE_GENERATION_ALIAS: OTHER_COLLECTION},
        alias_error=RuntimeError("alias operation rejected"),
    )
    adapter = make_adapter(client)
    adapter.verify_generation(VerifyGenerationRequest(GENERATION_ID, 3))

    with pytest.raises(VectorGenerationActivationFailed):
        adapter.activate_generation(ActivateGenerationRequest(GENERATION_ID))

    assert client.aliases == {ACTIVE_GENERATION_ALIAS: OTHER_COLLECTION}


def test_lost_alias_response_is_reconciled_against_server_state():
    client = FakeQdrantClient(alias_error="commit_then_timeout")
    adapter = make_adapter(client)
    adapter.verify_generation(VerifyGenerationRequest(GENERATION_ID, 3))

    result = adapter.activate_generation(ActivateGenerationRequest(GENERATION_ID))

    assert result.generation_id == GENERATION_ID
    assert client.aliases == {ACTIVE_GENERATION_ALIAS: COLLECTION}


def test_unconfirmed_alias_operation_without_state_change_is_not_success():
    client = FakeQdrantClient(alias_result=False)
    adapter = make_adapter(client)
    adapter.verify_generation(VerifyGenerationRequest(GENERATION_ID, 3))

    with pytest.raises(VectorGenerationActivationFailed):
        adapter.activate_generation(ActivateGenerationRequest(GENERATION_ID))

    assert client.aliases == {}


def test_upsert_invalidates_prior_verification_before_activation():
    client = FakeQdrantClient()
    adapter = make_adapter(client)
    adapter.verify_generation(VerifyGenerationRequest(GENERATION_ID, 3))
    chunk_id = "chunk-after-verification"
    point = UpsertPointInput(
        chunk_id=chunk_id,
        vector=[0.1] * VECTOR_DIMENSION,
        payload={
            "chunk_id": chunk_id,
            "document_id": "document-001",
            "source_path": "knowledge/policy.md",
            "title": "Policy",
            "format": "md",
            "content": "A policy chunk",
            "start_offset": 0,
            "end_offset": 1,
            "chunk_index": 0,
            "chunking_config_id": "c" * 64,
            "embedding_config_id": "d" * 64,
        },
    )
    adapter.upsert_points(UpsertPointsRequest(GENERATION_ID, [point]))

    with pytest.raises(VectorGenerationActivationFailed):
        adapter.activate_generation(ActivateGenerationRequest(GENERATION_ID))


def test_failed_generation_build_does_not_change_the_active_alias():
    client = FakeQdrantClient(
        aliases={ACTIVE_GENERATION_ALIAS: OTHER_COLLECTION},
        upsert_error=RuntimeError("upsert failed"),
    )
    adapter = make_adapter(client)
    chunk_id = "failed-build-chunk"
    point = UpsertPointInput(
        chunk_id=chunk_id,
        vector=[0.1] * VECTOR_DIMENSION,
        payload={
            "chunk_id": chunk_id,
            "document_id": "document-001",
            "source_path": "knowledge/policy.md",
            "title": "Policy",
            "format": "md",
            "content": "A policy chunk",
            "start_offset": 0,
            "end_offset": 1,
            "chunk_index": 0,
            "chunking_config_id": "c" * 64,
            "embedding_config_id": "d" * 64,
        },
    )

    from app.rag.vector_storage.exceptions import VectorGenerationBuildFailed

    with pytest.raises(VectorGenerationBuildFailed):
        adapter.upsert_points(UpsertPointsRequest(GENERATION_ID, [point]))

    assert client.aliases == {ACTIVE_GENERATION_ALIAS: OTHER_COLLECTION}
    assert client.alias_operations == []
