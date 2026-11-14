# Knowledge Retrieval — Dependency-Ordered Task Breakdown

- **Status:** Approved for planning on 2026-11-14; no implementation task is currently authorized.
- **Specification:** `specs/rag/knowledge-retrieval.md`
- **Subsystem:** Phase 4 — RAG / Knowledge Retrieval
- **Baseline:** Vector Storage T272–T278 is verified and merged.
- **Execution rule:** One task per authorized session. Implement only the named task, run its acceptance checks, verify, close, and stop.

## 1. Governing Rules

1. The Retrieval SDD and this task breakdown are the source of truth.
2. Approval of R-1–R-13 and R-15–R-21 does not authorize implementation. R-14 approves sequencing only.
3. Retrieval implementation MUST NOT begin until the Embeddings query-operation amendment and the separate Vector Storage generation-identity amendment are both approved, implemented, verified, and closed.
4. The exact technical contract, metadata mechanism, migration/backfill/rebuild policy, and implementation tasks for the Vector Storage amendment MUST be authored and approved in that separate amendment. This breakdown does not pre-approve those details.
5. No retrieval HTTP endpoint, chat workflow, context construction, source attribution, reranking, hybrid search, evaluation framework, or Agent integration is included.
6. Every task must preserve all-or-nothing behavior, deadlines, cancellation, privacy, and no-startup-network-I/O requirements.
7. A failed verification reopens the owning task. Do not silently patch another task or proceed.

## 2. Dependency Overview

```text
T279 Embeddings query-operation amendment (specification only)
  ↓ approval
T280 Embeddings query-operation implementation + verification
  ↓ close
T281 Vector Storage generation-identity amendment (separate SDD + task plan)
  ↓ separate approval
Vector Storage amendment implementation tasks (owned by that amendment)
  ↓ verify and close all amendment tasks
T282 Retrieval capacity/topology sizing decision (documentation only)
  ↓ approve numeric per-process limits
T283 Retrieval contracts, errors, and configuration
  ↓
T284 Typed VectorStore search contract + Qdrant adapter search
  ↓
T285 Retrieval service, compatibility gate, and result contract
  ↓
T286 Deadline, bounded admission, and metadata-only observability
  ↓
T287 Composition wiring and offline integration tests
  ↓
T288 Live conformance, full regression, and Retrieval closure
```

The Vector Storage amendment implementation tasks are intentionally not numbered or specified here. Their separate approved amendment breakdown owns task IDs, scope, migration/rebuild behavior, and acceptance criteria. T282–T288 are blocked until that amendment is fully closed.

## 3. Upstream Amendment Gates

| Task | Scope | Deliverable / acceptance | Dependencies |
|---|---|---|---|
| **T279 — Embeddings query-operation amendment (specification only)** | Amend `specs/rag/knowledge-document-embeddings.md` to define typed `embed_query(query)` and its immutable result contract. Specify how document/query operations expose the same explicit embedding-space identity while applying distinct task prefixes. Define validation, timeout/retry reuse, errors, config identity, tests, and compatibility guarantees. | Separately reviewable Embeddings amendment with exact contracts, file placement, tests, and task breakdown. No production code changes. | Retrieval SDD and task breakdown approved. |
| **T280 — Embeddings query-operation implementation** | Implement only the approved T279 amendment: typed query embedding operation, immutable query result/identity contract, query prefix exactly once, shared provider/model configuration, dimension/finiteness validation, timeout/retry behavior, and compatibility. | Focused offline tests; opt-in live Ollama conformance where required; full regression; no fake Chunk objects; no Qdrant dependency; no startup network I/O; verified closure. | T279 explicitly approved; separate task authorization. |
| **T281 — Vector Storage generation-identity amendment (specification only)** | Create a separate amendment to `specs/rag/knowledge-vector-storage.md`. Define trusted generation-level `embedding_config_id` metadata, how `GenerationInfo` exposes it, how generation verification validates it (including zero-point generations), and how missing/malformed identity fails closed. Define exact metadata storage, migration/backfill/rebuild, and compatibility policy. | Separately approved Vector Storage amendment and its own dependency-ordered implementation/verification breakdown. No production code changes in T281. | T279/T280 closed; Retrieval SDD and this breakdown approved. |
| **Vector Storage amendment implementation tasks** | Implement only tasks created by the approved T281 amendment. | All amendment tasks individually verified and closed; `GenerationInfo` provides trusted identity and generation verification guarantees it. Task IDs and acceptance criteria belong to the amendment breakdown, not this document. | T281 approved. |

## 4. Retrieval Implementation Tasks (Blocked Until Both Amendments Close)

| Task | Scope | Acceptance criteria | Dependencies |
|---|---|---|---|
| **T282 — Retrieval capacity and deployment-topology sizing** | Documentation/review only. Inspect actual application worker/process/replica topology and upstream Embeddings/Qdrant capacity. Select and record numeric per-process concurrency and finite queue capacities; document deployment-wide multiplication and rationale. Do not invent a distributed/global limit. | Numeric values, setting names, defaults, bounds, and topology assumptions are added to the Retrieval specification/task record and explicitly approved before runtime implementation. No production code changes. | T280 and all Vector Storage amendment tasks closed. |
| **T283 — Retrieval contracts, request validation, configuration, and errors** | Add immutable application-owned request/options/filter/result/candidate contracts and Retrieval-owned errors. Add `retrieval_max_query_length` and approved operational settings. Validate query, limit, filter allowlist/cardinality, and types before any upstream call. | Tests cover R-3, R-5, R-6, R-10, R-13, R-15, R-16, R-18. Invalid input makes zero Embeddings/VectorStore calls. Retrieval application layer imports no Qdrant SDK, HTTPX, FastAPI, database, or provider-specific modules. | T282 approved; both upstream amendment gates closed. |
| **T284 — Typed VectorStore search contract and Qdrant adapter search** | Replace the reserved search placeholder with typed application-owned request/result DTOs. Implement active-alias dense Cosine search and server-side exact-match filters in the Qdrant adapter. Preserve payload and score; normalize SDK failures through Vector Storage taxonomy. | Pinned `qdrant-client==1.20.0` contract tests; offline adapter tests; filter AND/OR semantics; top-k; empty result; tie-order preservation; malformed payload handling; no caller-controlled collection/alias/raw SDK filter; SDK types/exceptions do not escape. | T283; Vector Storage amendment closed. |
| **T285 — Retrieval service, compatibility gate, and result envelope** | Implement RetrievalService. Validate request, obtain active generation metadata, call `embed_query`, compare query embedding identity with trusted active-generation identity before search, search active alias, validate candidates, enforce generation equality, and return the complete envelope. Map normalized upstream errors and preserve causes. | Missing active generation differs from empty results; incompatible/missing identity prevents search; zero-point active generation returns valid empty result with generation identity; candidate mismatch/malformed payload fails all-or-nothing; no partial results; no second retry loop; cancellation propagates. | T284 and T280; trusted generation identity from closed Vector Storage amendment. |
| **T286 — Deadline, bounded admission, and observability** | Implement 10-second monotonic overall deadline, 5-second embedding cap, 3-second search cap, shared remaining budget, bounded per-process concurrency/finite queue using T282-approved values, cancellation-safe queue handling, and structured metadata-only events. | Fake-clock tests; retries consume same budget; no stage after expiry; overall expiry maps to `RetrievalDeadlineExceeded`; full queue maps to `RetrievalCapacityExceeded`; queued expiry maps to deadline error; cancellation removes waiter; telemetry excludes query/content/vector/filter values/secrets/exception text. | T285 and T282 approval. |
| **T287 — Composition wiring and offline integration verification** | Wire RetrievalService once through existing application composition/lifespan using existing EmbeddingService and VectorStore. Add service integration tests with deterministic fakes. | One RetrievalService in `app.state`; startup performs no network I/O; no endpoint; offline tests cover full request/result path and negative requirements; existing subsystem tests remain green; `git diff --check` clean. | T286. |
| **T288 — Live conformance, full regression, and Retrieval closure** | Run explicitly gated Ollama query-embedding conformance and Qdrant-backed retrieval integration against approved pinned versions. Record evidence and close subsystem. | Live query vector compatible with active generation; tests cover active alias, filters, zero-result generation, provenance, and cleanup of test-owned resources; focused suites and full regression pass; startup/network boundary verified; project-state updated; no subsequent task started. | T287. |

## 5. Cross-Task Test and Verification Rules

- Offline unit tests must not require Ollama, Qdrant, PostgreSQL, or network access.
- Live Ollama and Qdrant tests must be opt-in, explicitly gated, and isolated from production data.
- Qdrant integration tests must use uniquely owned test generations/aliases and clean up only resources created by the test.
- Verify the exact pinned client API before implementing adapter behavior.
- Query/document embedding compatibility uses explicit identity, not vector dimension alone.
- Filter rejection and compatibility failures occur before Qdrant search.
- A successful empty result still reports trusted active generation ID.
- No raw infrastructure exception escapes application boundaries; no public error/log leaks sensitive inputs.
- Verify the 10-second deadline with a monotonic clock and cancellation behavior.
- Verify per-process concurrency/queue settings against actual deployment topology; do not claim global admission control.
- Run focused tests, full regression, and `git diff --check` for each applicable task.
- Record exact commands, versions, outcomes, and skips in `specs/project-state.md`. Never claim a check that was not run.

## 6. Implementation Authorization

- **Current authorized implementation task:** None.
- T279 is next and is **specification-only**; it requires separate explicit authorization.
- T280 requires T279 approval and its own explicit authorization.
- T281 follows closure of T280 and is specification-only; it requires separate review/approval.
- Vector Storage amendment implementation is authorized only by its own approved task breakdown and individual task authorization.
- T282–T288 remain blocked until both upstream amendments are fully verified and closed.
- Completion of one task does not authorize the next task automatically.
