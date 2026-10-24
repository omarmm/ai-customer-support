"""Provider contract for knowledge document embeddings."""

from __future__ import annotations

from typing import Protocol, Sequence


class EmbeddingProvider(Protocol):
    """Structural contract implemented by embedding providers.

    Providers accept already-prefixed texts in input order, enforce the
    per-attempt timeout, validate the response envelope, and raise only the
    provider-layer exceptions defined in ``providers.exceptions``. They perform
    no persistence, call no metadata endpoint, and return no partial success.
    """

    @property
    def identity(self) -> str:
        """Return the pinned provider/model identity."""

    async def embed(
        self,
        texts: Sequence[str],
        *,
        timeout: float,
    ) -> tuple[tuple[float, ...], ...]:
        """Return one vector per input text, in input order."""
