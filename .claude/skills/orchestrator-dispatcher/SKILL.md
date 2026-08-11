---
name: orchestrator-dispatcher
description: Send the trigger prompt to the correct Domain Supervisor agent for each scheduled block and record the dispatch. Use only when invoked by the orchestrator agent, after orchestrator-scheduler.
---

Micro-agent skill under the **orchestrator** supervisor
(`.claude/agents/orchestrator.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- For each scheduled block, invoke the matching supervisor agent (mentor/architect/scout/brand/interrogator) with the sub-goal as context.
- Record every dispatch as a row in `execution_logs` (`task_id`, `command_run`, `exit_code`, `stdout`, `stderr`).
- Never mark the corresponding `tasks.status` as `done` based on the supervisor's own claim — only on a verified `exit_code == 0` per the Hallucination Loop (`specs/JARVIS_OS.md` §7).
- `orchestrator-dispatcher`: report one line per supervisor dispatched this cycle — your supervisor folds these into its "assemble" roll call.
