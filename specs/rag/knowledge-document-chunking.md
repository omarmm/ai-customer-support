# Knowledge Document Chunking Specification

Status: Approved

- Feature: Knowledge Document Chunking
- Phase: Phase 4 — RAG (second specification)
- Approval: Day 26 (2026-10-21)
- Implementation authority: Approval of this specification defines the contract only. It does not authorize implementation. The SDD workflow (architecture/contract → task scope and acceptance criteria → implementation) still applies, one task per session.

### 1. Purpose

Define a deterministic, token-aware mechanism for splitting normalized `KnowledgeDocument` content into retrieval-sized `Chunk` objects while preserving exact source text, source provenance, and reproducible configuration identity. This is the second explicit boundary of the RAG subsystem defined in `specs/tech-stack.md`. Embedding generation, vector storage, retrieval, context construction, and index migration remain separate boundaries with their own specifications.

### 2. Responsibilities

- Accept `KnowledgeDocument` objects produced by ingestion.
- Tokenize document content through an approved, injected tokenizer.
- Split content into token-bounded chunks.
- Prefer paragraph, sentence, then word boundaries where they preserve the token limit.
- Apply bounded token overlap.
- Assign deterministic chunk IDs, configuration IDs, and contiguous per-document chunk indexes.
- Preserve exact source slices and Unicode code-point offsets.
- Retain sufficient metadata to trace every chunk to its source document and position.
- Produce a deterministic aggregate result that represents every input document, including zero-chunk documents.
- Remain pure and offline with respect to the chunking algorithm.

### 3. Architecture and Boundaries

Data flow:

```
KnowledgeDocument[]
        ↓
Tokenizer.tokenize(content) → TokenSpan[]
        ↓
Token window → boundary snap → exact source slice
        ↓
Chunk[]
        ↓
DocumentChunking[]
        ↓
ChunkingResult(config, documents)
```

- Component boundary: `src/app/rag/chunking/`.
- The chunking algorithm must use the Python standard library only.
- A tokenizer adapter may add one approved dependency in T263, after separate approval.
- Chunking must not depend on HTTP frameworks, LLM providers, embedding runtimes, Qdrant, PostgreSQL, or business rules.
- The chunking algorithm performs no I/O. A tokenizer adapter may load approved local model assets during initialization, but `tokenize()` itself must be offline, deterministic, and side-effect free.
- The adapter must document whether concurrent read-only use is safe; the chunking service does not assume thread safety beyond that declaration.
- Existing ingestion, LLM, domain, and database behavior must remain unchanged.

### 4. Inputs, Outputs, and Immutability

#### 4.1 Inputs

- Immutable `KnowledgeDocument` objects from the approved ingestion contract.
- An injected `Tokenizer` implementation.
- A validated `ChunkingConfig`.

Input documents must have unique `(source_path, document_id)` pairs. A duplicate pair is invalid input and raises `ValueError`; ingestion produces unique source paths, so this is a programmatic-invariant check.

No per-document or per-request configuration overrides are supported in the initial implementation.

#### 4.2 Outputs

- One `DocumentChunking` per valid input document, including documents that produce zero chunks.
- One `ChunkingResult` containing the effective `ChunkingConfig` and ordered `DocumentChunking` records.
- Input documents are never mutated.

#### 4.3 Immutability

`Chunk`, `DocumentChunking`, `ChunkingConfig`, and `ChunkingResult` are frozen dataclasses. Collections are immutable tuples. Construction normalizes ordering and validates invariants; invalid direct construction raises `ValueError`.

### 5. Tokenizer Protocol and Span Contract

#### 5.1 Protocol

```python
@dataclass(frozen=True)
class TokenSpan:
    start_offset: int  # Unicode code-point offset, inclusive
    end_offset: int    # Unicode code-point offset, exclusive


class Tokenizer(Protocol):
    @property
    def identity(self) -> str: ...

    def tokenize(self, text: str) -> tuple[TokenSpan, ...]: ...
```

A `TokenSpan` is the normalized source region assigned to exactly one token. It is not required to contain only the tokenizer's normalized token text; it may include adjacent whitespace so that spans form a complete source partition.

#### 5.2 Raw span validation

The adapter MUST:

1. Obtain raw token offsets from the approved tokenizer.
2. Convert byte offsets to Unicode code-point offsets. A byte boundary that does not coincide with a code-point boundary is invalid.
3. Reject raw spans that are out of bounds, zero-width, out of order, or overlapping.
4. Reject any non-whitespace source character not covered by a raw span. Gaps between raw spans, before the first span, and after the last span MUST be whitespace-only.
5. Normalize the raw spans without adding, removing, reordering, or merging tokens.
6. Return the normalized spans.

#### 5.3 Normalization

Given raw spans `r[0..m-1]`, return normalized spans `s[0..m-1]`:

```text
s[0].start = 0
s[i].start = r[i].start                    for i > 0
s[i].end   = r[i + 1].start                for i < m - 1
s[m - 1].end = len(text)
```

This assigns leading whitespace to the first token and each internal or trailing whitespace gap to the preceding token. The token count is exactly `m`, the raw token count. Normalization MUST NOT change it.

#### 5.4 Required properties

- `m == 0` is allowed only when the text is empty or whitespace-only. Text containing non-whitespace must produce `m >= 1`; otherwise the adapter raises `TokenizerContractError`.
- For `m > 0`:
  - `s[0].start_offset == 0`
  - `s[m - 1].end_offset == len(text)`
  - `s[i].start_offset == s[i - 1].end_offset` for every `i > 0`
  - `0 <= start_offset < end_offset <= len(text)`
- Spans are non-overlapping, contiguous, and in token order.
- `tokenize("")` returns an empty tuple.
- Tokenization is deterministic, offline, and side-effect free.
- Tokenization does not truncate and does not add synthetic tokens such as BOS, EOS, padding, or special tokens.
- Offsets are Unicode code-point indexes into the original source text, not byte offsets.
- A tokenizer that normalizes text must still map each token back to the original source region. If exact mapping is impossible, the adapter must reject the tokenization rather than invent offsets.

#### 5.5 Tokenizer identity

`identity` must be stable and non-empty. It must include:

- Tokenizer implementation and library version.
- Model or encoding identifier.
- Pinned model revision.
- Any flags or normalization settings that affect tokenization output.

The identity is part of the chunking configuration identity (§8). A library upgrade or revision change that can alter tokenization must produce a different identity, even if the current corpus happens to tokenize identically. This is intentionally conservative: it may require a rebuild that turns out to be unnecessary, but it never allows silent tokenization drift.

The adapter must not execute remote model code by default.

#### 5.6 Tokenizer error

Any violation of this section raises `TokenizerContractError`. The error message contains identifiers and positions only, never document content.

#### 5.7 Production tokenizer dependency (approved)

The embedding provider/model and production tokenizer are approved in `specs/rag/embedding-tokenizer-decision.md`:

- Provider and serving model: Ollama `nomic-embed-text:v1.5`.
- Tokenizer implementation: `tokenizers==0.23.3`.
- Tokenizer/model repository: `nomic-ai/nomic-embed-text-v1.5` at revision `e9b6763023c676ca8431644204f50c2b100d9aab`, asset `tokenizer.json`.
- Identity format: `tokenizers:<lib_version>:<model_id>@<revision_sha>:<sha256(tokenizer.json)>`, where `model_id` is the tokenizer/model repository identifier, not the Ollama serving tag.
- Runtime mode: local tokenizer runtime; no runtime network access or downloads. Dependency installation is part of normal development setup and does not require an offline wheelhouse.

The tokenizer asset is vendored during T263 and its checksum is computed from the vendored file; it is never pre-filled. The adapter loads the pinned asset from a local filesystem path and must not depend on the Hugging Face Hub at runtime. The production tokenizer must be model-aligned and must provide source offsets that satisfy §5. A generation tokenizer is not assumed suitable for an embedding model.

Input-length compatibility was verified in T263: `500` maximum tokens plus `4` prefix tokens and `2` special tokens totals `506`, within the conservative 2048-token limit. The 500/75 defaults are retained. Had the check failed, this specification would have been amended before implementation; the defaults must not be changed silently.

### 6. Chunking Algorithm and Boundary Behavior

#### 6.1 Preconditions and empty documents

For each document:

1. If `content == ""` or `content.strip() == ""`, emit:

   ```text
   DocumentChunking(
       content_length=len(content),
       token_count=0,
       chunks=(),
       ...
   )
   ```

   Do not call the tokenizer.

2. Otherwise tokenize the complete content exactly once and validate the spans per §5.

If tokenization of non-whitespace content returns zero spans, the adapter has violated §5.4 and raises `TokenizerContractError`.

#### 6.2 Token window

Let `n` be the document token count. Start at token index `i = 0`.

1. Set `j = min(i + max_tokens, n)`.
2. If `j < n`, choose a snap index `k` in `(i, j]` using §6.3. Otherwise set `k = j`.
3. Emit a chunk covering token indexes `[i, k)`.
4. If `k == n`, stop.
5. Set `i = max(k - overlap_tokens, i + 1)` and repeat.

Because `k > i` and `next_i >= i + 1`, every iteration makes forward progress. Because `k <= j <= i + max_tokens`, every chunk satisfies `token_count <= max_tokens`.

#### 6.3 Boundary predicates

At token boundary `p = spans[k - 1].end_offset`, evaluate the following predicates.

```python
def is_paragraph_boundary(text: str, p: int) -> bool:
    return re.search(r"\n[ \t]*\n[ \t]*\Z", text[:p]) is not None


def is_sentence_boundary(text: str, p: int) -> bool:
    r = p
    while r > 0 and text[r - 1].isspace():
        r -= 1
    return (
        r > 0
        and text[r - 1] in ".!?"
        and (r == len(text) or text[r].isspace())
    )


def is_word_boundary(text: str, p: int) -> bool:
    return (
        p == len(text)
        or text[p - 1].isspace()
        or text[p].isspace()
    )
```

Boundary semantics:

- **Paragraph boundary:** the source prefix ends with a blank-line run, ignoring trailing spaces or tabs. A single newline is not a paragraph boundary. Only LF is recognized; ingestion guarantees LF-normalized input. CR and Unicode line separators are not recognized. The predicate is defined by the suffix match; an implementation may use an equivalent local suffix check and is not required to materialize the entire prefix.
- **Sentence boundary:** `.`, `!`, or `?` must be followed by whitespace or end of text. Punctuation followed immediately by a non-whitespace character is not a sentence boundary. Abbreviations such as `e.g.` may still be treated as sentence boundaries in V1.
- **Word boundary:** uses Unicode `str.isspace()`. Non-Latin text without whitespace may fall through to a hard cut. Non-Latin sentence punctuation such as `。` is not recognized in V1 and does not create a sentence boundary.
- **Hard cut:** if no preferred boundary qualifies, set `k = j`.

#### 6.4 Boundary selection

Choose the rightmost boundary of the highest available class:

```python
def choose_cut(text, spans, i, j):
    for predicate in (
        is_paragraph_boundary,
        is_sentence_boundary,
        is_word_boundary,
    ):
        for k in range(j, i, -1):
            if predicate(text, spans[k - 1].end_offset):
                return k
    return j
```

This rule is deterministic. An early paragraph boundary may produce a short chunk; V1 intentionally has no minimum chunk size. Short chunks are bounded: a chunk consumes at least one new token, so `chunk_count <= token_count` for every non-zero document.

#### 6.5 Chunk assembly

For a window `[i, k)`:

```text
start_offset = spans[i].start_offset
end_offset   = spans[k - 1].end_offset
content      = document.content[start_offset:end_offset]
token_start  = i
token_end    = k
token_count  = k - i
chunk_index  = next contiguous index for this document
```

The chunk content is an exact contiguous source slice. It is not trimmed, reflowed, re-normalized, or rewritten. Boundary whitespace may be included because the normalized spans partition the complete source. Context construction may later decide how to present or trim content for prompting, but any such transformation is outside this boundary and must not alter chunk offsets or identity.

#### 6.6 Overlap

- Planned overlap is `k - next_i`.
- Actual overlap never exceeds `overlap_tokens`.
- When `overlap_tokens == 0`, `next_i = k`, producing non-overlapping token windows and non-overlapping source slices.
- When the current chunk is shorter than the overlap target, the next start is `i + 1`; actual overlap is correspondingly smaller.
- Overlap is token-based, not character-based.

#### 6.7 Coverage and determinism

- Token ranges are visited without gaps: the first chunk starts at token 0, the last chunk ends at token `n`, and each next chunk starts at or before the previous chunk's end.
- Because normalized spans partition the source, every source character is represented in at least one chunk.
- Identical documents, tokenizer identity, configuration, and algorithm version produce identical spans, boundaries, chunks, offsets, IDs, ordering, and counts.
- Input document order does not affect the result.
- Chunk ordering is deterministic: documents by `(source_path, document_id)`, chunks by `chunk_index`.

#### 6.8 Known V1 limitations

- Sentence recognition uses ASCII `.`, `!`, and `?` only.
- Abbreviations and decimal numbers may produce false or missed sentence boundaries.
- Non-Latin sentence punctuation is not recognized.
- Non-Latin text without whitespace may be split at token boundaries rather than linguistic word boundaries.
- No heading-aware, fence-aware, semantic, or minimum-size chunking is provided.
- These limitations are deterministic and do not affect offset correctness or token-limit enforcement.

### 7. Contracts and Metadata

#### 7.1 `Chunk` (frozen dataclass)

| Field | Meaning |
| --- | --- |
| `chunk_id` | Deterministic ID from §8.4 |
| `document_id` | Source document content-version ID |
| `source_path` | Relative POSIX source path |
| `title` | Source document title |
| `format` | `markdown` or `text` |
| `content` | Exact source slice |
| `start_offset` | Inclusive Unicode code-point offset in `document.content` |
| `end_offset` | Exclusive Unicode code-point offset in `document.content` |
| `token_start` | Inclusive index in the document token sequence |
| `token_end` | Exclusive index in the document token sequence |
| `token_count` | `token_end - token_start` |
| `chunk_index` | 0-based, contiguous per document |
| `chunking_config_id` | Effective configuration identity |

Derived read-only property: `char_count == end_offset - start_offset`.

#### 7.2 `DocumentChunking` (frozen dataclass)

| Field | Meaning |
| --- | --- |
| `document_id` | Source document ID |
| `source_path` | Source path |
| `title` | Source title |
| `format` | Source format |
| `content_length` | `len(document.content)` in Unicode code points |
| `token_count` | Total tokens in the document; `0` for empty or whitespace-only content |
| `chunks` | Ordered immutable tuple of `Chunk` |

Derived read-only property: `chunk_count == len(chunks)`.

#### 7.3 `ChunkingResult` (frozen dataclass)

| Field | Meaning |
| --- | --- |
| `config` | Effective `ChunkingConfig` |
| `documents` | Ordered immutable tuple of `DocumentChunking` |

Derived read-only properties:

- `document_count == len(documents)`
- `chunk_count == sum(document.chunk_count for document in documents)`
- `total_token_count == sum(document.token_count for document in documents)`
- `chunks` — flattened tuple of all chunks in document order
- `has_chunks == chunk_count > 0`

#### 7.4 Construction invariants

These invariants apply to every construction path, including direct construction:

- `ChunkingConfig` satisfies §8.2.
- `documents` are sorted ascending by `(source_path, document_id)`.
- `(source_path, document_id)` pairs are unique. Duplicate pairs raise `ValueError`.
- Chunks within each document are sorted ascending by `chunk_index`.
- Chunk indexes are contiguous and start at 0.
- Each chunk's `document_id`, `source_path`, `title`, and `format` match its enclosing `DocumentChunking`.
- Each chunk's `chunking_config_id` matches `config.config_id`.
- Each chunk satisfies:
  - `0 <= token_start < token_end <= document.token_count`
  - `token_count == token_end - token_start`
  - `0 <= start_offset < end_offset <= document.content_length`
  - `len(content) == end_offset - start_offset`
  - `chunk_index` matches its position in the document.
- `document.token_count >= 0` and `document.content_length >= 0`.
- If `content_length == 0`, then `token_count == 0` and `chunks` is empty.
- If `token_count == 0`, then `chunks` is empty. A non-empty whitespace-only document is represented with `content_length > 0`, `token_count == 0`, and no chunks.
- If `token_count > 0`:
  - `chunks` is non-empty.
  - The first chunk's `token_start == 0`.
  - The last chunk's `token_end == token_count`.
  - Each next chunk's `token_start` is greater than the previous chunk's `token_start` and less than or equal to the previous chunk's `token_end`.
  - The first chunk's `start_offset == 0`.
  - The last chunk's `end_offset == content_length`.
  - Each next chunk's `start_offset` is greater than the previous chunk's `start_offset` and less than or equal to the previous chunk's `end_offset`.
  - Each chunk's `token_count <= config.max_tokens`.
- Collections are immutable tuples.
- A violation raises `ValueError`.

For `token_count == 0` documents, chunk-level source coverage does not apply because no chunks are emitted.

#### 7.5 Provenance

- `document_id` identifies the exact normalized content version produced by ingestion.
- `source_path` preserves the original source location.
- `start_offset` and `end_offset` identify the exact source range in that document version.
- `token_start` and `token_end` identify the token range under the approved tokenizer and configuration.
- `chunking_config_id` identifies the tokenizer, algorithm version, and chunk-affecting settings.
- Identical content ingested at two source paths remains distinguishable because `source_path` is part of the chunk ID.

### 8. Deterministic IDs and Configuration Identity

#### 8.1 Algorithm version

`ALGORITHM_VERSION = "chunking-v1"`.

Any change to boundary selection, windowing, overlap semantics, offset semantics, tokenizer-span normalization, or construction behavior requires a new version string.

#### 8.2 `ChunkingConfig`

```python
@dataclass(frozen=True)
class ChunkingConfig:
    max_tokens: int
    overlap_tokens: int
    tokenizer_id: str
    algorithm_version: str = ALGORITHM_VERSION
```

Validation:

- `max_tokens > 0`
- `overlap_tokens >= 0`
- `overlap_tokens < max_tokens`
- `tokenizer_id.strip()` is non-empty
- `algorithm_version.strip()` is non-empty

Invalid values raise `ValueError`.

#### 8.3 Configuration ID

```python
payload = {
    "algorithm_version": config.algorithm_version,
    "max_tokens": config.max_tokens,
    "overlap_tokens": config.overlap_tokens,
    "tokenizer_id": config.tokenizer_id,
}
config_id = sha256(
    json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
).hexdigest()
```

- Lowercase hexadecimal SHA-256.
- No timestamps, random values, hostnames, paths, or process state.
- Includes every chunk-affecting setting, the tokenizer identity, and the algorithm version.
- Excludes retrieval-only settings such as `top_k`, retrieval filters, Qdrant URLs, database URLs, and LLM generation settings.
- A change to any included value produces a different configuration ID.

#### 8.4 Chunk ID

```python
payload = {
    "chunking_config_id": chunking_config_id,
    "document_id": document_id,
    "source_path": source_path,
    "start_offset": start_offset,
    "end_offset": end_offset,
    "content": content,
}
chunk_id = sha256(
    json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
).hexdigest()
```

- Lowercase hexadecimal SHA-256.
- `source_path` is included deliberately so identical content at different source paths produces distinct chunk IDs.
- Identical content at different offsets within a document produces different IDs.
- Chunk identity is content-versioned, not a persistent logical identity.

#### 8.5 Reproducibility

Given the same document content, tokenizer identity and revision, algorithm version, and effective configuration, the system must produce identical spans, chunks, offsets, token indexes, IDs, ordering, and counts.

A tokenizer library version or model revision that can change tokenization must change `identity`, which changes the configuration ID and chunk IDs. This conservative rule prevents silent reuse of chunks produced by a different tokenizer behavior.

### 9. Configuration

Additive settings following the existing `pydantic-settings` conventions in `src/app/core/config.py`:

| Setting | Environment variable | Default | Meaning |
| --- | --- | --- | --- |
| `knowledge_chunk_max_tokens` | `KNOWLEDGE_CHUNK_MAX_TOKENS` | `500` | Maximum tokens per chunk |
| `knowledge_chunk_overlap_tokens` | `KNOWLEDGE_CHUNK_OVERLAP_TOKENS` | `75` | Maximum overlap target between consecutive chunks |

Requirements:

- `knowledge_chunk_max_tokens`: `Field(default=500, gt=0)`.
- `knowledge_chunk_overlap_tokens`: `Field(default=75, ge=0)`.
- Cross-field validation: `overlap_tokens < max_tokens`. Invalid settings fail clearly at application startup.
- Both settings are optional with defaults, so local development works with no environment changes.
- Both are documented in `.env.example` when T262 implements the settings.
- The tokenizer identity is selected in the composition root and pinned in code; it is not an environment override in the MVP, avoiding accidental tokenizer/config mismatch.
- `ChunkingService` must not call `get_settings()` eagerly. It exposes `from_settings(settings, tokenizer)` for the composition root and accepts explicit configuration values at construction.
- Retrieval-only settings, including `top_k`, belong to a later retrieval specification and must not enter the chunking configuration ID.
- The approved defaults are `500` tokens and `75` tokens of overlap. T263 conformance verified `500 + 4 prefix + 2 special = 506 <= 2048`; the defaults are retained. If a future model or limit does not fit, this specification must be amended before implementation; the defaults must not be silently changed.

There are no per-document or per-request overrides in V1.

### 10. Error Handling and Empty Input

Exception hierarchy under `src/app/rag/chunking/exceptions.py`:

- `ChunkingError` — base class; never raised directly.
- `TokenizerContractError` — the tokenizer returns invalid offsets, an incomplete or non-contiguous partition, an empty identity, truncated output, or otherwise violates §5. Structural; aborts the chunking run.

Validation behavior:

- Configuration errors raise `ValueError` at construction and fail settings validation at startup.
- Tokenizer initialization or model-loading failures propagate at the composition boundary; they are not swallowed or converted into per-document results.
- Empty content (`""`) produces `DocumentChunking(content_length=0, token_count=0, chunks=())`.
- Whitespace-only content produces `DocumentChunking(content_length=len(content), token_count=0, chunks=())`.
- The tokenizer is not called for empty or whitespace-only content.
- Every valid input document remains represented in `ChunkingResult.documents`, including zero-chunk documents.
- There is no per-document failure collection in V1 because valid `KnowledgeDocument` input has no content-dependent failure mode under this contract.
- Error messages contain identifiers and positions only, never document content or secrets.
- Every declared exception has a tested, reachable role.

### 11. Observability and Reproducibility

The in-memory result must expose or make recoverable:

- `chunking_config_id`
- `tokenizer_id`
- `algorithm_version`
- `max_tokens`
- `overlap_tokens`
- Per-document `content_length`, `token_count`, and `chunk_count`
- Per-chunk source offsets, token indexes, and chunk index

Future persistence requirements:

- Store the effective `ChunkingConfig` snapshot with every index generation.
- Store each document's chunking configuration ID alongside its indexed chunks.
- A chunk read in isolation is traceable through `chunking_config_id`; the full configuration must be recoverable from the generation manifest.
- No manifest persistence or index generation is implemented by this specification.

Structured logs, when added, must include identifiers, counts, and durations only. They must never include chunk content or document text.

### 12. Future Index Generation and Migration Principles

This section is design-only. It does not authorize Qdrant integration, embedding generation, persistence, re-chunking, re-embedding, re-ingestion, or migration.

#### 12.1 Change classification

| Change | Required future action |
| --- | --- |
| `max_tokens`, `overlap_tokens`, tokenizer identity, or algorithm version | Re-chunk affected documents and re-embed the resulting chunks |
| Embedding model or revision, with tokenizer identity unchanged | Re-embed affected documents; chunks may be reused |
| Embedding model with a different tokenizer identity | Re-chunk and re-embed affected documents |
| Retrieval-only setting such as `top_k` | No re-chunking, re-embedding, or index rebuild |

#### 12.2 Generation identity

A future index generation identity must combine at least:

- Chunking configuration ID
- Embedding model identity and revision
- Index or payload schema version

The exact formula belongs to the embedding and Qdrant specifications.

#### 12.3 Configuration drift

- Configuration drift is detected by comparing the active generation's recorded `chunking_config_id` with the current configuration ID.
- Drift produces a status or report; it never starts re-chunking, re-embedding, or rebuilding automatically.
- Affected documents are identified from persisted per-document configuration IDs.
- Silent in-place mutation of existing indexed data is prohibited.
- Without a persisted manifest, production drift detection cannot be implemented. Manifest persistence is a future decision.

#### 12.4 Build, validate, and activate

1. Build a new generation separately from the active generation.
2. Validate completeness, embedding dimensions, counts, metadata, and sample retrieval quality.
3. Activate only after validation succeeds.
4. Keep the previous active generation usable until the replacement is validated and activated.
5. Never expose a partially built generation as active.
6. On build or validation failure, leave the previous generation active, mark the new generation failed, and do not expose partial data.
7. Activation is the point at which the active reference switches to the validated generation.
8. If activation fails, the previous generation remains active.
9. Rollback switches the active reference back to the retained previous generation.
10. The failed generation must not receive reads through the active reference.

#### 12.5 Out of scope for this specification

Collection naming, alias strategy, payload schema, manifest persistence, retention windows, migration jobs, and Qdrant client integration are all out of scope. They belong to the Qdrant integration specification.

The Qdrant image should be pinned instead of using `latest` before migration work begins.

### 13. Security

- Document content is untrusted data: never executed, evaluated, rendered as a template, or logged.
- Tokenizer adapters must be pinned to an approved model, revision, and library version.
- Tokenizer adapters must not execute remote model code by default.
- The chunking algorithm performs no I/O or network access.
- Memory and runtime are bounded by the ingestion document-size limit and `max_tokens`.
- Error and log messages contain no content or secrets.
- Paths and identifiers are safe to report; document text is not.

### 14. Unit Test Requirements

Tests must be deterministic and offline: no network, LLM, embedding runtime, Qdrant, or PostgreSQL.

#### 14.1 T260–T262 tests (deterministic fixture tokenizer)

1. **Raw span validation:** bounds, zero-width, out-of-order, overlapping, non-whitespace gaps, empty input, whitespace-only input, and non-whitespace input that yields zero spans.
2. **Span normalization:** leading, internal, and trailing whitespace gaps; already-contiguous spans; token count unchanged; byte-to-code-point conversion; rejection of a byte boundary inside a multi-byte code point.
3. **Exact source slicing:** `content == document.content[start_offset:end_offset]` and `char_count == len(content) == end_offset - start_offset`.
4. **Token limit:** every chunk has `token_count <= max_tokens`.
5. **Boundary priority:** rightmost paragraph boundary, else rightmost sentence boundary, else rightmost word boundary, else hard cut.
6. **Paragraph predicate:** blank lines containing spaces or tabs; single newline is not a boundary; trailing spaces or tabs; LF-only input.
7. **Sentence predicate:** punctuation followed by whitespace or end of text; punctuation followed immediately by non-whitespace is not a boundary; decimal-number and abbreviation limitations; non-Latin punctuation falls through.
8. **Word predicate:** Unicode whitespace, NBSP, punctuation, and non-Latin text without whitespace.
9. **Overlap:** actual overlap never exceeds the target; zero overlap produces non-overlapping token windows; a chunk shorter than the overlap target still makes progress.
10. **Coverage:** every source character and token index is represented; first chunk starts at token 0 and source offset 0; last chunk ends at the document token count and content length.
11. **Bounded short chunks:** `chunk_count <= token_count` for non-zero documents; no infinite loop under repeated boundaries.
12. **Determinism and input-order independence.**
13. **Metadata and indexes:** metadata matches the parent document; `chunk_index` is contiguous per document.
14. **Unicode:** emoji, combining characters, and non-Latin scripts use code-point offsets and exact slices.
15. **Empty and whitespace-only documents:** zero tokens, zero chunks, preserved in the result, and the tokenizer is not called.
16. **IDs:** exact configuration and chunk ID formulas; canonical JSON stability; sensitivity to every included field; identical content at different paths yields distinct chunk IDs.
17. **Construction invariants:** ordering, unique document keys, metadata mismatch, configuration mismatch, duplicate or missing indexes, invalid token ranges, invalid offsets, invalid `content_length`, and token-limit violations.
18. **Purity and errors:** no I/O or network in the chunking boundary; `TokenizerContractError` roles; messages contain no document content.

#### 14.2 T263 real-tokenizer conformance

19. The approved production tokenizer must:
    - Satisfy §5 for Unicode, whitespace, punctuation, and non-Latin text.
    - Produce deterministic, untruncated spans.
    - Preserve source offsets and token counts.
    - Produce chunks within `max_tokens`.
    - Confirm that `max_tokens` plus embedding special or prefix tokens fits the embedding model's input limit.
    - Report a stable identity including implementation, library version, model or encoding, and pinned revision.

Tests 1–18 must pass with a deterministic fixture tokenizer before T263. Test 19 is T263-only and must not be treated as a T262 failure.

### 15. Task-Specific Acceptance Criteria

#### T260 — Contracts, configuration identity, tokenizer protocol

- `Chunk`, `DocumentChunking`, `ChunkingResult`, and `ChunkingConfig` are frozen and immutable.
- `Tokenizer`, `TokenSpan`, raw-span validation, and normalization follow §5.
- Configuration and chunk IDs follow §8 exactly.
- Construction invariants in §7.4 are enforced on every path.
- `ChunkingError` and `TokenizerContractError` have tested roles.
- Tests 1, 2, 16, and 17 pass.

#### T261 — Token-aware boundary selection and chunk assembly

- The algorithm follows §6 and uses a deterministic fixture tokenizer.
- Chunks are exact source slices with correct offsets and token indexes.
- Token limit, boundary priority, overlap, progress, coverage, determinism, Unicode, and empty-document behavior pass.
- `chunk_count <= token_count` for every non-zero document.
- Tests 3–15 and 18 pass in addition to T260 tests.

#### T262 — Configuration and chunking service

- Additive settings follow §9 and fail startup validation when invalid.
- `ChunkingService` does not access settings eagerly and supports `from_settings(settings, tokenizer)`.
- Aggregation represents every input document, sorts deterministically, and enforces §7.4.
- The algorithm remains pure and independent of FastAPI, PostgreSQL, embeddings, and Qdrant.
- Existing ingestion and LLM behavior remains unchanged.
- Tests 12, 13, 15, 17, and 18 pass at the service level.

#### T263 — Production tokenizer adapter and conformance

- Implemented only after separate approval of the embedding model and tokenizer.
- Adds a tokenizer dependency only after explicit approval.
- The adapter satisfies §5 and test 19.
- `max_tokens` is confirmed compatible with the embedding model input limit, or the specification is amended.
- The adapter identity is pinned and recorded.

#### T264 — Final integration verification and closure

- The focused chunking suite, including T263 conformance, passes offline.
- The full regression suite passes.
- `git diff --check` is clean and the diff is reviewed against this specification.
- Ingestion, LLM, domain, and database behavior is unchanged.
- `specs/project-state.md` records task outcomes, commits, tests, and exactly one next task.
- A closure commit follows repository precedent.

### 16. Out of Scope

- Embedding generation, embedding model execution, and vector storage.
- Qdrant collections, payloads, aliases, manifest persistence, migrations, re-indexing, and re-ingestion.
- Retrieval, metadata filtering, reranking, context construction, and source attribution.
- Persistent chunk storage, update tracking, incremental re-chunking, and deletion.
- HTTP endpoints, CLI wiring, background jobs, and database schema changes.
- Heading-aware, fence-aware, semantic, language-specific, minimum-size, or merge-based chunking.
- Per-document or per-request configuration overrides.
- Changes to ingestion behavior or document identity.
- Selection of an embedding model or production tokenizer.

This specification does not authorize implementation.

### 17. Unresolved Decisions and Dependencies

| Decision | Status | Blocks |
| --- | --- | --- |
| Embedding provider and model | Resolved — Ollama `nomic-embed-text:v1.5`; see `specs/rag/embedding-tokenizer-decision.md` | T263 implementation |
| Tokenizer implementation, dependency, version, and revision | Resolved — `tokenizers==0.23.3`, repository `nomic-ai/nomic-embed-text-v1.5` at revision `e9b6763023c676ca8431644204f50c2b100d9aab`; see decision record | T263 implementation |
| Exact tokenizer `identity` string format | Resolved — `tokenizers:<lib_version>:<model_id>@<revision_sha>:<sha256(tokenizer.json)>`; see decision record | T263 implementation |
| Confirmation that `500/75` fits the embedding model input limit | Resolved — measured `506` (500 + 4 prefix + 2 special) against the conservative 2048 limit in T263; 500/75 retained | None |
| Container packaging of the pinned tokenizer asset | Open — recorded in §20.1; not in T263 or T264 scope | Future packaging task (unnumbered) |
| Chunking composition-root wiring for the approved adapter | Open — recorded in §20.2; not in T263 scope | Future integration task (unnumbered) |
| Manifest persistence location: PostgreSQL, Qdrant payload, or dedicated manifest | Unresolved; no persistence contract exists | Future index-generation work |
| Qdrant collection naming, alias strategy, and payload schema | Unresolved; no Qdrant integration exists | Future Qdrant specification |
| Qdrant image version pin | Recommended before migration work | Future Qdrant specification |
| Configuration-drift reporting surface: startup warning, admin endpoint, or both | Unresolved | Future operations work |

Approved decisions recorded by this specification:

- Include `source_path` in the deterministic chunk ID.
- Reject duplicate `(source_path, document_id)` pairs.
- No minimum chunk size in V1.
- Empty and whitespace-only documents produce zero-token, zero-chunk records and do not call the tokenizer.
- Defaults of 500 tokens and 75 tokens of overlap, verified in T263 conformance (`506 <= 2048`) and retained.
- No automatic re-chunking, re-embedding, or index rebuilding when configuration changes.
- The embedding provider/model and production tokenizer are recorded separately in `specs/rag/embedding-tokenizer-decision.md`.

### 18. File Placement and Interfaces

```
src/app/rag/chunking/
    __init__.py
    contracts.py      # Chunk, DocumentChunking, ChunkingResult, ChunkingConfig, IDs
    tokenizer.py      # TokenSpan, Tokenizer protocol, span validation/normalization
    exceptions.py     # ChunkingError, TokenizerContractError
    chunker.py        # token-window and boundary assembly
    service.py        # ChunkingService, from_settings
```

Indicative interfaces:

```python
def chunk_document(
    document: KnowledgeDocument,
    tokenizer: Tokenizer,
    config: ChunkingConfig,
) -> DocumentChunking: ...


class ChunkingService:
    def __init__(
        self,
        tokenizer: Tokenizer,
        max_tokens: int = 500,
        overlap_tokens: int = 75,
    ): ...

    @classmethod
    def from_settings(cls, settings, tokenizer: Tokenizer) -> "ChunkingService": ...

    def chunk(self, documents: Iterable[KnowledgeDocument]) -> ChunkingResult: ...
```

The service accepts no per-request configuration overrides. The tokenizer is injected by the composition root.

### 19. Task Breakdown

Task IDs continue the project sequence after T259.

| Task | Scope (file scope only) | Depends on | Acceptance |
| --- | --- | --- | --- |
| **T260 — Contracts, configuration identity, tokenizer protocol** | `src/app/rag/chunking/__init__.py`, `contracts.py`, `tokenizer.py`, `exceptions.py`; `tests/rag/chunking/__init__.py`, `test_contracts.py`, `test_tokenizer_contract.py` | This specification approved | §5, §7, §8, §10; immutable types; span validation/normalization; exact IDs; construction invariants; tested exception roles |
| **T261 — Token-aware boundary selection and chunk assembly** | `chunker.py`; `test_chunker.py` with a deterministic fixture tokenizer | T260 | §6; exact slicing; token limit; boundary predicates and priority; overlap; progress; coverage; bounded chunk count; determinism; Unicode; empty short-circuit |
| **T262 — Configuration and chunking service** | `service.py`; additive fields and cross-field validation in `src/app/core/config.py`; `.env.example`; `test_service.py` | T261 | §9; settings validation; `from_settings` without eager settings access; aggregation; ordering; metadata; input-order independence; purity |
| **T263 — Production tokenizer adapter and conformance** | Selected adapter module; approved dependency declaration; `test_tokenizer_adapter.py` | T262 and approved embedding model/tokenizer decision | §5 with the real tokenizer; partition; determinism; no truncation; token limit; embedding input-length compatibility |
| **T264 — Final integration verification and closure** | No feature code | T263 | Focused suite, full regression, `git diff --check`, diff review, ingestion regression unchanged, project-state update, closure commit |

Notes:

- Each implementation task ends with focused tests green, no regression, and its own task commit.
- The embedding model and tokenizer decision is approved in `specs/rag/embedding-tokenizer-decision.md`. Asset vendoring/checksum and the 2048-token compatibility check are T263 deliverables. T260–T262 remain complete with the tokenizer protocol and a deterministic fixture tokenizer, but chunking is not production-ready until T263 and T264 are complete.
- T264 is mandatory. A defect found within approved scope reopens the owning task instead of being patched in T264.
- Implementing any task requires a separate authorized session; approval of this specification does not authorize implementation.

### 20. Follow-ups Recorded During T263 Review

These items are not part of T263 and are not authorized by this specification. They are recorded so they are not lost. Each requires its own approved task; no task number is assigned here, and the T260–T264 sequence is unchanged.

#### 20.1 Container packaging of the pinned tokenizer asset

- Scope: package the pinned `assets/tokenizers/nomic-embed-text-v1.5/tokenizer.json` into the production image (for example, the image build context and `Dockerfile`). T263 scope covers the adapter, dependency, and tests only; T264 is verification-only.
- Requirement: the production image must include the pinned asset, and the adapter must load it from the image filesystem without a repository bind mount.
- Acceptance evidence: build the image from a clean context; run the adapter in that image with no host bind mount and no network; load the asset, tokenize a fixed sample, and confirm the identity digest equals the SHA-256 of the packaged file.
- Status: Open. Do not mark resolved until the image build and no-bind-mount verification are recorded.

#### 20.2 Chunking composition-root wiring

- Scope: wire `NomicEmbedTextTokenizer` into the production chunking dependency construction and inject it into `ChunkingService` (using `from_settings` for configured max/overlap tokens). T263 delivered the adapter only; no production call site constructs it today.
- Requirement: the production chunking path must construct and use the approved adapter, with the tokenizer identity pinned in code rather than selected by an environment variable.
- Acceptance evidence: an integration test that exercises the actual production wiring, not the adapter in isolation; asserts `ChunkingService.config.tokenizer_id` equals the adapter identity; chunks a document end to end; and runs without network access.
- Status: Open. Do not mark resolved until the wiring and integration test are verified.
