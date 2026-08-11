---
name: performance-analyst
description: Compare planned vs. actual task duration and forecast velocity for the orchestrator. Use only when invoked by the performance agent.
---

Micro-agent skill under the **performance** supervisor
(`.claude/agents/performance.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Read `tasks` and `execution_logs` timing data; compute a concrete delta (e.g. "20% slower than planned on distributed systems module").
- Also watch long-running unpredictable work (fine-tuning, dataset curation) and flag overruns so dependent modules can be reshuffled.
- Never conclude a velocity trend from a single data point — say when there isn't enough history yet.
- `performance-analyst`: end with one line — velocity delta or "insufficient data" — for the supervisor's roll call.
