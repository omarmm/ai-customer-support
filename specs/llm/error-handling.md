# LLM Error Handling Specification

**Status:** Approved
**Feature:** LLM Error Handling
**Phase:** LLM Service (Phase 3)

**Related tasks:**
- **T252** — error normalization implementation.
- **T253** — retry implementation.

This document defines the error contract and the retry policy, but implements
neither. Retry implementation belongs to T253; error normalization
implementation belongs to T252.

**Decision log:**
- Application-level exceptions live in `src/app/llm/exceptions.py`, separate from
  provider exceptions in `src/app/llm/providers/exceptions.py`.
- Classification uses explicit provider exception types. Provider adapters own
  provider-specific interpretation; no universal HTTP status-code meanings.
- Unexpected/programming errors are not misclassified as provider failures and
  are not retried; when wrapped, the original cause is preserved.
- Per-attempt timeout is distinct from retry backoff; no overall deadline is
  introduced.

## 1. Purpose

Define a stable application-level error contract for the LLM Service so that
provider failures are normalized into predictable, provider-independent errors,
and so that timeout and retry behavior is explicit, bounded, and testable.

This specification complements `specs/llm/llm-service.md` (§9 Error Handling,
§11 Observability, §12 Security and Cost) and must not contradict it.

## 2. Scope

In scope:

- A provider-independent, application-level error contract.
- A clear separation between provider errors and application service errors.
- Normalization of provider errors into application service errors (defined
  here; implemented in T252).
- Classification of retryable vs. non-retryable errors.
- Retry policy (semantics and constraints only; implemented in T253).
- Timeout behavior and its interaction with retries.
- Error-related observability requirements (requirements only; not a full
  logging/metrics implementation).
- Auditability: provider errors must never leak into the application layer.
- Unit testability without a live provider.

Out of scope:

- Implementing error normalization (T252) or retries/backoff (T253).
- Token/cost accounting and pricing.
- Fallback to a secondary provider.
- Circuit breakers, distributed rate limiting, full structured logging, and
  metrics backends (Phase 8).
- RAG, tools, agent, and prompt-injection handling.
- Provider SDK selection.
- An overall request deadline (see §7).

## 3. Two-Layer Error Model

Errors must be separated into two distinct layers. Application/domain code
depends only on the application layer.

### 3.1 Provider Error Layer (provider-owned)

- Existing taxonomy in `src/app/llm/providers/exceptions.py`:
  `LLMProviderError`, `LLMProviderConnectionError`, `LLMProviderTimeoutError`,
  `LLMProviderHTTPError`, `LLMProviderResponseError`.
- Owned by provider adapters.
- This layer is where **provider-specific semantics live**, including how a
  given provider signals model-not-found, rate limiting, and other conditions.
- Provider adapters translate SDK/HTTP failures into this layer.
- This layer must not be consumed by application or domain code.

### 3.2 Application Service Error Layer (service-owned)

- New taxonomy raised by the LLM Service, located in
  **`src/app/llm/exceptions.py`** — separate from
  `src/app/llm/providers/exceptions.py`.
- Application and domain code depend only on this layer.
- Base exception: `LLMError`.

### 3.3 Boundary Rule

- Normalization from the provider layer to the application layer occurs at the
  LLM Service boundary.
- Provider exceptions (`LLMProvider*`), raw HTTP errors, and provider SDK
  errors must never propagate past this boundary as-is.
- Application code must not need to import provider modules or inspect HTTP
  status codes.

## 4. Application Error Taxonomy

| Exception | Retryable | Meaning |
|---|---|---|
| `LLMError` | — | Base class for all known LLM Service errors. |
| `LLMConnectionError` | Yes | Provider could not be reached. |
| `LLMTimeoutError` | Yes | An attempt exceeded the configured timeout. |
| `LLMRateLimitError` | Yes | Provider throttled the request. |
| `LLMUnavailableError` | Yes | Provider reported a transient server-side fault. |
| `LLMAuthenticationError` | No | Credentials are missing or rejected. |
| `LLMInvalidRequestError` | No | Request is malformed or rejected by the provider. |
| `LLMModelNotFoundError` | No | Provider explicitly reported that the requested model does not exist. |
| `LLMResponseError` | No | Provider response could not be parsed or is malformed. |
| `LLMConfigurationError` | No | Provider/model configuration is missing or invalid. |
| `LLMUnexpectedError` | No | An unexpected internal exception occurred; wraps the original cause and is **not** a known provider failure. |

Each known provider-failure error must carry a stable, machine-readable
`category` and may carry non-sensitive diagnostic context (provider, model).
It must not embed API keys, full prompts, or customer content.

`LLMUnexpectedError` is not part of the known provider-failure set and must be
distinguishable from it by type.

## 5. Normalization Rules

1. The LLM Service maps provider-layer exceptions to the application taxonomy
   **by explicit provider exception type**. Classification is decided by the
   provider adapter, which owns provider-specific interpretation.
2. The service must not classify failures by re-interpreting raw HTTP status
   codes.
3. **No universal status-code meanings.** A given status code does not carry a
   universal meaning across providers. In particular, an HTTP 404 must not be
   assumed to mean "model not found" — it may indicate a missing endpoint, an
   unknown route, or a different provider-specific condition.
   `LLMModelNotFoundError` is raised only when the provider adapter explicitly
   determines model-not-found from that provider's response and raises the
   corresponding provider exception type. Otherwise the failure maps to a
   generic, non-retryable `LLMError`.
4. To support classification, the provider layer may define additional explicit
   provider exception types (for example, distinct types for rate limiting,
   authentication failure, invalid request, model-not-found, and transient
   unavailability). Adding these provider types is part of **T252**.
5. Known provider failures must normalize **deterministically**: the same
   provider exception type always maps to the same application error type.
6. **Unclassified provider errors:** a provider failure that does not match any
   explicitly classified provider exception type (other than unexpected internal
   exceptions) must normalize to a generic, non-retryable `LLMError` — it must
   not be guessed into a more specific category.
7. **Unexpected exceptions:**
   - Programming errors, internal bugs, and non-provider exceptions must not be
     silently classified as provider failures and must never be retried.
   - If the service wraps an unexpected exception at the boundary, it must raise
     `LLMUnexpectedError`, preserve the original exception as the cause
     (`raise ... from exc`), and keep it distinguishable from known provider
     failures.
   - Unexpected exceptions must not be converted into a successful response and
     must not be assigned a known provider-failure category.
8. Normalization must not expose secrets, credentials, full prompts, or
   generated responses in messages.

## 6. Retry Policy (defined here; implemented in T253)

1. Retries apply only to errors classified retryable in §4.
2. Retry limits must be finite and configurable; uncontrolled retry loops are
   forbidden.
3. Retries must not be applied to authentication, invalid-request,
   model-not-found, response, configuration, or unexpected errors.
4. Backoff between attempts must be bounded and must avoid busy-looping
   (bounded exponential backoff, jitter permitted).
5. Retry behavior must be bounded: total provider attempts are limited to
   `1 + max_retries`.
6. Each attempt must honor the per-attempt timeout independently (see §7).
7. Backoff delay is separate from the per-attempt timeout and does not consume
   it.
8. If retries are exhausted, the final normalized error is raised.
9. Retry count must be available for observability.
10. Concrete defaults (e.g. `max_retries`, base delay, jitter) are implementation
    details to be chosen in T253 within these constraints.

## 7. Timeout Behavior

1. Every request must have a timeout; a request without one is invalid.
2. The timeout is **per attempt**: it applies to each provider attempt
   independently.
3. The timeout must be configurable per request and/or by configuration.
4. An attempt that exceeds the timeout must be normalized to `LLMTimeoutError`.
5. Timeouts are retryable subject to §6.
6. **Per-attempt timeout vs. retry backoff:** the timeout bounds a single
   attempt; the retry backoff delay is a separate wait between attempts and is
   not counted against any attempt's timeout.
7. **No overall deadline:** this specification does not introduce a global
   request deadline capping total elapsed time across retries and backoff. The
   existing requirements (`specs/llm/llm-service.md`) specify configurable
   timeouts and bounded retries, not a total deadline. Adding one would change
   behavior beyond the approved scope and requires a separate specification.
8. Timeout handling must not leak HTTP-library-specific exceptions.

## 8. Observability Requirements

Requirements only — building full structured logging or metrics is out of scope
and belongs to Phase 8. The service must make the following available at
completion (success or failure):

- Request duration.
- Provider and model.
- Success/failure status.
- Error category (from §4).
- Retry count.
- Correlation/request identifier when provided.

Constraints:

- Full prompts and generated responses must not be logged by default.
- No secrets, credentials, or customer content in error logs.
- Token usage may be recorded when available; cost calculation is out of scope.

## 9. Configuration

- Retry count, backoff, and timeout must be externalized (per
  `specs/system/configuration.md`), not hard-coded in business logic.
- Secrets remain environment-provided and must never be committed.
- Missing/invalid configuration must fail clearly.

## 10. Testing Requirements

Unit tests must run without a live provider or network access and must verify:

- Each known provider exception type normalizes to the correct application
  error.
- Normalization is deterministic for the same provider exception type.
- Provider-specific exceptions never escape the boundary.
- An unclassified provider error normalizes to a generic, non-retryable
  `LLMError`.
- A provider-ambiguous failure (e.g. a 404 that is not model-not-found for that
  provider) is **not** classified as `LLMModelNotFoundError`.
- An unexpected/programming exception is not classified as a known provider
  failure and is not retried; if wrapped, its original cause is preserved.
- Retryable errors are retried up to the configured limit (once implemented in
  T253).
- Non-retryable errors fail immediately without retry.
- Retry exhaustion raises the final normalized error.
- A per-attempt timeout produces `LLMTimeoutError`; backoff does not consume
  the attempt timeout.
- Error messages contain no secrets or sensitive content.
- Error category and retry count are observable.

## 11. Implementation Constraints

- Reuse the existing LLM Service and provider abstraction; do not redesign them.
- Application exceptions live in `src/app/llm/exceptions.py`, separate from
  provider exceptions in `src/app/llm/providers/exceptions.py`.
- Follow existing project conventions for modules, exceptions, and tests.
- Keep provider implementations replaceable; the error contract is
  provider-neutral.
- Do not introduce new frameworks without an explicit requirement.
- No file changes are made until this specification is approved.

## 12. Acceptance Criteria

- The application error contract is documented and enforced.
- Provider errors and application service errors are separated into two layers,
  in separate modules.
- Provider failures are normalized deterministically by explicit provider
  exception type; no provider SDK/HTTP exception leaks.
- Unclassified provider errors map to a generic, non-retryable `LLMError`.
- Status-code interpretation is provider-specific; no universal status-code
  assumptions.
- Unexpected/programming errors map to `LLMUnexpectedError`, are not
  misclassified as provider failures, are not retried, and preserve their
  original cause when wrapped.
- Retryable and non-retryable errors are distinguished and tested.
- Retry policy is defined and bounded; retry implementation is tracked as T253.
- Timeouts are enforced per attempt and normalized; backoff is distinct from the
  attempt timeout; no overall deadline is introduced.
- Error observability fields are available without implementing full
  logging/metrics.
- Errors expose no secrets or sensitive content.
- Unit tests cover success, failure, normalization, unclassified provider
  errors, unexpected-error handling, timeout, and (once implemented) retry
  paths.
- Existing tests continue to pass.
- No unrelated subsystem is redesigned.

## 13. Definition of Done

1. This specification is reviewed and approved (status: Approved).
2. Error normalization implementation is scoped as T252.
3. Retry implementation remains T253.
4. Focused and regression tests pass.
5. Changes are reviewed against this specification.
