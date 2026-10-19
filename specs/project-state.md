# AI Customer Support Backend — Project State

## Current Position
- Current Phase: Phase 3 — LLM Service verified complete and closed; Phase 4 — RAG active
- Day 25: Phase 3 acceptance verification complete; RAG unblocked
- RAG: Knowledge Document Ingestion Specification approved and saved at
  `specs/rag/knowledge-document-ingestion.md` (specification-only session,
  documentation-only changes, no commit, no implementation)
- RAG ingestion architecture/contract design approved and recorded in the same
  specification (§15 Placement and Contract Changes, §16 Task Breakdown);
  sections 1–14 and the decisions log are byte-for-byte unchanged
- Implementation tasks defined: T255–T258 plus required T259 integration
  verification and closure; task IDs continue the sequence after T254
- T255 complete: ingestion contracts and error taxonomy implemented and
  committed (fda7b87); RAG implementation in progress
- Remaining RAG implementation tasks: T256 (discovery and limit), T257 (loading
  pipeline), T258 (service, configuration, root resolution), T259 (required
  verification and closure)

## Last Completed Task
- Task: T255 — RAG ingestion contracts and error taxonomy
- Commit: fda7b87 (implementation); b568f20 records the approved specification
  and architecture design
- Scope delivered: `src/app/rag/ingestion/contracts.py`, `exceptions.py`, and
  package `__init__.py` files; `tests/rag/ingestion/test_contracts.py` and test
  package `__init__.py` files
- Outcome:
  - `IngestionResult` is a frozen dataclass storing immutable tuple
    collections; `__post_init__` sorts each collection ascending by relative
    POSIX path and coerces to tuple, so ordering cannot be bypassed by direct
    construction; `build()` is the canonical construction path
  - Counts are derived read-only properties (`succeeded_count`, `skipped_count`,
    `failed_count`, `candidate_count`, `discovered_count`, `has_failures`); no
    stored counts, so no construction path can contradict the collections
  - `candidate_count` adds skipped entries with reason
    `document_limit_exceeded`; both §9 count invariants are covered by tests
  - Error taxonomy: `IngestionError` base plus `SourceRootError` (structural)
    and the five per-file classifications, each with a stable distinct
    `error_type`; messages combine a fixed description with the path only —
    never document content; `FailedEntry.from_error` derives the stable name
- Evidence:
  - Focused: 18 passed (`pytest tests/rag`, run in the project Docker image)
  - Full suite: 160 passed (`pytest tests`, includes live-Ollama integration)
  - `git diff --check`: clean
- Note: `src/app/rag/__init__.py` (empty) was added so the RAG package follows
  the existing package convention; it is the only file beyond the T255 scope
  listed in the previous state entry.

## Phase 3 Closure Record — LLM Service (closed)
- Task: Phase 3 acceptance verification (specification gate review, no feature code)
- Commit: 1278734 (state record; verification-only, no implementation changes)
- Scope verified: LLM Service, structured output, prompt management, error handling,
  retries, and token/cost tracking against their approved specifications
- Evidence:
  - Full suite: 142 passed (`pytest tests/`, includes live-Ollama integration
    `test_ollama_real_integration` which now passes; Ollama reachable)
  - LLM unit suite: 129 passed (`tests/llm --ignore=test_ollama_integration.py`)
  - Focused: 13 passed (`tests/llm/test_prompt_management.py`); 104 passed across
    prompt/structured-output/error-normalization/retry/cost/service files
  - `git diff --check`: clean; working tree clean (verification-only session,
    no implementation changes)
- Verified findings carried forward plus closure checks:
  - Provider abstraction holds: app depends on `LLMProvider` (`providers/base.py`);
    provider errors (`providers/exceptions.py`) never escape — normalized at
    `LLMService` boundary to `src/app/llm/exceptions.py` taxonomy; deterministic
    map with unclassified -> generic non-retryable `LLMError`
  - Structured output enforces 9 categories + 3 priorities (`StrEnum`,
    `strict=True`, `extra="forbid"`); `StructuredOutputParseError` distinct from
    `StructuredOutputValidationError`; whitespace-only summary rejected; no
    coercion; no validated object on failure
  - Prompt management uses stdlib `string.Template` + strict `substitute`;
    validates value types, then missing, then unexpected before rendering;
    path-traversal (absolute/`..`/escape) -> existing `InvalidPromptTemplateError`;
    shipped template `support_message_analysis.txt` (`$customer_message` only)
    matches `PROMPT_DEFINITIONS`
  - Retry/cost/config externalized in `src/app/core/config.py`
    (`llm_max_retries`, delays, `llm_pricing`, currency); service injects
    `RetryPolicy`/`CostCalculator`, never eagerly calls `get_settings()`
- Phase 3 is closed. No open Phase 3 acceptance items.

## Current Task
- ID: T256
- Title: Deterministic discovery and limit (RAG ingestion)
- Status: Not started (requires a separate authorized implementation session)
- Depends on: T255 (contracts and error taxonomy) — complete
- Scope: `src/app/rag/ingestion/discovery.py`;
  `tests/rag/ingestion/test_discovery.py`
- Acceptance: §4, §5, §9, and §15.3–§15.4 of the specification — deterministic
  depth-first traversal with children in ascending name order; POSIX relative
  paths; unsupported extensions skipped as `unsupported_format`; candidates
  sorted before the limit; `document_limit_exceeded` entries never stat'ed,
  containment-checked, or read; directory symlinks never traversed; traversal
  failures at any level raise `SourceRootError`; §12 tests 1, 2, 11
- Remaining work after T256: T257 (loading pipeline), T258 (service,
  configuration, root resolution), and required T259 (integration verification
  and closure)
- Note: no implementation of T256 is authorized yet

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
- Phase 4 RAG: ingestion specification and architecture are approved; T255 is
  complete and T256–T258 plus required T259 remain. No ingestion code may be
  written outside an authorized task session. Remaining Phase 4 specifications
  (chunking, embeddings, Qdrant, retrieval, etc.) are undefined and will follow
  their own SDD cycles.
- Retry concrete defaults (chosen in T253) may be revisited during future
  hardening; not a Phase 3 blocker.

## Rules
- Specifications are the source of truth.
- Never start RAG before Phase 3 closure.
- Implement only one task per session.
- Do not repeat completed audits unless evidence is stale
  or a specific change requires re-verification.
- Update this file at every verified task closure.
