import json
import pytest

from app.llm.structured_output import (
    StructuredOutputParseError,
    StructuredOutputValidationError,
    SupportCategory,
    SupportMessageAnalysis,
    SupportPriority,
    parse_support_message_analysis,
)


def valid_payload() -> dict:
    return {
        "category": "refund",
        "priority": "high",
        "requires_human": False,
        "summary": "Customer requests a refund.",
    }


def test_valid_json_returns_typed_object():
    result = parse_support_message_analysis(
        '{"category":"refund","priority":"high",'
        '"requires_human":false,"summary":"Refund requested."}'
    )

    assert isinstance(result, SupportMessageAnalysis)
    assert result.category == SupportCategory.REFUND
    assert result.priority == SupportPriority.HIGH
    assert result.requires_human is False
    assert result.summary == "Refund requested."


@pytest.mark.parametrize(
    "category",
    [
        "refund",
        "order_status",
        "cancellation",
        "payment",
        "delivery",
        "product_issue",
        "account",
        "complaint",
        "general_inquiry",
    ],
)
def test_all_approved_categories_are_accepted(category: str):
    payload = valid_payload()
    payload["category"] = category

    result = parse_support_message_analysis(json.dumps(payload))

    assert result.category == category


@pytest.mark.parametrize(
    "priority",
    ["low", "medium", "high"],
)
def test_all_approved_priorities_are_accepted(priority: str):
    payload = valid_payload()
    payload["priority"] = priority

    result = parse_support_message_analysis(json.dumps(payload))

    assert result.priority == priority


@pytest.mark.parametrize(
    "field",
    ["category", "priority", "requires_human", "summary"],
)
def test_missing_required_field_is_rejected(field: str):
    payload = valid_payload()
    del payload[field]

    with pytest.raises(StructuredOutputValidationError):
        parse_support_message_analysis(__import__("json").dumps(payload))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("category", "unknown"),
        ("priority", "urgent"),
        ("requires_human", "false"),
        ("requires_human", 0),
        ("summary", 123),
    ],
)
def test_invalid_field_values_are_rejected(field: str, value):
    import json

    payload = valid_payload()
    payload[field] = value

    with pytest.raises(StructuredOutputValidationError):
        parse_support_message_analysis(json.dumps(payload))


@pytest.mark.parametrize("summary", ["", " ", "\t\n"])
def test_empty_summary_is_rejected(summary: str):
    import json

    payload = valid_payload()
    payload["summary"] = summary

    with pytest.raises(StructuredOutputValidationError):
        parse_support_message_analysis(json.dumps(payload))


def test_malformed_json_raises_parse_error():
    with pytest.raises(StructuredOutputParseError):
        parse_support_message_analysis('{"category":')


def test_extra_fields_are_rejected():
    import json

    payload = valid_payload()
    payload["unexpected"] = "value"

    with pytest.raises(StructuredOutputValidationError):
        parse_support_message_analysis(json.dumps(payload))


def test_json_array_is_rejected_by_schema():
    with pytest.raises(StructuredOutputValidationError):
        parse_support_message_analysis("[]")


def test_json_null_is_rejected_by_schema():
    with pytest.raises(StructuredOutputValidationError):
        parse_support_message_analysis("null")
