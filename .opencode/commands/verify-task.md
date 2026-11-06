---
description: Verify and finalize one explicitly prepared task handoff
---

Execute the `verify-task` workflow for this repository.

First, load and follow the project skill at `.opencode/skills/verify-task/SKILL.md`. Treat that skill as the authoritative procedure.

The skill is mandatory: do not improvise a different workflow.

Important boundaries:
- Verify only one complete, active implementation handoff recorded in `specs/project-state.md`.
- Do not select, plan, or implement a new task.
- Do not invoke or imitate `/next-task`.
- If there is no complete active handoff, stop immediately and report exactly what handoff information is missing.
- Fetch and inspect only the exact branch and prepared commit named by the handoff.
- Run the specified verification, fix only in-scope defects, record actual evidence, and stop.
- Never merge unless the user explicitly requests it.
