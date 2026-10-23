import ast
import re
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import app.rag.chunking.service as service_module
from app.core.config import Settings
from app.rag.chunking.contracts import ChunkingConfig, ChunkingResult
from app.rag.chunking.exceptions import TokenizerContractError
from app.rag.chunking.service import ChunkingService
from app.rag.chunking.tokenizer import TokenSpan
from app.rag.ingestion.contracts import KnowledgeDocument

TOKENIZER_ID = "fixture-whitespace|1.0|unicode-codepoints"
FORMAT = "markdown"


@dataclass
class WhitespaceTokenizer:
    """Deterministic fixture: one raw span per whitespace-delimited run."""

    identity: str = TOKENIZER_ID
    calls: int = 0

    def tokenize(self, text: str) -> tuple[TokenSpan, ...]:
        self.calls += 1
        return tuple(
            TokenSpan(match.start(), match.end())
            for match in re.finditer(r"\S+", text)
        )


class ExplodingTokenizer:
    """Fails the test if chunking calls the tokenizer."""

    identity = "fixture-exploding|1.0"

    def tokenize(self, text: str) -> tuple[TokenSpan, ...]:
        raise AssertionError("tokenizer must not be called")


class EmptyTokenizer:
    """Violates §5.4 by returning no spans for non-whitespace text."""

    identity = "fixture-empty|1.0"

    def tokenize(self, text: str) -> tuple[TokenSpan, ...]:
        return ()


def make_document(
    content: str = "one two three",
    *,
    document_id: str = "a" * 64,
    source_path: str = "docs/policy.md",
    title: str = "Policy",
) -> KnowledgeDocument:
    return KnowledgeDocument(
        document_id=document_id,
        source_path=source_path,
        title=title,
        format=FORMAT,
        content=content,
        size_bytes=len(content.encode("utf-8")),
    )


def make_settings(**overrides) -> Settings:
    values = {
        "app_env": "test",
        "app_name": "AI Customer Support Backend",
        "database_url": "postgresql://test",
        "qdrant_url": "http://localhost:6333",
        "ollama_url": "http://localhost:11434",
        "llm_provider": "ollama",
    }
    values.update(overrides)
    return Settings(**values)


def settings_for(**overrides) -> SimpleNamespace:
    values = {
        "knowledge_chunk_max_tokens": 500,
        "knowledge_chunk_overlap_tokens": 75,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


# --- §9: settings ----------------------------------------------------------


def test_chunking_settings_have_approved_defaults():
    settings = make_settings()

    assert settings.knowledge_chunk_max_tokens == 500
    assert settings.knowledge_chunk_overlap_tokens == 75


def test_chunking_settings_read_environment_variables(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_CHUNK_MAX_TOKENS", "128")
    monkeypatch.setenv("KNOWLEDGE_CHUNK_OVERLAP_TOKENS", "16")

    settings = make_settings()

    assert settings.knowledge_chunk_max_tokens == 128
    assert settings.knowledge_chunk_overlap_tokens == 16


@pytest.mark.parametrize(
    ("max_tokens", "overlap_tokens"),
    [(10, 10), (10, 11), (1, 1)],
)
def test_overlap_must_be_less_than_max_tokens(max_tokens, overlap_tokens):
    with pytest.raises(ValidationError, match="must be less than"):
        make_settings(
            knowledge_chunk_max_tokens=max_tokens,
            knowledge_chunk_overlap_tokens=overlap_tokens,
        )


@pytest.mark.parametrize("max_tokens", [0, -1])
def test_max_tokens_must_be_positive(max_tokens):
    with pytest.raises(ValidationError):
        make_settings(knowledge_chunk_max_tokens=max_tokens)


@pytest.mark.parametrize("overlap_tokens", [-1])
def test_overlap_tokens_must_be_non_negative(overlap_tokens):
    with pytest.raises(ValidationError):
        make_settings(knowledge_chunk_overlap_tokens=overlap_tokens)


def test_env_example_documents_chunking_settings():
    example = Path(__file__).resolve().parents[3] / ".env.example"
    contents = example.read_text(encoding="utf-8")

    assert "KNOWLEDGE_CHUNK_MAX_TOKENS=500" in contents
    assert "KNOWLEDGE_CHUNK_OVERLAP_TOKENS=75" in contents


# --- §9/§18: service construction and composition --------------------------


def test_service_defaults_match_the_approved_defaults():
    tokenizer = WhitespaceTokenizer()
    service = ChunkingService(tokenizer)

    assert service.config == ChunkingConfig(
        max_tokens=500,
        overlap_tokens=75,
        tokenizer_id=TOKENIZER_ID,
    )


def test_service_uses_explicit_configuration_values():
    service = ChunkingService(WhitespaceTokenizer(), max_tokens=4, overlap_tokens=1)

    assert service.config.max_tokens == 4
    assert service.config.overlap_tokens == 1
    assert service.config.tokenizer_id == TOKENIZER_ID


def test_from_settings_uses_configured_values():
    service = ChunkingService.from_settings(
        settings_for(
            knowledge_chunk_max_tokens=8,
            knowledge_chunk_overlap_tokens=2,
        ),
        WhitespaceTokenizer(),
    )

    assert service.config.max_tokens == 8
    assert service.config.overlap_tokens == 2


def test_from_settings_does_not_read_global_settings(monkeypatch):
    def fail_settings():
        raise AssertionError("get_settings must not be called")

    monkeypatch.setattr(service_module, "get_settings", fail_settings, raising=False)

    service = ChunkingService.from_settings(settings_for(), WhitespaceTokenizer())
    result = service.chunk([make_document()])

    assert result.chunk_count > 0


@pytest.mark.parametrize(
    ("max_tokens", "overlap_tokens"),
    [(0, 0), (4, 4), (4, 5), (-1, 0), (4, -1)],
)
def test_service_rejects_invalid_configuration(max_tokens, overlap_tokens):
    with pytest.raises(ValueError):
        ChunkingService(
            WhitespaceTokenizer(),
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )


def test_service_rejects_an_empty_tokenizer_identity():
    with pytest.raises(TokenizerContractError) as caught:
        ChunkingService(WhitespaceTokenizer(identity="  "))

    assert caught.value.reason == "empty_identity"


# --- Test 12: aggregation, determinism, input-order independence -----------


def test_every_document_is_represented_in_deterministic_order():
    tokenizer = WhitespaceTokenizer()
    service = ChunkingService(tokenizer, max_tokens=2, overlap_tokens=0)
    documents = [
        make_document("one two three", document_id="c" * 64, source_path="c.md"),
        make_document("", document_id="a" * 64, source_path="a.md"),
        make_document(" \n\t ", document_id="b" * 64, source_path="b.md"),
        make_document("alpha beta", document_id="d" * 64, source_path="b.md"),
    ]

    result = service.chunk(documents)

    assert result.document_count == 4
    assert tuple(
        (entry.source_path, entry.document_id) for entry in result.documents
    ) == (
        ("a.md", "a" * 64),
        ("b.md", "b" * 64),
        ("b.md", "d" * 64),
        ("c.md", "c" * 64),
    )
    assert result.chunk_count == sum(
        entry.chunk_count for entry in result.documents
    )
    assert result.total_token_count == sum(
        entry.token_count for entry in result.documents
    )
    assert result.has_chunks is True


def test_input_order_does_not_affect_the_result():
    service = ChunkingService(WhitespaceTokenizer(), max_tokens=2, overlap_tokens=1)
    documents = [
        make_document("one two three", document_id="c" * 64, source_path="c.md"),
        make_document("", document_id="a" * 64, source_path="a.md"),
        make_document("alpha beta gamma", document_id="b" * 64, source_path="b.md"),
    ]

    forward = service.chunk(documents)
    backward = service.chunk(reversed(documents))

    assert forward == backward
    assert tuple(chunk.chunk_id for chunk in forward.chunks) == tuple(
        chunk.chunk_id for chunk in backward.chunks
    )


def test_chunking_is_deterministic():
    service = ChunkingService(WhitespaceTokenizer(), max_tokens=3, overlap_tokens=1)
    documents = [
        make_document("Alpha beta. Gamma\n\nDelta epsilon zeta eta theta"),
    ]

    first = service.chunk(documents)
    second = service.chunk(documents)

    assert first == second
    assert first.config == service.config


def test_documents_are_not_mutated():
    service = ChunkingService(WhitespaceTokenizer(), max_tokens=2, overlap_tokens=0)
    documents = [
        make_document("one two three", document_id="b" * 64, source_path="b.md"),
        make_document("four five", document_id="a" * 64, source_path="a.md"),
    ]
    before = tuple(documents)

    service.chunk(documents)

    assert tuple(documents) == before


# --- Test 13: metadata and indexes -----------------------------------------


def test_aggregate_metadata_and_indexes_match_each_document():
    service = ChunkingService(WhitespaceTokenizer(), max_tokens=2, overlap_tokens=1)
    first = make_document(
        "one two three four",
        document_id="a" * 64,
        source_path="docs/refunds.md",
        title="Refunds",
    )
    second = make_document(
        "alpha beta",
        document_id="b" * 64,
        source_path="docs/shipping.md",
        title="Shipping",
    )

    result = service.chunk([first, second])

    assert result.config == service.config
    for document, source in zip(result.documents, (first, second)):
        assert document.document_id == source.document_id
        assert document.source_path == source.source_path
        assert document.title == source.title
        assert document.format == source.format
        assert document.content_length == len(source.content)
        assert document.chunk_count == len(document.chunks)

        for position, chunk in enumerate(document.chunks):
            assert chunk.chunk_index == position
            assert chunk.document_id == source.document_id
            assert chunk.source_path == source.source_path
            assert chunk.title == source.title
            assert chunk.format == source.format
            assert chunk.chunking_config_id == result.config.config_id
            assert chunk.token_count <= result.config.max_tokens
            assert chunk.token_count == chunk.token_end - chunk.token_start
            assert chunk.content == source.content[
                chunk.start_offset : chunk.end_offset
            ]
            assert len(chunk.content) == chunk.end_offset - chunk.start_offset


# --- Test 15: empty and whitespace-only documents --------------------------


@pytest.mark.parametrize("content", ["", " ", "\n\t ", "\u00a0"])
def test_empty_and_whitespace_documents_are_preserved_without_tokenizing(content):
    service = ChunkingService(
        ExplodingTokenizer(), max_tokens=2, overlap_tokens=0
    )

    result = service.chunk([make_document(content)])

    assert result.document_count == 1
    document = result.documents[0]
    assert document.content_length == len(content)
    assert document.token_count == 0
    assert document.chunks == ()
    assert document.chunk_count == 0
    assert result.chunk_count == 0
    assert result.has_chunks is False


def test_non_empty_documents_are_tokenized_exactly_once():
    tokenizer = WhitespaceTokenizer()
    service = ChunkingService(tokenizer, max_tokens=2, overlap_tokens=0)

    service.chunk(
        [
            make_document("one two", document_id="a" * 64, source_path="a.md"),
            make_document("", document_id="b" * 64, source_path="b.md"),
            make_document("three four", document_id="c" * 64, source_path="c.md"),
        ]
    )

    assert tokenizer.calls == 2


# --- Test 17: aggregate construction invariants ----------------------------


def test_duplicate_document_pairs_are_rejected_before_chunking():
    service = ChunkingService(ExplodingTokenizer(), max_tokens=2, overlap_tokens=0)
    documents = [
        make_document("same content"),
        make_document("same content"),
    ]

    with pytest.raises(ValueError, match="duplicate"):
        service.chunk(documents)


def test_duplicate_pairs_are_rejected_even_for_zero_chunk_documents():
    service = ChunkingService(WhitespaceTokenizer(), max_tokens=2, overlap_tokens=0)

    with pytest.raises(ValueError, match="duplicate"):
        service.chunk([make_document(""), make_document("")])


def test_result_rejects_a_configuration_mismatch():
    service = ChunkingService(WhitespaceTokenizer(), max_tokens=2, overlap_tokens=0)
    result = service.chunk([make_document("one two three")])
    other = ChunkingConfig(
        max_tokens=3,
        overlap_tokens=0,
        tokenizer_id=TOKENIZER_ID,
    )

    with pytest.raises(ValueError, match="config"):
        ChunkingResult(config=other, documents=result.documents)


def test_result_rejects_duplicate_documents_at_construction():
    service = ChunkingService(WhitespaceTokenizer(), max_tokens=2, overlap_tokens=0)
    document = service.chunk([make_document("one two")]).documents[0]

    with pytest.raises(ValueError, match="duplicate"):
        ChunkingResult(config=service.config, documents=(document, document))


# --- Test 18: purity and error roles ---------------------------------------


def test_service_imports_no_io_or_infrastructure_modules():
    source = Path(service_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert not any(
        module == "app.core" or module.startswith("app.core.")
        for module in imported_modules
    )
    assert "app.core.config" not in imported_modules
    assert imported_modules.isdisjoint(
        {
            "socket",
            "http",
            "urllib",
            "requests",
            "httpx",
            "sqlalchemy",
            "psycopg",
            "qdrant_client",
            "fastapi",
        }
    )


def test_service_performs_no_io(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("chunking service attempted I/O")

    monkeypatch.setattr("builtins.open", fail)

    result = ChunkingService(
        WhitespaceTokenizer(), max_tokens=2, overlap_tokens=0
    ).chunk([make_document("one two three")])

    assert result.chunk_count > 0


def test_tokenizer_contract_errors_propagate_without_document_content():
    service = ChunkingService(EmptyTokenizer(), max_tokens=2, overlap_tokens=0)

    with pytest.raises(TokenizerContractError) as caught:
        service.chunk([make_document("SECRET customer payload")])

    assert caught.value.reason == "missing_tokens"
    assert "SECRET" not in str(caught.value)
    assert "customer payload" not in str(caught.value)
