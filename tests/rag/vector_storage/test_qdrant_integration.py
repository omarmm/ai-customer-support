"""Opt-in container-backed T278 lifecycle test against the configured Qdrant.

Run only when the project Qdrant container is healthy:
RUN_QDRANT_INTEGRATION=1 pytest tests/rag/vector_storage/test_qdrant_integration.py
"""

from __future__ import annotations

import hashlib
import os
import uuid

import pytest
from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.core.config import Settings
from app.rag.vector_storage.composition import build_vector_store
from app.rag.vector_storage.contracts import (
    VECTOR_DIMENSION,
    ActivateGenerationRequest,
    CreateGenerationRequest,
    DeleteGenerationRequest,
    GetGenerationInfoRequest,
    UpsertPointInput,
    UpsertPointsRequest,
    VerifyGenerationRequest,
)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_QDRANT_INTEGRATION") != "1",
    reason="requires the project's healthy Qdrant container",
)


def test_composed_store_completes_generation_lifecycle() -> None:
    settings = Settings(
        app_env="test",
        app_name="AI Customer Support Backend",
        database_url="postgresql://test",
        qdrant_url=os.environ["QDRANT_URL"],
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        ollama_url="http://localhost:11434",
        llm_provider="ollama",
    )
    store = build_vector_store(settings)
    client = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=10.0,
        check_compatibility=False,
    )

    suffix = uuid.uuid4().hex
    generation_a = hashlib.sha256(f"{suffix}:a".encode()).hexdigest()
    generation_b = hashlib.sha256(f"{suffix}:b".encode()).hexdigest()
    embedding_config_id = hashlib.sha256(b"t278-integration-embedding").hexdigest()

    def point(chunk_id: str) -> UpsertPointInput:
        return UpsertPointInput(
            chunk_id=chunk_id,
            vector=tuple([0.01] * VECTOR_DIMENSION),
            payload={
                "chunk_id": chunk_id,
                "document_id": f"doc-{suffix}",
                "source_path": "knowledge/t278-integration.md",
                "title": "T278 integration fixture",
                "format": "markdown",
                "content": "A disposable integration-test chunk.",
                "start_offset": 0,
                "end_offset": len("A disposable integration-test chunk."),
                "chunk_index": 0,
                "chunking_config_id": hashlib.sha256(b"t278-chunking").hexdigest(),
                "embedding_config_id": embedding_config_id,
            },
        )

    created: list[str] = []
    try:
        for generation_id, chunk_id in (
            (generation_a, f"{suffix}-chunk-a"),
            (generation_b, f"{suffix}-chunk-b"),
        ):
            info = store.create_generation(
                CreateGenerationRequest(
                    generation_id=generation_id,
                    embedding_config_id=embedding_config_id,
                    vector_size=VECTOR_DIMENSION,
                )
            )
            created.append(info.collection_name)
            result = store.upsert_points(
                UpsertPointsRequest(generation_id, [point(chunk_id)])
            )
            assert result.succeeded is True
            assert result.completed_count == 1
            verified = store.verify_generation(
                VerifyGenerationRequest(generation_id, expected_point_count=1)
            )
            assert verified.actual_point_count == 1

        first_activation = store.activate_generation(
            ActivateGenerationRequest(generation_a)
        )
        assert first_activation.generation_id == generation_a
        assert first_activation.previous_generation_id is None

        second_activation = store.activate_generation(
            ActivateGenerationRequest(generation_b)
        )
        assert second_activation.generation_id == generation_b
        assert second_activation.previous_generation_id == generation_a

        first_info = store.get_generation_info(
            GetGenerationInfoRequest(generation_a)
        )
        second_info = store.get_generation_info(
            GetGenerationInfoRequest(generation_b)
        )
        assert first_info.point_count == 1
        assert first_info.is_active is False
        assert second_info.point_count == 1
        assert second_info.is_active is True

        deleted = store.delete_generation(DeleteGenerationRequest(generation_a))
        assert deleted.deleted is True
        assert deleted.generation_id == generation_a
        created.remove(f"knowledge_vectors_g_{generation_a}")
    finally:
        # Remove the test-owned alias before deleting the remaining disposable
        # generation. This cleanup is deliberately test-only and never runs in
        # application startup or production composition.
        try:
            aliases = client.get_aliases().aliases
            if any(
                alias.alias_name == "knowledge_vectors_active"
                and alias.collection_name in created
                for alias in aliases
            ):
                client.update_collection_aliases(
                    change_aliases_operations=[
                        models.DeleteAliasOperation(
                            delete_alias=models.DeleteAlias(
                                alias_name="knowledge_vectors_active"
                            )
                        )
                    ]
                )
            for collection_name in created:
                if client.collection_exists(collection_name):
                    client.delete_collection(collection_name)
        finally:
            client.close()
