---
name: performance-quantifier
description: Gather hard metrics: coding hours, commit streaks, problems solved, local system telemetry. Use only when invoked by the performance agent.
---

Micro-agent skill under the **performance** supervisor
(`.claude/agents/performance.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Intended sources: WakaTime API, GitHub commit API, LeetCode API (`actions/github_integration.py`), plus `actions/system_monitor.py` for local telemetry.
- GitHub/LeetCode credentials are wired via `.env` (GITHUB_TOKEN/GITHUB_USERNAME/LEETCODE_USERNAME); WakaTime is still unwired (`specs/JARVIS_OS.md` §10) — report what's actually available; say plainly when a source is missing rather than estimating.
- Write raw metrics to `vault/raw/performance/YYYY-MM-DD.json`.
- `performance-quantifier`: end with one line — which metrics were actually available — for the supervisor's roll call.
