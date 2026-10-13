# AI Customer Support Backend — Project State

## Current Position
- Current Day: 25
- Current Phase: Phase 3 — LLM Service
- Day 25: In progress — LLM Service implementation
- RAG: Blocked until Phase 3 is verified complete

## Last Completed Task
- Task: T254 — Token and cost tracking
- Commit: b775d31
- Artifacts:
  - specs/llm/token-cost-tracking.md (Approved specification)
  - src/app/llm/cost.py (ModelPricing; PricingTable; pure CostCalculator)
  - src/app/llm/contracts.py (LLMCost value object; additive LLMResponse.cost)
  - src/app/llm/services/llm_service.py (injected calculator; cost + cost_status on success)
  - src/app/llm/providers/ollama.py (both-known total rule; provider totals preserved)
  - src/app/core/config.py (llm_pricing; llm_pricing_currency)
  - .env.example (documents pricing variables)
  - tests/llm/test_cost.py (new)
  - tests/llm/test_contracts.py, test_service.py, test_ollama_provider.py (extended)
- Focused tests: 37 passed
- All LLM tests: 130 passed
- Full suite: 142 passed
- `git diff --check`: clean
- Git working tree: clean at closure

## Current Task
- ID: Unassigned
- Title: Phase 3 acceptance verification
- Status: Not started; verify Phase 3 acceptance criteria against implementation and tests before RAG
- Scope: confirm LLM Service, structured output, prompt management, error handling,
  retries, and token/cost tracking meet their specifications; close Phase 3.
- Depends on: T254 (complete)

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
- Token/cost tracking (T254): `LLMCost` carries Decimal input/output/total costs
  plus currency; exposed via additive `LLMResponse.cost`. Cost is computed only
  for the returned successful response and never affects retry decisions.
- Pricing is externalized (`LLM_PRICING` JSON per 1M tokens, single currency);
  absent/empty pricing is valid and means cost unavailable; malformed JSON and
  negative prices fail clearly. Configured zero is a known zero, never missing.
- `cost_status` is deterministic: pricing_missing -> usage_unavailable ->
  partial -> complete. Costs quantize to 12 decimals, ROUND_HALF_UP, under a
  local decimal context.
- Ollama preserves provider-reported totals; otherwise derives `total_tokens`
  only when both input and output counts are known. Unknown stays None.
- Latest full test run: 142 passed (130 LLM, including 37 focused).

## Open Questions
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
