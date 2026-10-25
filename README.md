# AI Customer Support Backend

**An AI-native customer support backend where the LLM interprets and proposes — deterministic backend services decide.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Qdrant](https://img.shields.io/badge/Qdrant-vector%20search-DC244C)](https://qdrant.tech/)
[![Ollama](https://img.shields.io/badge/Ollama-local%20inference-000000)](https://ollama.com/)
[![Tests](https://img.shields.io/badge/tests-800%2B-brightgreen)](#testing)
[![Status](https://img.shields.io/badge/status-active%20development-yellow)](#project-status)

## Overview

AI Customer Support Backend is a production-oriented backend that explores a practical question: **how much of customer support can a language model handle without letting it become an unchecked authority over business data?**

The intended flow is straightforward: the model reads natural-language requests, classifies intent, retrieves policy knowledge, and proposes actions. Authorization, refund eligibility, financial limits, order state, and data integrity remain in deterministic domain services and database constraints. The LLM is useful without being trusted.

The project is built in the open as a demonstration of production AI engineering: provider abstraction, strict structured outputs, a pinned and testable RAG pipeline, explicit trust boundaries, and a specification-driven development process.

## Design Principle

> **The LLM proposes. The backend decides.**

| The LLM may | The LLM may never |
| --- | --- |
| Understand customer intent | Approve or reject a refund |
| Retrieve and summarize policy knowledge | Modify order or refund state |
| Propose a backend action | Bypass authorization or business rules |
| Generate a customer-facing response | Treat generated text as authoritative business data |

Business rules do not live in prompts. They live in code and are enforced inside database transactions.

## Project Status

This repository is under active development. The table below distinguishes what is implemented and verified from what is designed but not yet built.

| Area | Capability | Status |
| --- | --- | --- |
| Foundation | Typed configuration, FastAPI app, health check, Docker Compose, Alembic migrations | ✅ Implemented |
| Domain | Customer, Order, and Refund persistence; refund authorization rules; row-level locking | ✅ Implemented |
| LLM | Provider abstraction, Ollama adapter, structured outputs, prompt registry, retries, token/cost tracking | ✅ Implemented |
| RAG | Knowledge document ingestion, token-aware chunking, batched embeddings | ✅ Implemented |
| RAG | Qdrant storage, semantic retrieval, metadata filtering, context construction, source attribution | ⏳ Planned |
| Tools | Order lookup, customer lookup, policy search, tool authorization and logging | ⏳ Planned |
| Agent | Agent loop, tool selection, stop conditions, guardrails, evaluation | ⏳ Planned |
| Workflow | End-to-end support workflows (order status, cancellations, refunds, policy questions) | ⏳ Planned |
| Hardening | Structured logging, correlation IDs, metrics, rate limiting, idempotency | ⏳ Planned |
| Providers | OpenAI adapter, provider comparison, cost comparison | ⏳ Planned |

## Architecture

The target architecture is layered, with a visible trust boundary between AI-assisted components and deterministic business enforcement.

```mermaid
flowchart LR
    Client([Client]) --> API["FastAPI API"]

    API --> App["Application / Orchestration"]

    subgraph AI["AI-assisted"]
        LLM["LLM Service<br/>structured output · retries · cost"]
        RAG["RAG Pipeline<br/>ingestion · chunking · embeddings"]
    end

    subgraph TRUST["Deterministic trust boundary"]
        Domain["Domain Services<br/>business rules · authorization"]
        DB[("PostgreSQL<br/>system of record")]
    end

    App --> LLM
    App --> RAG
    App --> Domain

    LLM --> Ollama["Ollama<br/>(future: OpenAI)"]
    RAG --> Ollama
    RAG -.->|planned| Qdrant[("Qdrant")]

    Domain --> DB

    classDef ai fill:#eef6ff,stroke:#4a90d9,color:#1a1a1a
    classDef trust fill:#eefaf0,stroke:#2e8b57,color:#1a1a1a
    class LLM,RAG,Ollama ai
    class Domain,DB trust
```

**Implemented today:** the API, PostgreSQL domain model and refund rules, the provider-agnostic LLM service, and the ingestion → chunking → embeddings pipeline. The application/orchestration layer, Qdrant retrieval, tools, and the agent are the next milestones; the diagram shows the intended end state.

### Layers

| Layer | Responsibility |
| --- | --- |
| API | HTTP boundary, request validation, health and readiness |
| Application | Orchestration of LLM, RAG, tools, and domain services |
| Domain | Entities, business rules, authorization and financial decisions |
| LLM | Provider-agnostic completions, structured outputs, prompts, retries, cost |
| RAG | Document ingestion, chunking, embeddings, retrieval |
| Infrastructure | SQLAlchemy sessions, Alembic migrations, centralized settings |

### Target request lifecycle

1. A customer message arrives at the API.
2. The LLM service produces a strict, schema-validated intent analysis.
3. Relevant policy passages are retrieved with source attribution.
4. The model may *request* a backend action through a tool; it cannot execute one itself.
5. Domain services authorize and apply the change under database constraints.
6. The response is composed from authoritative backend data, not from generated assertions.

Steps 3–6 are the target design; today only the intent-analysis and domain primitives exist.

## Engineering Highlights

- **Provider independence.** Application code depends on an `LLMProvider` contract, never on a specific vendor. Provider-specific HTTP semantics stay inside the adapter, and provider errors are normalized at the service boundary.
- **Deterministic refund authorization.** `RefundService` enforces positive amounts, order limits, cumulative refund limits, and a 30-day refund window. `SELECT … FOR UPDATE` locks the order row so concurrent requests cannot overdraw the refundable amount.
- **Strict structured output.** Pydantic models use `strict=True` and `extra="forbid"`; the analysis schema covers 9 support categories and 3 priorities. Parse failures and schema violations are distinct error types, and no type coercion is allowed.
- **Pinned RAG inputs.** Chunking uses a vendored `tokenizer.json` whose identity includes the library version, model revision, and SHA-256 of the asset. A 500-token chunk with 75-token overlap plus the document prefix stays within the model's 2048-token limit.
- **Resilient integrations.** LLM and embedding calls use bounded retries with exponential backoff, per-attempt timeouts, injectable sleep for deterministic tests, and stable failure reasons. A failed embedding batch invalidates the whole run — no partial results.
- **Cost visibility.** Token usage and configurable per-model pricing are captured per LLM request, so cost can be measured rather than estimated.
- **Explicit composition roots.** Services are constructed once at application startup from typed settings and exposed through application state. Configuration is centralized; services do not read the environment.
- **Specification-driven development.** Every subsystem has an approved specification and task breakdown in [`specs/`](specs/) before implementation. The loop is specification → architecture → task → implementation → test → verification.
- **Test depth.** 800+ tests across unit, integration, Docker, and opt-in live-provider conformance suites. The last recorded full regression run was **815 passed, 7 skipped**.

## Repository Layout

```text
.
├── src/app/
│   ├── core/                 # Typed settings and application configuration
│   ├── domain/               # Entities, exceptions, refund business rules
│   ├── llm/                  # Provider abstraction, prompts, structured output,
│   │                         # retries, cost tracking, Ollama adapter
│   ├── rag/
│   │   ├── ingestion/        # Discovery, loading, validation, metadata
│   │   ├── chunking/         # Tokenizer adapter, boundary selection, service
│   │   └── embeddings/       # Contracts, batching, retries, Ollama adapter
│   ├── infrastructure/       # Database engine and session management
│   └── main.py               # FastAPI application and composition root
├── tests/                    # Unit, integration, and conformance tests
├── specs/                    # Approved specifications and project state
├── migrations/               # Alembic migration history
├── assets/tokenizers/        # Pinned tokenizer asset for chunking
├── docker-compose.yml        # API, PostgreSQL, and Qdrant
└── Dockerfile
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- [Ollama](https://ollama.com/) for local LLM inference (required for live LLM and embedding features)
- Python 3.12 (only for the non-Docker workflow)

### 1. Clone and configure

```bash
git clone https://github.com/omarmm/ai-customer-support.git
cd ai-customer-support
cp .env.example .env
```

Required values in `.env` for the Docker Compose network:

```dotenv
APP_ENV=local
APP_NAME=AI Customer Support Backend

DATABASE_URL=postgresql+psycopg://ai_support:ai_support_dev@postgres:5432/ai_support
QDRANT_URL=http://qdrant:6333
OLLAMA_URL=http://host.docker.internal:11434
LLM_PROVIDER=ollama
```

Configuration is validated at startup, so missing or malformed values fail fast. The remaining settings in `.env.example` have safe defaults.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL DSN; the system of record |
| `QDRANT_URL` | Qdrant endpoint (reserved for the retrieval milestone) |
| `OLLAMA_URL` | Ollama endpoint used by the embedding pipeline |
| `OLLAMA_BASE_URL` | Ollama endpoint used by the chat adapter; set automatically by Compose |
| `LLM_PROVIDER` | Active LLM provider identifier |

### 2. Start the stack

```bash
docker compose up -d postgres qdrant
docker compose run --rm api alembic upgrade head
docker compose up api
```

Verify the service:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### 3. Pull the local models

```bash
ollama pull qwen3:8b                # chat model used by the LLM integration test
ollama pull nomic-embed-text:v1.5   # embedding model pinned by the RAG pipeline
```

### Run without Docker

Use the same `.env` with host-reachable endpoints (`localhost` instead of `postgres`, `qdrant`, and `host.docker.internal`), then:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export PYTHONPATH=src
alembic upgrade head
uvicorn app.main:app --reload
```

## Testing

The suite is split by dependency so most of it runs offline.

```bash
# Full suite (requires PostgreSQL for domain tests)
PYTHONPATH=src pytest tests -q

# Offline suites: LLM and RAG boundaries, no database or network required
PYTHONPATH=src pytest tests/llm tests/rag -q

# Containerized full suite
docker compose run --rm api python -m pytest tests -q

# Opt-in live conformance against a running Ollama instance
RUN_LIVE_OLLAMA=1 PYTHONPATH=src pytest \
  tests/llm/test_ollama_integration.py \
  tests/rag/embeddings/test_ollama_conformance.py -q
```

Live conformance tests are skipped by default so the suite stays deterministic and offline-safe. The embedding tests validate the served model identity, the measured vector dimension, and the finiteness of every returned value.

## Specification-Driven Development

This project is developed specification-first. A subsystem is not implemented until its contract, boundaries, failure modes, and acceptance criteria are written down and approved. That process is visible in the repository:

| Document | Description |
| --- | --- |
| [`specs/mission.md`](specs/mission.md) | Problem, goals, scope, non-goals, core principle |
| [`specs/tech-stack.md`](specs/tech-stack.md) | Runtime, data, AI, architecture, testing, infrastructure decisions |
| [`specs/roadmap.md`](specs/roadmap.md) | Ten-phase delivery roadmap |
| [`specs/project-state.md`](specs/project-state.md) | Current phase, completed tasks, verified findings, decisions |
| [`specs/domain/business-rules.md`](specs/domain/business-rules.md) | Refund authorization rules and the AI boundary |
| [`specs/llm/`](specs/llm/) | LLM service, structured output, prompts, errors, retries, cost |
| [`specs/rag/`](specs/rag/) | Ingestion, chunking, embeddings, tokenizer decision |
| [`specs/system/`](specs/system/) | Configuration and database specifications |

## Roadmap

| Phase | Focus | Status |
| --- | --- | --- |
| 1 | Foundation — project structure, configuration, PostgreSQL, Docker, tests | ✅ Complete |
| 2 | Domain and business backend — orders, refunds, authorization | ✅ Complete |
| 3 | LLM service — provider abstraction, structured output, retries, cost | ✅ Complete |
| 4 | RAG — ingestion, chunking, embeddings, retrieval, evaluation | 🚧 In progress |
| 5 | Tools — lookup, validation, authorization, execution logging | ⏳ Planned |
| 6 | Agent — state, loop, tool selection, guardrails, evaluation | ⏳ Planned |
| 7 | AI support workflow — LLM + RAG + tools + agent + business rules | ⏳ Planned |
| 8 | Production hardening — logging, metrics, rate limiting, idempotency | ⏳ Planned |
| 9 | External provider validation — OpenAI adapter, comparison, cost analysis | ⏳ Planned |
| 10 | Portfolio and open source — documentation, examples, evaluation results | 🚧 In progress |

## Non-Goals

- Letting the LLM directly modify business-critical state.
- Treating generated text as authoritative business data.
- Encoding business rules inside prompts.
- Coupling the architecture to a single LLM provider.
- Building the system as one fully autonomous agent.

## Author

**Omar** — [github.com/omarmm](https://github.com/omarmm)

## License

Released under the [MIT License](LICENSE).
