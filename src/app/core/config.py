from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str
    app_name: str

    database_url: str
    qdrant_url: str

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

    model_config = SettingsConfigDict(
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
