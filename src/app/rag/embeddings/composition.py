"""Production composition root for knowledge document embeddings.

This module is the only place where the production embedding path constructs the
approved Ollama adapter and service. The adapter receives the existing
``settings.ollama_url`` value explicitly (approved D-6); it does not read an
environment variable or introduce a competing setting.

The service is built once per application process and exposed through
``app.state.embedding_service``. Construction performs no network I/O, no
persistence, and no metadata endpoint call.

The canonical import root is ``app`` (``PYTHONPATH=/app/src`` in the image), and
the runtime entry point is ``uvicorn app.main:app``.
"""

from __future__ import annotations

from app.core.config import Settings
from app.rag.embeddings.providers.ollama import OllamaEmbeddingProvider
from app.rag.embeddings.service import EmbeddingService

__all__ = ["build_embedding_service"]


def build_embedding_service(settings: Settings) -> EmbeddingService:
    """Build the production embedding service with the approved Ollama adapter.

    ``EmbeddingService.from_settings`` copies the operational settings into the
    service without calling ``get_settings()``. The provider supplies the pinned
    ``ollama:nomic-embed-text:v1.5`` identity, and the base URL comes explicitly
    from ``settings.ollama_url``.
    """
    provider = OllamaEmbeddingProvider(base_url=settings.ollama_url)
    return EmbeddingService.from_settings(settings, provider)
