# AI Customer Support Backend — Project State


## Current Position
- Current Phase: Phase 4 — RAG. Ingestion (T255–T259), chunking (T260–T266),
  embeddings (T267–T271), vector storage contracts (T272), the Qdrant client
  adapter (T273), Qdrant container infrastructure/configuration (T274),
  generation collection creation/point upsert (T275), generation
  verification/activation (T276), generation information/explicit deletion
  (T277), and vector storage composition/integration verification (T278) are
  complete and closed.
- T272 — Vector storage contracts and application error taxonomy — complete
  (2aed1a8eaa6a98f207feacce7599f7a7e781f461).
- T273 — Qdrant client adapter and exception normalization — complete
  (fdff9c5afa71dfd96befad72359bc0e35930a036).
- T274 — Qdrant container infrastructure and application configuration —
  complete and verified at `615caa8a2833f8dd34fe86cc51c989117cf0c9db`
  (`fix(rag): isolate qdrant url configuration test`) on
  `feature/t274-qdrant-infrastructure-handoff`, after the prepared
  implementation at `51d9d50d724566a6da52d36e8b17c067d0ade310`.
- T275 — Generation collection creation and point upsert — complete and
  verified at `216545889b0804306e27f6b0883c34bb5e58bcc3`
  (`test(rag): cover ambiguous upsert completion states`) on
  `feature/t274-qdrant-infrastructure-handoff`, against base
  `f389895506ada89e32f0c36651ceb1c518f3d845`.
- T276 — Generation verification and activation lifecycle — complete and
  verified at `b898f65` (`test(rag): fix alias operation test double`) on
  `feature/t276-generation-verification-activation`, after the prepared
  implementation at `b86e895`
  (`feat(rag): verify and activate vector generations`) and base
  `92444a9c3a05fec79b9603df53666afd102f042f`.
- T277 — Generation information and explicit deletion — complete and verified
  at `7c7f855` (`fix(rag): preserve generation management error causes`) on
  `feature/t277-generation-info-deletion`, after the prepared implementation at
  `0c0d7716b7b68a46687b7334b91e81519a23a2c0`
  (`style(test): wrap invalid metadata assertion`) and base
  `1a5f431860b11c5419a9a1bb9ced88ac57cecc9e` (master).
- T278 — Vector storage composition and integration verification — complete and
  verified at `e63952fad1ba2c12477e02cfa384512242b6320e`
  (`test(rag): narrow startup network guard`) on
  `feature/t278-vector-storage-composition`, after the prepared implementation
  at `4bd41543dde2cc4c52299cfaa0d2b702082cae6b` and base
  `b08225e864ad386f0a558620e9343d318caec903` (master).
- The Vector Storage specification (specs/rag/knowledge-vector-storage.md)
  and task breakdown (specs/rag/knowledge-vector-storage-tasks.md) were
  approved on 2026-11-03. T272–T278 were closed after verification. No further
  task is authorized or active.
- Embedding/tokenizer decision approved (2026-10-23) at
  specs/rag/embedding-tokenizer-decision.md; pinned tokenizer identity:
  tokenizers:0.23.3:nomic-ai/nomic-embed-text-v1.5@e9b6763023c676ca8431644204f50c2b100d9aab:d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66
- Live embedding conformance evidence (2026-10-25): served model
  nomic-embed-text:v1.5, observed dimension 768, all returned values finite;
  the served model digest is evidence only, not runtime verification.

## Active Implementation Handoff

- None. T278 was verified and closed on 2026-11-09. No implementation task is
  active or authorized. The verified branch is ready for PR merge; do not start
  another task until the merge is complete.

## Last Completed Task
- Task: T278 — Vector storage composition and integration verification
- Prepared implementation commit:
  `4bd41543dde2cc4c52299cfaa0d2b702082cae6b`
  (`style(test): simplify startup network guard`) on
  `feature/t278-vector-storage-composition`, against base
  `b08225e864ad386f0a558620e9343d318caec903` (master). Verification found and
  fixed one in-scope startup-test defect at
  `e63952fad1ba2c12477e02cfa384512242b6320e`
  (`test(rag): narrow startup network guard`). Finalization is this
  documentation-only closure commit; its SHA is recorded in Git history.
- Scope delivered: new `src/app/rag/vector_storage/composition.py` with
  `build_vector_store(settings)`, which constructs one `QdrantClientConfig` from
  explicit `qdrant_url`/`qdrant_api_key` settings and delegates to the approved
  `QdrantClientAdapter.from_config`. `src/app/main.py` startup lifespan exposes
  that single application-owned instance through `app.state.vector_store`
  alongside the existing chunking and embedding services. New
  `tests/rag/vector_storage/test_composition.py` covers explicit setting
  forwarding, network-free factory construction, one-instance startup, the
  health endpoint, and the absence of Qdrant I/O during startup; new
  `tests/rag/vector_storage/test_qdrant_integration.py` is an opt-in
  container-backed lifecycle test. No endpoint, retrieval semantics, search
  implementation, configuration, Docker, or other subsystem changes were added.
- Verification (2026-11-09; final API image `ai-customer-support-api:latest`,
  ID `sha256:14e46b2fc061420aa741979acfd1f871f6b2cbad4f14f3e26d86523b58d044cd`;
  Qdrant image `ai-customer-support-qdrant:v1.20.0`, ID
  `sha256:42574bd137d89e4097ddb69965b6502ff045e7b539a4089fa0b498a04eb93be2`;
  no repository bind mount in image-level verification runs):
  - Scope review: `git diff b08225e8 4bd4154` was limited to
    `src/app/main.py`, `src/app/rag/vector_storage/composition.py`,
    `tests/rag/vector_storage/test_composition.py`,
    `tests/rag/vector_storage/test_qdrant_integration.py`, the two authorized
    specification files, and `specs/project-state.md`. The verification fix
    touched only `tests/rag/vector_storage/test_composition.py`. No unrelated
    files, secrets, endpoints, retrieval behavior, or configuration changes.
  - `docker compose config` → exit 0; the project network, pinned Qdrant image,
    healthcheck, and `service_healthy` dependency remain intact.
  - Build: `docker compose build api qdrant` → exit 0. The API image was rebuilt
    after the test fix; the Qdrant image reused its cached pinned layers.
  - Defect found and fixed: the first focused run failed
    `test_application_startup_exposes_one_vector_store_without_qdrant_io`
    (1 failed, 192 passed, 1 skipped) with
    `AssertionError: network access attempted during application startup`. The
    test replaced the `socket.socket` class, which also intercepted anyio's
    internal AF_UNIX `socketpair()` used to run `TestClient`; this was not
    Qdrant I/O. The guard now patches `socket.socket.connect`,
    `socket.socket.connect_ex`, and `socket.create_connection`, which still
    fail on any outbound connection. No production code changed.
  - Focused compose suite: `docker compose exec -T api pytest
    tests/rag/vector_storage -q` → 193 passed, 1 skipped, exit 0. The skip is
    the opt-in Qdrant integration test.
  - Focused in-image suite without a bind mount: `docker run --rm --network none
    ai-customer-support-api:latest python -m pytest tests/rag/vector_storage -q`
    → 193 passed, 1 skipped, exit 0.
  - Docker Compose runtime: `docker compose up -d` → exit 0; PostgreSQL and
    Qdrant reported `healthy` and the API started. Qdrant `/readyz` returned
    HTTP 200 (`all shards are ready`) and API `/health` returned HTTP 200
    `{"status": "ok"}`. `docker compose down` → exit 0; all three containers and
    the project network were removed.
  - Live Qdrant lifecycle integration (real Qdrant v1.20.0): `docker compose
    exec -T -e RUN_QDRANT_INTEGRATION=1 api pytest
    tests/rag/vector_storage/test_qdrant_integration.py -q` → 1 passed, exit 0.
    The same test in-image on the Compose network → 1 passed, exit 0. It created
    two uniquely named generations, upserted a point into each, verified each,
    activated A then B, inspected both (A inactive with 1 point, B active with
    1 point), and deleted inactive A. Teardown removed the temporary alias and
    the remaining collection; `/collections` and `/aliases` were both empty
    afterward.
  - Full regression via Compose: `docker compose exec -T api pytest tests -q`
    → 1008 passed, 8 skipped, exit 0. Full regression in-image without a bind
    mount on the Compose network → 1008 passed, 8 skipped, exit 0. The skips are
    the 4 unchanged environment-conditional ingestion permission fixtures, the
    3 opt-in live embedding conformance tests, and the opt-in Qdrant
    integration test.
  - Startup/network boundary: an in-image `TestClient` run with
    `--network none`, `--env-file .env`, and `socket.socket.connect`,
    `socket.socket.connect_ex`, and `socket.create_connection` replaced by
    failing stubs → application startup completed; `app.state.vector_store` was
    a `QdrantClientAdapter` whose underlying client was a `QdrantClient`; and
    `/health` returned HTTP 200 `{"status": "ok"}`. No Qdrant request occurred.
  - Negative requirements: startup exposes exactly one vector-store instance;
    construction receives explicit settings and the approved adapter; the
    factory and application startup perform no Qdrant network I/O; `/health`
    remains a static endpoint independent of Qdrant; and no endpoint, search
    implementation, retrieval semantics, or additional subsystem wiring was
    introduced.
  - Boundary scan: composition imports only application settings and the
    application-owned adapter; Qdrant SDK types remain confined to the adapter
    and tests. `git diff --check` → clean, exit 0.
- Outcome: T278 acceptance criteria in the task breakdown and §7.4 are met. The
  storage subsystem is composed once from explicit settings and exposed through
  `app.state.vector_store`, startup remains network-free, the container-backed
  lifecycle passes, and the full regression suite passes. T278 is closed. No
  next task was started and no merge was performed.

## Previously Completed Task — T277
- Task: T277 — Generation information and explicit deletion
- Prepared implementation commit:
  `0c0d7716b7b68a46687b7334b91e81519a23a2c0`
  (`style(test): wrap invalid metadata assertion`) on
  `feature/t277-generation-info-deletion`, against base
  `1a5f431860b11c5419a9a1bb9ced88ac57cecc9e` (master). Verification found and
  fixed one in-scope cause-chain defect at
  `7c7f85550b7a5ec7dbb446c72a4d1c5e8217d7dc`
  (`fix(rag): preserve generation management error causes`). Finalization is this
  documentation-only closure commit; its SHA is recorded in Git history.
- Scope delivered: `src/app/rag/vector_storage/qdrant_adapter.py` now implements
  `get_generation_info`, which loads the derived generation collection through
  the normalized retry boundary, requires one unnamed dense vector
  configuration, reads the actual vector dimension and distance, requires an
  exact `count(exact=True)` non-negative point count, reads the current
  `knowledge_vectors_active` alias target, and constructs the immutable
  `GenerationInfo` only from actual Qdrant metadata. Missing collections
  normalize to `VECTOR_GENERATION_NOT_FOUND`. The adapter also implements
  `delete_generation`, which derives the collection name, resolves existence
  independently, rejects deletion when the collection is the current active
  alias target, re-reads alias state immediately before deletion, requires an
  explicit `True` deletion confirmation, never mutates the active alias, performs
  no automatic cleanup, and constructs the immutable `GenerationDeletionResult`
  only after confirmed deletion. Missing collections raise
  `VECTOR_GENERATION_NOT_FOUND`; active-generation deletion raises
  `VECTOR_GENERATION_ACTIVE_DELETE_REJECTED`; operational failures use the
  normalized storage taxonomy. New
  `tests/rag/vector_storage/test_generation_management.py` covers active and
  inactive info, exact counts, missing collections, invalid metadata, missing
  and active deletion rejection, inactive deletion, unconfirmed deletion,
  operational and existence-check failures, and the pre-deletion alias recheck;
  `tests/rag/vector_storage/test_qdrant_adapter.py` now guards the authorized
  T277 methods. No composition wiring, retrieval behavior, endpoint,
  configuration, Docker, or application startup changes were added.
- Verification (2026-11-09; image `ai-customer-support-t277:local`, ID
  `sha256:87947c9c54fd7f30a6abdfa8d41e4e5518c9b1165a075cafa711e8f12a8ea1ce`;
  Qdrant image `ai-customer-support-qdrant:v1.20.0`, ID
  `sha256:a13177399a78a20dd70fa38c8b2614a4c202dcf95b29ac67065f4fe02479262e`;
  no repository bind mount in image verification runs):
  - Scope review: `git diff 1a5f4318 0c0d771` was limited to
    `src/app/rag/vector_storage/qdrant_adapter.py`,
    `tests/rag/vector_storage/test_generation_management.py`,
    `tests/rag/vector_storage/test_qdrant_adapter.py`, the two authorized
    specification files, and `specs/project-state.md`. The verification fix
    touched only the adapter and the new management test file. No unrelated
    files, secrets, configuration, startup, or composition changes.
  - Pinned API confirmation inside the image: `qdrant-client` 1.20.0.
    `QdrantClient.delete_collection(...) -> bool`;
    `QdrantClient.get_collection(...) -> CollectionInfo`;
    `QdrantClient.count(..., exact=True) -> CountResult`;
    `QdrantClient.get_aliases(...) -> CollectionsAliasesResponse`; and
    `models.Distance.COSINE` reports the application string `Cosine`. This
    matches the adapter's confirmation, metadata, count, and alias logic.
  - Build: `docker build -t ai-customer-support-t277:local .` → exit 0.
  - Defect found and fixed: the new T277 error paths re-raised an
    already-normalized `VectorStoreError` with `from exc`, which made
    `__cause__` self-referential and destroyed the original cause chain. The
    adapter now re-raises already-normalized storage errors unchanged and
    normalizes only raw SDK/transport exceptions; focused cause-chain assertions
    and an existence-check failure test were added. No approved contract or
    scope changed.
  - Focused offline suite: `docker run --rm --network none
    ai-customer-support-t277:local python -m pytest tests/rag/vector_storage -q`
    → 190 passed, exit 0.
  - Docker Compose runtime: `docker compose config` → exit 0;
    `docker compose up -d postgres qdrant` → exit 0; PostgreSQL and Qdrant both
    reported `healthy`. Qdrant `/readyz` returned HTTP 200
    (`all shards are ready`) and `/healthz` returned HTTP 200
    (`healthz check passed`); the container healthcheck reported `healthy`.
  - Live Qdrant lifecycle integration (in-image, Compose network, real
    Qdrant v1.20.0): create generation A → 3-point upsert → verify (3/3, 768,
    Cosine); info before activation returned `is_active=False`, `point_count=3`,
    `vector_size=768`, `distance="Cosine"`; first activation returned
    `previous_generation_id=None`; info after activation returned
    `is_active=True`; create generation B → 1-point upsert → verify; info for B
    returned `is_active=False`; inactive deletion of B returned a confirmed
    immutable result; subsequent info for B raised
    `VECTOR_GENERATION_NOT_FOUND`; generation A remained active with 3 points;
    deleting active generation A raised
    `VECTOR_GENERATION_ACTIVE_DELETE_REJECTED` and left the alias unchanged; and
    deleting a missing generation raised `VECTOR_GENERATION_NOT_FOUND`. All
    checks passed, exit 0. Test generation IDs:
    `45e01a8c80685f0910a0656a9a8673a0287a4f6c1a1b0de29b66e0880f0e378f` (A)
    and `4b5ed3c1b22ca3f31bf8aae3d4fbcdea8ef5f4462b3f874af9f634563d8bb002`
    (B); both were removed during script cleanup.
  - Full regression: `docker run --rm --network ai-customer-support_default
    --add-host host.docker.internal:host-gateway --env-file .env
    ai-customer-support-t277:local python -m pytest tests -q` → 1005 passed,
    7 skipped, exit 0. The skips are the 4 unchanged environment-conditional
    ingestion permission fixtures plus the 3 opt-in live embedding conformance
    tests.
  - Startup/network boundary: an in-image `TestClient` run with `--network
    none`, `--env-file .env`, and `socket.socket.connect`,
    `socket.create_connection`, and `QdrantClient.__init__` replaced by failing
    stubs → application startup completed; `/health` returned HTTP 200
    `{"status": "ok"}`; `chunking_service` and `embedding_service` were present
    and no `vector_store` was constructed. No Qdrant network I/O occurred.
  - Negative requirements: the lifecycle guard asserts `get_generation_info` and
    `delete_generation` exist while `search` remains absent; missing generation
    info/deletion raises `VECTOR_GENERATION_NOT_FOUND`; active-generation
    deletion raises `VECTOR_GENERATION_ACTIVE_DELETE_REJECTED` before any delete
    call; inactive deletion returns a result only after explicit `True`
    confirmation; alias state is re-read immediately before deletion; deletion
    never mutates the active alias; no automatic cleanup is introduced; and
    normalized failure causes remain chained without exposing SDK types.
  - Boundary scan: only `src/app/rag/vector_storage/qdrant_adapter.py` imports
    `qdrant_client` under `src/`; public adapter signatures return
    application-owned DTOs. `git diff --check` → clean, exit 0.
- Outcome: T277 acceptance criteria in the task breakdown and §5, §6.2, §7.1
  (get/delete), §9, and §11 are met. T277 is closed. T278 was subsequently
  implemented, verified, and closed as recorded above; no next task was started
  and no merge was performed.

## Previously Completed Task — T276
- Task: T276 — Generation verification and activation lifecycle
- Prepared implementation commit:
  `b86e89542f73a6f6d9dd99c0ca98dfa308940296`
  (`feat(rag): verify and activate vector generations`) on
  `feature/t276-generation-verification-activation`, against base
  `92444a9c3a05fec79b9603df53666afd102f042f` (master). Verification found and
  fixed one in-scope test-double defect at
  `b898f65a0e2e5ac538ddcf0bd9ee54c45f573004`
  (`test(rag): fix alias operation test double`). Finalization is this
  documentation-only closure commit; its SHA is recorded in Git history.
- Scope delivered: `src/app/rag/vector_storage/qdrant_adapter.py` now implements
  `verify_generation`, which loads the derived generation collection through the
  normalized retry boundary, requires one unnamed 768-dimensional
  `models.VectorParams` configuration with Cosine distance, requires an exact
  `count(exact=True)` point count equal to the requested expected count, and
  constructs `GenerationVerificationResult` only after every check passes. All
  verification failures normalize to `VECTOR_GENERATION_BUILD_FAILED` while
  preserving the normalized underlying cause chain. Successful verification is
  tracked per adapter instance and invalidated by `create_generation` and
  `upsert_points`. The adapter also implements `activate_generation`, which
  requires a successful prior verification in the same adapter, re-verifies
  immediately before the alias switch, validates the current
  `knowledge_vectors_active` target against the generation namespace and the
  64-character lowercase hexadecimal generation ID, and performs exactly one
  atomic `update_collection_aliases` call: a single create operation for a first
  activation, or delete-plus-create operations for a replacement. It requires
  an explicit `True` confirmation, reconciles a lost response by re-reading
  alias state, never deletes the previous generation, preserves the previous
  alias target on failure, and normalizes every activation failure to
  `VECTOR_GENERATION_ACTIVATION_FAILED`. New
  `tests/rag/vector_storage/test_generation_lifecycle.py` covers verification
  schema/count checks, first and replacement activation, unverified and
  failed-build rejection, re-verification, lost-response reconciliation,
  unconfirmed alias operations, and verification invalidation after a later
  upsert; `tests/rag/vector_storage/test_qdrant_adapter.py` now guards the
  authorized T276 lifecycle methods. No T277/T278 inspection or deletion
  operations, composition wiring, retrieval behavior, endpoint, configuration,
  or application startup changes were added.
- Verification (2026-11-08; image `ai-customer-support-t276:local`, ID
  `sha256:7bcc67a45e43b4ae7815d44d435bc43dbc8d40a415b569c30a3b112688488024`;
  Qdrant image `ai-customer-support-qdrant:v1.20.0`, ID
  `sha256:a13177399a78a20dd70fa38c8b2614a4c202dcf95b29ac67065f4fe02479262e`;
  no repository bind mount in image verification runs):
  - Scope review: `git diff 92444a9 b86e895` was limited to
    `src/app/rag/vector_storage/qdrant_adapter.py`,
    `tests/rag/vector_storage/test_generation_lifecycle.py`,
    `tests/rag/vector_storage/test_qdrant_adapter.py`, the two authorized
    specification files, and `specs/project-state.md`. The verification fix
    touched only the new lifecycle test file. No unrelated files, secrets,
    configuration, startup, or composition changes.
  - Pinned API confirmation inside the image: `qdrant-client` 1.20.0.
    `QdrantClient.update_collection_aliases(...) -> bool`;
    `QdrantClient.get_aliases(...) -> CollectionsAliasesResponse`;
    `QdrantClient.count(..., exact=True) -> CountResult`; and
    `CreateAliasOperation`/`DeleteAliasOperation` each expose only their own
    alias field. This matches the adapter's confirmation, reconciliation, count,
    and operation construction logic.
  - Build: `docker build -t ai-customer-support-t276:local .` → exit 0.
  - Defect found and fixed: the first focused run failed
    `test_first_activation_creates_the_fixed_alias_atomically` and
    `test_replacement_activation_atomically_retains_previous_generation`
    (2 failed, 176 passed) because the new test double read the unset
    `delete_alias`/`create_alias` attribute directly, which qdrant-client 1.20.0
    omits on the other operation type. The double now uses `getattr`, matching
    production behavior. No production code was changed for this fix; focused,
    full, and live suites were rerun afterward.
  - Focused offline suite: `docker run --rm --network none
    ai-customer-support-t276:local python -m pytest tests/rag/vector_storage -q`
    → 178 passed, exit 0.
  - Docker Compose runtime: `docker compose config` → exit 0;
    `docker compose up -d postgres qdrant` → exit 0; PostgreSQL and Qdrant both
    reported `healthy`. Qdrant `/readyz` returned HTTP 200
    (`all shards are ready`) and `/healthz` returned HTTP 200
    (`healthz check passed`); the container healthcheck exited 0.
  - Live Qdrant lifecycle integration (in-image, Compose network, real
    Qdrant v1.20.0): create → 3-point upsert → verify (3/3, 768, Cosine);
    wrong-count verification rejected with `VECTOR_GENERATION_BUILD_FAILED`;
    first activation returned `previous_generation_id=None` and moved
    `knowledge_vectors_active` to the target; replacement activation returned
    the previous generation ID, moved the alias atomically, and left the
    previous collection present; already-active activation was idempotent with
    `previous_generation_id` equal to the active generation; unverified
    activation was rejected with `VECTOR_GENERATION_ACTIVATION_FAILED` and the
    alias unchanged; an upsert after verification invalidated the precondition
    and activation failed with the alias unchanged; zero-point verification
    succeeded; and verification of a missing collection failed with
    `VECTOR_GENERATION_BUILD_FAILED`. All checks passed, exit 0.
  - Full regression: `docker run --rm --network ai-customer-support_default
    --add-host host.docker.internal:host-gateway --env-file .env
    ai-customer-support-t276:local python -m pytest tests -q` → 993 passed,
    7 skipped, exit 0. The skips are the 4 unchanged environment-conditional
    ingestion permission fixtures plus the 3 opt-in live embedding conformance
    tests.
  - Startup/network boundary: an in-image `TestClient` run with `--network
    none`, `--env-file .env`, and `socket.socket.connect`,
    `socket.create_connection`, and `QdrantClient.__init__` replaced by failing
    stubs → application startup completed; `/health` returned HTTP 200
    `{"status": "ok"}`; `chunking_service` and `embedding_service` were present
    and no `vector_store` was constructed. No Qdrant network I/O occurred.
  - Negative requirements: the lifecycle guard asserts `create_generation`,
    `upsert_points`, `verify_generation`, and `activate_generation` exist while
    `get_generation_info` and `delete_generation` remain absent; activation
    before verification is rejected without any alias operation; wrong point
    counts and missing collections are rejected without false success; failed
    alias updates leave the previous target unchanged; verification is
    invalidated by later writes; and activation/verification failures preserve
    the normalized underlying cause chain without exposing SDK types.
  - Boundary scan: only `src/app/rag/vector_storage/qdrant_adapter.py` imports
    `qdrant_client` under `src/`; public adapter signatures return
    application-owned DTOs. `git diff --check` → clean, exit 0.
- Outcome: T276 acceptance criteria in §5.2–§5.4, §6.1, §7.1 (verify/activate),
  §9, §11, and the T276 task breakdown are met. T276 is closed. T277 and T278
  were subsequently implemented, verified, and closed as recorded above; no next
  task was started and no merge was performed.

## Previously Completed Task — T275
- Task: T275 — Generation collection creation and point upsert
- Verified implementation commit: `216545889b0804306e27f6b0883c34bb5e58bcc3`
  (`test(rag): cover ambiguous upsert completion states`) on
  `feature/t274-qdrant-infrastructure-handoff`, against base
  `f389895506ada89e32f0c36651ceb1c518f3d845`. Finalization is this
  documentation-only closure commit (`docs: record T275 verification and
  closure in project state`); its SHA is recorded in Git history.
- Scope delivered: `src/app/rag/vector_storage/qdrant_adapter.py` now implements
  `create_generation` with the fixed 768-dimensional Cosine vector schema and
  the seven exact payload indexes, and `upsert_points` with ordered point
  conversion, deterministic UUIDv5 IDs, adapter-added `generation_id`, and
  required `COMPLETED` operation status. Failures normalize to
  `VECTOR_GENERATION_BUILD_FAILED` while preserving the normalized underlying
  cause and cause chain. New `tests/rag/vector_storage/test_generation_build.py`
  covers the build operations; `tests/rag/vector_storage/test_qdrant_adapter.py`
  now guards that only T275's create/upsert methods exist. The specification and
  task breakdown record the T275 authorization. No T276/T277 lifecycle
  operations, composition wiring, retrieval behavior, endpoint, or application
  startup changes were added.
- Verification (2026-11-07; image `ai-customer-support-t275:local`, ID
  `sha256:a2eb29879c654efc03ee61f5681c5f16ce9a07e692ced0e7e2463372852e5a9d`;
  no repository bind mount in image verification runs):
  - Scope review: `git diff f3898955 2165458` was limited to
    `src/app/rag/vector_storage/qdrant_adapter.py`,
    `tests/rag/vector_storage/test_generation_build.py`,
    `tests/rag/vector_storage/test_qdrant_adapter.py`, the two authorized
    specification files, and `specs/project-state.md`. No unrelated files,
    secrets, configuration, or startup changes.
  - Pinned API confirmation inside the image: `qdrant-client` 1.20.0.
    `QdrantClient.create_collection` returns `bool` from REST
    `InlineResponse2001.result`; `create_payload_index(..., wait=True)` and
    `upsert(..., wait=True)` return `UpdateResult`; `UpdateStatus` contains
    `ACKNOWLEDGED`, `COMPLETED`, and `WAIT_TIMEOUT`. This matches the adapter's
    `created is True` and `COMPLETED` checks.
  - Build: `docker build -t ai-customer-support-t275:local .` → exit 0.
  - Focused offline suite: `docker run --rm --network none
    ai-customer-support-t275:local python -m pytest tests/rag/vector_storage -q`
    → 164 passed, exit 0.
  - Full regression: `docker run --rm --network ai-customer-support_default
    --add-host host.docker.internal:host-gateway --env-file .env
    ai-customer-support-t275:local python -m pytest tests -q` → 979 passed,
    7 skipped, exit 0. The skips are the 4 unchanged environment-conditional
    ingestion permission fixtures plus the 3 opt-in live embedding conformance
    tests (all require `RUN_LIVE_OLLAMA=1`). PostgreSQL was started with
    `docker compose up -d postgres` and reported `healthy`.
  - Startup/network boundary: an in-image `TestClient` run with `--network
    none`, `--env-file .env`, and `socket.socket.connect`,
    `socket.create_connection`, and `QdrantClient.__init__` replaced by failing
    stubs → application startup completed; `/health` returned HTTP 200
    `{"status": "ok"}`; `chunking_service` and `embedding_service` were present
    and no `vector_store` was constructed. No Qdrant network I/O occurred.
  - Negative requirements: the lifecycle guard asserts `create_generation` and
    `upsert_points` exist while `verify_generation`, `activate_generation`,
    `get_generation_info`, and `delete_generation` remain absent; invalid
    adapter request types are rejected before SDK I/O; a caller-supplied
    `generation_id` payload key is rejected by the approved contracts;
    unconfirmed creation/index operations and ambiguous upsert statuses
    (`None`, `ACKNOWLEDGED`) raise `VECTOR_GENERATION_BUILD_FAILED` without
    false success.
  - Boundary scan: only `src/app/rag/vector_storage/qdrant_adapter.py` imports
    `qdrant_client`/`httpx` under `src/`; public adapter signatures return
    application-owned DTOs. `git diff --check` → clean, exit 0.
  - No defect was found during verification; no implementation code changed.
- Outcome: T275 acceptance criteria in §5.2–§5.4, §7.1 (create/upsert), §8,
  §9, and the T275 task breakdown are met. T275 is closed. T276, T277, and T278
  were subsequently implemented, verified, and closed as recorded above.

## Previously Completed Task — T274
- Commit: `615caa8a2833f8dd34fe86cc51c989117cf0c9db`
  (`fix(rag): isolate qdrant url configuration test`), on
  `feature/t274-qdrant-infrastructure-handoff`. The prepared implementation is
  `51d9d50d724566a6da52d36e8b17c067d0ade310`; verification started from
  prepared ref `963c6c89fb11bf58adfa6a8256388a0376bb30ec` and base master
  `ded515068f03edfd3c3ccd8d7ca1a349130bf7db`. This project state record
  follows in a separate documentation commit.
- Scope delivered: `docker/qdrant/Dockerfile` extends the pinned
  `qdrant/qdrant:v1.20.0` base and installs only `curl` for the readiness
  probe. `docker-compose.yml` builds and tags
  `ai-customer-support-qdrant:v1.20.0`, runs
  `curl -fsS http://localhost:6333/readyz` with interval 10s, timeout 5s,
  5 retries, and a 10s start period, and makes the API depend on
  `condition: service_healthy`. `.env.example` documents `QDRANT_URL` and the
  optional `QDRANT_API_KEY`; `src/app/core/config.py` adds
  `qdrant_api_key: str | None = Field(default=None, min_length=1)`; and
  `tests/rag/vector_storage/test_configuration.py` covers the required URL,
  optional API key, rejected empty key, and documented connection settings. No
  Qdrant client construction, composition wiring, generation lifecycle,
  endpoint, persistence, or retrieval behavior was added.
- Verification (2026-11-06; app image `ai-customer-support-t274:local`, ID
  `sha256:124d43a3e40ba205a0ab375587c29e256d439f44b4c1e157de314a5c0026cd5b`;
  Qdrant image `ai-customer-support-qdrant:v1.20.0`, ID
  `sha256:a13177399a78a20dd70fa38c8b2614a4c202dcf95b29ac67065f4fe02479262e`;
  no repository bind mount in image verification runs):
  - Scope review: the base-to-head diff was limited to T274 files —
    `docker/qdrant/Dockerfile`, `docker-compose.yml`, `.env.example`,
    `src/app/core/config.py`,
    `tests/rag/vector_storage/test_configuration.py`, and the T274
    authorization/state documentation. No secret values were added.
  - `docker compose config` → exit 0. Pinned Qdrant image/tag, healthcheck
    command and timing, API `service_healthy` dependency, the
    `ai-customer-support_default` project network, and the
    `postgres_data`/`qdrant_data` named volumes are all present.
  - `docker compose build qdrant` → exit 0; the pinned base resolved to
    `qdrant/qdrant:v1.20.0@sha256:9bfc89f9914fc14876a88c05270685921a55b8877b254a98bcc1cc2f0a424cd2`.
  - `docker compose up -d qdrant` → exit 0; Qdrant reached `healthy` after
    5.73 seconds. Healthcheck exit 0 with output `all shards are ready`;
    `/readyz` returned HTTP 200 (`all shards are ready`) and `/healthz`
    returned HTTP 200 (`healthz check passed`).
  - Focused offline configuration tests: `docker run --rm --network none
    ai-customer-support-t274:local python -m pytest
    tests/rag/vector_storage/test_configuration.py -q` → 6 passed, exit 0.
  - Focused configuration tests with `--env-file .env` → 6 passed, exit 0.
  - Full regression: `docker run --rm --network ai-customer-support_default
    --add-host host.docker.internal:host-gateway --env-file .env
    ai-customer-support-t274:local python -m pytest tests -q` → 970 passed,
    7 skipped, exit 0. The 7 skips are the 4 unchanged environment-conditional
    ingestion permission fixtures plus the 3 opt-in live embedding conformance
    tests.
  - Startup boundary: an in-image `TestClient` run with `--network none`,
    `--env-file .env`, and `socket.socket.connect`, `socket.create_connection`,
    and `QdrantClient.__init__` all replaced by failing stubs → application
    startup completed; `/health` returned HTTP 200 `{"status": "ok"}`;
    `chunking_service` and `embedding_service` were present and no
    `vector_store` was constructed. No Qdrant network I/O occurred.
  - Compose runtime: `docker compose build api` → exit 0; `docker compose up
    -d api` reported Postgres and Qdrant `Healthy` before starting the API, and
    `GET /health` returned HTTP 200 `{"status": "ok"}`. The API and Qdrant
    containers were stopped afterward; the pre-existing PostgreSQL container
    was left running and healthy.
  - `git diff --check` → clean, exit 0.
  - Correction during verification: the first full-regression run failed
    `test_qdrant_url_remains_required` because `QDRANT_URL` from `--env-file`
    satisfied the "required" field through the process environment. The test
    now removes `QDRANT_URL`/`qdrant_url` with `monkeypatch`; focused and full
    suites were rerun successfully. No production code changed for this
    correction.
- Outcome: T274 acceptance criteria in §7.3, §7.4, §11, and the T274 task
  breakdown are met. The pinned custom Qdrant runtime, readiness healthcheck,
  Compose `service_healthy` dependency, optional API-key setting, and
  configuration tests are present; FastAPI startup remains free of Qdrant
  network I/O and `/health` remains independent. T274 is closed. T275, T276,
  T277, and T278 were subsequently implemented, verified, and closed as recorded
  above.

## Previously Completed Task — T273
- Task: T273 — Qdrant client adapter and exception normalization
- Commit: `fdff9c5afa71dfd96befad72359bc0e35930a036`
  (`feat(rag): add qdrant client adapter and exception normalization`),
  committed and pushed directly to `master`
- Scope delivered: pinned `qdrant-client==1.20.0`; Qdrant client adapter
  behind the application-owned `VectorStore` protocol; explicit client
  configuration and 10-second per-attempt timeout; SDK/application exception
  normalization, including wrapped HTTPX causes and both 429 paths; dedicated
  bounded vector-storage retry policy with at most 3 total attempts, 0.5-second
  base delay, 8-second maximum delay, and Full Jitter. Sleep and randomness are
  injectable for deterministic offline tests. No business lifecycle
  orchestration, startup network I/O, Docker infrastructure, or T274 settings
  work was introduced.
- Verification recorded for T273: focused vector-storage suite — 149 passed;
  full regression — 964 passed, 7 skipped. The implementation commit is
  `fdff9c5afa71dfd96befad72359bc0e35930a036`. No Qdrant startup connectivity
  check or generation lifecycle operations were added.
- Outcome: T273 acceptance criteria are met and the task is closed. T274 —
  Qdrant container infrastructure and application configuration — was
  subsequently implemented and verified; it is closed and recorded above.

## Previously Completed Task — T272
- Task: T272 — Vector storage contracts and application error taxonomy
- Commit: `2aed1a8eaa6a98f207feacce7599f7a7e781f461`
  (`fix(rag): align vector storage contracts and tests`); T272 also includes the
  preceding contracts/tests commits on `feature/t272-vector-storage-contracts`
  (`4ceb964`, `60c3a36`, `446d0c9`, `56c5fbd`, `9573f89`, `4196762`, `2f3798c`,
  `e9c8c06`, `58e7f8a`, `bfcdfc9`, `9c85e15`, `b00d475`). This project state
  record follows in a separate documentation commit
- Scope delivered: new `src/app/rag/vector_storage/` package with `contracts.py`,
  `exceptions.py`, `identity.py`, and `__init__.py`; new
  `tests/rag/vector_storage/` package with `test_contracts.py`, `test_errors.py`,
  and `test_identity.py`. No Qdrant SDK, network client, settings,
  infrastructure, persistence, endpoint, composition, or retrieval code was
  added or changed
- Contract implemented: frozen application DTOs for create generation, upsert
  points, verify generation, activate generation, generation info, and delete
  generation exactly as specified in §7.1, including fixed single-batch limits
  (1–64), 768-dimensional finite non-boolean vectors, exact eleven-field payload
  validation, required `chunk_id` equality, derived collection names, fixed
  `Cosine` distance results, and success-only result construction. The
  `VectorStore` protocol exposes the seven approved operations; `search` remains
  a reserved interface operation with no retrieval behavior. Application error
  taxonomy exposes all nine stable §9 codes with retryability metadata; build
  and activation failures preserve underlying retryability and cause. UUIDv5
  point identity uses the fixed project namespace
  `452d7fec-5a06-47c6-801d-eb0363eec5c4` and the original `chunk_id`; the
  canonical SHA-256 helper uses the approved sorted-compact UTF-8 JSON encoding
- Verification (2026-11-03; image `ai-customer-support-t272:local`, ID
  `sha256:2aec8aeb3cc1bb7c88144ae9abc8041d6d7e57647c6a0924c45624734abb7e2e`;
  no repository bind mount in image verification runs):
  - Build: `docker build -t ai-customer-support-t272:local .` → exit 0
  - Focused offline suite: `docker run --rm --network none
    ai-customer-support-t272:local python -m pytest tests/rag/vector_storage -q`
    → 63 passed, exit 0
  - Full regression: `docker run --rm --network ai-customer-support_default
    --add-host host.docker.internal:host-gateway --env-file .env
    ai-customer-support-t272:local python -m pytest tests -q` → 878 passed,
    7 skipped, exit 0. The 7 skips are the 4 unchanged
    environment-conditional ingestion permission fixtures plus the 3 opt-in
    live embedding conformance tests. No repository bind mount was used
  - Static import scan: the new package imports only Python standard-library
    modules and its own `app.rag.vector_storage` modules; no Qdrant, HTTPX,
    SQLAlchemy, psycopg, FastAPI, settings, persistence, or retrieval import
  - Correction during verification: the renamed error module test import was
    updated from the deleted `errors` module to `exceptions`; the batch-limit
    fixture now constructs 64 unique points; `CollectionInfo` now enforces the
    derived collection name and fixed `Cosine` distance, with boundary tests
  - `git diff --check`: clean, exit 0; the implementation diff is limited to the
    approved T272 package and focused tests
- Outcome: T272 acceptance criteria in the approved task breakdown are met. The
  application-owned vector storage contracts, point identity, protocol, and
  normalized error taxonomy exist with focused tests, and no Qdrant I/O,
  configuration, persistence, or retrieval behavior was introduced. T272 is
  closed; T273 has since been completed as recorded above.

## Previously Completed Task — T271 (composition-root wiring)
- Task: T271 — Composition-root wiring and Docker image verification
- Commit: `77f610da76fd67392dfb504303372123f596a56a`
  (`feat(rag): wire embedding service composition root`); this project state
  record follows in a separate documentation commit
- Scope delivered: new `src/app/rag/embeddings/composition.py` with
  `build_embedding_service(settings)`; `src/app/main.py` startup lifespan
  constructs the service and exposes it through `app.state.embedding_service`;
  new `tests/rag/embeddings/test_composition.py`. No endpoint, consumer,
  retrieval, Qdrant, persistence, metadata, DI framework, adapter, service,
  retry, settings, chunking, ingestion, LLM, domain, Dockerfile, or dependency
  code was added or changed
- Contract implemented: the factory constructs one
  `OllamaEmbeddingProvider(base_url=settings.ollama_url)` (approved D-6) and
  injects it into `EmbeddingService.from_settings(settings, provider)`. The
  service is constructed once per application process in the startup lifespan.
  The adapter receives the existing `OLLAMA_URL` setting explicitly; no
  competing setting or rename was introduced. The pinned provider/model
  identity and provisional dimension come from the contracts and adapter
- Verification (2026-10-25; image `ai-customer-support-t271:local`, ID
  `sha256:f21276c083890b483bac9bddbc430a29352f77eee58f04aa1197281f2add8d10`;
  no repository bind mount in image verification runs):
  - Build: `docker build -t ai-customer-support-t271:local .` → exit 0
  - Focused offline suite: `docker run --rm --network none
    ai-customer-support-t271:local python -m pytest tests/rag/embeddings -q` →
    303 passed, 3 skipped, exit 0
  - Full regression: `docker run --rm --network ai-customer-support_default
    --add-host host.docker.internal:host-gateway --env-file .env
    ai-customer-support-t271:local python -m pytest tests -q` → 815 passed,
    7 skipped, exit 0. Networking was required for PostgreSQL and the live
    Ollama integration test; the 7 skips are the 4 unchanged
    environment-conditional ingestion permission fixtures plus the 3 opt-in
    live embedding conformance tests. No repository bind mount was used
  - In-image startup without a bind mount and with `--network none`:
    `TestClient(app.main.app)` constructed `EmbeddingService` with
    `ollama:nomic-embed-text:v1.5`, dimension `768`, and `GET /health` returned
    `{"status": "ok"}`, exit 0
  - `git diff --cached --check`: clean, exit 0; the implementation diff is
    limited to the composition root, startup wiring, and composition tests
- Outcome: T271 acceptance criteria in §13 are met. The production embedding
  service is constructed once per process from settings, receives the approved
  base URL explicitly, and is exposed through `app.state.embedding_service`.
  No endpoint, consumer, retrieval, persistence, or DI framework was added. The
  approved T267–T271 sequence is complete. No next implementation task was
  started; the next SDD step is the RAG vector storage/retrieval specification
  gate.

## Previously Completed Task — T270 (live conformance)
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
- No implementation task is in progress. T277 — Generation information and
  explicit deletion — is complete and verified on
  `feature/t277-generation-info-deletion` at
  `7c7f85550b7a5ec7dbb446c72a4d1c5e8217d7dc`
  (`fix(rag): preserve generation management error causes`), following the
  prepared implementation commit
  `0c0d7716b7b68a46687b7334b91e81519a23a2c0` and base master
  `1a5f431860b11c5419a9a1bb9ced88ac57cecc9e`.
- T277 delivered actual collection metadata inspection with exact point counts
  and active-alias membership, plus explicit inactive-generation deletion with
  existence and active-alias guards. Focused vector-storage tests: 190 passed;
  live Qdrant lifecycle integration passed; full regression: 1005 passed,
  7 skipped.
- T277 is closed. T278 was subsequently implemented, verified, and closed as
  recorded above; the T277 branch was not merged.

## Task Ordering
1. T277 — Generation information and explicit deletion (complete and verified).
2. T278 — Vector storage composition and integration verification (complete and
   verified).

Each task requires its own authorized session and must follow its approved
specification and acceptance criteria.

## Verified Findings
- T278 verification (2026-11-09; commit
  `e63952fad1ba2c12477e02cfa384512242b6320e`, prepared implementation
  `4bd41543dde2cc4c52299cfaa0d2b702082cae6b`, base
  `b08225e864ad386f0a558620e9343d318caec903`):
  `build_vector_store(settings)` constructs one `QdrantClientConfig` from the
  explicit Qdrant URL and optional API key and delegates to the approved
  `QdrantClientAdapter.from_config`. FastAPI lifespan exposes exactly one
  application-owned instance as `app.state.vector_store`; construction and
  startup perform no Qdrant network I/O because the adapter disables SDK
  compatibility checks. `/health` remains static and independent. One in-scope
  startup-test defect was fixed in `e63952f`: replacing the `socket.socket`
  class also blocked anyio's internal `socketpair()`; the guard now blocks only
  outbound `connect`/`connect_ex`/`create_connection`. The composed store
  completed the real Qdrant lifecycle (create → upsert → verify → activate →
  inspect → inactive delete) and cleaned up its alias and collections. Focused
  suite: 193 passed, 1 skipped; integration: 1 passed; full regression: 1008
  passed, 8 skipped; in-image `--network none` startup completed with a
  `QdrantClientAdapter` present, `/health` HTTP 200, and no Qdrant request.
  `git diff --check` clean.
- T277 verification (2026-11-09; commit
  `7c7f85550b7a5ec7dbb446c72a4d1c5e8217d7dc`, prepared implementation
  `0c0d7716b7b68a46687b7334b91e81519a23a2c0`, base
  `1a5f431860b11c5419a9a1bb9ced88ac57cecc9e`):
  `QdrantClientAdapter.get_generation_info` reads the derived collection,
  requires one unnamed dense vector configuration, returns the actual vector
  dimension and distance, uses an exact point count, and reports `is_active`
  only when the collection is the current `knowledge_vectors_active` target;
  missing collections raise `VECTOR_GENERATION_NOT_FOUND`. `delete_generation`
  derives the collection name, verifies existence, rejects the active alias
  target, re-reads alias state immediately before deletion, requires an explicit
  `True` confirmation, never mutates the alias or performs automatic cleanup,
  and returns the immutable confirmed result only after deletion; missing
  collections raise `VECTOR_GENERATION_NOT_FOUND` and active deletion raises
  `VECTOR_GENERATION_ACTIVE_DELETE_REJECTED`. One in-scope cause-chain defect
  was fixed in `7c7f855`; focused tests 190 passed, live Qdrant lifecycle
  integration passed, full regression 1005 passed with 7 skips, and the startup
  boundary remained free of Qdrant network I/O.
- T276 verification (2026-11-08; commit
  `b898f65a0e2e5ac538ddcf0bd9ee54c45f573004`, prepared implementation
  `b86e89542f73a6f6d9dd99c0ca98dfa308940296`, base
  `92444a9c3a05fec79b9603df53666afd102f042f`):
  `QdrantClientAdapter.verify_generation` reads the derived collection, requires
  one unnamed 768-dimensional Cosine vector configuration, compares the exact
  Qdrant count with the expected point count, returns the immutable
  `GenerationVerificationResult` only when all checks pass, and normalizes every
  failure to `VECTOR_GENERATION_BUILD_FAILED` with the normalized cause chain.
  `QdrantClientAdapter.activate_generation` refuses activation without a prior
  successful verification in the same adapter, re-verifies immediately before
  switching, validates the current active alias target, and performs one atomic
  `update_collection_aliases` call (create-only for first activation,
  delete-plus-create for replacement), requiring an explicit `True`
  confirmation. Lost responses are reconciled against alias state; the previous
  generation is retained; failure leaves the alias unchanged; and all failures
  normalize to `VECTOR_GENERATION_ACTIVATION_FAILED`. One test-double defect was
  found and fixed (unset alias attributes read directly); production code was
  unchanged. Focused offline suite: 178 passed. Live integration against Qdrant
  v1.20.0 passed first activation, replacement activation, retention,
  idempotent already-active activation, wrong-count and missing-collection
  rejection, unverified-activation rejection, post-verification invalidation,
  and zero-point verification. Full regression: 993 passed, 7 skipped. Startup
  with networking disabled and socket/`QdrantClient` stubs completed with
  `/health` HTTP 200 and no `vector_store`; `git diff --check` clean.
- T274 verification (2026-11-06; commit
  `615caa8a2833f8dd34fe86cc51c989117cf0c9db`):
  `docker/qdrant/Dockerfile` extends `qdrant/qdrant:v1.20.0` and installs only
  `curl`; `docker-compose.yml` builds
  `ai-customer-support-qdrant:v1.20.0`, uses
  `curl -fsS http://localhost:6333/readyz` with the approved timing, and
  requires `condition: service_healthy`; `.env.example` documents
  `QDRANT_URL` and the optional `QDRANT_API_KEY`;
  `src/app/core/config.py` defines `qdrant_api_key` as absent-or-non-empty; and
  focused configuration tests cover the URL, optional key, rejected empty key,
  and example documentation. `docker compose config` and the Qdrant image build
  exited 0; the Compose Qdrant healthcheck reached `healthy` in 5.73 seconds
  with output `all shards are ready`. Focused configuration tests: 6 passed;
  full regression: 970 passed, 7 skipped. With networking disabled and socket
  and `QdrantClient` construction stubbed to fail, startup completed, `/health`
  returned HTTP 200, and no Qdrant network I/O occurred. `docker compose up -d
  api` started the API only after Postgres and Qdrant were healthy, and
  `GET /health` returned HTTP 200. `git diff --check` was clean.
- T273 implementation (2026-11-06; commit
  `fdff9c5afa71dfd96befad72359bc0e35930a036`):
  `src/app/rag/vector_storage/qdrant_adapter.py` implements the Qdrant SDK
  boundary behind the application-owned `VectorStore` protocol. The adapter
  builds the client from explicit configuration, applies the 10-second
  per-attempt timeout, and normalizes SDK exceptions, wrapped HTTPX causes,
  rate-limit responses, parsing failures, and unknown failures into the
  application-owned taxonomy without exposing SDK types or raw response bodies.
  `src/app/rag/vector_storage/retry.py` implements a vector-storage-local
  retry policy, independent of LLM retry: maximum 3 total attempts, 0.5-second
  base delay, 8-second maximum delay, Full Jitter
  (`random.uniform(0, min(0.5 * 2**n, 8))`), and a separate 10-second
  per-attempt timeout. Sleep and random sources are injectable for deterministic
  tests. Focused vector-storage suite: 149 passed; full regression: 964 passed,
  7 skipped. Commit is pushed to `master`. No lifecycle orchestration,
  startup network I/O, container configuration, or generation persistence was
  introduced.
- T272 implementation (2026-11-03):
  `src/app/rag/vector_storage/contracts.py` defines the frozen application DTOs
  `CreateGenerationRequest`, `CollectionInfo`, `UpsertPointInput`,
  `UpsertPointsRequest`, `UpsertPointsResult`, `VerifyGenerationRequest`,
  `GenerationVerificationResult`, `ActivateGenerationRequest`,
  `GenerationActivationResult`, `GetGenerationInfoRequest`, `GenerationInfo`,
  `DeleteGenerationRequest`, and `GenerationDeletionResult`, plus the
  `VectorStore` protocol. Validation enforces 64-character lowercase hex
  generation/embedding-config IDs, 768-dimensional finite non-boolean vectors,
  batches of 1–64 unique chunk IDs and derived point IDs, the exact eleven
  non-generation payload fields with matching `chunk_id`, derived
  `knowledge_vectors_g_<generation_id>` collection names, fixed `Cosine`
  distance for collection and verification results, and success-only result
  objects. `search` is present only as a reserved protocol operation.
  `src/app/rag/vector_storage/identity.py` defines the fixed project namespace
  `452d7fec-5a06-47c6-801d-eb0363eec5c4`, canonical sorted-compact UTF-8 JSON
  SHA-256, and `UUIDv5(PROJECT_VECTOR_NAMESPACE, chunk_id)` point identity.
  `src/app/rag/vector_storage/exceptions.py` defines all nine stable §9 error
  codes with retryability metadata; build and activation failures preserve the
  underlying cause and retry eligibility. Focused offline suite: 63 passed;
  full regression: 878 passed / 7 skipped; static import scan found no Qdrant,
  HTTPX, SQLAlchemy, psycopg, FastAPI, settings, persistence, or retrieval
  imports; `git diff --check` clean.
- T271 implementation (2026-10-25):
  `src/app/rag/embeddings/composition.py` defines
  `build_embedding_service(settings)`, which constructs one
  `OllamaEmbeddingProvider(base_url=settings.ollama_url)` (approved D-6) and
  injects it into `EmbeddingService.from_settings(settings, provider)`.
  `src/app/main.py` calls the factory in the startup lifespan and exposes the
  result through `app.state.embedding_service`; the service is constructed once
  per process. `tests/rag/embeddings/test_composition.py` covers the factory
  identity and settings mapping, the explicit base URL, startup exposure and
  instance reuse, `/health`, and the absence of a new endpoint, consumer, or DI
  framework. Focused offline embeddings suite: 303 passed / 3 skipped; full
  regression: 815 passed / 7 skipped; in-image startup with `--network none`
  constructed `EmbeddingService` (`ollama:nomic-embed-text:v1.5`, dimension
  768) and served `/health` with HTTP 200; `git diff --cached --check` clean.
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
- Latest full test run: 993 passed, 7 skipped (2026-11-08, `pytest tests` from
  `ai-customer-support-t276:local` with PostgreSQL and Qdrant running and network
  access for the live Ollama integration test; the skips are the 4 unchanged
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
- Phase 4 RAG: ingestion (T255–T259), chunking (T260–T266), and the embeddings
  sequence (T267–T271) are complete. The asset is vendored, the dependency pin
  is present, and input-length compatibility is recorded as `506 <= 2048`. T264
  closed verification-only, T265 packaged and verified the asset in the image,
  T266 production-wired the chunking composition root, T270 completed live
  Ollama conformance, and T271 production-wired the embedding composition root.
  The Vector Storage specification and task breakdown are approved. T272–T278
  are complete and closed.
- Embeddings specification: `specs/rag/knowledge-document-embeddings.md` is
  approved at Revision 2 (2026-10-24) and its implementation sequence T267–T271
  is complete. Decisions D-1 through D-6 are resolved as recorded in the
  specification's §2.3 and §2.4. T270 observed dimension `768`, which equals
  the provisional expected value and is now confirmed by live measurement; the
  served model digest is recorded only as T270 evidence and is not verified at
  runtime in V1; and D-6 preserves the existing `OLLAMA_URL`/`OLLAMA_BASE_URL`
  inconsistency without changing LLM behavior.
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
- Vector Storage specification and task breakdown are approved. T272–T278 are
  complete and closed. Retrieval, metadata filtering behavior,
  context construction, source attribution, evaluation, and RAG failure
  handling outside storage remain separate SDD cycles.
- Retry concrete defaults (chosen in T253) may be revisited during future
  hardening; not a Phase 3 blocker.

## Rules
- Specifications are the source of truth.
- Never start RAG before Phase 3 closure.
- Implement only one task per session.
- Do not repeat completed audits unless evidence is stale
  or a specific change requires re-verification.
- Update this file at every verified task closure.
