"""Knowledge document ingestion service.

The service composes deterministic discovery and the per-file loading pipeline
into a single side-effect-free run. It never reads settings on its own: the
composition root supplies configuration directly or through ``from_settings``.
"""

from pathlib import Path

from app.rag.ingestion.contracts import FailedEntry, IngestionResult, KnowledgeDocument
from app.rag.ingestion.discovery import discover
from app.rag.ingestion.loader import load_document
from app.rag.ingestion.paths import resolve_source_root

DEFAULT_MAX_DOCUMENT_BYTES = 1_048_576
DEFAULT_MAX_DOCUMENTS_PER_RUN = 1000


class KnowledgeIngestionService:
    """Ingest every supported document beneath a resolved source root."""

    def __init__(
        self,
        source_root: Path,
        max_document_bytes: int = DEFAULT_MAX_DOCUMENT_BYTES,
        max_documents_per_run: int = DEFAULT_MAX_DOCUMENTS_PER_RUN,
    ):
        if max_document_bytes <= 0:
            raise ValueError("max_document_bytes must be positive")
        if max_documents_per_run <= 0:
            raise ValueError("max_documents_per_run must be positive")

        self._source_root = Path(source_root)
        self._max_document_bytes = max_document_bytes
        self._max_documents_per_run = max_documents_per_run

    @classmethod
    def from_settings(
        cls, settings, repo_root: Path | None = None
    ) -> "KnowledgeIngestionService":
        """Build a service from a settings object without reading globals."""
        return cls(
            source_root=resolve_source_root(
                settings.knowledge_dir, repo_root=repo_root
            ),
            max_document_bytes=settings.knowledge_max_document_bytes,
            max_documents_per_run=settings.knowledge_max_documents_per_run,
        )

    def ingest(self) -> IngestionResult:
        """Discover and load all candidates, collecting per-file failures."""
        plan = discover(self._source_root, self._max_documents_per_run)

        documents: list[KnowledgeDocument] = []
        failed: list[FailedEntry] = []

        for relative_path in plan.candidates:
            outcome = load_document(
                self._source_root, relative_path, self._max_document_bytes
            )
            if isinstance(outcome, KnowledgeDocument):
                documents.append(outcome)
            else:
                failed.append(outcome)

        return IngestionResult.build(
            documents=documents,
            skipped=plan.skipped,
            failed=failed,
        )
