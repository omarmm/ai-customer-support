"""Live Ollama embedding conformance evidence (T270).

These tests are opt-in and are skipped unless ``RUN_LIVE_OLLAMA=1`` (approved
D-5). They are not part of the default or offline focused suites.

Scope is conformance evidence only. The digest reported by ``GET /api/tags`` is
recorded verbatim as evidence; it is never compared with an expected value and
this module does not add runtime digest verification. The production adapter
and service never call ``/api/tags`` or ``/api/show``.

Documented metadata command::

    curl -s "${OLLAMA_URL}/api/tags"

The base URL is the existing ``OLLAMA_URL`` setting (D-6). Live execution
requires the pinned model and is recorded in ``specs/project-state.md``.
"""

import math
import os

import httpx
import pytest

from app.rag.embeddings.contracts import (
    DOCUMENT_PREFIX,
    EMBEDDING_MODEL,
    PROVISIONAL_EMBEDDING_DIMENSION,
)
from app.rag.embeddings.providers.ollama import OllamaEmbeddingProvider

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OLLAMA") != "1",
    reason="live Ollama conformance requires RUN_LIVE_OLLAMA=1",
)

DEFAULT_OLLAMA_URL = "http://localhost:11434"
TIMEOUT = 60.0

SAMPLE_TEXTS = (
    DOCUMENT_PREFIX + "Refunds are processed within 5-7 business days.",
    DOCUMENT_PREFIX + "Returns are accepted within 30 days of delivery.",
    DOCUMENT_PREFIX + "Contact support for help with a damaged item.",
)


def ollama_url() -> str:
    """Return the existing OLLAMA_URL setting, or a local default."""
    return (os.environ.get("OLLAMA_URL") or DEFAULT_OLLAMA_URL).rstrip("/")


def fetch_model_metadata() -> dict:
    """Return the live model entry from ``GET /api/tags`` (evidence only)."""
    response = httpx.get(f"{ollama_url()}/api/tags", timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    models = payload.get("models") if isinstance(payload, dict) else None
    assert isinstance(models, list), "live Ollama returned no models array"

    entries = [
        entry
        for entry in models
        if isinstance(entry, dict) and entry.get("name") == EMBEDDING_MODEL
    ]
    assert entries, f"approved model {EMBEDDING_MODEL!r} is not available"
    return entries[0]


def test_live_model_metadata_evidence():
    """Record the served model name and digest as reported by Ollama."""
    entry = fetch_model_metadata()

    digest = entry.get("digest")
    assert isinstance(digest, str) and digest, "live Ollama did not report a digest"

    print(f"\nmodel name: {entry.get('name')!r}")
    print(f"model digest (verbatim evidence, not verified): {digest!r}")
    print(f"model details: {entry.get('details')}")


def test_live_embed_response_evidence():
    """Record the raw response model and measure the live vector dimension.

    The production adapter validates the same ``model`` field. This raw call
    exists only to record the reported value and measured dimension as
    conformance evidence; it is not a second runtime code path.
    """
    response = httpx.post(
        f"{ollama_url()}/api/embed",
        json={"model": EMBEDDING_MODEL, "input": list(SAMPLE_TEXTS)},
        timeout=TIMEOUT,
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload.get("model") == EMBEDDING_MODEL

    embeddings = payload.get("embeddings")
    assert isinstance(embeddings, list)
    assert len(embeddings) == len(SAMPLE_TEXTS)

    dimensions = {len(vector) for vector in embeddings}
    assert dimensions == {PROVISIONAL_EMBEDDING_DIMENSION}

    for vector in embeddings:
        for value in vector:
            assert isinstance(value, (int, float)) and not isinstance(value, bool)
            assert math.isfinite(value)

    print(f"\nresponse model: {payload.get('model')!r}")
    print(f"observed dimension: {dimensions.pop()}")
    print(f"finite values: {sum(len(vector) for vector in embeddings)}")


@pytest.mark.asyncio
async def test_live_adapter_conformance():
    """Exercise the production adapter against the live approved model."""
    provider = OllamaEmbeddingProvider(base_url=ollama_url())

    vectors = await provider.embed(SAMPLE_TEXTS, timeout=TIMEOUT)

    assert len(vectors) == len(SAMPLE_TEXTS)
    assert {len(vector) for vector in vectors} == {
        PROVISIONAL_EMBEDDING_DIMENSION
    }
    for vector in vectors:
        assert all(math.isfinite(value) for value in vector)

    print(f"\nadapter identity: {provider.identity!r}")
    print(f"adapter vectors: {len(vectors)}")
