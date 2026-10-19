"""Per-file loading pipeline for knowledge document ingestion.

``load_document`` runs the exact ordered pipeline from the specification:
containment, size, bounded read, decode, normalization, whitespace validation,
and metadata extraction. The first failing step decides the outcome, and
per-file failures are returned as ``FailedEntry`` records rather than raised so
that a run can continue with the remaining candidates.

Nothing outside the resolved source root is ever read, and no message or
result carries document content.
"""

import hashlib
from pathlib import Path

from app.rag.ingestion.contracts import (
    FORMAT_MARKDOWN,
    FORMAT_TEXT,
    FailedEntry,
    KnowledgeDocument,
)
from app.rag.ingestion.exceptions import (
    DocumentDecodeError,
    DocumentReadError,
    DocumentTooLargeError,
    EmptyDocumentError,
    IngestionError,
    PathContainmentError,
)

_MARKDOWN_SUFFIX = ".md"
_TEXT_SUFFIX = ".txt"
_FENCE_MARKERS = ("```", "~~~")


def load_document(
    source_root: Path,
    relative_path: str,
    max_document_bytes: int,
) -> KnowledgeDocument | FailedEntry:
    """Load one discovered candidate into a normalized document.

    ``relative_path`` must be a supported document discovered beneath
    ``source_root``. Returns a ``KnowledgeDocument`` on success, or a
    ``FailedEntry`` describing the first failing pipeline step.
    """
    root = Path(source_root)
    candidate = root / relative_path

    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=False)
    except OSError:
        return _failure(relative_path, DocumentReadError(relative_path))

    if not resolved.is_relative_to(resolved_root):
        return _failure(relative_path, PathContainmentError(relative_path))

    try:
        stat_result = resolved.stat()
    except OSError:
        return _failure(relative_path, DocumentReadError(relative_path))

    size_bytes = stat_result.st_size
    if size_bytes > max_document_bytes:
        return _failure(relative_path, DocumentTooLargeError(relative_path))

    try:
        with resolved.open("rb") as handle:
            raw = handle.read(max_document_bytes + 1)
    except OSError:
        return _failure(relative_path, DocumentReadError(relative_path))

    if len(raw) > max_document_bytes:
        return _failure(relative_path, DocumentTooLargeError(relative_path))

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _failure(relative_path, DocumentDecodeError(relative_path))

    content = normalize_content(text)
    if not content.strip():
        return _failure(relative_path, EmptyDocumentError(relative_path))

    return KnowledgeDocument(
        document_id=content_id(content),
        source_path=relative_path,
        title=extract_title(content, relative_path),
        format=document_format(relative_path),
        content=content,
        size_bytes=size_bytes,
    )


def normalize_content(text: str) -> str:
    """Convert CRLF and bare-CR line endings to LF; alter nothing else."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def content_id(content: str) -> str:
    """Return the lowercase hex SHA-256 digest of the normalized content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def document_format(relative_path: str) -> str:
    """Return the document format for a supported path.

    Raises ``ValueError`` for a path whose extension is not supported; only
    discovered candidates are expected to reach the loader.
    """
    name = Path(relative_path).name.lower()
    if name.endswith(_MARKDOWN_SUFFIX):
        return FORMAT_MARKDOWN
    if name.endswith(_TEXT_SUFFIX):
        return FORMAT_TEXT
    raise ValueError(f"unsupported document extension: {relative_path}")


def extract_title(content: str, source_path: str) -> str:
    """Return the first ATX H1 outside fenced code blocks, or a fallback.

    Falls back to the filename stem, and to ``source_path`` when the stem is
    empty. Setext headings are not recognized.
    """
    fence_marker: str | None = None

    for line in content.split("\n"):
        stripped = line.strip()

        if fence_marker is not None:
            if stripped.startswith(fence_marker):
                fence_marker = None
            continue

        for marker in _FENCE_MARKERS:
            if stripped.startswith(marker):
                fence_marker = marker
                break
        else:
            if stripped.startswith("# "):
                return _heading_text(stripped)

    return _fallback_title(source_path)


def _heading_text(stripped_line: str) -> str:
    text = stripped_line[2:].strip()
    without_closing = text.rstrip("#")
    if without_closing != text and (
        without_closing == "" or text[len(without_closing) - 1] == " "
    ):
        return without_closing.rstrip()
    return text


def _fallback_title(source_path: str) -> str:
    stem = Path(source_path).stem
    return stem if stem else source_path


def _failure(relative_path: str, error: IngestionError) -> FailedEntry:
    return FailedEntry.from_error(relative_path, error)
