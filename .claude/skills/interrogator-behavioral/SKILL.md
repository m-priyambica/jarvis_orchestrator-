---
name: interrogator-behavioral
description: Ask standard behavioral ("tell me about a time...") questions and check whether answers follow the STAR method. Use only when invoked by the interrogator agent.
---

Micro-agent skill under the **interrogator** supervisor
(`.claude/agents/interrogator.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Grade against Situation, Task, Action, Result explicitly — name which part is missing or weak, don't just give a vague overall impression.
- Push for specifics (numbers, concrete decisions) when an answer stays abstract.
- Log outcome to `vault/raw/interviews/behavioral.md`.
- `interrogator-behavioral`: end with one line — pass/fail and weakest STAR component — for the supervisor's roll call.
