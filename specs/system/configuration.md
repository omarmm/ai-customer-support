# Configuration Specification

## Purpose

Define a centralized and environment-based configuration system for the application.

## Requirements

The application must:

- Load configuration from environment variables.
- Provide typed configuration values.
- Avoid hardcoded secrets in application source code.
- Support local development and future production environments.
- Fail clearly when required configuration is missing.
- Keep configuration access centralized.

## Configuration

The initial configuration must include:

- `APP_ENV`
- `APP_NAME`
- `DATABASE_URL`
- `QDRANT_URL`
- `OLLAMA_URL`
- `LLM_PROVIDER`

## Environments

The system must support:

- Local development
- Test
- Production

Environment-specific values must not require changes to application source code.

## Security

Secrets must not be committed to Git.

A `.env.example` file must document required variables without containing real secrets.

## Architecture

Application components must obtain configuration through a centralized configuration object.

Business logic must not directly read environment variables.

## Validation

Application startup must validate required configuration.

Invalid or missing required configuration must produce a clear startup error.
