"""Production tokenizer adapter for the approved embedding model.

The adapter loads the vendored ``tokenizer.json`` from a local filesystem path,
computes its SHA-256, and implements the chunking ``Tokenizer`` protocol. It
performs no network I/O and never contacts the Hugging Face Hub.

The installed ``tokenizers`` Python binding reports Unicode code-point offsets.
That is verified during initialization with a small multibyte probe before the
offsets are passed to the existing contract helpers.

The adapter never mutates the loaded configuration. It verifies that the
vendored asset already has truncation and padding disabled and fails safely
with a contract error if either is enabled. Special-token insertion is disabled
per call with ``add_special_tokens=False``.

Concurrency: the adapter performs no mutation after construction. It does not
declare thread safety beyond the underlying ``tokenizers.Tokenizer.encode``
implementation; callers must not assume concurrent use is safe without
verification. The chunking service uses the adapter sequentially.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import tokenizers
from tokenizers import Tokenizer as LibraryTokenizer

from app.rag.chunking.exceptions import TokenizerContractError
from app.rag.chunking.tokenizer import (
    TokenSpan,
    normalize_spans,
    validate_identity,
)
from app.rag.ingestion.paths import default_repo_root

__all__ = [
    "ASSET_RELATIVE_PATH",
    "MODEL_ID",
    "REVISION",
    "NomicEmbedTextTokenizer",
    "default_asset_path",
]

MODEL_ID = "nomic-ai/nomic-embed-text-v1.5"
REVISION = "e9b6763023c676ca8431644204f50c2b100d9aab"
ASSET_RELATIVE_PATH = Path("assets/tokenizers/nomic-embed-text-v1.5/tokenizer.json")

# One accented code point followed by a four-byte emoji code point. Byte offsets
# would exceed ``len(probe)``; code-point offsets cannot.
_OFFSET_PROBE = "é😀"


def default_asset_path(repo_root: Path | None = None) -> Path:
    """Return the vendored tokenizer asset path beneath the repository root."""
    root = default_repo_root() if repo_root is None else Path(repo_root)
    return root / ASSET_RELATIVE_PATH


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class NomicEmbedTextTokenizer:
    """Local-only tokenizer for ``nomic-ai/nomic-embed-text-v1.5``.

    The asset is loaded from disk on construction. The vendored configuration
    must already have truncation and padding disabled; the adapter verifies
    this and fails safely rather than mutating it. Special-token insertion is
    disabled per call so that token spans partition the exact source text and
    the token count matches the underlying tokenizer.
    """

    def __init__(self, asset_path: str | Path | None = None):
        path = Path(asset_path) if asset_path is not None else default_asset_path()
        if not path.is_absolute():
            path = default_repo_root() / path

        try:
            asset_bytes = path.read_bytes()
        except OSError:
            raise TokenizerContractError("tokenizer_asset_unreadable") from None

        try:
            tokenizer = LibraryTokenizer.from_str(asset_bytes.decode("utf-8"))
        except Exception:
            raise TokenizerContractError("tokenizer_asset_invalid") from None

        self._tokenizer = tokenizer
        self._verify_asset_configuration()
        self._verify_code_point_offsets()
        self._identity = validate_identity(
            f"tokenizers:{tokenizers.__version__}:{MODEL_ID}"
            f"@{REVISION}:{_sha256_hex(asset_bytes)}"
        )

    @property
    def identity(self) -> str:
        """Stable identity: library, model, revision, and asset digest."""
        return self._identity

    def tokenize(self, text: str) -> tuple[TokenSpan, ...]:
        """Tokenize ``text`` into normalized code-point spans."""
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if text == "":
            return ()

        return normalize_spans(text, self._raw_spans(text))

    def _raw_spans(self, text: str) -> tuple[TokenSpan, ...]:
        encoding = self._tokenizer.encode(text, add_special_tokens=False)
        return tuple(
            TokenSpan(start_offset=start, end_offset=end)
            for start, end in encoding.offsets
        )

    def _verify_asset_configuration(self) -> None:
        """Fail instead of mutating an asset that enables truncation/padding."""
        if self._tokenizer.truncation is not None:
            raise TokenizerContractError("asset_truncation_enabled")
        if self._tokenizer.padding is not None:
            raise TokenizerContractError("asset_padding_enabled")

    def _verify_code_point_offsets(self) -> None:
        """Reject a library that reports byte offsets instead of code points."""
        spans = self._raw_spans(_OFFSET_PROBE)
        if not spans:
            raise TokenizerContractError("offset_probe_failed")
        if any(
            span.start_offset < 0
            or span.end_offset > len(_OFFSET_PROBE)
            or span.start_offset >= span.end_offset
            for span in spans
        ):
            raise TokenizerContractError("unsupported_offset_units")
