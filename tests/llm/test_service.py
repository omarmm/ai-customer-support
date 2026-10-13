import pytest

from decimal import Decimal

from app.llm.contracts import LLMRequest, LLMResponse, LLMUsage
from app.llm.cost import CostCalculator, PricingTable
from app.llm.providers.base import LLMProvider
from app.llm.services.llm_service import LLMService


class FakeLLMProvider(LLMProvider):

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content="Service test response",
            model=request.model,
            provider="fake",
        )


@pytest.mark.asyncio
async def test_llm_service_delegates_to_provider():
    provider = FakeLLMProvider()
    service = LLMService(provider)

    request = LLMRequest(
        system_prompt="You are a support assistant.",
        user_prompt="I need help.",
        model="test-model",
    )

    response = await service.generate(request)

    assert response.content == "Service test response"
    assert response.provider == "fake"
    assert response.model == "test-model"


class UsageReturningProvider(LLMProvider):

    def __init__(self, usage: LLMUsage | None):
        self._usage = usage

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content="usage response",
            model=request.model,
            provider="fake",
            usage=self._usage,
        )


def make_priced_calculator() -> CostCalculator:
    return CostCalculator(
        PricingTable.parse(
            '{"test-model": {"input_per_1m": 2.0, "output_per_1m": 4.0}}'
        )
    )


def make_service_request() -> LLMRequest:
    return LLMRequest(
        system_prompt="You are a support assistant.",
        user_prompt="I need help.",
        model="test-model",
    )


@pytest.mark.asyncio
async def test_service_reports_pricing_missing_by_default():
    service = LLMService(UsageReturningProvider(LLMUsage(100, 50, 150)))

    response = await service.generate(make_service_request())

    assert response.cost is None
    assert response.metadata["cost_status"] == "pricing_missing"


@pytest.mark.asyncio
async def test_service_attaches_complete_cost():
    service = LLMService(
        UsageReturningProvider(LLMUsage(1000, 500, 1500)),
        cost_calculator=make_priced_calculator(),
    )

    response = await service.generate(make_service_request())

    assert response.metadata["cost_status"] == "complete"
    assert response.cost is not None
    assert response.cost.input_cost == Decimal("0.002")
    assert response.cost.output_cost == Decimal("0.002")
    assert response.cost.total_cost == Decimal("0.004")
    assert response.cost.currency == "USD"


@pytest.mark.asyncio
async def test_service_reports_partial_and_usage_unavailable():
    partial = LLMService(
        UsageReturningProvider(LLMUsage(input_tokens=1000)),
        cost_calculator=make_priced_calculator(),
    )
    partial_response = await partial.generate(make_service_request())

    assert partial_response.metadata["cost_status"] == "partial"
    assert partial_response.cost.input_cost == Decimal("0.002")
    assert partial_response.cost.total_cost is None

    missing = LLMService(
        UsageReturningProvider(None),
        cost_calculator=make_priced_calculator(),
    )
    missing_response = await missing.generate(make_service_request())

    assert missing_response.metadata["cost_status"] == "usage_unavailable"
    assert missing_response.cost.input_cost is None
    assert missing_response.cost.total_cost is None


@pytest.mark.asyncio
async def test_service_does_not_eagerly_read_settings(monkeypatch):
    import app.llm.services.llm_service as service_module

    def fail_settings():
        raise AssertionError("get_settings must not be called")

    monkeypatch.setattr(
        service_module, "get_settings", fail_settings, raising=False
    )
    provider = UsageReturningProvider(LLMUsage(100, 50, 150))

    service = LLMService(provider)
    response = await service.generate(make_service_request())

    assert response.metadata["cost_status"] == "pricing_missing"