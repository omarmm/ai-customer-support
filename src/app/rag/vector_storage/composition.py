"""Production composition root for knowledge vector storage.

The factory is the only production location that combines application settings
with the approved Qdrant adapter. Client construction disables the SDK's
compatibility request, so building the service performs no network I/O.
"""

from __future__ import annotations

from app.core.config import Settings
from app.rag.vector_storage.qdrant_adapter import (
    QdrantClientAdapter,
    QdrantClientConfig,
)

__all__ = ["build_vector_store"]


def build_vector_store(settings: Settings) -> QdrantClientAdapter:
    """Build the application-owned vector store from explicit settings.

    QdrantClientAdapter.from_config delegates to the adapter's client factory,
    which sets check_compatibility=False. The service is therefore ready to
    perform storage operations without probing Qdrant during application
    startup.
    """
    config = QdrantClientConfig(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
    )
    return QdrantClientAdapter.from_config(config)
