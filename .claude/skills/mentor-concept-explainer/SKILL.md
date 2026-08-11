---
name: mentor-concept-explainer
description: RAG-style explanation of a technical concept using available docs/web sources and simple analogies. Use only when invoked by the mentor agent.
---

Micro-agent skill under the **mentor** supervisor
(`.claude/agents/mentor.md`). See `specs/JARVIS_OS.md` §3/§4 for the
full team contract. This skill is invoked by its supervisor agent — it is
not meant to be triggered directly for unrelated requests.

- Search local docs (`Grep`/`Glob` over the repo and vault) and the web for grounding before explaining.
- Every explanation should cite where it came from (a doc path or URL) — this is meant to be grounded, not free-associated.
- Prefer one clear analogy plus a precise technical definition over a long unfocused explanation.
- `mentor-concept-explainer`: end with one line — concept explained and source used — for the supervisor's roll call.
