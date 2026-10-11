
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr, ValidationError


class SupportCategory(StrEnum):
    REFUND = "refund"
    ORDER_STATUS = "order_status"
    CANCELLATION = "cancellation"
    PAYMENT = "payment"
    DELIVERY = "delivery"
    PRODUCT_ISSUE = "product_issue"
    ACCOUNT = "account"
    COMPLAINT = "complaint"
    GENERAL_INQUIRY = "general_inquiry"


class SupportPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SupportMessageAnalysis(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    category: SupportCategory
    priority: SupportPriority
    requires_human: StrictBool
    summary: StrictStr


class StructuredOutputParseError(Exception):
    """Raised when generated content is not valid JSON."""


class StructuredOutputValidationError(Exception):
    """Raised when parsed JSON violates the output schema."""



def parse_support_message_analysis(
    content: str,
) -> SupportMessageAnalysis:
    try:
        json.loads(content)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as exc:
        raise StructuredOutputParseError(
            "Generated content is not valid JSON."
        ) from exc

    try:
        result = SupportMessageAnalysis.model_validate_json(
            content,
            strict=True,
        )
    except ValidationError as exc:
        raise StructuredOutputValidationError(
            "Generated JSON does not match the support analysis schema."
        ) from exc

    if not result.summary.strip():
        raise StructuredOutputValidationError(
            "Summary must not be empty or whitespace-only."
        )

    return result
