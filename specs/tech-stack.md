# AI Customer Support Backend — Tech Stack

## Runtime

- Python 3.x
- FastAPI
- Uvicorn

## AI / LLM

- LLM provider abstraction
- Ollama for local development
- OpenAI API as an external provider
- Structured Outputs
- Tool Calling

The application must not couple business logic directly to a specific LLM provider.

## Data

### Primary Database

- PostgreSQL
- SQLAlchemy
- Alembic

PostgreSQL is the source of truth for transactional and business data.

### Vector Database

- Qdrant

Qdrant is used for semantic retrieval and RAG-related data.

Vector storage must not replace the transactional database.

## RAG

The RAG subsystem will contain explicit boundaries for:

- Document ingestion
- Chunking
- Embedding generation
- Vector storage
- Retrieval
- Context construction
- Source attribution
- Evaluation

## Architecture

The application will use clear separation between:

- API layer
- Application layer
- Domain layer
- Infrastructure layer

Business rules must remain independent from:

- LLM providers
- Vector databases
- HTTP frameworks
- External APIs

## Testing

- Pytest
- Unit tests
- Integration tests
- End-to-end tests
- AI evaluation tests

## Infrastructure

- Docker
- Docker Compose

Local development should be reproducible using containerized infrastructure where practical.

## Observability

The system must provide structured observability for:

- Request IDs
- LLM requests
- LLM latency
- Token usage
- Tool execution
- Retrieval
- Errors
- Business decisions

## Development Environment

The primary development environment is Linux / Ubuntu-based.

The initial implementation must support fully local development without requiring paid external services.

## Cost Strategy

The project will initially use:

- Ollama for local LLM inference
- Local PostgreSQL
- Local Qdrant
- Local testing and observability

External paid AI providers will be introduced later for provider comparison and production-oriented validation.

## Architecture Principles

1. Provider independence
2. Deterministic business rules
3. Explicit boundaries
4. Testability
5. Observability
6. Security by default
7. Specification-driven development
8. Local-first development

## Local Infrastructure Isolation

Infrastructure services are project-scoped.

Each project must define its own container configuration, Docker network, and persistent volumes.

PostgreSQL and Qdrant must not be installed as host-level services for this project.

Application containers communicate with infrastructure services through the Docker Compose network using service names.

Host port mappings are provided only when external access from the development machine is required.

Persistent data must use named Docker volumes scoped to this project.

The project must be reproducible on another machine with:

docker compose up
