"""Embeddings-local bounded retry policy (approved D-3).

This module deliberately mirrors ``app.llm.retry.RetryPolicy`` without importing
it. Importing the LLM implementation from the RAG subsystem would introduce the
first production dependency from RAG to LLM and its settings adapter reads
``llm_*`` settings, which cannot describe embedding settings. The semantics and
defaults are fixed by the embeddings specification §8.6.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.config import Settings


@dataclass(frozen=True)
class EmbeddingRetryPolicy:
    """Bounded, configurable retry policy for the embedding service.

    Only normalized application errors with ``retryable=True`` are retried.
    Total provider attempts per batch are limited to ``1 + max_retries``. The
    backoff delay is separate from the per-attempt timeout and never consumes
    it.
    """

    max_retries: int = 2
    base_delay: float = 0.5
    max_delay: float = 8.0
    jitter: float = 0.0

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")

        if self.base_delay < 0:
            raise ValueError("base_delay must be >= 0")

        if self.max_delay < 0:
            raise ValueError("max_delay must be >= 0")

        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")

        if self.jitter < 0:
            raise ValueError("jitter must be >= 0")

    def delay_for_attempt(self, attempt: int) -> float:
        """Return the bounded backoff delay before the given retry attempt.

        ``attempt`` is zero-based: 0 is the delay before the first retry. The
        base delay grows exponentially and is capped at ``max_delay``. Optional
        jitter is a non-negative ratio applied on top of the capped delay, so the
        delay always remains finite and bounded.
        """

        if attempt < 0:
            raise ValueError("attempt must be >= 0")

        delay = min(self.base_delay * (2**attempt), self.max_delay)

        if self.jitter:
            delay += random.uniform(0.0, self.jitter * delay)

        return delay

    @classmethod
    def from_settings(cls, settings: Settings) -> "EmbeddingRetryPolicy":
        """Build a policy from centralized application settings."""

        return cls(
            max_retries=settings.embedding_max_retries,
            base_delay=settings.embedding_retry_base_delay,
            max_delay=settings.embedding_retry_max_delay,
            jitter=settings.embedding_retry_jitter,
        )
