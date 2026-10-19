from dataclasses import FrozenInstanceError

import pytest

from app.rag.ingestion.contracts import (
    FORMAT_MARKDOWN,
    SKIPPED_DOCUMENT_LIMIT_EXCEEDED,
    SKIPPED_UNSUPPORTED_FORMAT,
    FailedEntry,
    IngestionResult,
    KnowledgeDocument,
    SkippedEntry,
)
from app.rag.ingestion.exceptions import (
    DocumentDecodeError,
    DocumentReadError,
    DocumentTooLargeError,
    EmptyDocumentError,
    IngestionError,
    PathContainmentError,
    SourceRootError,
)

PER_FILE_ERRORS = (
    PathContainmentError,
    DocumentReadError,
    DocumentDecodeError,
    EmptyDocumentError,
    DocumentTooLargeError,
)


def document(source_path: str) -> KnowledgeDocument:
    return KnowledgeDocument(
        document_id="a" * 64,
        source_path=source_path,
        title="Title",
        format=FORMAT_MARKDOWN,
        content="# Title\n",
        size_bytes=8,
    )


def skipped(path: str, reason: str = SKIPPED_UNSUPPORTED_FORMAT) -> SkippedEntry:
    return SkippedEntry(path=path, reason=reason)


def failure(path: str) -> FailedEntry:
    return FailedEntry(path=path, error_type="document_read", message="message")


def test_knowledge_document_fields():
    doc = document("policies/refunds.md")

    assert doc.document_id == "a" * 64
    assert doc.source_path == "policies/refunds.md"
    assert doc.title == "Title"
    assert doc.format == FORMAT_MARKDOWN
    assert doc.content == "# Title\n"
    assert doc.size_bytes == 8


def test_skipped_entry_fields():
    entry = skipped("notes.pdf")

    assert entry.path == "notes.pdf"
    assert entry.reason == "unsupported_format"


def test_failed_entry_from_error_uses_stable_error_type():
    entry = FailedEntry.from_error("bad.md", DocumentDecodeError("bad.md"))

    assert entry.path == "bad.md"
    assert entry.error_type == "document_decode"
    assert entry.message == "document is not valid UTF-8: bad.md"


def test_failed_entry_message_never_contains_document_content():
    content = "SECRET customer payload"

    entry = FailedEntry.from_error("leak.md", DocumentReadError("leak.md"))

    assert content not in entry.message


def test_build_sorts_all_collections_by_path():
    result = IngestionResult.build(
        documents=[document("b.md"), document("a.md")],
        skipped=[skipped("z.bin"), skipped("c.bin")],
        failed=[failure("y.md"), failure("d.md")],
    )

    assert [doc.source_path for doc in result.documents] == ["a.md", "b.md"]
    assert [entry.path for entry in result.skipped] == ["c.bin", "z.bin"]
    assert [entry.path for entry in result.failed] == ["d.md", "y.md"]


def test_direct_construction_cannot_bypass_ordering():
    result = IngestionResult(
        documents=[document("zz.md"), document("aa.md")],
        skipped=[skipped("zz.bin"), skipped("aa.bin")],
        failed=[failure("zz.md"), failure("aa.md")],
    )

    assert [doc.source_path for doc in result.documents] == ["aa.md", "zz.md"]
    assert [entry.path for entry in result.skipped] == ["aa.bin", "zz.bin"]
    assert [entry.path for entry in result.failed] == ["aa.md", "zz.md"]


def test_collections_are_immutable_tuples_on_every_construction_path():
    built = IngestionResult.build(documents=[document("a.md")])
    direct = IngestionResult(documents=[document("a.md")])

    assert isinstance(built.documents, tuple)
    assert isinstance(direct.documents, tuple)
    assert isinstance(built.skipped, tuple)
    assert isinstance(built.failed, tuple)


def test_ordering_is_codepoint_ascending_and_case_sensitive():
    result = IngestionResult.build(
        documents=[document("a.md"), document("B.md"), document("A.md")]
    )

    assert [doc.source_path for doc in result.documents] == ["A.md", "B.md", "a.md"]


def test_result_is_frozen():
    result = IngestionResult.build()

    with pytest.raises(FrozenInstanceError):
        result.documents = ()  # type: ignore[misc]


def test_counts_are_derived_from_collections():
    result = IngestionResult.build(
        documents=[document("a.md"), document("b.md")],
        skipped=[skipped("c.bin")],
        failed=[failure("d.md")],
    )

    assert result.succeeded_count == 2
    assert result.skipped_count == 1
    assert result.failed_count == 1
    assert result.has_failures is True
    assert result.candidate_count == 3
    assert result.discovered_count == 4


def test_candidate_count_includes_limit_excluded_skips():
    result = IngestionResult.build(
        documents=[document("a.md")],
        skipped=[
            skipped("b.bin"),
            skipped("c.md", SKIPPED_DOCUMENT_LIMIT_EXCEEDED),
            skipped("d.md", SKIPPED_DOCUMENT_LIMIT_EXCEEDED),
        ],
    )

    assert result.skipped_count == 3
    assert result.candidate_count == 3
    assert result.discovered_count == 4


def test_empty_result_has_zero_counts():
    result = IngestionResult.build()

    assert result.documents == ()
    assert result.skipped == ()
    assert result.failed == ()
    assert result.succeeded_count == 0
    assert result.skipped_count == 0
    assert result.failed_count == 0
    assert result.candidate_count == 0
    assert result.discovered_count == 0
    assert result.has_failures is False


def test_failed_count_cannot_drift_from_failed_collection():
    result = IngestionResult.build(failed=[failure("x.md")])

    assert result.failed_count == len(result.failed) == 1
    assert result.has_failures is True


def test_error_taxonomy_derives_from_ingestion_error():
    for error_cls in PER_FILE_ERRORS:
        assert issubclass(error_cls, IngestionError)

    assert issubclass(SourceRootError, IngestionError)


def test_every_error_type_is_stable_and_distinct():
    hierarchy = [IngestionError, SourceRootError, *PER_FILE_ERRORS]

    assert [cls.error_type for cls in hierarchy] == [
        "ingestion_error",
        "source_root",
        "path_containment",
        "document_read",
        "document_decode",
        "empty_document",
        "document_too_large",
    ]
    assert len({cls.error_type for cls in hierarchy}) == len(hierarchy)


def test_per_file_messages_carry_the_path_and_stay_content_free():
    for error_cls in PER_FILE_ERRORS:
        error = error_cls("docs/example.md")

        assert error.path == "docs/example.md"
        assert "docs/example.md" in str(error)


def test_structural_error_carries_offending_directory():
    error = SourceRootError("private")

    assert error.path == "private"
    assert str(error) == "source root unavailable: private"


def test_structural_error_may_omit_the_path():
    error = SourceRootError()

    assert error.path is None
    assert str(error) == "source root unavailable"
