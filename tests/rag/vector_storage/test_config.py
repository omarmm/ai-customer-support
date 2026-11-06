"""Configuration tests for the Qdrant connection settings introduced by T274."""

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def required_settings(**overrides):
    values = {
        "app_env": "test",
        "app_name": "AI Customer Support Backend Tests",
        "database_url": "postgresql+psycopg://test:test@localhost/test",
        "qdrant_url": "http://localhost:6333",
        "ollama_url": "http://localhost:11434",
        "llm_provider": "ollama",
    }
    values.update(overrides)
    return values


def test_qdrant_url_remains_a_required_setting():
    values = required_settings()
    values.pop("qdrant_url")

    with pytest.raises(ValidationError):
        Settings(**values)


@pytest.mark.parametrize("url", ["", " ", "\t", "\n"])
def test_qdrant_url_rejects_empty_or_whitespace_values(url):
    with pytest.raises(ValidationError):
        Settings(**required_settings(qdrant_url=url))


def test_qdrant_api_key_is_optional_by_default(monkeypatch):
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)

    settings = Settings(**required_settings())

    assert settings.qdrant_api_key is None


def test_qdrant_api_key_can_be_supplied_through_environment(monkeypatch):
    monkeypatch.setenv("QDRANT_API_KEY", "test-qdrant-secret")

    settings = Settings(**required_settings())

    assert settings.qdrant_api_key == "test-qdrant-secret"
    assert "test-qdrant-secret" not in repr(settings)


@pytest.mark.parametrize("value", ["", " ", "\t", "\n"])
def test_empty_optional_qdrant_api_key_is_normalized_to_none(monkeypatch, value):
    monkeypatch.setenv("QDRANT_API_KEY", value)

    settings = Settings(**required_settings())

    assert settings.qdrant_api_key is None


def test_qdrant_api_key_rejects_non_string_values():
    with pytest.raises(ValidationError):
        Settings(**required_settings(qdrant_api_key=123))


def test_fastapi_startup_does_not_construct_a_qdrant_client():
    repository_root = Path(__file__).resolve().parents[3]
    main_path = repository_root / "src" / "app" / "main.py"
    source = main_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert not any(
        module == "qdrant_client" or module.startswith("qdrant_client.")
        for module in imported_modules
    )
    assert "QdrantClient" not in imported_names
    assert "build_qdrant_client" not in imported_names
    assert "QdrantClient" not in called_names
    assert "build_qdrant_client" not in called_names


@pytest.mark.parametrize(
    "url",
    ["localhost:6333", "ftp://qdrant:6333", "http:///missing-host", "http://bad host:6333"],
)
def test_qdrant_url_rejects_non_absolute_or_invalid_http_urls(url):
    with pytest.raises(ValidationError):
        Settings(**required_settings(qdrant_url=url))


def test_qdrant_url_accepts_https():
    settings = Settings(**required_settings(qdrant_url="https://qdrant.example.com"))

    assert settings.qdrant_url == "https://qdrant.example.com"
