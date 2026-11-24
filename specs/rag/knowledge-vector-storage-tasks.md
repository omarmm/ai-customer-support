# Knowledge Vector Storage — Implementation Task Breakdown

- **Specification:** `specs/rag/knowledge-vector-storage.md`
- **Specification status:** Approved (2026-11-03)
- **Task breakdown status:** Approved by the project owner on 2026-11-03
- **Implementation authorization:** T272–T277 are complete and closed. T278
  was authorized on 2026-11-09, verified, and closed on 2026-11-09.
- **Rule:** Execute exactly one explicitly authorized task per session. The approved specification is the source of truth.

## Scope

Implement only the Vector Storage subsystem defined by the approved specification. Retrieval semantics, query behavior, metadata filtering policy, context construction, source attribution, and Agent integration are out of scope and require their own specifications.

## Directory and test layout

Follow the existing RAG package convention (`ingestion/`, `chunking/`, `embeddings/`) and use the Python package name with an underscore:

- Production code: `src/app/rag/vector_storage/`
- Tests: `tests/rag/vector_storage/`

The directory name is `vector_storage`, not `vector-storage`, because it is an importable Python package and matches the existing subsystem naming convention. Keep tests parallel to the production package. Add focused unit/adapter tests with each task; do not defer testing until the final task. Add container-backed integration tests and full regression in T278. Tests must prove the approved specification contracts, not redefine them.

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
- Focused tests are added under `tests/rag/vector_storage/` for every DTO, validation boundary, and error contract introduced by this task.
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
- Offline adapter tests under `tests/rag/vector_storage/` cover the exception matrix and retry boundaries.
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
- Configuration tests under `tests/rag/vector_storage/` cover defaults, invalid values, and optional API key behavior.
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
- Adapter tests under `tests/rag/vector_storage/` cover empty/invalid boundaries and batch ordering.

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
- Tests under `tests/rag/vector_storage/` cover first activation, replacement activation, and failure paths.

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
- Tests under `tests/rag/vector_storage/` cover missing, active, inactive, and failed deletion paths.

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
- Local/containerized integration tests under `tests/rag/vector_storage/` prove generation create → upsert → verify → activate → inspect → inactive delete.
- Existing ingestion, chunking, embeddings, and full regression suites pass.
- Every new production module has corresponding focused tests; test coverage is delivered incrementally with T272–T277, not postponed to T278.
- Diff is limited to the approved task scope; project state is updated with evidence.

**Dependencies:** T272–T277.

## Execution order

T272 → T273 → T274 → T275 → T276 → T277 → T278.

T274 is technically independent of T273, but the proposed sequence is intentionally kept linear for reviewability and one-task-at-a-time execution.

## Authorization gate

This task breakdown was approved by the project owner on 2026-11-03. T272–T278 have been implemented, verified, committed, and closed. T278 verification evidence is recorded in `specs/project-state.md`. No further Vector Storage task is authorized. Execute exactly one task per authorized session, verify it, update project state, and STOP.


---

## 8. Amendment VS-GI-001 — Implementation Task Breakdown

- **Amendment:** VS-GI-001 in specs/rag/knowledge-vector-storage.md.
- **Approval:** Task breakdown approved by the project owner on 2026-11-23.
- **Implementation authorization:** None. Each task below requires separate explicit authorization.
- **Execution rule:** Implement exactly one task per authorized session, verify it, update project state, and STOP.

### 8.1 Dependencies and execution order

~~~text
VS281-A — Identity contracts and active-generation resolution contract
  ↓
VS281-B — Atomic collection metadata creation
  ↓
VS281-C — Generation verification identity validation
  ↓
VS281-D — Validated GenerationInfo and active-generation resolution
  ↓
VS281-E — Qdrant integration verification and amendment closure
~~~

No Retrieval implementation task may begin until VS281-A through VS281-E are individually verified and closed.

### 8.2 VS281-A — Identity contracts

**Goal:** Amend application-owned Vector Storage contracts and validation without changing Qdrant behavior.

**Scope:**
- Add embedding_config_id to VerifyGenerationRequest.
- Add embedding_config_id to GenerationVerificationResult.
- Add embedding_config_id to GenerationInfo.
- Define the application-owned get_active_generation_info() operation and its result/error contract.
- Define the pinned-generation identity carried by the future Retrieval search request, without implementing search.
- Add validation for metadata identity values and schema version at the contract boundary where appropriate.

**Acceptance criteria:**
- DTOs are frozen and application-owned.
- Both identity values use exactly 64 lowercase hexadecimal characters.
- No Qdrant SDK type is introduced into application contracts.
- Existing contracts remain backward-consistent except for the explicitly amended fields/operation.
- Focused contract tests cover valid, invalid, missing, and immutable values.
- No Qdrant I/O, collection mutation, Retrieval implementation, or production composition change is added.

**Dependencies:** Approved VS-GI-001.

### 8.3 VS281-B — Atomic collection metadata creation

**Goal:** Persist generation identity as part of Qdrant collection creation.

**Scope:**
- Build the exact three-field metadata object from CreateGenerationRequest.
- Pass metadata in the same Qdrant collection-creation operation.
- Keep existing collection name, vector configuration, and payload-index behavior unchanged.
- Do not add metadata update, repair, or backfill operations.

**Acceptance criteria:**
- Collection creation receives exact metadata values.
- No follow-up metadata write is performed.
- Invalid identity is rejected before Qdrant I/O.
- Adapter tests cover metadata mapping, create failure, and no post-create metadata mutation.
- Existing creation behavior and normalized errors remain correct.

**Dependencies:** VS281-A.

### 8.4 VS281-C — Generation verification identity validation

**Goal:** Make verification prove that a generation has the expected embedding identity.

**Scope:**
- Read and validate collection metadata during verification.
- Compare stored generation ID and embedding config ID against the request.
- Preserve existing dimension, Cosine distance, exact point-count, and verification-cache behavior only where still valid under the amended contract.
- Return GenerationVerificationResult with the validated embedding identity.

**Acceptance criteria:**
- Missing, malformed, unsupported, or mismatched metadata fails as VECTOR_GENERATION_BUILD_FAILED.
- Missing collection retains VECTOR_GENERATION_NOT_FOUND where specified.
- Zero-point valid and invalid generations are tested.
- Failed verification cannot mark a generation verified or activate it.
- No partial verification result is returned.
- Focused adapter tests cover every identity failure mode.

**Dependencies:** VS281-B.

### 8.5 VS281-D — Validated generation information and active resolution

**Goal:** Expose trusted generation identity to Retrieval without leaking Qdrant models.

**Scope:**
- Read and validate metadata in get_generation_info.
- Return GenerationInfo.embedding_config_id from validated collection metadata.
- Implement get_active_generation_info() by resolving knowledge_vectors_active and validating its concrete collection.
- Ensure the result identifies the concrete generation snapshot and reports is_active=True.
- Keep alias and collection mutation out of this operation.

**Acceptance criteria:**
- Existing generation info returns validated embedding identity.
- Active alias resolution returns the correct concrete generation and identity.
- Missing alias/target and malformed target follow the amended normalized error contract.
- Tests cover alias absence, invalid target name, missing collection, invalid metadata, zero points, and successful resolution.
- No search, Retrieval service, or endpoint is implemented.

**Dependencies:** VS281-C.

### 8.6 VS281-E — Integration verification and closure

**Goal:** Verify the complete generation identity lifecycle against the pinned Qdrant runtime.

**Scope:**
- Add/run Qdrant-backed tests for create → upsert → verify → activate → get info → resolve active generation.
- Verify legacy collection behavior without mutating or repairing legacy data.
- Run focused offline tests and full regression.
- Record exact commands, versions, outcomes, and skips in specs/project-state.md.

**Acceptance criteria:**
- New collection metadata is exact and readable from Qdrant.
- Verification and GenerationInfo expose the same trusted identity.
- Zero-point generation behavior is proven.
- Missing/malformed/mismatched identity fails closed.
- Failed verification leaves the active alias unchanged.
- Active generation resolution returns a pinned generation ID suitable for the later Retrieval search contract.
- No Retrieval implementation or search semantics are added.
- Focused tests, Qdrant integration tests, full regression, and git diff --check pass.
- Amendment tasks are closed only after evidence review; stop after closure.

**Dependencies:** VS281-D.

### 8.7 Authorization gate

- **Current authorized implementation task:** VS281-C — Generation verification identity validation only (explicit owner authorization, 2026-11-24; authorization record in `specs/project-state.md`).
- VS-GI-001 and this task breakdown approval alone do not authorize implementation; each task requires separate explicit owner authorization.
- VS281-A and VS281-B are task-verified under the approved cumulative protocol (§8.8).
- VS281-C is the only currently authorized implementation task. VS281-D and VS281-E remain unauthorized.
- Closing one task does not authorize the next task automatically.
- T282–T288 in the Retrieval task breakdown remain blocked until all VS281 tasks are verified and closed.


### 8.8 Cumulative implementation and verification protocol

**Status: APPROVED by the project owner on 2026-11-24.** This section changes execution/verification mechanics only. It does not change VS-GI-001 identity semantics, task scope, acceptance criteria, or dependency order.

- Implement VS281-A through VS281-E sequentially on one cumulative integration branch created from the approved master base. Preserve a distinct prepared commit/handoff for each task and record the exact base/head relationship.
- Authorize exactly one task at a time. After each task, run its focused offline tests, task-specific integration tests where applicable, scope review, and `git diff --check`; prepare its handoff and stop for owner review/authorization of the next task.
- Do not merge intermediate VS281 task commits to master. Later tasks may depend on the cumulative branch so that the adapter and contracts evolve together; no task may implement work owned by a later task before that later task is authorized.
- During VS281-A through VS281-D, run the full regression suite as a diagnostic. Failures caused solely by not-yet-implemented, explicitly downstream VS281 work must be recorded with exact failing tests, error signatures, and owning task. They are **deferred integration failures**, not passing tests and not evidence that the full regression is green. Any unrelated regression failure blocks closure of the current task.
- A task may be marked task-verified only when its own acceptance criteria and focused tests pass, scope is clean, and every full-regression failure is demonstrated to be an expected downstream dependency gap. The handoff must retain the red full-regression result and identify the task that will resolve each failure. No fallback/default identity or weakened fail-closed behavior is permitted.
- VS281-E is the final integration gate: all VS281-A–D work must be present on the cumulative branch; Qdrant integration tests and the complete full regression must pass; no deferred failure may remain; `git diff --check` and final scope review must pass.
- Only after VS281-E passes may one cumulative PR be prepared for owner review. No merge occurs without the owner's explicit approval. After merge, update project state to close the amendment and keep Retrieval blocked until the final merge/closure gate is satisfied.
- If a task reveals a specification contradiction, an unrelated regression, or a failure not attributable to a documented downstream task, stop and request a specification decision. Do not expand scope or silently change acceptance criteria.

**Approval:** Explicitly approved by the project owner on 2026-11-24. This protocol governs VS281 implementation and verification.
