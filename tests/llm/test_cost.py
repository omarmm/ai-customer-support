from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.llm.contracts import LLMCost, LLMUsage
from app.llm.cost import (
    COMPLETE,
    PARTIAL,
    PRICING_MISSING,
    USAGE_UNAVAILABLE,
    CostCalculator,
    ModelPricing,
    PricingTable,
)


PRICING_JSON = '{"qwen3:8b": {"input_per_1m": 3.0, "output_per_1m": 6.0}}'


def make_calculator(raw: str = PRICING_JSON, currency: str = "USD"):
    return CostCalculator(PricingTable.parse(raw, currency))


def test_empty_pricing_marks_pricing_missing():
    result = CostCalculator().calculate(
        "qwen3:8b", LLMUsage(1000, 500, 1500)
    )

    assert result.cost is None
    assert result.status == PRICING_MISSING


def test_unknown_model_marks_pricing_missing():
    result = make_calculator().calculate(
        "some-other-model", LLMUsage(1000, 500, 1500)
    )

    assert result.cost is None
    assert result.status == PRICING_MISSING


def test_full_usage_produces_complete_cost():
    result = make_calculator().calculate(
        "qwen3:8b", LLMUsage(1000, 500, 1500)
    )

    assert result.status == COMPLETE
    assert result.cost == LLMCost(
        input_cost=Decimal("0.003"),
        output_cost=Decimal("0.003"),
        total_cost=Decimal("0.006"),
        currency="USD",
    )


def test_missing_usage_marks_usage_unavailable():
    result = make_calculator().calculate("qwen3:8b", None)

    assert result.status == USAGE_UNAVAILABLE
    assert result.cost is not None
    assert result.cost.input_cost is None
    assert result.cost.output_cost is None
    assert result.cost.total_cost is None


def test_usage_with_unknown_counts_marks_usage_unavailable():
    result = make_calculator().calculate(
        "qwen3:8b", LLMUsage(None, None, None)
    )

    assert result.status == USAGE_UNAVAILABLE
    assert result.cost.input_cost is None
    assert result.cost.output_cost is None
    assert result.cost.total_cost is None


def test_only_input_tokens_is_partial():
    result = make_calculator().calculate(
        "qwen3:8b", LLMUsage(input_tokens=1000)
    )

    assert result.status == PARTIAL
    assert result.cost.input_cost == Decimal("0.003")
    assert result.cost.output_cost is None
    assert result.cost.total_cost is None


def test_only_output_tokens_is_partial():
    result = make_calculator().calculate(
        "qwen3:8b", LLMUsage(output_tokens=500)
    )

    assert result.status == PARTIAL
    assert result.cost.input_cost is None
    assert result.cost.output_cost == Decimal("0.003")
    assert result.cost.total_cost is None


def test_explicit_zero_price_is_a_known_zero_cost():
    calculator = make_calculator(
        '{"m": {"input_per_1m": 0, "output_per_1m": 0}}'
    )

    result = calculator.calculate("m", LLMUsage(0, 0, 0))

    assert result.status == COMPLETE
    assert result.cost.input_cost == Decimal("0")
    assert result.cost.output_cost == Decimal("0")
    assert result.cost.total_cost == Decimal("0")
    assert result.cost.input_cost is not None


def test_quantization_rounds_half_up():
    calculator = make_calculator(
        '{"m": {"input_per_1m": 0.0000005, "output_per_1m": 0}}'
    )

    result = calculator.calculate("m", LLMUsage(input_tokens=1, output_tokens=0))

    assert result.cost.input_cost == Decimal("0.000000000001")


def test_quantization_rounds_down_below_half():
    calculator = make_calculator(
        '{"m": {"input_per_1m": 0.0000004, "output_per_1m": 0}}'
    )

    result = calculator.calculate("m", LLMUsage(input_tokens=1, output_tokens=0))

    assert result.cost.input_cost == Decimal("0")


def test_currency_propagates_to_cost():
    result = make_calculator(currency="EUR").calculate(
        "qwen3:8b", LLMUsage(1000, 500, 1500)
    )

    assert result.cost.currency == "EUR"


def test_parse_absent_or_empty_is_valid():
    assert PricingTable.parse(None).pricing_for("m") is None
    assert PricingTable.parse("").pricing_for("m") is None
    assert PricingTable.parse("   ").pricing_for("m") is None


def test_parse_rejects_malformed_json():
    with pytest.raises(ValueError):
        PricingTable.parse("{not json")


def test_parse_rejects_non_object_root():
    with pytest.raises(ValueError):
        PricingTable.parse("[1, 2, 3]")


def test_parse_rejects_non_object_entry():
    with pytest.raises(ValueError):
        PricingTable.parse('{"m": 5}')


def test_parse_rejects_missing_key():
    with pytest.raises(ValueError):
        PricingTable.parse('{"m": {"input_per_1m": 1}}')


def test_parse_rejects_negative_price():
    with pytest.raises(ValueError):
        PricingTable.parse(
            '{"m": {"input_per_1m": -1, "output_per_1m": 0}}'
        )


def test_parse_rejects_non_numeric_price():
    with pytest.raises(ValueError):
        PricingTable.parse(
            '{"m": {"input_per_1m": "free", "output_per_1m": 0}}'
        )


def test_parse_rejects_boolean_price():
    with pytest.raises(ValueError):
        PricingTable.parse(
            '{"m": {"input_per_1m": true, "output_per_1m": 0}}'
        )


def test_model_pricing_rejects_negative_price():
    with pytest.raises(ValueError):
        ModelPricing(
            input_per_1m=Decimal("-1"),
            output_per_1m=Decimal("0"),
        )


def test_pricing_table_is_immutable():
    table = PricingTable.parse(PRICING_JSON)

    with pytest.raises(TypeError):
        table._models["other"] = ModelPricing(  # type: ignore[index]
            input_per_1m=Decimal("0"),
            output_per_1m=Decimal("0"),
        )


def test_from_settings_reads_pricing_and_currency():
    settings = SimpleNamespace(
        llm_pricing=PRICING_JSON,
        llm_pricing_currency="EUR",
    )

    table = PricingTable.from_settings(settings)

    assert table.currency == "EUR"
    assert table.pricing_for("qwen3:8b") == ModelPricing(
        input_per_1m=Decimal("3"),
        output_per_1m=Decimal("6"),
    )


def test_from_settings_defaults_currency_when_absent():
    settings = SimpleNamespace(llm_pricing=None)

    table = PricingTable.from_settings(settings)

    assert table.currency == "USD"
    assert table.pricing_for("qwen3:8b") is None
