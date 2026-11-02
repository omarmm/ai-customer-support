# Knowledge Vector Storage Specification

- **Status:** Draft — architecture decisions reviewed; final specification approval pending
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
- Each generation has one collection named `knowledge_vectors_g_<generation_id>`, using the full generation ID.
- The fixed active alias is `knowledge_vectors_active`.
- Generation identity is deterministic and derived using SHA-256 over canonical JSON.
- Canonical JSON serialization follows the existing Chunking and Embeddings convention: `json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`. The resulting SHA-256 digest is represented as lowercase hexadecimal. This exact convention applies to `corpus_digest`, `storage_config_id`, and `generation_id`.
- `corpus_digest` is SHA-256 over canonical JSON containing `corpus_version: "v1"` and the lexicographically sorted list of all `chunk_id` values. Chunks are the corpus unit; documents producing zero chunks contribute no IDs.
- `storage_config_id` is SHA-256 over canonical JSON containing `identity_version: "v1"`, `storage_schema_version: "v1"`, `payload_schema_version: "v1"`, `point_id_algorithm: "uuid5-v1"`, `distance_metric: "Cosine"`, `payload_index_schema_version: "v1"`, and `collection_layout: "one-collection-per-generation"`. Operational settings (Qdrant URL, API key, timeout, retries, batch size, and collection name) are excluded. Vector dimension is represented by `embedding_config_id` and is not duplicated here.
- The final `generation_id` is SHA-256 over canonical JSON containing `identity_version: "v1"`, `embedding_config_id`, `storage_config_id`, and `corpus_digest`.
- A new generation is built separately from the active generation.
- The active generation is selected through a Qdrant alias.
- Existing generation contents are not mutated in place.
- The previously active generation is retained after a successful activation.

### 5.2 Point identity

- Each Qdrant point ID is a deterministic UUIDv5.
- UUIDv5 uses one fixed namespace.
- The original application `chunk_id` is retained in the payload.
- The same logical chunk identity must not receive a random point ID on repeated builds.

The point ID is derived as `UUIDv5(PROJECT_VECTOR_NAMESPACE, chunk_id)`. `PROJECT_VECTOR_NAMESPACE` is the fixed, project-owned UUID constant `452d7fec-5a06-47c6-801d-eb0363eec5c4`, represented in Python as `UUID("452d7fec-5a06-47c6-801d-eb0363eec5c4")`. The canonical name input is the original `chunk_id`. `generation_id` is not part of the UUIDv5 name because each generation has its own collection. This namespace value must remain identical across development, testing, and production; it must not be generated at runtime, placed in environment configuration, or changed by an implementation agent.

### 5.3 Payload

The payload schema is fixed as follows; fields are required unless the upstream contract explicitly defines otherwise (the current approved source contracts define these fields as available):

| Field | Type | Source |
| --- | --- | --- |
| `chunk_id` | Keyword | Chunk |
| `generation_id` | Keyword | Vector Storage |
| `document_id` | Keyword | Chunk |
| `source_path` | Keyword | Chunk |
| `title` | Text | Chunk |
| `format` | Keyword | Chunk |
| `content` | Text | Chunk |
| `start_offset` | Integer | Chunk |
| `end_offset` | Integer | Chunk |
| `chunk_index` | Integer | Chunk |
| `chunking_config_id` | Keyword | Chunk |
| `embedding_config_id` | Keyword | Embedding |

No additional business fields may be invented during implementation. Documents that produce zero chunks produce no vector points.

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

A failed or incomplete build must not replace the currently active generation. An interrupted/incomplete generation remains inactive and is not automatically deleted in V1; the failure is recorded with its `generation_id`.

### 6.1 Rebuild policy

- V1 performs full generation rebuilds.
- Incremental updates to an existing generation are not supported.
- A generation must not become active before its build has completed successfully.
- Before activation, verify that the collection exists, its vector dimension matches the approved embedding configuration, its distance metric is Cosine, the stored point count equals the expected chunk count, and all upsert operations completed successfully.
- Only after all checks pass, atomically switch `knowledge_vectors_active` to the new generation.
- A failed or interrupted build leaves the active alias unchanged.

### 6.2 Retention and deletion

- Automatic generation cleanup is prohibited.
- Explicit deletion may target an inactive generation.
- Deletion of the active generation must be rejected.
- An incomplete generation is not automatically cleaned up; cleanup requires an explicit operation.
- Deletion must not implicitly move or remove the active alias.

## 7. Qdrant Client and Infrastructure

### 7.1 Client boundary

- Use the official `qdrant-client` package pinned to `1.20.0`, paired with Qdrant Server `v1.20.0`.
- Keep Qdrant SDK calls behind the application-owned `VectorStore` abstraction.
- Domain/application-facing code must not depend directly on Qdrant SDK client objects or SDK-specific models.

The application-owned `VectorStore` interface exposes these operations and high-level contracts:

- `create_generation`: create a generation collection with the approved vector and payload-index configuration.
- `upsert_points`: write points in batches while preserving input identity and order at the application boundary.
- `verify_generation`: verify collection existence, vector dimension, Cosine distance, expected point count, and successful completion of all upserts.
- `activate_generation`: atomically switch `knowledge_vectors_active` to a verified generation.
- `search`: reserved interface operation for vector similarity search; retrieval semantics remain governed by a separate Retrieval specification and are not defined here.
- `get_generation_info`: return storage-level generation metadata.
- `delete_generation`: explicitly delete an inactive generation and reject deletion of the active generation.



| Method | Input | Output |
| --- | --- | --- |
| `create_generation` | Generation configuration | Collection information |
| `upsert_points` | Points batch | Upsert result |
| `verify_generation` | Generation ID and expected point count | Verification result |
| `activate_generation` | Generation ID | Activation result |
| `search` | Search request | Search results |
| `get_generation_info` | Generation ID | Generation information |
| `delete_generation` | Generation ID | Deletion result |

All inputs and outputs are application-owned contracts with normalized errors. Detailed DTO fields and validation rules remain to be specified before implementation. `search` is reserved at the interface boundary only; its behavior and result semantics belong to the separate Retrieval specification. Qdrant SDK types must not escape the adapter boundary.

The approved version pair is Qdrant Server `v1.20.0` and Python package `qdrant-client==1.20.0`.

### 7.2 Connection and retry configuration

- Qdrant URL is supplied through application configuration.
- API key is optional.
- Client timeout is 10 seconds.
- Write batch size is 64.
- Retry transient failures only, including request timeouts, connection errors, and HTTP 5xx responses.
- Do not retry permanent validation, contract, or configuration failures.
- Allow 3 attempts total, including the initial attempt.
- Use exponential backoff with jitter.
- After exhaustion, return a normalized storage error to the application layer.
- Retry classification must not cause permanent errors to be retried.

### 7.3 Docker Compose

- Use the official Qdrant image as the base, pinned to `qdrant/qdrant:v1.20.0`; do not use a floating `latest` tag.
- Build a project-specific Qdrant image from a dedicated `docker/qdrant/Dockerfile`. The Dockerfile must extend the pinned official image and install `curl` solely to provide a reliable readiness probe. Do not modify Qdrant application binaries or configuration as part of this customization.
- Keep the existing root-level application `Dockerfile` dedicated to the FastAPI application and keep the root `docker-compose.yml` as the single Compose entry point.
- In `docker-compose.yml`, build the Qdrant service using context `./docker/qdrant` and tag the resulting image `ai-customer-support-qdrant:v1.20.0`.
- Configure the healthcheck using `curl -fsS http://localhost:6333/readyz`.
- Healthcheck timing: interval 10 seconds, timeout 5 seconds, 5 retries, and start period 10 seconds.
- Configure the API service dependency using `condition: service_healthy`.
- Preserve the repository's project-scoped Docker network and named-volume conventions.
- The custom image is an explicit, approved exception to the earlier preference for an unchanged official image; it exists only to add the healthcheck executable.

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

The storage error contract must distinguish:

- Connection failures.
- Request timeouts.
- Transient Qdrant/service availability failures.
- Permanent client/configuration failures.
- Invalid storage contracts, including incompatible vector dimensions or malformed point data.
- Generation build failures.
- Alias activation failures.
- Rejected deletion of an active generation.

Only transient failures (timeouts, connection errors, and HTTP 5xx) are eligible for the bounded 3-attempt retry policy with exponential backoff and jitter. Permanent contract and configuration failures fail without retry.

The application-owned stable error codes are:

| Condition | Error code |
| --- | --- |
| Connection failure | `VECTOR_STORE_UNAVAILABLE` |
| Request timeout | `VECTOR_STORE_TIMEOUT` |
| HTTP 5xx / service error | `VECTOR_STORE_SERVICE_ERROR` |
| Invalid vector or payload data | `VECTOR_STORE_INVALID_DATA` |
| Invalid configuration | `VECTOR_STORE_CONFIGURATION_ERROR` |
| Generation build failure | `VECTOR_GENERATION_BUILD_FAILED` |
| Alias activation failure | `VECTOR_GENERATION_ACTIVATION_FAILED` |
| Attempt to delete the active generation | `VECTOR_GENERATION_ACTIVE_DELETE_REJECTED` |

Qdrant SDK exceptions are translated inside the Qdrant adapter. SDK-specific exception/model types must not escape into the application layer. The exact SDK exception/status-to-code mapping must be verified and covered by tests.

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

- Deterministic UUIDv5 point identity using the fixed project namespace and `chunk_id` as the name input.
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
- Exactly 3 total attempts for eligible transient failures, with exponential backoff and jitter.
- No retries for permanent failures.
- No Qdrant network I/O during FastAPI startup.
- Docker Compose healthcheck against `/readyz`, using the verified executable/command and approved timing, plus `service_healthy` dependency.
- Structured metadata-only observability.
- Regression of existing ingestion, chunking, and embeddings behavior.

Tests must not require paid external AI services. Qdrant integration tests use the project's local/containerized infrastructure or controlled test doubles according to the finalized test design.

## 12. Open Specification Decisions

The architecture decisions D1–D16 are approved. The following lower-level contract details remain open and must be resolved during specification review, not invented during implementation:

2. Exact healthcheck probe command and project-specific image build configuration, as defined in §7.3.
3. Exact SDK exception/status-to-stable-error-code mapping for `qdrant-client==1.20.0`.
4. Detailed DTO fields, validation rules, and normalized error contracts for each `VectorStore` method.

The resolved decisions above have been approved in the Day 27 architecture discussion. The remaining details must be verified and recorded before final specification approval; implementation agents must not invent them.

## 13. Acceptance Criteria

This specification is ready for approval only when:

1. D1–D16 are represented without changing their approved meaning.
2. Storage and Retrieval remain separate boundaries.
3. Generation identity inputs and canonical digest construction are unambiguous.
4. The fixed UUIDv5 namespace value and canonical name input are explicit.
5. The exact payload schema and field types are defined.
6. Collection/generation naming and collection-per-generation behavior are explicit.
7. The compatible pinned `qdrant-client==1.20.0` version is specified.
8. The pinned Qdrant base image, dedicated Dockerfile path, custom image tag, readiness endpoint, healthcheck command and timing, and Compose dependency are specified.
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

- **Status:** Draft — architecture decisions D1–D16 and detailed architecture/contract decisions reviewed and approved in the Day 27 discussion.
- **Specification approval:** Pending final verification of the remaining open details.
- **Implementation authorization:** Not granted.
- **Task breakdown authorization:** Not granted.
