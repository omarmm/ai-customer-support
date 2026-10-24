"""Offline tests for the embedding service.

No network, Ollama, Qdrant, PostgreSQL, or filesystem write is used. Tests cover
the service contracts in §6 and the batching, validation, retry, and settings
requirements in §7, §8, §10.2, and §11.3.
"""

import ast
import builtins
import inspect
import math
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import app.rag.embeddings.service as service_module
from app.core.config import Settings
from app.rag.chunking.contracts import Chunk
from app.rag.embeddings.contracts import (
    DOCUMENT_PREFIX,
    EMBEDDING_IDENTITY,
    ChunkEmbedding,
    EmbeddingConfig,
    EmbeddingResult,
)
from app.rag.embeddings.exceptions import (
    EmbeddingAuthenticationError,
    EmbeddingConfigurationError,
    EmbeddingConnectionError,
    EmbeddingError,
    EmbeddingInvalidRequestError,
    EmbeddingModelMismatchError,
    EmbeddingModelNotFoundError,
    EmbeddingRateLimitError,
    EmbeddingResponseError,
    EmbeddingTimeoutError,
    EmbeddingUnavailableError,
    EmbeddingUnexpectedError,
)
from app.rag.embeddings.providers.exceptions import (
    EmbeddingProviderAuthenticationError,
    EmbeddingProviderConnectionError,
    EmbeddingProviderInvalidRequestError,
    EmbeddingProviderModelMismatchError,
    EmbeddingProviderModelNotFoundError,
    EmbeddingProviderRateLimitError,
    EmbeddingProviderResponseError,
    EmbeddingProviderTimeoutError,
    EmbeddingProviderUnavailableError,
)
from app.rag.embeddings.retry import EmbeddingRetryPolicy
from app.rag.embeddings.service import EmbeddingService

DIMENSION = 3
CONFIG = EmbeddingConfig(dimension=DIMENSION)
DOCUMENT_ID = "d" * 64
CHUNKING_CONFIG_ID = "a" * 64
SOURCE_PATH = "docs/policy.md"


def make_vector(seed: float = 0.1) -> tuple[float, ...]:
    return (seed, seed + 0.1, seed + 0.2)


def make_default_dimension_vector(seed: float = 0.1) -> tuple[float, ...]:
    """Vector matching the pinned provisional dimension for default configs."""
    return tuple(seed + index / 1000 for index in range(768))


def make_chunk(
    index: int = 0,
    *,
    content: str | None = None,
    chunk_id: str | None = None,
) -> Chunk:
    content = content if content is not None else f"chunk {index}"
    start_offset = index * 100
    return Chunk(
        chunk_id=chunk_id if chunk_id is not None else f"{index + 1:064x}",
        document_id=DOCUMENT_ID,
        source_path=SOURCE_PATH,
        title="Policy",
        format="markdown",
        content=content,
        start_offset=start_offset,
        end_offset=start_offset + len(content),
        token_start=index,
        token_end=index + 1,
        token_count=1,
        chunk_index=index,
        chunking_config_id=CHUNKING_CONFIG_ID,
    )


class SleepRecorder:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


class FakeProvider:
    """Deterministic provider: each call consumes one queued response."""

    def __init__(
        self,
        responses=(),
        *,
        identity: object = EMBEDDING_IDENTITY,
    ) -> None:
        self.identity = identity
        self.responses = list(responses)
        self.calls: list[tuple[tuple[str, ...], float]] = []

    async def embed(
        self,
        texts,
        *,
        timeout: float,
    ) -> tuple[tuple[float, ...], ...]:
        self.calls.append((tuple(texts), timeout))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    @property
    def call_sizes(self) -> list[int]:
        return [len(texts) for texts, _ in self.calls]


def make_service(provider, **overrides) -> EmbeddingService:
    values = {
        "provider": provider,
        "config": CONFIG,
        "sleep": SleepRecorder(),
    }
    values.update(overrides)
    return EmbeddingService(**values)


def make_settings(**overrides) -> Settings:
    values = {
        "app_env": "test",
        "app_name": "AI Customer Support Backend",
        "database_url": "postgresql://test",
        "qdrant_url": "http://localhost:6333",
        "ollama_url": "http://localhost:11434",
        "llm_provider": "ollama",
    }
    values.update(overrides)
    return Settings(**values)


# --- §7.1 and §6.5: batching and ordering ----------------------------------


@pytest.mark.asyncio
async def test_batches_in_consecutive_groups_of_batch_size():
    chunks = [make_chunk(index) for index in range(5)]
    provider = FakeProvider(
        [
            (make_vector(1.0), make_vector(2.0)),
            (make_vector(3.0), make_vector(4.0)),
            (make_vector(5.0),),
        ]
    )
    service = make_service(provider, batch_size=2)

    result = await service.embed_chunks(chunks)

    assert provider.call_sizes == [2, 2, 1]
    assert result.count == 5
    assert result.retry_count == 0


@pytest.mark.asyncio
async def test_document_prefix_is_prepended_without_modifying_chunk_text():
    content = "  leading and trailing whitespace  "
    chunk = make_chunk(0, content=content)
    provider = FakeProvider([(make_vector(),)])

    await make_service(provider).embed_chunks([chunk])

    assert provider.calls[0][0] == (DOCUMENT_PREFIX + content,)


@pytest.mark.asyncio
async def test_input_order_is_preserved_across_batches():
    chunks = [make_chunk(index) for index in range(4)]
    provider = FakeProvider(
        [
            (make_vector(1.0), make_vector(2.0)),
            (make_vector(3.0), make_vector(4.0)),
        ]
    )

    result = await make_service(provider, batch_size=2).embed_chunks(chunks)

    assert [embedding.chunk_id for embedding in result.embeddings] == [
        chunk.chunk_id for chunk in chunks
    ]
    assert [embedding.vector for embedding in result.embeddings] == [
        make_vector(1.0),
        make_vector(2.0),
        make_vector(3.0),
        make_vector(4.0),
    ]


@pytest.mark.asyncio
async def test_each_output_copies_chunk_provenance_and_maps_by_chunk_id():
    chunk = make_chunk(2, content="refunds")
    provider = FakeProvider([(make_vector(),)])

    result = await make_service(provider).embed_chunks([chunk])

    embedding = result.by_chunk_id[chunk.chunk_id]
    assert isinstance(embedding, ChunkEmbedding)
    assert embedding.document_id == chunk.document_id
    assert embedding.source_path == chunk.source_path
    assert embedding.chunk_index == chunk.chunk_index
    assert embedding.start_offset == chunk.start_offset
    assert embedding.end_offset == chunk.end_offset
    assert embedding.chunking_config_id == chunk.chunking_config_id
    assert embedding.embedding_config_id == CONFIG.config_id
    assert embedding.vector == make_vector()


# --- §7.2: empty and duplicate input ---------------------------------------


@pytest.mark.asyncio
async def test_empty_input_returns_empty_result_without_provider_call():
    provider = FakeProvider([])
    service = make_service(provider)

    result = await service.embed_chunks([])

    assert isinstance(result, EmbeddingResult)
    assert result.config is CONFIG
    assert result.embeddings == ()
    assert result.count == 0
    assert result.retry_count == 0
    assert provider.calls == []


@pytest.mark.asyncio
async def test_duplicate_chunk_id_is_rejected_before_any_provider_call():
    first = make_chunk(0, chunk_id="f" * 64)
    duplicate = make_chunk(1, chunk_id="f" * 64)
    provider = FakeProvider([])

    with pytest.raises(ValueError, match="^duplicate chunk_id$"):
        await make_service(provider).embed_chunks([first, duplicate])

    assert provider.calls == []


# --- §7.3: service-layer response validation -------------------------------


@pytest.mark.asyncio
async def test_count_mismatch_is_a_response_error():
    chunks = [make_chunk(0), make_chunk(1)]
    provider = FakeProvider([(make_vector(),)])

    with pytest.raises(EmbeddingResponseError) as caught:
        await make_service(provider, batch_size=2).embed_chunks(chunks)

    assert caught.value.reason == "count_mismatch"
    assert caught.value.retryable is False
    assert caught.value.retry_count == 0
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_empty_embeddings_for_a_non_empty_batch_is_a_response_error():
    provider = FakeProvider([()])

    with pytest.raises(EmbeddingResponseError) as caught:
        await make_service(provider).embed_chunks([make_chunk(0)])

    assert caught.value.reason == "empty_embeddings"
    assert caught.value.retryable is False


@pytest.mark.asyncio
async def test_dimension_mismatch_is_a_response_error():
    provider = FakeProvider([((0.1, 0.2),)])

    with pytest.raises(EmbeddingResponseError) as caught:
        await make_service(provider).embed_chunks([make_chunk(0)])

    assert caught.value.reason == "dimension_mismatch"
    assert caught.value.retryable is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    [math.nan, math.inf, -math.inf],
)
async def test_non_finite_vector_values_are_rejected(value):
    provider = FakeProvider([((0.1, value, 0.3),)])

    with pytest.raises(EmbeddingResponseError) as caught:
        await make_service(provider).embed_chunks([make_chunk(0)])

    assert caught.value.reason == "non_finite_value"
    assert caught.value.retryable is False


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [True, "0.1", None, [0.1]])
async def test_invalid_vector_element_types_are_rejected_without_leaking(value):
    provider = FakeProvider([((0.1, value, 0.3),)])

    with pytest.raises(EmbeddingResponseError) as caught:
        await make_service(provider).embed_chunks([make_chunk(0)])

    assert caught.value.reason == "malformed_response"


# --- §8: normalization, retries, and retry counts --------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason",
    ["invalid_json", "malformed_response", "missing_embeddings"],
)
async def test_provider_response_errors_preserve_the_reason_code(reason):
    provider_error = EmbeddingProviderResponseError(reason)
    provider = FakeProvider([provider_error])

    with pytest.raises(EmbeddingResponseError) as caught:
        await make_service(provider).embed_chunks([make_chunk(0)])

    assert caught.value.reason == reason
    assert caught.value.retryable is False
    assert caught.value.__cause__ is provider_error
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_model_mismatch_is_permanent_and_not_retried():
    provider_error = EmbeddingProviderModelMismatchError()
    provider = FakeProvider([provider_error])

    with pytest.raises(EmbeddingModelMismatchError) as caught:
        await make_service(provider).embed_chunks([make_chunk(0)])

    assert caught.value.retryable is False
    assert caught.value.retry_count == 0
    assert caught.value.__cause__ is provider_error
    assert len(provider.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_error", "application_error"),
    [
        (EmbeddingProviderConnectionError("down"), EmbeddingConnectionError),
        (EmbeddingProviderTimeoutError("slow"), EmbeddingTimeoutError),
        (EmbeddingProviderRateLimitError(429), EmbeddingRateLimitError),
        (EmbeddingProviderUnavailableError(503), EmbeddingUnavailableError),
    ],
)
async def test_retryable_provider_errors_are_retried_then_succeed(
    provider_error,
    application_error,
):
    provider = FakeProvider([provider_error, (make_vector(),)])
    sleep = SleepRecorder()

    result = await make_service(provider, sleep=sleep).embed_chunks([make_chunk(0)])

    assert len(provider.calls) == 2
    assert result.retry_count == 1
    assert sleep.delays == [0.5]
    assert isinstance(result.embeddings[0], ChunkEmbedding)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_error", "application_error"),
    [
        (EmbeddingProviderAuthenticationError(401), EmbeddingAuthenticationError),
        (EmbeddingProviderInvalidRequestError(400), EmbeddingInvalidRequestError),
        (EmbeddingProviderModelNotFoundError(404), EmbeddingModelNotFoundError),
    ],
)
async def test_non_retryable_provider_errors_are_not_retried(
    provider_error,
    application_error,
):
    provider = FakeProvider([provider_error])
    sleep = SleepRecorder()

    with pytest.raises(application_error) as caught:
        await make_service(provider, sleep=sleep).embed_chunks([make_chunk(0)])

    assert caught.value.retryable is False
    assert caught.value.retry_count == 0
    assert caught.value.__cause__ is provider_error
    assert len(provider.calls) == 1
    assert sleep.delays == []


@pytest.mark.asyncio
async def test_retry_exhaustion_raises_the_final_normalized_error():
    provider = FakeProvider(
        [
            EmbeddingProviderConnectionError("down"),
            EmbeddingProviderConnectionError("down"),
            EmbeddingProviderConnectionError("down"),
        ]
    )
    sleep = SleepRecorder()

    with pytest.raises(EmbeddingConnectionError) as caught:
        await make_service(
            provider,
            retry_policy=EmbeddingRetryPolicy(max_retries=2),
            sleep=sleep,
        ).embed_chunks([make_chunk(0)])

    # Three attempts = two retries; the terminal attempt is not a retry.
    assert len(provider.calls) == 3
    assert caught.value.retry_count == 2
    assert sleep.delays == [0.5, 1.0]


@pytest.mark.asyncio
async def test_successful_execution_aggregates_retry_count_across_batches():
    chunks = [make_chunk(index) for index in range(4)]
    provider = FakeProvider(
        [
            EmbeddingProviderConnectionError("down"),
            (make_vector(1.0), make_vector(2.0)),
            EmbeddingProviderConnectionError("down"),
            (make_vector(3.0), make_vector(4.0)),
        ]
    )
    sleep = SleepRecorder()

    result = await make_service(provider, batch_size=2, sleep=sleep).embed_chunks(
        chunks
    )

    assert len(provider.calls) == 4
    assert result.retry_count == 2
    assert result.count == 4
    assert sleep.delays == [0.5, 0.5]


@pytest.mark.asyncio
async def test_failed_execution_reports_earlier_batch_retries():
    chunks = [make_chunk(index) for index in range(4)]
    provider = FakeProvider(
        [
            EmbeddingProviderConnectionError("down"),
            (make_vector(1.0), make_vector(2.0)),
            EmbeddingProviderAuthenticationError(401),
        ]
    )

    with pytest.raises(EmbeddingAuthenticationError) as caught:
        await make_service(provider, batch_size=2).embed_chunks(chunks)

    assert len(provider.calls) == 3
    assert caught.value.retry_count == 1


@pytest.mark.asyncio
async def test_failed_execution_reports_retries_before_exhaustion():
    chunks = [make_chunk(index) for index in range(4)]
    provider = FakeProvider(
        [
            EmbeddingProviderConnectionError("down"),
            (make_vector(1.0), make_vector(2.0)),
            EmbeddingProviderConnectionError("down"),
            EmbeddingProviderConnectionError("down"),
            EmbeddingProviderConnectionError("down"),
        ]
    )

    with pytest.raises(EmbeddingConnectionError) as caught:
        await make_service(
            provider,
            batch_size=2,
            retry_policy=EmbeddingRetryPolicy(max_retries=2),
        ).embed_chunks(chunks)

    # One retry in the first batch + two retries in the second batch.
    assert len(provider.calls) == 5
    assert caught.value.retry_count == 3


@pytest.mark.asyncio
async def test_timeout_is_passed_to_every_attempt_and_backoff_is_separate():
    provider = FakeProvider(
        [
            EmbeddingProviderTimeoutError("slow"),
            EmbeddingProviderTimeoutError("slow"),
            (make_vector(),),
        ]
    )
    sleep = SleepRecorder()

    await make_service(
        provider,
        timeout=1.25,
        retry_policy=EmbeddingRetryPolicy(max_retries=2),
        sleep=sleep,
    ).embed_chunks([make_chunk(0)])

    assert [timeout for _, timeout in provider.calls] == [1.25, 1.25, 1.25]
    assert sleep.delays == [0.5, 1.0]


@pytest.mark.asyncio
async def test_unexpected_errors_map_to_unexpected_and_are_not_retried():
    original = RuntimeError("boom")
    provider = FakeProvider([original])
    sleep = SleepRecorder()

    with pytest.raises(EmbeddingUnexpectedError) as caught:
        await make_service(provider, sleep=sleep).embed_chunks([make_chunk(0)])

    assert caught.value.__cause__ is original
    assert caught.value.retryable is False
    assert caught.value.retry_count == 0
    assert len(provider.calls) == 1
    assert sleep.delays == []


@pytest.mark.asyncio
async def test_provider_exceptions_and_raw_errors_never_escape():
    provider = FakeProvider([EmbeddingProviderConnectionError("down")] * 3)

    with pytest.raises(EmbeddingError) as caught:
        await make_service(
            provider,
            retry_policy=EmbeddingRetryPolicy(max_retries=2),
        ).embed_chunks([make_chunk(0)])

    assert not isinstance(caught.value, EmbeddingProviderConnectionError)


# --- §6.4 and §10.2: construction, identity, and settings ------------------


def test_provider_identity_must_match_the_configuration():
    provider = FakeProvider([], identity="other:model")

    with pytest.raises(EmbeddingConfigurationError):
        make_service(provider)


def test_non_string_provider_identity_is_a_configuration_error():
    provider = FakeProvider([], identity=None)

    with pytest.raises(EmbeddingConfigurationError):
        make_service(provider)


@pytest.mark.parametrize("batch_size", [0, -1, True, 1.5])
def test_invalid_batch_size_is_rejected(batch_size):
    with pytest.raises(ValueError, match="batch_size"):
        make_service(FakeProvider([]), batch_size=batch_size)


@pytest.mark.parametrize("timeout", [0, -1, True, math.nan, math.inf])
def test_invalid_timeout_is_rejected(timeout):
    with pytest.raises(ValueError, match="timeout"):
        make_service(FakeProvider([]), timeout=timeout)


def test_non_policy_retry_policy_is_rejected():
    with pytest.raises(ValueError, match="retry_policy"):
        make_service(FakeProvider([]), retry_policy=object())


def test_non_configuration_config_is_rejected():
    with pytest.raises(ValueError, match="config"):
        make_service(FakeProvider([]), config=object())


def test_service_exposes_its_effective_configuration():
    service = make_service(FakeProvider([]))

    assert service.config is CONFIG
    assert service.config.config_id == CONFIG.config_id


@pytest.mark.asyncio
async def test_from_settings_maps_settings_without_eager_global_access(monkeypatch):
    import app.core.config as config_module

    def fail():
        raise AssertionError("from_settings must not call get_settings")

    monkeypatch.setattr(config_module, "get_settings", fail)

    settings = SimpleNamespace(
        embedding_batch_size=2,
        embedding_timeout_seconds=1.5,
        embedding_max_retries=4,
        embedding_retry_base_delay=0.25,
        embedding_retry_max_delay=2.0,
        embedding_retry_jitter=0.1,
    )
    provider = FakeProvider(
        [
            (
                make_default_dimension_vector(1.0),
                make_default_dimension_vector(2.0),
            ),
            (make_default_dimension_vector(3.0),),
        ]
    )
    service = EmbeddingService.from_settings(settings, provider)
    result = await service.embed_chunks([make_chunk(index) for index in range(3)])

    assert service.config == EmbeddingConfig()
    assert provider.call_sizes == [2, 1]
    assert [timeout for _, timeout in provider.calls] == [1.5, 1.5]
    assert result.retry_count == 0


def test_embedding_settings_have_the_approved_defaults():
    settings = make_settings()

    assert settings.embedding_batch_size == 16
    assert settings.embedding_timeout_seconds == 30.0
    assert settings.embedding_max_retries == 2
    assert settings.embedding_retry_base_delay == 0.5
    assert settings.embedding_retry_max_delay == 8.0
    assert settings.embedding_retry_jitter == 0.0


def test_embedding_settings_read_environment_variables(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "4")
    monkeypatch.setenv("EMBEDDING_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "5")
    monkeypatch.setenv("EMBEDDING_RETRY_BASE_DELAY", "0.2")
    monkeypatch.setenv("EMBEDDING_RETRY_MAX_DELAY", "3.0")
    monkeypatch.setenv("EMBEDDING_RETRY_JITTER", "0.1")

    settings = make_settings()

    assert settings.embedding_batch_size == 4
    assert settings.embedding_timeout_seconds == 12.5
    assert settings.embedding_max_retries == 5
    assert settings.embedding_retry_base_delay == 0.2
    assert settings.embedding_retry_max_delay == 3.0
    assert settings.embedding_retry_jitter == 0.1


@pytest.mark.parametrize(
    "overrides",
    [
        {"embedding_batch_size": 0},
        {"embedding_timeout_seconds": 0},
        {"embedding_max_retries": -1},
        {"embedding_retry_base_delay": -0.1},
        {"embedding_retry_max_delay": -0.1},
        {"embedding_retry_jitter": -0.1},
        {"embedding_retry_base_delay": 2.0, "embedding_retry_max_delay": 1.0},
    ],
)
def test_invalid_embedding_settings_fail_at_construction(overrides):
    with pytest.raises(ValidationError):
        make_settings(**overrides)


def test_env_example_documents_every_embedding_setting():
    example = (Path(__file__).parents[3] / ".env.example").read_text()

    for name in (
        "EMBEDDING_BATCH_SIZE",
        "EMBEDDING_TIMEOUT_SECONDS",
        "EMBEDDING_MAX_RETRIES",
        "EMBEDDING_RETRY_BASE_DELAY",
        "EMBEDDING_RETRY_MAX_DELAY",
        "EMBEDDING_RETRY_JITTER",
    ):
        assert name in example


# --- §10.3 and §11.5: security, imports, and no writes ---------------------


@pytest.mark.asyncio
async def test_error_messages_contain_no_chunk_text_or_vector_values():
    secret_text = "SECRET-CHUNK-TEXT"
    chunk = make_chunk(0, content=secret_text)
    provider = FakeProvider([((1234.5678,),)])

    with pytest.raises(EmbeddingResponseError) as caught:
        await make_service(provider).embed_chunks([chunk])

    message = str(caught.value)
    assert secret_text not in message
    assert "1234.5678" not in message
    assert "vector" not in message


@pytest.mark.asyncio
async def test_service_performs_no_filesystem_writes(monkeypatch):
    def fail_open(*args, **kwargs):
        raise AssertionError("embedding service must not open files")

    monkeypatch.setattr(builtins, "open", fail_open)
    monkeypatch.setattr(Path, "write_text", fail_open)
    monkeypatch.setattr(Path, "write_bytes", fail_open)

    provider = FakeProvider([(make_vector(),)])

    result = await make_service(provider).embed_chunks([make_chunk(0)])

    assert result.count == 1


def _imported_modules(module) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_service_imports_no_forbidden_modules():
    modules = _imported_modules(service_module)
    forbidden_prefixes = (
        "app.llm",
        "qdrant_client",
        "sqlalchemy",
        "psycopg",
        "fastapi",
        "app.infrastructure",
    )

    for module in modules:
        assert not module.startswith(forbidden_prefixes), module


def test_retry_module_does_not_import_the_llm_subsystem():
    from app.rag.embeddings import retry as retry_module

    modules = _imported_modules(retry_module)

    assert not any(module.startswith("app.llm") for module in modules)


def test_policy_is_frozen():
    policy = EmbeddingRetryPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.max_retries = 3  # type: ignore[misc]
