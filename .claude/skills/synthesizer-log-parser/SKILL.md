---
name: synthesizer-log-parser
description: Pull raw metrics from Mentor, Architect, Scout, Performance, and Radar outputs plus the tasks/execution_logs tables, for the synthesizer agent to fold into a Daily Briefing. Use only when invoked by the synthesizer agent.
---

Micro-agent skill under the **synthesizer** supervisor
(`.claude/agents/synthesizer.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Reads: `vault/raw/**`, `state/jarvis.db` (`tasks`, `execution_logs`) if it exists.
- Outputs: an in-memory structured summary matching the Daily Briefing field groups (learning, engineering, opportunities, performance, radar) — not the final JSON file itself, that's `synthesizer-state-updater`'s job.
- If a source has no data yet, report the field as missing — never interpolate a plausible number.
- `synthesizer-log-parser`: end with one line — which sources had data vs. were empty — for the supervisor's roll call.
