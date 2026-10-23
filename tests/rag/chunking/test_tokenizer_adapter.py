import ast
import hashlib
import socket
from pathlib import Path

import pytest
import tokenizers

from app.rag.chunking.exceptions import TokenizerContractError
from app.rag.chunking.tokenizer import TokenSpan
from app.rag.chunking.tokenizer_adapter import (
    ASSET_RELATIVE_PATH,
    MODEL_ID,
    REVISION,
    NomicEmbedTextTokenizer,
    default_asset_path,
)
from app.rag.ingestion.paths import default_repo_root

CONTEXT_LIMIT = 2048
MAX_TOKENS = 500
EMBEDDING_PREFIX = "search_document: "


@pytest.fixture(scope="module")
def adapter() -> NomicEmbedTextTokenizer:
    return NomicEmbedTextTokenizer()


def assert_partition(text: str, spans: tuple[TokenSpan, ...]) -> None:
    assert spans
    assert spans[0].start_offset == 0
    assert spans[-1].end_offset == len(text)
    assert "".join(
        text[span.start_offset : span.end_offset] for span in spans
    ) == text
    for left, right in zip(spans, spans[1:]):
        assert left.end_offset == right.start_offset
    for span in spans:
        assert 0 <= span.start_offset < span.end_offset <= len(text)


# --- Identity ---------------------------------------------------------------


def test_identity_uses_the_approved_format_and_actual_asset_digest(
    adapter: NomicEmbedTextTokenizer,
) -> None:
    digest = hashlib.sha256(default_asset_path().read_bytes()).hexdigest()

    assert len(digest) == 64
    assert adapter.identity == (
        f"tokenizers:{tokenizers.__version__}:{MODEL_ID}@{REVISION}:{digest}"
    )
    assert MODEL_ID == "nomic-ai/nomic-embed-text-v1.5"
    assert REVISION == "e9b6763023c676ca8431644204f50c2b100d9aab"


def test_identity_is_stable_across_instances(
    adapter: NomicEmbedTextTokenizer,
) -> None:
    assert NomicEmbedTextTokenizer().identity == adapter.identity


def test_identity_digest_tracks_the_loaded_bytes(tmp_path: Path) -> None:
    original = default_asset_path().read_bytes()
    altered = original + b"\n"
    path = tmp_path / "tokenizer.json"
    path.write_bytes(altered)

    altered_adapter = NomicEmbedTextTokenizer(path)

    assert altered_adapter.identity.endswith(hashlib.sha256(altered).hexdigest())
    assert altered_adapter.identity != NomicEmbedTextTokenizer().identity


# --- Loading and runtime ----------------------------------------------------


def test_default_asset_path_is_the_vendored_local_file() -> None:
    path = default_asset_path()

    assert path == default_repo_root() / ASSET_RELATIVE_PATH
    assert path.is_file()


def test_adapter_does_not_mutate_the_loaded_configuration(
    adapter: NomicEmbedTextTokenizer,
) -> None:
    reference = tokenizers.Tokenizer.from_str(
        default_asset_path().read_text(encoding="utf-8")
    )

    assert adapter._tokenizer.truncation is None
    assert adapter._tokenizer.padding is None
    assert adapter._tokenizer.truncation == reference.truncation
    assert adapter._tokenizer.padding == reference.padding


def test_adapter_does_not_modify_the_asset_file() -> None:
    path = default_asset_path()
    before = path.read_bytes()

    NomicEmbedTextTokenizer()

    assert path.read_bytes() == before


def test_asset_with_truncation_enabled_is_rejected(tmp_path: Path) -> None:
    source = tokenizers.Tokenizer.from_str(
        default_asset_path().read_text(encoding="utf-8")
    )
    source.enable_truncation(max_length=10)
    path = tmp_path / "tokenizer.json"
    path.write_text(source.to_str(), encoding="utf-8")

    with pytest.raises(TokenizerContractError) as caught:
        NomicEmbedTextTokenizer(path)

    assert caught.value.reason == "asset_truncation_enabled"
    assert str(path) not in str(caught.value)


def test_asset_with_padding_enabled_is_rejected(tmp_path: Path) -> None:
    source = tokenizers.Tokenizer.from_str(
        default_asset_path().read_text(encoding="utf-8")
    )
    source.enable_padding(pad_id=0, pad_token="[PAD]")
    path = tmp_path / "tokenizer.json"
    path.write_text(source.to_str(), encoding="utf-8")

    with pytest.raises(TokenizerContractError) as caught:
        NomicEmbedTextTokenizer(path)

    assert caught.value.reason == "asset_padding_enabled"
    assert str(path) not in str(caught.value)


def test_tokenization_does_not_require_network_access(monkeypatch) -> None:
    def blocked(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)

    adapter = NomicEmbedTextTokenizer()

    assert adapter.tokenize("customer refund policy")


def test_adapter_imports_no_network_or_hub_modules() -> None:
    import app.rag.chunking.tokenizer_adapter as adapter_module

    tree = ast.parse(Path(adapter_module.__file__).read_text(encoding="utf-8"))

    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    assert imported_roots.isdisjoint(
        {
            "aiohttp",
            "http",
            "httpx",
            "huggingface_hub",
            "requests",
            "socket",
            "urllib",
        }
    )


# --- Tokenization contract --------------------------------------------------


def test_tokenization_is_deterministic(adapter: NomicEmbedTextTokenizer) -> None:
    text = "Refunds are processed within 5-7 business days."

    first = adapter.tokenize(text)

    assert first == adapter.tokenize(text)
    assert isinstance(first, tuple)


@pytest.mark.parametrize(
    "text",
    [
        "naïve café",
        "日本語の返金ポリシー",
        "emoji 😀 and é",
        "a\tb\nc  d",
        "Refunds: 30 days.",
    ],
)
def test_spans_are_a_complete_partition_of_the_source(
    adapter: NomicEmbedTextTokenizer, text: str
) -> None:
    assert_partition(text, adapter.tokenize(text))


def test_non_ascii_offsets_are_unicode_code_points(
    adapter: NomicEmbedTextTokenizer,
) -> None:
    text = "日本語"

    assert adapter.tokenize(text) == (
        TokenSpan(0, 1),
        TokenSpan(1, 2),
        TokenSpan(2, 3),
    )


def test_emoji_offsets_are_unicode_code_points(
    adapter: NomicEmbedTextTokenizer,
) -> None:
    text = "😀a"

    spans = adapter.tokenize(text)

    assert spans == (TokenSpan(0, 2),)
    assert len(text.encode("utf-8")) == 5
    assert spans[0].end_offset == len(text)


def test_special_tokens_are_not_inserted(
    adapter: NomicEmbedTextTokenizer,
) -> None:
    text = "hello"

    spans = adapter.tokenize(text)

    assert len(spans) == 1
    assert text[spans[0].start_offset : spans[0].end_offset] == text


def test_long_input_is_not_truncated(adapter: NomicEmbedTextTokenizer) -> None:
    text = "word " * 600

    spans = adapter.tokenize(text)

    assert len(spans) == 600
    assert_partition(text, spans)


def test_empty_input_returns_an_empty_tuple(
    adapter: NomicEmbedTextTokenizer,
) -> None:
    assert adapter.tokenize("") == ()


@pytest.mark.parametrize("text", [" ", "\n", "\t\r\n  "])
def test_whitespace_only_input_returns_an_empty_tuple(
    adapter: NomicEmbedTextTokenizer, text: str
) -> None:
    assert adapter.tokenize(text) == ()


def test_non_whitespace_without_tokens_is_rejected(
    adapter: NomicEmbedTextTokenizer, monkeypatch
) -> None:
    monkeypatch.setattr(adapter, "_raw_spans", lambda text: ())

    with pytest.raises(TokenizerContractError) as caught:
        adapter.tokenize("SECRET customer payload")

    assert caught.value.reason == "missing_tokens"
    assert "SECRET" not in str(caught.value)
    assert "customer" not in str(caught.value)


def test_out_of_bounds_offsets_are_rejected_safely(
    adapter: NomicEmbedTextTokenizer, monkeypatch
) -> None:
    monkeypatch.setattr(
        adapter, "_raw_spans", lambda text: (TokenSpan(0, len(text) + 1),)
    )

    with pytest.raises(TokenizerContractError) as caught:
        adapter.tokenize("é")

    assert caught.value.reason == "span_out_of_bounds"
    assert "é" not in str(caught.value)


def test_overlapping_offsets_are_rejected(
    adapter: NomicEmbedTextTokenizer, monkeypatch
) -> None:
    monkeypatch.setattr(
        adapter,
        "_raw_spans",
        lambda text: (TokenSpan(0, 2), TokenSpan(1, 3)),
    )

    with pytest.raises(TokenizerContractError) as caught:
        adapter.tokenize("abc")

    assert caught.value.reason == "overlapping_spans"


def test_missing_asset_raises_a_safe_error(tmp_path: Path) -> None:
    missing = tmp_path / "sensitive-location" / "tokenizer.json"

    with pytest.raises(TokenizerContractError) as caught:
        NomicEmbedTextTokenizer(missing)

    assert caught.value.reason == "tokenizer_asset_unreadable"
    assert str(missing) not in str(caught.value)
    assert "sensitive-location" not in str(caught.value)


def test_corrupt_asset_raises_a_safe_error(tmp_path: Path) -> None:
    path = tmp_path / "tokenizer.json"
    path.write_text("not a tokenizer", encoding="utf-8")

    with pytest.raises(TokenizerContractError) as caught:
        NomicEmbedTextTokenizer(path)

    assert caught.value.reason == "tokenizer_asset_invalid"
    assert "not a tokenizer" not in str(caught.value)
    assert str(path) not in str(caught.value)


# --- Context-limit conformance ---------------------------------------------


def test_500_token_chunks_fit_the_conservative_2048_token_limit(
    adapter: NomicEmbedTextTokenizer,
) -> None:
    library_tokenizer = tokenizers.Tokenizer.from_str(
        default_asset_path().read_text(encoding="utf-8")
    )

    prefix_count = len(
        library_tokenizer.encode(
            EMBEDDING_PREFIX, add_special_tokens=False
        ).ids
    )
    without_specials = len(
        library_tokenizer.encode("x", add_special_tokens=False).ids
    )
    with_specials = len(
        library_tokenizer.encode("x", add_special_tokens=True).ids
    )
    special_count = with_specials - without_specials

    assert len(adapter.tokenize(EMBEDDING_PREFIX)) == prefix_count
    assert prefix_count == 4
    assert special_count == 2
    assert MAX_TOKENS + prefix_count + special_count <= CONTEXT_LIMIT
