from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str
    app_name: str

    database_url: str
    qdrant_url: str = Field(min_length=1)
    qdrant_api_key: str | None = Field(default=None, repr=False)

    ollama_url: str
    llm_provider: str

    llm_max_retries: int = 2
    llm_retry_base_delay: float = 0.5
    llm_retry_max_delay: float = 8.0
    llm_retry_jitter: float = 0.0

    llm_pricing: str = ""
    llm_pricing_currency: str = "USD"

    knowledge_dir: str = "knowledge"
    knowledge_max_document_bytes: int = Field(default=1_048_576, gt=0)
    knowledge_max_documents_per_run: int = Field(default=1000, gt=0)

    knowledge_chunk_max_tokens: int = Field(default=500, gt=0)
    knowledge_chunk_overlap_tokens: int = Field(default=75, ge=0)

    embedding_batch_size: int = Field(default=16, gt=0)
    embedding_timeout_seconds: float = Field(default=30.0, gt=0)
    embedding_max_retries: int = Field(default=2, ge=0)
    embedding_retry_base_delay: float = Field(default=0.5, ge=0)
    embedding_retry_max_delay: float = Field(default=8.0, ge=0)
    embedding_retry_jitter: float = Field(default=0.0, ge=0)

    model_config = SettingsConfigDict(
        case_sensitive=False,
    )

    @field_validator("qdrant_url")
    @classmethod
    def _validate_qdrant_url(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("qdrant_url must be a non-empty URL")
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("qdrant_url must be an absolute HTTP(S) URL")
        if any(character.isspace() for character in value):
            raise ValueError("qdrant_url must not contain whitespace")
        return value

    @field_validator("qdrant_api_key", mode="before")
    @classmethod
    def _normalize_optional_qdrant_api_key(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value if value.strip() else None
        raise ValueError("qdrant_api_key must be a string when provided")

    @model_validator(mode="after")
    def _validate_chunking_settings(self) -> "Settings":
        if self.knowledge_chunk_overlap_tokens >= self.knowledge_chunk_max_tokens:
            raise ValueError(
                "knowledge_chunk_overlap_tokens must be less than "
                "knowledge_chunk_max_tokens"
            )
        return self

    @model_validator(mode="after")
    def _validate_embedding_settings(self) -> "Settings":
        if self.embedding_retry_max_delay < self.embedding_retry_base_delay:
            raise ValueError(
                "embedding_retry_max_delay must be greater than or equal to "
                "embedding_retry_base_delay"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
