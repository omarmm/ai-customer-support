# Prompt Management Specification

**Status:** Approved
**Feature:** Prompt Management
**Phase:** LLM Service

**Decision log:**
- Path-traversal hardening (reject absolute paths and `..`; enforce
  resolved-path containment under `src/app/llm/prompts/`) maps to the
  existing `InvalidPromptTemplateError`. This is consistent with §4
  template storage and §7 invalid-template/rendering-failure contract;
  it introduces no new error type and expands no feature scope.

## 1. Purpose

Define a consistent and testable mechanism for managing prompt templates independently from LLM provider implementations and application business logic.

## 2. Responsibilities

The Prompt Management component is responsible for:

- Storing and organizing prompt templates.
- Defining required variables for each template.
- Rendering templates using validated input variables.
- Rejecting missing or invalid variables.
- Providing deterministic rendering behavior.
- Making prompt templates easy to test and maintain.

## 3. Architecture

The component integrates with the existing LLM Service.

Application / Use Case → Prompt Management → LLM Service → LLM Provider

- Prompt Management must be independent of LLM providers.
- Prompt Management must not make network calls.
- LLMService remains responsible for interacting with providers.
- Business rules remain outside Prompt Management.
- Existing LLM provider and structured-output behavior must remain unchanged.

## 4. Template Management

### 4.1 Template Storage

- Prompt templates must be stored as separate files under `src/app/llm/prompts/`.
- Each template must have a stable identifier.
- Templates must use Python's standard-library `string.Template`.
- Template files must contain prompt content only.
- Prompt content must be separated from application service logic.
- Template selection must be deterministic.
- Template content must be maintainable without modifying provider implementations.

### 4.2 Template Variables

- Each template must explicitly define its required variables.
- Required variables must be validated before rendering.
- Unexpected variables must be rejected.
- Rendering must use strict substitution.
- Partial rendering is not allowed.

## 5. Variables and Validation

- Missing required variables must produce a predictable error.
- Variable values must be rendered without accidental template substitution.
- Invalid inputs must not result in partially rendered prompts.
- Empty values are allowed unless explicitly prohibited by a template-specific requirement.
- Invalid template syntax must produce a predictable error.
- Validation must complete before rendering begins.
- Unexpected variables must be rejected consistently.
- Variable validation must not execute arbitrary code.

## 6. Rendering

- Rendering must be deterministic for the same template and inputs.
- Rendering must not make network calls.
- Rendering must not execute arbitrary code.
- Rendering must not modify the original template.
- Rendering must return the complete rendered prompt or raise a defined error.
- Rendering must not silently ignore missing variables.

## 7. Error Handling

The component must distinguish between:

- Unknown template identifiers.
- Missing required variables.
- Unexpected variables.
- Invalid variable values.
- Invalid template syntax.
- Template rendering failures.

Errors must be predictable and testable.

Error messages must not expose sensitive prompt inputs unnecessarily.

## 8. Security

- Template variables must be treated as untrusted input.
- Rendering must not be treated as a prompt-injection defense.
- Prompt injection mitigation remains a separate responsibility.
- Secrets and credentials must not be embedded in prompt templates.
- Template rendering must not evaluate input values as executable code.
- Sensitive customer data must not be unnecessarily exposed in logs or exceptions.

## 9. Testing Requirements

Automated unit tests must cover:

- Successful rendering.
- Rendering templates with multiple variables.
- Missing required variables.
- Unexpected variables.
- Unknown template identifiers.
- Empty and invalid values.
- Invalid template syntax.
- Template content preservation.
- Deterministic output.
- No partial rendering on failure.
- Security-related rendering edge cases.

Tests must not require a live LLM provider or network access.

## 10. Acceptance Criteria

- Prompt templates are managed independently from application business logic.
- Every template has a stable identifier and explicitly defined variables.
- Missing and unexpected variables are rejected.
- Invalid rendering requests fail predictably.
- Rendering is deterministic and does not require network access.
- The original template remains unchanged after rendering.
- The component has automated unit tests covering success and failure scenarios.
- Existing LLM provider and structured-output behavior remains unchanged.
- The implementation follows this specification without introducing unnecessary dependencies.

## 11. Out of Scope

- Prompt optimization and automatic prompt rewriting.
- A/B testing and experimentation platforms.
- External prompt-management services.
- Changes to LLM provider implementations.
- Changes to structured-output behavior.
- RAG and agent orchestration.
- Prompt-injection detection and mitigation mechanisms.
- Runtime prompt editing or database-backed prompt storage.
