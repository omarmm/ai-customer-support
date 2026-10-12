# AI Customer Support Backend — Project State

## Current Position
- Current Day: 25
- Current Phase: Phase 3 — LLM Service
- Day 24: Completed and closed
- Day 25: In progress — Phase 3 completion review
- RAG: Blocked until Phase 3 is verified complete

## Last Completed Task
- Task: T251 — LLM Error Handling Specification
- Artifact: specs/llm/error-handling.md (Status: Approved)
- Source/tests modified: none (specification-only task)
- Commit: not yet committed (docs change pending)
- Git working tree: specs/llm/error-handling.md added; specs/project-state.md updated

## Current Task
- ID: T252
- Title: Error Normalization Implementation
- Status: Ready to start; specification approved at specs/llm/error-handling.md
- Scope: implement the application-level error contract in
  `src/app/llm/exceptions.py` and normalization at the LLM Service boundary.
  Provider adapters own provider-specific classification via explicit provider
  exception types. Unclassified provider errors map to a generic non-retryable
  `LLMError`; unexpected internal/programming errors map to `LLMUnexpectedError`
  with the original cause preserved. No retries in this task.
- Depends on: T251 (complete)

## Next Task After T252
- ID: T253
- Title: Retry Implementation
- Status: Deferred; retry policy is defined in specs/llm/error-handling.md §6

## Verified Findings
- LLMService delegates directly to the configured provider (no normalization yet).
- OllamaProvider normalizes connection, timeout, HTTP, and response errors into
  the provider-level taxonomy (`LLMProvider*`).
- LLMRequest supports a configurable timeout; LLMUsage carries token counts.
- Latest LLM test run: 55 passed; full suite at Day 24 closure: 67 passed.
- T251 specification approved; provider-vs-application error layers are defined
  and separated, retry deferred to T253, normalization to T252.

## Open Questions
- Verify retry policy, cost tracking, and observability during Phase 3 review.
- Verify Phase 3 acceptance criteria against implementation and tests.
- Prompt Management specification still has Draft status.
- Token/cost accounting remains a separate Phase 3 item.

## Rules
- Specifications are the source of truth.
- Never start RAG before Phase 3 closure.
- Implement only one task per session.
- Do not repeat completed audits unless evidence is stale
  or a specific change requires re-verification.
- Update this file at every verified task closure.
