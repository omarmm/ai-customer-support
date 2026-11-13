# Knowledge Retrieval Specification

- **Status:** Draft — not approved; no implementation is authorized.
- **Phase:** Phase 4 — RAG
- **Subsystem:** Knowledge Retrieval
- **Depends on:** Approved ingestion, chunking, embeddings, and vector storage specifications and their completed implementations.
- **Current baseline:** Vector Storage T272–T278 is complete and merged into `master` (2026-11-09).
- **Approval rule:** This document defines a proposed contract only. Implementation requires explicit approval of this specification, followed by a separate dependency-ordered task breakdown and one-task-at-a-time authorization.

## 1. Purpose

Define the application-owned retrieval boundary that accepts a customer-support knowledge query and returns a ranked set of relevant knowledge chunks from the currently active Qdrant vector generation.

Retrieval is a separate subsystem from Vector Storage. It consumes the existing embedding and storage capabilities; it does not rebuild either subsystem or change their approved contracts without an explicit amendment.

The intended V1 path is:

```text
Query
  ↓
Validate query and retrieval options
  ↓
EmbeddingService.embed_query(query)
  ↓
Search the active Qdrant generation with approved metadata filters
  ↓
Validate and normalize candidate results
  ↓
Ranked RetrievalResult (application-owned DTOs)
```

`EmbeddingService` owns both document and query embedding operations. Retrieval depends on that application-owned capability, not on a concrete provider or model.

This specification does not assemble an LLM prompt or generate an answer. It returns evidence candidates for a later Context Construction boundary.

## 2. Goals

- Retrieve semantically relevant chunks using the active vector generation.
- Obtain query vectors through the Embeddings boundary using an explicitly compatible embedding-space identity. The current approved V1 configuration is `ollama:nomic-embed-text:v1.5` with the reserved `search_query: ` prefix; Retrieval must not hard-code this provider/model as its architectural dependency.
- Search through the application-owned `VectorStore` port; Qdrant SDK types must not escape the adapter.
- Support a bounded, explicit metadata-filter contract over fields already stored and indexed.
- Preserve source identity, provenance, offsets, generation identity, and similarity score in every result.
- Return deterministic application-level success/error contracts and never expose partial success as a complete result.
- Remain local-first and testable without requiring paid services.
- Emit metadata-only observability without logging query text, chunk content, vectors, or credentials.

## 3. Non-goals and Specification Boundaries

The following are separate boundaries and must not be silently pulled into this implementation:

- Context construction: token budgeting, selection/diversity, ordering, truncation, and prompt-ready assembly require a separate specification.
- Source attribution/citations: citation formatting, source-link resolution, and answer-to-source traceability require a separate specification.
- Retrieval evaluation: datasets, relevance labels, metrics, baselines, and acceptance thresholds require a separate evaluation specification.
- End-to-end RAG failure handling: cross-stage recovery, fallback policy, and user-facing degraded behavior require a separate specification.
- Sparse and hybrid dense/sparse search are excluded from Retrieval V1 (R-2 approved). Any future hybrid capability requires a separate Vector Storage specification amendment, generation rebuild plan, and comparative evaluation.
- Reranking with a second model/provider. It requires its own quality, latency, and cost evidence before inclusion.
- HTTP endpoints, chat APIs, agent/tool integration, prompt assembly, answer generation, and business decisions.
- Changes to ingestion, chunking, document identity, chunk identity, document embedding generation, vector generation identity, or vector payload schema.
- PostgreSQL manifests or another source of truth for active generation state.
- Tenant isolation or authorization filters not defined by the current domain model and an approved security specification.

## 4. Existing Contracts and Constraints

### 4.1 Embeddings

The approved Embeddings specification establishes:

- Provider/model identity: `ollama:nomic-embed-text:v1.5`.
- Query prefix: `search_query: ` (reserved for Retrieval; document embedding uses `search_document: `).
- Expected and live-observed vector dimension: 768.
- Vector normalization: none; provider-returned values are preserved.
- Query prefix and the current V1 embedding configuration are pinned in code, not selected by an environment variable.
- The embedding provider is hidden behind an application-owned provider abstraction.
- The existing `EmbeddingService` currently exposes `embed_chunks(chunks)` and applies the document prefix; it must be extended with a typed `embed_query(query)` operation. Retrieval must not manufacture fake `Chunk` instances.

**Compatibility requirement:** `EmbeddingService` owns provider/model identity, operation-specific prefixes, validation, timeout, and retry behavior for both document and query embeddings. Both operations must resolve to an explicitly compatible embedding-space identity. Equal vector dimensions alone do not establish compatibility. Provider/model-specific prefixes and configuration remain encapsulated behind the Embeddings boundary. Vectors from incompatible embedding configurations must never be compared.

### 4.2 Vector Storage

The approved Vector Storage specification establishes:

- Qdrant Server and `qdrant-client` are pinned to `1.20.0`.
- The active generation is addressed by the alias `knowledge_vectors_active`.
- Each generation is immutable; activation atomically switches the alias.
- Previous generations are retained; no automatic cleanup is allowed.
- The collection uses one dense 768-dimensional Cosine vector.
- Existing payload fields include `chunk_id`, `generation_id`, `document_id`, `source_path`, `title`, `format`, `content`, `start_offset`, `end_offset`, `chunk_index`, `chunking_config_id`, and `embedding_config_id`.
- Payload indexes already exist for `generation_id`, `document_id`, `source_path`, `format`, `chunking_config_id`, and `embedding_config_id` (keyword), and `chunk_index` (integer).
- The application-owned `VectorStore.search` method is currently reserved and intentionally has no retrieval semantics.

#### Required Vector Storage Amendment — blocking dependency

The current Vector Storage contract does not yet expose trusted generation-level
embedding-space identity. Retrieval MUST NOT infer active-generation
compatibility from point payloads or vector dimensions alone.

A separate Vector Storage specification amendment and its implementation/
verification task sequence are mandatory before any Retrieval implementation.
The amendment is intentionally deferred until the Retrieval SDD and its
dependency-ordered task breakdown are complete. The amendment must define how
the active generation's `embedding_config_id` is stored, returned through
`GenerationInfo`, and validated by generation verification. Retrieval will
compare the query embedding's configuration identity with the active
generation's trusted identity before issuing search, including when the
generation contains zero points. Missing, malformed, or mismatched identity
must fail closed without a Qdrant search.

This is a sequencing approval only. The exact storage metadata contract,
migration/backfill/rebuild policy, and amendment acceptance criteria remain
subject to a separate specification review and explicit approval.

Retrieval must search the active alias, not guess a collection name or accept a caller-supplied collection name. It must not mutate generations or aliases.

### 4.3 Upstream identity and provenance

- `chunk_id` is the stable identity of a specific chunk.
- `document_id` identifies normalized document content.
- `source_path`, `title`, `format`, offsets, and `chunk_index` originate from the approved Chunk contract.
- The stored `embedding_config_id` identifies the document embedding configuration.
- Retrieval must return stored provenance unchanged. It must not reconstruct or infer source metadata from chunk text.

## 5. Proposed Architecture

The proposed application boundary is `src/app/rag/retrieval/`.

Candidate responsibilities:

1. Validate the query and the typed retrieval options.
2. Obtain one query embedding through an approved query-embedding contract.
3. Construct an application-owned vector search request.
4. Call `VectorStore.search` using the active alias.
5. Translate storage results into immutable retrieval DTOs.
6. Normalize retrieval-specific errors and preserve safe internal causes.
7. Emit the structured metadata-only observability event defined by R-17.
8. Execute each request against the current active generation without a Retrieval result cache in V1 (R-21).

Proposed flow:

```text
RetrievalService
  ├── EmbeddingService
  │     └── approved embedding provider abstraction
  └── VectorStore (existing application-owned port)
        └── QdrantClientAdapter (existing infrastructure adapter)
              └── knowledge_vectors_active alias
```

The RetrievalService must not import Qdrant SDK types, HTTPX, FastAPI, database models, or provider-specific embedding adapters. It depends on the application-owned `EmbeddingService` and `VectorStore` contracts. The Qdrant adapter remains the only production module that translates Qdrant SDK request/response models.

The query-embedding composition and lifecycle wiring must reuse the application-owned `EmbeddingService`. No new network I/O may be introduced during FastAPI startup; query embedding and Qdrant search occur only when a retrieval operation is invoked.

## 6. Query Contract

A retrieval request represents one user/customer-support query, not an arbitrary Qdrant query.

Proposed logical input fields:

| Field | Meaning | Status |
| --- | --- | --- |
| `query` | Original natural-language query | Required |
| `limit` | Maximum number of returned chunks | Approved by R-3: default 5, range 1–20; no pagination in V1 |
| `filters` | Optional allowlisted metadata filters | Approved by R-5: exact-match allowlist and AND/OR composition; see §9 |
| `score_threshold` | Optional minimum similarity score | Excluded from V1 by approved R-4 |

Validation requirements:

- Query must be a string, non-empty after trimming leading/trailing whitespace for validation, and bounded by the configured `retrieval_max_query_length` (default 2000 Unicode code points). The length check applies to the original unmodified query.
- The original query is not rewritten, translated, summarized, or augmented by Retrieval V1.
- The query prefix is applied exactly once by the query-embedding boundary.
- The request must not accept collection names, aliases, raw Qdrant filters, vector values, or embedding model selection.
- Limit and filter cardinality must be bounded to prevent unbounded work.
- Query text and filter values are untrusted input and must never be interpolated into executable expressions.

Whitespace and maximum query length are approved by R-10. Result-limit semantics are approved by R-3; score-threshold exclusion is approved by R-4.

## 7. Query Embedding Contract

The query embedding must:

- Be produced by the typed `EmbeddingService.embed_query(query)` operation.
- Use the query-specific prefix and provider/model configuration encapsulated by `EmbeddingService` (current V1: `search_query: ` and `ollama:nomic-embed-text:v1.5`).
- Resolve to an embedding space explicitly compatible with the document embeddings in the active generation. Compatibility must not be inferred from vector dimension alone.
- Return exactly one vector containing 768 finite numeric values.
- Preserve provider-returned values; no normalization, truncation, padding, or dimension coercion is allowed.
- Use the existing bounded retry and timeout semantics where the approved query-embedding design permits reuse.
- Fail as a whole if the provider fails or returns malformed output; no search is issued with an invalid vector.
- Avoid logging the raw query or vector.

The approved Embeddings implementation currently exposes `embed_chunks(chunks)`, applies `search_document: `, and returns `EmbeddingResult`. R-1 is approved: amend the Embeddings subsystem with a typed `embed_query(query)` operation and an application-owned query result contract. Both document and query operations remain under `EmbeddingService`, including provider calls, operation-specific prefixes, configuration identity, dimension/finiteness validation, timeout, and retry semantics.

The query and document operations must identify their embedding space explicitly. For current V1, the Nomic model contract defines compatible document/query vectors despite their distinct task prefixes. A future provider/model change that is not explicitly compatible requires a new embedding configuration and a new document vector generation (including re-embedding and verification) before activation. Retrieval must not compare vectors across incompatible spaces.

## 8. Vector Search Contract

The application-owned search port must replace the current reserved `search(request: object) -> object` placeholder with typed request/result contracts only after this specification is approved.

Proposed request semantics:

- Search the fixed active alias `knowledge_vectors_active`.
- Supply the validated query vector, bounded result limit, and an optional typed metadata filter. The V1 search request has no score-threshold field.
- Never allow callers to choose a collection, alias, vector name, distance metric, or raw SDK filter object.
- Do not create, activate, delete, or otherwise mutate generations during search.
- Apply filters server-side in Qdrant; do not retrieve an unbounded candidate set and filter it in application memory.
- Use the existing Cosine collection configuration. Do not calculate a second, potentially inconsistent similarity score in application code.

Proposed successful result semantics:

- Return zero or more candidates, ordered by descending Qdrant similarity score.
- A no-match query is a successful result with an empty candidate tuple.
- Every candidate contains the original chunk payload fields needed by later context/source boundaries, plus the similarity score.
- Candidate values are application-owned immutable DTOs. Qdrant SDK models and raw responses never escape the adapter.
- Return only fields defined by the approved storage payload contract; do not invent business metadata.
- Preserve Qdrant's returned candidate order for equal scores; do not apply a secondary sort or promise stable tie ordering across calls (R-9).
- Do not claim that similarity score is a calibrated probability or a relevance percentage.

The exact Qdrant operation, score interpretation, and typed DTO schema must be finalized against the pinned client version during specification finalization and implementation planning. R-9 approves preservation of Qdrant's returned order for ties without a stability guarantee.

## 9. Metadata Filtering

Filtering must be explicit, typed, and allowlisted. Retrieval must not expose arbitrary Qdrant filter syntax.

Fields available in the approved payload/index schema:

| Field | Existing index | Candidate filter type |
| --- | --- | --- |
| `document_id` | Keyword | Exact value(s) |
| `source_path` | Keyword | Exact value(s) |
| `format` | Keyword | Exact value(s) |
| `chunking_config_id` | Keyword | Exact value(s) |
| `embedding_config_id` | Keyword | Exact value(s) |
| `chunk_index` | Integer | Excluded from caller filters in V1; returned as provenance only |
| `generation_id` | Keyword | Internal generation scoping only; caller must not override active alias |

Approved filter cardinality and composition (R-13):

- A request may contain at most 5 filter fields; this is the complete V1 allowlist.
- Each filter field may contain at most 20 values.
- Different filter fields are combined with logical AND.
- Multiple allowed values for one field are combined with logical OR.
- Empty filter values are rejected rather than interpreted as no filter.
- Unknown fields, unsupported operators, and cardinality violations are rejected before any Qdrant call.
- Filters are applied within the active generation only.
- No implicit customer, tenant, or authorization filter is invented. If tenant isolation becomes a requirement, it must be designed from an authoritative domain contract before exposing retrieval to customer data.

R-5 approves exact-match filtering and multi-value OR semantics for the five allowlisted fields. R-13 approves a maximum of 5 distinct filter fields per request and 20 distinct values per field. Integer range filtering is unsupported, and `chunk_index` filtering (exact or range) is excluded from V1 by R-6. The stored `chunk_index` remains in each returned candidate as provenance.

## 10. Ranking, Thresholds, and Hybrid Search

### 10.1 Dense semantic ranking

The existing storage schema supports dense Cosine similarity only. V1 can therefore define dense semantic retrieval without a storage migration.

Candidates are ordered by descending similarity score. The score is a ranking signal, not a probability and not a guarantee that the chunk answers the query.

### 10.2 Score threshold

A score threshold can remove weak candidates, but a useful threshold is model/corpus/query-distribution dependent. No threshold may be selected from intuition alone and presented as an evidence-based relevance boundary.

**Approved decision R-4:** Retrieval V1 has no score-threshold field and applies no default or caller-supplied threshold. Return the top bounded candidates and record scores for offline evaluation. Reconsider thresholding only after an evaluation set provides evidence.

### 10.3 Reranking

**Approved decision R-7:** exclude model-based reranking from Retrieval V1. First establish a dense retrieval baseline and an evaluation dataset. A reranker adds latency, provider/model configuration, cost, failure modes, and another quality-sensitive stage; it may be specified separately only if evaluation demonstrates a measurable need.

### 10.4 Hybrid retrieval

**Approved decision R-2:** exclude sparse and hybrid search from V1. The approved collection has one dense vector and no sparse-vector schema or sparse-index lifecycle. Any future hybrid search requires a separate Vector Storage specification amendment, data rebuild, and comparative evaluation. It must not be approximated by silently combining unrelated scores.

## 11. Result Contract and Provenance

The proposed immutable candidate DTO contains:

| Field | Source | Purpose |
| --- | --- | --- |
| `chunk_id` | Stored payload | Stable chunk identity |
| `document_id` | Stored payload | Content-version identity |
| `source_path` | Stored payload | Source location within knowledge corpus |
| `title` | Stored payload | Human-readable source title |
| `format` | Stored payload | Source format |
| `content` | Stored payload | Exact stored chunk text for downstream context construction |
| `start_offset` | Stored payload | Inclusive source offset |
| `end_offset` | Stored payload | Exclusive source offset |
| `chunk_index` | Stored payload | Chunk order within the document |
| `chunking_config_id` | Stored payload | Chunking identity |
| `embedding_config_id` | Stored payload | Document embedding identity |
| `generation_id` | Stored payload | Generation that produced the candidate |
| `score` | Qdrant result | Dense similarity ranking signal |

**Approved response envelope (R-15):** the application-owned retrieval result contains:

```json
{
  "active_generation_id": "generation-123",
  "results": [
    {
      "chunk_id": "...",
      "generation_id": "generation-123",
      "content": "...",
      "score": 0.87
    }
  ]
}
```

The envelope's `active_generation_id` identifies the active generation against which the search was executed, including when `results` is empty. Each candidate retains its own stored `generation_id` as provenance. Every returned candidate MUST have a `generation_id` equal to the envelope's `active_generation_id`; any mismatch is a response-contract failure and no partial result is returned. A successful empty result still carries the verified active generation identity. The identity must be established from the trusted generation-level metadata defined by the required Vector Storage Amendment, not inferred from candidate payloads.

Provenance requirements:

- Payload metadata is returned unchanged after type/contract validation.
- A malformed or incomplete payload is not silently repaired or partially returned.
- The score is finite and represented using an application-owned numeric type.
- No source URL is invented from `source_path`; source-link resolution belongs to Source Attribution SDD.
- Retrieval does not summarize, trim, or rewrite `content`; downstream context construction owns presentation transformations while preserving source offsets.

## 12. Errors and Failure Semantics

**Approved decision R-16 — Retrieval-owned Error Taxonomy:** Retrieval owns the stable error contract exposed at its subsystem boundary. It maps upstream normalized Embeddings and Vector Storage failures into explicitly defined Retrieval-owned error types while preserving the original normalized exception as the chained cause (`__cause__`). This mapping is explicit per failure category; it must not indiscriminately wrap programming defects or erase useful retryability/diagnostic metadata.

Retrieval-owned categories:
- `InvalidRetrievalRequest`: invalid query, options, or metadata filters; non-retryable request-contract failure.
- `ActiveGenerationNotFound`: the active alias/generation is absent (R-8); distinct from an empty successful result.
- `IncompatibleEmbeddingSpace`: query embedding identity does not match the trusted active-generation identity; fail closed before Qdrant search.
- `RetrievalEmbeddingError`: a normalized Embeddings operation fails; preserve that normalized error as `__cause__` and do not issue vector search.
- `RetrievalVectorSearchError`: a normalized Vector Storage search operation fails; preserve that normalized error as `__cause__`.
- `RetrievalResponseContractError`: malformed candidate payload/score, missing required provenance, or candidate generation identity inconsistent with the result envelope; fail the whole operation and return no partial results.

Raw Qdrant SDK, HTTPX, provider-specific, and other infrastructure exceptions must never escape Retrieval. The Retrieval layer must not import or branch on those concrete exception types; translation begins from the upstream subsystem's normalized application-owned errors. Public messages/codes must be safe and stable, and must not expose raw exception text, credentials, URLs containing secrets, or stack traces.

Retry and control-flow rules:
- Retry ownership remains singular. EmbeddingService owns query-embedding retries; Vector Storage owns storage-operation retries. Retrieval adds no retry loop and does not retry upstream failures.
- Mapping must preserve relevant normalized metadata (including retryability and stable upstream code) in the internal cause/diagnostic context without making upstream implementation details part of the public Retrieval contract.
- Cancellation propagates unchanged and is never converted into a retryable service error. Never catch `BaseException` as an ordinary failure.
- Empty candidate results are successful responses, not errors.
- Any candidate/envelope generation mismatch fails the complete operation; no partial result is returned.
- **Approved decision R-18 — All-or-Nothing Failure Atomicity:** the Retrieval operation returns either one complete, contract-valid `RetrievalResult` or one failure. It MUST NOT return partial candidates when query embedding, active-generation compatibility checks, vector search, payload validation, or result-envelope validation fails. A successful empty candidate set remains a complete success, not a partial result.

**Approved decision R-19 — Overall Deadline with Stage Limits (option A):**

- Overall Retrieval deadline: **10 seconds** for one invocation, measured with a monotonic clock.
- Query-embedding stage timeout: **5 seconds maximum**.
- Vector-search stage timeout: **3 seconds maximum**.
- Each stage's effective timeout is the smaller of its configured stage limit and the remaining overall deadline. The overall deadline is authoritative; stage limits do not extend it.
- Do not start a new stage after the overall deadline expires. In particular, do not issue Vector Storage search if query embedding or compatibility checks consume the remaining deadline.
- Retries performed inside EmbeddingService or Vector Storage consume the same stage and overall time budget. No retry may reset or extend the Retrieval deadline; Retrieval itself adds no retry loop.
- If the overall deadline expires, fail the complete operation with the Retrieval-owned `RetrievalDeadlineExceeded` error. If an upstream stage-specific timeout occurs before the overall deadline, map it according to R-16 while preserving the normalized cause.
- Deadline expiration does not permit partial results. Caller/task cancellation remains distinct and propagates unchanged.

**Approved decision R-20 — Bounded Concurrency (option A):** Retrieval must enforce a bounded in-process concurrency limit and a finite waiting queue. Requests may wait only while capacity is expected to become available and only within their existing R-19 overall deadline. A full waiting queue rejects new work immediately with the Retrieval-owned `RetrievalCapacityExceeded` error. A request already waiting whose overall deadline expires fails with `RetrievalDeadlineExceeded`, not a capacity error. No unbounded queue, unbounded wait, or unbounded accumulation of pending request state is permitted.

The concurrency limit and queue capacity are intentionally **not assigned numeric values by R-20**. They must be selected during task breakdown using measured resource capacity and the actual configured deployment topology, including worker/process/replica multiplication and upstream Embeddings/Qdrant capacity. The limit is per application process unless a separately approved distributed coordination mechanism is specified; do not imply a deployment-wide global limit from a process-local semaphore. Queue waiting consumes the same overall deadline and must not reset stage budgets. Cancellation while queued removes the waiter without consuming a concurrency slot or starting downstream work.

This section covers retrieval-operation semantics only. Cross-stage RAG fallback, degraded answer policy, and user-facing messaging remain in the separate RAG Failure Handling SDD.

## 13. Security and Observability

Security:

- Query and filter inputs are untrusted.
- Only the typed allowlisted filter fields/operators may reach the storage adapter.
- Callers cannot select an arbitrary collection or bypass the active alias.
- Do not log query text, chunk content, vectors, API keys, or raw provider/Qdrant response bodies.
- Do not expose raw SDK exceptions, URLs containing credentials, or internal stack traces in public error messages.
- No authorization or tenant isolation behavior may be inferred. Such behavior requires an authoritative domain/security contract before customer-facing exposure.

**Approved decision R-17 — Structured Metadata Observability (option A):** emit a structured metadata-only event for each completed Retrieval operation, including successful empty results and failures. The event contract includes:

| Field | Meaning / constraint |
| --- | --- |
| `correlation_id` | Propagate the caller/request correlation identifier when supplied by the surrounding request contract; Retrieval does not invent a new cross-system identity. |
| `active_generation_id` | Trusted active generation identity, when resolved. |
| `embedding_config_id` | Query embedding configuration identity, when available. |
| `requested_limit` | Validated result limit. |
| `result_count` | Number of candidates returned; zero for successful empty results. |
| `filter_field_names` | Names of applied allowlisted fields only; never filter values. |
| `embedding_duration_ms` | Time spent in the query-embedding stage, when that stage was entered. |
| `vector_search_duration_ms` | Time spent in the Vector Storage search stage, when that stage was entered. |
| `total_duration_ms` | Total elapsed Retrieval operation duration. |
| `retry_count` | Total upstream retries reported by the Embeddings and Vector Storage boundaries; Retrieval itself performs no retries. Preserve stage-level retry counts in structured attributes where available. |
| `outcome` | Bounded outcome classification, such as `success` or `failure`. |
| `error_code` | Stable Retrieval-owned error code on failure; absent on success. |

Telemetry must never contain raw query text, chunk content, vectors, filter values, credentials, raw provider/storage response bodies, or exception text. Missing stage values are represented as absent/null rather than fabricated. The event must distinguish a successful empty result (`outcome=success`, `result_count=0`) from a failure.

The exact logger/metrics exporter and correlation-ID integration point may follow the project's shared observability infrastructure; this decision defines the Retrieval event fields and privacy boundary, not a new telemetry platform. Telemetry emission must not change the Retrieval result/error contract or introduce a second retry path.


## 14. Approval Decisions

The following table records the owner decisions. Rows marked **Approved** are binding requirements for the subsequent specification finalization and task breakdown; they do not independently authorize implementation.

| ID | Decision required | Current recommendation | Why approval is required |
| --- | --- | --- | --- |
| R-1 | Query embedding ownership | **Approved:** Add typed `EmbeddingService.embed_query(query)` alongside `embed_chunks()`. The EmbeddingService owns provider/model identity, operation-specific prefixes, configuration identity, validation, timeout, and retry behavior. Query/document vectors must share an explicitly compatible embedding-space identity; equal dimensions alone are insufficient. | Keeps embedding concerns behind one boundary and prevents Retrieval from coupling to a provider/model or comparing incompatible vector spaces. |
| R-2 | V1 retrieval mode | **Approved:** Dense semantic search only, using the existing dense 768-dimensional Cosine vector through `knowledge_vectors_active`. Sparse and hybrid search are excluded from V1; any future hybrid capability requires a separate Vector Storage specification amendment, generation rebuild plan, and comparative evaluation. | Establishes a measurable dense baseline without expanding the approved storage schema; hybrid can be considered only with evidence and an explicit storage change. |
| R-3 | Result limits | **Approved:** `limit` defaults to 5 and has a maximum of 20. Values below 1 or above 20 are rejected before any Qdrant call. Retrieval V1 does not support pagination. | Bounds Qdrant work and downstream context size while keeping the request contract explicit; evaluation may inform a future revision.
| R-4 | Score threshold | **Approved:** Exclude `score_threshold` from the Retrieval V1 request contract; do not apply a default or caller-supplied threshold. Return the top bounded candidates ordered by similarity. Reconsider only after retrieval evaluation provides evidence. | Similarity scores are ranking signals, not calibrated relevance probabilities; an arbitrary threshold could discard useful evidence.
| R-5 | Metadata filters | **Approved:** Exact-match allowlist only for `document_id`, `source_path`, `format`, `chunking_config_id`, and `embedding_config_id`. Combine different fields with AND and multiple values within one field with OR. Reject unknown fields, unsupported operators, and empty values before Qdrant; apply filters server-side. | Uses existing indexed payload fields and provides bounded semantics without exposing raw Qdrant filters or inventing range behavior. |
| R-6 | `chunk_index` filtering | **Approved:** Exclude `chunk_index` from Retrieval V1 metadata filters, including exact-value and range filters. The field remains part of returned provenance. | No current business requirement justifies exposing positional filtering; exclusion keeps the filter contract narrow without discarding provenance needed downstream. |
| R-7 | Reranking | **Approved:** Exclude model-based reranking from Retrieval V1. Establish and evaluate the dense retrieval baseline first; any future reranker requires a separate specification backed by measurable quality, latency, and cost evidence. | A reranker adds another model, latency, cost, configuration, and failure modes before a baseline demonstrates a need. |
| R-8 | Missing active alias | **Approved:** Raise the normalized application-owned `ActiveGenerationNotFound` error when `knowledge_vectors_active` is absent. Do not convert this condition into an empty successful result. | Distinguishes an uninitialized/unavailable active knowledge generation from a valid query that has no matches. |
| R-9 | Equal-score ordering | **Approved:** Preserve the order returned by Qdrant for equal scores. Do not add a secondary sort and do not promise stable tie ordering across calls in V1. | Avoids extra application sorting without claiming that a tie-breaker improves relevance. |
| R-10 | Query length and whitespace | **Approved:** Reject a query that is empty after trimming leading/trailing whitespace; preserve and embed the original unmodified query. Enforce the maximum against the original string's Unicode code-point length using configurable `retrieval_max_query_length`, default `2000`, validated as an integer greater than zero. | Provides bounded input while allowing deployment-specific configuration and keeping validation separate from the exact text embedded. |
| R-11 | Result payload | **Approved:** Return all stored provenance fields and exact stored chunk content unchanged, together with the similarity score, in each candidate. | Downstream Context Construction and Source Attribution need the original evidence and complete provenance without another storage lookup. |
| R-12 | Retrieval composition | **Approved:** Reuse the existing application-owned `EmbeddingService` and `VectorStore`, wire them through the composition root, and perform no network I/O during FastAPI startup. Query embedding and Qdrant search occur only when a retrieval operation is invoked. | Preserves dependency boundaries and startup lifecycle guarantees while avoiding duplicate infrastructure capabilities. |
| R-13 | Filter cardinality | **Approved:** A request may contain at most 5 filter fields (the complete allowlist) and at most 20 values per field. Reject cardinality violations before any Qdrant call. | Bounds filter complexity while preserving the approved exact-match AND/OR semantics. |
| R-14 | Vector Storage Amendment sequencing | **Approved — sequencing only:** Complete Retrieval SDD and its dependency-ordered task breakdown first. Then create and approve a separate Vector Storage specification amendment and its implementation/verification tasks. Retrieval implementation is blocked until that amendment is implemented, verified, and closed. The technical amendment contract itself is not approved by this sequencing decision. | Keeps the current SDD review focused while making the upstream contract change an explicit, non-bypassable implementation dependency. |
| R-15 | Retrieval result envelope generation identity | **Approved:** Return `active_generation_id` at the result-envelope level and retain `generation_id` in every candidate. The envelope identifies the generation searched even when the result set is empty. Every candidate generation ID must equal the envelope identity; otherwise fail the entire operation with a response-contract error and return no partial results. The envelope identity must come from trusted generation-level metadata established by the required Vector Storage Amendment. | Makes empty-result provenance explicit and enforces that every candidate belongs to the exact active generation searched. |
| R-16 | Retrieval error taxonomy ownership | **Approved:** Retrieval owns its stable boundary error taxonomy and maps normalized Embeddings/Vector Storage errors into Retrieval-owned typed errors, preserving the original normalized exception as `__cause__`. Mapping is explicit; Retrieval adds no retry loop, cancellation propagates, and raw infrastructure exceptions never escape. | Keeps the Retrieval contract independent of upstream subsystem taxonomies while retaining diagnostic causes and single-owner retry semantics. |
| R-17 | Retrieval observability | **Approved:** Emit structured metadata-only events containing correlation ID (when supplied), active generation and embedding config identities, requested limit, result count, filter field names only, embedding/search/total durations, upstream retry count, outcome, and stable Retrieval error code on failure. Never log query text, chunk content, vectors, filter values, credentials, or raw exception/provider/storage payloads. | Enables stage-level latency and failure diagnosis while keeping customer content and sensitive inputs out of telemetry. |
| R-18 | Failure atomicity | **Approved:** Retrieval is all-or-nothing. Return either a complete contract-valid result (including a valid empty result) or a failure; never return partial candidates after any stage or response-contract failure. | Prevents downstream consumers and agents from treating incomplete evidence as a complete retrieval outcome. |
| R-19 | Retrieval timeout policy | **Approved:** Use a 10-second overall deadline, a maximum 5-second query-embedding stage timeout, and a maximum 3-second vector-search stage timeout. Each stage is capped by the remaining overall budget; retries consume the same budget and cannot reset it. Overall expiry raises `RetrievalDeadlineExceeded`; upstream stage timeouts follow R-16 mapping. | Gives the caller a hard upper bound while retaining stage-level latency diagnosis and preventing retries from extending request lifetime. |
| R-20 | Retrieval concurrency and admission control | **Approved:** Enforce bounded in-process concurrency and a finite waiting queue. Queue waiting consumes the R-19 overall deadline. Reject immediately with `RetrievalCapacityExceeded` when the waiting queue is full; a queued request whose deadline expires receives `RetrievalDeadlineExceeded`. Numeric concurrency/queue capacities are deferred to evidence-based task breakdown and must account for deployment process/replica multiplication and upstream capacity. | Prevents unbounded resource growth while distinguishing admission rejection from expiration of an accepted request's deadline. |
| R-21 | Retrieval caching | **Approved:** No Retrieval query-result cache in V1. Every accepted invocation performs the approved query-embedding and active-generation vector-search flow. Reconsider caching only after baseline evaluation demonstrates a measurable need and a separate design defines generation/config/filter-aware cache identity, invalidation, freshness, and bounded resource behavior. | Establishes an uncached retrieval baseline and avoids stale-generation results and premature cache-invalidation complexity. |

R-1 through R-13 and R-15 through R-21 are approved. R-14 is approved for sequencing only: finish Retrieval SDD and its task breakdown, then complete a separate Vector Storage amendment and its verification before any Retrieval implementation. The technical details of that amendment remain unapproved. The specification remains a draft until the final consistency review and dependency-ordered implementation task breakdown are completed and explicitly approved. No implementation is authorized by the decision approvals alone.

## 15. Testing and Verification Requirements

Tests are to be finalized in the dependency-ordered task breakdown now that decisions in §14 are approved. At minimum, the test plan must cover:

1. Query validation, whitespace behavior, maximum length, and invalid limits.
2. Query prefix applied exactly once through `EmbeddingService`; query/document vectors use an explicitly compatible embedding-space identity and the pinned V1 configuration.
3. Query embedding returns one finite 768-dimensional vector; malformed provider output prevents storage search.
4. Query embedding failures preserve normalized error semantics and do not trigger a second search.
5. Retrieval uses only `knowledge_vectors_active`; callers cannot choose a collection or alias.
6. Correct typed request translation to the VectorStore port and Qdrant adapter.
7. Dense ranking order, limit behavior, empty-result success, and score validation.
8. Exact metadata filter semantics, unknown-field rejection, and server-side filtering.
9. Missing active alias and unavailable Qdrant produce distinct normalized errors.
10. Malformed/missing payload fields cause a safe contract failure with no partial result.
11. Qdrant SDK models and exceptions do not escape the adapter boundary.
12. No query text, chunk content, vectors, or secrets appear in logs/errors.
13. No network I/O occurs during application startup; retrieval network calls occur only when invoked.
14. Offline unit tests use fakes and require no Ollama or Qdrant.
15. Opt-in live Ollama query-embedding conformance and container-backed Qdrant retrieval integration tests are explicitly gated and clean up their test-owned resources.
16. Overall deadline and per-stage timeout enforcement use a monotonic clock; retries consume the same remaining budget, no stage starts after expiry, overall expiry maps to `RetrievalDeadlineExceeded`, and cancellation propagates unchanged.
17. Bounded concurrency and finite queue admission are enforced per process; queue-full requests fail immediately with `RetrievalCapacityExceeded`; queued requests respect the overall deadline; cancellation removes queued waiters; capacity settings are tested against configured process/replica topology.
18. Retrieval V1 performs no query-result cache reads or writes; repeated equivalent requests follow the normal embedding/search path and active-generation changes cannot expose stale cached candidates.
19. Full regression preserves ingestion, chunking, embeddings, vector-storage lifecycle, domain, and LLM behavior.

The final task breakdown must split offline contract/unit tests from opt-in live provider/Qdrant integration where appropriate and define measurable acceptance criteria for each task.

## 16. Acceptance Criteria (Draft)

This specification can be submitted for final approval only when:

- All decisions in §14 have explicit owner outcomes; R-1 through R-13 and R-15 through R-21 are approved, and R-14 sequencing is approved. The technical Vector Storage Amendment remains a blocking dependency and is not yet approved.
- R-1 query embedding ownership is approved; the Embeddings specification amendment must be included in the approved Retrieval implementation task breakdown before implementation.
- The separate Vector Storage Amendment must be specified, approved, implemented, verified, and closed after Retrieval SDD/task-breakdown approval but before any Retrieval implementation task is authorized.
- The typed search request/result contracts are precise and compatible with the existing VectorStore boundary. Filter cardinality is fixed at no more than 5 allowlisted fields and 20 values per field.
- Active-alias and missing-alias behavior, filter allowlist and composition, limit (default 5, maximum 20, no pagination), score-threshold exclusion, tie ordering, configurable query validation, full payload, and composition semantics are unambiguous.
- Context Construction, Source Attribution, Evaluation, and RAG Failure Handling boundaries remain explicit.
- Test and security requirements are accepted.
- No implementation task is inferred from this draft.

After approval, create a separate dependency-ordered task breakdown. Implementation begins only after that breakdown is approved and a single task is explicitly authorized.

## 17. References

- `specs/roadmap.md` — Phase 4 RAG roadmap.
- `specs/rag/knowledge-document-ingestion.md` — ingestion source contract.
- `specs/rag/knowledge-document-chunking.md` — chunk and provenance contract.
- `specs/rag/knowledge-document-embeddings.md` — provider/model, document/query prefixes, vector identity, and embedding behavior.
- `specs/rag/knowledge-vector-storage.md` — active generation, payload, Qdrant boundary, and reserved search port.
- `specs/project-state.md` — verified implementation state through T278.
