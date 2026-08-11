---
name: orchestrator-scheduler
description: Allocate time blocks to decomposed sub-goals, adjusted for the Performance team's velocity data and any wellness override. Use only when invoked by the orchestrator agent, after orchestrator-decomposer.
---

Micro-agent skill under the **orchestrator** supervisor
(`.claude/agents/orchestrator.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Input: sub-goals from `orchestrator-decomposer`, latest Daily Briefing's `performance` block.
- If `velocity_delta_pct` is meaningfully negative, rebalance time allocation toward the lagging module before finalizing blocks.
- If the briefing (or a live performance-wellness call) flags burnout risk, insert a rest day first and schedule around it — this is the one case allowed to override the naive plan.
- `orchestrator-scheduler`: end with one line — blocks allocated, and whether a rest-day override fired — for the supervisor's roll call.
