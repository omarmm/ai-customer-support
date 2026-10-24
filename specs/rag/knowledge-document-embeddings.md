# Knowledge Document Embeddings Specification

**Status:** Draft — Pending Review and Explicit Approval
**Feature:** Knowledge document embeddings
**Phase:** Phase 4 — RAG
**Depends on:** T266 closure; `specs/rag/embedding-tokenizer-decision.md`; `specs/rag/knowledge-document-chunking.md`
**Authorizes implementation:** No

This document defines the Embeddings subsystem. It is a draft for review and
does not authorize implementation. T267–T271 in §13 are proposed and remain
unapproved until this specification and its task breakdown are explicitly
approved in a separate review.

## 1. Purpose

Define a deterministic, testable boundary for generating one embedding vector
for each chunk produced by the existing chunking subsystem, using the approved
Ollama embedding model.

The subsystem must:

- Accept chunks from the chunking layer without re-chunking them.
- Generate one vector per chunk through Ollama's `POST /api/embed` endpoint.
- Preserve chunk identity, order, and provenance.
- Validate provider responses before returning any result.
- Normalize provider failures into a stable application error contract.
- Apply bounded retries and per-attempt timeouts.
- Remain independent of Qdrant, persistence, retrieval, and application
  endpoints.

## 2. Status and Approval Gate

### 2.1 Approved existing decisions

The following decisions are already approved and are inputs to this draft:

| Decision | Source |
| --- | --- |
| Embedding provider is Ollama. | `specs/rag/embedding-tokenizer-decision.md` |
| Serving model is `nomic-embed-text:v1.5`. | `specs/rag/embedding-tokenizer-decision.md` |
| The tokenizer/model repository is pinned at revision `e9b6763023c676ca8431644204f50c2b100d9aab` for chunking. | `specs/rag/embedding-tokenizer-decision.md` |
| Chunks are exact source slices with deterministic `chunk_id`, offsets, ordering, and `chunking_config_id`. | `specs/rag/knowledge-document-chunking.md` |
| The input limit is conservatively 2048 tokens; `500` chunk tokens plus `4` prefix tokens and `2` special tokens totals `506`, verified in T263. | Chunking specification §5.7 and §9; embedding/tokenizer decision §3 |
| Error handling separates provider errors from application errors and uses bounded retries with per-attempt timeouts. | `specs/llm/error-handling.md` |
| Application components obtain configuration through centralized settings. | `specs/system/configuration.md` |

### 2.2 Proposed decisions in this draft

These decisions are proposed by this draft and are not approved until the
specification is approved:

| Decision | Proposal |
| --- | --- |
| Provider endpoint | `POST {OLLAMA_URL}/api/embed` with batched `input`. |
| Document prefix | `search_document: `, prepended to every chunk before embedding. |
| Query prefix | `search_query: `, reserved for the future retrieval specification and not used in V1. |
| Model identity pinning | Provider, model tag, prefixes, normalization policy, and algorithm version are pinned in code. No environment variable selects them. |
| Expected dimension | `768`, explicitly provisional until T270 verifies the actual served model. |
| Batch size | Configurable, default `16`. |
| Request timeout | Configurable per attempt, default `30` seconds. |
| Retry policy | Reuse the approved bounded-retry semantics and concrete defaults of `app.llm.retry.RetryPolicy`, with embedding-specific settings. |
| Vector normalization | V1 preserves provider-returned values unchanged. No L2 normalization is added. |
| Result ordering | Preserve input chunk order exactly. |
| Duplicate handling | Reject duplicate `chunk_id` values before any provider call. |
| Failure handling | Any failed batch invalidates the overall result; no partial success is returned. |
| Persistence | None. The subsystem returns in-memory results only. |

### 2.3 Unresolved decisions requiring evidence or approval

| Decision | Why unresolved | Required evidence or action |
| --- | --- | --- |
| Actual embedding dimension | `768` is provisional; this draft must not claim it is verified. | T270 must call the live model and record the observed dimension. If it is not `768`, stop and amend this specification and the pinned constant before closure. |
| Served model digest and Ollama runtime version | The approved decision names the serving tag, not a verified serving digest. Re-pulling or re-quantizing a tag can change vectors. | T270 must record the served model name and digest from Ollama metadata (`/api/tags` or `/api/show`) and the observed dimension. Whether to add a digest to the configuration identity is an approval decision. |
| Retry implementation location | The approved LLM retry policy is generic, but importing `app.llm.retry` from the RAG subsystem may be an undesirable dependency direction. | Implementation review must either reuse `RetryPolicy` or implement an embeddings-local policy with identical validation and behavior. The semantics and defaults are not unresolved. |
| Live conformance test gating | Offline unit tests must not require Ollama. | T270 must define and record the opt-in live test mechanism. A marker such as `RUN_LIVE_OLLAMA=1` is proposed, not approved. |

## 3. Scope

### 3.1 In scope

- Generate one embedding vector for each `Chunk` supplied by the existing
  chunking subsystem.
- Ollama integration through `POST /api/embed`.
- Provider contract, configuration identity, batching, response validation, and
  error handling.
- Injectable service design and dependency boundaries.
- Offline unit testing and live-model conformance verification.
- Additive centralized settings for operational values only.

### 3.2 Out of scope

- Qdrant collections, persistence, storage schemas, payloads, aliases, and
  manifests.
- Retrieval, filtering, reranking, context assembly, and source attribution.
- Re-embedding orchestration, index rebuilding, and re-ingestion.
- New HTTP endpoints, CLI wiring, agent integration, and database schema
  changes.
- Changes to ingestion, chunking, tokenizer behavior, or chunk defaults.
- OpenAI embeddings or any provider other than the approved Ollama model.
- Vector normalization, similarity-metric selection, and distance functions.
- Logging full source text or full vectors.

## 4. Provider and Model Contract

### 4.1 Provider and model

- Provider: Ollama.
- Serving model: `nomic-embed-text:v1.5`.
- Endpoint: `POST {OLLAMA_URL}/api/embed`.
- The model tag is pinned in code. It must not be selected or overridden by an
  environment variable in V1.
- No other provider or model is supported by this specification.

### 4.2 Request contract

The adapter sends a JSON object with exactly the fields required for this
subsystem:

```json
{
  "model": "nomic-embed-text:v1.5",
  "input": [
    "search_document: first chunk text",
    "search_document: second chunk text"
  ]
}
```

Requirements:

- `input` is always a JSON array, including when the batch contains one text.
- Input order is the batch order supplied by the service.
- The service supplies already-prefixed texts; the adapter does not add or
  remove prefixes.
- V1 sends no `options`, `truncate`, `keep_alive`, or other optional parameters.
- Input size is bounded by the chunking contract. This subsystem does not
  re-tokenize, truncate, or pad.

### 4.3 Response contract

A successful response is HTTP 200 with a JSON object containing at least:

```json
{
  "model": "nomic-embed-text:v1.5",
  "embeddings": [
    [0.1, -0.2, 0.3],
    [0.4, 0.5, -0.6]
  ]
}
```

Requirements:

- `model` must be a string and must equal the pinned model tag. A missing,
  non-string, or different `model` value is a model identity mismatch.
- `embeddings` must be an array with exactly one vector per input text, in input
  order.
- Each vector must be an array of JSON numbers.
- The number of vectors must equal the number of input texts.
- The length of every vector must equal the verified expected dimension.
- Every value must be finite. Booleans, strings, nulls, nested arrays, NaN, and
  infinity are invalid.
- Timing fields such as `total_duration`, `load_duration`, and
  `prompt_eval_count` are ignored by this subsystem.

### 4.4 Model identity validation

- The request always uses the pinned model tag.
- The adapter validates the response `model` field against the pinned tag.
- The service also validates that the injected provider's `identity` matches
  the pinned provider/model identity in `EmbeddingConfig`.
- A response `model` mismatch raises a permanent `EmbeddingModelMismatchError`.
  It is never retried.
- A provider-wiring identity mismatch raises a permanent
  `EmbeddingConfigurationError`. It is never retried.
- The running model must not be silently accepted when its reported identity
  differs from the approved tag.

### 4.5 Dimension status

The expected dimension is **proposed as `768` and is not verified by this
draft**. It is provisional until T270 measures the live model.

- Until T270, no document may claim that `768` is confirmed.
- T270 records the observed dimension and the method used to obtain it.
- If the observed dimension differs from `768`, implementation must stop and the
  specification, the pinned constant, and any affected identity must be amended
  before conformance can pass.
- A response whose vectors do not match the effective expected dimension raises
  `EmbeddingResponseError` with reason `dimension_mismatch`; it does not trigger
  a retry.

## 5. Prefixes and Configuration Identity

### 5.1 Prefixes

- Document prefix: `search_document: ` exactly, including the trailing space.
- Query prefix: `search_query: ` exactly, including the trailing space.
- The service prepends the document prefix to `chunk.content` without trimming,
  reflowing, or otherwise modifying the chunk text.
- Query embedding is not implemented in V1. The query prefix is defined now so
  the configuration identity remains stable for the future retrieval
  specification.
- Prefixes affect vector representation and are part of the configuration
  identity.

### 5.2 `EmbeddingConfig`

```python
@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str = "ollama"
    model: str = "nomic-embed-text:v1.5"
    dimension: int = 768             # provisional; verified in T270
    document_prefix: str = "search_document: "
    query_prefix: str = "search_query: "
    normalization: str = "none"      # V1: preserve provider values unchanged
    algorithm_version: str = "embeddings-v1"
```

Validation:

- `provider`, `model`, `document_prefix`, `query_prefix`, `normalization`, and
  `algorithm_version` must be non-empty strings.
- `dimension > 0`.
- V1 requires `normalization == "none"`. Any other value is invalid; adding a
  transformation requires a new algorithm version and a specification change.
- Invalid values raise `ValueError`.

The fields above are pinned defaults. The composition root must use the pinned
constants. Tests may construct explicit values to verify validation and
identity behavior, but production wiring must not expose those fields as
arbitrary environment overrides.

### 5.3 Algorithm version

`EMBEDDINGS_ALGORITHM_VERSION = "embeddings-v1"`.

Any change to prefixing, input ordering, batching semantics that affects
vector-to-chunk mapping, response validation, normalization, or the provider
request/response contract requires a new algorithm version. Batch size, timeout,
retry settings, and base URL do not require a new version because they do not
change vector values or identity.

### 5.4 Configuration ID

`EmbeddingConfig.config_id` is a deterministic lowercase hexadecimal SHA-256:

```python
payload = {
    "algorithm_version": config.algorithm_version,
    "dimension": config.dimension,
    "document_prefix": config.document_prefix,
    "model": config.model,
    "normalization": config.normalization,
    "provider": config.provider,
    "query_prefix": config.query_prefix,
}

config_id = sha256(
    json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
).hexdigest()
```

Rules:

- No timestamps, random values, hostnames, paths, process state, or deployment
  identifiers.
- Includes every field that affects vector representation.
- Excludes batch size, timeout, retry policy, base URL, Qdrant settings,
  database settings, logging settings, and retrieval settings.
- A change to any included field produces a different configuration ID.
- Identical inputs and identical configuration produce an identical
  configuration ID across processes and hosts.

## 6. Service Contracts

The proposed package is `src/app/rag/embeddings/`, with provider contracts
under `src/app/rag/embeddings/providers/`.

### 6.1 `EmbeddingProvider` protocol

```python
class EmbeddingProvider(Protocol):
    @property
    def identity(self) -> str:
        """Return the pinned provider/model identity, e.g. 'ollama:nomic-embed-text:v1.5'."""

    async def embed(
        self,
        texts: Sequence[str],
        *,
        timeout: float,
    ) -> tuple[tuple[float, ...], ...]:
        """Return one vector per input text, in input order."""
```

Responsibilities:

- Accept already-prefixed texts in input order.
- Enforce the per-attempt HTTP timeout.
- Validate the HTTP response envelope, JSON, `model`, and `embeddings` presence.
- Raise only provider-layer exceptions defined in §8.2.
- Perform no persistence and return no partial success.

The service validates vector count, dimension, and finite values after the
provider returns. Provider-layer parsing errors are normalized by the service.

### 6.2 `ChunkEmbedding`

A frozen dataclass representing the embedding of one chunk:

| Field | Meaning |
| --- | --- |
| `chunk_id` | The deterministic chunk ID from the chunking specification |
| `document_id` | Source document content-version ID |
| `source_path` | Relative POSIX source path |
| `chunk_index` | 0-based contiguous chunk index within the document |
| `start_offset` | Inclusive Unicode code-point offset in the source document |
| `end_offset` | Exclusive Unicode code-point offset in the source document |
| `chunking_config_id` | Effective chunking configuration identity |
| `embedding_config_id` | Effective embedding configuration identity |
| `vector` | Immutable tuple of finite floats |

Validation on every construction path:

- `chunk_id`, `document_id`, `source_path`, `chunking_config_id`, and
  `embedding_config_id` are non-empty strings.
- `chunk_index >= 0`.
- `0 <= start_offset < end_offset`.
- `vector` is a non-empty tuple of floats.
- Every vector value is finite.
- Document content, titles, and full vectors must not appear in error messages.

`ChunkEmbedding` does not store chunk text. The caller retains the `Chunk` and
can join by `chunk_id` when needed.

### 6.3 `EmbeddingResult`

A frozen dataclass representing one successful service run:

| Field | Meaning |
| --- | --- |
| `config` | The effective `EmbeddingConfig` |
| `embeddings` | Immutable tuple of `ChunkEmbedding`, in input order |
| `retry_count` | Total retries performed across all batches; default `0` |

Derived read-only properties:

- `count == len(embeddings)`
- `by_chunk_id` returns a read-only mapping from `chunk_id` to `ChunkEmbedding`

Validation on every construction path:

- `config` is an `EmbeddingConfig`.
- `embeddings` preserve the supplied order; the result does not sort them.
- `chunk_id` values are unique.
- Every `embedding_config_id == config.config_id`.
- Every vector length equals `config.dimension`.
- Every vector value is finite.
- `retry_count >= 0`.
- `ValueError` is raised for violations.

### 6.4 `EmbeddingService`

```python
class EmbeddingService:
    def __init__(
        self,
        provider: EmbeddingProvider,
        config: EmbeddingConfig | None = None,
        batch_size: int = 16,
        timeout: float = 30.0,
        retry_policy: EmbeddingRetryPolicy | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ): ...

    @classmethod
    def from_settings(cls, settings, provider: EmbeddingProvider) -> "EmbeddingService": ...

    @property
    def config(self) -> EmbeddingConfig: ...

    async def embed_chunks(self, chunks: Iterable[Chunk]) -> EmbeddingResult: ...
```

Responsibilities and guarantees:

- Construct one effective `EmbeddingConfig` per service.
- Validate that `provider.identity` matches
  `f"{config.provider}:{config.model}"`; mismatch raises
  `EmbeddingConfigurationError`.
- Validate `batch_size > 0`, `timeout > 0`, and a valid retry policy at
  construction.
- Do not call `get_settings()` eagerly.
- Accept no per-request configuration overrides in V1.
- Prepend the document prefix to each chunk's content.
- Batch inputs in consecutive groups of `batch_size`.
- Preserve input order across batches and within each batch.
- Return deterministic mapping from `chunk_id` to embedding.
- Reject duplicate `chunk_id` values before any provider call with `ValueError`.
- Return an empty result for empty input without calling the provider.
- Abort the whole run on any failed batch; never return partial results.
- Perform no persistence, file writes, Qdrant access, or database access.
- Import no Qdrant, SQLAlchemy, psycopg, HTTP framework, or agent modules.

### 6.5 Ordering and provenance

- The output `embeddings` tuple follows the exact order of the input chunks.
- No sorting or reordering is performed by the service or result.
- When the caller supplies `ChunkingResult.chunks`, that order is already
  deterministic under the chunking specification.
- Each `ChunkEmbedding` copies `chunk_id`, `document_id`, `source_path`,
  `chunk_index`, offsets, and `chunking_config_id` from its input `Chunk`.
- The result does not fabricate chunk identity or metadata.

## 7. Batching, Validation, and Failure Behavior

### 7.1 Batching

- Effective batch size is a positive integer setting, default `16`.
- Inputs are divided into consecutive batches of at most `batch_size` chunks.
- A final smaller batch is allowed.
- Batch boundaries must not reorder chunks.
- Empty input produces no batches and no provider calls.

### 7.2 Duplicate and empty input

- Duplicate `chunk_id` values are detected across the complete input before any
  provider call. The service raises `ValueError("duplicate chunk_id")` without
  exposing chunk text.
- Empty input returns `EmbeddingResult(config=config, embeddings=())` with
  `retry_count=0` and no provider call.

### 7.3 Response validation

For every batch, the service validates:

1. The provider returned a sequence of vectors.
2. The number of vectors equals the number of texts in the batch.
3. Every vector length equals `config.dimension`.
4. Every value is a finite integer or float; booleans are invalid.
5. The vectors are convertible to an immutable tuple of floats without
   normalization, rounding, scaling, or clipping.

A violation raises `EmbeddingResponseError` with a stable reason code:

| Reason | Meaning |
| --- | --- |
| `invalid_json` | Provider response is not valid JSON. |
| `malformed_response` | Response envelope is missing required structure. |
| `missing_embeddings` | `embeddings` field is absent. |
| `empty_embeddings` | Non-empty input produced zero vectors. |
| `count_mismatch` | Vector count differs from input count. |
| `dimension_mismatch` | A vector length differs from the expected dimension. |
| `non_finite_value` | A vector contains NaN, infinity, or a non-numeric value. |

`invalid_json` and `malformed_response` are normally raised by the provider
adapter and normalized to `EmbeddingResponseError` by the service. Count,
dimension, and finite checks are performed by the service.

### 7.4 Failure semantics

- Any failed batch invalidates the overall result.
- The service raises the normalized application error; it does not return
  successful batches alone.
- No retry is attempted for response validation failures, model mismatch,
  configuration errors, or unexpected internal errors.
- Retryable provider failures may be retried per §8.5.
- If retries are exhausted, the final normalized error is raised.

## 8. Errors and Retries

### 8.1 Two-layer error model

Mirroring the approved LLM error model:

- Provider-layer errors live under
  `src/app/rag/embeddings/providers/exceptions.py`.
- Application-layer errors live under
  `src/app/rag/embeddings/exceptions.py`.
- Provider exceptions, raw HTTP exceptions, and HTTP-library exceptions must
  never escape the service boundary.
- Normalization occurs at the `EmbeddingService` boundary by explicit provider
  exception type, not by re-interpreting raw status codes.

### 8.2 Provider error taxonomy

| Exception | Meaning |
| --- | --- |
| `EmbeddingProviderError` | Base class for provider failures. |
| `EmbeddingProviderConnectionError` | Provider could not be reached. |
| `EmbeddingProviderTimeoutError` | An attempt exceeded its timeout. |
| `EmbeddingProviderHTTPError` | Provider returned an HTTP error; carries `status_code`. |
| `EmbeddingProviderRateLimitError` | Provider throttled the request. |
| `EmbeddingProviderAuthenticationError` | Provider rejected credentials. |
| `EmbeddingProviderInvalidRequestError` | Provider rejected the request as invalid. |
| `EmbeddingProviderModelNotFoundError` | Provider explicitly reported the model as unknown. |
| `EmbeddingProviderUnavailableError` | Provider reported a transient server-side fault. |
| `EmbeddingProviderResponseError` | Response is invalid JSON or malformed; carries a reason code. |
| `EmbeddingProviderModelMismatchError` | Response `model` is missing, invalid, or differs from the pinned tag. |

Ollama-specific status interpretation belongs to the adapter. The proposed
mapping is: 429 → rate limit; 401/403 → authentication; 400/422 → invalid
request; 404 for `/api/embed` → model not found; 5xx → unavailable; other HTTP
errors → generic provider HTTP error. These are provider-specific and are not
universal status-code rules.

### 8.3 Application error taxonomy

| Exception | Retryable | Meaning |
| --- | --- | --- |
| `EmbeddingError` | No | Base class; used for unclassified provider failures. |
| `EmbeddingConnectionError` | Yes | Provider could not be reached. |
| `EmbeddingTimeoutError` | Yes | An attempt exceeded its timeout. |
| `EmbeddingRateLimitError` | Yes | Provider throttled the request. |
| `EmbeddingUnavailableError` | Yes | Provider reported a transient server-side fault. |
| `EmbeddingAuthenticationError` | No | Credentials are missing or rejected. |
| `EmbeddingInvalidRequestError` | No | Request is malformed or rejected. |
| `EmbeddingModelNotFoundError` | No | Provider explicitly reported an unknown model. |
| `EmbeddingModelMismatchError` | No | Served model identity differs from the approved identity. |
| `EmbeddingResponseError` | No | Response is invalid; carries a stable reason code. |
| `EmbeddingConfigurationError` | No | Provider/model wiring or configuration is invalid. |
| `EmbeddingUnexpectedError` | No | Unexpected internal exception; preserves the cause. |

Normalization rules:

- Known provider exceptions map deterministically to the corresponding
  application error type.
- Unclassified provider failures map to the generic non-retryable
  `EmbeddingError`.
- Unexpected/programming exceptions map to `EmbeddingUnexpectedError` with the
  original exception preserved as `__cause__`; they are never retried.
- Application errors already normalized at the boundary are not re-normalized.
- Error messages contain identifiers, model names, status codes, reason codes,
  and chunk IDs only. They must not contain chunk text, document text, full
  vectors, secrets, or credentials.

### 8.4 Model and configuration mismatches

- A mismatched response `model` raises `EmbeddingModelMismatchError`; it is
  permanent and is not retried.
- A provider whose `identity` does not match the pinned configuration raises
  `EmbeddingConfigurationError`; it is permanent and is not retried.
- A dimension mismatch raises `EmbeddingResponseError` with reason
  `dimension_mismatch`; it is permanent. If the mismatch reflects a genuinely
  different model dimension, stop and amend this specification.

### 8.5 Retry policy

This draft reuses the approved bounded-retry semantics and concrete defaults of
`app.llm.retry.RetryPolicy`:

- `max_retries = 2`
- `base_delay = 0.5`
- `max_delay = 8.0`
- `jitter = 0.0`

Rules:

- Retries apply only to `EmbeddingConnectionError`, `EmbeddingTimeoutError`,
  `EmbeddingRateLimitError`, and `EmbeddingUnavailableError`.
- Non-retryable errors fail immediately without retry.
- Total provider attempts per batch are limited to `1 + max_retries`.
- Backoff is bounded exponential:
  `min(base_delay * 2**attempt, max_delay)`, with optional non-negative jitter.
- Sleep is injectable so unit tests do not wait.
- Retry counts are observable on success through `EmbeddingResult.retry_count`
  and on failure through `error.retry_count`.
- Retry state is local to a service call; concurrent calls do not share mutable
  retry state.
- Retries are per batch. A retry does not duplicate previously successful
  chunks or change input order.
- If retries are exhausted, the final normalized error is raised.

Concrete settings are proposed in §10.2. Whether the implementation reuses the
existing `RetryPolicy` class or an embeddings-local equivalent is an
implementation-review decision; the semantics and defaults are not.

### 8.6 Timeout behavior

- Every provider attempt must have a timeout.
- The timeout is per attempt and is passed explicitly to the provider.
- Backoff does not consume the per-attempt timeout.
- No overall deadline across retries is introduced.
- A timed-out attempt normalizes to `EmbeddingTimeoutError` and may be retried.
- HTTP-library-specific timeout exceptions must not escape the adapter.

## 9. Vector Normalization

- V1 preserves provider-returned vector values unchanged.
- The subsystem must not apply L2 normalization, scaling, clipping, rounding,
  dimensionality reduction, or any other transformation.
- `EmbeddingConfig.normalization` is fixed to `"none"` in V1 and is part of the
  configuration identity.
- The provider may itself return normalized or unnormalized vectors depending on
  its implementation. This specification treats provider output as opaque and
  does not assert a normalization property.
- Similarity metric, normalization policy, distance function, and any
  query-time transformation belong to the future vector-storage/retrieval
  specification. Changing them must not silently change this subsystem's
  identity.

## 10. Configuration and Security

### 10.1 Pinned in code

The following are pinned constants in the embeddings package and must not be
environment overrides:

- Provider: `ollama`
- Model: `nomic-embed-text:v1.5`
- Expected dimension: `768` (provisional until T270)
- Document prefix: `search_document: `
- Query prefix: `search_query: `
- Normalization: `none`
- Algorithm version: `embeddings-v1`

### 10.2 Operational settings

Additive settings following `pydantic-settings` conventions in
`src/app/core/config.py`:

| Setting | Environment variable | Default | Validation |
| --- | --- | --- | --- |
| `embedding_batch_size` | `EMBEDDING_BATCH_SIZE` | `16` | `gt=0` |
| `embedding_timeout_seconds` | `EMBEDDING_TIMEOUT_SECONDS` | `30.0` | `gt=0` |
| `embedding_max_retries` | `EMBEDDING_MAX_RETRIES` | `2` | `ge=0` |
| `embedding_retry_base_delay` | `EMBEDDING_RETRY_BASE_DELAY` | `0.5` | `ge=0` |
| `embedding_retry_max_delay` | `EMBEDDING_RETRY_MAX_DELAY` | `8.0` | `ge=0`, `>= base_delay` |
| `embedding_retry_jitter` | `EMBEDDING_RETRY_JITTER` | `0.0` | `ge=0` |

Requirements:

- All settings are optional with defaults.
- Invalid values fail clearly at settings construction/startup.
- `embedding_retry_max_delay >= embedding_retry_base_delay` is enforced.
- These values are operational only and are excluded from
  `embedding_config_id`.
- The Ollama base URL reuses the existing `ollama_url` setting
  (`OLLAMA_URL`). The adapter receives it from the composition root; it does not
  read environment variables directly.
- No `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`, or prefix override is
  introduced in V1.
- `.env.example` documents the operational settings when T269 adds them.
- `EmbeddingService.from_settings(settings, provider)` must not call
  `get_settings()` eagerly.

### 10.3 Security and logging

- No secrets are introduced. Ollama authentication is not part of V1.
- The subsystem must not log source document text, chunk text, full vectors, or
  provider response bodies by default.
- Error messages may include chunk IDs, source paths, model names, status codes,
  reason codes, and retry counts.
- Provider errors must not expose credentials or request bodies.
- The subsystem performs no filesystem writes and no database or Qdrant access.

## 11. Testing Requirements

Unit tests must be deterministic and offline: no network, no Ollama, no Qdrant,
and no PostgreSQL.

### 11.1 Contract and identity tests (T267)

- Frozen `EmbeddingConfig`, `ChunkEmbedding`, and `EmbeddingResult`.
- Validation rejects invalid dimensions, empty identities, non-finite vectors,
  duplicate chunk IDs, and mismatched configuration IDs.
- `config_id` is stable across repeated construction and processes.
- Every included field changes `config_id`.
- Batch size, timeout, retry settings, base URL, Qdrant settings, and database
  settings do not change `config_id`.
- The canonical serialization uses `sort_keys=True`,
  `separators=(",", ":")`, `ensure_ascii=False`, and UTF-8.
- Every declared exception has a reachable, tested role.

### 11.2 Provider adapter tests (T268)

- Request method, URL, JSON body, model, input array, and timeout.
- Response parsing for one vector and multiple vectors.
- Missing, empty, or non-array `embeddings` raises the correct provider error.
- Missing, non-string, or different response `model` raises
  `EmbeddingProviderModelMismatchError`.
- Invalid JSON raises `EmbeddingProviderResponseError`.
- HTTP status mapping for 429, 401, 403, 400, 422, 404, 5xx, and other statuses.
- Connection and timeout errors map to their provider types.
- No raw `httpx` exception escapes.
- Tests use `httpx.MockTransport`; no real socket or Ollama is used.

### 11.3 Service tests (T269)

- Batch splitting: for example, 5 chunks with batch size 2 produce calls of
  sizes 2, 2, and 1.
- Input order is preserved across batches.
- One output per input chunk; mapping by `chunk_id` is correct.
- Empty input returns an empty result and calls the provider zero times.
- Duplicate `chunk_id` raises `ValueError` and calls the provider zero times.
- Count mismatch raises `EmbeddingResponseError(reason="count_mismatch")`.
- Dimension mismatch raises `EmbeddingResponseError(reason="dimension_mismatch")`.
- Non-finite values raise `EmbeddingResponseError(reason="non_finite_value")`.
- Missing or empty embeddings raise the correct response error.
- Retryable errors are retried up to the configured limit.
- Non-retryable errors are not retried.
- Retry exhaustion raises the final normalized error with the correct
  `retry_count`.
- Per-attempt timeout is passed to every attempt; backoff does not consume it.
- Error messages contain no chunk text or vector values.
- Service imports no Qdrant, SQLAlchemy, psycopg, FastAPI, or persistence code.
- Service performs no file writes.
- `from_settings` does not call `get_settings` eagerly.

### 11.4 Live conformance (T270)

- A live test or recorded verification command calls the real Ollama
  `POST /api/embed` with the approved model.
- The response `model` equals `nomic-embed-text:v1.5`.
- The observed vector dimension is recorded. It must equal `768`; otherwise stop
  and amend this specification.
- Every returned value is finite.
- The served model name and digest are recorded from Ollama metadata.
- The live test is opt-in and does not run in the offline focused suite.
- Actual commands and outcomes are recorded in `specs/project-state.md`; no
  success is claimed in advance.

### 11.5 Offline, regression, and boundary tests

- The focused embeddings suite passes with networking disabled.
- The full regression suite passes.
- A static import scan proves the embeddings implementation does not import
  Qdrant, SQLAlchemy, psycopg, FastAPI endpoint modules, or persistence modules.
- A no-write test proves the service and adapter perform no filesystem writes.
- No ingestion, chunking, tokenizer, LLM, or domain behavior changes.
- `git diff --check` is clean.

## 12. Acceptance Criteria

The specification is satisfied only when all of the following are true:

1. The provider is Ollama and the model is pinned to
   `nomic-embed-text:v1.5`; no environment variable selects either.
2. `POST /api/embed` request and response contracts are implemented as defined
   in §4.
3. Response `model` identity is validated; mismatch is permanent and tested.
4. Document input uses the `search_document: ` prefix; query embedding is not
   implemented.
5. `EmbeddingConfig.config_id` is deterministic, canonical, and includes every
   vector-affecting field while excluding operational settings.
6. `EmbeddingProvider`, `EmbeddingConfig`, `ChunkEmbedding`, `EmbeddingResult`,
   and `EmbeddingService` satisfy §6.
7. Batching preserves order and uses the configured batch size.
8. Empty input returns an empty result without a provider call.
9. Duplicate chunk IDs are rejected before any provider call.
10. Vector count, dimension, and finite-value validation are enforced.
11. Any failed batch invalidates the overall result; no partial success is
    returned.
12. Retryable and permanent errors are distinguished; retries are bounded;
    per-attempt timeouts and backoff are independent; no overall deadline is
    introduced.
13. Provider exceptions never escape the service boundary.
14. V1 preserves provider vectors unchanged; no L2 normalization is added.
15. Error messages and logs contain no source text, chunk text, full vectors, or
    secrets.
16. Offline unit tests, focused tests, and full regression pass.
17. Live conformance records the actual model identity, digest, and dimension;
    `768` is not treated as verified before T270.
18. The implementation requires no Qdrant, database, persistence, HTTP endpoint,
    or agent integration.
19. The specification is explicitly approved before T267 begins.

## 13. Proposed Task Breakdown

This breakdown is **proposed and not approved**. Only one task may be executed
per session after the specification is approved.

| Task | Scope | Depends on | Acceptance |
| --- | --- | --- | --- |
| **T267 — Embedding contracts, identity, configuration, and error taxonomy** | `src/app/rag/embeddings/__init__.py`, `contracts.py`, `exceptions.py`, `providers/__init__.py`, `providers/base.py`, `providers/exceptions.py`; `tests/rag/embeddings/__init__.py`, `test_contracts.py`, `test_errors.py` | Specification approval | Immutable contracts; deterministic `config_id`; canonical serialization; pinned constants; complete error taxonomy with tested roles; no HTTP, service, settings, or persistence code |
| **T268 — Ollama embedding adapter and offline HTTP-mock tests** | `src/app/rag/embeddings/providers/ollama.py`; `tests/rag/embeddings/test_ollama_provider.py` | T267 | `/api/embed` request/response contract; model mismatch detection; status/connection/timeout/response normalization; no raw HTTP exceptions; offline `httpx.MockTransport` tests |
| **T269 — Embedding service, batching, ordering, validation, and settings integration** | `src/app/rag/embeddings/service.py`; `src/app/rag/embeddings/retry.py` if required; additive `embedding_*` settings in `src/app/core/config.py`; `.env.example`; `tests/rag/embeddings/test_service.py`, `test_retry.py` | T268 | Batching and order preservation; empty input; duplicate rejection; count/dimension/finite validation; bounded retries; per-attempt timeout; `from_settings` without eager settings access; no Qdrant or persistence |
| **T270 — Live Ollama conformance, dimension verification, regression, and closure** | `tests/rag/embeddings/test_ollama_conformance.py`; task documentation and `specs/project-state.md` | T269 | Live model identity, digest, and dimension recorded; `768` confirmed or specification amended; offline and full regression pass; `git diff --check` clean; closure record |
| **T271 — Composition-root wiring and Docker image verification** | `src/app/rag/embeddings/composition.py`; `src/app/main.py` startup wiring; `tests/rag/embeddings/test_composition.py`; relevant documentation | T270 | Service constructed once per process from settings and exposed through `app.state`; image builds; no bind mount; focused offline suite and full regression pass; no new endpoint, consumer, or DI framework |

Task boundaries:

- T267 adds no HTTP or service code.
- T268 adds no batching or application settings.
- T269 adds no composition root or startup wiring.
- T270 is conformance and closure; a defect within approved scope reopens the
  owning task instead of being patched in T270.
- T271 adds no retrieval, Qdrant, or persistence behavior.

## 14. File Placement

```text
src/app/rag/embeddings/
    __init__.py
    contracts.py          # EmbeddingConfig, ChunkEmbedding, EmbeddingResult, IDs
    exceptions.py         # application-level error taxonomy
    retry.py              # embeddings-local policy if not reused
    service.py            # EmbeddingService, from_settings
    composition.py        # production composition root (T271)
    providers/
        __init__.py
        base.py           # EmbeddingProvider protocol
        exceptions.py     # provider-level error taxonomy
        ollama.py         # POST /api/embed adapter (T268)
tests/rag/embeddings/
    __init__.py
    test_contracts.py
    test_errors.py
    test_ollama_provider.py
    test_service.py
    test_retry.py
    test_ollama_conformance.py   # live, opt-in (T270)
    test_composition.py          # T271
```

The implementation must not add persistence, Qdrant, database, HTTP endpoint,
CLI, or agent modules under this boundary.

## 15. Definition of Done and Approval Gate

This draft is complete for review when:

- The specification content above is reviewed.
- The approved, proposed, and unresolved decisions in §2 are accepted or
  revised.
- The provisional `768` dimension is acknowledged as unverified.
- The retry implementation location is decided.
- The T267–T271 task breakdown is approved or revised.
- The specification status is changed to `Approved` in a separate approval
  commit.

Implementation must not begin until that approval. T267 remains unstarted and
is not authorized by this draft.
