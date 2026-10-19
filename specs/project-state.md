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
- T255 complete: ingestion contracts and error taxonomy (fda7b87)
- T256 complete: deterministic discovery and document limit (f80f2db)
- T257 complete: per-file loading pipeline (718ccd5)
- T258 complete: ingestion service, configuration, and root resolution
  (5da4f9d)
- Remaining RAG task: T259 — required integration verification and closure

## Last Completed Task
- Task: T258 — Service, configuration, and root resolution (RAG ingestion)
- Commit: 5da4f9d
- Scope delivered: `src/app/rag/ingestion/service.py`,
  `src/app/rag/ingestion/paths.py`; additive `knowledge_*` settings in
  `src/app/core/config.py`; `.env.example`; `tests/rag/ingestion/test_service.py`,
  `tests/rag/ingestion/test_paths.py`
- Outcome:
  - `default_repo_root()` derives the repository root from the imported `app`
    package (`parents[2]`), never the process working directory, so local and
    Docker (`/app`) layouts agree
  - `resolve_source_root` returns absolute values unchanged and resolves
    relative values against an injectable repository root; it performs no file
    I/O, and the resolved root is reused for discovery and containment
  - `KnowledgeIngestionService` composes `discover` and `load_document`,
    processes candidates sequentially, collects per-file failures, and builds
    the result through `IngestionResult.build`; structural errors still abort
  - Constructor validates both limits as positive (`ValueError`, not an
    ingestion exception); `from_settings` maps `knowledge_dir` and both limits
    without importing, patching, or eagerly calling `get_settings()`
  - Settings are additive with defaults `knowledge`, 1 MiB, and 1000; the two
    limits use `Field(gt=0)` so invalid startup configuration fails via
    Pydantic; `.env.example` documents all three variables
- Evidence:
  - Focused: 100 passed, 4 skipped (`pytest tests/rag`; skips are permission
    fixtures under root plus existing environment-conditional cases)
  - Full suite: 242 passed, 4 skipped (`pytest tests`; includes live-Ollama
    integration)
  - `git diff --check`: clean; diff reviewed against §10, §13, §15.6–§15.7
- Previously completed: T257 — per-file loading pipeline (718ccd5).

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
- ID: T259
- Title: Final integration verification and closure (RAG ingestion)
- Status: Not started (requires a separate authorized session)
- Depends on: T258 (service, configuration, root resolution) — complete
- Scope: no feature code
- Acceptance: §16 T259 — focused ingestion suite and full regression suite
  pass; Docker root-resolution check recorded (`default_repo_root()` must print
  `/app`); `git diff --check` clean; diff reviewed against §13;
  `specs/project-state.md` updated with task IDs, outcomes, commits, tests, and
  exactly one next task; closure commit follows repository precedent
- Note: T259 is mandatory. A defect found there within approved scope reopens
  the owning task instead of being patched in T259.

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
- T258 root resolution: `default_repo_root()` is
  `Path(app.__file__).resolve().parents[2]`; absolute configured roots are
  returned unchanged, relative roots resolve against an injectable repo root,
  and resolution is working-directory independent.
- T258 configuration: `knowledge_dir` defaults to `knowledge`,
  `knowledge_max_document_bytes` to 1 MiB, and
  `knowledge_max_documents_per_run` to 1000; both limits are `gt=0` and the
  service constructor rejects non-positive values before discovery.
- Latest full test run: 242 passed, 4 skipped (`pytest tests`).
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
- Phase 4 RAG: ingestion specification and architecture are approved; T255–T258
  are complete and required T259 remains. No new ingestion code may be written
  outside an authorized task session. Remaining Phase 4 specifications
  (chunking, embeddings, Qdrant, retrieval, etc.) are undefined and will follow
  their own SDD cycles. Chunking must not start before T259 closes ingestion.
- Retry concrete defaults (chosen in T253) may be revisited during future
  hardening; not a Phase 3 blocker.

## Rules
- Specifications are the source of truth.
- Never start RAG before Phase 3 closure.
- Implement only one task per session.
- Do not repeat completed audits unless evidence is stale
  or a specific change requires re-verification.
- Update this file at every verified task closure.
