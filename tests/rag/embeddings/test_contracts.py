import hashlib
import inspect
import json
import math
import re
from dataclasses import FrozenInstanceError, fields

import pytest

from app.rag.embeddings.contracts import (
    DOCUMENT_PREFIX,
    EMBEDDINGS_ALGORITHM_VERSION,
    EMBEDDING_IDENTITY,
    EMBEDDING_MODEL,
    EMBEDDING_NORMALIZATION,
    EMBEDDING_PROVIDER,
    PROVISIONAL_EMBEDDING_DIMENSION,
    QUERY_PREFIX,
    ChunkEmbedding,
    EmbeddingConfig,
    EmbeddingResult,
)
from app.rag.embeddings.providers.base import EmbeddingProvider

SMALL_CONFIG = EmbeddingConfig(dimension=3)
CHUNK_ID = "c" * 64
OTHER_CHUNK_ID = "e" * 64
DOCUMENT_ID = "d" * 64
CHUNKING_CONFIG_ID = "a" * 64
SOURCE_PATH = "docs/policy.md"


def canonical_digest(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def config_payload(config: EmbeddingConfig) -> dict:
    return {
        "algorithm_version": config.algorithm_version,
        "dimension": config.dimension,
        "document_prefix": config.document_prefix,
        "model": config.model,
        "normalization": config.normalization,
        "provider": config.provider,
        "query_prefix": config.query_prefix,
    }


def make_embedding(**overrides) -> ChunkEmbedding:
    values = {
        "chunk_id": CHUNK_ID,
        "document_id": DOCUMENT_ID,
        "source_path": SOURCE_PATH,
        "chunk_index": 0,
        "start_offset": 0,
        "end_offset": 10,
        "chunking_config_id": CHUNKING_CONFIG_ID,
        "embedding_config_id": SMALL_CONFIG.config_id,
        "vector": (0.1, -0.2, 0.3),
    }
    values.update(overrides)
    return ChunkEmbedding(**values)


def make_result(**overrides) -> EmbeddingResult:
    values = {
        "config": SMALL_CONFIG,
        "embeddings": (
            make_embedding(),
            make_embedding(
                chunk_id=OTHER_CHUNK_ID,
                chunk_index=1,
                start_offset=10,
                end_offset=20,
            ),
        ),
    }
    values.update(overrides)
    return EmbeddingResult(**values)


# --- Pinned constants and defaults -----------------------------------------


def test_pinned_constants_match_the_approved_specification():
    assert EMBEDDING_PROVIDER == "ollama"
    assert EMBEDDING_MODEL == "nomic-embed-text:v1.5"
    assert EMBEDDING_IDENTITY == "ollama:nomic-embed-text:v1.5"
    assert DOCUMENT_PREFIX == "search_document: "
    assert QUERY_PREFIX == "search_query: "
    assert EMBEDDING_NORMALIZATION == "none"
    assert EMBEDDINGS_ALGORITHM_VERSION == "embeddings-v1"


def test_dimension_constant_is_explicitly_provisional():
    assert PROVISIONAL_EMBEDDING_DIMENSION == 768
    # T270 must measure the live value; this constant is not a live-model claim.
    assert EmbeddingConfig().dimension == PROVISIONAL_EMBEDDING_DIMENSION


def test_configuration_defaults_are_the_pinned_values():
    config = EmbeddingConfig()

    assert config.provider == EMBEDDING_PROVIDER
    assert config.model == EMBEDDING_MODEL
    assert config.dimension == PROVISIONAL_EMBEDDING_DIMENSION
    assert config.document_prefix == DOCUMENT_PREFIX
    assert config.query_prefix == QUERY_PREFIX
    assert config.normalization == EMBEDDING_NORMALIZATION
    assert config.algorithm_version == EMBEDDINGS_ALGORITHM_VERSION


def test_configuration_contains_only_identity_fields():
    assert {field.name for field in fields(EmbeddingConfig)} == {
        "provider",
        "model",
        "dimension",
        "document_prefix",
        "query_prefix",
        "normalization",
        "algorithm_version",
    }

    config = EmbeddingConfig()

    for excluded in (
        "digest",
        "served_digest",
        "batch_size",
        "timeout",
        "timeout_seconds",
        "retry_max_retries",
        "retry_base_delay",
        "retry_max_delay",
        "retry_jitter",
        "base_url",
        "qdrant_url",
        "database_url",
    ):
        assert not hasattr(config, excluded)


# --- Configuration identity ------------------------------------------------


def test_config_id_matches_the_exact_spec_formula():
    config = EmbeddingConfig(
        provider="ollama",
        model="modèle-é",
        dimension=12,
        document_prefix="préfixe document: ",
        query_prefix="préfixe requête: ",
        normalization="none",
        algorithm_version="embeddings-v1",
    )
    expected = canonical_digest(config_payload(config))

    assert config.config_id == expected
    assert re.fullmatch(r"[0-9a-f]{64}", config.config_id)


def test_config_id_uses_utf8_and_does_not_escape_non_ascii():
    config = EmbeddingConfig(model="modèle-é")
    escaped = hashlib.sha256(
        json.dumps(
            config_payload(config),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()

    assert config.config_id == canonical_digest(config_payload(config))
    assert config.config_id != escaped


def test_config_id_is_stable_for_equal_configurations():
    first = EmbeddingConfig(model="model-a", dimension=5)
    second = EmbeddingConfig(model="model-a", dimension=5)

    assert first.config_id == second.config_id


@pytest.mark.parametrize(
    "overrides",
    [
        {"provider": "other"},
        {"model": "other-model"},
        {"dimension": 769},
        {"document_prefix": "other_document: "},
        {"query_prefix": "other_query: "},
        {"algorithm_version": "embeddings-v2"},
    ],
)
def test_config_id_is_sensitive_to_every_mutable_included_field(overrides):
    base = {"model": "model-a", "dimension": 5}
    changed = dict(base)
    changed.update(overrides)

    assert EmbeddingConfig(**base).config_id != EmbeddingConfig(**changed).config_id


def test_config_id_payload_includes_the_fixed_normalization_field():
    config = EmbeddingConfig()
    payload = config_payload(config)
    without_normalization = dict(payload)
    without_normalization.pop("normalization")

    assert config.config_id == canonical_digest(payload)
    assert config.config_id != canonical_digest(without_normalization)


@pytest.mark.parametrize(
    "excluded_key",
    [
        "served_digest",
        "digest",
        "batch_size",
        "timeout",
        "timeout_seconds",
        "retry_max_retries",
        "retry_base_delay",
        "retry_max_delay",
        "retry_jitter",
        "base_url",
        "qdrant_url",
        "database_url",
    ],
)
def test_config_id_excludes_operational_and_digest_fields(excluded_key):
    config = EmbeddingConfig()
    payload = config_payload(config)
    with_extra = dict(payload)
    with_extra[excluded_key] = "operational-value"

    assert config.config_id == canonical_digest(payload)
    assert config.config_id != canonical_digest(with_extra)


# --- Configuration validation ---------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"provider": ""},
        {"provider": "   "},
        {"provider": None},
        {"model": ""},
        {"model": "  \n"},
        {"model": None},
        {"document_prefix": ""},
        {"document_prefix": "   "},
        {"document_prefix": None},
        {"query_prefix": ""},
        {"query_prefix": "   "},
        {"query_prefix": None},
        {"normalization": ""},
        {"normalization": "   "},
        {"normalization": None},
        {"normalization": "l2"},
        {"normalization": "L2"},
        {"algorithm_version": ""},
        {"algorithm_version": "  "},
        {"algorithm_version": None},
        {"dimension": 0},
        {"dimension": -1},
        {"dimension": 1.5},
        {"dimension": True},
        {"dimension": "768"},
    ],
)
def test_invalid_configuration_is_rejected(overrides):
    with pytest.raises(ValueError):
        EmbeddingConfig(**overrides)


def test_configuration_is_frozen():
    config = EmbeddingConfig()

    with pytest.raises(FrozenInstanceError):
        config.dimension = 1


# --- ChunkEmbedding --------------------------------------------------------


def test_chunk_embedding_copies_chunk_provenance_and_vector():
    embedding = make_embedding()

    assert embedding.chunk_id == CHUNK_ID
    assert embedding.document_id == DOCUMENT_ID
    assert embedding.source_path == SOURCE_PATH
    assert embedding.chunk_index == 0
    assert embedding.start_offset == 0
    assert embedding.end_offset == 10
    assert embedding.chunking_config_id == CHUNKING_CONFIG_ID
    assert embedding.embedding_config_id == SMALL_CONFIG.config_id
    assert embedding.vector == (0.1, -0.2, 0.3)
    assert isinstance(embedding.vector, tuple)


def test_chunk_embedding_normalizes_sequences_to_immutable_float_tuples():
    embedding = make_embedding(vector=[1, 2.5, -3])

    assert embedding.vector == (1.0, 2.5, -3.0)
    assert all(isinstance(value, float) for value in embedding.vector)


def test_chunk_embedding_is_frozen():
    embedding = make_embedding()

    with pytest.raises(FrozenInstanceError):
        embedding.chunk_id = OTHER_CHUNK_ID


@pytest.mark.parametrize(
    "field",
    [
        "chunk_id",
        "document_id",
        "source_path",
        "chunking_config_id",
        "embedding_config_id",
    ],
)
@pytest.mark.parametrize("value", ["", "   ", None])
def test_chunk_embedding_rejects_empty_identifiers(field, value):
    with pytest.raises(ValueError):
        make_embedding(**{field: value})


@pytest.mark.parametrize(
    "overrides",
    [
        {"chunk_index": -1},
        {"chunk_index": 1.5},
        {"chunk_index": True},
        {"start_offset": -1},
        {"start_offset": 1.5},
        {"start_offset": True},
        {"end_offset": -1},
        {"end_offset": 0},
        {"start_offset": 10, "end_offset": 10},
        {"start_offset": 10, "end_offset": 5},
        {"end_offset": 1.5},
        {"end_offset": True},
    ],
)
def test_chunk_embedding_rejects_invalid_offsets_and_indexes(overrides):
    with pytest.raises(ValueError):
        make_embedding(**overrides)


@pytest.mark.parametrize(
    "vector",
    [
        (),
        [],
        None,
        (0.1, float("nan")),
        (0.1, float("inf")),
        (0.1, float("-inf")),
        (0.1, "0.2"),
        (0.1, None),
        (0.1, True),
        (0.1, [0.2]),
        (0.1, {"value": 0.2}),
    ],
)
def test_chunk_embedding_rejects_invalid_vectors(vector):
    with pytest.raises(ValueError):
        make_embedding(vector=vector)


def test_chunk_embedding_error_messages_do_not_include_vector_values():
    sentinel = 98765.4321

    with pytest.raises(ValueError) as exc_info:
        make_embedding(vector=(sentinel, float("nan")))

    message = str(exc_info.value)
    assert str(sentinel) not in message
    assert "nan" not in message.lower()


# --- EmbeddingResult -------------------------------------------------------


def test_result_preserves_order_and_derives_counts():
    first = make_embedding()
    second = make_embedding(
        chunk_id=OTHER_CHUNK_ID,
        chunk_index=1,
        start_offset=10,
        end_offset=20,
    )
    result = EmbeddingResult(
        config=SMALL_CONFIG,
        embeddings=(second, first),
    )

    assert result.count == 2
    assert result.embeddings == (second, first)
    assert result.embeddings[0].chunk_id == OTHER_CHUNK_ID


def test_result_by_chunk_id_is_correct_and_read_only():
    first = make_embedding()
    second = make_embedding(
        chunk_id=OTHER_CHUNK_ID,
        chunk_index=1,
        start_offset=10,
        end_offset=20,
    )
    result = EmbeddingResult(config=SMALL_CONFIG, embeddings=(first, second))

    mapping = result.by_chunk_id

    assert mapping[CHUNK_ID] is first
    assert mapping[OTHER_CHUNK_ID] is second
    with pytest.raises(TypeError):
        mapping[CHUNK_ID] = first


def test_empty_result_is_valid():
    result = EmbeddingResult(config=SMALL_CONFIG)

    assert result.count == 0
    assert result.embeddings == ()
    assert result.retry_count == 0
    assert dict(result.by_chunk_id) == {}


def test_result_normalizes_embeddings_to_a_tuple():
    result = EmbeddingResult(config=SMALL_CONFIG, embeddings=[make_embedding()])

    assert isinstance(result.embeddings, tuple)


def test_result_is_frozen():
    result = make_result()

    with pytest.raises(FrozenInstanceError):
        result.retry_count = 1


def test_result_rejects_a_non_configuration_config():
    with pytest.raises(ValueError):
        EmbeddingResult(config="not-a-config")


def test_result_rejects_duplicate_chunk_ids():
    duplicate = make_embedding()
    other = make_embedding(
        chunk_id=CHUNK_ID,
        chunk_index=1,
        start_offset=10,
        end_offset=20,
    )

    with pytest.raises(ValueError):
        EmbeddingResult(config=SMALL_CONFIG, embeddings=(duplicate, other))


def test_result_rejects_mismatched_embedding_configuration_ids():
    embedding = make_embedding(embedding_config_id="b" * 64)

    with pytest.raises(ValueError):
        EmbeddingResult(config=SMALL_CONFIG, embeddings=(embedding,))


def test_result_rejects_a_vector_length_that_differs_from_the_dimension():
    four_dimensional_config = EmbeddingConfig(dimension=4)
    embedding = make_embedding(
        embedding_config_id=four_dimensional_config.config_id,
    )

    with pytest.raises(ValueError):
        EmbeddingResult(
            config=four_dimensional_config,
            embeddings=(embedding,),
        )


def test_result_rejects_non_finite_values_even_if_construction_was_bypassed():
    embedding = make_embedding()
    object.__setattr__(embedding, "vector", (float("nan"), 0.2, 0.3))

    with pytest.raises(ValueError):
        EmbeddingResult(config=SMALL_CONFIG, embeddings=(embedding,))


@pytest.mark.parametrize(
    "retry_count",
    [-1, 1.5, True, "0"],
)
def test_result_rejects_invalid_retry_counts(retry_count):
    with pytest.raises(ValueError):
        make_result(retry_count=retry_count)


def test_result_accepts_a_positive_retry_count():
    assert make_result(retry_count=3).retry_count == 3


def test_result_error_messages_do_not_include_chunk_text_or_vectors():
    sentinel = "SECRET SOURCE TEXT"
    embedding = make_embedding(embedding_config_id="b" * 64)

    with pytest.raises(ValueError) as exc_info:
        EmbeddingResult(config=SMALL_CONFIG, embeddings=(embedding,))

    message = str(exc_info.value)
    assert sentinel not in message
    assert "0.1" not in message


# --- Provider protocol -----------------------------------------------------


def test_provider_protocol_declares_identity_and_embed():
    assert isinstance(EmbeddingProvider.identity, property)

    signature = inspect.signature(EmbeddingProvider.embed)

    assert list(signature.parameters) == ["self", "texts", "timeout"]
    assert signature.parameters["timeout"].kind is inspect.Parameter.KEYWORD_ONLY
