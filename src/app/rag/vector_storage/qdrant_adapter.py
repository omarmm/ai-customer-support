"""Qdrant client boundary for knowledge vector storage.

Only this module imports the Qdrant SDK and HTTPX. Qdrant SDK exceptions, SDK
response models, raw response bodies, and API keys never escape the adapter:
every failure is translated into the application-owned taxonomy defined in
``app.rag.vector_storage.exceptions``.

This module implements client construction, bounded retries, generation
collection creation, ordered point upserts, generation verification, and
atomic active-alias activation. Later tasks own generation inspection and
deletion.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

import httpx
from qdrant_client import QdrantClient
from qdrant_client.common.client_exceptions import ResourceExhaustedResponse
from qdrant_client.http import models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.rag.vector_storage.contracts import (
    VECTOR_DIMENSION,
    CollectionInfo,
    ACTIVE_GENERATION_ALIAS,
    ActivateGenerationRequest,
    CreateGenerationRequest,
    GenerationActivationResult,
    GenerationVerificationResult,
    UpsertPointsRequest,
    UpsertPointsResult,
    VerifyGenerationRequest,
)
from app.rag.vector_storage.exceptions import (
    VectorGenerationActivationFailed,
    VectorGenerationBuildFailed,
    VectorStoreConfigurationError,
    VectorStoreError,
    VectorStoreInvalidData,
    VectorStoreServiceError,
    VectorStoreTimeout,
    VectorStoreTransientServiceError,
    VectorStoreUnavailable,
)
from app.rag.vector_storage.retry import QdrantRetryPolicy

DEFAULT_QDRANT_TIMEOUT_SECONDS = 10.0

T = TypeVar("T")

__all__ = [
    "DEFAULT_QDRANT_TIMEOUT_SECONDS",
    "QdrantClientAdapter",
    "QdrantClientConfig",
    "build_qdrant_client",
    "execute_with_retry",
    "normalize_qdrant_error",
]


@dataclass(frozen=True)
class QdrantClientConfig:
    """Explicit Qdrant connection configuration.

    The URL, optional API key, and timeout are supplied by the caller. No
    environment variable or global settings object is read here; composition
    belongs to the application wiring task.
    """

    url: str
    api_key: str | None = field(default=None, repr=False)
    timeout: float = DEFAULT_QDRANT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if not isinstance(self.url, str) or not self.url.strip():
            raise ValueError("url must be a non-empty string")

        if self.api_key is not None:
            if not isinstance(self.api_key, str) or not self.api_key.strip():
                raise ValueError("api_key must be a non-empty string when provided")

        if isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float)):
            raise ValueError("timeout must be a positive number")
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("timeout must be positive and finite")

        object.__setattr__(self, "timeout", float(self.timeout))


def build_qdrant_client(
    config: QdrantClientConfig,
    *,
    client_factory: Callable[..., Any] = QdrantClient,
) -> Any:
    """Construct a Qdrant client without performing network I/O.

    ``check_compatibility=False`` is intentional: the SDK otherwise starts a
    background compatibility request during construction, which would violate
    the approved requirement that application startup performs no Qdrant
    network I/O.
    """

    if not isinstance(config, QdrantClientConfig):
        raise TypeError("config must be a QdrantClientConfig")

    try:
        return client_factory(
            url=config.url,
            api_key=config.api_key,
            timeout=config.timeout,
            check_compatibility=False,
        )
    except VectorStoreError:
        raise
    except Exception as exc:
        raise VectorStoreConfigurationError(
            "unable to construct Qdrant client", cause=exc
        ) from exc


def _is_timeout(exc: BaseException) -> bool:
    return isinstance(exc, httpx.TimeoutException)


def _is_connection_failure(exc: BaseException) -> bool:
    return isinstance(exc, httpx.ConnectError)


def _error_for_status(
    status_code: object, cause: Exception
) -> VectorStoreError:
    if isinstance(status_code, int) and not isinstance(status_code, bool):
        if 500 <= status_code <= 599:
            return VectorStoreTransientServiceError(
                "Qdrant service error", cause=cause
            )
        if status_code in (400, 422):
            return VectorStoreInvalidData(
                "invalid Qdrant vector or payload data", cause=cause
            )
        if status_code in (401, 403):
            return VectorStoreConfigurationError(
                "invalid Qdrant endpoint configuration or credentials", cause=cause
            )

    # Includes HTTP 429, other 4xx responses, and unknown status values. The
    # rate-limit path is explicitly not retried in V1.
    return VectorStoreServiceError("Qdrant request failed", cause=cause)


def normalize_qdrant_error(exc: Exception) -> VectorStoreError:
    """Translate a Qdrant/HTTPX/unknown exception into the application taxonomy.

    The original exception is retained as the internal ``__cause__`` for
    diagnostics. Error messages are fixed strings; raw response bodies, reason
    phrases, URLs, and credentials are never copied into them.
    """

    if isinstance(exc, VectorStoreError):
        return exc

    if isinstance(exc, UnexpectedResponse):
        return _error_for_status(exc.status_code, exc)

    if isinstance(exc, ResourceExhaustedResponse):
        # The SDK raises this for a 429 that carries ``Retry-After``. V1 does
        # not honor ``Retry-After`` and never retries a rate-limit response.
        return VectorStoreServiceError("Qdrant rate limit response", cause=exc)

    if isinstance(exc, ResponseHandlingException):
        source = exc.source
        if _is_timeout(source):
            return VectorStoreTimeout("Qdrant request timed out", cause=exc)
        if _is_connection_failure(source):
            return VectorStoreUnavailable("Qdrant connection failed", cause=exc)
        # A wrapper is not automatically a transport failure. Response
        # parsing/validation failures and unrecognized sources are permanent
        # application-level failures.
        return VectorStoreServiceError("Qdrant response handling failed", cause=exc)

    if _is_timeout(exc):
        return VectorStoreTimeout("Qdrant request timed out", cause=exc)
    if _is_connection_failure(exc):
        return VectorStoreUnavailable("Qdrant connection failed", cause=exc)
    return VectorStoreServiceError("Qdrant request failed", cause=exc)


def execute_with_retry(
    operation: Callable[[], T],
    *,
    policy: QdrantRetryPolicy | None = None,
    sleep: Callable[[float], None] | None = None,
) -> T:
    """Run one storage operation with bounded transient-only retries.

    The operation may raise an application-owned ``VectorStoreError`` or a raw
    exception from the Qdrant/HTTPX boundary. Non-retryable failures and HTTP
    429 fail immediately. Eligible failures receive at most
    ``policy.max_attempts`` total attempts.
    """

    effective_policy = policy or QdrantRetryPolicy()
    sleep_fn = time.sleep if sleep is None else sleep

    for attempt_index in range(effective_policy.max_attempts):
        try:
            return operation()
        except Exception as exc:
            error = normalize_qdrant_error(exc)
            if not error.retryable or attempt_index + 1 >= effective_policy.max_attempts:
                raise error
            sleep_fn(effective_policy.delay_for_attempt(attempt_index))

    # ``max_attempts`` is validated as at least one, so this is unreachable.
    raise AssertionError("retry loop exhausted without a result")


_PAYLOAD_INDEXES = (
    ("generation_id", models.PayloadSchemaType.KEYWORD),
    ("document_id", models.PayloadSchemaType.KEYWORD),
    ("source_path", models.PayloadSchemaType.KEYWORD),
    ("format", models.PayloadSchemaType.KEYWORD),
    ("chunking_config_id", models.PayloadSchemaType.KEYWORD),
    ("embedding_config_id", models.PayloadSchemaType.KEYWORD),
    ("chunk_index", models.PayloadSchemaType.INTEGER),
)


class QdrantClientAdapter:
    """Owns a Qdrant client and executes SDK calls at the application boundary.

    Application-owned DTOs enter and leave this adapter; Qdrant SDK models and
    exceptions remain private to this module. Construction performs no network
    I/O. Each remote operation is executed through the normalized retry policy.
    """

    def __init__(
        self,
        client: Any,
        *,
        retry_policy: QdrantRetryPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._client = client
        self._retry_policy = retry_policy or QdrantRetryPolicy()
        self._sleep = sleep
        # Verification is an explicit lifecycle precondition. It is invalidated
        # whenever this adapter writes to the generation.
        self._verified_generations: dict[str, int] = {}

    @classmethod
    def from_config(
        cls,
        config: QdrantClientConfig,
        *,
        client_factory: Callable[..., Any] = QdrantClient,
        retry_policy: QdrantRetryPolicy | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> "QdrantClientAdapter":
        client = build_qdrant_client(config, client_factory=client_factory)
        return cls(client, retry_policy=retry_policy, sleep=sleep)

    def _execute(self, operation: Callable[[Any], T]) -> T:
        """Execute an SDK operation through the normalized retry boundary."""

        return execute_with_retry(
            lambda: operation(self._client),
            policy=self._retry_policy,
            sleep=self._sleep,
        )

    def create_generation(self, request: CreateGenerationRequest) -> CollectionInfo:
        """Create one immutable generation collection and its exact payload indexes."""

        if not isinstance(request, CreateGenerationRequest):
            raise TypeError("request must be a CreateGenerationRequest")

        collection_name = f"knowledge_vectors_g_{request.generation_id}"
        self._verified_generations.pop(request.generation_id, None)
        try:
            created = self._execute(
                lambda client: client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=VECTOR_DIMENSION,
                        distance=models.Distance.COSINE,
                    ),
                )
            )
            if created is not True:
                raise VectorGenerationBuildFailed(
                    "Qdrant did not confirm generation collection creation"
                )

            for field_name, field_schema in _PAYLOAD_INDEXES:
                index_result = self._execute(
                    lambda client, name=field_name, schema=field_schema: (
                        client.create_payload_index(
                            collection_name=collection_name,
                            field_name=name,
                            field_schema=schema,
                            wait=True,
                        )
                    )
                )
                if (
                    getattr(index_result, "status", None)
                    is not models.UpdateStatus.COMPLETED
                ):
                    raise VectorGenerationBuildFailed(
                        "Qdrant did not confirm a generation payload index"
                    )
        except VectorGenerationBuildFailed:
            raise
        except Exception as exc:
            cause = normalize_qdrant_error(exc)
            raise VectorGenerationBuildFailed(
                "unable to create the vector generation", cause=cause
            ) from cause

        return CollectionInfo(
            generation_id=request.generation_id,
            collection_name=collection_name,
            vector_size=VECTOR_DIMENSION,
            distance="Cosine",
        )

    def upsert_points(self, request: UpsertPointsRequest) -> UpsertPointsResult:
        """Upsert one validated, ordered batch and require confirmed completion."""

        if not isinstance(request, UpsertPointsRequest):
            raise TypeError("request must be an UpsertPointsRequest")

        collection_name = f"knowledge_vectors_g_{request.generation_id}"
        self._verified_generations.pop(request.generation_id, None)
        qdrant_points = []
        for point in request.points:
            payload = dict(point.payload)
            payload["generation_id"] = request.generation_id
            qdrant_points.append(
                models.PointStruct(
                    id=str(point.point_id),
                    vector=list(point.vector),
                    payload=payload,
                )
            )

        try:
            result = self._execute(
                lambda client: client.upsert(
                    collection_name=collection_name,
                    points=qdrant_points,
                    wait=True,
                )
            )
            if getattr(result, "status", None) is not models.UpdateStatus.COMPLETED:
                raise VectorGenerationBuildFailed(
                    "Qdrant did not confirm completion of the complete upsert batch"
                )
        except VectorGenerationBuildFailed:
            raise
        except Exception as exc:
            cause = normalize_qdrant_error(exc)
            raise VectorGenerationBuildFailed(
                "unable to upsert the complete vector generation batch", cause=cause
            ) from cause

        return UpsertPointsResult(
            generation_id=request.generation_id,
            submitted_count=len(request.points),
            completed_count=len(request.points),
            succeeded=True,
        )


    def verify_generation(
        self, request: VerifyGenerationRequest
    ) -> GenerationVerificationResult:
        """Verify the complete stored generation against its approved schema."""

        if not isinstance(request, VerifyGenerationRequest):
            raise TypeError("request must be a VerifyGenerationRequest")

        collection_name = f"knowledge_vectors_g_{request.generation_id}"
        try:
            collection = self._execute(
                lambda client: client.get_collection(collection_name=collection_name)
            )
            params = getattr(getattr(collection, "config", None), "params", None)
            vectors = getattr(params, "vectors", None)
            # V1 uses one unnamed dense vector. Named/multi-vector configurations
            # are deliberately rejected rather than guessed or coerced.
            if not isinstance(vectors, models.VectorParams):
                raise ValueError(
                    "generation vector configuration is not a single dense vector"
                )
            vector_size = getattr(vectors, "size", None)
            distance = getattr(vectors, "distance", None)
            if isinstance(vector_size, bool) or vector_size != VECTOR_DIMENSION:
                raise ValueError("generation vector dimension does not match V1")
            if distance is not models.Distance.COSINE:
                raise ValueError("generation distance does not match Cosine")
            # CollectionInfo.points_count is explicitly approximate in
            # qdrant-client. Use Count(exact=True) for the acceptance check.
            count_result = self._execute(
                lambda client: client.count(
                    collection_name=collection_name,
                    exact=True,
                )
            )
            actual_point_count = getattr(count_result, "count", None)
            if (
                isinstance(actual_point_count, bool)
                or not isinstance(actual_point_count, int)
                or actual_point_count < 0
            ):
                raise ValueError("Qdrant returned an invalid exact point count")
            if actual_point_count != request.expected_point_count:
                raise ValueError("generation point count does not match expected count")

            result = GenerationVerificationResult(
                generation_id=request.generation_id,
                expected_point_count=request.expected_point_count,
                actual_point_count=actual_point_count,
                vector_size=vector_size,
                distance="Cosine",
            )
        except Exception as exc:
            if isinstance(exc, VectorGenerationBuildFailed):
                raise
            cause = normalize_qdrant_error(exc)
            raise VectorGenerationBuildFailed(
                "vector generation verification failed", cause=cause
            ) from cause

        self._verified_generations[request.generation_id] = request.expected_point_count
        return result

    @staticmethod
    def _alias_targets(aliases_response: Any) -> dict[str, str]:
        """Translate Qdrant alias response into alias-name -> collection-name."""

        aliases = getattr(aliases_response, "aliases", None)
        if aliases is None:
            raise ValueError("Qdrant returned an invalid alias response")
        targets: dict[str, str] = {}
        for alias in aliases:
            alias_name = getattr(alias, "alias_name", None)
            collection_name = getattr(alias, "collection_name", None)
            if not isinstance(alias_name, str) or not isinstance(collection_name, str):
                raise ValueError("Qdrant returned an invalid alias entry")
            if alias_name in targets:
                raise ValueError("Qdrant returned duplicate alias entries")
            targets[alias_name] = collection_name
        return targets

    def activate_generation(
        self, request: ActivateGenerationRequest
    ) -> GenerationActivationResult:
        """Atomically move the active alias to a successfully verified generation."""

        if not isinstance(request, ActivateGenerationRequest):
            raise TypeError("request must be an ActivateGenerationRequest")
        generation_id = request.generation_id
        collection_name = f"knowledge_vectors_g_{generation_id}"
        expected_point_count = self._verified_generations.get(generation_id)
        if expected_point_count is None:
            raise VectorGenerationActivationFailed(
                "generation must pass verification before activation"
            )

        # Verification is a hard precondition, not part of alias-error
        # reconciliation. A failed verification must never be mistaken for an
        # already-active or ambiguously-activated successful generation.
        try:
            self.verify_generation(
                VerifyGenerationRequest(generation_id, expected_point_count)
            )
        except Exception as exc:
            cause = normalize_qdrant_error(exc)
            raise VectorGenerationActivationFailed(
                "generation did not pass verification before activation",
                cause=cause,
            ) from cause

        previous_collection: str | None = None
        previous_generation_id: str | None = None
        alias_update_attempted = False
        try:
            aliases_response = self._execute(lambda client: client.get_aliases())
            alias_targets = self._alias_targets(aliases_response)
            previous_collection = alias_targets.get(ACTIVE_GENERATION_ALIAS)
            if previous_collection is not None:
                prefix = "knowledge_vectors_g_"
                if not previous_collection.startswith(prefix):
                    raise ValueError(
                        "active alias points outside the generation namespace"
                    )
                candidate = previous_collection[len(prefix):]
                if len(candidate) != 64 or any(
                    ch not in "0123456789abcdef" for ch in candidate
                ):
                    raise ValueError(
                        "active alias points to an invalid generation collection"
                    )
                previous_generation_id = candidate

            if previous_collection == collection_name:
                return GenerationActivationResult(
                    generation_id=generation_id,
                    alias_name=ACTIVE_GENERATION_ALIAS,
                    previous_generation_id=generation_id,
                )

            operations = []
            if previous_collection is not None:
                operations.append(
                    models.DeleteAliasOperation(
                        delete_alias=models.DeleteAlias(
                            alias_name=ACTIVE_GENERATION_ALIAS
                        )
                    )
                )
            operations.append(
                models.CreateAliasOperation(
                    create_alias=models.CreateAlias(
                        collection_name=collection_name,
                        alias_name=ACTIVE_GENERATION_ALIAS,
                    )
                )
            )
            alias_update_attempted = True
            confirmed = self._execute(
                lambda client: client.update_collection_aliases(
                    change_aliases_operations=operations
                )
            )
            if confirmed is not True:
                raise RuntimeError("Qdrant did not confirm the atomic alias operation")

            return GenerationActivationResult(
                generation_id=generation_id,
                alias_name=ACTIVE_GENERATION_ALIAS,
                previous_generation_id=previous_generation_id,
            )
        except Exception as exc:
            cause = normalize_qdrant_error(exc)
            # A transport error can occur after Qdrant committed the atomic
            # operation but before the response reached this client. Reconcile
            # only after the alias update was attempted: target means confirmed
            # success; unchanged previous target means a clean failure.
            if alias_update_attempted:
                try:
                    reconciled = self._execute(lambda client: client.get_aliases())
                    reconciled_targets = self._alias_targets(reconciled)
                    current_target = reconciled_targets.get(ACTIVE_GENERATION_ALIAS)
                    if current_target == collection_name:
                        return GenerationActivationResult(
                            generation_id=generation_id,
                            alias_name=ACTIVE_GENERATION_ALIAS,
                            previous_generation_id=previous_generation_id,
                        )
                    if current_target != previous_collection:
                        cause = VectorStoreServiceError(
                            "Qdrant alias state could not be reconciled safely",
                            cause=cause,
                        )
                except Exception as reconcile_exc:
                    cause = normalize_qdrant_error(reconcile_exc)
            raise VectorGenerationActivationFailed(
                "unable to activate the verified vector generation", cause=cause
            ) from cause

    def close(self) -> None:
        try:
            self._client.close()
        except Exception as exc:
            raise normalize_qdrant_error(exc) from exc
