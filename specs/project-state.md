# AI Customer Support Backend — Project State

## Current Position
- Current Phase: Phase 4 — RAG. Ingestion (T255–T259), chunking (T260–T266),
  and embeddings contracts through live conformance (T267–T270) are complete.
  T271 composition-root wiring is the single next authorized task.
- T270 — Live Ollama conformance, dimension verification, regression, and
  closure — complete and committed at
  `95eb8ed1a1a29c5701dcb849c90c353673f2ba70`
  (`test(rag): add live ollama embedding conformance evidence`)
- T269 — Embedding service, batching, ordering, validation, retries, and
  settings integration — complete and committed at
  `3d756db1dc484dcc63a0cb6d0c00652bc6e5cf38`
  (`feat(rag): add embedding service and retry policy`)
- T268 — Ollama embedding adapter and offline HTTP-mock tests — complete and
  committed at `b66d3c1d01efe758707e51af59d1a133f4451ac4`
  (`feat(rag): add ollama embedding adapter`)
- T267 — Embedding contracts, identity, configuration, and error taxonomy —
  complete and committed at `a22411eb4b41fc84884a890dcb528f1722893e09`
  (`feat(rag): add embedding contracts and error taxonomy`)
- T266 — Chunking composition-root wiring — complete and committed at 35e869b;
  startup constructs the approved tokenizer, injects it into
  `ChunkingService.from_settings`, and exposes the service through `app.state`.
  The canonical import root is `app` and the entry point is
  `uvicorn app.main:app`
- T260–T262 — chunking contracts, boundary assembly, configuration, and service —
  complete and committed (8721376, f9030d3, 68dbf55)
- T263–T265 — production tokenizer adapter, closure verification, and Docker
  asset packaging — complete (0e5af08, documentation closure, d126cb7)
- Embedding and tokenizer decision approved (2026-10-23) at
  `specs/rag/embedding-tokenizer-decision.md`; pinned tokenizer identity:
  `tokenizers:0.23.3:nomic-ai/nomic-embed-text-v1.5@e9b6763023c676ca8431644204f50c2b100d9aab:d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66`
- Live conformance evidence (2026-10-25): served model `nomic-embed-text:v1.5`;
  response `model` equals the pinned tag; observed dimension `768`, equal to
  `PROVISIONAL_EMBEDDING_DIMENSION`; all 2,304 returned values finite; digest
  reported by `GET /api/tags` recorded verbatim as
  `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`
  (evidence only, not runtime verification). `768` is confirmed by live
  measurement; no specification amendment is required.
- Current task: none. No implementation task is in progress. T270 is complete;
  T271 is authorized by the approved sequence and requires a separate session.
- Current activity: T270 was implemented, verified, and committed on 2026-10-25.
- Status: `Approved`. The Phase 4 embeddings specification remains the source
  of truth; T267–T270 are complete and T271 is the single next authorized task.
- RAG: Knowledge Document Ingestion Specification approved and closed;
  T255–T259 remain closed and unchanged
- RAG: Knowledge Document Chunking Specification approved at
  `specs/rag/knowledge-document-chunking.md` (approval commit: 2bab0a1);
  T260–T266 are complete
- RAG: Knowledge Document Embeddings Specification approved at Revision 2;
  T267–T271 are the approved implementation sequence; T267–T270 are complete
  and T271 is the single next authorized task

## Last Completed Task
- Task: T270 — Live Ollama conformance, dimension verification, regression, and
  closure
- Commit: `95eb8ed1a1a29c5701dcb849c90c353673f2ba70`
  (`test(rag): add live ollama embedding conformance evidence`); this project
  state record follows in a separate documentation commit
- Scope delivered: new `tests/rag/embeddings/test_ollama_conformance.py`; this
  project-state record. No production, adapter, service, retry, settings,
  composition-root, endpoint, persistence, Qdrant, metadata-client, chunking,
  ingestion, LLM, domain, Dockerfile, or dependency code was added or changed
- Contract implemented: the live suite is opt-in behind `RUN_LIVE_OLLAMA=1`
  (D-5) and is skipped in the default and offline focused suites. It reads the
  existing `OLLAMA_URL` setting (D-6) with a `http://localhost:11434` fallback,
  records the model entry reported by `GET /api/tags`, and records the raw
  `POST /api/embed` response model and measured dimension. It asserts the
  response model equals `nomic-embed-text:v1.5`, the observed dimension equals
  `PROVISIONAL_EMBEDDING_DIMENSION`, and every returned value is finite. A
  third test exercises `OllamaEmbeddingProvider` against the live model. The
  digest is recorded verbatim as evidence only; no test or document claims
  runtime digest verification
- Live evidence (2026-10-25; host Ollama 0.33.2; model pulled locally):
  - Metadata command: `curl -s http://localhost:11434/api/tags`
  - Served model name: `nomic-embed-text:v1.5`
  - Served digest (verbatim):
    `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`
  - Reported details: `family=nomic-bert`, `parameter_size=137M`,
    `quantization_level=F16`, `context_length=2048`, `embedding_length=768`,
    `size=274302450`, `capabilities=["embedding"]`
  - Response `model`: `nomic-embed-text:v1.5`
  - Observed dimension: `768` (three vectors; 2,304 values total), all finite
  - Result: `768` equals the provisional expected dimension and is confirmed by
    live measurement; no specification amendment is required
- Verification (2026-10-25; image `ai-customer-support-t270:local`, ID
  `sha256:27dc10ce59319cf3f9ccda4b1d45558d3f6efb1cedc5f670538c08e2417e7ee4`;
  no repository bind mount in image verification runs):
  - Build: `docker build -t ai-customer-support-t270:local .` → exit 0
  - Live conformance: `docker run --rm --network ai-customer-support_default
    --add-host host.docker.internal:host-gateway --env-file .env
    -e RUN_LIVE_OLLAMA=1 ai-customer-support-t270:local python -m pytest
    tests/rag/embeddings/test_ollama_conformance.py -q -s` → 3 passed, exit 0
  - Focused offline suite: `docker run --rm --network none
    ai-customer-support-t270:local python -m pytest tests/rag/embeddings -q` →
    300 passed, 3 skipped, exit 0
  - Full regression: `docker run --rm --network ai-customer-support_default
    --add-host host.docker.internal:host-gateway --env-file .env
    ai-customer-support-t270:local python -m pytest tests -q` → 812 passed,
    7 skipped, exit 0. Networking was required for PostgreSQL and the live
    Ollama integration test; the 7 skips are the 4 unchanged
    environment-conditional ingestion permission fixtures plus the 3 opt-in
    live embedding conformance tests. No repository bind mount was used
  - `git diff --cached --check`: clean, exit 0; the implementation diff is
    limited to the new conformance test file
- Outcome: T270 acceptance criteria in §11.4, §12, and §13 are met. The live
  model name, response model, dimension, and digest are recorded as evidence;
  the observed dimension matches `768`, so no amendment is required; the
  offline and full suites pass; and no runtime digest verification is claimed.
  No next implementation task was started; T271 is the single next authorized
  task.

## Previously Completed Task — T269 (embedding service)
- Task: T269 — Embedding service, batching, ordering, validation, retries, and
  settings integration
- Commit: `3d756db1dc484dcc63a0cb6d0c00652bc6e5cf38`
  (`feat(rag): add embedding service and retry policy`); this project state
  record follows in a separate documentation commit
- Scope delivered: new `src/app/rag/embeddings/service.py` and
  `src/app/rag/embeddings/retry.py`; additive `embedding_*` settings in
  `src/app/core/config.py`; `.env.example`; and
  `tests/rag/embeddings/test_service.py` and `test_retry.py`. No composition
  root, startup wiring, endpoint, persistence, Qdrant, metadata client,
  provider-adapter, chunking, ingestion, LLM, or domain code was added or
  changed
- Contract implemented: `EmbeddingService(provider, config=None, batch_size=16,
  timeout=30.0, retry_policy=None, sleep=None)` builds one effective
  `EmbeddingConfig`, validates `provider.identity` against
  `f"{config.provider}:{config.model}"`, validates positive `batch_size` and
  `timeout`, and accepts only the embeddings-local policy. `embed_chunks`
  rejects duplicate `chunk_id` values before any provider call, returns an empty
  `EmbeddingResult` for empty input without calling the provider, prepends
  `search_document: ` without modifying chunk text, splits consecutive batches,
  preserves input order across batches, copies chunk provenance into each
  `ChunkEmbedding`, and aborts the whole run on the first failed batch.
  Service-layer validation raises `EmbeddingResponseError` with reasons
  `empty_embeddings`, `count_mismatch`, `dimension_mismatch`, and
  `non_finite_value`; provider response errors retain their reason code.
  Provider errors are normalized by explicit type, `EmbeddingError` passes
  through un-re-normalized, unexpected exceptions become
  `EmbeddingUnexpectedError` with the original cause, and `CancelledError` is
  not swallowed. Retries apply only to connection, timeout, rate-limit, and
  unavailable application errors; attempts are bounded to `1 + max_retries`;
  backoff is bounded exponential with injectable sleep and is separate from the
  per-attempt timeout; no overall deadline is introduced. Successful and failed
  calls report the aggregate `retry_count` defined in §8.7, including retries
  spent in earlier successful batches and excluding the terminal attempt.
  `EmbeddingRetryPolicy` is embeddings-local (approved D-3) with defaults
  `2 / 0.5 / 8.0 / 0.0` and mirrors the approved LLM validation and delay
  semantics without importing `app.llm`. `from_settings` reads only
  `embedding_*` values and does not call `get_settings()`. Settings are
  `embedding_batch_size` (16, `gt=0`), `embedding_timeout_seconds` (30.0,
  `gt=0`), `embedding_max_retries` (2, `ge=0`), `embedding_retry_base_delay`
  (0.5, `ge=0`), `embedding_retry_max_delay` (8.0, `ge=0`), and
  `embedding_retry_jitter` (0.0, `ge=0`), with `max_delay >= base_delay`
  enforced at settings construction
- Verification (2026-10-25; image `ai-customer-support-t269:local`, ID
  `sha256:858b6f2c2397e7fa02378555871090a1ef6bc6bc29b53d668a18fe5de37c3fa5`;
  no repository bind mount in image verification runs):
  - Build: `docker build -t ai-customer-support-t269:local .` → exit 0
  - Focused offline suite: `docker run --rm --network none
    ai-customer-support-t269:local python -m pytest tests/rag/embeddings -q` →
    300 passed, exit 0
  - Adjacent RAG suite: `pytest tests/rag/chunking tests/rag/ingestion
    tests/rag/embeddings` with `--network none` → 670 passed, 4 skipped, exit 0
  - Full regression: `docker run --rm --network ai-customer-support_default
    --add-host host.docker.internal:host-gateway --env-file .env
    ai-customer-support-t269:local python -m pytest tests -q` → 812 passed,
    4 skipped, exit 0. Networking was required for PostgreSQL and the live
    Ollama integration test; no repository bind mount was used
  - Static import scan: the service and retry modules import no `app.llm`,
    Qdrant, SQLAlchemy, psycopg, FastAPI endpoint, or persistence module; the
    test suite parses both modules with `ast` and asserts the approved boundary
  - No-write test: the service path completes with `builtins.open`,
    `Path.write_text`, and `Path.write_bytes` replaced by failing stubs
  - `git diff --check`: clean, exit 0; the implementation diff is limited to
    the six T269 files
- Outcome: T269 acceptance criteria in §11.3, §12, and §13 are met. The
  embedding boundary now has an ordered, validated, bounded-retry service and
  embeddings-local retry policy wired to additive settings. No next
  implementation task was started; T270 is the single next authorized task.

## Previously Completed Task — T268 (Ollama embedding adapter)
- Task: T268 — Ollama embedding adapter and offline HTTP-mock tests
- Commit: `b66d3c1d01efe758707e51af59d1a133f4451ac4`
  (`feat(rag): add ollama embedding adapter`); this project state record follows
  in a separate documentation commit
- Scope delivered: new `src/app/rag/embeddings/providers/ollama.py` with
  `OllamaEmbeddingProvider`, and
  `tests/rag/embeddings/test_ollama_provider.py`. No service, batching, retry,
  settings, composition-root, endpoint, persistence, metadata-client, or
  `app.llm` code was added
- Adapter contract implemented: explicit `base_url` supplied by the composition
  root (no environment read, approved D-6); pinned identity
  `ollama:nomic-embed-text:v1.5`; `POST {base_url}/api/embed` with exactly
  `model` and `input`; input array order preserved with no prefixing or
  truncation; per-attempt `timeout`; response `model` must be a string equal to
  the pinned tag; `embeddings` must be a JSON array whose vectors contain only
  JSON numbers; empty `embeddings` is structurally valid and returned for
  service-level handling; stable reasons `invalid_json`, `malformed_response`,
  and `missing_embeddings`; Ollama status mapping 429 → rate limit, 401/403 →
  authentication, 400/422 → invalid request, 404 → model not found, 5xx →
  unavailable, other → generic HTTP; connection, timeout, and other transport
  failures normalize to provider types. The adapter calls no `/api/tags` or
  `/api/show`, exposes no digest field, makes no digest-verification claim, and
  does not validate count, dimension, or finiteness (service invariants)
- Verification (2026-10-25; image `ai-customer-support-t268:local`, ID
  `sha256:258ccc131af4c87b4cd2a7714a57299f811a5fa39dfbb1c6dc7b4bf740c96ed0`;
  no repository bind mount in image verification runs):
  - Build: `docker build -t ai-customer-support-t268:local .` → exit 0
  - Focused offline suite: `docker run --rm --network none
    ai-customer-support-t268:local python -m pytest tests/rag/embeddings -q` →
    221 passed, exit 0
  - Adjacent RAG suite: `pytest tests/rag/chunking tests/rag/ingestion
    tests/rag/embeddings` → 591 passed, 4 skipped, exit 0
  - Full regression: `docker run --rm --network ai-customer-support_default
    --add-host host.docker.internal:host-gateway --env-file .env
    ai-customer-support-t268:local python -m pytest tests -q` → 733 passed,
    4 skipped, exit 0. Networking was required for PostgreSQL and the live
    Ollama integration test; no repository bind mount was used
  - Static import scan: the adapter imports only `json`, `typing`, `httpx`, and
    `app.rag.embeddings` modules; no `app.llm`, Qdrant, SQLAlchemy, psycopg,
    FastAPI, persistence, or metadata endpoint reference
  - `git diff --check`: clean, exit 0; the implementation diff is limited to
    the two T268 files
- Outcome: T268 acceptance criteria in §11.2 and §13 are met. The provider
  boundary now implements the approved `/api/embed` contract with offline
  `httpx.MockTransport` coverage and no metadata or digest behavior. No next
  implementation task was started; T269 is the single next authorized task.

## Previously Completed Task — T267 (embedding contracts)
- Task: T267 — Embedding contracts, identity, configuration, and error taxonomy
- Commit: `a22411eb4b41fc84884a890dcb528f1722893e09`
  (`feat(rag): add embedding contracts and error taxonomy`); this project state
  record follows in a separate documentation commit
- Scope delivered: new `src/app/rag/embeddings/` package with `contracts.py`,
  `exceptions.py`, `providers/base.py`, and `providers/exceptions.py`, plus
  `tests/rag/embeddings/test_contracts.py` and `test_errors.py`. No HTTP,
  service, retry, settings, persistence, Qdrant, database, endpoint, or
  composition-root code was added
- Contract implemented: frozen `EmbeddingConfig`, `ChunkEmbedding`, and
  `EmbeddingResult` with construction-path validation; `EmbeddingConfig`
  defaults and pinned constants for provider `ollama`, model
  `nomic-embed-text:v1.5`, provisional dimension `768`, prefixes
  `search_document: ` and `search_query: `, normalization `none`, and
  algorithm version `embeddings-v1`; deterministic lowercase SHA-256
  `config_id` over the canonical JSON payload with `sort_keys=True`,
  separators `(",", ":")`, `ensure_ascii=False`, and UTF-8; no served digest or
  operational setting is part of the identity; provider and application error
  taxonomies with `category`/`retryable`/`retry_count`; explicit
  provider-to-application mapping preserving response reason codes and
  `__cause__`
- Verification (2026-10-25; image `ai-customer-support-t267:local`, ID
  `sha256:922e1447fc11dc28d9206e18e426fb4fbfaf6056e4ed397d2eef5fa86edb38df`;
  no repository bind mount in image verification runs):
  - Focused offline suite: `docker run --rm --network none
    ai-customer-support-t267:local python -m pytest tests/rag/embeddings -q` →
    175 passed, exit 0
  - Adjacent RAG regression: `pytest tests/rag/chunking tests/rag/ingestion` →
    370 passed, 4 skipped, exit 0 (repository mounted for this iteration run)
  - Full regression: `docker run --rm --network ai-customer-support_default
    --add-host host.docker.internal:host-gateway --env-file .env
    ai-customer-support-t267:local python -m pytest tests -q` → 687 passed,
    4 skipped, exit 0. Networking was required for PostgreSQL and the live
    Ollama integration test; no repository bind mount was used
  - Alembic: `alembic upgrade head` in the image exited 0
  - Static import scan: no `httpx`, `app.llm`, SQLAlchemy, psycopg, FastAPI,
    Qdrant, or persistence import under the new embeddings package
  - `git diff --check`: clean, exit 0; the implementation diff is limited to
    the T267 file scope
- Outcome: T267 acceptance criteria in §11.1 and §13 are met. The embedding
  boundary now has immutable contracts, deterministic identity, pinned
  constants, and a complete tested error taxonomy. No next implementation task
  was started; T268 is the single next authorized task.

## Previously Completed Task — T266 (chunking composition-root wiring)
- Task: T266 — Chunking composition-root wiring
- Commit: 35e869b (`feat(rag): wire chunking composition root`); this project
  state record follows in a separate documentation commit
- Scope delivered: new `src/app/rag/chunking/composition.py` with
  `build_chunking_service(settings)`; `src/app/main.py` startup lifespan
  constructs the service and exposes it through `app.state.chunking_service`;
  canonical `app` import root across `src/`, `tests/`, and `migrations/`; the
  `Dockerfile` runtime entry point is now `uvicorn app.main:app`; new
  `tests/rag/chunking/test_composition.py`. No ingestion endpoint, new consumer,
  dependency-injection framework, runtime download, or environment-based
  tokenizer identity override was added
- Contract implemented: the factory constructs one
  `NomicEmbedTextTokenizer` from the pinned local asset and injects it into
  `ChunkingService.from_settings(settings, tokenizer)`. Chunk sizes come from
  `Settings`; the adapter supplies the pinned tokenizer identity. The service is
  constructed once per application process in the startup lifespan
- Image: `ai-customer-support-t266:local`, ID
  `sha256:45b21c159abee3122fb91a393dc58ae2f0ca7275b3ca313ab3d4393d0b494a26`
- Verification (2026-10-24; no repository bind mount in any image run):
  - Build: `docker build -t ai-customer-support-t266:local .` → exit 0
  - Packaged asset: `docker run --rm --network none
    ai-customer-support-t266:local sha256sum
    /app/assets/tokenizers/nomic-embed-text-v1.5/tokenizer.json` →
    `d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66`, exit
    0
  - Composition factory in the image with `--network none`: the reported
    identity equals the approved identity, and a real `KnowledgeDocument`
    chunked into 1 chunk / 20 tokens, exit 0
  - Focused offline suite: `docker run --rm --network none
    ai-customer-support-t266:local python -m pytest tests/rag/chunking -q` →
    270 passed, exit 0
  - Full regression: `docker run --rm --network ai-customer-support_default
    --add-host host.docker.internal:host-gateway --env-file .env
    ai-customer-support-t266:local python -m pytest tests -q` → 512 passed,
    4 skipped, exit 0. Networking was required for PostgreSQL and the live
    Ollama integration test; no repository bind mount was used
  - Runtime entry point: `uvicorn app.main:app` started from the image with
    `--network none --env-file .env`; application startup completed, `GET
    /health` returned `{"status":"ok"}` with HTTP 200, and shutdown was clean
  - Alembic after import-root standardization: `docker run --rm --network
    ai-customer-support_default --env-file .env ai-customer-support-t266:local
    alembic upgrade head` → exit 0
  - `git diff --check`: clean, exit 0; the implementation diff is limited to
    T266 scope
- Outcome: T266 acceptance criteria in §15 and §20.2 are met. The production
  chunking path constructs and uses the approved adapter, and `app.state`
  exposes the composed service. Chunking is production-ready. No next
  implementation task is approved; the next SDD step is the Phase 4 embeddings
  specification gate, which has not started

## Previously Completed Task — T265 (Docker tokenizer asset packaging)
- Task: T265 — Docker tokenizer asset packaging
- Commit: d126cb7 (`feat(docker): package pinned tokenizer asset`)
- Scope delivered: `Dockerfile` explicitly copies the pinned
  `assets/tokenizers/nomic-embed-text-v1.5/tokenizer.json` to
  `/app/assets/tokenizers/nomic-embed-text-v1.5/tokenizer.json`. It also copies
  `.env.example` as a test fixture required by
  `tests/rag/chunking/test_service.py` when the focused suite runs inside the
  image. No adapter, application, test, migration, or specification code
  changed
- Image: `ai-customer-support-t265:local`, ID
  `sha256:5ec4597909346ad1382cdcb5afcba496b1cd69368f8a9ff7d28282ad822ee0ee`
- Verification (2026-10-24; no repository bind mount in any image run):
  - Build exit 0; packaged asset SHA-256
    `d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66` at the
    adapter path; `default_repo_root()` reported `/app`
  - The adapter reported the approved identity, and the fixed sample
    `"Refunds are processed within 5-7 business days."` produced 11 token spans
    that partition the source
  - Focused offline suite: 265 passed, exit 0
  - Full regression: 507 passed, 4 skipped, exit 0
  - `git diff --check`: clean, exit 0
- Outcome: T265 acceptance criteria in §15 were met, and T266 is now complete

## Previously Completed Task — T264 (final integration verification and closure)
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
  found and no implementation code was changed. T265 was the sole next task at
  that time

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
- No implementation task is in progress. T270 is complete; T271 is authorized
  but has not started.
- T270 — Live Ollama conformance, dimension verification, regression, and
  closure — is complete and committed at
  `95eb8ed1a1a29c5701dcb849c90c353673f2ba70`.
- Current activity: T270 implementation, live verification, and closure on
  2026-10-25. This documentation record is the only remaining change for the
  task.
- Status: T270 complete; the Phase 4 embeddings specification at
  `specs/rag/knowledge-document-embeddings.md` remains the source of truth.
- Decisions D-1 through D-6 remain approved as recorded in the specification's
  §2.3 and §2.4.
- Approved implementation sequence: T267–T271 in the specification's §13. Each
  task requires its own authorized session; multiple tasks must not be combined.
- Exactly one next authorized task: T271 — Composition-root wiring and Docker
  image verification. It has not started and must be executed in a separate
  session.
- Verification for T270: live conformance 3 passed; focused offline embeddings
  suite 300 passed / 3 skipped; full regression 812 passed / 7 skipped; the
  observed dimension is 768 and matches the provisional value; `git diff
  --cached --check` clean. No application source outside the approved T270
  scope changed.
- Do not begin T271 in this session.

## Task Ordering
1. T271 — Composition-root wiring and Docker image verification (authorized;
   not started; separate session).

Each task requires its own authorized session.

## Verified Findings
- T270 live conformance (2026-10-25):
  `tests/rag/embeddings/test_ollama_conformance.py` adds three opt-in live
  tests gated by `RUN_LIVE_OLLAMA=1`; the default and offline focused suites
  skip them. The metadata test records the `GET /api/tags` entry for
  `nomic-embed-text:v1.5`; the raw response test records the `POST /api/embed`
  response model and measured dimension; the adapter test exercises
  `OllamaEmbeddingProvider` against the live model. Observed evidence: model
  name `nomic-embed-text:v1.5`; digest
  `0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f`
  (verbatim, evidence only, not runtime verification); response model equal to
  the pinned tag; dimension `768` (three vectors, 2,304 values) with all values
  finite; reported details include `family=nomic-bert`, `parameter_size=137M`,
  `quantization_level=F16`, `context_length=2048`, and
  `embedding_length=768`. The observed dimension equals
  `PROVISIONAL_EMBEDDING_DIMENSION`; the value is confirmed by live measurement
  and no specification amendment is required. Live conformance: 3 passed;
  focused offline embeddings suite: 300 passed / 3 skipped; full regression:
  812 passed / 7 skipped; `git diff --cached --check` clean.
- T269 implementation (2026-10-25):
  `src/app/rag/embeddings/service.py` defines
  `EmbeddingService(provider, config=None, batch_size=16, timeout=30.0,
  retry_policy=None, sleep=None)`. Construction builds one effective
  `EmbeddingConfig`, validates `provider.identity` against
  `f"{config.provider}:{config.model}"` (`EmbeddingConfigurationError` on
  mismatch or non-string identity), rejects non-positive `batch_size` and
  `timeout`, and accepts only `EmbeddingRetryPolicy`.
  `embed_chunks` returns an empty `EmbeddingResult` with `retry_count == 0` for
  empty input without calling the provider, rejects duplicate `chunk_id` values
  with `ValueError("duplicate chunk_id")` before any call, prepends
  `search_document: ` exactly, splits consecutive batches of at most
  `batch_size`, preserves input order across batches, copies all chunk
  provenance, and aborts the whole run on any failed batch. Service validation
  raises `EmbeddingResponseError` with `empty_embeddings`, `count_mismatch`,
  `dimension_mismatch`, or `non_finite_value`; provider response reasons are
  preserved through normalization; invalid vector element types are rejected as
  `malformed_response` without leaking a raw `TypeError`. Provider errors
  normalize by explicit type, already-normalized `EmbeddingError` values pass
  through, unexpected exceptions become `EmbeddingUnexpectedError` with
  `__cause__`, and `CancelledError` is not swallowed. Retries are per batch,
  bounded to `1 + max_retries`, use bounded exponential backoff with injectable
  sleep, pass the configured timeout to every attempt, and do not introduce an
  overall deadline. Aggregate `retry_count` includes retries from earlier
  successful batches, excludes the terminal attempt, and is attached to
  successful results and terminal application errors, including validation
  failures after earlier retries. `src/app/rag/embeddings/retry.py` defines the
  approved embeddings-local `EmbeddingRetryPolicy` with defaults
  `2 / 0.5 / 8.0 / 0.0`, mirrored validation and delay semantics, and
  `from_settings` over `embedding_*` values; neither module imports `app.llm`.
  Additive settings are `embedding_batch_size` (16, `gt=0`),
  `embedding_timeout_seconds` (30.0, `gt=0`), `embedding_max_retries`
  (2, `ge=0`), `embedding_retry_base_delay` (0.5, `ge=0`),
  `embedding_retry_max_delay` (8.0, `ge=0`), and `embedding_retry_jitter`
  (0.0, `ge=0`), with `max_delay >= base_delay` enforced at construction;
  `.env.example` documents all six. Focused offline embeddings suite: 300
  passed; adjacent RAG suite: 670 passed / 4 skipped; full regression: 812
  passed / 4 skipped; static import scan and no-write test clean; `git diff
  --check` clean.
- T268 implementation (2026-10-25):
  `src/app/rag/embeddings/providers/ollama.py` defines
  `OllamaEmbeddingProvider(base_url, transport=None)`. The base URL is explicit
  and no environment variable is read (approved D-6). The adapter reports the
  pinned identity `ollama:nomic-embed-text:v1.5`, posts exactly
  `{"model": "nomic-embed-text:v1.5", "input": [...]}` to
  `POST {base_url}/api/embed`, preserves input order without adding or removing
  prefixes, and applies the per-attempt `timeout` to every HTTP timeout
  component. It requires the response `model` to be a string equal to the
  pinned tag; treats a missing `embeddings` key as reason `missing_embeddings`,
  a non-array envelope or invalid vector element as `malformed_response`, and
  invalid JSON as `invalid_json`; accepts an empty `embeddings` array as
  structurally valid; and returns tuple-of-tuple vectors of floats. Count,
  dimension, and finiteness are deliberately not validated by the adapter
  (service invariants). HTTP status mapping is Ollama-local: 429 rate limit;
  401/403 authentication; 400/422 invalid request; 404 model not found; 5xx
  unavailable; other statuses generic. Connection, timeout, and other transport
  failures normalize to provider types, and no raw `httpx` exception escapes.
  No model metadata endpoint is called, no digest field exists, and no digest
  verification is claimed. Focused offline embeddings suite with
  `--network none`: 221 passed; adjacent RAG suite: 591 passed / 4 skipped;
  full regression: 733 passed / 4 skipped; static import scan found no
  `app.llm`, Qdrant, SQLAlchemy, psycopg, FastAPI, persistence, or metadata
  import; `git diff --check` clean.
- T267 implementation (2026-10-25): `src/app/rag/embeddings/contracts.py`
  provides frozen `EmbeddingConfig`, `ChunkEmbedding`, and `EmbeddingResult`
  with validation on direct construction; pinned constants are provider
  `ollama`, model `nomic-embed-text:v1.5`, provisional dimension `768`,
  document prefix `search_document: `, query prefix `search_query: `,
  normalization `none`, and algorithm version `embeddings-v1`.
  `EmbeddingConfig.config_id` is the lowercase SHA-256 of the exact canonical
  JSON payload in §5.4 and excludes the served digest and all operational
  settings. `ChunkEmbedding` stores provenance and an immutable float vector
  without chunk text; `EmbeddingResult` preserves input order, validates unique
  chunk IDs, matching configuration IDs, vector length, and finite values, and
  exposes a read-only `by_chunk_id` mapping. The provider and application error
  taxonomies expose every approved type; `normalize_provider_error` maps by
  explicit provider type, preserves response reason codes and `__cause__`, and
  keeps messages free of chunk text and vectors. Focused offline embeddings
  suite: 175 passed; adjacent RAG suite: 370 passed / 4 skipped; full
  regression: 687 passed / 4 skipped; Alembic upgrade head exit 0;
  `git diff --check` clean.
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
- T265 verification (2026-10-24): `Dockerfile` now copies the pinned asset to
  `/app/assets/tokenizers/nomic-embed-text-v1.5/tokenizer.json` and
  `.env.example` for the in-image test fixture. The image
  `ai-customer-support-t265:local` built successfully (exit 0). With no bind
  mount and `--network none`, the packaged asset hash is
  `d241a60d…e5c66`, `default_repo_root()` is `/app`, the adapter reports the
  approved identity, the fixed sample tokenizes into 11 partitioning spans, and
  the focused chunking suite passes (265 passed, exit 0). The full regression
  suite from the image passes with networking for PostgreSQL and live Ollama
  (507 passed, 4 skipped, exit 0). `git diff --check` was clean (exit 0). No
  adapter, application, test, or migration code changed.
- T266 verification (2026-10-24): `src/app/rag/chunking/composition.py` builds
  one `NomicEmbedTextTokenizer` from the pinned asset and injects it into
  `ChunkingService.from_settings`; the `src/app/main.py` lifespan exposes the
  service through `app.state.chunking_service`. Imports across `src/`, `tests/`,
  and `migrations/` now use the canonical `app` root, and the `Dockerfile` CMD is
  `uvicorn app.main:app`. The new integration suite covers the approved identity,
  settings-derived maximum and overlap, end-to-end `KnowledgeDocument` chunking
  with exact source slices and recomputed chunk IDs, network-free factory use,
  startup exposure with one instance per process, and a source scan rejecting
  `src.app.*` imports. The image `ai-customer-support-t266:local`
  (`sha256:45b21c159abee3122fb91a393dc58ae2f0ca7275b3ca313ab3d4393d0b494a26`)
  contains the approved asset hash and identity. Without a repository bind
  mount: focused offline suite 270 passed (exit 0); full regression 512 passed,
  4 skipped (exit 0); `uvicorn app.main:app` served `/health` with HTTP 200 and
  shut down cleanly under `--network none`; `alembic upgrade head` exited 0; and
  `git diff --check` was clean (exit 0).
- Latest full test run: 812 passed, 7 skipped (2026-10-25, `pytest tests` from
  `ai-customer-support-t270:local` with PostgreSQL running and network access
  for the live Ollama integration test; the skips are the 4 unchanged
  environment-conditional ingestion permission fixtures plus the 3 opt-in live
  embedding conformance tests).
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
  verification-only, and T265 packaged the asset in the image. The embedding
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
- Phase 4 RAG: ingestion (T255–T259), chunking (T260–T266), embedding contracts
  (T267), the Ollama embedding adapter (T268), and the embedding service with
  batching, validation, retries, and settings (T269) are complete. The asset is
  vendored, the dependency pin is present, and input-length compatibility is
  recorded as `506 <= 2048`. T264 closed verification-only, T265 packaged and
  verified the asset in the image, and T266 production-wired the chunking
  composition root with no repository bind mount. The embeddings sequence
  T267–T271 is approved; T267–T269 are complete and T270 is the single next
  authorized task.
- Embeddings specification: `specs/rag/knowledge-document-embeddings.md` is
  approved at Revision 2 (2026-10-24). Decisions D-1 through D-6 are resolved
  as recorded in the specification's §2.3 and §2.4. `768` remains the
  provisional expected dimension until T270 measures the live model; the served
  model digest is recorded only as T270 evidence and is not verified at runtime
  in V1; and D-6 preserves the existing `OLLAMA_URL`/`OLLAMA_BASE_URL`
  inconsistency without changing LLM behavior. The provisional dimension must
  not be described as confirmed before T270 evidence.
- Embeddings retry-count contract (specification §8.7, approved): successful
  calls report total additional attempts; failures report retries performed
  before the terminal failure, including earlier successful batches. This
  extension of the LLM convention was approved with Revision 2.
- Chunking defaults of 500 tokens and 75 tokens of overlap are confirmed for
  the approved model: `500 + 4 prefix + 2 special = 506 <= 2048`.
- T265 — Docker tokenizer asset packaging — is complete and committed at
  d126cb7. The image contains the pinned asset at the adapter path, and asset
  hash, identity, fixed sample, focused offline suite, and full regression were
  verified without a repository bind mount.
- T266 — Chunking composition-root wiring — is complete and committed at
  35e869b. The canonical `app` import root is used throughout, `uvicorn
  app.main:app` is the runtime entry point, and the composed service is exposed
  through `app.state`.
- Remaining Phase 4 specifications (Qdrant, semantic retrieval, metadata
  filtering, context construction, source attribution, evaluation, and failure
  handling) are undefined and follow their own SDD cycles. Embedding
  implementation is authorized only as the approved sequence T267–T271, one
  task per session; T267–T269 are complete and T270 is next.
- Retry concrete defaults (chosen in T253) may be revisited during future
  hardening; not a Phase 3 blocker.

## Rules
- Specifications are the source of truth.
- Never start RAG before Phase 3 closure.
- Implement only one task per session.
- Do not repeat completed audits unless evidence is stale
  or a specific change requires re-verification.
- Update this file at every verified task closure.
