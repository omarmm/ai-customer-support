# AI Customer Support Backend — Project State

## Current Position
- Current Phase: Phase 4 — RAG; chunking implementation underway
- T260 — Contracts, configuration identity, and tokenizer protocol — complete
  and committed
- T261 — Token-aware boundary selection and chunk assembly — complete and
  committed (f9030d3)
- T262 — Configuration and chunking service — complete and committed (68dbf55)
- Embedding and tokenizer decision approved (2026-10-23) at
  `specs/rag/embedding-tokenizer-decision.md`; the T263 approval prerequisite
  is satisfied
- Next: T263 — Production tokenizer adapter and conformance. It has not started
  and requires a separate authorized session. Tokenizer asset vendoring,
  checksum computation, and the 2048-token compatibility check remain pending
- RAG: Knowledge Document Ingestion Specification approved and closed;
  T255–T259 remain closed and unchanged
- RAG: Knowledge Document Chunking Specification approved at
  `specs/rag/knowledge-document-chunking.md` (approval commit: 2bab0a1)

## Last Completed Task
- Task: T262 — Configuration and chunking service
- Commit: 68dbf55 (implementation; this project-state record follows in a
  separate documentation commit)
- Scope delivered: `src/app/rag/chunking/service.py`; additive chunking fields
  and cross-field validation in `src/app/core/config.py`; `.env.example`;
  `tests/rag/chunking/test_service.py`; no changes outside T262 file scope
- Contract implemented: `knowledge_chunk_max_tokens` defaults to 500 with
  `gt=0`; `knowledge_chunk_overlap_tokens` defaults to 75 with `ge=0`;
  `Settings` rejects `overlap_tokens >= max_tokens` at construction.
  `ChunkingService` builds one effective `ChunkingConfig` from explicit values
  and the tokenizer identity, supports `from_settings(settings, tokenizer)`
  without reading global settings, rejects duplicate
  `(source_path, document_id)` pairs before chunking, preserves zero-chunk
  documents, and aggregates deterministically through `ChunkingResult`.
- Verification:
  - Focused: 235 passed (`pytest tests/rag/chunking`)
  - Full regression: 477 passed, 4 skipped (`pytest tests` with PostgreSQL
    running; the skips are the unchanged environment-conditional ingestion
    permission fixtures)
  - `git diff --check`: clean; no changes outside T262 file scope
  - Service-level tests 12, 13, 15, 17, and 18 pass, plus settings validation
    and non-eager settings composition
- Outcome: T262 acceptance criteria in §9 and §15 are met

## Approved Decision — Embedding and tokenizer (T263 prerequisite)
- Task: Approve the embedding provider/model and production tokenizer decision
  (specification/decision gate; documentation only)
- Commit: this documentation commit (`docs(rag): approve embedding tokenizer
  decision`); SHA is recorded in Git history
- Scope delivered: `specs/rag/embedding-tokenizer-decision.md`; targeted updates
  to §5.7, §17, and the task-breakdown note in
  `specs/rag/knowledge-document-chunking.md`; this state record. No application
  code, tests, dependencies, model pulls, or tokenizer assets
- Decision recorded: Ollama serving model `nomic-embed-text:v1.5`;
  tokenizer `tokenizers==0.23.3`; repository
  `nomic-ai/nomic-embed-text-v1.5` at revision
  `e9b6763023c676ca8431644204f50c2b100d9aab`; asset `tokenizer.json`;
  identity format
  `tokenizers:<lib_version>:<model_id>@<revision_sha>:<sha256(tokenizer.json)[:12]>`
  with `model_id` denoting the tokenizer/model repository, not the Ollama
  serving tag. Runtime is local-first with no remote downloads or remote model
  code
- Remaining prerequisites for T263: vendor the asset from the pinned revision
  and compute its full SHA-256; add the approved dependency pin at
  implementation time; evidence `500 + prefix + special` tokens against the
  conservative 2048-token limit; authorize and execute T263 in a separate
  session
- Outcome: the T263 approval prerequisite is met. T263 is not complete and has
  not started. The context-limit compatibility check was not performed and is
  not claimed as passed

## Previously Completed Task — T261 (boundary selection and assembly)
- Task: T261 — Token-aware boundary selection and chunk assembly
- Commit: f9030d3 (state record c61676a)
- Scope delivered: `src/app/rag/chunking/chunker.py` and
  `tests/rag/chunking/test_chunker.py` with deterministic fixture tokenizers
- Contract implemented: `chunk_document` follows §6 (token window, rightmost
  paragraph → sentence → word boundary, hard cut, bounded overlap, forward
  progress); exact source slices and token indexes via `Chunk.build`; empty and
  whitespace-only documents short-circuit with zero tokens and zero chunks
  without calling the tokenizer; spans validated and normalized per §5
- Verification: focused 199 passed (`pytest tests/rag/chunking`); full
  regression 441 passed, 4 skipped (`pytest tests`); `git diff --check` clean
- Outcome: T261 acceptance criteria and tests 3–15 and 18 pass in addition to
  the T260 tests

## Previously Completed Task — T260 (chunking contracts)
- Task: T260 — Contracts, configuration identity, and tokenizer protocol
- Commit: 8721376 (state record 6262d5a)
- Scope delivered: `src/app/rag/chunking/` contracts, configuration/chunk ID
  formulas, tokenizer protocol, raw-span validation/normalization, and error
  taxonomy; `tests/rag/chunking/`
- Contract implemented: frozen `Chunk`, `DocumentChunking`, `ChunkingResult`,
  and `ChunkingConfig`; §7.4 invariants enforced on direct and built
  construction; canonical JSON SHA-256 configuration and chunk IDs per §8; §5
  span validation and normalization, including byte-to-code-point conversion
  with rejection of non-code-point byte boundaries; `ChunkingError` and
  `TokenizerContractError` with content-free messages
- Outcome: T260 acceptance criteria and tests 1, 2, 16, and 17 pass

## Previously Completed Task — Chunking specification approval
- Task: Day 26 — RAG Chunking Specification approval (specification gate;
  no feature code)
- Commit: 2bab0a1 (specification approval; state record 6d39a8e)
- Scope delivered: approved `specs/rag/knowledge-document-chunking.md`; no
  application, test, dependency, or environment changes
- Contract recorded: token-based chunking with 500-token default maximum and
  75-token default overlap; configuration ID covering tokenizer identity,
  algorithm version, maximum, and overlap; deterministic chunk IDs including
  `source_path`; exact source slices and Unicode code-point offsets;
  empty/whitespace documents represented with zero chunks; duplicate
  `(source_path, document_id)` pairs rejected; no minimum chunk size in V1
- Task breakdown recorded: T260–T264, with T263 blocked pending the separate
  embedding model/tokenizer decision
- Outcome: specification approved; T260–T264 remained unauthorized until a
  separate session
- Previously completed: T259 — Final integration verification and closure
  (RAG ingestion)

## Previously Completed Task — T259 (RAG ingestion closure)
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
- ID: T263 — Production tokenizer adapter and conformance
- Title: Implement the approved production tokenizer adapter and verify
  conformance
- Status: Decision approved; implementation not started. Requires a separate
  authorized session
- Depends on: T262 (68dbf55) and the approved embedding/tokenizer decision at
  `specs/rag/embedding-tokenizer-decision.md`
- Scope: selected adapter module; approved dependency declaration;
  `tests/rag/chunking/test_tokenizer_adapter.py`
- Acceptance: specification §5 and test 19; partition; determinism; no
  truncation; token limit; pinned identity; embedding input-length
  compatibility against the conservative 2048-token limit (amend the
  specification if 500/75 does not fit)
- Note: T264 (final integration verification and closure) follows T263. The
  tokenizer asset must be vendored from the pinned revision and its full
  SHA-256 computed before the adapter identity is finalized. The compatibility
  result remains unverified until T263 evidence exists; it must not be claimed
  in advance.

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
- T261 verification: `chunk_document` follows §6 with a deterministic fixture
  tokenizer. Empty and whitespace-only content short-circuits to zero tokens
  and zero chunks without calling the tokenizer; non-empty content tokenizes
  exactly once and validates/normalizes spans per §5. Boundaries prefer the
  rightmost paragraph, then sentence, then word boundary, with a hard cut;
  chunks are exact source slices with code-point offsets and contiguous token
  indexes; every chunk satisfies `token_count <= max_tokens`; overlap never
  exceeds its target and the next window always advances. Focused chunking
  suite: 199 passed; full regression: 441 passed, 4 skipped.
- Latest full test run: 477 passed, 4 skipped (`pytest tests` with PostgreSQL
  running; the skips are the unchanged environment-conditional ingestion
  permission fixtures).
- T262 verification: additive settings default to 500/75, are environment
  configurable, and reject `overlap_tokens >= max_tokens` at `Settings`
  construction. `ChunkingService` builds one config per service, uses
  `from_settings` without importing or calling `get_settings`, rejects duplicate
  `(source_path, document_id)` pairs before tokenizing, preserves zero-chunk
  documents, and aggregates through `ChunkingResult` so ordering is independent
  of input order. Focused chunking suite: 235 passed; full regression: 477
  passed, 4 skipped. No changes outside T262 file scope.
- Embedding/tokenizer decision approval (2026-10-23):
  `specs/rag/embedding-tokenizer-decision.md` records Ollama
  `nomic-embed-text:v1.5`, `tokenizers==0.23.3`, repository
  `nomic-ai/nomic-embed-text-v1.5` at revision
  `e9b6763023c676ca8431644204f50c2b100d9aab`, asset `tokenizer.json`, and the
  identity format
  `tokenizers:<lib_version>:<model_id>@<revision_sha>:<sha256(tokenizer.json)[:12]>`.
  `model_id` is the tokenizer/model repository, not the Ollama serving tag; the
  serving tag is excluded from the chunking identity so serving-side changes do
  not force re-chunking. Runtime is local-first with no remote downloads or
  remote model code; adapter behavior disables special tokens, truncation, and
  padding. The conservative input limit is 2048 tokens. The asset checksum,
  dependency installability, and the `500 + prefix + special <= 2048` check are
  T263 verification items and were not performed by this documentation-only
  approval.
- Day 26 chunking approval (2bab0a1):
  `specs/rag/knowledge-document-chunking.md` is Status: Approved. It defines
  token-based chunking with provisional 500-token maximum and 75-token overlap
  defaults; deterministic configuration and chunk IDs with `source_path`
  included in chunk identity; exact Unicode code-point source slices; a precise
  raw-token-span validation and whitespace-normalization contract;
  zero-chunk representation for empty and whitespace-only documents; duplicate
  `(source_path, document_id)` rejection; and a five-task breakdown T260–T264.
  T260–T262 have since completed; T263 is next, and the embedding
  model/tokenizer decision was subsequently approved (see above). No
  implementation code or dependencies were added by the approval.
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
- Phase 4 RAG: ingestion (T255–T259), the chunking specification, T260–T262,
  and the embedding/tokenizer decision are complete. T263 is next; its approval
  prerequisite is met, but it has not started and requires a separate
  authorized session. Before T263 can close, the tokenizer asset must be
  vendored with a computed checksum, the approved dependency pin added, and the
  2048-token compatibility check evidenced. Remaining Phase 4 specifications
  (embeddings, Qdrant, retrieval, etc.) are undefined and will follow their own
  SDD cycles.
- Chunking defaults of 500 tokens and 75 tokens of overlap are provisional
  until T263 records the compatibility result against the conservative
  2048-token limit.
- Retry concrete defaults (chosen in T253) may be revisited during future
  hardening; not a Phase 3 blocker.

## Rules
- Specifications are the source of truth.
- Never start RAG before Phase 3 closure.
- Implement only one task per session.
- Do not repeat completed audits unless evidence is stale
  or a specific change requires re-verification.
- Update this file at every verified task closure.
