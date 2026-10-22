"""Error taxonomy for knowledge document chunking.

``ChunkingError`` is the base type and is never raised directly.
``TokenizerContractError`` is structural: it aborts the chunking run because a
tokenizer that violates the span contract cannot produce trustworthy offsets.

Messages carry stable reason identifiers plus positions only. Document content
is never included.
"""

from __future__ import annotations


class ChunkingError(Exception):
    """Base class for chunking errors.

    Never raised directly. Subclasses describe a specific chunking failure.
    """

    error_type = "chunking_error"
    description = "chunking failed"


class TokenizerContractError(ChunkingError):
    """Raised when a tokenizer violates the span contract in §5.

    Covers out-of-bounds, zero-width, out-of-order, or overlapping spans,
    non-whitespace gaps, missing tokens, invalid byte boundaries, and empty
    identities. Structural: aborts the chunking run.
    """

    error_type = "tokenizer_contract"
    description = "tokenizer contract violation"

    def __init__(
        self,
        reason: str,
        *,
        token_index: int | None = None,
        position: int | None = None,
    ):
        self.reason = reason
        self.token_index = token_index
        self.position = position

        message = f"{self.description}: {reason}"
        if token_index is not None:
            message += f" (token_index={token_index})"
        if position is not None:
            message += f" (position={position})"
        super().__init__(message)
