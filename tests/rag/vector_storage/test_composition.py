"""T278 tests for the production vector storage composition root."""

from __future__ import annotations

import importlib
import socket
import sys

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.rag.vector_storage.composition import build_vector_store
from app.rag.vector_storage.qdrant_adapter import (
    DEFAULT_QDRANT_TIMEOUT_SECONDS,
    QdrantClientAdapter,
    QdrantClientConfig,
)

REQUIRED_ENV = {
    "APP_ENV": "test",
    "APP_NAME": "AI Customer Support Backend",
    "DATABASE_URL": "postgresql://test",
    "QDRANT_URL": "http://qdrant.test:6333",
    "OLLAMA_URL": "http://ollama.test:11434",
    "LLM_PROVIDER": "ollama",
}


def make_settings(**overrides) -> Settings:
    values = dict(REQUIRED_ENV)
    values.update(overrides)
    return Settings(**values)


def test_factory_passes_explicit_qdrant_settings_to_adapter(monkeypatch) -> None:
    captured: list[QdrantClientConfig] = []
    sentinel = object()

    def from_config(cls, config, **kwargs):
        captured.append(config)
        return sentinel

    monkeypatch.setattr(QdrantClientAdapter, "from_config", classmethod(from_config))
    settings = make_settings(qdrant_api_key="test-api-key")

    result = build_vector_store(settings)

    assert result is sentinel
    assert captured == [
        QdrantClientConfig(
            url="http://qdrant.test:6333",
            api_key="test-api-key",
            timeout=DEFAULT_QDRANT_TIMEOUT_SECONDS,
        )
    ]


def test_factory_construction_performs_no_network_io(monkeypatch) -> None:
    def blocked(*args, **kwargs):
        raise AssertionError("Qdrant network I/O attempted during construction")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)

    service = build_vector_store(make_settings())

    assert isinstance(service, QdrantClientAdapter)


def test_application_startup_exposes_one_vector_store_without_qdrant_io(
    monkeypatch,
) -> None:
    import app.rag.vector_storage.composition as composition

    constructed: list[object] = []
    sentinel = object()

    def build(settings):
        constructed.append(settings.qdrant_url)
        return sentinel

    monkeypatch.setattr(composition, "build_vector_store", build)
    def blocked(*args, **kwargs):
        raise AssertionError("network access attempted during application startup")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)

    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    sys.modules.pop("app.main", None)
    main_module = importlib.import_module("app.main")

    try:
        with TestClient(main_module.app) as client:
            service = main_module.app.state.vector_store
            assert service is sentinel
            assert constructed == ["http://qdrant.test:6333"]
            assert client.get("/health").status_code == 200
            assert client.get("/health").json() == {"status": "ok"}
            assert main_module.app.state.vector_store is service
            assert constructed == ["http://qdrant.test:6333"]
    finally:
        get_settings.cache_clear()
        sys.modules.pop("app.main", None)
