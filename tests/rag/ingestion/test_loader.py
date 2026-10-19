import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.rag.ingestion.contracts import (
    FORMAT_MARKDOWN,
    FORMAT_TEXT,
    FailedEntry,
    KnowledgeDocument,
)
from app.rag.ingestion.loader import (
    content_id,
    extract_title,
    load_document,
    normalize_content,
)

SYMLINKS_SUPPORTED = hasattr(os, "symlink")


def write(root: Path, relative: str, content: bytes | str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def test_loads_supported_document_with_complete_metadata(tmp_path):
    content = "# Refunds\nPolicy body\n"
    write(tmp_path, "docs/refunds.md", content)

    document = load_document(tmp_path, "docs/refunds.md", 1024)

    assert isinstance(document, KnowledgeDocument)
    assert document.source_path == "docs/refunds.md"
    assert document.format == FORMAT_MARKDOWN
    assert document.title == "Refunds"
    assert document.content == content
    assert document.size_bytes == len(content.encode("utf-8"))
    assert document.document_id == hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_text_format_is_detected(tmp_path):
    write(tmp_path, "notes.txt", "hello")

    document = load_document(tmp_path, "notes.txt", 1024)

    assert document.format == FORMAT_TEXT


def test_format_matching_is_case_insensitive(tmp_path):
    write(tmp_path, "UPPER.MD", "# Title")

    assert load_document(tmp_path, "UPPER.MD", 1024).format == FORMAT_MARKDOWN


def test_file_exactly_at_the_size_limit_is_accepted(tmp_path):
    write(tmp_path, "doc.txt", "abcde")

    document = load_document(tmp_path, "doc.txt", 5)

    assert isinstance(document, KnowledgeDocument)
    assert document.size_bytes == 5


def test_crlf_and_bare_cr_are_normalized_to_lf(tmp_path):
    write(tmp_path, "doc.txt", b"a\r\nb\rc\nd")

    document = load_document(tmp_path, "doc.txt", 1024)

    assert document.content == "a\nb\nc\nd"
    assert document.size_bytes == 8


def test_normalize_content_alters_nothing_else():
    assert normalize_content("  spaced  \r\n\r\n") == "  spaced  \n\n"


def test_size_bytes_reflects_original_bytes_while_id_reflects_normalized(tmp_path):
    content = "line1\nline2\n"
    write(tmp_path, "lf.txt", content.encode("utf-8"))
    write(tmp_path, "crlf.txt", content.replace("\n", "\r\n").encode("utf-8"))

    lf = load_document(tmp_path, "lf.txt", 1024)
    crlf = load_document(tmp_path, "crlf.txt", 1024)

    assert lf.size_bytes == 12
    assert crlf.size_bytes == 14
    assert crlf.content == lf.content
    assert crlf.document_id == lf.document_id


def test_identical_content_at_two_paths_shares_the_id(tmp_path):
    write(tmp_path, "a.md", "# Same\n")
    write(tmp_path, "b.md", "# Same\n")

    first = load_document(tmp_path, "a.md", 1024)
    second = load_document(tmp_path, "b.md", 1024)

    assert first.document_id == second.document_id
    assert (first.source_path, second.source_path) == ("a.md", "b.md")


def test_content_id_matches_sha256_of_normalized_utf8_bytes(tmp_path):
    write(tmp_path, "doc.md", b"caf\xc3\xa9\r\n")

    document = load_document(tmp_path, "doc.md", 1024)

    assert document.content == "café\n"
    assert document.document_id == hashlib.sha256("café\n".encode("utf-8")).hexdigest()
    assert content_id(document.content) == document.document_id


def test_utf8_bom_is_preserved(tmp_path):
    write(tmp_path, "doc.md", b"\xef\xbb\xbf# Title\n")

    document = load_document(tmp_path, "doc.md", 1024)

    assert document.content == "\ufeff# Title\n"


def test_title_uses_the_first_h1(tmp_path):
    write(tmp_path, "doc.md", "intro\n\n## Sub\nbody\n\n# Real Title\n")

    assert load_document(tmp_path, "doc.md", 1024).title == "Real Title"


def test_title_is_ignored_inside_backtick_fenced_code_blocks(tmp_path):
    write(tmp_path, "doc.md", "```\n# Not A Title\n```\n\n# Actual\n")

    assert load_document(tmp_path, "doc.md", 1024).title == "Actual"


def test_title_is_ignored_inside_tilde_fenced_code_blocks(tmp_path):
    write(tmp_path, "doc.md", "~~~python\n# Not A Title\n~~~\n# Actual\n")

    assert load_document(tmp_path, "doc.md", 1024).title == "Actual"


def test_title_allows_leading_whitespace_before_the_h1(tmp_path):
    write(tmp_path, "doc.md", "   # Indented Title\n")

    assert load_document(tmp_path, "doc.md", 1024).title == "Indented Title"


def test_title_requires_a_space_after_the_hash(tmp_path):
    write(tmp_path, "doc.md", "#NoSpace\n")

    assert load_document(tmp_path, "doc.md", 1024).title == "doc"


def test_title_strips_a_closing_hash_sequence(tmp_path):
    write(tmp_path, "doc.md", "# Title ###\n")

    assert load_document(tmp_path, "doc.md", 1024).title == "Title"


def test_title_keeps_hashes_without_a_preceding_space(tmp_path):
    write(tmp_path, "doc.md", "# Title###\n")

    assert load_document(tmp_path, "doc.md", 1024).title == "Title###"


def test_title_falls_back_to_the_filename_stem(tmp_path):
    write(tmp_path, "policies/refund-policy.md", "body only\n")

    assert load_document(tmp_path, "policies/refund-policy.md", 1024).title == (
        "refund-policy"
    )


def test_title_falls_back_to_the_source_path_when_the_stem_is_empty():
    assert extract_title("body only", "/") == "/"


def test_empty_file_fails_with_empty_document_error(tmp_path):
    write(tmp_path, "doc.md", "")

    entry = load_document(tmp_path, "doc.md", 1024)

    assert isinstance(entry, FailedEntry)
    assert entry.path == "doc.md"
    assert entry.error_type == "empty_document"


def test_whitespace_only_file_fails_with_empty_document_error(tmp_path):
    write(tmp_path, "doc.md", " \t\r\n\r\n")

    assert load_document(tmp_path, "doc.md", 1024).error_type == "empty_document"


def test_invalid_utf8_fails_with_decode_error(tmp_path):
    write(tmp_path, "doc.md", b"# Title\n\xff\xfe\n")

    assert load_document(tmp_path, "doc.md", 1024).error_type == "document_decode"


def test_oversized_file_fails_without_reading_content(tmp_path, monkeypatch):
    write(tmp_path, "doc.md", b"x" * 11)

    def fail(*args, **kwargs):
        raise AssertionError("oversized content must not be read")

    monkeypatch.setattr(Path, "open", fail)

    entry = load_document(tmp_path, "doc.md", 10)

    assert entry.error_type == "document_too_large"


def test_size_check_precedes_decode_and_whitespace_checks(tmp_path):
    write(tmp_path, "doc.md", b"\xff" * 11)

    assert load_document(tmp_path, "doc.md", 10).error_type == "document_too_large"


def test_bounded_read_detects_growth_between_stat_and_read(tmp_path, monkeypatch):
    write(tmp_path, "doc.md", b"abcdef")
    monkeypatch.setattr(Path, "stat", lambda self: SimpleNamespace(st_size=1))

    entry = load_document(tmp_path, "doc.md", 3)

    assert entry.error_type == "document_too_large"


def test_absolute_path_outside_the_root_is_rejected_without_reading(tmp_path, monkeypatch):
    root = tmp_path / "knowledge"
    root.mkdir()
    secret = write(tmp_path, "secret.md", "SECRET-PAYLOAD")

    def fail(*args, **kwargs):
        raise AssertionError("content outside the root must not be read")

    monkeypatch.setattr(Path, "open", fail)

    entry = load_document(root, str(secret), 1024)

    assert entry.error_type == "path_containment"
    assert "SECRET-PAYLOAD" not in entry.message


def test_parent_traversal_is_rejected_as_a_per_file_failure(tmp_path):
    root = tmp_path / "knowledge"
    root.mkdir()
    write(tmp_path, "outside.md", "content")

    assert load_document(root, "../outside.md", 1024).error_type == "path_containment"


@pytest.mark.skipif(not SYMLINKS_SUPPORTED, reason="symlinks unavailable")
def test_symlink_escaping_the_root_is_rejected_without_reading(tmp_path):
    root = tmp_path / "knowledge"
    root.mkdir()
    secret = write(tmp_path, "secret.md", "SECRET-PAYLOAD")
    os.symlink(secret, root / "escape.md")

    entry = load_document(root, "escape.md", 1024)

    assert entry.error_type == "path_containment"
    assert "SECRET-PAYLOAD" not in entry.message


@pytest.mark.skipif(not SYMLINKS_SUPPORTED, reason="symlinks unavailable")
def test_symlink_inside_the_root_is_ingested_normally(tmp_path):
    root = tmp_path / "knowledge"
    root.mkdir()
    write(root, "target.txt", "hello")
    os.symlink(root / "target.txt", root / "alias.md")

    document = load_document(root, "alias.md", 1024)

    assert isinstance(document, KnowledgeDocument)
    assert document.source_path == "alias.md"
    assert document.format == FORMAT_MARKDOWN
    assert document.content == "hello"


@pytest.mark.skipif(not SYMLINKS_SUPPORTED, reason="symlinks unavailable")
def test_broken_symlink_fails_with_read_error(tmp_path):
    root = tmp_path / "knowledge"
    root.mkdir()
    os.symlink(root / "missing.md", root / "broken.md")

    assert load_document(root, "broken.md", 1024).error_type == "document_read"


def test_missing_file_fails_with_read_error(tmp_path):
    assert load_document(tmp_path, "missing.md", 1024).error_type == "document_read"


def test_failure_messages_never_contain_document_content(tmp_path):
    write(tmp_path, "doc.md", b"SECRET-PAYLOAD\xff")

    entry = load_document(tmp_path, "doc.md", 1024)

    assert entry.error_type == "document_decode"
    assert "SECRET-PAYLOAD" not in entry.message


def test_unsupported_extension_is_a_caller_error(tmp_path):
    write(tmp_path, "doc.pdf", "content")

    with pytest.raises(ValueError):
        load_document(tmp_path, "doc.pdf", 1024)
