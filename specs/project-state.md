# AI Customer Support Backend — Project State

## Current Position
- Current Phase: Phase 4 — RAG; first specification (knowledge document
  ingestion) verified complete and closed
- Day 25: Phase 3 acceptance verification complete; RAG unblocked
- RAG: Knowledge Document Ingestion Specification approved at
  `specs/rag/knowledge-document-ingestion.md`, including the §15 architecture
  and §16 task breakdown
- Ingestion implementation complete: T255 (fda7b87), T256 (f80f2db),
  T257 (718ccd5), T258 (5da4f9d), and required T259 integration verification
  and closure (this session)
- No ingestion implementation work remains; no defect reopened a task
- Next: define and approve the Chunking specification (Phase 4, second
  specification). Chunking implementation is not authorized

## Last Completed Task
- Task: T259 — Final integration verification and closure (RAG ingestion)
- Commit: 36b4522 (closure record; verification-only, no implementation changes)
- Scope delivered: no feature code; this closure record in
  `specs/project-state.md`
- Verification against §13 and §16:
  - Focused ingestion suite: 104 collected, 100 passed, 4 skipped
    (`pytest tests/rag/ingestion`; skips are the unreadable-root/subdirectory
    permission fixtures, which are environment-conditional under root)
  - Offline rerun with no network: 100 passed, 4 skipped
    (`docker run --network none ... pytest tests/rag/ingestion`), confirming the
    §12 suite is offline and environment-independent
  - Full regression: 242 passed, 4 skipped (`pytest tests`; includes the live
    Ollama integration test)
  - Docker root resolution: `docker compose run --rm api python -c "from
    app.rag.ingestion.paths import default_repo_root; print(default_repo_root())"`
    printed `/app`
  - §13 checklist: documents carry complete metadata; discovery, ordering, IDs,
    and counts are deterministic and repeatable; relative roots resolve against
    the repository root, not the working directory; IDs are SHA-256 of
    normalized UTF-8 bytes; the pipeline imports no network client and performs
    no writes; per-file failures are collected while structural failures raise;
    containment, size, and count limits report metadata only; every declared
    exception has a tested role
  - Change scope since the T254 record: only additive `src/app/rag/ingestion/`
    modules, their tests, additive `knowledge_*` settings, `.env.example`, and
    state documentation; LLM, domain, and database behavior unchanged
  - `git diff --check`: clean
- Outcome: the ingestion specification's acceptance criteria are met; no
  defect was found within approved scope.
- Previously completed: T258 — service, configuration, and root resolution
  (5da4f9d).

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
- ID: Phase 4 RAG — Chunking (specification cycle; task IDs are assigned only
  after the specification is approved)
- Title: Define and approve the knowledge document chunking specification
- Status: Not started; not authorized
- Depends on: ingestion closed (T259 complete)
- Scope: specification-only session under `specs/rag/`; no implementation
- Acceptance: a new approved specification defining the chunking boundary,
  contract, configuration, testing requirements, acceptance criteria, and task
  breakdown
- Note: the roadmap lists chunking as the next Phase 4 item, but no chunking
  specification exists, so no chunking code may be written.

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
- T259 verification: ingestion acceptance criteria met and closed; focused
  ingestion suite 100 passed / 4 skipped, including an offline rerun with
  `--network none`; full regression 242 passed / 4 skipped; Docker
  `default_repo_root()` prints `/app`; ingestion code imports no network client
  and performs no writes.
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
- Phase 4 RAG: ingestion is complete and closed (T255–T259). The next boundary
  is chunking, whose specification does not exist yet; it must be defined and
  approved before any implementation. Remaining Phase 4 specifications
  (embeddings, Qdrant, retrieval, etc.) are undefined and will follow their own
  SDD cycles.
- Retry concrete defaults (chosen in T253) may be revisited during future
  hardening; not a Phase 3 blocker.

## Rules
- Specifications are the source of truth.
- Never start RAG before Phase 3 closure.
- Implement only one task per session.
- Do not repeat completed audits unless evidence is stale
  or a specific change requires re-verification.
- Update this file at every verified task closure.
