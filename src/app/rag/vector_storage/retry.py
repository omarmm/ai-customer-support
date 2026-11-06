"""Bounded retry policy for Qdrant storage operations.

The policy is deliberately storage-local. Only normalized application errors
whose ``retryable`` flag is true may be retried, and the approved V1 policy
allows at most three total attempts including the initial attempt. Backoff is
separate from the per-attempt Qdrant client timeout.

The approved delay policy is Full Jitter: the exponential cap is sampled
uniformly from zero up to that cap on every retry.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

MAX_TOTAL_ATTEMPTS = 3


def _require_finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    if not math.isfinite(value):
        raise ValueError(f"{field} must be finite")
    return float(value)


@dataclass(frozen=True)
class QdrantRetryPolicy:
    """Fixed-bound retry policy for transient Qdrant failures.

    ``max_attempts`` counts the initial attempt. The approved V1 ceiling is
    three total attempts, so values above three are rejected rather than
    silently clamped.
    """

    max_attempts: int = MAX_TOTAL_ATTEMPTS
    base_delay: float = 0.5
    max_delay: float = 8.0

    def __post_init__(self) -> None:
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int):
            raise ValueError("max_attempts must be an integer")
        if not 1 <= self.max_attempts <= MAX_TOTAL_ATTEMPTS:
            raise ValueError(
                f"max_attempts must be between 1 and {MAX_TOTAL_ATTEMPTS}"
            )
        _require_finite_number(self.base_delay, "base_delay")
        _require_finite_number(self.max_delay, "max_delay")
        if self.base_delay < 0:
            raise ValueError("base_delay must be >= 0")
        if self.max_delay < 0:
            raise ValueError("max_delay must be >= 0")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")

    def delay_for_attempt(self, attempt: int) -> float:
        """Return the Full Jitter delay before the given zero-based retry.

        ``attempt`` 0 is the wait before the first retry. The exponential cap
        is ``min(base_delay * 2**attempt, max_delay)`` and the delay is sampled
        uniformly from zero up to that cap.
        """

        if attempt < 0:
            raise ValueError("attempt must be >= 0")

        cap = min(self.base_delay * (2**attempt), self.max_delay)
        return random.uniform(0.0, cap)
