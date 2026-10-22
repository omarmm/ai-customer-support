import hashlib
import json
import re
from dataclasses import FrozenInstanceError, replace

import pytest

from app.rag.chunking.contracts import (
    ALGORITHM_VERSION,
    Chunk,
    ChunkingConfig,
    ChunkingResult,
    DocumentChunking,
    compute_chunk_id,
)

CONTENT = "Alpha beta gamma delta."
DOCUMENT_ID = "d" * 64
SOURCE_PATH = "docs/policy.md"
TITLE = "Policy"
FORMAT = "markdown"
TOKENIZER_ID = "fixture-tokenizer|1.0|unicode-codepoints"
CONFIG = ChunkingConfig(
    max_tokens=2,
    overlap_tokens=0,
    tokenizer_id=TOKENIZER_ID,
)
SMALL_CONFIG = ChunkingConfig(
    max_tokens=1,
    overlap_tokens=0,
    tokenizer_id=TOKENIZER_ID,
)
OTHER_CONFIG = ChunkingConfig(
    max_tokens=2,
    overlap_tokens=1,
    tokenizer_id=TOKENIZER_ID,
)


def make_chunk(**overrides) -> Chunk:
    values = {
        "document_id": DOCUMENT_ID,
        "source_path": SOURCE_PATH,
        "title": TITLE,
        "format": FORMAT,
        "start_offset": 0,
        "end_offset": 11,
        "token_start": 0,
        "token_end": 2,
        "chunk_index": 0,
        "chunking_config_id": CONFIG.config_id,
        "content": None,
    }
    values.update(overrides)
    content = values.pop("content")
    if content is None:
        content = CONTENT[values["start_offset"] : values["end_offset"]]
    return Chunk.build(content=content, **values)


def default_chunks(config_id: str = CONFIG.config_id) -> tuple[Chunk, ...]:
    return (
        make_chunk(chunking_config_id=config_id),
        make_chunk(
            start_offset=11,
            end_offset=23,
            token_start=2,
            token_end=4,
            chunk_index=1,
            chunking_config_id=config_id,
        ),
    )


def make_document(**overrides) -> DocumentChunking:
    values = {
        "document_id": DOCUMENT_ID,
        "source_path": SOURCE_PATH,
        "title": TITLE,
        "format": FORMAT,
        "content_length": len(CONTENT),
        "token_count": 4,
    }
    values.update(overrides)
    if "chunks" not in overrides:
        values["chunks"] = (
            make_chunk(
                document_id=values["document_id"],
                source_path=values["source_path"],
                title=values["title"],
                format=values["format"],
                chunking_config_id=CONFIG.config_id,
            ),
            make_chunk(
                document_id=values["document_id"],
                source_path=values["source_path"],
                title=values["title"],
                format=values["format"],
                start_offset=11,
                end_offset=23,
                token_start=2,
                token_end=4,
                chunk_index=1,
                chunking_config_id=CONFIG.config_id,
            ),
        )
    return DocumentChunking(**values)


def make_result(documents=None, config: ChunkingConfig = CONFIG) -> ChunkingResult:
    if documents is None:
        documents = (make_document(),)
    return ChunkingResult(config=config, documents=documents)


def canonical_digest(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


# --- Test 16: configuration and chunk IDs ----------------------------------


def test_config_id_matches_the_exact_spec_formula():
    config = ChunkingConfig(
        max_tokens=500,
        overlap_tokens=75,
        tokenizer_id="tokenizer-é|1.0",
    )
    expected = canonical_digest(
        {
            "algorithm_version": ALGORITHM_VERSION,
            "max_tokens": 500,
            "overlap_tokens": 75,
            "tokenizer_id": "tokenizer-é|1.0",
        }
    )

    assert config.config_id == expected
    assert re.fullmatch(r"[0-9a-f]{64}", config.config_id)


def test_config_id_is_stable_for_equal_configurations():
    first = ChunkingConfig(max_tokens=10, overlap_tokens=2, tokenizer_id="t")
    second = ChunkingConfig(max_tokens=10, overlap_tokens=2, tokenizer_id="t")

    assert first.config_id == second.config_id


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_tokens": 11},
        {"overlap_tokens": 3},
        {"tokenizer_id": "other"},
        {"algorithm_version": "chunking-v2"},
    ],
)
def test_config_id_is_sensitive_to_every_included_field(overrides):
    base = {"max_tokens": 10, "overlap_tokens": 2, "tokenizer_id": "t"}
    changed = dict(base)
    changed.update(overrides)

    assert (
        ChunkingConfig(**base).config_id
        != ChunkingConfig(**changed).config_id
    )


def test_config_defaults_to_the_algorithm_version():
    config = ChunkingConfig(max_tokens=500, overlap_tokens=75, tokenizer_id="t")

    assert config.algorithm_version == ALGORITHM_VERSION == "chunking-v1"


def test_chunk_id_matches_the_exact_spec_formula():
    expected = canonical_digest(
        {
            "chunking_config_id": CONFIG.config_id,
            "document_id": DOCUMENT_ID,
            "source_path": SOURCE_PATH,
            "start_offset": 0,
            "end_offset": 11,
            "content": CONTENT[0:11],
        }
    )

    assert make_chunk().chunk_id == expected


def test_chunk_id_is_stable_for_equal_inputs():
    first = make_chunk()
    second = make_chunk()

    assert first.chunk_id == second.chunk_id


@pytest.mark.parametrize(
    "overrides",
    [
        {"chunking_config_id": "c" * 64},
        {"document_id": "e" * 64},
        {"source_path": "docs/other.md"},
        {"start_offset": 1},
        {"end_offset": 12},
        {"content": "different content"},
    ],
)
def test_chunk_id_is_sensitive_to_every_included_field(overrides):
    base = {
        "chunking_config_id": CONFIG.config_id,
        "document_id": DOCUMENT_ID,
        "source_path": SOURCE_PATH,
        "start_offset": 0,
        "end_offset": 11,
        "content": "slice",
    }
    changed = dict(base)
    changed.update(overrides)

    assert compute_chunk_id(**base) != compute_chunk_id(**changed)


def test_identical_content_at_different_paths_has_distinct_chunk_ids():
    first = make_chunk(source_path="docs/a.md")
    second = make_chunk(source_path="docs/b.md")

    assert first.content == second.content
    assert first.chunk_id != second.chunk_id


# --- Configuration validation ----------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_tokens": 0},
        {"max_tokens": -1},
        {"overlap_tokens": -1},
        {"overlap_tokens": 2},
        {"overlap_tokens": 3},
        {"tokenizer_id": ""},
        {"tokenizer_id": "   "},
        {"algorithm_version": ""},
        {"algorithm_version": "  \n"},
        {"max_tokens": 2.5},
        {"overlap_tokens": 0.5},
    ],
)
def test_invalid_configuration_is_rejected(overrides):
    values = {"max_tokens": 2, "overlap_tokens": 0, "tokenizer_id": "t"}
    values.update(overrides)

    with pytest.raises(ValueError):
        ChunkingConfig(**values)


# --- Test 17: construction invariants --------------------------------------


def test_chunk_derived_char_count():
    assert make_chunk().char_count == 11


def test_document_derived_chunk_count():
    assert make_document().chunk_count == 2


def test_result_derived_properties():
    result = make_result(
        documents=(make_document(), make_document(source_path="docs/z.md"))
    )

    assert result.document_count == 2
    assert result.chunk_count == 4
    assert result.total_token_count == 8
    assert len(result.chunks) == 4
    assert result.has_chunks is True
    assert all(isinstance(chunk, Chunk) for chunk in result.chunks)


def test_empty_result_has_zero_counts_and_no_chunks():
    result = ChunkingResult(config=CONFIG)

    assert result.documents == ()
    assert result.document_count == 0
    assert result.chunk_count == 0
    assert result.total_token_count == 0
    assert result.chunks == ()
    assert result.has_chunks is False


def test_zero_chunk_document_is_preserved_in_the_result():
    document = DocumentChunking(
        document_id="w" * 64,
        source_path="docs/blank.md",
        title="Blank",
        format=FORMAT,
        content_length=5,
        token_count=0,
        chunks=(),
    )

    result = make_result(documents=(document,))

    assert result.document_count == 1
    assert result.chunk_count == 0
    assert result.total_token_count == 0
    assert result.has_chunks is False


def test_result_sorts_documents_by_source_path_then_document_id():
    high = make_document(source_path="b.md", document_id="b" * 64)
    late = make_document(source_path="a.md", document_id="z" * 64)
    early = make_document(source_path="a.md", document_id="a" * 64)

    result = make_result(documents=(high, late, early))

    assert [
        (document.source_path, document.document_id) for document in result.documents
    ] == [
        ("a.md", "a" * 64),
        ("a.md", "z" * 64),
        ("b.md", "b" * 64),
    ]


def test_document_sorts_chunks_by_chunk_index():
    chunks = tuple(reversed(default_chunks()))

    document = make_document(chunks=chunks)

    assert [chunk.chunk_index for chunk in document.chunks] == [0, 1]
    assert isinstance(document.chunks, tuple)


def test_direct_construction_normalizes_collections_to_tuples():
    document = DocumentChunking(
        document_id=DOCUMENT_ID,
        source_path=SOURCE_PATH,
        title=TITLE,
        format=FORMAT,
        content_length=len(CONTENT),
        token_count=4,
        chunks=list(default_chunks()),
    )
    result = ChunkingResult(config=CONFIG, documents=[document])

    assert isinstance(document.chunks, tuple)
    assert isinstance(result.documents, tuple)
    assert isinstance(result.chunks, tuple)


def test_duplicate_document_pairs_are_rejected():
    duplicate = make_document()

    with pytest.raises(ValueError):
        make_result(documents=(duplicate, duplicate))


@pytest.mark.parametrize(
    "field,value",
    [
        ("document_id", "e" * 64),
        ("source_path", "docs/other.md"),
        ("title", "Other"),
        ("format", "text"),
    ],
)
def test_chunk_metadata_must_match_the_enclosing_document(field, value):
    chunk = make_chunk(**{field: value})
    other = make_chunk(
        start_offset=11,
        end_offset=23,
        token_start=2,
        token_end=4,
        chunk_index=1,
    )

    with pytest.raises(ValueError):
        make_document(chunks=(chunk, other))


def test_chunk_configuration_must_match_the_result_configuration():
    document = make_document()

    with pytest.raises(ValueError):
        make_result(documents=(document,), config=OTHER_CONFIG)


def test_duplicate_chunk_indexes_are_rejected():
    chunks = (
        make_chunk(chunk_index=0),
        make_chunk(
            start_offset=11,
            end_offset=23,
            token_start=2,
            token_end=4,
            chunk_index=0,
        ),
    )

    with pytest.raises(ValueError):
        make_document(chunks=chunks)


def test_missing_chunk_indexes_are_rejected():
    chunks = (
        make_chunk(chunk_index=0),
        make_chunk(
            start_offset=11,
            end_offset=23,
            token_start=2,
            token_end=4,
            chunk_index=2,
        ),
    )

    with pytest.raises(ValueError):
        make_document(chunks=chunks)


@pytest.mark.parametrize(
    "overrides",
    [
        {"token_start": 1, "token_end": 1},
        {"token_start": 2, "token_end": 1},
        {"start_offset": 11, "end_offset": 11},
        {"start_offset": 12, "end_offset": 11},
    ],
)
def test_invalid_chunk_ranges_are_rejected(overrides):
    with pytest.raises(ValueError):
        make_chunk(**overrides)


def test_token_count_must_equal_the_range_width():
    valid = make_chunk()

    with pytest.raises(ValueError):
        replace(valid, token_count=3)


def test_content_must_match_the_offset_range():
    valid = make_chunk()

    with pytest.raises(ValueError):
        replace(valid, content="short")


def test_chunk_rejects_negative_offsets_and_index():
    valid = make_chunk()

    with pytest.raises(ValueError):
        replace(valid, start_offset=-1)
    with pytest.raises(ValueError):
        replace(valid, chunk_index=-1)


@pytest.mark.parametrize(
    "overrides",
    [
        {"content_length": -1},
        {"token_count": -1},
        {"content_length": 22},
    ],
)
def test_invalid_document_counts_are_rejected(overrides):
    with pytest.raises(ValueError):
        make_document(**overrides)


def test_zero_content_length_requires_zero_tokens_and_no_chunks():
    with pytest.raises(ValueError):
        DocumentChunking(
            document_id=DOCUMENT_ID,
            source_path=SOURCE_PATH,
            title=TITLE,
            format=FORMAT,
            content_length=0,
            token_count=1,
            chunks=(make_chunk(),),
        )

    with pytest.raises(ValueError):
        DocumentChunking(
            document_id=DOCUMENT_ID,
            source_path=SOURCE_PATH,
            title=TITLE,
            format=FORMAT,
            content_length=0,
            token_count=0,
            chunks=(make_chunk(),),
        )


def test_zero_token_count_requires_no_chunks():
    with pytest.raises(ValueError):
        make_document(token_count=0)


def test_positive_token_count_requires_chunks():
    with pytest.raises(ValueError):
        make_document(chunks=())


def test_first_chunk_must_start_at_token_zero():
    chunks = (
        make_chunk(token_start=1, token_end=2),
        make_chunk(
            start_offset=11,
            end_offset=23,
            token_start=2,
            token_end=4,
            chunk_index=1,
        ),
    )

    with pytest.raises(ValueError):
        make_document(chunks=chunks)


def test_last_chunk_must_end_at_document_token_count():
    chunks = (
        make_chunk(),
        make_chunk(
            start_offset=11,
            end_offset=23,
            token_start=2,
            token_end=3,
            chunk_index=1,
        ),
    )

    with pytest.raises(ValueError):
        make_document(chunks=chunks)


def test_first_chunk_must_start_at_offset_zero():
    chunks = (
        make_chunk(start_offset=1, end_offset=11),
        make_chunk(
            start_offset=11,
            end_offset=23,
            token_start=2,
            token_end=4,
            chunk_index=1,
        ),
    )

    with pytest.raises(ValueError):
        make_document(chunks=chunks)


def test_last_chunk_must_end_at_content_length():
    chunks = (
        make_chunk(),
        make_chunk(
            start_offset=11,
            end_offset=22,
            token_start=2,
            token_end=4,
            chunk_index=1,
        ),
    )

    with pytest.raises(ValueError):
        make_document(chunks=chunks)


def test_chunk_source_ranges_must_not_contain_gaps():
    chunks = (
        make_chunk(),
        make_chunk(
            start_offset=12,
            end_offset=23,
            token_start=2,
            token_end=4,
            chunk_index=1,
        ),
    )

    with pytest.raises(ValueError):
        make_document(chunks=chunks)


def test_chunk_token_ranges_must_not_contain_gaps():
    chunks = (
        make_chunk(token_end=1),
        make_chunk(
            start_offset=11,
            end_offset=23,
            token_start=3,
            token_end=4,
            chunk_index=1,
        ),
    )

    with pytest.raises(ValueError):
        make_document(chunks=chunks)


def test_chunk_token_count_must_not_exceed_config_max_tokens():
    document = make_document(
        chunks=(
            make_chunk(chunking_config_id=SMALL_CONFIG.config_id),
            make_chunk(
                start_offset=11,
                end_offset=23,
                token_start=2,
                token_end=4,
                chunk_index=1,
                chunking_config_id=SMALL_CONFIG.config_id,
            ),
        )
    )

    with pytest.raises(ValueError):
        make_result(documents=(document,), config=SMALL_CONFIG)


def test_result_config_must_be_a_chunking_config():
    with pytest.raises(ValueError):
        ChunkingResult(config="not-a-config")  # type: ignore[arg-type]


def test_contracts_are_frozen():
    chunk = make_chunk()
    document = make_document()
    result = make_result()
    config = CONFIG

    with pytest.raises(FrozenInstanceError):
        chunk.content = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        document.token_count = 1  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.documents = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        config.max_tokens = 10  # type: ignore[misc]
