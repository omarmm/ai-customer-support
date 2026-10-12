# AI Customer Support Backend — Project State

## Current Position
- Current Day: 25
- Current Phase: Phase 3 — LLM Service
- Day 25: In progress — Phase 3 completion review
- RAG: Blocked until Phase 3 is verified complete

## Last Completed Task
- Task: T252 — Error Normalization Implementation
- Commit: 54cbc09
- Artifacts:
  - src/app/llm/exceptions.py (application error taxonomy)
  - src/app/llm/services/llm_service.py (boundary normalization)
  - src/app/llm/providers/exceptions.py (explicit provider HTTP types)
  - src/app/llm/providers/ollama.py (adapter-local HTTP classification)
  - tests/llm/test_error_normalization.py (new)
  - tests/llm/test_ollama_errors.py (extended)
- Focused tests: 35 passed
- All LLM tests: 83 passed
- Full suite: 95 passed
- Git working tree: clean at closure

## Current Task
- ID: T253
- Title: Retry Implementation
- Status: Ready to start; retry policy is defined in specs/llm/error-handling.md §6
- Scope: implement bounded, configurable retries for retryable application errors.
  Retry limits finite; backoff bounded and distinct from the per-attempt timeout;
  no overall deadline; retry count observable. Non-retryable and unexpected
  errors must not be retried.
- Depends on: T252 (complete)

## Verified Findings
- Application error taxonomy in src/app/llm/exceptions.py: `LLMError` plus
  connection, timeout, rate_limit, unavailable, authentication, invalid_request,
  model_not_found, response, configuration, and unexpected subclasses, each with
  class-level `category` and `retryable` attributes.
- LLMService normalizes provider errors deterministically at the boundary;
  provider-level exceptions do not escape to callers.
- Unclassified provider failures map to the base `LLMError`
  (category "unclassified", non-retryable).
- Unexpected exceptions map to `LLMUnexpectedError` with `__cause__` preserved;
  `BaseException`/cancellation is not caught.
- Ollama maps HTTP statuses locally: 429 -> rate limit, 401/403 -> auth,
  400/422 -> invalid request, 404 -> model not found, 5xx -> unavailable;
  408 remains generic (no Ollama-specific timeout evidence).
- Timeout contract: `LLMRequest.timeout` defaults to 30.0; no construction or
  configuration path can supply `None`/invalid values; no timeout validation
  added in T252.
- Latest full test run: 95 passed (83 LLM, including 35 focused).

## Open Questions
- Verify retry policy, cost tracking, and observability during Phase 3 review.
- Verify Phase 3 acceptance criteria against implementation and tests.
- Prompt Management specification still has Draft status.
- Token/cost accounting remains a separate Phase 3 item.

## Rules
- Specifications are the source of truth.
- Never start RAG before Phase 3 closure.
- Implement only one task per session.
- Do not repeat completed audits unless evidence is stale
  or a specific change requires re-verification.
- Update this file at every verified task closure.
