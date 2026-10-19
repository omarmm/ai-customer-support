"""Contract types for knowledge document ingestion.

These types are data holders only. ``IngestionResult`` derives its counts from
the stored collections and normalizes ordering on every construction path, so
the ordering and count invariants of the specification cannot be bypassed by
direct construction.
"""

from dataclasses import dataclass, field

from app.rag.ingestion.exceptions import IngestionError

FORMAT_MARKDOWN = "markdown"
FORMAT_TEXT = "text"

SKIPPED_UNSUPPORTED_FORMAT = "unsupported_format"
SKIPPED_DOCUMENT_LIMIT_EXCEEDED = "document_limit_exceeded"


@dataclass(frozen=True)
class KnowledgeDocument:
    """A normalized knowledge document produced by the ingestion pipeline."""

    document_id: str
    source_path: str
    title: str
    format: str
    content: str
    size_bytes: int


@dataclass(frozen=True)
class SkippedEntry:
    """A discovered file that was not ingested, with its skip reason."""

    path: str
    reason: str


@dataclass(frozen=True)
class FailedEntry:
    """A per-file failure, reported without exposing document content."""

    path: str
    error_type: str
    message: str

    @classmethod
    def from_error(cls, path: str, error: IngestionError) -> "FailedEntry":
        """Classify a per-file failure using the error's stable identifier."""
        return cls(path=path, error_type=error.error_type, message=str(error))


def _ordered(entries, key) -> tuple:
    return tuple(sorted(entries, key=key))


@dataclass(frozen=True)
class IngestionResult:
    """The outcome of an ingestion run.

    Collections are immutable tuples ordered ascending by relative POSIX path.
    Counts are derived read-only properties, so no construction path can
    produce counts that contradict the stored collections.
    """

    documents: tuple[KnowledgeDocument, ...] = field(default_factory=tuple)
    skipped: tuple[SkippedEntry, ...] = field(default_factory=tuple)
    failed: tuple[FailedEntry, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "documents", _ordered(self.documents, lambda entry: entry.source_path)
        )
        object.__setattr__(self, "skipped", _ordered(self.skipped, lambda entry: entry.path))
        object.__setattr__(self, "failed", _ordered(self.failed, lambda entry: entry.path))

    @classmethod
    def build(cls, documents=(), skipped=(), failed=()) -> "IngestionResult":
        """Canonical construction path used by the ingestion service."""
        return cls(
            documents=tuple(documents),
            skipped=tuple(skipped),
            failed=tuple(failed),
        )

    @property
    def succeeded_count(self) -> int:
        return len(self.documents)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    @property
    def failed_count(self) -> int:
        return len(self.failed)

    @property
    def candidate_count(self) -> int:
        limit_excluded = sum(
            1
            for entry in self.skipped
            if entry.reason == SKIPPED_DOCUMENT_LIMIT_EXCEEDED
        )
        return self.succeeded_count + self.failed_count + limit_excluded

    @property
    def discovered_count(self) -> int:
        return self.succeeded_count + self.failed_count + self.skipped_count

    @property
    def has_failures(self) -> bool:
        return self.failed_count > 0
