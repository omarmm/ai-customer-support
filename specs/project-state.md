# AI Customer Support Backend — Project State

## Current Position
- Current Phase: Phase 4 — RAG; chunking implemented through T263 and verified
  through T264
- T260 — Contracts, configuration identity, and tokenizer protocol — complete
  and committed
- T261 — Token-aware boundary selection and chunk assembly — complete and
  committed (f9030d3)
- T262 — Configuration and chunking service — complete and committed (68dbf55)
- Embedding and tokenizer decision approved (2026-10-23) at
  `specs/rag/embedding-tokenizer-decision.md`; the T263 approval prerequisite
  is satisfied
- T263 — Production tokenizer adapter and conformance — complete and committed
  at `0e5af08dc6c8ec3375a0361836e9d7e0c7196c31` (`feat(rag): add pinned
  tokenizer adapter`). Pinned identity:
  `tokenizers:0.23.3:nomic-ai/nomic-embed-text-v1.5@e9b6763023c676ca8431644204f50c2b100d9aab:d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66`
- T264 — Final integration verification and closure — complete and committed
  in the documentation-only closure commit (`docs: record T264 closure in
  project state`; SHA is recorded in Git history). Verification-only with no
  feature code: focused chunking suite passed offline (265 passed), adapter
  conformance passed offline (30 passed), full regression passed (507 passed,
  4 skipped), `git diff --check` clean, and no behavior outside T263 scope
  changed
- Current task: T265 — Docker tokenizer asset packaging. It is Open, has not
  started, and depends on T264 closure. T266 — Chunking composition-root wiring
  depends on T265 closure and remains Open
- RAG: Knowledge Document Ingestion Specification approved and closed;
  T255–T259 remain closed and unchanged
- RAG: Knowledge Document Chunking Specification approved at
  `specs/rag/knowledge-document-chunking.md` (approval commit: 2bab0a1)

## Last Completed Task
- Task: T264 — Final integration verification and closure
- Commit: this documentation-only closure commit (`docs: record T264 closure in
  project state`); the SHA is recorded in Git history
- Scope delivered: no feature code; this closure record in
  `specs/project-state.md` only. No implementation, test, Dockerfile, or
  unrelated specification changes
- Verification (2026-10-24; Docker image `ai-customer-support-api:latest`;
  HEAD `fbc047a292be615014df74933bef2284d783775c`):
  - Scope audit: `git diff 9312b3f 0e5af08 -- src/ tests/ requirements.txt`
    contains only `tokenizer_adapter.py`, its tests, and the approved
    `tokenizers==0.23.3` pin. `git diff 36b4522 HEAD` shows no changes under
    `src/app/llm`, `src/app/domain`, `src/app/infrastructure`, or
    `src/app/rag/ingestion`; the only `src/app/core/config.py` change is the
    approved additive T262 chunking settings
  - Adapter review: satisfies §5 — loads the local asset, computes SHA-256 from
    the parsed bytes, verifies code-point offsets before normalization, requires
    truncation and padding to be disabled without mutating the configuration,
    disables special tokens per call, and imports no network or Hub modules
  - Asset: 711,396 bytes; SHA-256
    `d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66`
  - Identity measured with networking disabled:
    `tokenizers:0.23.3:nomic-ai/nomic-embed-text-v1.5@e9b6763023c676ca8431644204f50c2b100d9aab:d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66`
  - Focused offline suite: `docker run --rm --network none -v "$PWD:/app" -w
    /app -e PYTHONPATH=/app/src ai-customer-support-api:latest python -m pytest
    tests/rag/chunking -q` → 265 passed, exit 0
  - Adapter conformance offline: same command limited to
    `tests/rag/chunking/test_tokenizer_adapter.py` → 30 passed, exit 0
  - PostgreSQL readiness: `docker compose up -d postgres` reported healthy;
    `docker compose run --rm --no-deps api alembic upgrade head` exited 0
  - Full regression: `docker compose run --rm --no-deps api python -m pytest
    tests -q` → 507 passed, 4 skipped, exit 0 (the skips are the unchanged
    environment-conditional ingestion permission fixtures)
  - `git diff --check`: clean, exit 0; working tree clean before the closure
    edit
- Outcome: all T264 acceptance criteria in §15 pass. The committed T263
  implementation is verified against §5, §14.2, §15, and §20; no defect was
  found and no implementation code was changed. T265 is the sole next task

## Previously Completed Task — T263 (production tokenizer adapter)
- Commit: `0e5af08dc6c8ec3375a0361836e9d7e0c7196c31`
  (`feat(rag): add pinned tokenizer adapter`)
- Scope delivered: `src/app/rag/chunking/tokenizer_adapter.py`; the approved
  `tokenizers==0.23.3` dependency declaration; the vendored
  `assets/tokenizers/nomic-embed-text-v1.5/tokenizer.json`; and
  `tests/rag/chunking/test_tokenizer_adapter.py`, plus the targeted
  specification/status reconciliation. No changes outside the approved T263
  file scope
- Contract implemented: the adapter loads the pinned local asset, computes the
  full SHA-256 from the same bytes it parses, verifies code-point offsets
  before using the existing `normalize_spans` helpers, requires truncation and
  padding to be disabled without mutating the loaded configuration, and
  disables special-token insertion per call. Identity:
  `tokenizers:0.23.3:nomic-ai/nomic-embed-text-v1.5@e9b6763023c676ca8431644204f50c2b100d9aab:d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66`.
  The vendored asset is 711,396 bytes with SHA-256
  `d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66`.
  Input-length compatibility is `500 + 4 prefix + 2 special = 506 <= 2048`
- Verification at implementation time:
  - Adapter tests: 30 passed
  - Focused chunking suite: 265 passed (`pytest tests/rag/chunking`)
  - Full regression: 507 passed, 4 skipped (`pytest tests`; the skips are the
    unchanged environment-conditional ingestion permission fixtures)
  - Adapter tests with networking disabled: 30 passed
  - `git diff --check`: clean; working tree clean after the commit
- Outcome: T263 acceptance criteria and specification test 19 were met; T264
  subsequently verified closure

## Previously Completed Task — T262 (configuration and chunking service)
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
> Historical snapshot at the time of the embedding/tokenizer decision approval
> (2026-10-23). It is preserved as decision history and does not describe the
> current T263 state; see `## Current Position`, `## Current Task`, and the T263
> entry under `## Verified Findings`.
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
  `tokenizers:<lib_version>:<model_id>@<revision_sha>:<sha256(tokenizer.json)>`
  with `model_id` denoting the tokenizer/model repository, not the Ollama
  serving tag. Runtime is a local tokenizer runtime with no runtime network
  access or downloads; dependency installation is normal development setup
- Remaining prerequisites for T263: vendor the asset from the pinned revision
  and compute its full SHA-256; add the approved dependency pin at
  implementation time; evidence `500 + prefix + special` tokens against the
  conservative 2048-token limit; evidence local runtime behavior; authorize and
  execute T263 in a separate session
- Outcome at approval time: the T263 approval prerequisite was met. T263 was
  not complete and had not started; the context-limit compatibility check and
  local runtime behavior had not been tested or claimed

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
- ID: T265 — Docker tokenizer asset packaging
- Title: Package the pinned tokenizer asset into the production image and
  verify adapter operation without a bind mount or network
- Status: Sole next task; Open; not started
- Depends on: T264 closure (this documentation commit) and the approved
  chunking specification §15 and §20.1
- Scope: explicitly copy
  `assets/tokenizers/nomic-embed-text-v1.5/tokenizer.json` into the image at the
  path expected by the adapter; build the image; verify the packaged asset hash,
  approved identity, fixed-sample tokenization, focused chunking tests, and full
  regression with no repository bind mount and networking disabled; record
  actual evidence in this file
- Acceptance: see `specs/rag/knowledge-document-chunking.md` §15 T265. T265
  must not claim results before they are measured
- Note: T266 — Chunking composition-root wiring — depends on T265 closure and
  remains Open; it is not part of T265

## Task Ordering
1. T265 — Docker tokenizer asset packaging.
2. T266 — Production chunking composition-root wiring.

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
- T264 verification (2026-10-24): the scope audit found only the approved T263
  adapter, its tests, and the `tokenizers==0.23.3` pin; no LLM, domain,
  infrastructure, or ingestion changes since T259, and the only configuration
  change is the approved additive T262 chunking settings. The vendored asset is
  711,396 bytes with the approved SHA-256. Focused chunking suite with
  `--network none`: 265 passed (exit 0); adapter conformance offline: 30 passed
  (exit 0); full regression with PostgreSQL healthy and migrations at head:
  507 passed, 4 skipped (exit 0); the measured identity equals the approved
  identity; `git diff --check` was clean (exit 0). No defect was found, no
  implementation code changed, and T264 closed verification-only.
- Latest full test run: 507 passed, 4 skipped (2026-10-24, `pytest tests` in
  Docker with PostgreSQL running; the skips are the unchanged
  environment-conditional ingestion permission fixtures).
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
  `tokenizers:<lib_version>:<model_id>@<revision_sha>:<sha256(tokenizer.json)>`.
  `model_id` is the tokenizer/model repository, not the Ollama serving tag; the
  serving tag is excluded from the chunking identity so serving-side changes do
  not force re-chunking. The adapter loads the pinned asset from a local
  filesystem path and tokenizes without runtime network access or Hugging Face
  Hub access; dependency installation is normal development setup, with no
  offline-installation requirement. Adapter behavior disables special tokens,
  truncation, and padding. The conservative input limit is 2048 tokens. The
  asset checksum, dependency installability, local runtime behavior, and the
  `500 + prefix + special <= 2048` check are T263 verification items and were
  not performed by this documentation-only approval. They were subsequently
  verified in T263; see the T263 implementation finding below.
- T263 implementation (review documentation corrections applied):
  `src/app/rag/chunking/tokenizer_adapter.py` loads the vendored asset from
  disk, computes the full SHA-256 from the same bytes it parses, and verifies
  code-point offsets before using the existing `normalize_spans` helpers. It
  does not mutate the loaded configuration: truncation and padding must already
  be disabled, otherwise it raises `asset_truncation_enabled` or
  `asset_padding_enabled`; special-token insertion is disabled per call.
  Identity is
  `tokenizers:0.23.3:nomic-ai/nomic-embed-text-v1.5@e9b6763023c676ca8431644204f50c2b100d9aab:d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66`,
  computed from the vendored file; no digest is hard-coded. Compatibility
  measured at `500 + 4 prefix + 2 special = 506 <= 2048`. Focused adapter
  tests: 30 passed (including four configuration-mutation tests); chunking
  suite: 265 passed; full suite: 507 passed, 4 skipped; adapter suite with
  `--network none`: 30 passed. Committed at
  `0e5af08dc6c8ec3375a0361836e9d7e0c7196c31`; the working tree was clean after
  the commit. T264 subsequently verified and closed the task.
- Day 26 chunking approval (2bab0a1):
  `specs/rag/knowledge-document-chunking.md` is Status: Approved. It defines
  token-based chunking with a 500-token maximum and 75-token overlap that were
  provisional at approval; deterministic configuration and chunk IDs with
  `source_path` included in chunk identity; exact Unicode code-point source
  slices; a precise raw-token-span validation and whitespace-normalization
  contract; zero-chunk representation for empty and whitespace-only documents;
  duplicate `(source_path, document_id)` rejection; and an original five-task
  breakdown T260–T264, to which T265 and T266 were added later.
  T260–T262 have since completed; T263 has since completed and is committed at
  `0e5af08dc6c8ec3375a0361836e9d7e0c7196c31`; T264 subsequently closed
  verification-only. The embedding model/tokenizer decision was subsequently
  approved (see above). No implementation code or dependencies were added by
  the approval.
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
- Phase 4 RAG: ingestion (T255–T259), the chunking specification, T260–T264,
  and the embedding/tokenizer decision are complete. T263 is committed at
  `0e5af08dc6c8ec3375a0361836e9d7e0c7196c31`; the asset is vendored, the
  dependency pin is present, and input-length compatibility is recorded as
  `506 <= 2048`. T264 closed verification-only with focused offline, adapter
  conformance, and full regression evidence. T265 is the sole next task.
  Remaining Phase 4 specifications (embeddings, Qdrant, retrieval, etc.) are
  undefined and will follow their own SDD cycles.
- Chunking defaults of 500 tokens and 75 tokens of overlap are confirmed for
  the approved model: `500 + 4 prefix + 2 special = 506 <= 2048`.
- T265 — Docker tokenizer asset packaging — is Open and is the sole next task
  after T264 closure; it has not started. It must explicitly package the pinned
  asset in the image and verify adapter operation without a repository bind
  mount and without network access.
- T266 — Chunking composition-root wiring — is Open and depends on T265
  closure. It must use the canonical `app` import root and
  `uvicorn app.main:app`, add the composition factory at
  `src/app/rag/chunking/composition.py`, expose the service through `app.state`,
  and verify the production wiring with an integration test. Neither follow-up
  is resolved; see `specs/rag/knowledge-document-chunking.md` §20.
- Retry concrete defaults (chosen in T253) may be revisited during future
  hardening; not a Phase 3 blocker.

## Rules
- Specifications are the source of truth.
- Never start RAG before Phase 3 closure.
- Implement only one task per session.
- Do not repeat completed audits unless evidence is stale
  or a specific change requires re-verification.
- Update this file at every verified task closure.
