"""Offline tests for generation verification identity validation and activation."""

from types import SimpleNamespace

import httpx
import pytest
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

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
    VectorGenerationNotFound,
)
from app.rag.vector_storage.qdrant_adapter import QdrantClientAdapter
from app.rag.vector_storage.retry import QdrantRetryPolicy

GENERATION_ID = "a" * 64
OTHER_GENERATION_ID = "b" * 64
EMBEDDING_CONFIG_ID = "c" * 64
OTHER_EMBEDDING_CONFIG_ID = "d" * 64
COLLECTION = f"knowledge_vectors_g_{GENERATION_ID}"
OTHER_COLLECTION = f"knowledge_vectors_g_{OTHER_GENERATION_ID}"

VALID_METADATA = {
    "generation_id": GENERATION_ID,
    "embedding_config_id": EMBEDDING_CONFIG_ID,
    "metadata_schema_version": "v1",
}


def collection_info(
    *, size=VECTOR_DIMENSION, distance=models.Distance.COSINE, count=3,
    metadata=VALID_METADATA,
):
    return SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors=models.VectorParams(size=size, distance=distance)
            ),
            metadata=metadata,
        ),
        points_count=count,
    )


def not_found_error():
    """A genuine Qdrant 404, as observed at the SDK boundary."""
    return UnexpectedResponse(
        status_code=404,
        reason_phrase="Not Found",
        content=b"missing",
        headers=httpx.Headers(),
    )


class FakeQdrantClient:
    def __init__(
        self, *, collection=None, aliases=None, alias_result=True,
        alias_error=None, upsert_error=None, get_collection_error=None
    ):
        self.collection = collection or collection_info()
        self.aliases = dict(aliases or {})
        self.alias_result = alias_result
        self.alias_error = alias_error
        self.upsert_error = upsert_error
        self.get_collection_error = get_collection_error
        self.get_collection_calls = []
        self.count_calls = []
        self.get_aliases_calls = 0
        self.alias_operations = []

    def get_collection(self, *, collection_name):
        self.get_collection_calls.append(collection_name)
        if self.get_collection_error is not None:
            raise self.get_collection_error
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


def assert_no_qdrant_side_effects(client):
    assert client.alias_operations == []
    assert client.get_aliases_calls == 0


def verify_request(*, count=3, embedding_config_id=EMBEDDING_CONFIG_ID):
    return VerifyGenerationRequest(GENERATION_ID, embedding_config_id, count)


# 1. Valid metadata and matching request identity.
def test_verify_generation_returns_result_only_for_matching_schema_and_count():
    client = FakeQdrantClient()
    adapter = make_adapter(client)

    result = adapter.verify_generation(verify_request())

    assert result.generation_id == GENERATION_ID
    assert result.expected_point_count == 3
    assert result.actual_point_count == 3
    assert result.vector_size == VECTOR_DIMENSION
    assert result.distance == "Cosine"
    assert client.get_collection_calls == [COLLECTION]
    assert client.count_calls == [(COLLECTION, True)]
    assert_no_qdrant_side_effects(client)


# 2-10. Every collection-metadata failure mode: BUILD_FAILED, no count, no alias.
@pytest.mark.parametrize(
    "metadata",
    [
        pytest.param(None, id="missing-metadata"),
        pytest.param(
            {"generation_id": GENERATION_ID, "metadata_schema_version": "v1"},
            id="missing-embedding-config-id",
        ),
        pytest.param(
            {"embedding_config_id": EMBEDDING_CONFIG_ID,
             "metadata_schema_version": "v1"},
            id="missing-generation-id",
        ),
        pytest.param(
            {"generation_id": GENERATION_ID,
             "embedding_config_id": EMBEDDING_CONFIG_ID},
            id="missing-metadata-schema-version",
        ),
        pytest.param(
            {"generation_id": "A" * 64,
             "embedding_config_id": EMBEDDING_CONFIG_ID,
             "metadata_schema_version": "v1"},
            id="malformed-generation-digest",
        ),
        pytest.param(
            {"generation_id": GENERATION_ID,
             "embedding_config_id": "not-a-digest",
             "metadata_schema_version": "v1"},
            id="malformed-embedding-digest",
        ),
        pytest.param(
            {"generation_id": GENERATION_ID,
             "embedding_config_id": EMBEDDING_CONFIG_ID,
             "metadata_schema_version": "v2"},
            id="unsupported-schema-version",
        ),
        pytest.param(
            {"generation_id": OTHER_GENERATION_ID,
             "embedding_config_id": EMBEDDING_CONFIG_ID,
             "metadata_schema_version": "v1"},
            id="stored-generation-id-mismatch",
        ),
        pytest.param(
            {"generation_id": GENERATION_ID,
             "embedding_config_id": OTHER_EMBEDDING_CONFIG_ID,
             "metadata_schema_version": "v1"},
            id="stored-embedding-config-id-mismatch",
        ),
        pytest.param(
            {**VALID_METADATA, "unexpected_field": "value"},
            id="extra-metadata-field",
        ),
    ],
)
def test_verify_generation_rejects_invalid_collection_metadata(metadata):
    client = FakeQdrantClient(collection=collection_info(metadata=metadata))

    with pytest.raises(VectorGenerationBuildFailed) as caught:
        make_adapter(client).verify_generation(verify_request())

    assert caught.value.code == "VECTOR_GENERATION_BUILD_FAILED"
    assert client.get_collection_calls == [COLLECTION]
    assert client.count_calls == []
    assert_no_qdrant_side_effects(client)


# 11. A zero-point generation is valid when everything else is valid.
def test_verify_generation_accepts_valid_zero_point_generation():
    client = FakeQdrantClient(collection=collection_info(count=0))

    result = make_adapter(client).verify_generation(verify_request(count=0))

    assert result.expected_point_count == 0
    assert result.actual_point_count == 0
    assert result.embedding_config_id == EMBEDDING_CONFIG_ID
    assert client.count_calls == [(COLLECTION, True)]
    assert_no_qdrant_side_effects(client)


# 12. A zero-point generation with invalid metadata fails closed.
def test_verify_generation_rejects_invalid_zero_point_generation_metadata():
    client = FakeQdrantClient(
        collection=collection_info(
            count=0,
            metadata={
                **VALID_METADATA,
                "embedding_config_id": OTHER_EMBEDDING_CONFIG_ID,
            },
        )
    )

    with pytest.raises(VectorGenerationBuildFailed) as caught:
        make_adapter(client).verify_generation(verify_request(count=0))

    assert caught.value.code == "VECTOR_GENERATION_BUILD_FAILED"
    assert client.count_calls == []
    assert_no_qdrant_side_effects(client)


# 13-14. Existing exact count, dimension, and distance checks remain.
# The `None` case is a generic (non-404) read failure and stays BUILD_FAILED.
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
        make_adapter(client).verify_generation(verify_request(count=expected_count))
    assert caught.value.code == "VECTOR_GENERATION_BUILD_FAILED"
    assert_no_qdrant_side_effects(client)


# 15. A genuinely missing collection retains not-found, not identity failure.
def test_verify_generation_missing_collection_retains_not_found_error():
    client = FakeQdrantClient(get_collection_error=not_found_error())

    with pytest.raises(VectorGenerationNotFound) as caught:
        make_adapter(client).verify_generation(verify_request())

    assert caught.value.code == "VECTOR_GENERATION_NOT_FOUND"
    assert client.get_collection_calls == [COLLECTION]
    assert client.count_calls == []
    assert_no_qdrant_side_effects(client)


# 16. Failed verification never establishes an activation precondition.
def test_failed_verification_does_not_populate_activation_precondition():
    client = FakeQdrantClient(collection=collection_info(metadata=None))
    adapter = make_adapter(client)

    with pytest.raises(VectorGenerationBuildFailed):
        adapter.verify_generation(verify_request())
    with pytest.raises(VectorGenerationActivationFailed):
        adapter.activate_generation(ActivateGenerationRequest(GENERATION_ID))

    assert ACTIVE_GENERATION_ALIAS not in client.aliases
    assert_no_qdrant_side_effects(client)


# 17. A failed activation-time re-verification leaves the active alias intact.
def test_failed_activation_reverification_does_not_modify_active_alias():
    client = FakeQdrantClient(aliases={ACTIVE_GENERATION_ALIAS: OTHER_COLLECTION})
    adapter = make_adapter(client)
    adapter.verify_generation(verify_request())
    client.collection = collection_info(
        metadata={
            **VALID_METADATA,
            "embedding_config_id": OTHER_EMBEDDING_CONFIG_ID,
        }
    )

    with pytest.raises(VectorGenerationActivationFailed):
        adapter.activate_generation(ActivateGenerationRequest(GENERATION_ID))

    assert client.aliases == {ACTIVE_GENERATION_ALIAS: OTHER_COLLECTION}
    assert_no_qdrant_side_effects(client)


# 18. The result exposes only the validated embedding identity.
def test_successful_verification_result_exposes_validated_embedding_identity():
    client = FakeQdrantClient()

    result = make_adapter(client).verify_generation(verify_request())

    assert result.embedding_config_id == EMBEDDING_CONFIG_ID
    assert result.generation_id == GENERATION_ID
    assert client.get_collection_calls == [COLLECTION]
    assert_no_qdrant_side_effects(client)


def test_activation_requires_successful_verification():
    client = FakeQdrantClient()
    with pytest.raises(VectorGenerationActivationFailed):
        make_adapter(client).activate_generation(
            ActivateGenerationRequest(GENERATION_ID)
        )
    assert_no_qdrant_side_effects(client)


def test_first_activation_creates_the_fixed_alias_atomically():
    client = FakeQdrantClient()
    adapter = make_adapter(client)
    adapter.verify_generation(verify_request())

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
    adapter.verify_generation(verify_request())

    result = adapter.activate_generation(ActivateGenerationRequest(GENERATION_ID))

    assert result.previous_generation_id == OTHER_GENERATION_ID
    assert client.aliases == {ACTIVE_GENERATION_ALIAS: COLLECTION}
    operations = client.alias_operations[0]
    assert len(operations) == 2
    assert operations[0].delete_alias.alias_name == ACTIVE_GENERATION_ALIAS
    assert operations[1].create_alias.collection_name == COLLECTION


# 20. Activation re-verification reuses the exact verified identity and count.
def test_activation_reverification_uses_previously_verified_identity_and_count():
    client = FakeQdrantClient()
    adapter = make_adapter(client)
    verified_request = verify_request()
    adapter.verify_generation(verified_request)

    observed_requests = []
    original_verify = adapter.verify_generation

    def capturing_verify(request):
        observed_requests.append(request)
        return original_verify(request)

    adapter.verify_generation = capturing_verify

    result = adapter.activate_generation(ActivateGenerationRequest(GENERATION_ID))

    assert observed_requests == [verified_request]
    assert observed_requests[0].embedding_config_id == EMBEDDING_CONFIG_ID
    assert observed_requests[0].expected_point_count == 3
    assert result.generation_id == GENERATION_ID
    assert client.aliases == {ACTIVE_GENERATION_ALIAS: COLLECTION}


def test_activation_reverifies_generation_before_alias_update():
    client = FakeQdrantClient()
    adapter = make_adapter(client)
    adapter.verify_generation(verify_request())
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
    adapter.verify_generation(verify_request())

    with pytest.raises(VectorGenerationActivationFailed):
        adapter.activate_generation(ActivateGenerationRequest(GENERATION_ID))

    assert client.aliases == {ACTIVE_GENERATION_ALIAS: OTHER_COLLECTION}


def test_lost_alias_response_is_reconciled_against_server_state():
    client = FakeQdrantClient(alias_error="commit_then_timeout")
    adapter = make_adapter(client)
    adapter.verify_generation(verify_request())

    result = adapter.activate_generation(ActivateGenerationRequest(GENERATION_ID))

    assert result.generation_id == GENERATION_ID
    assert client.aliases == {ACTIVE_GENERATION_ALIAS: COLLECTION}


def test_unconfirmed_alias_operation_without_state_change_is_not_success():
    client = FakeQdrantClient(alias_result=False)
    adapter = make_adapter(client)
    adapter.verify_generation(verify_request())

    with pytest.raises(VectorGenerationActivationFailed):
        adapter.activate_generation(ActivateGenerationRequest(GENERATION_ID))

    assert client.aliases == {}


# 19. Any point upsert invalidates the prior verified precondition.
def test_upsert_invalidates_prior_verification_before_activation():
    client = FakeQdrantClient()
    adapter = make_adapter(client)
    adapter.verify_generation(verify_request())
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

    assert client.alias_operations == []
    assert ACTIVE_GENERATION_ALIAS not in client.aliases


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

    with pytest.raises(VectorGenerationBuildFailed):
        adapter.upsert_points(UpsertPointsRequest(GENERATION_ID, [point]))

    assert client.aliases == {ACTIVE_GENERATION_ALIAS: OTHER_COLLECTION}
    assert client.alias_operations == []
