import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

import app.rag.chunking.chunker as chunker_module
from app.rag.chunking.chunker import (
    choose_cut,
    chunk_document,
    is_paragraph_boundary,
    is_sentence_boundary,
    is_word_boundary,
)
from app.rag.chunking.contracts import ChunkingConfig
from app.rag.chunking.exceptions import TokenizerContractError
from app.rag.chunking.tokenizer import TokenSpan, normalize_spans
from app.rag.ingestion.contracts import KnowledgeDocument

DOCUMENT_ID = "d" * 64
SOURCE_PATH = "docs/policy.md"
TITLE = "Policy"
FORMAT = "markdown"
TOKENIZER_ID = "fixture-whitespace|1.0|unicode-codepoints"


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


@dataclass(frozen=True)
class FixedSpanTokenizer:
    """Deterministic fixture: raw spans of a fixed code-point width."""

    width: int
    identity: str = "fixture-fixed|1.0"

    def tokenize(self, text: str) -> tuple[TokenSpan, ...]:
        return tuple(
            TokenSpan(offset, min(offset + self.width, len(text)))
            for offset in range(0, len(text), self.width)
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


class OutOfBoundsTokenizer:
    """Violates §5.2 by returning a span beyond the source length."""

    identity = "fixture-out-of-bounds|1.0"

    def tokenize(self, text: str) -> tuple[TokenSpan, ...]:
        return (TokenSpan(0, len(text) + 1),)


def make_document(content: str, **overrides) -> KnowledgeDocument:
    values = {
        "document_id": DOCUMENT_ID,
        "source_path": SOURCE_PATH,
        "title": TITLE,
        "format": FORMAT,
        "content": content,
        "size_bytes": len(content.encode("utf-8")),
    }
    values.update(overrides)
    return KnowledgeDocument(**values)


def config(
    max_tokens: int,
    overlap_tokens: int = 0,
    tokenizer_id: str = TOKENIZER_ID,
) -> ChunkingConfig:
    return ChunkingConfig(
        max_tokens=max_tokens,
        overlap_tokens=overlap_tokens,
        tokenizer_id=tokenizer_id,
    )


def chunk(
    content: str,
    max_tokens: int,
    overlap_tokens: int = 0,
    tokenizer=None,
) -> tuple[KnowledgeDocument, ChunkingConfig]:
    document = make_document(content)
    return chunk_document(
        document,
        tokenizer or WhitespaceTokenizer(),
        config(max_tokens, overlap_tokens),
    ), config(max_tokens, overlap_tokens)


# --- Test 3: exact source slicing ------------------------------------------


@pytest.mark.parametrize(
    "content",
    [
        "Alpha beta gamma.",
        "  leading and trailing  ",
        "Line one\n\nLine two.\n",
        "A😀 e\u0301 日本語",
        "word,word;word!",
    ],
)
@pytest.mark.parametrize(("max_tokens", "overlap"), [(1, 0), (2, 1), (5, 2)])
def test_chunks_are_exact_source_slices(content, max_tokens, overlap):
    result, _ = chunk(content, max_tokens, overlap)

    for entry in result.chunks:
        assert entry.content == content[entry.start_offset : entry.end_offset]
        assert entry.char_count == len(entry.content)
        assert entry.char_count == entry.end_offset - entry.start_offset


# --- Test 4: token limit ---------------------------------------------------


@pytest.mark.parametrize(
    ("max_tokens", "overlap"),
    [(1, 0), (2, 0), (2, 1), (3, 1), (5, 2), (8, 3)],
)
def test_every_chunk_respects_the_token_limit(max_tokens, overlap):
    result, _ = chunk(
        "one two three four five six seven eight nine ten",
        max_tokens,
        overlap,
    )

    assert result.chunks
    assert all(entry.token_count <= max_tokens for entry in result.chunks)


# --- Tests 5-8: boundary predicates and priority ---------------------------


@pytest.mark.parametrize(
    ("text", "p", "expected"),
    [
        ("a\n\nb", 3, True),
        ("a\n \t\nb", 5, True),
        ("a\n\n \t", 5, True),
        ("a\n\n", 3, True),
        ("a\nb", 2, False),
        ("a\n\nb", 2, False),
        ("a\r\n\r\nb", 5, False),
    ],
)
def test_paragraph_boundary_predicate(text, p, expected):
    assert is_paragraph_boundary(text, p) is expected


@pytest.mark.parametrize(
    ("text", "p", "expected"),
    [
        ("Hello.", 6, True),
        ("Hello. Next", 6, True),
        ("Hello.Next", 6, False),
        ("Value 1.2 next", 9, False),
        ("e.g. next", 4, True),
        ("Wait!  Next", 7, True),
        ("你好。世界", 3, False),
    ],
)
def test_sentence_boundary_predicate(text, p, expected):
    assert is_sentence_boundary(text, p) is expected


@pytest.mark.parametrize(
    ("text", "p", "expected"),
    [
        ("ab cd", 2, True),
        ("ab cd", 3, True),
        ("a\u00a0b", 1, True),
        ("a,b", 1, False),
        ("a,b", 2, False),
        ("日本語", 1, False),
        ("abc", 3, True),
    ],
)
def test_word_boundary_predicate(text, p, expected):
    assert is_word_boundary(text, p) is expected


def test_choose_cut_prefers_the_rightmost_paragraph_boundary():
    text = "a\n\nb\n\nc d"
    spans = normalize_spans(text, WhitespaceTokenizer().tokenize(text))

    assert choose_cut(text, spans, 0, 3) == 2


def test_paragraph_boundary_outranks_a_later_sentence_boundary():
    content = "A.\n\nB. C"
    result, _ = chunk(content, 2, 0)

    assert result.token_count == 3
    assert result.chunks[0].token_count == 1
    assert result.chunks[0].content == "A.\n\n"


def test_sentence_boundary_outranks_a_word_boundary():
    content = "Hi there. Next"
    result, _ = chunk(content, 2, 0)

    assert result.chunks[0].token_count == 2
    assert result.chunks[0].content == "Hi there. "


def test_word_boundary_is_used_when_no_paragraph_or_sentence_applies():
    content = "ab cd ef gh"
    result, _ = chunk(content, 2, 0)

    assert result.chunks[0].token_count == 2
    assert result.chunks[0].content == "ab cd "


def test_hard_cut_is_used_when_no_preferred_boundary_qualifies():
    content = "abcdefgh"
    result, _ = chunk(content, 2, 0, tokenizer=FixedSpanTokenizer(width=2))

    assert result.chunks[0].token_count == 2
    assert result.chunks[0].content == "abcd"


# --- Test 9: overlap -------------------------------------------------------


def test_zero_overlap_produces_non_overlapping_token_windows_and_slices():
    result, _ = chunk("one two three four five six", 2, 0)

    for previous, current in zip(result.chunks, result.chunks[1:]):
        assert current.token_start == previous.token_end
        assert current.start_offset == previous.end_offset


@pytest.mark.parametrize("overlap", [1, 2, 3])
def test_actual_overlap_never_exceeds_the_target(overlap):
    result, _ = chunk("one two three four five six seven eight", 5, overlap)

    for previous, current in zip(result.chunks, result.chunks[1:]):
        actual = previous.token_end - current.token_start
        assert 0 <= actual <= overlap
        assert current.token_start > previous.token_start


def test_a_chunk_shorter_than_the_overlap_target_still_makes_progress():
    content = "a\n\nbcdefgh"
    result, _ = chunk(
        content, 3, 2, tokenizer=FixedSpanTokenizer(width=3)
    )

    assert result.chunks[0].token_count == 1
    assert result.chunks[1].token_start == 1
    assert result.chunks[1].token_start > result.chunks[0].token_start


# --- Test 10: coverage -----------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [
        "one two three",
        "a\n\nb. c d",
        "  lead trail  ",
        "😀e\u0301 日本語",
    ],
)
@pytest.mark.parametrize(("max_tokens", "overlap"), [(1, 0), (2, 1), (4, 2)])
def test_every_token_and_source_character_is_covered(content, max_tokens, overlap):
    result, _ = chunk(content, max_tokens, overlap)

    assert result.token_count > 0
    assert result.chunks[0].token_start == 0
    assert result.chunks[-1].token_end == result.token_count
    assert result.chunks[0].start_offset == 0
    assert result.chunks[-1].end_offset == len(content)

    for previous, current in zip(result.chunks, result.chunks[1:]):
        assert current.token_start > previous.token_start
        assert current.token_start <= previous.token_end
        assert current.start_offset > previous.start_offset
        assert current.start_offset <= previous.end_offset

    for position in range(len(content)):
        assert any(
            entry.start_offset <= position < entry.end_offset
            for entry in result.chunks
        )


# --- Test 11: bounded short chunks -----------------------------------------


@pytest.mark.parametrize(
    "content",
    [
        "a\n\nb\n\nc\n\nd",
        "a b c d e",
        "abcdefgh",
        "one. two! three? four",
    ],
)
@pytest.mark.parametrize(("max_tokens", "overlap"), [(1, 0), (2, 0), (2, 1), (3, 2)])
def test_chunk_count_never_exceeds_token_count(content, max_tokens, overlap):
    result, _ = chunk(content, max_tokens, overlap)

    assert result.token_count > 0
    assert 0 < result.chunk_count <= result.token_count


def test_repeated_boundaries_do_not_loop_forever():
    content = "\n\n".join(["x"] * 50)
    result, _ = chunk(content, 2, 1)

    assert 0 < result.chunk_count <= result.token_count


# --- Test 12: determinism --------------------------------------------------


def test_chunking_is_deterministic():
    content = "Alpha beta. Gamma\n\nDelta epsilon zeta eta theta"
    first, _ = chunk(content, 3, 1)
    second, _ = chunk(content, 3, 1)

    assert first == second
    assert tuple(entry.chunk_id for entry in first.chunks) == tuple(
        entry.chunk_id for entry in second.chunks
    )


def test_identical_content_at_different_paths_has_distinct_chunk_ids():
    first = chunk_document(
        make_document("same content", source_path="docs/a.md"),
        WhitespaceTokenizer(),
        config(2),
    )
    second = chunk_document(
        make_document("same content", source_path="docs/b.md"),
        WhitespaceTokenizer(),
        config(2),
    )

    assert first.chunks[0].content == second.chunks[0].content
    assert first.chunks[0].chunk_id != second.chunks[0].chunk_id


# --- Test 13: metadata and indexes -----------------------------------------


def test_chunk_metadata_and_indexes_match_the_document():
    content = "one two three four five"
    document = make_document(
        content,
        document_id="a" * 64,
        source_path="docs/refunds.md",
        title="Refunds",
    )
    effective_config = config(2, 1)
    result = chunk_document(document, WhitespaceTokenizer(), effective_config)

    assert result.document_id == document.document_id
    assert result.source_path == document.source_path
    assert result.title == document.title
    assert result.format == document.format
    assert result.content_length == len(content)
    assert result.chunk_count == len(result.chunks)

    for position, entry in enumerate(result.chunks):
        assert entry.chunk_index == position
        assert entry.document_id == document.document_id
        assert entry.source_path == document.source_path
        assert entry.title == document.title
        assert entry.format == document.format
        assert entry.chunking_config_id == effective_config.config_id
        assert 0 <= entry.token_start < entry.token_end <= result.token_count
        assert entry.token_count == entry.token_end - entry.token_start
        assert 0 <= entry.start_offset < entry.end_offset <= result.content_length
        assert len(entry.content) == entry.end_offset - entry.start_offset


# --- Test 14: Unicode ------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [
        "😀😀😀😀",
        "e\u0301e\u0301e\u0301e\u0301",
        "日本語日本語",
        "a😀 b\u0301 日",
    ],
)
def test_unicode_offsets_are_code_points_and_slices_are_exact(content):
    result, _ = chunk(
        content, 2, 0, tokenizer=FixedSpanTokenizer(width=2)
    )

    assert result.content_length == len(content)
    assert result.chunks[-1].end_offset == len(content)

    for entry in result.chunks:
        assert entry.content == content[entry.start_offset : entry.end_offset]
        assert entry.end_offset - entry.start_offset == len(entry.content)


def test_astral_characters_count_as_one_code_point():
    result, _ = chunk("😀", 1, 0)

    assert result.content_length == 1
    assert result.chunks[0].start_offset == 0
    assert result.chunks[0].end_offset == 1
    assert result.chunks[0].content == "😀"


# --- Test 15: empty and whitespace-only documents --------------------------


@pytest.mark.parametrize("content", ["", " ", "\n\t ", "\u00a0"])
def test_empty_and_whitespace_documents_are_not_tokenized(content):
    result = chunk_document(
        make_document(content),
        ExplodingTokenizer(),
        config(2, 0),
    )

    assert result.content_length == len(content)
    assert result.token_count == 0
    assert result.chunks == ()
    assert result.chunk_count == 0


def test_non_empty_document_is_tokenized_exactly_once():
    tokenizer = WhitespaceTokenizer()
    chunk_document(make_document("one two three"), tokenizer, config(2, 0))

    assert tokenizer.calls == 1


# --- Test 18: purity and error roles ---------------------------------------


def test_non_whitespace_content_without_spans_raises_contract_error():
    with pytest.raises(TokenizerContractError) as caught:
        chunk_document(
            make_document("SECRET customer payload"),
            EmptyTokenizer(),
            config(2, 0),
        )

    assert caught.value.reason == "missing_tokens"
    assert "SECRET" not in str(caught.value)
    assert "customer payload" not in str(caught.value)


def test_out_of_bounds_spans_raise_without_document_content():
    with pytest.raises(TokenizerContractError) as caught:
        chunk_document(
            make_document("SECRET customer payload"),
            OutOfBoundsTokenizer(),
            config(2, 0),
        )

    assert caught.value.reason == "span_out_of_bounds"
    assert "SECRET" not in str(caught.value)


def test_chunker_imports_no_io_or_infrastructure_modules():
    source = Path(chunker_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    assert imported_roots.isdisjoint(
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


def test_chunking_performs_no_io(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("chunking attempted I/O")

    monkeypatch.setattr("builtins.open", fail)

    result, _ = chunk("one two three four", 2, 0)

    assert result.chunk_count > 0
