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
- Local runtime behavior is a design requirement and is not yet tested; T263
  must provide the evidence.

## 2. Tokenizer identity

Format:

```text
tokenizers:<lib_version>:<model_id>@<revision_sha>:<sha256(tokenizer.json)>
```

Resolved example with the checksum still unknown:

```text
tokenizers:0.23.3:nomic-ai/nomic-embed-text-v1.5@e9b6763023c676ca8431644204f50c2b100d9aab:<sha256>
```

Rules:

- The checksum is computed from the actually vendored `tokenizer.json` during
  T263. It must never be invented, pre-filled, or hard-coded.
- The provenance record captures the full SHA-256 of the vendored asset, and the
  identity uses that full digest as approved.
- The actual digest remains unknown until the asset is vendored and hashed.
- The asset hash covers the tokenizer's normalization and flag configuration.
  Loading must not apply runtime overrides to that configuration.
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
- Status: **not yet verified.** The 500/75 defaults remain provisional until
  T263 measures this. If the check fails, the chunking specification must be
  amended before T263 implementation; the defaults must not be changed
  silently.

## 4. Why the serving tag is excluded from the identity

The tokenizer identity describes tokenization behavior, which determines chunk
boundaries and `chunking_config_id`. The Ollama tag describes model serving and
may be re-pulled, re-quantized, or re-tagged without changing tokenization.
Including it would force unnecessary re-chunking on serving-side changes and
would contradict the chunking specification's rule that an embedding model
change with an unchanged tokenizer identity re-embeds only and may reuse
chunks.

## 5. Remaining prerequisites for T263

1. Vendor `tokenizer.json` from revision
   `e9b6763023c676ca8431644204f50c2b100d9aab`, verify its presence and
   integrity, and compute the full SHA-256 from the vendored file.
2. Add the approved `tokenizers==0.23.3` dependency at T263 implementation
   time as part of normal development setup; this decision does not modify
   dependencies and does not require an offline wheelhouse.
3. Verify local runtime behavior: the adapter loads the local asset and
   tokenizes without network access or Hugging Face Hub access, and record the
   evidence.
4. Measure the 2048-token compatibility check including embedding prefix and
   special tokens, and record the evidence.
5. Authorize and execute T263 in a separate session. T264 follows T263.

## 6. Out of Scope

- T263 implementation and conformance code.
- Dependency changes and lock files.
- Ollama model pulls.
- Downloading or vendoring tokenizer assets.
- Embedding generation, vector storage, and Qdrant integration.
- Changes to chunking defaults or algorithm behavior.
