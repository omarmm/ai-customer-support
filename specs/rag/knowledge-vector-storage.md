# Knowledge Vector Storage Specification

- **Status:** Draft — pending specification review and approval
- **Phase:** Phase 4 — RAG
- **Subsystem:** Vector Storage
- **Implementation:** Not authorized
- **Task breakdown:** Not authorized

## 1. Purpose

Specify the persistence boundary for storing knowledge chunk embeddings in Qdrant. This subsystem consumes the existing ingestion, chunking, and embeddings outputs; it does not reimplement those stages.

Vector Storage and Retrieval are separate specification boundaries. This document covers storage and generation lifecycle only. Retrieval behavior requires its own specification and approval.

## 2. Scope

### 2.1 In scope

- Qdrant integration behind an application-owned storage abstraction.
- Collection/vector configuration.
- Deterministic point identity and payload contract.
- Immutable vector generations and active-generation alias management.
- Full-generation rebuild and activation lifecycle.
- Explicit generation retention/deletion rules.
- Qdrant client configuration and bounded transient retries.
- Docker Compose readiness configuration.
- Required payload indexes.
- Metadata-only structured observability.
- Storage unit/integration tests and verification requirements.

### 2.2 Out of scope

- Semantic/hybrid retrieval and query embedding.
- Similarity-search behavior and retrieval-time filtering semantics.
- Reranking, context construction, prompt assembly, grounded generation, and citations.
- Retrieval evaluation.
- PostgreSQL generation manifests or a second generation-state source of truth in V1.
- Changes to ingestion, chunking, or embedding contracts.
- Agent/tool integration.

These require separate specifications and approval.

## 3. Existing Contracts and System Boundaries

The storage subsystem consumes the output of the approved embeddings subsystem. It must preserve the existing chunk identity, provenance, embedding configuration identity, and validated vector values. It must not silently alter chunk text, metadata, vector dimension, or vector values.

The currently approved embedding model is `nomic-embed-text:v1.5`; its observed vector dimension is 768. The embeddings subsystem remains authoritative for producing and validating embeddings.

PostgreSQL remains the source of truth for transactional and business data. Qdrant is the vector store for RAG and does not replace PostgreSQL.

## 4. Approved Architecture Decisions

The following decisions were approved in the Day 27 architecture discussion and are binding constraints for this specification.

| ID | Decision |
| --- | --- |
| D1 | Vector Storage and Retrieval are separate specifications. This document specifies storage only. |
| D2 | Use immutable vector generations and an atomic Qdrant alias switch to identify the active generation. |
| D3 | Derive generation identity deterministically from the storage/embedding configuration identity and corpus digest. |
| D4 | Derive Qdrant point IDs using UUIDv5 with a fixed namespace; preserve the original `chunk_id` in the payload. |
| D5 | Store chunk text together with its metadata in the Qdrant payload. |
| D6 | Use the official, version-pinned `qdrant-client` behind an application-owned `VectorStore` abstraction. |
| D7 | Use Cosine distance. |
| D8 | Use a Qdrant alias to identify and switch the active generation. Do not add a PostgreSQL generation manifest in V1. |
| D9 | Rebuild each generation in full; incremental mutation of an existing generation is out of scope for V1. |
| D10 | Keep this subsystem storage-only. Retrieval behavior belongs to a separate specification. |
| D11 | Use a 10-second Qdrant client timeout, batch size 64, optional API key, and bounded retries for transient failures only. |
| D12 | Pin the Qdrant container image, configure a healthcheck, and make the API Compose service depend on Qdrant's `service_healthy` condition. |
| D13 | Retain the previous generation after activation. Do not perform automatic cleanup. Explicit deletion of the active generation must be rejected. |
| D14 | FastAPI application startup must perform no Qdrant network I/O. |
| D15 | Create keyword payload indexes for `generation_id`, `document_id`, `source_path`, `format`, `chunking_config_id`, and `embedding_config_id`; create an integer index for `chunk_index`. |
| D16 | Emit structured metadata-only observability containing generation ID, record count, batch count, duration, outcome, and retry count. Never log document/chunk content, vectors, or API keys. |

### 4.1 D12 and D14 — infrastructure/application boundary

D12 and D14 apply at different layers and must both be honored:

- Docker Compose controls container startup ordering: the API service depends on Qdrant reaching `service_healthy`.
- FastAPI startup code itself performs no Qdrant network request and does not run a connectivity check.
- The existing application `/health` endpoint remains independent of Qdrant availability.

The Compose dependency is infrastructure orchestration; it does not authorize application startup network I/O.

## 5. Storage Model

### 5.1 Generations

- A generation is an immutable collection of knowledge chunk vectors.
- Generation identity is deterministic and follows D3.
- A new generation is built separately from the active generation.
- The active generation is selected through a Qdrant alias.
- Existing generation contents are not mutated in place.
- The previously active generation is retained after a successful activation.

### 5.2 Point identity

- Each Qdrant point ID is a deterministic UUIDv5.
- UUIDv5 uses one fixed namespace.
- The original application `chunk_id` is retained in the payload.
- The same logical chunk identity must not receive a random point ID on repeated builds.

The exact namespace UUID and canonical UUIDv5 name input are still specification details to finalize. They must be explicit constants/rules before implementation approval; an implementation agent must not invent them.

### 5.3 Payload

The payload stores chunk text and its provenance/configuration metadata. It must preserve the original `chunk_id` and the fields required by D15.

The exact payload field names, types, nullability, and source mapping must be finalized in this specification before implementation approval. No extra business fields may be invented during implementation.

### 5.4 Vector configuration

- Distance metric: Cosine.
- Vector dimension: 768, matching the currently verified embeddings contract.
- Storage validates vector compatibility with the approved embeddings contract.
- Storage does not silently normalize, truncate, pad, or otherwise transform vectors.

## 6. Generation Lifecycle

The V1 lifecycle is:

1. Compute the target generation identity from the approved configuration identity and corpus digest.
2. Create/build the target generation separately from the active generation.
3. Write points in batches of 64.
4. Verify that the target generation build completed successfully.
5. Switch the active Qdrant alias to the completed generation atomically.
6. Retain the previously active generation.
7. Delete an inactive generation only through an explicit operation.

A failed or incomplete build must not replace the currently active generation.

### 6.1 Rebuild policy

- V1 performs full generation rebuilds.
- Incremental updates to an existing generation are not supported.
- A generation must not become active before its build has completed successfully.
- A failed build leaves the active alias unchanged.

### 6.2 Retention and deletion

- Automatic generation cleanup is prohibited.
- Explicit deletion may target an inactive generation.
- Deletion of the active generation must be rejected.
- Deletion must not implicitly move or remove the active alias.

## 7. Qdrant Client and Infrastructure

### 7.1 Client boundary

- Use the official `qdrant-client` package at an explicitly pinned version.
- Keep Qdrant SDK calls behind the application-owned `VectorStore` abstraction.
- Domain/application-facing code must not depend directly on Qdrant SDK client objects or SDK-specific models.

The exact package version must be selected and recorded before implementation approval.

### 7.2 Connection and retry configuration

- Qdrant URL is supplied through application configuration.
- API key is optional.
- Client timeout is 10 seconds.
- Write batch size is 64.
- Retries are bounded and apply only to transient failures.
- Permanent validation, contract, and configuration failures are not retried.

The exact retry count/backoff values and Qdrant status-to-error mapping must be finalized before implementation approval.

### 7.3 Docker Compose

- Pin the Qdrant image to an explicit version; do not use a floating `latest` tag.
- Configure a Qdrant healthcheck.
- Configure the API service dependency using `condition: service_healthy`.
- Preserve the repository's project-scoped Docker network and named-volume conventions.

The exact Qdrant image version and healthcheck command, interval, timeout, retries, and start period must be recorded before implementation approval.

### 7.4 FastAPI startup

- Construct storage dependencies without Qdrant network I/O during FastAPI startup.
- Application startup must not require a successful Qdrant request.
- The existing `/health` endpoint must not become a Qdrant connectivity check.

## 8. Payload Indexes

Create these payload indexes:

| Field | Index type |
| --- | --- |
| `generation_id` | Keyword |
| `document_id` | Keyword |
| `source_path` | Keyword |
| `format` | Keyword |
| `chunking_config_id` | Keyword |
| `embedding_config_id` | Keyword |
| `chunk_index` | Integer |

These are storage-schema requirements. They do not define retrieval query behavior.

## 9. Error Handling

The finalized storage error contract must distinguish:

- Connection failures.
- Request timeouts.
- Transient Qdrant/service availability failures.
- Permanent client/configuration failures.
- Invalid storage contracts, including incompatible vector dimensions or malformed point data.
- Generation build failures.
- Alias activation failures.
- Rejected deletion of an active generation.

Only transient failures are eligible for the bounded retry policy. Permanent contract and configuration failures fail without retry.

Stable reason codes, exception boundaries, and exact retryable/permanent Qdrant error mappings must be finalized before implementation approval.

## 10. Observability and Security

Emit structured metadata containing:

- Generation ID.
- Record count.
- Batch count.
- Duration.
- Outcome.
- Retry count.

Never log raw document content, chunk text, embedding vectors, Qdrant API keys, or other secrets. Exception/log formatting must not leak credentials.

## 11. Testing and Verification Requirements

The implementation specification must require tests for:

- Deterministic UUIDv5 point identity and fixed namespace/name derivation.
- Preservation of the original `chunk_id`.
- Payload field names, types, nullability, and required metadata.
- Cosine vector configuration and dimension compatibility.
- Payload index creation and index types.
- Generation creation and immutable-generation behavior.
- Full rebuild behavior.
- Alias activation only after successful completion.
- Failed build leaves the active alias unchanged.
- Retention of the previous active generation.
- Rejection of active-generation deletion.
- Explicit deletion of an inactive generation.
- Batch size 64 and 10-second timeout configuration.
- Optional API key handling without secret leakage.
- Bounded retries for transient failures only.
- No retries for permanent failures.
- No Qdrant network I/O during FastAPI startup.
- Docker Compose healthcheck and `service_healthy` dependency.
- Structured metadata-only observability.
- Regression of existing ingestion, chunking, and embeddings behavior.

Tests must not require paid external AI services. Qdrant integration tests use the project's local/containerized infrastructure or controlled test doubles according to the finalized test design.

## 12. Open Specification Decisions

The architecture decisions D1–D16 are approved. The following lower-level contract details remain open and must be resolved during specification review, not invented during implementation:

1. Exact generation ID canonicalization and digest algorithm/input serialization.
2. Fixed UUIDv5 namespace value and canonical name input.
3. Complete payload schema: field names, types, nullability, and source mapping.
4. Collection naming convention and whether one collection is created per generation.
5. Exact pinned `qdrant-client` package version.
6. Exact pinned Qdrant image version and healthcheck parameters.
7. Exact retry count/backoff policy and Qdrant error/status mapping.
8. Exact generation build verification criteria before alias activation.
9. Explicit behavior for an interrupted build and cleanup of an incomplete, never-active generation.
10. Whether collection/vector configuration is validated on startup, first storage operation, or an explicit provisioning operation, while preserving D14's no-network-I/O startup rule.
11. Exact interface methods and result/error contracts for the application-owned `VectorStore` abstraction.

Any proposed choice must be discussed and approved before this draft is revised to an approved specification.

## 13. Acceptance Criteria

This specification is ready for approval only when:

1. D1–D16 are represented without changing their approved meaning.
2. Storage and Retrieval remain separate boundaries.
3. Generation identity inputs and canonical digest construction are unambiguous.
4. UUIDv5 namespace and canonical name input are explicit.
5. The exact payload schema and field types are defined.
6. Collection/generation naming and collection-per-generation behavior are explicit.
7. The pinned `qdrant-client` version is specified.
8. The Qdrant image version and healthcheck parameters are specified.
9. Retryable and permanent Qdrant failures have explicit stable mappings.
10. Build, activation, interruption, retention, and deletion behavior is deterministic.
11. D12/D14 are reconciled exactly as described in §4.1.
12. Test and verification requirements are objectively verifiable.
13. Retrieval behavior has not leaked into this storage specification.

## 14. Implementation Gate

- This document is a draft and does not authorize implementation.
- No task breakdown is approved by this document.
- No Qdrant integration code, settings, dependencies, startup wiring, endpoint, or persistence changes may be made before explicit specification approval.
- After approval, implementation tasks must be individually scoped with dependencies and acceptance criteria.
- Only one authorized task may be implemented at a time, followed by tests and verification before proceeding.

## 15. Approval Record

- **Status:** Draft — pending review.
- **Architecture decisions:** D1–D16 approved in the Day 27 architecture discussion.
- **Specification approval:** Pending.
- **Implementation authorization:** Not granted.
- **Task breakdown authorization:** Not granted.
