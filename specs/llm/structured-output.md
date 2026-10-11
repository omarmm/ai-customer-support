# Structured Output Specification

## 1. Purpose

Define a reliable contract for converting LLM responses into validated, typed Python objects that can be safely consumed by the application.

The Structured Output subsystem must ensure that model responses conform to an explicitly defined schema before downstream application components consume them.

Schema validation does not guarantee that the model's interpretation is factually correct or that a requested business action is authorized.

## 2. Scope

This subsystem is responsible for:

- Defining output schemas using Pydantic.
- Validating field types, required fields, and allowed values.
- Parsing model responses into typed Python objects.
- Rejecting malformed JSON and schema-invalid responses.
- Providing predictable parsing and validation errors.
- Supporting unit testing independently of the LLM provider.

Out of scope:

- LLM provider communication and request execution.
- Domain business rules and refund eligibility decisions.
- Database persistence.
- RAG and agent workflows.
- Provider retries and fallback strategies.
- Determining the factual correctness of an LLM-generated analysis.

## 3. Output Contract

The initial output model represents a customer support message analysis.

### 3.1 Fields

| Field | Type | Constraints |
|---|---|---|
| `category` | Enum | Must match one of the nine approved category values |
| `priority` | Enum | Must be `low`, `medium`, or `high` |
| `requires_human` | Boolean | Must be a valid boolean |
| `summary` | String | Must contain at least one non-whitespace character |

All four fields are required.

### 3.2 Approved Category Vocabulary — v1

The `category` field must accept exactly one of the following values:

| Category | Meaning |
|---|---|
| `refund` | The customer requests a refund or discusses a refund-related matter. |
| `order_status` | The customer asks about the current status or progress of an order. |
| `cancellation` | The customer requests or discusses order cancellation. |
| `payment` | The customer reports or asks about a payment-related matter. |
| `delivery` | The customer reports or asks about delivery, shipping, or shipment progress. |
| `product_issue` | The customer reports a product problem, such as damage or a defect. |
| `account` | The customer reports or asks about an account-related matter. |
| `complaint` | The customer expresses dissatisfaction or raises a complaint that does not fit a more specific category. |
| `general_inquiry` | The customer asks a general question that does not fit any of the other categories. |

Category values are case-sensitive and must match the approved values exactly.

The model must not introduce new category values dynamically.

The approved vocabulary is the initial v1 contract. Any future addition, removal, or renaming of categories must be explicitly reviewed and documented before implementation.

### 3.3 Category Selection Rules

- Select the category that best represents the customer's primary intent.
- Prefer a specific category over `complaint` or `general_inquiry` when the message clearly matches a specific category.
- Use `complaint` for dissatisfaction that cannot be classified more specifically.
- Use `general_inquiry` for general questions that do not fit another category.
- The selected category represents message classification only; it does not authorize a business action.

If a message contains multiple intents, the model must select one primary category according to the instructions supplied to the LLM. The initial schema does not support multiple categories.

### 3.4 Priority Values

The `priority` field must accept exactly:

- `low`
- `medium`
- `high`

The value represents the assessed support priority of the message. It must not be interpreted as a business authorization or as proof that an action is required.

### 3.5 Human Escalation

The `requires_human` field indicates whether the analyzed message should be escalated for human review.

It must be a valid boolean value. The initial schema does not support textual substitutes such as `"true"` or `"false"`.

The field does not independently execute an escalation workflow.

### 3.6 Summary

The `summary` field contains a concise summary of the customer's message.

The value must be a string containing at least one non-whitespace character.

The schema validates the presence and basic format of the summary, not its factual accuracy.

### 3.7 Example

```json
{
  "category": "refund",
  "priority": "high",
  "requires_human": false,
  "summary": "Customer requests a refund for a damaged order."
}
```

This example illustrates the expected structure only. It does not establish that the customer is eligible for a refund.

## 4. Architecture and Responsibilities

### 4.1 LLM Service

The LLM Service:

- Sends requests to the configured LLM provider.
- Returns the provider response according to the existing LLM Service contract.
- Does not own domain business rules.
- Must remain provider-independent at the service abstraction level.

Structured Output must reuse the existing LLM Service rather than introducing a separate provider integration.

### 4.2 Structured Output Layer

The Structured Output layer:

- Owns the Pydantic output model and related schema definitions.
- Parses the LLM-generated content.
- Validates the parsed data against the approved schema.
- Returns a typed, validated object only when parsing and validation succeed.
- Reports parsing and validation failures through a predictable error contract.
- Does not execute business actions.
- Does not access the database or make domain authorization decisions.

### 4.3 Domain / Business Layer

The Domain / Business layer:

- Owns business decisions, including refund eligibility.
- Enforces existing domain rules and authorization requirements.
- Must not treat an LLM-generated category, priority, summary, or escalation flag as authorization to perform an action.

For example, classifying a message as `refund` does not authorize the system to approve or execute a refund.

### 4.4 Processing Flow

The intended flow is:

1. The application obtains an LLM response through the existing LLM Service.
2. The Structured Output layer receives the generated content.
3. The content is parsed and validated against the approved schema.
4. A typed object is returned only if validation succeeds.
5. Downstream components consume the validated object.
6. Any business operation remains subject to the relevant domain rules and authorization checks.

Invalid output must not proceed as a successfully validated object.

## 5. Validation Rules

The implementation must enforce the following rules:

1. All four required fields must be present.
2. Field types must match the schema.
3. `category` must match exactly one of the nine approved category values.
4. `priority` must be one of `low`, `medium`, or `high`.
5. `requires_human` must be a valid boolean.
6. `summary` must be a string containing non-whitespace characters.
7. Unexpected fields must be rejected.
8. Malformed JSON must be rejected.
9. Schema-invalid data must not be returned as a validated object.
10. Validation must be deterministic for the same input and schema.
11. Invalid values must not be silently coerced into valid-looking values.

The implementation must use Pydantic for schema validation and must explicitly configure the model to reject unexpected fields.

## 6. Error Handling

The component must distinguish between:

### 6.1 Error Contract

The Structured Output layer must expose separate exceptions for expected parsing and validation failures:

- `StructuredOutputParseError`: raised when the LLM-generated content cannot be parsed as valid JSON.
- `StructuredOutputValidationError`: raised when the parsed JSON does not conform to the approved Pydantic schema.

The two exceptions must remain distinguishable by callers and unit tests.

The Structured Output layer must not misclassify provider errors as parsing or schema validation errors. Unexpected internal errors must not be silently converted into successful validation results.

The parser must not return a validated object when parsing or validation fails.

### 6.2 Error Handling Tests

Unit tests must verify that:

- Malformed JSON raises `StructuredOutputParseError`.
- Valid JSON that violates the schema raises `StructuredOutputValidationError`.
- Valid JSON that conforms to the schema returns the expected Pydantic object.
- Provider errors are not incorrectly translated into Structured Output errors.


### 6.3 Unexpected Internal Error

An unexpected implementation error occurs during processing.

Expected parsing and validation failures must be represented consistently using an explicit, documented error contract.

The implementation must not silently replace invalid output with defaults or convert invalid output into a valid-looking object.

Provider retries and fallback behavior remain outside this task.

## 7. Testing Requirements

Unit tests must run without requiring a live LLM provider.

### 7.1 Successful Validation

- Valid JSON produces the expected typed object.
- All nine approved category values are accepted.
- All three approved priority values are accepted.
- Valid boolean values are accepted.
- A non-empty summary is accepted.

### 7.2 Invalid Output

- Missing required fields are rejected.
- Invalid field types are rejected.
- Unsupported category values are rejected.
- Unsupported priority values are rejected.
- Invalid boolean representations are rejected.
- Empty summaries are rejected.
- Whitespace-only summaries are rejected.
- Malformed JSON is rejected.
- Unexpected fields are rejected.

### 7.3 Error Contract

- JSON parsing failures are distinguishable from schema validation failures.
- Expected errors follow the documented error contract.
- Unexpected internal errors are not silently misreported as successful validation.
- Invalid responses never produce a validated output object.

### 7.4 Regression

- Existing LLM Service tests continue to pass.
- Existing Domain and Business Rules tests continue to pass.
- The Structured Output unit tests do not require live provider calls.

## 8. Security and Reliability

- LLM output must be treated as untrusted input.
- Schema validation does not establish factual correctness.
- Validated output must not bypass domain authorization or business rules.
- Raw provider responses and internal error details must be handled carefully to avoid exposing sensitive information.
- Error messages exposed to application consumers must not unnecessarily reveal internal implementation details.
- The approved category vocabulary must remain controlled by application code and the specification.

## 9. Implementation Constraints

- Use the existing project architecture and dependency configuration.
- Reuse the existing LLM Service without redesigning it.
- Use Pydantic for schema validation.
- Keep implementation changes limited to the Structured Output subsystem and its tests.
- Do not introduce additional frameworks without an explicit requirement.
- Do not implement RAG, agent workflows, provider retries, or business actions as part of this task.
- Follow the existing project conventions for module structure, configuration, exceptions, and tests.

## 10. Acceptance Criteria

The implementation is accepted when:

- The output contract is documented and reviewed.
- The nine approved category values are explicitly defined and enforced.
- The three allowed priority values are explicitly defined and enforced.
- All required fields and validation constraints are enforced.
- Unexpected fields are rejected.
- Parsing and validation behavior is deterministic.
- Parsing and validation errors follow the documented error contract.
- Invalid responses cannot be returned as validated objects.
- Automated unit tests cover the required success and failure cases.
- Unit tests run without a live LLM provider.
- Existing tests continue to pass.
- No domain business decisions are moved into the Structured Output layer.
- No unrelated subsystem is redesigned.

## 11. Definition of Done

The Structured Output task is complete only after:

1. The specification has been reviewed and approved.
2. The implementation task has been explicitly scoped.
3. The implementation is completed within that scope.
4. Required unit tests pass.
5. Existing regression tests pass.
6. The final changes have been reviewed against this specification.

The specification is the source of truth. Implementation must not begin until the contract and approved category vocabulary are finalized.
