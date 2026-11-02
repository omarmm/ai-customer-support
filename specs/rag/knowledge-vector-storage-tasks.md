# Knowledge Vector Storage — Implementation Task Breakdown

- **Specification:** `specs/rag/knowledge-vector-storage.md`
- **Specification status:** Approved (2026-11-03)
- **Task breakdown status:** Proposed — pending project-owner approval
- **Implementation authorization:** Not granted
- **Rule:** Execute exactly one explicitly authorized task per session. The approved specification is the source of truth.

## Scope

Implement only the Vector Storage subsystem defined by the approved specification. Retrieval semantics, query behavior, metadata filtering policy, context construction, source attribution, and Agent integration are out of scope and require their own specifications.

## Dependency-ordered tasks

### T272 — Vector storage contracts and application error taxonomy

**Goal:** Add application-owned DTOs, validation, and normalized errors without introducing Qdrant I/O.

**Scope:**
- Define the frozen request/result DTOs for create, upsert, verify, activate, generation info, and delete exactly as specified.
- Define the VectorStore application protocol/interface, keeping `search` reserved without implementing retrieval behavior.
- Define the normalized storage/generation error types and retryability metadata.
- Unit-test validation, immutability, error mapping contracts, and UUIDv5 point-ID derivation.

**Acceptance criteria:**
- All DTO fields, types, validation rules, and error codes match §§5–6 and §9.
- UUIDv5 uses the fixed project namespace and original `chunk_id`.
- No Qdrant SDK, network client, settings, infrastructure, endpoint, or persistence integration is added.
- Focused tests pass; existing tests remain unaffected.

**Dependencies:** None.

### T273 — Qdrant client adapter and exception normalization

**Goal:** Implement the pinned Qdrant client boundary behind the application-owned VectorStore interface.

**Scope:**
- Add `qdrant-client==1.20.0`.
- Implement client construction from explicit configuration, timeout, and optional API key.
- Implement SDK-to-application exception normalization using §9.1, including wrapped HTTPX causes and both 429 paths.
- Implement bounded retry behavior for eligible transient failures only.

**Acceptance criteria:**
- SDK types and raw response bodies never escape the adapter.
- Timeout, connection, 5xx, permanent 4xx, 429, parsing, and unknown failures follow §9/§9.1.
- At most 3 total attempts; 429 and permanent failures are never retried.
- Offline adapter tests cover the exception matrix and retry boundaries.
- No business lifecycle orchestration or startup network I/O is added.

**Dependencies:** T272.

### T274 — Qdrant container infrastructure and application configuration

**Goal:** Add the pinned local/containerized Qdrant runtime configuration.

**Scope:**
- Add the dedicated Qdrant Dockerfile extending `qdrant/qdrant:v1.20.0`.
- Install only the approved healthcheck utility and define the specified image tag.
- Add the approved readiness healthcheck and Compose `service_healthy` dependency.
- Add only the settings required by §7, including URL and optional API key.

**Acceptance criteria:**
- Image base, Dockerfile path, image tag, healthcheck endpoint/command/timing, and Compose dependency match §7.
- API startup remains free of Qdrant network I/O.
- Configuration tests cover defaults, invalid values, and optional API key behavior.
- Existing PostgreSQL/API Compose behavior remains intact.

**Dependencies:** T272. May proceed independently of T273, but only one task is authorized at a time.

### T275 — Generation collection creation and point upsert

**Goal:** Implement the storage primitives needed to build an immutable generation.

**Scope:**
- Implement collection creation with fixed 768-dimensional Cosine vectors and the exact payload indexes.
- Implement deterministic UUIDv5 point IDs and exact payload assembly.
- Implement ordered batches of 1–64 points and confirmed batch outcomes.

**Acceptance criteria:**
- Collection and index schema match §§4–5.
- Payload contains the approved fields and adapter-added generation ID.
- Vector validation rejects wrong dimensions, booleans, non-finite values, and invalid payloads.
- Partial or ambiguous writes fail as `VECTOR_GENERATION_BUILD_FAILED`; no false success is returned.
- Adapter tests cover empty/invalid boundaries and batch ordering.

**Dependencies:** T273, T274.

### T276 — Generation verification and activation lifecycle

**Goal:** Verify completed generations and atomically switch the active alias.

**Scope:**
- Implement generation verification against expected point count, vector size, distance, and collection identity.
- Implement verified-generation activation using one atomic alias operation.
- Preserve the previous generation and guarantee failed activation does not report partial success.

**Acceptance criteria:**
- Activation is impossible before successful verification.
- Verification returns a result only when all required checks pass.
- Alias switching is atomic; previous generation is retained.
- Failed build/verification/activation leaves the active alias unchanged.
- Tests cover first activation, replacement activation, and failure paths.

**Dependencies:** T275.

### T277 — Generation information and explicit deletion

**Goal:** Implement storage metadata inspection and safe inactive-generation deletion.

**Scope:**
- Implement generation info from actual Qdrant collection/alias state.
- Implement explicit deletion of inactive generations.
- Reject missing generations and active-generation deletion with the specified errors.

**Acceptance criteria:**
- Generation info fields match §5 and accurately reflect active alias membership.
- Missing collection raises `VECTOR_GENERATION_NOT_FOUND`.
- Active generation deletion raises `VECTOR_GENERATION_ACTIVE_DELETE_REJECTED`.
- Inactive deletion returns the immutable confirmed result only after successful deletion.
- Deletion never mutates the active alias; no automatic cleanup is introduced.

**Dependencies:** T273, T274, T276.

### T278 — Vector storage composition and integration verification

**Goal:** Wire the completed storage subsystem into the application without adding an endpoint or retrieval behavior.

**Scope:**
- Add the storage composition factory and expose the application-owned service through the agreed application lifecycle boundary.
- Ensure construction performs no Qdrant network I/O.
- Run focused storage tests, container integration tests, and full regression.

**Acceptance criteria:**
- Composition uses explicit settings and the approved adapter.
- FastAPI startup performs no Qdrant network call; existing health behavior remains independent.
- Local/containerized integration proves generation create → upsert → verify → activate → inspect → inactive delete.
- Existing ingestion, chunking, embeddings, and full regression suites pass.
- Diff is limited to the approved task scope; project state is updated with evidence.

**Dependencies:** T272–T277.

## Execution order

T272 → T273 → T274 → T275 → T276 → T277 → T278.

T274 is technically independent of T273, but the proposed sequence is intentionally kept linear for reviewability and one-task-at-a-time execution.

## Authorization gate

This document is a proposed task breakdown. It does not authorize implementation. After project-owner approval, only T272 may be separately authorized as the first implementation task. All later tasks remain unauthorized until their own dependency and scope checks are satisfied.
