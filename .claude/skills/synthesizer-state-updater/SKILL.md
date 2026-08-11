---
name: synthesizer-state-updater
description: Format the log-parser's structured summary into the Daily Briefing JSON contract and persist it to the vault. Use only when invoked by the synthesizer agent, after synthesizer-log-parser.
---

Micro-agent skill under the **synthesizer** supervisor
(`.claude/agents/synthesizer.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Writes: `vault/outputs/briefings/YYYY-MM-DD.json` using the exact schema in `specs/JARVIS_OS.md` §2.1.
- Also appends a short distilled `vault/wiki/` note for anything graph-worthy (new weak topic, burnout flag, notable market signal).
- Idempotent: re-running for the same date overwrites that date's briefing rather than duplicating it.
- `synthesizer-state-updater`: end with one line — where the briefing was written — for the supervisor's roll call.
