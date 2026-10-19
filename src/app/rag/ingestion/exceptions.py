"""Error taxonomy for knowledge document ingestion.

Structural errors abort an ingestion run and are raised. Per-file failures are
constructed as classifications and recorded in ``IngestionResult.failed``
instead of being raised.

Every type carries a stable ``error_type`` identifier and builds its message
from a fixed description plus the offending path, so messages never contain
document content or secrets.
"""


class IngestionError(Exception):
    """Base class for ingestion errors.

    Never raised directly. Structural subclasses are raised and abort the run;
    per-file subclasses are recorded as failure classifications.
    """

    error_type = "ingestion_error"
    description = "ingestion failed"

    def __init__(self, path: str | None = None):
        self.path = path
        message = self.description if path is None else f"{self.description}: {path}"
        super().__init__(message)


class SourceRootError(IngestionError):
    """Raised when the source root is missing, not a directory, or unreadable.

    Also raised for directory traversal failures at any level, carrying the
    offending relative path.
    """

    error_type = "source_root"
    description = "source root unavailable"


class PathContainmentError(IngestionError):
    """Classified when a fully resolved path escapes the resolved source root."""

    error_type = "path_containment"
    description = "path escapes the source root"


class DocumentReadError(IngestionError):
    """Classified when stat or read fails.

    Covers permissions, I/O errors, and broken symlinks.
    """

    error_type = "document_read"
    description = "document could not be read"


class DocumentDecodeError(IngestionError):
    """Classified when document content is not valid UTF-8."""

    error_type = "document_decode"
    description = "document is not valid UTF-8"


class EmptyDocumentError(IngestionError):
    """Classified when content is whitespace-only after normalization."""

    error_type = "empty_document"
    description = "document is empty"


class DocumentTooLargeError(IngestionError):
    """Classified when the original byte count exceeds the configured limit."""

    error_type = "document_too_large"
    description = "document exceeds the size limit"
