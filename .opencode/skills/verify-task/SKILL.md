---
name: verify-task
description: Verify and finalize exactly one implementation prepared by the project assistant and recorded as an active handoff in specs/project-state.md.
compatibility: opencode
---

# Verify Task — AI Customer Support Backend

## Objective

This command is exclusively for verifying and finalizing an implementation already prepared by the project assistant. It does not select or implement a new task.

## Required startup sequence

1. Read `specs/project-state.md`.
2. Require one active implementation handoff with a task ID, approved specification reference, base ref, implementation branch, and prepared commit (or equivalent immutable reference).
3. Run `git status --short` and `git log -1 --oneline`. Preserve and report unexpected user changes.
4. Fetch the exact handoff branch and check it out without discarding local work.
5. Confirm the prepared commit is present and inspect the diff against the stated base.
6. Read only the approved specification, task breakdown, relevant implementation, and tests.

If no complete active handoff exists, stop and report what is missing. Do not infer a branch, task, commit, or requirements. Do not fall back to `/next-task`.

## Verification and finalization

1. Check that the implementation and tests remain within the approved task scope.
2. Run the focused tests specified by the handoff.
3. Run the required full regression suite.
4. Run task-specific environment checks recorded in the handoff, including Docker Compose validation, Docker image build, container startup, readiness/health checks, and integration checks where applicable.
5. Verify negative requirements and startup/network boundaries, not only happy paths.
6. Fix defects only when they are clearly within the already-approved task and specification. Do not expand scope or make architecture/specification decisions.
7. Re-run affected focused tests, regression, and relevant runtime checks after any fix.
8. Review the final diff, secrets, configuration, and unrelated changes.
9. Commit the verified result on the same handoff branch.
10. Update `specs/project-state.md` with actual commands, outcomes, test counts, Docker/runtime evidence, final commit, and remaining work. Close the handoff only after all required evidence passes.

## Stop conditions

- If a requirement is ambiguous, a spec conflict appears, or a defect requires scope expansion, stop and report it.
- If Docker/runtime checks cannot run, record the exact blocker and do not mark the task complete.
- Never claim success without actual command output/evidence.
- Never merge a PR unless the project owner explicitly requests it.
- Never start the next task.
- This command must not change the normal `/next-task` workflow.
