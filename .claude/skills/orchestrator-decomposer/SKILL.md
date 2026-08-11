---
name: orchestrator-decomposer
description: Break a stated high-level goal into concrete, dated sub-goals ready to become task rows. Use only when invoked by the orchestrator agent.
---

Micro-agent skill under the **orchestrator** supervisor
(`.claude/agents/orchestrator.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Input: a goal string (e.g. "Get a Backend Internship by May") plus the latest Daily Briefing for context.
- Output: a list of sub-goals, each with a title and a deadline, suitable for inserting into the `tasks` table (`id`, `title`, `status='pending'`).
- Sub-goals should be independently verifiable — each needs a concrete definition of done, not a vague aspiration.
- `orchestrator-decomposer`: end with one line — how many sub-goals created — for the supervisor's roll call.
