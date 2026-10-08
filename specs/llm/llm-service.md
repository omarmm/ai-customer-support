# LLM Service Specification

## 1. Purpose

The LLM Service provides a controlled abstraction for interacting with Large Language Models.

Its primary purpose is to interpret natural-language input and generate AI-based responses that can be consumed by the application.

The service isolates the application from specific LLM providers and SDKs.

---

## 2. Responsibilities

The LLM Service is responsible for:

- Accepting natural-language requests from the application.
- Sending requests to the configured LLM provider.
- Managing LLM request and response contracts.
- Returning normalized responses to the application.
- Supporting multiple LLM providers through a common abstraction.
- Handling provider-level errors.
- Applying configured timeouts.
- Supporting retry policies where appropriate.
- Providing request-level observability.
- Supporting model and provider configuration.
- Preparing the architecture for future capabilities such as structured outputs, tool calling, and streaming.

The LLM Service may generate recommendations or proposed solutions, but it must not directly execute business actions.

---

## 3. Non-Responsibilities

The LLM Service must NOT:

- Execute business actions.
- Make deterministic business decisions.
- Modify domain state directly.
- Access the database for business operations.
- Implement domain business rules.
- Own customer/order/refund workflows.
- Decide whether an operation is legally or commercially allowed.
- Execute tools directly in this initial implementation.
- Contain application-specific business logic.

The LLM produces AI-generated information or recommendations.

Deterministic decisions remain under the application's domain/business layer.

---

## 4. Architecture

The application must communicate with an LLM through an internal abstraction.

```text
Application
     │
     ▼
┌─────────────────────┐
│     LLM Service     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   LLM Provider      │
│     Interface       │
└──────────┬──────────┘
           │
      ┌────┴─────┐
      ▼          ▼
   Ollama      OpenAI
```

The application must not depend directly on provider-specific SDKs.

Provider implementations are responsible for translating the internal contract into provider-specific requests and translating provider responses back into the internal response format.

---

## 5. Provider Abstraction

The system must define a provider abstraction that represents the minimum operations required by the LLM Service.

The abstraction must hide:

- Provider SDKs.
- HTTP implementation details.
- Provider-specific request formats.
- Provider-specific response formats.
- Provider-specific exceptions.

Initial providers:

- Ollama — local development.
- OpenAI — external/production provider.

Additional providers should be implementable without changing application or domain code.

The application should depend on the abstraction rather than a concrete provider.

---

## 6. Request Contract

The LLM request must contain enough information to perform a model interaction without exposing provider-specific structures.

Initial request information should support:

- System instructions.
- User input.
- Model selection.
- Temperature/configuration where supported.
- Optional metadata.
- Request timeout.

The contract should remain provider-neutral.

Provider-specific parameters must not leak into the application layer.

---

## 7. Response Contract

The LLM Service must return a normalized response independent of the provider.

The response should support:

- Generated content.
- Model identifier.
- Provider identifier.
- Usage information when available.
- Request metadata.
- Optional finish/reason information.

Example conceptual response:

```text
LLMResponse
├── content
├── model
├── provider
├── usage
└── metadata
```

The application must not need to understand the native response format of Ollama or OpenAI.

---

## 8. Configuration

Provider configuration must be externalized from application code.

Configuration should support:

- Active provider.
- Model.
- API endpoint.
- API credentials where required.
- Request timeout.
- Retry configuration.
- Generation parameters.
- Environment-specific configuration.

Secrets must be provided through environment/configuration mechanisms and must not be committed to source control.

The system must support changing the provider through configuration without changing business logic.

---

## 9. Error Handling

The LLM Service must normalize provider failures into application-level exceptions.

Potential failures include:

- Provider unavailable.
- Connection failure.
- Timeout.
- Authentication failure.
- Invalid request.
- Rate limiting.
- Model unavailable.
- Invalid provider response.

Provider-specific exceptions must not propagate directly into the application layer.

Errors must provide enough information for debugging while avoiding exposure of secrets or sensitive data.

Retries must only be applied to errors considered transient.

Non-retryable errors must fail immediately.

---

## 10. Testing

The LLM Service must be testable without requiring a real LLM provider.

Tests must include:

- Provider contract tests.
- Service behavior tests.
- Successful request/response handling.
- Provider failure handling.
- Timeout handling.
- Retry behavior where applicable.
- Response normalization.
- Configuration validation.

Tests should use mocks/fakes for provider interactions.

Integration tests may be added separately for real Ollama/OpenAI interactions.

Unit tests must not depend on network availability.

---

## 11. Observability

The LLM Service must provide sufficient observability for production debugging and cost/performance analysis.

The service should record:

- Request duration.
- Provider.
- Model.
- Success/failure status.
- Error category.
- Token usage when available.
- Retry count.
- Request correlation ID.

Sensitive information must not be logged by default.

Full prompts and generated responses must not be logged indiscriminately because they may contain customer or confidential information.

---

## 12. Security and Cost

The service must:

- Protect provider API credentials.
- Never hard-code secrets.
- Avoid logging sensitive prompts/responses.
- Apply configurable request timeouts.
- Apply reasonable retry limits.
- Track token usage when available.
- Allow model selection through configuration.
- Provide enough usage information to monitor LLM cost.
- Prevent uncontrolled retry loops.
- Keep provider credentials isolated from domain/application data.

Cost optimization is considered a service-level concern, while business-level authorization and spending decisions remain outside the LLM Service.

---

## 13. Architectural Rules

The following rules are mandatory:

1. Domain code must not import LLM provider SDKs.
2. Application code must depend on the LLM abstraction.
3. Provider implementations must remain replaceable.
4. LLM output must never be treated as deterministic business truth.
5. Deterministic business rules must remain outside the LLM.
6. Provider-specific exceptions must be normalized.
7. Unit tests must not require external LLM availability.
8. Secrets must never be committed to the repository.
9. The specification is the source of truth for implementation.
10. Future capabilities such as Structured Outputs, Tool Calling, Streaming, and RAG must extend the abstraction rather than bypass it.