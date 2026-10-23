# Embedding and Tokenizer Decision (T263 Prerequisite)

Status: Approved

- Feature: Knowledge Document Chunking — production tokenizer adapter (T263)
- Phase: Phase 4 — RAG
- Approval: 2026-10-23
- Scope: decision record only. This document does not authorize T263
  implementation, does not add dependencies, does not pull a model, and does
  not download or vendor assets.

## 1. Decision

| Item | Value |
| --- | --- |
| Embedding provider | Ollama |
| Embedding model (serving) | `nomic-embed-text:v1.5` |
| Tokenizer library | `tokenizers==0.23.3` |
| Tokenizer/model repository | `nomic-ai/nomic-embed-text-v1.5` |
| Pinned repository revision | `e9b6763023c676ca8431644204f50c2b100d9aab` |
| Tokenizer asset | `tokenizer.json` from that exact revision |
| Runtime mode | local tokenizer runtime; no runtime network access or downloads |

`model_id` in the tokenizer identity denotes the tokenizer/model repository
identifier, not the Ollama serving tag. The serving tag is embedding metadata
and is deliberately excluded from the chunking identity (see §4).

### Runtime and installation

- The production adapter loads the pinned `tokenizer.json` from a local
  filesystem path.
- Tokenization must work locally without network access or runtime downloads.
- The tokenizer must not depend on the Hugging Face Hub at runtime.
- Dependency installation is part of normal development setup. No offline
  wheelhouse or offline-installation requirement is imposed.
- Runtime tokenizer configuration must not override the vendored asset's
  configuration.
- Special-token insertion, truncation, and padding remain disabled according to
  §5.4 of the chunking specification.
- Local runtime behavior was verified in T263: the adapter loads the local asset
  and tokenizes with no network access. The adapter suite passed under Docker
  `--network none` (30 tests).

## 2. Tokenizer identity

Format:

```text
tokenizers:<lib_version>:<model_id>@<revision_sha>:<sha256(tokenizer.json)>
```

Resolved example with the checksum computed from the vendored asset in T263:

```text
tokenizers:0.23.3:nomic-ai/nomic-embed-text-v1.5@e9b6763023c676ca8431644204f50c2b100d9aab:d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66
```

The adapter recomputes this digest from the bytes it loads at runtime; the value
is not hard-coded.

Rules:

- The checksum is computed from the actually vendored `tokenizer.json` during
  T263. It must never be invented, pre-filled, or hard-coded.
- The provenance record captures the full SHA-256 of the vendored asset, and the
  identity uses that full digest as approved.
- The actual digest was computed from the vendored asset in T263. The adapter
  recomputes it from the loaded bytes and does not hard-code it.
- The asset hash covers the tokenizer's normalization and flag configuration.
  Loading must not apply runtime overrides to that configuration.
- The vendored asset already carries `truncation: null` and `padding: null`.
  The adapter verifies both and fails with a safe contract error if either is
  enabled; it does not call configuration setters or otherwise mutate the
  loaded asset configuration.
- Adapter behavior is pinned: special tokens disabled, truncation disabled,
  and padding disabled, per §5.4. Any change to adapter semantics (offset
  conversion, special-token policy, truncation, padding) requires a new
  identity segment and/or an algorithm-version bump per §8.
- A library upgrade, repository revision change, or asset change that can alter
  tokenization must change the identity.

## 3. Context-limit compatibility

- Ollama's listing for `nomic-embed-text:v1.5` reports a 2K context window.
- This decision uses **2048 tokens** as the conservative runtime limit.
- Required check: `max_tokens` (500) plus the embedding prefix tokens and
  special tokens must be less than or equal to 2048.
- Status: **verified in T263.** The measured total is `500 + 4 prefix + 2
  special = 506`, within the 2048-token limit. The 500/75 defaults are retained.
  If a future model or limit does not fit, the chunking specification must be
  amended before implementation; the defaults must not be changed silently.

## 4. Why the serving tag is excluded from the identity

The tokenizer identity describes tokenization behavior, which determines chunk
boundaries and `chunking_config_id`. The Ollama tag describes model serving and
may be re-pulled, re-quantized, or re-tagged without changing tokenization.
Including it would force unnecessary re-chunking on serving-side changes and
would contradict the chunking specification's rule that an embedding model
change with an unchanged tokenizer identity re-embeds only and may reuse
chunks.

## 5. T263 prerequisites and status

All T263 prerequisites were satisfied at the T263 review:

1. Vendor `tokenizer.json` from revision
   `e9b6763023c676ca8431644204f50c2b100d9aab`, verify its presence and
   integrity, and compute the full SHA-256 from the vendored file: satisfied.
   The asset is present and its full SHA-256 is
   `d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66`.
2. Add the approved `tokenizers==0.23.3` dependency at T263 implementation
   time as part of normal development setup; this decision does not modify
   dependencies and does not require an offline wheelhouse: satisfied in the
   working tree.
3. Verify local runtime behavior: the adapter loads the local asset and
   tokenizes without network access or Hugging Face Hub access, and record the
   evidence: satisfied. The adapter suite passed under Docker `--network none`
   (30 tests).
4. Measure the 2048-token compatibility check including embedding prefix and
   special tokens, and record the evidence: satisfied. The measured total is
   `500 + 4 prefix + 2 special = 506 <= 2048`.
5. Authorize and execute T263 in a separate session. T264 follows T263:
   satisfied. T263 is committed at
   `0e5af08dc6c8ec3375a0361836e9d7e0c7196c31`; T264 verification and closure
   follow.

Container packaging and composition-root wiring are follow-ups recorded in §20
of the chunking specification. They are not T263 prerequisites and are not
authorized by this decision. T265 is the Docker tokenizer-asset packaging task
and depends on T264 closure; T266 is the chunking composition-root wiring task
and depends on T265 closure. Both remain open.

## 6. Out of Scope

- T263 implementation and conformance code.
- Dependency changes and lock files.
- Ollama model pulls.
- Downloading or vendoring tokenizer assets.
- Embedding generation, vector storage, and Qdrant integration.
- Changes to chunking defaults or algorithm behavior.
