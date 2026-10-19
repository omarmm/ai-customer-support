# Knowledge Document Ingestion Specification

Status: Approved

- Feature: Knowledge Document Ingestion
- Phase: Phase 4 — RAG (first specification)
- Implementation authority: Approval of this specification defines the contract only. It does not authorize implementation. The SDD workflow (architecture/contract → task scope and acceptance criteria → implementation) still applies, one task per session.

### 1. Purpose

Define a deterministic, testable mechanism for discovering, loading, validating, and normalizing knowledge documents into a canonical form. This is the first explicit boundary of the RAG subsystem defined in `specs/tech-stack.md`. Chunking, embedding generation, vector storage, and retrieval remain separate boundaries with their own specifications.

### 2. Responsibilities

- Discover files under a configured source root, recursively and deterministically.
- Classify entries as supported documents, unsupported files, or document-limit exclusions.
- Load and decode supported files as UTF-8.
- Validate size, encoding, non-emptiness, and path containment.
- Normalize line endings; otherwise preserve content exactly.
- Extract metadata: relative source path, format, original size, title, and a deterministic content-version ID.
- Produce a per-document outcome set and an aggregate run result with well-defined counts.
- Fail predictably through a typed error contract that separates per-file failures from structural failures.

### 3. Architecture

Data flow:

```
Source root
    ↓
Discover → Classify → Sort → Apply limit
    ↓
Per file:
    Containment check → Size check → Read → Decode
    → Normalize → Validate → Extract metadata
    ↓
IngestionResult
```

- Component boundary: `src/app/rag/ingestion/`.
- Ingestion must not depend on HTTP frameworks, LLM providers, embedding models, vector databases, or business rules.
- The only I/O is reading files beneath the source root. No network calls, no code execution, no writes — the pipeline is side-effect free.
- Existing LLM, domain, and database behavior must remain unchanged.

### 4. Source and Formats

- The source root defaults to `knowledge/` at the repository root and is configurable (§10).
- Supported formats v1: Markdown (`.md`) and plain text (`.txt`), UTF-8 encoded.
- Extension matching is case-insensitive; the reported format is the normalized lowercase name (`markdown` or `text`).
- Traversal is recursive over regular directories. Directory symlinks are never traversed and contribute no entries.
- Files with unsupported extensions are skipped during classification and reported in `skipped` with reason `unsupported_format`. They are not candidates and are never read.
- An empty source root (no supported files) is not an error; the result is empty with zero counts.

### 5. Discovery, Ordering, and Determinism

- Discovered entries are identified by their path relative to the source root, normalized to POSIX separators.
- Candidates (supported files) are sorted by relative path in ascending Unicode codepoint order before any limit is applied.
- All three result collections — `documents`, `skipped`, and `failed` — are ordered by relative path ascending.
- Repeated runs over the same unchanged source tree and configuration produce equivalent results: same ordering, same IDs, same counts, same classifications.
- Directory traversal failures at any level, including an unreadable source root, are structural errors (§8) rather than silently incomplete discovery.

### 6. Size and Normalization Semantics

- `size_bytes` is the original file size in bytes, obtained before decoding and normalization.
- The per-document size limit applies to the original byte count and is checked before the file content is read, so an oversized file's content is never loaded.
- Normalization converts CRLF and bare-CR line endings to LF (`\n`). All other content is preserved exactly; no trimming, rewriting, or re-encoding of content.
- Normalized content must be valid UTF-8; otherwise the file fails with `DocumentDecodeError`.
- After normalization, a document whose content is whitespace-only fails with `EmptyDocumentError`.
- `document_id` is computed over the UTF-8 bytes of normalized content; `size_bytes` reflects the original file (§7).

### 7. Document Identity

The document ID is the lowercase hexadecimal SHA-256 digest of the UTF-8 byte sequence obtained by encoding the normalized content:

```python
document_id = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()
```

The hash input is the normalized content after CRLF and bare-CR line endings have been converted to LF (`\n`).

- Identical normalized content produces the same ID, including when it occurs at multiple source paths. Each occurrence is ingested independently; every source path is preserved in the result.
- Duplicates are informational, not errors.
- The ID identifies a content version, not a unique logical document. Persistent document identity, update tracking, and source attribution are deferred to later specifications.

#### 7.1 Title extraction

- The title is the first ATX level-1 heading: scanning lines top to bottom, the first line whose trimmed content begins with `# ` (one hash followed by a space), outside fenced code blocks.
- A fence is a line whose trimmed content starts with ` ``` ` or `~~~`; fences toggle until the next matching fence line.
- The title is the heading text with leading/trailing whitespace trimmed and an optional trailing closing hash sequence removed (CommonMark ATX closing sequence).
- If no H1 exists, the title falls back to the filename stem; if the stem is empty, the title is the relative `source_path`.
- Setext headings are not recognized in v1.

### 8. Error Contract

Hierarchy under `src/app/rag/ingestion/exceptions.py`, mirroring the LLM boundary pattern.

Structural errors — raised, abort the run immediately:

- `IngestionError` — base class; never raised directly.
- `SourceRootError` — source root missing, not a directory, or unreadable; also raised for directory traversal failures at any level, carrying the offending relative path.

Per-file failures — classified, recorded in `failed`, processing continues:

- `PathContainmentError` — the fully resolved path (all symlinks resolved) escapes the resolved source root.
- `DocumentReadError` — stat or read fails (permissions, I/O error, broken symlink).
- `DocumentDecodeError` — content is not valid UTF-8.
- `EmptyDocumentError` — content is whitespace-only after normalization.
- `DocumentTooLargeError` — original byte count exceeds the configured limit.

Notes:

- `UnsupportedFormatError` is removed; unsupported extensions are skipped, not rejected. Every declared exception has a reachable role.
- Per-file exception types are constructed as classifications and recorded, not raised out of the pipeline.
- Path containment is checked for every candidate before any content is read. Content outside the root is never read, and a symlink escaping the root never has its target loaded.
- Per-file failures report the offending relative path, the stable `error_type` name, and a safe message — paths and identifiers only, never file content or secrets.
- Invalid configuration values (non-positive limits) fail at application startup through settings validation (§10), not through an ingestion exception.

### 9. Result Contract

KnowledgeDocument

| Field         | Meaning                                                            |
| ------------- | ------------------------------------------------------------------ |
| `document_id` | SHA-256 of normalized content's UTF-8 bytes, lowercase hexadecimal |
| `source_path` | Relative POSIX path within the source root                         |
| `title`       | Defined in §7.1                                                    |
| `format`      | `markdown` or `text`                                               |
| `content`     | Normalized UTF-8 content                                           |
| `size_bytes`  | Original file size in bytes, before normalization                  |

IngestionResult

| Field              | Meaning                                                   |
| ------------------ | --------------------------------------------------------- |
| `documents`        | Successfully ingested documents, ordered by `source_path` |
| `skipped`          | `{path, reason}` entries, ordered by path                 |
| `failed`           | `{path, error_type, message}` entries, ordered by path    |
| `discovered_count` | All files discovered, supported and unsupported           |
| `candidate_count`  | Supported files that became candidates                    |
| `succeeded_count`  | `len(documents)`                                          |
| `skipped_count`    | `len(skipped)`                                            |
| `failed_count`     | `len(failed)`                                             |
| `has_failures`     | `failed_count > 0`                                        |

Skipped reasons:

- `unsupported_format` — extension not `.md`/`.txt`; content never read; not a candidate.
- `document_limit_exceeded` — sorted candidate beyond `knowledge_max_documents_per_run`; content never read.

Count invariants:

```
discovered_count = succeeded_count + failed_count + skipped_count

candidate_count = succeeded_count + failed_count
                  + skipped entries with reason document_limit_exceeded
```

No result is silently truncated: every discovered file appears in exactly one collection with a defined classification.

### 10. Configuration

Additive settings following the existing `Settings` conventions in `src/app/core/config.py`.

| Setting                           | Environment variable              | Default           | Meaning                                       |
| --------------------------------- | --------------------------------- | ----------------- | --------------------------------------------- |
| `knowledge_dir`                   | `KNOWLEDGE_DIR`                   | `knowledge`       | Source root                                   |
| `knowledge_max_document_bytes`    | `KNOWLEDGE_MAX_DOCUMENT_BYTES`    | `1048576` (1 MiB) | Maximum original bytes per document           |
| `knowledge_max_documents_per_run` | `KNOWLEDGE_MAX_DOCUMENTS_PER_RUN` | `1000`            | Maximum candidate documents processed per run |

Source-root resolution:

- The default relative value `knowledge` is resolved relative to the repository root, not the process's current working directory.
- Any configured relative `knowledge_dir` value is likewise resolved relative to the repository root.
- An absolute configured path is treated as an absolute source root, subject to the existing configuration and security conventions.
- The effective source root must be resolved before discovery and used consistently for path-containment checks.

Configuration validation:

- All three settings are optional with defaults; local development works with no environment changes.
- Limits must be positive; invalid values fail clearly at startup via Pydantic field constraints, per the configuration specification.
- All three are documented in `.env.example`, matching the existing optional-variable pattern.

### 11. Security

- Document content is untrusted data: never executed, never evaluated as a template, never passed to an LLM by this component.
- Content outside the resolved source root is never read; symlink escapes are rejected per-file before reading.
- Size and count limits bound memory and runtime; directory symlinks are never followed, preventing traversal loops.
- Logs and exceptions contain metadata only — never document content.

### 12. Testing Requirements

Automated unit tests must be deterministic and offline — no network access, no LLM, no Qdrant, no PostgreSQL.

Tests must cover:

1. Recursive discovery; supported vs. unsupported extensions; unsupported files reported and never read.
2. Stable ordering of all collections; repeated runs produce equivalent results.
3. Valid UTF-8 ingestion with correct metadata (`format`, `size_bytes`, `source_path`).
4. Title extraction from the first H1; H1 inside a fenced code block ignored; fallback to filename stem.
5. CRLF and bare-CR normalization; `size_bytes` reflects the original file while `document_id` reflects normalized content.
6. SHA-256 identity; identical content at two paths yields one ID and two preserved source paths.
7. Empty and whitespace-only files; oversized files with content never read; invalid UTF-8.
8. Missing, non-directory, and unreadable source roots raise `SourceRootError` (unreadable-root tests use permission fixtures where the environment permits, otherwise skip with a documented reason).
9. Unreadable subdirectory is structural, not silently incomplete.
10. Symlink escaping the root is rejected per-file with no external content read; symlink within the root ingested normally; directory symlinks not traversed; broken symlink yields `DocumentReadError`.
11. Document-limit behavior: candidates sorted before the limit; excluded candidates reported as `document_limit_exceeded` with content unread; counts match the invariants.
12. Error messages and results never contain document content.
13. Idempotency: identical unchanged inputs produce identical IDs, ordering, and counts.
14. Source-root resolution: default and configured relative paths resolve against the repository root, independently of the process's current working directory.
15. Absolute source-root behavior follows the specified configuration convention, with containment enforced relative to the effective source root.
16. Hash determinism: the SHA-256 input is exactly `normalized_content.encode("utf-8")`; line-ending variants that normalize to identical content produce identical IDs.

### 13. Acceptance Criteria

- Supported documents under the source root are ingested into `KnowledgeDocument` objects with complete, correct metadata.
- Discovery, ordering, and results are deterministic and repeatable.
- Relative source-root configuration is resolved against the repository root, independently of the process's current working directory.
- Document IDs are derived from the UTF-8 bytes of normalized content according to §7.
- The pipeline is side-effect free and requires no network access.
- Per-file failures are collected and reported; structural failures raise immediately; no result is silently truncated.
- Path containment, size limits, and count limits are enforced with content-free error reporting.
- Every declared exception type has a tested, reachable role.
- The full test list in §12 passes offline.
- Existing LLM, domain, and database behavior is unchanged.

### 14. Out of Scope

- Chunking, embedding generation, Qdrant integration, semantic or hybrid retrieval, metadata filtering for retrieval, context construction, source attribution implementation, and RAG evaluation beyond this contract — each a later Phase 4 specification.
- Persistent PostgreSQL document registry, persistent document identity, and update tracking.
- HTTP endpoints and CLI wiring.
- Remote sources (URLs, object storage), watch/incremental sync, and formats beyond `.md`/`.txt`.
- Prompt or LLM interaction of any kind.

This specification does not authorize implementation.

### Decisions embedded in this draft (flagged for review)

These deterministic choices were made where the earlier draft left room:

- Extension matching is case-insensitive; reported format is `markdown`/`text` (§4).
- Title rule is fence-aware ATX-only; Setext headings excluded (§7.1).
- Directory symlinks are never traversed; file symlinks are resolved and containment-checked before reading (§5, §8).
- Traversal failures at any directory level are structural (`SourceRootError`), preventing silently incomplete knowledge bases (§5, §8).
- `DocumentReadError` is a per-file classification for permission/I/O/broken-symlink failures (§8).
- Oversized files are rejected via stat before their content is ever read (§6).
- Empty source root is a valid empty result, not an error (§4).
- Relative source roots resolve against the repository root, not the process's current working directory (§10).
- `document_id` hashes the UTF-8 bytes of normalized content, with line endings normalized first (§7).
- No remaining ambiguity or conflict with approved specifications was found during the prior read-only inspection.

### 15. Placement and Contract Changes

This section records the approved architecture and contract stage for this specification. It adds implementation-level detail only; sections 1–14 and the decisions log remain unchanged and authoritative for the contract.

#### 15.1 Module Layout

Component boundary: `src/app/rag/ingestion/`. Standard library only; no new runtime dependencies.

| File | Contents |
| --- | --- |
| `contracts.py` | `KnowledgeDocument`, `SkippedEntry`, `FailedEntry`, `IngestionResult` |
| `exceptions.py` | `IngestionError` base; `SourceRootError`; per-file classifications `PathContainmentError`, `DocumentReadError`, `DocumentDecodeError`, `EmptyDocumentError`, `DocumentTooLargeError` |
| `paths.py` | `default_repo_root`, `resolve_source_root` |
| `discovery.py` | `DiscoveryPlan`, `discover` |
| `loader.py` | `load_document`, `normalize_content`, `extract_title`, `content_id` |
| `service.py` | `KnowledgeIngestionService`, `from_settings` |

Indicative interfaces:

```python
def default_repo_root() -> Path: ...
def resolve_source_root(configured: str, repo_root: Path | None = None) -> Path: ...

def discover(source_root: Path, max_documents_per_run: int) -> DiscoveryPlan: ...
def load_document(
    source_root: Path, relative_path: str, max_document_bytes: int
) -> KnowledgeDocument | FailedEntry: ...

class KnowledgeIngestionService:
    def __init__(
        self,
        source_root: Path,
        max_document_bytes: int = 1_048_576,
        max_documents_per_run: int = 1000,
    ): ...
    @classmethod
    def from_settings(cls, settings, repo_root: Path | None = None) -> "KnowledgeIngestionService": ...
    def ingest(self) -> IngestionResult: ...
```

`DiscoveryPlan` is an internal discovery-phase type; it introduces no new public result contract.

#### 15.2 Result Contract and Construction Invariant

`IngestionResult` is a frozen dataclass that stores three collections as immutable tuples:

- `documents: tuple[KnowledgeDocument, ...]`
- `skipped: tuple[SkippedEntry, ...]`
- `failed: tuple[FailedEntry, ...]`

Counts are derived read-only properties, never stored fields:

- `succeeded_count = len(documents)`
- `skipped_count = len(skipped)`
- `failed_count = len(failed)`
- `candidate_count = succeeded_count + failed_count + (skipped entries with reason document_limit_exceeded)`
- `discovered_count = succeeded_count + failed_count + skipped_count`
- `has_failures = failed_count > 0`

`IngestionResult.build(documents, skipped, failed)` is the canonical construction path used by the service: it sorts each collection ascending by relative POSIX path, freezes them into tuples, and returns the instance.

Construction invariant — applies to every construction path: ordering and the §9 count invariants must not be bypassable by direct construction.

- Collections are normalized on construction: for any construction path, `__post_init__` re-sorts each collection ascending by path and coerces it to a tuple, so an unsorted or mutable input can never yield unsorted or mutable stored state.
- Counts are derived from the stored collections, so no construction path can produce counts that contradict the collections.

Therefore `build()` is the documented canonical path and the only path used by the service, while direct construction remains normalized and invariant-safe instead of being able to bypass ordering or counts.

#### 15.3 Exact Discovery Order

1. Resolve the effective source root (§15.6). This step performs no I/O.
2. Structural preconditions, in order: the root exists; the root is a directory; the first directory listing succeeds. Any failure raises `SourceRootError` and aborts the run.
3. Recursive traversal: depth-first, with children visited in ascending name order at every level. Directory symlinks are never entered.
4. A directory read or stat failure at any level raises `SourceRootError` carrying the relative path. An entry whose type cannot be determined also raises `SourceRootError`, because discovery cannot produce a complete candidate list.
5. Entry handling, in this exact order: a real directory is descended into; a symlink to a directory is ignored (not traversed, not reported); every other entry is classified by its entry-name extension, matched case-insensitively — `.md` yields format `markdown` as a candidate, `.txt` yields format `text` as a candidate, and anything else becomes a skipped entry with reason `unsupported_format`. Non-regular, non-symlink entries (FIFO, socket, device) are outside the file contract and are ignored.
6. Reported paths are normalized to POSIX separators and are relative to the source root.

#### 15.4 Exact Ordering and Limit

1. Candidates are sorted ascending by relative POSIX path (Unicode codepoint order, case-sensitive).
2. The limit is applied after sorting: the first `max_documents_per_run` candidates form the processed set; every remaining candidate becomes a skipped entry with reason `document_limit_exceeded`.
3. Excluded candidates are never stat'ed, never containment-checked, and never read.
4. Skipped entries (unsupported format and limit-excluded) are sorted ascending by path.
5. Loading processes the candidates sequentially in the same ascending order.
6. Final collections are ordered ascending: `documents` by `source_path`; `skipped` and `failed` by `path`, re-normalized in `build()`.

Determinism: an identical source tree with identical configuration produces identical collections, ordering, IDs, and counts.

#### 15.5 Exact Loading and Containment Order

For each processed candidate, the steps run in this exact order. The first failing step determines the outcome; later steps are not attempted.

1. Containment — `resolved = (source_root / relative_path).resolve(strict=False)` and `resolved_root = source_root.resolve(strict=True)`. A resolution error such as a symlink loop yields `DocumentReadError`. If `resolved` is not inside `resolved_root`, the file fails with `PathContainmentError`; no stat and no read occur. Only processed candidates reach this step.
2. Size — `stat()` the resolved path; failure yields `DocumentReadError`. If `st_size > max_document_bytes`, the file fails with `DocumentTooLargeError` and content is never read; otherwise `size_bytes = st_size`.
3. Bounded read — open the resolved path and read at most `max_document_bytes + 1` bytes; a read failure yields `DocumentReadError`. If the bytes read exceed the limit (the file grew between stat and read), the file fails with `DocumentTooLargeError`, keeping memory bounded.
4. Decode — strict UTF-8 decoding; failure yields `DocumentDecodeError`. No BOM stripping; content is preserved exactly.
5. Normalize — `\r\n` becomes `\n`, then bare `\r` becomes `\n`. Nothing else is altered.
6. Whitespace validation — content that is whitespace-only after normalization fails with `EmptyDocumentError`.
7. Metadata — `format` from the entry extension; `title` per §7.1 over normalized content; `document_id = sha256(content.encode("utf-8")).hexdigest()`; `source_path`; `size_bytes` from step 2.
8. Outcome — success appends a `KnowledgeDocument`; failure appends `FailedEntry(relative_path, error_type, message)`; processing continues with the next candidate.

Per-file failures are recorded in the result; structural errors raise. Error messages are built from paths and stable `error_type` names only, never content.

#### 15.6 Repository-Root Resolution

- `default_repo_root()` returns `Path(app.__file__).resolve().parents[2]` — the directory containing the `src` package that contains `app`. It is derived from the imported package location, never from the process working directory, and is correct both locally and under the Docker Compose layout (`.:/app`, `WORKDIR /app`, `PYTHONPATH=/app/src`).
- `resolve_source_root(configured, repo_root=None)`: absolute values are used as-is; relative values resolve against `repo_root`, which defaults to `default_repo_root()`.
- The effective source root is resolved before discovery and reused unchanged for every containment check.
- `repo_root` is injectable at the helper and service level, so tests never depend on the real checkout.

#### 15.7 Required Architecture Tests

| Case | Test |
| --- | --- |
| Different working directories | resolution is identical after changing the process working directory |
| Relative paths | `knowledge` resolves to `<repo_root>/knowledge`, not the working directory |
| Absolute paths | returned unchanged; containment is measured against that root |
| Docker layout | an injected `repo_root` simulates the `/app` layout deterministically; the real container check is required in T259 via `docker compose run --rm api python -c "from app.rag.ingestion.paths import default_repo_root; print(default_repo_root())"`, expecting `/app` |
| Construction invariant | unsorted or mutable inputs to `IngestionResult` yield sorted, immutable stored collections; direct construction cannot bypass ordering or counts |

Automated tests remain offline and environment-independent; the real Docker check is mandatory in T259.

### 16. Task Breakdown

Task IDs continue the project sequence: T252–T254 already exist, so T255–T259 are new and do not collide.

| Task | Scope (file scope only) | Acceptance criteria |
| --- | --- | --- |
| T255 — Contracts and error taxonomy | `src/app/rag/ingestion/__init__.py`, `contracts.py`, `exceptions.py`; `tests/rag/__init__.py`, `tests/rag/ingestion/__init__.py`, `test_contracts.py` | §8, §9, §15.2 — type shapes; derived counts and both count invariants; `build()` as the canonical path; ordering enforced on every construction path; every exception has a reachable role; content-free messages |
| T256 — Deterministic discovery and limit | `discovery.py`; `test_discovery.py` | §4, §5, §9, §15.3–§15.4 — traversal order, POSIX paths, unsupported skips, sorted limit, `document_limit_exceeded` content never read, directory-symlink rule, structural traversal errors; §12 tests 1, 2, 11 |
| T257 — Per-file loading pipeline | `loader.py`; `test_loader.py` | §6, §7, §7.1, §8, §15.5 — containment before stat, size before read, bounded read, decode, normalization, title, ID, first-failure classification; §12 tests 3–7, 10, 16 |
| T258 — Service, configuration, and root resolution | `service.py`, `paths.py`; additive fields in `src/app/core/config.py`; `.env.example`; `test_service.py`, `test_paths.py` | §10, §13, §15.6–§15.7 — working-directory independence, relative/absolute/`/app`-layout tests, constructor validation, `from_settings` without eager `get_settings()`, end-to-end counts, idempotency; §12 tests 8, 9, 12–15 |
| T259 — Final integration verification and closure (required) | No feature code | Focused ingestion suite and the full regression suite pass; Docker root-resolution check recorded; `git diff --check` clean; diff reviewed against §13; `specs/project-state.md` updated with task IDs, outcomes, commits, tests, and exactly one next task; closure commit follows the repository precedent |

Notes:

- Each of T255–T258 ends with focused tests green, no regression, and its own task commit.
- T259 is mandatory, not optional. A defect found there within approved scope reopens the owning task instead of being patched in T259.
- Implementing any task requires a separate authorized session; approving this design does not authorize implementation.
