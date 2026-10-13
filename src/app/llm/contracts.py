from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class LLMRequest:
    system_prompt: str
    user_prompt: str
    model: str
    temperature: float = 0.0
    timeout: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class LLMCost:
    """Derived cost for a single LLM response.

    Any component that cannot be established is ``None``; ``None`` is never
    used as a substitute for a zero cost. An explicitly configured zero price
    produces ``Decimal("0")``.
    """

    input_cost: Decimal | None = None
    output_cost: Decimal | None = None
    total_cost: Decimal | None = None
    currency: str = "USD"


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    usage: LLMUsage | None = None
    cost: LLMCost | None = None
    metadata: dict[str, Any] = field(default_factory=dict)