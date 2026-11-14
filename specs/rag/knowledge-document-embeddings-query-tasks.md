# Embeddings Query Operation — Amendment Task Breakdown

- **Status:** Approved on 2026-11-14.
- **Amendment:** `specs/rag/knowledge-document-embeddings.md`, Amendment EMB-Q-001.
- **Parent task:** T279 — specification-only.
- **Implementation task:** T280 — separately authorized only after amendment approval.
- **Execution rule:** One task per authorized session. T279 performs documentation only; it must not change production code or tests.

## 1. Scope and governing decisions

This breakdown operationalizes the proposed query-operation amendment. The amendment is the source of truth; this file does not independently approve its design.

The target behavior is a single-query operation on the existing `EmbeddingService`:

```python
async def embed_query(self, query: str) -> QueryEmbedding: ...
```

The operation uses the existing provider, `EmbeddingConfig`, provider/model identity, query prefix, timeout, retry policy, and normalized error taxonomy. It returns an immutable `QueryEmbedding` carrying the same `embedding_config_id` as document embeddings. It does not create fake chunks, a second service/provider, or a Qdrant dependency.

## 2. Dependency sequence

```text
T279 — Specification-only amendment + this task breakdown
  ↓ explicit review and approval
T280 — Query operation implementation + offline tests + opt-in conformance
  ↓ local verification and closure
T281 — Separate Vector Storage generation-identity amendment
```

T280 does not start automatically when T279 is approved. It requires its own explicit task authorization. Retrieval implementation remains blocked until T280 and the separate Vector Storage amendment implementation/verification are closed, as already specified in `knowledge-retrieval-tasks.md`.

## 3. T280 — Query operation implementation

**Status:** Authorized by user on 2026-11-14.

### 3.1 Expected file scope

| File | Expected change |
|---|---|
| `src/app/rag/embeddings/contracts.py` | Add frozen `QueryEmbedding` contract and export it |
| `src/app/rag/embeddings/service.py` | Add `EmbeddingService.embed_query(query)`; reuse existing provider, config, timeout, retry policy, and normalization behavior |
| `tests/rag/embeddings/test_contracts.py` | Add immutable query-result and validation tests |
| `tests/rag/embeddings/test_service.py` | Add query input, prefix, provider invocation, response validation, retry, timeout, and cancellation tests |
| `tests/rag/embeddings/test_ollama_conformance.py` | Add query conformance under existing `RUN_LIVE_OLLAMA=1` gate, if the current test organization permits it |

No provider adapter change is expected: the current provider already accepts a sequence of prefixed strings and returns vectors. If implementation inspection shows an unavoidable provider-contract change, stop and request a separate specification amendment rather than expanding T280 silently.

### 3.2 Implementation requirements

1. Add `QueryEmbedding(config, vector, retry_count)` as a frozen dataclass.
2. Validate exact configured dimension, numeric finite values, immutable tuple storage, and non-negative integer retry count (reject booleans).
3. Expose `embedding_config_id` as a derived property equal to `config.config_id`.
4. Add `embed_query(query: str)`; reject non-string, empty, or whitespace-only input before provider invocation.
5. Preserve the original non-empty query string exactly; use trimming only for the emptiness check.
6. Prefix exactly once using `self._config.query_prefix`.
7. Call the existing provider with a one-element sequence and the configured per-attempt timeout.
8. Require exactly one returned vector; validate count, dimension, element types, and finiteness using stable Embeddings application errors.
9. Reuse the existing retry policy and provider-error normalization. Do not introduce a second retry loop or change document retry semantics.
10. Propagate cancellation unchanged.
11. Do not construct `Chunk`/`ChunkEmbedding` values or import Qdrant, database, HTTP framework, Retrieval, or `app.llm.*` modules.
12. Do not add settings, environment overrides, persistence, logs containing query/vector data, endpoints, or startup network I/O.

### 3.3 Offline acceptance tests

- Invalid query types and empty/whitespace-only queries fail before any provider call.
- Leading/trailing whitespace and all original query characters are preserved for valid input.
- Provider receives exactly one text with `search_query: ` applied exactly once.
- Provider receives the existing configured timeout.
- Exactly one valid vector returns a `QueryEmbedding`.
- Zero or multiple vectors fail with `empty_embeddings` or `count_mismatch`.
- Wrong dimension, malformed values, booleans, NaN, and infinity fail with the specified stable errors.
- Query result is immutable, finite, dimension-valid, and exposes the exact shared config ID.
- Query and document results from one service config have identical `embedding_config_id` values.
- Retryable provider failures retry within existing bounds and expose correct retry counts.
- Permanent provider failures and validation errors do not retry.
- Timeout applies to each provider attempt; cancellation propagates unchanged.
- Existing document embedding tests pass unchanged.
- Tests use fakes/mocks only; no live Ollama, Qdrant, PostgreSQL, or network is required.

### 3.4 Live conformance and regression

- Run live query conformance only with explicit `RUN_LIVE_OLLAMA=1`.
- Verify model identity and observed query vector dimension.
- Record exact command, environment gate, model tag, observed dimension, result, and skips in `specs/project-state.md`.
- Do not claim digest verification; existing D-1/D-2 remain unchanged.
- Run focused Embeddings tests, full regression, and `git diff --check`.
- Verify no Qdrant/network startup behavior was introduced.
- Close T280 only after all evidence is reviewed. If a result contradicts the approved amendment, stop and amend the specification.

## 4. T279 acceptance checklist (documentation-only)

- [x] Amendment EMB-Q-001 appended to the authoritative Embeddings specification.
- [x] Immutable query result contract and exact public API defined.
- [x] Shared config identity and distinct prefixes explained without changing document identity.
- [x] Input validation, no-truncation behavior, provider contract, timeout/retry, errors, cancellation, and privacy specified.
- [x] Offline tests, live conformance, compatibility, and negative requirements defined.
- [x] T280 implementation scope and acceptance criteria defined here.
- [x] `specs/project-state.md` and `specs/roadmap.md` reflect the draft/pending-review state accurately.
- [x] No production code or test files changed.
- [x] No implementation was included in T279.

## 5. Approval record

- **T279 status:** Approved by user on 2026-11-14.
- **T280 status:** Explicitly authorized by user on 2026-11-14; one-task scope only.
- **Current authorized implementation task:** T280 — Query operation implementation.
- **Stop condition:** Complete T280 implementation and its verification handoff, then stop. T281 is not authorized.
