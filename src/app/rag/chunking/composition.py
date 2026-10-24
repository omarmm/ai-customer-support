"""Production composition root for knowledge document chunking.

This module is the only place where the production chunking path constructs the
approved tokenizer. It loads the pinned local tokenizer asset through
``NomicEmbedTextTokenizer`` and injects the resulting tokenizer into
``ChunkingService`` using the application settings.

The tokenizer identity is pinned in code by the adapter. It is not selected or
overridden by an environment variable, and construction performs no network
I/O or runtime download.

The canonical import root is ``app`` (``PYTHONPATH=/app/src`` in the image), and
the runtime entry point is ``uvicorn app.main:app``.
"""

from __future__ import annotations

from app.core.config import Settings
from app.rag.chunking.service import ChunkingService
from app.rag.chunking.tokenizer_adapter import NomicEmbedTextTokenizer

__all__ = ["build_chunking_service"]


def build_chunking_service(settings: Settings) -> ChunkingService:
    """Build the production chunking service with the approved tokenizer.

    The service is built once per application process. ``from_settings`` copies
    the configured chunk sizes into one effective immutable configuration; the
    adapter supplies the pinned tokenizer identity.
    """
    tokenizer = NomicEmbedTextTokenizer()
    return ChunkingService.from_settings(settings, tokenizer)
