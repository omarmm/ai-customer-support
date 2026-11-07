"""T274 configuration contract tests for the Qdrant runtime settings."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


REQUIRED_ENV = {
    "app_env": "test",
    "app_name": "AI Customer Support Backend",
    "database_url": "postgresql://test",
    "qdrant_url": "http://localhost:6333",
    "ollama_url": "http://localhost:11434",
    "llm_provider": "ollama",
}


def make_settings(**overrides) -> Settings:
    values = dict(REQUIRED_ENV)
    values.update(overrides)
    return Settings(**values)


def test_qdrant_api_key_is_optional_by_default() -> None:
    settings = make_settings()

    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.qdrant_api_key is None


def test_qdrant_api_key_can_be_configured() -> None:
    settings = make_settings(qdrant_api_key="local-development-key")

    assert settings.qdrant_api_key == "local-development-key"


@pytest.mark.parametrize("api_key", ["", None])
def test_qdrant_api_key_accepts_only_absent_or_non_empty_values(api_key) -> None:
    if api_key is None:
        assert make_settings(qdrant_api_key=api_key).qdrant_api_key is None
    else:
        with pytest.raises(ValidationError):
            make_settings(qdrant_api_key=api_key)


def test_qdrant_url_remains_required(monkeypatch) -> None:
    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.delenv("qdrant_url", raising=False)
    values = dict(REQUIRED_ENV)
    values.pop("qdrant_url")

    with pytest.raises(ValidationError):
        Settings(**values)


def test_env_example_documents_qdrant_connection_settings() -> None:
    example = (Path(__file__).parents[3] / ".env.example").read_text(
        encoding="utf-8"
    )

    assert "QDRANT_URL=" in example
    assert "QDRANT_API_KEY=" in example
