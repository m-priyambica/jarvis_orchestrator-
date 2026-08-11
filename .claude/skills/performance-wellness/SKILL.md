---
name: performance-wellness
description: Analyze check-in sentiment and session timing for signs of fatigue or burnout, with authority to force a rest day. Use only when invoked by the performance agent.
---

Micro-agent skill under the **performance** supervisor
(`.claude/agents/performance.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Ground findings in actual check-in text or actual session-timing patterns (e.g. via `actions/proactive.py` data) — never infer burnout from vibes alone.
- If risk is detected, this is the one micro-agent allowed to force a rest day into the schedule ahead of the Orchestrator's normal plan — log the override in `execution_logs` for auditability, never apply it silently.
- State explicitly what evidence triggered the flag.
- `performance-wellness`: end with one line — risk level, and whether the override fired — for the supervisor's roll call.
