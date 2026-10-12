# AI Customer Support Backend — Project State

## Current Position
- Current Day: 25
- Current Phase: Phase 3 — LLM Service
- Day 25: In progress — LLM Service implementation
- RAG: Blocked until Phase 3 is verified complete

## Last Completed Task
- Task: T253 — Retry Implementation
- Commit: c9da8c8
- Artifacts:
  - src/app/llm/retry.py (RetryPolicy value object; validated defaults; from_settings)
  - src/app/llm/services/llm_service.py (bounded retry loop at the service boundary)
  - src/app/llm/exceptions.py (retry_count observable on LLMError)
  - src/app/core/config.py (externalized retry settings)
  - .env.example (documents retry variables)
  - tests/llm/test_retry.py (new)
- Focused tests: 15 passed
- All LLM tests: 98 passed
- Full suite: 110 passed
- `git diff --check`: clean
- Git working tree: clean at closure

## Current Task
- ID: T254
- Title: Token and cost tracking
- Status: Not started; requires an approved specification before implementation
- Scope: capture token usage and cost accounting at the LLM Service boundary.
  Pricing and cost calculation remain out of scope for Phase 3 error handling;
  a dedicated specification must be written and approved first.
- Depends on: T253 (complete)

## Verified Findings
- RetryPolicy defaults: max_retries=2, base_delay=0.5, max_delay=8.0,
  jitter=0.0. Construction validates invariants and raises ValueError on
  invalid values (negative limits, max_delay < base_delay, jitter < 0).
- Retries apply only to normalized provider errors with `retryable=True`;
  total provider attempts are bounded to `1 + max_retries`.
- Backoff is bounded exponential: `min(base_delay * 2**attempt, max_delay)`,
  with optional jitter. Sleep is injectable, so unit tests never wait.
  Backoff is separate from, and never consumes, the per-attempt timeout;
  no overall deadline is introduced.
- Non-retryable provider errors, unexpected/programming errors, and
  already-normalized `LLMError` pass-through paths are not retried.
  Cancellation/`BaseException` is never swallowed; `__cause__` is preserved.
- Retry count is observable: `response.metadata["retry_count"]` on success;
  `error.retry_count` on exhausted failure. Retry loop state is local per
  call, so concurrent requests do not share mutable retry state.
- LLMService does not eagerly call `get_settings()`; the policy is injected.
  `RetryPolicy.from_settings(settings)` is available for the composition root.
- Latest full test run: 110 passed (98 LLM, including 15 focused).

## Open Questions
- Token/cost accounting needs its own approved specification before T254.
- Verify Phase 3 acceptance criteria against implementation and tests.
- Prompt Management specification still has Draft status.
- Retry concrete defaults (chosen in T253) may be revisited during Phase 3
  review.

## Rules
- Specifications are the source of truth.
- Never start RAG before Phase 3 closure.
- Implement only one task per session.
- Do not repeat completed audits unless evidence is stale
  or a specific change requires re-verification.
- Update this file at every verified task closure.
