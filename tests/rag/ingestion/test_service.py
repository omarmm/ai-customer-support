import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.rag.ingestion.contracts import (
    FORMAT_MARKDOWN,
    FORMAT_TEXT,
    SKIPPED_DOCUMENT_LIMIT_EXCEEDED,
    SKIPPED_UNSUPPORTED_FORMAT,
)
from app.rag.ingestion.exceptions import SourceRootError
from app.rag.ingestion.service import KnowledgeIngestionService

RUNNING_AS_ROOT = getattr(os, "geteuid", lambda: -1)() == 0
SYMLINKS_SUPPORTED = hasattr(os, "symlink")


def write(root: Path, relative: str, content: bytes | str = "content") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def settings_for(root: Path, **overrides) -> SimpleNamespace:
    values = {
        "knowledge_dir": str(root),
        "knowledge_max_document_bytes": 1_048_576,
        "knowledge_max_documents_per_run": 1000,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


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


def test_ingests_supported_documents_with_complete_metadata(tmp_path):
    content = "# Refunds\nPolicy body\n"
    write(tmp_path, "a.md", content)
    write(tmp_path, "nested/b.txt", "plain text")

    result = KnowledgeIngestionService(tmp_path).ingest()

    assert [doc.source_path for doc in result.documents] == ["a.md", "nested/b.txt"]
    first = result.documents[0]
    assert first.title == "Refunds"
    assert first.format == FORMAT_MARKDOWN
    assert first.content == content
    assert first.size_bytes == len(content.encode("utf-8"))
    assert result.documents[1].format == FORMAT_TEXT
    assert result.succeeded_count == 2
    assert result.failed_count == 0
    assert result.skipped_count == 0
    assert result.has_failures is False


def test_unsupported_files_are_reported_and_never_read(tmp_path, monkeypatch):
    write(tmp_path, "a.md")
    write(tmp_path, "notes.pdf", b"not a document")
    original_open = Path.open

    def guarded(self, *args, **kwargs):
        if self.name == "notes.pdf":
            raise AssertionError("unsupported files must not be read")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)

    result = KnowledgeIngestionService(tmp_path).ingest()

    assert result.succeeded_count == 1
    assert [(entry.path, entry.reason) for entry in result.skipped] == [
        ("notes.pdf", SKIPPED_UNSUPPORTED_FORMAT)
    ]


def test_end_to_end_counts_match_the_specification_invariants(tmp_path):
    write(tmp_path, "a.md")
    write(tmp_path, "b.txt")
    write(tmp_path, "c.pdf")
    write(tmp_path, "bad.md", b"\xff\xfe")
    write(tmp_path, "d.md")
    write(tmp_path, "e.md")

    result = KnowledgeIngestionService(
        tmp_path, max_documents_per_run=3
    ).ingest()

    assert [doc.source_path for doc in result.documents] == ["a.md", "b.txt"]
    assert [entry.path for entry in result.failed] == ["bad.md"]
    assert [(entry.path, entry.reason) for entry in result.skipped] == [
        ("c.pdf", SKIPPED_UNSUPPORTED_FORMAT),
        ("d.md", SKIPPED_DOCUMENT_LIMIT_EXCEEDED),
        ("e.md", SKIPPED_DOCUMENT_LIMIT_EXCEEDED),
    ]
    assert result.succeeded_count == 2
    assert result.failed_count == 1
    assert result.skipped_count == 3
    assert result.candidate_count == 5
    assert result.discovered_count == 6
    assert result.has_failures is True


def test_limit_excluded_candidates_are_never_read(tmp_path, monkeypatch):
    write(tmp_path, "a.md")
    write(tmp_path, "b.md", b"\xff\xfe")
    original_open = Path.open

    def guarded(self, *args, **kwargs):
        if self.name == "b.md":
            raise AssertionError("limit-excluded candidates must not be read")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)

    result = KnowledgeIngestionService(tmp_path, max_documents_per_run=1).ingest()

    assert result.succeeded_count == 1
    assert [(entry.path, entry.reason) for entry in result.skipped] == [
        ("b.md", SKIPPED_DOCUMENT_LIMIT_EXCEEDED)
    ]


def test_per_file_failures_are_collected_and_processing_continues(tmp_path):
    write(tmp_path, "a.md", "# Keep\n")
    write(tmp_path, "bad.md", b"\xff")
    write(tmp_path, "c.md", "# Also keep\n")

    result = KnowledgeIngestionService(tmp_path).ingest()

    assert [doc.source_path for doc in result.documents] == ["a.md", "c.md"]
    assert [(entry.path, entry.error_type) for entry in result.failed] == [
        ("bad.md", "document_decode")
    ]


def test_failures_never_contain_document_content(tmp_path):
    write(tmp_path, "leak.md", b"SECRET-PAYLOAD\xff")

    result = KnowledgeIngestionService(tmp_path).ingest()

    failure = result.failed[0]
    assert failure.error_type == "document_decode"
    assert "SECRET-PAYLOAD" not in failure.message


def test_oversized_documents_fail_without_reading_content(tmp_path, monkeypatch):
    write(tmp_path, "big.md", b"x" * 11)

    def fail(*args, **kwargs):
        raise AssertionError("oversized documents must not be read")

    monkeypatch.setattr(Path, "open", fail)

    result = KnowledgeIngestionService(tmp_path, max_document_bytes=10).ingest()

    assert [(entry.path, entry.error_type) for entry in result.failed] == [
        ("big.md", "document_too_large")
    ]


@pytest.mark.skipif(not SYMLINKS_SUPPORTED, reason="symlinks unavailable")
def test_absolute_root_enforces_containment_for_symlink_escapes(tmp_path, monkeypatch):
    root = tmp_path / "knowledge"
    root.mkdir()
    write(tmp_path, "secret.md", "SECRET-PAYLOAD")
    os.symlink(tmp_path / "secret.md", root / "escape.md")

    def fail(*args, **kwargs):
        raise AssertionError("content outside the root must not be read")

    monkeypatch.setattr(Path, "open", fail)

    result = KnowledgeIngestionService(root).ingest()

    assert [(entry.path, entry.error_type) for entry in result.failed] == [
        ("escape.md", "path_containment")
    ]
    assert "SECRET-PAYLOAD" not in result.failed[0].message


def test_absolute_source_root_is_used_directly(tmp_path):
    root = tmp_path / "absolute-root"
    write(root, "policy.md", "# Policy\n")

    result = KnowledgeIngestionService(root).ingest()

    assert [doc.source_path for doc in result.documents] == ["policy.md"]


def test_missing_source_root_raises_source_root_error(tmp_path):
    with pytest.raises(SourceRootError):
        KnowledgeIngestionService(tmp_path / "missing").ingest()


def test_source_root_that_is_not_a_directory_raises_source_root_error(tmp_path):
    root = write(tmp_path, "not-a-directory")

    with pytest.raises(SourceRootError):
        KnowledgeIngestionService(root).ingest()


@pytest.mark.skipif(RUNNING_AS_ROOT, reason="root bypasses permission checks")
def test_unreadable_source_root_raises_source_root_error(tmp_path):
    root = tmp_path / "knowledge"
    root.mkdir()
    root.chmod(0)
    try:
        with pytest.raises(SourceRootError):
            KnowledgeIngestionService(root).ingest()
    finally:
        root.chmod(0o700)


@pytest.mark.skipif(RUNNING_AS_ROOT, reason="root bypasses permission checks")
def test_unreadable_subdirectory_is_structural(tmp_path):
    root = tmp_path / "knowledge"
    private = root / "private"
    private.mkdir(parents=True)
    (private / "inside.md").write_text("content", encoding="utf-8")
    private.chmod(0)
    try:
        with pytest.raises(SourceRootError) as excinfo:
            KnowledgeIngestionService(root).ingest()
    finally:
        private.chmod(0o700)

    assert excinfo.value.path == "private"


def test_repeated_runs_are_idempotent(tmp_path):
    write(tmp_path, "b.md", "# B\n")
    write(tmp_path, "a.txt", "A")
    write(tmp_path, "skip.pdf")

    service = KnowledgeIngestionService(tmp_path)
    first = service.ingest()
    second = service.ingest()

    assert first == second
    assert [doc.document_id for doc in first.documents] == [
        doc.document_id for doc in second.documents
    ]
    assert first.discovered_count == second.discovered_count


def test_from_settings_resolves_relative_paths_against_the_repo_root(tmp_path):
    write(tmp_path, "knowledge/policy.md", "# Policy\n")
    settings = settings_for(Path("knowledge"))

    service = KnowledgeIngestionService.from_settings(settings, repo_root=tmp_path)
    result = service.ingest()

    assert [doc.source_path for doc in result.documents] == ["policy.md"]


def test_from_settings_does_not_eagerly_read_global_settings(tmp_path, monkeypatch):
    import app.rag.ingestion.service as service_module

    write(tmp_path, "knowledge/policy.md", "# Policy\n")

    def fail_settings():
        raise AssertionError("get_settings must not be called")

    monkeypatch.setattr(
        service_module, "get_settings", fail_settings, raising=False
    )

    service = KnowledgeIngestionService.from_settings(
        settings_for(Path("knowledge")), repo_root=tmp_path
    )
    result = service.ingest()

    assert result.succeeded_count == 1


def test_from_settings_uses_configured_limits(tmp_path):
    write(tmp_path, "knowledge/a.md")
    write(tmp_path, "knowledge/b.md")
    settings = settings_for(
        Path("knowledge"), knowledge_max_documents_per_run=1
    )

    result = KnowledgeIngestionService.from_settings(
        settings, repo_root=tmp_path
    ).ingest()

    assert result.succeeded_count == 1
    assert [(entry.path, entry.reason) for entry in result.skipped] == [
        ("b.md", SKIPPED_DOCUMENT_LIMIT_EXCEEDED)
    ]


@pytest.mark.parametrize("value", [0, -1])
def test_constructor_rejects_non_positive_document_byte_limit(tmp_path, value):
    with pytest.raises(ValueError):
        KnowledgeIngestionService(tmp_path, max_document_bytes=value)


@pytest.mark.parametrize("value", [0, -1])
def test_constructor_rejects_non_positive_document_count_limit(tmp_path, value):
    with pytest.raises(ValueError):
        KnowledgeIngestionService(tmp_path, max_documents_per_run=value)


def test_settings_defaults_match_the_specification():
    settings = make_settings()

    assert settings.knowledge_dir == "knowledge"
    assert settings.knowledge_max_document_bytes == 1_048_576
    assert settings.knowledge_max_documents_per_run == 1000


@pytest.mark.parametrize(
    "field",
    ["knowledge_max_document_bytes", "knowledge_max_documents_per_run"],
)
@pytest.mark.parametrize("value", [0, -1])
def test_settings_reject_non_positive_limits(field, value):
    with pytest.raises(ValidationError):
        make_settings(**{field: value})
