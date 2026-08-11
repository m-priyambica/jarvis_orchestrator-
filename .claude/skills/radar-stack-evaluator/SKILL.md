---
name: radar-stack-evaluator
description: Compare the user's resume/skills against current market signals and identify concrete gaps. Use only when invoked by the radar agent.
---

Micro-agent skill under the **radar** supervisor
(`.claude/agents/radar.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Input: `vault/wiki/resume.md` plus recent `radar-signal-finder` output.
- State gaps concretely (e.g. "40% increase in Tier-2 AI roles asking for Qdrant instead of just pgvector"), not vaguely.
- When a real gap is found, explicitly hand off a suggested module to the mentor agent — don't just note it and stop.
- `radar-stack-evaluator`: end with one line — gaps found, or "none this round" — for the supervisor's roll call.
