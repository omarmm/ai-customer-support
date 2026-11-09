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
- Hybrid dense/sparse search. The approved V1 collection contains one dense vector configuration; adding sparse vectors or a hybrid index requires a storage-schema amendment and rebuild plan.
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
7. Emit metadata-only retrieval telemetry.

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

The query-embedding composition and lifecycle wiring must reuse the application-owned `EmbeddingService`. No new network I/O may be introduced during FastAPI startup; query embedding and Qdrant search occur only when a retrieval operation is invoked. In particular, no new network I/O may be introduced during FastAPI startup; query embedding and Qdrant search occur only when a retrieval operation is invoked.

## 6. Query Contract

A retrieval request represents one user/customer-support query, not an arbitrary Qdrant query.

Proposed logical input fields:

| Field | Meaning | Status |
| --- | --- | --- |
| `query` | Original natural-language query | Required |
| `limit` | Maximum number of returned chunks | Proposed; default and maximum require approval |
| `filters` | Optional allowlisted metadata filters | Proposed; exact shape and semantics require approval |
| `score_threshold` | Optional minimum similarity score | Proposed; enablement and default require approval |

Validation requirements to approve:

- Query must be a string, non-empty after validation, and bounded in length.
- The original query is not rewritten, translated, summarized, or augmented by Retrieval V1.
- The query prefix is applied exactly once by the query-embedding boundary.
- The request must not accept collection names, aliases, raw Qdrant filters, vector values, or embedding model selection.
- Limit and filter cardinality must be bounded to prevent unbounded work.
- Query text and filter values are untrusted input and must never be interpolated into executable expressions.

Whitespace policy, maximum query length, default/max result limit, and score-threshold semantics remain approval decisions (§14).

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
- Supply the validated query vector, bounded result limit, optional score threshold, and a typed metadata filter.
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
- Preserve Qdrant's returned candidate order for equal scores unless a deterministic tie-break rule is explicitly approved.
- Do not claim that similarity score is a calibrated probability or a relevance percentage.

The exact Qdrant operation, score interpretation, tie behavior, and typed DTO schema must be finalized against the pinned client version during specification review and implementation planning.

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
| `chunk_index` | Integer | Exact value or bounded range (range requires decision) |
| `generation_id` | Keyword | Internal generation scoping only; caller must not override active alias |

Proposed filter composition:

- Different filter fields are combined with logical AND.
- Multiple allowed values for one field are combined with logical OR.
- Empty filter values are rejected rather than interpreted as no filter.
- Unknown fields and unsupported operators are rejected before any Qdrant call.
- Filters are applied within the active generation only.
- No implicit customer, tenant, or authorization filter is invented. If tenant isolation becomes a requirement, it must be designed from an authoritative domain contract before exposing retrieval to customer data.

Whether V1 supports only exact-match filters or also integer ranges, and whether multi-value filters are required, remain approval decisions.

## 10. Ranking, Thresholds, and Hybrid Search

### 10.1 Dense semantic ranking

The existing storage schema supports dense Cosine similarity only. V1 can therefore define dense semantic retrieval without a storage migration.

Candidates are ordered by descending similarity score. The score is a ranking signal, not a probability and not a guarantee that the chunk answers the query.

### 10.2 Score threshold

A score threshold can remove weak candidates, but a useful threshold is model/corpus/query-distribution dependent. No threshold may be selected from intuition alone and presented as an evidence-based relevance boundary.

**Recommendation:** begin V1 with no default threshold (return the top bounded candidates), record scores in offline evaluation, and introduce a threshold only after a retrieval evaluation set supports it. Whether callers may supply an optional threshold in V1 remains an approval decision.

### 10.3 Reranking

**Recommendation:** exclude model-based reranking from Retrieval V1. First establish a dense retrieval baseline and an evaluation dataset. A reranker adds latency, provider/model configuration, cost, failure modes, and another quality-sensitive stage; it should be specified separately if evaluation demonstrates a measurable need.

### 10.4 Hybrid retrieval

**Recommendation:** exclude hybrid search from V1. The approved collection has one dense vector and no sparse-vector schema or sparse-index lifecycle. Hybrid search would require a separate Vector Storage specification amendment, data rebuild, and comparative evaluation. It must not be approximated by silently combining unrelated scores.

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

The retrieval result also carries the requested/active generation identity when it can be established safely by the search boundary. The precise response envelope and whether generation identity is repeated at both envelope and candidate levels are review decisions.

Provenance requirements:

- Payload metadata is returned unchanged after type/contract validation.
- A malformed or incomplete payload is not silently repaired or partially returned.
- The score is finite and represented using an application-owned numeric type.
- No source URL is invented from `source_path`; source-link resolution belongs to Source Attribution SDD.
- Retrieval does not summarize, trim, or rewrite `content`; downstream context construction owns presentation transformations while preserving source offsets.

## 12. Errors and Failure Semantics

Retrieval must expose an application-owned error taxonomy. Raw Qdrant, HTTPX, and provider exceptions must not escape the subsystem boundary.

Proposed categories (exact stable codes and inheritance require approval):

- Invalid query/options/filter: non-retryable client-contract failure.
- Query embedding failure: preserve the normalized Embeddings error as the internal cause; do not issue vector search.
- Active generation missing: explicit unavailable/not-initialized condition, not a successful empty result.
- Vector search timeout/unavailable/transient failure: normalized storage/retrieval service failure, with retry behavior owned by the relevant adapter boundary.
- Invalid or incompatible active-generation vector metadata: configuration/contract failure; do not silently search a mismatched collection.
- Malformed returned payload/score: response-contract failure; do not return partial candidates.
- No matches: successful empty result, not an error.

Retry ownership must remain singular: Retrieval must not wrap the Qdrant adapter's retry policy in a second retry loop or retry a non-retryable normalized error. Query embedding retry behavior belongs to the approved Embeddings implementation. Cancellation must propagate and must not be converted into a retryable service error.

This section covers retrieval-operation semantics only. Cross-stage RAG fallback, degraded answer policy, and user-facing messaging remain in the separate RAG Failure Handling SDD.

## 13. Security and Observability

Security:

- Query and filter inputs are untrusted.
- Only the typed allowlisted filter fields/operators may reach the storage adapter.
- Callers cannot select an arbitrary collection or bypass the active alias.
- Do not log query text, chunk content, vectors, API keys, or raw provider/Qdrant response bodies.
- Do not expose raw SDK exceptions, URLs containing credentials, or internal stack traces in public error messages.
- No authorization or tenant isolation behavior may be inferred. Such behavior requires an authoritative domain/security contract before customer-facing exposure.

Metadata-only observability should be sufficient to investigate retrieval without storing sensitive content. Candidate fields for approval:

- operation/correlation ID (if the surrounding request contract provides one),
- active generation ID,
- query embedding model/config identity,
- requested limit,
- number of candidates returned,
- filter field names (not necessarily values),
- embedding duration,
- vector search duration,
- total retrieval duration,
- retry count,
- outcome/error code.

The exact telemetry schema and correlation-ID integration may be finalized with the project observability specification. Never emit raw query or chunk content.

## 14. Approval Decisions

The following decisions are intentionally unresolved. Recommendations are proposals for review, not approved requirements.

| ID | Decision required | Current recommendation | Why approval is required |
| --- | --- | --- | --- |
| R-1 | Query embedding ownership | **Approved:** Add typed `EmbeddingService.embed_query(query)` alongside `embed_chunks()`. The EmbeddingService owns provider/model identity, operation-specific prefixes, configuration identity, validation, timeout, and retry behavior. Query/document vectors must share an explicitly compatible embedding-space identity; equal dimensions alone are insufficient. | Keeps embedding concerns behind one boundary and prevents Retrieval from coupling to a provider/model or comparing incompatible vector spaces. |
| R-2 | V1 retrieval mode | Dense semantic search only. | Existing Qdrant schema contains one dense Cosine vector; hybrid requires storage-schema work. |
| R-3 | Result limits | Default top_k = 5; maximum top_k = 20. | Bounds Qdrant work and downstream context size; must be aligned with later Context Construction. |
| R-4 | Score threshold | No default threshold in V1; optionally leave the field out until evaluation. | Similarity scores are not calibrated relevance probabilities; threshold needs evaluation evidence. |
| R-5 | Metadata filters | Exact-match allowlist on document_id, source_path, format, chunking_config_id, embedding_config_id; AND across fields and OR within values. | Defines a safe, indexed, bounded contract without inventing range semantics. |
| R-6 | chunk_index filtering | Exclude from V1 filters. | No current business requirement; integer range semantics add surface area. |
| R-7 | Reranking | Exclude from V1. | Establish baseline first; reranking requires separate model/latency/cost evaluation. |
| R-8 | Missing active alias | Raise an explicit normalized ActiveGenerationNotFound error. | Distinguishes uninitialized knowledge base from a valid query with no matches. |
| R-9 | Equal-score ordering | Preserve Qdrant order; do not promise stable tie order in V1. | Stable secondary ordering may require extra work and is not a relevance guarantee. |
| R-10 | Query length and whitespace | Trim leading/trailing whitespace for validation, reject empty-after-trim; preserve the original query text for embedding; maximum 2,000 Unicode code points. | A bounded request contract is needed; exact maximum is proposed and must be approved. |
| R-11 | Result payload | Return all stored provenance fields and exact chunk content with the score. | Downstream Context Construction and Source Attribution need evidence and provenance. |
| R-12 | Retrieval composition | Construct/reuse query-embedding capability and the existing app-owned VectorStore at operation time; no startup network calls. | Avoids coupling or eager network I/O and preserves the existing lifecycle guarantees. |

Approval may accept, reject, or amend each recommendation. Any unresolved decision remains a blocker for the affected contract; implementation must not guess.

## 15. Testing and Verification Requirements

Tests are to be designed after the decisions in §14 are approved. At minimum, the approved test plan must cover:

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
16. Full regression preserves ingestion, chunking, embeddings, vector-storage lifecycle, domain, and LLM behavior.

The final task breakdown must split offline contract/unit tests from opt-in live provider/Qdrant integration where appropriate and define measurable acceptance criteria for each task.

## 16. Acceptance Criteria (Draft)

This specification is ready for approval only when:

- All decisions in §14 have explicit owner outcomes.
- R-1 query embedding ownership is approved; the Embeddings specification amendment must be included in the approved Retrieval implementation task breakdown before implementation.
- The typed search request/result contracts are precise and compatible with the existing VectorStore boundary.
- Active-alias, filter, limit, score, payload, and error semantics are unambiguous.
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
