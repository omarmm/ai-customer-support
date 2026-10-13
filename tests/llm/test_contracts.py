from decimal import Decimal

from app.llm.contracts import LLMCost, LLMRequest, LLMResponse, LLMUsage


def test_llm_request_defaults():
    request = LLMRequest(
        system_prompt="You are a support assistant.",
        user_prompt="I want a refund.",
        model="qwen3:8b",
    )

    assert request.temperature == 0.0
    assert request.timeout == 30.0
    assert request.metadata == {}


def test_llm_usage():
    usage = LLMUsage(
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
    )

    assert usage.input_tokens == 100
    assert usage.output_tokens == 50
    assert usage.total_tokens == 150


def test_llm_response():
    usage = LLMUsage(
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
    )

    response = LLMResponse(
        content="Your refund request has been received.",
        model="qwen3:8b",
        provider="ollama",
        usage=usage,
    )

    assert response.content == "Your refund request has been received."
    assert response.model == "qwen3:8b"
    assert response.provider == "ollama"
    assert response.usage.total_tokens == 150
    assert response.cost is None


def test_llm_cost_unknown_stays_none():
    cost = LLMCost()

    assert cost.input_cost is None
    assert cost.output_cost is None
    assert cost.total_cost is None
    assert cost.currency == "USD"


def test_llm_cost_preserves_components_and_currency():
    cost = LLMCost(
        input_cost=Decimal("0.003"),
        output_cost=Decimal("0.003"),
        total_cost=Decimal("0.006"),
        currency="USD",
    )

    response = LLMResponse(
        content="Done.",
        model="qwen3:8b",
        provider="ollama",
        cost=cost,
    )

    assert response.cost.input_cost == Decimal("0.003")
    assert response.cost.output_cost == Decimal("0.003")
    assert response.cost.total_cost == Decimal("0.006")
    assert response.cost.currency == "USD"