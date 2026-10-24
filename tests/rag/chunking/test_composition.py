"""Integration tests for the production chunking composition root (T266).

These tests exercise the actual production wiring: the composition factory, the
FastAPI startup hook that exposes the service through ``app.state``, and
end-to-end chunking of a real ``KnowledgeDocument`` with the approved tokenizer.
They do not replace the adapter-level conformance tests.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import socket
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.rag.chunking.composition import build_chunking_service
from app.rag.chunking.contracts import ALGORITHM_VERSION, compute_chunk_id
from app.rag.chunking.service import ChunkingService
from app.rag.ingestion.contracts import KnowledgeDocument

REPO_ROOT = Path(__file__).resolve().parents[3]
FORMAT = "markdown"
APPROVED_IDENTITY = (
    "tokenizers:0.23.3:nomic-ai/nomic-embed-text-v1.5"
    "@e9b6763023c676ca8431644204f50c2b100d9aab"
    ":d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66"
)
REQUIRED_ENV = {
    "APP_ENV": "test",
    "APP_NAME": "AI Customer Support Backend",
    "DATABASE_URL": "postgresql://test",
    "QDRANT_URL": "http://localhost:6333",
    "OLLAMA_URL": "http://localhost:11434",
    "LLM_PROVIDER": "ollama",
}


def make_settings(**overrides) -> Settings:
    values = dict(REQUIRED_ENV)
    values.update(overrides)
    return Settings(**values)


def make_document(content: str) -> KnowledgeDocument:
    return KnowledgeDocument(
        document_id=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        source_path="knowledge/support-policy.md",
        title="Support Policy",
        format=FORMAT,
        content=content,
        size_bytes=len(content.encode("utf-8")),
    )


# --- Factory -----------------------------------------------------------------


def test_factory_builds_the_service_with_the_approved_tokenizer() -> None:
    settings = make_settings(
        knowledge_chunk_max_tokens=21,
        knowledge_chunk_overlap_tokens=5,
    )

    service = build_chunking_service(settings)

    assert isinstance(service, ChunkingService)
    assert service.config.tokenizer_id == APPROVED_IDENTITY
    assert service.config.algorithm_version == ALGORITHM_VERSION
    assert service.config.max_tokens == 21
    assert service.config.overlap_tokens == 5
    assert service.config.max_tokens == settings.knowledge_chunk_max_tokens
    assert service.config.overlap_tokens == settings.knowledge_chunk_overlap_tokens


def test_factory_and_chunking_run_without_network(monkeypatch) -> None:
    def blocked(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)

    service = build_chunking_service(make_settings())
    result = service.chunk([make_document("Refunds take five business days.")])

    assert result.chunk_count > 0


# --- End-to-end chunking -----------------------------------------------------


def test_real_document_chunks_end_to_end() -> None:
    settings = make_settings(
        knowledge_chunk_max_tokens=12,
        knowledge_chunk_overlap_tokens=3,
    )
    content = (
        "Refunds are processed within 5-7 business days.\n\n"
        "Shipping usually takes 3-5 business days.\n\n"
        "Contact support if an item arrives damaged."
    )
    document = make_document(content)

    result = build_chunking_service(settings).chunk([document])

    assert result.config.max_tokens == 12
    assert result.config.overlap_tokens == 3
    assert result.document_count == 1

    chunking = result.documents[0]
    assert chunking.document_id == document.document_id
    assert chunking.source_path == document.source_path
    assert chunking.content_length == len(document.content)
    assert chunking.token_count > 0
    assert chunking.chunk_count > 1

    assert chunking.chunks[0].start_offset == 0
    assert chunking.chunks[-1].end_offset == len(document.content)
    assert chunking.chunks[0].token_start == 0
    assert chunking.chunks[-1].token_end == chunking.token_count

    previous = None
    for chunk in chunking.chunks:
        assert chunk.content == document.content[chunk.start_offset : chunk.end_offset]
        assert chunk.document_id == document.document_id
        assert chunk.source_path == document.source_path
        assert chunk.title == document.title
        assert chunk.format == document.format
        assert chunk.token_count <= result.config.max_tokens
        assert chunk.chunking_config_id == result.config.config_id
        assert chunk.chunk_id == compute_chunk_id(
            chunking_config_id=result.config.config_id,
            document_id=document.document_id,
            source_path=document.source_path,
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            content=chunk.content,
        )

        if previous is not None:
            assert chunk.chunk_index == previous.chunk_index + 1
            assert chunk.token_start > previous.token_start
            assert chunk.token_start <= previous.token_end
            assert chunk.start_offset > previous.start_offset
            assert chunk.start_offset <= previous.end_offset

        previous = chunk


# --- Application startup and import root ------------------------------------


def test_application_startup_exposes_the_composed_service(monkeypatch) -> None:
    for key, value in {
        **REQUIRED_ENV,
        "KNOWLEDGE_CHUNK_MAX_TOKENS": "13",
        "KNOWLEDGE_CHUNK_OVERLAP_TOKENS": "3",
    }.items():
        monkeypatch.setenv(key, value)

    get_settings.cache_clear()
    sys.modules.pop("app.main", None)
    main_module = importlib.import_module("app.main")

    with TestClient(main_module.app) as client:
        service = main_module.app.state.chunking_service

        assert isinstance(service, ChunkingService)
        assert service.config.tokenizer_id == APPROVED_IDENTITY
        assert service.config.max_tokens == 13
        assert service.config.overlap_tokens == 3
        assert client.get("/health").json() == {"status": "ok"}

        # The service is constructed once per process, not per request.
        client.get("/health")
        assert main_module.app.state.chunking_service is service

    assert not any(name == "src" or name.startswith("src.") for name in sys.modules)
    get_settings.cache_clear()


def test_source_uses_only_the_canonical_app_import_root() -> None:
    violations: list[str] = []

    for root in (REPO_ROOT / "src", REPO_ROOT / "tests", REPO_ROOT / "migrations"):
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module]
                else:
                    continue

                if any(
                    module == "src.app" or module.startswith("src.app.")
                    for module in modules
                ):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}:{node.lineno}"
                    )

    assert not violations
