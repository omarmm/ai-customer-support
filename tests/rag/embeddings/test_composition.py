"""Integration tests for the production embedding composition root (T271).

These tests exercise the actual production wiring: the composition factory, the
FastAPI startup hook that exposes the service through ``app.state``, the
explicit ``settings.ollama_url`` hand-off required by D-6, and the absence of a
new endpoint, consumer, or dependency-injection framework.

The factory test replaces the HTTP adapter with an in-memory provider so the
suite remains offline. It does not replace the adapter-level conformance tests.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.rag.chunking.contracts import Chunk
from app.rag.embeddings import composition
from app.rag.embeddings.composition import build_embedding_service
from app.rag.embeddings.contracts import (
    EMBEDDING_IDENTITY,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    PROVISIONAL_EMBEDDING_DIMENSION,
    EmbeddingConfig,
)
from app.rag.embeddings.service import EmbeddingService

REPO_ROOT = Path(__file__).resolve().parents[3]
OLLAMA_URL = "http://embeddings.test:11434"
REQUIRED_ENV = {
    "APP_ENV": "test",
    "APP_NAME": "AI Customer Support Backend",
    "DATABASE_URL": "postgresql://test",
    "QDRANT_URL": "http://localhost:6333",
    "OLLAMA_URL": OLLAMA_URL,
    "LLM_PROVIDER": "ollama",
}


def make_settings(**overrides) -> Settings:
    values = dict(REQUIRED_ENV)
    values.update(overrides)
    return Settings(**values)


def make_chunk(index: int) -> Chunk:
    content = f"Chunk {index}."
    return Chunk.build(
        document_id="document-1",
        source_path="knowledge/support-policy.md",
        title="Support Policy",
        format="markdown",
        content=content,
        start_offset=0,
        end_offset=len(content),
        token_start=0,
        token_end=1,
        chunk_index=index,
        chunking_config_id="chunking-config-1",
    )


class RecordingProvider:
    """In-memory provider that records calls and returns finite vectors."""

    identity = EMBEDDING_IDENTITY

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.calls: list[tuple[tuple[str, ...], float]] = []

    async def embed(
        self,
        texts,
        *,
        timeout: float,
    ) -> tuple[tuple[float, ...], ...]:
        self.calls.append((tuple(texts), timeout))
        return tuple(
            tuple(0.0 for _ in range(PROVISIONAL_EMBEDDING_DIMENSION))
            for _ in texts
        )


# --- Factory -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_factory_builds_the_service_from_settings(monkeypatch) -> None:
    created: list[RecordingProvider] = []

    class Provider(RecordingProvider):
        def __init__(self, base_url: str) -> None:
            super().__init__(base_url)
            created.append(self)

    monkeypatch.setattr(composition, "OllamaEmbeddingProvider", Provider)

    settings = make_settings(
        embedding_batch_size=2,
        embedding_timeout_seconds=9.5,
        embedding_max_retries=3,
        embedding_retry_base_delay=0.0,
        embedding_retry_max_delay=1.0,
        embedding_retry_jitter=0.0,
    )

    service = build_embedding_service(settings)

    assert isinstance(service, EmbeddingService)
    assert service.config == EmbeddingConfig()
    assert service.config.provider == EMBEDDING_PROVIDER
    assert service.config.model == EMBEDDING_MODEL
    assert service.config.dimension == PROVISIONAL_EMBEDDING_DIMENSION

    # D-6: the adapter receives the existing setting explicitly.
    assert len(created) == 1
    assert created[0].base_url == settings.ollama_url == OLLAMA_URL

    result = await service.embed_chunks([make_chunk(index) for index in range(3)])

    # The operational settings are copied into the service, not read globally.
    assert [len(texts) for texts, _ in created[0].calls] == [2, 1]
    assert [timeout for _, timeout in created[0].calls] == [9.5, 9.5]
    assert result.count == 3
    assert result.retry_count == 0


# --- Application startup -----------------------------------------------------


def test_application_startup_exposes_the_composed_service(monkeypatch) -> None:
    created: list[RecordingProvider] = []

    class Provider(RecordingProvider):
        def __init__(self, base_url: str) -> None:
            super().__init__(base_url)
            created.append(self)

    monkeypatch.setattr(composition, "OllamaEmbeddingProvider", Provider)
    for key, value in {
        **REQUIRED_ENV,
        "EMBEDDING_BATCH_SIZE": "5",
        "EMBEDDING_TIMEOUT_SECONDS": "7.5",
    }.items():
        monkeypatch.setenv(key, value)

    get_settings.cache_clear()
    sys.modules.pop("app.main", None)
    main_module = importlib.import_module("app.main")

    with TestClient(main_module.app) as client:
        service = main_module.app.state.embedding_service

        assert isinstance(service, EmbeddingService)
        assert service.config == EmbeddingConfig()
        assert len(created) == 1
        assert created[0].base_url == OLLAMA_URL
        assert client.get("/health").json() == {"status": "ok"}

        # The service is constructed once per process, not per request.
        client.get("/health")
        assert main_module.app.state.embedding_service is service

    get_settings.cache_clear()


# --- Boundary ----------------------------------------------------------------


def test_composition_adds_no_endpoint_consumer_or_di_framework() -> None:
    main_tree = ast.parse(
        (REPO_ROOT / "src" / "app" / "main.py").read_text(encoding="utf-8")
    )
    route_paths: list[str] = []

    for node in ast.walk(main_tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Attribute):
                continue
            if not isinstance(decorator.func.value, ast.Name):
                continue
            if decorator.func.value.id != "app" or not decorator.args:
                continue
            route_paths.append(decorator.args[0].value)

    assert route_paths == ["/health"]

    composition_tree = ast.parse(
        Path(composition.__file__).read_text(encoding="utf-8")
    )
    imported: list[str] = []
    for node in ast.walk(composition_tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden_roots = {
        "app.llm",
        "dependency_injector",
        "fastapi",
        "injector",
        "psycopg",
        "qdrant_client",
        "sqlalchemy",
    }
    for module in imported:
        for root in forbidden_roots:
            assert not (module == root or module.startswith(f"{root}.")), module
