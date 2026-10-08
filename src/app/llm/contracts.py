from dataclasses import dataclass, field
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
class LLMResponse:
    content: str
    model: str
    provider: str
    usage: LLMUsage | None = None
    metadata: dict[str, Any] = field(default_factory=dict)