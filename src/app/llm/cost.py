from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping

from app.llm.contracts import LLMCost, LLMUsage

if TYPE_CHECKING:
    from app.core.config import Settings


# Deterministic pricing status exposed at ``response.metadata["cost_status"]``.
PRICING_MISSING = "pricing_missing"
USAGE_UNAVAILABLE = "usage_unavailable"
PARTIAL = "partial"
COMPLETE = "complete"

# Costs are quantized to 12 decimal places with ROUND_HALF_UP.
_QUANTUM = Decimal("0.000000000001")

# Prices are expressed per one million tokens.
_TOKENS_PER_PRICE_UNIT = Decimal(1_000_000)


def _to_decimal(value: Any, model: str, field_name: str) -> Decimal:
    """Convert a configured price to Decimal, rejecting invalid values."""

    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(
            f"LLM_PRICING entry for {model!r} has a non-numeric {field_name!r}"
        )

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(
            f"LLM_PRICING entry for {model!r} has an invalid {field_name!r}"
        ) from exc

    if not decimal_value.is_finite():
        raise ValueError(
            f"LLM_PRICING entry for {model!r} has a non-finite {field_name!r}"
        )

    if decimal_value < 0:
        raise ValueError(
            f"LLM_PRICING entry for {model!r} has a negative {field_name!r}"
        )

    return decimal_value


@dataclass(frozen=True)
class ModelPricing:
    """Per-model price, expressed per one million tokens."""

    input_per_1m: Decimal
    output_per_1m: Decimal

    def __post_init__(self) -> None:
        for name in ("input_per_1m", "output_per_1m"):
            value = getattr(self, name)

            if not isinstance(value, Decimal):
                raise ValueError(f"{name} must be a Decimal")

            if not value.is_finite():
                raise ValueError(f"{name} must be finite")

            if value < 0:
                raise ValueError(f"{name} must be >= 0")


@dataclass(frozen=True)
class PricingTable:
    """Immutable, operator-supplied pricing table keyed by model."""

    currency: str = "USD"
    _models: Mapping[str, ModelPricing] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_models", MappingProxyType(dict(self._models)))

        if not self.currency:
            object.__setattr__(self, "currency", "USD")

    @classmethod
    def empty(cls, currency: str = "USD") -> PricingTable:
        return cls(currency=currency)

    @classmethod
    def parse(cls, raw: str | None, currency: str = "USD") -> PricingTable:
        """Parse the ``LLM_PRICING`` JSON configuration.

        An absent or empty value is valid and yields an empty table, meaning
        cost is unavailable for every model. Malformed JSON, missing keys,
        non-numeric values, or negative prices raise ``ValueError``.
        """

        if raw is None or not raw.strip():
            return cls.empty(currency)

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"LLM_PRICING is not valid JSON: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("LLM_PRICING must be a JSON object keyed by model")

        models: dict[str, ModelPricing] = {}

        for model, entry in data.items():
            if not isinstance(entry, dict):
                raise ValueError(
                    f"LLM_PRICING entry for {model!r} must be an object"
                )

            for key in ("input_per_1m", "output_per_1m"):
                if key not in entry:
                    raise ValueError(
                        f"LLM_PRICING entry for {model!r} is missing {key!r}"
                    )

            models[model] = ModelPricing(
                input_per_1m=_to_decimal(
                    entry["input_per_1m"], model, "input_per_1m"
                ),
                output_per_1m=_to_decimal(
                    entry["output_per_1m"], model, "output_per_1m"
                ),
            )

        return cls(currency=currency, _models=models)

    @classmethod
    def from_settings(cls, settings: Settings) -> PricingTable:
        """Build a table from centralized application settings."""

        return cls.parse(
            getattr(settings, "llm_pricing", None),
            getattr(settings, "llm_pricing_currency", "USD"),
        )

    def pricing_for(self, model: str) -> ModelPricing | None:
        return self._models.get(model)


@dataclass(frozen=True)
class CostResult:
    """Result of a cost calculation: derived cost plus pricing status."""

    cost: LLMCost | None
    status: str


class CostCalculator:
    """Pure, injectable cost calculator for the LLM Service boundary.

    Derives cost from a pricing table and provider-sourced usage. Missing
    pricing or usage is represented explicitly as ``None`` and is never
    silently treated as zero.
    """

    def __init__(self, pricing: PricingTable | None = None):
        self.pricing = pricing if pricing is not None else PricingTable.empty()

    def calculate(self, model: str, usage: LLMUsage | None) -> CostResult:
        pricing = self.pricing.pricing_for(model)

        if pricing is None:
            return CostResult(cost=None, status=PRICING_MISSING)

        input_cost: Decimal | None = None
        output_cost: Decimal | None = None

        if usage is not None:
            if usage.input_tokens is not None:
                input_cost = self._component_cost(
                    usage.input_tokens, pricing.input_per_1m
                )

            if usage.output_tokens is not None:
                output_cost = self._component_cost(
                    usage.output_tokens, pricing.output_per_1m
                )

        total_cost: Decimal | None = None

        if input_cost is not None and output_cost is not None:
            with localcontext():
                total_cost = (input_cost + output_cost).quantize(
                    _QUANTUM, rounding=ROUND_HALF_UP
                )

        cost = LLMCost(
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            currency=self.pricing.currency,
        )

        if total_cost is not None:
            status = COMPLETE
        elif input_cost is not None or output_cost is not None:
            status = PARTIAL
        else:
            status = USAGE_UNAVAILABLE

        return CostResult(cost=cost, status=status)

    @staticmethod
    def _component_cost(tokens: int, price_per_1m: Decimal) -> Decimal:
        with localcontext():
            cost = Decimal(tokens) * price_per_1m / _TOKENS_PER_PRICE_UNIT
            return cost.quantize(_QUANTUM, rounding=ROUND_HALF_UP)
