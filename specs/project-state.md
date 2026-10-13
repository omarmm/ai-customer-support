# AI Customer Support Backend — Project State

## Current Position
- Current Day: 25
- Current Phase: Phase 3 — LLM Service
- Day 25: Prompt Management specification approved; Phase 3 verification unblocked, not yet started
- RAG: Blocked until Phase 3 is verified complete

## Last Completed Task
- Task: Prompt Management specification approval
- Commit: 8bc03aa
- Artifacts:
  - specs/llm/prompt-management.md (Draft -> Approved; decision note on path-traversal hardening)
- No implementation or test code changed; specification-only task
- Focused tests: 13 passed (tests/llm/test_prompt_management.py)
- All LLM unit tests: 129 passed (tests/llm, excluding live-Ollama integration)
- Live-Ollama integration test excluded: requires reachable Ollama at
  host.docker.internal:11434 (ConnectError offline); not a unit regression
- Domain suite not run to green here: requires provisioned Postgres
  (12 domain failures on missing DB in this environment); unrelated to this task
- `git diff --check`: clean
- Git working tree: clean at spec commit (state update follows)

## Current Task
- ID: Unassigned
- Title: Phase 3 acceptance verification
- Status: Not started; specification gate now cleared (prompt-management Approved).
  Verify Phase 3 acceptance criteria against implementation and tests before RAG.
- Scope: confirm LLM Service, structured output, prompt management, error handling,
  retries, and token/cost tracking meet their specifications; close Phase 3.
- Depends on: T254 (complete); Prompt Management specification approval (8bc03aa, complete)

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
- Prompt Management approval (8bc03aa): implementation
  `src/app/llm/prompt_management.py` uses stdlib `string.Template` with
  strict `substitute`; validates string names/values, then missing, then
  unexpected before rendering, so no partial output. Values are single-pass
  substituted (never re-evaluated as templates). Template/variable mismatch,
  bad syntax, missing files, and render failures all map to
  `InvalidPromptTemplateError`; unknown/missing/unexpected/invalid-value each
  have a distinct testable type. Error messages carry identifiers/names only,
  never variable values or secrets. No network, no code eval, template file
  never modified. Single shipped template
  `src/app/llm/prompts/support_message_analysis.txt` (`$customer_message`
  only) matches its `PROMPT_DEFINITIONS` entry and contains no secrets.
- Path-traversal hardening is consistent, not a scope expansion: absolute
  paths, `..` segments, and resolved-path escape all raise the existing
  `InvalidPromptTemplateError` (see spec decision log). Covered by
  `test_path_traversal_is_rejected`; no new contract introduced.

## Open Questions
- Verify Phase 3 acceptance criteria against implementation and tests.
- Retry concrete defaults (chosen in T253) may be revisited during Phase 3
  review.

## Rules
- Specifications are the source of truth.
- Never start RAG before Phase 3 closure.
- Implement only one task per session.
- Do not repeat completed audits unless evidence is stale
  or a specific change requires re-verification.
- Update this file at every verified task closure.
