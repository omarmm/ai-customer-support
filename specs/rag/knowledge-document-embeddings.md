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

**Revision 2** addresses the review findings on model identity and digest,
the provisional dimension, retry dependency, retry-count semantics,
provider-to-application error mapping, and task acceptance criteria. It
remains unapproved. Decisions that still require human approval are listed in
the decision register in §2.4.

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
| The existing LLM retry policy is bounded, retries only normalized errors with `retryable=True`, exposes `retry_count`, and uses `max_retries=2`, `base_delay=0.5`, `max_delay=8.0`, `jitter=0.0`. | `specs/llm/error-handling.md` §6; `src/app/llm/retry.py`; `src/app/llm/services/llm_service.py` |
| Ollama-specific HTTP status interpretation belongs to the Ollama adapter and is not treated as a universal status-code rule. The existing adapter maps 404 to `LLMProviderModelNotFoundError`. | `specs/llm/error-handling.md` §5; `src/app/llm/providers/ollama.py` |

### 2.2 Proposed decisions in this draft

These decisions are proposed by this draft and are not approved until the
specification is approved:

| Decision | Proposal |
| --- | --- |
| Provider endpoint | `POST {OLLAMA_URL}/api/embed` with batched `input`. |
| Document prefix | `search_document: `, prepended to every chunk before embedding. |
| Query prefix | `search_query: `, reserved for the future retrieval specification and not used in V1. |
| Model identity pinning | Provider, model tag, prefixes, normalization policy, and algorithm version are pinned in code. No environment variable selects them. Runtime validation compares the `model` reported by Ollama with the configured tag. |
| Expected dimension | `768` is the provisional expected dimension used by configuration and offline validation until T270 observes the live value. It is never described as verified. |
| Batch size | Configurable, default `16`. |
| Request timeout | Configurable per attempt, default `30` seconds. |
| Retry policy | Reuse the approved bounded-retry semantics and concrete defaults of the LLM policy. The code-level dependency remains open; see D-3. |
| Vector normalization | V1 preserves provider-returned values unchanged. No L2 normalization is added. |
| Result ordering | Preserve input chunk order exactly. |
| Duplicate handling | Reject duplicate `chunk_id` values before any provider call. |
| Failure handling | Any failed batch invalidates the overall result; no partial success is returned. |
| Persistence | None. The subsystem returns in-memory results only. |

### 2.3 Unresolved decisions requiring evidence or approval

The following items are not approved by this draft. Each maps to an entry in
the decision register in §2.4.

| Decision | Why unresolved | Required evidence or action |
| --- | --- | --- |
| Served model digest | The approved decision names the serving tag, not an observed digest. A tag can be re-pulled or re-quantized and produce different vectors. No repository code currently retrieves model metadata. | T270 records the digest reported by the live Ollama instance as conformance evidence. Whether the digest belongs in `embedding_config_id` or must be enforced at runtime is D-1 and D-2. |
| Runtime digest verification | Reliable verification requires a metadata call outside `POST /api/embed` and a failure policy. Adding that to the runtime path would extend the approved architecture. | A human decision is required before adding a metadata client or startup digest check (D-2). |
| Actual embedding dimension | `768` is provisional; this draft must not claim it is verified. | T270 must call the live model and record the observed dimension. If it is not `768`, stop and amend this specification and the pinned constant before closure (D-4). |
| Retry implementation location | Importing `app.llm.retry` from the RAG subsystem would introduce the first `app.rag.* -> app.llm.*` production dependency. | Choose one of the options in §8.8 before T269 begins (D-3). |
| Live conformance test gating | Offline unit tests must not require Ollama. | T270 must define and record the opt-in live test mechanism. A marker such as `RUN_LIVE_OLLAMA=1` is proposed, not approved (D-5). |
| Ollama base URL setting | `Settings.ollama_url` (`OLLAMA_URL`) exists, while the existing LLM Ollama adapter reads `OLLAMA_BASE_URL` directly. The embeddings adapter must not repeat direct environment access. | Confirm that the embeddings composition root passes `settings.ollama_url` and that the existing LLM behavior is left unchanged (D-6). |

### 2.4 Decision register

No item in this register is approved by the draft. Explicit specification
approval may approve the recommendations; otherwise the named task must stop
at its gate.

| ID | Decision | Status | Recommendation | Gate |
| --- | --- | --- | --- | --- |
| **D-1** | Is the served model digest part of `embedding_config_id`? | Open | Exclude it in V1. Keep `config_id` deterministic from configured inputs only. Record the observed digest as conformance evidence, outside the identity. Including an ambient, re-pullable digest would make the identity deployment-dependent and would require an approved pinning and migration policy. | Before approval of this specification / T267 |
| **D-2** | Is the served model digest verified at runtime? | Open | Do not verify it in V1. `POST /api/embed` does not return a digest, and no metadata client exists in the current architecture. If runtime enforcement is required, approve a separate task for a metadata lookup and its failure policy. | Before any task that adds a metadata call; not part of T267–T271 |
| **D-3** | Reuse `app.llm.retry.RetryPolicy` or add an embeddings-local equivalent? | Open | Add `EmbeddingRetryPolicy` under the embeddings package with identical validation, defaults, and delay semantics. It avoids a new cross-subsystem dependency and needs its own settings mapping anyway. Duplication is deliberate and small. | Before T269 |
| **D-4** | Is the observed dimension `768`? | Open; evidence required | T270 measures it. Any other value stops the task and requires a specification amendment before closure. | T270 |
| **D-5** | How is the live conformance test gated? | Open | An opt-in environment gate, not part of the default offline suite. Exact mechanism is confirmed in T270. | T270 |
| **D-6** | Which setting supplies the Ollama base URL? | Open | The composition root passes `settings.ollama_url`. The adapter accepts `base_url` explicitly. Do not change the existing LLM adapter or its `OLLAMA_BASE_URL` behavior in this work. | T271 |

## 3. Scope

### 3.1 In scope

- Generate one embedding vector for each `Chunk` supplied by the existing
  chunking subsystem.
- Ollama integration through `POST /api/embed`.
- Provider contract, configuration identity, batching, response validation, and
  error handling.
- Injectable service design and dependency boundaries.
- Offline unit testing and live-model conformance verification.
- Recording the live model name, observed dimension, and reported digest as
  conformance evidence, without treating the digest as runtime-verified.
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
- Runtime model-digest verification, metadata polling, and any `/api/tags` or
  `/api/show` integration. Digest evidence collection is a documented T270
  conformance action, not runtime behavior.
- Logging full source text or full vectors.

## 4. Provider and Model Contract

### 4.1 Provider and model

- Provider: Ollama.
- Serving model: `nomic-embed-text:v1.5`.
- Configured provider/model identity string:
  `ollama:nomic-embed-text:v1.5`, formed as `f"{provider}:{model}"`.
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
- The length of every vector must equal the effective expected dimension
  (`768` is provisional until T270).
- Every value must be finite. Booleans, strings, nulls, nested arrays, NaN, and
  infinity are invalid.
- Timing fields such as `total_duration`, `load_duration`, and
  `prompt_eval_count` are ignored by this subsystem.

### 4.4 Model identity: configured, reported, and served

Three distinct concepts must not be conflated:

| Concept | Source | Meaning | V1 treatment |
| --- | --- | --- | --- |
| Configured model tag | `EmbeddingConfig.model` | The local Ollama model name the subsystem requests, `nomic-embed-text:v1.5`. | Pinned in code and included in `embedding_config_id`. |
| Reported model name | `model` in the `POST /api/embed` response | The model name the running Ollama instance says it served. | Validated to equal the configured tag. A mismatch is permanent. |
| Served model digest | Manifest metadata reported by Ollama, for example `digest` on an entry returned by `GET /api/tags` | An identifier for the resolved local model manifest. Intended to distinguish different content served under the same tag. | Not used by configuration identity or runtime validation in V1. Recorded as conformance evidence in T270. Decisions D-1 and D-2. |

- The configured tag does not guarantee immutable vector output. Re-pulling,
  re-quantizing, or re-tagging can change the served manifest under the same
  tag.
- The response `model` check detects a wrongly reported or wrong model name. It
  does not prove which manifest or weights produced the vectors.
- `POST /api/embed` is not documented to return a digest. This draft does not
  assume that any response field can substitute for one.
- Reliable digest verification needs a separate Ollama metadata request. No
  such client exists in the repository today, and adding one to the runtime path
  would extend the approved architecture. That is why D-2 requires a human
  decision rather than being implemented silently.

### 4.5 Model identity validation

- The request always uses the pinned model tag.
- The adapter validates the response `model` field against the pinned tag and
  raises a permanent provider error on a missing, non-string, or different
  value.
- The service validates that the injected provider's `identity` matches the
  pinned provider/model identity in `EmbeddingConfig`.
- A response `model` mismatch, after normalization, is a permanent
  `EmbeddingModelMismatchError`. It is never retried.
- A provider-wiring identity mismatch is a permanent
  `EmbeddingConfigurationError`. It is never retried.
- The running model must not be silently accepted when its reported name
  differs from the approved tag.
- A successful run does not imply that the served digest was verified. No
  success message, log line, or result field may claim digest verification until
  D-2 is approved and implemented.

### 4.6 Served digest handling

V1 proposed behavior, subject to D-1 and D-2:

- `embedding_config_id` is computed from configured, deterministic inputs only.
  It does not include a digest observed from a deployment.
- The service and adapter do not call `/api/tags` or `/api/show`.
- T270 records the configured tag, the response `model`, the observed
  dimension, and the digest reported by the live Ollama instance. The digest is
  recorded verbatim as reported; no prefix or format is assumed.
- If a future requirement needs digest pinning or runtime enforcement, that
  work requires an approved specification change covering:
  - the metadata endpoint and response contract;
  - whether the digest enters the configuration identity or a separate
    generation manifest;
  - startup and request-time failure behavior;
  - re-embedding and invalidation consequences.
- A tag-only identity is an accepted residual risk for V1 only if the reviewer
  approves D-1 and D-2 as recommended.

### 4.7 Dimension status

The expected dimension is **proposed as `768` and is not verified by this
draft**. It is provisional until T270 measures the live model.

Implementation handling before T270:

- The contract exposes the provisional value as a clearly named pinned
  constant, for example `PROVISIONAL_EMBEDDING_DIMENSION = 768`. Its name and
  documentation must state that it is unverified.
- `EmbeddingConfig.dimension` defaults to that constant. Because the dimension
  is part of the configuration identity, an amendment after T270 changes
  `embedding_config_id`.
- Offline tests validate dimension behavior against explicit synthetic
  dimensions or the provisional constant. They do not imply that the live model
  returns `768`.
- The adapter does not validate dimension. The service does, using the effective
  `EmbeddingConfig.dimension`.
- No code path may accept an arbitrary or dynamically discovered dimension at
  runtime in V1. Discovery happens only in T270 evidence collection, and the
  value is pinned only after approval.
- Until T270, no document may claim that `768` is confirmed.
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
    dimension: int = 768             # provisional expected; T270 verifies
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

- `embedding_config_id` is an identity of configured inputs. It is not proof of
  the runtime manifest or of vector reproducibility.
- No timestamps, random values, hostnames, paths, process state, or deployment
  identifiers.
- No served digest is included in V1 under the recommendation for D-1. If D-1
  is approved differently, the canonical payload and this section must be
  amended before implementation.
- Includes every configured field that affects vector representation.
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
- Validate the HTTP response envelope, JSON, response `model`, `embeddings`
  presence, and vector element types. It does not validate batch count,
  dimension, or finiteness; those are service invariants.
- Raise only provider-layer exceptions defined in §8.2.
- Perform no persistence, call no metadata endpoint, and return no partial
  success.

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
| `retry_count` | Total additional attempts performed across all batches during this successful service call; default `0` |

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

The `retry_policy` type annotation shows the recommended D-3 option. If D-3
selects reuse instead, the parameter type is the approved shared policy; the
service contract does not change.

Responsibilities and guarantees:

- Construct one effective `EmbeddingConfig` per service.
- Validate that `provider.identity` matches
  `f"{config.provider}:{config.model}"`; mismatch raises
  `EmbeddingConfigurationError`.
- Validate `batch_size > 0`, `timeout > 0`, and a valid retry policy at
  construction.
- Use the retry policy implementation approved under D-3. The service must not
  import `app.llm.*` unless that option is explicitly approved.
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

Validation is split at the architectural boundary:

| Check | Detection layer |
| --- | --- |
| HTTP status classification, connection, timeout | Provider adapter |
| JSON decoding | Provider adapter |
| Response root is a JSON object | Provider adapter |
| `embeddings` field present and a list | Provider adapter |
| Each embedding is a list and each element is a JSON number (booleans excluded) | Provider adapter |
| Response `model` present, a string, and equal to the pinned tag | Provider adapter |
| Vector count equals the batch input count | Service |
| Non-empty batch produced a non-empty vector list | Service |
| Every vector length equals `config.dimension` | Service |
| Every value is finite (no NaN or infinity) | Service |
| Vectors are converted to immutable float tuples without transformation | Service |

The adapter does not validate dimension or batch-level count. It must not apply
normalization, rounding, scaling, clipping, or truncation.

A violation raises `EmbeddingResponseError` with a stable reason code. Provider
response errors are raised by the adapter with the same reason code and are
normalized by the service without reinterpretation.

| Reason | Layer | Meaning |
| --- | --- | --- |
| `invalid_json` | Provider | Provider response is not valid JSON. |
| `malformed_response` | Provider | Response root, envelope, `embeddings` container, a vector, or a vector element has an invalid type. Booleans, strings, nulls, and nested structures are invalid values. |
| `missing_embeddings` | Provider | The `embeddings` field is absent. |
| `empty_embeddings` | Service | A non-empty batch produced zero vectors. |
| `count_mismatch` | Service | Vector count differs from the batch input count. |
| `dimension_mismatch` | Service | A vector length differs from `config.dimension`. |
| `non_finite_value` | Service | A numeric vector value is NaN or infinity. |

The provider model check has its own exception and is not reported as an
`EmbeddingResponseError` reason; see §8.4.

### 7.4 Failure semantics

- Any failed batch invalidates the overall result.
- The service raises the normalized application error; it does not return
  successful batches alone.
- No retry is attempted for response validation failures, model mismatch,
  configuration errors, or unexpected internal errors.
- Retryable provider failures may be retried per §8.6.
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

The 404 mapping mirrors the existing Ollama LLM adapter. It is acceptable only
because the Ollama adapter owns Ollama-specific interpretation, as required by
`specs/llm/error-handling.md` §5.3. It cannot distinguish a missing model from a
wrong route; if T268 evidence shows that ambiguity matters, record it and
request a mapping change rather than guessing globally. Other providers must not
inherit this rule.

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

### 8.4 Provider-to-application mapping

The mapping is by explicit provider exception type, ordered from most specific
to most general. The service must not interpret raw HTTP status codes. The
Ollama adapter owns the provider-specific status interpretation described in
§8.2.

| Failure | Detected by | Provider exception | Application exception | Reason code | Retryable |
| --- | --- | --- | --- | --- | --- |
| Invalid JSON | Adapter | `EmbeddingProviderResponseError` | `EmbeddingResponseError` | `invalid_json` | No |
| Malformed response envelope or invalid vector types | Adapter | `EmbeddingProviderResponseError` | `EmbeddingResponseError` | `malformed_response` | No |
| Missing `embeddings` | Adapter | `EmbeddingProviderResponseError` | `EmbeddingResponseError` | `missing_embeddings` | No |
| Empty embeddings for a non-empty batch | Service | — | `EmbeddingResponseError` | `empty_embeddings` | No |
| Vector count mismatch | Service | — | `EmbeddingResponseError` | `count_mismatch` | No |
| Dimension mismatch | Service | — | `EmbeddingResponseError` | `dimension_mismatch` | No |
| Non-finite vector value | Service | — | `EmbeddingResponseError` | `non_finite_value` | No |
| Missing or mismatched response model | Adapter | `EmbeddingProviderModelMismatchError` | `EmbeddingModelMismatchError` | — | No |
| Provider-wiring or configuration mismatch | Service construction | — | `EmbeddingConfigurationError` | — | No |
| Connection failure | Adapter | `EmbeddingProviderConnectionError` | `EmbeddingConnectionError` | — | Yes |
| Timeout | Adapter | `EmbeddingProviderTimeoutError` | `EmbeddingTimeoutError` | — | Yes |
| Rate limiting | Adapter | `EmbeddingProviderRateLimitError` | `EmbeddingRateLimitError` | — | Yes |
| Authentication failure | Adapter | `EmbeddingProviderAuthenticationError` | `EmbeddingAuthenticationError` | — | No |
| Invalid request | Adapter | `EmbeddingProviderInvalidRequestError` | `EmbeddingInvalidRequestError` | — | No |
| Model not found | Adapter | `EmbeddingProviderModelNotFoundError` | `EmbeddingModelNotFoundError` | — | No |
| Transient server-side failure | Adapter | `EmbeddingProviderUnavailableError` | `EmbeddingUnavailableError` | — | Yes |
| Unclassified provider failure | Adapter | `EmbeddingProviderError` | `EmbeddingError` | — | No |
| Unexpected internal exception | Service | — | `EmbeddingUnexpectedError` | — | No |

Additional rules:

- Provider HTTP subclasses must be matched before the generic
  `EmbeddingProviderHTTPError`, and that before `EmbeddingProviderError`.
- A provider response error retains its reason code when normalized. The
  application error must expose the same reason code.
- An unexpected exception preserves the original exception as `__cause__` and
  is never retried or converted into a provider error.
- `asyncio.CancelledError` must not be swallowed, normalized, or retried.
- Raw `httpx` exceptions, `httpx.HTTPStatusError`, and response bodies must
  never escape the adapter or the service.
- All application errors expose `category` and `retryable` consistent with the
  approved LLM taxonomy.

### 8.5 Model and configuration mismatches

- A mismatched response `model` raises `EmbeddingModelMismatchError`; it is
  permanent and is not retried.
- A provider whose `identity` does not match the pinned configuration raises
  `EmbeddingConfigurationError`; it is permanent and is not retried.
- A dimension mismatch raises `EmbeddingResponseError` with reason
  `dimension_mismatch`; it is permanent. If the mismatch reflects a genuinely
  different model dimension, stop and amend this specification.
- None of these outcomes verify or assert the served digest. A successful model
  name comparison means only that the reported name equals the configured tag.

### 8.6 Retry policy

The approved bounded-retry semantics and concrete defaults are:

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
- Retry state is local to a service call; concurrent calls do not share mutable
  retry state.
- Retries are per batch. A retry does not duplicate previously successful
  chunks or change input order.
- If retries are exhausted, the final normalized error is raised.
- The existing LLM behavior and defaults are not changed by this specification.

Concrete settings are proposed in §10.2. The code-level dependency decision is
D-3 in §2.4 and §8.8; the semantics and defaults are not open.

### 8.7 Retry count semantics

An **attempt** is one call to `EmbeddingProvider.embed` for one batch. A
**retry** is an additional attempt made for the same batch after a retryable
failure. The first attempt is not a retry.

Successful execution:

- `EmbeddingResult.retry_count` is the total number of additional attempts
  performed across all batches during the service call.
- A run with no retryable failure reports `0`.
- A run in which two batches each retried once reports `2`.
- The count is per service call and is not persisted between calls.

Failed execution:

- `error.retry_count` is the total number of retries performed across the
  service call before the terminal failure.
- It includes retries performed in batches that completed successfully earlier
  in the same call.
- It excludes the terminal failed attempt, which is not itself a retry.
- A non-retryable failure in a later batch therefore still reports retries
  already spent in earlier batches.
- Validation failures, model mismatches, and configuration errors are not
  retries; if they occur after earlier retries, the earlier count is still
  reported.
- A failure no later than the first batch, with no retry, reports `0`.

Consistency:

- This is the same observable meaning used by the approved LLM implementation,
  where a normalized error carries the number of retries performed and a
  successful response reports `metadata["retry_count"]`.
- The multi-batch aggregate is an embeddings-specific extension of that
  convention. It does not change the per-attempt or per-batch retry limit.
- No approved specification defines a conflicting application-level retry-count
  contract.

### 8.8 Retry dependency decision

Importing `app.llm.retry.RetryPolicy` from `app.rag.embeddings` would introduce
the first production dependency from the RAG subsystem to the LLM subsystem.
Repository evidence: no `app.rag.*` module imports `app.llm.*` today, and
`RetryPolicy.from_settings` reads `llm_*` settings, so it cannot be used
unchanged for embedding settings.

Options:

1. **Reuse `app.llm.retry.RetryPolicy`.**
   - Advantages: one implementation, no duplication, defaults stay aligned.
   - Disadvantages: new cross-subsystem dependency; RAG becomes coupled to an
     LLM module; the settings adapter still needs an embeddings-specific
     factory or a settings object exposing `llm_*` names.
2. **Add an embeddings-local `EmbeddingRetryPolicy`.**
   - Advantages: preserves the current dependency direction; can validate
     embedding settings directly; keeps the small policy next to its only
     consumer.
   - Disadvantages: deliberate duplication of about sixty lines; drift risk,
     mitigated by mirrored tests for validation, defaults, and delay growth.
3. **Extract a shared retry abstraction.**
   - Advantages: one implementation with no cross-subsystem dependency.
   - Disadvantages: requires moving or re-exporting the existing class,
     updating LLM imports and tests, and a separate approved architectural
     change. This task and T267–T271 must not perform that refactor.

Recommendation: option 2, with identical validation and semantics. This is
D-3 and is not approved by the draft. T269 must not begin until D-3 is
resolved. No option changes the defaults listed in §8.6 or any LLM behavior.

### 8.9 Timeout behavior

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
- Model tag: `nomic-embed-text:v1.5`
- Provisional expected dimension: `PROVISIONAL_EMBEDDING_DIMENSION = 768`
  (unverified until T270; the constant name must state that it is provisional)
- Document prefix: `search_document: `
- Query prefix: `search_query: `
- Normalization: `none`
- Algorithm version: `embeddings-v1`
- Served digest: not pinned, not verified, and not part of the configuration
  identity under the D-1/D-2 recommendation

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
- The Ollama base URL is supplied to the adapter from the composition root.
  Repository evidence: `Settings` already defines `ollama_url` (`OLLAMA_URL`),
  while the existing LLM adapter reads `OLLAMA_BASE_URL` directly. The
  embeddings adapter must accept an explicit `base_url` argument and must not
  read environment variables. Confirming the production source is D-6. The
  existing LLM adapter is out of scope and must not be changed.
- The adapter must not call `/api/tags` or `/api/show`. Digest evidence
  collection in T270 may use a documented manual command outside the runtime
  path.
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
- The served digest, batch size, timeout, retry settings, base URL, Qdrant
  settings, and database settings do not change `config_id`.
- The canonical serialization uses `sort_keys=True`,
  `separators=(",", ":")`, `ensure_ascii=False`, and UTF-8.
- The provisional dimension constant is named and documented as unverified; no
  test asserts that the live model returns `768`.
- Every declared exception has a reachable, tested role, and every application
  error exposes `category` and `retryable`.
- Error messages contain no chunk text, document text, full vectors, or
  secrets.

### 11.2 Provider adapter tests (T268)

- Request method, URL, JSON body, model, input array, and timeout.
- Response parsing for one vector and multiple vectors.
- Missing or non-array `embeddings` raises the correct provider error. An empty
  `embeddings` list is structurally valid and is returned for service-level
  `empty_embeddings` handling.
- Non-array vectors and boolean, string, or null vector elements raise
  `EmbeddingProviderResponseError` with reason `malformed_response`.
- Missing, non-string, or different response `model` raises
  `EmbeddingProviderModelMismatchError`.
- Invalid JSON raises `EmbeddingProviderResponseError` with reason
  `invalid_json`.
- HTTP status mapping for 429, 401, 403, 400, 422, 404, 5xx, and other statuses.
- Connection and timeout errors map to their provider types.
- A response is rejected without any call to `/api/tags` or `/api/show`; the
  adapter never claims digest verification.
- No raw `httpx` exception escapes.
- Tests use `httpx.MockTransport`; no real socket or Ollama is used.

### 11.3 Service tests (T269)

- Batch splitting: for example, 5 chunks with batch size 2 produce calls of
  sizes 2, 2, and 1.
- Input order is preserved across batches.
- One output per input chunk; mapping by `chunk_id` is correct.
- Empty input returns an empty result with `retry_count == 0` and calls the
  provider zero times.
- Duplicate `chunk_id` raises `ValueError` and calls the provider zero times.
- Count mismatch raises `EmbeddingResponseError(reason="count_mismatch")`.
- Empty embeddings for a non-empty batch raises
  `EmbeddingResponseError(reason="empty_embeddings")`.
- Dimension mismatch raises `EmbeddingResponseError(reason="dimension_mismatch")`.
- Non-finite values raise `EmbeddingResponseError(reason="non_finite_value")`.
- Missing or malformed provider responses normalize to the correct application
  error and preserve the reason code.
- Retryable errors are retried up to the configured limit.
- Non-retryable errors are not retried.
- Retry exhaustion raises the final normalized error with the correct
  `retry_count`.
- Successful execution reports the aggregate retry count:
  - no retries → `0`;
  - one batch retried once → `1`;
  - two batches each retried once → `2`.
- Failed execution reports the aggregate retry count up to the failure:
  - first-batch non-retryable failure → `0`;
  - an earlier batch retried once, then a later batch fails permanently → `1`;
  - an earlier batch retried once, then a later batch exhausts two retries →
    `3`.
- The terminal failed attempt is not counted as a retry.
- Provider exceptions and raw HTTP errors never escape the service.
- Model mismatch and configuration mismatch are permanent and not retried.
- Per-attempt timeout is passed to every attempt; backoff does not consume it.
- Error messages contain no chunk text or vector values.
- Service imports no Qdrant, SQLAlchemy, psycopg, FastAPI, or persistence code.
- Service imports no `app.llm` module unless D-3 is explicitly approved as the
  reuse option.
- Service performs no file writes and calls no metadata endpoints.
- `from_settings` does not call `get_settings` eagerly.

### 11.4 Live conformance (T270)

- A live test or recorded verification command calls the real Ollama
  `POST /api/embed` with the approved model.
- The response `model` equals `nomic-embed-text:v1.5`.
- The observed vector dimension is recorded. It must equal `768`; otherwise stop
  and amend this specification.
- Every returned value is finite.
- The served model name and digest are recorded as reported by the live Ollama
  instance, using a documented metadata command. The digest format is recorded
  verbatim and is not assumed.
- No test or report claims runtime digest verification; the digest is evidence
  only.
- The live test is opt-in and does not run in the offline focused suite.
- Actual commands and outcomes are recorded in `specs/project-state.md`; no
  success is claimed in advance.

### 11.5 Offline, regression, and boundary tests

- The focused embeddings suite passes with networking disabled.
- The full regression suite passes.
- A static import scan proves the embeddings implementation does not import
  Qdrant, SQLAlchemy, psycopg, FastAPI endpoint modules, or persistence modules.
- Under the recommended D-3 option, the same scan proves no `app.llm` import.
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
5. `EmbeddingConfig.config_id` is deterministic, canonical, includes every
   configured vector-affecting field, and excludes operational settings and the
   served digest under the decision approved for D-1.
6. `EmbeddingProvider`, `EmbeddingConfig`, `ChunkEmbedding`, `EmbeddingResult`,
   and `EmbeddingService` satisfy §6.
7. Batching preserves order and uses the configured batch size.
8. Empty input returns an empty result without a provider call.
9. Duplicate chunk IDs are rejected before any provider call.
10. Vector count, dimension, and finite-value validation are enforced with
    stable reason codes and the detection layer defined in §7.3.
11. Any failed batch invalidates the overall result; no partial success is
    returned.
12. Retryable and permanent errors are distinguished; retries are bounded;
    per-attempt timeouts and backoff are independent; no overall deadline is
    introduced. Successful and failed calls report aggregate `retry_count`
    exactly as defined in §8.7.
13. Provider exceptions never escape the service boundary.
14. V1 preserves provider vectors unchanged; no L2 normalization is added.
15. Error messages and logs contain no source text, chunk text, full vectors, or
    secrets.
16. Offline unit tests, focused tests, and full regression pass.
17. Live conformance records the actual model name, observed dimension, and
    digest as evidence; `768` is not treated as verified before T270, and the
    digest is not treated as verified at runtime.
18. The implementation requires no Qdrant, database, persistence, HTTP endpoint,
    or agent integration.
19. Decisions D-1, D-2, D-3, D-5, and D-6 are explicitly resolved before the
    affected task begins; D-4 is resolved by T270 evidence before closure.
20. The specification is explicitly approved before T267 begins.

## 13. Proposed Task Breakdown

This breakdown is **proposed and not approved**. Only one task may be executed
per session after the specification is approved.

| Task | Scope | Depends on | Acceptance |
| --- | --- | --- | --- |
| **T267 — Embedding contracts, identity, configuration, and error taxonomy** | `src/app/rag/embeddings/__init__.py`, `contracts.py`, `exceptions.py`, `providers/__init__.py`, `providers/base.py`, `providers/exceptions.py`; `tests/rag/embeddings/__init__.py`, `test_contracts.py`, `test_errors.py` | Specification approval; D-1 decided | Immutable contracts; deterministic `config_id`; canonical serialization; pinned tag, prefixes, and provisionally named dimension constant; served digest excluded from `config_id` under the D-1 decision approved before T267; complete error taxonomy with tested roles and mapping; no HTTP, service, retry implementation, settings, or persistence code |
| **T268 — Ollama embedding adapter and offline HTTP-mock tests** | `src/app/rag/embeddings/providers/ollama.py`; `tests/rag/embeddings/test_ollama_provider.py` | T267 | `/api/embed` request/response contract; response model comparison; provider status/connection/timeout/response normalization with stable reason codes; no `/api/tags` or `/api/show` calls; no digest claim; no raw HTTP exceptions; offline `httpx.MockTransport` tests |
| **T269 — Embedding service, batching, ordering, validation, retries, and settings integration** | `src/app/rag/embeddings/service.py`; `src/app/rag/embeddings/retry.py` when the approved D-3 option requires it; additive `embedding_*` settings in `src/app/core/config.py`; `.env.example`; `tests/rag/embeddings/test_service.py`, `test_retry.py` | T268; D-3 decided | Batching and order preservation; empty input; duplicate rejection; count/empty/dimension/finite validation at the service layer; bounded retries with approved dependency option; per-attempt timeout; aggregate `retry_count` for successful and failed calls per §8.7; `from_settings` without eager settings access; no Qdrant, persistence, metadata, or unapproved `app.llm` import |
| **T270 — Live Ollama conformance, dimension verification, regression, and closure** | `tests/rag/embeddings/test_ollama_conformance.py`; task documentation and `specs/project-state.md` | T269; D-4 and D-5 decided or confirmed during execution | Live model name, observed dimension, and reported digest recorded as evidence; `768` confirmed or the specification amended before any conformance claim; offline and full regression pass; `git diff --check` clean; closure record that does not claim runtime digest verification |
| **T271 — Composition-root wiring and Docker image verification** | `src/app/rag/embeddings/composition.py`; `src/app/main.py` startup wiring; `tests/rag/embeddings/test_composition.py`; relevant documentation | T270; D-6 decided | Service constructed once per process from settings and exposed through `app.state`; base URL supplied explicitly from the approved setting; image builds; no bind mount; focused offline suite and full regression pass; no new endpoint, consumer, or DI framework |

Task boundaries:

- T267 adds no HTTP, service, retry implementation, or settings code.
- T268 adds no batching, application settings, or metadata endpoint client.
- T269 adds no composition root or startup wiring, and no `app.llm` import
  unless D-3 is explicitly approved as reuse.
- T270 is conformance and closure; a defect within approved scope reopens the
  owning task instead of being patched in T270. A dimension or digest finding
  that contradicts this specification stops the task and requires an amendment.
- T271 adds no retrieval, Qdrant, persistence, or metadata verification
  behavior.

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
- The approved, proposed, and unresolved decisions in §2 and the decision
  register in §2.4 are accepted, rejected, or revised. In particular:
  - D-1 and D-2 fix the served-digest policy;
  - D-3 fixes the retry dependency;
  - D-4 is acknowledged as the T270 evidence gate: `768` remains unverified
    now and a mismatch requires an amendment after measurement;
  - D-5 fixes live-test gating before T270;
  - D-6 fixes the base-URL source before T271.
- The provisional `768` dimension is acknowledged as unverified, and the
  constant name reflects that.
- Retry-count semantics in §8.7 are accepted for both success and failure.
- The T267–T271 task breakdown is approved or revised.
- The specification status is changed to `Approved` in a separate approval
  commit.

Implementation must not begin until that approval. T267 remains unstarted and
is not authorized by this draft. No decision in the register may be treated as
approved by implication.
