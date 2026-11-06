---
name: next-task
description: Resume the AI Customer Support Backend project from its saved SDD state, verify assistant-prepared implementation handoffs when present, otherwise execute exactly one approved task.
compatibility: opencode
---

# Next Task — AI Customer Support Backend

## Objective

Resume the existing project from its saved state. Do not restart project discovery or repeat completed work.

The project uses a two-stage implementation workflow:
- The project assistant prepares and pushes the scoped implementation to a dedicated branch and records a handoff in `specs/project-state.md`.
- OpenCode takes over that exact handoff to run local/runtime verification, fix implementation defects within the approved task scope, commit the verified result, and update project state.

OpenCode must not rewrite or recreate an implementation that is already prepared and identified by an active handoff.

## Required startup sequence

1. Read `specs/project-state.md` first.
2. Detect whether it contains an active **Implementation Handoff** with a task ID, branch, and PR/commit reference.
3. Run `git status --short` and `git log -1 --oneline`.
4. If the working tree has unexpected changes, inspect and report them before modifying anything.
5. For an active handoff:
   - Fetch the named remote branch.
   - Check out that exact branch, preserving any existing local work.
   - Confirm its HEAD contains the handoff commit and inspect the diff against the stated base branch.
   - Do not start a new task or create a replacement implementation.
6. Read `specs/roadmap.md` only if needed to resolve the next phase or verify a dependency.
7. Read only the specification, implementation, and tests relevant to the current task. Inspect additional files only when a concrete dependency, contradiction, or missing acceptance criterion requires it.

## Source of truth

Priority order:

1. Approved specifications under `specs/`
2. Explicitly approved task and acceptance criteria
3. Verified implementation and test results
4. `specs/project-state.md` as a continuity index

The state file never overrides an approved specification. Never invent requirements, architecture, or completed work.

## Task selection

- If an active implementation handoff exists, resume that exact task in **verification/finalization mode**.
- Otherwise resume an unfinished task if it remains valid; if not, select the next dependency-ready task from the approved roadmap and task breakdown.
- Do not silently approve a proposed task or specification.
- If the next task is ambiguous, explain the ambiguity and ask one focused question.
- Work on exactly ONE task per session.

## Handoff verification workflow

For an assistant-prepared implementation:

1. Confirm the branch and diff match the task scope and approved specification.
2. Inspect the implementation and tests; do not assume the handoff is correct merely because it exists.
3. Run focused tests, then required regression tests.
4. Run the task-specific runtime checks, including Docker Compose validation/build, container startup, health/readiness checks, or integration checks when required by the acceptance criteria.
5. Verify startup boundaries and negative requirements, not only happy paths.
6. Fix defects only within the approved task scope. If a specification ambiguity or out-of-scope dependency is discovered, stop and report it instead of inventing a solution.
7. Re-run affected tests and the required regression/runtime checks after fixes.
8. Review the final diff, secrets, configuration, and unintended changes.
9. Commit the verified changes on the same handoff branch. Do not merge the PR unless explicitly requested.

If runtime verification cannot be performed, do not mark the task complete. Record exact commands attempted, actual outputs, blockers, and the precise next action.

## Normal SDD workflow (when no handoff exists)

Specification
→ Architecture/Contract
→ Task scope and acceptance criteria
→ Approval
→ Implementation
→ Tests
→ Verification
→ Commit
→ STOP

If the specification is missing or unapproved, do not implement the feature. Define or revise the specification first and request approval.

## Verification rules

- Never claim a test, Docker build, healthcheck, or commit succeeded without actual evidence.
- Do not commit unrelated user changes.
- Keep runtime verification in the user's local execution environment when required; remote repository inspection is not a substitute for running commands.

## Session closure

After the task is verified and committed:

1. Update `specs/project-state.md`.
2. Record task ID, outcome, commit SHA, focused/regression tests, runtime/Docker evidence, and remaining work.
3. Close/remove the active handoff and identify exactly one next task, including whether it requires separate approval.
4. STOP. Do not start that next task automatically.

If the task cannot be completed, record its actual status, evidence, blockers, and precise next action. Keep the handoff active until verification is genuinely complete.

## Project constraints

- Phase 3 must be verified complete before starting RAG.
- Ollama remains supported for local development.
- The backend remains the authority for business decisions.
- Preserve the existing architecture unless an approved specification explicitly requires a change.
- Keep each session small, reviewable, and suitable for approximately 40 minutes of focused work.
