
---
name: next-task
description: Resume the AI Customer Support Backend project from its saved state, identify the next approved SDD task, and execute only that task without repeating completed audits.
compatibility: opencode
---

# Next Task — AI Customer Support Backend

## Objective

Resume the existing project from its saved state.
Do not restart project discovery or repeat completed work.

## Required startup sequence

1. Read `specs/project-state.md` first.
2. Read `specs/roadmap.md` only if needed to resolve the
   next phase or verify a dependency.
3. Run `git status --short` and `git log -1 --oneline`.
4. If the working tree has unexpected changes, inspect and
   report them before modifying anything.
5. Use the saved findings and references from the previous
   session. Do not reread all project files.
6. Read only the specification, implementation, and tests
   relevant to the current task.
7. Inspect additional files only when a concrete dependency,
   contradiction, or missing acceptance criterion requires it.

## Source of truth

Priority order:

1. Approved specifications under `specs/`
2. Explicitly approved task and acceptance criteria
3. Verified implementation and test results
4. `specs/project-state.md` as a continuity index

The state file never overrides an approved specification.

Never invent requirements, architecture, or completed work.

## Task selection

- Resume an unfinished task if it remains valid.
- Otherwise select the next dependency-ready task from the
  approved roadmap and task breakdown.
- Do not silently approve a proposed task or specification.
- If the next task is ambiguous, explain the ambiguity and
  ask one focused question.
- Work on exactly ONE task per session.

## SDD workflow

Specification
→ Architecture/Contract
→ Task scope and acceptance criteria
→ Implementation
→ Tests
→ Verification
→ Commit
→ STOP

If the specification is missing or unapproved, do not
implement the feature. Define or revise the specification
first and request approval.

## Verification

Run the focused tests, then the required regression tests.
Review the diff and check for unintended changes.
Never claim a test or commit succeeded without evidence.

Do not commit unrelated user changes.

## Session closure

After the task is verified and committed:

1. Update `specs/project-state.md`.
2. Record the task ID, outcome, commit, tests, and remaining work.
3. Identify exactly one next task.
4. STOP. Do not start that next task automatically.

If the task cannot be completed, record its actual status,
evidence, blockers, and precise next action.

## Project constraints

- Phase 3 must be verified complete before starting RAG.
- Ollama remains supported for local development.
- The backend remains the authority for business decisions.
- Preserve the existing architecture unless an approved
  specification explicitly requires a change.
- Keep each session small, reviewable, and suitable for
  approximately 40 minutes of focused work.
