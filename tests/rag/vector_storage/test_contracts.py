from dataclasses import FrozenInstanceError, fields

import pytest

from app.rag.vector_storage.contracts import (
    ACTIVE_GENERATION_ALIAS,
    MAX_UPSERT_BATCH_SIZE,
    VECTOR_DIMENSION,
    ActivateGenerationRequest,
    CollectionInfo,
    CreateGenerationRequest,
    DeleteGenerationRequest,
    GenerationActivationResult,
    GenerationDeletionResult,
    GenerationInfo,
    GenerationVerificationResult,
    GetGenerationInfoRequest,
    UpsertPointInput,
    UpsertPointsRequest,
    UpsertPointsResult,
    VectorStore,
    VerifyGenerationRequest,
)

GENERATION_ID = "a" * 64
OTHER_GENERATION_ID = "b" * 64
EMBEDDING_CONFIG_ID = "c" * 64
CHUNK_ID = "chunk-001"


def make_payload(**overrides):
    payload = {
        "chunk_id": CHUNK_ID,
        "document_id": "document-001",
        "source_path": "knowledge/policy.md",
        "title": "Policy",
        "format": "md",
        "content": "A policy chunk.",
        "start_offset": 0,
        "end_offset": 15,
        "chunk_index": 0,
        "chunking_config_id": "d" * 64,
        "embedding_config_id": EMBEDDING_CONFIG_ID,
    }
    payload.update(overrides)
    return payload


def make_point(**overrides):
    values = {
        "chunk_id": CHUNK_ID,
        "vector": [0.0] * VECTOR_DIMENSION,
        "payload": make_payload(),
    }
    values.update(overrides)
    return UpsertPointInput(**values)


def test_create_generation_accepts_approved_values():
    request = CreateGenerationRequest(GENERATION_ID, EMBEDDING_CONFIG_ID, 768)
    assert request.vector_size == VECTOR_DIMENSION


@pytest.mark.parametrize("value", ["A" * 64, "g" * 64, "a" * 63, "", None])
def test_generation_ids_must_be_64_lowercase_hex(value):
    with pytest.raises(ValueError):
        CreateGenerationRequest(value, EMBEDDING_CONFIG_ID, 768)


def test_create_generation_rejects_bool_and_wrong_dimension():
    with pytest.raises(ValueError):
        CreateGenerationRequest(GENERATION_ID, EMBEDDING_CONFIG_ID, True)
    with pytest.raises(ValueError):
        CreateGenerationRequest(GENERATION_ID, EMBEDDING_CONFIG_ID, 384)


def test_create_generation_contract_is_frozen():
    request = CreateGenerationRequest(GENERATION_ID, EMBEDDING_CONFIG_ID, 768)
    with pytest.raises(FrozenInstanceError):
        request.vector_size = 384


def test_collection_info_is_application_owned_and_immutable():
    result = CollectionInfo(
        GENERATION_ID, f"knowledge_vectors_g_{GENERATION_ID}", 768, "Cosine"
    )
    assert result.distance == "Cosine"
    with pytest.raises(FrozenInstanceError):
        result.distance = "Dot"
    with pytest.raises(ValueError, match="collection_name"):
        CollectionInfo(GENERATION_ID, "caller-selected", 768, "Cosine")
    with pytest.raises(ValueError, match="Cosine"):
        CollectionInfo(GENERATION_ID, f"knowledge_vectors_g_{GENERATION_ID}", 768, "Dot")


def test_upsert_point_normalizes_vector_and_freezes_payload():
    point = make_point(vector=[1] * VECTOR_DIMENSION)
    assert point.vector == (1.0,) * VECTOR_DIMENSION
    assert point.payload["chunk_id"] == CHUNK_ID
    with pytest.raises(TypeError):
        point.payload["chunk_id"] = "changed"


@pytest.mark.parametrize(
    "vector",
    [
        [0.0] * (VECTOR_DIMENSION - 1),
        [0.0] * (VECTOR_DIMENSION + 1),
        [True] + [0.0] * (VECTOR_DIMENSION - 1),
        ["0"] + [0.0] * (VECTOR_DIMENSION - 1),
        [float("nan")] + [0.0] * (VECTOR_DIMENSION - 1),
        [float("inf")] + [0.0] * (VECTOR_DIMENSION - 1),
        [None] + [0.0] * (VECTOR_DIMENSION - 1),
    ],
)
def test_upsert_point_rejects_invalid_vector(vector):
    with pytest.raises(ValueError):
        make_point(vector=vector)


def test_upsert_point_rejects_payload_with_missing_or_unknown_fields():
    missing = make_payload()
    missing.pop("title")
    with pytest.raises(ValueError, match="payload fields mismatch"):
        make_point(payload=missing)

    unknown = make_payload(extra="not allowed")
    with pytest.raises(ValueError, match="payload fields mismatch"):
        make_point(payload=unknown)


def test_upsert_point_rejects_payload_chunk_id_mismatch():
    with pytest.raises(ValueError, match="must match"):
        make_point(payload=make_payload(chunk_id="another-chunk"))


@pytest.mark.parametrize("field,value", [("chunk_index", True), ("start_offset", -1), ("end_offset", 0)])
def test_upsert_point_rejects_invalid_payload_integers(field, value):
    with pytest.raises(ValueError):
        make_point(payload=make_payload(**{field: value}))


@pytest.mark.parametrize(
    "field",
    [
        "document_id",
        "source_path",
        "title",
        "format",
        "content",
        "chunking_config_id",
        "embedding_config_id",
    ],
)
def test_upsert_point_rejects_non_string_payload_fields(field):
    with pytest.raises(ValueError, match=field):
        make_point(payload=make_payload(**{field: None}))


def test_upsert_point_rejects_empty_chunk_id_and_invalid_offsets():
    with pytest.raises(ValueError, match="chunk_id"):
        make_point(chunk_id="", payload=make_payload(chunk_id=""))
    with pytest.raises(ValueError, match="end_offset"):
        make_point(payload=make_payload(start_offset=15, end_offset=15))


def test_upsert_request_accepts_one_point_and_preserves_order():
    first = make_point()
    second_id = "chunk-002"
    second_payload = make_payload(chunk_id=second_id, chunk_index=1, start_offset=15, end_offset=30)
    second = UpsertPointInput(second_id, [0.5] * VECTOR_DIMENSION, second_payload)

    request = UpsertPointsRequest(GENERATION_ID, [first, second])

    assert request.points == (first, second)


def test_upsert_request_enforces_batch_limit():
    points = [
        UpsertPointInput(
            f"chunk-{index:03d}",
            [0.0] * VECTOR_DIMENSION,
            make_payload(chunk_id=f"chunk-{index:03d}", chunk_index=index),
        )
        for index in range(MAX_UPSERT_BATCH_SIZE)
    ]
    request = UpsertPointsRequest(GENERATION_ID, points)
    assert len(request.points) == 64

    with pytest.raises(ValueError):
        UpsertPointsRequest(GENERATION_ID, [])
    with pytest.raises(ValueError):
        UpsertPointsRequest(GENERATION_ID, points + [points[0]])


def test_upsert_request_rejects_duplicate_chunk_ids():
    with pytest.raises(ValueError, match="unique"):
        UpsertPointsRequest(GENERATION_ID, [make_point(), make_point()])


def test_upsert_result_represents_only_a_fully_confirmed_batch():
    result = UpsertPointsResult(GENERATION_ID, 2, 2, True)
    assert result.succeeded is True

    with pytest.raises(ValueError):
        UpsertPointsResult(GENERATION_ID, 2, 1, True)
    with pytest.raises(ValueError):
        UpsertPointsResult(GENERATION_ID, 2, 2, False)


def test_verification_allows_zero_points_and_requires_matching_count():
    request = VerifyGenerationRequest(GENERATION_ID, 0)
    result = GenerationVerificationResult(GENERATION_ID, 0, 0, 768, "Cosine")
    assert request.expected_point_count == result.actual_point_count

    with pytest.raises(ValueError):
        VerifyGenerationRequest(GENERATION_ID, True)
    with pytest.raises(ValueError):
        GenerationVerificationResult(GENERATION_ID, 1, 0, 768, "Cosine")
    with pytest.raises(ValueError):
        GenerationVerificationResult(GENERATION_ID, 0, 0, 768, "Dot")


def test_activation_contract_uses_fixed_alias():
    request = ActivateGenerationRequest(GENERATION_ID)
    result = GenerationActivationResult(GENERATION_ID, ACTIVE_GENERATION_ALIAS, None)
    assert request.generation_id == result.generation_id

    with pytest.raises(ValueError):
        GenerationActivationResult(GENERATION_ID, "caller-alias", None)


def test_generation_info_requires_derived_collection_name_and_valid_counts():
    result = GenerationInfo(
        GENERATION_ID, f"knowledge_vectors_g_{GENERATION_ID}", 0, 768, "Cosine", False
    )
    assert result.is_active is False

    with pytest.raises(ValueError):
        GenerationInfo(GENERATION_ID, "caller-selected", 0, 768, "Cosine", False)
    with pytest.raises(ValueError):
        GenerationInfo(GENERATION_ID, f"knowledge_vectors_g_{GENERATION_ID}", True, 768, "Cosine", False)


def test_deletion_contract_is_explicit_and_confirmed():
    request = DeleteGenerationRequest(GENERATION_ID)
    result = GenerationDeletionResult(
        GENERATION_ID, f"knowledge_vectors_g_{GENERATION_ID}", True
    )
    assert request.generation_id == result.generation_id

    with pytest.raises(ValueError):
        GenerationDeletionResult(GENERATION_ID, f"knowledge_vectors_g_{GENERATION_ID}", False)


def test_vector_store_protocol_exposes_storage_methods_and_reserved_search():
    expected = {
        "create_generation",
        "upsert_points",
        "verify_generation",
        "activate_generation",
        "search",
        "get_generation_info",
        "delete_generation",
    }
    assert expected.issubset(set(VectorStore.__dict__))


def test_request_and_result_dtos_are_frozen_dataclasses():
    dto_types = (
        CreateGenerationRequest,
        CollectionInfo,
        UpsertPointInput,
        UpsertPointsRequest,
        UpsertPointsResult,
        VerifyGenerationRequest,
        GenerationVerificationResult,
        ActivateGenerationRequest,
        GenerationActivationResult,
        GetGenerationInfoRequest,
        GenerationInfo,
        DeleteGenerationRequest,
        GenerationDeletionResult,
    )
    for dto_type in dto_types:
        assert getattr(dto_type, "__dataclass_params__").frozen is True
        assert fields(dto_type)
