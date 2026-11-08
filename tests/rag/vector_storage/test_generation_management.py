"""Offline tests for T277 generation inspection and explicit deletion."""

from types import SimpleNamespace

import httpx
import pytest
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.rag.vector_storage.contracts import (
    ACTIVE_GENERATION_ALIAS,
    VECTOR_DIMENSION,
    DeleteGenerationRequest,
    GetGenerationInfoRequest,
)
from app.rag.vector_storage.exceptions import (
    VectorGenerationActiveDeleteRejected,
    VectorGenerationNotFound,
    VectorStoreServiceError,
    VectorStoreUnavailable,
)
from app.rag.vector_storage.qdrant_adapter import QdrantClientAdapter
from app.rag.vector_storage.retry import QdrantRetryPolicy

GENERATION_ID = "a" * 64
OTHER_GENERATION_ID = "b" * 64
COLLECTION = f"knowledge_vectors_g_{GENERATION_ID}"
OTHER_COLLECTION = f"knowledge_vectors_g_{OTHER_GENERATION_ID}"


def collection(*, size=VECTOR_DIMENSION, distance=models.Distance.COSINE):
    return SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors=models.VectorParams(size=size, distance=distance)
            )
        )
    )


def missing_collection():
    return UnexpectedResponse(
        status_code=404,
        reason_phrase="Not Found",
        content=b"missing",
        headers=httpx.Headers(),
    )


class FakeQdrantClient:
    def __init__(
        self,
        *,
        collections=None,
        aliases=None,
        exact_count=7,
        delete_result=True,
        delete_error=None,
        count_error=None,
        aliases_error=None,
        activate_on_alias_read=None,
    ):
        self.collections = dict(
            {COLLECTION: collection()} if collections is None else collections
        )
        self.aliases = dict(aliases or {})
        self.exact_count = exact_count
        self.delete_result = delete_result
        self.delete_error = delete_error
        self.count_error = count_error
        self.aliases_error = aliases_error
        self.activate_on_alias_read = activate_on_alias_read
        self.get_collection_calls = []
        self.count_calls = []
        self.get_aliases_calls = 0
        self.delete_calls = []

    def get_collection(self, *, collection_name):
        self.get_collection_calls.append(collection_name)
        if collection_name not in self.collections:
            raise missing_collection()
        return self.collections[collection_name]

    def count(self, *, collection_name, exact):
        self.count_calls.append((collection_name, exact))
        if self.count_error is not None:
            raise self.count_error
        return SimpleNamespace(count=self.exact_count)

    def get_aliases(self):
        self.get_aliases_calls += 1
        if self.activate_on_alias_read == self.get_aliases_calls:
            self.aliases[ACTIVE_GENERATION_ALIAS] = COLLECTION
        if self.aliases_error is not None:
            raise self.aliases_error
        return SimpleNamespace(
            aliases=[
                SimpleNamespace(alias_name=name, collection_name=target)
                for name, target in self.aliases.items()
            ]
        )

    def delete_collection(self, *, collection_name):
        self.delete_calls.append(collection_name)
        if self.delete_error is not None:
            raise self.delete_error
        if self.delete_result is True:
            self.collections.pop(collection_name, None)
        return self.delete_result


def make_adapter(client):
    return QdrantClientAdapter(
        client,
        retry_policy=QdrantRetryPolicy(max_attempts=1),
        sleep=lambda _: None,
    )


def test_get_generation_info_returns_actual_metadata_and_exact_count():
    client = FakeQdrantClient(aliases={ACTIVE_GENERATION_ALIAS: COLLECTION})

    result = make_adapter(client).get_generation_info(
        GetGenerationInfoRequest(GENERATION_ID)
    )

    assert result.generation_id == GENERATION_ID
    assert result.collection_name == COLLECTION
    assert result.point_count == 7
    assert result.vector_size == VECTOR_DIMENSION
    assert result.distance == "Cosine"
    assert result.is_active is True
    assert client.count_calls == [(COLLECTION, True)]


def test_get_generation_info_marks_inactive_generation():
    client = FakeQdrantClient(aliases={ACTIVE_GENERATION_ALIAS: OTHER_COLLECTION})

    result = make_adapter(client).get_generation_info(
        GetGenerationInfoRequest(GENERATION_ID)
    )

    assert result.is_active is False


def test_get_generation_info_maps_missing_collection_to_not_found():
    client = FakeQdrantClient(collections={})

    with pytest.raises(VectorGenerationNotFound) as caught:
        make_adapter(client).get_generation_info(
            GetGenerationInfoRequest(GENERATION_ID)
        )

    assert caught.value.code == "VECTOR_GENERATION_NOT_FOUND"


def test_get_generation_info_normalizes_exact_count_failure():
    client = FakeQdrantClient(count_error=httpx.ConnectError("offline"))

    with pytest.raises(VectorStoreUnavailable) as caught:
        make_adapter(client).get_generation_info(
            GetGenerationInfoRequest(GENERATION_ID)
        )

    assert isinstance(caught.value.__cause__, httpx.ConnectError)


def test_get_generation_info_rejects_invalid_qdrant_metadata():
    client = FakeQdrantClient()
    client.collections[COLLECTION] = SimpleNamespace(config=None)

    with pytest.raises(VectorStoreServiceError):
        make_adapter(client).get_generation_info(
            GetGenerationInfoRequest(GENERATION_ID)
        )


def test_delete_generation_rejects_missing_collection_without_delete():
    client = FakeQdrantClient(collections={})

    with pytest.raises(VectorGenerationNotFound):
        make_adapter(client).delete_generation(DeleteGenerationRequest(GENERATION_ID))

    assert client.delete_calls == []


def test_delete_generation_rejects_active_generation_without_mutating_alias():
    client = FakeQdrantClient(aliases={ACTIVE_GENERATION_ALIAS: COLLECTION})

    with pytest.raises(VectorGenerationActiveDeleteRejected) as caught:
        make_adapter(client).delete_generation(DeleteGenerationRequest(GENERATION_ID))

    assert caught.value.code == "VECTOR_GENERATION_ACTIVE_DELETE_REJECTED"
    assert client.aliases == {ACTIVE_GENERATION_ALIAS: COLLECTION}
    assert client.delete_calls == []


def test_delete_generation_deletes_only_the_requested_inactive_collection():
    client = FakeQdrantClient(
        aliases={ACTIVE_GENERATION_ALIAS: OTHER_COLLECTION},
        collections={COLLECTION: collection(), OTHER_COLLECTION: collection()},
    )

    result = make_adapter(client).delete_generation(
        DeleteGenerationRequest(GENERATION_ID)
    )

    assert result.generation_id == GENERATION_ID
    assert result.collection_name == COLLECTION
    assert result.deleted is True
    assert client.delete_calls == [COLLECTION]
    assert COLLECTION not in client.collections
    assert OTHER_COLLECTION in client.collections
    assert client.aliases == {ACTIVE_GENERATION_ALIAS: OTHER_COLLECTION}


def test_delete_generation_does_not_report_unconfirmed_deletion_as_success():
    client = FakeQdrantClient(delete_result=False)

    with pytest.raises(VectorStoreServiceError):
        make_adapter(client).delete_generation(DeleteGenerationRequest(GENERATION_ID))

    assert client.delete_calls == [COLLECTION]
    assert COLLECTION in client.collections


def test_delete_generation_normalizes_operational_failure_and_preserves_alias():
    client = FakeQdrantClient(
        aliases={ACTIVE_GENERATION_ALIAS: OTHER_COLLECTION},
        delete_error=httpx.ConnectError("offline"),
    )

    with pytest.raises(VectorStoreUnavailable) as caught:
        make_adapter(client).delete_generation(DeleteGenerationRequest(GENERATION_ID))

    assert isinstance(caught.value.__cause__, httpx.ConnectError)
    assert client.aliases == {ACTIVE_GENERATION_ALIAS: OTHER_COLLECTION}
    assert COLLECTION in client.collections
    assert client.delete_calls == [COLLECTION]


def test_delete_generation_normalizes_existence_check_failure():
    client = FakeQdrantClient()

    def failing_get_collection(*, collection_name):
        raise httpx.ConnectError("offline")

    client.get_collection = failing_get_collection

    with pytest.raises(VectorStoreUnavailable) as caught:
        make_adapter(client).delete_generation(DeleteGenerationRequest(GENERATION_ID))

    assert isinstance(caught.value.__cause__, httpx.ConnectError)
    assert client.delete_calls == []



def test_delete_generation_rechecks_alias_before_deletion():
    client = FakeQdrantClient(activate_on_alias_read=2)

    with pytest.raises(VectorGenerationActiveDeleteRejected):
        make_adapter(client).delete_generation(DeleteGenerationRequest(GENERATION_ID))

    assert client.get_aliases_calls == 2
    assert client.delete_calls == []
    assert client.aliases == {ACTIVE_GENERATION_ALIAS: COLLECTION}
